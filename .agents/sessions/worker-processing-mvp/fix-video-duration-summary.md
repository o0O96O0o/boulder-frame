# Video Stream Duration Fix

## Change

- `FFprobeAdapter` derives `MediaMetadata.duration_ms` from the selected video stream's exact `duration_ts * time_base`, falling back to that stream's `duration` when timestamp timing is absent.
- `MediaMetadata.expected_frame_count` uses that exact video-stream duration, so frame decoding and crop-path cardinality no longer depend on container duration.
- Rendered output duration validation compares video-stream duration to the source video-stream duration. FFmpeg still maps source audio with `-map 0:a?` and bounds output with `-shortest`.
- Target selection and association code was not changed.

## Regression Coverage

- Added a metadata test where container duration is 44 seconds but video timing is 42 seconds; the metadata duration and expected frame count remain 42 seconds and 2,520 frames at 60 fps.
- Extended the FFmpeg integration test with a synthetic MP4 containing one second of two-fps H.264 video and two seconds of AAC audio. The test confirms the container duration exceeds one second, the worker accepts a two-frame crop path, retains AAC audio, and produces valid one-second video output.

## Verification

- `cd worker && pytest tests/test_media.py` -> `13 passed`
- `cd worker && pytest` -> `89 passed, 1 skipped` before a concurrent worktree edit; final rerun is blocked during collection by unrelated syntax error in `tests/test_models.py:56`.
- `cd worker && ruff check src/boulder_frame_worker/media.py tests/test_media.py` -> passed
- `cd worker && ruff format --check src/boulder_frame_worker/media.py tests/test_media.py` -> passed
- `git diff --check` -> passed
