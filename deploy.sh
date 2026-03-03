#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PROD=0
MSG=""

if [[ "${1:-}" == "--prod" || "${1:-}" == "--force" ]]; then
  PROD=1
  shift || true
  MSG="${1:-}"
else
  MSG="${1:-}"
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ $PROD -eq 1 && "$branch" != "main" ]]; then
  echo "ERROR: You are on branch '$branch'. Switch to main to deploy."
  exit 1
fi

if git diff --quiet && git diff --cached --quiet; then
  echo "Nothing to deploy (no changes)."
  exit 0
fi

changed_files="$(git status --porcelain | awk '{print $2}')"

frontend_changed=0
backend_changed=0

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if [[ "$f" == frontend/* ]]; then
    frontend_changed=1
  elif [[ "$f" == backend/* ]]; then
    backend_changed=1
  fi
done <<< "$changed_files"

echo "Change summary:"
echo "------------------------------"
git status --short
echo "------------------------------"
echo ""
echo "What will deploy:"
if [[ $frontend_changed -eq 1 ]]; then echo "  - Frontend (Cloudflare Pages -> app.brikops.com)"; fi
if [[ $backend_changed -eq 1 ]]; then echo "  - Backend (GitHub Actions -> api.brikops.com)"; fi
if [[ $frontend_changed -eq 0 && $backend_changed -eq 0 ]]; then echo "  - No frontend/backend changes (config/docs only)"; fi
echo ""

if [[ $PROD -eq 0 ]]; then
  echo "Dry-run only. To deploy to production:"
  echo "  ./deploy.sh --prod"
  echo "  ./deploy.sh --prod \"my commit message\""
  exit 0
fi

if [[ -z "$MSG" ]]; then
  if [[ $frontend_changed -eq 1 && $backend_changed -eq 1 ]]; then
    MSG="deploy: update frontend and backend"
  elif [[ $frontend_changed -eq 1 ]]; then
    MSG="deploy: update frontend"
  elif [[ $backend_changed -eq 1 ]]; then
    MSG="deploy: update backend"
  else
    MSG="deploy: update config"
  fi
fi

echo "Commit message: $MSG"
echo ""
read -rp "Deploy to production? (y/N): " confirm
if [[ "${confirm,,}" != "y" ]]; then
  echo "Cancelled."
  exit 0
fi

echo ""
echo "Deploying to production..."

git add -A
git commit -m "$MSG" || { echo "Nothing new to commit."; exit 0; }
git push origin main

SHA="$(git rev-parse --short HEAD)"
echo ""
echo "Pushed successfully. (commit: $SHA)"
echo ""
if [[ $frontend_changed -eq 1 ]]; then
  echo "  Frontend updating on https://app.brikops.com (~1 min)"
fi
if [[ $backend_changed -eq 1 ]]; then
  echo "  Backend updating on https://api.brikops.com (~2 min)"
fi
echo ""
echo "Monitor: https://github.com/zahis10/brikops-new/actions"
echo "Health:  https://api.brikops.com/health"
