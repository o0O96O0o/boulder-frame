# Boulder Frame

Boulder Frame turns a wide sports recording into a smooth, close-up video that keeps a selected athlete's complete movement in frame.

The first product is an offline, single-athlete reframing service. The approved implementation specification is in [docs/architecture/offline-reframing-mvp.md](docs/architecture/offline-reframing-mvp.md).

## Status

The frontend, Go API, worker pipeline, and Docker Compose module startup are implemented. Detailed component specifications are indexed in [docs/specs/README.md](docs/specs/README.md). PostgreSQL, Redis, and object storage remain external dependencies. Local `.env.example` keeps `MODEL_VERSION=unset-until-pinned`, which is normalized to the safe unconfigured state: the worker starts and matching jobs terminate with `model_unavailable`. To process video, run `./deploy/bin/local prepare-model` to provision and verify the W0.2 detector in `MODEL_DIR`, then set `MODEL_VERSION=w0.2-ssd-mobilenetv1-12-onnx-detector-only-1`; a configured baseline with a missing or invalid artifact prevents worker startup, and a worker rejects any job whose immutable `configuration.model_version` differs from its active runtime version.
