#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

MODE="dry"
YES="0"
SKIP_CHECKS="${SKIP_CHECKS:-0}"
FRONTEND_BACKEND_URL="${FRONTEND_BACKEND_URL:-https://api.brikops.com}"
RUN_LINT="${RUN_LINT:-0}"
MSG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod|--force) MODE="prod"; shift ;;
    --yes)          YES="1"; shift ;;
    --skip-checks)  SKIP_CHECKS=1; shift ;;
    *)              MSG="${MSG:+$MSG }$1"; shift ;;
  esac
done

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$MODE" == "prod" && "$branch" != "main" ]]; then
  echo "ERROR: You are on branch '$branch'. Switch to 'main' to deploy."
  exit 1
fi

has_uncommitted=0
if [[ -n "$(git status --porcelain)" ]]; then
  has_uncommitted=1
fi

ahead="$(git rev-list --count "origin/$branch..HEAD" 2>/dev/null || echo 0)"

if [[ $has_uncommitted -eq 0 && "$ahead" -eq 0 ]]; then
  echo "Nothing to deploy (no changes, nothing to push)."
  exit 0
fi

frontend_changed=0
backend_changed=0

check_files() {
  local f
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if [[ "$f" == frontend/* ]]; then frontend_changed=1; fi
    if [[ "$f" == backend/* ]]; then backend_changed=1; fi
  done
}

if [[ $has_uncommitted -eq 1 ]]; then
  { git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sort -u | check_files
fi
if [[ "$ahead" -gt 0 ]]; then
  git diff --name-only "origin/$branch..HEAD" | check_files
fi

check_frontend_staleness() {
  local bundle
  bundle=$(ls -t frontend/build/static/js/main*.js 2>/dev/null | head -1)
  if [[ -z "$bundle" ]]; then
    echo "[STALE BUILD] No frontend bundle found — will rebuild"
    frontend_changed=1
    return
  fi
  local bundle_ts
  bundle_ts=$(stat -c "%Y" "$bundle" 2>/dev/null || echo 0)

  local newest_src=0
  local inputs=(
    "frontend/src"
    "frontend/public"
  )
  local input_files=(
    "frontend/package.json"
    "frontend/yarn.lock"
    "frontend/craco.config.js"
    "frontend/tailwind.config.js"
    "frontend/postcss.config.js"
  )

  for dir in "${inputs[@]}"; do
    if [[ -d "$dir" ]]; then
      local dir_newest
      dir_newest=$(find "$dir" -type f -printf '%T@\n' 2>/dev/null | sort -rn | head -1 | cut -d. -f1)
      if [[ -n "$dir_newest" ]] && (( dir_newest > newest_src )); then
        newest_src=$dir_newest
      fi
    fi
  done

  for f in "${input_files[@]}"; do
    if [[ -f "$f" ]]; then
      local f_ts
      f_ts=$(stat -c "%Y" "$f" 2>/dev/null || echo 0)
      if (( f_ts > newest_src )); then
        newest_src=$f_ts
      fi
    fi
  done

  if (( newest_src > bundle_ts )); then
    local src_date bundle_date
    src_date=$(date -d "@$newest_src" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$newest_src")
    bundle_date=$(date -d "@$bundle_ts" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$bundle_ts")
    echo "[STALE BUILD] Frontend source ($src_date) is newer than build ($bundle_date) — will rebuild"
    frontend_changed=1
  fi
}

check_frontend_staleness

echo "=== Deploy Status ==="
if [[ $has_uncommitted -eq 1 ]]; then
  echo "Uncommitted changes:"
  git status --short
  echo
fi
if [[ "$ahead" -gt 0 ]]; then
  echo "Commits ahead of origin: $ahead"
  git log --oneline "origin/$branch..HEAD"
  echo
fi

echo "What will deploy:"
if [[ $frontend_changed -eq 1 ]]; then echo "  - Frontend (Cloudflare Pages -> https://app.brikops.com)"; fi
if [[ $backend_changed -eq 1 ]]; then echo "  - Backend  (GitHub Actions -> https://api.brikops.com)"; fi
if [[ $frontend_changed -eq 0 && $backend_changed -eq 0 ]]; then echo "  - Config/docs only (no pipeline trigger)"; fi
echo

if [[ "$MODE" != "prod" ]]; then
  echo "Dry-run only. To deploy:"
  echo "  ./deploy.sh --prod"
  echo "  ./deploy.sh --prod \"my commit message\""
  echo "  ./deploy.sh --prod --yes          # skip confirmation"
  echo "  ./deploy.sh --prod --skip-checks  # skip preflight"
  exit 0
fi

if [[ $has_uncommitted -eq 1 ]]; then
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
fi

if [[ $SKIP_CHECKS -eq 0 ]]; then
  echo "Preflight checks..."
  if [[ $backend_changed -eq 1 ]]; then
    echo "[backend] python3 -m compileall backend/ -q"
    python3 -m compileall backend/ -q
    echo "[backend] OK"
  fi
  if [[ $frontend_changed -eq 1 ]]; then
    if [[ "$RUN_LINT" == "1" ]]; then
      echo "[frontend] eslint"
      (cd frontend && npx eslint src/ --quiet)
      echo "[frontend] eslint OK"
    fi
    echo "[frontend] yarn build (REACT_APP_BACKEND_URL=$FRONTEND_BACKEND_URL)"
    (cd frontend && REACT_APP_BACKEND_URL="$FRONTEND_BACKEND_URL" yarn build)
    new_bundle=$(ls -t frontend/build/static/js/main*.js 2>/dev/null | head -1)
    if [[ -z "$new_bundle" ]]; then
      echo "[frontend] ERROR: build produced no bundle — aborting"
      exit 1
    fi
    bundle_name=$(basename "$new_bundle")
    bundle_size=$(( $(stat -c "%s" "$new_bundle") / 1024 ))
    bundle_time=$(date -d "@$(stat -c '%Y' "$new_bundle")" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || stat -c '%Y' "$new_bundle")
    echo "[frontend] Build verified: ${bundle_name} (${bundle_size}KB) at ${bundle_time}"
  fi
  echo
else
  echo "Preflight checks skipped."
  echo
fi

if [[ "$YES" != "1" ]]; then
  read -rp "Deploy to production? (y/N): " confirm
  if [[ "${confirm,,}" != "y" ]]; then
    echo "Cancelled."
    exit 0
  fi
fi

echo
echo "Deploying..."

if [[ $has_uncommitted -eq 1 ]]; then
  git add -A
  git commit -m "${MSG:-deploy: $(date '+%Y-%m-%d %H:%M')}" || true
fi

git push origin "$branch"

SHA="$(git rev-parse --short HEAD)"
echo
echo "Pushed successfully. (commit: $SHA)"
echo
if [[ $frontend_changed -eq 1 ]]; then echo "  Frontend updating: https://app.brikops.com (~1 min)"; fi
if [[ $backend_changed -eq 1 ]]; then echo "  Backend updating:  https://api.brikops.com (~2 min)"; fi
echo
echo "Monitor: https://github.com/zahis10/brikops-new/actions"
echo "Health:  https://api.brikops.com/health"
