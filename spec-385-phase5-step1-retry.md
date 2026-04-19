# #385 Phase 5 Step 1 — RETRY with pinned version

## What & Why

הניסיון הקודם של Step 1 נעצר נכון: `yarn add @capacitor/ios` בלי טווח גרסה גרם ל-yarn לבחור v8.3.1 האחרון, שלא תואם ל-Capacitor stack הנעול ל-v7.6.1 (`@capacitor/core`, `@capacitor/android`, `@capacitor/cli`). ערבוב major versions היה שובר את Android.

**התיקון:** pin את @capacitor/ios לטווח 7.6.x באמצעות `@^7.6.1`. כל שאר הספק נשאר זהה.

## Pre-existing state (post previous attempt)

* `git status` נקי אצל Replit — ה-`yarn add → yarn remove` ביטלו זה את זה.
* `frontend/ios/` עדיין לא קיים.
* `@capacitor/ios` עדיין לא ב-`package.json`.
* commit `d6bb2e1` הוא artifact של Replit Agent (עדכון `review.txt` בלבד) — מתעלמים ממנו.
* שאר ה-stack נשאר: `@capacitor/android@^7.6.1`, `@capacitor/core@^7.6.1`, `@capacitor/cli@^7.6.1`.

## Done looks like

זהה לספק המקורי של Step 1:

* `@capacitor/ios` ב-`frontend/package.json` עם `^7.6.x` — **אותו major כמו `@capacitor/android`**.
* `frontend/ios/App/` קיים עם: `App.xcworkspace/`, `App.xcodeproj/`, `Podfile`, `App/Info.plist`, `App/capacitor.config.json`.
* `frontend/ios/.gitignore` קיים (אוטומטי מ-Capacitor CLI).
* `cd frontend && CI=true REACT_APP_BACKEND_URL="https://api.brikops.com" yarn build` → `Compiled successfully.`
* `git diff HEAD~1 HEAD --name-only | grep "^frontend/src/"` → ריק.
* `git diff HEAD~1 HEAD -- frontend/capacitor.config.json` → ריק.
* commit מקומי בלבד — **אין `git push`**.

## Out of scope

זהה לספק המקורי:
* `@capacitor-community/apple-sign-in` — Step 2.
* כל שינוי ב-`frontend/src/`.
* Xcode config — Zahi במק.
* App Store Connect — Zahi בדפדפן.
* `pod install` — Step 2.
* שינויים ב-`frontend/android/` או ב-Capacitor plugin versions.

## ⚠️ Failure paths

**1. אם `yarn add @capacitor/ios@^7.6.1` מחזיר `No matching version found`:**
- עצור, אל תריץ `yarn add @capacitor/ios` בלי טווח.
- דווח ל-Zahi — ייתכן ש-Capacitor הסיר v7 מ-npm (לא צפוי).
- לא לבצע upgrade ל-v8 של כל ה-stack בלי הוראה חדשה.

**2. אם ה-fetch נתקע מעל 3 דקות (כמו @capgo/capacitor-updater בעבר):**
- עצור, עשה `yarn remove @capacitor/ios` אם הותקן חלקית.
- דווח ל-Zahi שיריץ ידנית על ה-Mac.

**3. אם `npx cap add ios` נכשל אחרי התקנה מוצלחת:**
- עצור, דווח את ה-error המלא.
- אל תנסה לתקן יצירתית — יש כאן dependencies לא ברורות שרלוונטיות רק ל-macOS.

## Steps

1. `cd frontend && yarn add @capacitor/ios@^7.6.1`
   - אישור: הגרסה ב-`package.json` היא `^7.6.x`, לא `^8.x.x`.
   - אם נכשל או נתקע — ראה Failure paths.

2. `cd frontend && npx cap add ios`
   - אם ה-CLI מבקש `npx cap sync ios` קודם — הרץ אותו.

3. אימות שקבצי iOS נוצרו:
   ```
   ls frontend/ios/App/App.xcworkspace
   ls frontend/ios/App/App.xcodeproj
   ls frontend/ios/App/Podfile
   ls frontend/ios/App/App/Info.plist
   ls frontend/ios/App/App/capacitor.config.json
   cat frontend/ios/.gitignore
   ```
   כל אחד חייב להחזיר קובץ/תיקייה תקפים.

4. Build sanity:
   ```
   cd frontend && CI=true REACT_APP_BACKEND_URL="https://api.brikops.com" yarn build 2>&1 | tail -20
   ```
   Expected: `Compiled successfully.` בלי warnings חדשים.

5. Commit בלבד. DO NOT PUSH:
   ```
   git add frontend/ios/ frontend/package.json frontend/yarn.lock
   git commit -m "feat(#385 Phase 5 Step 1): bootstrap iOS Capacitor platform"
   ```
   **אל תריץ `git push`** בשום מקרה.

## Relevant files

* `frontend/package.json`
* `frontend/yarn.lock`
* `frontend/ios/` (נוצר במשימה)

## DO NOT

- ❌ `yarn add @capacitor/ios` ללא `@^7.6.1` — יבחר v8, ישבור את Android.
- ❌ `yarn upgrade` / שינוי גרסאות של `@capacitor/android`, `@capacitor/core`, `@capacitor/cli`.
- ❌ כל שינוי ב-`frontend/src/` או `frontend/capacitor.config.json`.
- ❌ `pod install` — זה Step 2.
- ❌ `git push` — Zahi דוחף דרך `./deploy.sh --prod`.
- ❌ להמציא גרסאות — אם `^7.6.1` לא קיים, עצור ודווח.

## VERIFY

1. **Version pinned correctly:**
   ```
   grep "@capacitor/ios" frontend/package.json
   ```
   Expected: שורה עם `"@capacitor/ios": "^7.6.x"` (לא `^8.x`).

2. **iOS folder created:**
   ```
   ls frontend/ios/App/App.xcworkspace/contents.xcworkspacedata
   ```
   Expected: קיים.

3. **Build passes:**
   ```
   cd frontend && CI=true REACT_APP_BACKEND_URL="https://api.brikops.com" yarn build 2>&1 | tail -5
   ```
   Expected: `Compiled successfully.`

4. **No src touched:**
   ```
   git diff HEAD~1 HEAD --name-only | grep "^frontend/src/"
   ```
   Expected: ריק.

5. **capacitor.config.json untouched:**
   ```
   git diff HEAD~1 HEAD -- frontend/capacitor.config.json
   ```
   Expected: ריק.

## דיווח

- commit SHA
- `git diff HEAD~1 HEAD --stat` (ציפייה: הרבה קבצים חדשים ב-`frontend/ios/` + עדכון `package.json` + `yarn.lock`)
- `ls frontend/ios/App/`
- `grep "@capacitor/ios" frontend/package.json`
- 5 שורות אחרונות של `yarn build`
- אישור מפורש ש**לא** רצת `git push`
