"""Small dependency-free JSON logger for worker/queue boundary events."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from .media import MediaMetadata
from .state import SourceAsset

_LOG_CONTEXT: ContextVar[dict[str, object] | None] = ContextVar("worker_log_context", default=None)
_MISSING = object()
_LOG_FIELDS = (
    "trace_id",
    "request_body",
    "response_body",
    "job_id",
    "worker_id",
    "stage",
    "outcome",
    "progress",
    "pipeline_version",
    "model_version",
    "duration_ms",
    "error_code",
    "diagnostic",
    "source_video",
    "phase_io",
    "output_frame_count",
    "repeated_output_frame_count",
    "repeated_output_frame_intervals",
    "planned_crop_count",
    "render_input_was_normalized",
    "render_input_frame_count",
    "render_input_near_static_frame_count",
    "render_input_near_static_intervals",
    "planned_crop_near_static_frame_count",
    "planned_crop_near_static_intervals",
    "output_near_static_frame_count",
    "output_near_static_intervals",
    "original_source_frame_count",
    "original_source_near_static_frame_count",
    "original_source_near_static_intervals",
    "render_mapping_checked_frames",
    "render_mapping_matching_frames",
    "render_mapping_max_mean_absolute_error",
    "render_mapping_samples",
    "config_path",
    "configuration",
)


@contextmanager
def log_context(**fields: object) -> Iterator[None]:
    token = _LOG_CONTEXT.set({**(_LOG_CONTEXT.get() or {}), **fields})
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


def source_video_fields(source: SourceAsset) -> dict[str, object]:
    """Return bounded, credential-free source metadata for operational logs."""
    return {
        "asset_id": str(source.id),
        "storage_key": source.storage_key,
        "upload_state": source.upload_state,
        "content_type": source.content_type,
        "size_bytes": source.size_bytes,
        "recorded_width": source.width,
        "recorded_height": source.height,
        "recorded_frame_rate": source.frame_rate,
        "recorded_duration_ms": source.duration_ms,
    }


def safe_diagnostic(diagnostic: str | None, scratch: Path | None = None) -> str | None:
    """Redact job-local paths, URLs, and credential-shaped values from diagnostics."""
    if diagnostic is None:
        return None
    sanitized = diagnostic
    if scratch is not None:
        for value in {str(scratch), str(scratch.resolve())}:
            if value:
                sanitized = sanitized.replace(value, "<scratch>")
    sanitized = re.sub(r"https?://[^\s\"']+", "<redacted-url>", sanitized, flags=re.IGNORECASE)
    return re.sub(
        r"\b(password|passwd|token|secret|access_key|authorization)=([^\s,;]+)",
        r"\1=<redacted>",
        sanitized,
        flags=re.IGNORECASE,
    )


def media_metadata_fields(metadata: MediaMetadata) -> dict[str, object]:
    """Serialize exact inspected media properties without source bytes."""
    display_width, display_height = metadata.display_dimensions
    return {
        "coded_width": metadata.width,
        "coded_height": metadata.height,
        "display_width": display_width,
        "display_height": display_height,
        "duration_ms": metadata.duration_ms,
        "frame_rate": str(metadata.frame_rate),
        "frame_rate_fps": float(metadata.frame_rate),
        "expected_frame_count": metadata.expected_frame_count,
        "video_codec": metadata.video_codec,
        "audio_codec": metadata.audio_codec,
        "has_audio": metadata.has_audio,
        "audio_stream_index": metadata.audio_stream_index,
        "rotation": metadata.rotation,
    }


def local_artifact_fields(
    path: Path, role: str, *, media: MediaMetadata | None = None, **details: object
) -> dict[str, object]:
    """Describe a job-local phase artifact by stable name and size."""
    fields: dict[str, object] = {
        "kind": "video" if media is not None else "file",
        "role": role,
        "location": "scratch",
        "name": path.name,
        "size_bytes": path.stat().st_size,
        **details,
    }
    if media is not None:
        fields["media"] = media_metadata_fields(media)
    return fields


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "module": "worker",
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        context = _LOG_CONTEXT.get() or {}
        for key in _LOG_FIELDS:
            value = getattr(record, key, context.get(key, _MISSING))
            if value is not _MISSING:
                output_key = "trace-id" if key == "trace_id" else key
                event[output_key] = value
        if record.exc_info:
            error_type, error, _ = record.exc_info
            scratch = getattr(record, "scratch_path", None)
            event["error"] = {
                "message": safe_diagnostic(
                    str(error), scratch if isinstance(scratch, Path) else None
                ),
                "type": error_type.__name__ if error_type is not None else "UnknownError",
            }
        return json.dumps(event, sort_keys=True, default=str)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("boulder_frame_worker")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
