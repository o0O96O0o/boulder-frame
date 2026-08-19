# Component Specifications

These documents describe how the current implementation is structured at component level. They are scoped from the repository root into the corresponding submodule:

```text
docs/specs/
├── backend/     Go API, persistence, signed storage URLs, and asynq dispatch
├── worker/      Python worker runtime, media primitives, tracking, and planner
└── frontend/    Vite/React workflow and browser/API integration
```

The product boundary and algorithm contract remain authoritative in [../architecture/offline-reframing-mvp.md](../architecture/offline-reframing-mvp.md). The implementation sequence is in [../architecture/service-implementation-plan.md](../architecture/service-implementation-plan.md).

## Component Specifications

- [Backend](backend/README.md): Go process, API resources, PostgreSQL persistence, S3 URLs, and Redis/`asynq` task distribution.
- [Worker](worker/README.md): Python runtime, job state machine, media validation, measurement interfaces, and deterministic planner.
- [Frontend](frontend/README.md): Browser workflow, direct upload, target selection, polling, and download.

## Cross-Service Flow

```mermaid
flowchart LR
    B[Browser] -->|project and upload request| API[Go backend]
    API -->|metadata| PG[(PostgreSQL)]
    API -->|signed PUT URL| B
    B -->|source bytes| S3[(S3-compatible storage)]
    B -->|create immutable job| API
    API -->|job.process with job ID| R[(Redis)]
    R -->|asynq task| W[Python worker]
    W -->|read source and write output| S3
    W -->|state, progress, artifacts| PG
    B -->|poll job| API
    API -->|signed download URL| B
```

## Current Boundary

The Go API and frontend workflow are implemented. The Python worker currently provides the media, measurement, tracking, and planner foundation but runs in explicit idle mode because queue, database, storage, model, and full render orchestration adapters are not yet implemented. The specifications call out this distinction instead of describing planned adapters as existing behavior.
