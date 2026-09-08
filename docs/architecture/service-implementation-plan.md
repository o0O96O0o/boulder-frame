# Service Implementation Plan

This document records the implemented detector-only MVP service contract and its verification gates.
The authoritative product behavior is [Offline Reframing MVP](offline-reframing-mvp.md).

## Implemented Services

| Service | Responsibility | Contract boundary |
| --- | --- | --- |
| Frontend | Upload, normalized athlete tap, aspect/profile selection, job polling, download, terminal review | REST JSON and short-lived signed URLs only |
| Go API | Validation, authorization boundary, immutable job metadata, PostgreSQL, Redis dispatch, artifact/evaluation projection | Does not decode, infer, or render |
| Python worker | Source validation, VFR normalization, ONNX person detection, detector-box framing, FFmpeg rendering, artifact finalization | Claims PostgreSQL lease before durable work |

```mermaid
flowchart LR
  B[Browser] --> API[Go API]
  API --> DB[(PostgreSQL)]
  API --> Q[(Redis Streams)]
  B --> S[(Private object storage)]
  Q --> W[Python worker]
  W --> S
  W --> DB
```

## Cross-Service Contract

- Job configuration is immutable and includes source asset, target selection, output settings,
  pipeline version, model version, and planner configuration. The current default is `w0.2.6` with
  `lookahead-v1`, `deterministic-v3` seed, `scipy-highs-ds`, full-shot scope, sampled-detection
  containment policy, tolerance `1e-8`, unchanged hysteresis/motion constants, and configurable
  `detection_sample_fps`. Every key participates in the job hash.
- Profiles are `tight`, `balanced`, `safe`, `full_movement`, with target detected-athlete height
  fractions `.60`, `.50`, `.40`, `.33`. Zoom, scale hysteresis, miss widening, and source/aspect
  sizing remain causal; final dimensions exactly match the deterministic seed.
- Full-shot sparse per-axis pan optimization contains accepted sampled boxes when geometrically
  feasible and may move before a later displacement. Held targets are guidance only and may leave
  the crop. Future observations constrain the camera, never interpolate/predict athlete positions.
  Source bounds stay hard; unavoidable speed then acceleration excess is minimized and reported.
- Validate the exact immutable planner contract before cached replay and validate every optimum,
  geometry, and kinematic result. Solver failure is terminal analyzing `internal` with
  `"Video framing could not be planned."`, no causal fallback, and no committed analysis artifacts.
- Deploy backend and worker together through the [drained cutover](../dev/development.md#start-modules);
  never rewrite/retry old jobs or reuse old crop paths for new behavior. There is no generic
  claim-time pipeline-version check; exact planner parsing is not a rolling-deployment protocol.
- The selected model is `w0.2-yolo26n-onnx-detector-only-1`; configuration contains no
  additional CV state beyond detector framing.
- The worker review phases are ordered `detection`, `framing`, `render`. Phase roles are exactly
  `debug_detection`, `debug_framing`, and `debug_render`; telemetry and manifest remain
  `debug_telemetry` and `debug_manifest`.
- Migration `003_phase_evaluation.sql` retains the non-destructive legacy `debug` to
  `debug_telemetry` conversion. Migration `004_detector_only_review_roles.sql` removes retired
  review links and constrains new artifact roles to the W0.2 set. It leaves retired debug objects
  for configured object-storage lifecycle cleanup rather than deleting potentially shared assets.
- Review media, manifest, and telemetry are optional diagnostics. Required output upload/finalization,
  state handling, VFR normalization, and FFmpeg validation contracts are unchanged.

## Verification Gates

1. Backend: `go test ./...`, including manifest ordering, artifact role validation, migration checks,
   and authorized evaluation projection.
2. Worker: detector-framing, early pan, sampled-only containment, held-target policy, minimal excess,
   deterministic sparse optimization, solver failure, unchanged seed dimensions, model/runtime,
   telemetry, and media tests; synthetic full-rate look-ahead smoke with identical repeated crops.
3. Frontend: typecheck and tests validating the three-phase response schema, media URL requirements,
   phase switching, fixed profile copy, and analyzing label.
4. Documentation: validate internal Markdown links where tooling is available and run `git diff --check`.
