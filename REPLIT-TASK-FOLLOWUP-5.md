# REPLIT FOLLOWUP #5 — איכות תמונות + חתימות נסחים + עמ' 5 ריק

> 3 תיקונים אחרי סקירת PDF v3.4 בstaging:
>
> 1. **תמונות גדולות מדי + מטושטשות** — 1 תמונה ב-65% רוחב היא דומיננטית מדי, וגם המקור (600px) קטן מדי כדי להיראות חד בגודל הגדול. 76 dpi בפועל = blur בהדפסה.
> 2. **חתימות בנסחים משפטיים לא מופיעות** — בUI החתימות מוצגות (canvas strokes), אבל בPDF רואים רק סימן ירוק + שם + תאריך. ה-image_b64 נטען בservice אבל הtemplate לא מציג אותו.
> 3. **עמ' 5 ריק** — page-label "ROOM INSPECTIONS · בדיקת חדרים" נשאר לבד בעמ' 5 כי הroom הראשון (כניסה לדירה) דרש העתקה לעמ' 6 בגלל `no-break`.

---

## תיקון 1 — איכות תמונות + רוחב נכון

### חלק A — CSS: שינוי רוחב תאים ל-1 תמונה

קובץ: `backend/templates/handover_protocol_pdf.html`

מצא את הבלוק שהוסף בv3.4:
```css
.photo-row.count-1 .cell { width: 65%; }
.photo-row.count-2 .cell { width: 50%; }
.photo-row.count-3 .cell { width: 33.33%; }
```

החלף ל:
```css
.photo-row.count-1 .cell { width: 50%; }
.photo-row.count-2 .cell { width: 50%; }
.photo-row.count-3 .cell { width: 33.33%; }
```

**הסבר:** 1 תמונה ב-50% (לא 65%) משאירה אותה בגודל סביר על הדף, מתאים גם להדפסה A4. המשתמש כתב במפורש: "מקסימום 2 תמונות ביחד באותו הדף".

### חלק B — Service: בעיית רזולוציה במקור

קובץ: `backend/services/handover_pdf_service.py`

מצא את שורה 44-45:
```python
_DEFECT_PHOTO_WIDTH = 600
_DEFECT_PHOTO_QUALITY = 75
```

החלף ל:
```python
_DEFECT_PHOTO_WIDTH = 1100
_DEFECT_PHOTO_QUALITY = 85
```

**הסבר:**
- כיום: תמונה 600px נמתחת ל-12-15cm רוחב ב-A4 = ~76 DPI = מטושטש
- אחרי: 1100px = ~150 DPI = חד וברור גם בהדפסה
- Quality 85 (במקום 75) = פחות artifact JPEG = איכות חד טוב יותר

**Trade-off:** קובץ ה-PDF יגדל מ-235KB ל-~500-800KB (תלוי במספר התמונות). זה עדיין גדל בטוח לקריאה ולשליחה.

---

## תיקון 2 — חתימות בנסחים משפטיים

### האבחנה

ב-`backend/services/handover_pdf_service.py` שורות 604-648, השירות בונה `legal_sections` עם list של `signers`, וכל signer מקבל `sig_image_b64`. **המידע מגיע לtemplate.**

אבל ב-`backend/templates/handover_protocol_pdf.html` שורות 1474-1488, הtemplate רק מציג sigchip עם טקסט (שם + ת״ז + תאריך) — **בלי `<img>` של החתימה.**

### התיקון

קובץ: `backend/templates/handover_protocol_pdf.html`

מצא את הבלוק (בערך שורה 1474-1488):

```jinja
<div class="legal-sigline">
  {% if ls.signers %}
    {% for s in ls.signers %}
      {%- set _s_name = s.signer_name or s.typed_name or s.label or 'חתום' -%}
      {%- set _tnt = (tenants|default([]))|selectattr('name','equalto', _s_name)|list -%}
      {%- set _s_id = (s.id_number if s.id_number is defined else '') or (_tnt[0].id_number if _tnt else '') -%}
    <span class="sigchip"><span class="check">...</span>{{ _s_name }} · ת״ז {{ _s_id or '—' }} · {{ signed_date or s.signed_at or '—' }}</span>
    {% endfor %}
  {% else %}
    <span class="sigchip unsigned">ממתין לחתימה</span>
  {% endif %}
</div>
```

החלף ל:

```jinja
<div class="legal-sigline">
  {% if ls.signers %}
    {% for s in ls.signers %}
      {%- set _s_name = s.signer_name or s.typed_name or s.label or 'חתום' -%}
      {%- set _tnt = (tenants|default([]))|selectattr('name','equalto', _s_name)|list -%}
      {%- set _s_id = (s.id_number if s.id_number is defined else '') or (_tnt[0].id_number if _tnt else '') -%}
      <div class="legal-signer">
        <span class="sigchip"><span class="check"><svg width="8" height="8" viewBox="0 0 8 8" xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle"><polyline points="1.5,4.2 3.4,6 6.5,2.2" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></span>{{ _s_name }} · ת״ז {{ _s_id or '—' }} · {{ signed_date or s.signed_at or '—' }}</span>
        {% if s.sig_type == 'canvas' and s.sig_image_b64 %}
          <div class="legal-sig-img"><img src="{{ s.sig_image_b64 }}" alt="חתימה"></div>
        {% elif s.sig_type == 'typed' and s.typed_name %}
          <div class="legal-sig-typed">{{ s.typed_name }}</div>
        {% endif %}
      </div>
    {% endfor %}
  {% else %}
    <span class="sigchip unsigned">ממתין לחתימה</span>
  {% endif %}
</div>
```

**הוסף לCSS** (בסוף הbloc של `.legal-block`, סמוך לשורה 770):

```css
.legal-signer {
  display: block;
  margin-bottom: 12px;
}
.legal-sig-img {
  margin-top: 6px;
  max-width: 200px;
}
.legal-sig-img img {
  max-width: 100%;
  max-height: 60px;
  display: block;
}
.legal-sig-typed {
  margin-top: 6px;
  font-family: 'Caveat', cursive;
  font-size: 22px;
  color: var(--ink);
}
```

**מה זה עושה:** עבור כל signer, מציג sigchip + מתחתיו (אם canvas) IMG עם הציור של החתימה (max 60px גובה כדי לא לתפוס יותר מדי מקום), או (אם typed) טקסט בפונט Caveat.

---

## תיקון 3 — עמ' 5 ריק (orphaned page-label)

### האבחנה

עמ' 5 בPDF הנוכחי מכיל רק:
- Header strip ("5 · 30.04.2026")  
- page-label "ROOM INSPECTIONS · בדיקת חדרים"

**זהו.** ה-room הראשון ("כניסה לדירה") עבר לעמ' 6 כי הוא עטוף ב-`<div class="no-break">` ולא נכנס בעמ' 5.

תוצאה: page-label יושב לבד = עמ' מבוזבז.

### התיקון

קובץ: `backend/templates/handover_protocol_pdf.html`

מצא את ה-page-label של ROOM INSPECTIONS (בערך שורה 1305):
```jinja
<div class="page-label">ROOM INSPECTIONS · בדיקת חדרים</div>
```

הוסף לו class נוסף:
```jinja
<div class="page-label keep-with-next">ROOM INSPECTIONS · בדיקת חדרים</div>
```

**הוסף לCSS:**
```css
.keep-with-next {
  page-break-after: avoid;
  break-after: avoid;
}
```

**מה זה עושה:** WeasyPrint יידע שאסור לשבור עמ' אחרי ה-page-label. אם ה-room הראשון לא נכנס באותו עמ' — page-label יזוז יחד איתו לעמ' הבא. אין יותר orphaned label.

**הערה:** WeasyPrint מאז גרסה 53 תומך ב-`page-break-after: avoid`. אם הproduction דורש גרסה ישנה ולא עובד, fallback: לעטוף page-label + first room ב-`no-break` div גלובלי.

---

## VERIFY checklist

לאחר deploy:

**תיקון 1 (תמונות):**
- [ ] ליקוי עם 1 תמונה → התמונה ב-50% רוחב (לא 65%) — ממורכזת
- [ ] התמונה חדה וקריאה גם בהדפסה (PPI ב-`pdfimages -list` צריך להיות ~150, לא 76)
- [ ] גודל הקובץ עלה ל-500-800KB (סביר)

**תיקון 2 (חתימות):**
- [ ] בעמ' "נסחים משפטיים" — לכל signer יש לא רק טקסט אלא גם החתימה הצויירה (canvas)
- [ ] אם המשתמש בחר "typed" → הטקסט מופיע בפונט Caveat

**תיקון 3 (עמ' 5):**
- [ ] אין יותר עמ' שמכיל רק page-label
- [ ] ROOM INSPECTIONS header והroom הראשון מופיעים יחד באותו עמ'

---

## DO NOT

- אל תיגע בPhoto diag logging (עוזר לאבחן)
- אל תיגע ב-`.meter .photo` 
- אל תיגע במקרא של `_str_val` (מתיקון Excel import — נושא נפרד)
- אל תוסיף עוד forced page-breaks. רק `page-break-after: avoid` ו-`break-after: avoid`.

---

## Standing rule

Replit עורך קבצים בלבד. **לא commit, לא push, לא deploy.**

אחרי Build → אני (Zahi) אריץ `./deploy.sh --stag` ב-Shell של Replit. אחרי אימות → `./deploy.sh --prod`.

---

## Commit message מומלץ

```
handover-pdf v3.5: photo quality + legal signatures + orphan page-label fix

Fix #1 (photo size & quality):
  - 1-photo cell width: 65% → 50% (less dominant)
  - _DEFECT_PHOTO_WIDTH: 600 → 1100 (sharper at print size)
  - _DEFECT_PHOTO_QUALITY: 75 → 85 (less JPEG artifact)
  Result: 76 DPI → ~150 DPI defect photos.

Fix #2 (legal section signatures):
  Render the canvas signature image inside legal_sigline. The
  service was already loading sig_image_b64 into ls.signers[*]
  but the template only displayed name+date. Added <img> for
  canvas type and <Caveat> typed name for typed type.

Fix #3 (orphan page-label on empty page 5):
  Add page-break-after: avoid to .page-label.keep-with-next so
  the "ROOM INSPECTIONS" header stays glued to the first room
  card. No more empty pages with just a header strip.
```

מצופה זמן: 30 דקות. שני קבצים, שלושה שינויים מכניים.
