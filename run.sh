#!/bin/bash
set -e
/home/runner/workspace/.local/bin/mongod --dbpath /home/runner/workspace/.data/db --port 27017 --bind_ip 127.0.0.1 --fork --logpath /home/runner/workspace/.data/mongod.log 2>/dev/null || true
cd /home/runner/workspace/backend
export RELEASE_SHA=$(git rev-parse --short HEAD)
exec python -m uvicorn server:app --host 0.0.0.0 --port 5000
