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

## Prepare The Detector

The committed manifest pins the approved W0.2 detector. Before enabling it, download and verify the
artifact with:

```sh
./deploy/bin/local prepare-model
```

This writes the ignored `worker/models/ssd_mobilenet_v1_12.onnx` file, checks its exact byte size and
SHA-256 against `worker/models/model-manifest.json`, and makes it read-only. Then set this exact value
in `.env` before starting the worker:

```dotenv
MODEL_VERSION=w0.2-ssd-mobilenetv1-12-onnx-detector-only-1
```

`MODEL_VERSION=w0.1-ssd-mobilenetv1-12-onnx-mediapipe-pose-full-1` is unsupported and causes the
worker to exit before it can process jobs. Existing W0.1 jobs cannot be retried against W0.2: create
new jobs after the backend is configured with the W0.2 version.

Set one shared immutable processing-behavior version for the backend and worker. The timestamp-based
smooth-transition release (`deterministic-v3`), retaining independent crop hysteresis, uses:

```dotenv
PIPELINE_VERSION=w0.2.3
```

Set this explicitly in your private `.env`; changing `.env.example` does not migrate existing
environments. The version and fixed planner controller, thresholds, and motion limits enter the job
hash. An otherwise identical submission creates a new job; retrying an existing job retains that
job's original configuration and does not upgrade its controller behavior.

For a non-default host artifact directory, set `MODEL_DIR_HOST` both when preparing the artifact and
in `.env`; Compose mounts it read-only at the in-container `MODEL_DIR` path.

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

For an existing environment, deploy as a drained cutover: pause submissions, let the **old workers**
finish every queued and leased old-version job, confirm the Redis consumer-group pending count is
zero, and stop old workers. Set `PIPELINE_VERSION=w0.2.3` in the deployment `.env`, start backend
and worker together with the new code and shared version, verify both startup summaries, and only
then resume submissions. The worker enforces model-version compatibility but not pipeline-version
compatibility: replacing workers before the drain or overlapping versions could run new code under
an old immutable configuration.

Submit a new job for the new behavior. Never rewrite old job configuration, republish an old UUID,
or copy an old job's scratch/crop paths into a new job. New version/configuration hashes create
distinct jobs and isolate their caches; retrying an old job is not a migration.

The application binds to all host interfaces for trusted-network access. With the configured values
from `.env`, the endpoints are:

- Web app: `${WEB_BASE_URL}`
- Go API: `${API_BASE_URL}`
- API health: `${API_BASE_URL}/healthz`

Allow TCP ports `5173` and `8080` through the host firewall for remote access. This Compose setup
does not provide TLS or authentication; use it only on a trusted network.

Run migrations explicitly against the configured external PostgreSQL database:

```sh
./deploy/bin/migrate
```

This applies every pending migration and records each successful file in `schema_migrations`; it is
safe to run repeatedly. `./deploy/bin/local migrate` is an equivalent wrapper.

Inspect or stop the modules:

```sh
docker compose ps
docker compose logs -f backend worker
docker compose down
```

The worker scratch directory and frontend dependency cache are local Compose volumes. Source videos,
outputs, and durable metadata remain in their configured external services.

## Debug Review Troubleshooting

`debug_capture` is read when the worker starts and affects only jobs processed by that worker after
startup. It cannot add review artifacts to an already terminal job. For a job whose evaluation returns
`{"available":false}`, first confirm that the configured worker processed that exact UUID by finding
its `task request` and `debug review published` log records. If the latter is instead `debug review
publish failed`, its JSON `error` field identifies the non-blocking storage or finalization failure;
the completed output remains valid.
