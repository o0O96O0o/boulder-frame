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
    database_url: str = ""
    redis_url: str = ""
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

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> WorkerConfig:
        worker = values
        pipeline_version = str(worker.get("pipeline_version", "development")).strip()
        model_version = str(worker.get("model_version", "unconfigured")).strip()
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
            database_url=str(worker.get("database_url", "")).strip(),
            redis_url=str(worker.get("redis_url", "")).strip(),
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
        )

    def validate_runtime(self) -> None:
        if not self.database_url:
            raise ConfigError("database_url is required for --serve")
        if not self.redis_url:
            raise ConfigError("redis_url is required for --serve")
        if urlparse(self.database_url).scheme not in {"postgres", "postgresql"}:
            raise ConfigError("database_url must use postgres or postgresql")
        if urlparse(self.redis_url).scheme not in {"redis", "rediss"}:
            raise ConfigError("redis_url must use redis or rediss")
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
