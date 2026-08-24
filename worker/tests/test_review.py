from boulder_frame_worker import review
from boulder_frame_worker.review import PHASES, phase_annotations


def test_review_uses_detector_only_phase_vocabulary() -> None:
    assert PHASES == ("detection", "framing", "render")


def test_phase_annotations_use_detector_and_framing_trace_values() -> None:
    record = {
        "timestamp_ms": 250,
        "detection": {"detection": {"confidence": 0.9}, "selection": {"candidate_count": 0}},
        "framing": {
            "decision": {
                "target_height_fraction": 0.5,
                "action": "widen_on_miss",
                "detection_missed": True,
                "containment_override": False,
            }
        },
        "render": {"mapping_independently_verified": False},
    }

    assert "candidate=none/0" in phase_annotations(record, "detection", 3)[1]
    assert (
        phase_annotations(record, "framing", 3)[1]
        == "target_height_fraction=0.5 action=widen_on_miss"
    )
    assert "detection_missed=True" in phase_annotations(record, "framing", 3)[2]


def test_detection_overlay_keeps_selected_and_rejected_candidates() -> None:
    selection = {"candidates": [{"selected": False}, {"selected": True}]}
    assert review._measurement_overlay_candidates(selection) == (
        ({"selected": False}, (128, 128, 128), 1),
        ({"selected": True}, (0, 220, 255), 3),
    )
