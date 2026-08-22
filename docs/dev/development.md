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

The worker requires PostgreSQL and Redis URLs plus a stable `WORKER_ID`; `.env.example` provides a
local value. Its stream settings include an optional `stream_consumer` override, read block interval,
pending-entry reclaim idle time, heartbeat interval, and concurrency. Set unique consumer identities
for concurrent worker processes. PostgreSQL remains the job-lease authority; Redis consumer-group
pending state is only delivery coordination.

## Start Modules

Start the complete module set with:

```sh
docker compose up --build
```

Run detached:

```sh
docker compose up --build -d
```

The worker is built as `linux/amd64`, including on Apple Silicon hosts. The pinned MediaPipe wheel
does not support Linux ARM64; Docker/Podman must have x86_64 emulation available.

The local endpoints are:

- Web app: `http://localhost:5173`
- Go API: `http://localhost:8080`
- API health: `http://localhost:8080/healthz`

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

## Deployed Server

We have deploy infras like redis and database on root@76.13.185.64 with pass `+vc4j2VIUIAlygsd`
