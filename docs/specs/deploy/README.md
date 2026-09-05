# Compose Specification

This specification covers the Docker Compose startup of the frontend, backend, and worker modules.
PostgreSQL, Redis, and S3-compatible object storage are external dependencies; this repository does
not define or provision those services.

## Documents

- [Compose Runtime](compose-runtime.md): module services, networks, volumes, environment propagation,
  startup ordering, external dependencies, and drained `w0.2.2` pipeline cutover/cache isolation.
