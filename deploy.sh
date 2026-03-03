#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PROD=0
SKIP_CHECKS="${SKIP_CHECKS:-0}"

FRONTEND_BACKEND_URL="${FRONTEND_BACKEND_URL:-https://api.brikops.com}"
RUN_LINT="${RUN_LINT:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod|--force)
      PROD=1
      shift
      ;;
    --skip-checks)
      SKIP_CHECKS=1
      shift
      ;;
    *)
      break
      ;;
  esac
done

MSG="${*:-}"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ $PROD -eq 1 && "$branch" != "main" ]]; then
  echo "ERROR: You are on branch '$branch'. Switch to 'main' to deploy."
  exit 1
fi

mapfile -t files < <(
  { git diff --name-only
    git diff --cached --name-only
    git ls-files --others --exclude-standard
  } | sed '/^$/d' | sort -u
)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "Nothing to deploy (no changes)."
  exit 0
fi

frontend_changed=0
backend_changed=0

for f in "${files[@]}"; do
  if [[ "$f" == frontend/* ]]; then
    frontend_changed=1
  elif [[ "$f" == backend/* ]]; then
    backend_changed=1
  fi
done

echo "Change summary:"
echo "--------------------------------"
git status --short
echo "--------------------------------"
echo

echo "What will deploy:"
if [[ $frontend_changed -eq 1 ]]; then echo "  - Frontend (Cloudflare Pages -> https://app.brikops.com)"; fi
if [[ $backend_changed -eq 1 ]]; then echo "  - Backend  (GitHub Actions -> https://api.brikops.com)"; fi
if [[ $frontend_changed -eq 0 && $backend_changed -eq 0 ]]; then echo "  - No frontend/backend changes (docs/config only)"; fi
echo

if [[ $PROD -eq 0 ]]; then
  echo "Dry-run only."
  echo "To deploy to production:"
  echo "  ./deploy.sh --prod"
  echo "  ./deploy.sh --prod \"my commit message\""
  echo
  echo "Options:"
  echo "  --skip-checks                 Skip preflight checks"
  echo "  SKIP_CHECKS=1 ./deploy.sh     Same as above"
  echo "  RUN_LINT=1 ./deploy.sh        Also run ESLint on frontend"
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
    MSG="deploy: update config/docs"
  fi
fi

if [[ $SKIP_CHECKS -eq 0 ]]; then
  echo "Preflight checks..."
  echo

  if [[ $backend_changed -eq 1 ]]; then
    echo "[backend] python3 -m compileall backend/ -q"
    python3 -m compileall backend/ -q
    echo "[backend] OK"
    echo
  fi

  if [[ $frontend_changed -eq 1 ]]; then
    if [[ "$RUN_LINT" == "1" ]]; then
      echo "[frontend] npx eslint src/ --quiet"
      (cd frontend && npx eslint src/ --quiet)
      echo "[frontend] eslint OK"
      echo
    fi

    echo "[frontend] yarn build (with REACT_APP_BACKEND_URL=$FRONTEND_BACKEND_URL)"
    (cd frontend && REACT_APP_BACKEND_URL="$FRONTEND_BACKEND_URL" yarn build)
    echo "[frontend] build OK"
    echo
  fi
else
  echo "Preflight checks skipped (--skip-checks)."
  echo
fi

echo "Commit message: $MSG"
echo
read -rp "Deploy to production? (y/N): " confirm
if [[ "${confirm,,}" != "y" ]]; then
  echo "Cancelled."
  exit 0
fi

echo
echo "Deploying to production..."

git add -A
git commit -m "$MSG" || { echo "Nothing new to commit."; exit 0; }
git push origin main

SHA="$(git rev-parse --short HEAD)"

echo
echo "Pushed successfully. (commit: $SHA)"
echo
if [[ $frontend_changed -eq 1 ]]; then
  echo "  Frontend updating on https://app.brikops.com (~1 min)"
fi
if [[ $backend_changed -eq 1 ]]; then
  echo "  Backend updating on https://api.brikops.com (~2 min)"
fi
echo
echo "Monitor: https://github.com/zahis10/brikops-new/actions"
echo "Health:  https://api.brikops.com/health"
