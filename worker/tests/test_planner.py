from boulder_frame_worker.measurement import Point, Rect
from boulder_frame_worker.planner import DeterministicCropPlanner, FrameMeasurement
from boulder_frame_worker.protocol import AspectRatio, FramingProfile


def measurement(profile_confidence: float = 1.0, velocity: Point | None = None) -> FrameMeasurement:
    return FrameMeasurement(
        Point(1000, 800),
        Rect(800, 400, 400, 700),
        profile_confidence,
        velocity or Point(0, 0),
    )


def test_crop_is_aspect_correct_source_bounded_and_contains_subject() -> None:
    planner = DeterministicCropPlanner(3840, 2160, AspectRatio.LANDSCAPE, FramingProfile.BALANCED)
    crop = planner.plan([measurement()])[0]

    assert crop.width / crop.height == 16 / 9
    assert 0 <= crop.x <= crop.right <= 3840
    assert 0 <= crop.y <= crop.bottom <= 2160
    assert crop.contains(Rect(800, 400, 400, 700))


def test_profile_ordering_increases_crop_size() -> None:
    sizes = [
        DeterministicCropPlanner(3840, 2160, AspectRatio.LANDSCAPE, profile)
        .plan([measurement()])[0]
        .height
        for profile in FramingProfile
    ]

    assert sizes == sorted(sizes)


def test_low_confidence_and_lost_track_widen_framing() -> None:
    planner = DeterministicCropPlanner(3840, 2160, AspectRatio.LANDSCAPE, FramingProfile.BALANCED)
    high = planner.plan([measurement(1.0)])[0]
    low = planner.plan([measurement(0.1)])[0]
    lost = planner.plan([FrameMeasurement(None, None, 0, lost=True)])[0]

    assert low.height > high.height
    assert lost.width == 3840
    assert lost.height == 2160


def test_directional_lead_moves_crop_in_velocity_direction() -> None:
    planner = DeterministicCropPlanner(3840, 2160, AspectRatio.LANDSCAPE, FramingProfile.BALANCED)
    still, moving = planner.plan([measurement(), measurement(velocity=Point(200, 0))])

    assert moving.center.x > still.center.x
