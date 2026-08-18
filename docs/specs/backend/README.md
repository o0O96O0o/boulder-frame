# Backend Specifications

The backend is a Go HTTP process. It owns request validation, PostgreSQL metadata, signed object-storage URLs, and asynchronous processing dispatch. It must not decode video, run CV inference, or render media.

## Documents

- [HTTP API](http-api.md): routes, request validation, response shapes, ownership checks, and lifecycle behavior.
- [Persistence](persistence.md): PostgreSQL entities, constraints, immutable configuration, and repository responsibilities.
- [Asynq Task Distribution](asynq-task-distribution.md): Redis queue configuration, task payload, idempotency, retry boundary, and worker handoff.

## Runtime Composition

```mermaid
flowchart LR
    HTTP[HTTP request] --> H[chi handlers]
    H --> D[domain validation]
    H --> REPO[repository]
    REPO --> PG[(PostgreSQL)]
    H --> STORE[S3 store]
    STORE --> OBJ[(Object storage)]
    H --> PUB[asynq publisher]
    PUB --> REDIS[(Redis)]
```

## Startup

`backend/main.go` loads configuration, opens PostgreSQL, constructs the S3 client and presigner, constructs the asynq publisher, and starts the HTTP server. `GET /healthz` is process liveness. `GET /readyz` currently checks PostgreSQL only; Redis and object-storage readiness remain an operational gap.

The container entrypoint supports:

```sh
go run .
go run . migrate up
```

The migration command applies `backend/migrations/001_init.sql` and is idempotent.
