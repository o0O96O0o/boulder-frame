import sys
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


@pytest.fixture
def yolo_detector(monkeypatch, tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    model_path = tmp_path / "yolo26n.onnx"
    model_path.write_bytes(b"approved model bytes")
    monkeypatch.setattr(
        models,
        "YOLO26N",
        ModelArtifact(
            model_path.name, sha256(model_path.read_bytes()).hexdigest(), model_path.stat().st_size
        ),
    )

    def build(rows, *, score_threshold=0.2):
        predictions = np.zeros((1, 300, 6), dtype=np.float32)
        predictions[0, : len(rows)] = rows

        class Session:
            def __init__(self, *args, **kwargs):
                pass

            def get_inputs(self):
                return [
                    SimpleNamespace(name="images", type="tensor(float)", shape=[1, 3, 640, 640])
                ]

            def get_outputs(self):
                return [SimpleNamespace(name="output0", type="tensor(float)", shape=[1, 300, 6])]

            def run(self, output_names, feeds):
                return [predictions]

        monkeypatch.setitem(
            sys.modules,
            "onnxruntime",
            SimpleNamespace(InferenceSession=Session, SessionOptions=SimpleNamespace),
        )
        return models.OnnxYolo26Detector(tmp_path, score_threshold=score_threshold)

    return build


@pytest.mark.parametrize(
    ("frame_shape", "box", "expected"),
    [
        ((720, 1280, 3), [100, 190, 400, 440], Rect(200, 100, 600, 500)),
        ((1280, 720, 3), [190, 100, 440, 400], Rect(100, 200, 500, 600)),
        # A rounded 321-pixel resize has 159 pixels above and 160 below.
        ((501, 1000, 3), [64, 191, 256, 319], Rect(100, 50, 300, 200)),
    ],
)
def test_yolo26_restores_letterboxed_boxes_to_source_pixels(
    yolo_detector, frame_shape, box, expected
) -> None:
    np = pytest.importorskip("numpy")
    detector = yolo_detector([[*box, 0.9, 0]])

    detections = detector.detect(np.zeros(frame_shape, dtype=np.uint8))

    assert len(detections) == 1
    bounds = detections[0].bounds
    assert (bounds.x, bounds.y, bounds.width, bounds.height) == pytest.approx(
        (expected.x, expected.y, expected.width, expected.height)
    )
    assert detections[0].confidence == pytest.approx(0.9)


def test_yolo26_filters_classes_and_scores_without_suppressing_overlapping_people(
    yolo_detector,
) -> None:
    np = pytest.importorskip("numpy")
    detector = yolo_detector(
        [
            [10, 20, 110, 220, 0.2, 0],
            [10, 20, 110, 220, 0.8, 0],
            [10, 20, 110, 220, 0.199, 0],
            [10, 20, 110, 220, 0.99, 1],
            [10, 20, 110, 220, 0.99, 0.5],
        ]
    )

    detections = detector.detect(np.zeros((640, 640, 3), dtype=np.uint8))

    assert [detection.bounds for detection in detections] == [Rect(10, 20, 100, 200)] * 2
    assert [detection.confidence for detection in detections] == pytest.approx([0.2, 0.8])


def test_yolo26_rejects_invalid_and_padding_boxes_and_clips_partial_boxes(
    yolo_detector,
) -> None:
    np = pytest.importorskip("numpy")
    detector = yolo_detector(
        [
            [100, 200, 90, 300, 0.9, 0],  # Reversed width.
            [100, 300, 200, 200, 0.9, 0],  # Reversed height.
            [100, 200, 100, 300, 0.9, 0],  # Empty width.
            [0, 0, 640, 100, 0.9, 0],  # Entirely above the image.
            [0, 500, 640, 640, 0.9, 0],  # Entirely below the image.
            [float("nan"), 200, 300, 400, 0.9, 0],
            [100, 200, float("inf"), 400, 0.9, 0],
            [100, 200, 300, 400, float("nan"), 0],
            [100, 200, 300, 400, float("inf"), 0],
            [100, 200, 300, 400, 1.1, 0],
            [100, 200, 300, 400, 0.9, float("nan")],
            [-20, 120, 100, 200, 0.8, 0],  # Crosses the left and top edges.
            [600, 480, 660, 520, 0.7, 0],  # Crosses the right and bottom edges.
        ],
        score_threshold=0,
    )

    detections = detector.detect(np.zeros((720, 1280, 3), dtype=np.uint8))

    # The remaining zero-filled output slots must not become detections even at threshold zero.
    assert [detection.bounds for detection in detections] == [
        Rect(0, 0, 200, 120),
        Rect(1200, 680, 80, 40),
    ]
    assert [detection.confidence for detection in detections] == pytest.approx([0.8, 0.7])


def test_model_artifact_rejects_unapproved_file(tmp_path) -> None:
    artifact = ModelArtifact("model.bin", sha256(b"approved").hexdigest(), len(b"approved"))
    (tmp_path / artifact.file_name).write_bytes(b"wrong")
    with pytest.raises(ModelVerificationError):
        artifact.verify(tmp_path)


def test_model_artifact_rejects_same_size_checksum_mismatch(tmp_path) -> None:
    artifact = ModelArtifact("model.bin", sha256(b"approved").hexdigest(), len(b"approved"))
    (tmp_path / artifact.file_name).write_bytes(b"tampered")
    with pytest.raises(ModelVerificationError):
        artifact.verify(tmp_path)
