from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import cast

from .config import UNCONFIGURED_MODEL_VERSION, WorkerConfig
from .frame_reader import FrameReaderUnavailable, OpenCVFrameReader
from .measurement import PersonDetector
from .media import CFRNormalizer, FFmpegCFRNormalizer, FFmpegRenderer, FFprobeAdapter
from .models import (
    MODEL_VERSION,
    ModelVerificationError,
    OnnxSsdMobileNetV1Detector,
)
from .pipeline import FrameReader, OutputFinalizer, PlannerFactory, ProcessingPipeline
from .planner import DeterministicCropPlanner
from .queue_adapter import (
    QueueConsumerAdapter,
    QueueTransport,
    RedisStreamsTransport,
)
from .repository import PostgresJobRepository
from .review import ReviewLimits, ReviewRenderer
from .state import JobRepository
from .storage import S3Storage
from .worker import Worker


class RuntimeUnavailable(RuntimeError):
    """Configured worker adapters could not be constructed or verified."""


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    queue_adapter: bool
    database_adapter: bool
    storage_adapter: bool


class WorkerRuntime:
    def __init__(
        self,
        config: WorkerConfig,
        consumer: QueueConsumerAdapter,
        repository: JobRepository,
        storage: S3Storage,
        stop: Event | None = None,
    ) -> None:
        self.config = config
        self.consumer = consumer
        self.repository = repository
        self.storage = storage
        self.stop = stop or Event()
        self.capabilities = RuntimeCapabilities(
            queue_adapter=False, database_adapter=False, storage_adapter=False
        )

    def ready(self) -> None:
        try:
            ready = getattr(self.repository, "ready", None)
            if callable(ready):
                ready()
            self.storage.ready()
            if self.config.debug_capture and self.config.debug_require_private_storage:
                self.storage.require_private_debug_storage()
            self.consumer.ready()
        except Exception as error:
            raise RuntimeUnavailable(
                "configured PostgreSQL, Redis Streams, and object storage adapters are not ready"
            ) from error
        self.capabilities = RuntimeCapabilities(
            queue_adapter=True, database_adapter=True, storage_adapter=True
        )

    def serve(self) -> None:
        self.ready()
        self.consumer.serve(self.stop, self.config.concurrency)

    def close(self) -> None:
        self.consumer.close()


def compose_runtime(
    config: WorkerConfig,
    repository: JobRepository | None = None,
    transport: QueueTransport | None = None,
    storage: S3Storage | None = None,
    stop: Event | None = None,
    frame_reader: FrameReader | None = None,
    detector: PersonDetector | None = None,
    planner_factory: PlannerFactory | None = None,
    inspector: FFprobeAdapter | None = None,
    renderer: FFmpegRenderer | None = None,
    normalizer: CFRNormalizer | None = None,
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
            Redis.from_url(config.redis_url, health_check_interval=30),
            config.stream_name,
            config.stream_group,
            config.stream_consumer,
            config.stream_reclaim_idle_ms,
            config.stream_block_ms,
            config.heartbeat_seconds,
        )
    if storage is None:
        try:
            storage = S3Storage.from_config(config)
        except RuntimeError as error:
            message = "boto3 is required for S3-compatible worker storage"
            raise RuntimeUnavailable(message) from error
    if config.model_version not in {UNCONFIGURED_MODEL_VERSION, MODEL_VERSION}:
        raise RuntimeUnavailable(f"unsupported model_version: {config.model_version}")
    if detector is None and config.model_version == MODEL_VERSION:
        try:
            loaded_detector = OnnxSsdMobileNetV1Detector(config.model_dir)
            loaded_frame_reader = frame_reader or OpenCVFrameReader()
        except (FrameReaderUnavailable, ModelVerificationError) as error:
            raise RuntimeUnavailable(
                "configured model artifacts or decoder dependencies are unavailable"
            ) from error
        else:
            detector = loaded_detector
            frame_reader = loaded_frame_reader
    pipeline = ProcessingPipeline(
        storage,
        cast(OutputFinalizer, repository),  # PostgresJobRepository owns guarded finalization.
        inspector=inspector or FFprobeAdapter(config.ffprobe_bin),
        renderer=renderer or FFmpegRenderer(config.ffmpeg_bin),
        normalizer=normalizer
        or FFmpegCFRNormalizer(
            config.ffmpeg_bin, timeout_seconds=config.normalization_timeout_seconds
        ),
        frame_reader=frame_reader,
        detector=detector,
        planner_factory=planner_factory or DeterministicCropPlanner,
        debug_capture=config.debug_capture,
        debug_max_frames=config.debug_max_frames,
        debug_max_bytes=config.debug_max_bytes,
        review_renderer=(
            ReviewRenderer(
                config.ffmpeg_bin,
                ReviewLimits(
                    config.review_max_duration_ms,
                    config.review_width,
                    config.review_height,
                    config.review_max_bytes,
                    config.review_timeout_seconds,
                ),
            )
            if config.debug_visual_capture
            else None
        ),
        normalization_max_source_bytes=config.normalization_max_source_bytes,
    )
    worker = Worker(config, repository, config.worker_id)
    consumer = QueueConsumerAdapter(
        transport,
        lambda task: worker.process(
            task,
            pipeline.validating,
            pipeline.analyzing,
            pipeline.rendering,
            pipeline.uploading,
            pipeline.publish_debug,
        ),
    )
    return WorkerRuntime(config, consumer, repository, storage, stop)
