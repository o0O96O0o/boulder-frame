# W1 Storage Evidence

## Implemented

- Added `S3Storage`, a narrow boto3 S3-compatible adapter for private bucket readiness, source downloads, output uploads, and post-upload object heads. Storage service failures become transient `storage_unavailable` errors without disclosing credentials.
- Added worker S3 configuration matching the existing backend/Compose names: endpoint, presign endpoint, region, bucket, credentials, and path-style setting. Runtime readiness now verifies storage before Redis consumption and exposes `storage_adapter` capability status.
- Added `PostgresJobRepository.finalize_output`. Under a live `uploading` lease, one transaction upserts deterministic `private/output/{project_id}/{job_id}.mp4` asset metadata, upserts the unique output artifact relation, and updates `processing_jobs.output_asset_id`.
- The existing schema supports finalization through `assets.storage_key` and `job_artifacts(job_id, kind)` uniqueness; no migration was added.

## Files Changed

- `worker/pyproject.toml`
- `worker/conf/config.json`
- `worker/conf/config.dev.json`
- `worker/src/boulder_frame_worker/config.py`
- `worker/src/boulder_frame_worker/storage.py`
- `worker/src/boulder_frame_worker/repository.py`
- `worker/src/boulder_frame_worker/runtime.py`
- `worker/src/boulder_frame_worker/cli.py`
- `worker/tests/test_config.py`
- `worker/tests/test_storage.py`
- `worker/tests/test_repository.py`
- `worker/tests/test_runtime.py`
- `docs/specs/worker/runtime-and-pipeline.md`

## Verification

- `cd worker && pytest tests/test_config.py tests/test_storage.py tests/test_repository.py tests/test_runtime.py`: 31 passed.
- `cd worker && ruff check` on W1-owned source and test files: passed.
- `cd worker && ruff format --check` on W1-owned source and test files: passed.
- `git diff --check`: passed.

## Remaining Integration Notes

- The current `UnavailablePipeline` remains intentional and does not download, upload, or invoke `finalize_output`; W2-W4 must call storage upload/head after renderer validation, then finalize while the job is `uploading`, followed by the existing guarded completed transition.
- The adapter uses direct S3 operations; `s3_presign_endpoint` is retained and validated to match the shared backend/Compose configuration but is not needed for worker byte transfer.
- Full worker lint was not used as W1 evidence because unrelated pre-existing planner/tracking/test files have line-length/import violations. `mypy` is not installed in this environment (`command not found`).
