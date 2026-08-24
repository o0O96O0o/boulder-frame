# Worker Manifest Fixes

- Manifest v1 now emits exact root `pipeline_version`, `model_version`, and validated bounded source `timing`; worker-produced manifest tests mirror the strict backend root contract.
- Final rendering persists only a minimal aligned crop path. Optional semantic telemetry/review traces are bounded by `debug_max_frames` and `debug_max_bytes`, remove partial files, and cannot fail a validated output.
- Review child cleanup now reaps a process that remains live when the deadline expires after start and before join; deterministic regression coverage verifies termination and close.
- Worker specifications now describe root manifest metadata, minimal render state, optional trace limits, and cleanup responsibility.

Validation:

- `cd worker && uv run pytest` -> `229 passed, 5 skipped`
- `cd worker && uv run ruff format --check src tests` -> passed
- `cd worker && uv run ruff check src tests` -> passed
- Worker documentation internal-link check -> passed (external links excluded)
- `git diff --check` -> passed
- `cd worker && uv run mypy src` could not run because the environment has no `mypy` executable.
