# Worker Review Fixes

## Changed Files

- `worker/conf/config.json`
- `worker/conf/config.dev.json`
- `worker/src/boulder_frame_worker/config.py`
- `worker/src/boulder_frame_worker/pipeline.py`
- `worker/src/boulder_frame_worker/repository.py`
- `worker/src/boulder_frame_worker/review.py`
- `worker/src/boulder_frame_worker/runtime.py`
- `worker/tests/test_config.py`
- `worker/tests/test_pipeline.py`
- `worker/tests/test_repository.py`
- `worker/tests/test_review.py`

## Delivered

- Added default-off `debug_visual_capture`, rejected unless `debug_capture` is enabled, and instantiate `ReviewRenderer` only for visual capture.
- Published telemetry, parser-compatible manifest, and available phase MP4s under one UUID-scoped review prefix. The manifest uses schema v1, ordered phase IDs/statuses, primitive summaries, bounded `label`/optional `detail` intervals, and telemetry readiness.
- Added an atomic, lease-guarded repository finalizer for `debug_telemetry`, `debug_manifest`, and phase roles. Publication uploads and heads every artifact, preserves partial visual reviews, and deletes newly uploaded objects if finalization fails. Legacy telemetry finalization now uses `debug_telemetry`.
- Applied one review deadline across decode, annotation, and FFmpeg encoding; timed-out phase files are removed without affecting output or telemetry publication.
- Added phase-specific overlays from trace values and tests for configuration, manifest/publication, finalization guards, cleanup, semantic annotations, and deadline behavior.

## Verification

- `uv run ruff check src tests`: passed.
- `uv run pytest`: `218 passed, 2 skipped`.
- Focused `uv run ruff format --check` for changed files: passed. Full format check still reports four pre-existing unrelated files: `src/boulder_frame_worker/debug.py`, `src/boulder_frame_worker/measurement.py`, `tests/test_debug.py`, and `tests/test_media.py`.
- `git diff --check`: passed.
- `uv run mypy`: not run because the worker environment has no `mypy` executable.
