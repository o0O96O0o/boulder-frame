# Backend Persistence

## PostgreSQL Ownership

PostgreSQL is the durable source of truth for project metadata, asset references, immutable job configuration, job state/progress/errors, and artifact relationships. Video bytes and per-frame measurements do not belong in PostgreSQL.

The migrations are `backend/migrations/001_init.sql`, `backend/migrations/002_worker_leases.sql`,
`backend/migrations/003_phase_evaluation.sql`, and `backend/migrations/004_detector_only_review_roles.sql`.

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

Links a job to an output or optional debug-review asset. `(job_id, kind)` is unique so retries cannot
create multiple logical artifacts for the same semantic role. The current roles are `output`,
`debug_telemetry`, `debug_manifest`, `debug_detection`, `debug_framing`, and `debug_render`. All
review resources point to assets whose `assets.kind` remains `debug`.

### Phase-Review Rollout

Migration `003_phase_evaluation.sql` converts legacy `debug` rows to `debug_telemetry`. Migration
`004_detector_only_review_roles.sql` removes only retired `job_artifacts` links and limits new writes
to detector-only roles. It deliberately does not delete referenced debug assets or object-store bytes:
object storage lifecycle policy cleans these obsolete objects after its configured retention period,
avoiding deletion of arbitrary or shared data. Drain and stop workers that can finalize retired roles,
wait for their leases to finish or expire, apply `004`, then deploy/restart detector-only workers.
Existing W0.1 jobs fail immutable model-version compatibility with `model_unavailable`; users must
create a new W0.2 job rather than retrying an incompatible old job. Do not roll back to an older worker
while the detector-only schema is active.

## Repository Boundary

`backend/repository.Repository` hides SQL from HTTP handlers. The current interface covers project creation/read, source asset lifecycle, job create-or-get, job read, artifact listing, and queue-failure handling. The phase-review extension adds a lease-guarded worker operation that finalizes one complete debug artifact set and a read operation that returns authorized review metadata without revealing object keys. New worker adapters should use a separate worker-facing repository interface rather than importing HTTP handlers.

## Idempotency

Project and asset creation are not idempotent by request body. Job creation is idempotent by configuration hash. Redis Streams publication uses the job UUID as `task_id`; the publisher suppresses duplicate publication for that job, while PostgreSQL claims and deterministic artifacts make repeated delivery safe.

There is currently no transactional outbox. The API inserts the queued job before publishing the task. If Redis is unavailable, the job remains queued and a later identical request can attempt publication again. A future outbox should replace this recovery-by-repeat-request behavior before production use.
