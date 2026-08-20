# SSD-MobilenetV1-12 Contract Fix

Date: 2026-08-20

## Evidence

Downloaded the exact `person_detector` source URL from
`worker/models/model-manifest.json` and verified:

- Size: `29,461,455` bytes.
- SHA-256: `b8fba5e404077d4048d27fcd1667e85e27e192eb9bf51e696c46a3acd7d21058`.
- ONNX graph input: `inputs`, `uint8`, NHWC `[batch, height, width, 3]`.
- ONNX graph outputs, in graph/session order: `detection_boxes`,
  `detection_classes`, `detection_scores`, `num_detections`.

The prior adapter expected TensorFlow-style `*:0` names and unpacked results as count, boxes,
scores, classes. That does not match the SHA-pinned ONNX artifact.

## Change

- `OnnxSsdMobileNetV1Detector` now validates the exact pinned input/output names and order.
- Inference explicitly requests those ordered outputs and unpacks them as boxes, classes, scores,
  count.
- The regression test uses a faithful ONNX session fake, verifies BGR-to-RGB input conversion,
  exact output request order, normalized box conversion, and that only COCO class `1` is emitted.
- Target association and reacquisition code were not modified.

## Verification

- `uv run --project worker pytest tests/test_models.py`: passed, 6 tests.
- `uv run --project worker ruff check src/boulder_frame_worker/models.py tests/test_models.py`:
  passed.
- `git diff --check`: passed.
- `uv run --project worker pytest`: 94 passed, 1 skipped, 1 failed. The failure is the existing
  pose-miss runtime scenario in `tests/test_runtime.py`; it is outside this detector-only change.
- `uv run --project worker ruff check src tests`: reports an existing E501 line-length violation in
  `tests/test_worker.py`; the changed detector and model test files pass their focused Ruff check.
