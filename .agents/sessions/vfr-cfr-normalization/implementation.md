# VFR-to-CFR Normalization Implementation

## Delivered

- Added permissive VFR inspection plus injected `CFRNormalizer`/`FFmpegCFRNormalizer`.
- The pipeline downloads immutable media as `source-original`, passes strict CFR input through, and
  only normalizes `variable_frame_rate` input to scratch-local `source-cfr.mp4` at its exact average
  rational rate before strict reinspection and downstream processing.
- The normalizer maps validated optional AAC only, produces H.264/AAC MP4, relies on FFmpeg default
  display rotation normalization, clears derivative rotation metadata, and does not use `-shortest`,
  so a valid shorter AAC stream cannot truncate normalized or rendered video.
- Normalization preserves non-media `WorkerError` classifications, converts only media conversion
  failures to user-safe `invalid_media`, rejects VFR sources above 1 GiB before FFmpeg, and applies a
  configurable 1,800-second FFmpeg timeout. These defaults fit under the API's 2 GiB upload limit
  while reserving scratch capacity for the source and derivative.
- Wired the configured FFmpeg binary through runtime composition.
- Added unit, pipeline-branch, runtime composition, and real FFmpeg VFR integration coverage,
  including shorter/longer AAC duration handling and near-end target validation.
- Updated the MVP architecture, implementation plan, worker runtime contract, and project guide.

## Verification

- `cd worker && uv run ruff check src tests` passed.
- `cd worker && uv run pytest` passed: `193 passed, 1 skipped`.
- `git diff --check` passed.
- The real FFmpeg integration test covers VFR normalization and final rendering for both shorter and
  longer AAC streams, verifies retained video duration and longer-stream audio duration, and validates
  a target near the video end.
