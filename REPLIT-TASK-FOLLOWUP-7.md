# REPLIT FOLLOWUP #7 — תמונות קטנות יותר + תיקון splits של סקציות קטנות

> 2 תיקונים אחרי v3.6:
>
> 1. **תמונות עדיין גדולות מדי** — 40% רוחב לתמונה אחת. המשתמש: "בסגנון של סמנטו" (ש~25-30%). בנוסף, הוא רוצה לתמוך **יותר** מ-3 תמונות בליקוי.
> 2. **Section split bug** — "שירותי הורים" (13 פריטים, room קטן) מתחיל בתחתית עמ' עם header + 1 שורה, ממשיך בעמ' הבא. גרוע להדפסה A4.

---

## תיקון 1 — Photos: smaller + support up to 6

### חלק A — Service: bump cap 3 → 6

קובץ: `backend/services/handover_pdf_service.py` שורה 411:

```python
for photo_ref in item_photos[:3]:
```

החלף ל:
```python
for photo_ref in item_photos[:6]:
```

### חלק B — CSS: smaller widths + support count-4/5/6

קובץ: `backend/templates/handover_protocol_pdf.html`

מצא את הבלוק:
```css
.photo-row.count-1 .cell { width: 40%; }
.photo-row.count-2 .cell { width: 40%; }
.photo-row.count-3 .cell { width: 33.33%; }
```

החלף ל:
```css
.photo-row.count-1 .cell { width: 30%; }
.photo-row.count-2 .cell { width: 30%; }
.photo-row.count-3 .cell { width: 30%; }
.photo-row.count-4 .cell { width: 24%; }
.photo-row.count-5 .cell { width: 19%; }
.photo-row.count-6 .cell { width: 16%; }
```

**מה זה עושה:**
- 1-3 תמונות: כל אחת ב-30% (סגנון סמנטו, ~6cm רוחב על A4)
- 4 תמונות: 24% × 4 = 96% מהרוחב
- 5 תמונות: 19% × 5 = 95%
- 6 תמונות: 16% × 6 = 96%

הJinja loop כבר משתמש ב-`count-{{ _count }}` — אין צורך לשנות אותו. אוטומטית יתמוך בעד 6.

**Trade-off:** 6 תמונות בליקוי אחד יכול להיות גדול בקובץ, אבל המקור עדיין 1100px ו-quality 85, אז כל תמונה ~30KB jpeg. 6 × 30KB = 180KB extra per defect with all 6. סביר.

---

## תיקון 2 — Section split bug (Smart keep-together)

### האבחנה

בv3.6 הסרנו את `<div class="no-break">` סביב כל room ושמנו `page-break-inside: auto` — זה פתר את עמ' 5+6 הריקים אבל יצר בעיה חדשה: סקציות קטנות (כמו "שירותי הורים", 13 פריטים) מתחילות בתחתית עמ' עם header + שורה אחת ונמשכות בעמ' הבא.

### האסטרטגיה

הroom **הראשון** ב-ROOM INSPECTIONS חייב להיות `auto` כדי שיוכל להישבר אם לא נכנס בעמ' החדש (אחרי header strip + page-label). אחרת חוזרים לבעיית עמ' 5 הריק.

הrooms **האחרים** באמצע הflow לא צריכים להישבר. הם צריכים `page-break-inside: avoid` — אם לא נכנסים בעמ' הנוכחי, יעברו כולם לעמ' הבא.

### התיקון

קובץ: `backend/templates/handover_protocol_pdf.html`

#### שלב 2.1 — שינוי בtemplate (לולאת inspection_sections)

מצא:
```jinja
{% for sec in inspection_sections|default([]) %}
{% set sec_defects = (sec.fail|default(0)) + (sec.partial|default(0)) %}
<div class="room-block">
```

החלף ל:
```jinja
{% for sec in inspection_sections|default([]) %}
{% set sec_defects = (sec.fail|default(0)) + (sec.partial|default(0)) %}
<div class="room-block{% if not loop.first %} keep-together{% endif %}">
```

(שינוי: הוסף class מותנה `keep-together` לכל room שאינו הראשון.)

#### שלב 2.2 — CSS

מצא את הבלוק:
```css
.room-block {
  page-break-inside: auto;
}
```

החלף ל:
```css
.room-block {
  page-break-inside: auto;       /* default — first room can split */
}
.room-block.keep-together {
  page-break-inside: avoid;      /* all subsequent rooms try to stay together */
}
```

### תוצאה צפויה

- ROOM INSPECTIONS מתחיל בעמ' חדש (header strip + page-label)
- הroom הראשון נכנס באותו עמ' (יכול להישבר אם ארוך)
- אם הroom הראשון יוצא מאוד גדול ולא נכנס → WeasyPrint יחלק אותו (`auto`) → אין יותר orphan page
- room שני, שלישי וכו' מנסים להישאר שלמים — אם לא נכנסים בעמ' הנוכחי, עוברים כולם לעמ' הבא
- "שירותי הורים" (13 פריטים) → או נכנס שלם, או עובר כולו לעמ' הבא. **לא נשבר באמצע.**

---

## VERIFY

לאחר deploy:

**Fix 1 (photos):**
- [ ] ליקוי עם 1 תמונה → cell ב-30% (קטן יותר, סגנון סמנטו)
- [ ] ליקוי עם 4 תמונות → 4 cells ב-24% כל אחד (כל ה-4 בשורה אחת)
- [ ] ליקוי עם 6 תמונות → 6 cells ב-16% כל אחד (תמונות מיניאטוריות אבל ברורות)
- [ ] grep `[:6]` ב-`backend/services/handover_pdf_service.py` (שורה 411)

**Fix 2 (sections):**
- [ ] אין יותר section שמתחיל בתחתית עמ' עם רק 1-2 שורות וממשיך בעמ' הבא
- [ ] עדיין אין orphan pages (5+6) — הroom הראשון מתחיל בעמ' חדש ויכול להישבר
- [ ] grep `keep-together` בtemplate → מופיע בלולאת sections + בCSS

---

## DO NOT

- אל תיגע ב-Photo diag logging
- אל תיגע ב-`.meter .photo`  
- אל תיגע ב-`_str_val` (Excel import — separate PR)
- אל תיגע במאקרו `page_header()` (מ-v3.6)
- אל תיגע ב-`.defects-summary-block` (מ-v3.4)
- אל תיגע ב-Rubik-Bold.ttf (משמש safety_pdf.py)

---

## Carry-over invariants (must remain unchanged)

- `@font-face` count = 2 (variable Rubik + Caveat)
- `text-transform` count = 0
- `Photo diag` in service = 2
- `photo-empty` references = 0
- `Rubik-Bold.ttf` = 47688 bytes
- `_DEFECT_PHOTO_WIDTH` = 1100 (יותר חד עכשיו עם cells צרים יותר)
- `_DEFECT_PHOTO_QUALITY` = 85
- 7 calls של `{{ page_header() }}`
- 7 forced `<div class="page-break">`
- defects-summary-block wrapper

---

## Standing rule

Replit עורך קבצים בלבד. **לא commit, לא push, לא deploy.**

אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
handover-pdf v3.7: smaller photos + support up to 6 + smart section break

Fix #1 (photo size + count):
  - All photo widths reduced to 30% (Cemento-style)
  - Service cap raised from 3 to 6 photos per defect
  - Add count-4/5/6 CSS rules (24%/19%/16%)
  - Effective DPI further increased: ~250 DPI at 30% (was ~190 at 40%)

Fix #2 (section split bug):
  - All rooms except the first get a keep-together class
  - CSS: .room-block.keep-together { page-break-inside: avoid }
  - First room stays auto so it can split if it doesn't fit on the
    fresh page after the section header (preserves v3.6 orphan-page fix)
  - Result: small sections like "שירותי הורים" no longer split with
    just 1-2 rows at the bottom of a page
```

מצופה זמן: 15-20 דקות. שני קבצים, שינויים מכניים.
