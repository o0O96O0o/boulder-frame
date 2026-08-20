import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.measurement import (
    Detection,
    Point,
    PoseEstimate,
    Rect,
    TargetFrameAnalyzer,
    expand_roi,
    roi_to_source,
    select_target,
    source_tap,
)


def test_target_selection_prefers_detection_containing_tap() -> None:
    left = Detection(Rect(0, 0, 100, 100), 0.8)
    right = Detection(Rect(200, 0, 100, 100), 0.9)

    assert select_target([left, right], Point(250, 50)) is right


def test_target_selection_uses_nearest_when_tap_is_outside() -> None:
    left = Detection(Rect(0, 0, 100, 100), 0.8)
    right = Detection(Rect(200, 0, 100, 100), 0.9)

    assert select_target([left, right], Point(160, 50)) is right


def test_no_target_is_terminal() -> None:
    with pytest.raises(WorkerError) as raised:
        select_target([], Point(1, 1))

    assert raised.value.code is ErrorCode.NO_SELECTED_ATHLETE


def test_coordinate_mapping_and_roi_transform() -> None:
    assert source_tap(0.5, 0.25, 3840, 2160) == Point(1920, 540)
    roi = expand_roi(Rect(100, 50, 200, 100), 0.5, 1000, 1000)

    assert roi == Rect(0, 0, 400, 200)
    assert roi_to_source(Point(0.25, 0.5), roi) == Point(100, 100)


def test_analyzer_emits_source_coordinate_pose_observation() -> None:
    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return [Detection(Rect(100, 50, 200, 100), 0.9)]

    class Pose:
        def estimate(self, roi_pixels: object, roi: Rect) -> PoseEstimate:
            assert roi_pixels == "cropped"
            assert roi == Rect(50, 25, 300, 150)
            return PoseEstimate(
                root=Point(0.5, 0.5),
                landmarks=(Point(0.25, 0.5),),
                bounds=Rect(0.25, 0.1, 0.5, 0.8),
                confidence=0.8,
            )

    class Cropper:
        def crop(self, frame: object, roi: Rect) -> object:
            return "cropped"

    observation = TargetFrameAnalyzer(Detector(), Pose(), cropper=Cropper()).observe_selected(
        object(),
        frame_index=4,
        timestamp_ms=100,
        normalized_x=0.15,
        normalized_y=0.1,
        source_width=1000,
        source_height=1000,
    )

    assert observation.root == Point(200, 100)
    assert observation.pose_bounds == Rect(125, 40, 150, 120)
    assert observation.landmarks == (Point(125, 100),)


def test_analyzer_retains_detection_and_emits_no_pose_for_a_pose_miss() -> None:
    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return [Detection(Rect(100, 50, 200, 100), 0.9)]

    class Pose:
        def estimate(self, roi_pixels: object, roi: Rect) -> None:
            return None

    class Cropper:
        def crop(self, frame: object, roi: Rect) -> object:
            return "cropped"

    observation = TargetFrameAnalyzer(Detector(), Pose(), cropper=Cropper()).observe(
        object(),
        frame_index=4,
        timestamp_ms=100,
        normalized_x=0.15,
        normalized_y=0.1,
        source_width=1000,
        source_height=1000,
    )

    assert observation.detection is not None
    assert observation.pose is None
    assert observation.root is None
