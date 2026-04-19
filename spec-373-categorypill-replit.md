# Task #373 (Spec #346 Task 4) — CategoryPill אחיד

## What & Why
היום `tCategory(task.category)` מוצג ב-5 מקומות ב-3 וריאציות שונות של סטיילינג:
- **UnitDetailPage** — `text-[10px] text-slate-400` (בלי רקע, סתם טקסט אפור — חלש)
- **ApartmentDashboardPage**, **ContractorDashboard** — `bg-slate-100 text-slate-600` עם padding/size שונה
- **ProjectTasksPage**, **ProjectControlPage** — `bg-slate-100` בלי text color מפורש

המעבר: כולם הופכים לקומפוננטה אחת `<CategoryPill>` עם סטיילינג אחיד — `bg-slate-100 text-slate-600 text-[11px] rounded-md`.

ויזואלי בלבד. אפס שינוי data flow / state / props אחרים.

## Done looks like
- קובץ חדש: `frontend/src/components/CategoryPill.jsx`
- 5 שימושים מוחלפים ל-`<CategoryPill>{tCategory(task.category)}</CategoryPill>`
- 5 imports נוספים בראש הקבצים
- Build עובר נקי
- ויזואלית: כל ה-category pills באפליקציה זהים

## Out of scope
- ❌ `TaskDetailPage.js:820` — pill בכותרת (header) של עמוד פרט המשימה. שונה בקונטקסט (לא ברשימה / כרטיס). **לא בסקופ.**
- ❌ `TaskDetailPage.js:1037` — `label={tCategory(task.category)}` של Select picker, לא pill. **לא בסקופ.**
- ❌ `KIND_COLORS` ב-ProjectControlPage.js (שורות 65-74) ושימושו בשורה 2322 — זה pill של "סוג קומה" (residential/service/parking/etc), vocabulary שונה לחלוטין מ-category. **לא בסקופ.**
- ❌ אין מחיקת `tCategory` או שינוי ב-i18n.
- ❌ אין הוספת props ל-CategoryPill מעבר ל-`children`, `className`.

## Tasks

### 1 — צור `frontend/src/components/CategoryPill.jsx`

```jsx
import React from 'react';

const CategoryPill = ({ children, className = '' }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[11px] font-medium whitespace-nowrap ${className}`}>
    {children}
  </span>
);

export default CategoryPill;
```

### 2 — `frontend/src/pages/UnitDetailPage.js`

הוסף import ליד import של StatusPill הקיים:
```jsx
import CategoryPill from '../components/CategoryPill';
```

מצא ב-grep:
```bash
grep -n "text-\[10px\] text-slate-400" frontend/src/pages/UnitDetailPage.js
```

החלף את הבלוק (3 שורות):

BEFORE:
```jsx
                        <span className="text-[10px] text-slate-400">
                          {tCategory(task.category)}
                        </span>
```

AFTER:
```jsx
                        <CategoryPill>{tCategory(task.category)}</CategoryPill>
```

### 3 — `frontend/src/pages/ApartmentDashboardPage.js`

הוסף import ליד import של StatusPill הקיים:
```jsx
import CategoryPill from '../components/CategoryPill';
```

מצא ב-grep:
```bash
grep -n "bg-slate-100 px-2 py-0.5 rounded text-slate-600" frontend/src/pages/ApartmentDashboardPage.js
```

החלף את הבלוק (3 שורות):

BEFORE:
```jsx
                        <span className="text-[10px] bg-slate-100 px-2 py-0.5 rounded text-slate-600">
                          {tCategory(task.category)}
                        </span>
```

AFTER:
```jsx
                        <CategoryPill>{tCategory(task.category)}</CategoryPill>
```

### 4 — `frontend/src/pages/ContractorDashboard.js`

הוסף import בראש הקובץ:
```jsx
import CategoryPill from '../components/CategoryPill';
```

מצא ב-grep:
```bash
grep -n "px-1.5 py-0.5 rounded bg-slate-100 text-slate-600" frontend/src/pages/ContractorDashboard.js
```

החלף את הבלוק (שורה אחת):

BEFORE:
```jsx
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{tCategory(task.category)}</span>
```

AFTER:
```jsx
                        <CategoryPill>{tCategory(task.category)}</CategoryPill>
```

### 5 — `frontend/src/pages/ProjectTasksPage.js`

הוסף import בראש הקובץ:
```jsx
import CategoryPill from '../components/CategoryPill';
```

מצא ב-grep:
```bash
grep -n "bg-slate-100 px-2 py-0.5 rounded\">{tCategory" frontend/src/pages/ProjectTasksPage.js
```

החלף את הבלוק (שורה אחת):

BEFORE:
```jsx
                    <span className="bg-slate-100 px-2 py-0.5 rounded">{tCategory(task.category)}</span>
```

AFTER:
```jsx
                    <CategoryPill>{tCategory(task.category)}</CategoryPill>
```

### 6 — `frontend/src/pages/ProjectControlPage.js`

הוסף import בראש הקובץ:
```jsx
import CategoryPill from '../components/CategoryPill';
```

מצא ב-grep:
```bash
grep -n "bg-slate-100 px-2 py-0.5 rounded\">{tCategory" frontend/src/pages/ProjectControlPage.js
```

החלף את הבלוק (שורה אחת):

BEFORE:
```jsx
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{tCategory(task.category)}</span>
```

AFTER:
```jsx
                      <CategoryPill>{tCategory(task.category)}</CategoryPill>
```

⚠️ **שים לב:** ProjectControlPage גדול (3,800+ שורות). יש בו גם `KIND_COLORS` (שורות ~65-74) שנגוע ב-line ~2322 — **אסור** לגעת בו, זה pill של סוג קומה (residential/service/etc), vocabulary שונה.

## DO NOT
- ❌ אל תיגע ב-`KIND_COLORS` או ב-`KIND_LABELS` ב-ProjectControlPage.js. אלה לא category pills — הם kind pills של סוג קומה. הצבע שלהם משמעותי (8 סוגים נפרדים בעמוד מבנה).
- ❌ אל תיגע ב-`TaskDetailPage.js` — ה-tCategory pill שם בכותרת עמוד פרט (text-xs, padding גדול), קונטקסט שונה.
- ❌ אל תוסיף `import CategoryPill` בקבצים שלא משנים אותם.
- ❌ אל תשנה את ה-API של i18n / tCategory.
- ❌ אל תוסיף props ל-CategoryPill חוץ מ-`children` ו-`className`.
- ❌ אל תיגע בשאר ה-pills בסביבה (status, priority, "מסירה" badge וכו').

## VERIFY
1. `git status` — בדיוק 6 קבצים: 1 חדש + 5 modified (UnitDetailPage, ApartmentDashboardPage, ContractorDashboard, ProjectTasksPage, ProjectControlPage).
2. `cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build` — חייב לעבור.
3. `grep -n "tCategory(task.category)" frontend/src/pages/UnitDetailPage.js frontend/src/pages/ApartmentDashboardPage.js frontend/src/pages/ContractorDashboard.js frontend/src/pages/ProjectTasksPage.js frontend/src/pages/ProjectControlPage.js` — חייב להחזיר בדיוק 5 תוצאות, **כולן בתוך `<CategoryPill>...</CategoryPill>`**.
4. `grep -n "import CategoryPill" frontend/src/pages/*.js` — חייב להחזיר 5 תוצאות.
5. `grep -n "KIND_COLORS\|KIND_LABELS" frontend/src/pages/ProjectControlPage.js | wc -l` — חייב להחזיר את אותו מספר כמו לפני (לא נמחק כלום).
6. `git diff backend/` — ריק.
7. `git diff frontend/src/pages/TaskDetailPage.js` — ריק (לא נגעו).
8. אחרי deploy: פתח דירה עם ליקויים → ה-category labels (חשמל, אינסטלציה וכו') הופכים ל-pill קטן עם רקע אפור-100, אחיד בכל המסכים.

## Risks
🟢 נמוך מאוד. ויזואלי בלבד, scope צר (5 מקומות), ה-CategoryPill טריוויאלי. אם משהו ייראה לא טוב → revert של 6 קבצים.

## Relevant files
- `frontend/src/components/CategoryPill.jsx` (חדש)
- `frontend/src/pages/UnitDetailPage.js`
- `frontend/src/pages/ApartmentDashboardPage.js`
- `frontend/src/pages/ContractorDashboard.js`
- `frontend/src/pages/ProjectTasksPage.js`
- `frontend/src/pages/ProjectControlPage.js`
