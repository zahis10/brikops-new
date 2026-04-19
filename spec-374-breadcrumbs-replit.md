# Task #374 (Spec #346 Task 5) — Breadcrumbs קומפוננטה

## What & Why
היום ה"breadcrumb" (פרויקט › בניין › קומה) משוכפל inline ב-3 כותרות עם אותו markup בדיוק:

- **UnitDetailPage:138-141** — `{project && <span>...} {building && <><span>›</span>...</>}` בתוך amber gradient header
- **UnitHomePage:128-132** — אותו דבר
- **ApartmentDashboardPage:365-369** — אותו דבר

3 כפילויות → קומפוננטה אחת `<Breadcrumbs>` שמקבלת `items` (array) ומרנדרת עם spacing/separator אחיד.

ויזואלי בלבד. אפס שינוי data flow / state.

## Done looks like
- קובץ חדש: `frontend/src/components/Breadcrumbs.jsx`
- 3 שימושים מוחלפים ל-`<Breadcrumbs items={[project?.name, building?.name, floor?.name]} className="text-amber-100" />`
- 3 imports נוספים בראש הקבצים
- Build עובר נקי
- ויזואלית: ה-breadcrumbs נראים זהים ל-לפני (אם משהו שונה — זה בעיה)

## Out of scope
- ❌ `FloorDetailPage.js:226-232` — breadcrumb עם icons (Building2, Layers) ב-slate-800 header. shape שונה (icons + text). **לא בסקופ.**
- ❌ `UnitPlansPage.js:363` — משתמש ב-`subtitleParts.join(' › ')` בתוך `<p>` עם `text-[11px]` ו-`truncate` (single line). visual שונה. **לא בסקופ.**
- ❌ `UnitQCSelectionPage.js:114` — לא breadcrumb, סתם status text ("X/Y הושלמו"). **לא בסקופ.**
- ❌ אין שינוי בכותרת `<h1>` או ב-back button.
- ❌ אין שינוי ב-color context של ה-header (amber gradient נשאר).
- ❌ אין הוספת props ל-Breadcrumbs מעבר ל-`items`, `className`, `separator`.

## Tasks

### 1 — צור `frontend/src/components/Breadcrumbs.jsx`

```jsx
import React from 'react';

const Breadcrumbs = ({ items = [], separator = '›', className = '' }) => {
  const parts = items.filter(Boolean);
  if (parts.length === 0) return null;
  return (
    <div className={`flex items-center gap-1.5 text-xs ${className}`}>
      {parts.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span aria-hidden="true">{separator}</span>}
          <span className="truncate">{item}</span>
        </React.Fragment>
      ))}
    </div>
  );
};

export default Breadcrumbs;
```

### 2 — `frontend/src/pages/UnitDetailPage.js`

הוסף import ליד import של CategoryPill הקיים (מ-#373):
```jsx
import Breadcrumbs from '../components/Breadcrumbs';
```

מצא ב-grep:
```bash
grep -n "text-amber-100 text-xs" frontend/src/pages/UnitDetailPage.js
```

החלף את הבלוק (5 שורות):

BEFORE:
```jsx
              <div className="flex items-center gap-1.5 text-amber-100 text-xs">
                {project && <span>{project.name}</span>}
                {building && <><span>›</span><span>{building.name}</span></>}
                {floor && <><span>›</span><span>{floor.name}</span></>}
              </div>
```

AFTER:
```jsx
              <Breadcrumbs
                items={[project?.name, building?.name, floor?.name]}
                className="text-amber-100"
              />
```

### 3 — `frontend/src/pages/UnitHomePage.js`

הוסף import ליד שאר ה-component imports:
```jsx
import Breadcrumbs from '../components/Breadcrumbs';
```

מצא ב-grep:
```bash
grep -n "text-amber-100 text-xs" frontend/src/pages/UnitHomePage.js
```

החלף את הבלוק (5 שורות):

BEFORE:
```jsx
              <div className="flex items-center gap-1.5 text-amber-100 text-xs">
                {project && <span>{project.name}</span>}
                {building && <><span>›</span><span>{building.name}</span></>}
                {floor && <><span>›</span><span>{floor.name}</span></>}
              </div>
```

AFTER:
```jsx
              <Breadcrumbs
                items={[project?.name, building?.name, floor?.name]}
                className="text-amber-100"
              />
```

### 4 — `frontend/src/pages/ApartmentDashboardPage.js`

הוסף import ליד import של CategoryPill הקיים (מ-#373):
```jsx
import Breadcrumbs from '../components/Breadcrumbs';
```

מצא ב-grep:
```bash
grep -n "text-amber-100 text-xs" frontend/src/pages/ApartmentDashboardPage.js
```

החלף את הבלוק (5 שורות):

BEFORE:
```jsx
              <div className="flex items-center gap-1.5 text-amber-100 text-xs">
                {project && <span>{project.name}</span>}
                {building && <><span>›</span><span>{building.name}</span></>}
                {floor && <><span>›</span><span>{floor.name}</span></>}
              </div>
```

AFTER:
```jsx
              <Breadcrumbs
                items={[project?.name, building?.name, floor?.name]}
                className="text-amber-100"
              />
```

## DO NOT
- ❌ אל תיגע ב-`FloorDetailPage.js` — ה-breadcrumb שם עם icons (Building2, Layers) ובצבע slate-300 על header כהה. shape אחר, חוץ מסקופ.
- ❌ אל תיגע ב-`UnitPlansPage.js` — שם זה `subtitleParts.join(' › ')` בתוך `<p>` עם truncate. visual אחר.
- ❌ אל תוסיף Breadcrumbs בקבצים שלא משנים אותם.
- ❌ אל תוסיף props (`as`, `divider`, `icon`, `to`/`href`) — רק `items`, `className`, `separator`.
- ❌ אל תהפוך את הפריטים ל-clickable links. כיום הם plain text — נשאר plain text.
- ❌ אל תיגע ב-`<h1>` של הכותרת או ב-back button (`<ArrowRight>`).
- ❌ אל תשנה את ה-amber gradient של ה-header.
- ❌ אל תשנה את `unit_note` (השורה השלישית מתחת ל-breadcrumb ב-UnitHomePage / ApartmentDashboard).
- ❌ אל תוסיף react-router `<Link>` או navigation logic.

## VERIFY
1. `git status` — בדיוק 4 קבצים: 1 חדש + 3 modified (UnitDetailPage, UnitHomePage, ApartmentDashboardPage).
2. `cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build` — חייב לעבור.
3. `grep -rn "text-amber-100 text-xs" frontend/src/pages/UnitDetailPage.js frontend/src/pages/UnitHomePage.js frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר 0 תוצאות (ה-class הזה היה רק על ה-breadcrumb wrapper שהוסר).
4. `grep -n "import Breadcrumbs" frontend/src/pages/*.js` — חייב להחזיר 3 תוצאות (UnitDetail, UnitHome, ApartmentDashboard).
5. `grep -rn "<span>›</span>" frontend/src/pages/UnitDetailPage.js frontend/src/pages/UnitHomePage.js frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר 0 (כל ה-`›` inline הוסרו).
6. `grep -n "›" frontend/src/pages/FloorDetailPage.js frontend/src/pages/UnitPlansPage.js` — חייב להחזיר את אותו מספר כמו לפני (לא נגעו).
7. `git diff backend/` — ריק.
8. אחרי deploy: פתח דירה → ה-breadcrumb (פרויקט › בניין › קומה) נראה זהה למה שהיה. ב-3 העמודים — UnitDetail (עמוד הליקויים), UnitHome (דשבורד דירה), ApartmentDashboard (טאב הליקויים בדירה).
9. בדוק במובייל RTL — ה-`›` אמור להיראות נכון בין items, gap-1.5 שומר רווח אחיד.

## Risks
🟢 נמוך מאוד. ויזואלי בלבד, scope צר (3 מקומות), ה-Breadcrumbs טריוויאלי (12 שורות). אם משהו ייראה לא טוב → revert של 4 קבצים.

## Relevant files
- `frontend/src/components/Breadcrumbs.jsx` (חדש)
- `frontend/src/pages/UnitDetailPage.js` (line ~138)
- `frontend/src/pages/UnitHomePage.js` (line ~128)
- `frontend/src/pages/ApartmentDashboardPage.js` (line ~365)
