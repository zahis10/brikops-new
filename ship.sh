#!/usr/bin/env bash
# ship.sh — סקריפט מאוחד iOS + Android
#
# מזהה אוטומטית מה השתנה מאז הפעם האחרונה שהעלית native build,
# ופותח רק את ה-IDE שצריך:
#   • שינוי ב-ios/ בלבד → Xcode
#   • שינוי ב-android/ בלבד → Android Studio
#   • שינוי בשניהם → שניהם
#   • שינוי רק ב-frontend/src/ → כלום, Capgo OTA יטפל
#
# דגלים (override):
#   ./ship.sh --ios       — כפה פתיחת Xcode גם אם לא זוהה שינוי
#   ./ship.sh --android   — כפה פתיחת Android Studio
#   ./ship.sh --both      — כפה את שניהם
#   ./ship.sh --skip-sync — דלג על pull/push (אם כבר סנכרנת ידנית)

set -euo pipefail
cd "$(dirname "$0")"

# ── דגלים ─────────────────────────────────────────────
FORCE_IOS=false
FORCE_ANDROID=false
SKIP_SYNC=false
for arg in "$@"; do
  case "$arg" in
    --ios) FORCE_IOS=true ;;
    --android) FORCE_ANDROID=true ;;
    --both) FORCE_IOS=true; FORCE_ANDROID=true ;;
    --skip-sync) SKIP_SYNC=true ;;
    *) echo "⚠️  דגל לא מוכר: $arg"; exit 1 ;;
  esac
done

MARKER=".last-ship-sha"

echo "═══════════════════════════════════════"
echo " BrikOps — Ship (iOS + Android)"
echo "═══════════════════════════════════════"

# ── 1. קומיט שינויים מקומיים ─────────────────────────
if [[ -n "$(git status --porcelain)" ]]; then
  echo
  echo "► שומר שינויים מקומיים..."
  git add -A

  # 🔒 Secret-scan: refuse to commit files containing credentials.
  # Root-cause prevention for 2026-05-16 secrets leak incident.
  # Override (false positives only): SHIP_SKIP_SECRET_SCAN=1 ./ship.sh
  if [[ "${SHIP_SKIP_SECRET_SCAN:-0}" != "1" ]]; then
    STAGED_FILES="$(git diff --cached --name-only)"
    if [ -n "$STAGED_FILES" ]; then
      SECRETS_FOUND=""
      while IFS= read -r f; do
        [ -z "$f" ] && continue
        [ ! -f "$f" ] && continue
        # Skip binary files
        file -b "$f" 2>/dev/null | grep -qE "binary|ELF|image|video" && continue

        if grep -qE "mongodb(\+srv)?://[^:/]+:[^@]+@" "$f" 2>/dev/null; then
          SECRETS_FOUND="$SECRETS_FOUND\n  $f: MongoDB credentials"
        fi
        if grep -qE "AKIA[A-Z0-9]{16}" "$f" 2>/dev/null; then
          SECRETS_FOUND="$SECRETS_FOUND\n  $f: AWS access key"
        fi
        if grep -qE "JWT_SECRET[[:space:]]*[:=][[:space:]]*['\"]?[A-Za-z0-9+/=_-]{16,}" "$f" 2>/dev/null; then
          SECRETS_FOUND="$SECRETS_FOUND\n  $f: JWT_SECRET with real value"
        fi
        if grep -qE "EAA[A-Za-z0-9_-]{100,}" "$f" 2>/dev/null; then
          SECRETS_FOUND="$SECRETS_FOUND\n  $f: WhatsApp/Meta access token"
        fi
        if grep -qE "AC[a-f0-9]{32}" "$f" 2>/dev/null; then
          SECRETS_FOUND="$SECRETS_FOUND\n  $f: Twilio SID"
        fi
        if grep -qE "sk_(test|live)_[A-Za-z0-9]{20,}" "$f" 2>/dev/null; then
          SECRETS_FOUND="$SECRETS_FOUND\n  $f: Stripe key"
        fi
        if grep -qE "BEGIN.*PRIVATE KEY|BEGIN OPENSSH" "$f" 2>/dev/null; then
          SECRETS_FOUND="$SECRETS_FOUND\n  $f: Private key (PEM)"
        fi
      done <<< "$STAGED_FILES"

      if [ -n "$SECRETS_FOUND" ]; then
        echo
        echo "🚨 SECRETS DETECTED IN STAGED FILES — ABORTING COMMIT"
        echo -e "$SECRETS_FOUND"
        echo
        echo "Root-cause prevention for 2026-05-16 incident."
        echo "If this is a false positive:"
        echo "  SHIP_SKIP_SECRET_SCAN=1 ./ship.sh"
        echo
        exit 2
      fi
    fi
  else
    echo "  ⚠️  SHIP_SKIP_SECRET_SCAN=1 — secret-scan דולג (use with care)"
  fi

  MSG="chore: local native sync $(date '+%Y-%m-%d %H:%M')"
  git commit -m "$MSG" || true
  echo "  ✓ נשמר: $MSG"

  # 🔒 Push immediately to prevent local-only commits (incident 2026-05-16).
  # The root cause of the leak was that ship.sh left commits local.
  # If push fails (non-FF), HALT loud — do NOT continue.
  echo
  echo "► דוחף מיד ל-origin (מניעת local-only commits)..."
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  if ! git push origin "$current_branch"; then
    echo
    echo "🚨 git push FAILED — הקומיט עכשיו LOCAL-ONLY."
    echo "   זו בדיוק הסיבה השורש של דליפת הסודות מ-2026-05-16."
    echo "   חובה לפתור לפני שממשיכים:"
    echo "   - אם non-FF: git pull --rebase origin $current_branch"
    echo "   - אחר כך הרץ שוב ./ship.sh"
    exit 1
  fi
  echo "  ✓ נדחף ל-origin/$current_branch"
else
  echo
  echo "► אין שינויים מקומיים לקומיט."
fi

# ── 2. משיכת עדכונים מ-Replit ────────────────────────
# (Push כבר בוצע מיד אחרי הקומיט בשלב 1 — אין יותר push כפול
#  או hardcoded "main" שעלול לדחוף את ה-staging branch ל-main.)
if [[ "$SKIP_SYNC" == "false" ]]; then
  echo
  echo "► מושך עדכונים מ-Replit..."
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  git pull --rebase origin "$current_branch"
fi

# ── 3. זיהוי מה השתנה מאז ה-ship האחרון ──────────────
LAST_SHA=""
if [[ -f "$MARKER" ]]; then
  LAST_SHA="$(cat "$MARKER")"
fi
CURRENT_SHA="$(git rev-parse HEAD)"

NEEDS_IOS=false
NEEDS_ANDROID=false

if [[ -z "$LAST_SHA" ]]; then
  echo
  echo "► אין marker קודם — מתייחס כהעלאה ראשונה לשניהם."
  NEEDS_IOS=true
  NEEDS_ANDROID=true
elif [[ "$LAST_SHA" == "$CURRENT_SHA" ]]; then
  echo
  echo "► אין קומיטים חדשים מאז ה-ship האחרון ($LAST_SHA)."
else
  echo
  echo "► בודק מה השתנה מאז $LAST_SHA → $CURRENT_SHA..."
  CHANGED="$(git diff --name-only "$LAST_SHA" "$CURRENT_SHA")"

  # native iOS: frontend/ios/ או אייקונים/config
  if echo "$CHANGED" | grep -qE "^(frontend/ios/|frontend/capacitor\.config|frontend/package\.json)"; then
    NEEDS_IOS=true
  fi

  # native Android: frontend/android/
  if echo "$CHANGED" | grep -qE "^(frontend/android/|frontend/capacitor\.config|frontend/package\.json)"; then
    NEEDS_ANDROID=true
  fi

  # שינויי web (src/public) → לא native, Capgo יטפל
  if echo "$CHANGED" | grep -qE "^frontend/(src/|public/)" && ! $NEEDS_IOS && ! $NEEDS_ANDROID; then
    echo "  ► זוהו רק שינויי web — Capgo OTA יטפל, אין צורך ב-archive."
  fi
fi

# דגלי כפיה דורסים את הזיהוי האוטומטי
$FORCE_IOS && NEEDS_IOS=true
$FORCE_ANDROID && NEEDS_ANDROID=true

echo
echo "► החלטה:"
echo "    iOS:     $NEEDS_IOS"
echo "    Android: $NEEDS_ANDROID"

# אם אף אחד לא צריך — סיום
if [[ "$NEEDS_IOS" == "false" && "$NEEDS_ANDROID" == "false" ]]; then
  echo
  echo "═══════════════════════════════════════"
  echo " ✓ אין צורך ב-native build"
  echo "   Capgo OTA יעדכן את הטלפונים אוטומטית"
  echo "═══════════════════════════════════════"
  exit 0
fi

# ── 4. בניית frontend (פעם אחת, לשניהם) ──────────────
echo
echo "► בונה frontend..."
cd frontend
rm -rf build
npm run build
cd ..

# ── 5. sync + פתיחת IDE לכל פלטפורמה שצריכה ──────────
if [[ "$NEEDS_IOS" == "true" ]]; then
  echo
  echo "► מסנכרן ל-iOS..."
  (cd frontend && npx cap sync ios)
  echo
  echo "► פותח Xcode..."
  (cd frontend && npx cap open ios)
fi

if [[ "$NEEDS_ANDROID" == "true" ]]; then
  echo
  echo "► מסנכרן ל-Android..."
  (cd frontend && npx cap sync android)
  echo
  echo "► פותח Android Studio..."
  (cd frontend && npx cap open android)
fi

# ── 6. עדכון marker ──────────────────────────────────
echo "$CURRENT_SHA" > "$MARKER"

echo
echo "═══════════════════════════════════════"
echo " ✓ מוכן להעלאה"
echo "═══════════════════════════════════════"
echo

if [[ "$NEEDS_IOS" == "true" ]]; then
  echo "ב-Xcode:"
  echo "  1. Product → Clean Build Folder  (⇧⌘K)"
  echo "  2. Product → Archive"
  echo "  3. Distribute App → App Store Connect → Upload"
  echo
fi

if [[ "$NEEDS_ANDROID" == "true" ]]; then
  echo "ב-Android Studio:"
  echo "  1. Build → Clean Project"
  echo "  2. Build → Generate Signed Bundle / APK → Android App Bundle (.aab)"
  echo "  3. העלה את ה-.aab ל-Play Console → Production → Create new release"
  echo
fi

echo "לאחר העלאה מוצלחת, ה-marker עודכן ל-$CURRENT_SHA —"
echo "ההרצה הבאה תזהה רק את מה שהשתנה מכאן והלאה."
