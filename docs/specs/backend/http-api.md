# Backend HTTP API

## Base URL

The API is REST over JSON under `/api/v1`. The browser uses `api_base_url` from
`frontend/conf/config.json` or `frontend/conf/config.dev.json` to select the API origin.

The initial implementation uses the fixed development owner `development-owner`. This is not authentication.

## Routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/healthz` | Process liveness. |
| `GET` | `/readyz` | PostgreSQL readiness check. |
| `POST` | `/api/v1/projects` | Create a project. |
| `GET` | `/api/v1/projects/{projectID}` | Read an owned project. |
| `POST` | `/api/v1/projects/{projectID}/assets/upload` | Create a pending source asset and return a signed upload URL. |
| `POST` | `/api/v1/assets/{assetID}/complete` | Confirm the uploaded object exists and has the requested size. |
| `POST` | `/api/v1/projects/{projectID}/jobs` | Validate and persist immutable job configuration, then enqueue processing. |
| `GET` | `/api/v1/jobs/{jobID}` | Read job state, progress, configuration, timestamps, and safe error. |
| `GET` | `/api/v1/jobs/{jobID}/artifacts` | List output/debug artifact metadata. |
| `GET` | `/api/v1/jobs/{jobID}/download` | Return a short-lived signed URL for a completed output. |
| `GET` | `/api/v1/jobs/{jobID}/evaluation` | Return an authorized terminal-job visual-review manifest and short-lived phase-media URLs when optional debug visual capture exists. |

## Upload Contract

The client sends:

```json
{
  "filename": "session.mov",
  "content_type": "video/quicktime",
  "size_bytes": 104857600
}
```

The API requires an `.mp4`/`video/mp4` or `.mov`/`video/quicktime` pair, a positive size, and
`size_bytes <= MAX_UPLOAD_BYTES`. It creates an object key without trusting the filename:

```text
private/source/{project_uuid}/{asset_uuid}.mp4 or .mov
```

The response contains the `asset`, `upload_url`, and `expires_in_seconds`. The browser uploads bytes directly to the signed URL. The API does not proxy 4K video.

Completion performs an S3 `HeadObject`, checks the object size against the requested size, and changes `pending` to `uploaded`. Repeated completion of an already uploaded asset is idempotent. Media codec, timing, and decodability validation belongs to the worker.

## Job Contract

The client sends:

```json
{
  "source_asset_id": "asset_uuid",
  "target_selection": {
    "frame_time_ms": 0,
    "normalized_x": 0.5,
    "normalized_y": 0.5
  },
  "output": {
    "aspect_ratio": "16:9",
    "profile": "balanced"
  }
}
```

The API rejects negative frame times, coordinates outside `[0, 1]`, unsupported aspect ratios, unsupported profiles, assets from another project, and assets not in `uploaded` state.

The stored configuration additionally contains:

- `source_asset_id`
- `pipeline_version`
- `model_version`
- `planner.controller = deterministic-v1`

The configuration is serialized and SHA-256 hashed. The hash is used with `(project_id, configuration_hash)` to make repeated submissions idempotent.

## Phase Evaluation Contract

`GET /api/v1/jobs/{jobID}/evaluation` first verifies project ownership. It is available only when the
job is terminal and does not trigger worker processing. If no optional visual review run was finalized,
the response is `200` with `available: false`. Otherwise it returns the manifest projection and
short-lived signed URLs for available review-phase MP4s. It never exposes storage keys or permanent
URLs. Review URLs are omitted from structured logs and are refreshed by making the same request again.

The endpoint is intentionally distinct from `/artifacts`: artifact listing remains metadata-only and
must not become an unrestricted storage browser. The detailed phase contract is specified in
[Phase Evaluation Review](../frontend/phase-evaluation.md).

Each `unavailable` phase may include a user-safe `detail`. It is a 1-500 byte plain-text string and
is the only allowed unavailable-reason value; nested values, URLs, object paths, credentials, and
credential-like text are rejected with the complete manifest. `detail` is omitted for all other phase
statuses. The API preserves accepted details without adding storage or infrastructure context.

### Review Manifest v1

The worker's `manifest.json` is strict schema v1. Its root fields are `schema_version`, `review_id`,
`pipeline_version`, `model_version`, `timing`, `phases`, and optional `telemetry.status`. The API
accepts no other fields. `pipeline_version` and `model_version` are 1-128 character identifiers
matching `[A-Za-z0-9._-]+` and must exactly equal the job's immutable configuration. `timing` is:

```json
{"frame_rate":60,"duration_ms":1200,"frame_count":72}
```

`frame_rate` is finite and in `(0, 1000]`; `duration_ms` is an integer in `(0, 604800000]`; and
`frame_count` is an integer in `(0, 10000000]`. These fields are projected only for an available
visual review. They must contain source timing only, never URLs, keys, secrets, source identifiers,
or raw telemetry. A review is visually available only with at least one verified phase MP4. A
telemetry-only run returns `available: false` plus an optional short-lived telemetry URL, without
phase details or manifest metadata.

Each phase can include at most 100 `warning_intervals`. Every interval has a non-negative integer
`start_ms` no greater than `timing.duration_ms`, a required safe `label`, and optional safe `detail`.
When present, `end_ms` is an integer from `start_ms` through `timing.duration_ms`; it is otherwise
omitted for an open-ended interval.

## Errors

Errors use this shape:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "user-safe explanation"
  }
}
```

Internal stack traces, credentials, signed URL query strings, and infrastructure details must not be returned.

## CORS and Trace IDs

The API accepts local browser origins `http://localhost:5173` and `http://127.0.0.1:5173`. Every request carries an `X-Trace-ID`; the API preserves a valid UUID or creates one, returns it on the response, and logs it with the structured key `trace-id`. Request and response bodies are logged in bounded, redacted form. Online CORS/authentication policy must be tightened before external access.
