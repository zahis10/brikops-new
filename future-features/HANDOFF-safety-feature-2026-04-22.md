# Handoff — פיצ'ר בטיחות + יומן עבודה

**תאריך:** 2026-04-22
**סטטוס:** קונספט סגור — מוכן לכתיבת ספק ל-Replit
**Next step:** להיכנס ל-skill `brikops-spec-writer` ולכתוב ספק Phase 1 (Foundation — 4 שבועות)

---

## TL;DR — מה צריך לדעת

בונים פיצ'ר **בטיחות + יומן עבודה** ל-BrikOps. זה הפיצ'ר הקריטי ביותר — חובה רגולטורית בישראל, וגם מה שהמתחרה Cemento מציעים וחברות גדולות (שיכון ובינוי, אלקטרה) **דורשות**. אי אפשר למכור Enterprise בלי זה.

עבדנו 2 סשנים על הקונספט: תחילה ניתחנו 16 screenshots של Cemento, ואז זאהי צירף 4 PDFs אמיתיים של exports מ-Cemento ופיצחנו את פורמט ה-migration שלהם.

**כל 6 החלטות המוצר סגורות.** מוכנים לרדת לספק.

---

## קבצים חיוניים לקריאה (בסדר הזה)

1. **`future-features/safety-and-worklog-concept.md`** — הקונספט המלא, 850+ שורות
   - Cemento teardown (16 מסכים, screen-by-screen)
   - Safety Score algorithm (מפוצח, מאומת מתמטית)
   - Schemas של כל Collection (contractor_companies, workers, trainings, tours, equipment, defects, documentation)
   - **✅ 6 החלטות סגורות** — סעיף בסוף, לפני ה-"Next Step"
   - Phase 1-4 roadmap

2. **`future-features/cemento-research/CEMENTO_ANALYSIS.md`** — ניתוח 4 PDFs של Cemento exports
   - Parse-ability לכל סוג דוח (training = 95%, tasks = 65%, general log = 2%)
   - JSON schemas לייבוא
   - מה ניתן לחלץ ומה אובד

3. **`future-features/cemento-research/extracted-text/`** — 4 קבצי TXT גולמיים מה-PDFs (למקרה שצריך דוגמאות real data)

---

## 6 החלטות סגורות (סיכום לביקורת מהירה)

| # | נושא | החלטה |
|---|-------|--------|
| 1 | רשם הקבלנים | Manual entry ב-MVP + autocomplete organic מה-DB. אין scraping. |
| 2 | קטגוריות ציוד | Cemento's 10 + כפתור "+ הוסף קטגוריה מותאמת" (לא ב-Safety Score). |
| 3 | Safety Score weights | Cemento 1:1. `worker×10 + equipment×10 + medium(sum_days×1 + count×5) + high(sum_days×2 + count×10)`. |
| 4 | UI collapsibility | **כל בלוק collapsible עם חץ.** ריק → collapsed, <3 פריטים → expanded, ≥3 → collapsed. |
| 5 | חתימות Tour | **מנהל עבודה + עוזר בטיחות** (לא ממונה בטיחות — הוא לא בשטח יומית). ממונה אופציונלי. |
| 6 | Migration מ-Cemento | Hybrid: Concierge (MVP) → Training Form Auto-Importer (V2, 95% confidence) → Tasks Parser + Manual Review (V3). |

**החלטה ארכיטקטונית קריטית** (מזאהי): **הבטיחות כ-module נפרד לחלוטין** — לא לשבור את פיצ'ר הליקויים/QC הקיים. Collections נפרדים, routes נפרדים, components נפרדים.

---

## מה ה-Next Step אומר בדיוק

להיכנס ל-skill `brikops-spec-writer` ולכתוב **ספק Phase 1 ל-Replit**. ה-scope של Phase 1:

1. Collections: `contractor_companies`, `workers`, `worker_training_types`, `worker_trainings`
2. Routes: CRUD מלא לכל Collection + filtering + export (PDF/CSV/JSON)
3. Components: מסך עובדים עם grouping by company + collapsible blocks + "אין חברה" placeholder
4. Integration עם auth/tenant/project הקיימים ב-BrikOps
5. E2E test: יצירת חברה → הוספת עובד → רישום הדרכה → ייצוא דוח מסונן

**לא ב-Phase 1 (נדחה):** Safety tours, Equipment, Defects-בטיחות, Documentation, Safety Score, Project registration.

**משך משוער:** 4 שבועות ב-Replit.

---

## רקע על BrikOps (למקרה שה-chat החדש לא מכיר)

- **מוצר:** פלטפורמה לניהול ליקויי בנייה, QC ומסירות לשוק הישראלי
- **Stack:** React 19 + Capacitor 7 (mobile), FastAPI + MongoDB Atlas (backend), AWS EB, S3
- **Deployment:** `./deploy.sh --prod` ב-Replit (OTA דרך Capgo) או `./ship.sh` במק (native changes)
- **מתחרה עיקרי:** Cemento
- **מייסד:** זאהי שמי, עוסק מורשה 203004767
- **CLAUDE.md:** `/Users/zhysmy/brikops-new/CLAUDE.md` (workflow rules)

---

## פרומפט מוכן להדבקה ב-chat החדש

קח את הטקסט הזה, פתח chat חדש, הדבק:

---

```
אני ממשיך עבודה מסשן קודם על פיצ'ר הבטיחות + יומן עבודה של BrikOps.

קרא בסדר הזה:
1. /Users/zhysmy/brikops-new/future-features/HANDOFF-safety-feature-2026-04-22.md — handoff נקי עם סיכום מלא
2. /Users/zhysmy/brikops-new/future-features/safety-and-worklog-concept.md — הקונספט המלא עם 6 החלטות סגורות
3. /Users/zhysmy/brikops-new/future-features/cemento-research/CEMENTO_ANALYSIS.md — ניתוח 4 PDFs של Cemento exports

אחרי שקראת, היכנס ל-skill brikops-spec-writer וכתוב ספק Phase 1 ל-Replit (Foundation — 4 שבועות) לפי ה-scope שמוגדר ב-handoff. הספק צריך לכלול file paths, schemas, acceptance criteria, ו-DO NOT/VERIFY.

אל תתחיל ספק עד שקראת את 3 הקבצים לעומק. אחר כך תשאל אותי אם יש מה להבהיר לפני שאתה כותב.
```

---

## מה ה-chat החדש צריך לעשות (Step-by-step)

1. לקרוא את 3 הקבצים הנזכרים לעיל
2. לשאול את זאהי שאלות הבהרה אם יש
3. להיכנס ל-skill `brikops-spec-writer`
4. לייצר ספק Phase 1 במבנה שהסקיל מגדיר (file paths, line numbers, DO NOT, VERIFY)
5. לשמור את הספק ב-`/Users/zhysmy/brikops-new/specs/safety-feature-phase-1-spec.md`
6. לתת לזאהי link להדבקה ב-Replit

---

**סיום:** הקונספט בשל, ההחלטות סגורות, הדטה של המתחרה מופה. ה-chat החדש צריך רק לכתוב ספק נקי ולהעביר לריפליט.
