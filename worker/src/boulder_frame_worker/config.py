"""JSON configuration with no import-time dependency checks."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


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
    ffprobe_bin: str = "ffprobe"
    ffmpeg_bin: str = "ffmpeg"
    lease_seconds: int = 300
    retain_debug_artifacts: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> WorkerConfig:
        worker = values
        pipeline_version = str(
            worker.get("pipeline_version", "development")
        ).strip()
        model_version = str(worker.get("model_version", "unconfigured")).strip()
        if not pipeline_version:
            raise ConfigError("WORKER_PIPELINE_VERSION must not be empty")
        if not model_version:
            raise ConfigError("WORKER_MODEL_VERSION must not be empty")
        scratch_root = Path(worker.get("scratch_root", "/tmp/boulder-frame-worker"))
        return cls(
            pipeline_version=pipeline_version,
            model_version=model_version,
            scratch_root=scratch_root,
            ffprobe_bin=str(worker.get("ffprobe_bin", "ffprobe")),
            ffmpeg_bin=str(worker.get("ffmpeg_bin", "ffmpeg")),
            lease_seconds=_positive_int(
                str(worker.get("lease_seconds", 300)), "lease_seconds"
            ),
            retain_debug_artifacts=_boolean(
                str(worker.get("retain_debug_artifacts", False)), "retain_debug_artifacts"
            ),
        )

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
