#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

export APP_ENV="${APP_ENV:-development}"
export DEMO_MODE="${DEMO_MODE:-false}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.uv-cache}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5174}"

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "${WEB_PID:-}" ]]; then kill "$WEB_PID" 2>/dev/null || true; fi
}

trap cleanup EXIT INT TERM

cd "$ROOT_DIR/apps/api"
uv run alembic upgrade head
uv run uvicorn jhai_to_c.main:app --app-dir src --host "$APP_HOST" --port "$APP_PORT" &
API_PID=$!

API_READY_URL="http://$APP_HOST:$APP_PORT/openapi.json"
API_READY=false
for _ in {1..60}; do
  if curl --silent --fail --noproxy "*" --max-time 1 "$API_READY_URL" >/dev/null; then
    API_READY=true
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    API_STATUS=1
    wait "$API_PID" || API_STATUS=$?
    printf 'API 启动失败（退出码 %s），前端未启动。\n' "$API_STATUS" >&2
    exit "$API_STATUS"
  fi
  sleep 0.25
done

if [[ "$API_READY" != "true" ]]; then
  printf 'API 在 15 秒内未就绪：%s\n' "$API_READY_URL" >&2
  exit 1
fi

cd "$ROOT_DIR/apps/web"
npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT" --strictPort &
WEB_PID=$!

printf 'JHAi-to-C 已启动：http://%s:%s\n' "$WEB_HOST" "$WEB_PORT"

while kill -0 "$API_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do
  sleep 1
done

EXIT_STATUS=0
if ! kill -0 "$API_PID" 2>/dev/null; then
  wait "$API_PID" || EXIT_STATUS=$?
else
  wait "$WEB_PID" || EXIT_STATUS=$?
fi
exit "$EXIT_STATUS"
