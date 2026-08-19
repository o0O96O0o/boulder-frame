# Backend Persistence

## PostgreSQL Ownership

PostgreSQL is the durable source of truth for project metadata, asset references, immutable job configuration, job state/progress/errors, and artifact relationships. Video bytes and per-frame measurements do not belong in PostgreSQL.

The migrations are `backend/migrations/001_init.sql` and `backend/migrations/002_worker_leases.sql`.

## Tables

### `development_owners`

Provides the local fixed owner identity. It is a temporary substitute for authentication.

### `projects`

Stores `id`, `name`, `owner_id`, and `created_at`. Names are trimmed and constrained to 1-200 characters. Deleting a project cascades to its assets and jobs.

### `assets`

Stores source/output/debug object references and media metadata:

- `id`, `project_id`, `kind`, `storage_key`
- `upload_state`, `filename`, `content_type`, `size_bytes`
- Optional `width`, `height`, `frame_rate`, and `duration_ms`
- `created_at`

`storage_key` is globally unique. `kind` is constrained to `source`, `output`, or `debug`; upload state is constrained to `pending`, `uploaded`, or `invalid`.

### `processing_jobs`

Stores:

- Identity: `id`, `project_id`, `source_asset_id`
- State: `state`, `stage`, `progress`
- Immutable `configuration` JSONB and its `configuration_hash`
- Safe terminal `error_code` and `error_message`
- Optional `output_asset_id`
- `created_at`, `started_at`, and `completed_at`
- `lease_owner` and `lease_expires_at`

The unique constraint on `(project_id, configuration_hash)` prevents duplicate active/completed configurations. Migration `002_worker_leases.sql` adds lease ownership/expiry, expands the stage constraint for active processing, and adds an index for eligible worker claims. The worker must use atomic claims, lease renewal, and lease-guarded writes; a Redis Stream pending delivery does not itself authorize a state change.

### `job_artifacts`

Links a job to an output/debug asset. `(job_id, kind)` is unique so retries cannot create multiple logical output artifacts for the same job.

## Repository Boundary

`backend/repository.Repository` hides SQL from HTTP handlers. The current interface covers project creation/read, source asset lifecycle, job create-or-get, job read, artifact listing, and queue-failure handling. New worker adapters should use a separate worker-facing repository interface rather than importing HTTP handlers.

## Idempotency

Project and asset creation are not idempotent by request body. Job creation is idempotent by configuration hash. Redis Streams publication uses the job UUID as `task_id`; the publisher suppresses duplicate publication for that job, while PostgreSQL claims and deterministic artifacts make repeated delivery safe.

There is currently no transactional outbox. The API inserts the queued job before publishing the task. If Redis is unavailable, the job remains queued and a later identical request can attempt publication again. A future outbox should replace this recovery-by-repeat-request behavior before production use.
