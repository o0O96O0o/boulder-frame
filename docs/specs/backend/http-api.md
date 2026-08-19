# Backend HTTP API

## Base URL

The API is REST over JSON under `/api/v1`. Local Compose publishes it at `http://localhost:8080`;
the browser uses `api_base_url` from `frontend/conf/config.json` or `frontend/conf/config.dev.json`
to select the API origin.

The initial implementation uses the fixed development owner `development-owner`. This is not authentication. Online external access remains blocked by Caddy until authorization is implemented.

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
