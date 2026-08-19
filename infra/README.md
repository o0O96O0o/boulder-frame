# Infrastructure Operations

Copy `.env.example` to `.env` before running any command. `.env` is ignored and must contain generated, unique credentials on an online host.

Local operations use `infra/bin/local`:

```sh
infra/bin/local start-detached
infra/bin/local migrate
infra/bin/local status
infra/bin/local stop
infra/bin/local reset
```

`reset` runs `down -v` and is destructive. It removes local worker, frontend-dependency, and Caddy
volumes only; externally managed PostgreSQL, Redis, and S3 data are not affected.

Online operations use `infra/bin/online` after setting immutable image tags and `CADDY_DOMAIN` in `.env`:

```sh
infra/bin/online pull
infra/bin/online start
infra/bin/online update
infra/bin/online migrate
infra/bin/online status
```

There is deliberately no online reset command and online maintenance must never use `down -v`. Back up the externally managed PostgreSQL database and S3 bucket using their host-level tooling. Caddy exposes only `/healthz`; browser and API routes are blocked until authentication is implemented.
