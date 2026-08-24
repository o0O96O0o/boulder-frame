import pytest

from boulder_frame_worker.measurement import (
    Detection,
    Point,
    PoseMeasurement,
    RawFrameObservation,
    Rect,
)
from boulder_frame_worker.tracking import (
    SingleTargetTracker,
    TrackerConfig,
    TrackingState,
)


def observation(index: int, root: Point | None, confidence: float = 1) -> RawFrameObservation:
    pose = (
        None
        if root is None
        else PoseMeasurement(root, (), Rect(root.x - 20, root.y - 40, 40, 80), confidence)
    )
    detection = (
        None if root is None else Detection(Rect(root.x - 25, root.y - 45, 50, 90), confidence)
    )
    return RawFrameObservation(index, index * 100, detection, pose)


def test_tracker_tracks_motion_and_rejects_a_single_jump() -> None:
    tracked = SingleTargetTracker().track(
        [
            observation(0, Point(100, 100)),
            observation(1, Point(120, 100)),
            observation(2, Point(900, 900)),
            observation(3, Point(140, 100)),
        ]
    )

    assert [item.state for item in tracked] == [
        TrackingState.TRACKED,
        TrackingState.TRACKED,
        TrackingState.REACQUIRING,
        TrackingState.TRACKED,
    ]
    assert tracked[2].root is not None and tracked[2].root.x < 200


def test_tracker_enters_lost_after_gap_and_reacquires_without_inventing_root() -> None:
    tracker = SingleTargetTracker(TrackerConfig(max_gap_frames=1, reacquire_confirmations=2))
    tracked = tracker.track(
        [
            observation(0, Point(100, 100)),
            observation(1, None),
            observation(2, None),
            observation(3, Point(105, 100)),
            observation(4, Point(110, 100)),
        ]
    )

    assert tracked[1].state is TrackingState.REACQUIRING
    assert tracked[2].state is TrackingState.LOST
    assert tracked[2].root is None
    assert tracked[3].state is TrackingState.REACQUIRING
    assert tracked[3].root is None
    assert tracked[4].state is TrackingState.TRACKED
    assert tracked[4].reacquired


def test_tracker_requires_monotonic_timestamps() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        SingleTargetTracker().track(
            [observation(1, Point(1, 1)), RawFrameObservation(2, 50, None, None)]
        )
