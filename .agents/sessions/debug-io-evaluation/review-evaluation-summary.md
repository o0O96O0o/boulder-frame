# Evaluation Review Blocker Evidence

Scope: `worker/src/boulder_frame_worker/evaluation.py`, its tests, and permitted
JSON fixtures only. Excluded runtime, configuration, pipeline, storage, repository,
and documentation files were not modified.

## Changes Verified

- `load_debug_bundle(path, *, max_frames)` incrementally consumes gzip JSONL,
  retains only parsed frame records, and rejects bundles over the positive caller-supplied bound.
- Source metadata retains both optional `source_id` and `sha256`; evaluation accepts either
  matching identity only when dimensions, frame rate, and VFR status match.
- Missing detections yield `selection_correct: null` and are excluded from selection precision
  and recall denominators.
- `render_mapping` is diagnosed only if frame telemetry includes
  `render.mapping_independently_verified: true`; unverified telemetry is not render-validation evidence.

## Commands And Results

Run from `worker/` on 2026-08-24:

```text
$ pytest tests/test_evaluation.py
19 passed in 0.07s

$ pytest tests/test_debug.py tests/test_evaluation.py
36 passed in 0.12s

$ ruff check src/boulder_frame_worker/evaluation.py tests/test_evaluation.py
All checks passed!

$ ruff format --check src/boulder_frame_worker/evaluation.py tests/test_evaluation.py
2 files already formatted

$ git diff --check -- worker/src/boulder_frame_worker/evaluation.py worker/tests/test_evaluation.py worker/tests/evaluation
Command executed successfully
```
