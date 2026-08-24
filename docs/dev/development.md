# Development

## Scope

Docker Compose starts the repository modules: the frontend, Go API, and Python worker. PostgreSQL,
Redis, and S3-compatible object storage are external dependencies and are not provisioned here.

## Setup

Copy the non-secret template and replace the external service values:

```sh
cp .env.example .env
```

Keep `.env` out of version control. Configure the external database, Redis Streams transport, and
object-storage bucket separately, including credentials, CORS, and retention policy. The API writes
to stream `boulder-frame:jobs`; workers consume group `boulder-frame:job-processors`.

When those dependencies run on the Docker host, containers must use
`host.docker.internal` rather than `localhost` in their URLs. For example, use
`postgres://user:password@host.docker.internal:5432/database?sslmode=disable`. Compose maps that
name to Docker's host gateway for the backend and worker. `localhost` from either container refers
to that container, not the host.

The worker requires PostgreSQL and Redis URLs plus a stable `WORKER_ID`; `.env.example` provides a
local value. Its stream settings include an optional `stream_consumer` override, read block interval,
pending-entry reclaim idle time, heartbeat interval, and concurrency. Set unique consumer identities
for concurrent worker processes. PostgreSQL remains the job-lease authority; Redis consumer-group
pending state is only delivery coordination.

Worker `conf/config.json` and `conf/config.dev.json` set VFR normalization limits:
`normalization_max_source_bytes` defaults to 1 GiB and `normalization_timeout_seconds` to 1,800.
The API upload ceiling is 2 GiB; the lower VFR cap reserves scratch capacity for the immutable download
and temporary CFR derivative. Lower either value for a deployment with less disk or processing budget.

## Start Modules

Start the complete module set with:

```sh
docker compose up --build
```

Run detached:

```sh
docker compose up --build -d
```

The worker is built as `linux/amd64`, including on Apple Silicon hosts. The pinned ONNX Runtime
deployment target is x86_64; Docker/Podman must have x86_64 emulation available.

The application binds to all host interfaces for trusted-network access. With the configured values
from `.env`, the endpoints are:

- Web app: `${WEB_BASE_URL}`
- Go API: `${API_BASE_URL}`
- API health: `${API_BASE_URL}/healthz`

Allow TCP ports `5173` and `8080` through the host firewall for remote access. This Compose setup
does not provide TLS or authentication; use it only on a trusted network.

Run migrations explicitly against the configured external PostgreSQL database:

```sh
docker compose run --rm backend migrate up
```

Inspect or stop the modules:

```sh
docker compose ps
docker compose logs -f backend worker
docker compose down
```

The worker scratch directory and frontend dependency cache are local Compose volumes. Source videos,
outputs, and durable metadata remain in their configured external services.
