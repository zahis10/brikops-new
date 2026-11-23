#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

MODE="dry"
YES="0"
SKIP_CHECKS="${SKIP_CHECKS:-0}"
RUN_LINT="${RUN_LINT:-0}"
MSG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod|--force)   MODE="prod"; shift ;;
    --stag|--staging) MODE="stag"; shift ;;
    --yes)            YES="1"; shift ;;
    --skip-checks)    SKIP_CHECKS=1; shift ;;
    *)                MSG="${MSG:+$MSG }$1"; shift ;;
  esac
done

if [[ "$MODE" == "stag" ]]; then
  FRONTEND_BACKEND_URL="${FRONTEND_BACKEND_URL:-https://api-staging.brikops.com}"
else
  FRONTEND_BACKEND_URL="${FRONTEND_BACKEND_URL:-https://api.brikops.com}"
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$MODE" == "prod" && "$branch" != "main" ]]; then
  echo "ERROR: You are on branch '$branch'. Switch to 'main' to deploy."
  exit 1
fi
if [[ "$MODE" == "stag" && "$branch" != "staging" ]]; then
  echo "ERROR: You are on branch '$branch'. Switch to 'staging' to deploy to staging."
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
native_changed=0

check_files() {
  local f
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if [[ "$f" == frontend/* ]]; then frontend_changed=1; fi
    if [[ "$f" == backend/* || "$f" == .platform/* ]]; then backend_changed=1; fi
    if [[ "$f" == frontend/capacitor.config.json || "$f" == frontend/ios/* || "$f" == frontend/android/* ]]; then
      native_changed=1
    fi
    if [[ "$f" == frontend/package.json ]]; then
      if git diff -- frontend/package.json frontend/package.json 2>/dev/null | grep -qE '@capacitor|@capgo' \
         || git diff --cached -- frontend/package.json 2>/dev/null | grep -qE '@capacitor|@capgo' \
         || git diff "origin/$branch..HEAD" -- frontend/package.json 2>/dev/null | grep -qE '@capacitor|@capgo'; then
        native_changed=1
      fi
    fi
  done
}

if [[ $has_uncommitted -eq 1 ]]; then
  check_files < <({ git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sort -u)
fi
if [[ "$ahead" -gt 0 ]]; then
  check_files < <(git diff --name-only "origin/$branch..HEAD")
fi

check_frontend_staleness() {
  local bundle
  bundle=$(ls -t frontend/build/static/js/main*.js 2>/dev/null | head -1 || true)
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
if [[ $frontend_changed -eq 1 ]]; then
  if [[ "$MODE" == "stag" ]]; then
    echo "  - Frontend (Cloudflare Pages -> https://staging.brikops-new.pages.dev)"
  else
    echo "  - Frontend (Cloudflare Pages -> https://app.brikops.com)"
  fi
fi
if [[ $backend_changed -eq 1 ]]; then
  if [[ "$MODE" == "stag" ]]; then
    echo "  - Backend  (GitHub Actions -> https://api-staging.brikops.com)"
  else
    echo "  - Backend  (GitHub Actions -> https://api.brikops.com)"
  fi
fi
if [[ $frontend_changed -eq 0 && $backend_changed -eq 0 ]]; then echo "  - Config/docs only (no pipeline trigger)"; fi
echo

if [[ $native_changed -eq 1 ]]; then
  echo "⚠️  ═══════════════════════════════════════════════════"
  echo "   NATIVE CHANGES DETECTED"
  echo "   Files touched: capacitor.config.json / ios / android / capacitor plugins"
  echo "   ./deploy.sh --prod alone will NOT deliver these to the"
  echo "   installed iPhone/Android apps. After this deploy, you"
  echo "   MUST also run ./ship.sh on the Mac to rebuild the native"
  echo "   app and push to TestFlight / Play Store."
  echo "   ═══════════════════════════════════════════════════"
  echo
fi

if [[ "$MODE" != "prod" && "$MODE" != "stag" ]]; then
  echo "Dry-run only. To deploy:"
  echo "  ./deploy.sh --prod              # production (must be on main branch)"
  echo "  ./deploy.sh --stag              # staging    (must be on staging branch)"
  echo "  ./deploy.sh --prod \"my message\"  # with commit message"
  echo "  ./deploy.sh --prod --yes         # skip confirmation"
  echo "  ./deploy.sh --prod --skip-checks # skip preflight"
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

# --- GitHub login --------------------------------------------------------------
# This Shell gets its GitHub credential from Replit's GitHub connection (GIT_ASKPASS).
# The first request after a pause is sometimes turned down ("Invalid username or
# token"), or waits for an approval window in Replit, and the very same request
# passes a few seconds later. So: ask GitHub now, before the build (a --dry-run
# push logs in and sends nothing), and repeat a few times; the real push at the
# end is repeated the same way. GIT_TERMINAL_PROMPT=0: git never stops to ask for
# a user name or a password in the terminal — nobody should type a token here.
# (Emergency switch for the early check only: SKIP_GITHUB_CHECK=1 ./deploy.sh ...)
GITHUB_TRIES="${GITHUB_TRIES:-4}"
GITHUB_WAIT="${GITHUB_WAIT:-8}"
github_out=""

# github_push <name for the messages> <git push arguments...>
#   0 = went through
#   1 = still failing after $GITHUB_TRIES attempts
#   2 = GitHub rejected the push itself (repeating cannot help)
# git's output of the last attempt is left in $github_out.
github_push() {
  local what="$1"
  shift
  local n=1
  while true; do
    if github_out="$(GIT_TERMINAL_PROMPT=0 git push "$@" 2>&1)"; then
      return 0
    fi
    if grep -qE '\[(remote )?rejected\]|non-fast-forward|protected branch|does not match any' <<<"$github_out"; then
      return 2
    fi
    if (( n >= GITHUB_TRIES )); then
      return 1
    fi
    echo "[github] $what did not go through (attempt $n of $GITHUB_TRIES) - trying again in ${GITHUB_WAIT}s..."
    if (( n == 1 )); then
      echo "         If Replit shows a window asking to use your GitHub account, approve it."
    fi
    sleep "$GITHUB_WAIT"
    n=$((n + 1))
  done
}

github_rc=0
if [[ "${SKIP_GITHUB_CHECK:-0}" == "1" ]]; then
  echo "GitHub login check skipped."
  echo
else
  echo "Checking the GitHub login..."
  github_push "The GitHub login" --dry-run origin "$branch" || github_rc=$?
  if [[ $github_rc -eq 0 ]]; then
    echo "[github] OK"
    echo
  fi
fi
if [[ $github_rc -ne 0 ]]; then
  echo
  if [[ $github_rc -eq 2 ]]; then
    echo "[github] ERROR: GitHub would reject this push. Nothing was built and nothing was pushed."
  else
    echo "[github] ERROR: GitHub did not let us in. Nothing was built and nothing was pushed."
  fi
  echo "GitHub said:"
  sed 's/^/    /' <<<"$github_out"
  echo
  if [[ $github_rc -eq 2 ]]; then
    echo "This is not a login problem: GitHub refuses the push itself (see above)."
    echo "Do not force the push. Stop here and ask."
  else
    echo "What to do:"
    echo "  1. Run the same deploy command again, from a computer (not the phone)."
    echo "  2. Still failing? In your Replit account settings disconnect GitHub, connect it"
    echo "     again, and run the same command again."
    echo "  Do not type or paste a token or a password here."
  fi
  exit 1
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
  if [[ "$MODE" == "stag" ]]; then
    read -rp "Deploy to STAGING? (y/N): " confirm
  else
    read -rp "Deploy to production? (y/N): " confirm
  fi
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

github_rc=0
github_push "The push to GitHub" origin "$branch" || github_rc=$?
if [[ $github_rc -eq 0 ]]; then
  if [[ -n "$github_out" ]]; then
    echo "$github_out"
  fi
else
  echo
  echo "[github] ERROR: the push to GitHub did not go through. Everything else is done - only the push is missing."
  echo "GitHub said:"
  sed 's/^/    /' <<<"$github_out"
  echo
  if [[ $github_rc -eq 2 ]]; then
    echo "This is not a login problem: GitHub refuses the push itself (see above)."
    echo "Do not force the push. Stop here and ask."
  else
    echo "To finish, run this from a computer (not the phone):"
    if [[ "$MODE" == "prod" ]]; then
      echo "  git push origin main && git checkout staging"
    else
      echo "  git push origin staging"
    fi
    echo "Do not type or paste a token or a password here."
  fi
  exit 1
fi

SHA="$(git rev-parse --short HEAD)"

if [[ $frontend_changed -eq 1 ]]; then
  echo
  echo "[dev] Restoring local dev build (REACT_APP_BACKEND_URL=\"\")..."
  (cd frontend && REACT_APP_BACKEND_URL="" npx craco build 2>&1 | tail -3)
  echo "[dev] Dev preview restored — local build now uses relative URLs"
fi

echo
echo "═══════════════════════════════════════════════════"
echo " DEPLOY SUMMARY  (commit: $SHA)"
echo "═══════════════════════════════════════════════════"
echo
echo " Changes detected:"
if [[ $backend_changed -eq 1 ]]; then
  echo "   Backend  (backend/** .platform/**):  YES"
else
  echo "   Backend  (backend/** .platform/**):  NO"
fi
if [[ $frontend_changed -eq 1 ]]; then
  echo "   Frontend (frontend/**):              YES"
else
  echo "   Frontend (frontend/**):              NO"
fi
echo
echo " Deploy status:"
if [[ $backend_changed -eq 1 ]]; then
  echo "   Backend  (GitHub Actions → EB):      EXPECTED (~2 min)"
else
  echo "   Backend  (GitHub Actions → EB):      NOT EXPECTED"
  echo "     → no changes under backend/** or .platform/** — path filter skips"
fi
if [[ $frontend_changed -eq 1 ]]; then
  echo "   Frontend (Cloudflare Pages):         EXPECTED (~1 min)"
else
  echo "   Frontend (Cloudflare Pages):         NOT EXPECTED"
  echo "     → no changes under frontend/**"
fi
echo
echo " Where to check:"
echo "   Backend:   https://github.com/zahis10/brikops-new/actions"
if [[ "$MODE" == "stag" ]]; then
  echo "   Frontend:  https://staging.brikops-new.pages.dev"
  echo "   Health:    https://api-staging.brikops.com/health"
else
  echo "   Frontend:  https://app.brikops.com (Cloudflare Pages)"
  echo "   Health:    https://api.brikops.com/health"
fi
echo
echo "═══════════════════════════════════════════════════"
summary_line="✓ Push completed ($SHA)"
if [[ $frontend_changed -eq 1 ]]; then
  summary_line="$summary_line · Frontend → Cloudflare Pages"
else
  summary_line="$summary_line · Frontend → no deploy needed"
fi
if [[ $backend_changed -eq 1 ]]; then
  summary_line="$summary_line · Backend → GitHub Actions"
else
  summary_line="$summary_line · Backend → no deploy needed"
fi
if [[ $frontend_changed -eq 0 && $backend_changed -eq 0 ]]; then
  summary_line="✓ Push completed ($SHA) — no deploys expected (config/docs only)"
fi
echo " $summary_line"
echo "═══════════════════════════════════════════════════"

if [[ $native_changed -eq 1 ]]; then
  echo
  echo "⚠️  ═══════════════════════════════════════════════════"
  echo "   NATIVE CHANGES DETECTED — ./ship.sh STILL REQUIRED"
  echo "   This push touched capacitor.config.json / ios / android /"
  echo "   capacitor plugins. Capgo OTA cannot deliver native changes."
  echo "   Now run on the Mac:"
  echo "     cd ~/brikops-new && ./ship.sh"
  echo "   ═══════════════════════════════════════════════════"
fi
