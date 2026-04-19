# BrikOps — Chat Handoff

**תאריך:** 2026-04-18
**מטרה:** להעביר צ'אט חדש למצב עבודה תוך דקה.

---

## 1. איך לעבוד עם זהי (קרא קודם כל)

### סגנון תקשורת
- עברית, ישיר, בלי salesy talk.
- **אל תציע 5 אפשרויות** — תגיד מה הפתרון הנכון. אם לא בטוח, תגיד "לא בטוח, צריך לבדוק".
- אל תשאל 10 שאלות הבהרה. תן תשובה על סמך מה שאתה יודע, ותציין הנחות.
- בלי התנצלויות חוזרות. טעית → תיקון קצר → המשך.

### התפקיד שלך
- **ספקים ל-Replit** (פורמט למטה).
- **Code review** (diff או review.txt).
- **Status tracking** של משימות.
- אתה **לא כותב קוד ישירות** לפרויקט. Replit כותב, אתה בודק.

### ארכיטקטורה (לזכור!)
- **Frontend:** React 19 → Cloudflare Pages → `app.brikops.com`
- **Backend:** Python FastAPI → AWS Elastic Beanstalk (Docker, Frankfurt) → `api.brikops.com`
- **DB:** MongoDB Atlas
- **Storage:** S3 `brikops-prod-files` (eu-central-1)
- **CI/CD:** GitHub Actions (backend), Cloudflare auto-deploy (frontend)
- **Dev environment:** Replit (לא production host)
- **Deploy script:** `./deploy.sh --prod` מהטרמינל המקומי של זהי

### אין secrets ב-Replit
- Backend runtime secrets → AWS EB Environment Properties
- Frontend build-time vars → Cloudflare Pages env vars
- Deploy-time secrets (למשל `CAPGO_API_KEY`) → shell מקומי של זהי (`~/.zshrc`)

---

## 2. מצב נוכחי

### מה רץ ב-production
- App פועל על `app.brikops.com` + `api.brikops.com`.
- אנדרואיד **כבר build-ed כ-WebView עם `server.url = app.brikops.com`** (ראה `frontend/android/app/src/main/assets/capacitor.config.json`). כלומר מקבל עדכונים "בחינם" דרך Cloudflare.
- Google Play: closed beta פעיל (יום 9 מתוך 14 לפני promotion ל-production).
- Apple App Store: עדיין לא הוגש.

### Commit אחרון שאושר
- `0bf21cc` — spec #383 — backend enrichment ל-`/units/:unit_id/tasks`.

### Capgo — הוחלט לשלם
- $14/mo Solo (1000 MAU).
- משתמש **upload-only API key** שכבר נוצר: `abdd6...ace87` (זהי החזיק אותו).
- סיבה: התדירות הגבוהה של הפושים (כמה פעמים בשעה) + תאימות לאפל 3.3.2.
- **Organization name בונה:** `app.brikops.com` (זהי כבר הזין).

---

## 3. ספקים פתוחים (לפי סדר עדיפות)

### #384 — Capgo integration + bundled mode migration (הכי דחוף)
**מה צריך לקרות:**
1. `cd frontend && npm i @capgo/capacitor-updater`
2. ב-`frontend/capacitor.config.json` — **אין לשנות** (אין `server.url` שם, זה נקי).
3. ב-`frontend/android/app/src/main/assets/capacitor.config.json` — **להסיר** את הבלוק `"server": { "url": "...", "cleartext": false }`. אחרי זה האפליקציה טוענת את ה-bundle המקומי במקום את app.brikops.com.
4. ב-`frontend/src/App.js` — אחרי `ReactDOM.render` / בתוך `useEffect` ראשי, לקרוא:
   ```js
   import { CapacitorUpdater } from '@capgo/capacitor-updater';
   CapacitorUpdater.notifyAppReady();
   ```
5. **`deploy.sh`** — להוסיף שלב אחרי `yarn build` ולפני `git push` (או אחרי git push — זה לא משנה):
   ```bash
   if [[ $frontend_changed -eq 1 ]]; then
     (cd frontend && npx @capgo/cli bundle upload --apikey "$CAPGO_API_KEY")
   fi
   ```
6. זהי מוסיף ל-`~/.zshrc`: `export CAPGO_API_KEY="abdd6..."` ואז `source ~/.zshrc`.
7. Build חדש ל-Google Play → עלייה לגרסה ב-`android/app/build.gradle` → `npx cap sync android` → `./gradlew bundleRelease` → העלאה ל-Play Console.

**DO NOT:**
- לא לגעת ב-backend.
- לא לשנות `capacitor.config.json` הראשי (כבר נקי).
- לא להעלות ה-API key ל-git (tזהי ב-`~/.zshrc` בלבד).

**VERIFY:**
- אחרי push: בדיקה ב-Capgo dashboard שמופיע bundle חדש.
- בטלפון אנדרואיד בטא: לפתוח את האפליקציה → לעשות push קטן → לפתוח שוב → לראות שהשינוי נקלט תוך ~30 שניות.

### #382 — ExportModal multi-select support
מהקונטקסט הקודם. עדיין לא נוצר. לשאול את זהי אם זה רלוונטי לפני שמתחילים.

### Sign in with Apple (חוסם להגשה לאפל)
נדרש כי יש Google OAuth. ספק טרם נכתב.

### Apple App Store submission
תלוי ב-Sign in with Apple + Capgo (bundled mode).

### Google Play — promotion מ-closed beta ל-production
יום 9/14. עוד 5 ימים.

---

## 4. פורמט ספק (חובה לשמור עליו)

```markdown
# #[NUMBER] — [Title in English]

## What & Why
[פסקה אחת: מה משתנה ולמה]

## Done looks like
- bullets של מה המשתמש מאמת

## Out of scope
- מה לא לעשות

## Tasks
1. שלבים ספציפיים עם file paths

## Relevant files
- `frontend/src/...` lines 123-145
- `backend/contractor_ops/...` lines 67-89

## DO NOT
- לא לגעת ב-[X]
- לא להוסיף dependencies מעבר לרשום
- לא לעשות refactor

## VERIFY
1. פתח [page] → לחץ [button] → תוצאה: [X]
2. API: POST /endpoint body → status [code]
```

---

## 5. Gotchas ידועות (אל תשכח)

- `WebkitOverflowScrolling: 'touch'` → **NEVER** (iOS freeze).
- ObjectId → **NEVER** (רק string UUIDs).
- `now_il()` → **NEVER** (UTC בלבד).
- `console.log` עם PII → NEVER בפרודקשן.
- Radix Dialog עם `modal={true}` → יכול לגרום ל-`pointer-events: none` על body.
- Photo annotation ב-`createPortal` → אירועים מזלגים ל-parent.
- RTL: `dir="rtl"` על root.
- Auth: `get_current_user` על כל endpoint. `get_current_user_allow_pending_deletion` ל-whitelist.
- Audit: להשתמש ב-`_audit()` helper.

---

## 6. מקומות זיכרון

הצ'אט הבא ינסה לגשת ל-`/mnt/.auto-memory/` — זה המקום שבו זהי שומר זיכרונות מתמשכים. **הקובץ הקריטי שם:** `project_current_work_status.md`.

אם אין לך גישה (לא ב-Cowork/Claude Desktop) — תגיד את זה מיד ותבקש מזהי להדביק את הקובץ.

---

## 7. מה לא לעשות (מהניסיון הכושל שלי)

- לא להציע "Replit Secrets" — אין דבר כזה בפרויקט הזה.
- לא להציע `.env.local` בלי להבין איפה הסקריפט רץ.
- לא להציע Cloudflare/AWS כ-"שתי אופציות" לאותו סוג secret. קרא את deploy.sh ותבין איפה הוא רץ.
- לא לבלבל בין deploy-time secrets (מקומי) לבין runtime secrets (AWS EB).
- לא לסרב לתת תשובה כשאפשר לנחש בסבירות גבוהה — זהי מעדיף תשובה ישירה עם הנחה מסומנת על פני 5 שאלות הבהרה.

---

**בהצלחה לצ'אט הבא.**
