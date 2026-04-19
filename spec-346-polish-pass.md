# #346 — Polish Pass (typography, neutral pills, stat cards, breadcrumbs, skeletons, microcopy)

> **עודכן 17/04/2026:** Line numbers אומתו מחדש מול הקוד הנוכחי. STATUS_LABELS לא קיים ב‑ProjectControlPage — חפש status pills ידנית. KIND_COLORS ב‑lines 65–74.
>
> **שינוי הסקופ (16/04/2026):** Task 7 (refactor של `button.jsx` מ‑h-9 ל‑h-11) **הוצא** מהספק הזה והועבר לספק נפרד — **#346B**. הסיבה: שינוי ה‑base size של ה‑Button משפיע על 50+ הופעות באפליקציה ודורש visual audit נפרד. אין לבצע אותו כחלק מ‑pass של polish.

## What & Why
לאחר שספק 345 (Quick Wins) סוגר את הליקויים החריפים ביותר, ספק 346 מעלה את האפליקציה מ‑6.8 ל‑7.6 — מהמראה של "סטארט‑אפ פונקציונלי" למראה של "מוצר B2B מהשורה הראשונה" (ה‑0.2 שחסר מגיע מ‑346B). זהו pass של "ליטוש": ייצוב סקאלת טיפוגרפיה, האחדת pills, הפיכת stat cards מ‑Vegas ל‑monochrome עם type hierarchy, breadcrumbs בכל היררכיה, skeleton loaders במקום loaders עגולים, ומיקרו‑קופי שמדבר בשפה אנושית. צפי ~50 שעות. אין שינויי backend בכלל. אין ארכיטקטורה חדשה.

## Done looks like
- כל טקסט באפליקציה משתמש בסקאלה: `text-xs (12) / text-sm (14) / text-base (16) / text-lg (18) / text-2xl (24) / text-3xl (32)`
- ה‑Stat Cards (פתוחות / בטיפול / סגורות) הופכות מ‑3 צבעים שונים ל‑neutral עם number כסקאלה ראשית והאיקון משני
- כל ה‑pills של קטגוריה (חשמל, אינסטלציה, צבע…) משתמשים ב‑palette אחיד של 2 גוונים: `slate-100 + slate-700` (לא 7 צבעים שונים)
- כל ה‑status pills (פתוח / שויך / בביצוע / סגור) עוברים מצבעי pastel רגילים ל‑variant אחיד עם dot צבעוני קטן ואותו רקע אפור
- בכל עמוד עומק (Building → Floor → Unit → Task) מופיעים breadcrumbs בראש העמוד עם separator `›` ו‑hover state
- כל async data fetch ראשי מציג Skeleton במקום `<Loader2 spin />` ממורכז (השאר Loader2 רק לפעולות קצרות כמו submit)
- (הועבר לספק 346B) — שינוי `button.jsx` base size לא בסקופ של הספק הזה
- 6 strings של מיקרו‑קופי מתעדכנים לטון אנושי יותר (ראה Task 8)
- אין רגרסיה ב‑Quick Wins של ספק 345

## Out of scope
- אין להוסיף Dark Mode (זה ספק 347)
- אין לבנות סיידבר Desktop חדש (זה ספק 347)
- אין לגעת ב‑routing
- אין לגעת ב‑state management
- אין לגעת ב‑backend
- אין להוסיף Storybook או ספרייה חדשה
- אין לבצע migration של icons (Lucide נשאר Lucide)
- אין לכתוב tests חדשים (יש בדיקות ידניות ב‑VERIFY)

## Tasks

### Task 1 — סקאלת טיפוגרפיה אחידה ב‑`tailwind.config.js`
**File:** `frontend/tailwind.config.js`

הוסף את הסקאלה הבאה ל‑`theme.extend.fontSize`:

```js
fontSize: {
  // BrikOps unified type scale
  'caption': ['12px', { lineHeight: '16px', letterSpacing: '0.01em' }],
  'body-sm': ['14px', { lineHeight: '20px' }],
  'body':    ['16px', { lineHeight: '24px' }],
  'subhead': ['18px', { lineHeight: '26px', fontWeight: '600' }],
  'title':   ['24px', { lineHeight: '32px', fontWeight: '700' }],
  'display': ['32px', { lineHeight: '40px', fontWeight: '700', letterSpacing: '-0.01em' }],
}
```

**אסור** למחוק את ה‑sizes של Tailwind ה‑default (`text-xs`, `text-sm` וכו') — הם נשארים כדי לא לשבור קבצים קיימים. הסקאלה החדשה היא אופציונלית ומשמשת לקבצים שנעדכן ב‑Tasks 2–4.

```bash
cat frontend/tailwind.config.js | head -40
```

### Task 2 — Stat Cards Neutral Refactor
**File:** `frontend/src/pages/UnitDetailPage.js` lines 149–172
**File:** `frontend/src/pages/BuildingDefectsPage.js` (חפש `grid-cols-3 gap-3 text-center`)
**File:** `frontend/src/pages/ProjectControlPage.js` (חפש `grid-cols-3` או `grid-cols-4` של KPI)

```bash
grep -n "grid-cols-3\|grid-cols-4" frontend/src/pages/UnitDetailPage.js frontend/src/pages/BuildingDefectsPage.js frontend/src/pages/ProjectControlPage.js | head -20
```

BEFORE (UnitDetailPage.js 149–172):
```jsx
<div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
  <div className="grid grid-cols-3 gap-3 text-center">
    <div className="space-y-1">
      <div className="flex items-center justify-center gap-1 text-red-500">
        <AlertTriangle className="w-4 h-4" />
      </div>
      <div className="text-2xl font-bold text-slate-800">{kpi.open}</div>
      <div className="text-xs text-slate-500">פתוחות</div>
    </div>
    {/* in_progress with text-blue-500 */}
    {/* closed with text-green-500 */}
  </div>
</div>
```

AFTER (כל ה‑3 כרטיסים זהים בפורמט, רק הערך משתנה):
```jsx
<div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
  <div className="grid grid-cols-3 divide-x divide-slate-100" dir="ltr">
    <StatCard label="פתוחות" value={kpi.open} />
    <StatCard label="בטיפול" value={kpi.in_progress} />
    <StatCard label="סגורות" value={kpi.closed} />
  </div>
</div>
```

צור קומפוננטה חדשה `frontend/src/components/StatCard.jsx` (קובץ חדש):
```jsx
import React from 'react';

const StatCard = ({ label, value }) => (
  <div className="px-3 text-center" dir="rtl">
    <div className="text-3xl font-bold text-slate-900 tabular-nums leading-none">
      {value ?? 0}
    </div>
    <div className="text-xs text-slate-500 mt-1.5 font-medium">{label}</div>
  </div>
);

export default StatCard;
```

**עיקרון:** המספר הוא ה‑hero. אין צבע על האייקון. `tabular-nums` מבטיח שמספרים בגודל זהה. ה‑divider מוסיף מבנה חזותי בלי צבע.

החלף את 3 הופעות של ה‑grid שלוש‑עמודות ב‑UnitDetailPage / BuildingDefectsPage / ProjectControlPage (אם יש שם blocks דומים).

### Task 3 — Status Pills עם Dot
**File:** `frontend/src/pages/UnitDetailPage.js` lines 14–28 (`STATUS_LABELS`, `PRIORITY_CONFIG`)
**File:** `frontend/src/pages/ProjectControlPage.js` (⚠️ אין STATUS_LABELS בקובץ — חפש status pills ידנית)
**File:** `frontend/src/pages/ProjectTasksPage.js` (אם יש status pills)

צור קומפוננטה חדשה `frontend/src/components/StatusPill.jsx`:
```jsx
import React from 'react';

const STATUS_DOT = {
  open:           'bg-red-500',
  assigned:       'bg-orange-500',
  in_progress:    'bg-blue-500',
  waiting_verify: 'bg-purple-500',
  closed:         'bg-emerald-500',
  reopened:       'bg-amber-500',
};

const STATUS_LABEL = {
  open:           'פתוח',
  assigned:       'שויך',
  in_progress:    'בביצוע',
  waiting_verify: 'ממתין לאימות',
  closed:         'סגור',
  reopened:       'נפתח מחדש',
};

const StatusPill = ({ status, className = '' }) => {
  const dot = STATUS_DOT[status] || 'bg-slate-400';
  const label = STATUS_LABEL[status] || status;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[11px] font-medium ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
};

export default StatusPill;
```

החלף ב‑UnitDetailPage.js את הקטע סביב line 280–282:
```jsx
// BEFORE
<span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${statusInfo.color}`}>
  {statusInfo.label}
</span>

// AFTER
<StatusPill status={task.status} />
```

הוסף `import StatusPill from '../components/StatusPill';` בראש הקובץ.

**אסור** למחוק את `STATUS_LABELS` הישן ב‑UnitDetailPage.js — תמשיך להשתמש בו לדברים אחרים אם צריך, אבל ה‑pill עצמו מגיע מה‑קומפוננטה.

### Task 4 — Category Pills Unified Neutral
**File:** `frontend/src/pages/UnitDetailPage.js` line 283
**File:** כל מקום שמציג `tCategory(...)` עם רקע צבעוני

```bash
grep -rn "tCategory\|residential.*bg-emerald\|service.*bg-purple" frontend/src/pages/ frontend/src/components/ | grep -v node_modules | head -20
```

החלף את כל ה‑category pills מ‑7 צבעים שונים ל‑slate אחיד:

BEFORE:
```jsx
<span className="text-[10px] text-slate-400">{tCategory(task.category)}</span>
```

AFTER:
```jsx
<span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium">
  {tCategory(task.category)}
</span>
```

ולגבי מיפויי הצבעים ב‑ProjectControlPage.js (lines ~64–75 — `residential: bg-emerald-100`, `service: bg-purple-100`, `parking: bg-cyan-100` וכו'):
- אם זה משמש כ‑filter chip → השאר. שם הצבע מבדיל בין סוגים בעמוד אחד.
- אם זה pill בכרטיס פריט → החלף לכולם ב‑`bg-slate-100 text-slate-700`. הסוג צריך להיות ניתן לקריאה אבל לא להפוך כל כרטיס לקרנבל.

### Task 5 — Breadcrumbs קומפוננטה
**File חדש:** `frontend/src/components/Breadcrumbs.jsx`
**File:** `frontend/src/pages/UnitDetailPage.js` lines 137–141 (כרגע יש crumbs inline ב‑header)
**File:** `frontend/src/pages/BuildingDefectsPage.js` (אותו pattern בכותרת)

צור `Breadcrumbs.jsx`:
```jsx
import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';

const Breadcrumbs = ({ items = [], className = '' }) => (
  <nav className={`flex items-center gap-1 text-xs text-slate-500 overflow-x-auto whitespace-nowrap ${className}`} aria-label="Breadcrumb" dir="rtl">
    {items.map((item, idx) => {
      const isLast = idx === items.length - 1;
      return (
        <React.Fragment key={idx}>
          {idx > 0 && <ChevronLeft className="w-3 h-3 text-slate-300 flex-shrink-0" />}
          {item.to && !isLast ? (
            <Link to={item.to} className="hover:text-amber-600 hover:underline transition-colors truncate max-w-[120px]">
              {item.label}
            </Link>
          ) : (
            <span className={`truncate max-w-[140px] ${isLast ? 'text-slate-700 font-medium' : ''}`}>
              {item.label}
            </span>
          )}
        </React.Fragment>
      );
    })}
  </nav>
);

export default Breadcrumbs;
```

ב‑UnitDetailPage.js, החלף את ה‑crumbs ה‑inline (lines 137–141) ב:
```jsx
<Breadcrumbs
  items={[
    { label: project?.name, to: `/projects/${projectId}` },
    { label: building?.name, to: `/projects/${projectId}/buildings/${building?.id}` },
    { label: floor?.name },
    { label: formatUnitLabel(effectiveLabel) },
  ].filter(i => i.label)}
  className="text-amber-100"
/>
```

(העברנו את ה‑breadcrumbs לתוך הכותרת הכתומה — הצבע `text-amber-100` שומר על ניגודיות מספיק על gradient כתום).

חזור על הפעולה ב‑BuildingDefectsPage.js.

### Task 6 — Skeleton Loaders במקום Loader2 ממורכז
**File:** `frontend/src/pages/UnitDetailPage.js` lines 100–106, 249–252
**File:** `frontend/src/pages/ProjectControlPage.js` (חיפוש למטה)

```bash
grep -n "Loader2.*animate-spin\|min-h-screen.*flex.*items-center.*justify-center" frontend/src/pages/UnitDetailPage.js frontend/src/pages/ProjectControlPage.js frontend/src/pages/MyProjectsPage.js | head -20
```

צור קומפוננטה `frontend/src/components/ListSkeleton.jsx`:
```jsx
import React from 'react';
import { Skeleton } from './ui/skeleton';

const ListSkeleton = ({ rows = 5 }) => (
  <div className="space-y-2" aria-busy="true" aria-label="טוען...">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="bg-white rounded-xl border border-slate-200 p-3.5">
        <Skeleton className="h-4 w-2/3 mb-2" />
        <Skeleton className="h-3 w-full mb-1" />
        <Skeleton className="h-3 w-4/5 mb-3" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-14 rounded-full" />
          <Skeleton className="h-5 w-12 rounded-full" />
        </div>
      </div>
    ))}
  </div>
);

export default ListSkeleton;
```

**רק** למקומות הבאים החלף את ה‑full‑page Loader2 ב‑Skeleton:
- UnitDetailPage.js — כשטוען את רשימת הליקויים (lines 249–252):
  ```jsx
  // BEFORE
  {tasksLoading ? (
    <div className="flex justify-center py-8">
      <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
    </div>
  ) : ...

  // AFTER
  {tasksLoading ? <ListSkeleton rows={4} /> : ...
  ```
- BuildingDefectsPage.js — אותו pattern ברשימת tasks
- ProjectControlPage.js — רק ב‑3 המקומות הראשיים שבהם נטענת רשימה ארוכה

**אסור** להחליף את ה‑Loader2 שמופיע בתוך כפתור Submit (lines 318, 702, 857, 860, 966, 969, 1156, 1167, 1222 ב‑ProjectControlPage.js). הוא נשאר — הוא משדר action בתהליך, לא מסך טוען.

ב‑UnitDetailPage.js lines 100–106 (full page loading state) — החלף ל:
```jsx
if (loading) {
  return (
    <div className="min-h-screen bg-slate-50 pb-24" dir="rtl">
      <div className="bg-gradient-to-l from-amber-500 to-amber-600 text-white">
        <div className="max-w-lg mx-auto px-4 py-3 h-14" />
      </div>
      <div className="max-w-lg mx-auto px-4 mt-4">
        <Skeleton className="h-24 w-full rounded-xl mb-4" />
        <ListSkeleton rows={3} />
      </div>
    </div>
  );
}
```

(שומר על המבנה החזותי של הדף — אין "קפיצה" כשהתוכן נטען.)

### Task 7 — [הועבר לספק 346B]
שינוי ה‑base size של `button.jsx` הועבר ל‑**ספק 346B נפרד** עקב סיכון רגרסיה גבוה. דלג ל‑Task 8.

**אסור** לגעת ב‑`frontend/src/components/ui/button.jsx` בספק הזה. לא בגדלים, לא ב‑transition, לא ב‑variants.

ההוספה היחידה המותרת ל‑Button בספק הזה: **אם** משתמשים ב‑Button בקובץ חדש (StatCard, StatusPill, Breadcrumbs, ListSkeleton) — להעביר size מפורש (`size="lg"`) במקום להסתמך על default.

### Task 8 — Microcopy Refresh
**Files:** עדכן את ההופעות הבאות (חפש exact match):

```bash
grep -rn "אין ליקויים לדירה זו\|אין ליקויים התואמים לפילטר\|דירה לא נמצאה\|שגיאה בטעינת" frontend/src/pages/ frontend/src/components/ | head -10
```

| BEFORE | AFTER |
|---|---|
| "אין ליקויים לדירה זו" | "הדירה נקייה — לא דווחו ליקויים" |
| "אין ליקויים התואמים לפילטר" | "אין תוצאות לפילטר הזה — נסה לנקות חלק מהבחירות" |
| "דירה לא נמצאה" | "הדירה הזו כבר לא קיימת או שאין לך הרשאה" |
| "שגיאה בטעינת פרטי דירה" | "לא הצלחנו לטעון את הדירה. רענן את הדף ונסה שוב" |
| "שגיאה בטעינת ליקויים" | "לא הצלחנו לטעון את הליקויים. בדוק חיבור ונסה שוב" |
| "צור בניין" (כפתור) | "הוסף בניין" |

**עיקרון:** לא להאשים את המשתמש ("שגיאה" → "לא הצלחנו"). לא לכתוב הוראה צבאית ("צור" → "הוסף"). הסבר למה ומה לעשות.

החלף בכל הקבצים שבהם מופיעים, **בדיוק** האחד‑לאחד שבטבלה.

### Task 9 — Hover/Press States על כל כרטיס
**File:** `frontend/src/pages/UnitDetailPage.js` line 271

BEFORE:
```jsx
className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right cursor-pointer hover:shadow-md transition-shadow active:bg-slate-50"
```

AFTER:
```jsx
className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right cursor-pointer hover:shadow-md hover:border-slate-300 active:bg-slate-50 active:scale-[0.99] transition-all duration-200"
```

הוסף `hover:border-slate-300` + `active:scale-[0.99]` + שינוי ל‑`transition-all` בכל ה‑task cards / list items שבדפים:
- UnitDetailPage.js (line 271)
- BuildingDefectsPage.js (כל card של task)
- MyProjectsPage.js (project cards)
- ProjectControlPage.js (3 הופעות עיקריות של list item)

```bash
grep -rn "rounded-xl border border-slate-200.*hover:shadow" frontend/src/pages/ | head -10
```

### Task 10 — Empty States — Illustrations Hint
**File:** `frontend/src/pages/UnitDetailPage.js` lines 254–261

BEFORE:
```jsx
<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
  <div className="text-slate-400 mb-2">
    <CheckCircle2 className="w-10 h-10 mx-auto" />
  </div>
  <p className="text-sm text-slate-500">
    {activeFilters > 0 ? 'אין ליקויים התואמים לפילטר' : 'אין ליקויים לדירה זו'}
  </p>
</div>
```

AFTER:
```jsx
<div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
  <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-emerald-50 flex items-center justify-center">
    <CheckCircle2 className="w-8 h-8 text-emerald-500" strokeWidth={1.5} />
  </div>
  <h3 className="text-base font-semibold text-slate-800 mb-1">
    {activeFilters > 0 ? 'אין תוצאות' : 'הדירה נקייה'}
  </h3>
  <p className="text-sm text-slate-500">
    {activeFilters > 0
      ? 'אין ליקויים שתואמים לפילטר. נסה לנקות חלק מהבחירות.'
      : 'לא דווחו ליקויים. ברגע שיהיו — הם יופיעו כאן.'}
  </p>
</div>
```

חזור על הפעולה לכל empty state במערכת (פרויקט בלי ליקויים, חיפוש ריק, רשימת חברות ריקה).

```bash
grep -rn "אין ליקויים\|אין נתונים\|אין תוצאות\|לא נמצאו" frontend/src/pages/ frontend/src/components/ | head -20
```

## Relevant files
- `frontend/tailwind.config.js` (Task 1)
- `frontend/src/components/StatCard.jsx` (Task 2 — חדש)
- `frontend/src/components/StatusPill.jsx` (Task 3 — חדש)
- `frontend/src/components/Breadcrumbs.jsx` (Task 5 — חדש)
- `frontend/src/components/ListSkeleton.jsx` (Task 6 — חדש)
- `frontend/src/components/ui/skeleton.jsx` (קיים, נשאר ללא שינוי)
- `frontend/src/components/ui/button.jsx` (Task 7)
- `frontend/src/pages/UnitDetailPage.js` lines 14–28, 100–106, 137–141, 149–172, 249–252, 254–261, 271, 280–282
- `frontend/src/pages/BuildingDefectsPage.js` (אותם patterns של UnitDetailPage)
- `frontend/src/pages/ProjectControlPage.js` lines 65–74 (KIND_COLORS map), grid blocks
- `frontend/src/pages/MyProjectsPage.js` (project cards hover)
- `frontend/src/pages/ProjectTasksPage.js` (status pills if used)

## DO NOT
- ❌ אל תוסיף `dark:` variants — Dark Mode הוא ספק 347
- ❌ אל תכניס סיידבר חדש או שינוי layout כללי — זה ספק 347
- ❌ אל תיגע ב‑routing
- ❌ אל תיגע ב‑i18n / locale files
- ❌ אל תיגע ב‑backend
- ❌ אל תוסיף Storybook
- ❌ אל תוסיף תלויות חדשות (`framer-motion`, `react-loading-skeleton` וכו') — נשאר עם Tailwind בלבד
- ❌ אל תשנה את `bg-amber-500` ל‑hex code חדש או למשתנה CSS חדש — אין tokens חדשים בספק הזה
- ❌ אל תעשה rename של קבצים קיימים
- ❌ אל תרפקטר את ה‑`useDefectCount` או logic של state
- ❌ אל תיגע ב‑`PhotoAnnotation.js` (יש שם portal/event quirks ידועים)
- ❌ אל תוסיף animations יותר מ‑200ms — זה pass של polish, לא של motion design
- ❌ אל תשנה את `Loader2` ב‑submit buttons — הוא נשאר באותם 9+ מקומות

## VERIFY

### 1. Typography Scale
- פתח את DevTools → Computed
- לחץ על H1 בכותרת ProjectControl: צריך להיות 24–32px
- לחץ על body text של task title: צריך להיות 14px (`text-sm`)
- לחץ על pill ('פתוח'): צריך להיות 11–12px

### 2. Stat Cards
- היכנס לדירה
- 3 הכרטיסים נראים זהים בפורמט (אין צבעים שונים על האייקון)
- המספר גדול ובולט (24–30px)
- ה‑label מתחת בגודל 12px
- divider אנכי בין כל שניים

### 3. Status Pills
- בכל קלף ליקוי בדף הדירה — pill חדש עם dot צבעוני קטן (1.5×1.5) ורקע אפור
- ב‑hover אין שינוי צבע (הוא passive)
- בעמוד ProjectControl — אותו pill מופיע (לא הישן)

### 4. Category Pills
- כל ה‑category pills בעמוד הדירה — slate‑100 / slate‑600
- ב‑filter chips נשמרת אבחנת הצבע בין residential/service/parking/etc

### 5. Breadcrumbs
- בעמוד דירה: "פרויקט › בניין › קומה › דירה" עם chevron עדין בין כל שניים
- האחרון לא לחיץ (ה‑page הנוכחי), היתר לחיצים → navigate
- Hover על breadcrumb → underline + שינוי לכתום

### 6. Skeletons
- רענן את עמוד הדירה — לפני שהליקויים נטענים: 3-4 כרטיסי skeleton אפורים פולסים
- לא צריכה להיות "קפיצה" של layout כשהתוכן נטען
- כפתור Submit במודאל ליקוי חדש — Loader2 ספין נשאר (לא Skeleton)

### 7. Button
- ✅ אין שינוי בגודל הכפתורים בספק הזה — דחוי לספק 346B
- ודא שלא נגעת ב‑`frontend/src/components/ui/button.jsx` (git diff שלו צריך להיות ריק)

### 8. Microcopy
- פרויקט בלי ליקויים → "הדירה נקייה — לא דווחו ליקויים" (לא "אין ליקויים לדירה זו")
- פילטר ריק → "אין תוצאות לפילטר הזה — נסה לנקות חלק מהבחירות"
- כפתור הוספת בניין → "הוסף בניין" (לא "צור בניין")

### 9. Hover/Press
- hover על task card — shadow + border darker
- click → scale חלק ל‑99% ל‑200ms
- ב‑mobile (touch) — active:bg-slate-50 פועל

### 10. Empty States
- icon בתוך עיגול עדין (rounded-full bg-emerald-50)
- כותרת bold + תיאור רך מתחת
- הדף לא ריק חזותית

## Risks
- **Skeleton בזמן טעינה** עלול להציג מבנה שונה ממה שמופיע בפועל אם רשימה ריקה. הפתרון: להציג את ה‑empty state רק אחרי `!loading && tasks.length === 0`.
- **Breadcrumbs בכותרת כתומה** דורשים `text-amber-100` כדי לשמור ניגודיות 4.5:1. בדוק ידנית עם DevTools → Accessibility.
- **StatusPill / Category pills** — חובה לעבור ידנית ולא search‑and‑replace, אחרת מפספסים filter chips שצריכים להישאר צבעוניים.
- **קומפוננטות חדשות (StatCard, StatusPill, Breadcrumbs, ListSkeleton)** דורשות import path נכון. בדוק שאין circular imports.

---

**זמן עבודה משוער:** ~50 שעות (ירד מ‑60 בעקבות הוצאת Task 7)
**תוצאה צפויה:** ציון UX יעלה מ‑6.8 ל‑7.6
**תלות:** ספק 345 חייב להיות merged קודם
**ספק עוקב מקביל:** 346B — Button Component Resize Audit (ניתן לבצע בו זמנית או אחרי)
