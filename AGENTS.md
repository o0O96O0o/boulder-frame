# Boulder Frame Agent Guide

## Project Goal

Build an offline sports-video reframing service that converts a wide, static-camera recording into a smooth 1080p close-up while keeping one user-selected athlete's full available movement in frame.

The product should feel like an anticipating camera operator, not a basic auto-centering crop. Prefer the tightest crop that safely contains the athlete's current and future-aware movement envelope.

## Authoritative Documents

- `docs/architecture/offline-reframing-mvp.md` is the implementation contract and contains the product rationale and algorithm decisions for the approved MVP.
- `docs/architecture/service-implementation-plan.md` defines the service-by-service implementation sequence, interfaces, dependencies, and verification gates.
- `docs/dev/development.md` defines local and self-hosted online Docker Compose development environments.
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
- The Go API owns validation, PostgreSQL metadata, signed object-store URLs, and Redis/`asynq` job dispatch.
- The Python worker owns MediaPipe/ONNX/OpenCV CV work, tracking, crop planning, and FFmpeg rendering.
- Store video assets in S3-compatible object storage, not PostgreSQL or local service filesystems.
- Keep immutable job configuration, pipeline version, model version, state, progress, and errors in PostgreSQL.
- Do not run CV inference, decoding, or long-running rendering in the Go API process.

## Framing Rules

- Pan follows a stable torso/root signal, not a raw person-box center.
- Zoom contains the movement envelope: reliable pose landmarks, detector fallback bounds, profile padding, directional lead room, and uncertainty.
- Use future information from recorded video through forward filtering and backward smoothing.
- Zoom out quickly for containment risk or low confidence; zoom in slowly only after stable, high-confidence movement.
- On lost tracking, widen toward the full source frame and attempt reacquisition. Never invent a close crop when the athlete is not reliable.
- Keep the first deterministic crop planner behind an interface so a future whole-shot optimizer can replace it without changing API or storage contracts.

## Engineering Expectations

- Prefer the smallest change that meets the documented MVP.
- Pin and verify model licenses before adding a detector or pose model dependency.
- Reject unsupported or variable-frame-rate input until timestamp handling is intentionally implemented and tested.
- Make durable worker operations idempotent and record user-safe terminal errors with structured internal error codes.
- Add automated tests for API/job transitions, tracking/planning behavior, output-media validation, and browser workflow where applicable.
- Maintain a permitted fixture/evaluation manifest; keep private videos out of version control.
- Before completing a feature, update relevant docs, validate internal links, and run available formatting, type, test, and `git diff --check` commands. If a command cannot run, state why.
