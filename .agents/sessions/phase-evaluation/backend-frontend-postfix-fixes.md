# Backend/Frontend Post-Fix Evidence

## Delivered

- Defined strict visual-review manifest v1 metadata: `pipeline_version`, `model_version`, and
  `timing.frame_rate`, `timing.duration_ms`, `timing.frame_count`.
- Backend rejects unknown, unsafe, unbounded, or immutable-job-version-mismatched manifests before
  projection; it never projects manifest storage data or secrets.
- A review is visually available only when a verified phase MP4 exists. Telemetry-only or
  all-phase-unavailable runs return `available: false`; an explicit telemetry export remains
  available when present. Phase URLs are not presigned in those unavailable cases.
- The frontend validates the bounded metadata projection, opens review only after an explicit
  available response, and keeps a telemetry-only export on the terminal card without opening an
  empty workspace.
- Updated API and frontend phase-review contracts. The worker owner must emit the documented root
  metadata shape; worker files were intentionally not modified by this scope.

## Evidence

- `cd backend && go test ./...` passed.
- `cd frontend && npm test` passed: 3 files, 22 tests.
- `cd frontend && npm run typecheck` passed.
- `cd frontend && npm run build` passed.
- `git diff --check` passed.
- Local Markdown-link check passed for the 3 changed API/frontend documents; all local links resolve.

## Environment Note

- `markdown-link-check` is not installed; the local-link check used a read-only Node script against
  changed tracked Markdown links.
