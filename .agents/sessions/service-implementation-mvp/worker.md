## Implementation Summary

- Implemented Python worker foundation: configuration, task protocol, state transitions/leases, scratch cleanup, structured errors/progress, FFprobe validation, FFmpeg adapter, target-selection geometry, tracking interfaces, deterministic crop planner, and tests.
- The CLI exposes capability checks and an explicit idle `--serve` mode. Redis/`asynq`, PostgreSQL, S3, detector, pose, and render orchestration adapters remain unimplemented and are documented as the next worker milestone.
- Worker configuration accepts the Compose `PIPELINE_VERSION` and `MODEL_VERSION` values and retries resume at the failed stage.

Verification: `python3 -m pytest` passes with 26 tests; `python3 -m ruff check src tests` passes.
