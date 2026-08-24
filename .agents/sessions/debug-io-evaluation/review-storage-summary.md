# Storage Review Fix Evidence

## Changes

- `PostgresJobRepository.finalize_debug` now accepts a caller-provided canonical debug storage key.
- Debug keys are restricted to `private/debug/{project_id}/{job_id}/{debug_id}.jsonl.gz`, where `debug_id` is a canonical UUID. This preserves deterministic project/job scoping while allowing each upload attempt to use a unique object key.
- Debug finalization requires a current worker lease and permits every nonterminal job state, allowing failed-stage telemetry to be linked before the terminal transition.
- The existing `ON CONFLICT (job_id, kind) DO UPDATE` artifact-row update remains intact and idempotent.
- `S3Storage.delete` calls S3 `delete_object` and classifies delete failures as transient storage errors so callers can clean up an uploaded debug object after finalization fails.
- Output key construction and output finalization behavior are unchanged.

## Focused Verification

- `cd worker && uv run pytest tests/test_repository.py tests/test_storage.py` -> `33 passed in 0.06s`
- `cd worker && uv run ruff check src/boulder_frame_worker/repository.py src/boulder_frame_worker/storage.py tests/test_repository.py tests/test_storage.py` -> `All checks passed!`
- `git diff --check` -> success

## Test Coverage

- Debug finalization accepts each active job state and rejects terminal jobs.
- Invalid, cross-scope, non-UUID, and invalid-extension debug keys are rejected before SQL executes.
- The debug SQL remains lease guarded and retains the idempotent asset/artifact upserts.
- S3 delete dispatch and transient delete-failure classification are covered.
