"""Source-bounded deterministic virtual-camera geometry and baseline planner."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .measurement import Point, Rect
from .protocol import AspectRatio, FramingProfile


@dataclass(frozen=True, slots=True)
class CropRect:
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

    def contains(self, bounds: Rect) -> bool:
        return (
            self.x <= bounds.x
            and self.y <= bounds.y
            and self.right >= bounds.right
            and self.bottom >= bounds.bottom
        )


@dataclass(frozen=True, slots=True)
class FrameMeasurement:
    root: Point | None
    bounds: Rect | None
    confidence: float
    velocity: Point = Point(0, 0)
    lost: bool = False
    detector_bounds: Rect | None = None
    covariance: float | None = None


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    base_padding: float
    uncertainty_padding: float
    lead_fraction: float
    max_zoom_out_factor: float = 1.75
    max_zoom_in_factor: float = 0.96
    high_confidence: float = 0.8
    stable_hold_frames: int = 3
    max_pan_fraction: float = 0.18
    pan_dead_zone_fraction: float = 0.01
    envelope_radius: int = 2


PROFILE_CONFIGS: dict[FramingProfile, PlannerConfig] = {
    FramingProfile.TIGHT: PlannerConfig(0.10, 0.10, 0.08),
    FramingProfile.BALANCED: PlannerConfig(0.18, 0.16, 0.12),
    FramingProfile.SAFE: PlannerConfig(0.28, 0.25, 0.16),
    FramingProfile.FULL_MOVEMENT: PlannerConfig(0.40, 0.35, 0.20),
}


class CropPlanner(Protocol):
    def plan(self, measurements: Sequence[FrameMeasurement]) -> list[CropRect]: ...


def full_frame_crop(source_width: int, source_height: int, aspect_ratio: AspectRatio) -> CropRect:
    source_aspect = source_width / source_height
    output_aspect = aspect_ratio.value_float
    if source_aspect >= output_aspect:
        height = float(source_height)
        width = height * output_aspect
    else:
        width = float(source_width)
        height = width / output_aspect
    return CropRect((source_width - width) / 2, (source_height - height) / 2, width, height)


def clamp_crop(crop: CropRect, source_width: int, source_height: int) -> CropRect:
    if crop.width > source_width or crop.height > source_height:
        raise ValueError("crop cannot exceed source dimensions")
    x = min(max(crop.x, 0), source_width - crop.width)
    y = min(max(crop.y, 0), source_height - crop.height)
    return CropRect(x, y, crop.width, crop.height)


class DeterministicCropPlanner:
    """Future-aware, source-bounded local controller; it deliberately uses no optimizer."""

    def __init__(
        self,
        source_width: int,
        source_height: int,
        aspect_ratio: AspectRatio,
        profile: FramingProfile,
    ) -> None:
        if source_width <= 0 or source_height <= 0:
            raise ValueError("source dimensions must be positive")
        self.source_width = source_width
        self.source_height = source_height
        self.aspect_ratio = aspect_ratio
        self.config = PROFILE_CONFIGS[profile]
        self.full_frame = full_frame_crop(source_width, source_height, aspect_ratio)

    def _desired_crop(self, measurement: FrameMeasurement, envelope: Rect | None) -> CropRect:
        if measurement.lost or measurement.root is None or envelope is None:
            return self.full_frame
        uncertainty = self.config.uncertainty_padding * (1 - max(0, min(measurement.confidence, 1)))
        if measurement.covariance is not None:
            uncertainty += min(
                0.25, measurement.covariance / max(self.source_width, self.source_height)
            )
        padding = self.config.base_padding + uncertainty
        required_width = envelope.width * (1 + 2 * padding)
        required_height = envelope.height * (1 + 2 * padding)
        height = max(required_height, required_width / self.aspect_ratio.value_float)
        width = height * self.aspect_ratio.value_float
        if width > self.full_frame.width or height > self.full_frame.height:
            return self.full_frame
        lead = Point(
            measurement.velocity.x * self.config.lead_fraction,
            measurement.velocity.y * self.config.lead_fraction,
        )
        center = Point(measurement.root.x + lead.x, measurement.root.y + lead.y)
        return clamp_crop(
            CropRect(center.x - width / 2, center.y - height / 2, width, height),
            self.source_width,
            self.source_height,
        )

    def plan(self, measurements: Sequence[FrameMeasurement]) -> list[CropRect]:
        smoothed = self._smooth(measurements)
        crops: list[CropRect] = []
        previous: CropRect | None = None
        stable_frames = 0
        pan_delta = Point(0, 0)
        for index, measurement in enumerate(smoothed):
            envelope = self._movement_envelope(smoothed, index)
            desired = self._desired_crop(measurement, envelope)
            if previous is None:
                crop = desired
            elif measurement.lost or measurement.confidence < self.config.high_confidence:
                # Low-confidence observations may widen immediately but must never zoom in.
                crop = self._rate_limited(previous, desired, 1.0)
                stable_frames = 0
            else:
                stable_frames += 1
                factor = (
                    self.config.max_zoom_in_factor
                    if stable_frames >= self.config.stable_hold_frames
                    else 1.0
                )
                crop = self._rate_limited(previous, desired, factor)
            if previous is not None:
                crop, pan_delta = self._pan_limited(previous, crop, pan_delta)
                # Containment is more important than a motion limit when the athlete moves abruptly.
                if envelope is not None and not crop.contains(envelope):
                    crop = desired
                    pan_delta = Point(
                        crop.center.x - previous.center.x, crop.center.y - previous.center.y
                    )
            crop = clamp_crop(crop, self.source_width, self.source_height)
            crops.append(crop)
            previous = crop
        return crops

    def _smooth(self, measurements: Sequence[FrameMeasurement]) -> list[FrameMeasurement]:
        """Apply a causal pass followed by a backward pass because the source is recorded."""
        forward: list[Point | None] = []
        previous: Point | None = None
        for measurement in measurements:
            if measurement.lost or measurement.root is None:
                forward.append(None)
                previous = None
            elif previous is None:
                previous = measurement.root
                forward.append(previous)
            else:
                previous = Point(
                    previous.x * 0.35 + measurement.root.x * 0.65,
                    previous.y * 0.35 + measurement.root.y * 0.65,
                )
                forward.append(previous)
        backward: list[Point | None] = [None] * len(measurements)
        following: Point | None = None
        for index in range(len(measurements) - 1, -1, -1):
            point = forward[index]
            if point is None:
                following = None
            elif following is None:
                following = point
                backward[index] = point
            else:
                following = Point(
                    point.x * 0.65 + following.x * 0.35,
                    point.y * 0.65 + following.y * 0.35,
                )
                backward[index] = following
        return [
            FrameMeasurement(
                root=backward[index],
                bounds=measurement.bounds,
                confidence=measurement.confidence,
                velocity=measurement.velocity,
                lost=measurement.lost,
                detector_bounds=measurement.detector_bounds,
                covariance=measurement.covariance,
            )
            for index, measurement in enumerate(measurements)
        ]

    def _movement_envelope(
        self, measurements: Sequence[FrameMeasurement], index: int
    ) -> Rect | None:
        bounds: list[Rect] = []
        start = max(0, index - self.config.envelope_radius)
        stop = min(len(measurements), index + self.config.envelope_radius + 1)
        for measurement in measurements[start:stop]:
            if not measurement.lost:
                bound = measurement.bounds or measurement.detector_bounds
                if bound is not None:
                    bounds.append(bound)
        if not bounds:
            return None
        left = min(bound.x for bound in bounds)
        top = min(bound.y for bound in bounds)
        right = max(bound.right for bound in bounds)
        bottom = max(bound.bottom for bound in bounds)
        return Rect(left, top, right - left, bottom - top)

    def _rate_limited(self, previous: CropRect, desired: CropRect, zoom_factor: float) -> CropRect:
        # A larger height is a zoom out, so it may move by a larger factor than a zoom in.
        if desired.height >= previous.height:
            height = min(desired.height, previous.height * self.config.max_zoom_out_factor)
        else:
            height = max(desired.height, previous.height * zoom_factor)
        width = height * self.aspect_ratio.value_float
        center = desired.center
        return CropRect(center.x - width / 2, center.y - height / 2, width, height)

    def _pan_limited(
        self, previous: CropRect, desired: CropRect, prior_delta: Point
    ) -> tuple[CropRect, Point]:
        delta = Point(desired.center.x - previous.center.x, desired.center.y - previous.center.y)
        dead_zone = previous.height * self.config.pan_dead_zone_fraction
        if abs(delta.x) <= dead_zone:
            delta = Point(0, delta.y)
        if abs(delta.y) <= dead_zone:
            delta = Point(delta.x, 0)
        maximum = previous.height * self.config.max_pan_fraction
        delta = Point(
            min(max(delta.x, prior_delta.x - maximum), prior_delta.x + maximum),
            min(max(delta.y, prior_delta.y - maximum), prior_delta.y + maximum),
        )
        return (
            CropRect(
                previous.center.x + delta.x - desired.width / 2,
                previous.center.y + delta.y - desired.height / 2,
                desired.width,
                desired.height,
            ),
            delta,
        )
