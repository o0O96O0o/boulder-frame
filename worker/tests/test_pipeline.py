import gzip
import json
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

import pytest

from boulder_frame_worker.debug import append_debug_record
from boulder_frame_worker.errors import ErrorCode, WorkerError, terminal, transient
from boulder_frame_worker.measurement import (
    Detection,
    Point,
    PoseEstimate,
    RawFrameObservation,
    Rect,
)
from boulder_frame_worker.media import MediaMetadata
from boulder_frame_worker.pipeline import DecodedFrame, ProcessingPipeline
from boulder_frame_worker.planner import CropRect, FrameMeasurement
from boulder_frame_worker.repository import DebugAsset, OutputAsset
from boulder_frame_worker.state import JobConfiguration, JobRecord, JobState, SourceAsset
from boulder_frame_worker.storage import StoredObject
from boulder_frame_worker.tracking import SingleTargetTracker, TrackedMeasurement, TrackingState


class Storage:
    def __init__(self) -> None:
        self.uploaded = 0
        self.fail = False
        self.deleted: list[str] = []
        self.objects: dict[str, bytes] = {}

    def download(self, key: str, destination: Path) -> None:
        destination.write_bytes(b"source")

    def upload(self, key: str, source: Path, content_type: str) -> StoredObject:
        if self.fail:
            raise transient(ErrorCode.STORAGE_UNAVAILABLE, "storage unavailable")
        self.uploaded += 1
        self.objects[key] = source.read_bytes()
        return StoredObject(key, source.stat().st_size, content_type)

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


class Finalizer:
    def __init__(self) -> None:
        self.outputs: list[OutputAsset] = []
        self.debug: list[DebugAsset] = []
        self.fail = False
        self.debug_fail = False

    def finalize_output(self, record: JobRecord, output: OutputAsset) -> None:
        if self.fail:
            raise transient(ErrorCode.DATABASE_UNAVAILABLE, "database unavailable")
        self.outputs.append(output)

    def finalize_debug(self, record: JobRecord, storage_key: str, debug: DebugAsset) -> None:
        assert record.state is JobState.UPLOADING
        assert storage_key.startswith("private/debug/")
        if self.debug_fail:
            raise transient(ErrorCode.DATABASE_UNAVAILABLE, "database unavailable")
        self.debug.append(debug)


class Inspector:
    def inspect(self, path: Path) -> MediaMetadata:
        return MediaMetadata(1920, 1080, 1000, 30, "h264", "aac", 0, True)


class Renderer:
    def render_crop_path(
        self, source, destination, crop_path, source_metadata, aspect_ratio, inspector
    ):
        destination.write_bytes(b"x" * 4)
        return Inspector().inspect(destination)


class Normalizer:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[Path, Path, Fraction, int | None]] = []
        self.fail = fail

    def normalize(
        self, source: Path, destination: Path, frame_rate: Fraction, audio_stream_index: int | None
    ) -> None:
        self.calls.append((source, destination, frame_rate, audio_stream_index))
        if self.fail:
            raise terminal(ErrorCode.INVALID_MEDIA, "Video timing could not be normalized.")
        destination.write_bytes(b"cfr")


def _record(*, source_size_bytes: int = 1) -> JobRecord:
    source_id = uuid4()
    return JobRecord(
        uuid4(),
        state=JobState.UPLOADING,
        configuration=JobConfiguration(
            source_id,
            {"frame_time_ms": 0, "normalized_x": 0.5, "normalized_y": 0.5},
            {"aspect_ratio": "16:9", "profile": "balanced"},
            "pipeline",
            "model",
            {},
        ),
        source_asset=SourceAsset(
            source_id,
            uuid4(),
            "source",
            "uploaded",
            None,
            None,
            source_size_bytes,
            None,
            None,
            None,
            None,
        ),
    )


def test_upload_reuses_valid_render_and_finalizes_verified_output(tmp_path) -> None:
    storage = Storage()
    finalizer = Finalizer()
    pipeline = ProcessingPipeline(storage, finalizer, inspector=Inspector(), renderer=Renderer())
    record = _record()
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "source").write_bytes(b"source")
    (scratch / "output.mp4").write_bytes(b"x" * 4)

    pipeline.uploading(record, scratch)

    assert storage.uploaded == 1
    assert len(finalizer.outputs) == 1
    assert finalizer.outputs[0].size_bytes == 4


def test_upload_storage_failure_is_transient_and_skips_finalization(tmp_path) -> None:
    storage = Storage()
    storage.fail = True
    finalizer = Finalizer()
    pipeline = ProcessingPipeline(storage, finalizer, inspector=Inspector(), renderer=Renderer())
    record = _record()
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "source").write_bytes(b"source")
    (scratch / "output.mp4").write_bytes(b"x" * 4)

    with pytest.raises(WorkerError) as raised:
        pipeline.uploading(record, scratch)

    assert raised.value.transient
    assert finalizer.outputs == []


def test_upload_database_finalization_failure_is_transient(tmp_path) -> None:
    storage = Storage()
    finalizer = Finalizer()
    finalizer.fail = True
    pipeline = ProcessingPipeline(storage, finalizer, inspector=Inspector(), renderer=Renderer())
    record = _record()
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "source").write_bytes(b"source")
    (scratch / "output.mp4").write_bytes(b"x" * 4)

    with pytest.raises(WorkerError) as raised:
        pipeline.uploading(record, scratch)

    assert raised.value.code is ErrorCode.DATABASE_UNAVAILABLE
    assert raised.value.transient
    assert storage.uploaded == 1
    assert finalizer.outputs == []


def test_pipeline_uses_original_source_without_normalization_for_cfr_media(tmp_path) -> None:
    normalizer = Normalizer()
    pipeline = ProcessingPipeline(
        Storage(), Finalizer(), inspector=Inspector(), renderer=Renderer(), normalizer=normalizer
    )
    scratch = tmp_path / "job"
    scratch.mkdir()

    inputs = pipeline._inputs(_record(), scratch)

    assert inputs.source == scratch / "source-original"
    assert inputs.source.read_bytes() == b"source"
    assert normalizer.calls == []


def test_pipeline_normalizes_vfr_media_once_and_uses_derivative_downstream(tmp_path) -> None:
    class VFRInspector:
        def __init__(self) -> None:
            self.calls: list[tuple[Path, bool]] = []

        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            self.calls.append((path, allow_variable_frame_rate))
            if path.name == "source-original" and not allow_variable_frame_rate:
                raise terminal(
                    ErrorCode.VARIABLE_FRAME_RATE, "Variable-frame-rate video is not supported."
                )
            return MediaMetadata(
                1920, 1080, 1000, Fraction(30000, 1001), "h264", "aac", 0, True, None, 4
            )

    inspector = VFRInspector()
    normalizer = Normalizer()
    pipeline = ProcessingPipeline(
        Storage(), Finalizer(), inspector=inspector, renderer=Renderer(), normalizer=normalizer
    )
    scratch = tmp_path / "job"
    scratch.mkdir()

    inputs = pipeline._inputs(_record(), scratch)
    repeated_inputs = pipeline._inputs(_record(), scratch)

    assert inputs.source == scratch / "source-cfr.mp4"
    assert repeated_inputs.source == scratch / "source-cfr.mp4"
    assert normalizer.calls == [
        (scratch / "source-original", scratch / "source-cfr.mp4", Fraction(30000, 1001), 4)
    ]
    assert inspector.calls == [
        (scratch / "source-original", False),
        (scratch / "source-original", True),
        (scratch / "source-cfr.mp4", False),
        (scratch / "source-original", False),
        (scratch / "source-original", True),
        (scratch / "source-cfr.mp4", False),
    ]


def test_pipeline_stops_when_vfr_normalization_fails(tmp_path) -> None:
    class VFRInspector:
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            if not allow_variable_frame_rate:
                raise terminal(
                    ErrorCode.VARIABLE_FRAME_RATE, "Variable-frame-rate video is not supported."
                )
            return MediaMetadata(1920, 1080, 1000, Fraction(30, 1), "h264", None, 0, False)

    normalizer = Normalizer(fail=True)
    pipeline = ProcessingPipeline(
        Storage(), Finalizer(), inspector=VFRInspector(), renderer=Renderer(), normalizer=normalizer
    )
    scratch = tmp_path / "job"
    scratch.mkdir()

    with pytest.raises(WorkerError, match="Video timing could not be normalized"):
        pipeline._inputs(_record(), scratch)

    assert len(normalizer.calls) == 1
    assert not (scratch / "source-cfr.mp4").exists()


def test_pipeline_rejects_vfr_source_larger_than_normalization_limit(tmp_path) -> None:
    class VFRInspector:
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            if not allow_variable_frame_rate:
                raise terminal(
                    ErrorCode.VARIABLE_FRAME_RATE, "Variable-frame-rate video is not supported."
                )
            return MediaMetadata(1920, 1080, 1000, Fraction(30, 1), "h264", None, 0, False)

    normalizer = Normalizer()
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=VFRInspector(),
        renderer=Renderer(),
        normalizer=normalizer,
        normalization_max_source_bytes=100,
    )
    scratch = tmp_path / "job"
    scratch.mkdir()

    with pytest.raises(WorkerError) as raised:
        pipeline._inputs(_record(source_size_bytes=101), scratch)

    assert raised.value.code is ErrorCode.INVALID_MEDIA
    assert raised.value.message == "This variable-frame-rate video is too large to normalize."
    assert normalizer.calls == []


def test_pipeline_routes_pose_misses_through_tracker_loss_without_failing(tmp_path) -> None:
    class FiveFrameInspector:
        def inspect(self, path: Path) -> MediaMetadata:
            return MediaMetadata(1920, 1080, 1000, 5, "h264", "aac", 0, True)

    class Frames:
        def read(self, source: Path, metadata: MediaMetadata):
            return [DecodedFrame(index, index * 200, Pixels()) for index in range(5)]

    class Pixels:
        def __getitem__(self, item: object):
            return self

    class Detector:
        def detect(self, frame: object) -> list[Detection]:
            return [Detection(Rect(50, 10, 50, 70), 0.9)]

    class Pose:
        def __init__(self) -> None:
            self.calls = 0

        def estimate(self, roi_pixels: object, roi: Rect) -> PoseEstimate | None:
            self.calls += 1
            if self.calls > 1:
                return None
            return PoseEstimate(Point(0.5, 0.5), (), Rect(0.2, 0.1, 0.6, 0.8), 0.9)

    class CapturingTracker:
        def __init__(self) -> None:
            self.states: list[TrackingState] = []

        def track(self, observations):
            tracked = SingleTargetTracker().track(observations)
            self.states = [measurement.state for measurement in tracked]
            return tracked

    tracker = CapturingTracker()
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=FiveFrameInspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        pose_estimator=Pose(),
        tracker=tracker,
    )
    record = _record()
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "source").write_bytes(b"source")

    assert len(pipeline._crop_path(pipeline._inputs(record, scratch))) == 5
    assert tracker.states == [
        TrackingState.TRACKED,
        TrackingState.REACQUIRING,
        TrackingState.REACQUIRING,
        TrackingState.REACQUIRING,
        TrackingState.LOST,
    ]


def test_pipeline_publishes_sanitized_debug_bundle_with_phase_and_frame_records(tmp_path) -> None:
    storage = Storage()
    finalizer = Finalizer()
    pipeline = ProcessingPipeline(
        storage,
        finalizer,
        inspector=Inspector(),
        renderer=Renderer(),
        debug_capture=True,
    )
    record = _record()
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "source").write_bytes(b"source")
    observation = RawFrameObservation(0, 0, Detection(Rect(10, 20, 30, 40), 0.9), None)
    tracked = TrackedMeasurement(
        0, Point(25, 40), None, Rect(10, 20, 30, 40), 0.9, 1.0, TrackingState.TRACKED, 0
    )
    pipeline._write_analysis_trace(
        scratch / "debug-analysis.jsonl",
        [observation],
        [tracked],
        [FrameMeasurement(Point(25, 40), None, 0.9)],
        [CropRect(0, 0, 100, 100)],
    )
    append_debug_record(
        scratch / "debug-stages.jsonl",
        "stage_end",
        {"stage": "analyzing", "duration_ms": 4, "outcome": "completed"},
    )

    pipeline.publish_debug(record, scratch)

    key = next(key for key in storage.objects if key.startswith("private/debug/"))
    records = [
        json.loads(line)
        for line in gzip.decompress(storage.objects[key]).decode("ascii").splitlines()
    ]
    assert finalizer.debug and finalizer.debug[0].content_type == "application/gzip"
    assert records[0]["record_type"] == "header"
    assert records[0]["source_metadata"]["source_id"] == str(record.source_asset.id)  # type: ignore[union-attr]
    assert [item["record_type"] for item in records[1:]] == [
        "stage_end",
        "frame",
        "render_summary",
    ]
    assert records[2]["measurement"]["detection"]["bounds"] == {
        "height": 40,
        "width": 30,
        "x": 10,
        "y": 20,
    }
    assert records[3]["output"] == {"width": 1920, "height": 1080}


def test_pipeline_deletes_unlinked_debug_object_after_finalization_failure(tmp_path) -> None:
    storage = Storage()
    finalizer = Finalizer()
    finalizer.debug_fail = True
    pipeline = ProcessingPipeline(
        storage,
        finalizer,
        inspector=Inspector(),
        renderer=Renderer(),
        debug_capture=True,
    )
    record = _record()
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "source").write_bytes(b"source")

    with pytest.raises(WorkerError):
        pipeline.publish_debug(record, scratch)

    assert len(storage.deleted) == 1
    assert storage.objects == {}
