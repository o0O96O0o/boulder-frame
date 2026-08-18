from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from boulder_frame_worker.errors import ErrorCode, terminal
from boulder_frame_worker.state import (
    InMemoryJobRepository,
    JobRecord,
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

    failed = fail(claimed, terminal(ErrorCode.INVALID_MEDIA, "bad video"))
    repository.update(failed)
    assert repository.claim(record.id, "third", 60, now + timedelta(seconds=61)) is None
