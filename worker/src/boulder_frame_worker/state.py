"""Retry-safe state transition guards and a testable repository protocol."""

from __future__ import annotations

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


class JobRepository(Protocol):
    def claim(
        self, job_id: UUID, worker_id: str, lease_seconds: int, now: datetime
    ) -> JobRecord | None: ...

    def update(self, record: JobRecord) -> None: ...


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
        )
        self.records[job_id] = claimed
        return claimed

    def update(self, record: JobRecord) -> None:
        self.records[record.id] = record

    def get(self, job_id: UUID) -> JobRecord:
        return self.records[job_id]


def utc_now() -> datetime:
    return datetime.now(UTC)
