# Crop Hysteresis And Smooth Transitions

## Goal

Prevent detector-box jitter from producing visible zoom pumping while making real framing changes
accelerate and brake smoothly. Preserve profile targets, exact stationary crops, independent
scale/center hysteresis, detector containment, source/aspect bounds, and safe widening on misses.

The earlier `deterministic-v2` / `w0.2.2` release introduced independent gates. This approved
`deterministic-v3` / `w0.2.3` follow-on keeps those thresholds unchanged and replaces per-frame
exponential smoothing with timestamp-based speed/acceleration-limited motion.

## Design

### Profile target remains the centerline

Keep the existing target fractions:

| Profile | Target detector height / crop height |
| --- | ---: |
| `tight` | `0.60` |
| `balanced` | `0.50` |
| `safe` | `0.40` |
| `full_movement` | `0.33` |

The profile still computes the unconstrained desired height as `detection.height / target_height_fraction`. The deadband decides whether that new desired value is significant enough to move the existing crop.

### Scale Schmitt trigger

Use the previous final crop as the visual reference:

```text
observed_fraction = detection.height / previous_crop.height
relative_error = observed_fraction / target_height_fraction - 1
```

Maintain a causal `scale_adjusting` state:

- When idle and at rest, keep the previous width/height exactly unchanged while `abs(relative_error) <= 0.05`.
- Enter adjustment only when `abs(relative_error) > 0.05`.
- While adjusting, target `log(detection.height / target_height_fraction)`, subject to source/aspect limits.
- Close the gate once `abs(relative_error) <= 0.02`; brake any remaining zoom velocity before holding exactly.

The separate 5% entry and 2% exit thresholds prevent chatter. For `balanced`, entry corresponds to
leaving 47.5%–52.5% detected height and closure to entering 49%–51%. Closure is a gate decision,
not an instant crop stop or a guarantee that post-settling occupancy remains in that inner interval.

Do not compare against the immediately preceding detector height. Comparing against the current crop prevents gradual sub-threshold detector changes from ratcheting the crop every frame; accumulated real scale change eventually exits the 5% band.

### Center Schmitt trigger

Apply an independent deadband to the source-clamped desired center:

```text
x_error = (desired_center.x - previous_center.x) / previous_crop.width
y_error = (desired_center.y - previous_center.y) / previous_crop.height
```

Maintain `center_adjusting` independently:

- Hold the preceding center when idle and at rest while both absolute errors are at most 1%.
- Enter pan adjustment when either error exceeds 1%.
- While adjusting, move toward the source-clamped center with source-normalized motion limits.
- Close the gate when both errors are at most 0.4%; brake residual pan velocity, then hold exactly.

Scale and center state must be independent: a real zoom must not force a pan, and detector-center jitter must not change crop dimensions.

### Timestamp-based transitions

`FrameMeasurement` contains detector bounds, a required integer `timestamp_ms`, and confidence
defaulting to zero. Reject timestamps that do not strictly increase, including on missed detections.
Use elapsed seconds between measurements; do not assume a fixed frame rate.

Motion state is velocity in log-height for zoom and source-normalized center coordinates for pan.
Persist these fixed limits alongside the unchanged four gate thresholds:

| Key | Value | Units |
| --- | --- | --- |
| `zoom_max_speed` | `0.5` | log-height / second |
| `zoom_max_acceleration` | `1.0` | log-height / second² |
| `pan_max_speed` | `0.25` | source dimension / second, per axis |
| `pan_max_acceleration` | `0.5` | source dimension / second², per axis |

Integrate acceleration, capped-speed cruise, and stopping-distance braking over actual elapsed time.
Preserve velocity when a new detector box retargets motion: never restart an animation each frame.
An abrupt target change inside the current stopping distance may require crossing the target before
reversal. When a gate closes, brake to zero over a short settling interval rather than resetting
velocity immediately. Once at rest, hold the exact preceding crop components. Pan and zoom remain
independent; pan gates use crop dimensions even though pan velocity uses source dimensions.

### Decision order

For every detected frame:

1. Compute the profile-derived desired crop and clamp it to source/aspect bounds.
2. Apply independent scale/center hysteresis gates.
3. Advance active timestamp-based motion or idle braking/settling.
4. Build and clamp the candidate crop.
5. Run the existing containment logic.

Containment remains authoritative. If a crop would exclude the current detector box, `_contain`
may expand or shift it immediately, overriding deadbands and motion limits. Source/aspect
corrections and containment reset only the affected component velocities. If containment is
impossible, preserve the largest valid source/aspect crop and report `source_aspect_limited`.

For a missed detection, bypass/reset both gates, cancel pan and inward zoom velocity immediately,
and target the full valid source-aspect height with timestamp-based zoom limits. Preserve outward
zoom velocity. The center holds unless widening requires source-bound clamping; never extrapolate
an athlete position for a close crop. On reacquisition, compare against the widened previous crop.

The first detected frame has no prior visual reference and uses the profile-derived crop directly;
a first-frame miss uses the full valid source-aspect crop.

### Diagnostics and versioning

Retain existing trace fields rather than adding animation-state telemetry:

- `observed_height_fraction`
- `scale_relative_error`
- `scale_deadband_applied`
- `scale_adjusting`
- `center_error_x_fraction`
- `center_error_y_fraction`
- `center_deadband_applied`
- `center_adjusting`

`scale_deadband_applied` and `center_deadband_applied` mean the respective gate is idle; they do not
promise an instant stop. `smoothing_applied` includes residual braking/settling. Keep containment
and source/aspect diagnostics separate. Actions remain `deadband_hold`, `smoothed`,
`containment_override`, `source_aspect_limited`, and `widen_on_miss`.

Publish as `deterministic-v3` / `w0.2.3` and persist all eight constants in immutable backend planner
and pipeline debug configuration. Controller, pipeline version, and each constant must separate job
hashes. Drain old queued/leased jobs on old workers, confirm zero Redis pending deliveries, stop old
workers, then deploy backend and worker together with the shared new version before resuming
submissions. Runtime checks model compatibility, not pipeline compatibility; never roll overlapping
versions or retry/republish an old job UUID to request new behavior.

## Files To Change

- `worker/src/boulder_frame_worker/planner.py`: preserve hysteresis and add timestamp/velocity state, motion phases, settling, and safety reconciliation.
- `worker/tests/test_planner.py`: cover exact stationary holds, unchanged thresholds, speed/acceleration limits, braking, timestamp validation, retargeting, settling, misses, and safety.
- `worker/src/boulder_frame_worker/debug.py` and `worker/tests/test_debug.py`: retain trace schema and describe settling with existing smoothing evidence.
- `worker/src/boulder_frame_worker/pipeline.py`: supply frame timestamps and publish `deterministic-v3` with all eight constants.
- `worker/tests/test_pipeline.py` and `worker/tests/test_evaluation.py`: migrate measurement timestamps and verify frame-aligned crop behavior.
- `backend/domain/models.go` and its focused tests: persist immutable configuration and defend version/each-constant cache separation.
- `.env.example` and `docs/dev/development.md`: bump the pipeline version used for the clean cutover.
- `docs/architecture/offline-reframing-mvp.md`: update the authoritative framing contract with deadband, hysteresis, and safety precedence.
- `docs/specs/worker/measurements-and-planner.md`: document formulas, thresholds, state transitions, and diagnostics.
- `docs/specs/worker/debug-telemetry-and-evaluation.md`: document existing trace fields' gate/settling semantics.
- `docs/specs/backend/http-api.md`: update the immutable planner controller/configuration example.

No frontend control or public API field is needed. Thresholds and motion limits remain algorithm constants.

## Steps

### Plan

1. Retain 5%/2% scale and 1%/0.4% center hysteresis unchanged.
2. Preserve profile fractions, aspect handling, clamping, containment, and no position extrapolation.
3. Specify timestamp motion, braking, settling, and immutable-version cutover before changing output.

### Implement

1. Require increasing measurement timestamps and migrate every caller.
2. Carry independent gate states and zoom/pan velocities through the causal planner.
3. Integrate speed/acceleration-limited motion, preserving velocity on retarget and braking on gate closure.
4. Apply safety corrections after candidate motion and cancel unsafe motion on misses.
5. Cut backend/default and debug configuration over to `deterministic-v3` / `w0.2.3` with eight constants.
6. Update focused architecture, worker, backend, development documentation, and indexes.

### Test

1. Prove stationary in-band sequences keep byte-for-byte equal crops once at rest.
2. Prove unchanged inclusive hold/exit boundaries, no gate chatter, and accumulated change triggering.
3. Exercise timestamp-based log-height and source-normalized pan speed/acceleration limits.
4. Exercise braking, retargeted velocity preservation, reversal, and finite exact settling after closure.
5. Compare equivalent elapsed-time motion across frame rates and reject non-increasing timestamps.
6. Prove containment/source-aspect safety overrides limits and reconciles only affected velocities.
7. Prove misses widen without position extrapolation, cancel inward zoom, and allow reacquisition.
8. Preserve portrait/landscape bounds, requested aspect, and all four profile fractions.
9. Prove pipeline/controller and every immutable constant separate cache hashes.
10. After integration, run focused worker/domain tests and project checks once; inspect a rendered
    permitted motion fixture and its crop-path diagnostics for visible pan/zoom continuity.

## Risks

- Wide hysteresis bands delay response; narrow bands expose jitter. The unchanged thresholds and new
  motion limits require fixture-based visual validation.
- Sudden retargets can cross a newly moved target while braking; preserving velocity avoids animation
  resets but cannot guarantee no overshoot after arbitrary detector changes.
- Containment can still move the crop abruptly for a noisy box near an edge. Suppressing that override would risk clipping the selected athlete and is intentionally out of scope.
- A deadband suppresses detector noise but cannot correct wrong-person association or large erroneous boxes.
- The center gate may hold a slightly off-center athlete by design. Its threshold is normalized to crop dimensions so behavior is resolution-independent.
- Existing cached crop paths must not be reused across planner versions. The pipeline-version cutover and configuration hash must force a new job/output.