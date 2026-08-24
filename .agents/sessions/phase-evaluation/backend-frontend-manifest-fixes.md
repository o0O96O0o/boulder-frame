# Backend/Frontend Manifest Fixes

- Backend manifest validation now rejects warning `start_ms` or optional `end_ms` values after the inclusive `timing.duration_ms` boundary, while retaining non-negative, ordered, safe, and open-ended interval support.
- Frontend evaluation response validation applies the same source-duration bounds. Its fixture timing now contains its documented warning timestamps.
- Backend tests use a worker-compatible root manifest (`pipeline_version`, `model_version`, and `timing`) and cover the inclusive boundary plus invalid negative, reversed, start-overrun, and end-overrun intervals. Frontend tests cover valid inclusive and invalid overrun intervals.
- Updated `docs/specs/backend/http-api.md` and `docs/specs/frontend/phase-evaluation.md` with the exact interval bounds.

Verification passed on 2026-08-24:

- `cd backend && go test ./...`
- `cd backend && go vet ./...`
- `cd frontend && npm run typecheck`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- `git diff --check`
