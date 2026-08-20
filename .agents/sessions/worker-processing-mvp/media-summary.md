# W2 Media Evidence Summary

## Implemented

- `worker/src/boulder_frame_worker/media.py`
  - Added deterministic crop-path conversion to an FFmpeg frame-evaluated `crop` and `scale` filter script.
  - Applies display rotation once before interpreting display-coordinate crop rectangles; source auto-rotation is disabled.
  - Enforces a crop rectangle for every expected CFR source frame and validates source bounds and target aspect ratio.
  - Renders 1920x1080 or 1080x1920 H.264 MP4 with yuv420p pixels and AAC audio when the source has audio.
  - Probes rendered output for dimensions, H.264/AAC codecs, source-audio preservation, and frame-duration tolerance, then decodes all mapped streams to null before returning metadata.
  - Classifies FFmpeg rendering failures as `render_unavailable` and output decode/validation failures as `invalid_output`.
- `worker/tests/test_media.py`
  - Added synthetic FFmpeg end-to-end tests for landscape with AAC audio and portrait without audio.
  - Exercises a moving per-frame crop path, requested output dimensions, H.264/AAC presence, duration, and decode-to-null validation.
  - Added rotation-filter and output audio/duration validation coverage.

## Verification

- `cd worker && pytest tests/test_media.py` -> 11 passed
- `cd worker && pytest` -> latest rerun: 69 passed, 1 unrelated failure in `tests/test_measurement.py::test_no_target_is_terminal` because the worktree version references `pytest` without importing it. The full suite passed earlier in this session with 70 tests before that unrelated worktree edit was present.
- `cd worker && ruff check src/boulder_frame_worker/media.py tests/test_media.py` -> passed
- `cd worker && ruff format --check src/boulder_frame_worker/media.py tests/test_media.py` -> passed
- `git diff --check` -> passed

## Remaining Integration Notes

- Runtime composition still uses `UnavailablePipeline`; W4 must hydrate source media, invoke `FFmpegRenderer.render_crop_path`, and finalize the uploaded artifact under the active lease.
- The crop path must be generated in normalized display coordinates after analysis/planning. This W2 slice does not add detector, pose, tracking, or planner behavior.
- The filter script is written beside the temporary output path and should remain inside the job scratch directory managed by the worker.
- FFmpeg/ffprobe availability is required in the worker runtime image; the existing Docker image installs FFmpeg.
