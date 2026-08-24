import gzip
import json
from pathlib import Path
from uuid import UUID

import pytest

from boulder_frame_worker.debug import (
    DEBUG_BUNDLE_SCHEMA_VERSION,
    DebugBundleLimitError,
    DebugBundleWriter,
    canonical_json_bytes,
    crop_path_digest,
    debug_bundle_header,
    deterministic_digest,
    serialize_crop_rect,
    serialize_frame_measurement,
    serialize_point,
    serialize_raw_frame_observation,
    serialize_rect,
    serialize_tracked_measurement,
)
from boulder_frame_worker.measurement import (
    Detection,
    Point,
    PoseMeasurement,
    RawFrameObservation,
    Rect,
)
from boulder_frame_worker.planner import CropRect, FrameMeasurement
from boulder_frame_worker.tracking import TrackedMeasurement, TrackingState


def test_debug_bundle_is_deterministic_and_records_each_stage(tmp_path: Path) -> None:
    header = debug_bundle_header(
        job_id=UUID("00000000-0000-0000-0000-000000000001"),
        source_metadata={"display_width": 3840, "display_height": 2160},
        pipeline_version="pipeline-1",
        model_version="model-1",
        planner_config={"profile": "balanced"},
        model_manifest={"detector": "ssd-v1", "pose": "pose-v1"},
        source_object_version="version-1",
        source_checksum="sha256:abc",
    )
    first = tmp_path / "first.jsonl.gz"
    second = tmp_path / "second.jsonl.gz"

    for path in (first, second):
        with DebugBundleWriter(path, header) as writer:
            for stage in ("validating", "analyzing", "rendering", "uploading"):
                writer.write("stage_start", {"stage": stage, "monotonic_ms": 100, "progress": 0.2})
                writer.write(
                    "stage_end",
                    {
                        "stage": stage,
                        "monotonic_ms": 125,
                        "duration_ms": 25,
                        "progress": 0.3,
                        "outcome": "completed",
                    },
                )

    assert first.read_bytes() == second.read_bytes()
    records = _records(first)
    assert records[0]["record_type"] == "header"
    assert records[0]["schema_version"] == DEBUG_BUNDLE_SCHEMA_VERSION
    assert [record["stage"] for record in records[1:]] == [
        "validating",
        "validating",
        "analyzing",
        "analyzing",
        "rendering",
        "rendering",
        "uploading",
        "uploading",
    ]


def test_debug_bundle_removes_urls_credentials_and_pixel_payloads(tmp_path: Path) -> None:
    path = tmp_path / "debug.jsonl.gz"
    secret = "not-for-output"
    signed_url = "https://storage.example/private?signature=do-not-emit"
    header = debug_bundle_header(
        job_id="job-1",
        source_metadata={"source_url": signed_url, "frame_rate": 30},
        pipeline_version="pipeline-1",
        model_version="model-1",
        planner_config={},
        model_manifest={},
    )

    with DebugBundleWriter(path, header) as writer:
        writer.write(
            "analysis_frame",
            {
                "frame_index": 1,
                "pixels": b"raw pixels",
                "nested": {"token": secret, "download_url": signed_url, "root": [10, 20]},
                "safe_url_text": "result available",
                "message": f"source was {signed_url}",
                "error": {"message": "failed", "diagnostic": secret},
            },
        )

    contents = gzip.decompress(path.read_bytes()).decode("ascii")
    assert secret not in contents
    assert signed_url not in contents
    assert "raw pixels" not in contents
    record = _records(path)[1]
    assert record["nested"] == {"root": [10, 20]}
    assert "pixels" not in record
    assert record["message"] is None
    assert record["error"] == {"message": "failed"}


@pytest.mark.parametrize(
    "key",
    ["encryption_key", "encryptionKey", "private_key", "privateKey", "raw_frame", "rawFrame"],
)
def test_debug_bundle_sanitizes_sensitive_camel_case_and_raw_frame_keys(
    tmp_path: Path, key: str
) -> None:
    path = tmp_path / "debug.jsonl.gz"
    header = debug_bundle_header(
        job_id="job-1",
        source_metadata={},
        pipeline_version="pipeline-1",
        model_version="model-1",
        planner_config={},
        model_manifest={},
    )

    with DebugBundleWriter(path, header) as writer:
        writer.write("analysis_frame", {key: "must-not-appear", "safe": True})

    assert _records(path)[1] == {
        "record_type": "analysis_frame",
        "safe": True,
        "schema_version": DEBUG_BUNDLE_SCHEMA_VERSION,
    }


def test_debug_bundle_rejects_frame_count_limit_before_writing(tmp_path: Path) -> None:
    path = tmp_path / "debug.jsonl.gz"
    header = debug_bundle_header(
        job_id="job-1",
        source_metadata={},
        pipeline_version="pipeline-1",
        model_version="model-1",
        planner_config={},
        model_manifest={},
    )

    with DebugBundleWriter(path, header, max_frames=1) as writer:
        writer.write("frame", {"frame_index": 0})
        with pytest.raises(DebugBundleLimitError, match="max_frames"):
            writer.write("frame", {"frame_index": 1})
        writer.write("stage_end", {"stage": "analyzing"})

    assert [record["record_type"] for record in _records(path)] == ["header", "frame", "stage_end"]


def test_debug_bundle_removes_partial_output_when_byte_limit_is_exceeded(tmp_path: Path) -> None:
    header = debug_bundle_header(
        job_id="job-1",
        source_metadata={},
        pipeline_version="pipeline-1",
        model_version="model-1",
        planner_config={},
        model_manifest={},
    )
    baseline = tmp_path / "baseline.jsonl.gz"
    with DebugBundleWriter(baseline, header):
        pass
    path = tmp_path / "debug.jsonl.gz"

    with pytest.raises(DebugBundleLimitError, match="max_bytes"):
        with DebugBundleWriter(path, header, max_bytes=baseline.stat().st_size + 1) as writer:
            writer.write("analysis_frame", {"details": "a" * 10_000})

    assert not path.exists()


def test_sanitization_ignores_non_string_mapping_keys() -> None:
    assert json.loads(canonical_json_bytes({1: "ignored", "frame_index": 1})) == {
        "frame_index": 1
    }


def test_serializers_preserve_only_source_coordinate_measurements() -> None:
    point = Point(100, 200)
    rect = Rect(10, 20, 30, 40)
    observation = RawFrameObservation(
        frame_index=7,
        timestamp_ms=233,
        detection=Detection(rect, 0.9),
        pose=PoseMeasurement(point, (point, Point(110, 220)), rect, 0.8),
    )
    tracked = TrackedMeasurement(
        frame_index=7,
        timestamp_ms=233,
        root=point,
        pose_bounds=rect,
        detector_bounds=rect,
        confidence=0.8,
        covariance=12.5,
        state=TrackingState.TRACKED,
    )
    frame = FrameMeasurement(point, rect, 0.8, Point(15, 5), detector_bounds=rect, covariance=12.5)

    assert serialize_point(point) == {"x": 100, "y": 200}
    assert serialize_rect(rect) == {"x": 10, "y": 20, "width": 30, "height": 40}
    assert serialize_crop_rect(CropRect(1, 2, 3, 4)) == {
        "x": 1,
        "y": 2,
        "width": 3,
        "height": 4,
    }
    assert serialize_raw_frame_observation(observation) == {
        "frame_index": 7,
        "timestamp_ms": 233,
        "detection": {"bounds": serialize_rect(rect), "confidence": 0.9},
        "pose": {
            "root": serialize_point(point),
            "landmarks": [serialize_point(point), {"x": 110, "y": 220}],
            "bounds": serialize_rect(rect),
            "confidence": 0.8,
        },
    }
    assert serialize_tracked_measurement(tracked)["state"] == "tracked"
    assert serialize_frame_measurement(frame)["velocity"] == {"x": 15, "y": 5}


def test_serializers_represent_missing_and_lost_measurements_with_nulls() -> None:
    observation = RawFrameObservation(7, 233, None, None)
    tracked = TrackedMeasurement(7, None, None, None, 0, None, TrackingState.LOST, 233)
    frame = FrameMeasurement(None, None, 0, lost=True)

    assert serialize_raw_frame_observation(observation)["detection"] is None
    assert serialize_raw_frame_observation(observation)["pose"] is None
    assert serialize_tracked_measurement(tracked)["root"] is None
    assert serialize_tracked_measurement(tracked)["covariance"] is None
    assert serialize_frame_measurement(frame)["lost"]


def test_digest_helpers_are_stable_and_do_not_accept_nonfinite_numbers() -> None:
    crops = [CropRect(1, 2, 3, 4), CropRect(5, 6, 7, 8)]

    assert deterministic_digest({"b": 2, "a": 1}) == deterministic_digest({"a": 1, "b": 2})
    assert crop_path_digest(crops) == crop_path_digest(crops)
    assert json.loads(canonical_json_bytes({"value": float("inf")})) == {"value": None}


def test_writer_rejects_bad_headers_and_closed_writes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="header"):
        DebugBundleWriter(tmp_path / "bad.jsonl.gz", {})

    writer = DebugBundleWriter(
        tmp_path / "closed.jsonl.gz",
        debug_bundle_header(
            job_id="job-1",
            source_metadata={},
            pipeline_version="pipeline-1",
            model_version="model-1",
            planner_config={},
            model_manifest={},
        ),
    )
    writer.close()
    with pytest.raises(ValueError, match="closed"):
        writer.write("stage_start", {})


@pytest.mark.parametrize("name", ["max_frames", "max_bytes"])
def test_writer_rejects_invalid_limits(tmp_path: Path, name: str) -> None:
    header = debug_bundle_header(
        job_id="job-1",
        source_metadata={},
        pipeline_version="pipeline-1",
        model_version="model-1",
        planner_config={},
        model_manifest={},
    )

    with pytest.raises(ValueError, match=name):
        DebugBundleWriter(tmp_path / "debug.jsonl.gz", header, **{name: 0})


def _records(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rt", encoding="ascii") as source:
        return [json.loads(line) for line in source]
