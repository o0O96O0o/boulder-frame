# Analysis Observability Evidence

- Scope: worker-only bounded detector-association evidence in optional debug telemetry and measurement review.
- Association behavior: the selected frame always uses the immutable user tap (`reference_kind: tap`); non-selected frames use the most recent raw pose root (`reference_kind: prior_pose_root`), initially falling back to the tap. Containment precedes nearest-center selection.
- Bound: `MAX_ASSOCIATION_CANDIDATES = 32`; deterministic retention always includes the selected candidate.
- Capture boundary: `ProcessingPipeline.debug_capture` explicitly controls analyzer evidence capture. Disabled capture does not construct or retain `AssociationEvidence` or candidate records; enabled capture retains bounded evidence for the private trace/review.
- Privacy: source-coordinate metadata only; no pixels, biometric identity data, arbitrary model payloads, external models, or crop/planning behavior changes.
- Identity: review annotations name the recorded reference kind and state that evidence documents deterministic visual association only. Human annotation/evaluation is required for identity correctness.
- Focused verification: `uv run pytest tests/test_measurement.py tests/test_debug.py tests/test_review.py tests/test_pipeline.py` completed with `58 passed, 4 skipped`.
- Full verification: `uv run pytest` completed with `238 passed, 5 skipped`; `uv run ruff check .`, `uv run ruff format --check .`, and `git diff --check` passed. No repository documentation link checker is configured.
