# Worker

The Python 3.12 worker owns source validation, ONNX person detection, full-shot look-ahead pan with
causal detector-box zoom, FFmpeg rendering, and artifact upload. It is stateless between jobs; PostgreSQL owns durable
job state and object storage owns video assets.

## Documents

- [Runtime and Pipeline](runtime-and-pipeline.md): configuration, task boundary, attempt-scoped leases and scratch, opaque JSON processing reports, media validation, cache isolation across version cutovers, and durable processing.
- [Model Manifest](models.md): W0.2 detector artifact, license, checksum, tensor contract, and provisioning.
- [Detection and Framing](measurements-and-planner.md): sampled detection/provenance, full-shot sparse pan optimization, sampled-only hard containment, permitted stale-target exclusion, causal seed zoom, minimal motion excess, and validated optima.
- [Debug Telemetry and Evaluation](debug-telemetry-and-evaluation.md): bounded private telemetry, sampled/held containment, look-ahead kinematics/excess warnings, immutable configuration, and detector-only review.

## Current Contract

The worker consumes Redis Streams tasks under a PostgreSQL lease, downloads and validates the source,
normalizes supported VFR input only in job scratch, detects the selected athlete, derives a
`lookahead-v1` crop path with full-shot per-axis pan optimization and unchanged `deterministic-v3`
causal seed dimensions, renders and validates 1080p H.264/AAC output, and finalizes under the lease.
The default pipeline is `w0.2.5`, with detection sampled at 10 fps by default and full-rate planning/rendering.
Only fresh accepted samples constrain containment. Held targets may leave the crop; future observed
boxes guide the camera without athlete trajectory interpolation. Invalid optimizer output fails
analyzing safely with `internal`, no causal fallback, and no committed analysis artifacts.
The exact immutable planner map is validated before cached replay. Deploy backend/worker together
through a [drained cutover](../../dev/development.md#start-modules); never upgrade old jobs by retry.
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
measurements and camera planning from observed boxes, never predicted athlete positions.
