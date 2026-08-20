# W3 Evidence Summary

## Scope

Implemented raw source-frame observation contracts, injectable target analysis, a concrete single-target tracker, and deterministic recorded-video crop planning. No external detector or pose weights were selected or downloaded. Multi-athlete identity tracking and a global optimizer remain out of scope.

## Files Changed

- `worker/src/boulder_frame_worker/measurement.py`: added `PoseEstimate`, `RawFrameObservation`, source-coordinate pose transformation, frame cropping seam, and `TargetFrameAnalyzer`.
- `worker/src/boulder_frame_worker/tracking.py`: changed the tracker input seam to raw observations and added `SingleTargetTracker` with tracked/reacquiring/lost states, bounded gap prediction, outlier rejection, and monotonic timestamps.
- `worker/src/boulder_frame_worker/planner.py`: added detector fallback bounds, covariance padding, forward/backward smoothing, local movement envelopes, dead-zone/rate-limited panning, and conservative lost-track widening.
- `worker/tests/test_measurement.py`: added analyzer and source-coordinate transformation coverage.
- `worker/tests/test_tracking.py`: added movement, jump rejection, occlusion/loss/reacquisition, and timestamp tests.
- `docs/specs/worker/measurements-and-planner.md`: documented the W3 contracts and boundaries.
- `docs/specs/worker/README.md`: updated worker status.

## Verification

- `pytest tests/test_measurement.py tests/test_tracking.py tests/test_planner.py`: passed, 12 tests.
- `ruff check src/boulder_frame_worker/measurement.py src/boulder_frame_worker/tracking.py src/boulder_frame_worker/planner.py tests/test_measurement.py tests/test_tracking.py`: passed.
- `python3 -m compileall -q src tests/test_measurement.py tests/test_tracking.py`: passed.
- `git diff --check`: passed.
- Full `pytest`: 64 passed, 6 failed in pre-existing media/runtime tests unrelated to W3 (`test_media.py` crop fps assertion and FFmpeg fixture rendering, `test_runtime.py` storage config fixture). `mypy` was unavailable in the environment (`command not found`).

## Integration Notes

- Runtime composition still needs to inject concrete detector/pose adapters once model licenses and weights are verified.
- `TargetFrameAnalyzer` expects the decoded frame object to support source-pixel slicing, or a custom `FrameCropper` must be injected.
- Planner inputs must convert `TrackedMeasurement` values to `FrameMeasurement` values at the render orchestration boundary.
