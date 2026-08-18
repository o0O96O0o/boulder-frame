# Infrastructure Implementation Summary

Implemented I1.1 through I1.3 within `infra/` only.

## Delivered

- `compose.yaml` defines local frontend, backend, worker, PostgreSQL, Redis, MinIO, and idempotent MinIO bucket initialization on an internal `private` network.
- Local-only loopback ports expose the frontend (`5173`) and API (`8080`); PostgreSQL, Redis, MinIO, and the worker have no host ports.
- Persistent named volumes cover PostgreSQL, Redis, object storage, worker scratch, and Caddy state/configuration.
- Health checks and health-based startup ordering cover all dependency edges.
- `compose.online.yaml` switches application services to explicit versioned image variables, removes bind mounts and local ports, adds `online` profiles, restart policies, resource limits, and Caddy TLS routing.
- `Caddyfile` serves only `GET /healthz`; all browser and API access is explicitly blocked with HTTP 403 until authentication is implemented.
- `.env.example` separates MinIO root credentials from the S3 application credentials and is ignored when copied to `.env`.
- MinIO initialization creates/reuses the application user, creates the configured bucket idempotently, and reapplies an object lifecycle policy based on `ASSET_RETENTION_DAYS`.
- Local and online operational scripts provide startup, migration, inspection, logs, PostgreSQL dump/restore, updates, and a local-only destructive reset. The online script deliberately has no reset command.

## Validation

Run from `/Users/didi/boulder-frame` on 2026-08-18:

```sh
docker compose --env-file infra/.env.example -f infra/compose.yaml config --quiet
docker compose --env-file infra/.env.example -f infra/compose.yaml -f infra/compose.online.yaml --profile online config --quiet
```

Both commands passed.

Additional checks passed:

- Ruby parsed both Compose YAML files.
- `sh -n infra/bin/local` and `sh -n infra/bin/online` passed.
- Rendered Compose topology assertions confirmed all local services exist, online PostgreSQL/Redis/MinIO/worker services publish no host ports, and Caddy publishes HTTP/HTTPS.
- Both operational scripts are executable.

`caddy` is not installed on the host, so native Caddy validation was unavailable. A containerized `caddy validate` attempt returned exit code 125 without diagnostic output; it did not affect the successful Docker Compose configuration validations.

The application images intentionally include runnable placeholders because the frontend, backend, and worker service scaffolds do not yet exist. Replace their placeholder branches with service entrypoints as those owners implement S0.2/B1.1/F1.1/W1.1.
