from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from boulder_frame_worker.errors import ErrorCode, terminal
from boulder_frame_worker.state import (
    InMemoryJobRepository,
    JobRecord,
    JobStage,
    JobState,
    fail,
    transition,
)


def test_valid_state_transitions_are_monotonic() -> None:
    record = JobRecord(id=uuid4())
    record = transition(record, JobState.VALIDATING, 10)
    record = transition(record, JobState.ANALYZING, 45)

    assert record.state is JobState.ANALYZING
    assert record.progress == 45


def test_invalid_state_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid job transition"):
        transition(JobRecord(id=uuid4()), JobState.COMPLETED, 100)


def test_terminal_error_and_duplicate_claim_are_safe() -> None:
    record = JobRecord(id=uuid4())
    repository = InMemoryJobRepository([record])
    now = datetime.now(UTC)

    claimed = repository.claim(record.id, "first", 60, now)
    assert claimed is not None
    assert repository.claim(record.id, "second", 60, now) is None

    validating = transition(claimed, JobState.VALIDATING, 10)
    repository.update(validating)
    failed = fail(validating, terminal(ErrorCode.INVALID_MEDIA, "bad video"))
    repository.update(failed)
    assert repository.get(record.id).lease_owner is None
    assert repository.claim(record.id, "third", 60, now + timedelta(seconds=61)) is None


def test_update_rejects_stale_owner_and_decreasing_progress() -> None:
    record = JobRecord(id=uuid4())
    repository = InMemoryJobRepository([record])
    claimed = repository.claim(record.id, "worker", 60, datetime.now(UTC))
    assert claimed is not None

    with pytest.raises(ValueError, match="lease"):
        repository.update(replace(claimed, lease_owner="other"))

    with pytest.raises(ValueError, match="stage"):
        repository.update(replace(claimed, stage=JobStage.VALIDATING))


def test_release_makes_transient_retry_immediately_claimable() -> None:
    record = JobRecord(id=uuid4())
    repository = InMemoryJobRepository([record])
    now = datetime.now(UTC)
    assert repository.claim(record.id, "worker-a", 60, now) is not None

    assert repository.release(record.id, "worker-a")
    assert repository.claim(record.id, "worker-b", 60, now) is not None
