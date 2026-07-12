#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill -TERM "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill -TERM "$BACKEND_PID" 2>/dev/null || true
  fi

  wait "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
}

stop_cleanly() {
  trap - INT TERM
  cleanup
  exit 0
}

trap stop_cleanly INT TERM
trap cleanup EXIT

if command -v lsof >/dev/null 2>&1; then
  BUSY_PORTS=""
  for PORT in 3000 8000; do
    if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      BUSY_PORTS="$BUSY_PORTS $PORT"
    fi
  done

  if [[ -n "$BUSY_PORTS" ]]; then
    echo "无法启动：端口${BUSY_PORTS} 已被占用。"
    echo "请先在原来的开发终端按 Ctrl+C，再重新运行 make dev。"
    exit 1
  fi
fi

# 只清理 Next.js 开发缓存，避免旧的 Client Manifest 让按钮失去交互。
rm -rf "$ROOT_DIR/frontend/.next/dev"

echo "正在准备可见力本地环境…"
(
  cd "$ROOT_DIR/backend"
  uv run alembic upgrade head
  exec uv run uvicorn keeplix.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

(
  cd "$ROOT_DIR/frontend"
  export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://127.0.0.1:8000}"
  exec npm run dev
) &
FRONTEND_PID=$!

echo "前端：http://127.0.0.1:3000"
echo "后端：http://127.0.0.1:8000"
echo "接口文档：http://127.0.0.1:8000/docs"
echo "按 Ctrl+C 同时停止前后端。"

STATUS=0
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

if ! wait "$BACKEND_PID" 2>/dev/null; then
  STATUS=1
fi
if ! wait "$FRONTEND_PID" 2>/dev/null; then
  STATUS=1
fi

exit "$STATUS"
