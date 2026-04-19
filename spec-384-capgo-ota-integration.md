# #384 — Capgo OTA integration + bundled mode migration

## What & Why
כרגע האפליקציה של אנדרואיד טוענת את `app.brikops.com` דרך WebView (`server.url` ב-Capacitor config), כלומר כל deploy של Cloudflare Pages מגיע מיידית לטלפון. זה אפור אפורה לפי Apple 3.3.2 ולכן לא מתאים להגשה לאפל. המעבר: להפוך את האפליקציה ל-**bundled mode** (טוען bundle מקומי), ולהשתמש ב-**Capgo OTA** כדי לדחוף עדכוני JS/CSS ישירות לטלפון ללא הגשה לחנות. ההעלאה ל-Capgo תרוץ אוטומטית ב-GitHub Actions על כל push שמשנה `frontend/**`.

## Done looks like
- `@capgo/capacitor-updater` מותקן ב-frontend.
- הקובץ הראשי `frontend/capacitor.config.json` נקי (כבר נקי — לא נוגעים).
- ה-generated `frontend/android/app/src/main/assets/capacitor.config.json` (gitignored) יתחדש ללא `server` כש-Zahi ירוץ `cap sync android` ב-Phase 3.
- `App.js` קורא ל-`CapacitorUpdater.notifyAppReady()` מיד אחרי mount (בתוך ה-`useEffect` הקיים של `function App()`).
- GitHub Actions workflow חדש בשם `deploy-frontend-capgo.yml` מתפעל על push ל-main עם שינויים תחת `frontend/**`, בונה את ה-bundle עם כל ה-`REACT_APP_*` env vars הנדרשים ומעלה אותו ל-Capgo באמצעות `CAPGO_API_KEY` מ-GitHub Secrets.
- בסיום push: Capgo dashboard מציג bundle חדש עם commit SHA.
- גרסת אנדרואיד חדשה (`versionCode 2`) זמינה בטא ב-Play Console עם bundled mode.
- אחרי התקנת הגרסה החדשה בטלפון: push של שינוי קטן ל-main → תוך 30 שניות מפתיחת האפליקציה השינוי נקלט ללא צורך בעדכון מהחנות.

## Out of scope
- iOS build / הגשה לאפל (יגיע בספק נפרד אחרי Capgo מאומת על אנדרואיד).
- Sign in with Apple (ספק נפרד).
- שינויים ב-frontend config הראשי (`frontend/capacitor.config.json`) — הוא כבר נקי.
- שינויים ב-backend.

## Prerequisites — ✅ הושלמו על-ידי Zahi (2026-04-18)

### A. הגדרת Capgo dashboard — ✅
- אפליקציה `com.brikops.app` קיימת ב-Capgo.
- Channel `production` קיים ומוגדר כ-default.
- Upload-only API key קיים ומקושר.

### B. GitHub Secrets + Variables — ✅
**Secrets:**
- `CAPGO_API_KEY` (upload-only key מ-Capgo)
- `AWS_ROLE_ARN` (קיים מקודם — לא רלוונטי ל-workflow הזה)

**Variables (Repository):**
- `NODE_VERSION` = `20`
- `REACT_APP_BACKEND_URL` = `https://api.brikops.com`
- `REACT_APP_GOOGLE_CLIENT_ID` = `394294810491-u5q1t9vabqpumvuue422...`

**לא מוגדרים (כי לא היו ב-Cloudflare Pages Production):**
- `REACT_APP_ENABLE_REGISTER_MANAGEMENT_REDIRECTS` — נשאר default (false).
- `REACT_APP_ENABLE_DEV_LOGIN` — נשאר default (false). חשוב: אסור להוסיף בפרודקשן.

Cloudflare כרגע עדיין בונה את ה-frontend במקביל; אחרי verification מלא של Capgo נפרק את ה-automatic deployments של Cloudflare בספק נפרד.

## Tasks

### Phase 1 — Code changes

**1. התקנת ה-plugin:**
הפרויקט משתמש ב-**yarn** (ראה `deploy.sh` שורה 169 ו-`frontend/yarn.lock`).
```bash
cd frontend
yarn add @capgo/capacitor-updater
```
ודא ש-`yarn.lock` מתעדכן ונכנס ל-commit.

**2. Android config — NO-OP (skip).**
- `frontend/android/app/src/main/assets/capacitor.config.json` הוא **generated file גיטאיגנור** (ראה `frontend/android/.gitignore` שורה 99).
- הקובץ הראשי `frontend/capacitor.config.json` כבר נקי (אין `server` key, tracked, commit Task #251).
- ה-generated file יתחדש אוטומטית כש-Zahi ירוץ `npx cap sync android` ב-Phase 3.
- Replit: אל תיגע בשום capacitor.config.json. לא הראשי, לא ה-generated.

**3. הוספת `notifyAppReady()` ב-App.js:**
- קובץ: `frontend/src/App.js`
- **שורה 16** — אחרי `import { Capacitor } from '@capacitor/core';` — הוסף:
```js
import { CapacitorUpdater } from '@capgo/capacitor-updater';
```
- **שורות 459-466** — ב-`function App()` כבר יש `useEffect` עם בדיקת `isNativePlatform()` שמגדיר StatusBar. **הוסף בתוך אותו if — לא תיצור useEffect חדש.**

**לפני:**
```js
function App() {
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      StatusBar.setOverlaysWebView({ overlay: false });
      StatusBar.setBackgroundColor({ color: '#0F172A' });
      StatusBar.setStyle({ style: Style.Dark });
    }
  }, []);
```

**אחרי:**
```js
function App() {
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      StatusBar.setOverlaysWebView({ overlay: false });
      StatusBar.setBackgroundColor({ color: '#0F172A' });
      StatusBar.setStyle({ style: Style.Dark });
      try {
        CapacitorUpdater.notifyAppReady();
      } catch (e) {
        console.warn('Capgo notifyAppReady failed:', e);
      }
    }
  }, []);
```

**למה ככה ולא ב-`AppRoutes`:**
- `function App()` (שורה 459) הוא ה-root component — רץ לפני הראוטר, ה-providers, והילדים.
- כבר יש שם `useEffect([], [])` עם בדיקת `isNativePlatform()` — אין סיבה לשכפל.
- `AppRoutes` (שורה 149) רץ יותר מאוחר וה-`useEffect` שלו תלוי ב-`location` — לא מתאים ל-init one-shot.
- ה-`try/catch` מגן מפני crash בדפדפן בפיתוח (שם `CapacitorUpdater` עובד דרך polyfill שעלול להיכשל).

### Phase 2 — CI/CD workflow

**4. יצירת workflow חדש:**
- קובץ חדש: `.github/workflows/deploy-frontend-capgo.yml`
- תוכן:
```yaml
name: Upload Frontend Bundle to Capgo

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'

jobs:
  capgo-upload:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{ vars.NODE_VERSION }}

      - name: Install frontend dependencies
        working-directory: frontend
        run: yarn install --frozen-lockfile

      - name: Build frontend
        working-directory: frontend
        env:
          REACT_APP_BACKEND_URL: ${{ vars.REACT_APP_BACKEND_URL }}
          REACT_APP_GOOGLE_CLIENT_ID: ${{ vars.REACT_APP_GOOGLE_CLIENT_ID }}
          REACT_APP_GIT_SHA: ${{ github.sha }}
        run: yarn build

      - name: Upload bundle to Capgo
        working-directory: frontend
        env:
          CAPGO_API_KEY: ${{ secrets.CAPGO_API_KEY }}
        run: npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY" --channel production
```

> ⚠️ **לפני הרצת ה-workflow** — ודא שכל המשתנים לעיל קיימים ב-GitHub → Settings → Secrets and variables → Actions → **Variables** (לא Secrets, כי אלה build-time public values). אם Zahi הוסיף משתנה נוסף בשלב Prerequisites B שלא ברשימה הזאת — הוסף גם אותו לבלוק `env`.

### Phase 3 — Android build (Zahi מקומית)

**5. העלאת versionCode:**
- קובץ: `frontend/android/app/build.gradle`
- שורה 10: `versionCode 1` → `versionCode 2`
- שורה 11: `versionName "1.0"` → `versionName "1.0.1"`

**6. Build + העלאה ל-Play Console:**
```bash
cd frontend
yarn build
npx cap sync android
cd android
./gradlew bundleRelease
# AAB ב: frontend/android/app/build/outputs/bundle/release/app-release.aab
```
- עלה ל-Play Console → Internal testing → שחרר לבודקים.
- אחרי שהבודקים אישרו שעובד: promote ל-closed beta → production.

## Relevant files
- `frontend/package.json` — הוספת dependency
- `frontend/yarn.lock` — מתעדכן אוטומטית
- `frontend/android/app/src/main/assets/capacitor.config.json` — הסרת `server` block
- `frontend/src/App.js` — שורה 16 (import חדש), שורות 459-466 (useEffect קיים בתוך `function App()`)
- `frontend/android/app/build.gradle` — שורות 10-11 (versionCode, versionName)
- `.github/workflows/deploy-frontend-capgo.yml` — קובץ חדש

**grep commands לאימות:**
```bash
grep -n "server" frontend/android/app/src/main/assets/capacitor.config.json
grep -n "CapacitorUpdater\|notifyAppReady" frontend/src/App.js
grep -n "capgo" frontend/package.json
grep -n "versionCode" frontend/android/app/build.gradle
grep -n "capgo" .github/workflows/deploy-frontend-capgo.yml
```

## DO NOT
- ❌ לא לגעת ב-`frontend/capacitor.config.json` (ה-config הראשי כבר נקי).
- ❌ לא להוסיף את `CAPGO_API_KEY` ל-`deploy.sh`, ל-`~/.zshrc`, או לקוד. הוא רק ב-GitHub Secrets. `deploy.sh` ממשיך לא לקרוא secrets בכלל.
- ❌ לא להשתמש ב-`npm install` — הפרויקט על yarn. גם לא לערבב yarn + npm באותו workflow.
- ❌ לא להסיר את `@capacitor/core` / `@capacitor/status-bar` וכו' — רק להוסיף את `@capgo/capacitor-updater`.
- ❌ לא להריץ את ה-workflow לפני ש-Zahi אישר שסעיף Prerequisites (A + B) הושלם.
- ❌ לא לשנות את `deploy-backend.yml` הקיים.
- ❌ לא לעדכן את iOS config או לעשות `cap sync ios` עד שיהיה ספק נפרד ל-iOS.
- ❌ לא לעשות refactor ל-`App.js` מעבר להוספת ה-import וה-`try/catch` בתוך ה-useEffect הקיים.
- ❌ לא ליצור `useEffect` חדש — להשתמש בקיים בשורה 460.
- ❌ לא להזיז או לשנות את קוד ה-StatusBar שכבר קיים ב-useEffect.
- ❌ לא לעלות `google-services.json` או `keystore` לגיט.

## VERIFY

### 1. בדיקת קוד
- `frontend/src/App.js` שורה 16: `import { CapacitorUpdater } from '@capgo/capacitor-updater';` קיים.
- `frontend/src/App.js` שורות 459-466: ה-useEffect הקיים עדיין מכיל את 3 שורות ה-StatusBar **ואחריהן** `try { CapacitorUpdater.notifyAppReady(); } catch ...`.
- `frontend/capacitor.config.json` (הראשי, tracked): אין `server` key. כבר המצב הקיים — לא שונה.
- `frontend/android/app/src/main/assets/capacitor.config.json` לא נוגעים בכלל ב-Phase 1 (gitignored, regenerated ב-Phase 3).
- `frontend/package.json`: `@capgo/capacitor-updater` מופיע ב-dependencies.

### 2. בדיקת workflow
- עשה push ריק (למשל שינוי קטן ב-`frontend/README.md`) ל-main.
- היכנס ל-`github.com/zahis10/brikops-new/actions` — צריך לראות run חדש של `Upload Frontend Bundle to Capgo` שמסתיים בירוק.
- היכנס ל-Capgo dashboard → `com.brikops.app` → Bundles. צריך להופיע bundle חדש עם timestamp + SHA.

### 3. בדיקת האפליקציה
- התקן את ה-AAB החדש (versionCode 2) בטלפון בטא דרך Play Console.
- פתח את האפליקציה — עובדת כרגיל (לא מזהה שהיא עכשיו ב-bundled mode).
- עשה שינוי טקסט קטן ב-frontend (למשל טקסט כפתור ב-`LoginPage.js`) → `git push`.
- המתן שה-workflow יסיים (2-3 דקות).
- סגור ופתח מחדש את האפליקציה → השינוי צריך להופיע תוך 30 שניות.

### 4. Edge case — אם notifyAppReady לא נקרא
אם `CapacitorUpdater.notifyAppReady()` לא רץ תוך 10 שניות מה-boot, Capgo יבצע rollback אוטומטי לגרסה הקודמת. לכן — אם המשתמש מדווח שגרסה חדשה לא נקלטה, תבדוק שב-`App.js` ה-useEffect באמת מורץ early. זה חשוב במיוחד אם מישהו בעתיד יוסיף await async לפני רינדור ראשון.

---

**הערות ל-Replit:**
- זה ספק רב-פאזי. **סיים Phase 1, ספר, עצור ותן לי לבדוק לפני שתמשיך ל-Phase 2.**
- ב-Phase 1 אל תעשה `cap sync` עדיין — אעשה אני באופן ידני אחרי בדיקה של הקוד.
- **Phase 2 לא להתחיל לפני ש-Zahi מאשר שסעיפי Prerequisites A + B סגורים.**
- אחרי Phase 2: דווח אם ה-workflow עלה בירוק על ה-push הראשון. אם לא — שלח את ה-logs ונבדוק.
- Phase 3 (build + Play Store) — זו משימה מקומית שלי (Zahi), אל תנסה לעשות אותה אוטומטית.
