from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import copysign, exp, inf, isclose, isfinite, log, nextafter, sqrt
from typing import Protocol, overload

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linprog  # type: ignore[import-untyped]
from scipy.sparse import coo_matrix, vstack  # type: ignore[import-untyped]

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
    detection_sampled: bool = True

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
class LookaheadPlannerFrameTrace:
    target_height_fraction: float
    desired_crop: CropRect
    detection_missed: bool
    smoothing_applied: bool
    containment_override: bool
    source_aspect_limited: bool
    action: str
    observed_height_fraction: float | None
    scale_relative_error: float | None
    scale_deadband_applied: bool
    scale_adjusting: bool
    lookahead_center_adjusted: bool
    sampled_detection_constraint: bool
    sampled_detection_contained: bool | None
    held_target_contained: bool | None
    pan_velocity_x_source_per_second: float | None
    pan_velocity_y_source_per_second: float | None
    pan_acceleration_x_source_per_second2: float | None
    pan_acceleration_y_source_per_second2: float | None
    pan_speed_limit_exceeded: bool
    pan_acceleration_limit_exceeded: bool


class PlannerError(RuntimeError):
    """The optimizer did not produce a validated framing optimum."""


@dataclass(frozen=True, slots=True)
class CropPlan(Sequence[CropRect]):
    crops: tuple[CropRect, ...]
    trace: tuple[PlannerFrameTrace | LookaheadPlannerFrameTrace, ...]

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


@dataclass(frozen=True, slots=True)
class _AxisInterval:
    """Pixel origins and normalized centers for an unchanged crop extent."""

    origin_lower: float
    origin_upper: float
    center_lower: float
    center_upper: float


class LookaheadCropPlanner:
    """Optimize camera centers, never athlete positions, over the complete shot."""

    pan_max_speed = 0.25
    pan_max_acceleration = 0.5
    solver_feasibility_tolerance = 1e-8

    def __init__(
        self,
        source_width: int,
        source_height: int,
        aspect_ratio: AspectRatio,
        profile: FramingProfile,
    ) -> None:
        self.seed_planner = DeterministicCropPlanner(
            source_width, source_height, aspect_ratio, profile
        )
        self.source_width = source_width
        self.source_height = source_height
        self.aspect_ratio = aspect_ratio

    def plan(self, measurements: Sequence[FrameMeasurement]) -> CropPlan:
        seed = self.seed_planner.plan(measurements)
        if not seed:
            return seed
        self._validate_geometry(seed.crops)
        for measurement in measurements:
            box = measurement.detector_bounds
            if box is not None and (
                not all(isfinite(value) for value in (box.x, box.y, box.width, box.height))
                or box.width <= 0
                or box.height <= 0
            ):
                raise PlannerError("Non-finite or non-positive detector geometry.")
        feasible = tuple(
            measurement.detection_sampled
            and measurement.detector_bounds is not None
            and measurement.detector_bounds.width <= crop.width
            and measurement.detector_bounds.height <= crop.height
            for measurement, crop in zip(measurements, seed.crops, strict=True)
        )
        for measurement, possible, trace in zip(measurements, feasible, seed.trace, strict=True):
            if (
                measurement.detection_sampled
                and measurement.detector_bounds is not None
                and not possible
                and not trace.source_aspect_limited
            ):
                raise PlannerError("Sampled detector cannot fit a non-limited seed crop.")
        intervals = tuple(
            (right.timestamp_ms - left.timestamp_ms) / 1000
            for left, right in pairwise(measurements)
        )
        # Each axis owns and releases its sparse matrices and LP results independently.
        origins_x = self._solve_axis(seed.crops, measurements, feasible, intervals, horizontal=True)
        origins_y = self._solve_axis(
            seed.crops, measurements, feasible, intervals, horizontal=False
        )
        crops = tuple(
            CropRect(x, y, crop.width, crop.height)
            for x, y, crop in zip(origins_x, origins_y, seed.crops, strict=True)
        )
        self._validate_geometry(crops)
        for crop, measurement, possible in zip(crops, measurements, feasible, strict=True):
            if possible and measurement.detector_bounds is not None:
                if not crop.contains(measurement.detector_bounds):
                    raise PlannerError("Validated crop does not contain its sampled detector.")
        return CropPlan(crops, self._traces(crops, seed, measurements, intervals))

    def _axis_intervals(
        self,
        crops: tuple[CropRect, ...],
        measurements: Sequence[FrameMeasurement],
        feasible: tuple[bool, ...],
        *,
        horizontal: bool,
    ) -> tuple[_AxisInterval, ...]:
        source = self.source_width if horizontal else self.source_height
        result: list[_AxisInterval] = []
        for crop, measurement, possible in zip(crops, measurements, feasible, strict=True):
            extent = crop.width if horizontal else crop.height
            lower, upper = 0.0, source - extent
            # Choose representable pixel bounds that also survive crop.right/bottom addition.
            if upper + extent > source:
                upper = nextafter(upper, -inf)
            box = measurement.detector_bounds
            if possible and box is not None:
                near, far = (box.x, box.right) if horizontal else (box.y, box.bottom)
                lower = max(lower, far - extent)
                upper = min(upper, near)
                if lower + extent < far:
                    lower = nextafter(lower, inf)
            if not isfinite(lower) or not isfinite(upper) or lower > upper:
                raise PlannerError("Sampled detector has an empty legal center interval.")
            result.append(
                _AxisInterval(
                    lower,
                    upper,
                    (lower + extent / 2) / source,
                    (upper + extent / 2) / source,
                )
            )
        return tuple(result)

    def _canonical_origins(
        self,
        centers: NDArray[np.float64],
        crops: tuple[CropRect, ...],
        legal: tuple[_AxisInterval, ...],
        *,
        horizontal: bool,
    ) -> tuple[float, ...]:
        source = self.source_width if horizontal else self.source_height
        tolerance = self.solver_feasibility_tolerance
        result: list[float] = []
        for index, (crop, bounds) in enumerate(zip(crops, legal, strict=True)):
            center = float(centers[index])
            if (
                not isfinite(center)
                or center < bounds.center_lower - tolerance
                or center > bounds.center_upper + tolerance
            ):
                raise PlannerError("Optimizer center is outside its legal interval.")
            extent = crop.width if horizontal else crop.height
            origin = center * source - extent / 2
            origin = min(max(origin, bounds.origin_lower), bounds.origin_upper)
            result.append(origin)
            # Validate motion using the actual reconstructed crop center, not solver metadata.
            centers[index] = (origin + extent / 2) / source
        return tuple(result)

    @staticmethod
    def _transitions(
        intervals: tuple[float, ...],
    ) -> tuple[tuple[tuple[tuple[int, float], ...], float], ...]:
        """Velocity changes with their time spans, including both shot/rest boundaries."""
        first = intervals[0]
        result: list[tuple[tuple[tuple[int, float], ...], float]] = [
            (((0, -1 / first), (1, 1 / first)), first / 2)
        ]
        for index in range(2, len(intervals) + 1):
            previous, current = intervals[index - 2], intervals[index - 1]
            result.append(
                (
                    (
                        (index - 2, 1 / previous),
                        (index - 1, -1 / previous - 1 / current),
                        (index, 1 / current),
                    ),
                    (previous + current) / 2,
                )
            )
        last = intervals[-1]
        result.append((((len(intervals) - 1, 1 / last), (len(intervals), -1 / last)), last / 2))
        return tuple(result)

    def _solve_axis(
        self,
        crops: tuple[CropRect, ...],
        measurements: Sequence[FrameMeasurement],
        feasible: tuple[bool, ...],
        intervals: tuple[float, ...],
        *,
        horizontal: bool,
    ) -> tuple[float, ...]:
        count = len(crops)
        source = self.source_width if horizontal else self.source_height
        legal = self._axis_intervals(crops, measurements, feasible, horizontal=horizontal)
        seed_centers = np.array(
            [(crop.center.x if horizontal else crop.center.y) / source for crop in crops],
            dtype=np.float64,
        )
        if count == 1:
            # Preserve the legal seed byte-for-byte rather than round-tripping its origin.
            origin = crops[0].x if horizontal else crops[0].y
            if not legal[0].origin_lower <= origin <= legal[0].origin_upper:
                return self._canonical_origins(seed_centers, crops, legal, horizontal=horizontal)
            return (origin,)

        speed_index, acceleration_index = count, count + 1
        deviation_start, variation_start = count + 2, 2 * count + 2
        variable_count = 3 * count + 2
        bounds: list[tuple[float, float | None]] = [
            (item.center_lower, item.center_upper) for item in legal
        ] + [(0.0, None)] * (variable_count - count)
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        limits: list[float] = []

        def add_row(coefficients: tuple[tuple[int, float], ...], limit: float) -> None:
            row = len(limits)
            for column, value in coefficients:
                rows.append(row)
                columns.append(column)
                values.append(value)
            limits.append(limit)

        for index, dt in enumerate(intervals, 1):
            for sign in (1.0, -1.0):
                add_row(
                    (
                        (index - 1, -sign / dt),
                        (index, sign / dt),
                        (speed_index, -1.0),
                    ),
                    self.pan_max_speed,
                )
        transitions = self._transitions(intervals)
        for index, (coefficients, duration) in enumerate(transitions):
            for sign in (1.0, -1.0):
                # Express acceleration in source/second² so feasibility tolerance has
                # the same meaning at short, long, and irregular frame intervals.
                add_row(
                    tuple((column, sign * value / duration) for column, value in coefficients)
                    + ((acceleration_index, -1.0),),
                    self.pan_max_acceleration,
                )
                add_row(
                    tuple((column, sign * value) for column, value in coefficients)
                    + ((variation_start + index, -1.0),),
                    0.0,
                )
        for index, center in enumerate(seed_centers):
            add_row(((index, 1.0), (deviation_start + index, -1.0)), float(center))
            add_row(((index, -1.0), (deviation_start + index, -1.0)), -float(center))
        matrix = coo_matrix(
            (values, (rows, columns)), shape=(len(limits), variable_count), dtype=np.float64
        ).tocsr()
        rhs = np.asarray(limits, dtype=np.float64)
        rows.clear()
        columns.clear()
        values.clear()
        limits.clear()
        weights = np.empty(count, dtype=np.float64)
        weights[0], weights[-1] = intervals[0] / 2, intervals[-1] / 2
        for index in range(1, count - 1):
            weights[index] = (intervals[index - 1] + intervals[index]) / 2
        tolerance = self.solver_feasibility_tolerance
        origins: tuple[float, ...] = ()
        for pass_index in range(4):
            objective = np.zeros(variable_count, dtype=np.float64)
            if pass_index == 0:
                objective[speed_index] = 1
            elif pass_index == 1:
                objective[acceleration_index] = 1
            elif pass_index == 2:
                objective[deviation_start:variation_start] = weights
            else:
                objective[variation_start:] = 1
            try:
                result = linprog(
                    objective,
                    A_ub=matrix,
                    b_ub=rhs,
                    bounds=bounds,
                    method="highs-ds",
                    options={
                        "primal_feasibility_tolerance": tolerance / 100,
                        "dual_feasibility_tolerance": tolerance / 100,
                    },
                )
            except (ValueError, RuntimeError) as error:
                raise PlannerError(
                    f"Optimizer invocation failed ({type(error).__name__})."
                ) from error
            if not result.success or result.status != 0:
                # Never expose arbitrary optimizer strings as user-facing text.
                message = " ".join(str(result.message).split())
                message = "".join(character for character in message if character.isprintable())
                raise PlannerError(f"Optimizer status {result.status}: {message[:240]}")
            solution = np.asarray(result.x, dtype=np.float64)
            optimum = float(result.fun)
            if (
                solution.shape != (variable_count,)
                or not np.all(np.isfinite(solution))
                or not isfinite(optimum)
                or abs(float(objective @ solution) - optimum) > tolerance
            ):
                raise PlannerError("Optimizer returned non-finite or inconsistent variables.")
            origins = self._canonical_origins(solution[:count], crops, legal, horizontal=horizontal)
            if np.any(matrix @ solution - rhs > tolerance):
                raise PlannerError("Canonical optimizer output violates linear constraints.")
            for value, (lower, upper) in zip(solution, bounds, strict=True):
                if value < lower - tolerance or (upper is not None and value > upper + tolerance):
                    raise PlannerError("Optimizer output violates variable bounds.")
            speed_excess = max(0.0, float(solution[speed_index]))
            acceleration_excess = max(0.0, float(solution[acceleration_index]))
            self._validate_axis_motion(
                solution[:count], intervals, speed_excess, acceleration_excess
            )
            if pass_index == 0:
                bounds[speed_index] = (0.0, max(0.0, optimum) + tolerance)
            elif pass_index == 1:
                bounds[acceleration_index] = (0.0, max(0.0, optimum) + tolerance)
            elif pass_index == 2:
                deviation_row = coo_matrix(
                    (
                        weights,
                        (
                            np.zeros(count, dtype=np.int32),
                            np.arange(deviation_start, variation_start),
                        ),
                    ),
                    shape=(1, variable_count),
                ).tocsr()
                matrix = vstack((matrix, deviation_row), format="csr")
                rhs = np.append(rhs, max(0.0, optimum) + tolerance)
                del deviation_row
            del result, solution, objective
        return origins

    def _validate_axis_motion(
        self,
        centers: NDArray[np.float64],
        intervals: tuple[float, ...],
        speed_excess: float,
        acceleration_excess: float,
    ) -> None:
        velocities = np.diff(centers) / np.asarray(intervals)
        tolerance = self.solver_feasibility_tolerance
        if np.any(np.abs(velocities) > self.pan_max_speed + speed_excess + tolerance):
            raise PlannerError("Canonical crop path exceeds the optimized speed envelope.")
        accelerations = [
            2 * float(velocities[0]) / intervals[0],
            -2 * float(velocities[-1]) / intervals[-1],
        ]
        accelerations.extend(
            2
            * float(velocities[index] - velocities[index - 1])
            / (intervals[index] + intervals[index - 1])
            for index in range(1, len(intervals))
        )
        if any(
            abs(value) > self.pan_max_acceleration + acceleration_excess + tolerance
            for value in accelerations
        ):
            raise PlannerError("Canonical crop path exceeds the optimized acceleration envelope.")

    def _validate_geometry(self, crops: tuple[CropRect, ...]) -> None:
        for crop in crops:
            if (
                not all(isfinite(value) for value in (crop.x, crop.y, crop.width, crop.height))
                or crop.width <= 0
                or crop.height <= 0
                or not 0 <= crop.x < crop.right <= self.source_width
                or not 0 <= crop.y < crop.bottom <= self.source_height
                or not isclose(
                    crop.width / crop.height,
                    self.aspect_ratio.value_float,
                    rel_tol=self.solver_feasibility_tolerance,
                )
            ):
                raise PlannerError("Crop path has invalid source/aspect geometry.")

    def _limit_exceeded(self, value: float, limit: float) -> bool:
        boundary = limit + self.solver_feasibility_tolerance
        return value > boundary and not isclose(value, boundary, rel_tol=0, abs_tol=1e-12)

    def _traces(
        self,
        crops: tuple[CropRect, ...],
        seed: CropPlan,
        measurements: Sequence[FrameMeasurement],
        intervals: tuple[float, ...],
    ) -> tuple[LookaheadPlannerFrameTrace, ...]:
        velocities = tuple(
            (
                (current.center.x - previous.center.x) / self.source_width / dt,
                (current.center.y - previous.center.y) / self.source_height / dt,
            )
            for (previous, current), dt in zip(pairwise(crops), intervals, strict=True)
        )
        traces: list[LookaheadPlannerFrameTrace] = []
        for index, (crop, measurement, causal) in enumerate(
            zip(crops, measurements, seed.trace, strict=True)
        ):
            velocity = velocities[index - 1] if index else (None, None)
            acceleration: tuple[float | None, float | None] = (None, None)
            boundary_acceleration = 0.0
            if index >= 2:
                dt = (intervals[index - 2] + intervals[index - 1]) / 2
                acceleration = (
                    (velocities[index - 1][0] - velocities[index - 2][0]) / dt,
                    (velocities[index - 1][1] - velocities[index - 2][1]) / dt,
                )
            if velocities and index == 0:
                boundary_acceleration = (
                    max(abs(value) for value in velocities[0]) * 2 / intervals[0]
                )
            if velocities and index == len(crops) - 1:
                boundary_acceleration = max(
                    boundary_acceleration,
                    max(abs(value) for value in velocities[-1]) * 2 / intervals[-1],
                )
            speed = max((abs(value) for value in velocity if value is not None), default=0.0)
            acceleration_magnitude = max(
                boundary_acceleration,
                max((abs(value) for value in acceleration if value is not None), default=0.0),
            )
            box = measurement.detector_bounds
            sampled = measurement.detection_sampled and box is not None
            moved = index > 0 and crop.center != crops[index - 1].center
            if causal.source_aspect_limited:
                action = "source_aspect_limited"
            elif index == 0:
                action = "initial"
            elif causal.detection_missed:
                action = "widen_on_miss"
            else:
                action = "lookahead_pan" if moved else "lookahead_hold"
            traces.append(
                LookaheadPlannerFrameTrace(
                    target_height_fraction=causal.target_height_fraction,
                    desired_crop=causal.desired_crop,
                    detection_missed=causal.detection_missed,
                    smoothing_applied=index > 0 and crop != crops[index - 1],
                    containment_override=False,
                    source_aspect_limited=causal.source_aspect_limited,
                    action=action,
                    observed_height_fraction=causal.observed_height_fraction,
                    scale_relative_error=causal.scale_relative_error,
                    scale_deadband_applied=causal.scale_deadband_applied,
                    scale_adjusting=causal.scale_adjusting,
                    lookahead_center_adjusted=crop.center != seed.crops[index].center,
                    sampled_detection_constraint=sampled,
                    sampled_detection_contained=crop.contains(box) if sampled and box else None,
                    held_target_contained=(
                        crop.contains(box) if not measurement.detection_sampled and box else None
                    ),
                    pan_velocity_x_source_per_second=velocity[0],
                    pan_velocity_y_source_per_second=velocity[1],
                    pan_acceleration_x_source_per_second2=acceleration[0],
                    pan_acceleration_y_source_per_second2=acceleration[1],
                    pan_speed_limit_exceeded=self._limit_exceeded(speed, self.pan_max_speed),
                    pan_acceleration_limit_exceeded=self._limit_exceeded(
                        acceleration_magnitude, self.pan_max_acceleration
                    ),
                )
            )
        return tuple(traces)
