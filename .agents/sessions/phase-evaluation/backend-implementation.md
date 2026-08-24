# Backend Phase Evaluation Implementation

## Findings

- `job_artifacts` previously allowed one legacy `debug` relation only. Migration `003_phase_evaluation.sql` migrates it to `debug_telemetry` before replacing the kind constraint with the seven approved review roles.
- The existing worker review renderer is still in progress and does not yet emit the finalized API manifest shape or persist the review set. Backend work does not modify worker-owned files.
- The stable manifest interface consumed by the API is schema version `1`: a UUID `review_id`; ordered `measurement`, `pose`, `tracking`, `planning`, and `render` phase entries; each phase has `id`, `status`, optional primitive-only `summary`, and optional bounded `warning_intervals`; optional `telemetry.status = "ready"`. Ready/partial/warning phase media is eligible only when its matching uploaded role and canonical key are linked.

## Changed Files

- `backend/migrations/003_phase_evaluation.sql`
- `backend/domain/models.go`
- `backend/domain/models_test.go`
- `backend/repository/repository.go`
- `backend/storage/storage.go`
- `backend/httpapi/handler.go`
- `backend/httpapi/handler_test.go`
- `backend/main_test.go`

## Verification

- `gofmt -w domain/models.go domain/models_test.go httpapi/handler_test.go main_test.go`
- `go test ./...`
- `go vet ./...`
- `git diff --check`
