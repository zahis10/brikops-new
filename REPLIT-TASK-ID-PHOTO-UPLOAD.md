# REPLIT TASK — צילום ת.ז של דייר (Front Only)

> **מטרה:** העלאת תמונת ת.ז קדמית לכל דייר. תוצג בעמ' הדיירים בPDF (משתמשת בplaceholder slots קיימים).
>
> **גישה מצומצמת לעומת SPEC-B המקורי:**
> - **רק צד קדמי** (לא back) — שדה אחד, תמונה אחת
> - הplaceholders של צד אחורי בטמפלייט מוסרים
>
> **groundwork קיים:** השדה `id_photo_url` כבר קיים ב-Frontend `EMPTY_TENANT`, ב-Backend tenant init (שורות 989, 1042, 1051 ב-handover_router.py), וב-data_export_service. **חסר רק:** UI לupload + endpoint + טעינה ב-PDF service + רנדור בtemplate.

---

## חלק 1 — Backend Endpoint (POST upload)

קובץ: `backend/contractor_ops/handover_router.py`

הוסף endpoint חדש מיד לפני או אחרי `upload_meter_photo` (שורה ~2410). **השתמש באותו pattern בדיוק** — אותה validation, אותה storage, אותו audit logging.

```python
@router.post("/projects/{project_id}/handover/protocols/{protocol_id}/tenants/{tenant_idx}/id-photo")
async def upload_tenant_id_photo(
    project_id: str, protocol_id: str, tenant_idx: int,
    file: UploadFile = File(...), user: dict = Depends(get_current_user),
):
    """העלאת תמונת ת.ז (קדמית) של דייר. PII — נדרש audit log."""
    from services.object_storage import save_bytes as _save_bytes, generate_url as _gen_url
    import asyncio

    if tenant_idx < 0 or tenant_idx > 9:
        raise HTTPException(status_code=400, detail="אינדקס דייר לא תקין")

    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    tenants = protocol.get("tenants") or []
    if tenant_idx >= len(tenants):
        raise HTTPException(status_code=400, detail=f"דייר {tenant_idx + 1} לא קיים")

    validate_upload(file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
    MAX_SIZE = 8 * 1024 * 1024  # ת.ז יכולה להיות מצולמת באיכות גבוהה לקריאות בית משפט
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="קובץ ריק")
    if len(raw) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="גודל הקובץ חורג מ-8MB")

    ext = (file.filename or "id.jpg").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    ct = file.content_type or "image/jpeg"

    key = f"handover/{project_id}/{protocol_id}/tenant_{tenant_idx}_id.{ext}"
    stored_ref = await asyncio.to_thread(_save_bytes, raw, key, ct)

    db = get_db()
    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$set": {f"tenants.{tenant_idx}.id_photo_url": stored_ref, "updated_at": _now()}}
    )

    # Audit log — PII tracking (חובה!)
    logger.info(
        f"[HANDOVER-PII] Protocol={protocol_id} tenant_idx={tenant_idx} "
        f"id_photo_uploaded by user={user['id']} ({user.get('email', '?')})"
    )

    url = await asyncio.to_thread(_gen_url, stored_ref)
    return {"id_photo_url": stored_ref, "display_url": url}


@router.delete("/projects/{project_id}/handover/protocols/{protocol_id}/tenants/{tenant_idx}/id-photo")
async def delete_tenant_id_photo(
    project_id: str, protocol_id: str, tenant_idx: int,
    user: dict = Depends(get_current_user),
):
    """מחיקת תמונת ת.ז של דייר. PII — נדרש audit log."""
    if tenant_idx < 0 or tenant_idx > 9:
        raise HTTPException(status_code=400, detail="אינדקס דייר לא תקין")

    await _check_handover_management(user, project_id)
    protocol = await _get_protocol_or_404(protocol_id, project_id)
    _check_not_locked(protocol)

    db = get_db()
    await db.handover_protocols.update_one(
        {"id": protocol_id, "project_id": project_id},
        {"$set": {f"tenants.{tenant_idx}.id_photo_url": None, "updated_at": _now()}}
    )

    # Audit log
    logger.info(
        f"[HANDOVER-PII] Protocol={protocol_id} tenant_idx={tenant_idx} "
        f"id_photo_deleted by user={user['id']} ({user.get('email', '?')})"
    )

    return {"ok": True}
```

**הערות:**
- 8MB max (לעומת 5MB במונים) — ת.ז = ראיה משפטית פוטנציאלית, רוצים איכות
- Audit prefix `[HANDOVER-PII]` (מובחן מ-`[HANDOVER]` הרגיל) — קל לחלץ logs לרגולציה
- תוקף: רק `_check_handover_management` (אותה רמת הרשאות כמו meter_photo)

---

## חלק 2 — Backend Service (טעינת התמונה ל-PDF)

קובץ: `backend/services/handover_pdf_service.py`

### 2.1 — בקטע שטוען image_keys (סביב שורה 386-410, בקרבת `logo_url = snapshot.get("company_logo_url")`)

הוסף בלוק חדש לטעינת ID photos של דיירים:

```python
# Tenant ID photos — load each tenant's id_photo_url
tenants_for_id = protocol.get("tenants") or []
for t_idx, tnt in enumerate(tenants_for_id):
    id_url = tnt.get("id_photo_url")
    if id_url:
        image_keys.append((f"tenant_{t_idx}_id", id_url))
```

### 2.2 — בקטע fetch tasks (סביב שורה 463-470, היכן שמוגדרים `mw, q` per type)

הוסף ל-elif chain:

```python
elif key_name.startswith("tenant_") and key_name.endswith("_id"):
    mw, q = 1200, 80   # קריאות בית משפט — יותר גבוה ממונים, פחות מsignatures
```

### 2.3 — בקטע tenants_data (סביב שורה 370 — חפש `tenants_data = [t for t in tenants if t.get("name")]`)

החלף את ה-list comprehension ב-loop שמחזיר tenants עם `id_photo_b64`:

```python
tenants_raw = protocol.get("tenants") or []
tenants_data = []
for t_idx, t in enumerate(tenants_raw):
    if not t.get("name"):
        continue
    t_with_photo = dict(t)
    t_with_photo["id_photo_b64"] = images.get(f"tenant_{t_idx}_id")
    tenants_data.append(t_with_photo)
```

(ה-loop משמר את כל השדות הקיימים ב-tenant + מוסיף `id_photo_b64`.)

---

## חלק 3 — Template (עיצוב תצוגת התמונה)

קובץ: `backend/templates/handover_protocol_pdf.html`

### 3.1 — עדכן את הCSS של `.id-photo` (סביב שורה 411-435)

מצא:
```css
.tenant-id-photos {
  ...
}
.id-photo {
  ...
}
.id-photo .lbl {
  ...
}
```

החלף ל:
```css
.tenant-id-photos {
  display: flex;
  gap: 8px;
  align-items: center;
}
.id-photo {
  width: 90px;
  height: 56px;
  border: 1px dashed var(--slate-3);
  border-radius: 6px;
  background: var(--slate-1);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
.id-photo.has-image {
  border: 1px solid var(--slate-3);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}
.id-photo .lbl {
  font-size: 9px;
  color: var(--slate-5);
  text-align: center;
  padding: 0 4px;
}
.id-photo.has-image .lbl {
  display: none;        /* הסתר label כשיש תמונה */
}
```

### 3.2 — עדכן את ה-rendering בעמ' Tenants (סביב שורה 1243)

מצא:
```jinja
<div class="tenant-id-photos">
  <div class="id-photo"><span class="lbl">ת.ז · קדמי</span></div>
  <div class="id-photo"><span class="lbl">ת.ז · אחורי</span></div>
</div>
```

החלף ל:
```jinja
<div class="tenant-id-photos">
  {% if t.id_photo_b64 %}
    <div class="id-photo has-image" style="background-image: url('{{ t.id_photo_b64 }}');"></div>
  {% else %}
    <div class="id-photo"><span class="lbl">ת.ז · אין תמונה</span></div>
  {% endif %}
</div>
```

(שינויים: הוסר ה-back placeholder; ה-front מציג את התמונה אם קיימת, אחרת label "אין תמונה".)

---

## חלק 4 — Frontend UI

קובץ: `frontend/src/components/handover/HandoverTenantForm.js`

### 4.1 — הוסף את ה-import של ה-service וה-icon

בראש הקובץ, עדכן את ה-imports:

```javascript
import { Loader2, Plus, Trash2, Upload, X } from 'lucide-react';
import { handoverService } from '../../services/api';
```

(הוסף `Upload, X` ל-lucide imports.)

### 4.2 — הוסף state לטיפול בupload

ב-component, אחרי `const [saving, setSaving] = useState(false);`:

```javascript
const [uploadingIdx, setUploadingIdx] = useState(null);

const handleIdPhotoUpload = async (idx, file) => {
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) {
    toast.error('גודל הקובץ חורג מ-8MB');
    return;
  }
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    toast.error('פורמט לא נתמך — יש להעלות JPG / PNG / WEBP');
    return;
  }
  try {
    setUploadingIdx(idx);
    const fd = new FormData();
    fd.append('file', file);
    const res = await handoverService.uploadTenantIdPhoto(projectId, protocol.id, idx, fd);
    setTenants(prev => prev.map((ten, i) =>
      i === idx ? { ...ten, id_photo_url: res.id_photo_url } : ten
    ));
    toast.success('תמונת ת.ז הועלתה');
  } catch (err) {
    console.error(err);
    toast.error('שגיאה בהעלאת תמונת ת.ז');
  } finally {
    setUploadingIdx(null);
  }
};

const handleIdPhotoDelete = async (idx) => {
  try {
    setUploadingIdx(idx);
    await handoverService.deleteTenantIdPhoto(projectId, protocol.id, idx);
    setTenants(prev => prev.map((ten, i) =>
      i === idx ? { ...ten, id_photo_url: null } : ten
    ));
    toast.success('תמונת ת.ז נמחקה');
  } catch (err) {
    console.error(err);
    toast.error('שגיאה במחיקת תמונת ת.ז');
  } finally {
    setUploadingIdx(null);
  }
};
```

### 4.3 — הוסף את ה-UI ב-tenant card

בתוך הloop של tenants, אחרי ה-grid של 4 השדות (name/id/phone/email), לפני ה-`</div>` שסוגר את ה-`tenants.map`:

```jsx
{/* תמונת ת.ז (קדמית) */}
<div className="space-y-1">
  <label className="text-[10px] font-medium text-slate-500">צילום ת.ז (קדמי)</label>
  <div className="flex items-center gap-2">
    {tenant.id_photo_url ? (
      <>
        <span className="text-xs text-emerald-600 font-medium">✓ תמונה הועלתה</span>
        {!isSigned && (
          <button
            onClick={() => handleIdPhotoDelete(idx)}
            disabled={uploadingIdx === idx}
            className="text-red-400 hover:text-red-600 p-1 disabled:opacity-50"
            title="מחק תמונה"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </>
    ) : (
      !isSigned && (
        <label className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-800 cursor-pointer font-medium">
          {uploadingIdx === idx ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Upload className="w-3.5 h-3.5" />
          )}
          {uploadingIdx === idx ? 'מעלה...' : 'העלה צילום ת.ז'}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            disabled={uploadingIdx === idx}
            onChange={(e) => handleIdPhotoUpload(idx, e.target.files?.[0])}
          />
        </label>
      )
    )}
    {tenant.id_photo_url && isSigned && (
      <span className="text-xs text-slate-400">(נעול — פרוטוקול חתום)</span>
    )}
  </div>
</div>
```

### 4.4 — הוסף את ה-API methods ב-handoverService

קובץ: `frontend/src/services/api.js` — מצא את ה-`handoverService` object והוסף:

```javascript
async uploadTenantIdPhoto(projectId, protocolId, tenantIdx, formData) {
  const res = await fetch(
    `${API_BASE}/api/projects/${projectId}/handover/protocols/${protocolId}/tenants/${tenantIdx}/id-photo`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: formData,
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
},

async deleteTenantIdPhoto(projectId, protocolId, tenantIdx) {
  const res = await fetch(
    `${API_BASE}/api/projects/${projectId}/handover/protocols/${protocolId}/tenants/${tenantIdx}/id-photo`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${getToken()}` },
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Delete failed');
  }
  return res.json();
},
```

(תאם את הצורה (helper function name, base URL var) למה שיש כיום ב-`api.js`.)

---

## VERIFY checklist

לאחר deploy ל-staging:

**End-to-end flow:**
- [ ] התחבר ל-staging, פתח פרוטוקול דמו
- [ ] עבור לטאב הדיירים → לכל דייר רואים שדה "צילום ת.ז (קדמי)"
- [ ] לחיצה על "העלה צילום ת.ז" → file picker נפתח
- [ ] בחר תמונה (JPG/PNG, מתחת ל-8MB) → toast "תמונת ת.ז הועלתה" + הסטטוס משתנה ל-"✓ תמונה הועלתה"
- [ ] לחיצה על X → toast "תמונת ת.ז נמחקה" + חזרה לכפתור העלאה

**PDF rendering:**
- [ ] Generate PDF → בעמ' הדיירים, לכל דייר עם תמונה רואים את התמונה האמיתית במקום placeholder
- [ ] לכל דייר ללא תמונה — placeholder "ת.ז · אין תמונה"
- [ ] התמונה ברורה וקריאה (ת.ז ניתנת לזיהוי)

**Edge cases:**
- [ ] קובץ > 8MB → toast שגיאה, לא מעלה
- [ ] קובץ TIFF/BMP → toast שגיאה
- [ ] פרוטוקול חתום (locked) → אין כפתור העלאה/מחיקה (כי `isSigned` true)
- [ ] CloudWatch / EB logs מציגים `[HANDOVER-PII]` עבור כל upload + delete

**Privacy:**
- [ ] הקובץ נשמר ב-S3 בpath `handover/{project_id}/{protocol_id}/tenant_{idx}_id.jpg`
- [ ] רק משתמשים מורשים יכולים להעלות (validated by `_check_handover_management`)

---

## DO NOT

- אל תוסיף שדה back-side (המשתמש ביקש front only)
- אל תיגע ב-`upload_meter_photo` (analog בלבד, לא לשנות)
- אל תיגע ב-Photo diag, page_header, room-block, defects-summary-block וכל carry-over
- אל תיגע ב-`generate_handover_pdf` או ב-PDF service בעיקר — רק תוספת קטנה לטעינת התמונה
- אל תאפשר העלאה לפרוטוקול נעול (`_check_not_locked`)

---

## Carry-over invariants

- v3.8 header strip על כל עמ' (CSS Paged Media running())
- `tenants_data` עם `id_photo_b64` field חדש (מוסיף, לא מחליף)
- כל ה-fields הקיימים של tenant (name, id_number, phone, email) ממשיכים לעבוד
- `id_photo_url` field כבר קיים ב-DB tenant docs (groundwork מ-v2)

---

## Standing rule

Replit עורך קבצים בלבד. **לא commit, לא push, לא deploy.**

אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
handover: tenant ID photo upload (front side only)

End-to-end implementation of tenant ID photo upload for handover
protocols. The id_photo_url field already existed in tenant data
shape (frontend EMPTY_TENANT, backend init, data export); this PR
wires the upload UI + endpoint + PDF rendering.

Backend:
  - POST /projects/{p}/handover/protocols/{id}/tenants/{idx}/id-photo
  - DELETE same path (for replace/remove)
  - 8MB max, JPG/PNG/WEBP only, S3 storage via object_storage
  - [HANDOVER-PII] audit log on every upload/delete (PII tracking)
  - locked-protocol guard

Service (handover_pdf_service.py):
  - Load each tenant's id_photo_url as base64 (1200px / q80 — court-grade)
  - Pass as id_photo_b64 on each tenant in template context

Template:
  - Render tenant.id_photo_b64 as background-image when present
  - Otherwise show "אין תמונה" placeholder
  - Removed back-side placeholder (front-only per spec)

Frontend (HandoverTenantForm.js):
  - Upload button per tenant card
  - Delete button when uploaded
  - Loading state, toast feedback
  - 8MB / image-type client-side validation
  - Disabled when protocol is signed

Privacy: PII audit logging on all photo events. URLs stored as S3
references (not base64 in DB). Only authorized users can upload.
```

מצופה זמן: 1-2 שעות עבודה ברפליט. 4 קבצים נערכים, אחד נוסף בכל קובץ ביזורי.
