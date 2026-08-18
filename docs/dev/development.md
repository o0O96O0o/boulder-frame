# Development Environments

## Scope

The development environment runs the complete Boulder Frame service with Docker Compose. It is self-hosted in both modes:

- **Local:** Compose runs on a developer workstation for implementation and fixture testing.
- **Online:** Compose runs on a single self-managed Linux host for shared development and acceptance testing.

The online environment is a development system, not a production deployment. It must not receive private user videos until authentication, TLS, access control, backups, and retention settings have been reviewed.

The architecture and service responsibilities are defined in [../architecture/offline-reframing-mvp.md](../architecture/offline-reframing-mvp.md).

## Service Topology

Compose manages these application and infrastructure services:

| Service | Container responsibility | Persistent data |
| --- | --- | --- |
| `frontend` | Vite/React web application and development reverse-proxy entrypoint | None; source is bind-mounted locally or built into the image online. |
| `backend` | Go HTTP API, PostgreSQL access, signed object URLs, and `asynq` dispatch | None; all durable state is externalized. |
| `worker` | Python CV pipeline, tracking, crop planning, FFmpeg rendering, and artifact upload | Temporary processing workspace only; jobs must be restart-safe. |
| `postgres` | Application metadata and job state | `postgres-data` volume. |
| `redis` | `asynq` queue and transient coordination | `redis-data` volume is optional and must not be treated as the source of job truth. |
| `objectstore` | S3-compatible source, output, and debug artifact storage | `objectstore-data` volume. |
| `caddy` | Online-only HTTPS termination and routing | `caddy-data` and `caddy-config` volumes. |

The initial implementation may use MinIO for `objectstore`. The API and worker must use the S3 API, not MinIO-specific APIs, so another S3-compatible store can replace it later.

```mermaid
flowchart LR
    B[Browser] --> C[Caddy online profile]
    B --> F[Frontend local profile]
    C --> F
    F --> A[Go backend]
    A --> PG[(PostgreSQL)]
    A --> R[(Redis)]
    A --> O[(S3-compatible object store)]
    R --> Q[asynq task]
    Q --> W[Python worker]
    W --> O
    W --> PG
```

## Repository Layout

The service directories are intentionally kept at the repository root:

```text
frontend/       Vite + React + TypeScript application
backend/        Go API and database migrations
worker/         Python worker, CV pipeline, planner, and renderer
infra/          Docker Compose files, Caddy configuration, and environment templates
docs/           Authoritative documentation
tests/          Fixtures, evaluation manifests, and integration tests
```

The Compose files and infrastructure configuration belong under `infra/`. Do not put credentials, source videos, model weights, or rendered private assets in Git.

## Required Tooling

Install on a local development machine:

- Docker Engine or Docker Desktop with Compose v2.
- Git.
- Optional: Go, Node.js, and Python only when running a service outside its container.
- Optional: NVIDIA Container Toolkit and a compatible NVIDIA GPU for worker acceleration.

The online host should be a supported 64-bit Linux machine with:

- Docker Engine and the Compose v2 plugin.
- A stable DNS name pointing to the host for HTTPS.
- At least 8 GB RAM for the baseline stack; 16 GB or more is recommended for 4K processing.
- Sufficient disk for PostgreSQL, object storage, temporary worker files, and backups.
- Optional NVIDIA GPU and container toolkit for CV workloads after the worker image supports it.

## Environment Configuration

Compose is the infrastructure boundary and may read `infra/.env`:

```sh
cp infra/.env.example infra/.env
```

The template must contain safe development defaults only. Never commit `infra/.env`.

Application services do not read `.env` files. Each module owns its JSON configuration:
`backend/conf/`, `worker/conf/`, and `frontend/conf/`, each containing `config.json` and
`config.dev.json`:

```mermaid
flowchart LR
  Env[infra/.env] --> Compose[Docker Compose]
  Compose -->|deployment variables| BackendProd[backend/conf/config.json]
  Compose -->|deployment variables| WorkerProd[worker/conf/config.json]
  BackendDev[backend/conf/config.dev.json] --> Backend[Go API]
  WorkerDev[worker/conf/config.dev.json] --> Worker[Python worker]
  FrontendDev[frontend/conf/config.dev.json] --> Frontend[Vite frontend]
  BackendProd --> Backend
  WorkerProd --> Worker
  FrontendProd[frontend/conf/config.json] --> Frontend
```

Local Compose selects each module's `config.dev.json`. Online Compose selects each module's
`config.json`; `${NAME}` placeholders in the backend and worker files are expanded from the
environment provided by Compose. Do not add service-specific `.env` files under `backend/`,
`worker/`, or `frontend/`.

Required variables:

```dotenv
COMPOSE_PROJECT_NAME=boulder-frame
APP_ENV=local

POSTGRES_DB=boulder_frame
POSTGRES_USER=boulder_frame
POSTGRES_PASSWORD=change-for-local
DATABASE_URL=postgres://boulder_frame:change-for-local@postgres:5432/boulder_frame?sslmode=disable

REDIS_URL=redis://redis:6379/0

S3_ENDPOINT=http://objectstore:9000
S3_PRESIGN_ENDPOINT=http://localhost:9000
S3_REGION=us-east-1
S3_BUCKET=boulder-frame
S3_ACCESS_KEY=change-for-local
S3_SECRET_KEY=change-for-local
S3_FORCE_PATH_STYLE=true

API_BASE_URL=http://localhost:8080
WEB_BASE_URL=http://localhost:5173
SIGNED_URL_TTL=15m
ASSET_RETENTION_DAYS=7

MODEL_VERSION=unset-until-pinned
PIPELINE_VERSION=dev
MAX_UPLOAD_BYTES=2147483648
```

Online development must replace all passwords, access keys, and signing secrets with generated values. Online `DATABASE_URL`, `S3_ENDPOINT`, and public URLs must use the host's internal service names or HTTPS route as appropriate. Do not expose PostgreSQL, Redis, or object-store admin ports to the public network.

## Local Development

### Start infrastructure and applications

After Compose files and service Dockerfiles are implemented:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml up --build
```

Run detached when desired:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml up --build -d
```

The expected local endpoints are:

- Web app: `http://localhost:5173`
- Go API: `http://localhost:8080`
- API health: `http://localhost:8080/healthz`
- MinIO/S3 API: `http://localhost:9000` for browser-direct signed uploads; the MinIO console remains internal-only.

### Run migrations

Database migrations must run as an explicit, repeatable command before API use. The migration mechanism is a backend implementation choice, but it must execute against `DATABASE_URL` from a one-shot container:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml run --rm backend migrate up
```

If migrations are included in backend startup, startup must remain idempotent and the explicit command must still be available for CI and online maintenance.

### Inspect services

```sh
docker compose --env-file infra/.env -f infra/compose.yaml ps
docker compose --env-file infra/.env -f infra/compose.yaml logs -f backend
docker compose --env-file infra/.env -f infra/compose.yaml logs -f worker
```

Use service-specific logs for failures. The worker must log job ID, stage, progress, pipeline version, model version, and structured internal error code without logging signed URLs or credentials.

### Process a fixture

Keep permitted small fixture videos under `tests/fixtures/`. Do not use private recordings in the repository or CI. From the browser, upload a fixture, select the athlete, start a `balanced` job, and verify the resulting asset. For a direct integration test:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml run --rm worker pytest
docker compose --env-file infra/.env -f infra/compose.yaml run --rm backend go test ./...
```

The exact test commands may be refined when service scaffolding is implemented, but each service must provide a container-native test command.

### Stop and reset

Stop without deleting data:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml down
```

Reset all local metadata and assets. This is destructive and should only be used for disposable local data:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml down -v
```

## Online Self-Hosted Development

### Host preparation

1. Provision a dedicated Linux host with Docker Engine and Compose v2.
2. Create a non-root deploy user with access to Docker.
3. Point a DNS name such as `dev.example.com` to the host.
4. Configure the host firewall to allow only SSH, HTTP, and HTTPS. Keep PostgreSQL, Redis, S3, and worker ports on the Compose private network.
5. Clone the repository into a controlled deployment directory.
6. Create `infra/.env` from the template and fill it with generated online-only credentials.
7. Configure the online Compose override and Caddy hostname before startup.

The online host must have a persistent backup target separate from the host disk. A second local disk is not sufficient protection against host loss.

### Online Compose profile

The Compose setup must provide an `online` profile or override that:

- Uses built, versioned images instead of development bind mounts.
- Runs the frontend behind Caddy with HTTPS.
- Does not publish PostgreSQL, Redis, MinIO, or worker ports.
- Mounts named volumes for PostgreSQL, object storage, Caddy state/configuration, and worker scratch space.
- Uses restart policies for API, worker, infrastructure, and Caddy services.
- Uses health checks and service dependency conditions so API and worker start only after required infrastructure is healthy.
- Sets resource limits appropriate for the host, especially worker concurrency and temporary disk usage.
- Uses an explicit image tag or Git revision for every application image.

Start the online environment with the repository's production-like Compose configuration:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online pull
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online up -d
```

Apply migrations as a one-shot operation:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online run --rm backend migrate up
```

Verify the deployment:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online ps
curl --fail https://dev.example.com/healthz
```

### Online updates

Updates must be performed from a known Git revision or release tag:

```sh
git fetch --tags
git checkout <approved-revision>
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online build
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online up -d
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online run --rm backend migrate up
```

Inspect logs after every update:

```sh
docker compose --env-file infra/.env -f infra/compose.yaml -f infra/compose.online.yaml --profile online logs --since=10m backend worker caddy
```

Do not run `down -v` on the online environment. Volume deletion is data loss.

## Storage and Backups

### Object storage

- Keep source, output, and debug assets in separate private prefixes or buckets.
- Use signed URLs with a short expiry, default 15 minutes.
- Configure lifecycle deletion for temporary debug assets and expired source/output assets according to `ASSET_RETENTION_DAYS`.
- Do not expose the object-store console or S3 API directly to the public internet.

### PostgreSQL

Back up metadata daily at minimum for the online environment. Test restoration into a separate database before relying on the backup. PostgreSQL is the source of truth for job configuration, status, artifact references, and error metadata.

### Object assets

Back up source and completed output assets according to their retention and privacy requirements. If the development environment is disposable, document that assets are not backed up rather than implying that PostgreSQL backups restore them.

### Compose volumes

List volumes before maintenance:

```sh
docker volume ls --filter label=com.docker.compose.project=boulder-frame
```

Back up or snapshot volumes using the host's approved backup tooling. Do not copy active database files as a substitute for a PostgreSQL-consistent dump.

## Security Requirements

- Treat online development as internet-facing when Caddy is enabled.
- Use HTTPS for browser/API traffic; Caddy may obtain and renew certificates automatically for a valid DNS name.
- Do not use local default passwords online.
- Do not publish internal service ports.
- Keep `.env` files and model credentials outside version control.
- Redact authorization headers, signed URLs, object keys with sensitive identifiers, and credentials from logs.
- Add authentication and per-user authorization before inviting external users.
- Configure deletion and retention before uploading private videos.

## GPU Worker Option

CPU processing is the baseline and must remain supported. GPU acceleration is an optional Compose override:

- Use a worker image with the required runtime and model dependencies.
- Pass through only the intended GPU devices.
- Set worker concurrency based on available VRAM, not CPU count.
- Keep a CPU worker path for CI and environments without a GPU.
- Benchmark detector, pose, decode, and render stages before requiring a GPU for online development.

## Troubleshooting

| Symptom | Checks |
| --- | --- |
| API cannot connect to PostgreSQL | Check `postgres` health, `DATABASE_URL` service name/port, and migration logs. |
| Jobs remain queued | Check Redis health, `asynq` queue configuration, worker logs, and whether the worker can reach PostgreSQL/object storage. |
| Upload succeeds but validation fails | Inspect FFmpeg/ffprobe output, source codec, frame-rate mode, rotation metadata, and object-store read permissions. |
| Worker exits during rendering | Check temporary disk capacity, memory/VRAM, FFmpeg logs, and worker concurrency. |
| Browser cannot call API online | Check Caddy routing, HTTPS certificate status, API CORS policy, and configured public base URLs. |
| Output is missing | Check worker upload logs, object-store bucket/prefix permissions, output artifact row, and signed download URL generation. |
