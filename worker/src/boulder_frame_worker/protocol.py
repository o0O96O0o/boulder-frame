"""Cross-service task and immutable configuration protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from .errors import ErrorCode, terminal


class AspectRatio(StrEnum):
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"

    @property
    def value_float(self) -> float:
        return 16 / 9 if self is AspectRatio.LANDSCAPE else 9 / 16


class FramingProfile(StrEnum):
    TIGHT = "tight"
    BALANCED = "balanced"
    SAFE = "safe"
    FULL_MOVEMENT = "full_movement"


@dataclass(frozen=True, slots=True)
class TargetSelection:
    frame_time_ms: int
    normalized_x: float
    normalized_y: float

    def __post_init__(self) -> None:
        if self.frame_time_ms < 0:
            raise terminal(
                ErrorCode.INVALID_TARGET_SELECTION, "Target frame time must not be negative."
            )
        if not 0 <= self.normalized_x <= 1 or not 0 <= self.normalized_y <= 1:
            raise terminal(
                ErrorCode.INVALID_TARGET_SELECTION,
                "Target coordinates must be between zero and one.",
            )


@dataclass(frozen=True, slots=True)
class OutputSettings:
    aspect_ratio: AspectRatio
    profile: FramingProfile


@dataclass(frozen=True, slots=True)
class JobConfiguration:
    source_asset_id: UUID
    target_selection: TargetSelection
    output: OutputSettings
    pipeline_version: str
    model_version: str


@dataclass(frozen=True, slots=True)
class JobTask:
    """The queue payload must contain exactly one durable job identifier."""

    job_id: UUID

    @classmethod
    def from_payload(cls, payload: object) -> JobTask:
        if not isinstance(payload, dict) or set(payload) != {"job_id"}:
            raise terminal(ErrorCode.INVALID_TASK, "Worker task payload is invalid.")
        value = payload["job_id"]
        if not isinstance(value, str):
            raise terminal(ErrorCode.INVALID_TASK, "Worker task payload is invalid.")
        try:
            return cls(job_id=UUID(value))
        except ValueError as error:
            raise terminal(ErrorCode.INVALID_TASK, "Worker task payload is invalid.") from error
