from pathlib import Path
from uuid import uuid4

import pytest

from boulder_frame_worker.config import WorkerConfig
from boulder_frame_worker.errors import ErrorCode, WorkerError, terminal, transient
from boulder_frame_worker.protocol import JobTask
from boulder_frame_worker.state import InMemoryJobRepository, JobRecord, JobState
from boulder_frame_worker.worker import Worker


def worker_for(tmp_path: Path) -> tuple[Worker, InMemoryJobRepository, JobTask]:
    record = JobRecord(id=uuid4())
    repository = InMemoryJobRepository([record])
    worker = Worker(WorkerConfig("test", "unconfigured", tmp_path), repository, worker_id="worker")
    return worker, repository, JobTask(record.id, "00000000-0000-0000-0000-000000000042")


def no_op(record: JobRecord, scratch: Path) -> None:
    (scratch / "marker").write_text(record.state)


def test_worker_completes_and_removes_job_scratch(tmp_path: Path) -> None:
    worker, repository, task = worker_for(tmp_path)

    assert worker.process(task, no_op, no_op, no_op, no_op)
    assert repository.get(task.job_id).state is JobState.COMPLETED
    assert not (tmp_path / str(task.job_id)).exists()
    assert not worker.process(task, no_op, no_op, no_op, no_op)


def test_worker_records_terminal_stage_error(tmp_path: Path) -> None:
    worker, repository, task = worker_for(tmp_path)

    def invalid_media(record: JobRecord, scratch: Path) -> None:
        raise terminal(ErrorCode.INVALID_MEDIA, "bad video")

    worker.process(task, invalid_media, no_op, no_op, no_op)
    record = repository.get(task.job_id)
    assert record.state is JobState.FAILED
    assert record.error is not None
    assert record.error.code is ErrorCode.INVALID_MEDIA


def test_worker_leaves_transient_error_for_queue_retry(tmp_path: Path) -> None:
    worker, repository, task = worker_for(tmp_path)

    def unavailable_storage(record: JobRecord, scratch: Path) -> None:
        raise transient(ErrorCode.STORAGE_UNAVAILABLE, "storage temporarily unavailable")

    with pytest.raises(WorkerError) as raised:
        worker.process(task, unavailable_storage, no_op, no_op, no_op)

    assert raised.value.transient
    assert repository.get(task.job_id).state is JobState.VALIDATING
