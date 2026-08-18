#!/bin/sh
set -eu

config=/workspace/backend/conf/config.json
if [ "${APP_ENV:-}" = "local" ]; then
  config=/workspace/backend/conf/config.dev.json
fi

exec go run . --config "$config" "$@"
