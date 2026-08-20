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
    """A pose expressed in decoded source-pixel coordinates."""

    root: Point
    landmarks: tuple[Point, ...]
    bounds: Rect
    confidence: float


@dataclass(frozen=True, slots=True)
class PoseEstimate:
    """A pose model result expressed as normalized coordinates within its input ROI."""

    root: Point
    landmarks: tuple[Point, ...]
    bounds: Rect
    confidence: float


@dataclass(frozen=True, slots=True)
class RawFrameObservation:
    """The one target-associated detector/pose result for an analysis frame."""

    frame_index: int
    timestamp_ms: int
    detection: Detection | None
    pose: PoseMeasurement | None

    def __post_init__(self) -> None:
        if self.frame_index < 0 or self.timestamp_ms < 0:
            raise ValueError("frame index and timestamp must not be negative")

    @property
    def detector_bounds(self) -> Rect | None:
        return None if self.detection is None else self.detection.bounds

    @property
    def pose_bounds(self) -> Rect | None:
        return None if self.pose is None else self.pose.bounds

    @property
    def root(self) -> Point | None:
        return None if self.pose is None else self.pose.root

    @property
    def landmarks(self) -> tuple[Point, ...]:
        return () if self.pose is None else self.pose.landmarks

    @property
    def confidence(self) -> float:
        if self.pose is not None and self.detection is not None:
            return min(self.pose.confidence, self.detection.confidence)
        if self.pose is not None:
            return self.pose.confidence
        if self.detection is not None:
            return self.detection.confidence
        return 0


class PersonDetector(Protocol):
    def detect(self, frame: object) -> Sequence[Detection]: ...


class PoseEstimator(Protocol):
    def estimate(self, roi_pixels: object, roi: Rect) -> PoseEstimate | None: ...


class FrameCropper(Protocol):
    def crop(self, frame: object, roi: Rect) -> object: ...


class UnavailableDetector:
    def detect(self, frame: object) -> Sequence[Detection]:
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE, "Person detection is not configured for this worker."
        )


class UnavailablePoseEstimator:
    def estimate(self, roi_pixels: object, roi: Rect) -> PoseEstimate | None:
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE, "Pose estimation is not configured for this worker."
        )


class SourceFrameCropper:
    """Minimal array-like frame cropper kept separate from detector/pose adapters."""

    def crop(self, frame: object, roi: Rect) -> object:
        try:
            return frame[int(roi.y) : int(roi.bottom), int(roi.x) : int(roi.right)]  # type: ignore[index]
        except (IndexError, TypeError) as error:
            raise ValueError("frame does not support source-pixel ROI cropping") from error


class TargetFrameAnalyzer:
    """Associates one selected athlete and produces source-coordinate raw observations."""

    def __init__(
        self,
        detector: PersonDetector,
        pose_estimator: PoseEstimator,
        *,
        roi_padding: float = 0.25,
        cropper: FrameCropper | None = None,
    ) -> None:
        if not 0 <= roi_padding <= 1:
            raise ValueError("ROI padding must be between zero and one")
        self.detector = detector
        self.pose_estimator = pose_estimator
        self.roi_padding = roi_padding
        self.cropper = cropper or SourceFrameCropper()

    def observe_selected(
        self,
        frame: object,
        *,
        frame_index: int,
        timestamp_ms: int,
        normalized_x: float,
        normalized_y: float,
        source_width: int,
        source_height: int,
    ) -> RawFrameObservation:
        detection = select_target(
            self.detector.detect(frame),
            source_tap(normalized_x, normalized_y, source_width, source_height),
        )
        roi = expand_roi(detection.bounds, self.roi_padding, source_width, source_height)
        estimate = self.pose_estimator.estimate(self.cropper.crop(frame, roi), roi)
        return RawFrameObservation(
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            detection=detection,
            pose=None if estimate is None else pose_to_source(estimate, roi),
        )

    def observe(
        self,
        frame: object,
        *,
        frame_index: int,
        timestamp_ms: int,
        normalized_x: float,
        normalized_y: float,
        source_width: int,
        source_height: int,
    ) -> RawFrameObservation:
        """Return an empty observation for later-frame detector gaps."""
        detections = self.detector.detect(frame)
        if not detections:
            return RawFrameObservation(frame_index, timestamp_ms, None, None)
        detection = select_target(
            detections,
            source_tap(normalized_x, normalized_y, source_width, source_height),
        )
        roi = expand_roi(detection.bounds, self.roi_padding, source_width, source_height)
        estimate = self.pose_estimator.estimate(self.cropper.crop(frame, roi), roi)
        return RawFrameObservation(
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            detection=detection,
            pose=None if estimate is None else pose_to_source(estimate, roi),
        )


def source_tap(normalized_x: float, normalized_y: float, width: int, height: int) -> Point:
    if width <= 0 or height <= 0:
        raise ValueError("source dimensions must be positive")
    if not 0 <= normalized_x <= 1 or not 0 <= normalized_y <= 1:
        raise ValueError("normalized target coordinates must be between zero and one")
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


def rect_to_source(bounds: Rect, roi: Rect) -> Rect:
    """Transforms a normalized ROI rectangle emitted by a pose model to source pixels."""
    top_left = roi_to_source(Point(bounds.x, bounds.y), roi)
    return Rect(top_left.x, top_left.y, bounds.width * roi.width, bounds.height * roi.height)


def pose_to_source(estimate: PoseEstimate, roi: Rect) -> PoseMeasurement:
    return PoseMeasurement(
        root=roi_to_source(estimate.root, roi),
        landmarks=tuple(roi_to_source(point, roi) for point in estimate.landmarks),
        bounds=rect_to_source(estimate.bounds, roi),
        confidence=estimate.confidence,
    )
