from __future__ import annotations

import json
from pathlib import Path

import pytest

from boulder_frame_worker.debug import DebugBundleWriter, debug_bundle_header
from boulder_frame_worker.evaluation import (
    AnnotationFrame,
    AnnotationSet,
    DebugBundle,
    DebugFrame,
    DebugHeader,
    EvaluationValidationError,
    FailureClass,
    Point,
    Rect,
    SourceMetadata,
    aggregate_reports,
    evaluate,
    load_annotations,
    load_debug_bundle,
    load_manifest,
)

SOURCE_SHA256 = "a" * 64
SOURCE = SourceMetadata("permitted-source-v1", 100, 100, 10, False, SOURCE_SHA256)
HEADER = DebugHeader(
    SOURCE,
    "pipeline-v1",
    "model-v1",
    {"planner_version": "planner-v1", "profile": "balanced"},
    {"name": "permitted-test-model"},
)
ANNOTATION = AnnotationFrame(
    0,
    0,
    True,
    False,
    False,
    Rect(20, 20, 20, 40),
    (Point(20, 20), Point(40, 60)),
    Point(30, 45),
    "athlete-a",
)
DETECTION = Rect(20, 20, 20, 40)
TRACKER_ROOT = Point(30, 45)
CROP = Rect(10, 10, 50, 70)


def frame(
    index: int,
    timestamp_ms: int,
    *,
    detection: Rect | None = DETECTION,
    selected: bool | None = True,
    tracker_root: Point | None = TRACKER_ROOT,
    tracker_state: str | None = "tracked",
    crop: Rect | None = CROP,
    rendered_crop: Rect | None = None,
    rendered_timestamp_ms: int | None = None,
    render_mapping_independently_verified: bool = False,
) -> DebugFrame:
    return DebugFrame(
        index,
        timestamp_ms,
        detection,
        selected,
        Point(30, 45),
        tracker_root,
        tracker_state,
        crop,
        rendered_crop,
        rendered_timestamp_ms,
        render_mapping_independently_verified,
    )


def report(*frames: DebugFrame, annotations: tuple[AnnotationFrame, ...] = (ANNOTATION,)):
    return evaluate(
        DebugBundle(HEADER, frames),
        AnnotationSet("case-v1", SOURCE, "reviewer", annotations),
    )


def test_loads_permitted_manifest_and_human_reviewed_annotations() -> None:
    directory = Path(__file__).parent / "evaluation"

    cases = load_manifest(directory / "manifest.json")
    annotations = load_annotations(directory / "stationary.json")

    assert cases[0].case_id == annotations.case_id
    assert cases[0].scenario == "stationary"
    assert annotations.frames[0].bounds == Rect(20, 20, 20, 40)


def test_rejects_unreviewed_and_out_of_bounds_annotations(tmp_path: Path) -> None:
    path = tmp_path / "annotations.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "case",
                "human_reviewed": False,
                "reviewer": "reviewer",
                "source": source_json(),
                "frames": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvaluationValidationError, match="human_reviewed"):
        load_annotations(path)

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "case",
                "human_reviewed": True,
                "reviewer": "reviewer",
                "source": source_json(),
                "frames": [annotation_json(bounds={"x": 90, "y": 10, "width": 20, "height": 10})],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvaluationValidationError, match="outside source bounds"):
        load_annotations(path)


def test_parses_v1_gzip_jsonl_bundle(tmp_path: Path) -> None:
    path = tmp_path / "debug.jsonl.gz"
    header = debug_bundle_header(
        job_id="job-v1",
        source_metadata=source_json(),
        pipeline_version="pipeline-v1",
        model_version="model-v1",
        planner_config={"planner_version": "planner-v1", "profile": "balanced"},
        model_manifest={"name": "permitted-test-model"},
    )
    with DebugBundleWriter(path, header) as writer:
        writer.write(
            "frame",
            {
                "frame_index": 0,
                "timestamp_ms": 0,
                "measurement": {
                    "detection": {"bounds": {"x": 20, "y": 20, "width": 20, "height": 40}},
                    "selection": {"selected": True},
                    "pose": {"root": {"x": 30, "y": 45}},
                },
                "tracking": {"root": {"x": 30, "y": 45}, "state": "tracked"},
                "planning": {
                    "input": {"lost": False},
                    "crop": {"x": 10, "y": 10, "width": 50, "height": 70},
                },
                "render": {
                    "crop": {"x": 10, "y": 10, "width": 50, "height": 70},
                    "timestamp_ms": 0,
                    "mapping_independently_verified": True,
                },
            },
        )

    bundle = load_debug_bundle(path, max_frames=1)

    assert bundle.header.source == SOURCE
    assert bundle.header.planner_version == "planner-v1"
    assert bundle.frames[0].render_mapping_independently_verified is True


def test_ignores_operational_stage_records_in_debug_bundle(tmp_path: Path) -> None:
    path = tmp_path / "debug.jsonl.gz"
    with DebugBundleWriter(
        path,
        debug_bundle_header(
            job_id="job-1",
            source_metadata=source_json(),
            pipeline_version="pipeline-v1",
            model_version="model-v1",
            planner_config={"planner_version": "planner-v1", "profile": "balanced"},
            model_manifest={},
        ),
    ) as writer:
        writer.write("stage_end", {"stage": "analyzing", "duration_ms": 1})
        writer.write(
            "frame",
            {
                "frame_index": 0,
                "timestamp_ms": 0,
                "measurement": {
                    "detection": {"bounds": {"x": 20, "y": 20, "width": 20, "height": 40}},
                    "selection": {"selected": True},
                    "pose": {"root": {"x": 30, "y": 45}},
                },
                "tracking": {"root": {"x": 30, "y": 45}, "state": "tracked"},
                "planning": {
                    "input": {"lost": False},
                    "crop": {"x": 10, "y": 10, "width": 50, "height": 70},
                },
                "render": {
                    "crop": {"x": 10, "y": 10, "width": 50, "height": 70},
                    "timestamp_ms": 0,
                },
            },
        )

    bundle = load_debug_bundle(path, max_frames=1)

    assert len(bundle.frames) == 1
    assert bundle.header.profile == "balanced"
    assert bundle.frames[0] == frame(0, 0, rendered_crop=CROP, rendered_timestamp_ms=0)


def test_accepts_sha256_when_source_metadata_has_no_source_id(tmp_path: Path) -> None:
    path = tmp_path / "debug.jsonl.gz"
    metadata = source_json()
    metadata.pop("source_id")
    metadata["sha256"] = "a" * 64
    header = debug_bundle_header(
        job_id="job-v1",
        source_metadata=metadata,
        pipeline_version="pipeline-v1",
        model_version="model-v1",
        planner_config={},
        model_manifest={},
    )
    with DebugBundleWriter(path, header):
        pass

    source = load_debug_bundle(path, max_frames=1).header.source

    assert source.source_id is None
    assert source.sha256 == "a" * 64


def test_streaming_loader_rejects_bundles_exceeding_max_frames(tmp_path: Path) -> None:
    path = tmp_path / "debug.jsonl.gz"
    with DebugBundleWriter(
        path,
        debug_bundle_header(
            job_id="job-v1",
            source_metadata=source_json(),
            pipeline_version="pipeline-v1",
            model_version="model-v1",
            planner_config={},
            model_manifest={},
        ),
    ) as writer:
        for index in range(2):
            writer.write("frame", frame_record(index, index * 100))

    with pytest.raises(EvaluationValidationError, match="exceeds max_frames: 1"):
        load_debug_bundle(path, max_frames=1)

    with pytest.raises(EvaluationValidationError, match="max_frames"):
        load_debug_bundle(path, max_frames=0)


@pytest.mark.parametrize(
    ("bundle_source", "annotation_source"),
    [
        (
            SourceMetadata("matching-id", 100, 100, 10, False, "a" * 64),
            SourceMetadata("matching-id", 100, 100, 10, False, "b" * 64),
        ),
        (
            SourceMetadata("bundle-id", 100, 100, 10, False, "a" * 64),
            SourceMetadata("annotation-id", 100, 100, 10, False, "a" * 64),
        ),
    ],
)
def test_source_identity_matches_id_or_sha256(
    bundle_source: SourceMetadata, annotation_source: SourceMetadata
) -> None:
    header = DebugHeader(bundle_source, "pipeline-v1", "model-v1", {}, {})
    annotations = AnnotationSet("case-v1", annotation_source, "reviewer", (ANNOTATION,))

    assert evaluate(DebugBundle(header, (frame(0, 0),)), annotations).case_id == "case-v1"


def test_source_identity_requires_matching_dimensions_and_timing() -> None:
    header = DebugHeader(SOURCE, "pipeline-v1", "model-v1", {}, {})
    annotations = AnnotationSet(
        "case-v1",
        SourceMetadata("permitted-source-v1", 100, 100, 30, False, SOURCE_SHA256),
        "reviewer",
        (ANNOTATION,),
    )

    with pytest.raises(EvaluationValidationError, match="source metadata"):
        evaluate(DebugBundle(header, (frame(0, 0),)), annotations)


def test_metrics_include_detection_crop_tracking_recovery_and_normalized_motion() -> None:
    annotations = (
        ANNOTATION,
        AnnotationFrame(1, 100, True, False, False, Rect(20, 20, 20, 40), (), Point(30, 45), None),
        AnnotationFrame(2, 200, True, False, False, Rect(20, 20, 20, 40), (), Point(30, 45), None),
        AnnotationFrame(3, 300, True, False, False, Rect(20, 20, 20, 40), (), Point(30, 45), None),
    )
    value = report(
        frame(0, 0, tracker_root=None, tracker_state="lost", crop=Rect(10, 10, 50, 70)),
        frame(1, 100, crop=Rect(15, 10, 50, 70)),
        frame(2, 200, crop=Rect(30, 10, 50, 70)),
        frame(3, 300, crop=Rect(35, 10, 50, 70)),
        annotations=annotations,
    )

    assert value.frames[0].detection_iou == 1
    assert value.frames[1].tracking_recovery_ms == 100
    assert value.frames[1].crop_contains_subject
    assert value.frames[1].cropped_landmarks == 0
    assert value.frames[1].edge_risk is False
    assert value.frames[1].subject_scale == pytest.approx(800 / (50 * 70))
    assert value.frames[1].pan_velocity == pytest.approx(5 / (100**2 + 100**2) ** 0.5 / 0.1)
    assert value.frames[2].pan_acceleration is not None
    assert value.frames[3].pan_jerk is not None
    assert value.frames[1].zoom_velocity is not None
    assert value.aggregate["tracker_availability"] == pytest.approx(3 / 4)
    assert value.aggregate["mean_tracking_recovery_ms"] == 100


@pytest.mark.parametrize(
    ("debug", "annotation", "expected"),
    [
        (frame(0, 0, detection=None), ANNOTATION, FailureClass.MEASUREMENT),
        (frame(0, 0, selected=False), ANNOTATION, FailureClass.SELECTION),
        (frame(0, 0, tracker_root=None, tracker_state="lost"), ANNOTATION, FailureClass.TRACKING),
        (frame(0, 0, crop=Rect(25, 25, 20, 30)), ANNOTATION, FailureClass.PLANNING),
        (
            frame(0, 0, rendered_crop=Rect(11, 10, 50, 70), rendered_timestamp_ms=0),
            ANNOTATION,
            None,
        ),
        (
            frame(
                0,
                0,
                rendered_crop=Rect(11, 10, 50, 70),
                rendered_timestamp_ms=0,
                render_mapping_independently_verified=True,
            ),
            ANNOTATION,
            FailureClass.RENDER_MAPPING,
        ),
        (
            frame(0, 0),
            AnnotationFrame(0, 0, True, False, True, Rect(20, 20, 20, 40), (), Point(30, 45), None),
            FailureClass.INSUFFICIENT_ANNOTATION,
        ),
    ],
)
def test_first_failure_classification(
    debug: DebugFrame, annotation: AnnotationFrame, expected: FailureClass | None
) -> None:
    value = report(debug, annotations=(annotation,))

    assert value.first_failure_frame == (None if expected is None else 0)
    assert value.first_failure == expected


def test_missing_detection_is_excluded_from_selection_metrics() -> None:
    annotations = (
        ANNOTATION,
        AnnotationFrame(1, 100, True, False, False, DETECTION, (), Point(30, 45), None),
    )
    value = report(frame(0, 0, detection=None), frame(1, 100), annotations=annotations)

    assert value.frames[0].selection_correct is None
    assert value.aggregate["selection_precision"] == 1
    assert value.aggregate["selection_recall"] == 1


def test_missing_telemetry_for_an_annotated_frame_is_reported() -> None:
    missing = AnnotationFrame(1, 100, True, False, False, DETECTION, (), Point(30, 45), None)

    value = report(frame(0, 0), annotations=(ANNOTATION, missing))

    assert value.first_failure_frame == 1
    assert value.first_failure is FailureClass.INSUFFICIENT_ANNOTATION


def test_aggregate_reports_is_deterministic_by_versioned_segment() -> None:
    first = report(frame(0, 0))
    second = report(frame(0, 0))

    aggregate = aggregate_reports([second, first])

    assert len(aggregate) == 1
    assert next(iter(aggregate.values()))["detection_availability"] == 1


def source_json() -> dict[str, object]:
    return {
        "source_id": "permitted-source-v1",
        "sha256": SOURCE_SHA256,
        "display_width": 100,
        "display_height": 100,
        "frame_rate": 10,
        "variable_frame_rate": False,
    }


def annotation_json(*, bounds: dict[str, int]) -> dict[str, object]:
    return {
        "frame_index": 0,
        "timestamp_ms": 0,
        "visible": True,
        "occluded": False,
        "bounds": bounds,
        "root": {"x": 30, "y": 45},
        "landmarks": [],
    }


def frame_record(index: int, timestamp_ms: int) -> dict[str, object]:
    return {
        "frame_index": index,
        "timestamp_ms": timestamp_ms,
        "measurement": {
            "detection": {"bounds": {"x": 20, "y": 20, "width": 20, "height": 40}},
            "selection": {"selected": True},
            "pose": {"root": {"x": 30, "y": 45}},
        },
        "tracking": {"root": {"x": 30, "y": 45}, "state": "tracked"},
        "planning": {
            "input": {"lost": False},
            "crop": {"x": 10, "y": 10, "width": 50, "height": 70},
        },
        "render": {
            "crop": {"x": 10, "y": 10, "width": 50, "height": 70},
            "timestamp_ms": timestamp_ms,
        },
    }
