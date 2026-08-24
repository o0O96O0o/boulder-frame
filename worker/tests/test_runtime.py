from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from boulder_frame_worker.config import WorkerConfig
from boulder_frame_worker.errors import ErrorCode
from boulder_frame_worker.measurement import Detection, Point, PoseEstimate, Rect
from boulder_frame_worker.media import MediaMetadata
from boulder_frame_worker.models import MODEL_VERSION
from boulder_frame_worker.pipeline import DecodedFrame
from boulder_frame_worker.protocol import JobTask
from boulder_frame_worker.runtime import RuntimeUnavailable, compose_runtime
from boulder_frame_worker.state import (
    InMemoryJobRepository,
    JobConfiguration,
    JobRecord,
    JobState,
    SourceAsset,
)
from boulder_frame_worker.storage import S3Storage
from boulder_frame_worker.tracking import SingleTargetTracker, TrackingState


class FakeStorageClient:
    def head_bucket(self, *, Bucket: str) -> None:
        assert Bucket == "boulder-frame"

    def download_file(self, Bucket: str, Key: str, Filename: str) -> None:
        assert (Bucket, Key) == ("boulder-frame", "private/source/input.mp4")
        Path(Filename).write_bytes(b"source")

    def upload_file(self, Filename: str, Bucket: str, Key: str, ExtraArgs: dict[str, str]) -> None:
        assert Path(Filename).read_bytes() == b"x" * 42
        assert (Bucket, Key, ExtraArgs) == (
            "boulder-frame",
            f"private/output/{project_id}/{job_id}.mp4",
            {"ContentType": "video/mp4"},
        )

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        return {"ContentLength": 42, "ContentType": "video/mp4"}


class FakeInspector:
    def inspect(self, path: Path) -> MediaMetadata:
        dimensions = (1920, 1080) if path.name == "output.mp4" else (160, 90)
        return MediaMetadata(
            width=dimensions[0],
            height=dimensions[1],
            duration_ms=1000,
            frame_rate=2,
            video_codec="h264",
            audio_codec=None,
            rotation=0,
            has_audio=False,
        )


class FakeRenderer:
    def render_crop_path(
        self, source, destination, crop_path, source_metadata, aspect_ratio, inspector
    ):
        assert len(crop_path) == 2
        destination.write_bytes(b"x" * 42)
        return MediaMetadata(1920, 1080, 1000, 2, "h264", None, 0, False)


class Pixels:
    def __getitem__(self, item: object) -> Pixels:
        return self


class FakeFrames:
    def read(self, source: Path, metadata: MediaMetadata) -> list[DecodedFrame]:
        return [DecodedFrame(0, 0, Pixels()), DecodedFrame(1, 500, Pixels())]


class FakeDetector:
    def detect(self, frame: object) -> list[Detection]:
        return [Detection(Rect(50, 10, 50, 70), 0.9)]


class FakePose:
    def __init__(self) -> None:
        self.closed = 0

    def estimate(self, roi_pixels: object, roi: Rect) -> PoseEstimate:
        return PoseEstimate(
            root=Point(0.5, 0.5),
            landmarks=(),
            bounds=Rect(0.2, 0.1, 0.6, 0.8),
            confidence=0.9,
        )

    def close(self) -> None:
        self.closed += 1


class FinalizingRepository(InMemoryJobRepository):
    def __init__(self, records: list[JobRecord]) -> None:
        super().__init__(records)
        self.finalizations = 0

    def finalize_output(self, record: JobRecord, output: object) -> None:
        assert record.state is JobState.UPLOADING
        self.finalizations += 1


def _runtime_values() -> dict[str, object]:
    return {
        "database_url": "postgresql://user:secret@db/app",
        "redis_url": "redis://:secret@redis/0",
        "s3_endpoint": "http://storage:9000",
        "s3_presign_endpoint": "http://storage:9000",
        "s3_region": "us-east-1",
        "s3_bucket": "boulder-frame",
        "s3_access_key": "key",
        "s3_secret_key": "secret",
        "worker_id": "worker-1",
    }


class FakeTransport:
    def ready(self) -> None:
        return None

    def serve(self, handler, stop, concurrency) -> None:
        assert concurrency == 1

    def close(self) -> None:
        return None


project_id = uuid4()
job_id = uuid4()


def _record(model_version: str = MODEL_VERSION) -> JobRecord:
    source_id = uuid4()
    return JobRecord(
        job_id,
        configuration=JobConfiguration(
            source_id,
            {"frame_time_ms": 0, "normalized_x": 0.5, "normalized_y": 0.5},
            {"aspect_ratio": "16:9", "profile": "balanced"},
            "test",
            model_version,
            {},
        ),
        source_asset=SourceAsset(
            source_id,
            project_id,
            "private/source/input.mp4",
            "uploaded",
            "input.mp4",
            "video/mp4",
            1,
            None,
            None,
            None,
            None,
        ),
    )


def test_runtime_composes_real_pipeline_and_finalizes_successfully(tmp_path) -> None:
    record = _record()
    repository = FinalizingRepository([record])
    config = WorkerConfig.from_mapping(
        {**_runtime_values(), "scratch_root": str(tmp_path), "model_version": MODEL_VERSION}
    )
    pose = FakePose()
    runtime = compose_runtime(
        config,
        repository,
        FakeTransport(),
        S3Storage(FakeStorageClient(), "boulder-frame"),
        frame_reader=FakeFrames(),
        detector=FakeDetector(),
        pose_estimator=pose,
        inspector=FakeInspector(),
        renderer=FakeRenderer(),
    )

    runtime.ready()
    assert runtime.consumer.processor(JobTask(job_id, "00000000-0000-0000-0000-000000000042"))
    assert repository.get(job_id).state is JobState.COMPLETED
    assert repository.finalizations == 1
    assert not (tmp_path / str(job_id)).exists()
    runtime.close()
    assert pose.closed == 1


def test_runtime_bypasses_private_storage_check_only_when_explicitly_configured(tmp_path) -> None:
    config = WorkerConfig.from_mapping(
        {
            **_runtime_values(),
            "scratch_root": str(tmp_path),
            "debug_capture": True,
            "debug_require_private_storage": False,
        }
    )
    runtime = compose_runtime(
        config,
        InMemoryJobRepository([]),
        FakeTransport(),
        S3Storage(FakeStorageClient(), "boulder-frame"),
    )

    runtime.ready()


def test_runtime_completes_job_when_pose_misses_transition_tracker_to_lost(tmp_path) -> None:
    class FiveFrameInspector:
        def inspect(self, path: Path) -> MediaMetadata:
            return MediaMetadata(
                width=1920,
                height=1080,
                duration_ms=1000,
                frame_rate=5,
                video_codec="h264",
                audio_codec=None,
                rotation=0,
                has_audio=False,
            )

    class IndexedPixels:
        def __init__(self, index: int) -> None:
            self.index = index

        def __getitem__(self, item: object) -> IndexedPixels:
            return self

    class FiveFrames:
        def read(self, source: Path, metadata: MediaMetadata) -> list[DecodedFrame]:
            return [DecodedFrame(index, index * 200, IndexedPixels(index)) for index in range(5)]

    class FiveFrameRenderer:
        def render_crop_path(
            self, source, destination, crop_path, source_metadata, aspect_ratio, inspector
        ):
            assert len(crop_path) == 5
            destination.write_bytes(b"x" * 42)
            return FiveFrameInspector().inspect(destination)

    class PoseWithMisses:
        def estimate(self, roi_pixels: object, roi: Rect) -> PoseEstimate | None:
            assert isinstance(roi_pixels, IndexedPixels)
            if roi_pixels.index > 0:
                return None
            return PoseEstimate(
                root=Point(0.5, 0.5),
                landmarks=(),
                bounds=Rect(0.2, 0.1, 0.6, 0.8),
                confidence=0.9,
            )

    class CapturingTracker:
        def __init__(self) -> None:
            self.states: list[TrackingState] = []

        def track(self, observations):
            tracked = SingleTargetTracker().track(observations)
            self.states = [measurement.state for measurement in tracked]
            return tracked

    record = _record()
    repository = FinalizingRepository([record])
    tracker = CapturingTracker()
    config = WorkerConfig.from_mapping(
        {**_runtime_values(), "scratch_root": str(tmp_path), "model_version": MODEL_VERSION}
    )
    runtime = compose_runtime(
        config,
        repository,
        FakeTransport(),
        S3Storage(FakeStorageClient(), "boulder-frame"),
        frame_reader=FiveFrames(),
        detector=FakeDetector(),
        pose_estimator=PoseWithMisses(),
        tracker=tracker,
        inspector=FiveFrameInspector(),
        renderer=FiveFrameRenderer(),
    )

    assert runtime.consumer.processor(JobTask(job_id, "00000000-0000-0000-0000-000000000042"))
    completed = repository.get(job_id)
    assert completed.state is JobState.COMPLETED, completed.error
    assert tracker.states[-1] is TrackingState.LOST


def test_runtime_default_model_adapters_fail_safely(tmp_path) -> None:
    record = _record("unconfigured")
    repository = FinalizingRepository([record])
    config = WorkerConfig.from_mapping({**_runtime_values(), "scratch_root": str(tmp_path)})
    runtime = compose_runtime(
        config,
        repository,
        FakeTransport(),
        S3Storage(FakeStorageClient(), "boulder-frame"),
        inspector=FakeInspector(),
        renderer=FakeRenderer(),
    )

    assert runtime.consumer.processor(JobTask(job_id, "00000000-0000-0000-0000-000000000042"))
    failed = repository.get(job_id)
    assert failed.state is JobState.FAILED
    assert failed.error is not None and failed.error.code is ErrorCode.MODEL_UNAVAILABLE


def test_runtime_missing_configured_baseline_models_prevents_startup(tmp_path) -> None:
    record = _record()
    repository = FinalizingRepository([record])
    config = WorkerConfig.from_mapping(
        {
            **_runtime_values(),
            "scratch_root": str(tmp_path),
            "model_dir": str(tmp_path / "missing-models"),
            "model_version": MODEL_VERSION,
        }
    )
    with pytest.raises(RuntimeUnavailable, match="configured model artifacts"):
        compose_runtime(
            config,
            repository,
            FakeTransport(),
            S3Storage(FakeStorageClient(), "boulder-frame"),
            inspector=FakeInspector(),
            renderer=FakeRenderer(),
        )


def test_runtime_requires_configured_runtime_identity() -> None:
    config = WorkerConfig.from_mapping(_runtime_values())
    assert config.stream_consumer == "worker-1"


def test_runtime_rejects_an_unknown_configured_model_version() -> None:
    with pytest.raises(RuntimeUnavailable, match="unsupported model_version"):
        compose_runtime(
            WorkerConfig.from_mapping({**_runtime_values(), "model_version": "unknown"}),
            FinalizingRepository([]),
            FakeTransport(),
            S3Storage(FakeStorageClient(), "boulder-frame"),
            frame_reader=FakeFrames(),
            detector=FakeDetector(),
            pose_estimator=FakePose(),
        )


def test_runtime_creates_default_frame_reader_only_with_loaded_baseline_models(
    tmp_path, monkeypatch
) -> None:
    import boulder_frame_worker.runtime as runtime

    captured: dict[str, object] = {}

    class Detector:
        def __init__(self, model_dir) -> None:
            assert model_dir == tmp_path

    class Pose:
        def __init__(self, model_dir) -> None:
            assert model_dir == tmp_path

    class Reader:
        pass

    class Pipeline:
        def __init__(self, *args, **kwargs) -> None:
            captured.update(kwargs)

        def validating(self, record, scratch) -> None:
            return None

        def analyzing(self, record, scratch) -> None:
            return None

        def rendering(self, record, scratch) -> None:
            return None

        def uploading(self, record, scratch) -> None:
            return None

    monkeypatch.setattr(runtime, "OnnxSsdMobileNetV1Detector", Detector)
    monkeypatch.setattr(runtime, "MediaPipePoseLandmarkerFull", Pose)
    monkeypatch.setattr(runtime, "OpenCVFrameReader", Reader)
    monkeypatch.setattr(runtime, "ProcessingPipeline", Pipeline)
    compose_runtime(
        WorkerConfig.from_mapping(
            {
                **_runtime_values(),
                "scratch_root": str(tmp_path),
                "model_dir": str(tmp_path),
                "model_version": MODEL_VERSION,
            }
        ),
        FinalizingRepository([]),
        FakeTransport(),
        S3Storage(FakeStorageClient(), "boulder-frame"),
    )

    assert isinstance(captured["frame_reader"], Reader)
    assert isinstance(captured["normalizer"], runtime.FFmpegCFRNormalizer)
    assert captured["normalizer"].timeout_seconds == 1800
