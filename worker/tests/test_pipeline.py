from pathlib import Path
from uuid import uuid4

import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError, transient
from boulder_frame_worker.measurement import Detection, Point, PoseEstimate, Rect
from boulder_frame_worker.media import MediaMetadata
from boulder_frame_worker.pipeline import DecodedFrame, ProcessingPipeline
from boulder_frame_worker.repository import OutputAsset
from boulder_frame_worker.state import JobConfiguration, JobRecord, JobState, SourceAsset
from boulder_frame_worker.storage import StoredObject
from boulder_frame_worker.tracking import SingleTargetTracker, TrackingState


class Storage:
    def __init__(self) -> None:
        self.uploaded = 0
        self.fail = False

    def download(self, key: str, destination: Path) -> None:
        destination.write_bytes(b"source")

    def upload(self, key: str, source: Path, content_type: str) -> StoredObject:
        if self.fail:
            raise transient(ErrorCode.STORAGE_UNAVAILABLE, "storage unavailable")
        self.uploaded += 1
        return StoredObject(key, source.stat().st_size, content_type)


class Finalizer:
    def __init__(self) -> None:
        self.outputs: list[OutputAsset] = []
        self.fail = False

    def finalize_output(self, record: JobRecord, output: OutputAsset) -> None:
        if self.fail:
            raise transient(ErrorCode.DATABASE_UNAVAILABLE, "database unavailable")
        self.outputs.append(output)


class Inspector:
    def inspect(self, path: Path) -> MediaMetadata:
        return MediaMetadata(1920, 1080, 1000, 30, "h264", "aac", 0, True)


class Renderer:
    def render_crop_path(
        self, source, destination, crop_path, source_metadata, aspect_ratio, inspector
    ):
        destination.write_bytes(b"x" * 4)
        return Inspector().inspect(destination)


def _record() -> JobRecord:
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
            source_id, uuid4(), "source", "uploaded", None, None, 1, None, None, None, None
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
