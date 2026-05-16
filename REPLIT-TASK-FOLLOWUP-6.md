# REPLIT FOLLOWUP #6 — עמ' ריקים, גודל תמונות, וכותרת עליונה

> 3 תיקונים אחרי סקירת PDF v3.5:
>
> 1. **עמ' 5 ו-6 עדיין ריקים** — התיקון הקודם עם `keep-with-next` לא עזר. עכשיו יש 2 עמ' ריקים במקום 1.
> 2. **תמונות עדיין גדולות מדי** — 50% רוחב לתמונה אחת זה דומיננטי. צריך לקטן.
> 3. **כותרת עליונה (header strip)** — להוסיף לוגו של החברה הקבלנית + תאריך מסירה.

---

## תיקון 1 — עמ' 5+6 ריקים

### האבחנה

ב-PDF הנוכחי:
- עמ' 4: סיכום ליקויים (טבלה)
- **עמ' 5: ריק** (רק header strip בראש)
- **עמ' 6: כמעט ריק** (רק page-label "ROOM INSPECTIONS · בדיקת חדרים")
- עמ' 7: room ראשון (כניסה לדירה)

הבעיה: יש `<div class="page-break">` שכופה new page לפני ROOM INSPECTIONS. אז:
- עמ' 5 מתחיל בכפיה
- ה-page-label עם `keep-with-next` רוצה להישאר עם ה-room הראשון
- ה-room ראשון לא נכנס בעמ' 5 (אפילו אחרי הheader)
- WeasyPrint מזיז את שניהם לעמ' 6
- עמ' 5 נשאר ריק
- בעמ' 6 הroom עדיין לא נכנס → עובר לעמ' 7
- עמ' 6 נשאר עם רק ה-label

### התיקון

**הסר את ה-`<div class="page-break">` לפני ROOM INSPECTIONS.** תן לסעיף לזרום מטבעי אחרי "סיכום ליקויים".

קובץ: `backend/templates/handover_protocol_pdf.html`

מצא את הבלוק (סביב שורה 1305):
```jinja
{# room inspections #}
<div class="page-break">
  <div class="ph">
    <div class="ph-left">...</div>
    <div class="ph-right">...</div>
  </div>

  <div class="page-label keep-with-next">ROOM INSPECTIONS · בדיקת חדרים</div>

  {% for sec in inspection_sections|default([]) %}
  ...
  {% endfor %}
</div>
```

החלף ל:
```jinja
{# room inspections — flows naturally from summary table, no forced page break #}
<div>
  <div class="page-label">ROOM INSPECTIONS · בדיקת חדרים</div>

  {% for sec in inspection_sections|default([]) %}
  ...
  {% endfor %}
</div>
```

**שינויים:**
- `<div class="page-break">` → `<div>` (מסיר את הכפיה)
- מסיר את ה-`<div class="ph">` block — הheader strip יוצג אוטומטית מ-`@page` של WeasyPrint (אם יש), או אפשר להעתיק אותו אם לא
- מסיר `keep-with-next` מ-page-label (כבר לא נחוץ)

**הערה:** אם הheader strip בכל עמ' מוצג מ-`@page` ולא מהtemplate — אז ה-`<div class="ph">` בכל page-break הוא רק לעמ' הראשון של אותה sub-section. בדוק זאת ובחר את הגישה הנכונה.

**אופציה חלופית** (אם הסרת page-break משבשת משהו אחר):
- השאר את ה-`<div class="page-break">` אבל **הסר את `<div class="no-break">` מהrooms**. כך rooms יכולים להישבר בין שורות. הroom הראשון יתחיל בעמ' 5 ואם לא נכנס יישבר טבעית לעמ' 6.

תבחר אופציה לפי מה שעובד בwidth WeasyPrint.

---

## תיקון 2 — תמונות גדולות מדי

המשתמש: "תמונות עדיין ענקיות מדי לדעתי".

### השינוי

קובץ: `backend/templates/handover_protocol_pdf.html`

מצא את הבלוק שהוסף בv3.5:
```css
.photo-row.count-1 .cell { width: 50%; }
.photo-row.count-2 .cell { width: 50%; }
.photo-row.count-3 .cell { width: 33.33%; }
```

החלף ל:
```css
.photo-row.count-1 .cell { width: 40%; }
.photo-row.count-2 .cell { width: 40%; }
.photo-row.count-3 .cell { width: 33.33%; }
```

**הסבר:** 40% במקום 50% — תמונה אחת תהיה קטנה יותר, ותשאיר מקום לכותרת + תיאור הליקוי במצב שטוח. גם 2 תמונות ב-40% (= 80%) נכנסות יפה עם רווח קטן בצדדים.

3 תמונות נשארות 33% — אין סיבה להזיז.

### תוצאה צפויה

תמונה 1 — גודל "card-style" קטן וקריא, לא דומיננטית.
2 תמונות — אחת ליד השנייה בגודל סביר.
3 תמונות — נשאר.

---

## תיקון 3 — Header strip: הוספת לוגו חברה + תאריך מסירה

### הצורך

המשתמש (בהתבסס על מתחרה Cemento):
- לוגו של חברה קבלנית בצד שמאל של הheader
- תאריך מסירה בולט בצד ימין

### העדויות

הservice (`handover_pdf_service.py`) כבר טוען את הלוגו של החברה בשורה 387-389 ומעביר אותו ל-context בשורה 705 כ-`logo_b64`.

הtemplate הנוכחי מציג רק את `brikops_logo_b64` (לוגו של הפלטפורמה), לא את `logo_b64` (לוגו של הקבלן).

`signed_date` גם זמין ב-context (שורה 707 בservice).

### התיקון

קובץ: `backend/templates/handover_protocol_pdf.html`

יש 7 הופעות של `<div class="ph">...` בtemplate. הגישה המומלצת: **macro Jinja**.

#### חלק A — הוסף macro בראש הtemplate (אחרי הCSS, לפני הbody או בתחילת הbody):

```jinja
{% macro page_header() %}
<div class="ph">
  <div class="ph-left">
    {% if brikops_logo_b64 %}<img class="ph-logo" src="{{ brikops_logo_b64 }}" alt=""/>{% endif %}
    {% if logo_b64 %}<img class="ph-logo ph-company-logo" src="{{ logo_b64 }}" alt=""/>{% endif %}
    <span class="ph-title">פרוטוקול מסירה{% if building_name or unit_name %} · <b>{{ building_name }}{% if unit_name %} · {{ unit_name }}{% endif %}</b>{% endif %}</span>
  </div>
  <div class="ph-right">
    {% if signed_date %}<span class="ph-date">מסירה: <b>{{ signed_date }}</b></span>{% else %}{{ generation_date }}{% endif %}
    {% if display_number %} · {{ display_number }}{% endif %}
  </div>
</div>
{% endmacro %}
```

#### חלק B — הוסף CSS לlogo החברה ולתאריך:

```css
.ph-company-logo {
  height: 22px;
  margin-right: 8px;
  vertical-align: middle;
}
.ph-date {
  color: var(--ink);
}
.ph-date b {
  color: var(--orange);
  font-weight: 700;
}
```

#### חלק C — החלף כל 7 ההופעות של `<div class="ph">...</div>` ב-`{{ page_header() }}`:

```jinja
{{ page_header() }}

<div class="page-label">TENANTS · דיירים</div>
...
```

(במקום הblock הישן של `<div class="ph">...</div>` עם 6 שורות.)

### תוצאה צפויה

- בכל עמ' (פרט לcover) יוצג: לוגו BrikOps + לוגו הקבלן (אם יש) + שם הפרוטוקול
- בצד ימין: "מסירה: [תאריך]" בכתום bold + מספר אסמכתא

---

## VERIFY

לאחר deploy:

**תיקון 1 (עמ' ריקים):**
- [ ] אין יותר עמ' ריק/חצי-ריק בין סיכום ליקויים לROOM INSPECTIONS
- [ ] עמ' שמתחיל ב"ROOM INSPECTIONS" מכיל גם את הroom הראשון

**תיקון 2 (תמונות):**
- [ ] ליקוי עם 1 תמונה → cell ב-40% (לא 50%) — סביר ולא ענק
- [ ] ליקוי עם 2 תמונות → 80% מהרוחב לא יותר

**תיקון 3 (header):**
- [ ] בכל עמ' header strip מציג: BrikOps logo + לוגו חברה (אם הוגדר) + שם פרוטוקול בשמאל
- [ ] בצד ימין: "מסירה: [תאריך]" + מספר אסמכתא
- [ ] אם המשתמש שלך מהארגון "חברת הדגמה" — בדוק אם יש להם company_logo_url מוגדר. אם כן — אמור להופיע. אם לא — רק BrikOps logo

---

## DO NOT

- אל תיגע בPhoto diag logging
- אל תיגע ב-`.meter .photo`
- אל תיגע במקרא של `_str_val` (Excel import bug)
- אל תוסיף עוד forced page-breaks. רק הסרת אחד הקיים.
- אל תיגע בRubik-Bold.ttf (משמש safety_pdf.py)

---

## Standing rule

Replit עורך קבצים בלבד. **לא commit, לא push, לא deploy.**

אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
handover-pdf v3.6: smaller photos + header logo+date + remove orphan pages

Fix #1 (orphan pages 5+6):
  Remove forced page-break before ROOM INSPECTIONS section. Let the
  page-label and first room flow naturally after summary table. The
  v3.5 keep-with-next attempt left an extra empty page; this is a
  cleaner solution.

Fix #2 (photos still too large):
  1-photo and 2-photo cell width 50% → 40%. Less dominant on the page,
  matches Cemento-style proportions.

Fix #3 (header improvements):
  - Refactor page header into a Jinja macro for DRY
  - Add company (contractor) logo next to BrikOps logo when configured
  - Add prominent delivery date "מסירה: [date]" in header right
  - Falls back to generation_date if not yet signed
```

מצופה זמן: 30-45 דקות. macro refactor = 7 החלפות + CSS חדש.
