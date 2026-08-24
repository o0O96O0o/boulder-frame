import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.measurement import (
    MAX_ASSOCIATION_CANDIDATES,
    MAX_ASSOCIATION_CENTER_DISTANCE_DIAGONALS,
    AssociationEvidence,
    Detection,
    DetectionCandidate,
    Point,
    Rect,
    SelectionOutcome,
    SelectionReferenceKind,
    SelectionStrategy,
    TargetFrameAnalyzer,
    select_target,
    source_tap,
)


def test_selected_frame_prefers_detection_containing_tap() -> None:
    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return [Detection(Rect(0, 0, 20, 20), 0.5), Detection(Rect(100, 100, 20, 20), 0.9)]

    observation = TargetFrameAnalyzer(Detector()).observe_selected(
        object(),
        frame_index=0,
        timestamp_ms=0,
        normalized_x=0.11,
        normalized_y=0.11,
        source_width=1000,
        source_height=1000,
    )

    assert observation.selection_outcome is SelectionOutcome.SELECTED_CONTAINING_TAP
    assert observation.detector_bounds == Rect(100, 100, 20, 20)
    assert observation.association is not None
    assert observation.association.reference_kind is SelectionReferenceKind.TAP
    assert [candidate.selected for candidate in observation.association.candidates] == [False, True]


def test_later_frame_associates_against_prior_detector_box_center() -> None:
    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return [Detection(Rect(0, 0, 20, 20), 0.4), Detection(Rect(90, 90, 20, 20), 0.9)]

    observation = TargetFrameAnalyzer(Detector()).observe(
        object(),
        frame_index=1,
        timestamp_ms=33,
        reference=Point(99, 99),
        reference_kind=SelectionReferenceKind.PRIOR_DETECTOR_BOX_CENTER,
    )

    assert observation.selection_outcome is SelectionOutcome.ASSOCIATED_CONTAINING_REFERENCE
    assert observation.association is not None
    assert (
        observation.association.reference_kind is SelectionReferenceKind.PRIOR_DETECTOR_BOX_CENTER
    )
    assert observation.association.reference == Point(99, 99)
    assert observation.association.candidates[1].selected


def test_later_detector_gap_is_an_explicit_non_terminal_observation() -> None:
    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return []

    observation = TargetFrameAnalyzer(Detector()).observe(
        object(),
        frame_index=1,
        timestamp_ms=33,
        reference=Point(50, 25),
        reference_kind=SelectionReferenceKind.PRIOR_DETECTOR_BOX_CENTER,
    )

    assert observation.detection is None
    assert observation.selection_outcome is SelectionOutcome.NO_DETECTIONS
    assert observation.association is not None
    assert observation.association.candidate_count == 0


def test_association_rejects_distant_competing_person_without_updating_reference() -> None:
    target = Rect(100, 100, 20, 40)
    competing = Detection(Rect(500, 500, 20, 40), 0.9)

    observation = TargetFrameAnalyzer(type("Detector", (), {"detect": lambda *_: []})()).associate(
        [competing],
        frame_index=1,
        timestamp_ms=33,
        reference=target.center,
        reference_kind=SelectionReferenceKind.PRIOR_DETECTOR_BOX_CENTER,
        reference_bounds=target,
    )

    assert MAX_ASSOCIATION_CENTER_DISTANCE_DIAGONALS == 1.5
    assert observation.detection is None
    assert observation.selection_outcome is SelectionOutcome.NO_ACCEPTED_CANDIDATE
    assert observation.association is not None
    assert not any(candidate.selected for candidate in observation.association.candidates)


def test_association_selects_an_accepted_candidate_over_a_distant_containing_candidate() -> None:
    target = Rect(100, 100, 20, 40)
    accepted = Detection(Rect(125, 100, 20, 40), 0.9)
    distant_containing = Detection(Rect(0, 0, 1000, 1000), 0.9)

    observation = TargetFrameAnalyzer(type("Detector", (), {"detect": lambda *_: []})()).associate(
        [distant_containing, accepted],
        frame_index=1,
        timestamp_ms=33,
        reference=target.center,
        reference_kind=SelectionReferenceKind.PRIOR_DETECTOR_BOX_CENTER,
        reference_bounds=target,
    )

    assert observation.detector_bounds == accepted.bounds


def test_selected_frame_detector_gap_is_terminal() -> None:
    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return []

    with pytest.raises(WorkerError) as raised:
        TargetFrameAnalyzer(Detector()).observe_selected(
            object(),
            frame_index=0,
            timestamp_ms=0,
            normalized_x=0.5,
            normalized_y=0.5,
            source_width=100,
            source_height=100,
        )

    assert raised.value.code is ErrorCode.NO_SELECTED_ATHLETE


def test_association_evidence_is_optional_and_bounded() -> None:
    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return [Detection(Rect(index * 10, 0, 5, 5), 0.5) for index in range(40)]

    analyzer = TargetFrameAnalyzer(Detector())
    without_evidence = analyzer.observe_selected(
        object(),
        frame_index=0,
        timestamp_ms=0,
        normalized_x=0.395,
        normalized_y=0.02,
        source_width=1000,
        source_height=100,
        capture_association_evidence=False,
    )
    with_evidence = analyzer.observe_selected(
        object(),
        frame_index=0,
        timestamp_ms=0,
        normalized_x=0.395,
        normalized_y=0.02,
        source_width=1000,
        source_height=100,
    )

    assert without_evidence.association is None
    assert with_evidence.association is not None
    assert len(with_evidence.association.candidates) == MAX_ASSOCIATION_CANDIDATES
    assert [candidate.original_index for candidate in with_evidence.association.candidates][
        -1
    ] == 39


def test_association_evidence_rejects_unselected_detected_frame() -> None:
    with pytest.raises(ValueError, match="exactly one selected"):
        AssociationEvidence(
            Point(1, 1),
            SelectionReferenceKind.TAP,
            SelectionStrategy.CONTAINING_REFERENCE_THEN_NEAREST_CENTER,
            SelectionOutcome.SELECTED_NEAREST_TAP,
            1,
            (DetectionCandidate(0, Detection(Rect(0, 0, 2, 2), 0.9), True, 0, False),),
            False,
        )


def test_selection_geometry_and_empty_selection_contract() -> None:
    right = Detection(Rect(200, 0, 100, 100), 0.9)
    assert select_target([Detection(Rect(0, 0, 100, 100), 0.8), right], Point(250, 50)) is right
    assert source_tap(0.5, 0.25, 3840, 2160) == Point(1920, 540)
    with pytest.raises(WorkerError, match="No athlete"):
        select_target([], Point(1, 1))
