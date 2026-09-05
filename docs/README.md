# Documentation

## Architecture

- [Offline Reframing MVP](architecture/offline-reframing-mvp.md): approved product boundary, independent crop hysteresis and safety precedence, immutable version cutover, and service contracts.
- [Service Implementation Plan](architecture/service-implementation-plan.md): service-by-service implementation tasks, dependencies, interfaces, and verification gates.
- [Worker Debug Telemetry and Evaluation](specs/worker/debug-telemetry-and-evaluation.md): private debug-bundle contract, independent crop-gate diagnostics, redaction, evaluation inputs/metrics, and visual phase-review integration.
- [Phase Evaluation Review](specs/frontend/phase-evaluation.md): private, terminal-job visual diagnostics for detection through rendering.

## Development

- [Development](dev/development.md): Docker Compose startup, external dependencies, and drained `w0.2.2` deployment cutover.

## References

- [Asynq Historical Reference](ref/asynq/SOURCE.md): copied upstream material retained for historical research; it is not the active API/worker queue implementation.
- [Tailwind Plus UI Blocks](ref/tailwind/README.md): setup, integration, asset, and licensing notes for future frontend work.

## Component Specifications

- [Component Specifications](specs/README.md): root-to-submodule implementation specifications for the backend, worker, frontend, and Compose runtime.
