from __future__ import annotations

from dataclasses import dataclass
from threading import Event

from .config import WorkerConfig
from .errors import ErrorCode, terminal
from .protocol import JobTask
from .queue_adapter import (
    DeliveryAction,
    QueueConsumerAdapter,
    QueueTransport,
    RedisStreamsTransport,
)
from .repository import PostgresJobRepository
from .state import TERMINAL_STATES, JobRepository, JobState, fail, transition, utc_now


class RuntimeUnavailable(RuntimeError):
    """Configured worker adapters could not be constructed or verified."""


class UnavailablePipeline:
    """Marks claimed jobs unavailable without creating scratch or output artifacts."""

    def __init__(
        self, repository: JobRepository, lease_seconds: int, worker_id: str | None = None
    ) -> None:
        self.repository = repository
        self.lease_seconds = lease_seconds
        self.worker_id = worker_id or ""

    def __call__(self, task: JobTask) -> DeliveryAction:
        record = self.repository.claim(task.job_id, self.worker_id, self.lease_seconds, utc_now())
        if record is None:
            state = self.repository.current_state(task.job_id)
            return (
                DeliveryAction.ACK
                if state is None or state in TERMINAL_STATES
                else DeliveryAction.RETRY
            )
        try:
            if record.state is JobState.QUEUED:
                record = transition(record, JobState.VALIDATING, 10)
                self.repository.update(record)
            self.repository.update(
                fail(
                    record,
                    terminal(
                        ErrorCode.MODEL_UNAVAILABLE,
                        "Video processing is temporarily unavailable.",
                    ),
                )
            )
        except Exception:
            # A pending stream delivery will be reclaimed; release its DB claim first when possible.
            try:
                self.repository.release(task.job_id, self.worker_id)
            except Exception:
                pass
            raise
        return DeliveryAction.ACK


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    queue_adapter: bool
    database_adapter: bool


class WorkerRuntime:
    def __init__(
        self,
        config: WorkerConfig,
        consumer: QueueConsumerAdapter,
        repository: JobRepository,
        stop: Event | None = None,
    ) -> None:
        self.config = config
        self.consumer = consumer
        self.repository = repository
        self.stop = stop or Event()
        self.capabilities = RuntimeCapabilities(queue_adapter=False, database_adapter=False)

    def ready(self) -> None:
        try:
            ready = getattr(self.repository, "ready", None)
            if callable(ready):
                ready()
            self.consumer.ready()
        except Exception as error:
            raise RuntimeUnavailable(
                "configured Redis Streams and PostgreSQL adapters are not ready"
            ) from error
        self.capabilities = RuntimeCapabilities(queue_adapter=True, database_adapter=True)

    def serve(self) -> None:
        self.ready()
        self.consumer.serve(self.stop, self.config.concurrency)

    def close(self) -> None:
        self.consumer.close()


def compose_runtime(
    config: WorkerConfig,
    repository: JobRepository | None = None,
    transport: QueueTransport | None = None,
    stop: Event | None = None,
) -> WorkerRuntime:
    config.validate_runtime()
    if repository is None:
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeUnavailable("psycopg is required for PostgreSQL worker access") from error
        repository = PostgresJobRepository(lambda: psycopg.connect(config.database_url))
    if transport is None:
        try:
            from redis import Redis
        except ImportError as error:
            raise RuntimeUnavailable("redis is required for Redis Streams worker access") from error
        transport = RedisStreamsTransport(
            Redis.from_url(config.redis_url),
            config.stream_name,
            config.stream_group,
            config.stream_consumer,
            config.stream_reclaim_idle_ms,
            config.stream_block_ms,
            config.heartbeat_seconds,
        )
    consumer = QueueConsumerAdapter(
        transport,
        UnavailablePipeline(repository, config.lease_seconds, config.worker_id),
    )
    return WorkerRuntime(config, consumer, repository, stop)
