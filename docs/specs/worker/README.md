# Worker Specifications

The worker is a Python 3.12 process responsible for media validation, CV measurement, tracking, movement-envelope construction, crop planning, rendering, and artifact upload. It is stateless between jobs; durable state belongs in PostgreSQL and object storage.

## Documents

- [Runtime and Pipeline](runtime-and-pipeline.md): configuration, task boundary, media validation, and current adapter status.
- [Model Manifest](models.md): pinned detector and pose artifacts, licenses, checksums, runtime contracts, and operator provisioning.
- [Measurements and Planner](measurements-and-planner.md): target association, coordinate systems, tracking interfaces, crop geometry, profiles, and fallback behavior.
- [Debug Telemetry and Evaluation](debug-telemetry-and-evaluation.md): default-off capture configuration, private JSONL bundle format/redaction, evaluation annotations and metrics, and current integration limits.

## Current Status

Implemented worker components include Redis Streams consumption, PostgreSQL-backed claims/leases, pending-delivery recovery, and terminal acknowledgement, alongside source download, FFprobe validation, target coordinate mapping, ROI geometry, injectable raw observations, single-target tracking, deterministic crop planning, FFmpeg source-frame crop-bbox annotation/validation, deterministic upload/head, lease-guarded output finalization, state/lease semantics, and structured worker errors. Default-off `debug_capture` is wired through runtime, pipeline, and worker: it captures bounded source-coordinate analysis frames and phase timings, then best-effort publishes a UUID-scoped private bundle under the active lease after success or before a stage failure is persisted. It requires a bucket with all four S3 public-access blocks enabled, cleans up newly uploaded objects after failed finalization when possible, and never changes the required job outcome. The evaluator streams frames, ignores operational records, and marks annotations with no telemetry as insufficient. The output MP4 is currently the rotation-normalized original video with the final per-frame planned crop rectangle drawn in lime; it is an inspection artifact rather than a cropped 1080p render. The CLI exposes `--check` and `--serve`. The checked-in model manifest selects an ONNX SSD-MobilenetV1 detector and MediaPipe Pose Landmarker Full; after those exact local files verify and load, OpenCV streams rotation-normalized BGR CFR frames into analysis. No external weights are bundled or downloaded. The local `unset-until-pinned` sentinel is the safe `unconfigured` runtime state, where matching jobs fail with `model_unavailable`; configured W0.1 with missing artifacts fails startup, and provisioned W0.1 rejects immutable job model-version mismatches before stage handlers run.

Production enables the public-access-block check; a trusted development environment may explicitly set `debug_require_private_storage: false` while using `debug_capture`.
