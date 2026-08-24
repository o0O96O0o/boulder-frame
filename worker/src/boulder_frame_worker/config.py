"""JSON configuration with no import-time dependency checks."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    pass


UNCONFIGURED_MODEL_VERSION = "unconfigured"
LOCAL_ENV_UNCONFIGURED_MODEL_VERSION = "unset-until-pinned"
DEFAULT_DEBUG_MAX_FRAMES = 10_000
DEFAULT_DEBUG_MAX_BYTES = 50 * 1024 * 1024


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigError(f"{name} must be an integer") from error
    if parsed <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return parsed


def _boolean(value: str, name: str) -> bool:
    if value.lower() in {"1", "true", "yes"}:
        return True
    if value.lower() in {"0", "false", "no"}:
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
    debug_max_frames: int = DEFAULT_DEBUG_MAX_FRAMES
    debug_max_bytes: int = DEFAULT_DEBUG_MAX_BYTES

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> WorkerConfig:
        worker = values
        pipeline_version = str(worker.get("pipeline_version", "development")).strip()
        model_version = str(worker.get("model_version", UNCONFIGURED_MODEL_VERSION)).strip()
        if model_version == LOCAL_ENV_UNCONFIGURED_MODEL_VERSION:
            model_version = UNCONFIGURED_MODEL_VERSION
        if not pipeline_version:
            raise ConfigError("WORKER_PIPELINE_VERSION must not be empty")
        if not model_version:
            raise ConfigError("WORKER_MODEL_VERSION must not be empty")
        scratch_root = Path(worker.get("scratch_root", "/tmp/boulder-frame-worker"))
        lease_seconds = _positive_int(str(worker.get("lease_seconds", 300)), "lease_seconds")
        heartbeat_seconds = _positive_int(
            str(worker.get("heartbeat_seconds", 30)), "heartbeat_seconds"
        )
        if heartbeat_seconds >= lease_seconds:
            raise ConfigError("heartbeat_seconds must be less than lease_seconds")
        stream_name = str(worker.get("stream_name", "boulder-frame:jobs")).strip()
        stream_group = str(worker.get("stream_group", "boulder-frame:job-processors")).strip()
        worker_id = str(worker.get("worker_id", "")).strip()
        stream_consumer = str(worker.get("stream_consumer", worker_id)).strip()
        if not stream_name:
            raise ConfigError("stream_name must not be empty")
        if not stream_group:
            raise ConfigError("stream_group must not be empty")
        return cls(
            pipeline_version=pipeline_version,
            model_version=model_version,
            scratch_root=scratch_root,
            model_dir=Path(worker.get("model_dir") or "/models"),
            database_url=str(worker.get("database_url", "")).strip(),
            redis_url=str(worker.get("redis_url", "")).strip(),
            s3_endpoint=str(worker.get("s3_endpoint", "")).strip(),
            s3_presign_endpoint=str(worker.get("s3_presign_endpoint", "")).strip(),
            s3_region=str(worker.get("s3_region", "us-east-1")).strip(),
            s3_bucket=str(worker.get("s3_bucket", "")).strip(),
            s3_access_key=str(worker.get("s3_access_key", "")).strip(),
            s3_secret_key=str(worker.get("s3_secret_key", "")).strip(),
            s3_use_path_style=_boolean(
                str(worker.get("s3_use_path_style", False)), "s3_use_path_style"
            ),
            ffprobe_bin=str(worker.get("ffprobe_bin", "ffprobe")),
            ffmpeg_bin=str(worker.get("ffmpeg_bin", "ffmpeg")),
            lease_seconds=lease_seconds,
            heartbeat_seconds=heartbeat_seconds,
            concurrency=_positive_int(str(worker.get("concurrency", 1)), "concurrency"),
            worker_id=worker_id,
            stream_name=stream_name,
            stream_group=stream_group,
            stream_consumer=stream_consumer,
            stream_reclaim_idle_ms=_positive_int(
                str(worker.get("stream_reclaim_idle_ms", lease_seconds * 1000)),
                "stream_reclaim_idle_ms",
            ),
            stream_block_ms=_positive_int(
                str(worker.get("stream_block_ms", 1000)), "stream_block_ms"
            ),
            retain_debug_artifacts=_boolean(
                str(worker.get("retain_debug_artifacts", False)), "retain_debug_artifacts"
            ),
            debug_capture=_boolean(str(worker.get("debug_capture", False)), "debug_capture"),
            debug_max_frames=_positive_int(
                str(worker.get("debug_max_frames", DEFAULT_DEBUG_MAX_FRAMES)), "debug_max_frames"
            ),
            debug_max_bytes=_positive_int(
                str(worker.get("debug_max_bytes", DEFAULT_DEBUG_MAX_BYTES)), "debug_max_bytes"
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

    @classmethod
    def from_file(cls, path: str | Path) -> WorkerConfig:
        try:
            source = Path(path).read_text()
            source = re.sub(
                r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
                lambda match: os.environ.get(match.group(1), ""),
                source,
            )
            values = json.loads(source)
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigError(f"could not read configuration {path}: {error}") from error
        if not isinstance(values, Mapping):
            raise ConfigError("configuration must be an object")
        return cls.from_mapping(values)
