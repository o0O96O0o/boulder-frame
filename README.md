# Boulder Frame

Boulder Frame turns a wide sports recording into a smooth, close-up video that keeps a selected athlete's complete movement in frame.

The first product is an offline, single-athlete reframing service. The approved implementation specification is in [docs/architecture/offline-reframing-mvp.md](docs/architecture/offline-reframing-mvp.md).

Development setup for local and self-hosted online Docker Compose environments is documented in [docs/dev/development.md](docs/dev/development.md).

## Status

The frontend, Go API, worker foundation, and Docker Compose topology are implemented. Detailed component specifications are indexed in [docs/specs/README.md](docs/specs/README.md). The Python worker's queue, database, storage, model, and full render adapters remain to be implemented before end-to-end processing is active.
