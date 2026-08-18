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
- `PoseEstimator.estimate(roi_pixels, roi)` returns root, landmarks, bounds, and confidence.

The concrete ONNX detector and MediaPipe adapter are not yet installed or selected because model license/performance verification remains required.

## Tracking Interface

`TrackedMeasurement` contains frame index, root, pose bounds, detector bounds, confidence, covariance, and `tracked`/`reacquiring`/`lost` state. `TargetTracker` is the seam for the planned single-target Kalman filter. The current `UnavailableTargetTracker` fails explicitly instead of inventing tracking data.

## Crop Geometry

`CropRect` supports right/bottom bounds, center, and envelope containment. `full_frame_crop` creates the widest crop for the requested output aspect ratio. `clamp_crop` keeps a valid crop within source dimensions.

`DeterministicCropPlanner` currently:

- Uses measurement bounds plus profile padding.
- Adds uncertainty padding as confidence decreases.
- Adds velocity-based directional lead.
- Returns the widest valid crop for lost or absent measurements.
- Zooms out faster than it zooms in.
- Requires a stable high-confidence hold before zooming in.

Profiles are ordered from tightest to widest: `tight`, `balanced`, `safe`, `full_movement`. The planned pan dead zone, explicit pan-rate limit, forward/backward smoothing, and complete pose movement envelope remain future implementation work.
