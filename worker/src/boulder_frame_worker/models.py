from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .measurement import Detection, Point, PoseEstimate, Rect

MODEL_VERSION = "w0.1-ssd-mobilenetv1-12-onnx-mediapipe-pose-full-1"


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


SSD_MOBILENET_V1_12 = ModelArtifact(
    "ssd_mobilenet_v1_12.onnx",
    "b8fba5e404077d4048d27fcd1667e85e27e192eb9bf51e696c46a3acd7d21058",
    29461455,
)
POSE_LANDMARKER_FULL = ModelArtifact(
    "pose_landmarker_full.task",
    "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1",
    9398198,
)


class OnnxSsdMobileNetV1Detector:
    """COCO-person adapter for the checked-in SSD-MobilenetV1-12 contract."""

    def __init__(self, model_dir: Path, *, score_threshold: float = 0.2) -> None:
        if not 0 <= score_threshold <= 1:
            raise ValueError("score_threshold must be between zero and one")
        try:
            import onnxruntime as ort
        except ImportError as error:
            raise ModelVerificationError(
                "onnxruntime==1.22.0 is required for the person detector"
            ) from error
        model_path = SSD_MOBILENET_V1_12.verify(model_dir)
        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        inputs = self._session.get_inputs()
        outputs = self._session.get_outputs()
        if (
            len(inputs) != 1
            or inputs[0].name != "inputs"
            or inputs[0].type != "tensor(uint8)"
            or [output.name for output in outputs]
            != [
                "detection_boxes",
                "detection_classes",
                "detection_scores",
                "num_detections",
            ]
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
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("person detector requires an HWC three-channel frame")
        height, width = frame.shape[:2]
        if height <= 0 or width <= 0:
            raise ValueError("person detector requires non-empty frame dimensions")
        # OpenCV decoding is BGR; the published SSD preprocessing requires RGB uint8 NHWC.
        image = np.ascontiguousarray(frame[:, :, ::-1][None, ...].astype(np.uint8, copy=False))
        boxes, classes, scores, count = self._session.run(
            self._output_names, {self._input_name: image}
        )
        detections: list[Detection] = []
        for index in range(int(count[0])):
            if int(classes[0][index]) != 1 or float(scores[0][index]) < self._score_threshold:
                continue
            top, left, bottom, right = (float(value) for value in boxes[0][index])
            x = max(0.0, min(left * width, float(width)))
            y = max(0.0, min(top * height, float(height)))
            right = max(x, min(right * width, float(width)))
            bottom = max(y, min(bottom * height, float(height)))
            if right > x and bottom > y:
                detections.append(
                    Detection(Rect(x, y, right - x, bottom - y), float(scores[0][index]))
                )
        return detections


class MediaPipePoseLandmarkerFull:
    """MediaPipe Pose Landmarker Full adapter using image-mode ROI inference."""

    def __init__(self, model_dir: Path) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
        except ImportError as error:
            raise ModelVerificationError(
                "mediapipe==0.10.18 is required for Pose Landmarker Full"
            ) from error
        model_path = POSE_LANDMARKER_FULL.verify(model_dir)
        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)), num_poses=1
        )
        self._image_type = mp.Image
        self._image_format = mp.ImageFormat.SRGB
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def estimate(self, roi_pixels: object, roi: Rect) -> PoseEstimate | None:
        del roi
        try:
            import numpy as np
        except ImportError as error:
            raise ModelVerificationError("numpy==1.26.4 is required for pose estimation") from error
        if (
            not isinstance(roi_pixels, np.ndarray)
            or roi_pixels.ndim != 3
            or roi_pixels.shape[2] != 3
        ):
            raise ValueError("pose estimator requires an HWC three-channel ROI")
        # SourceFrameCropper preserves OpenCV BGR pixels; MediaPipe SRGB requires RGB.
        image = self._image_type(
            image_format=self._image_format, data=np.ascontiguousarray(roi_pixels[:, :, ::-1])
        )
        result = self._landmarker.detect(image)
        if not result.pose_landmarks:
            return None
        pose_landmarks = result.pose_landmarks[0]
        if len(pose_landmarks) != 33:
            raise ModelVerificationError("pose landmarker did not return the required 33 landmarks")
        landmarks = tuple(_normalized_point(landmark) for landmark in pose_landmarks)
        root = Point(
            (landmarks[23].x + landmarks[24].x) / 2,
            (landmarks[23].y + landmarks[24].y) / 2,
        )
        xs = tuple(point.x for point in landmarks)
        ys = tuple(point.y for point in landmarks)
        left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
        confidence = sum(_visibility(landmark) for landmark in pose_landmarks) / len(landmarks)
        return PoseEstimate(
            root, landmarks, Rect(left, top, right - left, bottom - top), confidence
        )


def _normalized_point(landmark: Any) -> Point:
    return Point(min(1.0, max(0.0, float(landmark.x))), min(1.0, max(0.0, float(landmark.y))))


def _visibility(landmark: Any) -> float:
    return min(1.0, max(0.0, float(getattr(landmark, "visibility", 0.0))))
