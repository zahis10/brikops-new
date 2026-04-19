# #385 Phase 5 Step 2 — Native Apple Sign-In plugin + platform-aware frontend

## What & Why

ב-Step 1 יצרנו פלטפורמת iOS ריקה (`frontend/ios/App/`). עכשיו נוסיף את ה-plugin של Apple Sign-In ונתאים את ה-frontend כך ש:

* **על iOS native** — ייפתח sheet נטיבי של Apple (Face ID / Touch ID), ללא popup של webview.
* **על web / Android / desktop** — הקוד הקיים נשאר בדיוק כמו שהוא (Services ID + `window.AppleID.auth.signIn`).
* **ה-backend לא משתנה בכלל** — `APPLE_AUDIENCES` כבר מקבל גם Bundle ID (`com.brikops.app`, ל-iOS native) וגם Services ID (`com.brikops.app.signin`, ל-web). זה נסגר ב-Phase 1.

**מדוע native:** Apple App Review מסמנים לעיתים קרובות אפליקציות שמציגות Apple Sign-In דרך WebView popup במקום sheet נטיבי. Native = UX יותר טוב + פחות סיכוי ל-rejection.

## Pre-existing state (verified 2026-04-18)

* `@capacitor/ios@^7.6.1` ב-`frontend/package.json` — Step 1 הושלם.
* `frontend/ios/App/` קיים — Xcode project תקף.
* שאר stack של Capacitor נעול ל-`^7.6.1` (core / android / cli).
* ב-`frontend/src/pages/LoginPage.js` line 346-404 יש `handleAppleSignIn` מבוסס web — **עובד בפרודקשן היום**.
* ב-`frontend/src/pages/OnboardingPage.js` line 232-290 יש `handleAppleSignIn` כמעט זהה — **עובד בפרודקשן היום**.
* `Capacitor` כבר מיובא ב-`frontend/src/App.js` line 15 — אותו pattern זמין.
* Backend `/auth/social` כבר תומך בשני ה-audiences — אל תיגע.

## Done looks like

* `@capacitor-community/apple-sign-in` ב-`frontend/package.json` — **version pinned ל-Capacitor 7 compatible** (ראה Steps).
* ב-`LoginPage.js` וב-`OnboardingPage.js`: הפונקציה `handleAppleSignIn` מבדילה בין iOS native ל-web:
  * **iOS native** (`Capacitor.getPlatform() === 'ios'`) → קוראת ל-`SignInWithApple.authorize()` עם `clientId: 'com.brikops.app'`.
  * **כל השאר** → רצה הקוד הקיים של web (Services ID + `window.AppleID.auth.signIn`). **בלי שום שינוי בלוגיקה הזו**.
* `await onboardingService.socialAuth('apple', idToken, appleName)` — **אותה קריאה בשני המסלולים**. אין שינוי ב-`services/api.js`.
* `npx cap sync ios` רץ בהצלחה אחרי ההתקנה.
* `CI=true REACT_APP_BACKEND_URL="https://api.brikops.com" yarn build` → `Compiled successfully.` ללא warnings חדשים.
* אין שינוי ב-`frontend/capacitor.config.json`.
* אין שינוי ב-`frontend/android/`.
* אין שינוי ב-`backend/`.
* commit מקומי בלבד — **אין `git push`**.

## Out of scope

* `pod install` — Zahi עושה ב-Mac (רק ל-Mac יש CocoaPods מלא).
* Xcode Signing & Capabilities — Step 3, Zahi ב-Mac.
* App Store Connect listing — Step 4, Zahi בדפדפן.
* שינויים ב-`backend/` — ה-multi-audience כבר קיים.
* שינויים ב-`frontend/android/` או בקוד ה-Android native.
* שינוי ב-`frontend/capacitor.config.json`.
* טיפול ב-Google Sign-In — לא נגעים.
* טיפול ב-phone OTP — לא נגעים.
* Apple Sign-In native ל-Android — out of scope (Android keeps web flow).

## ⚠️ Failure paths

**1. אם `yarn add @capacitor-community/apple-sign-in@^7.0.0` מחזיר `No matching version found`:**
- נסה `@7` (major only). אם גם זה לא — עצור ודווח.
- אל תתקין v6 / v5 / v4 — הם ל-Capacitor 6 ומטה, ישברו את ה-iOS build.
- אל תתקין את ה-`latest` tag — ייתכן שעבר ל-v8 שלא תואם ל-Capacitor 7 שלנו.

**2. אם `npx cap sync ios` נכשל:**
- עצור, דווח את ה-error המלא.
- אל תעשה `pod install` ידנית ב-Replit — אין שם CocoaPods מלא.
- דווח, Zahi יריץ את ה-sync שוב ב-Mac אחרי המשיכה.

**3. אם `yarn build` נכשל בגלל import של `SignInWithApple`:**
- בדוק שהיבוא מ-`@capacitor-community/apple-sign-in`, לא מ-`@capacitor/apple-sign-in`.
- אם עדיין נכשל — עצור, דווח.

**4. אם תגלה שיש `crypto.randomUUID` שלא נתמך ב-browsers ישנים:**
- השתמש בחלופה פשוטה: `Math.random().toString(36).slice(2) + Date.now().toString(36)`.
- אל תוסיף תלות חדשה ל-uuid package.

## Tasks

### 1. Install plugin — PIN TO v7

```bash
cd frontend
yarn add @capacitor-community/apple-sign-in@^7.0.0
```

אישור: הגרסה ב-`package.json` היא `^7.x.x` (לא `^6.x` ולא `^8.x`).

אם `^7.0.0` לא קיים → ראה Failure path #1.

### 2. Sync iOS

```bash
cd frontend
npx cap sync ios
```

Expected: `✔ Sync finished in ... ms` או דומה. ללא errors.

### 3. Update `frontend/src/pages/LoginPage.js`

**א. יבוא חדש בראש הקובץ** (ליד שאר הייבואים של Capacitor — בדוק אם יש כבר `Capacitor` מיובא; אם אין, יבא מ-`@capacitor/core`):

```javascript
import { Capacitor } from '@capacitor/core';
import { SignInWithApple } from '@capacitor-community/apple-sign-in';
```

**ב. החלף את הפונקציה `handleAppleSignIn`** (line 346-404). הקוד החדש:

```javascript
const handleAppleSignIn = useCallback(async () => {
  setSocialLoading(true);

  try {
    let idToken;
    let appleName = null;

    if (Capacitor.getPlatform() === 'ios') {
      // iOS native — Face ID / Touch ID sheet
      const nonce = (window.crypto?.randomUUID?.())
        || (Math.random().toString(36).slice(2) + Date.now().toString(36));
      const result = await SignInWithApple.authorize({
        clientId: 'com.brikops.app',
        redirectURI: '',
        scopes: 'email name',
        state: '',
        nonce,
      });
      idToken = result.response.identityToken;
      if (result.response.givenName || result.response.familyName) {
        appleName = `${result.response.givenName || ''} ${result.response.familyName || ''}`.trim();
      }
    } else {
      // Web flow — UNCHANGED. Do NOT modify anything inside this else block.
      if (!window.AppleID) {
        await new Promise((resolve, reject) => {
          if (document.getElementById('apple-signin-script')) {
            const check = setInterval(() => {
              if (window.AppleID) { clearInterval(check); resolve(); }
            }, 100);
            setTimeout(() => { clearInterval(check); reject(new Error('timeout')); }, 5000);
          } else {
            const script = document.createElement('script');
            script.id = 'apple-signin-script';
            script.src = 'https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
          }
        });
      }

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

      const response = await window.AppleID.auth.signIn();
      idToken = response.authorization.id_token;
      appleName = response.user
        ? `${response.user.name?.firstName || ''} ${response.user.name?.lastName || ''}`.trim()
        : null;
    }

    const result = await onboardingService.socialAuth('apple', idToken, appleName);
    await handleSocialAuthResult(result);
  } catch (error) {
    if (error.error === 'popup_closed_by_user' || error.code === '1001') {
      // User cancelled — do nothing. 1001 is iOS user cancel.
    } else {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'object' && detail.code === 'pending_deletion') {
        navigate('/account/pending-deletion');
        return;
      }
      toast.error(typeof detail === 'string' ? detail : 'אימות Apple נכשל');
    }
  } finally {
    setSocialLoading(false);
  }
}, [navigate, handleSocialAuthResult]);
```

**שים לב:**
- הלוגיקה של ה-web `else` block היא **העתק מדויק** של מה שהיה ב-346-404 — לא להוסיף/לגרוע.
- הוספנו `|| error.code === '1001'` ל-catch כדי לטפל בביטול native של iOS.

### 4. Update `frontend/src/pages/OnboardingPage.js`

זהה לגמרי ל-LoginPage אבל ב-line 232-290. שני הקבצים משתמשים באותה פונקציית `handleAppleSignIn`.

**יבוא חדש בראש הקובץ** (אם `Capacitor` כבר מיובא שם — לא להוסיף שוב):

```javascript
import { Capacitor } from '@capacitor/core';
import { SignInWithApple } from '@capacitor-community/apple-sign-in';
```

**החלף את הפונקציה `handleAppleSignIn`** (line 232-290) בדיוק באותו קוד כמו ב-LoginPage.

### 5. Build sanity

```bash
cd frontend
CI=true REACT_APP_BACKEND_URL="https://api.brikops.com" yarn build 2>&1 | tail -20
```

Expected: `Compiled successfully.` ללא warnings חדשים.

### 6. Verify iOS project reflects the new plugin

```bash
grep -r "apple-sign-in" frontend/ios/App/Podfile frontend/ios/App/Podfile.lock 2>/dev/null | head -5
ls frontend/ios/App/App/capacitor.config.json
```

Expected: `Podfile` (ולא בהכרח `Podfile.lock` — ה-lock נוצר רק אחרי `pod install` ב-Mac) מכיל reference ל-`CapacitorCommunityAppleSignIn` או pod דומה.

אם לא מופיע ב-Podfile — `npx cap sync ios` לא סיים את עבודתו. דווח.

### 7. Commit ONLY. DO NOT PUSH.

```bash
git add frontend/package.json frontend/yarn.lock frontend/src/pages/LoginPage.js frontend/src/pages/OnboardingPage.js frontend/ios/
git commit -m "feat(#385 Phase 5 Step 2): native Apple Sign-In plugin + platform-aware frontend"
```

**אל תריץ `git push`** בשום מקרה. Zahi דוחף דרך `./deploy.sh --prod` מה-Mac.

## Relevant files

* `frontend/package.json` — הוספת `@capacitor-community/apple-sign-in`
* `frontend/yarn.lock` — מעודכן אוטומטית
* `frontend/src/pages/LoginPage.js` — line 346-404 מוחלף; יבואים חדשים בראש
* `frontend/src/pages/OnboardingPage.js` — line 232-290 מוחלף; יבואים חדשים בראש
* `frontend/ios/App/Podfile` — יתעדכן אוטומטית מ-`cap sync ios`
* `frontend/ios/App/App/capacitor.config.json` — יתעדכן אוטומטית מ-`cap sync ios`

## DO NOT

- ❌ **אל תריץ `git push`.** Zahi דוחף דרך `./deploy.sh --prod`.
- ❌ **אל תשנה את `backend/`.** `APPLE_AUDIENCES` כבר תומך בשני Bundle IDs.
- ❌ **אל תשנה את `frontend/capacitor.config.json`.** הוא תקף.
- ❌ **אל תשנה את `frontend/android/`.** Android keeps web flow.
- ❌ **אל תשנה את `REACT_APP_APPLE_SERVICES_ID`** או כל env var.
- ❌ **אל תגע ב-`frontend/src/services/api.js`.** `socialAuth('apple', idToken, name)` — same signature.
- ❌ **אל תשנה את הקוד של Google Sign-In** (`handleGoogleSignIn`) או phone OTP.
- ❌ **אל תעשה `pod install`** ב-Replit — אין שם CocoaPods מלא. זה ירוץ אוטומטית ב-Mac.
- ❌ **אל תוסיף `uuid` package** — השתמש ב-`window.crypto.randomUUID()` עם fallback כמפורט.
- ❌ **אל תשנה גרסאות של `@capacitor/android`, `@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`** — כולם נעולים ל-`^7.6.1`.
- ❌ **אל תתקין plugin בגרסה אחרת מ-`^7`** — ישבור את ה-iOS build.
- ❌ **אל תשנה את הלוגיקה של `handleSocialAuthResult`** או את ה-catch branches של navigation (`pending_deletion`).
- ❌ **אל תעטוף את הייבוא של `SignInWithApple` ב-try/catch** — import שבור צריך להיכשל ב-build, לא ב-runtime.

## VERIFY

1. **Plugin installed with correct major:**
   ```bash
   grep "@capacitor-community/apple-sign-in" frontend/package.json
   ```
   Expected: שורה עם `"@capacitor-community/apple-sign-in": "^7.x.x"`.

2. **Imports added to both pages:**
   ```bash
   grep -n "SignInWithApple\|from '@capacitor/core'" frontend/src/pages/LoginPage.js | head -5
   grep -n "SignInWithApple\|from '@capacitor/core'" frontend/src/pages/OnboardingPage.js | head -5
   ```
   Expected: שני import שורות בכל קובץ.

3. **Platform branch present:**
   ```bash
   grep -n "Capacitor.getPlatform() === 'ios'" frontend/src/pages/LoginPage.js frontend/src/pages/OnboardingPage.js
   ```
   Expected: שורה אחת בכל קובץ.

4. **Web flow still intact (Services ID branch):**
   ```bash
   grep -n "REACT_APP_APPLE_SERVICES_ID" frontend/src/pages/LoginPage.js frontend/src/pages/OnboardingPage.js
   ```
   Expected: שורה אחת בכל קובץ (בתוך ה-else block).

5. **Build passes:**
   ```bash
   cd frontend && CI=true REACT_APP_BACKEND_URL="https://api.brikops.com" yarn build 2>&1 | tail -5
   ```
   Expected: `Compiled successfully.`

6. **iOS sync completed:**
   ```bash
   ls frontend/ios/App/Podfile
   grep -i "apple" frontend/ios/App/Podfile | head -3
   ```
   Expected: Podfile קיים; pod של Apple Sign-In מופיע.

7. **No backend touched:**
   ```bash
   git diff HEAD~1 HEAD --name-only | grep "^backend/"
   ```
   Expected: ריק.

8. **No android touched:**
   ```bash
   git diff HEAD~1 HEAD --name-only | grep "^frontend/android/"
   ```
   Expected: ריק.

9. **capacitor.config.json untouched:**
   ```bash
   git diff HEAD~1 HEAD -- frontend/capacitor.config.json
   ```
   Expected: ריק.

## דיווח

- commit SHA
- `git diff HEAD~1 HEAD --stat`
- `grep "@capacitor-community/apple-sign-in" frontend/package.json`
- 30 שורות ראשונות של `handleAppleSignIn` מ-`LoginPage.js` (להוכיח שיש branch לפי `Capacitor.getPlatform()`)
- 5 שורות אחרונות של `yarn build`
- אישור מפורש ש**לא** רצת `git push`
- אישור מפורש שלא נגעת ב-`backend/`, `frontend/android/`, `frontend/capacitor.config.json`, `frontend/src/services/api.js`
