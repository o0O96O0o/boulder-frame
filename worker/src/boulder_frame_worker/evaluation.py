"""Offline evaluation for sanitized, source-coordinate debug bundles.

Version 1 consumes the canonical writer's gzip JSON Lines records: a
``debug_bundle_header`` header followed by ``frame`` records. A frame contains
``detection`` (current detector box and association evidence), ``framing``
(detector input and crop), and ``render`` (crop and timestamp). Ground truth
remains a separate, human-reviewed JSON document; neither format permits raw
image or video payloads.
"""

from __future__ import annotations

import gzip
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SELECTION_IOU_THRESHOLD = 0.5
EDGE_RISK_FRACTION = 0.05
SCENARIOS = frozenset({"stationary", "lateral_sprint", "jump", "occlusion", "lost_subject"})


class EvaluationValidationError(ValueError):
    """An evaluation input is malformed, unreviewed, or incompatible."""


class FailureClass(StrEnum):
    DETECTION = "detection"
    SELECTION = "selection"
    FRAMING = "framing"
    RENDER_MAPPING = "render_mapping"
    INSUFFICIENT_ANNOTATION = "insufficient_annotation"


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
    def area(self) -> float:
        return self.width * self.height

    def contains_point(self, point: Point) -> bool:
        return self.x <= point.x <= self.right and self.y <= point.y <= self.bottom

    def contains_rect(self, other: Rect) -> bool:
        return (
            self.x <= other.x
            and self.y <= other.y
            and self.right >= other.right
            and self.bottom >= other.bottom
        )


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    source_id: str | None
    width: int
    height: int
    frame_rate: float
    variable_frame_rate: bool
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class DebugHeader:
    source: SourceMetadata
    pipeline_version: str
    model_version: str
    planner_config: Mapping[str, object]
    model_manifest: Mapping[str, object]

    @property
    def planner_version(self) -> str:
        return _configuration_label(self.planner_config, "planner_version")

    @property
    def profile(self) -> str:
        return _configuration_label(self.planner_config, "profile")


@dataclass(frozen=True, slots=True)
class DebugFrame:
    frame_index: int
    timestamp_ms: int
    detection: Rect | None
    selected: bool | None
    crop: Rect | None
    rendered_crop: Rect | None
    rendered_timestamp_ms: int | None
    render_mapping_independently_verified: bool = False
    source_aspect_limited: bool = False


@dataclass(frozen=True, slots=True)
class DebugBundle:
    header: DebugHeader
    frames: tuple[DebugFrame, ...]


@dataclass(frozen=True, slots=True)
class AnnotationFrame:
    frame_index: int
    timestamp_ms: int
    visible: bool
    occluded: bool
    ambiguous: bool
    bounds: Rect | None
    landmarks: tuple[Point, ...]
    root: Point | None
    identity: str | None


@dataclass(frozen=True, slots=True)
class AnnotationSet:
    case_id: str
    source: SourceMetadata
    reviewer: str
    frames: tuple[AnnotationFrame, ...]


@dataclass(frozen=True, slots=True)
class ManifestCase:
    case_id: str
    scenario: str
    annotation: str
    source: SourceMetadata
    target_frame_index: int


@dataclass(frozen=True, slots=True)
class FrameMetrics:
    frame_index: int
    timestamp_ms: int
    detection_available: bool | None
    detection_iou: float | None
    selection_correct: bool | None
    crop_contains_subject: bool | None
    source_aspect_limited: bool | None
    edge_risk: bool | None
    subject_scale: float | None
    pan_velocity: float | None
    pan_acceleration: float | None
    pan_jerk: float | None
    zoom_velocity: float | None
    zoom_acceleration: float | None
    zoom_jerk: float | None
    failure: FailureClass | None


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    case_id: str
    segment: Mapping[str, str]
    frames: tuple[FrameMetrics, ...]
    aggregate: Mapping[str, float | int | None]
    first_failure_frame: int | None
    first_failure: FailureClass | None

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "segment": dict(self.segment),
            "frames": [
                {**asdict(frame), "failure": None if frame.failure is None else frame.failure.value}
                for frame in self.frames
            ],
            "aggregate": dict(self.aggregate),
            "first_failure_frame": self.first_failure_frame,
            "first_failure": None if self.first_failure is None else self.first_failure.value,
        }


def load_debug_bundle(path: Path, *, max_frames: int) -> DebugBundle:
    """Load and validate a v1 gzip JSONL telemetry bundle without decoding media."""
    _positive_int(max_frames, "max_frames")
    header: DebugHeader | None = None
    frames: list[DebugFrame] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                record = json.loads(line)
                if header is None:
                    header_record = _mapping(record, "debug header")
                    if header_record.get("record_type") != "header":
                        raise EvaluationValidationError("first debug record must be a header")
                    _schema_version(header_record, "debug bundle")
                    header = DebugHeader(
                        source=_source_metadata(
                            _mapping(header_record.get("source_metadata"), "header source_metadata")
                        ),
                        pipeline_version=_string(
                            header_record.get("pipeline_version"), "pipeline_version"
                        ),
                        model_version=_string(header_record.get("model_version"), "model_version"),
                        planner_config=_mapping(
                            header_record.get("planner_config"), "planner_config"
                        ),
                        model_manifest=_mapping(
                            header_record.get("model_manifest"), "model_manifest"
                        ),
                    )
                elif isinstance(record, dict) and record.get("record_type") == "frame":
                    if len(frames) >= max_frames:
                        raise EvaluationValidationError(
                            f"debug bundle exceeds max_frames: {max_frames}"
                        )
                    frames.append(_debug_frame(record))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationValidationError(f"invalid debug bundle: {path}") from error
    if header is None:
        raise EvaluationValidationError("debug bundle is empty")
    _strictly_increasing_frames(frames, "debug")
    return DebugBundle(header, tuple(frames))


def load_annotations(path: Path) -> AnnotationSet:
    """Load human-reviewed v1 source-coordinate annotations from JSON."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationValidationError(f"invalid annotation file: {path}") from error
    data = _mapping(record, "annotations")
    _schema_version(data, "annotations")
    if data.get("human_reviewed") is not True:
        raise EvaluationValidationError("annotations must be marked human_reviewed")
    annotations = AnnotationSet(
        case_id=_string(data.get("case_id"), "case_id"),
        source=_source_metadata(_mapping(data.get("source"), "annotation source")),
        reviewer=_string(data.get("reviewer"), "reviewer"),
        frames=tuple(
            _annotation_frame(
                item, _source_metadata(_mapping(data.get("source"), "annotation source"))
            )
            for item in _sequence(data.get("frames"), "annotation frames")
        ),
    )
    if not annotations.frames:
        raise EvaluationValidationError("annotations must contain at least one frame")
    _strictly_increasing_frames(annotations.frames, "annotation")
    return annotations


def load_manifest(path: Path) -> tuple[ManifestCase, ...]:
    """Load permitted evaluation case metadata; it deliberately contains no media path."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationValidationError(f"invalid evaluation manifest: {path}") from error
    data = _mapping(record, "manifest")
    _schema_version(data, "manifest")
    cases: list[ManifestCase] = []
    identifiers: set[str] = set()
    for raw_case in _sequence(data.get("cases"), "manifest cases"):
        item = _mapping(raw_case, "manifest case")
        case_id = _string(item.get("case_id"), "case_id")
        if case_id in identifiers:
            raise EvaluationValidationError(f"duplicate manifest case_id: {case_id}")
        identifiers.add(case_id)
        scenario = _string(item.get("scenario"), "scenario")
        if scenario not in SCENARIOS:
            raise EvaluationValidationError(f"unsupported scenario: {scenario}")
        selection = _mapping(item.get("target_selection"), "target_selection")
        target_frame_index = _non_negative_int(selection.get("frame_index"), "target frame_index")
        cases.append(
            ManifestCase(
                case_id,
                scenario,
                _string(item.get("annotation"), "annotation"),
                _source_metadata(_mapping(item.get("source"), "manifest source")),
                target_frame_index,
            )
        )
    if not cases:
        raise EvaluationValidationError("manifest must contain at least one case")
    return tuple(cases)


def evaluate(bundle: DebugBundle, annotations: AnnotationSet) -> EvaluationReport:
    """Compare one bundle to reviewed annotations and return deterministic metrics."""
    if not _source_matches(bundle.header.source, annotations.source):
        raise EvaluationValidationError("debug and annotation source metadata do not match")
    annotation_by_index = {frame.frame_index: frame for frame in annotations.frames}
    motion = _motion_metrics(bundle.frames, bundle.header.source)
    frames: list[FrameMetrics] = []
    for debug in bundle.frames:
        annotation = annotation_by_index.get(debug.frame_index)
        values = _frame_metrics(
            debug, annotation, motion.get(debug.frame_index)
        )
        frames.append(values)
    recorded_indices = {frame.frame_index for frame in bundle.frames}
    for annotation in annotations.frames:
        if annotation.frame_index not in recorded_indices:
            frames.append(
                _empty_metrics(
                    DebugFrame(
                        annotation.frame_index,
                        annotation.timestamp_ms,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                    None,
                    FailureClass.INSUFFICIENT_ANNOTATION,
                )
            )
    frames.sort(key=lambda frame: frame.frame_index)
    aggregate = _aggregate(frames)
    first = next((frame for frame in frames if frame.failure is not None), None)
    segment = {
        "model_version": bundle.header.model_version,
        "planner_version": bundle.header.planner_version,
        "pipeline_version": bundle.header.pipeline_version,
        "profile": bundle.header.profile,
        "resolution": f"{bundle.header.source.width}x{bundle.header.source.height}",
    }
    return EvaluationReport(
        annotations.case_id,
        segment,
        tuple(frames),
        aggregate,
        None if first is None else first.frame_index,
        None if first is None else first.failure,
    )


def aggregate_reports(
    reports: Iterable[EvaluationReport],
) -> dict[tuple[tuple[str, str], ...], dict[str, float | int | None]]:
    """Aggregate sequence reports by model/planner/profile/resolution segment."""
    grouped: dict[tuple[tuple[str, str], ...], list[EvaluationReport]] = defaultdict(list)
    for report in reports:
        key = tuple(sorted(report.segment.items()))
        grouped[key].append(report)
    return {
        key: _aggregate(frame for report in group for frame in report.frames)
        for key, group in grouped.items()
    }


def _debug_frame(record: object) -> DebugFrame:
    data = _mapping(record, "debug frame")
    if data.get("record_type") != "frame":
        raise EvaluationValidationError("debug records after header must be frames")
    _schema_version(data, "debug frame")
    detection_section = _required_mapping(data, "detection")
    framing = _required_mapping(data, "framing")
    render = _required_mapping(data, "render")
    _require_keys(detection_section, "detection", "detection")
    _require_keys(framing, "framing", "input", "crop")
    _require_keys(render, "render", "crop", "timestamp_ms")
    detection = _nested_rect(detection_section, "detection")
    selection = _optional_mapping(detection_section.get("selection"), "selection")
    decision = _optional_mapping(framing.get("decision"), "framing.decision")
    return DebugFrame(
        _non_negative_int(data.get("frame_index"), "frame_index"),
        _non_negative_int(data.get("timestamp_ms"), "timestamp_ms"),
        detection,
        None if selection is None else _boolean(selection.get("selected"), "selection.selected"),
        None if framing.get("crop") is None else _rect(framing.get("crop"), "framing.crop"),
        None if render.get("crop") is None else _rect(render.get("crop"), "render.crop"),
        None
        if render.get("timestamp_ms") is None
        else _non_negative_int(render.get("timestamp_ms"), "render.timestamp_ms"),
        _boolean(
            render.get("mapping_independently_verified", False),
            "render.mapping_independently_verified",
        ),
        False
        if decision is None
        else _boolean(
            decision.get("source_aspect_limited", False), "framing.source_aspect_limited"
        ),
    )


def _annotation_frame(record: object, source: SourceMetadata) -> AnnotationFrame:
    data = _mapping(record, "annotation frame")
    visible = _boolean(data.get("visible"), "annotation visible")
    occluded = _boolean(data.get("occluded", False), "annotation occluded")
    ambiguous = _boolean(data.get("ambiguous", False), "annotation ambiguous")
    bounds = None if data.get("bounds") is None else _rect(data.get("bounds"), "annotation bounds")
    if visible and bounds is None:
        raise EvaluationValidationError("visible annotation requires bounds")
    if bounds is not None:
        _within_source(bounds, source, "annotation bounds")
    landmarks = tuple(
        _point(item, "annotation landmark")
        for item in _sequence(data.get("landmarks", []), "annotation landmarks")
    )
    for landmark in landmarks:
        _within_source(landmark, source, "annotation landmark")
    root = None if data.get("root") is None else _point(data.get("root"), "annotation root")
    if root is not None:
        _within_source(root, source, "annotation root")
    return AnnotationFrame(
        _non_negative_int(data.get("frame_index"), "annotation frame_index"),
        _non_negative_int(data.get("timestamp_ms"), "annotation timestamp_ms"),
        visible,
        occluded,
        ambiguous,
        bounds,
        landmarks,
        root,
        None
        if data.get("identity") is None
        else _string(data.get("identity"), "annotation identity"),
    )


def _frame_metrics(
    debug: DebugFrame,
    annotation: AnnotationFrame | None,
    motion: tuple[
        float | None, float | None, float | None, float | None, float | None, float | None
    ]
    | None,
) -> FrameMetrics:
    if annotation is None or annotation.ambiguous:
        return _empty_metrics(debug, motion, FailureClass.INSUFFICIENT_ANNOTATION)
    if not annotation.visible or annotation.bounds is None:
        return _empty_metrics(debug, motion, None)
    detection_iou = None if debug.detection is None else _iou(debug.detection, annotation.bounds)
    detection_available = debug.detection is not None
    selected = detection_available if debug.selected is None else debug.selected
    selection_correct = (
        None
        if not detection_available
        else selected and detection_iou is not None and detection_iou >= SELECTION_IOU_THRESHOLD
    )
    crop = debug.crop
    contained = None if crop is None else crop.contains_rect(annotation.bounds)
    edge_risk = None if crop is None else _edge_risk(crop, annotation.bounds)
    scale = None if crop is None else annotation.bounds.area / crop.area
    failure = _failure(
        annotation,
        detection_available,
        selection_correct,
        contained,
        debug,
    )
    pan_v, pan_a, pan_j, zoom_v, zoom_a, zoom_j = motion or (None,) * 6
    return FrameMetrics(
        debug.frame_index,
        debug.timestamp_ms,
        detection_available,
        detection_iou,
        selection_correct,
        contained,
        debug.source_aspect_limited,
        edge_risk,
        scale,
        pan_v,
        pan_a,
        pan_j,
        zoom_v,
        zoom_a,
        zoom_j,
        failure,
    )


def _empty_metrics(
    debug: DebugFrame,
    motion: tuple[
        float | None, float | None, float | None, float | None, float | None, float | None
    ]
    | None,
    failure: FailureClass | None,
) -> FrameMetrics:
    pan_v, pan_a, pan_j, zoom_v, zoom_a, zoom_j = motion or (None,) * 6
    return FrameMetrics(
        debug.frame_index,
        debug.timestamp_ms,
        None,
        None,
        None,
        None,
        debug.source_aspect_limited,
        None,
        None,
        pan_v,
        pan_a,
        pan_j,
        zoom_v,
        zoom_a,
        zoom_j,
        failure,
    )


def _failure(
    annotation: AnnotationFrame,
    detection_available: bool,
    selection_correct: bool | None,
    contained: bool | None,
    debug: DebugFrame,
) -> FailureClass | None:
    if not detection_available:
        return FailureClass.DETECTION
    if selection_correct is False:
        return FailureClass.SELECTION
    if contained is False:
        return FailureClass.FRAMING
    if debug.render_mapping_independently_verified and (
        (
            debug.rendered_crop is not None
            and (debug.crop is None or not _same_rect(debug.crop, debug.rendered_crop))
        )
        or (
            debug.rendered_timestamp_ms is not None
            and debug.rendered_timestamp_ms != debug.timestamp_ms
        )
    ):
        return FailureClass.RENDER_MAPPING
    del annotation
    return None


def _motion_metrics(
    frames: Sequence[DebugFrame], source: SourceMetadata
) -> dict[
    int, tuple[float | None, float | None, float | None, float | None, float | None, float | None]
]:
    result: dict[
        int,
        tuple[float | None, float | None, float | None, float | None, float | None, float | None],
    ] = {}
    previous: DebugFrame | None = None
    previous_pan_velocity: float | None = None
    previous_zoom_velocity: float | None = None
    previous_pan_acceleration: float | None = None
    previous_zoom_acceleration: float | None = None
    diagonal = math.hypot(source.width, source.height)
    for frame in frames:
        pan_v = zoom_v = pan_a = zoom_a = pan_j = zoom_j = None
        if previous is not None and frame.crop is not None and previous.crop is not None:
            elapsed = (frame.timestamp_ms - previous.timestamp_ms) / 1000
            if elapsed > 0:
                pan_v = (
                    math.hypot(
                        frame.crop.x
                        + frame.crop.width / 2
                        - previous.crop.x
                        - previous.crop.width / 2,
                        frame.crop.y
                        + frame.crop.height / 2
                        - previous.crop.y
                        - previous.crop.height / 2,
                    )
                    / diagonal
                    / elapsed
                )
                zoom_v = abs(math.log(frame.crop.height / previous.crop.height)) / elapsed
                if previous_pan_velocity is not None:
                    pan_a = abs(pan_v - previous_pan_velocity) / elapsed
                if previous_zoom_velocity is not None:
                    zoom_a = abs(zoom_v - previous_zoom_velocity) / elapsed
                if previous_pan_acceleration is not None and pan_a is not None:
                    pan_j = abs(pan_a - previous_pan_acceleration) / elapsed
                if previous_zoom_acceleration is not None and zoom_a is not None:
                    zoom_j = abs(zoom_a - previous_zoom_acceleration) / elapsed
        result[frame.frame_index] = (pan_v, pan_a, pan_j, zoom_v, zoom_a, zoom_j)
        previous = frame
        if pan_v is not None:
            previous_pan_velocity = pan_v
        if zoom_v is not None:
            previous_zoom_velocity = zoom_v
        if pan_a is not None:
            previous_pan_acceleration = pan_a
        if zoom_a is not None:
            previous_zoom_acceleration = zoom_a
    return result


def _aggregate(frames: Iterable[FrameMetrics]) -> dict[str, float | int | None]:
    values = tuple(frames)
    visible = tuple(frame for frame in values if frame.detection_available is not None)
    selection_evaluated = tuple(frame for frame in visible if frame.selection_correct is not None)
    true_positives = sum(frame.selection_correct is True for frame in selection_evaluated)
    false_positives = sum(frame.selection_correct is False for frame in selection_evaluated)
    false_negatives = len(selection_evaluated) - true_positives
    return {
        "annotated_frames": len(visible),
        "detection_availability": _rate(
            sum(frame.detection_available is True for frame in visible), len(visible)
        ),
        "mean_detection_iou": _mean(frame.detection_iou for frame in visible),
        "selection_precision": _rate(true_positives, true_positives + false_positives),
        "selection_recall": _rate(true_positives, true_positives + false_negatives),
        "crop_containment": _rate(
            sum(frame.crop_contains_subject is True for frame in visible), len(visible)
        ),
        "source_aspect_limited_rate": _rate(
            sum(frame.source_aspect_limited is True for frame in visible), len(visible)
        ),
        "edge_risk_rate": _rate(sum(frame.edge_risk is True for frame in visible), len(visible)),
        "mean_subject_scale": _mean(frame.subject_scale for frame in visible),
        "mean_pan_velocity": _mean(frame.pan_velocity for frame in values),
        "mean_pan_acceleration": _mean(frame.pan_acceleration for frame in values),
        "mean_pan_jerk": _mean(frame.pan_jerk for frame in values),
        "mean_zoom_velocity": _mean(frame.zoom_velocity for frame in values),
        "mean_zoom_acceleration": _mean(frame.zoom_acceleration for frame in values),
        "mean_zoom_jerk": _mean(frame.zoom_jerk for frame in values),
    }


def _source_metadata(data: Mapping[str, object]) -> SourceMetadata:
    source_id = data.get("source_id")
    sha256 = data.get("sha256")
    if source_id is None and sha256 is None:
        raise EvaluationValidationError("source metadata requires source_id or sha256")
    source = SourceMetadata(
        None if source_id is None else _string(source_id, "source_id"),
        _positive_int(data.get("display_width", data.get("width")), "source display_width"),
        _positive_int(data.get("display_height", data.get("height")), "source display_height"),
        _positive_float(data.get("frame_rate"), "source frame_rate"),
        _boolean(data.get("variable_frame_rate"), "source variable_frame_rate"),
        None if sha256 is None else _string(sha256, "sha256"),
    )
    if source.variable_frame_rate:
        raise EvaluationValidationError("variable-frame-rate sources are not supported")
    return source


def _source_matches(left: SourceMetadata, right: SourceMetadata) -> bool:
    if (
        left.width != right.width
        or left.height != right.height
        or left.frame_rate != right.frame_rate
        or left.variable_frame_rate != right.variable_frame_rate
    ):
        return False
    return (left.source_id is not None and left.source_id == right.source_id) or (
        left.sha256 is not None and left.sha256 == right.sha256
    )


def _nested_rect(data: Mapping[str, object], key: str) -> Rect | None:
    nested = _optional_mapping(data.get(key), key)
    return (
        None
        if nested is None or nested.get("bounds") is None
        else _rect(nested.get("bounds"), f"{key}.bounds")
    )


def _configuration_label(config: Mapping[str, object], key: str) -> str:
    value = config.get(key, config.get("version") if key == "planner_version" else None)
    return value if isinstance(value, str) and value else "unknown"


def _required_mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    if key not in data:
        raise EvaluationValidationError(f"debug frame requires {key}")
    return _mapping(data[key], key)


def _require_keys(data: Mapping[str, object], name: str, *keys: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise EvaluationValidationError(f"{name} requires {', '.join(missing)}")


def _rect(value: object, name: str) -> Rect:
    data = _mapping(value, name)
    return Rect(
        _finite(data.get("x"), f"{name}.x"),
        _finite(data.get("y"), f"{name}.y"),
        _positive_float(data.get("width"), f"{name}.width"),
        _positive_float(data.get("height"), f"{name}.height"),
    )


def _point(value: object, name: str) -> Point:
    data = _mapping(value, name)
    return Point(_finite(data.get("x"), f"{name}.x"), _finite(data.get("y"), f"{name}.y"))


def _within_source(value: Rect | Point, source: SourceMetadata, name: str) -> None:
    right = value.right if isinstance(value, Rect) else value.x
    bottom = value.bottom if isinstance(value, Rect) else value.y
    if value.x < 0 or value.y < 0 or right > source.width or bottom > source.height:
        raise EvaluationValidationError(f"{name} is outside source bounds")


def _strictly_increasing_frames(frames: Sequence[Any], name: str) -> None:
    previous_index = previous_timestamp = -1
    for frame in frames:
        if frame.frame_index <= previous_index:
            raise EvaluationValidationError(f"{name} frame indices must be unique and increasing")
        if frame.timestamp_ms <= previous_timestamp:
            raise EvaluationValidationError(f"{name} timestamps must be strictly increasing")
        previous_index, previous_timestamp = frame.frame_index, frame.timestamp_ms


def _iou(left: Rect, right: Rect) -> float:
    width = max(0.0, min(left.right, right.right) - max(left.x, right.x))
    height = max(0.0, min(left.bottom, right.bottom) - max(left.y, right.y))
    intersection = width * height
    return intersection / (left.area + right.area - intersection)


def _edge_risk(crop: Rect, bounds: Rect) -> bool:
    margin = min(
        bounds.x - crop.x, bounds.y - crop.y, crop.right - bounds.right, crop.bottom - bounds.bottom
    )
    return margin / min(crop.width, crop.height) <= EDGE_RISK_FRACTION


def _distance(left: Point | None, right: Point | None) -> float | None:
    if left is None or right is None:
        return None
    return math.hypot(left.x - right.x, left.y - right.y)


def _same_rect(left: Rect, right: Rect) -> bool:
    return all(
        math.isclose(a, b, abs_tol=1e-6)
        for a, b in zip(asdict(left).values(), asdict(right).values(), strict=True)
    )


def _mean(values: Iterable[float | int | None]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    return None if not numeric else sum(numeric) / len(numeric)


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _schema_version(data: Mapping[str, object], name: str) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise EvaluationValidationError(f"unsupported {name} schema_version")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise EvaluationValidationError(f"{name} must be an object")
    return value


def _optional_mapping(value: object, name: str) -> Mapping[str, object] | None:
    return None if value is None else _mapping(value, name)


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise EvaluationValidationError(f"{name} must be an array")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvaluationValidationError(f"{name} must be a non-empty string")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise EvaluationValidationError(f"{name} must be a boolean")
    return value


def _non_negative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EvaluationValidationError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value: object, name: str) -> int:
    result = _non_negative_int(value, name)
    if result == 0:
        raise EvaluationValidationError(f"{name} must be positive")
    return result


def _finite(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise EvaluationValidationError(f"{name} must be finite")
    return float(value)


def _positive_float(value: object, name: str) -> float:
    result = _finite(value, name)
    if result <= 0:
        raise EvaluationValidationError(f"{name} must be positive")
    return result
