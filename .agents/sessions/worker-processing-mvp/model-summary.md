# W0.1 Model Summary

Date: 2026-08-20
Status: selected and license-verified; weights intentionally not bundled or downloaded.

## Decision

Use `w0.1-ssd-mobilenetv1-12-onnx-mediapipe-pose-full-1`:

- Person detector: ONNX Model Zoo SSD-MobilenetV1-12, COCO class 1 (`person`), ONNX 1.9.0,
  opset 12, MIT-licensed model artifact.
- Pose: Google MediaPipe Pose Landmarker Full float16 artifact version 1, using MediaPipe
  `0.10.32` Tasks Python runtime and the bundled BlazePose GHUM 3D model card.
- Runtime: `onnxruntime==1.22.0`, `mediapipe==0.10.32`, and `numpy==1.26.4` were added as exact
  dependency pins. Their authoritative package/source licenses are MIT, Apache-2.0, and
  BSD-3-Clause-compatible respectively.

The detector is the concrete ONNX baseline because it is available from the ONNX Model Zoo,
has a documented CPU inference contract, supports variable positive H/W input, and exposes the
COCO person class. MediaPipe Pose Landmarker Full is the requested pose implementation and has a
documented Python video/image API and 33 normalized landmarks.

## Artifact Evidence

The machine-readable manifest is [`worker/models/model-manifest.json`](../../../worker/models/model-manifest.json).
Model files are excluded from Git and runtime never downloads them.

| Artifact | Version/source | Size | SHA-256 | License/evidence |
| --- | --- | ---: | --- | --- |
| `ssd_mobilenet_v1_12.onnx` | ONNX Model Zoo commit [`4f43949841cb55a0b98dc8fcd045431ccafd9f96`](https://github.com/onnx/models/tree/4f43949841cb55a0b98dc8fcd045431ccafd9f96/validated/vision/object_detection_segmentation/ssd-mobilenetv1) | 29,461,455 | `b8fba5e404077d4048d27fcd1667e85e27e192eb9bf51e696c46a3acd7d21058` | [MIT model README](https://github.com/onnx/models/blob/4f43949841cb55a0b98dc8fcd045431ccafd9f96/validated/vision/object_detection_segmentation/ssd-mobilenetv1/README.md#license); [Apache-2.0 repository](https://github.com/onnx/models/blob/4f43949841cb55a0b98dc8fcd045431ccafd9f96/LICENSE) |
| `pose_landmarker_full.task` | Google artifact [version 1](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task) | 9,398,198 | `5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1` | [Apache-2.0 BlazePose GHUM 3D Model Card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf); [MediaPipe v0.10.32 Apache-2.0 source](https://github.com/google-ai-edge/mediapipe/blob/v0.10.32/LICENSE) |

Checksums were independently computed after download on 2026-08-20. The detector's Git LFS
pointer reports the same SHA-256 and byte size as the downloaded media artifact. The pose task
bundle contains `pose_detector.tflite` and `pose_landmarks_detector.tflite`; its archive checksum,
not an inferred inner-file checksum, is the installation gate.

## Contracts

### Detector

`OnnxSsdMobileNetV1Detector` accepts decoded OpenCV BGR HWC three-channel pixels, converts them to
contiguous RGB `uint8` NHWC `[1, height, width, 3]`, and calls the CPU execution provider. The
session must expose exactly one input named `image_tensor:0`, type `tensor(uint8)`, and outputs in
this order:

1. `num_detections:0`: count.
2. `detection_boxes:0`: normalized `[top, left, bottom, right]`.
3. `detection_scores:0`: scores in `[0, 1]`.
4. `detection_classes:0`: COCO numeric class IDs.

Only class ID 1 with score at least `0.20` is emitted as source-pixel `Detection` rectangles.

### Pose

`MediaPipePoseLandmarkerFull` verifies the `.task` archive, creates `PoseLandmarker` in image mode
with `num_poses=1`, and accepts an HWC three-channel ROI. It converts BGR to contiguous RGB and
returns the first result's exactly 33 normalized landmarks. The source-coordinate adapter uses
the midpoint of landmark indices 23 and 24 as the torso/root, all-landmark extrema as bounds, and
mean landmark visibility as confidence. `TargetFrameAnalyzer` maps those values from ROI-normalized
coordinates to source pixels.

### Configuration and loading

Set `MODEL_DIR` to a read-only directory containing exactly:

```text
ssd_mobilenet_v1_12.onnx
pose_landmarker_full.task
```

Set `MODEL_VERSION` to the manifest identifier only after provisioning. Runtime verifies name,
size, and SHA-256 before loading. Missing/unverified artifacts cause startup failure rather than
fallback or download. `MODEL_VERSION=unconfigured` retains the existing safe `model_unavailable`
adapter behavior. A decoded-frame reader is still a separate prerequisite; W0.1 does not claim
end-to-end rendering.

## Redistribution Constraints

- Preserve the ONNX model's MIT copyright, permission, and disclaimer notices.
- Preserve Apache-2.0 license, copyright, patent, attribution, and applicable NOTICE text for
  MediaPipe, BlazePose model material, and the ONNX Model Zoo source when redistributing them.
- Mark modified Apache source files and do not imply endorsement through upstream names/trademarks.
- Preserve BSD-3-Clause and bundled-wheel notices for NumPy and all notices of transitive runtime
  packages in a distributed image or installer.
- The service itself does not redistribute model bytes to end users; external redistribution must
  include the applicable license texts and notices.

## Verification Blockers

Network access was available for authoritative GitHub, Google Cloud Storage, PyPI, and Google
documentation endpoints. The Firecrawl client was unavailable (`fetch failed`), but it was not used
as the evidence source because direct authoritative endpoints succeeded. The current environment
does not have `mediapipe` or `onnxruntime` installed, so live inference and wheel installation
could not be executed here. The pinned package metadata, source licenses, platform wheel hashes,
model bytes, model licenses, checksums, and adapter contracts were verified; a clean worker image
build/install remains the next verification gate.

## Files Added/Changed

- `worker/models/model-manifest.json`: artifact/version/license/checksum manifest.
- `worker/src/boulder_frame_worker/models.py`: checksum gate and ONNX/MediaPipe protocol adapters.
- `worker/pyproject.toml`: exact runtime pins.
- `worker/conf/config*.json`, `.env.example`, `docker-compose.yml`: `MODEL_DIR` configuration and
  read-only model mount.
- `docs/specs/worker/models.md`: focused authoritative model and redistribution documentation.
- `docs/specs/worker/README.md`, `runtime-and-pipeline.md`, `measurements-and-planner.md`, and
  `docs/architecture/service-implementation-plan.md`: status and integration references.

## Checks Run

- `pytest tests/test_models.py tests/test_config.py tests/test_measurement.py`: passed, 20 tests.
- `ruff check` on new model/runtime/config files: passed after formatting correction.
- `python3 -m compileall` on new model/runtime/config files: passed.
- `jq empty worker/models/model-manifest.json`: passed.
- `docker compose config --quiet`: passed; default model mount resolves to `/models`.
- `git diff --check`: passed.
