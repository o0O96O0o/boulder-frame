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


def test_balanced_targets_detector_box_at_half_crop_height() -> None:
    box = Rect(1600, 600, 200, 400)
    crop = planner().plan([FrameMeasurement(box)])[0]

    assert crop.height == pytest.approx(800)
    assert box.height / crop.height == pytest.approx(0.5)
    assert crop.width / crop.height == pytest.approx(16 / 9)
    assert crop.contains(box)


def test_profiles_order_from_tightest_to_widest_fixed_target_size() -> None:
    box = Rect(1600, 600, 200, 400)
    sizes = [planner(profile).plan([FrameMeasurement(box)])[0].height for profile in FramingProfile]

    assert PROFILE_TARGET_HEIGHT_FRACTIONS[FramingProfile.BALANCED] == 0.50
    assert sizes == sorted(sizes)


def test_source_edge_and_largest_valid_crop_are_bounded() -> None:
    box = Rect(0, 300, 300, 1600)
    crop = planner().plan([FrameMeasurement(box)])[0]

    assert crop.x == 0
    assert 0 <= crop.y <= crop.bottom <= 2160
    assert crop.contains(box)


def test_smoothing_temporally_filters_center_and_scale() -> None:
    first = Rect(1000, 500, 200, 400)
    second = Rect(2000, 500, 300, 600)
    crops = planner().plan([FrameMeasurement(first), FrameMeasurement(second)])
    desired = DeterministicCropPlanner(3840, 2160, AspectRatio.LANDSCAPE, FramingProfile.BALANCED)
    second_desired = desired.plan([FrameMeasurement(second)])[0]

    assert crops[1].center.x > crops[0].center.x
    assert crops[1].center.x < second_desired.center.x
    assert crops[1].height > crops[0].height
    assert crops[1].height < second_desired.height
    assert crops.trace[1].smoothing_applied


def test_abrupt_motion_overrides_smoothing_to_contain_current_box() -> None:
    crops = planner().plan(
        [FrameMeasurement(Rect(1000, 500, 200, 400)), FrameMeasurement(Rect(3100, 500, 300, 600))]
    )

    assert crops[1].contains(Rect(3100, 500, 300, 600))
    assert crops.trace[1].containment_override


def test_detector_miss_widens_prior_crop_without_extrapolating_center() -> None:
    plan = planner().plan([FrameMeasurement(Rect(1800, 500, 200, 400)), FrameMeasurement(None)])

    assert plan[1].height > plan[0].height
    assert plan[1].center == plan[0].center
    assert plan.trace[1].detection_missed
    assert plan.trace[1].action == "widen_on_miss"


@pytest.mark.parametrize(
    ("aspect_ratio", "box"),
    [
        (AspectRatio.PORTRAIT, Rect(400, 200, 3200, 500)),
        (AspectRatio.PORTRAIT, Rect(1200, 100, 1400, 1800)),
    ],
)
def test_impossible_detection_containment_uses_largest_valid_crop_with_diagnostic(
    aspect_ratio: AspectRatio, box: Rect
) -> None:
    result = DeterministicCropPlanner(3840, 2160, aspect_ratio, FramingProfile.BALANCED).plan(
        [FrameMeasurement(box)]
    )

    assert not result[0].contains(box)
    expected = DeterministicCropPlanner(
        3840, 2160, aspect_ratio, FramingProfile.BALANCED
    ).full_frame
    assert result[0].width == pytest.approx(expected.width)
    assert result.trace[0].source_aspect_limited
    assert not result.trace[0].containment_override
    assert result.trace[0].action == "source_aspect_limited"


def centered_box(
    height: float, center_x: float = 1920, center_y: float = 1080, width: float = 200
) -> Rect:
    return Rect(center_x - width / 2, center_y - height / 2, width, height)


@pytest.mark.parametrize("profile", list(FramingProfile))
def test_scale_jitter_holds_byte_identical_dimensions(profile: FramingProfile) -> None:
    heights = [401.23456789, 408, 392, 415, 401, 389]
    result = planner(profile).plan([FrameMeasurement(centered_box(height)) for height in heights])
    original_size = pack("!dd", result[0].width, result[0].height)

    for crop, trace in zip(result[1:], result.trace[1:], strict=True):
        assert pack("!dd", crop.width, crop.height) == original_size
        assert trace.scale_deadband_applied
        assert not trace.scale_adjusting
        assert not trace.containment_override


def test_center_and_scale_jitter_hold_exact_rectangle_without_round_trip_drift() -> None:
    center_x, center_y = 1900.123456789, 1070.987654321
    result = planner().plan(
        [
            FrameMeasurement(centered_box(401.23456789, center_x, center_y)),
            FrameMeasurement(centered_box(410, center_x + 8, center_y - 3)),
            FrameMeasurement(centered_box(398, center_x - 7, center_y + 2)),
            FrameMeasurement(centered_box(404, center_x + 4, center_y - 1)),
        ]
    )

    assert all(crop == result[0] for crop in result)
    for trace in result.trace[1:]:
        assert trace.scale_deadband_applied and trace.center_deadband_applied
        assert not trace.scale_adjusting and not trace.center_adjusting
        assert not trace.smoothing_applied
        assert trace.action == "deadband_hold"


@pytest.mark.parametrize("direction", [-1, 1])
def test_scale_crosses_outer_band_and_exits_only_at_inclusive_inner_band(direction: int) -> None:
    measurements = [FrameMeasurement(centered_box(400))]
    expected_heights = [800.0]
    # Equality holds at entry and exits while adjusting; an actually larger error moves.
    errors = [0.05, 0.050001, 0.035, 0.020001, 0.02, 0.035]
    adjusting = [False, True, True, True, False, False]
    for error, active in zip(errors, adjusting, strict=True):
        previous_height = expected_heights[-1]
        desired_height = previous_height * (1 + direction * error)
        measurements.append(FrameMeasurement(centered_box(desired_height * 0.5)))
        expected_heights.append(
            previous_height + (desired_height - previous_height) * 0.25
            if active
            else previous_height
        )
    result = planner().plan(measurements)

    assert [crop.height for crop in result] == pytest.approx(expected_heights)
    assert [trace.scale_adjusting for trace in result.trace[1:]] == adjusting
    assert [trace.scale_relative_error for trace in result.trace[1:]] == pytest.approx(
        [direction * error for error in errors]
    )
    assert all(not trace.center_adjusting for trace in result.trace)
    assert all(crop.center == result[0].center for crop in result)
    assert result[1] == result[0]
    assert result[-1] == result[-2] == result[-3]


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("direction", [-1, 1])
def test_center_crosses_outer_band_and_exits_only_at_inclusive_inner_band(
    axis: str, direction: int
) -> None:
    measurements = [FrameMeasurement(centered_box(400))]
    dimension = 800 * 16 / 9 if axis == "x" else 800
    original_center = 1920.0 if axis == "x" else 1080.0
    expected_centers = [original_center]
    errors = [0.01, 0.010001, 0.006, 0.004001, 0.004, 0.006]
    adjusting = [False, True, True, True, False, False]
    for error, active in zip(errors, adjusting, strict=True):
        previous_center = expected_centers[-1]
        desired_center = previous_center + direction * error * dimension
        measurements.append(
            FrameMeasurement(
                centered_box(
                    400,
                    desired_center if axis == "x" else 1920,
                    desired_center if axis == "y" else 1080,
                )
            )
        )
        expected_centers.append(
            previous_center + (desired_center - previous_center) * 0.35
            if active
            else previous_center
        )
    result = planner().plan(measurements)

    actual_centers = [crop.center.x if axis == "x" else crop.center.y for crop in result]
    assert actual_centers == pytest.approx(expected_centers)
    assert [trace.center_adjusting for trace in result.trace[1:]] == adjusting
    assert all(not trace.scale_adjusting for trace in result.trace)
    assert all((crop.width, crop.height) == (result[0].width, result[0].height) for crop in result)
    assert result[1] == result[0]
    assert result[-1] == result[-2] == result[-3]


@pytest.mark.parametrize("gate", ["scale", "center"])
def test_outer_boundary_jitter_does_not_chatter_after_adjustment_latches(gate: str) -> None:
    measurements = [FrameMeasurement(centered_box(400))]
    for offset in [1, -1] * 12:
        box = (
            centered_box(420 + offset * 0.4)
            if gate == "scale"
            else centered_box(400, 1920 + (0.01 + offset * 0.00001) * (800 * 16 / 9))
        )
        measurements.append(FrameMeasurement(box))
    result = planner().plan(measurements)
    active = [
        trace.scale_adjusting if gate == "scale" else trace.center_adjusting
        for trace in result.trace[1:]
    ]

    assert active[0]
    first_hold = active.index(False)
    assert first_hold > 1
    assert all(active[:first_hold])
    assert not any(active[first_hold:])
    assert all(crop == result[first_hold] for crop in result[first_hold + 1 :])


def test_gradual_scale_change_accumulates_against_held_crop_not_previous_detection() -> None:
    result = planner().plan(
        [FrameMeasurement(centered_box(height)) for height in [400, 404, 408, 412, 416, 420, 424]]
    )

    assert all(crop == result[0] for crop in result[:6])
    assert result[6].height > result[5].height
    assert result[6].height < 848
    assert result.trace[6].scale_relative_error == pytest.approx(0.06)
    assert result.trace[6].scale_adjusting
    assert not result.trace[6].center_adjusting


def test_containment_overrides_held_gates_only_when_detection_would_be_clipped() -> None:
    boxes = [
        centered_box(400),
        centered_box(400, 1930, width=1300),
        centered_box(400, 1930, width=1420),
        centered_box(400, 1930, width=1450),
    ]
    result = planner().plan([FrameMeasurement(box) for box in boxes])

    assert result[1] == result[0]
    assert not result.trace[1].containment_override
    for index in (2, 3):
        assert not result[index - 1].contains(boxes[index])
        assert result[index].contains(boxes[index])
        assert result.trace[index].scale_deadband_applied
        assert result.trace[index].center_deadband_applied
        assert result.trace[index].containment_override
        assert result.trace[index].action == "containment_override"
    assert result[2].height == result[1].height
    assert result[2].width == result[1].width
    assert result[3].height > result[2].height


def test_miss_resets_both_gates_and_reacquisition_uses_widened_crop_without_extrapolation() -> None:
    controller = planner()
    measurements = [
        FrameMeasurement(centered_box(400)),
        FrameMeasurement(centered_box(480, 2020)),
        FrameMeasurement(None),
    ]
    missed = controller.plan(measurements)
    reference = missed[-1]
    # Between the two bands: reacquisition must hold, proving both active states reset.
    measurements.append(
        FrameMeasurement(
            centered_box(
                reference.height * 0.5 * 1.03,
                reference.center.x + reference.width * 0.006,
                reference.center.y,
            )
        )
    )
    measurements.append(FrameMeasurement(centered_box(400, reference.center.x, reference.center.y)))
    result = controller.plan(measurements)

    assert result.trace[1].scale_adjusting and result.trace[1].center_adjusting
    assert result[2].height > result[1].height
    assert result[2].center == result[1].center
    assert result.trace[2].action == "widen_on_miss"
    assert not result.trace[2].scale_adjusting and not result.trace[2].center_adjusting
    assert not result.trace[2].scale_deadband_applied
    assert not result.trace[2].center_deadband_applied
    assert result[3] == result[2]
    assert result.trace[3].observed_height_fraction == pytest.approx(0.515)
    assert result.trace[3].scale_relative_error == pytest.approx(0.03)
    assert result.trace[3].center_error_x_fraction == pytest.approx(0.006)
    assert result.trace[3].center_error_y_fraction == pytest.approx(0)
    assert 800 < result[4].height < result[3].height
    assert result[4].center == result[3].center
    assert result.trace[4].scale_adjusting
    assert not result.trace[4].center_adjusting
    for index in (0, 2):
        trace = result.trace[index]
        assert trace.observed_height_fraction is None
        assert trace.scale_relative_error is None
        assert trace.center_error_x_fraction is None
        assert trace.center_error_y_fraction is None


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
    result = controller.plan([FrameMeasurement(box) for box in boxes])

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
    ("source_width", "source_height", "aspect", "expected_width", "expected_height", "limited"),
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
    expected_width: float,
    expected_height: float,
    limited: bool,
) -> None:
    controller = DeterministicCropPlanner(source_width, source_height, aspect, profile)
    box = Rect(0, 0, source_width, source_height)
    result = controller.plan([FrameMeasurement(box), FrameMeasurement(box)])

    assert result[0] == result[1]
    for crop, trace in zip(result, result.trace, strict=True):
        assert crop.width == expected_width
        assert crop.height == expected_height
        assert 0 <= crop.x < crop.right <= source_width
        assert 0 <= crop.y < crop.bottom <= source_height
        assert crop.contains(box) is not limited
        assert trace.source_aspect_limited is limited
        assert not trace.containment_override
        if limited:
            assert trace.action == "source_aspect_limited"
