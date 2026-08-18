import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.measurement import (
    Detection,
    Point,
    Rect,
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
