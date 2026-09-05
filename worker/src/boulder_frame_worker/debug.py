"""Safe, deterministic source-coordinate debug telemetry serialization."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from .measurement import AssociationEvidence, Point, RawFrameObservation, Rect, SelectionOutcome
from .planner import CropRect, FrameMeasurement, PlannerFrameTrace

DEBUG_BUNDLE_SCHEMA_VERSION = 1
DEFAULT_DEBUG_MAX_FRAMES = 10_000
DEFAULT_DEBUG_MAX_BYTES = 50 * 1024 * 1024

_RESERVED_RECORD_FIELDS = frozenset({"record_type", "schema_version"})
_SENSITIVE_FIELD_PARTS = (
    "access_key",
    "apikey",
    "api_key",
    "authorization",
    "credential",
    "diagnostic",
    "encryption_key",
    "password",
    "private_key",
    "secret",
    "signature",
    "token",
)
_UNSAFE_FIELD_PARTS = (
    "endpoint",
    "pixel",
    "raw_frame",
    "uri",
    "url",
)
_UNSAFE_FIELD_NAMES = frozenset(
    {
        "binary",
        "buffer",
        "bytes",
        "data",
        "frame",
        "image",
        "media",
        "payload",
        "video",
    }
)
_URL_PATTERN = re.compile(r"(?i)(?:https?|s3|postgres(?:ql)?|rediss?)://\S+")


class DebugBundleLimitError(ValueError):
    """Raised when a debug bundle would exceed a configured output limit."""


def debug_bundle_header(
    *,
    job_id: UUID | str,
    source_metadata: Mapping[str, object],
    pipeline_version: str,
    model_version: str,
    planner_config: Mapping[str, object],
    model_manifest: Mapping[str, object],
    source_object_version: str | None = None,
    source_checksum: str | None = None,
) -> dict[str, object]:
    """Build the fixed first record for a debug bundle."""
    return sanitize_record(
        {
            "record_type": "header",
            "schema_version": DEBUG_BUNDLE_SCHEMA_VERSION,
            "job_id": str(job_id),
            "source_metadata": sanitize_record(source_metadata),
            "pipeline_version": pipeline_version,
            "model_version": model_version,
            "planner_config": sanitize_record(planner_config),
            "model_manifest": sanitize_record(model_manifest),
            "source_object_version": source_object_version,
            "source_checksum": source_checksum,
        }
    )


class DebugBundleWriter(AbstractContextManager["DebugBundleWriter"]):
    """Incrementally write one deterministic, sanitized gzip JSON Lines bundle."""

    def __init__(
        self,
        path: str | Path,
        header: Mapping[str, object],
        *,
        max_frames: int = DEFAULT_DEBUG_MAX_FRAMES,
        max_bytes: int = DEFAULT_DEBUG_MAX_BYTES,
    ) -> None:
        if header.get("record_type") != "header":
            raise ValueError("debug bundle header must have record_type 'header'")
        self._max_frames = _positive_limit(max_frames, "max_frames")
        self._max_bytes = _positive_limit(max_bytes, "max_bytes")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._raw_file: BinaryIO = self.path.open("wb")
        self._gzip_file = gzip.GzipFile(fileobj=self._raw_file, mode="wb", mtime=0, filename="")
        self._closed = False
        self._frame_count = 0
        try:
            self._write(sanitize_record(header))
        except Exception:
            self._fail()
            raise

    def write(self, record_type: str, fields: Mapping[str, object]) -> None:
        if self._closed:
            raise ValueError("debug bundle writer is closed")
        if not record_type:
            raise ValueError("debug record type must not be empty")
        if record_type == "frame" and self._frame_count >= self._max_frames:
            raise DebugBundleLimitError(
                f"debug bundle exceeds max_frames limit of {self._max_frames}"
            )
        record = {
            "record_type": record_type,
            "schema_version": DEBUG_BUNDLE_SCHEMA_VERSION,
            **{
                key: value
                for key, value in sanitize_record(fields).items()
                if key not in _RESERVED_RECORD_FIELDS
            },
        }
        self._write(record)
        if record_type == "frame":
            self._frame_count += 1

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._gzip_file.close()
            self._raw_file.close()
            if self.path.stat().st_size > self._max_bytes:
                raise DebugBundleLimitError(
                    f"debug bundle exceeds max_bytes limit of {self._max_bytes}"
                )
        except Exception:
            self._fail()
            raise
        self._closed = True

    def __exit__(self, *_: object) -> None:
        self.close()

    def _write(self, record: Mapping[str, object]) -> None:
        encoded = canonical_json_bytes(record)
        self._gzip_file.write(encoded + b"\n")
        self._gzip_file.flush()
        # Reserve the fixed gzip trailer that close() will append.
        if self._raw_file.tell() + 8 > self._max_bytes:
            self._fail()
            raise DebugBundleLimitError(
                f"debug bundle exceeds max_bytes limit of {self._max_bytes}"
            )

    def _fail(self) -> None:
        if self._closed:
            return
        try:
            self._gzip_file.close()
        finally:
            self._raw_file.close()
            self._closed = True
            self.path.unlink(missing_ok=True)


def append_debug_record(path: str | Path, record_type: str, fields: Mapping[str, object]) -> None:
    """Append one sanitized intermediate record for a job-local debug bundle."""
    if not record_type:
        raise ValueError("debug record type must not be empty")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "record_type": record_type,
        "schema_version": DEBUG_BUNDLE_SCHEMA_VERSION,
        **{
            key: value
            for key, value in sanitize_record(fields).items()
            if key not in _RESERVED_RECORD_FIELDS
        },
    }
    with destination.open("ab") as output:
        output.write(canonical_json_bytes(record) + b"\n")


def sanitize_record(record: Mapping[str, object]) -> dict[str, object]:
    """Return JSON-safe telemetry without credentials, URLs, or media payloads."""
    safe: dict[str, object] = {}
    for key in sorted(key for key in record if isinstance(key, str)):
        if _unsafe_field(key):
            continue
        safe[key] = _sanitize_value(record[key])
    return safe


def canonical_json_bytes(value: object) -> bytes:
    """Encode a safe value with a stable JSON representation suitable for hashing."""
    safe = sanitize_record(value) if isinstance(value, Mapping) else _sanitize_value(value)
    return json.dumps(
        safe, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def deterministic_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def crop_path_digest(crops: Sequence[CropRect]) -> str:
    return deterministic_digest([serialize_crop_rect(crop) for crop in crops])


def serialize_point(point: Point | None) -> dict[str, float | None] | None:
    if point is None:
        return None
    return {"x": _finite(point.x), "y": _finite(point.y)}


def serialize_rect(rect: Rect | None) -> dict[str, float | None] | None:
    if rect is None:
        return None
    return {
        "x": _finite(rect.x),
        "y": _finite(rect.y),
        "width": _finite(rect.width),
        "height": _finite(rect.height),
    }


def serialize_crop_rect(crop: CropRect | None) -> dict[str, float | None] | None:
    if crop is None:
        return None
    return {
        "x": _finite(crop.x),
        "y": _finite(crop.y),
        "width": _finite(crop.width),
        "height": _finite(crop.height),
    }


def serialize_raw_frame_observation(observation: RawFrameObservation) -> dict[str, object]:
    result: dict[str, object] = {
        "frame_index": observation.frame_index,
        "timestamp_ms": observation.timestamp_ms,
        "detection": (
            None
            if observation.detection is None
            else {
                "bounds": serialize_rect(observation.detection.bounds),
                "confidence": _finite(observation.detection.confidence),
            }
        ),
    }
    if observation.selection_outcome is not None:
        result["selection_outcome"] = observation.selection_outcome.value
    if observation.association is not None:
        result["selection"] = serialize_association_evidence(observation.association)
    return result


def serialize_association_evidence(evidence: AssociationEvidence) -> dict[str, object]:
    return {
        "selected": evidence.outcome is not SelectionOutcome.NO_DETECTIONS,
        "reference": serialize_point(evidence.reference),
        "reference_kind": evidence.reference_kind.value,
        "strategy": evidence.strategy.value,
        "outcome": evidence.outcome.value,
        "candidate_count": evidence.candidate_count,
        "candidates_truncated": evidence.candidates_truncated,
        "candidates": [
            {
                "original_index": candidate.original_index,
                "bounds": serialize_rect(candidate.detection.bounds),
                "confidence": _finite(candidate.detection.confidence),
                "contains_reference": candidate.contains_reference,
                "center_distance": _finite(candidate.center_distance),
                "selected": candidate.selected,
            }
            for candidate in evidence.candidates
        ],
    }


def serialize_frame_measurement(measurement: FrameMeasurement) -> dict[str, object]:
    return {
        "detector_bounds": serialize_rect(measurement.detector_bounds),
        "confidence": _finite(measurement.confidence),
        "detection_missed": measurement.missed,
    }


def serialize_planner_trace(trace: PlannerFrameTrace) -> dict[str, object]:
    return {
        "target_height_fraction": _finite(trace.target_height_fraction),
        "desired_crop": serialize_crop_rect(trace.desired_crop),
        "detection_missed": trace.detection_missed,
        "smoothing_applied": trace.smoothing_applied,
        "containment_override": trace.containment_override,
        "source_aspect_limited": trace.source_aspect_limited,
        "observed_height_fraction": _finite(trace.observed_height_fraction),
        "scale_relative_error": _finite(trace.scale_relative_error),
        "scale_deadband_applied": trace.scale_deadband_applied,
        "scale_adjusting": trace.scale_adjusting,
        "center_error_x_fraction": _finite(trace.center_error_x_fraction),
        "center_error_y_fraction": _finite(trace.center_error_y_fraction),
        "center_deadband_applied": trace.center_deadband_applied,
        "center_adjusting": trace.center_adjusting,
        "action": trace.action,
    }


def _unsafe_field(key: str) -> bool:
    normalized = _normalized_field_name(key)
    return (
        normalized in _UNSAFE_FIELD_NAMES
        or any(part in normalized for part in _SENSITIVE_FIELD_PARTS)
        or any(part in normalized for part in _UNSAFE_FIELD_PARTS)
    )


def _normalized_field_name(key: str) -> str:
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    return re.sub(r"[^a-z0-9]+", "_", separated.lower()).strip("_")


def _sanitize_value(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _finite(value)
    if isinstance(value, str):
        return None if _URL_PATTERN.search(value) else value
    if isinstance(value, Mapping):
        return sanitize_record(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, Sequence):
        return [_sanitize_value(item) for item in value]
    return None


def _finite(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return value


def _positive_limit(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value
