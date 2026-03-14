#!/bin/bash
set -e

echo "[POST-MERGE] Rebuilding frontend..."
cd frontend && REACT_APP_BACKEND_URL="" npx craco build 2>&1
echo "[POST-MERGE] Frontend rebuild complete."
