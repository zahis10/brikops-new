# #385 Phase 5 Step 1 — Bootstrap iOS Platform in Capacitor

## What & Why

ב-Phase 1-4 הוקם Apple Sign-In ל-web + Android bundled mode. Phase 5 מוסיף iOS native — המטרה המקורית של Apple Guideline 4.8 ל-App Store submission.

**Step 1 הוא bootstrap בלבד.** אין קוד, אין Apple Sign-In integration עדיין. רק הוספת הפלטפורמה ל-Capacitor כך שתיווצר תיקיית `frontend/ios/` עם Xcode project מוכן להמשך עבודה.

Step 2 יוסיף את ה-plugin של Apple Sign-In ואת שינויי ה-frontend code — **זה לא חלק מהspec הזה**.

## Pre-existing state (verified)

* `frontend/package.json` — יש `@capacitor/android` ו-`@capacitor/core` גרסה 7.6.1. **אין** `@capacitor/ios`.
* `frontend/ios/` — לא קיים בכלל.
* `frontend/capacitor.config.json` — יש `appId: "com.brikops.app"`, `webDir: "build"`, `iosScheme: "https"`, `hostname: "app.brikops.com"`. זה כבר מוכן ל-iOS.
* `frontend/build/` — קיים עם bundle מעודכן מ-Phase 2 (deploy.sh האחרון).

## Done looks like

* `@capacitor/ios` מופיע ב-`frontend/package.json` עם אותה גרסה כמו `@capacitor/android` (כרגע `^7.6.1`).
* תיקייה `frontend/ios/App/` קיימת עם הקבצים הסטנדרטיים של Capacitor iOS:
  * `frontend/ios/App/App.xcworkspace/` (לפתיחה ב-Xcode)
  * `frontend/ios/App/App.xcodeproj/`
  * `frontend/ios/App/Podfile`
  * `frontend/ios/App/App/Info.plist`
  * `frontend/ios/App/App/capacitor.config.json` (mirror של frontend/capacitor.config.json)
* `frontend/ios/.gitignore` קיים (אוטומטי מ-Capacitor CLI) — מתעלם מ-`App/Pods/`, `App/build/`.
* `yarn build` — עדיין עובד, אין warnings חדשים.
* אין שינוי ב-`frontend/src/` בכלל.
* Google / Apple / phone auth flows — לא נגעו, עובדים כרגיל.

## Out of scope

* `@capacitor-community/apple-sign-in` — Phase 5 Step 2.
* שינויים ב-`LoginPage.js` / `OnboardingPage.js` — Phase 5 Step 2.
* Xcode configuration (Team, capabilities, Bundle ID) — Zahi עושה במק שלו.
* `App Store Connect` listing — Zahi עושה בדפדפן.
* `cap sync ios` לא חייב להריץ ב-CI — זה ירוץ בפעמים הבאות אוטומטית דרך הסקריפטים של Zahi.
* Pod install — לא צריך עכשיו (זה יקרה בשלב 2 עם הוספת הplugin).
* Capgo / OTA — אין השפעה; אותו bundle, אותה תשתית.

## Steps

### 1. Install `@capacitor/ios`

```bash
cd frontend
yarn add @capacitor/ios
```

יוודא שהגרסה מתואמת עם שאר חבילות `@capacitor/*` שכבר בפרויקט (7.6.1). אם Yarn בוחר גרסה אחרת (למשל 7.x.x major מעודכן) — **עצור ודווח** לפני ההמשך.

### 2. Add iOS platform via Capacitor CLI

```bash
cd frontend
npx cap add ios
```

זה יוצר את `frontend/ios/App/` עם כל ה-Xcode project. אם הפקודה דורשת `cap sync` לפני — הרץ:

```bash
cd frontend
npx cap sync ios
```

### 3. Verify files created

בדוק שכל הקבצים הבאים קיימים:

```bash
ls -la frontend/ios/App/App.xcworkspace
ls -la frontend/ios/App/App.xcodeproj
ls -la frontend/ios/App/Podfile
ls -la frontend/ios/App/App/Info.plist
ls -la frontend/ios/App/App/capacitor.config.json
cat frontend/ios/.gitignore
```

כל אחד אמור להחזיר קובץ / תיקייה תקפים.

### 4. Verify build still works

```bash
cd frontend
yarn build 2>&1 | tail -20
```

Expected: `Compiled successfully.` — בלי warnings חדשים.

### 5. Commit only. DO NOT PUSH.

```bash
git add frontend/ios/ frontend/package.json frontend/yarn.lock
git commit -m "feat(#385 Phase 5 Step 1): bootstrap iOS Capacitor platform"
```

**אל תעשה `git push` בשום מקרה.** Zahi דוחף בעצמו דרך `./deploy.sh --prod` מה-Mac שלו.

## Relevant files

* `frontend/package.json` — הוספת `@capacitor/ios` ל-dependencies
* `frontend/yarn.lock` — מעודכן אוטומטית
* `frontend/ios/**` — נוצר כולו אוטומטית מ-`npx cap add ios`

## DO NOT

- ❌ **אל תריץ `git push`.** Zahi pushה דרך `./deploy.sh --prod`.
- ❌ **אל תיגע ב-`frontend/src/`**. אין קוד Apple Sign-In ב-Step הזה.
- ❌ **אל תוסיף `@capacitor-community/apple-sign-in`.** זה Step 2.
- ❌ **אל תשנה את `frontend/capacitor.config.json`.** הוא כבר מוגדר נכון.
- ❌ **אל תעשה `pod install`** בתוך `frontend/ios/App/` — זה ירוץ אוטומטית ב-Step 2 כשנוסיף plugin.
- ❌ **אל תגע ב-`frontend/android/`.** Android stays untouched.
- ❌ **אל תעשה `cap sync`** אם אחד מה-platforms הקיימים לא עובד אחרי — עצור ודווח.
- ❌ **אל תשנה גרסאות של `@capacitor/android` או `@capacitor/core`** — השאר כמו שהן.

## VERIFY

1. **Dependency installed:**
   ```bash
   grep "@capacitor/ios" frontend/package.json
   ```
   Expected: שורה אחת עם הגרסה, למשל `"@capacitor/ios": "^7.6.1"`.

2. **iOS folder exists:**
   ```bash
   ls frontend/ios/App/App.xcworkspace/contents.xcworkspacedata
   ```
   Expected: הקובץ קיים.

3. **Info.plist created with Bundle ID:**
   ```bash
   grep -A1 CFBundleIdentifier frontend/ios/App/App/Info.plist
   ```
   Expected: מופיע Bundle ID (אוטומטי — כנראה `$(PRODUCT_BUNDLE_IDENTIFIER)` placeholder).

4. **Build clean:**
   ```bash
   cd frontend && yarn build 2>&1 | tail -5
   ```
   Expected: `Compiled successfully.`

5. **No src changes:**
   ```bash
   git diff HEAD~1 HEAD --name-only | grep "^frontend/src/"
   ```
   Expected: ריק.

6. **Capacitor config untouched:**
   ```bash
   git diff HEAD~1 HEAD -- frontend/capacitor.config.json
   ```
   Expected: ריק.

## דיווח אחרי שסיימת

- commit SHA
- פלט `git diff HEAD~1 HEAD --stat` (אמור להראות הוספה של `frontend/ios/*` + עדכון `package.json` + `yarn.lock`)
- פלט `ls frontend/ios/App/`
- פלט `grep "@capacitor/ios" frontend/package.json`
- פלט `yarn build 2>&1 | tail -5`
- confirmation ש**לא** עשית `git push`
