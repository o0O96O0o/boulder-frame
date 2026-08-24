import json
import logging
import time
from pathlib import Path
from uuid import uuid4

import pytest

from boulder_frame_worker.config import WorkerConfig
from boulder_frame_worker.errors import ErrorCode, WorkerError, terminal, transient
from boulder_frame_worker.protocol import JobTask
from boulder_frame_worker.queue_adapter import DeliveryAction
from boulder_frame_worker.state import InMemoryJobRepository, JobConfiguration, JobRecord, JobState
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
    assert worker.process(task, no_op, no_op, no_op, no_op) is DeliveryAction.ACK


def test_worker_acknowledges_duplicate_missing_or_terminal_delivery(tmp_path: Path) -> None:
    worker, repository, task = worker_for(tmp_path)

    assert worker.process(task, no_op, no_op, no_op, no_op)
    assert worker.process(task, no_op, no_op, no_op, no_op) is DeliveryAction.ACK
    del repository.records[task.job_id]
    assert worker.process(task, no_op, no_op, no_op, no_op) is DeliveryAction.ACK


def test_worker_records_terminal_stage_error(tmp_path: Path) -> None:
    worker, repository, task = worker_for(tmp_path)

    def invalid_media(record: JobRecord, scratch: Path) -> None:
        raise terminal(ErrorCode.INVALID_MEDIA, "bad video")

    worker.process(task, invalid_media, no_op, no_op, no_op)
    record = repository.get(task.job_id)
    assert record.state is JobState.FAILED
    assert record.error is not None
    assert record.error.code is ErrorCode.INVALID_MEDIA


def test_worker_publishes_failed_stage_telemetry_before_terminal_transition(tmp_path: Path) -> None:
    record = JobRecord(id=uuid4())
    repository = InMemoryJobRepository([record])
    worker = Worker(
        WorkerConfig("test", "unconfigured", tmp_path, debug_capture=True),
        repository,
        worker_id="worker",
    )
    task = JobTask(record.id, "00000000-0000-0000-0000-000000000042")
    captured: list[dict[str, object]] = []

    def failing_stage(record: JobRecord, scratch: Path) -> None:
        del record, scratch
        raise terminal(ErrorCode.INVALID_MEDIA, "bad video")

    def publish(record: JobRecord, scratch: Path) -> None:
        assert record.state is JobState.VALIDATING
        captured.extend(
            json.loads(line) for line in (scratch / "debug-stages.jsonl").read_text().splitlines()
        )

    assert worker.process(task, failing_stage, no_op, no_op, no_op, publish)

    assert captured[-1]["record_type"] == "stage_end"
    assert captured[-1]["outcome"] == "failed"
    assert captured[-1]["error_code"] == ErrorCode.INVALID_MEDIA.value


def test_worker_rejects_a_job_with_a_different_immutable_model_version(tmp_path: Path) -> None:
    record = JobRecord(
        id=uuid4(),
        configuration=JobConfiguration(
            uuid4(),
            {},
            {},
            "test",
            "another-model",
            {},
        ),
    )
    repository = InMemoryJobRepository([record])
    worker = Worker(WorkerConfig("test", "active-model", tmp_path), repository, worker_id="worker")
    task = JobTask(record.id, "00000000-0000-0000-0000-000000000042")
    invoked: list[JobState] = []

    def unexpected_stage(record: JobRecord, scratch: Path) -> None:
        del scratch
        invoked.append(record.state)

    assert worker.process(
        task, unexpected_stage, unexpected_stage, unexpected_stage, unexpected_stage
    )
    failed = repository.get(task.job_id)
    assert failed.state is JobState.FAILED
    assert failed.error is not None and failed.error.code is ErrorCode.MODEL_UNAVAILABLE
    assert invoked == []


@pytest.mark.parametrize("stage", ["analyzing", "rendering", "uploading"])
def test_worker_records_terminal_error_from_each_later_stage(tmp_path: Path, stage: str) -> None:
    worker, repository, task = worker_for(tmp_path)

    def failed_stage(record: JobRecord, scratch: Path) -> None:
        raise terminal(ErrorCode.INVALID_OUTPUT, "bad output")

    handlers = {
        "validating": no_op,
        "analyzing": no_op,
        "rendering": no_op,
        "uploading": no_op,
    }
    handlers[stage] = failed_stage

    assert worker.process(task, **handlers)
    record = repository.get(task.job_id)
    assert record.state is JobState.FAILED
    assert record.error is not None and record.error.code is ErrorCode.INVALID_OUTPUT


def test_worker_leaves_transient_error_for_queue_retry(tmp_path: Path) -> None:
    worker, repository, task = worker_for(tmp_path)

    def unavailable_storage(record: JobRecord, scratch: Path) -> None:
        raise transient(ErrorCode.STORAGE_UNAVAILABLE, "storage temporarily unavailable")

    with pytest.raises(WorkerError) as raised:
        worker.process(task, unavailable_storage, no_op, no_op, no_op)

    assert raised.value.transient
    assert repository.get(task.job_id).state is JobState.VALIDATING
    assert repository.get(task.job_id).lease_owner is None


def test_worker_reclaims_stale_scratch_before_retry(tmp_path: Path) -> None:
    worker, repository, task = worker_for(tmp_path)
    stale = tmp_path / str(task.job_id)
    stale.mkdir()
    (stale / "partial-output").write_text("stale")

    assert worker.process(task, no_op, no_op, no_op, no_op)

    assert repository.get(task.job_id).state is JobState.COMPLETED
    assert not stale.exists()


def test_worker_records_all_phase_timings_before_publishing_debug_bundle(tmp_path: Path) -> None:
    record = JobRecord(id=uuid4())
    repository = InMemoryJobRepository([record])
    worker = Worker(
        WorkerConfig("test", "unconfigured", tmp_path, debug_capture=True),
        repository,
        worker_id="worker",
    )
    task = JobTask(record.id, "00000000-0000-0000-0000-000000000042")
    captured: list[dict[str, object]] = []

    def publish(record: JobRecord, scratch: Path) -> None:
        del record
        captured.extend(
            json.loads(line) for line in (scratch / "debug-stages.jsonl").read_text().splitlines()
        )

    assert worker.process(task, no_op, no_op, no_op, no_op, publish)

    assert [record["record_type"] for record in captured] == [
        "stage_start",
        "stage_end",
    ] * 4
    assert [record["stage"] for record in captured if record["record_type"] == "stage_end"] == [
        "validating",
        "analyzing",
        "rendering",
        "uploading",
    ]
    assert all(record["duration_ms"] >= 0 for record in captured if "duration_ms" in record)


def test_worker_logs_debug_publish_failure_without_failing_the_job(tmp_path: Path) -> None:
    class LogRecords(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.records: list[logging.LogRecord] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.records.append(record)

    record = JobRecord(id=uuid4())
    repository = InMemoryJobRepository([record])
    worker = Worker(
        WorkerConfig("test", "unconfigured", tmp_path, debug_capture=True),
        repository,
        worker_id="worker",
    )
    task = JobTask(record.id, "00000000-0000-0000-0000-000000000042")
    logs = LogRecords()
    worker.logger.addHandler(logs)

    def failed_publish(record: JobRecord, scratch: Path) -> None:
        del record, scratch
        raise OSError("debug bucket is unavailable")

    try:
        assert worker.process(task, no_op, no_op, no_op, no_op, failed_publish)
    finally:
        worker.logger.removeHandler(logs)

    warning = next(record for record in logs.records if record.msg == "debug review publish failed")
    assert warning.job_id == str(task.job_id)
    assert warning.exc_info is not None
    assert repository.get(task.job_id).state is JobState.COMPLETED


def test_worker_heartbeats_database_lease_during_a_stage(tmp_path: Path) -> None:
    class HeartbeatRepository(InMemoryJobRepository):
        def __init__(self, records: list[JobRecord]) -> None:
            super().__init__(records)
            self.renewals = 0

        def renew(self, job_id, worker_id, lease_seconds):
            self.renewals += 1
            return super().renew(job_id, worker_id, lease_seconds)

    record = JobRecord(id=uuid4())
    repository = HeartbeatRepository([record])
    config = WorkerConfig(
        "test",
        "unconfigured",
        tmp_path,
        lease_seconds=2,
        heartbeat_seconds=1,
    )
    worker = Worker(config, repository, worker_id="worker")
    task = JobTask(record.id, "00000000-0000-0000-0000-000000000042")

    def slow_stage(record: JobRecord, scratch: Path) -> None:
        time.sleep(1.05)

    assert worker.process(task, slow_stage, no_op, no_op, no_op)
    assert repository.renewals >= 1
