from uuid import uuid4

from boulder_frame_worker.config import WorkerConfig
from boulder_frame_worker.errors import ErrorCode
from boulder_frame_worker.protocol import JobTask
from boulder_frame_worker.queue_adapter import DeliveryAction
from boulder_frame_worker.runtime import UnavailablePipeline, compose_runtime
from boulder_frame_worker.state import InMemoryJobRepository, JobRecord, JobState, utc_now


def test_unavailable_pipeline_persists_safe_terminal_error(tmp_path) -> None:
    record = JobRecord(uuid4())
    repository = InMemoryJobRepository([record])
    pipeline = UnavailablePipeline(repository, lease_seconds=30, worker_id="worker")

    assert pipeline(JobTask(record.id, "00000000-0000-0000-0000-000000000042"))
    result = repository.get(record.id)
    assert result.state is JobState.FAILED
    assert result.error is not None
    assert result.error.code is ErrorCode.MODEL_UNAVAILABLE
    assert result.error.message == "Video processing is temporarily unavailable."
    assert not (tmp_path / str(record.id)).exists()


def test_unavailable_pipeline_keeps_live_lease_delivery_pending() -> None:
    record = JobRecord(uuid4())
    repository = InMemoryJobRepository([record])
    assert repository.claim(record.id, "other-worker", 30, utc_now()) is not None
    pipeline = UnavailablePipeline(repository, lease_seconds=30, worker_id="worker")

    outcome = pipeline(JobTask(record.id, "00000000-0000-0000-0000-000000000042"))

    assert outcome is DeliveryAction.RETRY


def test_runtime_requires_configured_runtime_identity() -> None:
    config = WorkerConfig.from_mapping(
        {
            "database_url": "postgresql://user:secret@db/app",
            "redis_url": "redis://:secret@redis/0",
            "worker_id": "worker-1",
        }
    )
    assert config.stream_consumer == "worker-1"


class FakeTransport:
    def ready(self) -> None:
        return None

    def serve(self, handler, stop, concurrency) -> None:
        assert concurrency == 1

    def close(self) -> None:
        return None


def test_runtime_composes_injected_adapters() -> None:
    record = JobRecord(uuid4())
    repository = InMemoryJobRepository([record])
    config = WorkerConfig.from_mapping(
        {
            "database_url": "postgresql://db/app",
            "redis_url": "redis://redis/0",
            "worker_id": "worker-1",
        }
    )

    runtime = compose_runtime(config, repository, FakeTransport())
    runtime.ready()
    assert runtime.capabilities.queue_adapter
    assert runtime.capabilities.database_adapter
    runtime.serve()
    runtime.close()
