# Redis Streams Control Plane Implementation

## Completed

- Replaced the Go API's Asynq publisher with Redis Streams `XADD` to
  `boulder-frame:jobs`.
- Defined the shared entry contract: `type=job.process`, `task_id`, and the unchanged JSON payload
  containing exactly `job_id` and `trace_id`.
- Added idempotent Redis publication, PostgreSQL worker claims/leases, guarded state writes, lease
  renewal/release, and ordered schema migrations.
- Added a Python Redis Streams consumer group (`boulder-frame:job-processors`) with `XREADGROUP`,
  `XAUTOCLAIM`, active-delivery `XCLAIM` heartbeats, and terminal-only `XACK`.
- Added real psycopg and redis-py runtime composition, readiness checks, signal-aware drain behavior,
  and required worker identity propagation through Compose.
- Kept the intentional no-media-pipeline behavior: a claimed job becomes terminal
  `model_unavailable` after `validating`; no output artifact is created.
- Fixed the review-discovered live-lease race: a delivery that cannot obtain a nonterminal PostgreSQL
  job claim remains pending rather than being acknowledged.
- Updated authoritative architecture, runtime, deployment, persistence, and queue-contract docs.

## Verification

- `go test ./...` passed in `backend/`.
- `go vet ./...` passed in `backend/`.
- `python3 -m pytest` passed in `worker/`: 51 tests.
- `python3 -m ruff check .` and `python3 -m ruff format --check .` passed in `worker/`.
- `docker compose --env-file .env.example config --quiet` passed.
- `git diff --check` passed.
- The Go Redis publisher test used a local `redis-server` when available.

## Remaining Limits

- PostgreSQL integration testing was not runnable because no local PostgreSQL client/server is available.
- Mypy is not installed in the workspace.
- The actual source download, CV, tracking, crop planning, rendering, upload, and output-artifact
  pipeline remains intentionally out of scope.
