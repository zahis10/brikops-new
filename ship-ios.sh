#!/usr/bin/env bash
# ship-ios.sh — סנכרון מלא + הכנה ל-Xcode Archive בפקודה אחת
# שימוש: ./ship-ios.sh
#
# מטפל ב:
# 1. קומיט אוטומטי של שינויים מקומיים (אייקונים, Xcode config)
# 2. משיכת קוד חדש מ-Replit
# 3. דחיפה חזרה כדי לסנכרן
# 4. npm build + cap sync ios
# 5. פתיחת Xcode - נשאר רק Archive + Upload

set -euo pipefail
cd "$(dirname "$0")"

echo "═══════════════════════════════════════"
echo " BrikOps — Ship iOS"
echo "═══════════════════════════════════════"

# 1. קומיט שינויים מקומיים אם יש
if [[ -n "$(git status --porcelain)" ]]; then
  echo
  echo "► שומר שינויים מקומיים..."
  git add -A
  MSG="chore: local iOS/Android sync $(date '+%Y-%m-%d %H:%M')"
  git commit -m "$MSG" || true
  echo "  ✓ נשמר: $MSG"
else
  echo
  echo "► אין שינויים מקומיים לקומיט."
fi

# 2. משיכת קוד מ-Replit
echo
echo "► מושך עדכונים מ-Replit..."
git pull --rebase origin main

# 3. דחיפה לאחר pull
echo
echo "► מסנכרן בחזרה ל-Replit..."
git push origin main

# 4. בנייה + סנכרון ל-iOS
echo
echo "► בונה frontend..."
cd frontend
rm -rf build
npm run build

echo
echo "► מסנכרן ל-iOS..."
npx cap sync ios

# 5. פתיחת Xcode
echo
echo "► פותח Xcode..."
npx cap open ios

cd ..
echo
echo "═══════════════════════════════════════"
echo " ✓ מוכן ל-Archive"
echo "═══════════════════════════════════════"
echo
echo "ב-Xcode עכשיו:"
echo "  1. Product → Clean Build Folder  (⇧⌘K)"
echo "  2. Product → Archive"
echo "  3. Distribute App → App Store Connect → Upload"
echo
