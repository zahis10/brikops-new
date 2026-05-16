# SPEC — Handover PDF Template v3 (Jinja conversion of v2.2 design)

> **TL;DR:** קח את העיצוב של `BrikOps Handover Protocol v2.2.html` (המוקאפ הסטטי שאנחנו אישרנו), המר אותו ל-Jinja template, **חבר אותו ל-64 המשתנים שכבר קיימים** ב-`backend/services/handover_pdf_service.py`. אסור לגעת ב-schema של ה-DB. אסור להוסיף שדות חדשים. רק להחליף את ה-PDF שיוצא מהמערכת בעיצוב המודרני.

---

## 1. קבצים

| קובץ | תפקיד |
|---|---|
| `BrikOps Handover Protocol v2.2.html` (workspace root) | **מקור עיצובי** — קח את ה-template החדש מתוך ה-bundler |
| `backend/templates/handover_protocol_pdf.html` (883 שורות) | **יעד** — להחליף לחלוטין בעיצוב החדש |
| `backend/services/handover_pdf_service.py` | **לא לגעת.** הוא מספק את 64 המשתנים |
| `backend/contractor_ops/handover_router.py` | **לא לגעת.** מקור אמת ל-rooms/items/trades |

---

## 2. עקרונות-על

1. **שמור על העיצוב של v2.2.** Cover Hero כהה + סטטס פאנל + severity bars + defect cards + signature grid + legal blocks — אסור לשנות.
2. **שמור על ה-schema של ה-DB.** אל תוסיף, אל תוריד, אל תשנה שדות. אם משהו בעיצוב לא תואם — תקן את העיצוב, לא את ה-DB.
3. **כל hardcoded data במוקאפ → Jinja variable.** רשימת המשתנים בסעיף 4 למטה.
4. **תמיכה ב-`@media print` ו-WeasyPrint.** ה-PDF מיוצר עם WeasyPrint דרך השירות הקיים.

---

## 3. 5 התאמות סכמה — חובה לפני המרה ל-Jinja

### א. להחזיר 11 trade classes (לא 8)

המוקאפ v2.2 איחד trades. **בטל את האיחוד** וחזור ל-11 הנפרדים שהמערכת תומכת בהם:

| class | תווית | רקע / טקסט |
|---|---|---|
| `elec` | חשמל | `#FEF3C7` / `#92400E` |
| `plumb` | אינסטלציה | `#DBEAFE` / `#1E40AF` |
| `tile` | ריצוף | `#E0E7FF` / `#3730A3` |
| `alum` | אלומיניום | `#CFFAFE` / `#155E75` |
| `door` | דלתות | `#DCFCE7` / `#14532D` |
| `iron` | ברזל | `#E2E8F0` / `#334155` |
| `paint` | צביעה | `#FCE7F3` / `#9D174D` |
| `plast` | טיח | `#FAE8FF` / `#6B21A8` |
| `kitch` | מטבחים | `#FFEDD5` / `#9A3412` |
| `marble` | שיש | `#F5F5F4` / `#44403C` (חדש — היה בתוך kitch) |
| `gen` | כללי | `--slate-1` / `--slate-7` |

מחק את המחלקות `frame` ו-`finish` שהוספתי בv2.1 — הן שגויות.

מיפוי מ-trade בעברית (כפי שבא מה-DB) ל-class:
```
{% set trade_class = {
  'חשמל': 'elec', 'אינסטלציה': 'plumb', 'ריצוף': 'tile',
  'אלומיניום': 'alum', 'דלתות': 'door', 'ברזל': 'iron',
  'צביעה': 'paint', 'טיח': 'plast', 'מטבחים': 'kitch',
  'שיש': 'marble', 'כללי': 'gen'
}.get(item.trade, 'gen') %}
```

### ב. להוסיף 2 status states שחסרים

המוקאפ יש 3 (`ok / part / bad`). המערכת יש 5. הוסף:

```html
<span class="status not-relevant"><span class="d"></span>לא רלוונטי</span>
<span class="status not-checked"><span class="d"></span>לא נבדק</span>
```

CSS:
```css
.status.not-relevant   { background: var(--slate-1); color: var(--slate-5); }
.status.not-relevant .d { background: var(--slate-3); }
.status.not-checked    { background: white; color: var(--slate-5); border: 1px dashed var(--slate-3); }
.status.not-checked .d  { background: transparent; border: 1px solid var(--slate-3); }
```

ושנה את שמות ה-classes הקיימים: `part` → `partial`, `bad` → `defective` (להתאים ל-DB).

מיפוי:
```
{% set status_class = {
  'ok': 'ok', 'partial': 'partial', 'defective': 'defective',
  'not_relevant': 'not-relevant', 'not_checked': 'not-checked'
}.get(item.status, 'not-checked') %}
```

### ג. להוריד מונה גז

הקובץ יש 3 קלפי מונה (מים/חשמל/גז). **המערכת תומכת רק ב-2.** הסר את `.meter.gas` HTML+CSS. שנה את ה-grid מ-3 עמודות ל-2:

```css
.meters { grid-template-columns: repeat(2, 1fr); }
```

### ד. שנה את רשימת ה-rooms ב-TOC

ה-TOC במוקאפ סטטי. הפוך אותו ל-`{% for section in sections %}` שירוץ על המשתנה `sections` הקיים. אורך: בדרך כלל 15 חדרים, אבל אם ה-template של הארגון שונה — זה ידאג לעצמו.

```html
<div class="toc">
  {% for section in sections %}
    <div class="toc-item {% if section.fail == 0 %}clean{% endif %}">
      <span class="name">
        {{ section.name }}
        {% if section.fail > 0 %}<span class="badge">{{ section.fail }}</span>{% endif %}
      </span>
      <span class="pg">עמ׳ {{ loop.index + 2 }}</span>
    </div>
  {% endfor %}
</div>
```

### ה. הרחב את `.info-card "פרטי נכס"` ל-loop של property_rows

המוקאפ יש 5 שדות hardcoded. המערכת מספקת `property_rows` — מערך של תוויות-ערך מסונן (רק שדות עם ערך). השתמש ב-loop:

```html
<div class="info-card">
  <h4><span class="dot"></span>פרטי נכס</h4>
  {% for row in property_rows %}
    <div class="kv">
      <span class="k">{{ row.label }}</span>
      <span class="v">{{ row.value }}</span>
    </div>
  {% endfor %}
</div>
```

זה מטפל אוטומטית בשטחים, דגם, חניה/מחסן ריקים, וכו'.

---

## 4. מיפוי משתנים — מוקאפ → Jinja

| במוקאפ (hardcoded) | Jinja variable | מקור |
|---|---|---|
| `BO-2026-0412-А3-12` | `{{ display_number }}` | service |
| `מתחם הסופרים · בני ברק` | `{{ project_name }}` | service |
| `בניין A` / `קומה 3` / `דירה 12` | `{{ building_name }}` / `{{ floor_name }}` / `{{ unit_name }}` | service |
| `4 באפריל 2026` (תאריך מסירה) | `{{ signed_date }}` | service (פורמט עברי) |
| `28.04.2026` (תאריך הפקה) | `{{ generation_date }}` | service |
| `145 / 140 / 2 / 3` (KPIs) | `{{ stats_total }}` / `{{ stats_ok }}` / `{{ stats_partial }}` / `{{ stats_fail }}` | service |
| `1 / 4 / 0` (severity bars) | `{{ defect_severity_counts.critical }}` / `.normal` / `.cosmetic` | service |
| `5 ליקויים פתוחים` | `{{ total_defects }}` | service |
| לוגו | `{{ brikops_logo_b64 }}` (כהה) / `{{ logo_b64 }}` (בהיר) | service |
| מים `11111111` | `{{ meter_water_reading }}` + `{{ meter_water_photo_b64 }}` | service |
| חשמל `00042` | `{{ meter_electricity_reading }}` + `{{ meter_electricity_photo_b64 }}` | service |
| `אלי אריאלי` (דייר 1) | `{% for tenant in tenants %}{{ tenant.name }}` | service |
| ת״ז / טלפון / אימייל | `{{ tenant.id_number }}` / `{{ tenant.phone }}` / `{{ tenant.email }}` | service |
| 3 בלוקים משפטיים | `{% for ls in legal_sections %}{{ ls.title }} / {{ ls.body|safe }}` | org_legal_sections |
| 4 כרטיסי חתימה | `{% for sig in signatures %}{{ sig.label }} / {{ sig.signer_name }} / {{ sig.image_b64 }}` | service |
| `הערות הדייר` (אם נוספו) | `{{ tenant_notes }}` | service |

**רשימה מלאה של 64 משתנים:** ראה את `backend/templates/handover_protocol_pdf.html` הקיים — הוא משתמש בכולם. העתק את ה-`{% for %}` patterns שכבר עובדים שם.

---

## 5. רכיבים שצריך להפוך ל-loop במוקאפ

| מקטע במוקאפ | מקור | הערה |
|---|---|---|
| TOC items (14 hardcoded) | `{% for section in sections %}` | ראה ג |
| Defects summary table (5 שורות) | `{% for d in defects %}` | משתני `d.section_name`, `d.item_name`, `d.trade`, `d.severity_label`, `d.severity_color`, `d.description` |
| Room inspection tables | `{% for section in sections %}{% for item in section.items %}` | פר חדר, פר פריט |
| Defect detail cards | `{% for d in critical_defects %}` (משתנה חדש קל לחישוב — סינון לפי severity == 'critical') |
| Tenants block (Cover) | `{% for tenant in tenants %}` | תמיד 1-3 דיירים |
| Legal blocks (3 hardcoded) | `{% for ls in legal_sections %}` | טעון פר-org מה-DB |
| Signature cards (4 hardcoded) | `{% for sig in signatures %}` | manager / tenant / tenant_2 / contractor_rep |
| Property fields (5 hardcoded) | `{% for row in property_rows %}` | המקור מסנן ריקים |
| Handed-over items table (9 שורות) | `{% for item in delivered_items %}` | אם המערכת תומכת — אחרת השאר ריק |

---

## 6. Conditionals חשובים

```jinja
{# התאם cover thumbnail — אם יש תמונת חזית בפרויקט #}
{% if project_cover_image_b64 %}
  <img class="cover-thumb-img" src="{{ project_cover_image_b64 }}" alt="חזית">
{% else %}
  <div class="cover-thumb"><svg>...building icon...</svg><span class="lab">חזית</span></div>
{% endif %}

{# הסתר severity bar אם 0 ליקויים מהסוג הזה #}
{% if defect_severity_counts.cosmetic > 0 %}<div class="sev cosm">...</div>{% endif %}

{# הסתר tenant notes block אם אין הערות #}
{% if tenant_notes %}<section class="tenant-notes">{{ tenant_notes }}</section>{% endif %}

{# חתימת קבלן — show as unsigned card אם sig.image_b64 ריק #}
<div class="sig-card {% if sig.image_b64 %}signed{% else %}unsigned{% endif %}">
```

---

## 7. WeasyPrint compatibility — שינויים נדרשים

WeasyPrint לא תומך ב:
- `aspect-ratio` — החלף ב-`padding-bottom: 75%` hack לתמונות
- `gap` ב-flexbox — השתמש ב-`margin` במקום
- ה-data-uri SVG ב-`background-image` — וודא שה-encoding נכון (UTF-8 + URL escape)
- `@font-face` עם blob URLs — יצטרך לטעון פונטים מ-`{{ fonts_dir }}/` (Heebo + JetBrains Mono כבר קיימים)
- CSS variables ב-`oklch()` או חישובים מתקדמים — היצמד ל-hex

החלף את כל ה-`<svg>` inline שהוספנו (Lucide) — וודא שהם עובדים ב-WeasyPrint (`width`/`height` מפורש כ-attribute, לא רק CSS).

---

## 8. בדיקות לפני merge

הרץ את `services/handover_pdf_service.py.generate_handover_pdf()` על 3 דירות שונות:

| תרחיש | מה לבדוק |
|---|---|
| 1. דירה ללא ליקויים בכלל (stats_fail=0) | האם severity bars מתחבאים יפה? sig-cards של דיירים נראים? |
| 2. דירה עם 1 ליקוי קריטי + 5 רגיל + 2 קוסמטי | האם 3 ה-bars מציגים נכון? defect detail cards מציגים תמונות? |
| 3. דירה ללא חניה/מחסן/מרפסת + ארגון עם 5 נסחים משפטיים | האם property_rows מסתיר ריקים? legal_sections מציג את כל ה-5? |

וודא:
- [ ] PDF נוצר בלי warnings מ-WeasyPrint
- [ ] גודל קובץ סביר (< 5MB לדירה ממוצעת עם 10 תמונות)
- [ ] עברית RTL מוצגת נכון
- [ ] תאריכים בעברית (`4 באפריל 2026`, לא `April 4`)
- [ ] חתימות מוטמעות כתמונה (לא URL חיצוני)

---

## 9. DO NOT

- **אל תוסיף עמודות חדשות ל-DB.** כל מה שצריך כבר שם.
- **אל תשנה את חתימת `generate_handover_pdf()`.** ה-API עומד.
- **אל תוסיף JS ל-template.** WeasyPrint לא מריץ JS.
- **אל תוסיף ספריות חיצוניות ל-CSS** (CDN fonts, Tailwind וכו'). הכל inline או מ-`{{ fonts_dir }}`.
- **אל תיגע בקובץ המוקאפ** `BrikOps Handover Protocol v2.4.html` — הוא reference, לא יעד.

---

## 10. הקשר נוסף

קרא לפני התחלה:
- `HANDOVER-v2.2-GAP-REPORT.md` — דוח הפערים המלא (workspace root)
- `backend/templates/handover_protocol_pdf.html` — ה-template הישן, ראה את ה-loops ו-conditionals שכבר עובדים
- `backend/services/handover_pdf_service.py` lines 25-150 — מילון `STATUS_LABELS`, `SEVERITY_LABELS`, `HARDCODED_PROPERTY_LABELS`

**בעת ספק:** ה-Jinja הישן הוא ה-source of truth ל-data flow. **v2.4** הוא ה-source of truth ל-visual.

---

## 11. פלט

- שמור את ה-template החדש בשם `backend/templates/handover_protocol_pdf.html` (החלפה).
- שמור backup של הישן בשם `handover_protocol_pdf.v1.html.bak`.
- כתוב CHANGELOG קצר ב-PR description: מה השתנה ב-Jinja vars (אם שינית), אילו testing scenarios רצו.

**זמן עבודה משוער:** 4-6 שעות (+ 1-2 שעות לתוספות 12-13 למטה).

---

## 12. תוספת חדשה — צילומי ת.ז של דיירים (אופציונלי)

**הקשר:** v2.5 כולל את התמונות בשני מקומות: thumbnails בעמ' 1 (Cover) + הצגה גדולה ב-ID Appendix (עמ' 10). כרגע **השדה לא קיים ב-DB** ולכן זה optional, אבל **המקום בעיצוב חייב להיות מוקצה** כדי שכשנוסיף את ה-feature נוכל פשוט להזין URL וזה יעבוד.

### ⚠️ עיקרון קריטי — מקור אמת אחד (Single Source of Truth)

**שני המיקומים בעיצוב חייבים לקרוא מאותו השדה ב-DB.** המשתמש מעלה את התמונה **פעם אחת**, והיא מופיעה **בשני המקומות אוטומטית**.

- מעלים בעמ' 1 (Cover thumbnail) → תמונה גדולה מופיעה גם בעמ' 10
- מעלים בעמ' 10 (ID Appendix) → thumbnail מופיע גם בעמ' 1
- מחליפים תמונה → מתעדכן בשני המקומות מיד
- מוחקים → נעלם משני המקומות

**אסור** ליצור שני שדות נפרדים (`thumbnail_url` + `large_url`). השדה ב-DB הוא `tenant.id_card_image_front_url` (URL אחד) + `tenant.id_card_image_back_url` (URL אחד). הטמפלייט פשוט משתמש ב-CSS `background-size: cover` כדי להתאים את אותה תמונה לגדלים שונים.

### א. שדות חדשים שצריך להוסיף ל-Tenant model

ב-`backend/models.py` (או היכן שיש Tenant Pydantic model — חפש `class Tenant`/`TenantCreate`):

```python
id_card_image_front_url: Optional[str] = None
id_card_image_back_url: Optional[str] = None
```

ב-`backend/services/handover_pdf_service.py` — הוסף לטעינת התמונות:
```python
tenant.id_card_image_front_b64 = await _fetch_image_as_base64(
    tenant.get('id_card_image_front_url'), session, max_width=120
)
tenant.id_card_image_back_b64 = await _fetch_image_as_base64(
    tenant.get('id_card_image_back_url'), session, max_width=120
)
```

### ב. ב-template (Jinja)

החלף את ה-tenant block ב-Cover ל:
```html
{% for tenant in tenants %}
  <div class="tenant">
    <div class="tenant-avatar">{{ tenant.name[:2] }}</div>
    <div class="tenant-info">
      <div class="name">{{ tenant.name }} <span style="...">{{ tenant.role_label }}</span></div>
      ת״ז {{ tenant.id_number }} · {{ tenant.phone }} · {{ tenant.email }}
      <div class="tags">
        {% if tenant.signed %}<span class="tag-mini">חתום ✓</span>{% endif %}
        {% if tenant.received_keys %}<span class="tag-mini">קיבל מפתחות</span>{% endif %}
      </div>
    </div>
    <div class="tenant-id-photos">
      {% if tenant.id_card_image_front_b64 %}
        <div class="id-photo has-image" style="background-image: url('{{ tenant.id_card_image_front_b64 }}'); background-size: cover; background-position: center;">
          <span class="lbl">ת.ז · קדמי</span>
        </div>
      {% else %}
        <div class="id-photo"><span class="lbl">ת.ז · קדמי</span></div>
      {% endif %}
      {% if tenant.id_card_image_back_b64 %}
        <div class="id-photo has-image" style="background-image: url('{{ tenant.id_card_image_back_b64 }}'); background-size: cover; background-position: center;">
          <span class="lbl">ת.ז · אחורי</span>
        </div>
      {% else %}
        <div class="id-photo"><span class="lbl">ת.ז · אחורי</span></div>
      {% endif %}
    </div>
  </div>
{% endfor %}
```

### ג. UI להעלאת התמונות

ב-`frontend/src/components/handover/HandoverTenantForm.js` — הוסף 2 שדות upload לכל דייר ("צילום ת.ז קדמי" + "אחורי"). השתמש באותו upload helper שכבר קיים ב-`SignaturePadModal` או ב-meter form.

**חובה:** רק נקודת העלאה אחת ב-UI לכל דייר (לא שני שדות נפרדים — לא חשוב אם הקבלן ניגש מ"פרטי דייר" או מ"נספח תעודות זהות", שניהם פותחים את אותו modal). השדות נשמרים פעם אחת, מוצגים פעמיים ב-PDF.

**Workflow אמיתי:**
1. הקבלן מתחיל פרוטוקול חדש, מזין שם + ת״ז של אלי אריאלי (לפעמים זה כבר מיובא מ-Excel)
2. **חובה:** מעלה צילום קדמי + אחורי של הת.ז שלו
3. ה-PDF שיווצר יציג את התמונות גם ב-Cover thumbnail וגם ב-Appendix גדול
4. אם הקבלן רוצה להוסיף ת.ז של דייר 2 (ורד) **אחרי** המסירה — נכנס שוב לאפליקציה, מעלה לורד, ה-PDF הבא שיווצר יציג גם אותם

**עדיפות:** Phase 2 — כרגע ה-PDF פשוט יציג את ה-placeholder עם האייקון, וזה בסדר.

---

## 13. תוספת חדשה — ת״ז בחתימות נסחים משפטיים (חובה)

**הקשר:** עד עכשיו ה-`.legal-sigline .sigchip` הציג רק שם + תאריך:
> אלי אריאלי · 4.4.2026

זה **לא מספיק** — חוק חתימה דורש זיהוי. צריך:
> אלי אריאלי · ת״ז 31200009 · 4.4.2026

### ב-template (Jinja)

מצא את ה-loop של legal_sections ועדכן את ה-sigline:
```html
<div class="legal-sigline">
  {% for tenant in tenants %}
    <span class="sigchip">{{ tenant.name }} · ת״ז {{ tenant.id_number }} · {{ signed_date }}</span>
  {% endfor %}
</div>
```

### CSS — וודא wrap

`.legal-sigline` ו-`.sigchip` חייבים `flex-wrap: wrap` כי ה-chip עכשיו ארוך יותר ועלול לחרוג בעמוד צר. ב-v2.4 הוספתי:
```css
.sigchip { flex-wrap: wrap; }
.legal-sigline { flex-wrap: wrap; gap: 12px 24px; }
```

### בדיקת תאימות

חפש בכל ה-template שלא נשארה הופעה של chip ישן (שם בלי ת.ז):
```bash
grep -E "sigchip\">[^<]*[א-ת][^·]*·\s*[0-9]" backend/templates/handover_protocol_pdf.html
```
כל chip צריך להכיל לפחות 2 פעמים `·` (שם · ת״ז · תאריך).

**עדיפות:** P0 — חובה לפני שזה יוצא לקבלן/יזם.

---

**שאלות → אלי. צא לדרך.**
