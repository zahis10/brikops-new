#!/bin/bash
set -e
cd /home/runner/workspace/frontend
export REACT_APP_BACKEND_URL=''
export REACT_APP_GIT_SHA=$(git -C /home/runner/workspace rev-parse --short HEAD 2>/dev/null || echo "unknown")
yarn build
echo "Frontend build complete"
