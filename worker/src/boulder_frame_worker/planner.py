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


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    base_padding: float
    uncertainty_padding: float
    lead_fraction: float
    max_zoom_out_factor: float = 1.25
    max_zoom_in_factor: float = 0.96
    high_confidence: float = 0.8
    stable_hold_frames: int = 3


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
    """Conservative local controller; it deliberately uses no model prediction."""

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

    def _desired_crop(self, measurement: FrameMeasurement) -> CropRect:
        if measurement.lost or measurement.root is None or measurement.bounds is None:
            return self.full_frame
        uncertainty = self.config.uncertainty_padding * (1 - max(0, min(measurement.confidence, 1)))
        padding = self.config.base_padding + uncertainty
        required_width = measurement.bounds.width * (1 + 2 * padding)
        required_height = measurement.bounds.height * (1 + 2 * padding)
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
        crops: list[CropRect] = []
        previous: CropRect | None = None
        stable_frames = 0
        for measurement in measurements:
            desired = self._desired_crop(measurement)
            if previous is None:
                crop = desired
            elif measurement.lost or measurement.confidence < self.config.high_confidence:
                crop = self._rate_limited(previous, desired, self.config.max_zoom_out_factor)
                stable_frames = 0
            else:
                stable_frames += 1
                factor = (
                    self.config.max_zoom_in_factor
                    if stable_frames >= self.config.stable_hold_frames
                    else 1.0
                )
                crop = self._rate_limited(previous, desired, factor)
            crop = clamp_crop(crop, self.source_width, self.source_height)
            crops.append(crop)
            previous = crop
        return crops

    def _rate_limited(self, previous: CropRect, desired: CropRect, zoom_factor: float) -> CropRect:
        # A larger height is a zoom out, so it may move by a larger factor than a zoom in.
        if desired.height > previous.height:
            height = min(desired.height, previous.height * self.config.max_zoom_out_factor)
        else:
            height = max(desired.height, previous.height * zoom_factor)
        width = height * self.aspect_ratio.value_float
        center = desired.center
        return CropRect(center.x - width / 2, center.y - height / 2, width, height)
