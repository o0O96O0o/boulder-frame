# Debug I/O Review Hardening

## Implemented

- Normalized telemetry keys before safety matching, so snake_case, kebab-case, and camelCase variants are handled consistently. Sensitive and unsafe examples including `encryption_key`, `encryptionKey`, `private_key`, `privateKey`, `raw_frame`, and `rawFrame` are omitted.
- Added `DebugBundleLimitError` and bounded `DebugBundleWriter` output with positive `max_frames` and `max_bytes` limits. Frame records are rejected before write once the frame limit is reached. Compressed output is checked during writes and at close; a byte-limit failure removes the partial bundle.
- Added independently configurable `debug_max_frames` and `debug_max_bytes` defaults, parsed and validated separately from default-off `debug_capture`.
- Added focused tests for key variants, invalid configuration and writer limits, frame-limit behavior, and byte-limit partial-output cleanup.

## Verification

- `cd worker && uv run pytest tests/test_debug.py tests/test_config.py` -> `39 passed in 0.11s`
- `cd worker && uv run ruff check src/boulder_frame_worker/debug.py src/boulder_frame_worker/config.py tests/test_debug.py tests/test_config.py` -> passed
- `git diff --check` -> passed

## Scope

Only `debug.py`, `config.py`, and their focused tests were edited for this hardening work. No pipeline, worker, repository, storage, evaluation, or documentation files were modified.
