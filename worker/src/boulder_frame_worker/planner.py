from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, overload

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
    detector_bounds: Rect | None
    confidence: float = 0

    @property
    def missed(self) -> bool:
        return self.detector_bounds is None


@dataclass(frozen=True, slots=True)
class PlannerFrameTrace:
    target_height_fraction: float
    desired_crop: CropRect
    detection_missed: bool
    smoothing_applied: bool
    containment_override: bool
    source_aspect_limited: bool
    action: str


@dataclass(frozen=True, slots=True)
class CropPlan(Sequence[CropRect]):
    crops: tuple[CropRect, ...]
    trace: tuple[PlannerFrameTrace, ...]

    def __post_init__(self) -> None:
        if len(self.crops) != len(self.trace):
            raise ValueError("crop plan records must have matching frame counts")

    def __len__(self) -> int:
        return len(self.crops)

    @overload
    def __getitem__(self, index: int) -> CropRect: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[CropRect]: ...

    def __getitem__(self, index: int | slice) -> CropRect | tuple[CropRect, ...]:
        return self.crops[index]


PROFILE_TARGET_HEIGHT_FRACTIONS: dict[FramingProfile, float] = {
    FramingProfile.TIGHT: 0.60,
    FramingProfile.BALANCED: 0.50,
    FramingProfile.SAFE: 0.40,
    FramingProfile.FULL_MOVEMENT: 0.33,
}


class CropPlanner(Protocol):
    def plan(self, measurements: Sequence[FrameMeasurement]) -> CropPlan: ...


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
    return CropRect(
        min(max(crop.x, 0), source_width - crop.width),
        min(max(crop.y, 0), source_height - crop.height),
        crop.width,
        crop.height,
    )


class DeterministicCropPlanner:
    """Causal detector-box controller with no target-position extrapolation."""

    center_alpha = 0.35
    height_alpha = 0.25
    miss_widen_alpha = 0.35

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
        self.target_height_fraction = PROFILE_TARGET_HEIGHT_FRACTIONS[profile]
        self.full_frame = full_frame_crop(source_width, source_height, aspect_ratio)

    def plan(self, measurements: Sequence[FrameMeasurement]) -> CropPlan:
        crops: list[CropRect] = []
        traces: list[PlannerFrameTrace] = []
        previous: CropRect | None = None
        for measurement in measurements:
            detection = measurement.detector_bounds
            if detection is None:
                desired = self.full_frame if previous is None else self._widen(previous)
                crop = desired
                action = "full_frame" if previous is None else "widen_on_miss"
                traces.append(
                    PlannerFrameTrace(
                        self.target_height_fraction,
                        desired,
                        True,
                        previous is not None,
                        False,
                        False,
                        action,
                    )
                )
            else:
                desired = self._desired_crop(detection)
                smoothed = desired if previous is None else self._smooth(previous, desired)
                crop, source_aspect_limited = self._contain(smoothed, detection)
                contained = crop != smoothed and not source_aspect_limited
                traces.append(
                    PlannerFrameTrace(
                        self.target_height_fraction,
                        desired,
                        False,
                        previous is not None,
                        contained,
                        source_aspect_limited,
                        "source_aspect_limited"
                        if source_aspect_limited
                        else "containment_override"
                        if contained
                        else "smoothed"
                        if previous
                        else "initial",
                    )
                )
            crop = clamp_crop(crop, self.source_width, self.source_height)
            crops.append(crop)
            previous = crop
        return CropPlan(tuple(crops), tuple(traces))

    def _desired_crop(self, detection: Rect) -> CropRect:
        height = min(self.full_frame.height, detection.height / self.target_height_fraction)
        width = height * self.aspect_ratio.value_float
        if width > self.full_frame.width:
            width, height = self.full_frame.width, self.full_frame.height
        center = detection.center
        return clamp_crop(
            CropRect(center.x - width / 2, center.y - height / 2, width, height),
            self.source_width,
            self.source_height,
        )

    def _smooth(self, previous: CropRect, desired: CropRect) -> CropRect:
        height = previous.height + (desired.height - previous.height) * self.height_alpha
        width = height * self.aspect_ratio.value_float
        center = Point(
            previous.center.x + (desired.center.x - previous.center.x) * self.center_alpha,
            previous.center.y + (desired.center.y - previous.center.y) * self.center_alpha,
        )
        return clamp_crop(
            CropRect(center.x - width / 2, center.y - height / 2, width, height),
            self.source_width,
            self.source_height,
        )

    def _widen(self, previous: CropRect) -> CropRect:
        height = (
            previous.height + (self.full_frame.height - previous.height) * self.miss_widen_alpha
        )
        width = height * self.aspect_ratio.value_float
        center = previous.center
        return clamp_crop(
            CropRect(center.x - width / 2, center.y - height / 2, width, height),
            self.source_width,
            self.source_height,
        )

    def _contain(self, crop: CropRect, detection: Rect) -> tuple[CropRect, bool]:
        if detection.width > self.full_frame.width or detection.height > self.full_frame.height:
            # No valid crop of the requested aspect can contain this box. Preserve as much of
            # the current detection as source/aspect bounds allow without falsely claiming it.
            return (
                clamp_crop(
                    CropRect(
                        detection.center.x - self.full_frame.width / 2,
                        detection.center.y - self.full_frame.height / 2,
                        self.full_frame.width,
                        self.full_frame.height,
                    ),
                    self.source_width,
                    self.source_height,
                ),
                True,
            )
        required_height = max(
            crop.height, detection.height, detection.width / self.aspect_ratio.value_float
        )
        height = min(required_height, self.full_frame.height)
        width = height * self.aspect_ratio.value_float
        x = min(crop.x, detection.x)
        x = max(x, detection.right - width)
        y = min(crop.y, detection.y)
        y = max(y, detection.bottom - height)
        return (
            clamp_crop(CropRect(x, y, width, height), self.source_width, self.source_height),
            False,
        )
