# REPLIT FOLLOWUP #4 — תמונות מותאמות + תיקון פעור עמודים

> **Context:** ה-PR הקודם (`#459`) פתר את שני הבאגים של הג׳יבריש והתמונות. אומת ב-staging.
>
> **2 שיפורים נוספים שנמצאו בסקירה הויזואלית של הPDF:**
> 1. **תמונות בליקויים** — כיום תמיד 3 cells (גם אם הועלתה תמונה אחת בלבד → 1 קטנה + 2 ריקים). צריך layout מותאם: 1/2/3 תמונות → 1/2/3 cells בגודל מתאים, **בלי** placeholder cells ריקים.
> 2. **פגיעה משפטית של "סיכום ליקויים"** — הטבלה נשברת בין עמ' 3 לעמ' 4 (header בעמ' 3, השורות בעמ' 4). צריך לשמור על הטבלה עמ' אחד בלבד.

---

## תיקון A — Adaptive Photo Layout

### הבעיה

כיום הCSS+Jinja תמיד מייצר 3 תאים בשורה אופקית בגודל 33.33% כל אחד. אם המשתמש העלה רק תמונה אחת:
- תא 1: התמונה (קטנה — 33% רוחב)
- תא 2: dashed placeholder ריק
- תא 3: dashed placeholder ריק

המשתמש רוצה: התמונה היחידה תהיה גדולה (~60% רוחב, או full row), ובלי תאים ריקים.

### התיקון

**שינוי 1 — לCSS** (לאחר תיקון Bug 2 הקודם, היכן שמופיע `.photo-row`):

החלף את הCSS של `.photo-row` ו-`.photo-row .cell` ל:

```css
.photo-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  width: 100%;
}
.photo-row .cell {
  flex: 1 1 0;       /* כל cell חולק שווה את הרוחב */
  min-width: 0;
}
.photo-row.count-1 .cell {
  flex: 0 0 65%;     /* תמונה אחת — 65% רוחב, ממורכזת */
  margin: 0 auto;
}
.photo-row.count-2 .cell {
  flex: 0 0 calc(50% - 4px);   /* 2 תמונות חולקות שוויון */
}
/* count-3 משתמש בdefault flex: 1 — 3 תמונות שוות */
```

**הערה אם flex לא עובד טוב ב-WeasyPrint:** fallback ל-table-layout עם רוחבים מפורשים:

```css
.photo-row {
  display: table;
  table-layout: fixed;
  width: 100%;
  border-spacing: 8px 0;
  margin-top: 8px;
}
.photo-row .cell {
  display: table-cell;
  vertical-align: top;
}
.photo-row.count-1 .cell { width: 65%; }
.photo-row.count-2 .cell { width: 50%; }
.photo-row.count-3 .cell { width: 33.33%; }
```

(תבחר את האופציה שעובדת. WeasyPrint תומך ב-flex בגרסאות חדשות, אבל table הוא יותר אמין.)

**שינוי 2 — לJinja** (היכן שכרגע יש `<div class="photo-row">`):

```jinja
{%- set _ph = (it.photos or [])|select|list -%}
{%- set _count = _ph|length -%}
{% if _count > 0 %}
<div class="photo-row count-{{ _count }}">
  {% for p in _ph %}
    <div class="cell">
      <div class="photo" style="background-image: url('{{ p }}');"></div>
    </div>
  {% endfor %}
</div>
{% endif %}
```

**מה השתנה:**
- `_ph = (it.photos or [])|select|list` — רק תמונות אמיתיות (מסנן None/empty)
- `_count` — כמה תמונות יש בפועל
- מסיר את ה-`{% for i in range(3) %}` שהיה תמיד 3
- מוסיף class `count-1`/`count-2`/`count-3` ל-`.photo-row` כדי לקבוע את הרוחב
- **לא מציג** `.photo-empty` cells בכלל אם יש פחות מ-3 תמונות (המשתמש רצה במפורש: בלי תאים ריקים)

### Edge cases

- 0 תמונות: ה-defect-card לא מופיע בכלל (מסונן ב-`has_photo_items`). ✓ אין שינוי
- 1 תמונה: 1 תא, 65% רוחב, ממורכז. גדול וקריא בהדפסה.
- 2 תמונות: 2 תאים, 50% רוחב כל אחד.
- 3+ תמונות: 3 תאים שווים (אם _ph הוא 4+ → רק 3 הראשונים, כי באמת יש מגבלה ב-`item_photos[:3]` ב-service).

### VERIFY

לאחר deploy, צור 3 ליקויים שונים:
1. ליקוי עם תמונה אחת → צריך לראות תמונה גדולה ממורכזת, **בלי תאים ריקים משני הצדדים**
2. ליקוי עם 2 תמונות → 2 תמונות בגודל בינוני, אחת ליד השנייה
3. ליקוי עם 3 תמונות → 3 תמונות קטנות (כמו היום)

---

## תיקון B — שמירת "סיכום ליקויים" על עמוד אחד

### הבעיה

עמ' 3 כיום מכיל:
1. תוכן עניינים (TOC) — list של 15 חדרים
2. כותרת "סיכום ליקויים"
3. הסבר טקסטואלי
4. **טבלת `defects-table`** — אבל היא לא נכנסת בעמ' זה ונדחקת לעמ' 4

עמ' 4 הוא רק 4 שורות של הטבלה — בזבוז עמוד שלם.

### התיקון

הוסף `page-break-inside: avoid` על הטבלה והכותרת שלה. אם הטבלה לא נכנסת אחרי ה-TOC, היא תועבר *כולה* לעמ' חדש.

**שינוי לCSS** (חפש את `.defects-table` או הוסף בלוק חדש בסוף הCSS):

```css
.defects-summary-block {
  page-break-inside: avoid;
}
.defects-table {
  page-break-inside: avoid;
}
.defects-table tbody tr {
  page-break-inside: avoid;
}
```

**שינוי לטמפלייט** — עטוף את הסיכום והטבלה ב-wrapper:

לפני (שורות ~1255-1294):
```html
<h2 style="font-size:22px;font-weight:800;...">סיכום ליקויים</h2>
{%- set _td = total_defects|default(0) -%}
<p style="font-size:12.5px;color:var(--slate-7);margin:0 0 12px;">
  סה״כ {% if _td == 1 %}<b>...</b>{% else %}<b>{{ _td }} ליקויים</b> פתוחים{% endif %} —
  ...
</p>
{% if all_defects|default([]) %}
<table class="defects-table">
  ...
</table>
{% else %}
<div class="room-summary clean">...</div>
{% endif %}
```

אחרי:
```html
<div class="defects-summary-block">
  <h2 style="font-size:22px;font-weight:800;...">סיכום ליקויים</h2>
  {%- set _td = total_defects|default(0) -%}
  <p style="font-size:12.5px;color:var(--slate-7);margin:0 0 12px;">
    סה״כ {% if _td == 1 %}<b>...</b>{% else %}<b>{{ _td }} ליקויים</b> פתוחים{% endif %} —
    ...
  </p>
  {% if all_defects|default([]) %}
  <table class="defects-table">
    ...
  </table>
  {% else %}
  <div class="room-summary clean">...</div>
  {% endif %}
</div>
```

### מה זה עושה

WeasyPrint יראה את ה-`page-break-inside: avoid` על ה-wrapper ויחליט אחת משתיים:
- אם הסיכום + טבלה נכנסים אחרי ה-TOC באותו עמ' → ישאיר אותם שם
- אם לא → יקפיץ את כל הblock לעמ' חדש (במקום לפצל header בעמ' 3 ושורות בעמ' 4)

### VERIFY

- [ ] עמ' 3 או עמ' 4 (לא משנה איזה) מכיל **את כל** סיכום הליקויים: כותרת + הסבר + טבלה מלאה — ללא פיצול
- [ ] אין יותר עמ' שמתחיל באמצע טבלה

---

## DO NOT

- אל תיגע ב-`.meter .photo` (ממשיך לעבוד עם <img>)
- אל תיגע ב-`has_photo_items` filter (תקין — defects בלי תמונות לא מקבלים card)
- אל תיגע ב-Photo diag logging (עוזר לאבחן)
- אל תוסיף עוד forced page-breaks. אם משהו צריך להיות באותו עמוד — `page-break-inside: avoid`.

---

## Standing rule

Replit עורך קבצים בלבד. **לא commit, לא push, לא deploy.**

אחרי Build:
- אני (Zahi) אריץ `./deploy.sh --stag` ב-Shell של Replit (אחד יחיד אם השינויים באותו קובץ).
- אחרי אימות ב-staging → `./deploy.sh --prod`.

---

## Commit message מומלץ (commit אחד)

```
handover-pdf v3.4: adaptive photo layout + summary table page-break fix

Fix #1 (photo layout):
  Render 1/2/3 photos as 1/2/3 cells at 65%/50%/33% width
  instead of always 3 cells (which left empty placeholders when
  user uploaded fewer than 3 photos). Empty cells removed
  entirely — single photo now displays large + centered, fully
  readable when printed on A4.

Fix #2 (defects summary pagination):
  Wrap "סיכום ליקויים" header + table in .defects-summary-block
  with page-break-inside: avoid. Eliminates the bad split where
  the table header sat alone on one page and rows on the next.
```

---

מצופה זמן: 30 דקות. שני שינויים בקובץ אחד, ברורים ומכניים.
