# REPLIT TASK — תיקון: לחיצה על תמונה בבקרת ביצוע פותחת AWS במקום modal

## הבעיה

במסך **בקרת ביצוע** (StageDetailPage), לחיצה על תמונה (thumbnail) של ליקוי מנווטת את המשתמש מהאפליקציה ל-URL של S3 (`...eu-central-1.amazonaws.com/...`) בדפדפן. הוא יוצא מהאפליקציה ולא יודע איך לחזור.

הצורך: בלחיצה על תמונה — תיפתח אותה תמונה ב-modal (lightbox) **בתוך** האפליקציה, עם כפתור X לסגירה. אין יציאה מהאפליקציה.

## המיקום היחיד שצריך לתקן

קובץ: `frontend/src/pages/StageDetailPage.js`

הקומפוננטה `PhotoThumbnail` (שורות 73-91), במיוחד שורה 78:

```jsx
const PhotoThumbnail = ({ photo, isPM }) => {
  const src = photo.url?.startsWith('http') ? photo.url : `${BACKEND_URL}${photo.url}`;
  const actorName = resolveActorName(photo.uploaded_by_name);
  return (
    <div className="inline-block">
      <a href={src} target="_blank" rel="noopener noreferrer" className="block">  {/* ← הבאג */}
        <img src={src} alt="" className="w-14 h-14 rounded-lg object-cover border border-slate-200 hover:border-amber-400 transition-all" />
      </a>
      ...
    </div>
  );
};
```

**אבחנה:** ה-`<a target="_blank">` מנווט לדפדפן. צריך להחליף ל-`<button>` שפותח modal פנימי.

**בדיקה שעשיתי:** `grep -rn "<a target=\"_blank\""` בכל ה-frontend הראה שזה המקום היחיד עם תמונות. שאר ה-target=_blank הם לdownload בלבד (ProjectDataExportTab) — אלה תקינים, לא לגעת.

## התיקון

### חלק A — הוספת state ולחצן (במקום `<a>`)

החלף את הקומפוננטה `PhotoThumbnail` (שורות 73-91) ב:

```jsx
const PhotoThumbnail = ({ photo, isPM, onOpen }) => {
  const src = photo.url?.startsWith('http') ? photo.url : `${BACKEND_URL}${photo.url}`;
  const actorName = resolveActorName(photo.uploaded_by_name);
  return (
    <div className="inline-block">
      <button
        type="button"
        onClick={() => onOpen(src)}
        className="block p-0 bg-transparent border-0 cursor-pointer"
        aria-label="הגדל תמונה"
      >
        <img src={src} alt="" className="w-14 h-14 rounded-lg object-cover border border-slate-200 hover:border-amber-400 transition-all" />
      </button>
      {(actorName || photo.uploaded_at) && (
        <p className="text-xs text-slate-600 mt-1 max-w-[160px] leading-normal" dir="rtl">
          {actorName ? <>צולם ע"י <span className="font-medium text-slate-700">{actorName}</span></> : 'צולם'}
          {photo.uploaded_at && <span className="block text-[11px] text-slate-400">{formatShortTime(photo.uploaded_at)}</span>}
        </p>
      )}
    </div>
  );
};
```

**שינויים:**
- `<a target="_blank">` → `<button onClick={() => onOpen(src)}>`
- הוספת prop `onOpen` שיקבל את ה-src לפתיחה
- aria-label לaccessibility

### חלק B — הוספת קומפוננטת PhotoLightbox

הוסף את הקומפוננטה הזו בסמוך ל-PhotoThumbnail (לפני או אחרי, לבחירת רפליט):

```jsx
const PhotoLightbox = ({ src, onClose }) => {
  // ESC key closes
  useEffect(() => {
    if (!src) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    // Lock body scroll
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [src, onClose]);

  if (!src) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/20 hover:bg-white/30 active:bg-white/40 flex items-center justify-center text-white transition-colors"
        aria-label="סגור"
      >
        <X className="w-6 h-6" />
      </button>
      <img
        src={src}
        alt=""
        className="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
};
```

**מה זה עושה:**
- `fixed inset-0 z-[100]` — מכסה את כל המסך
- `bg-black/80 backdrop-blur-sm` — רקע שחור שקוף עם blur
- לחיצה על הרקע → סוגר
- לחיצה על התמונה עצמה → לא סוגר (`stopPropagation`)
- כפתור X בפינה ימנית (RTL — אבל absolutel `right-4` נכון בRTL כי ב-LTR זה ימין; בRTL אם זה ימין מבחינה לוגית ולא ויזואלית, אם תרצה מצד שמאל ב-RTL, החלף `right-4` ל-`left-4`)
- ESC סוגר
- body scroll נעול בזמן שהlightbox פתוח

### חלק C — חיבור הstate בStageDetailPage

ב-`StageItemRow` (סביב שורה 92) או בקומפוננטה הרלוונטית שמרנדרת את התמונות, הוסף:

```jsx
// בתוך הfunction component, אחרי הuseStates הקיימים
const [lightboxSrc, setLightboxSrc] = useState(null);

// בשימוש ב-PhotoThumbnail (חפש את המקום שמרנדר אותן):
{photos.map((photo, i) => (
  <PhotoThumbnail
    key={i}
    photo={photo}
    isPM={isPM}
    onOpen={setLightboxSrc}
  />
))}

// בסוף ה-render (לפני ה-`</div>` הסוגר):
<PhotoLightbox src={lightboxSrc} onClose={() => setLightboxSrc(null)} />
```

**הערה לרפליט:** למצוא את המיקום המדויק של `photos.map(...)` בקובץ. אני זיהיתי `const photos = item.photos || [];` בשורה ~108 וצריך לחפש איפה הם רנדרים (כנראה אחרי `<PhotoThumbnail`).

### אם תרצה — יבוא של X icon

כן, צריך לוודא ש-`X` מ-lucide-react כבר מיובא. תבדוק אם הוא ברשימת imports בראש הקובץ. אם לא, הוסף:
```jsx
import { ..., X } from 'lucide-react';
```

(סביר שזה כבר שם כי ה-WhatsAppRejectionModal משתמש בו.)

## VERIFY

לאחר deploy ל-staging:

- [ ] במסך בקרת ביצוע, לחץ על תמונה כלשהי → תיפתח modal עם הtmunה במלואה (לא יציאה לדפדפן)
- [ ] לחיצה על הרקע השחור → סוגרת
- [ ] לחיצה על X בפינה → סוגרת
- [ ] ESC מהמקלדת → סוגר (במחשב)
- [ ] התמונה נשארת באיכות טובה גם בגדול
- [ ] גלילה ברקע נחסמת בזמן שהlightbox פתוח
- [ ] בtouch (טלפון) — Tap בכל מקום ברקע סוגר

## DO NOT

- אל תיגע ב-`ProjectDataExportTab.js` — שם target=_blank תקין (להורדה של export)
- אל תיגע ב-PhotoThumbnail במקומות אחרים אם יש (לא מצאתי אבל בודק) — רק בStageDetailPage
- אל תעשה שינוי גלובלי לטיפול תמונות באפליקציה — רק לקומפוננטה הזו
- אל תוסיף ספרייה חיצונית ללייטבוקס (yet-another-image-viewer וכו') — הקומפוננטה הזו פשוטה מספיק לכתיבה ידנית

## Standing rule

Replit עורך קבצים בלבד. **לא commit, לא push, לא deploy.**

אחרי Build → אני (Zahi) אריץ `./deploy.sh --stag`. אחרי אימות → `./deploy.sh --prod`.

**הערה:** זה שינוי frontend בלבד. ה-`./deploy.sh` יעלה אותו דרך Cloudflare Pages + Capgo OTA, אז גם המכשירים הניידים יקבלו את התיקון אוטומטית.

## Commit message

```
StageDetailPage: open photos in modal lightbox instead of new browser tab

Clicking a QC inspection photo previously navigated the user to the
raw S3 URL in a new tab — taking them out of the app with no easy
way back. Replace <a target="_blank"> with a button that opens an
in-app modal lightbox.

The PhotoLightbox component:
- Fullscreen black backdrop with blur
- Image centered, contained to viewport
- Close on backdrop click, X button, or ESC key
- Locks body scroll while open
- No external dependencies

Affects only PhotoThumbnail in StageDetailPage.js. ProjectDataExportTab
target=_blank links unchanged (those are for downloads).
```

מצופה זמן: 20-30 דקות. שינוי frontend בקובץ אחד, פשוט וברור.
