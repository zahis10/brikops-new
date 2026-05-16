# REPLIT TASK — Cleanup #1: דבר מוסר ושימושי

> **מטרה:** הסרה של ~50 שורות קוד מת מ-handover. **אפס שינוי visual, אפס שינוי behavior.**
>
> **רקע:** אחרי v2 → v3.8, נצברו CSS classes ופונקציה שלא בשימוש. דוח cleanup מאומת ל-100%.

---

## חלק 1 — Template: הסרת CSS classes מתות

קובץ: `backend/templates/handover_protocol_pdf.html`

### 1.1 — מחק `.no-break` (שורה 87)

```css
.no-break { page-break-inside: avoid; }
```

**אישור שלא בשימוש:** הוחלף ב-`.room-block` בv3.7. הרצנו `grep -c 'class="no-break"'` → 0 matches בbody.

### 1.2 — מחק `.keep-with-next` (שורות 116-120)

```css
.keep-with-next {
  page-break-after: avoid;
  break-after: avoid;
}
```

**אישור:** הוסף בv3.5 ל-page-label של ROOM INSPECTIONS, הוסר משם בv3.6. הרצנו `grep -c 'class="keep-with-next"\|class="page-label keep-with-next"'` → 0 matches.

### 1.3 — מחק `.tags` (שורה 397)

```css
.tags { margin-top: 4px; }
```

**אישור:** Grep → 0 matches בbody.

### 1.4 — מחק `.tag-mini` (שורות 398-411)

```css
.tag-mini {
  display: inline-block;
  font-size: 9.5px;
  ...
  background: var(--paper);
  color: var(--slate-7);
  border: 1px solid var(--slate-2);
}
.tag-mini.warn {
  ...
}
```

(מחק את כל ה-block של `.tag-mini` + `.tag-mini.warn`.)

**אישור:** Grep → 0 matches בbody.

---

## חלק 2 — Service: הסרת פונקציה לא בשימוש

קובץ: `backend/services/handover_pdf_service.py`

### 2.1 — מחק `_sanitize_filename` (שורה 141 + body של הפונקציה)

```python
def _sanitize_filename(text: str) -> str:
    ...
```

(מחק את כל הdefinition של הפונקציה.)

**אישור:**
- 0 קריאות בתוך service.py
- 0 קריאות מקבצים אחרים בbackend (רץ `grep -rn "_sanitize_filename" backend/ --include="*.py"`)
- הפונקציה היא private (`_` prefix) ולא חשופה כ-public API

---

## VERIFY

לפני merge:

```bash
# Template — וודא שאין שום reference למחקים
grep -E "no-break|keep-with-next|tag-mini|tags " backend/templates/handover_protocol_pdf.html
# צריך להחזיר רק matches שלא קשורים לclasses (כמו 'no-break-string-in-comment' או 'tags' בתוך מחרוזת)

# Service — וודא שהפונקציה הוסרה
grep -c "_sanitize_filename" backend/services/handover_pdf_service.py
# צריך להחזיר 0

# כל ה-codebase לא מסתמך על הפונקציה
grep -rn "_sanitize_filename" backend/ --include="*.py"
# צריך להחזיר 0 results
```

הtemplate צריך להמשיך לרנדר נכון (אין שינוי visual). הPDF צריך להיות זהה ל-v3.8.

---

## DO NOT

- אל תיגע ב-**Photo diag** logging (עדיין שימושי לדיבאג)
- אל תיגע ב-**legal_sections diagnostic** (warning מועיל לפרודקשן)
- אל תיגע ב-router (audit נפרד עתידי)
- אל תשנה שום CSS rule שכן בשימוש
- אל תיגע ב-`generate_handover_pdf` (זו הfunction הציבורית, נקראת מהrouter בשורה 1927)

---

## Carry-over invariants

כל ה-invariants מ-v3.3 → v3.8 ממשיכים:
- @font-face = 2, text-transform = 0
- Photo diag = 2 (לא נגוע)
- room-block, defects-summary-block, page-break × 7 — כולם נשמרים
- page_header() macro + .running-header (v3.8) — לא נגוע
- Rubik-Bold.ttf = 47688 bytes
- כל הCSS classes שכן בשימוש (.room-block, .row-bad, .row-part, .photo-row, וכו')

---

## Standing rule

Replit עורך קבצים בלבד. אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
handover: cleanup — remove 4 dead CSS classes + 1 unused function

Template:
  - .no-break (replaced by .room-block in v3.7)
  - .keep-with-next (added in v3.5, removed from usage in v3.6)
  - .tags (never used)
  - .tag-mini / .tag-mini.warn (never used)

Service:
  - _sanitize_filename() (defined but never called, public or private)

Net: ~50 lines removed, zero behavior change. PDF rendering identical
to v3.8.
```

מצופה זמן: 5-10 דקות. שינויים מכניים, אפס logic.
