# #385 — Sign in with Apple: unblock submission + fix Services ID mismatch

## What & Why

**המצב היום:** ה-infrastructure של Apple Sign-In כבר כתובה:
- **Backend** (`backend/contractor_ops/social_auth_service.py:63` + `onboarding_router.py:1756`) — `verify_apple_token()` + endpoint `POST /auth/social` עם `provider=apple`.
- **Frontend** (`LoginPage.js:346` + `OnboardingPage.js:232`) — כפתור Apple + `AppleID.auth.signIn()`.

**הבעיה:** ה-`clientId` ב-frontend מקודד ל-`com.brikops.app` (Bundle ID של האפליקציה). Apple דורשת שזרימת web תשתמש ב-**Services ID** (מחרוזת שונה מה-Bundle ID), ולכן ב-prod ה-login ייכשל עם "invalid_client" ברגע שה-Services ID יוגדר בקונסול של Apple.

**מה משתנה:**
1. Backend יקבל **רשימת audiences** (Bundle ID לאייפון native בעתיד + Services ID ל-web היום) במקום audience יחיד.
2. Frontend יקרא את ה-Services ID מ-env var במקום לקודד אותו.
3. זהי יגדיר את כל המזהים ב-Apple Developer Console (מחוץ לקוד — הוראות בסוף).

**למה עכשיו:** Apple Guideline 4.8 חוסם הגשה ל-App Store אם יש Google Sign-In ואין Apple Sign-In. זו החוליה האחרונה לפני submission.

## Done looks like

- משתמש ב-`app.brikops.com` (דפדפן) לוחץ "Apple" → popup של Apple → מתחבר → נחתם עם JWT.
- משתמש חדש ב-Apple מגיע לזרימת הצמדת טלפון (OTP) כמו ב-Google.
- משתמש עם חשבון קיים (שנוצר דרך Google או OTP עם אותו email) מזוהה ומחובר.
- Tokens של Apple נבדקים מול Services ID **או** Bundle ID (שניהם תקפים) — Bundle ID ישאר תקף לאייפון native בעתיד.
- אין הארדקוד של `com.brikops.app` ב-`LoginPage.js` או `OnboardingPage.js`.

## Out of scope

- **Native iOS Capacitor plugin** (`@capacitor-community/apple-sign-in`) — לא לגעת. זה Phase 2 כשזהי יבנה iOS build. היום העבודה היא web flow בלבד.
- **Android** — Apple Sign-In לא רלוונטי ל-Android (Google כבר שם).
- **Linking אפל לחשבון קיים מדפי פרופיל** — לא בטאסק הזה.
- **Sign-out מאפל** — לא נעשה. logout רגיל מספיק.
- לא לשנות את זרימת Google.
- לא לעדכן package.json.

## Tasks

### Phase 1 — Backend: multi-audience support

**קובץ:** `backend/config.py` (שורה 190)

**מה לשנות:**

Before:
```python
APPLE_BUNDLE_ID = os.getenv("APPLE_BUNDLE_ID", "com.brikops.app")
```

After:
```python
APPLE_BUNDLE_ID = os.getenv("APPLE_BUNDLE_ID", "com.brikops.app")
APPLE_SERVICES_ID = os.getenv("APPLE_SERVICES_ID", "")  # e.g. "com.brikops.app.signin" — required for web flow

# Audiences accepted when verifying Apple ID tokens
APPLE_AUDIENCES = [a for a in [APPLE_BUNDLE_ID, APPLE_SERVICES_ID] if a]
```

**קובץ:** `backend/contractor_ops/social_auth_service.py`

**שינוי 1 — import:**

Before (שורה 14-19):
```python
from config import (
    GOOGLE_CLIENT_ID_WEB,
    GOOGLE_CLIENT_ID_IOS,
    GOOGLE_CLIENT_ID_ANDROID,
    APPLE_BUNDLE_ID,
)
```

After:
```python
from config import (
    GOOGLE_CLIENT_ID_WEB,
    GOOGLE_CLIENT_ID_IOS,
    GOOGLE_CLIENT_ID_ANDROID,
    APPLE_AUDIENCES,
)
```

**שינוי 2 — audience check (שורות 94-100):**

Before:
```python
        decoded = pyjwt.decode(
            id_token_str,
            public_key,
            algorithms=["RS256"],
            audience=APPLE_BUNDLE_ID,
            issuer="https://appleid.apple.com",
        )
```

After:
```python
        if not APPLE_AUDIENCES:
            logger.error("Apple audiences not configured (set APPLE_BUNDLE_ID and/or APPLE_SERVICES_ID)")
            raise ValueError("אימות Apple נכשל — שירות לא מוגדר")

        decoded = pyjwt.decode(
            id_token_str,
            public_key,
            algorithms=["RS256"],
            audience=APPLE_AUDIENCES,  # pyjwt accepts list — passes if aud matches ANY
            issuer="https://appleid.apple.com",
        )
```

**הערה ל-Replit:** pyjwt מקבל רשימה של audiences — הטוקן מתקבל אם `aud` תואם **לפחות אחד** מהם. לא צריך לוגיקת ידנית.

### Phase 2 — Frontend: env-driven clientId

**קובץ:** `frontend/src/pages/LoginPage.js` (שורות 368-373)

Before:
```javascript
      window.AppleID.auth.init({
        clientId: 'com.brikops.app',
        scope: 'name email',
        redirectURI: window.location.origin + '/login',
        usePopup: true,
      });
```

After:
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

**קובץ:** `frontend/src/pages/OnboardingPage.js` (שורות 254-259, בתוך `handleAppleSignIn`)

⚠️ **חשוב:** ה-`redirectURI` ב-OnboardingPage **נשאר `/login`** (זה המצב הנוכחי בקוד — לא לשנות ל-`/onboarding`). זה מצמצם את רשימת ה-Return URLs ב-Apple Developer Console לערך אחד בלבד.

Before:
```javascript
      window.AppleID.auth.init({
        clientId: 'com.brikops.app',
        scope: 'name email',
        redirectURI: window.location.origin + '/login',
        usePopup: true,
      });
```

After:
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

**grep כדי לוודא שלא נשאר hardcode:**
```bash
grep -rn "com.brikops.app" frontend/src/ | grep -v node_modules
```
אחרי השינוי — לא אמורות להיות תוצאות ב-frontend/src.

### Phase 3 — Env vars setup (Replit + production)

ב-Replit Secrets (development only):
- `APPLE_SERVICES_ID` = `com.brikops.app.signin` *(ערך סופי ייקבע בצעד Apple Developer Console)*
- `REACT_APP_APPLE_SERVICES_ID` = `com.brikops.app.signin`

ב-AWS Elastic Beanstalk Environment Properties (production backend):
- `APPLE_SERVICES_ID` = `com.brikops.app.signin`

ב-Cloudflare Pages env vars (production frontend) — **זהי יוסיף דרך Cloudflare dashboard**:
- `REACT_APP_APPLE_SERVICES_ID` = `com.brikops.app.signin`

ב-GitHub Actions `vars` (לפי `deploy-frontend-capgo.yml` הוא משתמש ב-`vars.*` ל-REACT_APP_BACKEND_URL) — **זהי יוסיף דרך GitHub Settings → Environments/Variables**:
- `REACT_APP_APPLE_SERVICES_ID` = `com.brikops.app.signin`

### Phase 4 — עדכון Capgo workflow להזריק את ה-env var ל-build

**קובץ:** `.github/workflows/deploy-frontend-capgo.yml` (שלב "Build frontend", שורות 25-31)

⚠️ **זה יישלח כ-spec נפרד ל-Replit** (PAT של זהי חסר `workflow` scope ולא יכול לדחוף שינויים ל-`.github/workflows/**` מהמק שלו). הספק הנפרד ישוגר אחרי ש-Replit סיים את phases 1-2.

Before:
```yaml
      - name: Build frontend
        working-directory: frontend
        env:
          REACT_APP_BACKEND_URL: ${{ vars.REACT_APP_BACKEND_URL }}
          REACT_APP_GOOGLE_CLIENT_ID: ${{ vars.REACT_APP_GOOGLE_CLIENT_ID }}
          REACT_APP_GIT_SHA: ${{ github.sha }}
        run: yarn build
```

After:
```yaml
      - name: Build frontend
        working-directory: frontend
        env:
          REACT_APP_BACKEND_URL: ${{ vars.REACT_APP_BACKEND_URL }}
          REACT_APP_GOOGLE_CLIENT_ID: ${{ vars.REACT_APP_GOOGLE_CLIENT_ID }}
          REACT_APP_APPLE_SERVICES_ID: ${{ vars.REACT_APP_APPLE_SERVICES_ID }}
          REACT_APP_GIT_SHA: ${{ github.sha }}
        run: yarn build
```

**בנוסף — הרחב את ה-smoke test** (שורה 36) כדי לאמת גם שה-Services ID נכנס לבאנדל:

Before:
```yaml
          if ! grep -rq "api.brikops.com" build/static/js/; then
            echo "::error::Built bundle does NOT contain 'api.brikops.com'. REACT_APP_BACKEND_URL was probably not set. Refusing to upload a broken bundle to Capgo."
            exit 1
          fi
          echo "Smoke test passed: backend URL is present in bundle."
```

After:
```yaml
          if ! grep -rq "api.brikops.com" build/static/js/; then
            echo "::error::Built bundle does NOT contain 'api.brikops.com'. REACT_APP_BACKEND_URL was probably not set. Refusing to upload a broken bundle to Capgo."
            exit 1
          fi
          if ! grep -rq "com.brikops.app.signin" build/static/js/; then
            echo "::error::Built bundle does NOT contain Apple Services ID. REACT_APP_APPLE_SERVICES_ID was probably not set. Refusing to upload a broken bundle to Capgo."
            exit 1
          fi
          echo "Smoke test passed: backend URL and Apple Services ID are present in bundle."
```

## Relevant files

- `backend/config.py` — שורה 190 (APPLE_BUNDLE_ID)
- `backend/contractor_ops/social_auth_service.py` — שורות 14-19 (imports), 94-100 (audience check)
- `frontend/src/pages/LoginPage.js` — שורות 346-397 (handleAppleSignIn)
- `frontend/src/pages/OnboardingPage.js` — שורות 232-290 (handleAppleSignIn)

## DO NOT

- ❌ **לא לגעת ב-`verify_google_token`** ולא ב-GOOGLE_CLIENT_ID_*.
- ❌ **לא להסיר את `APPLE_BUNDLE_ID`** — הוא נשאר ב-config כי הוא ישמש ל-native iOS בעתיד.
- ❌ **לא להוסיף @capacitor-community/apple-sign-in** או כל dependency חדש ל-package.json.
- ❌ **לא לשנות את `scope` או `usePopup`** ב-`AppleID.auth.init`.
- ❌ **לא לגעת במבנה הזרימה של `/auth/social`** (Phone OTP linking, pending_approval, וכו').
- ❌ **לא לעשות refactor ל-`handleAppleSignIn`** מעבר לשינוי ה-clientId.
- ❌ **לא לשנות את ה-verify audience logic של Google** — רק של Apple.

## VERIFY

### בדיקות ב-Replit (אחרי שינוי + deploy dev):

**לפני שמתחילים:** זהי צריך להוסיף ב-Replit Secrets:
- `APPLE_SERVICES_ID=com.brikops.app.signin`
- `REACT_APP_APPLE_SERVICES_ID=com.brikops.app.signin`

1. **Backend config loads:**
   ```bash
   cd backend && python -c "from config import APPLE_AUDIENCES; print(APPLE_AUDIENCES)"
   # Expected: ['com.brikops.app', 'com.brikops.app.signin']
   ```

2. **Frontend env var reaches code:**
   ```bash
   cd frontend && yarn build 2>&1 | tail
   grep -r "com.brikops.app.signin" frontend/build/static/js/ | head -c 200
   # Expected: at least one match (env var baked into bundle)
   ```

3. **No hardcoded bundle ID in source:**
   ```bash
   grep -rn "com.brikops.app" frontend/src/
   # Expected: NO matches (comments/docs OK; code should use env var)
   ```

### בדיקות ב-production (אחרי deploy מלא + Apple Developer setup):

4. פתח `https://app.brikops.com/login` → לחץ על כפתור Apple → popup של Apple → הכנס Apple ID → מקבל OTP לטלפון אם חשבון חדש → מתחבר.

5. עם חשבון קיים שיצר דרך Google (אותו email): לחץ Apple → מזהה לפי email match → מתחבר ישירות בלי OTP.

6. Edge case — `APPLE_SERVICES_ID` ריק בשרת: קריאה ל-`/auth/social` עם `provider=apple` צריכה להחזיר `400` עם `"אימות Apple נכשל — שירות לא מוגדר"`.

### דיווח לזהי אחרי Replit סיים:

- commit SHA
- diff של 4 הקבצים
- פלט `grep -rn "com.brikops.app" frontend/src/` (צריך להיות ריק)

---

## הוראות ל-Zahi (מחוץ ל-Replit) — Apple Developer Console setup

**אחרי ש-Replit מסיים, זהי עושה את זה בדפדפן ב-https://developer.apple.com/account:**

### צעד 1 — הפעל "Sign in with Apple" על ה-App ID

1. Certificates, Identifiers & Profiles → **Identifiers**
2. מצא את `com.brikops.app` → Edit
3. סמן V על **Sign In with Apple** → Save

### צעד 2 — צור Services ID (ל-web flow)

1. Identifiers → + (New) → **Services IDs** → Continue
2. Description: `BrikOps Web Sign-In`
3. Identifier: `com.brikops.app.signin`
4. Continue → Register
5. אחר כך Edit אותו → סמן V על Sign In with Apple → Configure:
   - **Primary App ID:** `com.brikops.app`
   - **Domains and Subdomains:** `app.brikops.com`
   - **Return URLs:** `https://app.brikops.com/login`, `https://app.brikops.com/onboarding`
   - Save

### צעד 3 — צור Sign in with Apple Key (למקרה שנצטרך backchannel verify)

1. Keys → + (New)
2. Key Name: `BrikOps Sign In with Apple Key`
3. סמן V על **Sign In with Apple** → Configure → Primary App ID: `com.brikops.app` → Save
4. Continue → Register
5. **הורד את קובץ ה-`.p8`** (רק פעם אחת!) — שמור ב-`~/brikops-secrets/`
6. רשום: **Key ID** (10 תווים) + **Team ID** (מהפינה הימנית העליונה)

### צעד 4 — אמת domain

1. ב-הגדרת Services ID, לחץ על "Download" ליד Domains
2. קבלת קובץ: `apple-developer-domain-association.txt`
3. **זהי צריך לוודא שהקובץ הזה נגיש מ-** `https://app.brikops.com/.well-known/apple-developer-domain-association.txt` — דרך Cloudflare Pages או backend route. זה חוסם את שלב Verify עד שזה זמין.
4. חזור לקונסול של Apple → Verify → Save

### צעד 5 — הגדר את הערכים באפליקציה

בכל המקומות שבספק:
- `APPLE_SERVICES_ID` = `com.brikops.app.signin`
- `APPLE_BUNDLE_ID` = `com.brikops.app` (נשאר כמו שהיה)

### צעד 6 — בדיקה end-to-end

פתח incognito → `https://app.brikops.com/login` → Apple → login → אמור לעבוד.

---

**סטטוס חסימת הגשת iOS:** אחרי שהצעדים 1-6 עבדו, ה-requirement של Guideline 4.8 נפתר עבור web. עבור iOS native (כשזהי יגיע לבניית iOS build), נעשה Phase 2 נפרד עם `@capacitor-community/apple-sign-in`.
