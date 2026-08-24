"""Detector-only target association in decoded source-pixel coordinates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import hypot
from typing import Protocol

from .errors import ErrorCode, terminal


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    def contains(self, point: Point) -> bool:
        return self.x <= point.x <= self.right and self.y <= point.y <= self.bottom


@dataclass(frozen=True, slots=True)
class Detection:
    bounds: Rect
    confidence: float


class SelectionOutcome(StrEnum):
    SELECTED_CONTAINING_TAP = "selected_containing_tap"
    SELECTED_NEAREST_TAP = "selected_nearest_tap"
    ASSOCIATED_CONTAINING_REFERENCE = "associated_containing_reference"
    ASSOCIATED_NEAREST_REFERENCE = "associated_nearest_reference"
    NO_DETECTIONS = "no_detections"
    NO_ACCEPTED_CANDIDATE = "no_accepted_candidate"


class SelectionReferenceKind(StrEnum):
    TAP = "tap"
    PRIOR_DETECTOR_BOX_CENTER = "prior_detector_box_center"


class SelectionStrategy(StrEnum):
    CONTAINING_REFERENCE_THEN_NEAREST_CENTER = "containing_reference_then_nearest_center"


MAX_ASSOCIATION_CANDIDATES = 32
# A candidate center may move by at most 1.5 times the last accepted detector-box diagonal.
# This makes the gate independent of source resolution without allowing a large, distant
# candidate to loosen the gate or extrapolating a target position.
MAX_ASSOCIATION_CENTER_DISTANCE_DIAGONALS = 1.5


@dataclass(frozen=True, slots=True)
class DetectionCandidate:
    original_index: int
    detection: Detection
    contains_reference: bool
    center_distance: float
    selected: bool

    def __post_init__(self) -> None:
        if self.original_index < 0 or self.center_distance < 0:
            raise ValueError("candidate index and center distance must not be negative")


@dataclass(frozen=True, slots=True)
class AssociationEvidence:
    """Bounded evidence for deterministic detector-box association."""

    reference: Point
    reference_kind: SelectionReferenceKind
    strategy: SelectionStrategy
    outcome: SelectionOutcome
    candidate_count: int
    candidates: tuple[DetectionCandidate, ...]
    candidates_truncated: bool

    def __post_init__(self) -> None:
        if self.candidate_count < 0 or len(self.candidates) > MAX_ASSOCIATION_CANDIDATES:
            raise ValueError("association candidate count is invalid")
        if self.candidate_count < len(self.candidates):
            raise ValueError("association candidate count is smaller than retained candidates")
        if self.candidates_truncated != (self.candidate_count > len(self.candidates)):
            raise ValueError("association candidate truncation state is invalid")
        indexes = [candidate.original_index for candidate in self.candidates]
        if indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
            raise ValueError("retained association candidates must have unique sorted indexes")
        selected = [candidate for candidate in self.candidates if candidate.selected]
        if self.outcome is SelectionOutcome.NO_DETECTIONS:
            if self.candidate_count or selected:
                raise ValueError("no-detection association cannot select a candidate")
        elif self.outcome is SelectionOutcome.NO_ACCEPTED_CANDIDATE:
            if selected:
                raise ValueError("rejected association cannot select a candidate")
        elif len(selected) != 1:
            raise ValueError("detected association must retain exactly one selected candidate")


@dataclass(frozen=True, slots=True)
class RawFrameObservation:
    """The selected detector box, or an explicit later-frame detector miss."""

    frame_index: int
    timestamp_ms: int
    detection: Detection | None
    selection_outcome: SelectionOutcome
    association: AssociationEvidence | None = None

    def __post_init__(self) -> None:
        if self.frame_index < 0 or self.timestamp_ms < 0:
            raise ValueError("frame index and timestamp must not be negative")
        if self.association is not None:
            if self.selection_outcome is not self.association.outcome:
                raise ValueError("observation selection outcome must match association evidence")
            selected = next(
                (
                    candidate.detection
                    for candidate in self.association.candidates
                    if candidate.selected
                ),
                None,
            )
            if self.detection != selected:
                raise ValueError("observation detection must match selected association candidate")

    @property
    def detector_bounds(self) -> Rect | None:
        return None if self.detection is None else self.detection.bounds

    @property
    def confidence(self) -> float:
        return 0 if self.detection is None else self.detection.confidence


class PersonDetector(Protocol):
    def detect(self, frame: object) -> Sequence[Detection]: ...


class UnavailableDetector:
    def detect(self, frame: object) -> Sequence[Detection]:
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE, "Person detection is not configured for this worker."
        )


class TargetFrameAnalyzer:
    """Runs full-frame detection and associates the selected athlete deterministically."""

    def __init__(self, detector: PersonDetector) -> None:
        self.detector = detector

    def observe_selected(
        self,
        frame: object,
        *,
        frame_index: int,
        timestamp_ms: int,
        normalized_x: float,
        normalized_y: float,
        source_width: int,
        source_height: int,
        capture_association_evidence: bool = True,
    ) -> RawFrameObservation:
        return self.select_selected(
            self.detector.detect(frame),
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            normalized_x=normalized_x,
            normalized_y=normalized_y,
            source_width=source_width,
            source_height=source_height,
            capture_association_evidence=capture_association_evidence,
        )

    def select_selected(
        self,
        detections: Sequence[Detection],
        *,
        frame_index: int,
        timestamp_ms: int,
        normalized_x: float,
        normalized_y: float,
        source_width: int,
        source_height: int,
        capture_association_evidence: bool = True,
    ) -> RawFrameObservation:
        reference = source_tap(normalized_x, normalized_y, source_width, source_height)
        detection, association = select_target_with_association(
            detections,
            reference,
            reference_kind=SelectionReferenceKind.TAP,
            containing_outcome=SelectionOutcome.SELECTED_CONTAINING_TAP,
            nearest_outcome=SelectionOutcome.SELECTED_NEAREST_TAP,
            capture_evidence=capture_association_evidence,
            terminal_on_empty=True,
        )
        assert detection is not None
        return RawFrameObservation(
            frame_index,
            timestamp_ms,
            detection,
            _selection_outcome(
                association,
                SelectionOutcome.SELECTED_CONTAINING_TAP,
                SelectionOutcome.SELECTED_NEAREST_TAP,
                detection.bounds.contains(reference),
            ),
            association,
        )

    def observe(
        self,
        frame: object,
        *,
        frame_index: int,
        timestamp_ms: int,
        reference: Point,
        reference_kind: SelectionReferenceKind,
        capture_association_evidence: bool = True,
    ) -> RawFrameObservation:
        return self.associate(
            self.detector.detect(frame),
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            reference=reference,
            reference_kind=reference_kind,
            reference_bounds=None,
            capture_association_evidence=capture_association_evidence,
        )

    def associate(
        self,
        detections: Sequence[Detection],
        *,
        frame_index: int,
        timestamp_ms: int,
        reference: Point,
        reference_kind: SelectionReferenceKind,
        reference_bounds: Rect | None,
        capture_association_evidence: bool = True,
    ) -> RawFrameObservation:
        accepted = (
            detections
            if reference_bounds is None
            else tuple(
                detection
                for detection in detections
                if _within_association_gate(detection.bounds, reference_bounds)
            )
        )
        if detections and not accepted:
            return RawFrameObservation(
                frame_index,
                timestamp_ms,
                None,
                SelectionOutcome.NO_ACCEPTED_CANDIDATE,
                _rejected_association_evidence(
                    detections, reference, reference_kind, capture_association_evidence
                ),
            )
        detection, association = select_target_with_association(
            accepted,
            reference,
            reference_kind=reference_kind,
            containing_outcome=SelectionOutcome.ASSOCIATED_CONTAINING_REFERENCE,
            nearest_outcome=SelectionOutcome.ASSOCIATED_NEAREST_REFERENCE,
            capture_evidence=capture_association_evidence,
            terminal_on_empty=False,
        )
        if detection is None:
            return RawFrameObservation(
                frame_index,
                timestamp_ms,
                None,
                (
                    SelectionOutcome.NO_DETECTIONS
                    if not accepted
                    else SelectionOutcome.NO_ACCEPTED_CANDIDATE
                ),
                association,
            )
        return RawFrameObservation(
            frame_index,
            timestamp_ms,
            detection,
            _selection_outcome(
                association,
                SelectionOutcome.ASSOCIATED_CONTAINING_REFERENCE,
                SelectionOutcome.ASSOCIATED_NEAREST_REFERENCE,
                detection.bounds.contains(reference),
            ),
            association,
        )


def source_tap(normalized_x: float, normalized_y: float, width: int, height: int) -> Point:
    if width <= 0 or height <= 0:
        raise ValueError("source dimensions must be positive")
    if not 0 <= normalized_x <= 1 or not 0 <= normalized_y <= 1:
        raise ValueError("normalized target coordinates must be between zero and one")
    return Point(normalized_x * width, normalized_y * height)


def select_target(detections: Sequence[Detection], tap: Point) -> Detection:
    selected, _ = select_target_with_association(
        detections,
        tap,
        reference_kind=SelectionReferenceKind.TAP,
        containing_outcome=SelectionOutcome.SELECTED_CONTAINING_TAP,
        nearest_outcome=SelectionOutcome.SELECTED_NEAREST_TAP,
        terminal_on_empty=True,
    )
    assert selected is not None
    return selected


def select_target_with_association(
    detections: Sequence[Detection],
    reference: Point,
    *,
    reference_kind: SelectionReferenceKind,
    containing_outcome: SelectionOutcome,
    nearest_outcome: SelectionOutcome,
    capture_evidence: bool = True,
    terminal_on_empty: bool,
) -> tuple[Detection | None, AssociationEvidence | None]:
    if not detections:
        if terminal_on_empty:
            raise terminal(
                ErrorCode.NO_SELECTED_ATHLETE, "No athlete was found at the selected frame."
            )
        return None, _no_detection_evidence(reference, reference_kind, capture_evidence)
    selected = _select(detections, reference)
    outcome = containing_outcome if selected.bounds.contains(reference) else nearest_outcome
    if not capture_evidence:
        return selected, None
    selected_index = next(
        index for index, detection in enumerate(detections) if detection is selected
    )
    candidates = tuple(
        DetectionCandidate(
            index,
            detection,
            detection.bounds.contains(reference),
            _center_distance(detection, reference),
            index == selected_index,
        )
        for index, detection in enumerate(detections)
    )
    retained = _retained_candidates(candidates, selected_index)
    return selected, AssociationEvidence(
        reference,
        reference_kind,
        SelectionStrategy.CONTAINING_REFERENCE_THEN_NEAREST_CENTER,
        outcome,
        len(candidates),
        retained,
        len(retained) < len(candidates),
    )


def _no_detection_evidence(
    reference: Point, reference_kind: SelectionReferenceKind, capture: bool
) -> AssociationEvidence | None:
    if not capture:
        return None
    return AssociationEvidence(
        reference,
        reference_kind,
        SelectionStrategy.CONTAINING_REFERENCE_THEN_NEAREST_CENTER,
        SelectionOutcome.NO_DETECTIONS,
        0,
        (),
        False,
    )


def _rejected_association_evidence(
    detections: Sequence[Detection],
    reference: Point,
    reference_kind: SelectionReferenceKind,
    capture: bool,
) -> AssociationEvidence | None:
    if not capture:
        return None
    candidates = tuple(
        DetectionCandidate(
            index,
            detection,
            detection.bounds.contains(reference),
            _center_distance(detection, reference),
            False,
        )
        for index, detection in enumerate(detections)
    )
    retained = _retained_candidates(candidates, 0)
    return AssociationEvidence(
        reference,
        reference_kind,
        SelectionStrategy.CONTAINING_REFERENCE_THEN_NEAREST_CENTER,
        SelectionOutcome.NO_ACCEPTED_CANDIDATE,
        len(candidates),
        retained,
        len(retained) < len(candidates),
    )


def _within_association_gate(candidate: Rect, reference: Rect) -> bool:
    return hypot(
        candidate.center.x - reference.center.x, candidate.center.y - reference.center.y
    ) <= MAX_ASSOCIATION_CENTER_DISTANCE_DIAGONALS * hypot(reference.width, reference.height)


def _select(detections: Sequence[Detection], reference: Point) -> Detection:
    containing = [detection for detection in detections if detection.bounds.contains(reference)]
    return min(
        containing or detections,
        key=lambda detection: _center_distance_squared(detection, reference),
    )


def _center_distance(detection: Detection, reference: Point) -> float:
    center = detection.bounds.center
    return hypot(center.x - reference.x, center.y - reference.y)


def _center_distance_squared(detection: Detection, reference: Point) -> float:
    center = detection.bounds.center
    return (center.x - reference.x) ** 2 + (center.y - reference.y) ** 2


def _selection_outcome(
    association: AssociationEvidence | None,
    containing_outcome: SelectionOutcome,
    nearest_outcome: SelectionOutcome,
    selected_contains_reference: bool,
) -> SelectionOutcome:
    return (
        association.outcome
        if association is not None
        else containing_outcome
        if selected_contains_reference
        else nearest_outcome
    )


def _retained_candidates(
    candidates: tuple[DetectionCandidate, ...], selected_index: int
) -> tuple[DetectionCandidate, ...]:
    if len(candidates) <= MAX_ASSOCIATION_CANDIDATES:
        return candidates
    retained_indexes = set(range(MAX_ASSOCIATION_CANDIDATES))
    retained_indexes.add(selected_index)
    if len(retained_indexes) > MAX_ASSOCIATION_CANDIDATES:
        retained_indexes.remove(MAX_ASSOCIATION_CANDIDATES - 1)
    return tuple(
        candidate for candidate in candidates if candidate.original_index in retained_indexes
    )
