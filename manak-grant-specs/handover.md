# manak-grant — מדריך העברה לבעלים

מסמך זה מפרט את כל הצעדים להעברת בעלות מלאה על המערכת אליך.
זמן ביצוע משוער: **2 שעות**, מתוכן ~30 דקות עבודה אקטיבית.

---

## מה אתה מקבל

מערכת SaaS פנימית למשרד רוה״ח בארכיטקטורה שמיועדת להיות עצמאית לחלוטין:

- **Frontend**: React + Vite אתר סטטי שאתה יכול לארח בכל מקום
- **Backend**: FastAPI Python שאתה יכול לארח בכל מקום (כרגע ב-Render)
- **DB**: Postgres סטנדרטי ב-Supabase (אפשר לייצא ולעבור לכל Postgres אחר)
- **Auth**: Supabase Auth (אפשר להחליף ל-Auth0 / Cognito / משלך)
- **קוד**: GitHub repo פרטי

**אין tech שאסור לזוז ממנו.** כל שירות אפשר להחליף ב-1-2 ימי עבודה.

---

## תזה לפני שמתחילים

לפני יום ההעברה אתה צריך:

1. **כתובת אימייל ייעודית** לשירותים — לא הפרטית. למשל: `tech@<החברה_שלך>.co.il`
2. **כרטיס אשראי** — רק כדי לאמת חשבונות, לא יחויב כל עוד אנחנו ב-free tiers
3. **דומיין משלך** — אם אתה רוצה כתובת מקצועית כמו `manak.<החברה_שלך>.co.il`

---

## שלבי ההעברה

### שלב 1 — פתיחת חשבונות (15 דקות)

צור 4 חשבונות באימייל הייעודי:

1. **Supabase** — https://supabase.com → Sign in with Email
2. **Render** — https://render.com → Get Started
3. **Cloudflare** — https://cloudflare.com → Sign Up
4. **GitHub** — https://github.com (אם אין לך כבר)

שלח לי את 4 כתובות האימייל אחרי שהחשבונות מוכנים.

### שלב 2 — העברת הקוד (5 דקות)

אני (Zahi):
- GitHub → manak-grant → Settings → Transfer ownership
- מעביר ל-username שלך

אתה:
- מקבל אימייל אישור → Accept
- ה-repo נמצא תחת השם שלך

### שלב 3 — העברת ה-DB (Supabase) (10 דקות)

אני:
- Supabase → manak-grant project → Settings → General
- "Transfer project" → אני מזין את האימייל שלך
- מאשר

אתה:
- מקבל אימייל הזמנה לארגון → Accept
- כעת אתה Owner של הפרויקט
- כל הנתונים, השבלונה, ה-auth users — אצלך

### שלב 4 — העברת ה-Frontend (Cloudflare) (5 דקות)

אני:
- Cloudflare → Workers & Pages → manak-grant → Manage Domain → לא קיים API נקי להעברה
- יש 2 אפשרויות:
  - **א.** אני נותן לך את הקוד מ-GitHub. אתה מחבר ל-Cloudflare של עצמך, deploy אוטומטי. אותו URL שהיה אצלי אצלך.
  - **ב.** אני מעביר את הפרויקט שלי ל-Cloudflare שלך (יש ב-Cloudflare "Account-to-account project move" — דורש בקשת תמיכה).

מומלץ א'. תוך 5 דקות אתה לבד.

### שלב 5 — העברת ה-Backend (Render) (10 דקות)

אני:
- מוחק את השירות בחשבון שלי

אתה:
- Render → New → Web Service → Connect to GitHub → manak-grant repo
- Render מזהה את `render.yaml` ומגדיר אוטומטית
- מוסיף את ה-env vars (אני אתן לך אותם)
- Deploy

תוך ~5 דקות הbackend עולה אצלך.

### שלב 6 — עדכון ה-env vars (5 דקות)

ב-Cloudflare Pages → Settings → Environment Variables:
```
VITE_SUPABASE_URL=https://<פרויקט שלך>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key מ-Supabase API settings>
VITE_API_BASE_URL=https://<שם שלך>.onrender.com
```

ב-Render → Service → Environment:
```
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...   (שמור! זה key אדמיני)
SUPABASE_JWT_SECRET=...
ALLOWED_ORIGINS=https://<דומיין שלך>
```

Render → Manual Deploy לאחר השמירה.
Cloudflare → Retry build.

### שלב 7 — דומיין משלך (אופציונלי, 30 דקות)

אם רכשת דומיין:

1. Cloudflare → Pages → manak-grant → Custom domains → Set up custom domain
2. הוסף את הדומיין (למשל `manak.חברה_שלך.co.il`)
3. הוסף את ה-CNAME record שמופיע (לרוב אצל ספק הדומיין שלך)
4. תוך ~10 דקות SSL פעיל

ב-Render → Settings → Custom Domains → הוסף `api.manak.חברה_שלך.co.il`.
תקבל CNAME להוסיף ל-DNS שלך.

עדכן ב-`VITE_API_BASE_URL` ב-Cloudflare ל-domain החדש.

---

## אחרי ההעברה

### Backup — שגרה מומלצת

**Supabase:** מציעה pg_dump אוטומטי יומי בחשבונות בתשלום. ב-free tier:
```bash
# חודשי, מהמחשב שלך
pg_dump "postgresql://postgres:<password>@<host>:5432/postgres" > manak-grant-backup-$(date +%F).sql
```

שמור איפשהו בטוח (למשל S3 פרטי / Drive פרטי).

### עדכוני קוד

`git push` ל-main:
- Render auto-deploys
- Cloudflare auto-deploys

לפני שאתה pushes — תריץ tests מקומית:
```bash
cd backend && pytest
cd frontend && npm test  # אם יוסף phase
```

### הוספת עובדת חדשה

UI יוסף בשלב 5. בינתיים, ידני:
1. Supabase → Authentication → Add user → הזן אימייל ידני + סיסמה זמנית
2. Supabase → SQL Editor:
```sql
insert into user_profiles (id, firm_id, full_name, role)
values ('<auth user id>', '<firm id>', 'מיכל כהן', 'clerk');
```
3. שלח לעובדת אימייל + סיסמה זמנית. בכניסה הראשונה היא תשנה.

---

## מספרים שכדאי לדעת

| מצב | עלות חודשית |
|-----|-------------|
| 5-10 עובדות, 100-200 לקוחות, 50MB DB | **0₪** |
| כש-DB עוברת 500MB (כ-50K לקוחות) | ~95₪ (Supabase Pro) |
| כש-Render הולך כל הזמן (לא נרדם) | ~25₪ |
| Vision AI לפענוח ESNA וקטוריים (אופציונלי, 100 לקוחות) | ~35₪ |

**גג סביר ל-1,000 לקוחות פעילים: ~150₪/חודש כולל הכל.**

עד 200 לקוחות: 0₪. עד 100 לקוחות פעילים: 0₪ עד שתחליט שאתה רוצה שלא יירדם בלילה.

---

## מי לפנות אם משהו נשבר

### Supabase down
- Status: https://status.supabase.com
- DB ב-pg_dump הוא הbackup. אם Supabase קורסת לחלוטין: רים up פוסטגרס בכל מקום, restore.

### Render down
- Status: https://status.render.com
- Backend stateless = ירים מחדש בכל מקום (Fly.io, Railway, AWS, מכונה וירטואלית) תוך שעה

### Cloudflare down
- 99.99% uptime היסטורית — סבירות נמוכה
- Frontend סטטי = העלה ל-Netlify / Vercel / GitHub Pages תוך 5 דקות

### לא יודע מה נשבר
- כתבתי לך תיעוד מלא ב-`docs/architecture.md`
- אני זמין לבעיות תשתית קריטיות בתשלום ייעוץ ([להגדיר תעריף])

---

## נקודות חשובות

- **שמור את ה-`SUPABASE_SERVICE_KEY` כמו סיסמת בנק.** מי שמחזיק בו יכול למחוק את כל ה-DB.
- **אל תתן את ה-key הזה לעובדות.** הן רואות רק את ה-`SUPABASE_ANON_KEY` שמותקן ב-frontend.
- **שינוי קוד ה-calculator** = שדרוג רק על-ידי מי שמבין מס. יש 40 unit tests שצריכים להיות ירוקים אחרי כל שינוי.
- **שינוי השבלונה** = העלאה חדשה ל-Supabase Storage + `seed-template.py` מהrepo. הקוד בתוך `core/excel_filler.py` מכיר את התאים — עדכון נדרש אם משנים מבנה.

---

## לסיום

אם הכל עבד אחרי ההעברה — שלח לי הודעה. אסגור את החשבונות שלי ואסיים.
אם יש דבר שלא ברור — שאל.

בהצלחה.
