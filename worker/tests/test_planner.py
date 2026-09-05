from itertools import pairwise
from math import log
from struct import pack

import pytest

from boulder_frame_worker.measurement import Rect
from boulder_frame_worker.planner import (
    PROFILE_TARGET_HEIGHT_FRACTIONS,
    DeterministicCropPlanner,
    FrameMeasurement,
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
