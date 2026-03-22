#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-5000}"
MONGO_PORT="${MONGO_PORT:-27017}"
WORKSPACE="/home/runner/workspace"

echo "[BOOT] Freeing port $PORT..."

( fuser -k "${PORT}/tcp" 2>/dev/null || true )
( lsof -ti "tcp:${PORT}" 2>/dev/null | xargs -r kill -9 || true )

for i in $(seq 1 25); do
  if lsof -iTCP:${PORT} -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    echo "[BOOT] Port $PORT still in use, retry $i/25..."
    sleep 0.2
  else
    echo "[BOOT] Port $PORT is free."
    break
  fi
done

if lsof -iTCP:${PORT} -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "[BOOT][ERROR] Port $PORT still in use after retries. Debug:"
  lsof -iTCP:${PORT} -sTCP:LISTEN -n -P || true
  exit 1
fi

if mongosh --port "$MONGO_PORT" --eval "db.runCommand({ping:1})" --quiet >/dev/null 2>&1; then
  echo "[BOOT] mongod already running and healthy on port $MONGO_PORT."
else
  echo "[BOOT] mongod not responding, starting fresh..."

  ( pkill -9 mongod 2>/dev/null || true )
  ( fuser -k "${MONGO_PORT}/tcp" 2>/dev/null || true )
  ( lsof -ti "tcp:${MONGO_PORT}" 2>/dev/null | xargs -r kill -9 || true )
  sleep 1

  for i in $(seq 1 25); do
    if lsof -iTCP:${MONGO_PORT} -sTCP:LISTEN -n -P >/dev/null 2>&1; then
      echo "[BOOT] Mongo port $MONGO_PORT still in use, retry $i/25..."
      sleep 0.2
    else
      echo "[BOOT] Mongo port $MONGO_PORT is free."
      break
    fi
  done

  if lsof -iTCP:${MONGO_PORT} -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    echo "[BOOT][ERROR] Mongo port $MONGO_PORT still in use after retries. Debug:"
    lsof -iTCP:${MONGO_PORT} -sTCP:LISTEN -n -P || true
    exit 1
  fi

  rm -f "${WORKSPACE}/.data/db/mongod.lock" 2>/dev/null || true

  echo "[BOOT] Starting mongod..."
  "${WORKSPACE}/.local/bin/mongod" \
    --dbpath "${WORKSPACE}/.data/db" \
    --port "$MONGO_PORT" \
    --bind_ip 127.0.0.1 \
    --fork \
    --logpath "${WORKSPACE}/.data/mongod.log"

  MONGO_READY=false
  for i in $(seq 1 15); do
    if mongosh --port "$MONGO_PORT" --eval "db.runCommand({ping:1})" --quiet >/dev/null 2>&1; then
      echo "[BOOT] mongod is ready."
      MONGO_READY=true
      break
    fi
    echo "[BOOT] Waiting for mongod... $i/15"
    sleep 1
  done

  if [ "$MONGO_READY" != "true" ]; then
    echo "[BOOT][ERROR] mongod failed to become ready after 15 seconds."
    exit 1
  fi
fi

export GIT_SHA
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo none)

PROXY_PORT="${PROXY_PORT:-}"
if [ -n "$PROXY_PORT" ] && [ "$PROXY_PORT" != "$PORT" ]; then
  echo "[BOOT] Starting TCP proxy $PROXY_PORT -> $PORT in background..."
  python3 -c "
import socket, threading, sys
def proxy(src, dst):
    try:
        while True:
            d = src.recv(65536)
            if not d: break
            dst.sendall(d)
    except: pass
    finally: src.close(); dst.close()
def accept_loop(s, target_port):
    while True:
        c, _ = s.accept()
        try:
            t = socket.create_connection(('127.0.0.1', target_port))
            threading.Thread(target=proxy, args=(c, t), daemon=True).start()
            threading.Thread(target=proxy, args=(t, c), daemon=True).start()
        except: c.close()
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', int(sys.argv[1]))); s.listen(128)
accept_loop(s, int(sys.argv[2]))
" "$PROXY_PORT" "$PORT" &
  PROXY_PID=$!
  echo "[BOOT] TCP proxy started (PID $PROXY_PID)"
fi

echo "[BOOT] Starting uvicorn on port $PORT..."
cd "${WORKSPACE}/backend"
exec python -m uvicorn server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers 1 \
  --no-access-log
