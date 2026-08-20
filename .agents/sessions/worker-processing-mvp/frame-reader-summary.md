# Frame Reader Integration Evidence

Date: 2026-08-20

## Delivered

- Added `OpenCVFrameReader`, backed by the pinned `opencv-python-headless==4.10.0.84` package.
- The reader opens the CFR source once, disables OpenCV auto-orientation, applies the validated
  `MediaMetadata.rotation` explicitly, and yields sequential display-coordinate BGR frames.
- Frame timestamps are deterministically calculated with `MediaMetadata.timestamp_for_frame`; decoded
  count, original decoded dimensions, indices, and timestamps are verified against immutable metadata.
- `ProcessingPipeline` now consumes the reader as a stream, creates observations immediately, closes
  generators on all paths, and drops each decoded-frame reference before reading the next frame.
- `compose_runtime` creates the OpenCV default only after the configured W0.1 detector and pose models
  have both verified and loaded. Unconfigured, missing, invalid, or unavailable model/decoder defaults
  remain the safe terminal `model_unavailable` pipeline behavior.
- Documented OpenCV's Apache-2.0 license evidence and decoder contract in
  `docs/specs/worker/models.md` and `docs/specs/worker/runtime-and-pipeline.md`.

## Automated Evidence

| Command | Result |
| --- | --- |
| `cd worker && python3 -m pytest` | `84 passed, 1 skipped` |
| `cd worker && python3 -m ruff check` on changed decoder/runtime/test files | passed |
| `cd worker && python3 -m ruff format --check` on changed decoder/runtime/test files | passed |
| `cd worker && python3 -m compileall -q src` | passed |
| `git diff --check` | passed |
| `PYTHONPATH=/tmp/boulder-frame-opencv-test python3 -m pytest tests/test_frame_reader.py -rs` | `4 passed` |

The normal host test environment has no `cv2`, so `tests/test_frame_reader.py` is skipped there. The
isolated final command installed the exact pin `opencv-python-headless==4.10.0.84` and executed all four
synthetic integration cases: three CFR frames/timestamps and 90/180/270-degree display rotation.

## Formatting Note

The repository-wide `python3 -m ruff format --check src tests` reports only the pre-existing
`src/boulder_frame_worker/models.py` formatting difference. Every file changed by this integration passes
the targeted formatter check; the unrelated file was not modified.
