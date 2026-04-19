# #385 Phase 2 — Frontend: Apple Sign-In uses Services ID from env var

## What & Why

Phase 1 (backend, commit 17789c1e) כבר על main. ה-backend מקבל כעת **שני audiences** — Bundle ID **או** Services ID. עכשיו צריך ש-frontend יעביר את ה-Services ID הנכון כ-`clientId` ב-`AppleID.auth.init`, במקום ה-hardcode הנוכחי של `'com.brikops.app'` (שהוא Bundle ID — לא תקף ל-web flow של Apple).

השינוי חל ב-**שני קבצי frontend** עם לוגיקת `handleAppleSignIn` זהה: `LoginPage.js` ו-`OnboardingPage.js`.

## Pre-existing state (verified)

* `frontend/src/pages/LoginPage.js:368-373` — `AppleID.auth.init({ clientId: 'com.brikops.app', ..., redirectURI: window.location.origin + '/login', usePopup: true })`.
* `frontend/src/pages/OnboardingPage.js:254-259` — זהה לחלוטין, כולל `redirectURI: window.location.origin + '/login'` (**לא** `/onboarding`).
* `handleAppleSignIn` משתי הדפים קורא ל-`onboardingService.socialAuth('apple', idToken, appleName)` — לא נוגעים בזה.
* `toast` מ-`sonner` וה-hook `setSocialLoading` כבר קיימים ב-scope של שני ה-handlers.

## Done looks like

* שני הדפים קוראים את `process.env.REACT_APP_APPLE_SERVICES_ID` לפני קריאה ל-`AppleID.auth.init`.
* אם ה-env var ריק/לא מוגדר: `toast.error('שירות Apple לא מוגדר')` + `setSocialLoading(false)` + `return` — הפונקציה מסיימת בלי לנסות לפתוח popup.
* כש-env var מוגדר: `AppleID.auth.init({ clientId: <ערך env var>, ... })`.
* **ה-`redirectURI` נשאר `window.location.origin + '/login'` בשני הדפים** (גם ב-OnboardingPage — זה ה-state הנוכחי).
* `scope`, `usePopup`, שאר הלוגיקה — ללא שינוי.
* `grep -rn "com.brikops.app" frontend/src/` — ריק אחרי השינוי.
* Google flow (`handleGoogleSignIn`) — ללא שינוי.

## Out of scope

* `backend/` — כבר נעשה בPhase 1.
* `.github/workflows/deploy-frontend-capgo.yml` — ספק נפרד של Zahi (PAT שלו בלי workflow scope).
* הגדרת `REACT_APP_APPLE_SERVICES_ID` ב-Replit Secrets / Cloudflare / GitHub — Zahi יוסיף.
* Apple Developer Console — Zahi עושה בדפדפן.
* `package.json`, dependencies חדשות.
* Refactor של `handleAppleSignIn` מעבר לשינוי ה-clientId.
* שינוי `handleGoogleSignIn`.

## Steps

### 1. Edit `frontend/src/pages/LoginPage.js`

Locate the block at lines 368-373:

```javascript
      window.AppleID.auth.init({
        clientId: 'com.brikops.app',
        scope: 'name email',
        redirectURI: window.location.origin + '/login',
        usePopup: true,
      });
```

Replace with:

```javascript
      const appleServicesId = process.env.REACT_APP_APPLE_SERVICES_ID;
      if (!appleServicesId) {
        toast.error('שירות Apple לא מוגדר');
        setSocialLoading(false);
        return;
      }

      window.AppleID.auth.init({
        clientId: appleServicesId,
        scope: 'name email',
        redirectURI: window.location.origin + '/login',
        usePopup: true,
      });
```

### 2. Edit `frontend/src/pages/OnboardingPage.js`

Locate the block at lines 254-259:

```javascript
      window.AppleID.auth.init({
        clientId: 'com.brikops.app',
        scope: 'name email',
        redirectURI: window.location.origin + '/login',
        usePopup: true,
      });
```

Replace with:

```javascript
      const appleServicesId = process.env.REACT_APP_APPLE_SERVICES_ID;
      if (!appleServicesId) {
        toast.error('שירות Apple לא מוגדר');
        setSocialLoading(false);
        return;
      }

      window.AppleID.auth.init({
        clientId: appleServicesId,
        scope: 'name email',
        redirectURI: window.location.origin + '/login',
        usePopup: true,
      });
```

**⚠️ חשוב:** `redirectURI` נשאר `'/login'` — זהו המצב הנוכחי. אל תשנה ל-`/onboarding`.

### 3. Verify no hardcoded Bundle ID remains

Run:
```bash
grep -rn "com.brikops.app" frontend/src/
```

Expected output: **no matches**. אם יש תוצאות, יש עוד מקום שפספסנו.

### 4. Build sanity check

```bash
cd frontend && yarn build 2>&1 | tail -20
```

Expected: `Compiled successfully.` — בלי warnings חדשים של ESLint שנוספו ב-diff שלנו.

### 5. Commit only. DO NOT PUSH.

- עשה `git add` + `git commit` בלבד.
- **אל תעשה `git push`** בשום מקרה.
- זהי pushה לבד דרך `./deploy.sh --prod` מה-Mac שלו. אם תדחוף — תשבור את ה-deploy flow שלו.

## Relevant files

* `frontend/src/pages/LoginPage.js` — שורות 368-373 (בתוך `handleAppleSignIn`)
* `frontend/src/pages/OnboardingPage.js` — שורות 254-259 (בתוך `handleAppleSignIn`)

## DO NOT

- ❌ **אל תשנה את `redirectURI`** בשום דף — הוא נשאר `'/login'` בשניהם.
- ❌ **אל תשנה את `scope` או `usePopup`**.
- ❌ **אל תיגע ב-`handleGoogleSignIn`** בשום דף.
- ❌ **אל תוסיף dependencies** ל-`package.json`.
- ❌ **אל תעשה refactor** ל-`handleAppleSignIn` מעבר לשינוי ה-clientId + guard.
- ❌ **אל תעביר את ה-env var ל-React Context או hook** — קריאה ישירה ל-`process.env.REACT_APP_APPLE_SERVICES_ID` ב-handler זה בסדר.
- ❌ **אל תשנה את `onboardingService.socialAuth`** או את ה-API call.
- ❌ **אל תוסיף logging** מעבר למה שקיים.

## VERIFY

1. **grep clean:**
   ```bash
   grep -rn "com.brikops.app" frontend/src/
   ```
   Expected: `(no matches)`

2. **Build passes:**
   ```bash
   cd frontend && yarn build
   ```
   Expected: `Compiled successfully.`

3. **Env var empty case** (DEV — לפני הגדרת הסיקרט):
   - פתח את האפליקציה
   - לחץ על כפתור Apple
   - Expected: toast בעברית "שירות Apple לא מוגדר", ה-popup של Apple **לא** נפתח, אין crash.

4. **Env var set case** (אחרי הגדרת `REACT_APP_APPLE_SERVICES_ID=com.brikops.app.signin` ב-Replit Secrets ו-rebuild):
   ```bash
   grep "com.brikops.app.signin" frontend/build/static/js/ | head -1
   ```
   Expected: לפחות תוצאה אחת — ה-Services ID נצרב לתוך ה-bundle.

## דיווח אחרי Replit סיים

- commit SHA
- `git diff HEAD~1 HEAD --stat`
- פלט של `grep -rn "com.brikops.app" frontend/src/` (חייב להיות ריק)
- פלט של `yarn build 2>&1 | tail -5`
