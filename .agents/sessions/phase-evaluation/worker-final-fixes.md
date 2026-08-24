# Worker Final Fixes

Applied the approved worker-side fixes only.

- Registered every review object key before `upload()` performs its head verification, so an upload-success/head-failure path deletes the private object.
- Made review finalization delete omitted review-role links in the same active-lease transaction, preventing stale artifacts from an earlier full retry from surviving a partial retry.
- Rendered all documented phase-specific evidence from the aligned analysis trace. Source-coordinate geometry is scaled and clipped per pane, including the 4K-source/1080p render split view.
- Added a bounded, user-safe unavailable `detail` to every unavailable manifest phase. Renderer failure reasons are allowlisted codes.

Verification completed in `worker/`:

```text
uv run ruff format src tests
uv run ruff check src tests
uv run pytest
223 passed, 3 skipped
```

`git diff --check -- worker` also passed. Existing backend, frontend, documentation, and untracked root telemetry changes were not modified.
