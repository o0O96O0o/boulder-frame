---
name: debug-remote-job
description: Trace a Boulder Frame processing job end to end on the remote Docker Compose server by correlating the job UUID and X-Trace-ID across the API, PostgreSQL, Redis Streams, backend logs, worker logs, leases, and artifacts. Use when a job is queued, stuck, retrying, failed, missing output, or when asked to inspect remote job errors or production Compose logs.
user-invocable: true
---

# Debug Remote Job

Diagnose one Boulder Frame job on `root@76.13.185.64`. Treat PostgreSQL as durable truth, Redis as delivery state, and logs as execution evidence.

## Safety boundary

- Read-only by default. Never restart services, run `docker compose down`, edit configuration, update PostgreSQL, acknowledge/delete Redis entries, delete objects, or retry/requeue a job while diagnosing.
- Never place the SSH password in this skill, a command, an environment variable, shell history, a report, or a repository file. Prefer an SSH key; otherwise let `ssh` request the password interactively.
- Never print `.env`, container environment, `DATABASE_URL`, `REDIS_URL`, S3 credentials, authorization headers, signed URL query strings, or full `docker inspect` output.
- Do not fetch `/evaluation` into logs: its response can contain signed URLs. `/artifacts` is metadata-only and safe for routine collection.
- Do not expose user filenames or source media. Quote only the bounded, sanitized diagnostics already emitted by the services.
- Obtain explicit user approval before any recovery mutation. Diagnosis and recovery are separate operations.

## Required input

Require the exact job UUID. Accept an optional Docker log window such as `6h`, `24h`, or an RFC 3339 timestamp. Default to `24h`.

If only a trace UUID is available, search backend and worker logs for that exact `trace-id`, extract the associated `job_id`, then continue with the job UUID. Do not guess identifiers.

## Collect evidence

From the repository root, run:

```bash
.agents/skills/debug-remote-job/scripts/collect-job-debug.sh <job-uuid> [since] [ssh-target]
```

Defaults:

- `since`: `24h`
- `ssh-target`: `root@76.13.185.64`

Run it as a finite command. Use a PTY only if `ssh` needs an interactive password. The collector is read-only and discovers containers through Compose labels, so it does not need the deployment directory.

If the collector cannot authenticate, stop. Report that SSH key or interactive password authentication is required; never work around authentication by recording the password.

If the worker container is not running, PostgreSQL and Redis snapshots are unavailable through its installed clients. Continue with container state, API state, and historical Docker logs; state that external dependency snapshots were not collected.

## Correlate the timeline

Analyze evidence in this order:

1. **Container state** — service, health, start time, and restart count. A replaced or restarted container can explain missing in-container activity.
2. **API snapshot** — current safe job resource and artifact metadata.
3. **PostgreSQL snapshot** — authoritative `state`, `stage`, `progress`, error, immutable pipeline/model versions, lease owner/expiry, timestamps, output asset, and persisted artifacts.
4. **Redis snapshot** — stream/group state, recent matching entry, and matching pending delivery. Redis is not job truth.
5. **Backend log chain** — HTTP request/response, `queue request`, and `queue response`, joined by `trace-id` and job UUID.
6. **Worker log chain** — `task request` → `job claimed` → each `stage request`/`stage response` → `task response`.
7. **Nearby infrastructure warnings** — connection, timeout, retry, warning, and error events in the same window. Treat uncorrelated warnings as context, not root cause.

The expected stages are `validating` (10), `analyzing` (45), `rendering` (75), and `uploading` (90), followed by `completed` (100). Every completed stage should have a terminal `stage response` with `outcome`, `duration_ms`, and bounded `phase_io`. A failed stage should have `outcome=failed`, `error_code`, and optionally a sanitized `diagnostic`.

## Interpret state consistently

- **`queued`, no lease, no matching recent Stream entry**: publication likely failed or the entry is older than the bounded Redis scan. Confirm backend `queue response` before concluding. The durable row may legitimately remain queued after `queue_unavailable`.
- **`queued`, Stream entry present, no claim**: inspect worker health/startup logs, consumer-group state, active model capability, and Redis connectivity.
- **Active state with unexpired lease**: the lease owner is authoritative. Follow that worker's stage logs; do not recover or duplicate-deliver it.
- **Active state with expired lease**: look for worker exit/restart, lease-renewal/database errors, and pending-entry recovery evidence. An expired lease alone does not prove data loss.
- **`response_body.state=retry`**: transient failure. The worker releases or lets the lease expire and intentionally leaves the Stream entry pending for recovery. Do not manually requeue.
- **`failed`**: use PostgreSQL `error_code` as the durable user-safe result; use the correlated failed `stage response` and `diagnostic` for cause.
- **`completed` with no output artifact**: report a persistence/finalization inconsistency. Do not infer success from a render log alone.
- **Terminal job with a pending Redis entry**: PostgreSQL remains authoritative. A duplicate delivery should be acknowledged without reprocessing; do not manually acknowledge it during diagnosis.

Common terminal worker codes: `invalid_media`, `unsupported_container`, `unsupported_video_codec`, `unsupported_audio_codec`, `variable_frame_rate`, `missing_video_stream`, `invalid_target_selection`, `no_selected_athlete`, `model_unavailable`, `render_unavailable`, `invalid_output`, `storage_unavailable`, `database_unavailable`, and `internal`.

`model_unavailable` before stage work usually means the job's immutable `model_version` differs from the active worker. `storage_unavailable` and `database_unavailable` may be transient or terminal depending on the recorded task response; use `response_body.state`, not the code alone, to classify retry behavior.

## Examine debug evidence

Routine collection calls `/artifacts` only. When `debug_capture` was enabled, look for `debug_telemetry` and `debug_manifest`; visual review may additionally contain `debug_detection`, `debug_framing`, and `debug_render`.

Only if visual inspection is necessary:

1. Request `/api/v1/jobs/{jobID}/evaluation` without saving or quoting the response.
2. Open short-lived phase URLs directly in a browser.
3. Report observed detection/framing/render behavior, never the URL.
4. Treat `available: false` as absence of finalized optional review evidence, not as the processing cause.

## Report

Return a compact evidence-backed report:

```text
Problem: <current durable state and failed/stuck boundary>
Job: <uuid>
Trace: <uuid or "not found in retained logs">
Timeline: <UTC event sequence with service/container and stage>
Root cause: <specific evidence-backed cause>
Durable error: <error_code and safe error_message>
Queue/lease: <matching entry, pending state, lease owner/expiry>
Artifacts: <persisted roles and output consistency>
Confidence: <high|medium|low; explain missing evidence>
Next: <smallest safe recovery or code/config action; no mutation performed>
```

Separate fact from inference. If log retention excludes publication or execution, say so explicitly. Never claim the trace is complete unless API, PostgreSQL, Redis, and the relevant backend/worker window were all collected and correlated.
