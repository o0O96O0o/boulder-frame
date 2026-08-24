import json

from boulder_frame_worker.debug import (
    canonical_json_bytes,
    serialize_frame_measurement,
    serialize_planner_trace,
    serialize_raw_frame_observation,
)
from boulder_frame_worker.measurement import (
    AssociationEvidence,
    Detection,
    DetectionCandidate,
    Point,
    RawFrameObservation,
    Rect,
    SelectionOutcome,
    SelectionReferenceKind,
    SelectionStrategy,
)
from boulder_frame_worker.planner import CropRect, FrameMeasurement, PlannerFrameTrace


def test_detector_and_framing_serializers_contain_no_pose_or_tracking_data() -> None:
    bounds = Rect(10, 20, 30, 40)
    observation = RawFrameObservation(
        7,
        233,
        Detection(bounds, 0.9),
        SelectionOutcome.SELECTED_CONTAINING_TAP,
        AssociationEvidence(
            Point(20, 30),
            SelectionReferenceKind.TAP,
            SelectionStrategy.CONTAINING_REFERENCE_THEN_NEAREST_CENTER,
            SelectionOutcome.SELECTED_CONTAINING_TAP,
            1,
            (DetectionCandidate(0, Detection(bounds, 0.9), True, 0, True),),
            False,
        ),
    )
    trace = PlannerFrameTrace(0.5, CropRect(0, 0, 100, 100), False, True, False, False, "smoothed")

    serialized = serialize_raw_frame_observation(observation)
    assert serialized["detection"] == {
        "bounds": {"x": 10, "y": 20, "width": 30, "height": 40},
        "confidence": 0.9,
    }
    assert "pose" not in serialized
    assert "tracking" not in json.dumps(serialized)
    assert serialize_frame_measurement(FrameMeasurement(bounds, 0.9)) == {
        "detector_bounds": {"x": 10, "y": 20, "width": 30, "height": 40},
        "confidence": 0.9,
        "detection_missed": False,
    }
    assert serialize_planner_trace(trace)["target_height_fraction"] == 0.5


def test_canonical_json_remains_safe_and_deterministic() -> None:
    assert json.loads(canonical_json_bytes({"b": 2, "a": 1})) == {"a": 1, "b": 2}
    assert json.loads(canonical_json_bytes({"token": "secret", "pixels": "raw"})) == {}
