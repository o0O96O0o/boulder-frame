from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from .errors import ErrorCode, WorkerError
from .state import JobConfiguration, JobRecord, JobStage, JobState, SourceAsset


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...]) -> None: ...

    def fetchone(self) -> tuple[Any, ...] | None: ...

    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class LeaseLostError(RuntimeError):
    """Raised when a worker no longer owns a current database lease."""


class OutputNotValidatedError(ValueError):
    """Raised when finalization is requested without a verified media object."""


@dataclass(frozen=True, slots=True)
class OutputAsset:
    size_bytes: int
    content_type: str
    width: int
    height: int
    frame_rate: float
    duration_ms: int

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise OutputNotValidatedError("output asset size must be greater than zero")
        if self.content_type != "video/mp4":
            raise OutputNotValidatedError("output asset must be video/mp4")
        if self.width <= 0 or self.height <= 0 or self.frame_rate <= 0 or self.duration_ms <= 0:
            raise OutputNotValidatedError("output asset media metadata must be positive")


class PostgresJobRepository:
    """Durable worker repository using PostgreSQL as the job ownership authority."""

    def __init__(self, connection_factory: Callable[[], Connection]) -> None:
        self._connection_factory = connection_factory

    def claim(
        self, job_id: UUID, worker_id: str, lease_seconds: int, now: datetime
    ) -> JobRecord | None:
        del now  # PostgreSQL's clock makes lease arbitration consistent across workers.
        return self._returning(
            _CLAIM_SQL,
            (worker_id, lease_seconds, job_id),
            missing_ok=True,
        )

    def renew(self, job_id: UUID, worker_id: str, lease_seconds: int) -> bool:
        return self._execute(_RENEW_SQL, (lease_seconds, job_id, worker_id)) == 1

    def release(self, job_id: UUID, worker_id: str) -> bool:
        return self._execute(_RELEASE_SQL, (job_id, worker_id)) == 1

    def current_state(self, job_id: UUID) -> JobState | None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(_CURRENT_STATE_SQL, (job_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()
            connection.close()
        return None if row is None else JobState(str(row[0]))

    def ready(self) -> None:
        self._execute("SELECT 1", ())

    def update(self, record: JobRecord) -> None:
        if record.lease_owner is None:
            raise LeaseLostError("job update requires a worker lease owner")
        error_code = record.error.code.value if record.error else None
        error_message = record.error.message if record.error else None
        updated = self._execute(
            _UPDATE_SQL,
            (
                record.state.value,
                record.stage.value,
                record.progress,
                error_code,
                error_message,
                record.id,
                record.lease_owner,
            ),
        )
        if updated != 1:
            raise LeaseLostError("job state was changed, cancelled, or lease expired")

    def finalize_output(self, record: JobRecord, output: OutputAsset) -> UUID:
        """Link a verified deterministic output object while the current lease remains live."""
        if record.lease_owner is None or record.source_asset is None:
            raise LeaseLostError("output finalization requires a claimed job with a source asset")
        if record.state is not JobState.UPLOADING:
            raise ValueError("output finalization requires the uploading state")
        storage_key = output_storage_key(record.source_asset.project_id, record.id)
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                _FINALIZE_OUTPUT_SQL,
                (
                    record.id,
                    record.source_asset.project_id,
                    record.lease_owner,
                    storage_key,
                    output.content_type,
                    output.size_bytes,
                    output.width,
                    output.height,
                    output.frame_rate,
                    output.duration_ms,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
        if row is None:
            raise LeaseLostError("job state was changed, cancelled, or lease expired")
        return _uuid(row[0])

    def _returning(
        self, query: str, params: tuple[object, ...], *, missing_ok: bool
    ) -> JobRecord | None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            row = cursor.fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
        if row is None:
            if missing_ok:
                return None
            raise LeaseLostError("job was not updated")
        return _record_from_row(row)

    def _execute(self, query: str, params: tuple[object, ...]) -> int:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            updated = getattr(cursor, "rowcount", -1)
            connection.commit()
            return int(updated)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()


_RETURNING_COLUMNS = """
    jobs.id, jobs.project_id, jobs.source_asset_id, jobs.state, jobs.stage, jobs.progress,
    jobs.configuration, jobs.error_code, jobs.error_message, jobs.created_at, jobs.started_at,
    jobs.completed_at, jobs.lease_owner, jobs.lease_expires_at, assets.id, assets.project_id,
    assets.storage_key, assets.upload_state, assets.filename, assets.content_type,
    assets.size_bytes,
    assets.width, assets.height, assets.frame_rate, assets.duration_ms
"""

_CLAIM_SQL = f"""
UPDATE processing_jobs AS jobs
SET lease_owner = %s,
    lease_expires_at = now() + (%s * interval '1 second'),
    started_at = COALESCE(jobs.started_at, now())
FROM assets
WHERE jobs.id = %s
  AND jobs.source_asset_id = assets.id
  AND jobs.state NOT IN ('completed', 'failed', 'cancelled')
  AND (jobs.lease_expires_at IS NULL OR jobs.lease_expires_at <= now())
RETURNING {_RETURNING_COLUMNS}
"""

_RENEW_SQL = """
UPDATE processing_jobs
SET lease_expires_at = now() + (%s * interval '1 second')
WHERE id = %s
  AND lease_owner = %s
  AND lease_expires_at > now()
  AND state NOT IN ('completed', 'failed', 'cancelled')
"""

_RELEASE_SQL = """
UPDATE processing_jobs
SET lease_owner = NULL,
    lease_expires_at = NULL
WHERE id = %s
  AND lease_owner = %s
  AND state NOT IN ('completed', 'failed', 'cancelled')
"""

_CURRENT_STATE_SQL = "SELECT state FROM processing_jobs WHERE id = %s"

_UPDATE_SQL = """
WITH requested AS (
  SELECT %s::text AS state, %s::text AS stage, %s::integer AS progress,
         %s::text AS error_code, %s::text AS error_message
)
UPDATE processing_jobs AS jobs
SET state = requested.state,
    stage = requested.stage,
    progress = requested.progress,
    error_code = requested.error_code,
    error_message = requested.error_message,
    completed_at = CASE
      WHEN requested.state IN ('completed', 'failed', 'cancelled') THEN now()
      ELSE jobs.completed_at
    END,
    lease_owner = CASE
      WHEN requested.state IN ('completed', 'failed', 'cancelled') THEN NULL
      ELSE jobs.lease_owner
    END,
    lease_expires_at = CASE
      WHEN requested.state IN ('completed', 'failed', 'cancelled') THEN NULL
      ELSE jobs.lease_expires_at
    END
FROM requested
WHERE jobs.id = %s
  AND jobs.lease_owner = %s
  AND jobs.lease_expires_at > now()
  AND jobs.state <> 'cancelled'
  AND jobs.progress <= requested.progress
  AND (requested.state <> 'completed' OR requested.progress = 100)
  AND requested.stage = requested.state
  AND (
    (jobs.state = 'queued' AND requested.state = 'validating') OR
    (jobs.state = 'validating' AND requested.state IN ('validating', 'analyzing', 'failed')) OR
    (jobs.state = 'analyzing' AND requested.state IN ('analyzing', 'rendering', 'failed')) OR
    (jobs.state = 'rendering' AND requested.state IN ('rendering', 'uploading', 'failed')) OR
    (jobs.state = 'uploading' AND requested.state IN ('uploading', 'completed', 'failed'))
  )
"""

_FINALIZE_OUTPUT_SQL = """
WITH owned_job AS (
  SELECT id, project_id
  FROM processing_jobs
  WHERE id = %s
    AND project_id = %s
    AND state = 'uploading'
    AND lease_owner = %s
    AND lease_expires_at > now()
), output_asset AS (
  INSERT INTO assets (
    project_id, kind, storage_key, upload_state, content_type, size_bytes,
    width, height, frame_rate, duration_ms
  )
  SELECT project_id, 'output', %s, 'uploaded', %s, %s, %s, %s, %s, %s
  FROM owned_job
  ON CONFLICT (storage_key) DO UPDATE
  SET content_type = EXCLUDED.content_type,
      size_bytes = EXCLUDED.size_bytes,
      width = EXCLUDED.width,
      height = EXCLUDED.height,
      frame_rate = EXCLUDED.frame_rate,
      duration_ms = EXCLUDED.duration_ms
  WHERE assets.project_id = EXCLUDED.project_id
    AND assets.kind = 'output'
    AND assets.upload_state = 'uploaded'
  RETURNING id
), output_artifact AS (
  INSERT INTO job_artifacts (job_id, asset_id, kind)
  SELECT owned_job.id, output_asset.id, 'output'
  FROM owned_job
  JOIN output_asset ON true
  ON CONFLICT (job_id, kind) DO UPDATE
  SET asset_id = EXCLUDED.asset_id
  RETURNING asset_id
)
UPDATE processing_jobs AS jobs
SET output_asset_id = output_artifact.asset_id
FROM owned_job, output_artifact
WHERE jobs.id = owned_job.id
RETURNING output_artifact.asset_id
"""


def output_storage_key(project_id: UUID, job_id: UUID) -> str:
    return f"private/output/{project_id}/{job_id}.mp4"


def _record_from_row(row: tuple[Any, ...]) -> JobRecord:
    configuration = _configuration(row[6])
    error = None
    if row[7] is not None:
        error = WorkerError(ErrorCode(row[7]), str(row[8]), transient=False)
    return JobRecord(
        id=_uuid(row[0]),
        state=JobState(row[3]),
        stage=JobStage(row[4]),
        progress=int(row[5]),
        configuration=configuration,
        error=error,
        started_at=_datetime(row[10]),
        completed_at=_datetime(row[11]),
        lease_owner=row[12],
        lease_expires_at=_datetime(row[13]),
        source_asset=SourceAsset(
            id=_uuid(row[14]),
            project_id=_uuid(row[15]),
            storage_key=str(row[16]),
            upload_state=str(row[17]),
            filename=row[18],
            content_type=row[19],
            size_bytes=int(row[20]),
            width=row[21],
            height=row[22],
            frame_rate=row[23],
            duration_ms=row[24],
        ),
    )


def _configuration(value: object) -> JobConfiguration:
    raw = json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value
    if not isinstance(raw, Mapping):
        raise ValueError("job configuration must be a JSON object")
    return JobConfiguration(
        source_asset_id=_uuid(raw["source_asset_id"]),
        target_selection=_mapping(raw["target_selection"]),
        output=_mapping(raw["output"]),
        pipeline_version=str(raw["pipeline_version"]),
        model_version=str(raw["model_version"]),
        planner=_mapping(raw["planner"]),
    )


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("job configuration section must be a JSON object")
    return dict(value)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value)).astimezone(UTC)
