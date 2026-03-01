#!/bin/bash
set -e

echo "=== BrikOps Run Start ==="
echo "Date: $(date)"
echo "PWD: $(pwd)"
echo "Python: $(which python 2>/dev/null || echo 'not found')"
echo "Pip motor: $(pip show motor 2>/dev/null | grep Version || echo 'not found')"

export GIT_SHA=$(git -C /home/runner/workspace rev-parse --short HEAD 2>/dev/null || echo "unknown")
export RELEASE_SHA="$GIT_SHA"
echo "Release SHA: $GIT_SHA"

MONGO_URL_VAL="${MONGO_URL:-}"

MU_IS_SET="false"
MU_LEN=0
MU_STARTS_MONGO="false"
MU_HAS_AT="false"
MU_HAS_SRV="false"
if [ -n "$MONGO_URL_VAL" ]; then
    MU_IS_SET="true"
    MU_LEN=${#MONGO_URL_VAL}
    echo "$MONGO_URL_VAL" | grep -q "^mongodb" && MU_STARTS_MONGO="true"
    echo "$MONGO_URL_VAL" | grep -q "@" && MU_HAS_AT="true"
    echo "$MONGO_URL_VAL" | grep -q "mongodb+srv://" && MU_HAS_SRV="true"
fi
echo "[DB] MONGO_URL sanity: is_set=$MU_IS_SET len=$MU_LEN starts_mongo=$MU_STARTS_MONGO has_at=$MU_HAS_AT has_srv=$MU_HAS_SRV"
echo "[DB] DB_NAME: ${DB_NAME:-not set}"
echo "[DB] APP_MODE: ${APP_MODE:-not set}"

if [ -z "$MONGO_URL_VAL" ]; then
    echo "[DB] FATAL: MONGO_URL is not set! Cannot start."
    exit 1
fi

if echo "$MONGO_URL_VAL" | grep -qE "^mongodb\+srv://|@.*\.mongodb\.net"; then
    echo "[DB] MONGO_URL points to Atlas (external). Skipping local mongod."
elif echo "$MONGO_URL_VAL" | grep -qE "localhost|127\.0\.0\.1"; then
    MONGOD="/home/runner/workspace/.local/bin/mongod"
    DBPATH="/home/runner/workspace/.data/db"
    LOGPATH="/home/runner/workspace/.data/mongod.log"

    mkdir -p "$DBPATH"

    if [ -x "$MONGOD" ]; then
        echo "[DB] Starting local MongoDB..."
        "$MONGOD" --dbpath "$DBPATH" --port 27017 --bind_ip 127.0.0.1 --fork --logpath "$LOGPATH" 2>/dev/null || true
        sleep 2
        echo "[DB] Local MongoDB started"
    else
        echo "[DB] WARNING: mongod not found at $MONGOD, checking if already running..."
        if command -v mongosh >/dev/null 2>&1; then
            mongosh --quiet --eval "db.adminCommand('ping')" 2>/dev/null && echo "[DB] MongoDB is reachable" || echo "[DB] MongoDB not reachable"
        fi
    fi
else
    echo "[DB] MONGO_URL is external (non-localhost). Skipping local mongod."
fi

echo "Testing Python import..."
cd /home/runner/workspace/backend
python -c "print('[TEST] Python import OK'); from server import app; print('[TEST] FastAPI app import OK')" 2>&1 || {
    echo "FATAL: Python import failed!"
    exit 1
}

echo "Starting FastAPI server on 0.0.0.0:5000..."
exec python -m uvicorn server:app --host 0.0.0.0 --port 5000
