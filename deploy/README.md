# Module Containers

The Compose file starts only the repository modules. PostgreSQL, Redis, and S3-compatible object
storage are external dependencies and are not provisioned by this repository.

```sh
cp .env.example .env
./deploy/bin/local prepare-model
docker compose up --build
```

`prepare-model` downloads the detector selected by `worker/models/model-manifest.json` into
`worker/models`, verifies its byte size and SHA-256, and marks it read-only. Set
`MODEL_VERSION=w0.2-ssd-mobilenetv1-12-onnx-detector-only-1` in `.env` before starting the
worker. To place the host-side artifact elsewhere, run
`MODEL_DIR_HOST=/srv/boulder-frame-models ./deploy/bin/local prepare-model` and mount that
directory at the container's `MODEL_DIR`.

Useful commands:

```sh
./deploy/bin/migrate
docker compose ps
docker compose down
```

`migrate` applies every pending SQL migration once, in filename order. It is safe to run repeatedly.

Do not commit `.env`. Configure the external database, queue, and object store separately.
