# Worker Specifications

The worker is a Python 3.12 process responsible for media validation, CV measurement, tracking, movement-envelope construction, crop planning, rendering, and artifact upload. It is stateless between jobs; durable state belongs in PostgreSQL and object storage.

## Documents

- [Runtime and Pipeline](runtime-and-pipeline.md): configuration, task boundary, media validation, and current adapter status.
- [Measurements and Planner](measurements-and-planner.md): target association, coordinate systems, tracking interfaces, crop geometry, profiles, and fallback behavior.

## Current Status

Implemented primitives include FFprobe validation, target coordinate mapping, ROI geometry, deterministic crop planning, state/lease semantics, and structured worker errors. The CLI currently exposes `--check` and an explicit idle `--serve` mode. Redis/asynq consumption, PostgreSQL/S3 adapters, detector/pose models, and full render orchestration are pending.
