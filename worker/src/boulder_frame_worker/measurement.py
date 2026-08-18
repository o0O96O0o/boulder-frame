"""Deterministic interfaces for target association and pose-coordinate transforms."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .errors import ErrorCode, terminal


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    def contains(self, point: Point) -> bool:
        return self.x <= point.x <= self.right and self.y <= point.y <= self.bottom


@dataclass(frozen=True, slots=True)
class Detection:
    bounds: Rect
    confidence: float


@dataclass(frozen=True, slots=True)
class PoseMeasurement:
    root: Point
    landmarks: tuple[Point, ...]
    bounds: Rect
    confidence: float


class PersonDetector(Protocol):
    def detect(self, frame: object) -> Sequence[Detection]: ...


class PoseEstimator(Protocol):
    def estimate(self, roi_pixels: object, roi: Rect) -> PoseMeasurement: ...


class UnavailableDetector:
    def detect(self, frame: object) -> Sequence[Detection]:
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE, "Person detection is not configured for this worker."
        )


class UnavailablePoseEstimator:
    def estimate(self, roi_pixels: object, roi: Rect) -> PoseMeasurement:
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE, "Pose estimation is not configured for this worker."
        )


def source_tap(normalized_x: float, normalized_y: float, width: int, height: int) -> Point:
    if width <= 0 or height <= 0:
        raise ValueError("source dimensions must be positive")
    return Point(normalized_x * width, normalized_y * height)


def select_target(detections: Sequence[Detection], tap: Point) -> Detection:
    if not detections:
        raise terminal(ErrorCode.NO_SELECTED_ATHLETE, "No athlete was found at the selected frame.")
    containing = [detection for detection in detections if detection.bounds.contains(tap)]
    candidates = containing or list(detections)
    return min(
        candidates,
        key=lambda detection: (
            (detection.bounds.center.x - tap.x) ** 2 + (detection.bounds.center.y - tap.y) ** 2
        ),
    )


def expand_roi(
    bounds: Rect, padding_fraction: float, source_width: int, source_height: int
) -> Rect:
    if not 0 <= padding_fraction <= 1:
        raise ValueError("ROI padding must be between zero and one")
    width = bounds.width * (1 + 2 * padding_fraction)
    height = bounds.height * (1 + 2 * padding_fraction)
    x = max(0, min(bounds.center.x - width / 2, source_width - width))
    y = max(0, min(bounds.center.y - height / 2, source_height - height))
    return Rect(x, y, min(width, source_width), min(height, source_height))


def roi_to_source(point: Point, roi: Rect) -> Point:
    """Transforms normalized ROI coordinates emitted by a pose model to source pixels."""
    return Point(roi.x + point.x * roi.width, roi.y + point.y * roi.height)
