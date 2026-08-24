# Final Phase Evaluation Review

The previously reported publication and schema blockers are fixed, but three reviewers found these remaining issues.

## Must Fix

1. `pipeline.py` records an uploaded object only after its head verification. If upload succeeds but head fails, cleanup does not delete that private object.
2. Re-finalizing a review with fewer available phase artifacts leaves old phase relations in place. The backend then rejects the newer manifest because linked roles belong to different review UUIDs.
3. Phase overlays are incomplete relative to the documented evidence contract. In particular, the render phase draws source-coordinate crop rectangles after source resizing, so overlays are incorrect for source/output resolution differences.

## Should Fix

- Preserve bounded per-phase unavailable reasons through manifest, API, and UI.
- Validate successful evaluation JSON at the frontend API boundary rather than assuming the response shape.
- Document or enforce coordinated rollout because migration rejects old worker `debug` finalization.

## Test Gaps

- Upload-success/head-failure cleanup.
- Re-finalization with a reduced artifact set.
- Pixel/coordinate assertions for all semantic overlays, including 4K source to 1080p output.
- Worker publication through storage/PostgreSQL/backend endpoint/browser contract.
- PostgreSQL migration behavior was skipped locally because `DATABASE_URL` is unavailable.

No fixes from this review have been applied. The two untracked root telemetry exports remain untouched and must not be committed.
