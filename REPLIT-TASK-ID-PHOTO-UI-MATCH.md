# REPLIT TASK — ID Photo UI: התאמה ל-pattern של "צלם מונה"

> **שינוי visual בלבד.** הendpoints, service, template — נשארים כפי שהם. רק ה-UI של ה-upload בtenant card משתנה ל-pattern קיים בקוד.
>
> **הצורך:** היום ה-button של ID photo נראה כ-text-link עם אייקון Upload. המשתמש רוצה שזה ייראה **בדיוק כמו** ה-button של "צלם מונה" ב-meters: outlined card-button עם אייקון Camera ו-`capture="environment"` (פותח מצלמה במובייל ישר).

---

## הקובץ היחיד שמשתנה

`frontend/src/components/handover/HandoverTenantForm.js`

### חלק A — Imports

מצא את שורת ה-imports של lucide-react:
```javascript
import { Loader2, Plus, Trash2, Upload, X } from 'lucide-react';
```

החלף ל:
```javascript
import { Loader2, Plus, Trash2, Camera, Upload, X } from 'lucide-react';
```

(מוסיף `Camera`, משאיר `Upload`. שני אייקונים שונים לשני כפתורים שונים.)

### חלק B — UI של ה-photo control (החלף את הblock כולו)

ב-tenant card, אחרי ה-grid של 4 השדות (name/id/phone/email), כיום יש block של "צילום ת.ז (קדמי)" עם label + flex container שמכיל "✓ תמונה הועלתה" / "העלה צילום ת.ז" / X.

**החלף את כל ה-block ב:**

```jsx
{/* תמונת ת.ז (קדמי) — אותה תבנית של "צלם מונה" */}
<div className="space-y-1">
  <label className="text-[10px] font-medium text-slate-500">צילום ת.ז (קדמי)</label>

  {tenant.id_photo_url && (
    <div className="relative inline-block">
      <img
        src={tenant.id_photo_url}
        alt="ת.ז"
        className="w-24 h-18 object-cover rounded-lg border border-slate-200"
      />
      {!isSigned && (
        <button
          onClick={() => handleIdPhotoDelete(idx)}
          disabled={uploadingIdx === idx}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center disabled:opacity-50 shadow"
          title="מחק תמונה"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  )}

  {!isSigned && (
    <div className="flex items-center gap-2">
      {/* Hidden inputs — אחד למצלמה, אחד לגלריה */}
      <input
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        id={`id-photo-camera-${idx}`}
        disabled={uploadingIdx === idx}
        onChange={(e) => handleIdPhotoUpload(idx, e.target.files?.[0])}
      />
      <input
        type="file"
        accept="image/*"
        className="hidden"
        id={`id-photo-upload-${idx}`}
        disabled={uploadingIdx === idx}
        onChange={(e) => handleIdPhotoUpload(idx, e.target.files?.[0])}
      />

      {/* כפתור 1 — צלם (פותח מצלמה במובייל) */}
      <button
        onClick={() => document.getElementById(`id-photo-camera-${idx}`)?.click()}
        disabled={uploadingIdx === idx}
        className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors border-purple-300 hover:bg-slate-50 disabled:opacity-50"
      >
        {uploadingIdx === idx ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Camera className="w-3.5 h-3.5" />
        )}
        {uploadingIdx === idx
          ? 'מעלה...'
          : tenant.id_photo_url
            ? 'החלף בצילום'
            : 'צלם'}
      </button>

      {/* כפתור 2 — העלה מהגלריה */}
      <button
        onClick={() => document.getElementById(`id-photo-upload-${idx}`)?.click()}
        disabled={uploadingIdx === idx}
        className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors border-slate-300 hover:bg-slate-50 disabled:opacity-50 text-slate-600"
      >
        <Upload className="w-3.5 h-3.5" />
        {tenant.id_photo_url ? 'החלף מהגלריה' : 'העלה'}
      </button>
    </div>
  )}

  {tenant.id_photo_url && isSigned && (
    <span className="text-xs text-slate-400">(נעול — פרוטוקול חתום)</span>
  )}
</div>
```

### מה השתנה (לעומת ה-UI הנוכחי)

1. **2 כפתורים קטנים זה לצד זה** — "צלם" (עם מצלמה) + "העלה" (מהגלריה)
2. **כפתור Camera בvolet סגול** (כמו "צלם מונה" — primary action)
3. **כפתור Upload ב-slate** (secondary action — קצת פחות בולט)
4. **`capture="environment"`** רק ב-input של ה-Camera button — פותח מצלמה במובייל ישירות
5. **Preview thumbnail** מופיע אחרי העלאה (`w-24 h-18`)
6. **כפתור X** בפינת הthumbnail (אדום עגול)
7. **2 inputs נפרדים** עם ids ייחודיים: `id-photo-camera-{idx}` ו-`id-photo-upload-{idx}` — מאפשרים לכפתור לפתוח חוויה שונה (camera vs file picker)
8. **Labels של כפתורים משתנים בהתאם למצב:**
   - אין תמונה → "צלם" + "העלה"
   - יש תמונה → "החלף בצילום" + "החלף מהגלריה"
   - בעת upload → "מעלה..." + spinner על הbutton הראשון

**הLogic של handleIdPhotoUpload + handleIdPhotoDelete לא משתנה** — שני הinputs קוראים לאותו handler.

---

## DO NOT

- אל תיגע ב-endpoints (POST/DELETE) — הם תקינים
- אל תיגע ב-PDF service או בtemplate — הרנדור עובד
- אל תיגע ב-`handleIdPhotoUpload` ו-`handleIdPhotoDelete` (הlogic) — רק במשמש את ה-UI שלהם
- אל תיגע ב-`HandoverMeterForm.js` (שירת כ-reference בלבד)

---

## VERIFY

לאחר deploy:

- [ ] בtenant card רואים label "צילום ת.ז (קדמי)" + **2 כפתורים** זה לצד זה: "צלם" (סגול) + "העלה" (אפור)
- [ ] **במובייל:** לחיצה על "צלם" פותחת מצלמה ישירות. לחיצה על "העלה" פותחת file picker רגיל (גלריה)
- [ ] **במחשב:** שתי הלחיצות פותחות file picker (capture="environment" מתעלם בדסקטופ — תקין)
- [ ] אחרי העלאה → thumbnail 24×18 + labels משתנים ל"החלף בצילום" / "החלף מהגלריה"
- [ ] X אדום בפינת הthumbnail מוחק
- [ ] פרוטוקול חתום + תמונה קיימת → רואים thumbnail + "(נעול — פרוטוקול חתום)" אבל אין X או buttons
- [ ] פרוטוקול חתום + אין תמונה → אין שום control

---

## Standing rule

Replit עורך קבצים בלבד. אחרי Build → אני אריץ `./deploy.sh --stag`.

---

## Commit message

```
HandoverTenantForm: ID photo — two side-by-side small buttons (צלם + העלה)

Replace the single text-link upload control with two small outlined
buttons side by side, matching the HandoverMeterForm "צלם מונה" pattern
but offering both camera and gallery options.

- "צלם" button (purple, Camera icon, capture="environment") — opens
  the device camera directly on mobile
- "העלה" button (slate, Upload icon, no capture) — opens file picker
  for an existing image (gallery on mobile, file dialog on desktop)
- Preview thumbnail appears after upload (24x18 cover)
- X delete moved to top corner of thumbnail
- Labels switch when photo exists: "החלף בצילום" / "החלף מהגלריה"
- Two unique hidden inputs per tenant (camera + upload) sharing the
  same handleIdPhotoUpload handler

No endpoint, service, or PDF template changes — pure UI fix.
```

מצופה זמן: 10 דקות. שינוי קוסמטי בקובץ אחד.
