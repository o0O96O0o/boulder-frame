# Debug Telemetry D1 Verification

Implemented only the D1 configuration/schema layer.

- Added default-off `WorkerConfig.debug_capture`, independently parsed and validated from `retain_debug_artifacts`.
- Added schema version `1`, a deterministic gzip JSON Lines writer, canonical SHA-256 digest helpers, generic record sanitization, and source-coordinate serializers for `Point`, `Rect`, `CropRect`, `RawFrameObservation`, `TrackedMeasurement`, and `FrameMeasurement`.
- Sanitization omits credential, URL, diagnostic, endpoint, pixel, binary, and media-payload fields. URL-bearing string values and nonfinite numeric values become `null`.
- Added focused tests for deterministic compression/output ordering, all pipeline stage record names, redaction, missing observations, lost tracking, serializers, and digest stability.

Verification:

- `cd worker && uv run pytest tests/test_debug.py tests/test_config.py` -> `22 passed`.
- A full `cd worker && uv run pytest` run passed before concurrent evaluation work appeared (`116 passed, 1 skipped`). A subsequent run failed only in concurrently added, uncommitted `tests/test_evaluation.py::test_metrics_include_detection_crop_tracking_recovery_and_normalized_motion` (`pan_jerk` was `None`); this D1 change does not touch evaluation code.
- `cd worker && uv run ruff check src/boulder_frame_worker/debug.py src/boulder_frame_worker/config.py tests/test_debug.py tests/test_config.py` -> passed.
- `git diff --check` -> passed.
- `cd worker && uv run mypy src/boulder_frame_worker/debug.py src/boulder_frame_worker/config.py` could not run because `mypy` is not installed in the worker environment.
