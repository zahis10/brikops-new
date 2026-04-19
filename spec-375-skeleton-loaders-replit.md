# Task #375 (Spec #346 Task 6) — Skeleton loaders אחידים לרשימת ליקויים

## What & Why
היום יש שני שימושים של `TaskCardSkeleton` כפולים inline בקבצים שונים, ועוד שני מקומות שמציגים `Loader2` spinner ריק כש-tasksLoading למרות שהם רשימת ליקויים שיכולה להציג skeleton.

**מצב נוכחי:**
- **ProjectTasksPage.js:55-73** — `function TaskCardSkeleton()` inline. משומש 7 פעמים (lines 326-329, 466-468). **מועתק לקומפוננטה.**
- **UnitDetailPage.js:249-252** — `<Loader2 className="w-6 h-6 text-amber-500 animate-spin" />` כש-`tasksLoading`. **משודרג ל-3× TaskCardSkeleton.**
- **ApartmentDashboardPage.js:655-658** — אותו דבר בדיוק. **משודרג ל-3× TaskCardSkeleton.**

**מטרה:** קומפוננטה אחת `<TaskCardSkeleton />` ב-`components/`, 3 עמודים שמייבאים אותה. UX אחיד לטעינת רשימת ליקויים.

## Done looks like
- קובץ חדש: `frontend/src/components/TaskCardSkeleton.jsx`
- ProjectTasksPage: מחיקת ה-`function TaskCardSkeleton()` המקומי, import של החדש. 7 השימושים נשארים.
- UnitDetailPage: ה-Loader2 spinner מוחלף ב-3× `<TaskCardSkeleton />` בתוך `<div className="space-y-2">`.
- ApartmentDashboardPage: אותו דבר.
- Build עובר נקי.
- ויזואלית: ProjectTasks נראה זהה ל-לפני (אותו skeleton, רק import אחר). UnitDetail/Apartment — במקום ספינר במרכז יש 3 כרטיסי שלד שגוניים.

## Out of scope
- ❌ **ContractorDashboard.js:80-100** — יש שם `TaskCardSkeleton` בעל shape שונה (border-r-4 status indicator + שורת action buttons בגובה h-10). **לא בסקופ.** ייתכן spec נפרד בעתיד.
- ❌ **UnitDetailPage.js:103** — `Loader2 w-8 h-8` כש-`loading` (page-level loader, לפני header נטען). זה מסך טעינה כללי — להשאיר.
- ❌ **ApartmentDashboardPage.js:264** — אותו דבר (page-level loader). להשאיר.
- ❌ **כל ה-Loader2 inline בכפתורים** (`spareTilesSaving`, `submitting`, `loading` בתוך כפתורים) — נכון בהקשר. להשאיר.
- ❌ **`frontend/src/components/ui/skeleton.jsx`** — primitive shadcn לא בשימוש. ספין נפרד אם נרצה לעבור ל-primitive הזה.
- ❌ אין שינוי ב-API של TaskCardSkeleton — בלי props (אין variants, אין `count`, אין `className`).
- ❌ אין שינוי ב-empty state או ב-actual TaskCard rendering.

## Tasks

### 1 — צור `frontend/src/components/TaskCardSkeleton.jsx`

זה byte-identical לפונקציה שב-ProjectTasksPage היום (lines 55-73), רק עטוף ב-export.

```jsx
import React from 'react';
import { Card } from './ui/card';

const TaskCardSkeleton = () => {
  return (
    <Card className="p-3">
      <div className="animate-pulse">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            <div className="h-4 bg-slate-200 rounded w-3/4 mb-1"></div>
            <div className="h-3 bg-slate-100 rounded w-1/2"></div>
          </div>
          <div className="h-5 bg-slate-200 rounded w-16 mr-2"></div>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-4 bg-slate-100 rounded w-16"></div>
          <div className="h-4 bg-slate-100 rounded w-12"></div>
        </div>
      </div>
    </Card>
  );
};

export default TaskCardSkeleton;
```

### 2 — `frontend/src/pages/ProjectTasksPage.js`

הוסף import ליד שאר ה-component imports בראש הקובץ:
```jsx
import TaskCardSkeleton from '../components/TaskCardSkeleton';
```

מחק את הפונקציה המקומית (lines 55-73):

BEFORE:
```jsx
function TaskCardSkeleton() {
  return (
    <Card className="p-3">
      <div className="animate-pulse">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            <div className="h-4 bg-slate-200 rounded w-3/4 mb-1"></div>
            <div className="h-3 bg-slate-100 rounded w-1/2"></div>
          </div>
          <div className="h-5 bg-slate-200 rounded w-16 mr-2"></div>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-4 bg-slate-100 rounded w-16"></div>
          <div className="h-4 bg-slate-100 rounded w-12"></div>
        </div>
      </div>
    </Card>
  );
}
```

AFTER:
```jsx
// (מחוק לגמרי — הקומפוננטה הגיעה דרך import)
```

7 השימושים של `<TaskCardSkeleton />` (lines 326-329, 466-468) **נשארים בדיוק כמו שהם** — מה שנקרא הוא עכשיו ה-import במקום הפונקציה המקומית.

### 3 — `frontend/src/pages/UnitDetailPage.js`

הוסף import בסוף בלוק ה-component imports (אחרי `import NewDefectModal from '../components/NewDefectModal';`):
```jsx
import TaskCardSkeleton from '../components/TaskCardSkeleton';
```

מצא ב-grep:
```bash
grep -n "tasksLoading ?" frontend/src/pages/UnitDetailPage.js
```

החלף את הבלוק (4 שורות, line ~249):

BEFORE:
```jsx
        {tasksLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : tasks.length === 0 ? (
```

AFTER:
```jsx
        {tasksLoading ? (
          <div className="space-y-2">
            <TaskCardSkeleton />
            <TaskCardSkeleton />
            <TaskCardSkeleton />
          </div>
        ) : tasks.length === 0 ? (
```

**שים לב:** ה-`Loader2` import נשאר — עדיין משומש ב-line 103 (page-level loader). אל תמחק אותו מה-import.

### 4 — `frontend/src/pages/ApartmentDashboardPage.js`

הוסף import ליד שאר ה-component imports (אחרי `import UnitTypeEditModal, { TAG_MAP } from '../components/UnitTypeEditModal';`):
```jsx
import TaskCardSkeleton from '../components/TaskCardSkeleton';
```

מצא ב-grep:
```bash
grep -n "tasksLoading ?" frontend/src/pages/ApartmentDashboardPage.js
```

החלף את הבלוק (4 שורות, line ~655):

BEFORE:
```jsx
        {tasksLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : filteredTasks.length === 0 ? (
```

AFTER:
```jsx
        {tasksLoading ? (
          <div className="space-y-2">
            <TaskCardSkeleton />
            <TaskCardSkeleton />
            <TaskCardSkeleton />
          </div>
        ) : filteredTasks.length === 0 ? (
```

**שים לב:** ה-`Loader2` import נשאר — עדיין משומש ב-line 264 (page-level loader) ו-line 565 (כפתור spareTilesSaving). אל תמחק אותו מה-import.

## DO NOT
- ❌ אל תיגע ב-`ContractorDashboard.js` — ה-TaskCardSkeleton שם עם action buttons + border-r-4. shape אחר. חוץ מסקופ.
- ❌ אל תיגע ב-`Loader2` ב-UnitDetailPage:103 או ApartmentDashboardPage:264 — אלה page-level loaders, לפני שה-header נטען. נכון להשאיר ספינר.
- ❌ אל תיגע ב-`Loader2` בתוך כפתורים (saving, submitting) — נכון בהקשר.
- ❌ אל תוסיף props ל-TaskCardSkeleton (`count`, `variant`, `className`). זה קומפוננטה דממית לחלוטין.
- ❌ אל תייבא TaskCardSkeleton בקבצים שלא רשומים כאן.
- ❌ אל תשנה את `space-y-2` או את ה-padding של ה-container — match לרשימת הליקויים האמיתית.
- ❌ אל תשנה את כמות ה-skeleton cards מ-3. שלוש זה הגודל הנכון — לא יותר מדי, לא מעט מדי.
- ❌ אל תוסיף `<Card>` במקום `<div className="space-y-2">` — ה-Card כבר בתוך כל TaskCardSkeleton.
- ❌ אל תמחק את `Loader2` מה-imports של UnitDetailPage / ApartmentDashboardPage.
- ❌ אל תיגע ב-`/components/ui/skeleton.jsx` — לא חלק מה-spec.
- ❌ אל תשנה את ה-empty state (`tasks.length === 0` block).

## VERIFY
1. `git status` — בדיוק 4 קבצים: 1 חדש (`TaskCardSkeleton.jsx`) + 3 modified (`ProjectTasksPage.js`, `UnitDetailPage.js`, `ApartmentDashboardPage.js`).
2. `cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build` — חייב לעבור.
3. `grep -n "import TaskCardSkeleton" frontend/src/pages/*.js` — חייב להחזיר בדיוק 3 תוצאות (ProjectTasksPage, UnitDetailPage, ApartmentDashboardPage).
4. `grep -n "function TaskCardSkeleton" frontend/src/pages/*.js` — חייב להחזיר 1 תוצאה בלבד (ContractorDashboard.js שלא נגענו בו). אם חוזר 2 → ProjectTasksPage לא נוקה.
5. `grep -n "<TaskCardSkeleton" frontend/src/pages/ProjectTasksPage.js` — חייב להחזיר 7 תוצאות (lines 326-329, 466-468 — לא לזוז).
6. `grep -n "<TaskCardSkeleton" frontend/src/pages/UnitDetailPage.js` — חייב להחזיר 3 תוצאות.
7. `grep -n "<TaskCardSkeleton" frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר 3 תוצאות.
8. `grep -n "Loader2" frontend/src/pages/UnitDetailPage.js` — חייב להחזיר 2 תוצאות (line 9 import + line 103 page-level). השלישי (line 251) הוסר.
9. `grep -n "Loader2" frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר 3 תוצאות (line 13 import + line 264 page-level + line 565 button). הרביעי (line 657) הוסר.
10. `grep -n "Loader2" frontend/src/pages/ContractorDashboard.js | wc -l` — צריך להישאר זהה למה שהיה לפני. לא נגעתם בקובץ הזה.
11. `git diff backend/` — ריק.
12. אחרי deploy: פתח דירה עם ליקויים → רענן ב-throttle "Slow 3G" ב-DevTools → בעת tasksLoading=true אמור להופיע 3 skeleton cards (לא ספינר). עמודים: UnitDetail, ApartmentDashboard.
13. ProjectTasksPage: אותו skeleton כמו לפני (זהה ויזואלית — אם משהו שונה, ה-import לא תפס את הקומפוננטה הנכונה).
14. ContractorDashboard: ה-skeleton שלו לא השתנה (different file, different shape).

## Risks
🟢 נמוך מאוד.
- ProjectTasksPage: byte-identical refactor (אותו markup, רק import). אפס סיכון ויזואלי.
- UnitDetailPage / ApartmentDashboardPage: שינוי UX קל — ספינר → 3 skeleton cards. UX זהה למצב טעינה ב-ProjectTasksPage שכבר קיים בפרודקשן.
- אם משהו ייראה לא טוב → revert של 4 קבצים.

## Relevant files
- `frontend/src/components/TaskCardSkeleton.jsx` (חדש)
- `frontend/src/pages/ProjectTasksPage.js` (מחיקת lines 55-73 + import)
- `frontend/src/pages/UnitDetailPage.js` (החלפת lines 249-252 + import)
- `frontend/src/pages/ApartmentDashboardPage.js` (החלפת lines 655-658 + import)
