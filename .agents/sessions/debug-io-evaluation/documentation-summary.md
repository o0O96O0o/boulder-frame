# Debug Telemetry And Evaluation Documentation Summary

## Documentation Changes

- Added `docs/specs/worker/debug-telemetry-and-evaluation.md` as the focused authoritative worker specification.
- Indexed it from `docs/README.md`, `docs/specs/README.md`, and `docs/specs/worker/README.md`.
- Updated `docs/specs/worker/runtime-and-pipeline.md` to distinguish local scratch retention from durable capture and to describe publication/finalization timing.
- Updated `worker/conf/config.json` and `worker/conf/config.dev.json` with the default-off capture flag and bounded-capture defaults.

## Code Evidence

- `worker/src/boulder_frame_worker/config.py`: `debug_capture` defaults to `false` and is parsed independently from `retain_debug_artifacts`.
- `worker/src/boulder_frame_worker/runtime.py`: passes `config.debug_capture` into `ProcessingPipeline` and supplies `pipeline.publish_debug` to `Worker.process`.
- `worker/src/boulder_frame_worker/config.py`: `debug_max_frames` and `debug_max_bytes` default to `10000` and `52428800` (50 MiB), and both require positive values.
- `worker/src/boulder_frame_worker/debug.py`: the gzip writer incrementally enforces frame/byte limits and removes partial bundles on a limit/error; field-name normalization redacts camelCase and raw-frame fields.
- `worker/src/boulder_frame_worker/pipeline.py`: enabled capture writes source-coordinate analysis-frame traces, streams a bounded mixed bundle, assigns a per-publication UUID storage key, and deletes the uploaded object if verification/finalization fails.
- `worker/src/boulder_frame_worker/worker.py`: `retain_debug_artifacts` controls only `job_scratch` cleanup; enabled capture writes phase records best-effort and calls `publish_debug` after output finalization or after a failed phase, before that failure is persisted. Publication failures are warnings and cannot change the job outcome.
- `worker/src/boulder_frame_worker/debug.py`: schema-v1 deterministic gzip JSONL writer; canonical records; header, generic stage, and source-coordinate serialization; recursive credential/URL/raw-media redaction.
- `worker/src/boulder_frame_worker/repository.py`: lease-guarded `finalize_debug` requires non-empty `application/gzip` and canonical `private/debug/{project_id}/{job_id}/{debug_uuid}.jsonl.gz` keys while the job is nonterminal.
- `worker/src/boulder_frame_worker/storage.py`: debug-enabled readiness requires all four S3 public-access blocks.
- `worker/src/boulder_frame_worker/evaluation.py`: bounded streaming schema-v1 bundle loading, human-review/source-coordinate validation, no-telemetry annotation insufficiency, metrics, versioned aggregates, and first-failure classifications. Renderer mapping is assessed only when independently verified.
- `worker/src/boulder_frame_worker/media.py` and `worker/src/boulder_frame_worker/pipeline.py`: current output is source-frame crop annotation, not a cropped/scaled 1080p reframe.

## Documented Integration

The private bundle deliberately combines `stage_start`, `stage_end`, source-coordinate `frame`, and
`render_summary` records. The evaluator streams and evaluates frame records only, adding an
insufficient result for each reviewed annotation without telemetry. Debug artifact publication is
best-effort: it runs after successful output finalization or after a failed phase while the lease is
active, and cannot alter the job result.

## Verification

- No configured documentation link-check command was found in repository scripts or build files.
- A repository-wide internal-link scan found three pre-existing absolute-path links in
  `docs/ref/asynq/README.md` (`/tools/asynq/README.md#pause`, `/tools/asynq/README.md`, and
  `/CONTRIBUTING.md`). They are outside this feature's documentation changes.
- Final refresh checks: focused internal Markdown references passed, both worker configuration examples
  passed `jq empty`, and `git diff --check` passed.
