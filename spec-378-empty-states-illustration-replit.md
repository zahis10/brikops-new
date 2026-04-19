# Task #378 (Spec #346 Task 10) — Empty states illustration hint

## What & Why
ה-3 empty states המרכזיים של רשימת הליקויים נראים כרגע "שטוחים" — אייקון Lucide בלבד על רקע לבן, ואז טקסט. זה תקין, אבל לא מרגיש מגובש. כל אפליקציה מודרנית (Linear, Stripe, Vercel, Notion) עוטפת את האייקון במעגל רקע עדין — זה נותן "illustration hint" שהופך empty state מ"חסר תוכן" ל"רגע מכובד בממשק".

**המטרה:** עטיפת ה-Lucide icon במעגל רקע עדין (`rounded-full` עם `bg-slate-100`) כדי להוסיף עומק ויזואלי. אפס שינוי בטקסט, אפס שינוי בלוגיקה, אפס תלות חדשה, אפס שינוי צבעים חדשים ב-Tailwind.

**הערות:**
- **שימוש ב-microcopy #376** — כל הטקסטים כבר עברו אלינמנט. הספק הזה ויזואלי בלבד.
- **אופציה מעוצבת, לא חיה** — אין interactions, animations, או state חדש.
- ב-3 המקומות בלבד. השאר (ProjectControl של ClipboardCheck, Building2, handover empty states, admin, וכו') — out of scope.

## Done looks like
- UnitDetail, Apartment, ProjectTasks: ה-icon יושב כעת במעגל `bg-slate-100` רך, ממורכז, עם padding טבעי.
- הגדלים:
  - UnitDetail/Apartment: מעגל `w-16 h-16` (64px), icon `w-8 h-8` (32px, CheckCircle2)
  - ProjectTasks: מעגל `w-20 h-20` (80px), icon `w-10 h-10` (40px, ListTodo)
- ה-`mb-2` הקיים מוחלף ב-`mb-3` (מעגל צריך נשימה).
- צבע האייקון נשמר (`text-slate-400` / `text-slate-300`).
- הטקסט מתחת לא זז — אותו markup, אותו hierarchy.
- Build עובר נקי. אפס regression.

## Out of scope
- ❌ **ProjectControlPage ה-ClipboardCheck horizontal card** (ליד "אין ליקויים בפרויקט") — layout אחר (flex items-center), לא centered stack. לא נוגעים.
- ❌ **ProjectControlPage Building2 empty state** (`אין בניינים בפרויקט`, line ~3829) — חי בתוך Card שונה (py-12 בלבד, בלי border). אפשר לטפל בו בספק נפרד אם נרצה; לא עכשיו.
- ❌ **ProjectControl filter chips empty states** (overdue/status-specific) — microcopy נפרד, לא נוגעים.
- ❌ **Handover empty states** (HandoverOverviewPage, HandoverSectionPage) — out of module scope.
- ❌ **Admin pages empty states** — out of scope.
- ❌ **MyProjectsPage empty state** (אם יש) — out of scope.
- ❌ אין שינוי בטקסט (`'אין ליקויים בדירה'`, `'אין ליקויים בפרויקט'`, `'אין ליקויים התואמים לסינון'`, subtitles, CTAs).
- ❌ אין שינוי בצבע האייקון.
- ❌ אין שינוי ב-`<h3>` או `<p>` — אותם classes בדיוק.
- ❌ אין שינוי ב-CTA button שב-ProjectTasks.
- ❌ אין שינוי ב-i18n או backend.
- ❌ אין תוספת tailwind utilities מותאמים אישית — רק tokens קיימים (slate-100, rounded-full, flex, items-center, justify-center).
- ❌ אין הוספת animation/transition.
- ❌ אין שינוי ב-Card primitive (`components/ui/card.jsx`).
- ❌ אין find-and-replace global — 3 עריכות ידניות בלבד.

## Tasks

### 1 — `frontend/src/pages/UnitDetailPage.js` (line 254–257, inside `tasks.length === 0` block)

מצא ב-grep:
```bash
grep -n "CheckCircle2 className=\"w-10 h-10 mx-auto\"" frontend/src/pages/UnitDetailPage.js
```

החלף 3 שורות (ה-wrapper div + AutoCircle2 + סגירת div):

BEFORE:
```jsx
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="text-slate-400 mb-2">
              <CheckCircle2 className="w-10 h-10 mx-auto" />
            </div>
            <p className="text-sm text-slate-500">
              {activeFilters > 0 ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים בדירה'}
            </p>
          </div>
```

AFTER:
```jsx
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-slate-400" />
            </div>
            <p className="text-sm text-slate-500">
              {activeFilters > 0 ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים בדירה'}
            </p>
          </div>
```

### 2 — `frontend/src/pages/ApartmentDashboardPage.js` (line 660–663, inside `filteredTasks.length === 0` block)

מצא ב-grep:
```bash
grep -n "CheckCircle2 className=\"w-10 h-10 mx-auto\"" frontend/src/pages/ApartmentDashboardPage.js
```

**שינוי זהה בדיוק ל-#1** (אותו markup, אותה טרנספורמציה):

BEFORE:
```jsx
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="text-slate-400 mb-2">
              <CheckCircle2 className="w-10 h-10 mx-auto" />
            </div>
            <p className="text-sm text-slate-500">
              {hasActiveFilters ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים בדירה'}
            </p>
          </div>
```

AFTER:
```jsx
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-slate-400" />
            </div>
            <p className="text-sm text-slate-500">
              {hasActiveFilters ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים בדירה'}
            </p>
          </div>
```

### 3 — `frontend/src/pages/ProjectTasksPage.js` (line 471–472, inside `tasks.length === 0` block)

מצא ב-grep:
```bash
grep -n "ListTodo className=\"w-12 h-12 text-slate-300 mx-auto mb-3\"" frontend/src/pages/ProjectTasksPage.js
```

**החלף שורה אחת (ה-icon עצמה) בתוך wrapper חדש** — h3 ו-p למטה לא נוגעים:

BEFORE:
```jsx
          <Card className="p-8 text-center">
            <ListTodo className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-700 mb-1">
```

AFTER:
```jsx
          <Card className="p-8 text-center">
            <div className="w-20 h-20 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center">
              <ListTodo className="w-10 h-10 text-slate-300" />
            </div>
            <h3 className="text-base font-bold text-slate-700 mb-1">
```

(שים לב: האייקון היה `w-12 h-12` → `w-10 h-10` כדי להתאים ל-50% מהמעגל. זה חזותית עקבי עם #1 ו-#2.)

## DO NOT
- ❌ אל תיגע ב-`<h3>` או ב-`<p>` בשום קובץ — אותו טקסט, אותם classes.
- ❌ אל תיגע ב-CTA button ב-ProjectTasksPage (ה-`<button>` אחרי ה-`<p>`).
- ❌ אל תיגע ב-loading skeleton (`TaskCardSkeleton`, `Loader2`) למעלה מה-empty state.
- ❌ אל תיגע ב-wrapper החיצוני (`<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">` / `<Card className="p-8 text-center">`).
- ❌ אל תיגע ב-`activeFilters`/`hasActiveFilters`/`hasActiveFilter` logic.
- ❌ אל תיגע ב-icons עצמם (לא מחליף CheckCircle2 → CheckCircle או דומה).
- ❌ אל תוסיף `shadow` או `border` למעגל — bg-slate-100 בלבד.
- ❌ אל תוסיף `transition`/`animation`/`hover:` למעגל — empty state סטטי.
- ❌ אל תיגע ב-ProjectControlPage כלל (לא Building2 ולא ClipboardCheck).
- ❌ אל תיגע ב-Handover, Admin, Auth, Settings, Plans.
- ❌ אל תיגע ב-`components/ui/card.jsx`.
- ❌ אל תיגע ב-`tailwind.config.js`.
- ❌ אל תיגע ב-backend או ב-i18n.
- ❌ אל תשתמש ב-`bg-slate-50` (בהיר מדי על לבן) או ב-`bg-slate-200` (יותר מדי ניגוד) — רק `bg-slate-100`.
- ❌ אל תפעיל find-and-replace global.

## VERIFY

1. `git status` — בדיוק 3 קבצים modified (אפס חדשים, אפס מחוקים).

2. **Build נקי:**
   ```bash
   cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build
   ```

3. **UnitDetail — מעגל חדש קיים:**
   ```bash
   grep -n "w-16 h-16 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center" frontend/src/pages/UnitDetailPage.js
   ```
   חייב להחזיר **1**.

4. **UnitDetail — markup ישן לא קיים:**
   ```bash
   grep -n "text-slate-400 mb-2" frontend/src/pages/UnitDetailPage.js
   ```
   חייב להחזיר **0**.

5. **UnitDetail — icon size החדש:**
   ```bash
   grep -n "CheckCircle2 className=\"w-8 h-8 text-slate-400\"" frontend/src/pages/UnitDetailPage.js
   ```
   חייב להחזיר **1**.

6. **Apartment — מעגל חדש:**
   ```bash
   grep -n "w-16 h-16 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center" frontend/src/pages/ApartmentDashboardPage.js
   ```
   חייב להחזיר **1**.

7. **Apartment — markup ישן לא קיים:**
   ```bash
   grep -n "text-slate-400 mb-2" frontend/src/pages/ApartmentDashboardPage.js
   ```
   חייב להחזיר **0**.

8. **Apartment — icon size החדש:**
   ```bash
   grep -n "CheckCircle2 className=\"w-8 h-8 text-slate-400\"" frontend/src/pages/ApartmentDashboardPage.js
   ```
   חייב להחזיר **1**.

9. **ProjectTasks — מעגל חדש:**
   ```bash
   grep -n "w-20 h-20 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center" frontend/src/pages/ProjectTasksPage.js
   ```
   חייב להחזיר **1**.

10. **ProjectTasks — icon size החדש:**
    ```bash
    grep -n "ListTodo className=\"w-10 h-10 text-slate-300\"" frontend/src/pages/ProjectTasksPage.js
    ```
    חייב להחזיר **1**.

11. **ProjectTasks — icon size ישן לא קיים:**
    ```bash
    grep -n "ListTodo className=\"w-12 h-12 text-slate-300 mx-auto mb-3\"" frontend/src/pages/ProjectTasksPage.js
    ```
    חייב להחזיר **0**.

12. **Microcopy #376 נשמר:**
    ```bash
    grep -rn "אין ליקויים בדירה\|אין ליקויים התואמים לסינון\|אין ליקויים בפרויקט" frontend/src/pages/ | wc -l
    ```
    חייב להחזיר **≥5** (5 hits: Unit×2, Apt×2, ProjectTasks×2, ProjectControl×1 — הטקסטים נשארים שלמים).

13. **ProjectControl לא נגע:**
    ```bash
    git diff frontend/src/pages/ProjectControlPage.js
    ```
    חייב להיות ריק.

14. `git diff backend/` — ריק.

15. `git diff frontend/src/i18n/` — ריק.

16. `git diff frontend/tailwind.config.js` — ריק.

17. `git diff frontend/src/components/` — ריק (לא נוגעים ב-Card/Button/Breadcrumbs/TaskCardSkeleton).

18. **אחרי deploy — בדיקה ידנית:**
    - פתח דירה ריקה ללא ליקויים → רואים עיגול אפור-בהיר עם וי ירקרק-אפור במרכז, ואז הטקסט `'אין ליקויים בדירה'`.
    - פתח פרויקט ריק ב-ProjectTasks → רואים עיגול אפור-בהיר גדול יותר עם רשימת-מטלות במרכז, ואז h3 + p + CTA.
    - הפעל פילטר שלא מחזיר כלום → אותו טיפול ויזואלי, אבל הטקסט `'אין ליקויים התואמים לסינון'`.
    - ProjectControlPage נראה בדיוק אותו דבר — לא נגענו בה.

## Risks
🟢 כמעט אפס.
- 3 עריכות JSX קטנות, אפס logic change.
- ה-circle הוא רק div wrapper נוסף — אפס השפעה על responsive/layout.
- אם משהו נראה רע → revert של 3 קבצים = 3 commits.
- אין breaking change ל-API/props/state.

## Relevant files
- `frontend/src/pages/UnitDetailPage.js` (lines 254–257)
- `frontend/src/pages/ApartmentDashboardPage.js` (lines 660–663)
- `frontend/src/pages/ProjectTasksPage.js` (lines 471–472)
