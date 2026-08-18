"""Tracking contracts reserved for the selected-athlete implementation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .errors import ErrorCode, terminal
from .measurement import Point, Rect


class TrackingState(StrEnum):
    TRACKED = "tracked"
    REACQUIRING = "reacquiring"
    LOST = "lost"


@dataclass(frozen=True, slots=True)
class TrackedMeasurement:
    frame_index: int
    root: Point | None
    pose_bounds: Rect | None
    detector_bounds: Rect | None
    confidence: float
    covariance: float | None
    state: TrackingState


class TargetTracker(Protocol):
    def track(self, measurements: Sequence[TrackedMeasurement]) -> list[TrackedMeasurement]: ...


class UnavailableTargetTracker:
    """Avoids presenting planned Kalman behavior as an implemented CV feature."""

    def track(self, measurements: Sequence[TrackedMeasurement]) -> list[TrackedMeasurement]:
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE, "Target tracking is not configured for this worker."
        )
