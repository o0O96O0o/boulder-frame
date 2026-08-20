# Worker Model Contract Alignment

## Contract States

| Runtime state | Startup behavior | Job behavior |
| --- | --- | --- |
| Local sentinel `MODEL_VERSION=unset-until-pinned` | API and worker normalize it to `unconfigured`; startup is allowed. | A matching immutable `configuration.model_version=unconfigured` reaches terminal `model_unavailable`. |
| W0.1 configured without verified artifacts or decoder dependencies | Worker runtime composition fails and the process does not consume jobs. | No job is claimed by that worker. |
| Provisioned W0.1 baseline | Runtime verifies the two manifest artifacts and loads detector, pose, and frame reader before startup. | A claimed job must have the exact active `configuration.model_version`; a mismatch is terminal `model_unavailable` before a stage handler or media/CV work. |

## Implementation Evidence

- `worker/src/boulder_frame_worker/config.py` normalizes the local sentinel.
- `backend/config/config.go` performs the same normalization so locally created immutable jobs match the safe worker state.
- `worker/src/boulder_frame_worker/runtime.py` rejects unsupported configured versions and raises `RuntimeUnavailable` when configured W0.1 artifacts or decoder dependencies cannot load.
- `worker/src/boulder_frame_worker/worker.py` compares the claimed immutable model version to the active runtime version. For a queued mismatch it first records the valid `validating` transition, then terminally fails without invoking a stage handler.
- Authoritative documentation now distinguishes all three states in the repository README, architecture documents, Redis Streams contract, specs index, and worker runtime/model specifications.

## Verification

Executed on 2026-08-20:

```text
worker:  pytest
result:  87 passed, 1 skipped

backend: go test ./...
result:  all packages passed

repo:    git diff --check
result:  passed
```
