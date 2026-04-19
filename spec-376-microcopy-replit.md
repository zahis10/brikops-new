# Task #376 (Spec #346 Task 8) — Microcopy refresh ל-defect-list empty states

## What & Why
ארבעה עמודים מציגים empty states לרשימת ליקויים, וכל אחד מהם משתמש בנוסח אחר לאותה הודעה. שני אזורים של אי-עקביות:

**A. Filter-active empty state — 3 ניסוחים שונים לאותו דבר:**
- UnitDetailPage:259 — `'אין ליקויים התואמים לפילטר'` (פילטר באנגלית, חורג מסגנון עברית)
- ApartmentDashboardPage:665 — `'אין ליקויים התואמים לסינון'` ✓
- ProjectTasksPage:474 — `'אין ליקויים התואמים את הסינון'` (דקדוקית שגוי — "התואמים את" → "התואמים ל")

**B. No-defects baseline — 3 ניסוחים שונים:**
- UnitDetailPage:259 — `'אין ליקויים לדירה זו'`
- ApartmentDashboardPage:665 — `'אין ליקויים לדירה זו'`
- ProjectTasksPage:474 — `'אין ליקויים עדיין'`
- ProjectControlPage:3811 — `'עדיין אין ליקויים בפרויקט'`

**מטרה:** ניסוח אחיד לכל context. שיניוי טקסט בלבד — אפס שינוי לוגי, אפס שינוי markup, אפס props חדשים.

## Done looks like
**Filter-active (כל מקום): `'אין ליקויים התואמים לסינון'`**
**Unit-context no-defects: `'אין ליקויים בדירה'`**
**Project-context no-defects: `'אין ליקויים בפרויקט'`**

4 קבצים נגעו, 4 שורות שונו. Build עובר נקי. ויזואלית: רק טקסט שונה, layout/spacing/colors נשארים.

## Out of scope
- ❌ **ProjectControlPage.js:3730** — `'אין ליקויים באיחור'` / `'אין ליקויים במצב "X"'` — אלה filter chips ספציפיים (overdue, status), לא generic filter. הניסוח שם נכון ואינפורמטיבי. **לא נוגעים.**
- ❌ **i18n/he.json:358** — `"no_open_defects": "אין ליקויים פתוחים — כל הכבוד!"` — celebratory tone, context אחר (סיכום dashboard). **לא נוגעים.**
- ❌ אין שינוי ב-icons (CheckCircle2, ListTodo).
- ❌ אין שינוי ב-subtitle ("הוסף ליקוי חדש כדי להתחיל...", "צור ליקוי ראשון..."). זה microcopy של row 2 שיכול להיות spec נפרד.
- ❌ אין שינוי ב-CTA buttons (כתרים כמו "נקה סינון", "צור ליקוי →").
- ❌ אין שינוי ב-error messages, loading states, או toast messages.
- ❌ אין שינוי ב-empty states של תוכניות, מסירה, dashboard cards, או כל מסך אחר חוץ מ-defect-list.

## Tasks

### 1 — `frontend/src/pages/UnitDetailPage.js` (line 259)

מצא ב-grep:
```bash
grep -n "אין ליקויים התואמים לפילטר" frontend/src/pages/UnitDetailPage.js
```

החלף את השורה בודדת:

BEFORE:
```jsx
              {activeFilters > 0 ? 'אין ליקויים התואמים לפילטר' : 'אין ליקויים לדירה זו'}
```

AFTER:
```jsx
              {activeFilters > 0 ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים בדירה'}
```

### 2 — `frontend/src/pages/ApartmentDashboardPage.js` (line 665)

מצא ב-grep:
```bash
grep -n "אין ליקויים לדירה זו" frontend/src/pages/ApartmentDashboardPage.js
```

החלף:

BEFORE:
```jsx
              {hasActiveFilters ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים לדירה זו'}
```

AFTER:
```jsx
              {hasActiveFilters ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים בדירה'}
```

(שים לב: רק החצי השני משתנה. החצי הראשון `'אין ליקויים התואמים לסינון'` כבר נכון.)

### 3 — `frontend/src/pages/ProjectTasksPage.js` (line 474)

מצא ב-grep:
```bash
grep -n "התואמים את הסינון" frontend/src/pages/ProjectTasksPage.js
```

החלף:

BEFORE:
```jsx
              {hasActiveFilter ? 'אין ליקויים התואמים את הסינון' : 'אין ליקויים עדיין'}
```

AFTER:
```jsx
              {hasActiveFilter ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים בפרויקט'}
```

### 4 — `frontend/src/pages/ProjectControlPage.js` (line 3811)

מצא ב-grep:
```bash
grep -n "עדיין אין ליקויים בפרויקט" frontend/src/pages/ProjectControlPage.js
```

החלף:

BEFORE:
```jsx
                  <p className="text-sm font-medium text-slate-700">עדיין אין ליקויים בפרויקט</p>
```

AFTER:
```jsx
                  <p className="text-sm font-medium text-slate-700">אין ליקויים בפרויקט</p>
```

(הסרת "עדיין " בתחילה — הניסוח החדש קצר, נקי, ועקבי. ה-CTA "צור ליקוי →" שמתחת מספק את ה-encouragement.)

## DO NOT
- ❌ אל תיגע ב-`subtitle` (השורה השנייה ב-empty state) — `'נסה לשנות את הסינון או לחפש מחדש'`, `'הוסף ליקוי חדש כדי להתחיל לנהל את הפרויקט'`, `'צור ליקוי ראשון כדי להתחיל לעבוד'`. ספק נפרד אם נצטרך.
- ❌ אל תיגע ב-CTA buttons (`'נקה סינון'`, `'צור ליקוי →'`, `'+ ליקוי חדש'`).
- ❌ אל תיגע ב-icons (CheckCircle2 בUnitDetail/Apartment, ListTodo ב-ProjectTasks, ClipboardCheck ב-ProjectControl).
- ❌ אל תיגע ב-`<Card>` או ב-`<div>` wrappers של ה-empty state.
- ❌ אל תיגע ב-classes (`text-sm text-slate-500`, `text-base font-bold text-slate-700` וכו').
- ❌ אל תיגע ב-i18n/he.json — הטקסטים האלה inline ב-pages, לא בקובץ תרגום.
- ❌ אל תיגע ב-ProjectControlPage:3730 (`'אין ליקויים באיחור'` / `'במצב X'`) — זה filter-chip-specific, נכון להישאר.
- ❌ אל תוסיף `'עדיין'` לאף ניסוח שלא היה בו.
- ❌ אל תפעיל find-and-replace global — שנות יד את 4 השורות בלבד.
- ❌ אל תיגע ב-backend.

## VERIFY
1. `git status` — בדיוק 4 קבצים modified (אפס חדשים, אפס מחוקים).
2. `cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build` — חייב לעבור.
3. `grep -rn "אין ליקויים התואמים לפילטר" frontend/src` — חייב להחזיר 0 (פילטר → סינון).
4. `grep -rn "אין ליקויים התואמים את הסינון" frontend/src` — חייב להחזיר 0 (גרמטיקה תוקנה).
5. `grep -rn "אין ליקויים התואמים לסינון" frontend/src` — חייב להחזיר 3 תוצאות (UnitDetail, Apartment, ProjectTasks). אחת לכל קובץ.
6. `grep -rn "אין ליקויים לדירה זו" frontend/src` — חייב להחזיר 0.
7. `grep -rn "אין ליקויים בדירה" frontend/src` — חייב להחזיר 2 (UnitDetail, Apartment).
8. `grep -rn "אין ליקויים בפרויקט" frontend/src` — חייב להחזיר 2 (ProjectTasks, ProjectControl).
9. `grep -rn "עדיין אין ליקויים" frontend/src` — חייב להחזיר 0.
10. `grep -rn "אין ליקויים עדיין" frontend/src` — חייב להחזיר 0.
11. `grep -n "אין ליקויים באיחור" frontend/src/pages/ProjectControlPage.js` — חייב להחזיר 1 (לא נגענו).
12. `git diff backend/` — ריק.
13. `git diff frontend/src/i18n/` — ריק.
14. אחרי deploy: בדיקה ידנית של 4 ה-empty states:
    - **UnitDetail בלי ליקויים** → `'אין ליקויים בדירה'`
    - **UnitDetail עם פילטר פעיל וללא תוצאות** → `'אין ליקויים התואמים לסינון'`
    - **Apartment עם פילטר פעיל וללא תוצאות** → `'אין ליקויים התואמים לסינון'`
    - **ProjectTasks בפרויקט חדש** → `'אין ליקויים בפרויקט'`
    - **ProjectControl בפרויקט חדש** → `'אין ליקויים בפרויקט'`

## Risks
🟢 כמעט אפס.
- 4 שינויי טקסט inline. אפס logic, אפס markup, אפס styling.
- שום שינוי בהתנהגות, רק נראה אחיד יותר.
- אם משהו נראה שונה ממה שתכננו → revert של 4 שורות.

## Relevant files
- `frontend/src/pages/UnitDetailPage.js:259`
- `frontend/src/pages/ApartmentDashboardPage.js:665`
- `frontend/src/pages/ProjectTasksPage.js:474`
- `frontend/src/pages/ProjectControlPage.js:3811`
