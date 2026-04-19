# Spec: Billing Cleanup — Minimal, Low-Risk Touches Only

**Date:** 2026-04-15
**Target branch:** `main` (post-rebase, at commit `f50dd9e`)
**Priority:** P4 — cleanup, not a bug fix
**Risk tier:** MINIMAL (pure dead-code removal + constant unification)

---

## TL;DR לקובע המדיניות

לאחר בדיקת קוד מעמיקה, מערכת ה-billing **עובדת נכון**. הממצאים המקוריים (3 מקורות אמת, snapshot stale וכו') התבררו כלא נכונים: ה-single source of truth `get_billable_amount()` כן מופעל מכל 3 קוראי `generate_invoice`, רק בקריאה אחת למעלה מ-`build_invoice_preview`.

**הספק הזה כולל רק 2 תיקונים בטוחים ביותר**, ומפורט מה **לא** לגעת ולמה. אם יש ספק כלשהו — **אל תבצע גם את הספק הזה**. הסיכון בשינוי billing עובד גדול מהתועלת של ניקיון.

---

## מה אני **מחריג מהספק הזה בכוונה** (DO NOT TOUCH)

| ממצא מקורי | למה לא לגעת |
|---|---|
| "3 מקורות אמת" / `build_invoice_preview` לא משתמש ב-`get_billable_amount` | **שגוי** — ה-callers של `generate_invoice` כן משתמשים. `build_invoice_preview` משמש רק לתצוגה/line_items. המערכת תקינה. |
| `PROJECT_LICENSE_FIRST == PROJECT_LICENSE_ADDITIONAL == 450` | ייתכן שזו **תשתית לעתיד** (הנחה רב-פרויקטית). להשאיר כפי שהוא. אם תרצו להחליט עסקית לבטל — ספק נפרד עם PM. |
| Snapshot fields ב-`invoice_line_items` | זה **חוק ישראלי** — חשבונית חייבת להיות immutable. השדות `*_snapshot` הם הרשומה החשבונאית. **לא לגעת לעולם.** |
| Yearly billing אין הנחה | החלטה עסקית, לא באג. |
| `calculate_monthly` override חוזר שקטית | תיאורטי. רק super admin יכול להגדיר override; הם יראו מה שהם מגדירים. |
| `invoice_line_items` כפילות `units_count` + `contracted_units_snapshot` | **חשבוניות קיימות נשמרו עם השדות האלה.** כל דוח/ייצוא שקרא אותן מסתמך על זה. לא לגעת. |

---

## מה **כן** לעשות (2 שינויים)

### שינוי 1: מחיקת `calculate_org_monthly` (dead code)

**קובץ:** `backend/contractor_ops/billing_plans.py`
**שורות:** 83-99

**מה למחוק:** את כל הפונקציה `calculate_org_monthly`.

**למה בטוח למחוק:**
- `grep -rn "calculate_org_monthly" backend/` מחזיר **רק את ההגדרה עצמה** — אין callers. לא ב-production, לא בטסטים, לא בסקריפטים.
- הפונקציה עדיין משתמשת ב-`proj.get("units_count", 0)` — שדה שהוחלף ב-Task #338 ל-`total_units`. כל ניסיון להחיות אותה יגרום לחישוב שגוי.
- ללא cross-reference, ללא סיכון.

**איך לוודא לפני המחיקה:**
```bash
grep -rn "calculate_org_monthly" backend/ frontend/
```
צריך להחזיר שורה אחת בלבד (ההגדרה ב-`billing_plans.py:83`). אם יותר — **עצור ולדווח.**

**DO NOT:**
- אל תגע בקבועים `PROJECT_LICENSE_FIRST`, `PROJECT_LICENSE_ADDITIONAL`, `PRICE_PER_UNIT` — הם בשימוש במקומות אחרים.
- אל תגע ב-`calculate_monthly` (יחיד, ללא `org_`) — זה בשימוש פעיל.
- אל תגע ב-`get_pricing_breakdown`.

**VERIFY after deletion:**
```bash
cd backend && python -c "from contractor_ops.billing_plans import calculate_monthly, PROJECT_LICENSE_FIRST, PROJECT_LICENSE_ADDITIONAL, PRICE_PER_UNIT, FOUNDER_PLAN, get_pricing_breakdown, get_plan, list_plans, seed_default_plans, set_plans_db; print('OK')"
```
חייב להדפיס `OK`.

והריצו את הטסטים:
```bash
cd backend && pytest tests/test_billing_v1.py -v
```
חייב לעבור ירוק.

---

### שינוי 2: קבוע יחיד ל-founder monthly price

**קובץ:** `backend/contractor_ops/billing_plans.py`
**פעולה:** החליפו את ה-literal `499` בקבוע מודול-level.

**מצב נוכחי** (5 מקומות, הוכח במסורת — Task #270 שינה 500→499):

```python
# billing_plans.py:31
FOUNDER_PLAN = {
    "plan_id": "founder_6m",
    "name": "מנוי מייסדים",
    "monthly_price": 499,     # ← literal
    "locked_months": 6,
}

# billing_plans.py:45 (calculate_monthly)
if plan_id == "founder_6m":
    return 499                # ← literal

# billing_plans.py:66 (get_pricing_breakdown)
if plan_id == "founder_6m":
    return {
        "plan": "מנוי מייסדים",
        "total_monthly": 499,         # ← literal
        "breakdown": "מנוי מייסדים — 499₪/חודש",   # ← literal
    }

# billing_plans.py:91 (calculate_org_monthly — יימחק בשינוי 1, לא רלוונטי)
if plan_id == "founder_6m":
    return 499

# billing_plans.py:122 (get_plan)
if plan_id == "founder_6m":
    return {
        'id': 'founder_6m',
        'name': 'מנוי מייסדים',
        'monthly_price': 499,        # ← literal
        'is_active': True,
    }
```

**פעולה נדרשת:**
1. הוסיפו קבוע אחרי `PRICE_PER_UNIT = 15`:
   ```python
   FOUNDER_MONTHLY_PRICE = 499
   ```
2. החליפו בכל 4 ה-literals של `499` בקובץ **את המספר עצמו בלבד** בקבוע `FOUNDER_MONTHLY_PRICE`.
3. ב-`get_pricing_breakdown:68` ה-string `"מנוי מייסדים — 499₪/חודש"` — עדכנו ל-f-string:
   ```python
   "breakdown": f"מנוי מייסדים — {FOUNDER_MONTHLY_PRICE}₪/חודש",
   ```

**DO NOT:**
- אל תחליפו `499` ב-`billing.py:1668` (יש `499` מחוץ ל-`billing_plans.py`). אם רוצים לאחד גם שם, זה ספק נפרד. הסיבה: `billing.py` מיובא לפני `billing_plans.py` ויש סיכוי קטן לקשיחות סדר-טעינה. שינוי בקובץ אחד — סיכון מינימלי.
- אל תגעו ב-`FOUNDER_PLAN["monthly_price"]` ב-schema validators או ב-frontend. אל תוסיפו export לקבוע ל-API.
- אל תשנו `"monthly_price"` key name — הוא בשימוש בטסטים ובצרכני API חיצוניים אולי.

**VERIFY:**
```bash
grep -n "499" backend/contractor_ops/billing_plans.py
```
צריך להחזיר **רק**: `FOUNDER_MONTHLY_PRICE = 499` (שורה אחת).

```bash
cd backend && pytest tests/test_billing_v1.py -v
```
חייב לעבור ירוק.

ידנית: התחברו לדמו, גשו ל-`OrgBillingPage`, ודאו שמנוי מייסדים מציג 499₪ (לא שינוי לעיני משתמש).

---

## Pre-flight checklist — **חייב** להתבצע לפני כל שינוי

- [ ] Backup של DB הפרודקשן (MongoDB Atlas snapshot) — לא חלק מהספק, חייב להיות פעולה ידנית שלך.
- [ ] Branch עבודה נפרד (`chore/billing-cleanup-minimal`), **לא על main**.
- [ ] הריצו את **כל** `backend/tests/test_billing*.py` לפני כל שינוי — שמרו את ה-output כ-baseline.
- [ ] `grep -rn "calculate_org_monthly" backend/ frontend/` — חייב להחזיר שורה אחת בלבד (הגדרה). אחרת — **עצור.**

## Post-deployment verification

- [ ] `pytest backend/tests/test_billing_v1.py` ירוק.
- [ ] `pytest backend/tests/test_e2e.py` ירוק (טסט אינטגרציה שנוגע ב-billing flow).
- [ ] ידנית ב-staging/demo: הפקת חשבונית ידנית ב-`OrgBillingPage` → סכום זהה לפני/אחרי.
- [ ] ידנית ב-staging/demo: דשבורד סופר-אדמין → MRR זהה לפני/אחרי.
- [ ] 48 שעות של בקרה על לוגים `[BILLING_AMOUNT]` בפרודקשן אחרי merge — מחפשים שגיאות ImportError או KeyError.

## Rollback plan

אם משהו נשבר:
```bash
git revert <commit-sha>
git push origin main
```
השינויים הם pure refactor (ללא שינויי schema/DB), כך ש-revert פשוט מחזיר את המצב הקודם.

---

## מה **לא** לעשות ולמה (תזכורת)

**אל תבצעו רפקטור של `monthly_total` snapshot → live computation.** גם אם זה "נקי יותר":
1. המערכת עובדת (אימות: `get_billable_amount` נקרא מכל 3 קוראי `generate_invoice`).
2. שינוי כזה יחייב מיגרציה של חשבוניות היסטוריות.
3. בישראל — חשבונית מס עברית חייבת להיות immutable אחרי issuance. המבנה הנוכחי נכון מבחינה חוקית.

**אל תאחדו PROJECT_LICENSE_FIRST/ADDITIONAL.** אם הם זהים כרגע אבל שני קבועים — יש פה אופציה עתידית להבדל. מחיקה של אחד = loss of optionality.

**אל "תכניסו סדר" ב-`billing.py` הגדול.** הוא 2,177 שורות ומכיל 40+ commits של תיקונים מהחודש האחרון. כל רפקטור = סיכון לאבד באג fix שכבר הוכח.

---

## שאלות שהמפתח ב-Replit **חייב** לעצור ולשאול לפני commit

1. האם `grep -rn "calculate_org_monthly" backend/ frontend/` מחזיר שורה אחת בלבד?
2. האם `pytest backend/tests/test_billing_v1.py` עבר ירוק לפני השינוי (baseline)?
3. האם יש תקלות פתוחות (GitHub Issues) הקשורות ל-billing שעדיין לא סגורות? אם כן — **עצור**. תיקונים פתוחים הם עדיפות גבוהה יותר מ-cleanup.

אם התשובה לאחת מהשאלות היא "לא" או "לא בטוח" — **אל תבצע את הספק. סגור PR ריק ובקש הבהרה.**
