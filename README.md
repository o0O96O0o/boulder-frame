# Boulder Frame

Boulder Frame turns a wide sports recording into a smooth, close-up video that keeps a selected athlete's complete movement in frame.

The first product is an offline, single-athlete reframing service. The approved implementation specification is in [docs/architecture/offline-reframing-mvp.md](docs/architecture/offline-reframing-mvp.md).

## Status

The frontend, Go API, worker pipeline, and Docker Compose module startup are implemented. Detailed component specifications are indexed in [docs/specs/README.md](docs/specs/README.md). PostgreSQL, Redis, and object storage remain external dependencies. Local `.env.example` keeps `MODEL_VERSION=unset-until-pinned`, which is normalized to the safe unconfigured state: the worker starts and matching jobs terminate with `model_unavailable`. To process video, run `./deploy/bin/local prepare-model` to provision and verify the AGPL-3.0-approved YOLO26n CPU ONNX detector, then set `MODEL_VERSION=w0.2-yolo26n-onnx-detector-only-1` and `PIPELINE_VERSION=w0.2.7`. The `lookahead-v2` full-shot planner reduces pan travel within a 5%-of-seed-crop deadzone while preserving sampled containment and causal crop dimensions. A missing or invalid artifact prevents configured worker startup, and immutable job model versions must match the active runtime. Existing deployments must [drain old jobs and deploy backend and worker together](docs/dev/development.md#start-modules); never rewrite or retry old jobs as a migration.
