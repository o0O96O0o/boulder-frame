#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: collect-job-debug.sh <job-uuid> [since] [ssh-target]

Collects read-only API, PostgreSQL, Redis Streams, and Docker log evidence for one job.
Defaults: since=24h, ssh-target=root@76.13.185.64
Authentication is delegated to ssh; do not put a password in this command or script.
EOF
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 || $# -gt 3 ]]; then
  usage >&2
  exit 2
fi

job_id=$1
since=${2:-24h}
ssh_target=${3:-root@76.13.185.64}

if [[ ! $job_id =~ ^[[:xdigit:]]{8}-[[:xdigit:]]{4}-[1-5][[:xdigit:]]{3}-[89abAB][[:xdigit:]]{3}-[[:xdigit:]]{12}$ ]]; then
  printf 'error: job ID must be a canonical UUID\n' >&2
  exit 2
fi
if [[ -z $since || ! $since =~ ^[A-Za-z0-9:.+_-]+$ || $since == -* ]]; then
  printf 'error: since must be a Docker --since duration or timestamp using only letters, digits, colon, period, plus, underscore, or hyphen\n' >&2
  exit 2
fi
if [[ ! $ssh_target =~ ^[A-Za-z0-9._-]+@[A-Za-z0-9._:-]+$ ]]; then
  printf 'error: ssh target must look like user@host\n' >&2
  exit 2
fi

printf -v remote_job_id '%q' "$job_id"
printf -v remote_since '%q' "$since"
ssh -- "$ssh_target" "bash -s -- ${remote_job_id} ${remote_since}" <<'REMOTE'
set -uo pipefail

job_id=$1
since=$2
project=boulder-frame

section() {
  printf '\n===== %s =====\n' "$1"
}

redact_logs() {
  sed -E \
    -e 's#(https?|redis|rediss|postgres|postgresql)://[^ "'\''}]+#<redacted-url>#gI' \
    -e 's#("(password|passwd|token|secret|access[_-]?key|authorization)"[[:space:]]*:[[:space:]]*)"[^"]*"#\1"<redacted>"#gI' \
    -e 's#((password|passwd|token|secret|access[_-]?key)[[:space:]]*(=|:)[[:space:]]*)[^ ,;"'\''}]+#\1<redacted>#gI' \
    -e 's#(authorization["]?[[:space:]]*:[[:space:]]*).*$#\1<redacted>#gI'
}

mapfile -t all_containers < <(
  docker ps -aq --filter "label=com.docker.compose.project=${project}"
)
mapfile -t backend_containers < <(
  docker ps -aq \
    --filter "label=com.docker.compose.project=${project}" \
    --filter "label=com.docker.compose.service=backend"
)
mapfile -t worker_containers < <(
  docker ps -aq \
    --filter "label=com.docker.compose.project=${project}" \
    --filter "label=com.docker.compose.service=worker"
)
mapfile -t running_workers < <(
  docker ps -q \
    --filter "label=com.docker.compose.project=${project}" \
    --filter "label=com.docker.compose.service=worker"
)

section "collection"
printf 'collected_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'job_id=%s\n' "$job_id"
printf 'docker_since=%s\n' "$since"
printf 'compose_project=%s\n' "$project"

section "compose containers"
if ((${#all_containers[@]} == 0)); then
  printf 'No containers found with Compose project label %s.\n' "$project"
  exit 3
fi
docker ps -a \
  --filter "label=com.docker.compose.project=${project}" \
  --format '{{.ID}} service={{.Label "com.docker.compose.service"}} name={{.Names}} status={{.Status}}'
for container in "${all_containers[@]}"; do
  docker inspect --format \
    '{{.Name}} service={{index .Config.Labels "com.docker.compose.service"}} state={{.State.Status}} started={{.State.StartedAt}} finished={{.State.FinishedAt}} restart_count={{.RestartCount}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
    "$container"
done

section "safe API snapshot"
collector_trace=$(cat /proc/sys/kernel/random/uuid)
printf 'collector_trace_id=%s (ignore this trace when reconstructing the originating request)\n' "$collector_trace"
for path in "/api/v1/jobs/${job_id}" "/api/v1/jobs/${job_id}/artifacts"; do
  printf '\nGET %s\n' "$path"
  curl --silent --show-error --connect-timeout 5 --max-time 15 \
    --header "X-Trace-ID: ${collector_trace}" \
    --write-out '\nHTTP %{http_code}\n' \
    "http://127.0.0.1:8080${path}" || printf 'API request failed.\n'
done

section "PostgreSQL durable state"
if ((${#running_workers[@]} == 0)); then
  printf 'Unavailable: no running worker container from which to use the configured PostgreSQL client.\n'
else
  docker exec -i "${running_workers[0]}" python - "$job_id" <<'PYDB' || \
    printf 'PostgreSQL snapshot failed without exposing connection configuration.\n'
import json
import os
import sys

import psycopg
from psycopg.rows import dict_row

job_id = sys.argv[1]
with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, project_id, source_asset_id, state, stage, progress,
                   configuration->>'pipeline_version' AS pipeline_version,
                   configuration->>'model_version' AS model_version,
                   error_code, error_message, output_asset_id,
                   created_at, started_at, completed_at,
                   lease_owner, lease_expires_at
            FROM processing_jobs
            WHERE id = %s
            """,
            (job_id,),
        )
        job = cursor.fetchone()
        print("job=" + json.dumps(job, default=str, sort_keys=True))
        if job is None:
            raise SystemExit(0)
        cursor.execute(
            """
            SELECT upload_state, content_type, size_bytes, width, height,
                   frame_rate, duration_ms, created_at
            FROM assets
            WHERE id = %s
            """,
            (job["source_asset_id"],),
        )
        print("source_asset=" + json.dumps(cursor.fetchone(), default=str, sort_keys=True))
        cursor.execute(
            """
            SELECT ja.kind, a.upload_state, a.content_type, a.size_bytes, ja.created_at
            FROM job_artifacts AS ja
            JOIN assets AS a ON a.id = ja.asset_id
            WHERE ja.job_id = %s
            ORDER BY ja.created_at
            """,
            (job_id,),
        )
        print("artifacts=" + json.dumps(cursor.fetchall(), default=str, sort_keys=True))
PYDB
fi

section "Redis Streams delivery state"
if ((${#running_workers[@]} == 0)); then
  printf 'Unavailable: no running worker container from which to use the configured Redis client.\n'
else
  docker exec -i "${running_workers[0]}" python - "$job_id" <<'PYREDIS' || \
    printf 'Redis snapshot failed without exposing connection configuration.\n'
import json
import os
import sys

import redis

job_id = sys.argv[1]
stream = "boulder-frame:jobs"
group = "boulder-frame:job-processors"
client = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
client.ping()

try:
    groups = client.xinfo_groups(stream)
except redis.ResponseError as error:
    groups = {"unavailable": str(error)}
print("groups=" + json.dumps(groups, default=str, sort_keys=True))

try:
    pending_summary = client.xpending(stream, group)
except redis.ResponseError as error:
    pending_summary = {"unavailable": str(error)}
print("pending_summary=" + json.dumps(pending_summary, default=str, sort_keys=True))

matching_id = None
matching_fields = None
try:
    recent_entries = client.xrevrange(stream, count=10_000)
except redis.ResponseError:
    recent_entries = []
for entry_id, fields in recent_entries:
    if fields.get("task_id") == job_id:
        matching_id = entry_id
        matching_fields = fields
        break
print(
    "matching_recent_entry="
    + json.dumps(
        {
            "scan_limit": 10_000,
            "entry_id": matching_id,
            "fields": matching_fields,
            "task_index_present": bool(client.exists(f"{stream}:task:{job_id}")),
        },
        default=str,
        sort_keys=True,
    )
)
if matching_id is None:
    print("matching_pending=[] (entry was not found in the bounded recent-entry scan)")
else:
    try:
        pending = client.xpending_range(stream, group, matching_id, matching_id, 1)
    except redis.ResponseError as error:
        pending = {"unavailable": str(error)}
    print("matching_pending=" + json.dumps(pending, default=str, sort_keys=True))
PYREDIS
fi

log_tmp=$(mktemp -d)
trap 'rm -rf -- "$log_tmp"' EXIT

capture_container_logs() {
  local container=$1
  local output=$2
  if docker logs --since "$since" --timestamps "$container" 2>&1 | redact_logs >"$output"; then
    return 0
  fi
  printf 'Docker log collection failed for container=%s:\n' "$container"
  tail -n 20 <"$output"
  rm -f -- "$output"
  return 1
}

show_job_logs() {
  local service=$1
  shift
  section "${service} logs for exact job UUID"
  if (($# == 0)); then
    printf 'No %s containers found.\n' "$service"
    return
  fi
  local container log_file
  for container in "$@"; do
    printf '\n--- container=%s ---\n' "$container"
    log_file="${log_tmp}/${container}.log"
    if capture_container_logs "$container" "$log_file"; then
      if ! grep -F -- "$job_id" <"$log_file"; then
        printf 'No matching lines in this window.\n'
      fi
    fi
  done
}

show_job_logs backend "${backend_containers[@]}"
show_job_logs worker "${worker_containers[@]}"

section "nearby backend and worker warnings"
for container in "${backend_containers[@]}" "${worker_containers[@]}"; do
  [[ -n $container ]] || continue
  printf '\n--- container=%s (last 200 matching lines) ---\n' "$container"
  log_file="${log_tmp}/${container}.log"
  if [[ -f $log_file ]] || capture_container_logs "$container" "$log_file"; then
    if ! grep -Ei '"level":"(warning|warn|error)"|"outcome":"failed"|"state":"retry"|connection|timed? out|timeout|unavailable' \
      <"$log_file" | tail -n 200; then
      printf 'No warning/error lines in this window.\n'
    fi
  fi
done
REMOTE
