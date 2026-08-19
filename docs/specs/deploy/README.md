# Compose Specification

This specification covers the Docker Compose startup of the frontend, backend, and worker modules.
PostgreSQL, Redis, and S3-compatible object storage are external dependencies; this repository does
not define or provision those services.

## Documents

- [Compose Runtime](compose-runtime.md): module services, networks, volumes, environment propagation,
  startup ordering, and external dependency configuration.
