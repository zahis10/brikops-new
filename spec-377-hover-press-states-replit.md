# Task #377 (Spec #346 Task 9) — Hover/Press states polish

## What & Why
ב-BrikOps רוב המשתמשים משתמשים בטלפון בשטח. ברגע שלוחצים על כרטיס/כפתור, לא תמיד יש פידבק מיידי שהמערכת רשמה את המגע. בקבצים מסוימים זה מטופל מצוין (StageDetailPage, NewDefectModal, QCApproversTab, HamburgerMenu — כולם עם `active:` עקבי), אבל יש 3 מקומות מרכזיים שחסר בהם פידבק לחיצה:

1. **`Button` primitive (shadcn)** — אין אף `active:` בכל 6 הוריאנטים. כל `<Button>` באפליקציה יורש את החסר הזה.
2. **ProjectTasksPage defect cards** — הכרטיסים שנלחצים הכי הרבה בעמוד הליקויים, ויש להם רק `hover:shadow-md`. מובייל לא רואה hover, אז משתמש שלוחץ לא מקבל כלום עד שהניווט קורה.
3. **ProjectControlPage "ליקויים באיחור" CTA** — באנר כתום, יש לו `hover:bg-orange-100` בלבד.

**מטרה:** הוספת `active:` עקבי ל-3 המקומות האלה. אפס שינוי לוגי, אפס שינוי markup, אפס props חדשים, אפס שינוי בצבעים שכבר קיימים.

## Done looks like
- כל `<Button variant="...">` באפליקציה (default, destructive, outline, secondary, ghost, link) נותן feedback ויזואלי על לחיצה (כהה יותר / פחות שקוף לרגע).
- הכרטיסי ליקויים ב-ProjectTasks נותנים feedback של רקע אפור על לחיצה (תואם ל-UnitDetail/Apartment שכבר עושים את זה).
- באנר "ליקויים באיחור" נותן feedback של כתום עמוק יותר על לחיצה.
- בטלפון: כל לחיצה מורגשת מיד, לפני שהניווט/האקשן קורה.
- Build עובר נקי. אפס regression ויזואלי במצב normal/hover.

## Out of scope
- ❌ לא מוסיפים `transition-*` חדש — המקומות שנגעים בהם כבר עם `transition-colors` או `transition-shadow`. `active:bg-X` עובד אוטומטית כי הצבע משתמש באותו transition.
- ❌ לא נוגעים ב-`focus-visible:` (כבר מוגדר ב-Button).
- ❌ לא נוגעים ב-`disabled:` states.
- ❌ לא מוסיפים `active:scale-*` חדש בשום מקום (UnitHomePage כבר משתמש בזה — לא משנים את המוסכמה הזו).
- ❌ לא נוגעים בקבצים הבאים — כבר תקינים: `StageDetailPage.js`, `components/NewDefectModal.js`, `components/QCApproversTab.js`, `components/HamburgerMenu.js`, `pages/UnitDetailPage.js` (יש active:bg-slate-50), `pages/ApartmentDashboardPage.js` (יש active:bg-slate-50), `pages/MyProjectsPage.js` (יש active:bg-slate-50), `pages/UnitHomePage.js` (יש active:scale).
- ❌ לא נוגעים ב-Modals/Dialogs (FilterDrawer זה ספק נפרד עתידי).
- ❌ לא נוגעים ב-Admin pages, Auth pages, Settings, Handover module, QC pages, Project Plans.
- ❌ לא נוגעים ב-i18n או backend.
- ❌ לא נוגעים בצבעי tailwind config — משתמשים רק במה שכבר קיים (slate-100, amber/primary opacity, orange-200).
- ❌ אל תפעיל find-and-replace global — שנות יד את 3 המקומות בלבד.

## Tasks

### 1 — `frontend/src/components/ui/button.jsx` (lines 12–21, the `variant` block)

מצא ב-grep:
```bash
grep -n "buttonVariants" frontend/src/components/ui/button.jsx
```

החלף את כל ה-`variant` object (lines 12–21) — מוסיפים `active:` בכל וריאנט. שום שינוי אחר.

BEFORE:
```jsx
      variant: {
        default:
          "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
```

AFTER:
```jsx
      variant: {
        default:
          "bg-primary text-primary-foreground shadow hover:bg-primary/90 active:bg-primary/80",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90 active:bg-destructive/80",
        outline:
          "border border-input shadow-sm hover:bg-accent hover:text-accent-foreground active:bg-accent/70",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80 active:bg-secondary/70",
        ghost: "hover:bg-accent hover:text-accent-foreground active:bg-accent/70",
        link: "text-primary underline-offset-4 hover:underline active:opacity-75",
      },
```

(הערה: ה-base `cva` קלאס בשורה 8 כבר מכיל `transition-colors` — אפס צורך להוסיף transition.)

### 2 — `frontend/src/pages/ProjectTasksPage.js` (line 507)

מצא ב-grep:
```bash
grep -n "hover:shadow-md transition-shadow cursor-pointer" frontend/src/pages/ProjectTasksPage.js
```

החלף שורה בודדת בתוך ה-`<Card>`:

BEFORE:
```jsx
                <Card
                  key={task.id}
                  className="p-3 hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => navigate(...)}
                >
```

AFTER:
```jsx
                <Card
                  key={task.id}
                  className="p-3 hover:shadow-md active:bg-slate-100 transition-all cursor-pointer"
                  onClick={() => navigate(...)}
                >
```

(שני שינויים בלבד באותה שורה: `transition-shadow` → `transition-all`, ו-`active:bg-slate-100` נוסף. הסיבה: `transition-shadow` לא מכסה רקע, אז משדרגים ל-`transition-all` כדי שגם הרקע יקבל מעבר חלק.)

### 3 — `frontend/src/pages/ProjectControlPage.js` (line 265)

מצא ב-grep:
```bash
grep -n "ליקויים באיחור טיפול" frontend/src/pages/ProjectControlPage.js
```

החלף שורת ה-`className` בלבד (השורה אחרי `onClick={onViewDefects}`):

BEFORE:
```jsx
        <button type="button" onClick={onViewDefects}
          className="w-full flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-lg px-3.5 py-2.5 cursor-pointer hover:bg-orange-100 transition-colors text-right">
```

AFTER:
```jsx
        <button type="button" onClick={onViewDefects}
          className="w-full flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-lg px-3.5 py-2.5 cursor-pointer hover:bg-orange-100 active:bg-orange-200 transition-colors text-right">
```

(שינוי בודד: הוספת `active:bg-orange-200` בלבד. כל השאר זהה.)

## DO NOT
- ❌ אל תיגע בשום וריאנט אחר ב-`button.jsx` (size, defaultVariants).
- ❌ אל תוסיף `active:` לכרטיסים/כפתורים שכבר יש להם (UnitDetail, Apartment, MyProjects, UnitHome, StageDetail, וכו').
- ❌ אל תשנה את `transition-shadow` → `transition-all` בשום מקום אחר חוץ מ-ProjectTasks line 507 — רק שם זה צריך כי הוספנו רקע. בכל המקומות האחרים ה-transition כבר מותאם.
- ❌ אל תוסיף `transition-*` חדש — בשני שאר המקומות כבר יש `transition-colors`/`transition-shadow`.
- ❌ אל תוסיף `cursor-pointer` או `min-h-` או touch-target classes חדשים.
- ❌ אל תשנה את הצבע הבסיסי (bg-primary, bg-orange-50 וכו') — רק מוסיפים active: state כהה יותר.
- ❌ אל תיגע בשום modal/dialog/dropdown/popover.
- ❌ אל תיגע ב-`tailwind.config.js`.
- ❌ אל תיגע ב-`shadcn/ui` components אחרים (input, select, dialog וכו').
- ❌ אל תיגע ב-`backend/`.
- ❌ אל תפעיל find-and-replace global — 3 שינויים ידניים בלבד.

## VERIFY
1. `git status` — בדיוק 3 קבצים modified (אפס חדשים, אפס מחוקים).

2. **Build נקי:**
   ```bash
   cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build
   ```

3. **Button — וודא שכל 6 הוריאנטים קיבלו `active:`:**
   ```bash
   grep -c "active:" frontend/src/components/ui/button.jsx
   ```
   חייב להחזיר **6** (אחד לכל וריאנט).

4. **Button — וודא שאף וריאנט לא נמחק:**
   ```bash
   grep -E "default:|destructive:|outline:|secondary:|ghost:|link:" frontend/src/components/ui/button.jsx | wc -l
   ```
   חייב להחזיר **6**.

5. **ProjectTasks — וודא שהשינוי נכנס:**
   ```bash
   grep -n "active:bg-slate-100 transition-all cursor-pointer" frontend/src/pages/ProjectTasksPage.js
   ```
   חייב להחזיר **1** תוצאה.

6. **ProjectTasks — וודא שאין יותר `transition-shadow cursor-pointer` (השורה הספציפית):**
   ```bash
   grep -n "p-3 hover:shadow-md transition-shadow cursor-pointer" frontend/src/pages/ProjectTasksPage.js
   ```
   חייב להחזיר **0**.

7. **ProjectControl — וודא שה-`active:bg-orange-200` נכנס בשורה הנכונה:**
   ```bash
   grep -n "hover:bg-orange-100 active:bg-orange-200 transition-colors" frontend/src/pages/ProjectControlPage.js
   ```
   חייב להחזיר **1**.

8. **אפס שינוי בקבצים אחרים:**
   ```bash
   git diff --stat | grep -v "button.jsx\|ProjectTasksPage.js\|ProjectControlPage.js"
   ```
   חייב להיות ריק.

9. `git diff backend/` — ריק.

10. `git diff frontend/src/i18n/` — ריק.

11. `git diff frontend/tailwind.config.js` — ריק.

12. `git diff frontend/src/components/ui/` — רק `button.jsx` משתנה.

13. **אחרי deploy — בדיקה ידנית בטלפון (או DevTools mobile mode):**
    - לחיצה ארוכה על `<Button>` כלשהו (למשל "צור ליקוי", "שמור" במודל) → רואים שינוי גוון רגעי.
    - לחיצה על כרטיס ליקוי בעמוד `/projects/[id]/tasks` → הכרטיס נצבע באפור-בהיר לרגע לפני הניווט.
    - לחיצה על באנר "🔥 X ליקויים באיחור טיפול" ב-ProjectControl → הבאנר נצבע בכתום עמוק יותר לרגע.
    - בדיקה רגרסיה: כפתורים/כרטיסים שלא נגעו (UnitDetail defect rows, MyProjects cards, FAB) — נראים ומתנהגים בדיוק אותו דבר.

## Risks
🟢 כמעט אפס.
- 3 שינויי className בלבד (אפס logic, אפס markup, אפס props).
- שינוי ה-Button primitive חל על כל הכפתורים באפליקציה — אבל מדובר רק בהוספת state חדש שלא קיים. אפס שינוי במצב default/hover.
- אם משהו נראה רע → revert של 3 שורות.
- אין שינוי breaking ל-API של הקומפוננטות.

## Relevant files
- `frontend/src/components/ui/button.jsx` (lines 12–21, the variant block)
- `frontend/src/pages/ProjectTasksPage.js` (line 507)
- `frontend/src/pages/ProjectControlPage.js` (line 265)
