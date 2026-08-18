# Infrastructure Operations

Copy `.env.example` to `.env` before running any command. `.env` is ignored and must contain generated, unique credentials on an online host.

Local operations use `infra/bin/local`:

```sh
infra/bin/local start-detached
infra/bin/local migrate
infra/bin/local status
infra/bin/local backup-db
infra/bin/local restore-db infra/backups/postgres-YYYYMMDDTHHMMSS.sql
infra/bin/local stop
infra/bin/local reset
```

`reset` runs `down -v` and is destructive. It is only for disposable local data. The MinIO initializer creates the private `S3_BUCKET` idempotently and reapplies the lifecycle policy from `ASSET_RETENTION_DAYS` on each run.

Online operations use `infra/bin/online` after setting immutable image tags and `CADDY_DOMAIN` in `.env`:

```sh
infra/bin/online pull
infra/bin/online start
infra/bin/online update
infra/bin/online migrate
infra/bin/online status
infra/bin/online backup-db
```

There is deliberately no online reset command and online maintenance must never use `down -v`. Copy database dumps to a backup target outside the host. Mirror the private S3 bucket to that same independent target with an S3-compatible backup tool. Caddy exposes only `/healthz`; browser and API routes are blocked until authentication is implemented.
