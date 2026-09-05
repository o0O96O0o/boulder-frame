# Worker

The Python 3.12 worker owns source validation, ONNX person detection, deterministic detector-box
framing, FFmpeg rendering, and artifact upload. It is stateless between jobs; PostgreSQL owns durable
job state and object storage owns video assets.

## Documents

- [Runtime and Pipeline](runtime-and-pipeline.md): configuration, task boundary, media validation, cache isolation across version cutovers, and durable processing.
- [Model Manifest](models.md): W0.2 detector artifact, license, checksum, tensor contract, and provisioning.
- [Detection and Framing](measurements-and-planner.md): selection association, source coordinates, profile targets, independent scale/center hysteresis, safety precedence, and miss/reacquisition behavior.
- [Debug Telemetry and Evaluation](debug-telemetry-and-evaluation.md): bounded private telemetry, gate errors/states, and detector-only visual-review contract.

## Current Contract

The worker consumes Redis Streams tasks under a PostgreSQL lease, downloads and validates the source,
normalizes supported VFR input only in job scratch, detects the selected athlete, derives a
`deterministic-v2` crop path with independent scale/center hysteresis, renders and validates 1080p
H.264/AAC output, and finalizes it under the active lease. The default pipeline is `w0.2.2`.
It uses model version
`w0.2-ssd-mobilenetv1-12-onnx-detector-only-1`; a matching unconfigured runtime fails jobs safely
with `model_unavailable`, while a configured W0.2 runtime with an unavailable decoder or invalid
artifact fails startup.

When `debug_capture` is enabled, the worker writes bounded source-coordinate detector/framing/render
telemetry and phase timing. `debug_visual_capture` additionally renders optional bounded review media.
Each review set has `debug_telemetry`, `debug_manifest`, and only available `debug_detection`,
`debug_framing`, and `debug_render` artifacts at
`private/debug/{project_id}/{job_id}/{review_id}/`. Capture and review-finalization failures are
best-effort and never alter a validated product output. The implementation contains only detector
measurements and current-box framing decisions.
