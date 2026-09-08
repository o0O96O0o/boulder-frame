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

### Environment Configuration

The root `.env` is the local configuration source; `.env.example` lists supported settings.
Compose passes it directly to the backend and worker. Both read typed environment values at startup;
there are no runtime `conf/config*.json` files or `--config` flags. Restart services after changing
values. Existing custom JSON values must be moved into `.env` before upgrading.

```mermaid
flowchart LR
    Env["Root .env"] --> Compose
    Compose --> API["Go API environment"]
    Compose --> Worker["Python worker environment"]
    Env --> Vite
    Compose --> Vite
    Vite --> Browser["Browser: API_BASE_URL and MAX_UPLOAD_BYTES only"]
```

Shared database, Redis, S3, pipeline, and model settings use the same names in both services.
`S3_FORCE_PATH_STYLE` now controls both clients. API-specific options include `HTTP_ADDR`,
`SIGNED_URL_TTL`, `MAX_UPLOAD_BYTES`, `DETECTION_SAMPLE_FPS`, `WEB_BASE_URL`, and `DEVELOPMENT_OWNER`.
Worker-only options use `WORKER_` plus the uppercase former JSON key, except `worker_id` is
`WORKER_ID`, and executable paths are `FFMPEG_BIN` and `FFPROBE_BIN`. Model paths use `MODEL_DIR`.
`APP_ENV` no longer selects a configuration file.

Vite loads the repository-root `.env` (and standard Vite mode/local variants), with existing process
environment taking precedence. Only `API_BASE_URL` and `MAX_UPLOAD_BYTES` are compiled into browser
configuration; database and storage credentials are never included. An unset API URL uses `/`;
an unset upload limit uses 2 GiB. Rebuild the frontend to change these values in a production bundle.

For native backend/worker commands, export the environment first; they do not parse dotenv files.
If your `.env` is shell-compatible, run `set -a; . ./.env; set +a` from the repository root, then
`(cd backend && go run .)` or `(cd worker && uv run boulder-frame-worker --check)`.
For native worker runs, use a writable `WORKER_SCRATCH_ROOT` and a local `MODEL_DIR`.
Compose keeps `/work` and the existing debug-capture defaults; deployments can override them in `.env`.

When those dependencies run on the Docker host, containers must use
`host.docker.internal` rather than `localhost` in their URLs. For example, use
`postgres://user:password@host.docker.internal:5432/database?sslmode=disable`. Compose maps that
name to Docker's host gateway for the backend and worker. `localhost` from either container refers
to that container, not the host.

The worker requires PostgreSQL and Redis URLs plus a stable `WORKER_ID`; `.env.example` provides a
local value. Its stream settings include an optional `WORKER_STREAM_CONSUMER` override, read block interval,
pending-entry reclaim idle time, heartbeat interval, and concurrency. Set unique consumer identities
for concurrent worker processes. PostgreSQL remains the job-lease authority; Redis consumer-group
pending state is only delivery coordination.

## Prepare The Detector

The committed manifest pins the approved YOLO26n detector and its AGPL-3.0 source checkpoint and
export toolchain. AGPL-3.0 use is explicitly accepted. Before enabling it, provision and verify with:

```sh
./deploy/bin/local prepare-model
```

This exports the ignored `worker/models/yolo26n.onnx` file using the pinned Python 3.12 build
toolchain, checks its exact byte size and SHA-256 against `worker/models/model-manifest.json`, and
makes it read-only. Provisioning needs Python 3.11+; export also needs `uv` and `curl`. Export is CPU,
FP32, batch 1, fixed 640x640, explicitly `end2end=True`, `nms=False`, without graph simplification.
Metadata is removed for deterministic serialization. If platform-dependent export bytes differ,
verification fails closed: copy the approved artifact and run
`./deploy/bin/local prepare-model /path/to/yolo26n.onnx` instead of changing the pin. Then set:

```dotenv
MODEL_VERSION=w0.2-yolo26n-onnx-detector-only-1
```

Previous model versions are unsupported by this worker. Existing jobs must drain on their original
workers; they cannot be retried to upgrade their immutable detector configuration. Create new jobs
after the backend and worker are configured with the new shared model and pipeline versions.
Retain the bundled [AGPL-3.0 license](../../worker/models/LICENSE) with redistributed weights and
satisfy applicable corresponding-source and network-use obligations; the license file alone is not
compliance. See [detector provisioning and license details](../specs/worker/models.md).

Set one shared immutable processing-behavior version for backend and worker. The YOLO26n release
retains the existing selection, sampling, pan-only `lookahead-v1` planner, causal zoom and miss widening:

```dotenv
PIPELINE_VERSION=w0.2.6
DETECTION_SAMPLE_FPS=10
```

Set this explicitly in your private `.env`; changing `.env.example` does not migrate existing
environments. `DETECTION_SAMPLE_FPS` is a backend deployment option: finite numeric values from `0`
through `1000`, default `10` when unset or empty; `0` detects every frame. Fractional rates are allowed.
It is snapshotted as `planner.detection_sample_fps`, not read from the worker environment. Changing
the rate affects new submissions only, changes the job hash, and cannot alter existing retries.
The version and entire planner map (controller, seed, optimizer, scope, policy, tolerance, thresholds,
motion limits, and sampling rate) enter the hash. No new environment controls are needed.

Only accepted sampled detections constrain look-ahead containment. Held targets may leave the crop;
future observed boxes guide camera movement without athlete-position interpolation or prediction.
SciPy `1.15.3` supplies sparse deterministic `highs-ds` optimization. A non-optimal/invalid solver
result fails analyzing safely with `internal` and no causal fallback or committed analysis artifacts.

YOLO26n inference uses `CPUExecutionProvider`, 2 intra-op threads, and 1 inter-op thread. Keep
`WORKER_CONCURRENCY=1` on the 2-vCPU server. Export dependencies are not installed in the worker
runtime; only the approved ONNX artifact is mounted read-only.

For a non-default host artifact directory, set `MODEL_DIR_HOST` both when preparing the artifact and
in `.env`; Compose mounts it read-only at the in-container `MODEL_DIR` path.

Worker `WORKER_NORMALIZATION_MAX_SOURCE_BYTES` sets the VFR normalization source cap (default 1 GiB);
`WORKER_NORMALIZATION_TIMEOUT_SECONDS` sets its timeout (default 1,800 seconds).
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
zero, and stop old workers. Provision the verified artifact, then set `PIPELINE_VERSION=w0.2.6`
and `MODEL_VERSION=w0.2-yolo26n-onnx-detector-only-1` in the deployment `.env`. Start backend
and worker together with the new code and shared versions, verify both startup summaries, and only
then resume submissions. There is no generic claim-time pipeline-version compatibility check.
The worker validates the exact immutable planner contract before cached replay and rejects old
or malformed maps; this safety check does not replace the drained deployment protocol.

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

`WORKER_DEBUG_CAPTURE` is read when the worker starts and affects only jobs processed by that worker after
startup. It cannot add review artifacts to an already terminal job. For a job whose evaluation returns
`{"available":false}`, first confirm that the configured worker processed that exact UUID by finding
its `task request` and `debug review published` log records. If the latter is instead `debug review
publish failed`, its JSON `error` field identifies the non-blocking storage or finalization failure;
the completed output remains valid.
