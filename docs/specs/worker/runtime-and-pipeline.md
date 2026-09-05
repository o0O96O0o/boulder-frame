# Runtime And Pipeline

## Runtime

`WorkerConfig` supplies PostgreSQL, Redis Streams, private S3-compatible storage, `WORKER_ID`, FFmpeg,
FFprobe, scratch, lease, VFR-normalization, and debug limits. `MODEL_VERSION=unset-until-pinned`
normalizes to `unconfigured`; the only configured runtime model is
`w0.2-ssd-mobilenetv1-12-onnx-detector-only-1` with one verified
`ssd_mobilenet_v1_12.onnx` artifact in `MODEL_DIR`.

Configured model verification or decoder composition failure prevents startup. A claimed job with a
different immutable `configuration.model_version` fails with `model_unavailable` before a stage
handler runs. `debug_capture` is default-off. `debug_visual_capture` requires it and uses independent
duration, dimensions, aggregate-byte, and child-process deadline limits.

## Durable Pipeline

```mermaid
flowchart LR
  Q[Redis delivery] --> L[PostgreSQL lease claim]
  L --> S[source-original]
  S --> I[Strict ffprobe]
  I -->|CFR| D[ONNX person detection]
  I -->|Supported VFR only| N[Bounded local CFR normalization]
  N --> D
  D --> F[Detector-box framing]
  F --> R[Per-frame crop resize and fixed-frame FFmpeg encode]
  R --> O[Lease-finalize output]
  O --> V[Optional telemetry and review]
  V --> T[Persist terminal state then XACK]
```

Stages are `validating`, `analyzing`, `rendering`, and `uploading`, surrounded by queued/terminal job
states. The worker acknowledges Redis only after a terminal PostgreSQL state is durable. Pending stream
deliveries can be reclaimed; an active PostgreSQL lease prevents duplicate processing.

`validating` downloads the immutable object as `source-original`, strictly inspects supported media,
and normalizes only supported VFR input to job-local `source-cfr.mp4` under configured source-size and
timeout bounds. The immutable object and derivative policy are unchanged: the derivative is never
uploaded or persisted. Valid optional AAC is retained without truncating video, and display rotation
is normalized consistently for analysis and rendering.

`analyzing` maps the immutable tap, detects persons, selects the target on that frame, then associates
forward and backward from its detector box. Later candidates must pass the detector-box-relative spatial
gate; a miss or rejected candidate does not update the reference. `framing` derives the profile-target
crop, independently holds or smooths scale and center through `deterministic-v2` hysteresis, then
contains the current box when possible and reports `source_aspect_limited` when it is not.
Misses bypass/reset the gates and widen without position extrapolation. See
[Detection and Framing](measurements-and-planner.md) for threshold and safety precedence.
`rendering` reads display-normalized BGR frames,
applies every planned crop once with OpenCV, resizes each crop to the fixed 1080p output surface, and
streams the fixed-size frames to FFmpeg for H.264/AAC encoding and muxing. Source, crop, written, and
fully decoded output frame counts must be exactly equal; the renderer never repairs a short output by
duplicating frames or applying an output frame-rate filter. A local rendered output is reusable only
after the same strict media and exact decoded-frame-count validation, and only when its atomic sidecar
matches the persisted crop-path digest, output aspect ratio, and `fixed-output-v1` renderer version.
`uploading` heads and lease-finalizes the deterministic output object before completion.

The `w0.2.2` pipeline and immutable planner controller/threshold hash create distinct jobs for the
same input and settings under the new controller. Old jobs must drain on old workers before the
[version cutover](../../dev/development.md#start-modules), because claim-time compatibility checks
cover model version, not pipeline version. Never carry old job scratch or crop paths into a new job.

## Review Finalization

While a nonterminal lease remains active, `publish_debug` may upload a UUID-scoped review set below
`private/debug/{project_id}/{job_id}/{review_id}/`. Required publication resources are telemetry and
manifest; available phase MP4s are only `detection.mp4`, `framing.mp4`, and `render.mp4`, finalizing
as roles `debug_detection`, `debug_framing`, and `debug_render`. `finalize_review` atomically replaces
these roles and removes stale current-review roles. Debug failures clean up newly uploaded objects
where possible and never alter the required output result.
