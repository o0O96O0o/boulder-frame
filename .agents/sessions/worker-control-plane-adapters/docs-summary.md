# Documentation Summary

## Scope

Updated only authoritative repository documentation and `AGENTS.md` for the approved Redis Streams
MVP control plane. No application source files or copied upstream Asynq reference files were changed.

## Documented Contract

- API publishes `job.process` entries to Redis Stream `boulder-frame:jobs`.
- Each entry has exactly `type`, `task_id`, and `payload`; the payload contains `job_id` and `trace_id`.
- Workers consume group `boulder-frame:job-processors`, use `XREADGROUP`, recover pending deliveries
  with `XAUTOCLAIM`, heartbeat active deliveries with `XCLAIM`, and issue `XACK` only after a terminal
  PostgreSQL result.
- PostgreSQL is the authority for worker ownership via lease owner/expiry, atomic claims, renewal, and
  lease-guarded writes. Migration `002_worker_leases.sql` supplies the lease schema/index boundary.
- Worker runtime configuration now documents database/Redis URLs, worker/consumer identity, read and
  recovery timing, heartbeat, and concurrency.
- The connected control plane intentionally ends claimed work as `model_unavailable` until the
  detector/pose/render pipeline exists; this terminal failure is acknowledged and creates no output.

## Indexes

Renamed the backend contract to `redis-streams-task-distribution.md`, updated all authoritative index
links, and marked `docs/ref/asynq` as historical reference only.
