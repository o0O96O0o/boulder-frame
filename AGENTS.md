# Boulder Frame Agent Guide

## Project Goal

Build an offline sports-video reframing service that converts a wide, static-camera recording into a smooth 1080p close-up around one user-selected athlete.

The W0.2 product is a detector-only virtual camera: it holds the selected athlete's detected box at a fixed profile height and widens safely when detection is missed.

## Authoritative Documents

- [Roadmap](road-map.md) defines target status and scope boundaries. Before every task, read it to establish what is in scope and out of scope; do not pull in planned or excluded work unless the user explicitly requests it.
- `docs/architecture/offline-reframing-mvp.md` is the implementation contract and contains the product rationale and algorithm decisions for the approved MVP.
- `docs/architecture/service-implementation-plan.md` defines the service-by-service implementation sequence, interfaces, dependencies, and verification gates.
- `docs/dev/development.md` defines Docker Compose startup for repository modules and external dependency configuration.
- `docs/specs/README.md` indexes detailed root-to-submodule implementation specifications.
- `docs/README.md` indexes project documentation.

Update the focused documentation and its index whenever an implementation decision changes the documented architecture, API, persistence model, or processing behavior.

## MVP Boundary

- Offline processing only.
- One continuous, static-camera shot.
- One user-selected athlete.
- 4K source is recommended; render 1080p `16:9` or `9:16` H.264/AAC MP4.
- Profiles: `tight`, `balanced`, `safe`, and `full_movement`.
- Do not add real-time mode, multi-athlete tracking, equipment/ball detection, super-resolution, lens correction, or native capture unless the task explicitly expands scope.

## Architecture Rules

- The Vite/React/TypeScript web app handles upload UI, athlete selection, job status, and download only.
- The Go API owns validation, PostgreSQL metadata, signed object-store URLs, and Redis Streams job dispatch.
- The Python worker owns ONNX/OpenCV detection, detector-box crop planning, and FFmpeg rendering.
- Store video assets in S3-compatible object storage, not PostgreSQL or local service filesystems.
- Keep immutable job configuration, pipeline version, model version, state, progress, and errors in PostgreSQL.
- Do not run CV inference, decoding, or long-running rendering in the Go API process.

## Framing Rules

- Plan pan offline across the full normalized shot with `lookahead-v1` (`scipy-highs-ds`), using future accepted sampled boxes as crop constraints, never interpolating or predicting athlete positions.
- Keep `DeterministicCropPlanner` (`deterministic-v3`) as the causal seed: final width/height are unchanged, including profile targets (`tight` .60, `balanced` .50, `safe` .40, `full_movement` .33), 5%/2% scale hysteresis, timestamp-based zoom limits, and miss widening. Its 1%/0.4% center hysteresis supplies the objective reference, not final pan gates.
- Require strictly increasing non-negative integer timestamps. Optimize source-normalized pan per axis with speed `0.25`/second and acceleration `0.5`/second², including rest before/after the shot. If sampled containment conflicts with motion limits, minimize and report required speed then acceleration excess; never snap after optimization.
- Sample using immutable `planner.detection_sample_fps` (default 10 fps; 0 detects every frame), including the selected frame. Preserve `detection_sampled` provenance: only accepted fresh sampled boxes constrain containment. Skipped frames hold chronological camera guidance, not observed positions or hard bounds; held targets may leave the crop. Actual sampled misses clear the held target and cause causal widening.
- Preserve source/aspect bounds on every crop. Contain every geometrically feasible sampled box; record source/aspect-impossible containment explicitly. Validate the optimum and final geometry/kinematics; solver failure is terminal analyzing `internal` with no causal fallback or committed analysis artifacts.
- Keep `CropPlanner` API/storage contracts unchanged. Validate the exact immutable planner map before cached replay. Deploy backend/worker `w0.2.6` together after draining old jobs; never rewrite/retry old jobs or reuse old crop paths for the new detector.

## Engineering Expectations

- Prefer the smallest change that meets the documented MVP.
- Pin and verify model licenses before adding a detector dependency.
- Reject unsupported media. For supported VFR input, normalize once to a job-local CFR derivative
  before analysis and rendering; never alter the immutable source object. Bound normalization by its
  configured source-size cap and FFmpeg timeout; retain valid AAC without truncating video.
- Make durable worker operations idempotent and record user-safe terminal errors with structured internal error codes.
- Add automated tests for API/job transitions, detector-framing behavior, output-media validation, and browser workflow where applicable.
- Maintain a permitted fixture/evaluation manifest; keep private videos out of version control.
- Before completing a feature, update relevant docs, validate internal links, and run available formatting, type, test, and `git diff --check` commands. If a command cannot run, state why.

## Debug Conventions

- To debug, you can actively inspect logs from containers (you have access to the host), and with credentials configured for different environments to query data/storage directly.
