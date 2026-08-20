# W4 Worker Processing MVP Integration Evidence

## Outcome

W4 replaces the runtime `UnavailablePipeline` with the injectable `ProcessingPipeline`, executed by
the existing `Worker.process` lifecycle. The pipeline reconstructs job-scoped prerequisites on each
attempt and executes validating, analyzing, rendering, and uploading stages. It uses immutable job
configuration and source metadata, downloads from object storage, validates with FFprobe, analyzes
through explicit frame/detector/pose adapters, tracks and plans crops, renders and validates with
FFmpeg, uploads and heads the deterministic output key, calls lease-guarded repository finalization,
then allows `Worker.process` to persist `completed`.

Redis and PostgreSQL ownership semantics remain intact: terminal and missing/duplicate durable jobs
ACK; live foreign leases and transient errors remain pending; transient errors release the database
lease; both the Redis delivery and database lease heartbeats are unchanged. Per-job scratch is removed
in `finally` unless debug retention is selected, and stale crash leftovers are removed before a retry.

## Files Changed

- `worker/src/boulder_frame_worker/pipeline.py`: concrete four-stage pipeline, explicit injection
  interfaces, immutable configuration parsing, storage validation, crop-path analysis, render reuse,
  upload/head verification, and output finalization.
- `worker/src/boulder_frame_worker/runtime.py`: composes `ProcessingPipeline` and `Worker.process`
  with injectable media/CV dependencies instead of `UnavailablePipeline`.
- `worker/src/boulder_frame_worker/worker.py`: ACKs duplicate terminal/missing jobs and recreates
  job scratch safely on reclaimed attempts.
- `worker/src/boulder_frame_worker/measurement.py`: supports non-terminal later-frame observation gaps.
- `worker/tests/test_runtime.py`: successful injected-adapter runtime composition and safe default
  `model_unavailable` failure.
- `worker/tests/test_pipeline.py`: verified upload/finalization, transient storage failure, and
  transient database-finalization failure.
- `worker/tests/test_worker.py`: terminal failures at every later stage, terminal/missing duplicate
  ACK behavior, transient lease release, scratch cleanup, and lease heartbeat coverage.
- `docs/specs/worker/runtime-and-pipeline.md`: implemented data flow, finalization, retry/ACK, and
  model-adapter boundary.
- `docs/specs/worker/README.md`: worker implementation status.
- `docs/architecture/service-implementation-plan.md`: implementation status updated for W4.

## Tests Run

- `cd worker && python3 -m ruff check src tests`
- `cd worker && python3 -m ruff format --check src tests`
- `cd worker && python3 -m pytest` -> `78 passed`
- `cd worker && python3 -m compileall -q src`
- `git diff --check`

`python3 -m mypy src` was attempted earlier but could not run because this environment has no `mypy`
module installed.

## Known Limitations

- No detector, pose, or frame-reader model adapter or external weights are bundled. The default path
  persists safe terminal `model_unavailable`; deployments must inject licensed, pinned adapters.
- The injected frame reader is responsible for supplying every display-rotation-normalized CFR frame;
  no production decoder adapter is selected in this change.
- Full disposable PostgreSQL/Redis/S3 integration testing remains a W5 verification task. Unit tests
  cover adapter contracts, state semantics, deterministic finalization SQL, and pipeline orchestration.
