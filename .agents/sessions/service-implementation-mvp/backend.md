## Implementation Summary

- Implemented Go API configuration, health/readiness, CORS, PostgreSQL repositories/migrations, S3 signed URL storage, and `asynq` task publishing.
- Implemented project, source asset upload/confirmation, job creation/status, artifacts, and signed download routes.
- Added immutable job configuration hashing and queued-job republish behavior after transient queue publication failure.
- Added migration command support through `migrate up`.

Verification: `go test ./...` passes.
