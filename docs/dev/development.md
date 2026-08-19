# Development

## Scope

Docker Compose starts the repository modules: the frontend, Go API, and Python worker. PostgreSQL,
Redis, and S3-compatible object storage are external dependencies and are not provisioned here.

## Setup

Copy the non-secret template and replace the external service values:

```sh
cp .env.example .env
```

Keep `.env` out of version control. Configure the external database, Redis/asynq queue, and
object-storage bucket separately, including credentials, CORS, and retention policy.

## Start Modules

Start the complete module set with:

```sh
docker compose up --build
```

Run detached:

```sh
docker compose up --build -d
```

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
