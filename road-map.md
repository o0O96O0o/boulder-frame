# Goal

Turn one wide, static-camera sports recording into a smooth 1080p close-up of one user-selected athlete.

## Worker (Model and Video Processing)

### Implemented

- Model worker baseline is set up.
- [Person detection](docs/specs/worker/measurements-and-planner.md): Associate the selected athlete across sampled YOLO26n CPU ONNX detections, always including the selected frame.
- [Smooth framing](docs/specs/worker/measurements-and-planner.md): Optimize pan offline across the full shot with `lookahead-v2`: prioritize required speed/acceleration excess, duration-weighted distance outside a 5%-of-seed-crop-radius deadzone, travel, velocity change, then exact seed composition. Preserve hard sampled-only containment; held targets may leave the crop, and zoom/hysteresis and miss widening remain causal. Invalid solver output fails safely without fallback.
- [Media processing](docs/specs/worker/runtime-and-pipeline.md): Validate supported sources, normalize VFR when needed, and render verified 1080p H.264 MP4 with retained optional AAC audio.
- [Worker recovery](docs/specs/backend/redis-streams-task-distribution.md): Handle duplicate and abandoned deliveries with PostgreSQL leases, heartbeats, retries, and idempotent output finalization.
- [Offline evaluation](docs/specs/worker/debug-telemetry-and-evaluation.md): Measure framing quality from sanitized telemetry and human-reviewed annotations.

## Frontend (React Native)

### Planned

- Build the React Native app for the existing offline workflow: video upload, athlete selection, output settings, job progress, and output download.
- Keep inference and rendering in the worker; native capture remains out of scope.

### Implemented Web Baseline

The current frontend is a Vite/React web app, not a React Native implementation. These workflows provide the reference for the RN app:

- [Video upload](docs/specs/frontend/workflow.md): Upload MP4/MOV directly to private object storage with progress and server-side completion checks.
- [Athlete selection](docs/specs/frontend/workflow.md): Choose a video frame, tap the athlete, and select landscape or portrait output with one of four framing profiles.
- [Job status and download](docs/specs/frontend/workflow.md): Follow processing progress and download completed output through expiring links.
- [Processing review](docs/specs/frontend/phase-evaluation.md): Inspect optional detection, framing, and render videos with warnings and downloadable telemetry.

## Backend (Go API)

### Implemented

- [Job workflow](docs/specs/backend/http-api.md): Submit immutable, configuration-deduplicated jobs, follow processing progress, and download completed output through expiring links.

### Planned

- [Production access](docs/specs/backend/http-api.md): Replace the fixed development owner with real authentication and tighten browser-origin policy before external access.
- [Reliable job dispatch](docs/specs/backend/persistence.md): Add a transactional outbox so Redis publication failures recover without a repeated submission.

## Deployment

### Implemented

- [Local deployment](docs/specs/deploy/compose-runtime.md): Run the web frontend, API, and worker in Docker Compose against external services with integrity-verified detector provisioning.
- [Versioned cutover](docs/specs/deploy/compose-runtime.md): Deploy backend and worker `w0.2.7` together after draining old jobs; immutable model versions and exact `lookahead-v2` planner validation isolate incompatible cached paths.

## Not Planned

- Real-time processing or native capture: Keep the MVP focused on offline uploaded recordings.
- Multi-athlete tracking or equipment/ball detection: Follow one user-selected person only.
- Landmark inference or athlete-position prediction: Keep reframing detector-only without interpolating or extrapolating athlete movement. Full-shot camera optimization uses future observed boxes as constraints, not a predicted athlete trajectory.
- Super-resolution or lens correction: Exclude image enhancement and optical correction from the MVP.
