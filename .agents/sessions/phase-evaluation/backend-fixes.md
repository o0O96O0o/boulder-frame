# Backend Review Fixes

- Aligned warning intervals with `label` and optional `detail`; `end_ms` remains optional and timestamps remain non-negative and ordered.
- The v1 manifest parser accepts the worker-produced UUID review ID, ordered five phase entries, primitive-or-null summaries, and telemetry status. It projects only safe fields and rejects sensitive summary/warning content.
- Evaluation reconciliation now rejects duplicate/unknown roles and requires every linked artifact to use its canonical UUID-scoped key, expected filename, content type, project, and debug asset state before exposing any URL.
- HTTP logging redacts sensitive field names and sensitive values embedded in ordinary fields.
- Added API contracts for authorization, terminal failure/partial review, worker-compatible manifests, sensitive manifests, and mismatched/duplicate artifacts.
- Added `TestPhaseEvaluationMigrationPostgresBehavior`, which migrates a legacy `debug` relation and verifies accepted, rejected, and unique roles in an isolated PostgreSQL schema when `DATABASE_URL` is configured.

Verification:

- `gofmt -w domain/models.go domain/models_test.go httpapi/handler.go httpapi/handler_test.go httpapi/logging.go main_test.go`
- `go test ./...` passed.
- `go vet ./...` passed.
- `git diff --check` passed.
- The PostgreSQL behavior test was skipped locally because `DATABASE_URL` is not configured and `docker compose ps` showed no running database service. It will run automatically against a disposable PostgreSQL database when that environment variable is supplied.
