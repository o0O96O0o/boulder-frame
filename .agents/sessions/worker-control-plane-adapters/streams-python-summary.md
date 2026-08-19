# Redis Streams Python Worker Summary

## Changed Files

- `worker/pyproject.toml`: pinned `psycopg[binary]` and `redis` runtime dependencies.
- `worker/src/boulder_frame_worker/config.py`: added Redis Streams names, consumer settings, recovery timing, and runtime worker identity validation.
- `worker/src/boulder_frame_worker/queue_adapter.py`: replaced the Asynq fail-closed boundary with a Redis Streams consumer-group transport using `XREADGROUP`, `XAUTOCLAIM`, active-delivery `XCLAIM` heartbeats, and terminal `XACK`.
- `worker/src/boulder_frame_worker/runtime.py`: composes configured `psycopg` PostgreSQL and `redis-py` Streams adapters, verifies readiness, and preserves the `validating` then `model_unavailable` pipeline.
- `worker/src/boulder_frame_worker/cli.py`: reports verified adapter readiness and stops consumption cleanly on `SIGINT` or `SIGTERM`.
- `worker/src/boulder_frame_worker/state.py`: added the repository lease-release contract and in-memory implementation.
- `worker/src/boulder_frame_worker/repository.py`: added PostgreSQL readiness and lease release operations.
- `worker/src/boulder_frame_worker/worker.py`: heartbeats active database leases and releases them before transient queue retries.
- `worker/tests/test_config.py`, `worker/tests/test_queue_adapter.py`, `worker/tests/test_repository.py`, `worker/tests/test_runtime.py`, `worker/tests/test_state.py`, `worker/tests/test_worker.py`: focused transport, readiness, heartbeat, and lease lifecycle coverage.

## Assumptions

- Producers write Redis Stream fields named `type`, `task_id`, and `payload`; `payload` is the unchanged JSON bytes for `JobTask`, and `task_id` equals its `job_id`.
- The configured `worker_id` is used as the default Redis consumer identity; `stream_consumer` can override it when a deployment needs a distinct consumer name.
- Pending retry entries are intentionally not acknowledged. `XAUTOCLAIM` recovers entries idle for `stream_reclaim_idle_ms`; active handlers reset their pending idle timer with `XCLAIM`, while database lease release makes transient retries immediately claimable once recovered.
- The worker intentionally has no media pipeline. A successfully claimed entry transitions `queued -> validating -> failed(model_unavailable)` and is acknowledged.

## Verification

- `pytest`: 48 passed.
- `ruff check .`: passed.
