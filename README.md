# Boulder Frame

Boulder Frame turns a wide sports recording into a smooth, close-up video that keeps a selected athlete's complete movement in frame.

The first product is an offline, single-athlete reframing service. The approved implementation specification is in [docs/architecture/offline-reframing-mvp.md](docs/architecture/offline-reframing-mvp.md).

## Status

The frontend, Go API, worker pipeline, and Docker Compose module startup are implemented. Detailed component specifications are indexed in [docs/specs/README.md](docs/specs/README.md). PostgreSQL, Redis, and object storage remain external dependencies. Local `.env.example` keeps `MODEL_VERSION=unset-until-pinned`, which is normalized to the safe unconfigured state: the worker starts and matching jobs terminate with `model_unavailable`. To process video, provision the verified W0.1 artifacts in `MODEL_DIR` and set the selected baseline version; a configured baseline with missing or invalid artifacts prevents worker startup, and a worker rejects any job whose immutable `configuration.model_version` differs from its active runtime version.
