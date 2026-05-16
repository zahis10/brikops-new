# REPLIT FOLLOWUP #6 (גרסה מתוקנת — Option A)

> **חשוב:** זה מחליף את הספק הקודם. ההבדל: בFix 1, שומרים את ה-page-break (כדי שה-header strip יישאר בראש עמ' חדש) ובמקום זאת מסירים את ה-`<div class="no-break">` שעוטף כל room.

3 תיקונים לPDF v3.6:

1. **עמ' 5+6 ריקים** — orphan page-label אחרי forced page-break
2. **תמונות עדיין גדולות מדי** — 50% רוחב לתמונה אחת
3. **Header strip חסר לוגו קבלן + תאריך מסירה**

---

## תיקון 1 — Orphan pages (Option A: keep page-break, allow rooms to break)

### האבחנה

ב-v3.5 PDF:
- עמ' 4: סיכום ליקויים
- **עמ' 5: ריק** (רק header strip)
- **עמ' 6: כמעט ריק** (רק page-label "ROOM INSPECTIONS · בדיקת חדרים")
- עמ' 7: room ראשון (כניסה לדירה)

הבעיה: יש `<div class="page-break">` שמכריח עמ' חדש, ויש `<div class="no-break">` סביב כל room. הroom הראשון לא נכנס בעמ' 5 → WeasyPrint מזיז גם את ה-page-label לעמ' 6 (בגלל `keep-with-next` שהוסף בv3.5) → אבל הroom עדיין לא נכנס שם → עובר לעמ' 7. תוצאה: 2 עמ' ריקים.

### התיקון

**שמור את ה-`<div class="page-break">` של ROOM INSPECTIONS** — זה חשוב כדי שה-header strip יופיע בראש עמ' חדש. **הסר את ה-`<div class="no-break">` סביב כל room בלולאה** — תן לrooms להישבר טבעית בין שורות הטבלה.

קובץ: `backend/templates/handover_protocol_pdf.html`

#### שלב 1.1 — הסר את `<div class="no-break">` בלולאת inspection_sections

מצא את הבלוק (סביב שורה 1305-1314):
```jinja
{% for sec in inspection_sections|default([]) %}
{% set sec_defects = (sec.fail|default(0)) + (sec.partial|default(0)) %}
<div class="no-break">
  <div class="room-head">
    ...
```

החלף ל:
```jinja
{% for sec in inspection_sections|default([]) %}
{% set sec_defects = (sec.fail|default(0)) + (sec.partial|default(0)) %}
<div class="room-block">
  <div class="room-head">
    ...
```

(שינוי: `class="no-break"` → `class="room-block"`)

ומצא את ה-`</div>` שסוגר את הבלוק (יש לו pair, לפני `{% endfor %}`). לא צריך לשנות אותו — הוא נשאר.

#### שלב 1.2 — הוסף CSS שמתיר לroom להישבר אבל שומר את ה-room-head עם תחילת הטבלה

הוסף בסוף ה-CSS (סמוך ל-`.room-head` או למקום הגיוני):

```css
.room-block {
  page-break-inside: auto;     /* תן לroom להישבר אם הוא ארוך */
}
.room-head {
  page-break-after: avoid;     /* room-head תמיד יישאר עם תחילת הטבלה */
}
.items tbody tr {
  page-break-inside: avoid;    /* שורה בודדת לא תישבר באמצע */
}
```

#### שלב 1.3 — הסר את `keep-with-next` מ-page-label של ROOM INSPECTIONS

מצא (סביב שורה 1305 או היכן שזה כיום):
```jinja
<div class="page-label keep-with-next">ROOM INSPECTIONS · בדיקת חדרים</div>
```

החלף ל:
```jinja
<div class="page-label">ROOM INSPECTIONS · בדיקת חדרים</div>
```

(שלא יתחרה עם הshift הטבעי של הroom-block.)

#### תוצאה צפויה

- ROOM INSPECTIONS עדיין מתחיל בעמ' חדש (header strip יפה בראש)
- הroom הראשון מתחיל מיד אחרי ה-page-label, ממלא את העמ'
- אם הroom ארוך מדי — הטבלה נשברת בין שורות (לא מכוערת)
- אין יותר orphan pages

---

## תיקון 2 — תמונות קטנות יותר

קובץ: `backend/templates/handover_protocol_pdf.html`

מצא:
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

---

## תיקון 3 — Header strip עם לוגו קבלן + תאריך מסירה

### Macro חדש

קובץ: `backend/templates/handover_protocol_pdf.html`

#### שלב 3.1 — הוסף macro בראש הtemplate (אחרי ה-CSS, לפני ה-body או בתחילת ה-body)

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

#### שלב 3.2 — הוסף CSS לlogo החברה ולתאריך

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

#### שלב 3.3 — החלף את 7 ההופעות של `<div class="ph">...</div>` ב-`{{ page_header() }}`

יש 7 page-break sections, כל אחד עם header inline:
- TENANTS · דיירים
- TABLE OF CONTENTS · DEFECTS SUMMARY
- ROOM INSPECTIONS · בדיקת חדרים
- HANDED-OVER ITEMS · METER READINGS
- LEGAL DECLARATIONS · נסחים משפטיים
- TENANT NOTES · הערות הדייר
- SIGNATURES · חתימות

בכל אחד, החלף את הבלוק:
```jinja
<div class="ph">
  <div class="ph-left">
    {% if brikops_logo_b64 %}<img class="ph-logo" src="{{ brikops_logo_b64 }}" alt="">{% endif %}
    <span class="ph-title">פרוטוקול מסירה{% if building_name or unit_name %} · <b>{{ building_name }}{% if unit_name %} · {{ unit_name }}{% endif %}</b>{% endif %}</span>
  </div>
  <div class="ph-right">{{ generation_date }}{% if display_number %} · {{ display_number }}{% endif %}</div>
</div>
```

ב-:
```jinja
{{ page_header() }}
```

---

## VERIFY

לאחר deploy:

**Fix 1 (orphan pages):**
- [ ] `grep -c "no-break" backend/templates/handover_protocol_pdf.html` → רק על הCSS rule הישן `.no-break` (אם הושאר), אבל לא בtemplate body. אם תרצה — תוכל למחוק את ה-CSS rule הישן `.no-break { page-break-inside: avoid; }` כי לא משתמשים בה יותר.
- [ ] בPDF: אין יותר עמ' שמכיל רק header strip + page-label
- [ ] ROOM INSPECTIONS מתחיל בעמ' חדש (header strip בראש), והroom הראשון נכנס באותו עמ'
- [ ] אם room ארוך — נשבר טבעית בין שורות הטבלה (הroom-head נשאר עם תחילת הטבלה)

**Fix 2 (smaller photos):**
- [ ] ליקוי עם 1 תמונה → cell ב-40% רוחב

**Fix 3 (header):**
- [ ] בכל עמ' (פרט לcover): BrikOps logo + לוגו חברה (אם הוגדר) + שם פרוטוקול בשמאל
- [ ] בצד ימין: "מסירה: [תאריך]" בכתום bold + מספר אסמכתא
- [ ] קל לוודא ש-7 הופעות של `<div class="ph">` הוחלפו: `grep -c "<div class=\"ph\">" backend/templates/handover_protocol_pdf.html` = 0
- [ ] `grep -c "page_header()" backend/templates/handover_protocol_pdf.html` = 7

---

## DO NOT

- אל תיגע בPhoto diag logging
- אל תיגע ב-`.meter .photo`
- אל תיגע ב-`_str_val` (Excel import bug — separate PR)
- אל תוסיף עוד forced page-breaks. הסרת `keep-with-next` ו-`no-break` בלבד.
- אל תיגע ב-`backend/fonts/Rubik-Bold.ttf` (משמש safety_pdf.py)

---

## Carry-over invariants (must remain unchanged)

- `@font-face` count = 2 (variable Rubik + Caveat)
- `text-transform` count = 0
- `Photo diag` in service = 2
- `photo-empty` references = 0
- `Rubik-Bold.ttf` = 47688 bytes
- Defect signature rendering wired (legal sigs from v3.5)
- Meter `<img>` tags still present
- defects-summary-block wrapper intact (v3.4)

---

## Standing rule

Replit עורך קבצים בלבד. **לא commit, לא push, לא deploy.**

אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
handover-pdf v3.6: smaller photos + header logo+date + fix orphan pages

Fix #1 (orphan pages 5+6):
  Keep the forced page-break before ROOM INSPECTIONS so the section
  still starts cleanly on a new page with its header strip on top.
  Remove the no-break wrapper around individual rooms — let rooms
  split naturally between table rows when they're too tall to fit on
  one page. The v3.5 keep-with-next attempt is removed (no longer
  needed and was making things worse).

Fix #2 (photos still too large):
  1-photo and 2-photo cell width 50% → 40%. Less dominant on the page.

Fix #3 (header improvements):
  - Refactor page header into a Jinja macro (DRY across 7 sections)
  - Add company (contractor) logo next to BrikOps logo when configured
  - Add prominent delivery date "מסירה: [date]" in header right
  - Falls back to generation_date if not yet signed
```

מצופה זמן: 30-45 דקות.
