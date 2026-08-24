# D2 Debug Persistence Summary

- Added `DebugAsset` validation and `PostgresJobRepository.finalize_debug`.
- The finalizer accepts only verified, non-empty `application/gzip` uploads, derives `private/debug/{project_id}/{job_id}.jsonl.gz`, and uses the live `uploading` lease guard.
- SQL upserts the deterministic uploaded `debug` asset and the existing unique `(job_id, 'debug')` artifact link, making reclaimed-job finalization idempotent.
- No migration was needed: `assets.kind` and `job_artifacts.kind` already allow `debug`, and `job_artifacts` already enforces one debug artifact per job.
- Existing generic `S3Storage.upload` already performs upload plus HEAD metadata verification and is reusable for the debug bundle; output finalization was not modified.

Evidence:

- `cd worker && pytest tests/test_repository.py tests/test_storage.py` -> `19 passed in 0.06s`
- `cd worker && pytest tests/test_pipeline.py -k upload` -> `3 passed, 1 deselected in 0.04s`
- `cd worker && ruff check src/boulder_frame_worker/repository.py tests/test_repository.py` -> `All checks passed!`
- `git diff --check` -> success
