# REPLIT HOTFIX — תיקון רוחב תמונות (v3.7.1)

> **Bug שלא תוקן ב-v3.7:** למרות שה-CSS אומר `.photo-row.count-1 .cell { width: 30%; }`, התמונות עדיין רנדרות ב-~95% רוחב (20cm על A4 במקום 5cm).

## האבחנה הטכנית

ה-CSS הנוכחי:
```css
.photo-row {
  display: table;
  width: 100%;          /* ← הbug! */
  border-spacing: 6px 0;
  margin-top: 8px;
  table-layout: fixed;
}
.photo-row .cell {
  display: table-cell;
  ...
}
.photo-row.count-1 .cell { width: 30%; }
```

**הבעיה:** כש-`.photo-row` הוא `display: table` עם `width: 100%`, ויש בו רק **cell אחד** עם `width: 30%`, WeasyPrint מתעלם מה-30% ומותח את הcell ל-100% מהtable כדי למלא את הרוחב המוקצה. באג מוכר בTable Layout עם column יחיד.

**העדות:** PDF v3.7 מציג photo כ-1100×715 ב-140 DPI = **20cm רוחב** על A4. אם CSS היה תקף, היה צריך להיות 5cm (30% של ~17cm רוחב תוכן).

---

## התיקון

קובץ: `backend/templates/handover_protocol_pdf.html`

**העבר את ה-width מ-`.cell` ל-`.photo-row` עצמו.**

מצא את הבלוק (שורות 1005-1022):

```css
.photo-row {
  display: table;
  width: 100%;
  border-spacing: 6px 0;
  margin-top: 8px;
  table-layout: fixed;
}
.photo-row .cell {
  display: table-cell;
  vertical-align: top;
  padding: 0 4px;
}
.photo-row.count-1 .cell { width: 30%; }
.photo-row.count-2 .cell { width: 30%; }
.photo-row.count-3 .cell { width: 30%; }
.photo-row.count-4 .cell { width: 24%; }
.photo-row.count-5 .cell { width: 19%; }
.photo-row.count-6 .cell { width: 16%; }
```

החלף ל:

```css
.photo-row {
  display: table;
  border-spacing: 6px 0;
  margin-top: 8px;
  table-layout: fixed;
}
.photo-row .cell {
  display: table-cell;
  vertical-align: top;
  padding: 0 4px;
}
.photo-row.count-1 { width: 30%; }
.photo-row.count-2 { width: 60%; }
.photo-row.count-3 { width: 90%; }
.photo-row.count-4 { width: 96%; }
.photo-row.count-5 { width: 95%; }
.photo-row.count-6 { width: 96%; }
```

### מה השתנה

1. **הוסר `width: 100%` מ-`.photo-row`.** הtable כבר לא נמתח כברירת מחדל.
2. **הוסר `width:` מ-`.photo-row .cell`.** הcells חולקים שווה את רוחב הrow (per CSS table layout).
3. **נוסף `width:` ל-`.photo-row.count-N`.** עכשיו הrow כולו הוא ברוחב הנכון, וה-cells שלו חולקים את הרוחב הזה.

### התוצאה החישובית

A4 רוחב תוכן ≈ 17cm:
- count-1 (30%): row 5.1cm, 1 cell × 5.1cm = **5.1cm photo** ✓
- count-2 (60%): row 10.2cm, 2 cells × 5.1cm = **5.1cm כל photo** ✓
- count-3 (90%): row 15.3cm, 3 cells × 5.1cm = **5.1cm כל photo** ✓
- count-4 (96%): row 16.3cm, 4 cells × 4.1cm = **4.1cm כל photo** ✓
- count-5 (95%): row 16.2cm, 5 cells × 3.2cm = **3.2cm כל photo** ✓
- count-6 (96%): row 16.3cm, 6 cells × 2.7cm = **2.7cm כל photo** ✓

כל התמונות יהיו ברוחב אחיד ~5cm (פרט ל-4+ שצריך להיות צפוף יותר). סגנון Cemento מושג.

---

## VERIFY

לאחר deploy:

- [ ] `pdfimages -list staging.pdf` → defect photos עם DPI גבוה (~250+) במקום 140
- [ ] חישוב: 1100px / DPI ≈ 1.5-2 inch = 4-5cm רוחב
- [ ] בPDF: ליקוי עם 1 תמונה → ה-cell + photo בולטים בצד ימין (RTL), שאר השורה ריקה
- [ ] ליקוי עם 2 תמונות → 2 cells בצד ימין, שאר השורה ריקה
- [ ] לא רואים אבל אם תרצה לוודא שאין overflow: כל row לא יוצא מגבולות הדף

---

## DO NOT

- אל תיגע בJinja loop (כבר משתמש ב-`count-{{ _count }}` נכון)
- אל תיגע ב-`.photo` CSS (background-image וכו' עובד)
- אל תיגע ב-`.meter .photo`
- אל תיגע ב-Photo diag, page_header macro, room-block, או כל carry-over

---

## Standing rule

Replit עורך קבצים בלבד. אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
handover-pdf v3.7.1 hotfix: move photo-row width from .cell to .photo-row

v3.7 set width: 30% on .photo-row .cell but WeasyPrint ignored it because
the parent .photo-row was display:table with width:100%, and a single
cell in a 100%-wide table gets stretched to fill the table.

Fix: remove width:100% from .photo-row, drop the per-cell widths, and
put the modifier widths on .photo-row.count-N (the table itself):
  count-1: 30% / count-2: 60% / count-3: 90%
  count-4: 96% / count-5: 95% / count-6: 96%

Cells now share the row width equally — each photo is ~5cm wide on A4
regardless of count, matching the Cemento-style miniature design.
```

מצופה זמן: 5 דקות. שינוי מכני ב-CSS אחד.
