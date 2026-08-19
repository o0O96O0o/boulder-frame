from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from boulder_frame_worker.repository import LeaseLostError, PostgresJobRepository, _record_from_row
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
