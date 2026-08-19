# W1.2/W1.3 Persistence Summary

## Changed Files

- `backend/main.go`: applies sorted SQL migrations with a transactional `schema_migrations` ledger.
- `backend/main_test.go`: tests migration ordering and worker lease migration declarations.
- `backend/migrations/002_worker_leases.sql`: adds job lease fields, stage constraint, and active-claim index.
- `worker/src/boulder_frame_worker/state.py`: adds immutable claimed execution context, lease renewal, guarded in-memory state writes, and terminal lease cleanup.
- `worker/src/boulder_frame_worker/repository.py`: adds the worker-specific PostgreSQL repository with atomic claims, configuration/source-asset hydration, lease renewal, and lease-guarded transition/progress/error writes.
- `worker/tests/test_state.py`: covers guarded terminal and stale-owner state behavior.
- `worker/tests/test_repository.py`: covers repository claim hydration, live-lease rejection, stale-owner rejection, and terminal lease cleanup SQL.

## Verification

- `backend: go test ./...` passed.
- `worker: pytest` passed: 44 tests.
- `worker: ruff check` and `ruff format --check` passed for W1.2/W1.3 worker files.
- `git diff --check` passed.
- PostgreSQL integration tests were not run: this workspace has no PostgreSQL server/client and no installed Python PostgreSQL driver. Repository tests use an injected DB-API connection fake to verify query parameters and guarded-write behavior.
- `mypy` was not run: the executable is not installed in the workspace.
