import json
from dataclasses import replace

import pytest

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
    trace = PlannerFrameTrace(
        target_height_fraction=0.5,
        desired_crop=CropRect(0, 0, 100, 100),
        detection_missed=False,
        smoothing_applied=True,
        containment_override=False,
        source_aspect_limited=False,
        action="smoothed",
        observed_height_fraction=0.6,
        scale_relative_error=0.2,
        scale_deadband_applied=False,
        scale_adjusting=True,
        center_error_x_fraction=0.03,
        center_error_y_fraction=0.0,
        center_deadband_applied=False,
        center_adjusting=True,
    )

    serialized = serialize_raw_frame_observation(observation)
    assert serialized["detection"] == {
        "bounds": {"x": 10, "y": 20, "width": 30, "height": 40},
        "confidence": 0.9,
    }
    assert "pose" not in serialized
    assert "tracking" not in json.dumps(serialized)
    assert serialize_frame_measurement(FrameMeasurement(bounds, 0, 0.9)) == {
        "detector_bounds": {"x": 10, "y": 20, "width": 30, "height": 40},
        "confidence": 0.9,
        "detection_missed": False,
    }
    assert serialize_planner_trace(trace)["target_height_fraction"] == 0.5


def test_canonical_json_remains_safe_and_deterministic() -> None:
    assert json.loads(canonical_json_bytes({"b": 2, "a": 1})) == {"a": 1, "b": 2}
    assert json.loads(canonical_json_bytes({"token": "secret", "pixels": "raw"})) == {}


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -float("inf")])
def test_planner_diagnostics_serialize_missing_and_nonfinite_values_as_null(value) -> None:
    from boulder_frame_worker.planner import DeterministicCropPlanner
    from boulder_frame_worker.protocol import AspectRatio, FramingProfile

    plan = DeterministicCropPlanner(
        1920, 1080, AspectRatio.LANDSCAPE, FramingProfile.BALANCED
    ).plan([FrameMeasurement(Rect(700, 200, 200, 400), 0)])
    trace = replace(
        plan.trace[0],
        observed_height_fraction=value,
        scale_relative_error=value,
        center_error_x_fraction=value,
        center_error_y_fraction=value,
    )
    serialized = serialize_planner_trace(trace)
    # The direct serializer must be safe even before bundle-level sanitization.
    decoded = json.loads(json.dumps(serialized, allow_nan=False))
    for field in (
        "observed_height_fraction",
        "scale_relative_error",
        "center_error_x_fraction",
        "center_error_y_fraction",
    ):
        assert decoded[field] is None
