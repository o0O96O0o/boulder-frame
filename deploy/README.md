# Module Containers

The Compose file starts only the repository modules. PostgreSQL, Redis, and S3-compatible object
storage are external dependencies and are not provisioned by this repository.

Runtime configuration comes directly from the root `.env`; no JSON configuration files are generated
or loaded. See [environment configuration](../docs/dev/development.md#environment-configuration)
for variable names, native commands, and migration from the removed JSON files.

```sh
cp .env.example .env
./deploy/bin/local prepare-model
docker compose up --build
```

`prepare-model` exports the detector pinned by `worker/models/model-manifest.json` into
`worker/models/yolo26n.onnx`, verifies its byte size and SHA-256, and marks it read-only.
It needs Python 3.11+, `uv`, and `curl`; export runs in the pinned Python 3.12 toolchain with
CPU-only FP32, batch 1, fixed 640x640, explicit `end2end=True` and `nms=False`.
To install an already exported approved artifact without the export toolchain, use
`./deploy/bin/local prepare-model /path/to/yolo26n.onnx`; it performs the same integrity checks.
Platform-dependent export differences fail closed: copy the approved artifact, never loosen its pin.
Set `MODEL_VERSION=w0.2-yolo26n-onnx-detector-only-1` and `PIPELINE_VERSION=w0.2.6` in `.env`
before starting the backend and worker. For a different artifact location, set
`MODEL_DIR_HOST=/srv/boulder-frame-models` when provisioning and in `.env`; Compose mounts it
read-only at `MODEL_DIR`.

The AGPL-3.0 model license is explicitly accepted. Retain [the bundled license](../worker/models/LICENSE)
and meet applicable corresponding-source and network-use obligations; see the
[model contract](../docs/specs/worker/models.md). The worker uses only CPU ONNX Runtime, with
2 intra-op threads and 1 inter-op thread. Keep `WORKER_CONCURRENCY=1` on a 2-vCPU host.

For existing environments, pause submissions and drain all queued/leased old jobs on old workers,
confirm no Redis consumer-group pending deliveries, then stop them and deploy backend and worker
together with the new shared versions. Never rewrite/retry old jobs, republish old UUIDs, or reuse
their scratch/crop paths for the new detector; submit new versioned jobs after the cutover.

Useful commands:

```sh
./deploy/bin/migrate
docker compose ps
docker compose down
```

`migrate` applies every pending SQL migration once, in filename order. It is safe to run repeatedly.

Do not commit `.env`. Configure the external database, queue, and object store separately.
