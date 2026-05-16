# REPLIT FOLLOWUP #8 — Header strip בכל עמ' (לא רק בראש sub-section)

> **הבעיה:** כיום ה-header strip (BrikOps logo + לוגו חברה + תאריך מסירה + מספר אסמכתא) מופיע רק בעמ' הראשון של כל sub-section. בעמ' המשך (תוך-section) — אין header. המשתמש רוצה אחיד **בכל** עמ'.
>
> **הפתרון:** CSS Paged Media `running()` element. במקום 7 הופעות נפרדות, נציב את ה-header פעם אחת בlayer מיוחד שWeasyPrint משכפל אוטומטית בראש כל עמ' (פרט לcover).

---

## האסטרטגיה

**WeasyPrint תומך ב-CSS Paged Media `position: running()` ו-`content: element(...)`.** זה הסטנדרט הרשמי לrepeating headers בPDF.

המנגנון:
1. אלמנט בbody עם `position: running(page-header)` — נשלף מ-normal flow ונשמר כ"name slot"
2. ב-`@page { @top-left { content: element(page-header); } }` — WeasyPrint מציב את ה-element המשומר בראש כל עמ' אוטומטית

---

## התיקון

קובץ: `backend/templates/handover_protocol_pdf.html`

### שלב 1 — עדכן את ה-`@page` rules (סביב שורה 43-65)

**לפני:**
```css
@page {
  size: A4;
  margin: 18mm 12mm 18mm 12mm;
  @bottom-right {
    content: counter(page) " / " counter(pages);
    font-family: 'Rubik', sans-serif;
    font-size: 10px;
    color: #94A3B8;
    padding-top: 4mm;
  }
  @bottom-left {
    content: "נוצר באמצעות BrikOps · brikops.com";
    font-family: 'Rubik', sans-serif;
    font-size: 10px;
    color: #94A3B8;
    padding-top: 4mm;
  }
}
@page :first {
  margin: 0;
  @bottom-right { content: ""; }
  @bottom-left { content: ""; }
}
```

**אחרי:**
```css
@page {
  size: A4;
  margin: 24mm 12mm 18mm 12mm;   /* top margin הוגדל מ-18mm ל-24mm כדי לפנות מקום לheader */
  @top-left {
    content: element(page-header);
    width: 100%;                  /* ה-header תופס את כל רוחב העמ' */
    vertical-align: top;
  }
  @bottom-right {
    content: counter(page) " / " counter(pages);
    font-family: 'Rubik', sans-serif;
    font-size: 10px;
    color: #94A3B8;
    padding-top: 4mm;
  }
  @bottom-left {
    content: "נוצר באמצעות BrikOps · brikops.com";
    font-family: 'Rubik', sans-serif;
    font-size: 10px;
    color: #94A3B8;
    padding-top: 4mm;
  }
}
@page :first {
  margin: 0;
  @top-left { content: ""; }       /* cover ללא header */
  @bottom-right { content: ""; }
  @bottom-left { content: ""; }
}

.running-header {
  position: running(page-header);
}
```

**שינויים:**
- top margin: 18mm → 24mm (פינוי מקום לheader)
- `@top-left { content: element(page-header); width: 100%; }` חדש
- `.running-header { position: running(page-header); }` חדש (מסמן את האלמנט שיועתק ל-@top-left)
- ב-`@page :first` (cover): `@top-left { content: ""; }` כדי שהcover יישאר ללא header

### שלב 2 — הוסף את ה-running element בbody (מיד אחרי `<body>`)

מצא את תחילת ה-`<body>` ב-template, הוסף בשורה הראשונה:

```jinja
<body>

<!-- Running header — appears at top of every page (except cover) -->
<div class="running-header">{{ page_header() }}</div>

...rest of body...
```

(הוספת `<div class="running-header">{{ page_header() }}</div>` כשורה ראשונה ב-body, לפני ה-cover.)

### שלב 3 — מחק את 7 ההופעות של `{{ page_header() }}` בתוך ה-section page-breaks

חפש בכל ה-template:
```bash
grep -n "{{ page_header() }}" template
```

תמצא 7 מופעים בתוך ה-`<div class="page-break">` blocks. **מחק את כולם** — הם מיותרים עכשיו.

לדוגמה לפני:
```jinja
<div class="page-break">
  {{ page_header() }}

  <div class="page-label">TENANTS · דיירים</div>
  ...
```

אחרי:
```jinja
<div class="page-break">
  <div class="page-label">TENANTS · דיירים</div>
  ...
```

### שלב 4 — הוסיף top padding לpage-break sections (אופציונלי, לפיצוי על הגדלת המרגין)

אם אחרי השינויים ה-page-label נראה צפוף לheader, אפשר להוסיף ב-CSS של `.page-break`:

```css
.page-break { 
  page-break-before: always;
  padding-top: 6mm;   /* רווח קטן בין header לתוכן */
}
```

---

## VERIFY

לאחר deploy:

- [ ] `pdfinfo staging.pdf` → 22 עמ' (או דומה — עמ' מוסיף לו top margin גדול יותר אז ייתכן שהיו 22 ועכשיו 21)
- [ ] רנדר עמ' 5, 6, 7, 8 — **כל אחד** מציג את ה-header strip בראש
- [ ] עמ' 1 (cover) — **ללא** header strip (margin 0 משמר את העיצוב המקורי)
- [ ] בעמ' המשך של room ארוך (אם יש כזה) — header מופיע גם שם
- [ ] `grep -c "{{ page_header() }}" backend/templates/handover_protocol_pdf.html` → 1 (רק בתוך ה-`.running-header`)
- [ ] `grep -c "<div class=\"page-break\">" backend/templates/handover_protocol_pdf.html` → עדיין 7 (לא נגעת ב-page-break wrappers)

---

## הערה לWeasyPrint compatibility

WeasyPrint תומך ב-`position: running()` מאז גרסה 0.30 (2014). אם ה-version בproduction חדש מ-2014 — יעבוד. בדוק לפני deploy:

```python
import weasyprint
print(weasyprint.__version__)  # אמור להיות 53+ בBrikOps
```

---

## DO NOT

- אל תיגע ב-page_header macro עצמו (העיצוב נשאר זהה)
- אל תיגע ב-`<div class="page-break">` wrappers (נשארים, רק מסירים את ה-page_header() מתוכם)
- אל תיגע בcover page (`@page :first { margin: 0 }` נשמר כדי שהcover יישאר ללא header)
- אל תיגע ב-Photo diag, room-block, defects-summary-block, photo widths

---

## Carry-over invariants

- 7 `<div class="page-break">` נשארים
- 7 page-break-before nestings נשארים
- page_header macro definition יחיד (בקובץ)
- כעת רק 1 קריאה ל-`{{ page_header() }}` (בתוך `.running-header`), במקום 7
- Cover page עיצוב unchanged

---

## Standing rule

Replit עורך קבצים בלבד. אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
handover-pdf v3.8: repeat page header on EVERY page via CSS running()

Switched the page header strip from 7 inline calls to a single
running() element via CSS Paged Media.

- Added .running-header { position: running(page-header); } 
- Added @page { @top-left { content: element(page-header); } }
- Bumped @page top margin from 18mm to 24mm to fit the strip
- Cover page (@page :first) explicitly suppresses the running header
- Removed all 7 inline {{ page_header() }} calls from page-break sections

Result: header strip with BrikOps + contractor logos + delivery date +
reference number now appears at the top of EVERY page (except cover),
not just on the first page of each section. Matches Cemento layout.
```

מצופה זמן: 15-20 דקות. שינוי CSS + הוספת div אחד + מחיקת 7 קריאות. פשוט ובטוח.
