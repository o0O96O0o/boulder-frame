from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import copysign, exp, isclose, log, sqrt
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
    timestamp_ms: int
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
    observed_height_fraction: float | None
    scale_relative_error: float | None
    center_error_x_fraction: float | None
    center_error_y_fraction: float | None
    scale_deadband_applied: bool
    scale_adjusting: bool
    center_deadband_applied: bool
    center_adjusting: bool


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

    zoom_max_speed = 0.5
    zoom_max_acceleration = 1.0
    pan_max_speed = 0.25
    pan_max_acceleration = 0.5
    scale_enter_fraction = 0.05
    scale_exit_fraction = 0.02
    center_enter_fraction = 0.01
    center_exit_fraction = 0.004

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
        previous_timestamp: int | None = None
        velocities = (0.0, 0.0, 0.0)
        scale_adjusting = center_adjusting = False
        for measurement in measurements:
            timestamp = measurement.timestamp_ms
            if type(timestamp) is not int or timestamp < 0:
                raise ValueError("measurement timestamp_ms must be a non-negative integer")
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError("measurement timestamps must be strictly increasing")
            dt = 0.0 if previous_timestamp is None else (timestamp - previous_timestamp) / 1000
            previous_timestamp = timestamp
            detection = measurement.detector_bounds
            observed_fraction = scale_error = x_error = y_error = None
            scale_held = center_held = False
            source_aspect_limited = False
            smoothing_applied = False
            if detection is None:
                scale_adjusting = center_adjusting = False
                if previous is None:
                    desired = candidate = self.full_frame
                else:
                    center = previous.center
                    desired = CropRect(
                        center.x - self.full_frame.width / 2,
                        center.y - self.full_frame.height / 2,
                        self.full_frame.width,
                        self.full_frame.height,
                    )
                    # Missing observations must never extrapolate position or keep zooming in.
                    # These safety cancellations deliberately supersede acceleration limits.
                    velocities = (0.0, 0.0, max(0.0, velocities[2]))
                    candidate, velocities = self._adjust(
                        previous, desired, True, False, velocities, dt
                    )
                    smoothing_applied = candidate != previous
                action = "full_frame" if previous is None else "widen_on_miss"
            else:
                desired = self._desired_crop(detection)
                if previous is None:
                    candidate = desired
                else:
                    observed_fraction = detection.height / previous.height
                    scale_error = observed_fraction / self.target_height_fraction - 1
                    previous_center = previous.center
                    desired_center = desired.center
                    x_error = (desired_center.x - previous_center.x) / previous.width
                    y_error = (desired_center.y - previous_center.y) / previous.height
                    scale_threshold = (
                        self.scale_exit_fraction if scale_adjusting else self.scale_enter_fraction
                    )
                    center_threshold = (
                        self.center_exit_fraction
                        if center_adjusting
                        else self.center_enter_fraction
                    )
                    scale_adjusting = self._outside_deadband(scale_error, scale_threshold)
                    center_adjusting = self._outside_deadband(
                        x_error, center_threshold
                    ) or self._outside_deadband(y_error, center_threshold)
                    scale_held = not scale_adjusting
                    center_held = not center_adjusting
                    smoothing_applied = scale_adjusting or center_adjusting or any(velocities)
                    candidate, velocities = self._adjust(
                        previous, desired, scale_adjusting, center_adjusting, velocities, dt
                    )
                action = (
                    "smoothed"
                    if smoothing_applied
                    else "deadband_hold"
                    if previous is not None
                    else "initial"
                )
            bounded = candidate
            if candidate.width > self.full_frame.width or candidate.height > self.full_frame.height:
                center = candidate.center
                bounded = CropRect(
                    center.x - self.full_frame.width / 2,
                    center.y - self.full_frame.height / 2,
                    self.full_frame.width,
                    self.full_frame.height,
                )
            crop = clamp_crop(bounded, self.source_width, self.source_height)
            if detection is not None:
                crop, source_aspect_limited = self._contain(crop, detection)
            contained = crop != candidate and not source_aspect_limited
            if crop != candidate:
                # Synchronize only corrected components: safety must not leave hidden momentum.
                candidate_center, center = candidate.center, crop.center
                velocities = (
                    velocities[0] if center.x == candidate_center.x else 0.0,
                    velocities[1] if center.y == candidate_center.y else 0.0,
                    velocities[2] if crop.height == candidate.height else 0.0,
                )
            if source_aspect_limited:
                action = "source_aspect_limited"
            elif contained:
                action = "containment_override"
            traces.append(
                PlannerFrameTrace(
                    target_height_fraction=self.target_height_fraction,
                    desired_crop=desired,
                    detection_missed=detection is None,
                    smoothing_applied=smoothing_applied,
                    containment_override=contained,
                    source_aspect_limited=source_aspect_limited,
                    action=action,
                    observed_height_fraction=observed_fraction,
                    scale_relative_error=scale_error,
                    center_error_x_fraction=x_error,
                    center_error_y_fraction=y_error,
                    scale_deadband_applied=scale_held,
                    scale_adjusting=scale_adjusting,
                    center_deadband_applied=center_held,
                    center_adjusting=center_adjusting,
                )
            )
            crops.append(crop)
            previous = crop
        return CropPlan(tuple(crops), tuple(traces))

    @staticmethod
    def _outside_deadband(error: float, threshold: float) -> bool:
        # Division and center subtraction can round an exact boundary just above it.
        # Treat only floating-point noise as equality, preserving inclusive hold/exit bands.
        magnitude = abs(error)
        return magnitude > threshold and not isclose(magnitude, threshold, rel_tol=1e-12)

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

    def _adjust(
        self,
        previous: CropRect,
        desired: CropRect,
        scale_adjusting: bool,
        center_adjusting: bool,
        velocities: tuple[float, float, float],
        dt: float,
    ) -> tuple[CropRect, tuple[float, float, float]]:
        if not scale_adjusting and not center_adjusting and not any(velocities):
            return previous, velocities
        vx, vy, vz = velocities
        center, target = previous.center, desired.center
        x, y = center.x, center.y
        if center_adjusting or vx:
            x, vx = self._advance_motion(
                x / self.source_width,
                vx,
                target.x / self.source_width if center_adjusting else None,
                dt,
                self.pan_max_speed,
                self.pan_max_acceleration,
            )
            x *= self.source_width
        if center_adjusting or vy:
            y, vy = self._advance_motion(
                y / self.source_height,
                vy,
                target.y / self.source_height if center_adjusting else None,
                dt,
                self.pan_max_speed,
                self.pan_max_acceleration,
            )
            y *= self.source_height
        height, width = previous.height, previous.width
        if scale_adjusting or vz:
            position = log(height)
            target_height = log(desired.height) if scale_adjusting else None
            updated, vz = self._advance_motion(
                position, vz, target_height, dt, self.zoom_max_speed, self.zoom_max_acceleration
            )
            if updated != position:
                height = desired.height if updated == target_height else exp(updated)
                width = height * self.aspect_ratio.value_float
                if height == self.full_frame.height:
                    width = self.full_frame.width
        return (
            CropRect(
                previous.x if x == center.x and width == previous.width else x - width / 2,
                previous.y if y == center.y and height == previous.height else y - height / 2,
                width,
                height,
            ),
            (vx, vy, vz),
        )

    @staticmethod
    def _advance_motion(
        position: float,
        velocity: float,
        target: float | None,
        dt: float,
        max_speed: float,
        acceleration: float,
    ) -> tuple[float, float]:
        """Integrate exact constant-acceleration phases, independent of frame interval.

        A closed gate brakes to rest. An open gate uses a triangular/trapezoidal
        velocity profile ending at rest at its target. Retargets retain velocity;
        a target moved inside the stopping distance can necessarily be crossed
        while braking, unlike a stationary target approached from rest.
        """
        distance = 0.0 if target is None else target - position
        if velocity and (
            target is None
            or velocity * distance <= 0
            or velocity * velocity / (2 * acceleration) > abs(distance)
        ):
            stop_time = abs(velocity) / acceleration
            elapsed = min(dt, stop_time)
            braking = -copysign(acceleration, velocity)
            position += velocity * elapsed + braking * elapsed * elapsed / 2
            if dt < stop_time:
                return position, velocity + braking * elapsed
            velocity = 0.0
            dt -= stop_time
        if target is None:
            return position, velocity
        distance = target - position
        if distance == 0 and velocity == 0:
            return target, 0.0
        direction = copysign(1.0, distance)
        distance = abs(distance)
        speed = velocity * direction
        peak = min(max_speed, sqrt(acceleration * distance + speed * speed / 2))
        accelerate_time = max(0.0, (peak - speed) / acceleration)
        if dt < accelerate_time:
            return (
                position + direction * (speed * dt + acceleration * dt * dt / 2),
                direction * (speed + acceleration * dt),
            )
        acceleration_distance = (speed + peak) * accelerate_time / 2
        position += direction * acceleration_distance
        dt -= accelerate_time
        cruise_distance = max(
            0.0, distance - acceleration_distance - peak * peak / (2 * acceleration)
        )
        cruise_time = cruise_distance / peak if peak else 0.0
        if dt < cruise_time:
            return position + direction * peak * dt, direction * peak
        position += direction * cruise_distance
        dt -= cruise_time
        if dt < peak / acceleration:
            return (
                position + direction * (peak * dt - acceleration * dt * dt / 2),
                direction * (peak - acceleration * dt),
            )
        return target, 0.0

    def _contain(self, crop: CropRect, detection: Rect) -> tuple[CropRect, bool]:
        if crop.contains(detection):
            return crop, False
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
        width = crop.width if height == crop.height else height * self.aspect_ratio.value_float
        x = min(crop.x, detection.x)
        x = max(x, detection.right - width)
        y = min(crop.y, detection.y)
        y = max(y, detection.bottom - height)
        return (
            clamp_crop(CropRect(x, y, width, height), self.source_width, self.source_height),
            False,
        )
