# Detector Stable Framing Review Fixes

## Applied

- `004_detector_only_review_roles.sql` now drops the prior role constraint before adding the W0.2
  constraint and deletes only obsolete `job_artifacts` links. Retired object-store bytes are left to
  configured lifecycle cleanup.
- Pipeline analysis now selects at the user frame first, then independently associates detector boxes
  forward and backward. Output observations remain chronological. A 1.5 last-accepted-box-diagonal spatial
  gate filters candidates before deterministic association; missed or rejected frames do not update the
  reference.
- Crop planning records `source_aspect_limited` and uses the largest valid requested-aspect crop when
  a detector box cannot be contained. Review summaries, warning intervals, overlays, and evaluator
  metrics expose the condition without claiming containment.
- Evaluation consumes only detector-only `detection`, `framing`, and `render` telemetry. It no longer
  requires pose/tracking telemetry and has an end-to-end writer/load/evaluate test.
- Worker and backend documentation now describe gated bidirectional association, impossible-containment
  diagnostics, lifecycle-managed retired debug objects, and W0.1 immutable-job incompatibility. Old W0.1
  jobs fail `model_unavailable`; users must create W0.2 jobs.

## Verification

- `cd worker && uv run ruff check src tests --output-format concise`: passed.
- `cd worker && uv run pytest -q`: passed, 190 tests.
- `cd backend && go test ./...`: passed.
- `cd frontend && npm test -- --run`: passed, 25 tests.
- `git diff --check`: passed.
- PostgreSQL executable validation was unavailable because neither `psql` nor `initdb` is installed.
  The migration uses standard PostgreSQL `ALTER TABLE ... DROP CONSTRAINT IF EXISTS`, `DELETE`, and
  `ADD CONSTRAINT ... CHECK` syntax and is statically reviewed against migrations 001-003.
