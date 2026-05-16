# REPLIT FOLLOWUP — Hebrew gibberish + Photos diagnostic

> **Context:** ה-PR הקודם (`f618eaa "Add photos to defect details and fix Hebrew text rendering"`) פתר רק חלק מהבעיה.
>
> **בדיקה שלי על origin/staging הראתה:** עדיין יש **5** הצהרות `text-transform: uppercase` בtemplate שמופעלות על טקסט עברית — זה הסיבה לג׳יבריש. ה-PR הקודם הסיר רק 3 מתוך 8.
>
> **תמונות:** הקוד נראה תקין מבחינת data-flow, אבל המשתמש מדווח שהן עדיין לא מופיעות. צריך diagnostic logs כדי להבין למה.

---

## חלק 1 — תיקון Hebrew gibberish (CRITICAL, חובה)

### הבעיה הטכנית

ב-WeasyPrint, כשיש `text-transform: uppercase` על טקסט בעברית:
1. WeasyPrint מנסה למצוא variant של uppercase ל-glyphs בעברית
2. עברית לא תומכת ב-case — אין uppercase
3. WeasyPrint עושה fallback ל-font הבא ב-stack (DejaVu Sans Bold)
4. DejaVu Sans Bold לא מכיל glyphs בעברית → מציג squares/glitched chars
5. התוצאה: "Akñàá" וג׳יבריש דומה

**הפתרון:** להסיר את `text-transform: uppercase` מכל מקום שעלול להגיע אליו טקסט בעברית.

### מה צריך לתקן

קובץ: `backend/templates/handover_protocol_pdf.html`

חמש הצהרות `text-transform: uppercase` שעדיין נמצאות במקור — **כולן** מופעלות על תוכן עברית:

| # | שורה | Selector | תוכן עברית שנפגע |
|---|---|---|---|
| 1 | 166 | `.cover-thumb .lab` | "חזית" (תווית התמונה הקדמית בעמ' 1) |
| 2 | 226 | `.cover-card-strip .lab` | "בניין", "קומה", "דירה", "דייר"/"דיירים" (תוויות card הסיכום בעמ' 1) |
| 3 | 334 | `.info-card h4` | "פרטי נכס", "צוות מסירה", "דיירים" (כותרות info-cards) |
| 4 | 865 | `.sig-grid td .role` | "מנהל פרויקט", "רוכש/ת ראשי/ת", "רוכש/ת נוסף/ת", "נציג קבלן" (תוויות תפקידי החותמים) |
| 5 | 962 | `.defect-card-body .desc h5` | "תיאור הליקוי" (כותרת תיאור הליקוי בdefect-cards) |

### איך לתקן — diff מדויק

**שורה ~166 (`.cover-thumb .lab`):**
```diff
.cover-thumb .lab {
  display: block;
  font-size: 9px;
  margin-top: 2px;
  letter-spacing: 0.06em;
- text-transform: uppercase;
  color: rgba(255,255,255,0.55);
}
```

**שורה ~226 (`.cover-card-strip .lab`):**
```diff
.cover-card-strip .lab {
  font-size: 9.5px; color: rgba(255,255,255,0.45);
- letter-spacing: 0.10em; text-transform: uppercase;
+ letter-spacing: 0.04em;
  margin-bottom: 4px;
}
```

**שורה ~334 (`.info-card h4`):**
```diff
.info-card h4 {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--slate-7);
  letter-spacing: 0.04em;
- text-transform: uppercase;
  margin: 0 0 10px;
}
```

**שורה ~865 (`.sig-grid td .role`):**
```diff
.sig-grid td .role {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--orange);
- text-transform: uppercase;
  margin-bottom: 4px;
}
```

**שורה ~962 (`.defect-card-body .desc h5`):**
```diff
.defect-card-body .desc h5 {
  margin: 0 0 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--slate-5);
- text-transform: uppercase;
}
```

### Verification (חובה לפני merge!)

לפני merge, רוץ:
```bash
grep -n "text-transform" backend/templates/handover_protocol_pdf.html
```

**התוצאה הצפויה:** *זירו matches.* אם יש אפילו אחד — לא הסרת מספיק.

---

## חלק 2 — Photos diagnostic (DIAGNOSE, לא לתקן עדיין)

### הבעיה

המשתמש מדווח שתמונות ליקויים לא מופיעות. הקוד שלך ב-`handover_pdf_service.py` נראה תקין:
- שורה 532: `item_data["photos"] = photo_b64s` ✓
- שורה 551: `all_defects.append({..., "photos": photo_b64s})` ✓

ה-template ב-line 1366-1389:
```jinja
{% set has_photo_items = [] %}
{% for it in sec['items']|default([]) %}
  {% if it.photos and (it.photos|select|list)|length > 0 %}
    {% set _ = has_photo_items.append(it) %}
  {% endif %}
{% endfor %}
```

**אנחנו לא יודעים מה המצב בפועל.** האם:
1. `item.photos` ריק (המשתמש לא העלה)?
2. `defect.proof_urls` ריק (הdefect לא נשמר עם תמונות)?
3. `_fetch_local_or_remote_image` נכשל (S3/object storage failure)?
4. `images.get(pk)` מחזיר `None` (key mismatch)?

### מה לעשות עכשיו — להוסיף diagnostic logs (לא לתקן ראיה לוגיקה)

ב-`backend/services/handover_pdf_service.py`, **אחרי** שורה 502 (`photo_b64s = [images.get(pk) for pk in photo_keys]`), הוסף:

```python
# DIAGNOSTIC — log photo flow per item
if photo_keys:
    truthy_count = sum(1 for p in photo_b64s if p)
    logger.info(
        f"[PDF] Photo diag: section='{sec.get('name', '?')}' "
        f"item='{item.get('name', '?')[:30]}' "
        f"item_id={item.get('item_id', '?')} "
        f"defect_id={item.get('defect_id', 'none')} "
        f"status={item.get('status')} "
        f"item.photos_count={len(item.get('photos', []) or [])} "
        f"defect.proof_urls_count={len((defect_map.get(item.get('defect_id', '')) or {}).get('proof_urls', []) or [])} "
        f"photo_keys={photo_keys} "
        f"fetched_truthy={truthy_count}/{len(photo_keys)}"
    )
elif item.get("status") in ("defective", "partial"):
    logger.info(
        f"[PDF] Photo diag: NO photos registered for defective item "
        f"section='{sec.get('name', '?')}' item='{item.get('name', '?')[:30]}' "
        f"item.photos={item.get('photos', [])} "
        f"defect_id={item.get('defect_id', 'none')}"
    )
```

ואז המשתמש יקבל פרוטוקול אחד, יבדוק את הלוגים ב-CloudWatch/Beanstalk, ויעלה את הפלט. **אז** נוכל להחליט אם צריך תיקון logic ובאיזה שכבה.

### DO NOT

- אל תיגע ב-template הסקציה הזאת (רק הDiagnostic לservice)
- אל תוסיף defect cards שמראים placeholders כשאין תמונות בכלל — הfilter `has_photo_items` הוא הנכון. אם אין תמונה → אין card. זה הdesign.
- אל תשנה את הdata-flow בservice — רק להוסיף logs

---

## VERIFY checklist

- [ ] `grep -n "text-transform" backend/templates/handover_protocol_pdf.html` → 0 matches
- [ ] גלגול PDF דמו עם דייר אחד → כל הטקסט בעברית קריא (אין "Akñàá", אין squares)
- [ ] גלגול PDF דמו עם 2 דיירים → רואים "מנהל פרויקט", "רוכש/ת ראשי/ת", "רוכש/ת נוסף/ת" — קריא
- [ ] גלגול PDF דמו עם defect שיש לו תיאור → "תיאור הליקוי" קריא
- [ ] CloudWatch/Beanstalk logs מציגים את ה-`[PDF] Photo diag:` עם מידע על photo_keys, defect_id, item.photos
- [ ] `letter-spacing` נשמר על כל הסלקטורים (רק `text-transform` הוסר)

---

## תוצרים

- 1 commit שמסיר את כל 5 ה-text-transform
- 1 commit נפרד שמוסיף Photo diagnostic logging
- בPR description: copy-paste של הdiff המלא + screenshot של PDF דמו אחרי

**מצופה זמן:** 15 דקות. זה תיקון מכני 100%.
