"""Typed environment configuration with no import-time dependency checks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    pass


UNCONFIGURED_MODEL_VERSION = "unconfigured"
LOCAL_ENV_UNCONFIGURED_MODEL_VERSION = "unset-until-pinned"
DEFAULT_DEBUG_MAX_FRAMES = 10_000
DEFAULT_DEBUG_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_NORMALIZATION_MAX_SOURCE_BYTES = 1024 * 1024 * 1024
DEFAULT_NORMALIZATION_TIMEOUT_SECONDS = 30 * 60
DEFAULT_REVIEW_MAX_DURATION_MS = 5 * 60 * 1000
DEFAULT_REVIEW_WIDTH = 960
DEFAULT_REVIEW_HEIGHT = 540
DEFAULT_REVIEW_MAX_BYTES = 250 * 1024 * 1024
DEFAULT_REVIEW_TIMEOUT_SECONDS = 10 * 60


def _positive_int(name: str, default: int) -> int:
    try:
        parsed = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ConfigError(f"{name} must be an integer") from error
    if parsed <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return parsed


def _boolean(name: str, default: bool) -> bool:
    value = os.environ.get(name, str(default)).lower()
    if value in {"1", "true", "yes"}:
        return True
    if value in {"0", "false", "no"}:
        return False
    raise ConfigError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    pipeline_version: str
    model_version: str
    scratch_root: Path
    model_dir: Path = Path("/models")
    database_url: str = ""
    redis_url: str = ""
    s3_endpoint: str = ""
    s3_presign_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_use_path_style: bool = False
    ffprobe_bin: str = "ffprobe"
    ffmpeg_bin: str = "ffmpeg"
    lease_seconds: int = 300
    heartbeat_seconds: int = 30
    concurrency: int = 1
    worker_id: str = ""
    stream_name: str = "boulder-frame:jobs"
    stream_group: str = "boulder-frame:job-processors"
    stream_consumer: str = ""
    stream_reclaim_idle_ms: int = 300_000
    stream_block_ms: int = 1_000
    retain_debug_artifacts: bool = False
    debug_capture: bool = False
    debug_visual_capture: bool = False
    debug_require_private_storage: bool = True
    debug_max_frames: int = DEFAULT_DEBUG_MAX_FRAMES
    debug_max_bytes: int = DEFAULT_DEBUG_MAX_BYTES
    review_max_duration_ms: int = DEFAULT_REVIEW_MAX_DURATION_MS
    review_width: int = DEFAULT_REVIEW_WIDTH
    review_height: int = DEFAULT_REVIEW_HEIGHT
    review_max_bytes: int = DEFAULT_REVIEW_MAX_BYTES
    review_timeout_seconds: int = DEFAULT_REVIEW_TIMEOUT_SECONDS
    normalization_max_source_bytes: int = DEFAULT_NORMALIZATION_MAX_SOURCE_BYTES
    normalization_timeout_seconds: int = DEFAULT_NORMALIZATION_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> WorkerConfig:
        pipeline_version = os.environ.get("PIPELINE_VERSION", "w0.2.6").strip()
        model_version = os.environ.get("MODEL_VERSION", UNCONFIGURED_MODEL_VERSION).strip()
        if model_version == LOCAL_ENV_UNCONFIGURED_MODEL_VERSION:
            model_version = UNCONFIGURED_MODEL_VERSION
        if not pipeline_version:
            raise ConfigError("PIPELINE_VERSION must not be empty")
        if not model_version:
            raise ConfigError("MODEL_VERSION must not be empty")
        lease_seconds = _positive_int("WORKER_LEASE_SECONDS", 300)
        heartbeat_seconds = _positive_int("WORKER_HEARTBEAT_SECONDS", 30)
        if heartbeat_seconds >= lease_seconds:
            raise ConfigError("WORKER_HEARTBEAT_SECONDS must be less than WORKER_LEASE_SECONDS")
        stream_name = os.environ.get("WORKER_STREAM_NAME", "boulder-frame:jobs").strip()
        stream_group = os.environ.get("WORKER_STREAM_GROUP", "boulder-frame:job-processors").strip()
        worker_id = os.environ.get("WORKER_ID", "").strip()
        stream_consumer = os.environ.get("WORKER_STREAM_CONSUMER", worker_id).strip()
        if not stream_name:
            raise ConfigError("WORKER_STREAM_NAME must not be empty")
        if not stream_group:
            raise ConfigError("WORKER_STREAM_GROUP must not be empty")
        debug_capture = _boolean("WORKER_DEBUG_CAPTURE", False)
        debug_visual_capture = _boolean("WORKER_DEBUG_VISUAL_CAPTURE", False)
        if debug_visual_capture and not debug_capture:
            raise ConfigError("WORKER_DEBUG_VISUAL_CAPTURE requires WORKER_DEBUG_CAPTURE")
        return cls(
            pipeline_version=pipeline_version,
            model_version=model_version,
            scratch_root=Path(os.environ.get("WORKER_SCRATCH_ROOT", "/tmp/boulder-frame-worker")),
            model_dir=Path(os.environ.get("MODEL_DIR") or "/models"),
            database_url=os.environ.get("DATABASE_URL", "").strip(),
            redis_url=os.environ.get("REDIS_URL", "").strip(),
            s3_endpoint=os.environ.get("S3_ENDPOINT", "").strip(),
            s3_presign_endpoint=os.environ.get("S3_PRESIGN_ENDPOINT", "").strip(),
            s3_region=os.environ.get("S3_REGION", "us-east-1").strip(),
            s3_bucket=os.environ.get("S3_BUCKET", "").strip(),
            s3_access_key=os.environ.get("S3_ACCESS_KEY", "").strip(),
            s3_secret_key=os.environ.get("S3_SECRET_KEY", "").strip(),
            s3_use_path_style=_boolean("S3_FORCE_PATH_STYLE", False),
            ffprobe_bin=os.environ.get("FFPROBE_BIN", "ffprobe"),
            ffmpeg_bin=os.environ.get("FFMPEG_BIN", "ffmpeg"),
            lease_seconds=lease_seconds,
            heartbeat_seconds=heartbeat_seconds,
            concurrency=_positive_int("WORKER_CONCURRENCY", 1),
            worker_id=worker_id,
            stream_name=stream_name,
            stream_group=stream_group,
            stream_consumer=stream_consumer,
            stream_reclaim_idle_ms=_positive_int(
                "WORKER_STREAM_RECLAIM_IDLE_MS", lease_seconds * 1000
            ),
            stream_block_ms=_positive_int("WORKER_STREAM_BLOCK_MS", 1000),
            retain_debug_artifacts=_boolean("WORKER_RETAIN_DEBUG_ARTIFACTS", False),
            debug_capture=debug_capture,
            debug_visual_capture=debug_visual_capture,
            debug_require_private_storage=_boolean("WORKER_DEBUG_REQUIRE_PRIVATE_STORAGE", True),
            debug_max_frames=_positive_int("WORKER_DEBUG_MAX_FRAMES", DEFAULT_DEBUG_MAX_FRAMES),
            debug_max_bytes=_positive_int("WORKER_DEBUG_MAX_BYTES", DEFAULT_DEBUG_MAX_BYTES),
            review_max_duration_ms=_positive_int(
                "WORKER_REVIEW_MAX_DURATION_MS", DEFAULT_REVIEW_MAX_DURATION_MS
            ),
            review_width=_positive_int("WORKER_REVIEW_WIDTH", DEFAULT_REVIEW_WIDTH),
            review_height=_positive_int("WORKER_REVIEW_HEIGHT", DEFAULT_REVIEW_HEIGHT),
            review_max_bytes=_positive_int("WORKER_REVIEW_MAX_BYTES", DEFAULT_REVIEW_MAX_BYTES),
            review_timeout_seconds=_positive_int(
                "WORKER_REVIEW_TIMEOUT_SECONDS", DEFAULT_REVIEW_TIMEOUT_SECONDS
            ),
            normalization_max_source_bytes=_positive_int(
                "WORKER_NORMALIZATION_MAX_SOURCE_BYTES", DEFAULT_NORMALIZATION_MAX_SOURCE_BYTES
            ),
            normalization_timeout_seconds=_positive_int(
                "WORKER_NORMALIZATION_TIMEOUT_SECONDS", DEFAULT_NORMALIZATION_TIMEOUT_SECONDS
            ),
        )

    def validate_runtime(self) -> None:
        if not self.database_url:
            raise ConfigError("database_url is required for --serve")
        if not self.redis_url:
            raise ConfigError("redis_url is required for --serve")
        for name, value in {
            "s3_endpoint": self.s3_endpoint,
            "s3_presign_endpoint": self.s3_presign_endpoint,
            "s3_region": self.s3_region,
            "s3_bucket": self.s3_bucket,
            "s3_access_key": self.s3_access_key,
            "s3_secret_key": self.s3_secret_key,
        }.items():
            if not value:
                raise ConfigError(f"{name} is required for --serve")
        if urlparse(self.database_url).scheme not in {"postgres", "postgresql"}:
            raise ConfigError("database_url must use postgres or postgresql")
        if urlparse(self.redis_url).scheme not in {"redis", "rediss"}:
            raise ConfigError("redis_url must use redis or rediss")
        for name, value in {
            "s3_endpoint": self.s3_endpoint,
            "s3_presign_endpoint": self.s3_presign_endpoint,
        }.items():
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ConfigError(f"{name} must be an absolute HTTP URL")
        if not self.worker_id:
            raise ConfigError("worker_id is required for --serve")
        if self.stream_reclaim_idle_ms < self.lease_seconds * 1000:
            raise ConfigError("stream_reclaim_idle_ms must be at least lease_seconds * 1000")
