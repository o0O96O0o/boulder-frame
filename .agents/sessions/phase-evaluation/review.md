# Phase Evaluation Review

Three independent read-only reviews identified the following implementation blockers.

1. The worker generates review files only in job scratch and still publishes telemetry using the retired `debug` artifact role. Migration `003_phase_evaluation.sql` replaces that role with `debug_telemetry`, so debug publication becomes best-effort failure and the API cannot find phase media.
2. The worker manifest is not compatible with the backend parser: it lacks `review_id` and uses a phase object while the API requires an ordered phase array with IDs and statuses.
3. Visual capture is coupled to `debug_capture`; the documented, independently default-off `debug_visual_capture` flag is missing.

Additional findings:

- Apply one total review deadline across source decode, overlay, and encodes; current timeout only covers each FFmpeg invocation.
- Render the semantic overlay fields captured in the trace and test phase-specific overlays.
- Restrict or redact manifest-provided summary/reason fields so they cannot expose URLs or credentials through API responses/logs.
- Align backend `reason` with frontend `label`/`detail` warning fields and use one fixture/schema across worker, backend, and frontend tests.
- Add review-video load failure/refresh UX and either implement accessible tab behavior or use regular buttons.
- Add migrated-PostgreSQL and cross-service manifest/API/UI integration coverage.

No review fixes were applied. User approval is required before continuing with these changes.
