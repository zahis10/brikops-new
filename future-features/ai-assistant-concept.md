# BrikOps AI Assistant — קונספט ותכנון

> **סטטוס:** פיצ'ר עתידי. לא בפיתוח עכשיו.
> **תאריך:** 2026-04-20
> **מעדיף:** Zahi שמר לעצמו. אל תתחיל פיתוח עד שזאהי יאשר.
> **המתין אחרי:** Build 5 (Wave 5) + Spec #386 (Splash) + Phase 5 (Apple Sign-In) ייצאו קודם.

## לאדם שקורא את זה
המסמך הזה מיועד ל-Cowork. לא spec טכני ל-Replit — זו תמונה כללית של הרעיון, איך הוא משתלב באפליקציה, ומה המודל הכלכלי. Cowork יעזור לחדד את הקונספט ולפרק ל-specs קטנים יותר בהמשך.

---

## הרעיון במשפט אחד

AI Assistant אופציונלי בתוך BrikOps, שמנהל פרויקט יכול להפעיל ברמת פרויקט ספציפי, שמספק daily briefings, Q&A על ה-data של הפרויקט, וניבוי עיכובים — ב-add-on בתשלום נפרד.

---

## למה זה X-Factor

**השוק:** Cemento, PlanRadar, Fieldwire — אף אחד לא מציע AI assistant שיודע לדבר על ה-data שלך. כולם מראים dashboards סטטיים.

**המיצוב:** "BrikOps זה לא עוד כלי ניהול ליקויים — זה מנהל פרויקט אישי עם AI."

**Enterprise sales:** מישהו כמו עמית (CTO) שרואה Daily AI Briefing — מבין שאתה קפיצה דורית, לא תחליף זול.

---

## מה ה-Assistant עושה

### 1. Daily Briefing (7:30 בבוקר)

הודעת WhatsApp או push notification:

> בוקר טוב נועה. פרויקט אורנים:
> 🔴 דחוף: 3 ליקויים חוסמי מסירה בדירה 12 — מסירה בעוד 3 ימים
> 🟡 לב: קבלן האינסטלציה לא עדכן 5 משימות כבר 4 ימים
> 🟢 טוב: 8 ליקויים נסגרו אתמול
>
> המלצה: להתחיל ממסירה של דירה 12.

### 2. Chat בתוך האפליקציה — Q&A בזמן אמת

PM פותח widget, שואל בטבעיות:
- "כמה ליקויים פתוחים בדירה 8?"
- "מה הסטטוס של קבלן הריצוף?"
- "איזו דירה הכי מוכנה למסירה?"
- "הראה לי את כל הליקויים החוסמים"

Assistant עונה עם נתונים אמיתיים מ-BrikOps API + insights.

### 3. Decision Support

PM שואל: "הדייר רוצה למסור בשבוע הבא, האם אנחנו מוכנים?"

Assistant מנתח ועונה:
> בניין A: 3 דירות מוכנות.
> בניין B: לא מומלץ — 12 ליקויים פתוחים, 4 חוסמי מסירה.
> המלצה: לדחות את B בשבועיים או לסגור את ה-4 הקריטיים השבוע.

### 4. Risk Predictor (הדבר הכי חזק)

Assistant סורק ברקע את ה-data ומזהה דפוסים לפני שבעיות מתפרצות:

> ⚠️ התראה: קצב סגירת ליקויים ירד 40% בשבוע האחרון. בקצב הזה המסירה תתעכב ב-12 ימים. הגורם העיקרי: קבלן החשמל לא מעדכן משימות.

זה מה שגורם ליזמים לאהוב את BrikOps — הם שונאים הפתעות.

### 5. Weekly Report (יום שישי בבוקר)

סיכום מקצועי של השבוע, שאפשר להעביר ליזם/הנהלה:
- ליקויים שנסגרו השבוע
- Top/bottom performers
- צפי לסיום פרויקט
- המלצות לשבוע הבא

### 6. Onboarding ל-PM חדש

PM חדש בחברה נכנס לפרויקט קיים → Assistant עושה לו סיור:
> יש לך 180 דירות ב-3 בניינים, 450 ליקויים פתוחים, 8 קבלני משנה.
> רוצה להתחיל ממסירה מתוכננת, ליקויים דחופים, או סקירה כללית?

חוסך ימים של "להיכנס לפרויקט".

---

## עקרון מנחה: שליטה מלאה של ה-PM

**ה-PM חייב לשלוט מתי ואיך ה-Assistant פועל.** אחרת זה רק מטרד יקר.

### הגדרות ברמת הפרויקט:

| הגדרה | אפשרויות ברירת מחדל |
|---|---|
| הפעל AI Assistant | ON / OFF (ברירת מחדל: OFF) |
| Daily Briefing | שעה שנבחרה / כבוי |
| ערוץ briefing | WhatsApp / Push / Email / כבוי |
| Risk alerts | מופעל / מופעל רק לקריטיים / כבוי |
| Weekly Report | יום+שעה / כבוי |
| Chat widget | ON / OFF |

### הגדרות ברמת הארגון:

- מי מורשה להפעיל Assistant בפרויקטים (owner + PM / רק owner)
- מכסת שימוש חודשית (אם רוצים cap על עלויות)
- דוח שימוש (כמה שאלות נשאלו, עלות API מצטברת)

**הנקודה הקריטית:** אם PM לא רוצה AI — הוא פשוט לא מפעיל. אין overhead. אין עלות API. האפליקציה עובדת כרגיל.

---

## המודל הכלכלי

### הבעיה
Claude API (או OpenAI GPT) עולים כסף אמיתי. שאלה קצרה: $0.01-0.05. Daily briefing מסובך: $0.10-0.30. אם PM עם פרויקט פעיל שואל 50 שאלות ביום + briefings + risk scans → עלות שלך: $30-80/חודש ללקוח.

עם ₪499/חודש תקיפה זה בלתי אפשרי.

### הפתרון: Add-on בתשלום

**BrikOps AI** כ-module נוסף:

| תוכנית | עלות | מה כולל |
|---|---|---|
| BrikOps Base | ₪499/חודש | כל מה שקיים היום |
| BrikOps + AI | ₪749/חודש | + Assistant בפרויקט אחד |
| BrikOps AI Pro | ₪999/חודש | + Assistant בכל הפרויקטים |

**הלוגיקה:**
- ₪250 add-on מכסה עלות API של ~$30/חודש + רווח
- לקוחות שלא רוצים AI לא משלמים, לא משתמשים
- לקוחות שכן רוצים — מקבלים פיצ'ר ייחודי בשוק
- שווה לכל PM שחוסך שעה ביום (= ₪2,200 שווי)

### Rate limiting מובנה

גם לשלם משתמשים — יש cap:
- 100 שאלות ליום per project
- 50 briefings/week per project
- 20 risk scans/day per project

מעבר ל-cap → הודעה: "הגעת למכסה יומית. מחר נמשיך." או upgrade ל-unlimited (₪1,499).

---

## ⭐ Self-Service Activation Flow (החלטה של Zahi)

**עיקרון ברזל: לא לגעת ב-core billing (PayPlus). המערכת הקיימת מסורבלת וכל שינוי שובר.**

### ה-Flow:

1. PM רואה באפליקציה כרטיס "שדרג ל-AI Assistant — ₪250/חודש"
2. לוחץ **"הפעל AI"**
3. מסך אישור: "האם להוסיף ₪250 לחשבון החודשי שלך?"
4. לוחץ **"אישור"**
5. Backend:
   - מחשב sum חדש = (החישוב הנוכחי של ה-org) + 250
   - מעדכן `manual_override.total_monthly` לסכום החדש
   - מסמן `ai_enabled: true`
6. החודש הבא — PayPlus גובה את הסכום החדש אוטומטית (הוא גובה מה שיש ב-`manual_override`, בלי שאלות)

### מה זה דורש בפיתוח:

- **Frontend:** כפתור חדש ב-Settings + מסך אישור
- **Backend:**
  - Endpoint חדש `POST /api/ai/enable` — עושה 3 דברים: מחשב sum, מעדכן `manual_override`, מסמן flag
  - Endpoint `POST /api/ai/disable` — ההפך (מפחית 250, מסמן flag כ-false)
- **אפס שינוי ב-PayPlus**, ב-charge flow, ב-renewal, ב-founder pricing, ב-per-apartment pricing

### יתרון — שקיפות ל-PM:

```
המנוי הנוכחי שלך:    ₪499
AI Assistant:        +₪250
סה"כ חודשי:          ₪749
החיוב הבא:           15/05/2026
```

### תזמון — החלטה סופית:

**הפעלה מיידית + חיוב מתחיל בחודש הבא.**

- 2-3 שבועות של AI חינם = marketing טוב (PM מתרגל, לא רוצה לוותר)
- אין pro-rating, אין חישובים חלקיים, אין רעשים ב-PayPlus
- פשוט, שקוף, מונע בעיות

### חלופה שנדחתה:

❌ חיוב חד-פעמי מיידי של ₪250 דרך PayPlus checkout → יותר מורכב, שובר את הפשטות.

---

## מבנה טכני (גבוה-רמה)

### Components

**Backend:**
- `ai_service.py` — wrapper סביב Claude API
- `ai_context_builder.py` — אוסף data מ-BrikOps DB → מכין context ל-Claude
- `ai_scheduler.py` — cron לbriefings ו-risk scans
- `ai_usage_tracker.py` — עוקב אחרי API costs per org
- `ai_activation_router.py` — `/api/ai/enable` + `/api/ai/disable` (ה-endpoints של Self-Service Activation)
- `/api/ai/*` endpoints — chat, briefing, risk

**Frontend:**
- Chat widget (דומה ל-support bot שדיברנו עליו, אבל נפרד)
- הגדרות AI בתוך Project Settings
- **Upgrade card** — "הפעל AI Assistant — ₪250/חודש" עם כפתור Self-Service
- Dashboard שמציג briefings + risk alerts
- Billing page עם add-on — **קריאה בלבד**, לא שינוי של PayPlus

**Infrastructure:**
- Cache של תשובות נפוצות (מפחית עלויות)
- API key management נכון (rotation, per-customer tracking)

### Context שה-Assistant מקבל

בכל request ל-Claude, מוזרק system prompt עם:
- פרטי הפרויקט (שם, סטטוס, לו"ז)
- רשימת בניינים/קומות/דירות
- סטטיסטיקות ליקויים (פתוחים/סגורים לפי קטגוריה)
- סטטיסטיקות קבלנים
- היסטוריה של 30 ימים אחרונים
- מסירות מתוכננות

**לא נשלח:** תמונות (יקרות), טלפונים פרטיים, נתוני billing.

### Risk Detection — איך זה עובד

Background job רץ פעם ביום per project פעיל:
1. אוסף metrics (קצב סגירה, מי עדכן, זמן ממוצע לתיקון)
2. משווה ל-baseline (14 ימים אחרונים)
3. מזהה חריגות
4. אם חריגה משמעותית → שולח ל-Claude עם השאלה "נסח התראה למנהל פרויקט"
5. שולח ל-PM ב-WhatsApp/push

---

## שאלות פתוחות שצריך לענות עליהן

1. **Claude API או OpenAI?** Claude יותר טוב בעברית ואינטיליגנטי יותר. OpenAI זול יותר ועם יותר features. מחקר נוסף נדרש.

2. **Cache strategy:** כמה אפשר לחסוך ב-API costs עם cache חכם? (תשובה: ~40-60%)

3. **Privacy:** האם לשלוח ל-Claude data רגיש? AWS Bedrock עם Claude on-premise יכול להיות פתרון ל-enterprise.

4. **Offline:** אם Claude API down — מה קורה? Fallback to generic responses או "Assistant לא זמין"?

5. **Language support:** עברית first. אבל אם נרצה לפרוץ בינלאומית — Claude כבר תומך בכל שפה.

6. **Onboarding ל-Assistant:** איך מלמדים PM להשתמש? הדרכה? video? interactive tour?

---

## שלבי פיתוח מוצעים

### Phase 1: Foundation (2-3 שבועות)
- AI service backend
- Context builder
- Usage tracking + cost monitoring
- **Self-service activation endpoints** (`/api/ai/enable`, `/api/ai/disable`) דרך `manual_override`
- **Upgrade card ב-Frontend** עם flow הפעלה עצמאי
- הגדרות ברמת פרויקט

### Phase 2: Chat Widget (שבוע)
- UI של chat בתוך האפליקציה
- Q&A על ה-data של הפרויקט
- History per user

### Phase 3: Daily Briefing (שבוע)
- Scheduler
- WhatsApp/Push integration
- Template של briefing

### Phase 4: Risk Predictor (2 שבועות)
- Metrics collection
- Baseline comparison
- Alert generation

### Phase 5: Weekly Report + Polish (שבוע)
- Weekly summary
- Onboarding flow
- Analytics dashboard לאדמין (עלויות, usage)

**סה"כ: 7-9 שבועות עבודה.**

---

## סיכון ומזעור

| סיכון | איך מתמודדים |
|---|---|
| עלויות API מתפוצצות | Rate limiting, cache, usage caps ברמת לקוח |
| Claude מחזיר תשובה שגויה | Disclaimer בכל תשובה: "זו המלצה, לא החלטה — בדוק בעצמך" |
| PM לא משתמש → יורד ל-basic | Analytics + outreach: "שמנו לב שלא השתמשת השבוע — הכל בסדר?" |
| Data leak של פרויקט ללקוח אחר | Isolation חזקה: context per-project, לא per-user |
| עברית לא מושלמת | Claude מצוין בעברית, אבל בדיקות מקיפות לפני launch |
| מתחרה משכפל | ה-moat של לקוחות משלמים + integration עמוקה ב-BrikOps = יתרון 6-12 חודשים |
| **שבירה של PayPlus** | **Self-service activation דרך `manual_override` בלבד — אפס שינוי ב-PayPlus** |

---

## Go-to-Market

**Launch strategy:**
1. **Beta free** — הפעלה חינם ל-10 לקוחות קיימים למשך חודש, אוסף feedback
2. **Soft launch** — ₪250 add-on, prominently displayed ב-billing page + Upgrade Card ב-Project Settings
3. **Case study** — "איך AI חסך ל-PM 15 שעות בשבוע" — מאמר + video
4. **Sales tool** — Demo ל-enterprise מראה את ה-Daily Briefing בזמן אמת

**Positioning:**
"BrikOps AI — המנהל פרויקט שלך בכיס"

**Differentiator:**
"אתה לא שוכר עוד כלי SaaS. אתה שוכר צוות AI שעובד 24/7 על הפרויקט שלך."

---

## מה לעשות עם המסמך הזה

פתח את זה ב-Claude Cowork במחשב. דיון ממוקד על:

1. **עדיפות:** האם זה הפיצ'ר הבא אחרי Spec #386 (splash) + Apple Sign-In + סימון ליקוי על תוכנית?
2. **תמחור:** ₪250 add-on הגיוני? אולי ₪150? אולי ₪500?
3. **טכנולוגיה:** Claude vs OpenAI — החלטה סופית
4. **Phase order:** האם Chat Widget ראשון או Daily Briefing?
5. **MVP scope:** מה מספיק ל-V1? (אולי רק Chat + Briefing, Risk אחר כך)
6. **מה לא עושים:** איזה פיצ'רים לדחות ל-V2?

אחרי שמגובש כיוון — פירוק ל-specs פרטניים ל-Replit.

---

## החלטות שכבר נסגרו (אל תפתח מחדש)

- ✅ **Self-service activation** — PM מפעיל לבד דרך כפתור באפליקציה
- ✅ **Billing דרך `manual_override`** — לא לגעת ב-PayPlus core
- ✅ **הפעלה מיידית + חיוב מחודש הבא** — בלי pro-rating, בלי רעשים
- ✅ **Add-on ₪250** (BrikOps+AI = ₪749)
- ✅ **OFF by default** — PM שלא רוצה לא חייב, אין overhead
- ✅ **Rate limiting מובנה גם למשלמים** — 100 שאלות/יום/פרויקט

---

## Cross-refs

- `/Users/zhysmy/brikops-new/HANDOFF-2026-04-20.md` — תמונת מצב נוכחית של BrikOps
- `/Users/zhysmy/brikops-new/spec-386-phase7-splash-experience.txt` — ספק פעיל (Build 6)
- `/Users/zhysmy/brikops-new/CLAUDE.md` — שיטת עבודה לעדכונים

---

**Last updated:** 2026-04-20 (הוספת Self-Service Activation flow של Zahi)
