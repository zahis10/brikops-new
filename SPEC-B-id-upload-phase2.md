# SPEC B — תמונות ת.ז של דיירים (Phase 2)

> **לא חלק מהמשימה הנוכחית.** ספק זה נשמר ל-batch הבא, אחרי שה-template החדש (Spec A / REPLIT-TASK.txt) ייכנס לפרודקשן ויתייצב.
>
> **מטרה:** הפיכת ה-ID Appendix ב-PDF (עמ' 10) ואת ה-thumbnails ב-Cover (עמ' 1) מ-placeholders לתמונות אמיתיות שמועלות באפליקציה.

---

## מתי להתחיל את הספק הזה

✓ אחרי ש-Spec A (ה-template החדש) ב-production לפחות שבוע  
✓ אחרי שיש בקשה אקטיבית מקבלן/יזם להעלות ת.ז (לא לעשות בלי trigger)  
✓ אחרי דיון על privacy/legal (העלאת מסמכי ת.ז למערכת = הקשחת רגולציה)

---

## עיקרון מנחה — מקור אמת אחד (לא לסטות!)

**שני המיקומים בעיצוב חייבים לקרוא מאותו השדה ב-DB.**

- מעלים בעמ' 1 → תמונה גדולה מופיעה גם בעמ' 10
- מעלים בעמ' 10 → thumbnail מופיע גם בעמ' 1
- מחליפים → מתעדכן בשני המקומות מיד
- מוחקים → נעלם משני המקומות

**אסור** ליצור שני שדות נפרדים (`thumbnail_url` + `large_url`). השדה ב-DB הוא `tenant.id_card_image_front_url` (URL אחד) + `tenant.id_card_image_back_url` (URL אחד). הטמפלייט פשוט משתמש ב-CSS `background-size: cover` כדי להתאים את אותה תמונה לגדלים שונים.

---

## משימה — 3 חלקים שמשתחררים יחד

חשוב: **אל תעשה רק חלק אחד.** הם תלויים זה בזה. אם תוסיף DB fields בלי UI → dead fields. אם תוסיף UI בלי service rendering → תמונות עולות אבל לא מופיעות ב-PDF. **שחרר את כל ה-3 ב-PR אחד.**

### חלק א — Backend Model

ב-`backend/models.py` (חפש `class Tenant`/`TenantCreate`):

```python
id_card_image_front_url: Optional[str] = None
id_card_image_back_url: Optional[str] = None
```

### חלק ב — Backend Service (PDF render)

ב-`backend/services/handover_pdf_service.py` — הוסף לטעינת התמונות. **חשוב: max_width=1200** כדי שהן יישארו קריאות לבית משפט (ת"ז = ראיה משפטית), ועם compression טוב כדי לא לפוצץ את גודל ה-PDF:

```python
tenant.id_card_image_front_b64 = await _fetch_image_as_base64(
    tenant.get('id_card_image_front_url'), session, max_width=1200, jpeg_quality=80
)
tenant.id_card_image_back_b64 = await _fetch_image_as_base64(
    tenant.get('id_card_image_back_url'), session, max_width=1200, jpeg_quality=80
)
```

(אם `_fetch_image_as_base64` לא תומך ב-`jpeg_quality` כפרמטר — להוסיף אותו במסגרת ה-batch הזה.)

### חלק ג — Backend Endpoint (העלאה)

חדש: `POST /api/handover/{protocol_id}/tenants/{tenant_id}/id-card`

- Multipart upload, validates JPEG/PNG only, max 8MB raw upload
- שומר ל-object storage (כבר קיים: `services/object_storage.py`)
- מחזיר URL חתום (signed URL)
- Body param: `side` = `"front"` או `"back"` כדי לדעת לאיזה שדה לכתוב
- חובה: רק משתמשים מורשים (project_manager, או הדייר עצמו אם יש לו account) יכולים להעלות
- חובה: `audit_log` של פעולת העלאה/מחיקה (PII tracking)

### חלק ד — Frontend UI

ב-`frontend/src/components/handover/HandoverTenantForm.js`:

- כל דייר מקבל **2 שדות upload**: "צילום ת.ז קדמי" + "צילום ת.ז אחורי"
- Preview של thumbnail מיד אחרי העלאה (160×100 lookup)
- Validation: JPEG/PNG, מקסימום 8MB raw
- אופציה למחוק/להחליף
- אינדיקטור ברור (warning badge ב-tenant card) אם ת.ז עוד לא הועלתה
- Soft warning (לא block) כשמנסים לסגור פרוטוקול ללא תמונות

**חובה:** רק נקודת העלאה אחת ב-UI לכל דייר. השדות נשמרים פעם אחת, מוצגים פעמיים ב-PDF.

### חלק ה — Template (Jinja)

ב-`backend/templates/handover_protocol_pdf.html` — שני המקומות:

**Cover (עמ' 1) — thumbnail:**
```html
<div class="tenant-id-photos">
  {% if tenant.id_card_image_front_b64 %}
    <div class="id-photo has-image" style="background-image: url('{{ tenant.id_card_image_front_b64 }}'); background-size: cover; background-position: center;">
      <span class="lbl">ת.ז · קדמי</span>
    </div>
  {% else %}
    <div class="id-photo"><span class="lbl">ת.ז · קדמי</span></div>
  {% endif %}
  {# חזור על אותו דבר ל-back #}
</div>
```

**ID Appendix (עמ' 10) — large:**
```html
<div class="id-card-large {% if tenant.id_card_image_front_b64 %}has-image{% endif %}"
     {% if tenant.id_card_image_front_b64 %}style="background-image: url('{{ tenant.id_card_image_front_b64 }}');"{% endif %}>
  <div class="id-image"></div>
  <div class="id-caption">
    <span>תעודת זהות</span>
    <span class="side-label">FRONT · קדמי</span>
  </div>
</div>
```

**שים לב:** **אותו** `tenant.id_card_image_front_b64` משמש בשני המקומות. CSS עושה את ה-resize עם `background-size: cover`. רינדור אחד, שדה אחד, שני displays.

---

## VERIFY checklist (חובה לפני merge)

תרחיש Single-Source:
- [ ] Upload תמונת קדמי בUI → generate PDF → תמונה מופיעה גם ב-cover thumbnail וגם ב-Appendix large
- [ ] Replace תמונת קדמי → generate PDF חדש → התמונה החדשה מופיעה בשני המקומות
- [ ] Delete תמונת קדמי → generate PDF חדש → placeholder חוזר בשני המקומות
- [ ] Upload front-only (לא back) → cover מציג קדמי-אמיתי + אחורי-placeholder, Appendix אותו דבר

תרחיש קריאות:
- [ ] תמונת ת.ז ב-Appendix קריאה — מספר ת.ז ברור, פנים ניתנות לזיהוי, תאריך תוקף נראה
- [ ] גודל הקובץ הסופי < 16MB גם עם 2 תעודות זהות + 30 ליקויים עם תמונות

תרחיש privacy:
- [ ] רק משתמשים מורשים יכולים להעלות (לא ציבורי!)
- [ ] audit log רושם כל פעולת העלאה/מחיקה
- [ ] לא נחשפים ה-URLs בלוגים או error messages

---

## DO NOT

- אל תיצור שדות `_thumbnail_url` ו-`_large_url` נפרדים — שדה אחד פר תמונה
- אל תאחסן את התמונה ב-base64 ב-DB (רק URL)
- אל תאפשר העלאה ציבורית — רק authenticated
- אל תשכח את ה-`audit_log` — ת"ז זה PII, יש חשיבות לעקוב

---

**תוצרים סופיים:**
- 1 PR יחיד שמשחרר את כל ה-5 חלקים יחד
- CHANGELOG ב-PR description
- Screenshots של tenant form עם תמונה מועלית + PDF שיצא
