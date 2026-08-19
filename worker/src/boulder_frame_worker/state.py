"""Retry-safe state transition guards and a testable repository protocol."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from .errors import WorkerError


class JobState(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    RENDERING = "rendering"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    RENDERING = "rendering"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class JobConfiguration:
    source_asset_id: UUID
    target_selection: Mapping[str, object]
    output: Mapping[str, object]
    pipeline_version: str
    model_version: str
    planner: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SourceAsset:
    id: UUID
    project_id: UUID
    storage_key: str
    upload_state: str
    filename: str | None
    content_type: str | None
    size_bytes: int
    width: int | None
    height: int | None
    frame_rate: float | None
    duration_ms: int | None


TERMINAL_STATES = frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED})
_ALLOWED_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.VALIDATING, JobState.CANCELLED}),
    JobState.VALIDATING: frozenset({JobState.ANALYZING, JobState.FAILED}),
    JobState.ANALYZING: frozenset({JobState.RENDERING, JobState.FAILED}),
    JobState.RENDERING: frozenset({JobState.UPLOADING, JobState.FAILED}),
    JobState.UPLOADING: frozenset({JobState.COMPLETED, JobState.FAILED}),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: UUID
    state: JobState = JobState.QUEUED
    stage: JobStage = JobStage.QUEUED
    progress: int = 0
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    error: WorkerError | None = None
    configuration: JobConfiguration | None = None
    source_asset: SourceAsset | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobRepository(Protocol):
    def claim(
        self, job_id: UUID, worker_id: str, lease_seconds: int, now: datetime
    ) -> JobRecord | None: ...

    def update(self, record: JobRecord) -> None: ...

    def renew(self, job_id: UUID, worker_id: str, lease_seconds: int) -> bool: ...

    def release(self, job_id: UUID, worker_id: str) -> bool: ...

    def current_state(self, job_id: UUID) -> JobState | None: ...


def transition(record: JobRecord, next_state: JobState, progress: int) -> JobRecord:
    if next_state not in _ALLOWED_TRANSITIONS[record.state]:
        raise ValueError(f"invalid job transition {record.state} -> {next_state}")
    if progress < record.progress or not 0 <= progress <= 100:
        raise ValueError("job progress must be monotonic and between 0 and 100")
    stage = JobStage(next_state.value)
    if next_state is JobState.COMPLETED and progress != 100:
        raise ValueError("completed jobs must have 100 progress")
    return replace(record, state=next_state, stage=stage, progress=progress)


def fail(record: JobRecord, error: WorkerError) -> JobRecord:
    if record.state in TERMINAL_STATES:
        raise ValueError("cannot fail a terminal job")
    return replace(record, state=JobState.FAILED, stage=JobStage.FAILED, error=error)


class InMemoryJobRepository:
    """Reference claim semantics; a PostgreSQL adapter must make claim atomic."""

    def __init__(self, records: list[JobRecord]) -> None:
        self.records = {record.id: record for record in records}

    def claim(
        self, job_id: UUID, worker_id: str, lease_seconds: int, now: datetime
    ) -> JobRecord | None:
        record = self.records.get(job_id)
        if record is None or record.state in TERMINAL_STATES:
            return None
        lease_available = record.lease_expires_at is None or record.lease_expires_at <= now
        if not lease_available:
            return None
        claimed = replace(
            record,
            lease_owner=worker_id,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            started_at=record.started_at or now,
        )
        self.records[job_id] = claimed
        return claimed

    def update(self, record: JobRecord) -> None:
        current = self.records.get(record.id)
        now = utc_now()
        if (
            current is None
            or current.state in TERMINAL_STATES
            or current.lease_owner != record.lease_owner
            or current.lease_expires_at is None
            or current.lease_expires_at <= now
        ):
            raise ValueError("job lease is not owned by this worker")
        if record.progress < current.progress or not 0 <= record.progress <= 100:
            raise ValueError("job progress must be monotonic and between 0 and 100")
        if record.state is JobState.COMPLETED and record.progress != 100:
            raise ValueError("completed jobs must have 100 progress")
        if record.stage.value != record.state.value:
            raise ValueError("job stage must match its state")
        if (
            record.state is not current.state
            and record.state not in _ALLOWED_TRANSITIONS[current.state]
        ):
            raise ValueError(f"invalid job transition {current.state} -> {record.state}")
        if record.state in TERMINAL_STATES:
            record = replace(record, lease_owner=None, lease_expires_at=None, completed_at=now)
        self.records[record.id] = record

    def renew(self, job_id: UUID, worker_id: str, lease_seconds: int) -> bool:
        record = self.records.get(job_id)
        now = utc_now()
        if (
            record is None
            or record.state in TERMINAL_STATES
            or record.lease_owner != worker_id
            or record.lease_expires_at is None
            or record.lease_expires_at <= now
        ):
            return False
        self.records[job_id] = replace(
            record, lease_expires_at=now + timedelta(seconds=lease_seconds)
        )
        return True

    def release(self, job_id: UUID, worker_id: str) -> bool:
        record = self.records.get(job_id)
        if record is None or record.state in TERMINAL_STATES or record.lease_owner != worker_id:
            return False
        self.records[job_id] = replace(record, lease_owner=None, lease_expires_at=None)
        return True

    def current_state(self, job_id: UUID) -> JobState | None:
        record = self.records.get(job_id)
        return None if record is None else record.state

    def get(self, job_id: UUID) -> JobRecord:
        return self.records[job_id]


def utc_now() -> datetime:
    return datetime.now(UTC)
