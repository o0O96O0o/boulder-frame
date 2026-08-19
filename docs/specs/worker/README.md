# Worker Specifications

The worker is a Python 3.12 process responsible for media validation, CV measurement, tracking, movement-envelope construction, crop planning, rendering, and artifact upload. It is stateless between jobs; durable state belongs in PostgreSQL and object storage.

## Documents

- [Runtime and Pipeline](runtime-and-pipeline.md): configuration, task boundary, media validation, and current adapter status.
- [Measurements and Planner](measurements-and-planner.md): target association, coordinate systems, tracking interfaces, crop geometry, profiles, and fallback behavior.

## Current Status

Implemented control-plane components include Redis Streams consumption, PostgreSQL-backed claims/leases, pending-delivery recovery, and terminal acknowledgement, alongside FFprobe validation, target coordinate mapping, ROI geometry, deterministic crop planning, state/lease semantics, and structured worker errors. The CLI exposes `--check` and `--serve`. Detector/pose models, source/object storage, and full render orchestration remain unavailable; the current pipeline records terminal `model_unavailable` after claiming and validating a job.
