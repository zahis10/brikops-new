# #384 Phase 2 — GitHub Actions workflow ל-Capgo OTA

> Phase 1 הושלם כבר (קומיט `94d383a` על main). ה-plugin מותקן, `notifyAppReady()` נוסף ל-App.js.
> הספק הזה הוא **Phase 2 בלבד**: יצירת workflow בודד ב-GitHub Actions שמעלה את ה-bundle ל-Capgo בכל push שנוגע ב-`frontend/**`.

## Prerequisites — ✅ הושלמו על-ידי Zahi

- **GitHub Secret** `CAPGO_API_KEY` (upload-only key) — קיים.
- **GitHub Variables** (Repository): `NODE_VERSION=20`, `REACT_APP_BACKEND_URL=https://api.brikops.com`, `REACT_APP_GOOGLE_CLIENT_ID=394294810491-u5q1t9vabqpumvuue422...` — קיימים.
- **לא מוגדרים** `REACT_APP_ENABLE_REGISTER_MANAGEMENT_REDIRECTS` ו-`REACT_APP_ENABLE_DEV_LOGIN` — כוונה. אסור להוסיף אותם ל-workflow.

אל תיצור, תשנה או תוסיף משתנים ב-GitHub. הספק הזה הוא רק יצירת קובץ workflow.

## משימה יחידה — יצירת קובץ workflow

**קובץ חדש:** `.github/workflows/deploy-frontend-capgo.yml`

**תוכן מלא (הדבק בדיוק ככה, ללא שינויים):**

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

זהו. קובץ בודד. לא להתקין חבילות, לא להריץ builds, לא לגעת בשום קובץ אחר.

## DO NOT

- ❌ לא לגעת ב-`.github/workflows/deploy-backend.yml` הקיים או workflows אחרים.
- ❌ לא לשנות את השם של הקובץ — חייב להיות `deploy-frontend-capgo.yml`.
- ❌ לא להוסיף steps נוספים, matrix, cache, או optimization.
- ❌ לא להוסיף את `REACT_APP_ENABLE_*` ל-env — הם לא מוגדרים ב-GitHub Variables וזה מכוון.
- ❌ לא להריץ את ה-workflow בעצמך (אין ל-Replit הרשאה — Zahi יריץ על push אמיתי).
- ❌ לא לעדכן את `deploy.sh`, `package.json`, או כל קובץ אחר.
- ❌ לא לגעת ב-`frontend/capacitor.config.json` (נקי ולא נוגעים).
- ❌ לא לשנות את `frontend/src/App.js` (כבר טופל ב-Phase 1).

## VERIFY

1. הקובץ קיים ב-`.github/workflows/deploy-frontend-capgo.yml`.
2. `grep -n "CAPGO_API_KEY" .github/workflows/deploy-frontend-capgo.yml` — מחזיר שורה אחת.
3. `grep -n "working-directory: frontend" .github/workflows/deploy-frontend-capgo.yml` — מחזיר 3 שורות (install, build, upload).
4. `grep -n "vars.NODE_VERSION\|vars.REACT_APP" .github/workflows/deploy-frontend-capgo.yml` — מחזיר 3 שורות.
5. אף קובץ אחר ברפו לא שונה מלבד הקובץ הזה.

## זרימת deployment מהרגע הזה

אחרי ש-Replit דוחפת את הקובץ ל-main:
- ה-push הראשון הוא הטסט הראשון של ה-workflow (כי הוא נוגע ב-`.github/**` לא ב-`frontend/**`, אז הוא *לא* ירוץ על הקומיט שיצר אותו — רק מהקומיט הבא שיכנס ל-`frontend/**`).
- כל push עתידי ל-main שנוגע ב-`frontend/**` יפעיל את ה-workflow אוטומטית.
- ה-workflow: checkout → setup node → yarn install → yarn build → העלאה ל-Capgo channel `production`.
- Zahi יראה run ב-GitHub Actions, ואחרי הצלחה — bundle חדש ב-Capgo dashboard עם ה-SHA של הקומיט.

## דווח לי כשסיימת

- commit SHA של הקובץ החדש.
- פלט של `ls -la .github/workflows/` (מאשר שהקובץ נוצר בצד הקבצים הקיימים, בלי לדרוס אותם).
- פלט `git diff --stat HEAD~1 HEAD` (מאשר שרק קובץ אחד השתנה/נוצר).

לאחר דיווח — אני אבצע push ריק של שינוי קטן ב-frontend כדי לוודא שה-workflow רץ בהצלחה, ונמשיך ל-Phase 3.
