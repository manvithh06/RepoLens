#!/usr/bin/env bash
# Run the RepoLens backend and frontend together. Stop both with Ctrl+C.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PORT=8000
WEB_PORT=5173

if [ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]; then
  echo "Backend virtualenv not found at backend/.venv (or uvicorn is not installed in it)." >&2
  exit 1
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Frontend dependencies missing. Run: cd frontend && npm install" >&2
  exit 1
fi

port_in_use() {
  # A successful TCP connect means something is already listening.
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null || (exec 3<>"/dev/tcp/::1/$1") 2>/dev/null
}

for port in "$API_PORT" "$WEB_PORT"; do
  if port_in_use "$port"; then
    echo "Port $port is already in use. Stop whatever is using it first." >&2
    echo "Hint: ss -ltnp \"sport = :$port\"" >&2
    exit 1
  fi
done

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping backend and frontend..."
  kill 0 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "Backend:  http://localhost:$API_PORT  (docs at /docs in development)"
echo "Frontend: http://localhost:$WEB_PORT"
echo "Press Ctrl+C to stop both."
echo

(
  cd "$ROOT/backend"
  exec .venv/bin/uvicorn app.main:app --reload --reload-dir app --port "$API_PORT" 2>&1 | sed -u 's/^/[api] /'
) &

(
  cd "$ROOT/frontend"
  exec npm run dev -- --strictPort --port "$WEB_PORT" 2>&1 | sed -u 's/^/[web] /'
) &

wait -n
