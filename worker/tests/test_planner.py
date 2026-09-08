from itertools import pairwise
from math import log
from struct import pack

import numpy as np
import pytest
from scipy.optimize import OptimizeResult

import boulder_frame_worker.planner as planner_module
from boulder_frame_worker.measurement import Rect
from boulder_frame_worker.planner import (
    PROFILE_TARGET_HEIGHT_FRACTIONS,
    CropPlan,
    DeterministicCropPlanner,
    FrameMeasurement,
    LookaheadCropPlanner,
    LookaheadPlannerFrameTrace,
    PlannerError,
)
from boulder_frame_worker.protocol import AspectRatio, FramingProfile


def planner(profile: FramingProfile = FramingProfile.BALANCED) -> DeterministicCropPlanner:
    return DeterministicCropPlanner(3840, 2160, AspectRatio.LANDSCAPE, profile)


def centered_box(
    height: float, center_x: float = 1920, center_y: float = 1080, width: float = 200
) -> Rect:
    return Rect(center_x - width / 2, center_y - height / 2, width, height)


def measurements(boxes: list[Rect | None], interval_ms: int = 20) -> list[FrameMeasurement]:
    return [FrameMeasurement(box, index * interval_ms) for index, box in enumerate(boxes)]


def test_balanced_targets_detector_box_at_half_crop_height() -> None:
    box = Rect(1600, 600, 200, 400)
    crop = planner().plan([FrameMeasurement(box, 0)])[0]
    assert crop.height == pytest.approx(800)
    assert box.height / crop.height == pytest.approx(0.5)
    assert crop.width / crop.height == pytest.approx(16 / 9)
    assert crop.contains(box)


def test_profiles_order_from_tightest_to_widest_fixed_target_size() -> None:
    box = Rect(1600, 600, 200, 400)
    sizes = [
        planner(profile).plan([FrameMeasurement(box, 0)])[0].height for profile in FramingProfile
    ]
    assert sizes == sorted(sizes)


@pytest.mark.parametrize("timestamps", [[-1, 0], [0, 0], [100, 99], [0, 1.5], [0, True]])
def test_timestamps_reject_non_increasing_or_non_integer_values(timestamps: list[int]) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        planner().plan([FrameMeasurement(centered_box(400), timestamp) for timestamp in timestamps])


def test_plan_state_is_local_and_absolute_timestamp_origin_does_not_affect_motion() -> None:
    controller = planner()
    sequence = measurements([centered_box(400), centered_box(500, 2100), None])
    expected = controller.plan(sequence)
    controller.plan(measurements([None, centered_box(200), centered_box(300, 1200)]))
    assert controller.plan(sequence) == expected
    shifted = [
        FrameMeasurement(item.detector_bounds, item.timestamp_ms + 50000) for item in sequence
    ]
    assert controller.plan(shifted) == expected


@pytest.mark.parametrize("profile", list(FramingProfile))
def test_scale_jitter_holds_byte_identical_dimensions(profile: FramingProfile) -> None:
    result = planner(profile).plan(
        measurements([centered_box(height) for height in [401.23456789, 408, 392, 415, 401, 389]])
    )
    original_size = pack("!dd", result[0].width, result[0].height)
    for crop, trace in zip(result[1:], result.trace[1:], strict=True):
        assert pack("!dd", crop.width, crop.height) == original_size
        assert trace.scale_deadband_applied
        assert not trace.scale_adjusting
        assert not trace.containment_override


def test_center_and_scale_jitter_hold_exact_rectangle_without_round_trip_drift() -> None:
    x, y = 1900.123456789, 1070.987654321
    result = planner().plan(
        measurements(
            [
                centered_box(401.23456789, x, y),
                centered_box(410, x + 8, y - 3),
                centered_box(398, x - 7, y + 2),
                centered_box(404, x + 4, y - 1),
            ]
        )
    )
    assert all(crop == result[0] for crop in result)
    for trace in result.trace[1:]:
        assert trace.scale_deadband_applied and trace.center_deadband_applied
        assert not trace.scale_adjusting and not trace.center_adjusting
        assert not trace.smoothing_applied


@pytest.mark.parametrize("gate", ["scale", "x", "y"])
@pytest.mark.parametrize("direction", [-1, 1])
def test_hysteresis_inclusive_boundaries_and_independent_gates(gate: str, direction: int) -> None:
    controller = planner()
    sequence = [FrameMeasurement(centered_box(400), 0)]
    errors = (
        [0.05, 0.050001, 0.035, 0.020001, 0.02, 0.035]
        if gate == "scale"
        else [0.01, 0.010001, 0.006, 0.004001, 0.004, 0.006]
    )
    expected = [False, True, True, True, False, False]
    for index, (error, active) in enumerate(zip(errors, expected, strict=True), start=1):
        prior = controller.plan(sequence)[-1]
        box = centered_box(
            prior.height * 0.5 * (1 + direction * error) if gate == "scale" else 400,
            prior.center.x + direction * error * prior.width if gate == "x" else 1920,
            prior.center.y + direction * error * prior.height if gate == "y" else 1080,
        )
        sequence.append(FrameMeasurement(box, index * 10))
        result = controller.plan(sequence)
        trace = result.trace[-1]
        assert (trace.scale_adjusting if gate == "scale" else trace.center_adjusting) is active
        assert not (trace.center_adjusting if gate == "scale" else trace.scale_adjusting)
        if index == 1:
            assert result[-1] == result[-2]
        if index == 5:
            # Closing the gate brakes rather than snapping the moving crop to a stop.
            assert trace.smoothing_applied
            assert result[-1] != result[-2]


def test_gradual_scale_change_accumulates_against_held_crop_not_previous_detection() -> None:
    result = planner().plan(
        measurements([centered_box(height) for height in [400, 404, 408, 412, 416, 420, 424]])
    )
    assert all(crop == result[0] for crop in result[:6])
    assert result[5].height < result[6].height < 848
    assert result.trace[6].scale_adjusting
    assert not result.trace[6].center_adjusting


@pytest.mark.parametrize("zoom_out", [False, True])
def test_stationary_target_motion_is_bounded_monotone_and_settles_exactly(zoom_out: bool) -> None:
    initial = centered_box(400 if zoom_out else 600, 1600, 1080)
    target = centered_box(700 if zoom_out else 400, 2050, 1120)
    result = planner().plan(measurements([initial] + [target] * 400, 10))
    assert not any(trace.containment_override for trace in result.trace)
    values = [
        [crop.center.x / 3840 for crop in result],
        [crop.center.y / 2160 for crop in result],
        [log(crop.height) for crop in result],
    ]
    destinations = [2050 / 3840, 1120 / 2160, log(target.height * 2)]
    for coordinates, destination, speed, acceleration in zip(
        values, destinations, [0.25, 0.25, 0.5], [0.5, 0.5, 1.0], strict=True
    ):
        differences = [right - left for left, right in pairwise(coordinates)]
        assert max(abs(delta) for delta in differences) <= speed * 0.01 + 1e-12
        assert (
            max(abs(right - left) for left, right in pairwise(differences))
            <= acceleration * 0.01**2 + 1e-12
        )
        assert abs(differences[0]) == pytest.approx(acceleration * 0.01**2 / 2)
        direction = 1 if destination > coordinates[0] else -1
        assert all(delta * direction >= -1e-12 for delta in differences)
        assert all(
            min(coordinates[0], destination) - 1e-12
            <= value
            <= max(coordinates[0], destination) + 1e-12
            for value in coordinates
        )
        assert differences[-1] == 0
    settling = [
        trace
        for trace in result.trace
        if trace.smoothing_applied
        and (trace.scale_deadband_applied or trace.center_deadband_applied)
    ]
    assert settling
    assert all(crop == result[-1] for crop in result[-50:])
    assert not result.trace[-1].smoothing_applied
    assert all(crop.contains(target) for crop in result[1:])


def test_retarget_preserves_velocity_and_brakes_before_reversing() -> None:
    forward = centered_box(250, 2200)
    reverse = centered_box(450, 1750)
    sequence = measurements([centered_box(400)] + [forward] * 20 + [reverse] * 300, 10)
    result = planner().plan(sequence)
    assert not any(trace.containment_override for trace in result.trace)
    # Both targets reverse abruptly, but pan keeps moving right and zoom keeps moving inward.
    assert result[21].center.x > result[20].center.x
    assert result[21].height < result[20].height
    for values, acceleration in [
        ([crop.center.x / 3840 for crop in result], 0.5),
        ([log(crop.height) for crop in result], 1.0),
    ]:
        deltas = [right - left for left, right in pairwise(values)]
        assert (
            max(abs(right - left) for left, right in pairwise(deltas))
            <= acceleration * 0.01**2 + 1e-12
        )
    assert result[-1].center.x < result[20].center.x
    assert result[-1].height > result[20].height
    assert result[-1] == result[-20]


def test_timestamp_intervals_not_frame_counts_determine_acceleration() -> None:
    first, target = centered_box(400), centered_box(650, 2200)
    controller = planner()
    coarse = controller.plan([FrameMeasurement(first, 0), FrameMeasurement(target, 200)])
    fine = controller.plan(measurements([first] + [target] * 20, 10))
    assert coarse[-1].center.x == pytest.approx(fine[-1].center.x, abs=1e-9)
    assert coarse[-1].height == pytest.approx(fine[-1].height, abs=1e-9)
    short = controller.plan([FrameMeasurement(first, 0), FrameMeasurement(target, 100)])
    assert coarse[-1].center.x - coarse[0].center.x == pytest.approx(
        4 * (short[-1].center.x - short[0].center.x)
    )


def test_irregular_frame_rates_follow_same_trajectory_and_settle_in_deadbands() -> None:
    first, target = centered_box(400), centered_box(650, 2200)
    controller = planner()
    plans = []
    for interval in [10, 20, 40]:
        plans.append(
            controller.plan(measurements([first] + [target] * (4000 // interval), interval))
        )
    irregular = [0, 17, 49, 103, 180, 200, 271, 400, 711, 1000, 1600, 2400, 3200, 4000]
    plans.append(
        controller.plan(
            [FrameMeasurement(first if time == 0 else target, time) for time in irregular]
        )
    )
    for result in plans:
        assert (
            abs(result[-1].center.x - 2200) / result[-1].width <= controller.center_enter_fraction
        )
        assert abs(target.height / result[-1].height / 0.5 - 1) <= controller.scale_enter_fraction
        assert not result.trace[-1].smoothing_applied
    assert (
        max(result[-1].height for result in plans) - min(result[-1].height for result in plans) < 15
    )
    assert (
        max(result[-1].center.x for result in plans) - min(result[-1].center.x for result in plans)
        < 10
    )


def test_miss_cancels_pan_and_inward_zoom_then_widens_with_bounded_outward_motion() -> None:
    sequence = measurements([centered_box(400)] + [centered_box(250, 2200)] * 20 + [None] * 300, 10)
    result = planner().plan(sequence)
    assert result[20].center.x > result[19].center.x
    assert result[20].height < result[19].height
    assert result[21].center == result[20].center
    assert result[21].height > result[20].height
    assert log(result[21].height / result[20].height) == pytest.approx(0.5 * 0.01**2)
    assert all(right.height >= left.height for left, right in pairwise(result[20:]))
    assert result[-1] == planner().full_frame
    assert not result.trace[-1].smoothing_applied
    for trace in result.trace[21:]:
        assert not trace.scale_adjusting and not trace.center_adjusting
        assert trace.observed_height_fraction is None


def test_miss_resets_gates_and_reacquisition_brakes_remaining_outward_zoom() -> None:
    controller = planner()
    sequence = measurements([centered_box(400), centered_box(480, 2020), None], 100)
    reference = controller.plan(sequence)[-1]
    sequence.append(
        FrameMeasurement(
            centered_box(
                reference.height * 0.5 * 1.03,
                reference.center.x + reference.width * 0.006,
                reference.center.y,
            ),
            210,
        )
    )
    result = controller.plan(sequence)
    assert result[2].center == result[1].center
    assert result[3].center == result[2].center
    assert result[3].height > result[2].height
    assert result.trace[3].scale_deadband_applied and result.trace[3].center_deadband_applied
    assert result.trace[3].smoothing_applied


def test_containment_overrides_held_gates_only_when_detection_would_be_clipped() -> None:
    boxes = [
        centered_box(400),
        centered_box(400, 1930, width=1300),
        centered_box(400, 1930, width=1420),
        centered_box(400, 1930, width=1450),
    ]
    result = planner().plan(measurements(boxes))
    assert result[1] == result[0]
    assert not result.trace[1].containment_override
    for index in (2, 3):
        assert not result[index - 1].contains(boxes[index])
        assert result[index].contains(boxes[index])
        assert result.trace[index].scale_deadband_applied
        assert result.trace[index].center_deadband_applied
        assert result.trace[index].containment_override
    assert result[2].height == result[1].height
    assert result[3].height > result[2].height


def test_containment_correction_cancels_pan_momentum_without_windup() -> None:
    controller = planner()
    sequence = measurements([centered_box(400)] + [centered_box(400, 2200)] * 20, 10)
    sequence.append(FrameMeasurement(centered_box(400, 3100), 210))
    corrected = controller.plan(sequence)
    assert corrected.trace[-1].containment_override
    assert corrected[-1].contains(centered_box(400, 3100))
    reference = corrected[-1]
    sequence.append(
        FrameMeasurement(centered_box(400, reference.center.x, reference.center.y), 220)
    )
    result = controller.plan(sequence)
    assert result[-1] == reference
    assert not result.trace[-1].smoothing_applied


def test_target_moved_inside_stopping_distance_is_crossed_without_velocity_snap() -> None:
    controller = planner()
    sequence = measurements([centered_box(400)] + [centered_box(400, 2200)] * 20, 10)
    reference = controller.plan(sequence)[-1]
    target_x = reference.center.x + 20
    sequence.extend(
        FrameMeasurement(centered_box(400, target_x), timestamp)
        for timestamp in range(210, 2210, 10)
    )
    result = controller.plan(sequence)
    assert not any(trace.containment_override for trace in result.trace)
    assert max(crop.center.x for crop in result[21:]) > target_x
    positions = [crop.center.x / 3840 for crop in result]
    deltas = [right - left for left, right in pairwise(positions)]
    assert max(abs(right - left) for left, right in pairwise(deltas)) <= 0.5 * 0.01**2 + 1e-12
    assert result[-1] == result[-20]
    assert (
        abs(result[-1].center.x - target_x) / result[-1].width <= controller.center_enter_fraction
    )


def test_containment_height_correction_cancels_inward_zoom_momentum() -> None:
    controller = planner()
    sequence = measurements([centered_box(400)] + [centered_box(250)] * 20, 10)
    sequence.append(FrameMeasurement(centered_box(400, width=1600), 210))
    corrected = controller.plan(sequence)
    assert corrected[-2].height < corrected[-3].height
    assert corrected.trace[-1].containment_override
    assert corrected[-1].height > corrected[-2].height
    reference = corrected[-1]
    sequence.append(
        FrameMeasurement(
            centered_box(reference.height * 0.5, reference.center.x, reference.center.y), 220
        )
    )
    result = controller.plan(sequence)
    assert result[-1] == reference
    assert not result.trace[-1].smoothing_applied


@pytest.mark.parametrize("profile", list(FramingProfile))
@pytest.mark.parametrize(
    ("source_width", "source_height", "aspect"),
    [
        (3840, 2160, AspectRatio.LANDSCAPE),
        (3840, 2160, AspectRatio.PORTRAIT),
        (1080, 1920, AspectRatio.LANDSCAPE),
        (1080, 1920, AspectRatio.PORTRAIT),
    ],
)
@pytest.mark.parametrize("far_edge", [False, True])
def test_all_profiles_and_source_aspects_hold_at_edges_and_preserve_target(
    profile: FramingProfile,
    source_width: int,
    source_height: int,
    aspect: AspectRatio,
    far_edge: bool,
) -> None:
    controller = DeterministicCropPlanner(source_width, source_height, aspect, profile)
    boxes = [
        Rect(
            source_width - 100 if far_edge else 0,
            source_height - height if far_edge else 0,
            100,
            height,
        )
        for height in (200, 202, 198)
    ]
    result = controller.plan(measurements(boxes))
    assert boxes[0].height / result[0].height == pytest.approx(
        PROFILE_TARGET_HEIGHT_FRACTIONS[profile]
    )
    assert all(crop == result[0] for crop in result)
    for crop, box in zip(result, boxes, strict=True):
        assert 0 <= crop.x < crop.right <= source_width
        assert 0 <= crop.y < crop.bottom <= source_height
        assert crop.width / crop.height == pytest.approx(aspect.value_float)
        assert crop.contains(box)


@pytest.mark.parametrize("profile", list(FramingProfile))
@pytest.mark.parametrize(
    ("source_width", "source_height", "aspect", "width", "height", "limited"),
    [
        (3840, 2160, AspectRatio.LANDSCAPE, 3840, 2160, False),
        (3840, 2160, AspectRatio.PORTRAIT, 1215, 2160, True),
        (1080, 1920, AspectRatio.LANDSCAPE, 1080, 607.5, True),
        (1080, 1920, AspectRatio.PORTRAIT, 1080, 1920, False),
    ],
)
def test_source_limits_override_profile_scale_for_every_source_aspect(
    profile: FramingProfile,
    source_width: int,
    source_height: int,
    aspect: AspectRatio,
    width: float,
    height: float,
    limited: bool,
) -> None:
    controller = DeterministicCropPlanner(source_width, source_height, aspect, profile)
    box = Rect(0, 0, source_width, source_height)
    result = controller.plan(measurements([box, box]))
    assert result[0] == result[1]
    for crop, trace in zip(result, result.trace, strict=True):
        assert crop.width == width
        assert crop.height == height
        assert 0 <= crop.x < crop.right <= source_width
        assert 0 <= crop.y < crop.bottom <= source_height
        assert crop.contains(box) is not limited
        assert trace.source_aspect_limited is limited
        assert not trace.containment_override


def lookahead() -> LookaheadCropPlanner:
    return LookaheadCropPlanner(3840, 2160, AspectRatio.LANDSCAPE, FramingProfile.BALANCED)


def lookahead_reacquisition(timestamps: list[int]) -> list[FrameMeasurement]:
    first = centered_box(400, 1200, 700)
    last = centered_box(400, 2800, 1500)
    return [
        FrameMeasurement(
            last if index == len(timestamps) - 1 else first,
            timestamp,
            detection_sampled=index in (0, len(timestamps) - 1),
        )
        for index, timestamp in enumerate(timestamps)
    ]


def axis_motion(
    result: CropPlan, sequence: list[FrameMeasurement], *, horizontal: bool
) -> tuple[list[float], list[float]]:
    centers = [crop.center.x / 3840 if horizontal else crop.center.y / 2160 for crop in result]
    intervals = [
        (right.timestamp_ms - left.timestamp_ms) / 1000 for left, right in pairwise(sequence)
    ]
    velocities = [
        (right - left) / dt for (left, right), dt in zip(pairwise(centers), intervals, strict=True)
    ]
    accelerations = [2 * velocities[0] / intervals[0], -2 * velocities[-1] / intervals[-1]]
    accelerations.extend(
        2 * (velocities[index] - velocities[index - 1]) / (intervals[index] + intervals[index - 1])
        for index in range(1, len(intervals))
    )
    return velocities, accelerations


def test_lookahead_moves_before_reacquisition_and_can_leave_stale_held_box() -> None:
    sequence = lookahead_reacquisition(list(range(0, 4001, 100)))
    result = lookahead().plan(sequence)
    seed = planner().plan(sequence)
    assert any(
        crop.center.x > causal.center.x + 1
        for crop, causal in zip(result.crops[1:-1], seed.crops[1:-1], strict=True)
    )
    assert result[0].contains(sequence[0].detector_bounds)
    assert result[-1].contains(sequence[-1].detector_bounds)
    assert any(not crop.contains(sequence[0].detector_bounds) for crop in result[1:-1])
    for index, (crop, trace) in enumerate(zip(result, result.trace, strict=True)):
        assert isinstance(trace, LookaheadPlannerFrameTrace)
        assert trace.sampled_detection_constraint is (index in (0, len(result) - 1))
        if trace.sampled_detection_constraint:
            assert trace.sampled_detection_contained is True
            assert trace.held_target_contained is None
        else:
            assert trace.sampled_detection_contained is None
            assert trace.held_target_contained is crop.contains(sequence[index].detector_bounds)
        assert not trace.containment_override
        assert not trace.pan_speed_limit_exceeded
        assert not trace.pan_acceleration_limit_exceeded
    assert any(trace.lookahead_center_adjusted for trace in result.trace[:-1])
    assert any(trace.action == "lookahead_pan" for trace in result.trace[1:-1])
    for horizontal in (True, False):
        velocities, accelerations = axis_motion(result, sequence, horizontal=horizontal)
        assert max(abs(value) for value in velocities) <= 0.25 + 1.1e-8
        assert max(abs(value) for value in accelerations) <= 0.5 + 1.1e-8


def test_lookahead_irregular_timestamps_obey_both_axis_limits_and_rest_boundaries() -> None:
    timestamps = [0]
    for interval in [40, 160, 75, 225] * 8:
        timestamps.append(timestamps[-1] + interval)
    sequence = lookahead_reacquisition(timestamps)
    controller = lookahead()
    result = controller.plan(sequence)
    assert result[0].contains(sequence[0].detector_bounds)
    assert result[-1].contains(sequence[-1].detector_bounds)
    for horizontal in (True, False):
        velocities, accelerations = axis_motion(result, sequence, horizontal=horizontal)
        assert max(abs(value) for value in velocities) <= 0.25 + 1.1e-8
        assert max(abs(value) for value in accelerations) <= 0.5 + 1.1e-8
        for index, trace in enumerate(result.trace):
            velocity = (
                trace.pan_velocity_x_source_per_second
                if horizontal
                else trace.pan_velocity_y_source_per_second
            )
            acceleration = (
                trace.pan_acceleration_x_source_per_second2
                if horizontal
                else trace.pan_acceleration_y_source_per_second2
            )
            if index:
                assert velocity == pytest.approx(velocities[index - 1], abs=1e-12)
            else:
                assert velocity is None
            if index >= 2:
                expected = (
                    2
                    * (velocities[index - 1] - velocities[index - 2])
                    / ((timestamps[index] - timestamps[index - 2]) / 1000)
                )
                assert acceleration == pytest.approx(expected, abs=1e-12)
            else:
                assert acceleration is None


def test_lookahead_repeated_solves_and_timestamp_translation_are_deterministic() -> None:
    sequence = lookahead_reacquisition(list(range(0, 4001, 100)))
    controller = lookahead()
    result = controller.plan(sequence)
    assert controller.plan(sequence) == result
    shifted = [
        FrameMeasurement(
            item.detector_bounds,
            item.timestamp_ms + 123456,
            item.confidence,
            item.detection_sampled,
        )
        for item in sequence
    ]
    assert controller.plan(shifted) == result


def test_lookahead_preserves_causal_dimensions_through_zoom_misses_and_reacquisition() -> None:
    sequence = [
        FrameMeasurement(centered_box(400), 0),
        FrameMeasurement(centered_box(400), 100, detection_sampled=False),
        FrameMeasurement(centered_box(650, 2200), 350),
        FrameMeasurement(centered_box(650, 2200), 500, detection_sampled=False),
        FrameMeasurement(None, 700),
        FrameMeasurement(None, 1100, detection_sampled=False),
        FrameMeasurement(centered_box(300, 1700), 1500),
        FrameMeasurement(centered_box(300, 1700), 1700, detection_sampled=False),
    ]
    seed = planner().plan(sequence)
    result = lookahead().plan(sequence)
    assert [(crop.width, crop.height) for crop in result] == [
        (crop.width, crop.height) for crop in seed
    ]
    assert result[5].height > result[3].height
    for index in (4, 5):
        trace = result.trace[index]
        assert trace.detection_missed
        assert not trace.sampled_detection_constraint
        assert trace.sampled_detection_contained is None
        assert trace.held_target_contained is None
        assert trace.action == "widen_on_miss"
    for crop, item in zip(result, sequence, strict=True):
        if item.detection_sampled and item.detector_bounds is not None:
            assert crop.contains(item.detector_bounds)


@pytest.mark.parametrize(
    ("displacement", "speed_excess", "acceleration_excess"),
    [(600, 5.75, 119.5), (20, 0.0, 3.5)],
)
def test_lookahead_infeasible_motion_keeps_containment_with_minimum_excess(
    displacement: int, speed_excess: float, acceleration_excess: float
) -> None:
    # Width equals the seed crop width, fixing the two X centers exactly. These
    # analytic lower bounds distinguish unavoidable speed and rest-acceleration excess.
    boxes = [Rect(0, 400, 400, 100), Rect(displacement, 400, 400, 100)]
    sequence = measurements(boxes, 100)
    controller = LookaheadCropPlanner(1000, 1000, AspectRatio.LANDSCAPE, FramingProfile.BALANCED)
    result = controller.plan(sequence)
    assert all(crop.contains(box) for crop, box in zip(result, boxes, strict=True))
    velocity = (result[1].center.x - result[0].center.x) / 1000 / 0.1
    assert max(0, abs(velocity) - 0.25) == pytest.approx(speed_excess, abs=1e-8)
    assert max(0, 2 * abs(velocity) / 0.1 - 0.5) == pytest.approx(acceleration_excess, abs=1e-8)
    assert result.trace[1].pan_speed_limit_exceeded is (speed_excess > 0)
    assert all(trace.pan_acceleration_limit_exceeded for trace in result.trace)
    assert all(trace.sampled_detection_contained for trace in result.trace)
    assert all(trace.pan_acceleration_x_source_per_second2 is None for trace in result.trace)
    assert all(not trace.containment_override for trace in result.trace)


@pytest.mark.parametrize(
    ("width", "height", "aspect"),
    [(3840, 2160, AspectRatio.PORTRAIT), (1080, 1920, AspectRatio.LANDSCAPE)],
)
def test_lookahead_reports_source_aspect_impossible_sample_without_claiming_containment(
    width: int, height: int, aspect: AspectRatio
) -> None:
    box = Rect(0, 0, width, height)
    controller = LookaheadCropPlanner(width, height, aspect, FramingProfile.BALANCED)
    result = controller.plan(measurements([box, box], 100))
    for crop, trace in zip(result, result.trace, strict=True):
        assert 0 <= crop.x < crop.right <= width
        assert 0 <= crop.y < crop.bottom <= height
        assert crop.width / crop.height == pytest.approx(aspect.value_float)
        assert not crop.contains(box)
        assert trace.source_aspect_limited
        assert trace.sampled_detection_constraint
        assert trace.sampled_detection_contained is False
        assert trace.action == "source_aspect_limited"
        assert not trace.containment_override


def test_lookahead_empty_and_single_frame_do_not_require_optimizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise AssertionError("No optimization is needed without frame intervals")

    monkeypatch.setattr(planner_module, "linprog", unavailable)
    assert lookahead().plan([]) == CropPlan((), ())
    sequence = [FrameMeasurement(centered_box(400, 1900.123456789, 1070.987654321), 50)]
    result = lookahead().plan(sequence)
    assert result.crops == planner().plan(sequence).crops
    assert result[0].contains(sequence[0].detector_bounds)
    assert result.trace[0].action == "initial"
    assert result.trace[0].pan_velocity_x_source_per_second is None
    assert result.trace[0].pan_acceleration_y_source_per_second2 is None


@pytest.mark.parametrize("timestamps", [[-1, 0], [0, 0], [100, 99], [0, 1.5], [0, True]])
def test_lookahead_rejects_invalid_timestamps(timestamps: list[int]) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        lookahead().plan(
            [FrameMeasurement(centered_box(400), timestamp) for timestamp in timestamps]
        )


@pytest.mark.parametrize("failed_pass", range(4))
def test_lookahead_rejects_nonoptimal_solver_pass_without_causal_fallback(
    monkeypatch: pytest.MonkeyPatch, failed_pass: int
) -> None:
    real_linprog = planner_module.linprog
    calls = 0

    def fail_pass(*args: object, **kwargs: object) -> OptimizeResult:
        nonlocal calls
        current = calls
        calls += 1
        if current == failed_pass:
            return OptimizeResult(success=False, status=4, message="numerical failure")
        return real_linprog(*args, **kwargs)

    monkeypatch.setattr(planner_module, "linprog", fail_pass)
    with pytest.raises(PlannerError):
        lookahead().plan(measurements([centered_box(400), centered_box(400)], 100))


@pytest.mark.parametrize("corruption", ["nan_center", "nan_objective", "illegal_center", "motion"])
def test_lookahead_rejects_invalid_successful_solver_output(
    monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    real_linprog = planner_module.linprog

    def corrupt(*args: object, **kwargs: object) -> OptimizeResult:
        result = real_linprog(*args, **kwargs)
        if corruption == "nan_center":
            result.x[0] = np.nan
        elif corruption == "nan_objective":
            result.fun = np.nan
        elif corruption == "illegal_center":
            result.x[0] = 2
        else:
            # Still inside the box/source interval, but no longer motion-feasible
            # under the reported optimized excess.
            result.x[1] = result.x[0] + 0.1
            result.x[2] = 0
            result.x[3] = 0
        return result

    monkeypatch.setattr(planner_module, "linprog", corrupt)
    with pytest.raises(PlannerError):
        lookahead().plan(measurements([centered_box(400), centered_box(400)], 100))


def test_lookahead_canonicalizes_sub_tolerance_bound_error_and_revalidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_linprog = planner_module.linprog

    def rounded_bound(*args: object, **kwargs: object) -> OptimizeResult:
        result = real_linprog(*args, **kwargs)
        # X is fixed by a box exactly as wide as the crop. Identical perturbations
        # introduce no motion and must be canonicalized before returning the crop.
        bounds = kwargs["bounds"]
        if bounds[0][0] == bounds[0][1]:
            result.x[:2] -= 1e-10
        return result

    monkeypatch.setattr(planner_module, "linprog", rounded_bound)
    box = Rect(0, 400, 400, 100)
    controller = LookaheadCropPlanner(1000, 1000, AspectRatio.LANDSCAPE, FramingProfile.BALANCED)
    result = controller.plan(measurements([box, box], 100))
    assert all(crop.x == 0 and crop.contains(box) for crop in result)
    assert all(not trace.pan_speed_limit_exceeded for trace in result.trace)
