# Documentation

## Architecture

- [Offline Reframing MVP](architecture/offline-reframing-mvp.md): pan-only full-shot look-ahead, sampled-only containment, causal zoom, safe solver failure, and immutable service contracts.
- [Service Implementation Plan](architecture/service-implementation-plan.md): service-by-service implementation tasks, dependencies, interfaces, and verification gates.
- [Worker Debug Telemetry and Evaluation](specs/worker/debug-telemetry-and-evaluation.md): sampled/held provenance, look-ahead kinematics and excess warnings, redaction, evaluation inputs, and visual phase review.
- [Phase Evaluation Review](specs/frontend/phase-evaluation.md): private, terminal-job visual diagnostics for detection through rendering.

## Development

- [Development](dev/development.md): shared environment configuration, Docker Compose startup, external dependencies, detection sampling, and drained `w0.2.7` look-ahead objective cutover with old-job/cache isolation.

## References

- [Asynq Historical Reference](ref/asynq/SOURCE.md): copied upstream material retained for historical research; it is not the active API/worker queue implementation.
- [Tailwind Plus UI Blocks](ref/tailwind/README.md): setup, integration, asset, and licensing notes for future frontend work.

## Component Specifications

- [Component Specifications](specs/README.md): root-to-submodule implementation specifications for the backend, worker, frontend, and Compose runtime.
