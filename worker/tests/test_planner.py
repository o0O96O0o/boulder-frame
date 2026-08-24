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
