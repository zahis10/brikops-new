# REPLIT FOLLOWUP #3 — אבחנה מלאה: שני באגים שונים, שני תיקונים נפרדים

> **Context:** ה-PR הקודם (`7bb28e2`) הסיר את 5 ה-`text-transform: uppercase` והוסיף Photo diag.
>
> **חדשות טובות מהLogs:**
> - הDiagnostic נורה — **כל התמונות נטענות בהצלחה** (`fetched_truthy=1/1` עבור כל פריט defective עם תמונה)
> - הdata layer **תקין לחלוטין**.
>
> **חדשות רעות מהPDF:**
> 1. **הג׳יבריש עדיין שם** — אבל זה לא היה text-transform. זה font חסר.
> 2. **התמונות קיימות בPDF** (`pdfimages` מאשר 3 jpegים מוטמעים) — אבל לא **מוצגות** באלמנטי `.photo`.
>
> שני הבאגים הם שני בעיות נפרדות שדורשות שני תיקונים שונים.

---

## אבחנה — Bug 1: Hebrew gibberish (אמיתי, לא text-transform)

### העדויות

קובץ: `backend/fonts/Rubik-Bold.ttf` (47KB, סטטי)
בדיקה ב-`fontTools`:
```
Latin lowercase a-z: 26/26 ✓
Latin uppercase A-Z: 26/26 ✓
Hebrew letters: 0/27 ❌❌❌
Total glyphs: 221
```

קובץ: `backend/fonts/Rubik-Regular.ttf` (359KB, **משתנה**, ציר wght=300-900)
```
Latin lowercase a-z: 26/26 ✓
Latin uppercase A-Z: 26/26 ✓
Hebrew letters: 27/27 ✓
Total glyphs: 885
```

### מה קורה ב-WeasyPrint

הCSS מכיל:
```css
@font-face { font-family: 'Rubik'; font-weight: 400; src: Rubik-Regular.ttf; }
@font-face { font-family: 'Rubik'; font-weight: 700; src: Rubik-Bold.ttf; }

.cover-eyebrow { font-weight: 600; ... }   /* "Handover Protocol · פרוטוקול מסירה" */
.cover-sub     { font-weight: 500; ... }
.cover-title   { font-weight: 800; ... }
```

WeasyPrint מקבל בקשה לרנדר טקסט בweight 600. הוא:
1. בוחר Rubik @ 700 (קרוב יותר מ-400)
2. עבור עברית — Rubik-Bold.ttf אין לו Hebrew → fallback ל-Rubik-Regular (variable) instanced ב-700
3. עבור Latin lowercase — אמור להשתמש ב-Rubik-Bold.ttf, אבל בפועל משתמש ב**variable instance** של Rubik-Regular @ 700
4. ה-subset של ה-variable instance מכיל רק תווים שכבר נוצרו עבורו (uppercase Latin + Hebrew + ספרות) — **בלי lowercase Latin**
5. כשהוא מנסה לרנדר את "andover" lowercase → ה-glyph mapping שבור → תוצאה: `AOĻŠŇŜŴÒÜ! ÚŜÛŜŅŜŜ` (Latin Extended chars שכן יש ב-subset)

### עדות מהפלט של pdfminer (extracted from latest staging PDF)

```
Text:  'הריסמ לוקוטורפ · Handover Protocol'  (cover-eyebrow)
Hebrew chars  → IRKPGT+Rubik (variable, weight ~400)  ✓ נכון
Latin chars   → IEUYIT+Rubik-Bold ❌ אבל ה-glyphs רנדרו כג׳יבריש
```

ועדות מ-fontTools subset log:
```
Restricted limits: {'wght': (700, 700, 700)}
Glyph names: ['.notdef', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'L', 'M', 'N', 'O', 'P', 'R', 'S', 'T', 'U', 'V', 'Y', 'hyphen', 'one', 'periodcentered', 'space', 'two', 'zero']
```

**אין lowercase בsubset.** זה מאשר את הבאג.

### התיקון — Bug 1

**אופציה A (מומלצת, פשוטה):** Use the variable font for ALL weights, מחק את `Rubik-Bold.ttf`.

ב-`backend/templates/handover_protocol_pdf.html`, החלף את שני הצהרות ה-@font-face ל:

```css
@font-face {
  font-family: 'Rubik';
  src: url('file://{{ fonts_dir }}/Rubik-Regular.ttf') format('truetype-variations');
  font-weight: 300 900;  /* range — covers all weights */
  font-style: normal;
}
```

ומחק את הקובץ `backend/fonts/Rubik-Bold.ttf` (לא בשימוש יותר).

**למה זה יעבוד:** הvariable font מכיל את כל הglyphs (Latin lowercase, uppercase, Hebrew). WeasyPrint יוצר subsets ממנו לכל weight בנפרד, וכל subset יקבל את הglyphs הנדרשים — כולל lowercase Latin עבור "Handover Protocol".

**אופציה B (אם A לא עובד):** הורד גרסה חדשה של Rubik-Bold.ttf שכוללת Hebrew. מ-Google Fonts:
```bash
# דוגמה
curl -L 'https://fonts.gstatic.com/s/rubik/v36/iJWZBXyIfDnIV5PNhY1KTN7Z-Yh-WYi1UA.ttf' -o backend/fonts/Rubik-Bold.ttf
```
ואז וודא ש-`fontTools` מאשר Hebrew letters: `27/27`.

**אופציה אחרי הבחירה:** רוץ verify:
```python
from fontTools.ttLib import TTFont
f = TTFont('backend/fonts/Rubik-Bold.ttf')  # אם השארת את הקובץ
cmap = f.getBestCmap()
hebrew = sum(1 for cp in range(0x05D0, 0x05EB) if cp in cmap)
print(f"Hebrew: {hebrew}/27")  # חייב להיות 27/27
```

---

## אבחנה — Bug 2: Photos לא מוצגות בdefect-cards

### העדויות

מהLogs (אבחנה שאתה הוספת):
```
[PDF] Photo diag: section='כניסה לדירה' item='משקוף' ...
  status=defective item.photos_count=1 defect.proof_urls_count=1
  photo_keys=['photo_0'] fetched_truthy=1/1   ✓ TRUTHY!
```
→ data flow תקין. התמונות נשלפות מ-S3 בהצלחה.

מ-`pdfimages -list latest.pdf`:
```
page  num  type   width height
   6    0  image  600    390   ← תמונה של משקוף
   7    1  image  600    390   ← תמונה של דלת כניסה
   8    2  image  600    390   ← תמונה של טיח
```
→ התמונות **כן מוטמעות בPDF**. הן רק לא מוצגות בקווים של ה-`.photo`.

מ-rendered PDF (cropped):
- ה-cell הראשון (right) של כל defect-card נראה כ-`.photo` (solid bg, no dashed border) — אבל **ריק** מתמונה
- שני ה-cells האחרים נראים כ-`.photo-empty` (dashed border) — מצופה

### הבעיה הטכנית

הCSS הנוכחי:
```css
.photo {
  display: block;
  position: relative;
  padding-bottom: 75%;   /* aspect-ratio trick */
  ...
}
.photo img {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: cover;     /* ← BAD: WeasyPrint תמיכה חלקית ב-object-fit */
  display: block;
}
```

WeasyPrint:
- מטמיע את התמונה בPDF (אנחנו רואים ב-pdfimages)
- אבל `object-fit: cover` או הקומבינציה של absolute+inset+padding-bottom-% לא רנדרת נכון
- התוצאה: התמונה ב-PDF object table אבל לא מוצגת בoutput

### התיקון — Bug 2

החלף את ה-`<img>` ב-**background-image**. WeasyPrint תומך ב-`background-size: cover` בצורה אמינה.

ב-`backend/templates/handover_protocol_pdf.html`, **שינוי 1 — לCSS** (שורה 970-997):

```css
.photo {
  display: block;
  width: 100%;
  height: 0;
  padding-bottom: 75%;     /* aspect ratio */
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--paper);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  border: 1px solid var(--slate-2);
}
/* מחק את כל הבלוק .photo img — לא נחוץ יותר */
```

**שינוי 2 — לtemplate** (שורה ~1389, בתוך `photo-row`):

```jinja
<div class="photo-row">
  {%- set _ph = (it.photos or [])|list -%}
  {% for i in range(3) %}
    <div class="cell">
      {%- set p = _ph[i] if i < _ph|length else None -%}
      {% if p %}
        <div class="photo" style="background-image: url('{{ p }}');"></div>
      {% else %}
        <div class="photo-empty"></div>
      {% endif %}
    </div>
  {% endfor %}
</div>
```

(שינוי: `<div class="photo"><img src="{{ p }}" alt=""></div>` → `<div class="photo" style="background-image: url('{{ p }}');"></div>`)

**שיקול אבטחה:** `{{ p }}` הוא data URL מ-base64 שאנחנו יצרנו בעצמנו. בטוח להזריק לCSS inline. autoescape של Jinja לא ישפיע.

**הערה — meter photos:** ה-`.meter .photo` כן עובד היום. אם תרצה להאחיד, אפשר להחיל את אותו תיקון גם שם. אבל לא חובה — אם meter photos עובדים, אל תיגע בהם.

---

## VERIFY checklist

לאחר deploy ל-staging, צור פרוטוקול אמיתי, העלה תמונה אמיתית ל-defect, generate PDF:

**Bug 1 — Hebrew:**
- [ ] ב-cover עמ' 1, הטקסט הכתום מעל "פרוטוקול מסירה סופי" קריא: "Handover Protocol · פרוטוקול מסירה" (לא ג׳יבריש)
- [ ] `pdftotext latest.pdf` מציג טקסט תקין בעברית
- [ ] `pdffonts latest.pdf` לא מכיל DejaVu-Sans-Bold (אם בחרת אופציה A)

**Bug 2 — Photos:**
- [ ] בdefect-card שיש לו תמונה, ה-cell הראשון מציג את התמונה (לא ריק)
- [ ] ל-cells בלי תמונה — placeholder עם "תמונה לא זמינה" מוצג כרגיל
- [ ] `pdfimages -list latest.pdf` ממשיך להראות את התמונות (וודא שלא מחקנו אותן בטעות)

**Diagnostic logging:**
- [ ] הLogs ב-`[PDF] Photo diag` ממשיכים להופיע (השאר את הbblock)

---

## הערות חשובות

1. **Standing rule:** Replit לא מבצע `git commit`, לא מבצע `git push`, לא מבצע deploy. רק עורך קבצים ויוצר review.txt.
2. **2 commits:**
   - Commit A: `handover-pdf: use variable Rubik font for all weights (Hebrew gibberish fix #3)`
   - Commit B: `handover-pdf: use background-image instead of <img> for defect photos (object-fit fix)`
3. **לפני merge** — וודא ש`grep -n "<img" backend/templates/handover_protocol_pdf.html` לא מציג תמונות במקומות שאמורים להיות background-image.

---

## DO NOT

- אל תיגע בdiagnostic logging — הוא עובד מצוין ועוזר לאבחן
- אל תיגע ב`.meter .photo` (הוא לא מתקלקל היום)
- אל תיגע ב-`Rubik-Regular.ttf` — זה הvariable font הטוב

---

מצופה זמן: 30-45 דקות עבודה. שני שינויים פשוטים אבל מדויקים.
