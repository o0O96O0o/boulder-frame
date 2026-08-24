from pathlib import Path

import pytest

from boulder_frame_worker.config import WorkerConfig
from boulder_frame_worker.measurement import Detection, Rect
from boulder_frame_worker.models import MODEL_VERSION
from boulder_frame_worker.runtime import RuntimeUnavailable, compose_runtime
from boulder_frame_worker.state import InMemoryJobRepository
from boulder_frame_worker.storage import S3Storage


class StorageClient:
    def head_bucket(self, *, Bucket: str) -> None:
        assert Bucket == "boulder-frame"


class Transport:
    def ready(self) -> None:
        return None

    def serve(self, handler, stop, concurrency) -> None:
        return None

    def close(self) -> None:
        return None


class Detector:
    def detect(self, frame: object) -> list[Detection]:
        return [Detection(Rect(1, 1, 2, 2), 0.9)]


def config_values(tmp_path: Path) -> dict[str, object]:
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
        "scratch_root": str(tmp_path),
        "model_version": MODEL_VERSION,
    }


def test_runtime_composes_detector_only_pipeline(tmp_path, monkeypatch) -> None:
    import boulder_frame_worker.runtime as runtime

    captured: dict[str, object] = {}

    class Reader:
        pass

    class Pipeline:
        def __init__(self, *args, **kwargs) -> None:
            captured.update(kwargs)

        def validating(self, record, scratch) -> None:
            pass

        def analyzing(self, record, scratch) -> None:
            pass

        def rendering(self, record, scratch) -> None:
            pass

        def uploading(self, record, scratch) -> None:
            pass

    monkeypatch.setattr(runtime, "OnnxSsdMobileNetV1Detector", lambda path: Detector())
    monkeypatch.setattr(runtime, "OpenCVFrameReader", Reader)
    monkeypatch.setattr(runtime, "ProcessingPipeline", Pipeline)
    compose_runtime(
        WorkerConfig.from_mapping(config_values(tmp_path)),
        InMemoryJobRepository([]),
        Transport(),
        S3Storage(StorageClient(), "boulder-frame"),
    )

    assert isinstance(captured["detector"], Detector)
    assert isinstance(captured["frame_reader"], Reader)
    assert "pose_estimator" not in captured
    assert "tracker" not in captured


def test_runtime_rejects_old_model_version(tmp_path) -> None:
    with pytest.raises(RuntimeUnavailable, match="unsupported model_version"):
        compose_runtime(
            WorkerConfig.from_mapping({**config_values(tmp_path), "model_version": "w0.1-pose"}),
            InMemoryJobRepository([]),
            Transport(),
            S3Storage(StorageClient(), "boulder-frame"),
            detector=Detector(),
        )


def test_runtime_missing_detector_artifact_prevents_configured_startup(tmp_path) -> None:
    with pytest.raises(RuntimeUnavailable, match="configured model artifacts"):
        compose_runtime(
            WorkerConfig.from_mapping(
                {**config_values(tmp_path), "model_dir": str(tmp_path / "missing")}
            ),
            InMemoryJobRepository([]),
            Transport(),
            S3Storage(StorageClient(), "boulder-frame"),
        )
