# E1/E2 Evaluation Evidence

Implemented an isolated stdlib/dataclass evaluation layer in
`worker/src/boulder_frame_worker/evaluation.py`, reconciled with the canonical
writer in `worker/src/boulder_frame_worker/debug.py`.

- Parses schema-v1 gzip JSONL debug bundles emitted by `DebugBundleWriter`:
  `record_type`, `debug_bundle_header` fields (`source_metadata`,
  `planner_config`, `model_manifest`), and complete generic `frame` records.
- Accepts a source identity from `source_metadata.source_id` or `.sha256` and
  display dimensions from `display_width`/`display_height`.
- Validates versioned permitted manifests and independently human-reviewed,
  source-coordinate annotations; rejects VFR sources, duplicate/non-monotonic
  frames, missing source identities, and out-of-bounds coordinates.
- Produces deterministic per-frame and aggregate detection/selection, pose,
  tracking recovery, crop quality, normalized camera motion, and first-failure
  metrics. Aggregate reports are segmented by pipeline/model/planner/profile
  and resolution.
- Added permitted synthetic metadata/annotation fixtures only; no raw video.

Evidence run from `worker/`:

```text
$ pytest tests/test_debug.py tests/test_evaluation.py
19 passed in 0.07s

$ ruff check src/boulder_frame_worker/evaluation.py tests/test_evaluation.py
All checks passed!

$ git diff --check
Command executed successfully
```

The existing worker virtualenv does not contain pytest or ruff, so focused tests
and lint used the available system tools. The added files also compile with the
project virtualenv Python 3.13.
