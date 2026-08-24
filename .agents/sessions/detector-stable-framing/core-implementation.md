# Detector-Only Stable-Framing Core Implementation

## Summary

Implemented D1-D3 for the worker without changing durable job stages, VFR normalization, persisted crop paths, rendering, upload, or output validation.

- Replaced pose ROI/landmark observations with selected detector boxes and explicit later-frame misses.
- The tap selects the athlete on the selected frame. Other frames associate full-frame detections using the prior accepted detector-box center and the containing-reference, then nearest-center rule.
- Replaced alpha-beta tracking and future/envelope planning with a causal fixed-ratio crop controller.
- Profile target detector-height fractions are `tight=0.60`, `balanced=0.50`, `safe=0.40`, and `full_movement=0.33`.
- A detector miss widens the preceding crop toward the valid full crop without deriving a new target position.
- Removed MediaPipe, pose adapters, tracker composition, resource cleanup, `tracking.py`, and its tests.
- Updated debug/review telemetry to detector/framing/render data only, preserving optional association evidence from the existing uncommitted telemetry work.
- Published detector-only model version `w0.2-ssd-mobilenetv1-12-onnx-detector-only-1`; jobs configured for earlier model versions fail through the existing model-version mismatch path.

## Changed Files

- `worker/src/boulder_frame_worker/measurement.py`
- `worker/src/boulder_frame_worker/planner.py`
- `worker/src/boulder_frame_worker/pipeline.py`
- `worker/src/boulder_frame_worker/runtime.py`
- `worker/src/boulder_frame_worker/models.py`
- `worker/src/boulder_frame_worker/debug.py`
- `worker/src/boulder_frame_worker/review.py`
- `worker/src/boulder_frame_worker/cli.py`
- `worker/src/boulder_frame_worker/tracking.py` (removed)
- `worker/pyproject.toml`
- `worker/uv.lock`
- `worker/models/model-manifest.json`
- `worker/tests/test_measurement.py`
- `worker/tests/test_planner.py`
- `worker/tests/test_pipeline.py`
- `worker/tests/test_runtime.py`
- `worker/tests/test_models.py`
- `worker/tests/test_debug.py`
- `worker/tests/test_review.py`
- `worker/tests/test_tracking.py` (removed)

Pre-existing uncommitted documentation changes under `docs/specs/worker/` were preserved and not modified for this scoped D1-D3 implementation.

## Verification

- `uv lock`: passed.
- `uv run ruff check src tests --output-format concise`: passed.
- Focused worker tests: `28 passed`.
- Full worker tests: `183 passed, 1 skipped`.
- `git diff --check`: passed.
- `uv run mypy src`: unavailable because `mypy` is not installed in the locked environment.
- `uv run --with mypy mypy src`: ran but reported existing strict typing failures in unrelated worker adapters; the detector-core annotation issues it identified were corrected. The project has no clean strict-mypy baseline.
