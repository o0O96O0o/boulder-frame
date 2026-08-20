# Worker Measurements And Planner

## Coordinate System

All source measurements use decoded source pixels with origin at the top-left:

- `Point(x, y)` is a source pixel coordinate.
- `Rect(x, y, width, height)` is a source-pixel rectangle.
- Normalized browser selection is converted by `source_tap(x, y, width, height)`.
- Pose ROI normalized coordinates are mapped back by `roi_to_source`.

## Target Association

`select_target` first chooses detections containing the selected tap. If none contains the tap, it chooses the nearest detection center. An empty detection set is a terminal `no_selected_athlete` error. `expand_roi` adds bounded padding and clamps the ROI to source dimensions.

The model interfaces are protocols:

- `PersonDetector.detect(frame)` returns detection rectangles/confidence.
- `PoseEstimator.estimate(roi_pixels, roi)` returns root, landmarks, bounds, and confidence, or
  `None` when a valid inference finds no pose in the ROI.

The baseline adapters are `OnnxSsdMobileNetV1Detector` and `MediaPipePoseLandmarkerFull`; their versions, input/output contracts, checksums, and license evidence are pinned in [Model Manifest](models.md). They require locally provisioned artifacts that pass SHA-256 and size verification. The worker does not download or bundle weights.

## Raw Observations

`RawFrameObservation` is the model-independent contract for one selected target at one source
frame. It contains the source frame index/timestamp, the associated detector result, and an
optional pose. A valid MediaPipe empty landmark result produces an observation with its associated
detection and no pose; this drives the existing tracker through `reacquiring` and `lost` rather
than failing the job. Invalid model output and inference infrastructure failures remain errors.
`TargetFrameAnalyzer` requires injected `PersonDetector` and `PoseEstimator` adapters, expands the
selected detection ROI, and transforms pose output back to source pixels.
The repository intentionally does not include weights. The local `MODEL_VERSION=unset-until-pinned`
sentinel normalizes to `unconfigured` and retains the explicit unavailable adapters. The selected model
version loads only local artifacts matching the manifest; missing or invalid configured artifacts prevent
worker startup rather than falling back to unavailable adapters.

## Tracking Interface

`TrackedMeasurement` contains frame index/timestamp, root, pose bounds, detector bounds, confidence,
covariance, and `tracked`/`reacquiring`/`lost` state. `SingleTargetTracker` is a deterministic
single-target alpha-beta filter: it rejects large residuals, predicts only through a bounded short
gap, requires consecutive observations to reacquire, and emits no root after loss. It never
 associates a second target or uses appearance identity. A nearby athlete can therefore be selected
 during detector fallback or reacquisition; identity-preserving re-identification remains deferred.

## Crop Geometry

`CropRect` supports right/bottom bounds, center, and envelope containment. `full_frame_crop` creates the widest crop for the requested output aspect ratio. `clamp_crop` keeps a valid crop within source dimensions.

`DeterministicCropPlanner`:

- Uses measurement bounds plus profile padding.
- Adds uncertainty padding as confidence decreases.
- Adds velocity-based directional lead.
- Returns the widest valid crop for lost or absent measurements.
- Zooms out faster than it zooms in.
- Requires a stable high-confidence hold before zooming in.
- Uses a short forward/backward recorded-shot smoothing pass and a local movement envelope.
- Uses detector bounds when pose bounds are unavailable, uncertainty/covariance padding, a pan dead
  zone, and bounded pan changes.
- Widens immediately toward the full source-aspect frame for lost tracking and never uses predicted
  roots for a close crop after the lost state.

Profiles are ordered from tightest to widest: `tight`, `balanced`, `safe`, `full_movement`. The
deterministic controller remains the only MVP planner; a global optimizer and multi-athlete tracking
remain out of scope.
