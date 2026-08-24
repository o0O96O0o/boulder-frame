# Backend Final Fixes

## Completed

- Extended the strict v1 evaluation manifest projection with an optional per-phase `detail` only for
  `unavailable` phases. The field is restricted to one safe 1-500 byte primitive string, and manifests
  with unknown fields, nested detail values, URLs, object paths, credentials, or credential-like text
  are rejected before projection.
- Preserved accepted unavailable details in the authorized evaluation API response. Existing response
  logging still redacts sensitive values and does not log manifest contents or signed URLs.
- Confirmed API reconciliation accepts a current partial canonical review set containing only a valid
  manifest and telemetry run after a retry has removed stale optional phase roles. Mixed-review and
  duplicate role rejection remains covered.
- Documented the migration `003_phase_evaluation.sql` rollout: drain older workers, wait for active
  leases to finish or expire, migrate, then start only compatible workers before resuming consumption.

## Verification

- `gofmt -w domain/models.go domain/models_test.go`
- `go test ./...` passed in `backend/`.
- `go vet ./...` passed in `backend/`.
- `git diff --check` passed.
- Local documentation link targets passed. No installed documentation link checker was available.
- `TestPhaseEvaluationMigrationPostgresBehavior` remains intentionally skipped because `DATABASE_URL`
  is not configured; run it against a disposable PostgreSQL instance to exercise migration `003`.
