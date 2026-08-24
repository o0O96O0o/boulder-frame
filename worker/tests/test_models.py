import sys
from hashlib import sha256
from types import SimpleNamespace

import pytest

import boulder_frame_worker.models as models
from boulder_frame_worker.measurement import Rect
from boulder_frame_worker.models import (
    MediaPipePoseLandmarkerFull,
    ModelArtifact,
    ModelVerificationError,
)


def test_model_artifact_verifies_exact_size_and_checksum(tmp_path) -> None:
    data = b"approved model bytes"
    artifact = ModelArtifact("model.bin", sha256(data).hexdigest(), len(data))
    (tmp_path / artifact.file_name).write_bytes(data)

    assert artifact.verify(tmp_path) == tmp_path / artifact.file_name


@pytest.mark.parametrize("contents", [b"wrong", b""])
def test_model_artifact_rejects_unapproved_file(tmp_path, contents: bytes) -> None:
    artifact = ModelArtifact("model.bin", sha256(b"approved").hexdigest(), len(b"approved"))
    (tmp_path / artifact.file_name).write_bytes(contents)

    with pytest.raises(ModelVerificationError):
        artifact.verify(tmp_path)


def test_ssd_mobilenet_v1_12_uses_pinned_session_contract_and_parses_people(
    monkeypatch, tmp_path
) -> None:
    np = pytest.importorskip("numpy")
    model_path = tmp_path / "ssd_mobilenet_v1_12.onnx"
    model_path.write_bytes(b"approved model bytes")
    monkeypatch.setattr(
        models,
        "SSD_MOBILENET_V1_12",
        ModelArtifact(
            model_path.name,
            sha256(model_path.read_bytes()).hexdigest(),
            model_path.stat().st_size,
        ),
    )

    class Session:
        def __init__(self, path: str, providers: list[str]) -> None:
            assert path == str(model_path)
            assert providers == ["CPUExecutionProvider"]
            self.output_names: list[str] | None = None
            self.feeds: dict[str, object] | None = None

        def get_inputs(self):
            return [SimpleNamespace(name="inputs", type="tensor(uint8)")]

        def get_outputs(self):
            return [
                SimpleNamespace(name="detection_boxes"),
                SimpleNamespace(name="detection_classes"),
                SimpleNamespace(name="detection_scores"),
                SimpleNamespace(name="num_detections"),
            ]

        def run(self, output_names: list[str], feeds: dict[str, object]):
            self.output_names = output_names
            self.feeds = feeds
            return [
                np.array([[[0.1, 0.2, 0.8, 0.9], [0.0, 0.0, 1.0, 1.0]]]),
                np.array([[1.0, 17.0]]),
                np.array([[0.95, 0.99]]),
                np.array([2.0]),
            ]

    created_sessions: list[Session] = []

    def create_session(path: str, providers: list[str]) -> Session:
        session = Session(path, providers)
        created_sessions.append(session)
        return session

    monkeypatch.setitem(
        sys.modules, "onnxruntime", SimpleNamespace(InferenceSession=create_session)
    )
    detector = models.OnnxSsdMobileNetV1Detector(tmp_path)

    detections = detector.detect(np.array([[[1, 2, 3]]], dtype=np.uint8))

    session = created_sessions[0]
    assert session.output_names == [
        "detection_boxes",
        "detection_classes",
        "detection_scores",
        "num_detections",
    ]
    assert session.feeds is not None
    np.testing.assert_array_equal(
        session.feeds["inputs"], np.array([[[[3, 2, 1]]]], dtype=np.uint8)
    )
    assert len(detections) == 1
    detection = detections[0]
    assert detection.bounds == Rect(0.2, 0.1, 0.7, pytest.approx(0.7))
    assert detection.confidence == 0.95


def test_pose_landmarker_returns_none_when_mediapipe_finds_no_pose() -> None:
    np = pytest.importorskip("numpy")

    class Image:
        def __init__(self, *, image_format, data) -> None:
            self.image_format = image_format
            self.data = data

    class Landmarker:
        def detect(self, image):
            return type("Result", (), {"pose_landmarks": []})()

    adapter = object.__new__(MediaPipePoseLandmarkerFull)
    adapter._image_type = Image
    adapter._image_format = object()
    adapter._landmarker = Landmarker()

    assert adapter.estimate(np.zeros((10, 10, 3), dtype=np.uint8), Rect(0, 0, 10, 10)) is None


def test_pose_landmarker_rejects_non_empty_invalid_landmark_contract() -> None:
    np = pytest.importorskip("numpy")

    class Image:
        def __init__(self, *, image_format, data) -> None:
            self.image_format = image_format
            self.data = data

    class Landmarker:
        def detect(self, image):
            return type("Result", (), {"pose_landmarks": [[object()] * 32]})()

    adapter = object.__new__(MediaPipePoseLandmarkerFull)
    adapter._image_type = Image
    adapter._image_format = object()
    adapter._landmarker = Landmarker()

    with pytest.raises(ModelVerificationError, match="required 33 landmarks"):
        adapter.estimate(np.zeros((10, 10, 3), dtype=np.uint8), Rect(0, 0, 10, 10))


def test_pose_landmarker_closes_mediapipe_landmarker_once() -> None:
    class Landmarker:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    adapter = object.__new__(MediaPipePoseLandmarkerFull)
    landmarker = Landmarker()
    adapter._landmarker = landmarker

    adapter.close()
    adapter.close()

    assert landmarker.closed == 1
