from boulder_frame_worker import review
from boulder_frame_worker.review import PHASES


def test_review_uses_detector_only_phase_vocabulary() -> None:
    assert PHASES == ("detection", "framing", "render")


def test_detection_overlay_keeps_selected_and_rejected_candidates() -> None:
    selection = {"candidates": [{"selected": False}, {"selected": True}]}
    assert review._measurement_overlay_candidates(selection) == (
        ({"selected": False}, (128, 128, 128), 1),
        ({"selected": True}, (0, 220, 255), 3),
    )
