from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from boulder_frame_worker.repository import (
    DebugAsset,
    DebugNotValidatedError,
    LeaseLostError,
    OutputAsset,
    OutputNotValidatedError,
    PostgresJobRepository,
    ReviewArtifact,
    _record_from_row,
    debug_storage_key,
    output_storage_key,
    review_storage_key,
)
from boulder_frame_worker.state import JobStage, JobState


class FakeCursor:
    def __init__(self, rows: list[tuple[object, ...] | None], rowcount: int = 1) -> None:
        self.rows = rows
        self.rowcount = rowcount
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.calls.append((query, params))

    def fetchone(self) -> tuple[object, ...] | None:
        return self.rows.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def repository(cursor: FakeCursor) -> tuple[PostgresJobRepository, FakeConnection]:
    connection = FakeConnection(cursor)
    return PostgresJobRepository(lambda: connection), connection


def test_claim_hydrates_immutable_configuration_and_source_asset() -> None:
    now = datetime.now(UTC)
    job_id = uuid4()
    source_id = uuid4()
    row = (
        job_id,
        uuid4(),
        source_id,
        "queued",
        "queued",
        0,
        (
            '{"source_asset_id": "'
            + str(source_id)
            + '", "target_selection": {}, "output": {}, "pipeline_version": "p", '
            '"model_version": "m", "planner": {}}'
        ),
        None,
        None,
        now,
        now,
        None,
        "worker-a",
        now + timedelta(seconds=60),
        source_id,
        uuid4(),
        "private/source/test.mp4",
        "uploaded",
        "test.mp4",
        "video/mp4",
        123,
        3840,
        2160,
        30.0,
        1000,
    )
    cursor = FakeCursor([row])
    repo, connection = repository(cursor)

    claimed = repo.claim(job_id, "worker-a", 60, now)

    assert claimed is not None
    assert claimed.configuration is not None
    assert claimed.configuration.source_asset_id == source_id
    assert claimed.source_asset is not None
    assert claimed.source_asset.storage_key == "private/source/test.mp4"
    assert cursor.calls[0][1] == ("worker-a", 60, job_id)
    assert connection.committed and connection.closed


def test_claim_returns_none_when_another_live_lease_exists() -> None:
    cursor = FakeCursor([None])
    repo, _ = repository(cursor)

    assert repo.claim(uuid4(), "worker-b", 60, datetime.now(UTC)) is None


def test_update_rejects_stale_owner_or_expired_lease() -> None:
    cursor = FakeCursor([], rowcount=0)
    repo, _ = repository(cursor)
    record = _record_from_row(_row("validating", "validating", "worker-a"))

    with pytest.raises(LeaseLostError):
        repo.update(record)


def test_terminal_update_clears_lease_in_sql() -> None:
    cursor = FakeCursor([], rowcount=1)
    repo, _ = repository(cursor)
    record = _record_from_row(_row("validating", "validating", "worker-a"))
    record = replace(record, state=JobState.FAILED, stage=JobStage.FAILED)
    repo.update(record)

    query, params = cursor.calls[0]
    assert "lease_owner = CASE" in query
    assert "THEN NULL" in query
    assert "requested.stage = requested.state" in query
    assert params[0] == "failed"


def test_release_clears_a_live_worker_lease() -> None:
    cursor = FakeCursor([], rowcount=1)
    repo, _ = repository(cursor)

    assert repo.release(uuid4(), "worker-a")
    query, params = cursor.calls[0]
    assert "lease_owner = NULL" in query
    assert params[1] == "worker-a"


def test_finalize_output_requires_validated_media_metadata() -> None:
    with pytest.raises(OutputNotValidatedError, match="size"):
        OutputAsset(0, "video/mp4", 1920, 1080, 30.0, 1000)
    with pytest.raises(OutputNotValidatedError, match="video/mp4"):
        OutputAsset(1, "video/quicktime", 1920, 1080, 30.0, 1000)


def test_finalize_output_links_deterministic_asset_and_unique_artifact() -> None:
    asset_id = uuid4()
    cursor = FakeCursor([(asset_id,)])
    repo, connection = repository(cursor)
    record = _record_from_row(_row("uploading", "uploading", "worker-a"))
    assert record.source_asset is not None

    result = repo.finalize_output(record, OutputAsset(123, "video/mp4", 1920, 1080, 30.0, 1000))

    query, params = cursor.calls[0]
    assert result == asset_id
    assert "lease_owner = %s" in query
    assert "lease_expires_at > now()" in query
    assert "ON CONFLICT (storage_key) DO UPDATE" in query
    assert "ON CONFLICT (job_id, kind) DO UPDATE" in query
    assert params[3] == output_storage_key(record.source_asset.project_id, record.id)
    assert connection.committed and connection.closed


def test_finalize_output_rejects_stale_lease_without_writing_asset() -> None:
    cursor = FakeCursor([None])
    repo, _ = repository(cursor)
    record = _record_from_row(_row("uploading", "uploading", "worker-a"))

    with pytest.raises(LeaseLostError):
        repo.finalize_output(record, OutputAsset(123, "video/mp4", 1920, 1080, 30.0, 1000))


def test_finalize_debug_requires_verified_gzip_metadata() -> None:
    with pytest.raises(DebugNotValidatedError, match="size"):
        DebugAsset(0, "application/gzip")
    with pytest.raises(DebugNotValidatedError, match="application/gzip"):
        DebugAsset(1, "application/json")


def test_finalize_debug_links_deterministic_asset_and_unique_artifact() -> None:
    asset_id = uuid4()
    cursor = FakeCursor([(asset_id,)])
    repo, connection = repository(cursor)
    record = _record_from_row(_row("uploading", "uploading", "worker-a"))
    assert record.source_asset is not None

    storage_key = debug_storage_key(record.source_asset.project_id, record.id, uuid4())
    result = repo.finalize_debug(record, storage_key, DebugAsset(123, "application/gzip"))

    query, params = cursor.calls[0]
    assert result == asset_id
    assert "lease_owner = %s" in query
    assert "lease_expires_at > now()" in query
    assert "'debug_telemetry'" in query
    assert "ON CONFLICT (storage_key) DO UPDATE" in query
    assert "ON CONFLICT (job_id, kind) DO UPDATE" in query
    assert params[3] == storage_key
    assert connection.committed and connection.closed


@pytest.mark.parametrize("state", ["queued", "validating", "analyzing", "rendering", "uploading"])
def test_finalize_debug_allows_any_active_job_state(state: str) -> None:
    asset_id = uuid4()
    cursor = FakeCursor([(asset_id,)])
    repo, _ = repository(cursor)
    record = _record_from_row(_row(state, state, "worker-a"))
    assert record.source_asset is not None

    result = repo.finalize_debug(
        record,
        debug_storage_key(record.source_asset.project_id, record.id, uuid4()),
        DebugAsset(123, "application/gzip"),
    )

    assert result == asset_id
    assert "state NOT IN ('completed', 'failed', 'cancelled')" in cursor.calls[0][0]


def test_finalize_debug_rejects_stale_lease_without_writing_asset() -> None:
    cursor = FakeCursor([None])
    repo, _ = repository(cursor)
    record = _record_from_row(_row("uploading", "uploading", "worker-a"))
    assert record.source_asset is not None

    with pytest.raises(LeaseLostError):
        repo.finalize_debug(
            record,
            debug_storage_key(record.source_asset.project_id, record.id, uuid4()),
            DebugAsset(123, "application/gzip"),
        )


@pytest.mark.parametrize("state", ["completed", "failed", "cancelled"])
def test_finalize_debug_rejects_terminal_jobs(state: str) -> None:
    cursor = FakeCursor([])
    repo, _ = repository(cursor)
    record = _record_from_row(_row(state, state, "worker-a"))
    assert record.source_asset is not None

    with pytest.raises(ValueError, match="nonterminal"):
        repo.finalize_debug(
            record,
            debug_storage_key(record.source_asset.project_id, record.id, uuid4()),
            DebugAsset(123, "application/gzip"),
        )

    assert cursor.calls == []


@pytest.mark.parametrize(
    "storage_key",
    [
        "private/debug/not-a-project/not-a-job/not-a-uuid.jsonl.gz",
        "private/debug/{project_id}/{job_id}.jsonl.gz",
        "private/debug/{project_id}/{job_id}/not-a-uuid.jsonl.gz",
        "private/debug/{project_id}/{job_id}/{debug_id}.zip",
    ],
)
def test_finalize_debug_rejects_keys_outside_the_canonical_job_namespace(storage_key: str) -> None:
    cursor = FakeCursor([])
    repo, _ = repository(cursor)
    record = _record_from_row(_row("rendering", "rendering", "worker-a"))
    assert record.source_asset is not None
    key = storage_key.format(
        project_id=record.source_asset.project_id,
        job_id=record.id,
        debug_id=uuid4(),
    )

    with pytest.raises(ValueError, match="debug storage key"):
        repo.finalize_debug(record, key, DebugAsset(123, "application/gzip"))

    assert cursor.calls == []


def test_output_storage_key_is_deterministic_per_project_and_job() -> None:
    project_id = uuid4()
    job_id = uuid4()

    assert output_storage_key(project_id, job_id) == f"private/output/{project_id}/{job_id}.mp4"


def test_debug_storage_key_is_deterministic_per_project_job_and_debug_asset() -> None:
    project_id = uuid4()
    job_id = uuid4()
    debug_id = uuid4()

    assert (
        debug_storage_key(project_id, job_id, debug_id)
        == f"private/debug/{project_id}/{job_id}/{debug_id}.jsonl.gz"
    )


def test_finalize_review_links_canonical_scoped_artifacts_atomically() -> None:
    cursor = FakeCursor([(2,)])
    repo, connection = repository(cursor)
    record = _record_from_row(_row("uploading", "uploading", "worker-a"))
    assert record.source_asset is not None
    review_id = uuid4()
    artifacts = (
        ReviewArtifact(
            "debug_telemetry",
            review_storage_key(
                record.source_asset.project_id, record.id, review_id, "telemetry.jsonl.gz"
            ),
            123,
            "application/gzip",
        ),
        ReviewArtifact(
            "debug_manifest",
            review_storage_key(
                record.source_asset.project_id, record.id, review_id, "manifest.json"
            ),
            456,
            "application/json",
        ),
    )

    repo.finalize_review(record, review_id, artifacts)

    query, params = cursor.calls[0]
    assert "jsonb_to_recordset" in query
    assert "ON CONFLICT (job_id, kind) DO UPDATE" in query
    assert "removed_review_artifacts" in query
    assert "kind NOT IN (SELECT role FROM artifact_input)" in query
    assert "lease_expires_at > now()" in query
    assert {item["role"] for item in json.loads(params[3])} == {
        "debug_telemetry",
        "debug_manifest",
    }
    assert connection.committed and connection.closed


def test_finalize_review_retry_with_fewer_artifacts_removes_stale_phase_roles() -> None:
    cursor = FakeCursor([(5,), (2,)])
    repo, _ = repository(cursor)
    record = _record_from_row(_row("uploading", "uploading", "worker-a"))
    assert record.source_asset is not None
    full_review, partial_review = uuid4(), uuid4()
    full = tuple(
        ReviewArtifact(
            role,
            review_storage_key(record.source_asset.project_id, record.id, full_review, name),
            10,
            content_type,
        )
        for role, name, content_type in (
            ("debug_telemetry", "telemetry.jsonl.gz", "application/gzip"),
            ("debug_manifest", "manifest.json", "application/json"),
            ("debug_detection", "detection.mp4", "video/mp4"),
            ("debug_framing", "framing.mp4", "video/mp4"),
            ("debug_render", "render.mp4", "video/mp4"),
        )
    )
    partial = tuple(
        ReviewArtifact(
            role,
            review_storage_key(record.source_asset.project_id, record.id, partial_review, name),
            10,
            content_type,
        )
        for role, name, content_type in (
            ("debug_telemetry", "telemetry.jsonl.gz", "application/gzip"),
            ("debug_manifest", "manifest.json", "application/json"),
        )
    )

    repo.finalize_review(record, full_review, full)
    repo.finalize_review(record, partial_review, partial)

    query, params = cursor.calls[1]
    assert "DELETE FROM job_artifacts" in query
    assert "debug_render" in query
    assert {item["role"] for item in json.loads(params[3])} == {
        "debug_telemetry",
        "debug_manifest",
    }


def test_finalize_review_rejects_missing_manifest_or_invalid_scope() -> None:
    cursor = FakeCursor([])
    repo, _ = repository(cursor)
    record = _record_from_row(_row("uploading", "uploading", "worker-a"))
    assert record.source_asset is not None
    review_id = uuid4()
    telemetry = ReviewArtifact(
        "debug_telemetry",
        review_storage_key(
            record.source_asset.project_id, record.id, review_id, "telemetry.jsonl.gz"
        ),
        123,
        "application/gzip",
    )

    with pytest.raises(ValueError, match="telemetry and manifest"):
        repo.finalize_review(record, review_id, (telemetry,))
    assert cursor.calls == []


def _row(state: str, stage: str, owner: str) -> tuple[object, ...]:
    now = datetime.now(UTC)
    job_id = uuid4()
    source_id = uuid4()
    return (
        job_id,
        uuid4(),
        source_id,
        state,
        stage,
        10,
        {
            "source_asset_id": str(source_id),
            "target_selection": {},
            "output": {},
            "pipeline_version": "p",
            "model_version": "m",
            "planner": {},
        },
        None,
        None,
        now,
        now,
        None,
        owner,
        now + timedelta(seconds=60),
        source_id,
        uuid4(),
        "private/source/test.mp4",
        "uploaded",
        "test.mp4",
        "video/mp4",
        123,
        3840,
        2160,
        30.0,
        1000,
    )
