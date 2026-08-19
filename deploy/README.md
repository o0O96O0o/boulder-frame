# Module Containers

The Compose file starts only the repository modules. PostgreSQL, Redis, and S3-compatible object
storage are external dependencies and are not provisioned by this repository.

```sh
cp .env.example .env
docker compose up --build
```

Useful commands:

```sh
docker compose run --rm backend migrate up
docker compose ps
docker compose down
```

Do not commit `.env`. Configure the external database, queue, and object store separately.
