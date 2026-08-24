from hashlib import sha256
from types import SimpleNamespace

import pytest

import boulder_frame_worker.models as models
from boulder_frame_worker.measurement import Rect
from boulder_frame_worker.models import ModelArtifact, ModelVerificationError


def test_model_artifact_verifies_exact_size_and_checksum(tmp_path) -> None:
    data = b"approved model bytes"
    artifact = ModelArtifact("model.bin", sha256(data).hexdigest(), len(data))
    (tmp_path / artifact.file_name).write_bytes(data)
    assert artifact.verify(tmp_path) == tmp_path / artifact.file_name


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
            model_path.name, sha256(model_path.read_bytes()).hexdigest(), model_path.stat().st_size
        ),
    )

    class Session:
        def __init__(self, path: str, providers: list[str]) -> None:
            assert path == str(model_path)
            assert providers == ["CPUExecutionProvider"]

        def get_inputs(self):
            return [SimpleNamespace(name="inputs", type="tensor(uint8)")]

        def get_outputs(self):
            return [
                SimpleNamespace(name=name)
                for name in (
                    "detection_boxes",
                    "detection_classes",
                    "detection_scores",
                    "num_detections",
                )
            ]

        def run(self, output_names, feeds):
            assert output_names[0] == "detection_boxes"
            np.testing.assert_array_equal(
                feeds["inputs"], np.array([[[[3, 2, 1]]]], dtype=np.uint8)
            )
            return [
                np.array([[[0.1, 0.2, 0.8, 0.9]]]),
                np.array([[1.0]]),
                np.array([[0.95]]),
                np.array([1.0]),
            ]

    monkeypatch.setitem(
        __import__("sys").modules, "onnxruntime", SimpleNamespace(InferenceSession=Session)
    )
    detections = models.OnnxSsdMobileNetV1Detector(tmp_path).detect(
        np.array([[[1, 2, 3]]], dtype=np.uint8)
    )
    assert detections[0].bounds == Rect(0.2, 0.1, 0.7, pytest.approx(0.7))


def test_model_artifact_rejects_unapproved_file(tmp_path) -> None:
    artifact = ModelArtifact("model.bin", sha256(b"approved").hexdigest(), len(b"approved"))
    (tmp_path / artifact.file_name).write_bytes(b"wrong")
    with pytest.raises(ModelVerificationError):
        artifact.verify(tmp_path)
