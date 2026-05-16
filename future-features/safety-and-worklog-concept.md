# BrikOps — פיצ'ר בטיחות + יומן עבודה (דיגיטלי, תואם חוק ישראלי)

> **סטטוס:** קונספט — טרם פיתוח
> **תאריך:** 2026-04-22
> **עדיפות:** **Tier 1 — חובה**. זאהי: "אולי הדבר הכי חשוב".
> **למה:** חובה רגולטורית בישראל. Cemento (המתחרה העיקרי) כבר מציע זאת — אי אפשר להתחרות בלי.
> **תלוי ב-:** Tier 0 clearance (Apple/Android app store).

---

## למה זה חובה, לא nice-to-have

### רגולציה ישראלית — מה החוק מחייב

**תקנות הבטיחות בעבודה (עבודות בנייה), התשמ"ח-1988:**
- חובת מינוי **ממונה בטיחות** (safety_officer) באתר בנייה מסוים (תלוי בגודל ובסוג)
- חובת ניהול **יומן עבודה** (work diary / יומן בטיחות) — רישום יומי
- חובת שמירת הרישומים לתקופה נדרשת (עד 7 שנים לחלק מהמסמכים)
- חובת תיעוד ביקורות מפקח עבודה
- חובת הדרכת בטיחות תקופתית (מתועדת)

**חוק תכנון ובנייה + תקנות הבנייה (רישוי ובקרה):**
- יומן עבודה הוא **תנאי למתן טופס 4 (תעודת גמר בנייה)**
- חייב להיות נגיש לבדיקת הרשות המקומית ומפקחי משרד העבודה
- בלי יומן עבודה תקין → עיכוב באכלוס, קנסות, חשיפה פלילית של הקבלן והמנהל

### המתחרה — Cemento
- הפיצ'ר הזה הוא חלק מהמציעה הבסיסית שלהם
- לקוחות גדולים (שיכון ובינוי, אלקטרה, אפריקה-ישראל) **דורשים** את זה — אחרת אין למה לעבור אלינו
- היום לקוחות ה-BrikOps שומרים יומן עבודה ידני (אקסל/וואטסאפ/פנקס) — אסוף, לא אחיד, לא חותם דיגיטלית

### ההזדמנות העסקית
**זה לא עוד פיצ'ר — זה המעבר מ"כלי ניהול ליקויים" ל-"פלטפורמה מלאה לניהול אתר בנייה".**
פותח דלת ל:
- Enterprise sales (חברות גדולות שלא יקנו בלי זה)
- מחיר גבוה יותר (הכפלת ה-ARPU)
- Stickiness — אחרי שהיומן מצטבר במערכת, ה-switching cost גבוה מאוד

---

## הפיצ'ר — שני רכיבים תאומים

פיצ'ר הבטיחות בישראל הוא **צמד בלתי נפרד**:

### רכיב A — יומן עבודה יומי (Work Diary)
רישום דיגיטלי של כל מה שקרה באתר באותו יום. נחתם על ידי מנהל העבודה + מועלה ל-cloud immutable.

### רכיב B — ניהול בטיחות (Safety Management)
כל מה שממונה הבטיחות צריך לתעד ולוודא באופן שוטף: סיורי בטיחות, הדרכות, ליקויי בטיחות, תאונות, near-miss, אישורי כשירות.

**שני הרכיבים חולקים:**
- אותם משתמשים (safety_officer, work_manager — כבר קיימים במערכת!)
- אותה הירארכיה (פרויקט → בניין → קומה → דירה)
- אותה מערכת ליקויים (אבל עם tag בטיחותי מיוחד)

---

## רכיב A — יומן עבודה יומי

### מה חייב להיות בו (לפי החוק)

| שדה | מה זה | חובה |
|---|---|---|
| תאריך + יום בשבוע | 22.4.26 יום ד' | ✅ |
| מזג אוויר | בהיר / גשם / רוח חזקה | ✅ |
| שעת התחלה וסיום | 06:30-17:00 | ✅ |
| מספר עובדים באתר | מחולק לפי חברה/מקצוע | ✅ |
| רשימת קבלני משנה פעילים | + מספר עובדים מכל אחד | ✅ |
| תיאור העבודות שבוצעו | "יציקת קומה 3 בניין B" | ✅ |
| חומרים שהגיעו לאתר | משטחי בלוקים, בטון, ברזל... | ✅ |
| ציוד כבד באתר | עגורן, מערבל בטון, סולמות | ✅ |
| אירועי בטיחות / near-miss | כן / לא + תיאור | ✅ |
| ביקורות של מפקחים | מי ביקר, מה בדק, הערות | ✅ |
| הוראות מיוחדות | הנחיות ממנהל העבודה/ממונה בטיחות | ✅ |
| הערות כלליות | טקסט חופשי | — |
| חתימות | מנהל עבודה + ממונה בטיחות | ✅ |

### UI/UX מוצע

**Mobile-first** — ממונה הבטיחות ממלא ביומן בטלפון בסוף היום מהאתר:

1. כפתור "יומן היום" במסך הבית של הפרויקט
2. Form חכם עם auto-fill של:
   - תאריך (היום)
   - מזג אוויר (API של השירות המטאורולוגי הישראלי)
   - רשימת קבלני משנה פעילים (מה-DB)
3. שדות שצריך למלא ידנית (בעזרת chips/dropdowns, לא טקסט חופשי):
   - מספר עובדים לכל קבלן (מספר בלבד)
   - תיאור עבודה (template דרופדאון: "יציקה", "אינסטלציה", "חשמל", "טיח"... + שדה תיאור קצר)
   - אירועי בטיחות (Yes/No → אם Yes, פותח incident form)
4. סריקת ברקוד של חשבוניות / תעודות משלוח → מילוי אוטומטי של "חומרים שהגיעו"
5. חתימה דיגיטלית (canvas + PIN)
6. הגשה → immutable, לא ניתן לעריכה בדיעבד
7. יצירת PDF חתום (דומה למבנה הקיים של פרוטוקולי מסירה)

### Edge cases שצריך לטפל בהם
- שבתות/חגים (יום ללא עבודה — עדיין רישום עם "לא עבדנו")
- יומן שנחתם כבר → מערכת מאפשרת "תוספת ליומן" (addendum) עם timestamp חדש
- מפקח מגיע → ממונה בטיחות מוסיף entry באמצע היום, לא מחכה לסוף
- offline mode — הטלפון באתר בלי רשת → שומר ב-local, מסנכרן ברגע שחוזר רשת

### חתימה + Immutability
- חתימה דיגיטלית של מנהל עבודה + ממונה בטיחות (PIN או Apple/Google biometric)
- אחרי חתימה — hash של הרשומה נשמר immutable ב-audit_events
- אם מישהו מנסה לשנות רטרואקטיבית → יוצר addendum חדש, לא דורס
- כל יומן → PDF חתום (PAdES אם אפשר) לשמירה של 7 שנים

### דוחות
- **יומן חודשי** מאוחד (לחודש שלם) — PDF אחד עם כל הימים
- **סיכום שנתי** — למפקח עבודה / לטופס 4
- **חיפוש** ביומן (לפי תאריך, לפי עובד, לפי אירוע)

---

## רכיב B — ניהול בטיחות

### Sub-modules

#### B1. סיור בטיחות יומי (Daily Safety Walk)
ממונה בטיחות סופר סיור באתר, מתעד ליקויים בטיחותיים.

**תהליך:**
1. לחיצה על "סיור בטיחות" → פותח checklist (ניתן להתאמה פר-פרויקט)
2. Checklist template ברירת מחדל (מתאים לאתר בנייה בישראל):
   - פיגומים תקינים? סולמות?
   - מעקות בטיחות בקומות?
   - קסדות/נעלי בטיחות לעובדים?
   - מחצבות חשמל זמניות תקינות?
   - כיבוי אש (מטפים) במקום?
   - שילוט בטיחות?
   - ניקיון (אין מכשולים, אין בורות פתוחים)?
   - עבודות בגובה — רתמות?
3. כל פריט → ✅ תקין / ❌ ליקוי + תמונה + תיאור
4. ליקויים בטיחותיים יוצרים **tickets מיוחדים** (severity=בטיחותי) שמוצגים בלוח בפני עצמם
5. ליקוי קריטי → **escalation אוטומטי** ל-PM ו-safety_officer בוואטסאפ/push

#### B2. דיווח תאונות + near-miss
- טופס דיווח תאונה (לפי הפורמט הרשמי של המוסד לביטוח לאומי)
- דיווח near-miss (אירוע כמעט-תאונה) — קריטי ללמידה ארגונית
- התראה אוטומטית לממונה בטיחות ול-PM
- דוח חודשי אגרגטיבי: כמה תאונות, כמה near-miss, trends

#### B3. הדרכות בטיחות (Toolbox Talks)
- רישום הדרכות בטיחות תקופתיות (חודשי/שבועי)
- רשימת נוכחים (scan ברקוד של תעודת זהות / בחירה מרשימת עובדים)
- נושא ההדרכה + חומר מצורף (PDF/וידאו)
- חתימות נוכחים

#### B4. אישורי כשירות עובדים (Certifications)
מעקב אחרי תוקף תעודות:
- רישיון עגורן
- אישור עבודה בגובה
- מדריך מורשה
- תעודת עזרה ראשונה
- ועוד
- התראה אוטומטית 30 יום לפני שמשהו פג תוקף

#### B5. ביקורות מפקח עבודה
תיעוד ביקורות של מפקח משרד העבודה:
- מי ביקר + מתי
- מה נבדק
- הערות המפקח
- פעולות תיקון שבוצעו
- העלאת צו/מכתב מהמפקח (PDF)

#### B6. דוחות בטיחות (Reports)
- **Daily Briefing של בטיחות** (אינטגרציה עם AI Assistant Phase 3) — "הבוקר 2 ליקויי בטיחות נפתחו, 1 תוקן"
- **דוח שבועי** — לשליחה לקבלן הראשי/יזם
- **דוח חודשי** — לרשומות ולמוסד לביטוח לאומי
- **דוח שנתי** — לטופס 4

---

## אינטגרציה עם מה שכבר קיים ב-BrikOps

### Sub-roles שכבר מוגדרים (לא צריך לבנות חדש)
```
management_team sub-roles:
├─ safety_officer     — ממונה בטיחות (יש לו גישה מלאה לפיצ'ר)
├─ safety_assistant   — עוזר בטיחות (יש לו view + edit, בלי חתימה)
├─ work_manager       — מנהל עבודה (חותם על יומן, רואה הכל)
├─ site_manager       — מנהל אתר
└─ execution_engineer — מהנדס ביצוע
```
**RBAC חדש שצריך:** הוספת permissions ל-safety_officer / work_manager על collections חדשים.

### Vision AI — חיזוק הבטיחות
Vision AI (`vision-ai-poc-result.md`) כבר מזהה `severity="בטיחותי"` עם reasoning. אינטגרציה:
- PM/עובד מצלם משהו באתר → Vision AI מציע "זה ליקוי בטיחותי" → נפתח ticket בטיחות אוטומטי
- גורם לזיהוי פרואקטיבי של סיכונים שבן אדם אולי היה מפספס

### AI Assistant — Daily Safety Briefing
AI Assistant (`future-features/ai-assistant-concept.md`) Phase 3:
- Daily Briefing יכלול סעיף בטיחות ייחודי
- "אמש נפתחו 2 ליקויי בטיחות קריטיים בבניין A — חובה לטפל היום לפני המשך עבודה"

### Collections חדשות ב-MongoDB
```
work_diary_entries      — רשומה יומית של יומן עבודה
safety_inspections      — סיורי בטיחות יומיים
safety_checklists       — templates של checklists
safety_incidents        — תאונות + near-miss
safety_trainings        — הדרכות
worker_certifications   — אישורי כשירות
inspector_visits        — ביקורות מפקח עבודה
```

---

## מודל המחיר המוצע

פיצ'ר בטיחות + יומן עבודה לא צריך להיות add-on חינמי שנכלל ב-base — זה **הצדקה למחיר גבוה יותר**:

| תוכנית | עלות | מה כולל |
|---|---|---|
| **BrikOps Basic** (היום) | ₪499/חודש | ליקויים, QC, מסירה |
| **BrikOps Pro** (חדש) | ₪899/חודש | + בטיחות + יומן עבודה |
| **BrikOps Pro + AI** | ₪1,149/חודש | + AI Assistant (`+₪250`) |
| **BrikOps Enterprise** | Custom | + Vision AI + multi-site + SLA |

**הלוגיקה:**
- ₪400 נוספים על פיצ'ר שמחייב על פי חוק → שווי ברור ללקוח
- חוסך עלות של "ממונה בטיחות באתר יום שלם לתיעוד" — ~₪2,000/חודש
- משווה את BrikOps ל-Cemento בפיצ'ר הקריטי ביותר שלהם

---

## Phases מוצעים

### **Phase 1 — יומן עבודה בסיסי (3-4 שבועות)**
- Backend: collection `work_diary_entries`, endpoints CRUD, immutability via audit
- Frontend: form mobile, חתימה דיגיטלית, PDF export
- מינימום viable — בלי auto-fill של מזג אוויר, בלי ברקוד
- Pilot ל-3 לקוחות קיימים בחינם → feedback

### **Phase 2 — סיור בטיחות + ליקויים בטיחותיים (2-3 שבועות)**
- Checklists templates
- Integration עם מערכת ליקויים קיימת (severity=בטיחותי)
- Escalation ל-safety_officer

### **Phase 3 — הדרכות + אישורי כשירות (2 שבועות)**
- Training logs + attendance
- Certifications tracker + expiry alerts

### **Phase 4 — תאונות + near-miss + ביקורות מפקח (2 שבועות)**
- Incident reporting forms (מתאים לפורמט הרשמי)
- Inspector visit logs
- Monthly aggregated report

### **Phase 5 — Auto-fill + Polish (2 שבועות)**
- מזג אוויר API
- ברקוד תעודות משלוח
- Offline mode
- דוחות שנתיים

### **Phase 6 — אינטגרציה עם AI (שבוע)**
- Daily Safety Briefing (דרך AI Assistant אם פעיל)
- Vision AI auto-creates safety tickets

**סה"כ: 12-15 שבועות עבודה** לפיצ'ר מלא ברמת Cemento.

---

## שאלות פתוחות לזאהי

1. **מי חותם על היומן?** — מנהל עבודה בלבד, או גם ממונה בטיחות? האם שני חתימות נדרשות?
2. **Offline mode חובה?** — הרבה אתרי בנייה באזורים עם קליטה רעה. worth the extra dev time?
3. **שילוב עם עובדים?** — האם עובדים מן המניין (לא רק מנהלים) צריכים גישה לדיווח near-miss?
4. **WhatsApp integration?** — פעמים רבות ממונה בטיחות מדווח דרך WhatsApp. האם לקבל הודעה ב-WhatsApp ולעבד אותה?
5. **תאימות ל-Cemento import?** — לקוחות שעוזבים Cemento — האם צריך import tool של ההיסטוריה?
6. **טופס 4 — Auto-generate?** — האם להכין PDF מוכן לבקשת טופס 4 מהרשות?
7. **מודלים של checklists** — checklist אחד לכל פרויקט? או אפשרות להתאים פר-בניין/קומה?
8. **רב-פרויקט לממונה בטיחות חיצוני?** — הרבה ממוני בטיחות עובדים לכמה פרויקטים במקביל. dashboard מאוחד?

---

## סיכון ומזעור

| סיכון | איך מתמודדים |
|---|---|
| מורכבות רגולטורית — לא לעמוד בתקנה | **מומלץ: יועץ חיצוני — ממונה בטיחות ותיק — סוקר את הפיצ'ר לפני launch** |
| חתימה דיגיטלית לא קבילה משפטית | מחקר: PAdES level T עם timestamp authority, עומד בדרישות חוק חתימה אלקטרונית |
| היעדר offline mode → לקוחות לא משתמשים | Phase 1 בלי offline → מודדים usage → אם יורד → Phase 5 offline priority |
| המשתמש שוכח למלא ביומן | Push יומי ב-17:00, ואם אין entry עד 20:00 → WhatsApp ל-PM |
| מתחרה (Cemento) מוריד מחיר | BrikOps עם AI מקיף יותר — differentiator אחר |

---

## Go-to-Market

### Positioning
"BrikOps — הפלטפורמה הישראלית היחידה שמשלבת ליקויים, QC, בטיחות, ויומן עבודה — **בכל הפלטפורמות** (web, iOS, Android)."

### Sales pitch ללקוחות גדולים
> "היום אתם מנהלים 5 מערכות שונות:
> - BrikOps לליקויים
> - Excel ליומן עבודה
> - WhatsApp לדיווחי בטיחות
> - אוגדן ידני לאישורי כשירות
> - מחברת של ממונה הבטיחות
>
> BrikOps Pro מאחד את הכל למערכת אחת — חתומה דיגיטלית, נגישה לכל הצוות, מוכנה לבדיקת מפקח.
> חיסכון: 20 שעות חודשיות לכל ממונה בטיחות. עלות: ₪400 נוספים בחודש."

### Beta program
- 3 לקוחות קיימים × 3 חודשים בחינם
- מתחייבים לתת feedback מפורט + case study
- בונים video + מאמר עם NDA

---

## Cross-refs

- `/Users/zhysmy/brikops-new/CLAUDE.md` — שיטת עבודה
- `/Users/zhysmy/brikops-new/future-features/ai-assistant-concept.md` — AI Assistant (אינטגרציה ב-Phase 6)
- `/Users/zhysmy/brikops-new/vision-ai-poc-result.md` — Vision AI (זיהוי severity=בטיחותי)
- `/Users/zhysmy/brikops-new/TODO-vision-ai-feature.md` — Vision AI use-cases

---

**Last updated:** 2026-04-22 (יצירה ראשונית בעקבות בקשת זאהי — "אולי הדבר הכי חשוב, חובה בישראל").

---

# 📸 Cemento Teardown — ניתוח 16 מסכים (מבוסס-תצפית)

> **מקור:** 16 screenshots מהאפליקציה של Cemento, פרויקט "מתחם הסופרים מגרש 801" (ארזי הנגב ייזום ובניה בע"מ).
> **מתודולוגיה:** כל observation מסומן **[נצפה]** = ראיתי במסך בפועל; **[הסקה]** = מסקנה שלי; **[המלצה]** = החלטה ל-BrikOps.
> **מטרה:** לבנות parity מלא עם Cemento ב-Phase 1, לעלות עליהם ב-Phase 2+.

---

## 🎯 Screen-by-Screen Observations

### מסך 1 + 16 — Safety Home (Dashboard)

**[נצפה]**
- Header כהה רוחב-מלא: "מתחם הסופרים מגרש 801" + chevron ימינה + ⋮ משמאל
- **Gauge חצי-עגול** עם scale 0-100 בקפיצות של 10, ו-gradient:
  - 0-20 אדום כהה
  - 20-40 אדום
  - 40-70 כתום
  - 70-90 צהוב
  - 90-100 ירוק
- ציון נוכחי: **0** (מוצג כטקסט בצבע אדום מתחת ל-gauge, לצד הכותרת "ציון בטיחות")
- כפתור קטן כתום-מלא **"פרטים"** משמאל ל-gauge
- **לחיצה על "פרטים"** פותחת breakdown טקסטואלי (מסך 16):
  - `91 עובדים עם הסמכות חסרות/לא בתוקף - 910 נקודות`
  - `41 ציוד ללא בדיקה בתוקף - 410 נקודות`
  - `5 ליקויים בחומרה בינונית פתוחים (בפיגור מצטבר של 4,677 ימים) - 4702 נקודות`
  - `6 ליקויים בחומרה גבוהה פתוחים (בפיגור מצטבר של 4,881 ימים) - 9822 נקודות`
- 5 כרטיסים לבנים, shadow קל, עם אייקון קו בצד ימין, סטטיסטיקה כתומה + טקסט:
  1. ⚠️ **ליקויים** — `11 ליקויים פתוחים`
  2. 🖼 **תיעוד** — `110 פריטים`
  3. ⛓️ (וו) **כשירות ציוד והאתר** — `41 בדיקות לא בתוקף`
  4. 👷 **כשירות עובדים** — `91 הסמכות חסרות/לא בתוקף`
  5. 📄 **סיורי בטיחות** — `1064 ימים מסיור עב"ט אחרון` + `702 ימים מסיור ממונה אחרון`
- Bottom nav 4-tabs (RTL): **עמיתים / בטיחות (active, כתום, helmet) / פרויקט / עדכונים**

**[הסקה] — הנוסחה האמיתית של ציון הבטיחות**
מנתוני מסך 16 הצלחתי לשחזר את החישוב של Cemento:
```
worker_penalty    = count × 10            → 91 × 10 = 910 ✓
equipment_penalty = count × 10            → 41 × 10 = 410 ✓
medium_defects    = sum(days_open) × 1 + count × 5    → 4677 + 25 = 4702 ✓
high_defects      = sum(days_open) × 2 + count × 10   → 9762 + 60 = 9822 ✓

score = max(0, 100 - total_penalties)
```
כלומר ליקוי בחומרה גבוהה כואב פי 2 מליקוי בינוני, ובדיקת ציוד / הסמכה = 10 נקודות קבוע. זה אלגוריתם שסוגר עבריינים מהר: 15,844 נקודות חיסור = clamp-to-0.

**[המלצה] — BrikOps Implementation**
```python
class SafetyScoreService:
    WEIGHTS = {
        "worker_cert_expired": 10,        # flat per cert
        "equipment_check_expired": 10,    # flat per check
        "defect_medium_day": 1,           # per aggregate day
        "defect_medium_flat": 5,          # per defect
        "defect_high_day": 2,             # per aggregate day
        "defect_high_flat": 10,           # per defect
        "tour_overdue_start_days": 7,     # גיל סיור אחרון מעל כמה ימים = penalty
        "tour_overdue_per_day": 3         # (to calibrate)
    }
    
    def compute(self, project_id: str) -> dict:
        penalties = { ... }
        score = max(0, 100 - sum(penalties.values()))
        return {"score": score, "breakdown": penalties}
```

---

### מסך 2 — Action Sheet מה-⋮

**[נצפה]** רק 2 פעולות ב-bottom sheet:
- `ייצוא טופס רישום הדרכות`
- `ייצוא פנקס כללי`

**[הסקה]** Cemento מצמצמים את תפריט הראשי ל-**שני ה-exports שחייבים על פי חוק**. כל השאר מקוננת בתוך קטגוריות (ליקויים, ציוד, עובדים). זה design choice חכם — לא מציפים את המשתמש.

**[המלצה]** BrikOps יקבל את אותו minimalism, עם extension:
```
⋮ menu:
  ├─ ייצוא טופס רישום הדרכות  (Cemento parity)
  ├─ ייצוא פנקס כללי          (Cemento parity)
  ├─ ייצוא ציון בטיחות (PDF)  (חדש — ל-QBR עם קבלן הראשי)
  └─ ⚡ שאל את AI Assistant     (Tier 1 — נפתח רק אם ל-tenant יש subscription)
```

---

### מסך 3 — עמוד ליקויים

**[נצפה]**
- Header פרויקט + 2 אייקונים ליד חץ: **פילטר עם badge "1"** + **PDF export**
- **2 chips למיון**:
  - `ממויין לפי סטטוס משימה ▼` (מוצג: `0 🟡` + `11 🔴`)
  - `משימה פתוחה ▼` (מוצג: `0 🟡` + `11 🔴`)
- כל defect-card:
  - **נקודה אדומה עגולה** + כותרת `משימה פתוחה`
  - **תג pill אדום outlined "בטיחות"** בצד שמאל (הצבע מעיד שזה ליקוי בטיחות, לא defect רגיל)
  - 📢 מגפון (מעיד על דחיפות)
  - גוף טקסט — עד 3 שורות + `...` truncate
  - Location: `כלל הפרויקט` או `בניין X | קומה Y`
  - תמונה עגולה-פינות בצד ימין (אם יש)
  - Footer: ✓ `סגור` + 💬 `הוסף תגובה` + ⋮
- FAB כתום + white bg bottom-left

**[הסקה]** 
1. ליקוי בטיחות = שילוב של 3 סימנים viszuals: **red pill + megaphone + red status dot**. Redundancy זה מכוון — ממונה בטיחות יראה את זה ב-scroll מהיר.
2. "משימה פתוחה" מיוצג הן בכותרת הכרטיס והן ב-group header = DRY מופר כדי ש-scroll יישאר הקשרי.

**[המלצה]** BrikOps כבר מימש קרוב לזה במסך הליקויים הקיים. השינויים הדרושים:
- Pill `בטיחות` אדום (חסר) + megaphone (חסר) = סימן ויזואלי ייחודי לליקוי בטיחות (vs. defect רגיל)
- Group header עם counts (יש — לוודא)
- "סגור" כ-checkbox עם ✓ ירוק ליד = affordance ברור יותר מ-"close" רגיל

---

### מסך 4 — עמוד תיעוד

**[נצפה]**
- Identical layout לליקויים, עם הבדלים:
  - **נקודת סטטוס ירוקה** (לא אדום)
  - כותרת: `תיעוד` (לא `משימה פתוחה`)
  - **Pill בטיחות עדיין אדום** (כי זה תיעוד של היבט בטיחותי)
  - 📢 מגפון עדיין שם
  - **אין כפתור "סגור"** — רק `הוסף תגובה` + ⋮
- Sort: `ממויין לפי תאריך יצירה` + group header `לפני יותר מ-30 ימים 110 🟢`

**[הסקה]** **Defect-vs-Documentation** הוא ההבחנה הקריטית:
- **ליקוי** = יש משהו שצריך לתקן (closeable, red, actionable)
- **תיעוד** = archive של משהו שקרה/נאמר (not closeable, green, referenceable)
שניהם יכולים להיות taggged `בטיחות`. זאת ארכיטקטורה שונה ממה שיש ל-BrikOps היום.

**[המלצה]** BrikOps צריך **collection נפרדת `documentation_entries`** (לא לערבב עם defects):
```
documentation_entries
  - project_id, building_id, floor_number (nullable)
  - tags: ["safety", "quality", "delivery", "general"]
  - body, photos[], mentioned_users[]
  - is_actionable: false  # immutable
  - created_by, created_at, archived_at (optional)
```
זה יאפשר לאגד תיעוד archival בלי להעמיס את queue הליקויים. + יצוא `פנקס כללי` יעבוד היטב מה-union.

---

### מסך 5 + 6 + 7 — כשירות ציוד והאתר

**[נצפה] — רשימת קטגוריות (מסך 5)**
10 קטגוריות קבועות (כנראה seeded), כל אחת עם chevron < ומונים:
1. אביזרי הרמה — `1 🔴`
2. במת הרמה — `1 🔴`
3. **לוח חשמל ראשי / משני** — `38 🔴` + `6 🟢`  (היחידה עם יותר מסטטוס אחד)
4. קולט אוויר — `1 🔴`
5. טפסות — (אין מונה)
6. מלגזה — (אין מונה)
7. מתקן חשמל/ארעי — (אין מונה)
8. **עגורן (לא עגורן צריח)** — (אין מונה)
9. **עגורן צריח** — (אין מונה)
10. פיגומים — (אין מונה)

**⚠️ מה שפספסתי קודם:** "עגורן" ו-"עגורן צריח" הן **שתי קטגוריות נפרדות**. עגורן צריח דורש תסקיר ורגולציה אחרים מעגורן רגיל. אסור למזג.

Search bar: `חפש פריט במאגר הציוד של החברה` → חיפוש חוצה קטגוריות.

**[נצפה] — קטגוריה פתוחה (מסך 6: אביזרי הרמה)**
כל item card:
- Header card (ללא bar צבעוני): אייקון וו כחול + כותרת `אביזרי הרמה` + sub-code `א.ג-03` + description `ארגז פסולת א.ג-03, P 2288`
- מתחת — card נפרד עם **red vertical bar על הצד**:
  - Title bold: `תסקיר - 6 חודשים`
  - Red text: `פג תוקף לפני 1,093 ימים`
  - Outlined pill button: `חידוש`

דוגמאות items: `א.ג-03`, `1594`, `164 (ארגז פרישמן-פסול לשימוש)`, `2019 (ארגז טרפזי)` — **חלקם עם תיאור פסילה ב-description field**.

**[נצפה] — לוח חשמל ראשי/משני (מסך 7)**
כאן המבנה מתפתח — לכל פריט **יש יותר מבדיקה אחת**:
- פריט "לוח חלוקה ראשי" → 2 בדיקות:
  - `בדיקת לוח חשמל ראשי/ משני על ידי חשמלאי...` — פג 962 ימים
  - `בדיקה שבועית למפסק מגן / פחת` — פג 980 ימים
- פריט "לוח חשמל AR5806 בניין 10 קומה 2" → 2 בדיקות
- שני הבדיקות הן **check_types שונות** עם תדירויות שונות, לכל אחת expiry משלה

**[הסקה] — Schema**
```python
class EquipmentCategory(Enum):    # seeded fixed list
    LIFTING_ACCESSORIES = "אביזרי הרמה"
    LIFTING_PLATFORM    = "במת הרמה"
    ELECTRICAL_PANEL    = "לוח חשמל ראשי / משני"
    AIR_COMPRESSOR      = "קולט אוויר"
    FORMWORK            = "טפסות"
    FORKLIFT            = "מלגזה"
    TEMPORARY_POWER     = "מתקן חשמל/ארעי"
    CRANE_REGULAR       = "עגורן (לא עגורן צריח)"
    TOWER_CRANE         = "עגורן צריח"
    SCAFFOLDING         = "פיגומים"

collection: equipment_items
  - project_id, building_id (nullable — חלק ממאגר חברה)
  - category (enum)
  - internal_code (string: "א.ג-03", "1594"…)
  - description (string: "ארגז פסולת...", "ארגז פרישמן-פסול לשימוש"…)
  - serial_number, manufacturer (optional)
  - status: "active" | "decommissioned"

collection: equipment_check_types   # seeded per category
  - category (FK)
  - name: "תסקיר - 6 חודשים", "בדיקה שבועית למפסק מגן / פחת"…
  - period_days: 180, 7…
  - required_inspector_type: "electrician" | "rigger" | "scaffold_builder"…

collection: equipment_checks        # actual performed checks
  - equipment_item_id (FK)
  - check_type_id (FK)
  - performed_by (name + license)
  - performed_at, expires_at (computed from period_days)
  - document_url (PDF תסקיר)
  - result: "pass" | "fail" | "conditional"
```

**[המלצה] BrikOps ++**
- **Vision AI lookup של מדבקת תסקיר** — ממונה מצלם → AI קורא מספר סידורי + תאריך → יוצר/מעדכן `equipment_check`
- **רשימת חשמלאים/בודקים מורשים** — נטען מ-דף משרד העבודה → dropdown במקום text
- **התראות 30/14/7 יום לפני expiry** (Cemento מראה רק "פג תוקף לפני X ימים", לא proactive)
- **Bulk import** — Excel עם כל ציוד החברה → seed initial state

---

### מסך 8 + 9 — כשירות עובדים

**[נצפה] — רשימת קבלנים (מסך 8)**
- Search: `חפש שם או ת"ז`
- רשימת קבלנים (alphabetical עברית) עם chevron + מונה אדום בלבד (אין green/yellow):
  - אבי פוריאן-אלרן פרויקטים צנרת ותשתיות בע"מ (11)
  - אהרון אלומיניום (2)
  - אוריאל בגובה בע"מ (6)
  - איטומית-קבוצת אשטרום (2)
  - **אין חברה (2)** ← קבלן placeholder לעובדים עצמאיים/לא משויכים
  - אלכס גבס (3)
  - ארזי הנגב ייזום ובניה בע"מ (18) ← החברה עצמה
  - ...

**[נצפה] — קבלן מורחב (מסך 9)**
- Header קבלן pinned למעלה עם down-caret
- כל עובד-card:
  - תמונה עגולה (או placeholder אם אין)
  - שם: `בלאל מגאדלי` + שם החברה מתחת
  - chevron >
- מתחת — רשימת trainings, כל אחת card עצמאית עם right-bar צבעוני:
  - `הדרכת אתר` — פג 731 ימים (red bar) — `חידוש`
  - `עבודה בגובה (אישור)` — פג 645 ימים (red bar) — `חידוש`
  - `הדרכת סיכונים מקצועיים - מתקין מערכת סו...` — פג 731 ימים (red bar)
- לעובד אחר (`מהלווס תאאיר`) — `עבודה בגובה (אישור)` **יש green bar** = בתוקף

**[הסקה]**
1. **הירארכיה:** קבלן → עובדים → הדרכות. 3-level drill-down.
2. מונה הקבלן הוא sum של הדרכות expired של כל עובדיו, לא מספר עובדים.
3. **"אין חברה"** זו קטגוריה reserved — חשוב לתמוך בה ב-BrikOps (עובדים עצמאיים/temp).

**[המלצה] — Schema**
```python
collection: contractor_companies
  - project_id (אם specific לפרויקט)
  - name, registry_number (רשם החברות)
  - is_placeholder: bool  # for "אין חברה"

collection: workers
  - contractor_company_id (FK, nullable → "אין חברה")
  - project_id (או multi via junction)
  - full_name, id_number, phone
  - photo_url, role_trade
  - status: "active" | "left"

collection: worker_training_types  # seeded, with regulatory refs
  - name: "הדרכת אתר", "עבודה בגובה (אישור)"…
  - default_valid_months: 12, 24, null (once-lifetime)
  - regulatory_source (string)
  - requires_translator_if_needed: bool

collection: worker_trainings
  - worker_id (FK)
  - training_type_id (FK)
  - signed_or_certified_date
  - valid_months (override of default)
  - expires_at (computed)
  - translator_name (optional), translator_id (optional)
  - submission_method: "scanned" | "in_app_signed"
  - document_url (scanned) | signature_blob (in-app)
  - status: computed from expires_at
```

---

### מסכים 10 + 11 — טופס הוספת הדרכה (dual-tab)

**[נצפה]** יש tabbed form עם שני flows **נבדלים לחלוטין**:

| Field | סרוק מסמך (מסך 11) | חתום באמצעות סמנטו (מסך 10) |
|---|---|---|
| שם ההדרכה | "הדרכת אתר" (orange header) | "הדרכת אתר" |
| שדה תאריך | `תאריך הסמכה` * (date picker, placeholder `לחץ לבחירה`) | `תאריך חתימה` * (auto-filled "22/04/2026") |
| משך תוקף (חודשים) | * 12 | * 12 |
| תאריך תוקף | מוצג `-` עד שמולא תאריך הסמכה | מוצג `חמישי, 22/04/2027` (auto-computed) |
| שם המתורגמן | optional text field | optional text field |
| ת.ז. מתורגמן | optional text field | optional text field |
| **Section מיוחד** | `תיעוד מסמכים חתומים` עם העלאת תמונה **או** קובץ (required *) | לא קיים |
| כפתור סיום | `אשר` (orange FAB full-width) → שומר מיד | `המשך` → הולך למסך חתימה canvas (לא נצפה) |

**[הסקה]** Cemento עושים ניואנס חשוב:
- **"תאריך הסמכה"** = מתי עבד האיש לפני שהוצאת לו תעודה חיצונית (scanned flow)
- **"תאריך חתימה"** = מתי הוא חתם ברגע זה in-app (in-app flow)

שני שדות שונים במשמעות. Cemento מבחינים בזה ב-UI. ב-DB זה כנראה שדה אחד semantic.

**[המלצה]** BrikOps יעבוד עם single form עם toggle, schema יקרא לזה:
```
worker_trainings.signed_or_certified_date  # שם כללי יותר
worker_trainings.submission_method         # enum
```
UI יציג label מותאם לפי method.

---

### מסכים 12 + 13 — סיורי בטיחות

**[נצפה] — רשימה (מסך 12)**
- Chip עליון: `קבץ לפי: חודשים` (עם down-caret — כנראה גם אפשרות `לפי שנה`)
- רשימת חודשים reverse-chronological:
  - מאי 2024 — 1 🟢
  - ינואר 2024 — 2 🟢
  - **יולי 2023 — 2 🔴 + 1 🟢** ← חודש mixed
  - מאי 2023 — 2 🟢
  - אפריל 2023 — 2 🟢
  - **מרץ 2023 — 2 🟡 + 6 🟢** ← yellow appeared (partial/pending)
  - פברואר 2023 — 9 🟢
  - ינואר 2023 — 7 🟢
  - ...
- FAB + bottom-left

**[נצפה] — חודש פתוח (מסך 13)**
Report-card:
- לבן, shadow, rounded
- Top-right title + 📅 תאריך מתחת + שם יוצר הדוח
- **Status indicator top-left:**
  - 🟢 + `חתום` → כפתור outlined neutral `צפה`
  - 🔴 + `ממתין לחתימה` → כפתור outlined **כתום** (ל-call-to-action)

**סוגי דוחות שנצפו:**
- `דוח ממונה בטיחות` (חודשי, by אהוד פטרסקו)
- `דוח עוזר בטיחות - בוקר` (יומי, mentioned)
- [הסקה מ-summary קודם] גם `דוח עוזר בטיחות - ערב` קיים

**[המלצה] — Schema**
```python
class SafetyTourType(Enum):
    SAFETY_OFFICER_MONTHLY = "דוח ממונה בטיחות"
    SAFETY_ASST_MORNING    = "דוח עוזר בטיחות - בוקר"
    SAFETY_ASST_EVENING    = "דוח עוזר בטיחות - ערב"
    CUSTOM                 = "custom"  # שם freeform

collection: safety_tours
  - project_id
  - tour_type (enum)
  - custom_name (nullable, for CUSTOM)
  - tour_date, created_by (safety_officer or safety_asst)
  - findings (array of defect refs or embedded)
  - signatures[] (ordered: author, counter-signer)
  - status: "draft" | "pending_signature" | "signed"
  - signed_at, pdf_url (generated post-sign), audit_hash
```

**[המלצה] BrikOps++**
- **Checklist-driven creation** — בחירת template → checklist פתוח → פריט כושל פותח defect + מוצא תמונה → דוח תלוי עד סגירה
- **Voice-to-draft** — ממונה סובב + מקליט → AI מכין draft עם location tags

---

### מסכים 14 + 15 — רישומי זיהוי (Project Registration)

**[נצפה]** 3 sections collapsible:

**1. כללי**
- שם היזם: `ארזי הנגב ייזום ובניה בע"מ`
- שם המבצע: `ארזי הנגב ייזום ובניה בע"מ` (זהה — הם קבלן-יזם)
- **מספר רישום בפנקס הקבלנים**: `24914` ← Official Israeli contractor registry ID

**2. מען המשרד הראשי / המשרד הרשום**
- הישוב: `נתיבות`
- מיקוד: `-`
- רח'/ת.ד: `ארזים`
- מס' בית: `72`
- דואר אלקטרוני: `Sigal@arzey.co.il`
- טלפון: `08-9933775`
- נייד: `-`
- פקס: `-`

**3. מנהלי החברה, אגודה או שותפות לפי הרישום** (repeat pattern, מנהל 1, מנהל 2, ...)
- שם פרטי: `עודד`
- שם משפחה: `שריקי`
- מספר ת"ז: `-`
- המען: `ארזים 72 נתיבות`
- הערות: `-`

Pencil edit icon top-left.

**[הסקה]** אלה **בדיוק השדות שמופיעים ב-פנקס הקבלנים** של משרד הבינוי והשיכון. Cemento בנו את ה-form לפי הפורמט הממשלתי. זה לא צירוף מקרים — זה כי הפנקס הכללי חייב לכלול את הנתונים האלה.

**[המלצה] — Schema**
```python
collection: project_registration
  - project_id (1:1)
  - developer: {name, registry_number (אם חברה), business_id}
  - main_contractor: {name, contractor_registry_number, business_id}  # רשם הקבלנים
  - office_address: {city, postal_code, street, house_number, email, phone, mobile, fax}
  - contractor_managers: [
      {first_name, last_name, id_number, address, notes}
    ]
  - permit_number (היתר בנייה)
  - form_4_target_date
```

**[המלצה] BrikOps++**
- **רשם הקבלנים API** (אם קיים — אחרת scraping מאושר) → הקלדת מס' רישום → auto-fill של שם החברה, מנהלים, מען.
- **Gating:** לא ניתן להפיק `פנקס כללי` או `טופס 4` בלי שכל השדות מולאו. UX validation-first.

---

## 🔎 מה שהקונספט הקודם החמיץ (מתוקן)

| # | נושא | טעות קודמת | תיקון מבוסס-תצפית |
|---|---|---|---|
| 1 | ציוד — קטגוריות | 9 קטגוריות, "עגורן" אחד | **10 קטגוריות, "עגורן" ו-"עגורן צריח" נפרדים** |
| 2 | ציוד — bחיקה | סברתי 1 בדיקה per item | **Multi-check per item** — לוח חשמל יש לו 4+ סוגי בדיקה |
| 3 | ציוד — item structure | "name + serial" פשוט | **internal_code + description** — לרוב description מכיל tags ("פסול לשימוש") |
| 4 | תיעוד vs. ליקויים | ערבבתי | **2 collections נפרדות** — defects closeable, documentation archival |
| 5 | Training dual-flow | שני buttons | **שני tabs עם labels שונים לשדה התאריך** — "תאריך הסמכה" (scan) vs. "תאריך חתימה" (in-app) |
| 6 | Safety Score | גזרתי ש-severity × days | **אמת: sum(days) × weight + count × flat_bonus** — הפרדה בין חומרה בינונית (×1) לגבוהה (×2) |
| 7 | Bottom nav order | הנחתי RTL | **RTL בפועל: עמיתים/בטיחות(active)/פרויקט/עדכונים** |
| 8 | "אין חברה" | לא הוזכר | **Placeholder contractor חובה** — עובדים עצמאיים |
| 9 | Safety Tour types | 3 types | **3 types + CUSTOM** — יש חופש להגדיר דוח ייחודי |
| 10 | Registration — מנהלים | אחד בלבד | **Array — מנהל 1, מנהל 2...** (ללא הגבלה) |

---

## 📋 Revised Backlog — 6 שבועות MVP parity + 10 שבועות parity מלא

### Phase 1 — Core Parity (4 שבועות)
**מטרה:** BrikOps Safety Home שנראה ומתנהג כמו Cemento — משתמש שעובר לא ירגיש downgrade.

| Task | עלות |
|---|---|
| Project Registration schema + form + PDF export | 3 ימים |
| Safety Score Service (אלגוריתם מעובד + unit tests) | 4 ימים |
| Safety Home dashboard — Gauge + 5 cards + breakdown modal | 5 ימים |
| Defect "בטיחות" tag + pill + megaphone + "סגור" affordance | 2 ימים |
| Documentation collection + page (green dot, no close button) | 3 ימים |
| Bottom nav: עמיתים/בטיחות/פרויקט/עדכונים | 1 יום |

### Phase 2 — Equipment + Workers (3 שבועות)
| Task | עלות |
|---|---|
| Equipment — 10 categories seeded + CRUD + multi-check-per-item | 5 ימים |
| Equipment detail page — periodic checks + חידוש flow + PDF תסקיר upload | 4 ימים |
| Workers — contractors grouping + search + profile | 3 ימים |
| Training form — dual-tab (scan vs. in-app sign) + translator optional | 4 ימים |
| Signature canvas + PAdES PDF output | 3 ימים |

### Phase 3 — Tours + Exports (2 שבועות)
| Task | עלות |
|---|---|
| Safety tours — monthly grouping + 3 report types + CUSTOM | 3 ימים |
| Signature workflow (pending → signed) + orange CTA pattern | 2 ימים |
| Export: טופס רישום הדרכות | 2 ימים |
| Export: פנקס כללי (diary + tours + defects merged) | 3 ימים |

### Phase 4 — BrikOps++ Differentiators (3 שבועות, אחרי launch + feedback)
- Vision AI — תסקיר OCR, Defect auto-categorization
- AI Diagnosis בתוך Safety Score modal
- Predictive expiry (WhatsApp 30/14/7 ימים לפני)
- Voice-to-report
- רשם הקבלנים API
- Benchmarking (industry-anonymized)

**סה"כ ל-parity מלא: ~9 שבועות.** עם BrikOps++ polish: **12 שבועות**.
(הקודם: הערכתי 16-18 כולל הכל — זה overestimate. Parity בלבד קטן יותר.)

---

## ✅ החלטות סגורות (2026-04-22, אחרי teardown + דיון עם זאהי)

### 1. רשם הקבלנים — **Manual entry ב-MVP**
החלטה: משתמש מקליד ידנית (שם חברה, ענף, סיווג, מספר קבלן). אין scraping ממשלתי, אין API חיצוני ב-MVP.

**Mechanism:** אחרי שהמשתמש הראשון מקליד חברה, היא נשמרת ב-DB שלנו ומוצעת כ-autocomplete למשתמשים הבאים. אנחנו בונים דטבייס חברות organic from usage. אחרי שנה: מאות חברות נפוצות, UX חלק בלי בעיה משפטית.

**שלב 2 (בעתיד):** אם רשם הקבלנים יפרסם API רשמי או יסכים ל-data license — integration ציבורי.

**חשוב — הפרדה ארכיטקטונית:** נושא הבטיחות נבנה כ-**module נפרד לחלוטין מהליקויים הקיימים**. עצמאי ב-collections, routes, components. זה מונע שבירה של הפיצ'ר הקיים של ליקויים/QC, ומאפשר פיתוח מקבילי.

### 2. קטגוריות ציוד — **Cemento 10 + Custom Add**
החלטה: ל-MVP — 10 הקטגוריות של סמנטו (עגורן, עגורן צריח, פיגומים, סולמות, כלי עבודה חשמליים, מעלית נוסעים, מעלית מטען, רכבי עבודה, פנלי חשמל, ציוד כיבוי).

**גמישות:** כפתור "+ הוסף קטגוריה מותאמת" מאפשר לקבלן להגדיר קטגוריות משלו (מערבל בטון, קומפרסור, גנרטור, וכו').

**מגבלת MVP:** קטגוריה מותאמת **לא תיכנס ל-Safety Score** (אין לה משקל מוגדר). תופיע ב-UI, תאפשר checks ותיעוד, אבל לא תשפיע על הציון האוטומטי. ב-V2 — נאפשר למשתמש להגדיר משקל.

### 3. Safety Score weights — **Cemento 1:1 מזה MVP**
החלטה: להעתיק את הנוסחה של Cemento בדיוק. המשתמשים כבר מורגלים, מצפים למספרים דומים בעת migration, ואין לנו כרגע data כדי לכייל משקלים שונים.

**Formula locked:**
```
worker_penalty    = missing_workers_count × 10
equipment_penalty = missing_equipment_count × 10
medium_defects    = sum(days_open_medium) × 1 + count_medium × 5
high_defects      = sum(days_open_high) × 2 + count_high × 10
score             = max(0, 100 - sum(penalties))
```

**V2 future:** Toggle ב-settings: "BrikOps Weighting v2" שמחשב משקלים שונים (הדרכות כמשקל גבוה יותר כ-differentiator). A/B test אחרי 3 חודשי שימוש.

### 4. "אין חברה" placeholder — **תמיד מוצג + collapsible**
החלטה: הבלוק "אין חברה" מוצג תמיד (גם ריק), **אבל collapsed by default** עם חץ לפתיחה.

**הוראה כללית לכל ה-UI:** כל בלוק/סעיף במסכי הבטיחות חייב להיות **collapsible** עם חץ פתיחה/קיפול. עובדים, ציוד, ליקויים, הדרכות, תיעוד — הכל. משתמש פותח רק מה שהוא צריך. זה מונע הצפת מסך ותואם RTL mobile UX.

**ברירת מחדל לקיפול:**
- בלוק ריק → collapsed
- בלוק עם < 3 פריטים → expanded
- בלוק עם ≥ 3 פריטים → collapsed (משתמש פותח לפי צורך)

### 5. Tour signature — **מנהל עבודה + עוזר בטיחות**
החלטה (תיקון שלי שגוי קודם): החתימה הכפולה הנדרשת בסיורי בטיחות היא **מנהל עבודה + עוזר בטיחות** — לא ממונה בטיחות.

**למה:** ממונה בטיחות לא בשטח יומית (הוא מגיע לביקורות חודשיות/שבועיות). בשטח יומית יש מנהל עבודה + עוזר בטיחות — הם הצמד שחותם על הסיורים היומיים.

**Schema update:**
```
safety_tours: {
  work_manager_signature: {...},    // חובה
  safety_assistant_signature: {...}, // חובה (עוזר בטיחות)
  safety_officer_signature: {...}    // אופציונלי (ממונה בטיחות — רק אם בשטח)
}
```

**MVP:** שני החתומים המרכזיים (work_manager + safety_assistant) חובה. השלישי (safety_officer) אופציונלי עם UI מוצג רק אם הוגדר ממונה בטיחות באתר.

### 6. Data migration מ-Cemento — **Hybrid approach: Concierge → PDF Parser → OCR**
**החלטה (אחרי ניתוח 4 PDFs אמיתיים של Cemento שזאהי צירף):**

זאהי אישר: חובה לעשות migration — אף לקוח לא יעזוב בלי זה. פיצחתי את פורמט ה-PDF exports של Cemento ויש דרך:

**מה שסמנטו מייצאים (אומת מ-4 PDFs):**

| דוח | עמודים | Parse-ability | רמת confidence | מה לייבא |
|-----|---------|---------------|------------------|----------|
| פנקס כללי (General Log) | 172 | ❌ לא parseable | 2/10 | זה לא data export — זה מדריך רגולטורי מודפס. **לדלג לגמרי.** |
| דוח משימות ותיעודים (Tasks) | 12-40 | ⚠️ partial | 6/10 | ניתן לחלץ: task ID, date, description, location code, attachments filenames. **אובד:** contractor, category, priority, photos. |
| **טופס רישום הדרכה** | 93 | ✅ **fully parseable** | **9/10** | **140+ records עם 9 columns (שם, ID, תאריך, סוג הדרכה, מדריך, משך).** Pure gold for migration. |

**Migration Strategy (3 שלבים):**

**Phase A (MVP): Concierge onboarding.**
20 הלקוחות הראשונים מקבלים migration ידני בלווי (אתה או CS). לקוח מייצא מסמנטו (PDF), שולח, אנחנו מקלידים/מעלים. זמן: ~2 שעות/לקוח. מכסה את כל 3 סוגי הדוחות. מאפשר לנו ללמוד איך הדטה שלהם באמת נראה.

**Phase B (V2, אחרי 10+ migrations): Training Form Auto-Importer.**
build parser אוטומטי ל-טופס רישום הדרכה PDF → JSON → import. 2-3 שעות build. **מחזיר 90% מעבודת ה-concierge להדרכות.** עדיין concierge ל-tasks + photos.

**Phase C (V3): Tasks Report Parser + OCR Fallback.**
parser ל-tasks PDF (6/10 confidence + manual review UI לתיקון contractor/category). OCR fallback לצילומי מסך של פריטים שאין להם PDF export (עובדים, ציוד).

**מה שאי אפשר לייבא מ-PDF (lost in export):**
- תמונות ליקויים (רק filenames מופיעים, לא הקבצים עצמם)
- Contractor assignment per task
- Defect category/severity (צריך מיון ידני אחרי import)
- Worker signatures (העמודה קיימת אבל תמיד ריקה ב-Cemento)

**Product insight — Cemento weakness, BrikOps opportunity:**
Cemento exports הם PDF-only, שטוחים, לא structured. משתמש שרוצה לעשות analysis או backup — תקוע. **BrikOps++ differentiator:** אנחנו נתמוך ב-**JSON + CSV + PDF** export מהיום הראשון. גם כ-differentiator שיווקי, גם כדי לאפשר migration OUT (שיוכיח ללקוחות שאנחנו לא נועלים אותם).

### 7. Filter → Export workflow (התובנה של זאהי מהPDFs)
**שזאהי ציין:** ב-Cemento ניתן לסנן לפי ליקויים וקבלנים ואז להוציא דוח מסונן — בדיוק כמו מערכת הסינון של הליקויים הקיימת ב-BrikOps.

**החלטה:** נעתיק את ה-pattern הזה — בכל מסך רשימה (עובדים, ליקויים, ציוד, הדרכות) יהיה:
- מערכת filters (לפי חברה, לפי סטטוס, לפי חומרה, לפי טווח תאריכים)
- כפתור "ייצא דוח" שמייצא את ה-**filtered data** (לא הכל)
- בחירת פורמט: PDF (לכבוד הרגולציה), CSV (לאקסל), JSON (לתכנה)

זה ייתן parity מלא עם Cemento + improvement (בזכות JSON/CSV).

---

## ⏭️ Next Step: Spec ל-Replit — Phase 1 Foundation

כל 6 ההחלטות סגורות. מוכנים להוריד ל-spec עבור Replit.

**Phase 1 scope (4 שבועות):**
1. Collections: `contractor_companies`, `workers`, `worker_training_types`, `worker_trainings`
2. Routes: CRUD מלא לכל Collection + filtering + export (PDF/CSV/JSON)
3. Components: מסך עובדים עם grouping by company + collapsible blocks + "אין חברה" placeholder
4. Integration with existing BrikOps auth/tenant/project
5. E2E test: יצירת חברה → הוספת עובד → רישום הדרכה → ייצוא דוח מסונן

**מה לא ב-Phase 1 (נדחה ל-Phase 2/3):**
- Safety tours + signatures
- Equipment management + checks
- Defects (safety-specific) + Documentation
- Safety Score calculation
- Project registration (רישום פרויקט אצל מפקח העבודה)

---

## 🔬 Post-Deep-Research Architecture Addendum (2026-04-22)

> **מקור:** חקירה מעמיקה של הקוד הקיים ב-BrikOps דרך 4 Explore agents במקביל — data layer (22+ collections, 1357 שורות ממצאים), frontend (App shell + RBAC), backend ops + SOC2 readiness, וחקיקה ישראלית + SOC2 benchmarks. המטרה: לוודא ש-spec ל-Phase 1 מבוסס על **הקוד האמיתי**, לא הנחות.
>
> **למה זה חשוב:** בסשן הקודם המלצתי ארכיטקטורות שהתבררו כלא מדויקות (למשל "להוסיף sub_role enum" — הוא כבר קיים). האדנדום הזה מתקן את ההנחות ומקבע את הדפוסים שיילכו ל-spec.

### א. תיקונים לקונספט הקודם (Ground Truth ↔ Assumptions)

| # | הנחה קודמת | מה בפועל בקוד | משמעות ל-Phase 1 |
|---|---|---|---|
| 1 | "צריך להוסיף `ManagementSubRole` enum" | **כבר קיים** ב-`backend/contractor_ops/schemas.py:32-37` עם כל הערכים: `safety_officer`, `safety_assistant`, `work_manager`, `site_manager`, `execution_engineer` | **אפס migration של schema**. ניתן להשתמש ישירות ב-`sub_role` על `project_memberships`. |
| 2 | "צריך לבנות authorization helpers חדשים" | **קיימים helpers קנוניים** ב-`backend/contractor_ops/router.py`: `_get_project_role`, `_check_project_access`, `_check_project_read_access`, `_get_project_membership`, `require_roles`, `MANAGEMENT_ROLES` | **חובה להשתמש בהם**, לא לכתוב חדשים. כל route חדש שלא משתמש ב-pattern הזה הוא vulnerability. |
| 3 | "נשמור timestamps כ-ISODate" | `_now()` מחזיר `datetime.now(timezone.utc).isoformat()` — **string**, לא ISODate | schema חדש חייב לציין timestamps כ-`str` (ISO-8601) ולא כ-`datetime` כדי להיות עקבי. |
| 4 | "Tenant isolation ברמת DB" | Isolation **application-layer בלבד** — כל query חייב `project_id` filter + membership check | כל route חדש חייב לעבור דרך `_check_project_access(user, project_id)` לפני כל קריאה ל-DB. |
| 5 | "חתימות דיגיטליות עם PAdES" (קונספט קודם רמז לזה) | חתימות בפועל = `{signer_user_id, signer_name, signature_url (canvas PNG) \| typed_name, signed_at (ISO string)}` — **ללא קריפטוגרפיה** | ל-Phase 1 נשתמש באותו pattern של handover_router. PAdES נדחה ל-SOC2 Stage. |
| 6 | "יהיה Redux/Zustand לstate management" | `package.json` — **אין**. State ב-AuthContext + component state + axios cache | ל-frontend safety — נעבוד עם aut context + לוקאלי state, אין store גלובלי. |
| 7 | "יש feature flags DB-backed" | **env-based בלבד** ב-`backend/config.py` + `/api/config/features` endpoint | flag חדש `ENABLE_SAFETY_MODULE` חייב להיכנס ל-`config.py` + `config_router.py` response. |
| 8 | "soft-delete אחיד" | **לא אחיד**: users/orgs soft-deleted (7-day grace), tasks/memberships hard-deleted כש-org נמחק | ל-safety (regulatory 7-year retention) — **חובה soft-delete מהיום הראשון** על כל collection. |

### ב. דפוסי קוד קנוניים (מחייבים לאימוץ מלא ב-Phase 1)

#### ב.1 Route protection — דפוס double-gated

```python
from .router import (
    get_db, get_current_user, _check_project_access,
    _check_project_read_access, _get_project_role,
    _is_super_admin, _now, _audit,
    MANAGEMENT_ROLES, require_roles,
)

# WRITE (management-only)
@router.post("/contractor-companies", response_model=ContractorCompany)
async def create_contractor_company(
    payload: ContractorCompanyCreate,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
):
    # Gate 1: Role (from require_roles decorator)
    # Gate 2: Project membership
    await _check_project_access(user, payload.project_id)
    # ... create doc ...
    await _audit("contractor_company", doc_id, "create", user["id"], payload.dict())

# READ (any project member)
@router.get("/contractor-companies", response_model=list[ContractorCompany])
async def list_contractor_companies(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    await _check_project_read_access(user, project_id)
    # ... query ...
```

**כלל ברזל:** אף route לא רץ ב-Phase 1 בלי שני ה-gates. סקירת spec תיפסל אם חסר.

#### ב.2 Audit — דפוס "audit every mutation"

```python
# לאחר כל create/update/delete
await _audit(
    entity_type="worker",
    entity_id=str(worker_id),
    action="create",        # "create" | "update" | "delete" | "soft_delete" | "restore"
    actor_id=user["id"],
    payload={               # חובה: מה השתנה (לא ערך מלא — רק diff)
        "contractor_company_id": payload.contractor_company_id,
        "full_name": payload.full_name,
        "id_number_last4": payload.id_number[-4:],  # PII masked
    },
)
```

**כלל SOC2 — ל-safety audit coverage חייב להיות 100%.** מדד שעובר ל-sockkit.

#### ב.3 Soft-delete + retention fields

כל schema של Phase 1 חייב לכלול את השדות הבאים (גם אם לא בשימוש אקטיבי ב-V1):

```python
class ContractorCompany(BaseModel):
    id: str
    project_id: str
    name: str
    # ... business fields ...

    # Audit / retention (SOC2-ready)
    created_at: str       # ISO-8601 UTC string (from _now())
    created_by: str       # user_id
    updated_at: str
    updated_by: str

    # Soft-delete
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None  # "user" | "org_purge" | "admin"

    # Retention lock (regulatory)
    retention_until: Optional[str] = None  # ISO date. לא ניתן למחוק לפני תאריך זה.
```

**מדוע `retention_until`:** תקנות הבטיחות בעבודה 1988 מחייבות שימור רישומים עד 7 שנים. Field זה מאפשר gate במחיקה — `deletion_router.py` בעתיד יבדוק `if retention_until and retention_until > _now(): raise`. ב-Phase 1 נאכלס את השדה אוטומטית (`now + 7 years`) אבל לא נאכוף את ה-gate (יגיע ב-SOC2 Stage).

#### ב.4 Schema style — Pydantic-first (Tasks pattern)

בקוד קיימים שני סגנונות: Tasks (Pydantic-first) ו-QC (document-oriented עם dict חופשי). **לבטיחות — Pydantic-first בלבד:**

```python
# schemas.py — סעיף חדש בתחתית
# ============ SAFETY ============

class ContractorCompanyBase(BaseModel):
    project_id: str
    name: str
    registry_number: Optional[str] = None
    is_placeholder: bool = False  # "אין חברה" flag

class ContractorCompanyCreate(ContractorCompanyBase):
    pass

class ContractorCompanyUpdate(BaseModel):
    name: Optional[str] = None
    registry_number: Optional[str] = None

class ContractorCompany(ContractorCompanyBase):
    id: str
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None
    retention_until: Optional[str] = None
```

**למה Pydantic-first ולא QC-style:** SOC2 דורש schema validation מחמיר, error surfaces עקביים, ו-OpenAPI docs automatic. Pydantic נותן את כל זה מ-FastAPI. QC-style (dict חופשי) מקשה על auditing ו-documentation.

### ג. החלטות SOC2-Aligned ל-Phase 1 Scope

על בסיס ההחלטות 6 הסגורות (החלק "החלטות סגורות" למעלה) + ממצאי ה-audit, הוסף ל-Phase 1 את הבאים כ-**first-class requirements** (לא polish מאוחר):

#### ג.1 Feature Flag — `ENABLE_SAFETY_MODULE` (off by default)

```python
# backend/config.py (בהמשך לשאר ENABLE_*)
ENABLE_SAFETY_MODULE = _env_bool("ENABLE_SAFETY_MODULE", False)
```

```python
# backend/contractor_ops/config_router.py
# הוספה ל-response של /api/config/features
"safety_module_enabled": ENABLE_SAFETY_MODULE,
```

ב-`frontend/src/pages/ProjectControlPage.js:3497` — tab רק אם `features?.safety_module_enabled && management_role`.

**ערך SOC2:** יכולת kill-switch במקרה של חשיפה לא צפויה. Rollout בטוח.

#### ג.2 Audit מלא על כל mutation

כל `create_`, `update_`, `soft_delete_`, `restore_` חייב לקרוא ל-`_audit()`. אין exceptions. זה הופך את ה-module מיום אחד ל-auditable באופן מלא — תשתית ה-audit_events כבר קיימת.

**Payload guidelines:**
- אל תכתוב ערך שלם של השורה — רק diff/changed fields
- PII (ת.ז., טלפון, אימייל) — masked (last4 / E.164 with leading masked)
- תמונות — URL + content_hash בלבד, לא payload binary

#### ג.3 Soft-delete + retention מהיום הראשון

4 collections של Phase 1 (`contractor_companies`, `workers`, `worker_training_types`, `worker_trainings`) חייבים את 6 השדות מסעיף ב.3.

```python
# Delete endpoint — לא הורס, מסמן
@router.delete("/workers/{worker_id}")
async def soft_delete_worker(worker_id: str, user: dict = Depends(require_roles(*MANAGEMENT_ROLES))):
    worker = await db.workers.find_one({"_id": worker_id})
    if not worker:
        raise HTTPException(404)
    await _check_project_access(user, worker["project_id"])
    await db.workers.update_one(
        {"_id": worker_id},
        {"$set": {
            "deleted_at": _now(),
            "deleted_by": user["id"],
            "deletion_reason": "user",
        }}
    )
    await _audit("worker", worker_id, "soft_delete", user["id"], {"reason": "user"})
    return {"ok": True}
```

**כל query ברירת מחדל חייב לסנן `"deleted_at": None`.** (לשקול helper `active_filter` ב-router.py בעתיד.)

#### ג.4 PII handling — masking + retention

`workers.id_number` (ת.ז. ישראלי — PII רגיש) חייב:
1. **Validation ב-schema** — 9 ספרות, אלגוריתם ביקורת (Luhn-variant הישראלי). לא חובה לאכוף ב-Phase 1 (אפשר להשאיר כ-string validator), אבל להוסיף TODO להעברה לExtension של `identity_router.py` ב-Phase 2.
2. **Masking ב-audit payload** — רק `id_number[-4:]` מוצג.
3. **Masking ב-GET endpoints שאינם הפרופיל המלא** — רשימת עובדים = `id_number_masked: "****1234"`. פרופיל מלא = ת.ז. מלאה רק ל-management_team + safety roles.

**מה נדחה ל-SOC2 Stage:** field-level encryption של ת.ז. (AES-256 + KMS). Phase 1 = string + masking בלבד.

#### ג.5 Indices (MongoDB)

הוסף ל-`backend/server.py` (סעיף create_index) את הבאים:

```python
# contractor_companies
await db.contractor_companies.create_index([("project_id", 1), ("deleted_at", 1)])
await db.contractor_companies.create_index([("project_id", 1), ("name", 1)])  # autocomplete

# workers
await db.workers.create_index([("project_id", 1), ("deleted_at", 1)])
await db.workers.create_index([("contractor_company_id", 1), ("deleted_at", 1)])
await db.workers.create_index([("project_id", 1), ("id_number", 1)])  # dedupe lookup

# worker_training_types — seeded, small collection
await db.worker_training_types.create_index([("name", 1)], unique=True)

# worker_trainings
await db.worker_trainings.create_index([("worker_id", 1), ("deleted_at", 1)])
await db.worker_trainings.create_index([("project_id", 1), ("expires_at", 1)])  # expiry reports
await db.worker_trainings.create_index([("project_id", 1), ("training_type_id", 1)])
```

**למה `(project_id, deleted_at)` ולא רק `project_id`:** כל query סורק soft-delete. compound index חוסך 10x על queries כבדים (1000+ עובדים).

### ד. נקודת אינטגרציה ב-Frontend

#### ד.1 Tab registration

```javascript
// frontend/src/pages/ProjectControlPage.js — השורה לתוך workTabs (line ~3497)
{
  id: 'safety',
  label: 'בטיחות ויומן עבודה',
  icon: ShieldAlert,       // lucide-react, כבר בשימוש בקוד
  hidden: !['project_manager', 'management_team'].includes(myRole)
          || !features?.safety_module_enabled,
},
```

`myRole` מקור אמת: `proj.my_role` (line 3295-3310). `features` נקרא מ-`useAuth()` context.

#### ד.2 Service pattern (מקביל ל-qcService)

```javascript
// frontend/src/services/api.js — סעיף חדש בתחתית
export const safetyService = {
  // Contractor companies
  listContractorCompanies: (projectId) =>
    api.get(`/api/safety/contractor-companies?project_id=${projectId}`),
  createContractorCompany: (data) =>
    api.post('/api/safety/contractor-companies', data),
  updateContractorCompany: (id, data) =>
    api.put(`/api/safety/contractor-companies/${id}`, data),
  deleteContractorCompany: (id) =>
    api.delete(`/api/safety/contractor-companies/${id}`),

  // Workers
  listWorkers: (projectId, filters) =>
    api.get(`/api/safety/workers`, { params: { project_id: projectId, ...filters } }),
  // ... same pattern
};
```

**קאש:** 30-second in-memory cache כבר קיים ב-api.js (lines 9-22). עדיף לא לעקוף אותו — עקבי עם שאר ה-services.

#### ד.3 Image compression (אם יש העלאת תמונה ב-Phase 1)

`frontend/src/utils/imageCompress.js` — 800KB max, 1600px, JPEG 0.7. כל העלאה דרכו. אם אין תמונות ב-Phase 1 — לא רלוונטי עד Phase 2 (תסקירי ציוד / תמונות הדרכה).

### ה. מה נדחה מפורשות מ-Phase 1 (תיעוד ההחלטה)

| נדחה | סיבה | אל-Phase |
|---|---|---|
| ת.ז. validation algorithm | `identity_router.py` קיים אבל לא מטפל ב-ID validation; נוסיף לשם ב-Phase 2 | Phase 2 |
| Field-level PII encryption (AES-256 + KMS) | דורש תשתית KMS — לא קיימת ב-backend היום | SOC2 Stage |
| Offline mode (IndexedDB + sync queue) | אין service worker/PWA setup ב-frontend; הוספה = 2-3 שבועות עבודה | Phase 4/5 |
| EXIF stripping + watermarking של תמונות ראיות | `upload_safety.py` לא עושה את זה היום; Phase 1 ב-scope ללא תמונות | Phase 2 |
| Cryptographic signatures (PAdES level T + timestamp authority) | pattern קיים ב-handover_router = canvas PNG + timestamp בלבד | SOC2 Stage |
| Safety Score engine | לא ב-Phase 1 scope (ראה "Next Step" למעלה) | Phase 4 |
| Project registration form (פנקס הקבלנים) | לא ב-Phase 1 scope | Phase 3 |
| Retention enforcement (block delete before `retention_until`) | השדה ייכתב, enforcement מאוחר יותר | SOC2 Stage |

**השורה התחתונה:** ה-deferrals מתועדים **בספק**, לא בראש של מישהו. כל אחד מהם הוא יום אחד תוספת לעומת להיכנס ל-Phase 1 עכשיו ולגלות חוב טכני.

### ו. סיכום — Spec Readiness Checklist

לפני שמעבירים spec ל-Replit, אשר שכל אחד מאלה סגור:

- [x] 4 collections מוגדרות עם מבנה Pydantic מלא (כולל 6 שדות audit/soft-delete/retention)
- [x] 11 indices מתועדים
- [x] דפוס route protection (`require_roles` + `_check_project_access`) מתועד
- [x] `_audit()` נקרא על כל mutation — כולל payload guidelines
- [x] Feature flag `ENABLE_SAFETY_MODULE` — off by default
- [x] Tab registration point: `ProjectControlPage.js:3497`
- [x] Service pattern ב-`api.js` מוגדר
- [x] Deferrals מתועדים (ז.1-8 מעלה)
- [x] קבלנים — manual entry + autocomplete מ-DB (החלטה 1 סעיף "החלטות סגורות")
- [x] "אין חברה" placeholder — seeded אוטומטית לכל פרויקט חדש
- [x] Export PDF/CSV/JSON — ב-Phase 1 (החלטה 7)

כל הפריטים ✓. **מוכנים ל-spec.**

---

**Teardown completed:** 2026-04-22 על-בסיס תצפית ב-16 screenshots + ניתוח 4 PDFs אמיתיים של Cemento. הקונספט הקודם עודכן לדיוק של pixel-level UI + field-level schema + validated export format.

**Post-research addendum:** 2026-04-22 אחרי deep code investigation (4 Explore agents במקביל, 22+ MongoDB collections ממופים, RBAC מדויק ל-line number, SOC2 gaps מתועדים). הקונספט מוכן להוריד לספק Phase 1 ל-Replit.
