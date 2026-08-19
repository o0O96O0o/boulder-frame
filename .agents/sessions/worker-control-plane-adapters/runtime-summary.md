# Runtime Summary

## Scope

Implemented worker-side W1.1, W1.4, and W1.5 boundaries without changing `backend/main.go`, backend migrations, or the worker repository/state implementation owned by unrelated worktree changes.

## Files Changed

- `worker/src/boulder_frame_worker/config.py`: database/Redis URLs, heartbeat, concurrency, worker identity, and runtime URL validation.
- `worker/conf/config.json`: environment-backed production runtime settings.
- `worker/conf/config.dev.json`: environment-backed development runtime settings.
- `worker/src/boulder_frame_worker/queue_adapter.py`: transport-neutral task consumer boundary, exact `job.process` filtering, payload parsing, ack/retry mapping, shutdown delegation, and fail-closed unavailable adapter.
- `worker/src/boulder_frame_worker/runtime.py`: injectable runtime composition and unavailable pipeline that transitions a claimed job to `validating`, then terminal `model_unavailable` without scratch/output artifacts.
- `worker/src/boulder_frame_worker/cli.py`: prompt startup failure instead of indefinite idle sleep; readiness remains false until real adapters are injected.
- `worker/tests/test_config.py`, `worker/tests/test_queue_adapter.py`, `worker/tests/test_runtime.py`: focused unit coverage.

## Compatibility Evidence

Backend pins `github.com/hibiken/asynq v0.25.1`. Official Asynq exposes its consumer/server as Go APIs (`asynq.NewServer`, `Server.Run`, `Server.Start`); it does not publish a Python consumer protocol/client. Public Python search results found `newlife/asynq-py`, an unlicensed, dormant, enqueue-only repository with no consumer, lease, acknowledgement, or retry implementation. Therefore no maintained Python client passed the W1.1 gate. The worker does not add a raw Redis protocol clone or claim queue readiness. `UnavailableQueueAdapter` fails closed with the explicit compatibility blocker.

## Verification

- `python3 -m pytest` in `worker/`: **44 passed**.
- `python3 -m ruff check src tests` in `worker/`: **all checks passed**.
- `python3 -m mypy` in `worker/`: not run successfully because `mypy` is not installed in the environment.
- Cross-language Redis/Asynq integration was not run because no compatible Python consumer exists and no Redis protocol clone was introduced.
- `PYTHONPATH=src python3 -m boulder_frame_worker.cli --config conf/config.dev.json --serve`: exited promptly with status 2 and a safe missing-`database_url` message; no indefinite idle loop.
- Existing unrelated changes remain in `backend/main.go`, `backend/migrations/002_worker_leases.sql`, `worker/repository.py`, `worker/state.py`, and related tests; they were not reverted or modified.
