# Compose Runtime

## Services

| Service | Role | Local host exposure |
| --- | --- | --- |
| `frontend` | Vite development server | `127.0.0.1:5173` |
| `backend` | Go API | `127.0.0.1:8080` |
| `worker` | Python worker process | None |
| `postgres` | Durable metadata | None |
| `redis` | asynq coordination | None |
| `objectstore` | MinIO S3 API | `127.0.0.1:9000` for browser-direct signed URLs |
| `objectstore-init` | Idempotent bucket/user/lifecycle/CORS setup | None |
| `caddy` | Online HTTPS routing | Ports 80/443 in online profile |

All services use the internal `private` network. Online Compose removes internal service ports and adds restart policies, resource limits, persistent Caddy volumes, and versioned application images.

## Startup Ordering

PostgreSQL, Redis, and MinIO expose health checks. The API and worker wait for healthy dependencies and successful `objectstore-init`. The frontend waits for a healthy API. The online Caddy service waits for healthy frontend/API containers.

## Object Storage

The backend uses:

- `S3_ENDPOINT=http://objectstore:9000` for container-to-container operations.
- `S3_PRESIGN_ENDPOINT=http://localhost:9000` for URLs consumed by the local host browser.

MinIO is published only on loopback locally. `minio-cors.json` permits local frontend origins for signed `PUT`, `GET`, and `HEAD` operations. The initializer creates the application user, private bucket, lifecycle policy, and CORS policy idempotently.

## Persistence

Named volumes:

- `postgres-data`
- `redis-data`
- `objectstore-data`
- `worker-scratch`
- `caddy-data`
- `caddy-config`

`docker compose down` preserves data. `down -v` is local-only destructive maintenance and must not be run online.

## Configuration

`infra/.env.example` is the non-secret infrastructure template. The Compose anchor supplies the
deployment values used to expand placeholders in each module's `conf/config.json`; application
services read those JSON files rather than `.env`. Online deployments must replace credentials and
use explicit image tags.

## Online Boundary

The current Caddyfile serves `/healthz` and returns `403` for application routes until authentication and authorization are implemented. HTTPS termination is configured, but HTTPS alone is not an access-control mechanism.
