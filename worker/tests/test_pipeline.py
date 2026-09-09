import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError, terminal
from boulder_frame_worker.frame_reader import DecodedFrame
from boulder_frame_worker.measurement import Detection, Rect
from boulder_frame_worker.media import MediaMetadata, TemporalFrameProgress
from boulder_frame_worker.pipeline import (
    ProcessingPipeline,
    _Inputs,
    _render_mapping_samples,
    _review_summary,
    _review_warning_intervals,
)
from boulder_frame_worker.planner import CropRect, PlannerError
from boulder_frame_worker.protocol import (
    AspectRatio,
    FramingProfile,
    OutputSettings,
    TargetSelection,
)
from boulder_frame_worker.state import JobConfiguration, JobRecord, JobState, SourceAsset
from boulder_frame_worker.storage import StoredObject


class Storage:
    def download(self, key: str, destination: Path) -> None:
        destination.write_bytes(b"source")

    def upload(self, key: str, source: Path, content_type: str) -> StoredObject:
        return StoredObject(key, source.stat().st_size, content_type)


class Finalizer:
    def finalize_output(self, record: JobRecord, output: object) -> None:
        return None

    def finalize_review(self, record, review_id, artifacts) -> None:
        return None


class Inspector:
    def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
        return MediaMetadata(1920, 1080, 1000, 2, "h264", None, 0, False)


class Renderer:
    def __init__(self) -> None:
        self.crops: list[CropRect] | None = None
        self.calls = 0
        self.validations = 0

    def render_crop_path(
        self,
        source,
        destination,
        crop_path,
        source_metadata,
        aspect_ratio,
        inspector,
        frame_reader,
    ):
        del source, source_metadata, aspect_ratio, inspector, frame_reader
        self.calls += 1
        self.crops = crop_path
        destination.write_bytes(b"output")
        return Inspector().inspect(destination)

    def validate_rendered_output(
        self, output, source_metadata, aspect_ratio, inspector
    ) -> MediaMetadata:
        del source_metadata, aspect_ratio, inspector
        self.validations += 1
        return Inspector().inspect(output)


PLANNER_SETTINGS = {
    "controller": "lookahead-v2",
    "seed_controller": "deterministic-v3",
    "optimizer": "scipy-highs-ds",
    "lookahead_scope": "full_shot",
    "containment_policy": "sampled_detections",
    "solver_feasibility_tolerance": 1e-8,
    "detection_sample_fps": 10,
    "scale_enter_fraction": 0.05,
    "scale_exit_fraction": 0.02,
    "center_enter_fraction": 0.01,
    "center_exit_fraction": 0.004,
    "zoom_max_speed": 0.5,
    "zoom_max_acceleration": 1.0,
    "pan_max_speed": 0.25,
    "pan_max_acceleration": 0.5,
    "pan_dead_zone_fraction": 0.05,
}


def record(frame_time_ms: int = 0, *, detection_sample_fps: int | float = 0) -> JobRecord:
    source_id = uuid4()
    return JobRecord(
        id=uuid4(),
        state=JobState.UPLOADING,
        configuration=JobConfiguration(
            source_id,
            {"frame_time_ms": frame_time_ms, "normalized_x": 0.5, "normalized_y": 0.5},
            {"aspect_ratio": "16:9", "profile": "balanced"},
            "w0.2.7",
            "model",
            {**PLANNER_SETTINGS, "detection_sample_fps": detection_sample_fps},
        ),
        source_asset=SourceAsset(
            source_id, uuid4(), "source", "uploaded", None, None, 1, None, None, None, None
        ),
    )


def sampling_pipeline(
    source_fps: Fraction,
    frame_count: int,
    *,
    sample_fps: int | float = 10,
    selected_time_ms: int = 0,
    boxes: dict[int, Rect | None] | None = None,
):
    duration = Fraction(frame_count, 1) / source_fps
    metadata = MediaMetadata(
        1920, 1080, round(duration * 1000), source_fps, "h264", None, 0, False, duration
    )
    calls: list[int] = []

    class SamplingInspector:
        def inspect(self, path, *, allow_variable_frame_rate=False):
            return metadata

    class Frames:
        def read(self, source, metadata):
            for index in range(frame_count):
                yield DecodedFrame(index, metadata.timestamp_for_frame(index), index)

    class Detector:
        def detect(self, index):
            calls.append(index)
            box = Rect(860, 340, 200, 400) if boxes is None else boxes[index]
            return [] if box is None else [Detection(box, 0.9)]

    return (
        ProcessingPipeline(
            Storage(),
            Finalizer(),
            inspector=SamplingInspector(),
            renderer=Renderer(),
            frame_reader=Frames(),
            detector=Detector(),
            debug_capture=True,
        ),
        record(selected_time_ms, detection_sample_fps=sample_fps),
        calls,
    )


@pytest.mark.parametrize(
    ("source_fps", "frame_count", "sample_fps", "selected_time_ms", "expected"),
    [
        (Fraction(30), 12, 10, 134, [0, 3, 4, 6, 9]),
        (Fraction(30), 8, 0, 0, list(range(8))),
        (Fraction(5), 6, 10, 0, list(range(6))),
        (Fraction(24000, 1001), 13, 10, 0, [0, 3, 5, 8, 10, 12]),
        (Fraction(30), 13, 12.5, 0, [0, 3, 5, 8, 10, 12]),
        (Fraction(1, 2), 6, 0.2, 0, [0, 3, 5]),
    ],
)
def test_sampling_detects_exact_grid_plus_selection_and_replays_all_cached_crops(
    tmp_path, source_fps, frame_count, sample_fps, selected_time_ms, expected
) -> None:
    pipeline, job, calls = sampling_pipeline(
        source_fps,
        frame_count,
        sample_fps=sample_fps,
        selected_time_ms=selected_time_ms,
    )
    pipeline.analyzing(job, tmp_path)
    crops = (tmp_path / "crop-path.jsonl").read_bytes()
    rows = [json.loads(line) for line in crops.splitlines()]
    assert calls == expected
    assert [row["frame_index"] for row in rows] == list(range(frame_count))
    assert [row["timestamp_ms"] for row in rows] == [
        round(Fraction(index * 1000, 1) / source_fps) for index in range(frame_count)
    ]
    pipeline.analyzing(job, tmp_path)
    assert calls == expected
    assert (tmp_path / "crop-path.jsonl").read_bytes() == crops


def test_report_distinguishes_sample_misses_from_held_gaps_and_survives_resume(tmp_path) -> None:
    pipeline, job, calls = sampling_pipeline(
        Fraction(30),
        18,
        boxes={
            0: Rect(860, 340, 200, 400),
            3: None,
            6: Rect(0, 0, 20, 40),
            9: Rect(860, 340, 200, 400),
            12: None,
            15: None,
        },
    )
    pipeline.debug_capture = False
    report = pipeline.analyzing(job, tmp_path)["report"]
    detection = report["detection"]
    assert detection["sampled_frames"] == 6
    assert detection["skipped_frames"] == 12
    assert detection["detected_frames"] == 2
    assert detection["missed_frames"] == 4
    assert detection["outcome_counts"]["no_detections"] == 3
    assert detection["outcome_counts"]["no_accepted_candidate"] == 1
    assert report["framing"]["unavailable_target_frames"] == 12
    assert report["framing"]["detection_gap_count"] == 2
    assert report["framing"]["longest_detection_gap_ms"] == 200
    assert not (tmp_path / "analysis-trace.jsonl").exists()
    assert pipeline.analyzing(job, tmp_path)["report"] == report
    assert pipeline.uploading(job, tmp_path)["report"]["detection"] == detection
    assert calls == [0, 3, 6, 9, 12, 15]


def test_report_measures_unavoidable_motion_excess_without_containment_snap(tmp_path) -> None:
    pipeline, job, _ = sampling_pipeline(
        Fraction(30),
        9,
        boxes={0: Rect(1400, 300, 200, 700), 3: None, 6: Rect(700, 300, 200, 700)},
    )
    job = replace(
        job,
        configuration=replace(
            job.configuration, output={"aspect_ratio": "9:16", "profile": "full_movement"}
        ),
    )
    framing = pipeline.analyzing(job, tmp_path)["report"]["framing"]
    rows = [
        json.loads(line) for line in (tmp_path / "analysis-trace.jsonl").read_text().splitlines()
    ]
    assert framing["containment_override_frames"] == 0
    assert framing["sampled_detection_constraint_frames"] == 2
    assert framing["sampled_detection_uncontained_frames"] == 0
    assert framing["max_center_step_source_px"] < 300
    assert rows[1]["framing"]["crop"]["x"] < rows[0]["framing"]["crop"]["x"]
    assert framing["max_height_step_fraction"] == 0
    assert framing["pan_speed_limit_excess_source_fraction_per_second"] > 0
    assert framing["pan_acceleration_limit_excess_source_fraction_per_second2"] > 0
    assert framing["pan_speed_limit_exceeded_frames"] > 0
    assert framing["pan_acceleration_limit_exceeded_frames"] > 0
    summary = _review_summary(rows, "framing")
    for key in (
        "sampled_detection_constraint_frames",
        "sampled_detection_uncontained_frames",
        "held_target_outside_crop_frames",
        "pan_speed_limit_exceeded_frames",
        "pan_acceleration_limit_exceeded_frames",
    ):
        assert summary[key] == framing[key]
    warnings = _review_warning_intervals(rows, "framing")
    assert any("speed" in warning["label"].lower() for warning in warnings)
    assert any("acceleration" in warning["label"].lower() for warning in warnings)


def test_skips_continue_camera_motion_but_sampled_miss_clears_hold_until_reacquisition(
    tmp_path,
) -> None:
    moved = Rect(960, 390, 200, 300)
    pipeline, job, calls = sampling_pipeline(
        Fraction(30),
        15,
        boxes={0: Rect(860, 340, 200, 400), 3: moved, 6: None, 9: None, 12: moved},
    )
    pipeline.analyzing(job, tmp_path)
    trace = [
        json.loads(line) for line in (tmp_path / "analysis-trace.jsonl").read_text().splitlines()
    ]
    assert calls == [0, 3, 6, 9, 12]
    for index in (4, 5):
        assert trace[index]["detection"]["selection_outcome"] == "detection_skipped"
        assert trace[index]["detection"]["detection"] is None
        assert "selection" not in trace[index]["detection"]
        assert (
            trace[index]["framing"]["input"]["detector_bounds"]
            == (trace[3]["framing"]["input"]["detector_bounds"])
        )
        assert not trace[index]["framing"]["input"]["detection_sampled"]
        previous = trace[index - 1]["framing"]["crop"]
        current = trace[index]["framing"]["crop"]
        assert current["height"] < previous["height"]
    for index in range(6, 12):
        assert trace[index]["framing"]["input"]["detection_sampled"] == (index in (6, 9))
        assert trace[index]["framing"]["input"]["detector_bounds"] is None
        assert trace[index]["framing"]["decision"]["detection_missed"]
        assert (
            trace[index]["framing"]["crop"]["height"]
            > trace[index - 1]["framing"]["crop"]["height"]
        )
    assert trace[9]["detection"]["selection"]["reference"] == {"x": 1060, "y": 540}
    assert trace[12]["detection"]["detection"] is not None
    assert not trace[12]["framing"]["decision"]["detection_missed"]
    assert (
        trace[13]["framing"]["input"]["detector_bounds"]
        == (trace[12]["framing"]["input"]["detector_bounds"])
    )
    assert [row["framing"]["input"]["detection_sampled"] for row in trace] == [
        index in (0, 3, 6, 9, 12) for index in range(15)
    ]
    assert [row["framing"]["decision"]["sampled_detection_constraint"] for row in trace] == [
        index in (0, 3, 12) for index in range(15)
    ]
    assert _review_summary(trace, "detection") == {
        "frames": 15,
        "sampled_frames": 5,
        "skipped_frames": 10,
        "detected_frames": 3,
        "missed_frames": 2,
    }
    warnings = _review_warning_intervals(trace, "detection")
    assert [(warning["start_ms"], warning["end_ms"]) for warning in warnings] == [
        (200, 233),
        (300, 333),
    ]


def test_off_grid_selected_sample_miss_is_terminal_even_with_neighbors_detected(tmp_path) -> None:
    target = Rect(860, 340, 200, 400)
    pipeline, job, calls = sampling_pipeline(
        Fraction(30),
        12,
        selected_time_ms=134,
        boxes={0: target, 3: target, 4: None, 6: target, 9: target},
    )
    with pytest.raises(WorkerError) as raised:
        pipeline.analyzing(job, tmp_path)
    assert raised.value.code is ErrorCode.NO_SELECTED_ATHLETE
    assert calls == [0, 3, 4, 6, 9]
    assert not (tmp_path / "crop-path.jsonl").exists()


def test_late_selection_never_holds_future_boxes_into_earlier_frames(tmp_path) -> None:
    pipeline, job, calls = sampling_pipeline(
        Fraction(30),
        12,
        selected_time_ms=267,
        boxes={
            0: None,
            3: None,
            6: Rect(700, 340, 200, 400),
            8: Rect(800, 340, 200, 400),
            9: Rect(820, 340, 200, 400),
        },
    )
    pipeline.analyzing(job, tmp_path)
    trace = [
        json.loads(line) for line in (tmp_path / "analysis-trace.jsonl").read_text().splitlines()
    ]
    assert calls == [0, 3, 6, 8, 9]
    assert all(row["framing"]["input"]["detector_bounds"] is None for row in trace[:6])
    assert all(
        row["framing"]["crop"] == {"x": 0, "y": 0, "width": 1920, "height": 1080}
        for row in trace[:6]
    )
    assert [row["framing"]["input"]["detector_bounds"]["x"] for row in trace[6:]] == [
        700,
        700,
        800,
        820,
        820,
        820,
    ]
    assert trace[3]["detection"]["selection"]["reference"] == {"x": 800, "y": 540}
    assert trace[0]["detection"]["selection"]["reference"] == {"x": 800, "y": 540}


def test_default_lookahead_moves_early_and_reports_stale_held_targets(tmp_path) -> None:
    first = Rect(1400, 300, 200, 700)
    later = Rect(700, 300, 200, 700)
    pipeline, job, _ = sampling_pipeline(
        Fraction(30),
        91,
        sample_fps=1,
        boxes={0: first, 30: first, 60: later, 90: later},
    )
    job = replace(
        job,
        configuration=replace(
            job.configuration, output={"aspect_ratio": "9:16", "profile": "full_movement"}
        ),
    )
    framing = pipeline.analyzing(job, tmp_path)["report"]["framing"]
    rows = [
        json.loads(line) for line in (tmp_path / "analysis-trace.jsonl").read_text().splitlines()
    ]
    crops = [row["framing"]["crop"] for row in rows]
    assert crops[59]["x"] < crops[30]["x"]
    for index, box in ((0, first), (30, first), (60, later), (90, later)):
        crop = crops[index]
        assert crop["x"] <= box.x + 1e-5
        assert crop["x"] + crop["width"] >= box.x + box.width - 1e-5
        assert crop["y"] <= box.y + 1e-5
        assert crop["y"] + crop["height"] >= box.y + box.height - 1e-5
    assert framing["planner_controller"] == "lookahead-v2"
    assert framing["optimizer"] == "scipy-highs-ds"
    assert framing["lookahead_scope"] == "full_shot"
    assert framing["containment_policy"] == "sampled_detections"
    assert framing["sampled_detection_constraint_frames"] == 4
    assert framing["sampled_detection_uncontained_frames"] == 0
    assert framing["held_target_outside_crop_frames"] > 0
    assert framing["pan_speed_limit_exceeded_frames"] == 0
    assert framing["pan_acceleration_limit_exceeded_frames"] == 0
    assert framing["pan_speed_limit_excess_source_fraction_per_second"] == 0
    assert framing["pan_acceleration_limit_excess_source_fraction_per_second2"] == 0
    assert framing["max_pan_axis_speed_source_fraction_per_second"] <= 0.25 + 1e-8 + 1e-12
    assert framing["max_pan_axis_acceleration_source_fraction_per_second2"] <= 0.5 + 1e-8 + 1e-12
    assert framing["max_center_step_source_px"] <= 1920 * 0.25 * 0.034 + 1e-5
    manifest_path = pipeline._write_review_manifest(
        tmp_path / "review",
        uuid4(),
        rows,
        {},
        "w0.2.7",
        "model",
        pipeline._inputs(job, tmp_path).metadata,
    )
    manifest = json.loads(manifest_path.read_text())
    phase = next(phase for phase in manifest["phases"] if phase["id"] == "framing")
    assert (
        phase["summary"]["held_target_outside_crop_frames"]
        == (framing["held_target_outside_crop_frames"])
    )
    assert any("Held target" in warning["label"] for warning in phase["warning_intervals"])
    assert all(
        row["framing"]["input"]["detection_sampled"] is False
        for row in rows
        if row["framing"]["decision"]["held_target_contained"] is False
    )


def test_report_counts_source_aspect_impossible_samples_not_held_targets(tmp_path) -> None:
    box = Rect(460, 190, 1000, 700)
    pipeline, job, _ = sampling_pipeline(Fraction(30), 6, boxes={0: box, 3: box})
    job = replace(
        job,
        configuration=replace(
            job.configuration, output={"aspect_ratio": "9:16", "profile": "full_movement"}
        ),
    )
    framing = pipeline.analyzing(job, tmp_path)["report"]["framing"]
    assert framing["sampled_detection_constraint_frames"] == 2
    assert framing["sampled_detection_uncontained_frames"] == 2
    assert framing["held_target_outside_crop_frames"] == 4
    assert framing["source_aspect_limited_frames"] == 6
    assert framing["containment_override_frames"] == 0


def test_planning_failure_is_terminal_without_analysis_artifacts(tmp_path, monkeypatch) -> None:
    pipeline, job, _ = sampling_pipeline(Fraction(30), 6)
    monkeypatch.setattr(
        "boulder_frame_worker.planner.linprog",
        lambda *args, **kwargs: SimpleNamespace(
            success=False, status=4, message="numerical optimizer failure"
        ),
    )
    with pytest.raises(WorkerError) as raised:
        pipeline.analyzing(job, tmp_path)
    assert raised.value.code is ErrorCode.INTERNAL
    assert not raised.value.transient
    assert isinstance(raised.value.__cause__, PlannerError)
    for name in ("crop-path.jsonl", "analysis-report.json", "analysis-trace.jsonl"):
        assert not (tmp_path / name).exists()
        assert not (tmp_path / name).with_suffix(".tmp").exists()


def test_review_keeps_overlapping_sampling_and_motion_warnings() -> None:
    def frame(timestamp, *, held=False, speed=False, acceleration=False):
        return {
            "timestamp_ms": timestamp,
            "framing": {
                "decision": {
                    "held_target_contained": False if held else None,
                    "pan_speed_limit_exceeded": speed,
                    "pan_acceleration_limit_exceeded": acceleration,
                }
            },
        }

    warnings = _review_warning_intervals(
        [
            frame(0, held=True, speed=True),
            frame(100, held=True, speed=True, acceleration=True),
            frame(200, acceleration=True),
            frame(300),
        ],
        "framing",
    )
    by_kind = {
        "held"
        if "Held target" in item["label"]
        else ("acceleration" if "acceleration" in item["label"] else "speed"): (
            item["start_ms"],
            item["end_ms"],
        )
        for item in warnings
    }
    assert by_kind == {"held": (0, 200), "speed": (0, 200), "acceleration": (100, 300)}


@pytest.mark.parametrize(
    "planner",
    [
        {},
        {**PLANNER_SETTINGS, "unexpected": 1},
        *[
            {key: value for key, value in PLANNER_SETTINGS.items() if key != missing}
            for missing in PLANNER_SETTINGS
        ],
        *[
            {**PLANNER_SETTINGS, key: invalid}
            for key, value in PLANNER_SETTINGS.items()
            for invalid in (
                (None, True, 123, "wrong")
                if isinstance(value, str)
                else (None, True, "10", float("nan"), float("inf"), 10**1000)
            )
        ],
        *[
            {**PLANNER_SETTINGS, key: value + 0.01}
            for key, value in PLANNER_SETTINGS.items()
            if not isinstance(value, str) and key != "detection_sample_fps"
        ],
        {**PLANNER_SETTINGS, "controller": "deterministic-v3"},
        {**PLANNER_SETTINGS, "controller": "lookahead-v1"},
        {
            **{
                key: value
                for key, value in PLANNER_SETTINGS.items()
                if key != "pan_dead_zone_fraction"
            },
            "controller": "lookahead-v1",
        },
        {**PLANNER_SETTINGS, "detection_sample_fps": -1},
        {**PLANNER_SETTINGS, "detection_sample_fps": 1001},
    ],
)
def test_invalid_planner_snapshot_is_rejected_before_cached_crop_replay(tmp_path, planner) -> None:
    pipeline, job, calls = sampling_pipeline(Fraction(30), 6)
    pipeline.analyzing(job, tmp_path)
    cached = (tmp_path / "crop-path.jsonl").read_bytes()
    invalid = replace(job, configuration=replace(job.configuration, planner=planner))
    with pytest.raises(WorkerError) as raised:
        pipeline.analyzing(invalid, tmp_path)
    assert raised.value.code is ErrorCode.INTERNAL
    assert calls == [0, 3]
    assert (tmp_path / "crop-path.jsonl").read_bytes() == cached


def test_validation_phase_reports_persisted_and_inspected_source_metadata(tmp_path) -> None:
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=Renderer(),
    )
    job = record()
    scratch = tmp_path / "job"
    scratch.mkdir()

    phase_io = pipeline.validating(job, scratch)

    assert phase_io["inputs"] == [
        {
            "kind": "video",
            "role": "source",
            "location": "object_storage",
            "asset_id": str(job.source_asset.id),
            "storage_key": "source",
            "upload_state": "uploaded",
            "content_type": None,
            "size_bytes": 1,
            "recorded_width": None,
            "recorded_height": None,
            "recorded_frame_rate": None,
            "recorded_duration_ms": None,
        }
    ]
    output = phase_io["outputs"][0]
    assert output["role"] == "source_original"
    assert output["size_bytes"] == len(b"source")
    assert output["media"] == {
        "coded_width": 1920,
        "coded_height": 1080,
        "display_width": 1920,
        "display_height": 1080,
        "duration_ms": 1000,
        "frame_rate": "2",
        "frame_rate_fps": 2.0,
        "expected_frame_count": 2,
        "video_codec": "h264",
        "audio_codec": None,
        "has_audio": False,
        "audio_stream_index": None,
        "rotation": 0,
    }


def test_detector_only_pipeline_persists_aligned_crops_and_widens_later_miss(tmp_path) -> None:
    class Pixels:
        def __init__(self, index: int) -> None:
            self.index = index

    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(index, index * 500, Pixels(index)) for index in range(2)]

    class Detector:
        def detect(self, pixels: Pixels) -> list[Detection]:
            return [Detection(Rect(700, 200, 200, 400), 0.9)] if pixels.index == 0 else []

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        debug_capture=True,
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    phase_io = pipeline.analyzing(record(), scratch)
    inputs = pipeline._inputs(record(), scratch)
    crops = pipeline._crop_path(inputs)
    stored = [json.loads(line) for line in (scratch / "crop-path.jsonl").read_text().splitlines()]
    trace = [
        json.loads(line) for line in (scratch / "analysis-trace.jsonl").read_text().splitlines()
    ]

    assert len(crops) == len(stored) == len(trace) == 2
    assert crops[1].height > crops[0].height
    assert trace[1]["detection"]["selection_outcome"] == "no_detections"
    assert trace[1]["framing"]["decision"]["detection_missed"]
    assert 0 <= crops[1].x < crops[1].right <= 1920
    assert 0 <= crops[1].y < crops[1].bottom <= 1080
    assert "pose" not in json.dumps(trace)
    assert "tracking" not in json.dumps(trace)
    assert [artifact["role"] for artifact in phase_io["outputs"]] == [
        "crop_path",
        "analysis_trace",
    ]


def test_detector_jitter_persists_identical_frame_aligned_crops(tmp_path) -> None:
    class JitterInspector(Inspector):
        def inspect(self, path, *, allow_variable_frame_rate=False):
            return MediaMetadata(1920, 1080, 1000, 4, "h264", None, 0, False)

    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(index, index * 250, index) for index in range(4)]

    class Detector:
        def detect(self, index):
            height = (400, 408, 392, 404)[index]
            center_x = (960, 963, 957, 961)[index]
            center_y = (540, 542, 538, 541)[index]
            return [Detection(Rect(center_x - 100, center_y - height / 2, 200, height), 0.9)]

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=JitterInspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        debug_capture=True,
    )
    job = record()
    pipeline.analyzing(job, tmp_path)
    stored = [json.loads(line) for line in (tmp_path / "crop-path.jsonl").read_text().splitlines()]
    trace = [
        json.loads(line) for line in (tmp_path / "analysis-trace.jsonl").read_text().splitlines()
    ]
    assert [(row["frame_index"], row["timestamp_ms"]) for row in stored] == [
        (0, 0),
        (1, 250),
        (2, 500),
        (3, 750),
    ]
    assert [(row["frame_index"], row["timestamp_ms"]) for row in trace] == [
        (0, 0),
        (1, 250),
        (2, 500),
        (3, 750),
    ]
    assert all(row["crop"] == stored[0]["crop"] for row in stored[1:])
    persisted = pipeline._crop_path(pipeline._inputs(job, tmp_path))
    assert len(persisted) == 4
    assert all(crop == persisted[0] for crop in persisted[1:])


def test_temporal_progress_compares_normalized_input_output_and_original_source(tmp_path) -> None:
    class TemporalRenderer(Renderer):
        def __init__(self) -> None:
            super().__init__()
            self.sources: list[Path] = []

        def temporal_frame_progress(
            self, source: Path, sample_size: tuple[int, int] = (192, 108)
        ) -> TemporalFrameProgress:
            del sample_size
            self.sources.append(source)
            return TemporalFrameProgress(30, ((4, 20),))

        def crop_path_temporal_progress(
            self,
            source: Path,
            crops: list[CropRect],
            metadata: MediaMetadata,
            aspect_ratio: AspectRatio,
            frame_reader,
        ) -> TemporalFrameProgress:
            del source, crops, metadata, aspect_ratio, frame_reader
            return TemporalFrameProgress(30, ((4, 20),))

    class Logger:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict[str, object]]] = []

        def info(self, message: str, *, extra: dict[str, object]) -> None:
            self.events.append((message, extra))

        def warning(self, message: str, *, extra: dict[str, object], exc_info: bool) -> None:
            raise AssertionError(message)

    renderer = TemporalRenderer()
    pipeline = ProcessingPipeline(Storage(), Finalizer(), inspector=Inspector(), renderer=renderer)
    logger = Logger()
    pipeline.logger = logger  # type: ignore[assignment]
    inputs = _Inputs(
        tmp_path / "source-cfr.mp4",
        tmp_path / "output.mp4",
        Inspector().inspect(tmp_path / "output.mp4"),
        TargetSelection(0, 0.5, 0.5),
        OutputSettings(AspectRatio.LANDSCAPE, FramingProfile.BALANCED),
        0,
    )
    (tmp_path / "crop-path.jsonl").write_text(
        """{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":0,"timestamp_ms":0}
{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":1,"timestamp_ms":500}
""",
        encoding="ascii",
    )

    pipeline._log_render_temporal_progress(record(), inputs)

    assert [source.name for source in renderer.sources] == [
        "source-cfr.mp4",
        "output.mp4",
        "source-original",
    ]
    assert [message for message, _ in logger.events] == [
        "render temporal progress",
        "planned crop temporal progress",
        "original source temporal progress",
    ]
    assert logger.events[0][1]["render_input_was_normalized"] is True
    assert logger.events[1][1]["planned_crop_near_static_frame_count"] == 17


def test_render_progress_is_skipped_without_debug_capture(tmp_path) -> None:
    class FailingRenderer(Renderer):
        def output_frame_progress(self, output: Path) -> object:
            del output
            raise AssertionError("debug diagnostics must be disabled")

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=FailingRenderer(),
        debug_capture=False,
    )
    inputs = _Inputs(
        tmp_path / "source-original",
        tmp_path / "output.mp4",
        Inspector().inspect(tmp_path / "output.mp4"),
        TargetSelection(0, 0.5, 0.5),
        OutputSettings(AspectRatio.LANDSCAPE, FramingProfile.BALANCED),
        0,
    )

    pipeline._log_render_progress(record(), inputs)


def test_render_reuses_crop_path_without_running_detector(tmp_path) -> None:
    class FailingFrames:
        def read(self, source, metadata):
            raise AssertionError("persisted crop path must be reused")

    renderer = Renderer()
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=renderer,
        frame_reader=FailingFrames(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "crop-path.jsonl").write_text(
        """{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":0,\"timestamp_ms\":0}
{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":1,\"timestamp_ms\":500}
""",
        encoding="ascii",
    )

    phase_io = pipeline.rendering(record(), scratch)
    assert renderer.crops == [CropRect(0, 0, 1920, 1080), CropRect(0, 0, 1920, 1080)]
    assert phase_io["inputs"][1]["role"] == "crop_path"
    assert phase_io["outputs"][0]["role"] == "rendered_output"


def test_upload_phase_reports_local_input_and_verified_storage_output(tmp_path) -> None:
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=Renderer(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "crop-path.jsonl").write_text(
        """{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":0,"timestamp_ms":0}
{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":1,"timestamp_ms":500}
""",
        encoding="ascii",
    )

    phase_io = pipeline.uploading(record(), scratch)

    assert phase_io["inputs"][0]["role"] == "rendered_output"
    stored = phase_io["outputs"][0]
    assert stored["role"] == "output"
    assert stored["location"] == "object_storage"
    assert stored["size_bytes"] == len(b"output")
    assert stored["content_type"] == "video/mp4"
    assert stored["media"]["display_width"] == 1920


def test_render_discards_output_when_crop_path_changes(tmp_path) -> None:
    class FailingFrames:
        def read(self, source, metadata):
            raise AssertionError("persisted crop path must be reused")

    renderer = Renderer()
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=renderer,
        frame_reader=FailingFrames(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    crop_path = scratch / "crop-path.jsonl"
    crop_path.write_text(
        """{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":0,\"timestamp_ms\":0}
{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":1,\"timestamp_ms\":500}
""",
        encoding="ascii",
    )

    pipeline.rendering(record(), scratch)
    pipeline.rendering(record(), scratch)
    assert renderer.calls == 1
    assert renderer.validations == 1
    cache_path = scratch / "render-cache.json"
    cache = json.loads(cache_path.read_text(encoding="ascii"))
    assert cache["renderer_version"] == "fixed-output-v1"
    del cache["renderer_version"]
    cache_path.write_text(json.dumps(cache), encoding="ascii")

    pipeline.rendering(record(), scratch)
    assert renderer.calls == 2

    crop_path.write_text(
        """{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":0,\"timestamp_ms\":0}
{\"crop\":{\"height\":1080,\"width\":1920,\"x\":1,\"y\":0},\"frame_index\":1,\"timestamp_ms\":500}
""",
        encoding="ascii",
    )

    pipeline.rendering(record(), scratch)

    assert renderer.calls == 3
    assert renderer.crops == [CropRect(0, 0, 1920, 1080), CropRect(1, 0, 1920, 1080)]


def test_cached_render_validation_failure_is_terminal_without_cache_rewrite(tmp_path) -> None:
    class RejectingRenderer(Renderer):
        def validate_rendered_output(
            self, output, source_metadata, aspect_ratio, inspector
        ) -> MediaMetadata:
            del output, source_metadata, aspect_ratio, inspector
            raise terminal(
                ErrorCode.INVALID_OUTPUT,
                "Rendered video frame count is invalid.",
                diagnostic="expected_frame_count=2 actual_frame_count=1",
            )

    renderer = RejectingRenderer()
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=renderer,
        frame_reader=object(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "crop-path.jsonl").write_text(
        """{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":0,"timestamp_ms":0}
{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":1,"timestamp_ms":500}
""",
        encoding="ascii",
    )
    pipeline.rendering(record(), scratch)
    cache_path = scratch / "render-cache.json"
    cache_before = cache_path.read_bytes()

    with pytest.raises(WorkerError) as raised:
        pipeline.rendering(record(), scratch)

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
    assert renderer.calls == 1
    assert cache_path.read_bytes() == cache_before


def test_render_mapping_samples_include_the_first_crop_change() -> None:
    crops = [
        CropRect(0, 0, 1920, 1080),
        CropRect(0, 0, 1920, 1080),
        CropRect(20, 0, 1900, 1068.75),
        CropRect(30, 0, 1890, 1063.125),
    ]

    assert _render_mapping_samples(crops) == (0, 2, 3)


def test_selected_frame_miss_remains_terminal(tmp_path) -> None:
    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(0, 0, object()), DecodedFrame(1, 500, object())]

    class Detector:
        def detect(self, pixels) -> list[Detection]:
            return []

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    with pytest.raises(WorkerError) as raised:
        pipeline._crop_path(pipeline._inputs(record(), scratch))
    assert raised.value.code is ErrorCode.NO_SELECTED_ATHLETE


def test_selected_frame_association_propagates_both_directions_without_identity_switch(
    tmp_path,
) -> None:
    class Pixels:
        def __init__(self, index: int) -> None:
            self.index = index

    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(index, index * 500, Pixels(index)) for index in range(3)]

    class ThreeFrameInspector(Inspector):
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            return MediaMetadata(1920, 1080, 1500, 2, "h264", None, 0, False)

    target = [Rect(680, 200, 100, 400), Rect(700, 200, 100, 400), Rect(720, 200, 100, 400)]
    competitor = Rect(1300, 200, 100, 400)

    class Detector:
        def detect(self, pixels: Pixels) -> list[Detection]:
            if pixels.index == 0:
                return [Detection(target[0], 0.9), Detection(competitor, 0.9)]
            if pixels.index == 1:
                return [Detection(competitor, 0.9), Detection(target[1], 0.9)]
            return [Detection(competitor, 0.9), Detection(target[2], 0.9)]

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=ThreeFrameInspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        debug_capture=True,
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    inputs = pipeline._inputs(record(frame_time_ms=500), scratch)
    pipeline._crop_path(inputs)
    trace = [
        json.loads(line) for line in (scratch / "analysis-trace.jsonl").read_text().splitlines()
    ]

    assert [entry["detection"]["detection"]["bounds"]["x"] for entry in trace] == [680, 700, 720]


def test_competing_person_after_loss_is_rejected_until_target_is_reacquired(tmp_path) -> None:
    class Pixels:
        def __init__(self, index: int) -> None:
            self.index = index

    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(index, index * 500, Pixels(index)) for index in range(3)]

    class ThreeFrameInspector(Inspector):
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            return MediaMetadata(1920, 1080, 1500, 2, "h264", None, 0, False)

    target = Rect(700, 200, 100, 400)

    class Detector:
        def detect(self, pixels: Pixels) -> list[Detection]:
            return {
                0: [Detection(Rect(1500, 200, 100, 400), 0.9)],
                1: [Detection(target, 0.9)],
                2: [Detection(Rect(740, 200, 100, 400), 0.9)],
            }[pixels.index]

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=ThreeFrameInspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        debug_capture=True,
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    pipeline._crop_path(pipeline._inputs(record(frame_time_ms=500), scratch))
    trace = [
        json.loads(line) for line in (scratch / "analysis-trace.jsonl").read_text().splitlines()
    ]

    assert trace[0]["detection"]["detection"] is None
    assert trace[0]["detection"]["selection_outcome"] == "no_accepted_candidate"
    assert trace[2]["detection"]["detection"]["bounds"]["x"] == 740


def test_vfr_normalization_stays_job_local_and_reusable(tmp_path) -> None:
    class VFRInspector:
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            if path.name == "source-original" and not allow_variable_frame_rate:
                raise terminal(
                    ErrorCode.VARIABLE_FRAME_RATE, "Variable-frame-rate video is not supported."
                )
            return MediaMetadata(1920, 1080, 1000, Fraction(30, 1), "h264", None, 0, False)

    class Normalizer:
        def __init__(self) -> None:
            self.calls = 0

        def normalize(self, source, destination, frame_rate, audio_stream_index) -> None:
            self.calls += 1
            destination.write_bytes(b"cfr")

    normalizer = Normalizer()
    pipeline = ProcessingPipeline(
        Storage(), Finalizer(), inspector=VFRInspector(), renderer=Renderer(), normalizer=normalizer
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    phase_io = pipeline.validating(record(), scratch)
    assert [artifact["role"] for artifact in phase_io["outputs"]] == [
        "source_original",
        "source_normalized",
    ]
    assert pipeline._inputs(record(), scratch).source.name == "source-cfr.mp4"
    assert normalizer.calls == 1
