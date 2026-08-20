# Fix Pose Miss Summary

## Objective

Fix review blocker 2: a normal MediaPipe Pose Landmarker result with no poses must not escape as
an unclassified exception and fail the job with `internal`.

## Implementation

- `MediaPipePoseLandmarkerFull.estimate` now returns `None` when MediaPipe returns an empty
  `pose_landmarks` collection.
- `PoseEstimator` explicitly permits `PoseEstimate | None`.
- `TargetFrameAnalyzer` converts `None` into a `RawFrameObservation` with the associated
  detection and no pose. This lets the existing `SingleTargetTracker` produce its established
  `reacquiring` and `lost` states.
- Non-empty MediaPipe output with any landmark count other than 33 remains a
  `ModelVerificationError`. Model-loading and inference infrastructure errors are unchanged and
  continue to fail processing.
- Target association and reacquisition identity behavior were not changed. Review blocker 3 is
  intentionally deferred.

## Coverage

- Adapter unit test: empty MediaPipe result returns `None`.
- Adapter unit test: non-empty malformed MediaPipe result raises `ModelVerificationError`.
- Analyzer unit test: a pose miss retains the selected detection and produces no pose/root.
- Pipeline test: one tracked result followed by four pose misses transitions through
  `tracked`, `reacquiring`, `reacquiring`, `reacquiring`, `lost` and completes crop planning.
- Worker/runtime test: the same sequence completes the full job through rendering and uploading;
  the captured tracker ends in `lost` instead of the job failing with `internal`.

## Validation

Passed:

```text
pytest tests/test_models.py::test_pose_landmarker_returns_none_when_mediapipe_finds_no_pose \
  tests/test_models.py::test_pose_landmarker_rejects_non_empty_invalid_landmark_contract \
  tests/test_measurement.py::test_analyzer_retains_detection_and_emits_no_pose_for_a_pose_miss \
  tests/test_pipeline.py::test_pipeline_routes_pose_misses_through_tracker_loss_without_failing \
  tests/test_runtime.py::test_runtime_completes_job_when_pose_misses_transition_tracker_to_lost \
  tests/test_tracking.py
# 8 passed

ruff check src/boulder_frame_worker/models.py src/boulder_frame_worker/measurement.py
# All checks passed

git diff --check
# passed
```

The repository-wide Ruff command still reports unrelated existing issues in `tests/test_media.py`
and `tests/test_worker.py`. `mypy` is not installed in the current environment.
