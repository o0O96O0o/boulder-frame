# D4-D5 Contract And Documentation Alignment

## Changed Contract

- Backend domain, repository query, API projection, manifest validation, and tests now use ordered
  review phases `detection`, `framing`, `render` and roles `debug_detection`, `debug_framing`,
  `debug_render`, plus `debug_telemetry` and `debug_manifest`.
- Added `backend/migrations/004_detector_only_review_roles.sql`. It preserves migration `003`'s
  legacy `debug` to `debug_telemetry` conversion, deletes retired review links, and constrains future
  artifact writes to the detector-only role set.
- Worker review finalization validates and removes stale roles from the same detector-only set.
- Frontend API types/parser, fixtures, phase-review tests, profile descriptions, and analyzing label
  match the detector-only contract. Profiles state fixed height fractions: tight `.60`, balanced
  `.50`, safe `.40`, full_movement `.33`.
- Updated architecture, service plan, worker specs, frontend phase evaluation, backend persistence/API
  spec, development guide, indexes, root README, and AGENTS guidance. Mermaid diagrams now show
  detector-box framing and the three-phase review flow. Removed an accidental deployed-server
  credential from `docs/dev/development.md`.

## Files Changed For D4-D5

- `backend/domain/models.go`, `backend/domain/models_test.go`
- `backend/repository/repository.go`
- `backend/httpapi/handler.go`, `backend/httpapi/handler_test.go`
- `backend/main_test.go`, `backend/migrations/004_detector_only_review_roles.sql`
- `worker/src/boulder_frame_worker/repository.py`, `worker/tests/test_repository.py`
- `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/api.test.ts`
- `frontend/src/fixtures/evaluation.ts`, `frontend/src/components/PhaseReview.test.tsx`
- `AGENTS.md`, `README.md`
- `docs/architecture/offline-reframing-mvp.md`
- `docs/architecture/service-implementation-plan.md`
- `docs/dev/development.md`, `docs/README.md`, `docs/specs/README.md`
- `docs/specs/backend/http-api.md`, `docs/specs/backend/persistence.md`
- `docs/specs/frontend/phase-evaluation.md`
- `docs/specs/worker/README.md`, `models.md`, `runtime-and-pipeline.md`,
  `measurements-and-planner.md`, `debug-telemetry-and-evaluation.md`

## Verification Evidence

- `go test ./...` in `backend`: passed.
- `uv run pytest tests/test_repository.py tests/test_review.py tests/test_pipeline.py tests/test_planner.py tests/test_runtime.py tests/test_models.py tests/test_measurement.py tests/test_debug.py` in `worker`: `56 passed`.
- `npm run typecheck && npm test` in `frontend`: typecheck passed; `25 passed`.
- `npx --yes markdown-link-check` across changed authoritative/docs index files: passed.
- `git diff --check`: passed.

The PostgreSQL migration behavior test remains skipped unless `DATABASE_URL` points to a disposable
database, as designed by the existing test.
