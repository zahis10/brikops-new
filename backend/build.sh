#!/bin/bash
set -e

echo "=== BrikOps Build Start ==="
echo "Date: $(date)"
echo "PWD: $(pwd)"

echo "--- Step 1: Install frontend dependencies ---"
cd /home/runner/workspace/frontend

if [ -f yarn.lock ]; then
    echo "Found yarn.lock, using yarn install"
    yarn install --frozen-lockfile 2>/dev/null || yarn install
else
    echo "No yarn.lock, running yarn install"
    yarn install
fi

echo "--- Step 2: Build frontend ---"
GENERATE_SOURCEMAP=false yarn build

if [ ! -d "build" ]; then
    echo "ERROR: Frontend build directory not found after build!"
    exit 1
fi

echo "--- Step 3: Verify build output ---"
ls -la build/
echo "index.html exists: $(test -f build/index.html && echo YES || echo NO)"

echo "=== BrikOps Build Complete ==="
exit 0
