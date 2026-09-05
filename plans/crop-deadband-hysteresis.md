# Crop Deadband And Hysteresis

## Goal

Prevent detector-box jitter from producing visible zoom pumping while preserving the selected profile's target athlete proportion and the existing safety guarantees.

For a stable detection sequence, small detector-height changes must leave the final crop width and height exactly unchanged. A genuine sustained scale change must still move the crop toward the profile target without oscillating at the threshold. Detector containment, source bounds, and missed-detection widening remain higher-priority safety behavior.

A scale deadband alone cannot guarantee a completely still frame because detector-center jitter can still change `x` and `y`. The recommended design therefore uses independent scale and center gates. Scale gating is required for the reported defect; center gating completes the stable-crop behavior.

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

- When idle, keep the previous crop width and height exactly unchanged while `abs(relative_error) <= 0.05`.
- Enter adjustment only when `abs(relative_error) > 0.05`.
- While adjusting, retain the existing `height_alpha = 0.25` transition toward `detection.height / target_height_fraction`.
- Stop adjusting and latch the current crop size once `abs(relative_error) <= 0.02`.

The separate 5% entry and 2% exit thresholds provide hysteresis, so measurements near one boundary cannot alternate between hold and adjust. For `balanced`, the crop holds while the detected athlete occupies 47.5% to 52.5% of crop height, then settles back inside 49% to 51% after a real zoom transition.

Do not compare against the immediately preceding detector height. Comparing against the current crop prevents gradual sub-threshold detector changes from ratcheting the crop every frame; accumulated real scale change eventually exits the 5% band.

### Center Schmitt trigger

Apply an independent deadband to the source-clamped desired center:

```text
x_error = (desired_center.x - previous_center.x) / previous_crop.width
y_error = (desired_center.y - previous_center.y) / previous_crop.height
```

Maintain `center_adjusting` independently:

- Hold the preceding center while both absolute errors are at most 1% of the crop dimension.
- Enter pan adjustment when either error exceeds 1%.
- While adjusting, retain `center_alpha = 0.35`.
- Stop and latch when both errors are at most 0.4%.

Scale and center state must be independent: a real zoom must not force a pan, and detector-center jitter must not change crop dimensions.

### Decision order

For every detected frame:

1. Compute the profile-derived desired crop and clamp it to source/aspect bounds.
2. Apply scale hysteresis to choose held or adjusted width/height.
3. Apply center hysteresis to choose held or adjusted center.
4. Build and clamp the candidate crop.
5. Run the existing containment logic.

Containment remains authoritative. If a held crop would exclude the current detector box, `_contain` may expand or shift it immediately. This is an intentional safety override, not jitter suppression failure. `source_aspect_limited` behavior also remains unchanged.

For a missed detection, bypass both deadbands and retain the existing widening behavior. Reset both adjustment states to idle after applying the miss crop. On reacquisition, compare the new detection against the widened previous crop; a material error naturally resumes adjustment.

The first detected frame has no prior visual reference and therefore uses the existing profile-derived crop directly.

### Diagnostics and versioning

Add trace evidence rather than hiding the controller decision:

- `observed_height_fraction`
- `scale_relative_error`
- `scale_deadband_applied`
- `scale_adjusting`
- `center_error_x_fraction`
- `center_error_y_fraction`
- `center_deadband_applied`
- `center_adjusting`

Keep containment and source/aspect diagnostics separate. Use action values that distinguish `deadband_hold`, `smoothed`, `containment_override`, `source_aspect_limited`, and `widen_on_miss`.

This changes processing behavior. Publish it as `deterministic-v2` and bump the configured pipeline version rather than silently changing output for jobs identified as `deterministic-v1`/`w0.2.1`. Persist the threshold values in planner/debug configuration so an output remains explainable.

## Files To Change

- `worker/src/boulder_frame_worker/planner.py`: add independent scale/center hysteresis state, decision ordering, and trace fields.
- `worker/tests/test_planner.py`: cover exact holds, threshold crossings, hysteresis, accumulated changes, independent center/scale behavior, containment priority, misses, reacquisition, source edges, and every profile.
- `worker/src/boulder_frame_worker/debug.py`: serialize the new bounded finite diagnostics.
- `worker/tests/test_debug.py`: verify serialization and safe handling of diagnostic values.
- `worker/src/boulder_frame_worker/pipeline.py`: identify the controller as `deterministic-v2` and include thresholds in planner diagnostics.
- `worker/tests/test_pipeline.py`: verify persisted crop paths contain identical consecutive rectangles inside the deadband and remain frame-aligned.
- `backend/domain/models.go` and its focused tests: persist the new planner controller/version and fixed threshold configuration in immutable job configuration.
- `.env.example` and `docs/dev/development.md`: bump the pipeline version used for the clean cutover.
- `docs/architecture/offline-reframing-mvp.md`: update the authoritative framing contract with deadband, hysteresis, and safety precedence.
- `docs/specs/worker/measurements-and-planner.md`: document formulas, thresholds, state transitions, and diagnostics.
- `docs/specs/worker/debug-telemetry-and-evaluation.md`: document the additive trace fields.
- `docs/specs/backend/http-api.md`: update the immutable planner controller/configuration example.

No frontend control or public API field is needed. Thresholds remain algorithm constants, not user-tunable job inputs.

## Steps

### Plan

1. Treat 5%/2% scale and 1%/0.4% center bands as initial deterministic-v2 defaults.
2. Preserve existing profile fractions, aspect handling, clamping, containment, and missed-detection policies.
3. Make the diagnostic and immutable-version cutover explicit before changing output behavior.

### Implement

1. Split the current combined `_smooth` operation into independently gated height and center decisions.
2. Carry `scale_adjusting` and `center_adjusting` through the causal planning loop.
3. Apply containment after both gates and reset gate state on missed detections.
4. Extend trace serialization and planner configuration without compatibility aliases.
5. Cut backend/default configuration over to `deterministic-v2` and the new pipeline version.
6. Update focused architecture, worker, backend, and development documentation.

### Test

1. Prove detections fluctuating within the scale band produce byte-for-byte equal crop width and height.
2. Prove center fluctuations within the center band produce an entirely identical `CropRect` when scale is also held.
3. Prove a change beyond the outer threshold begins bounded adjustment and does not stop until it reaches the inner threshold.
4. Prove alternating values around the outer boundary do not chatter after the controller has latched.
5. Prove gradual accumulated subject-scale movement eventually crosses the band and adjusts.
6. Prove containment overrides a deadband hold only when the detector would otherwise be clipped.
7. Prove misses widen and reacquisition returns smoothly without position extrapolation.
8. Prove portrait/landscape source limits and all four profile target fractions remain valid.
9. Run the focused worker tests, backend domain tests, Ruff, mypy, documentation-link validation, and `git diff --check`.
10. Render a permitted jitter fixture and inspect crop-path diagnostics plus the actual output for removed zoom/pan chatter.

## Risks

- A threshold that is too wide makes genuine approach/recede motion react late; one that is too narrow leaves detector jitter visible. The proposed defaults require fixture-based visual validation.
- Frame-count-based exponential coefficients remain frame-rate dependent. This change does not introduce time-normalized smoothing.
- Containment can still move the crop abruptly for a noisy box near an edge. Suppressing that override would risk clipping the selected athlete and is intentionally out of scope.
- A deadband suppresses detector noise but cannot correct wrong-person association or large erroneous boxes.
- The center gate may hold a slightly off-center athlete by design. Its threshold is normalized to crop dimensions so behavior is resolution-independent.
- Existing cached crop paths must not be reused across planner versions. The pipeline-version cutover and configuration hash must force a new job/output.