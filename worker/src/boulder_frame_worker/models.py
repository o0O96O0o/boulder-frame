from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .measurement import Detection, Rect

MODEL_VERSION = "w0.2-yolo26n-onnx-detector-only-1"


class ModelVerificationError(RuntimeError):
    """A locally provisioned model does not match the approved manifest."""


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    file_name: str
    sha256: str
    size_bytes: int

    def verify(self, model_dir: Path) -> Path:
        path = model_dir / self.file_name
        if not path.is_file():
            raise ModelVerificationError(f"required model file is missing: {path}")
        if path.stat().st_size != self.size_bytes:
            raise ModelVerificationError(f"model file has an unexpected size: {path}")
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != self.sha256:
            raise ModelVerificationError(f"model file checksum does not match the manifest: {path}")
        return path


YOLO26N = ModelArtifact(
    "yolo26n.onnx",
    "5337a01d635c068479e7e4ff41ebb8142a8e0152afc6d0cd9e60db3dba2d8597",
    9892215,
)


class OnnxYolo26Detector:
    """COCO-person adapter for the fixed FP32 YOLO26n end-to-end ONNX export."""

    def __init__(self, model_dir: Path, *, score_threshold: float = 0.2) -> None:
        if not 0 <= score_threshold <= 1:
            raise ValueError("score_threshold must be between zero and one")
        try:
            import onnxruntime as ort
        except ImportError as error:
            raise ModelVerificationError(
                "onnxruntime==1.22.0 is required for the person detector"
            ) from error
        model_path = YOLO26N.verify(model_dir)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        inputs = self._session.get_inputs()
        outputs = self._session.get_outputs()
        if (
            len(inputs) != 1
            or inputs[0].type != "tensor(float)"
            or inputs[0].shape != [1, 3, 640, 640]
            or len(outputs) != 1
            or outputs[0].type != "tensor(float)"
            or outputs[0].shape != [1, 300, 6]
        ):
            raise ModelVerificationError(
                "person detector input/output contract does not match the manifest"
            )
        self._input_name = inputs[0].name
        self._output_names = [output.name for output in outputs]
        self._score_threshold = score_threshold

    def detect(self, frame: object) -> list[Detection]:
        try:
            import numpy as np
        except ImportError as error:
            raise ModelVerificationError(
                "numpy==1.26.4 is required for the person detector"
            ) from error
        try:
            import cv2
        except ImportError as error:
            raise ModelVerificationError(
                "opencv-python-headless==4.10.0.84 is required for the person detector"
            ) from error
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("person detector requires an HWC three-channel frame")
        height, width = frame.shape[:2]
        if height <= 0 or width <= 0:
            raise ValueError("person detector requires non-empty frame dimensions")
        scale = min(640 / width, 640 / height)
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        left_pad = (640 - resized_width) // 2
        top_pad = (640 - resized_height) // 2
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
        # OpenCV frames are BGR; the export expects normalized RGB NCHW.
        image = np.full((1, 3, 640, 640), 114, dtype=np.float32)
        image[0, :, top_pad : top_pad + resized_height, left_pad : left_pad + resized_width] = (
            resized[:, :, ::-1].transpose(2, 0, 1)
        )
        image *= np.float32(1 / 255)
        (predictions,) = self._session.run(self._output_names, {self._input_name: image})
        if predictions.shape != (1, 300, 6):
            raise ModelVerificationError("person detector returned an unexpected output shape")
        rows = predictions[0]
        accepted = (
            np.isfinite(rows).all(axis=1)
            & (rows[:, 5] == 0)
            & (rows[:, 4] >= self._score_threshold)
            & (rows[:, 4] <= 1)
        )
        detections: list[Detection] = []
        # The end-to-end head already selects detections; do not apply external NMS.
        for left, top, right, bottom, score, _ in rows[accepted]:
            x = max(0.0, min((float(left) - left_pad) / scale, float(width)))
            y = max(0.0, min((float(top) - top_pad) / scale, float(height)))
            right = max(0.0, min((float(right) - left_pad) / scale, float(width)))
            bottom = max(0.0, min((float(bottom) - top_pad) / scale, float(height)))
            if right > x and bottom > y:
                detections.append(Detection(Rect(x, y, right - x, bottom - y), float(score)))
        return detections
