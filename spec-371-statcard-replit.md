# Task #371 (Spec #346 Task 2) — StatCard neutral refactor

## What & Why
היום ה-3 כרטיסי KPI ("פתוחות / בטיפול / סגורות") שמופיעים בחלק העליון של 3 מסכים מציגים כל מספר עם **אייקון בצבע שונה** (אדום / כחול / ירוק). זה הופך את הכרטיס לרועש ומצמצם את הבולטות של עצם המספר.

המעבר: כל ה-KPI ל-**neutral**: המספר הוא ה-hero (גדול, slate-900, tabular-nums), ה-label אפור מתחתיו, **אין אייקונים, אין צבעים**, ובמקום gap יש divider אנכי דק בין השניים.

זה Task ויזואלי בלבד. אפס שינוי backend / state / props.

## Done looks like
- קובץ חדש: `frontend/src/components/StatCard.jsx`
- 3 דפים מציגים KPI במבנה החדש (StatCard × 3 + divider אנכי)
- אין אייקונים בכרטיסי KPI עצמם (האייקונים נמחקים מ-3 המקומות)
- בכל קובץ יש `import StatCard from '../components/StatCard';` בראש
- אין שינוי בערכים שמועברים — אותו `kpi.open / kpi.in_progress / kpi.closed`, אותם labels (כולל i18n ב-UnitHomePage)
- Build עובר, האפליקציה לא קורסת

## File 1: צור `frontend/src/components/StatCard.jsx` (חדש)

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

## File 2: `frontend/src/pages/UnitDetailPage.js` שורות 149–171

הוסף בראש הקובץ עם שאר ה-imports:
```jsx
import StatCard from '../components/StatCard';
```

BEFORE (שורות 149–171):
```jsx
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="space-y-1">
              <div className="flex items-center justify-center gap-1 text-red-500">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <div className="text-2xl font-bold text-slate-800">{kpi.open}</div>
              <div className="text-xs text-slate-500">פתוחות</div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-center gap-1 text-blue-500">
                <Clock className="w-4 h-4" />
              </div>
              <div className="text-2xl font-bold text-slate-800">{kpi.in_progress}</div>
              <div className="text-xs text-slate-500">בטיפול</div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-center gap-1 text-green-500">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div className="text-2xl font-bold text-slate-800">{kpi.closed}</div>
              <div className="text-xs text-slate-500">סגורות</div>
            </div>
          </div>
```

AFTER:
```jsx
          <div className="grid grid-cols-3 divide-x divide-slate-100" dir="ltr">
            <StatCard label="פתוחות" value={kpi.open} />
            <StatCard label="בטיפול"  value={kpi.in_progress} />
            <StatCard label="סגורות" value={kpi.closed} />
          </div>
```

## File 3: `frontend/src/pages/UnitHomePage.js` שורות 143–165

הוסף import:
```jsx
import StatCard from '../components/StatCard';
```

BEFORE (שורות 143–165):
```jsx
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="space-y-1">
              <div className="flex items-center justify-center gap-1 text-red-500">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <div className="text-2xl font-bold text-slate-800">{kpi?.open ?? 0}</div>
              <div className="text-xs text-slate-500">{t('unitHome', 'kpiOpen')}</div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-center gap-1 text-blue-500">
                <Clock className="w-4 h-4" />
              </div>
              <div className="text-2xl font-bold text-slate-800">{kpi?.in_progress ?? 0}</div>
              <div className="text-xs text-slate-500">{t('unitHome', 'kpiInProgress')}</div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-center gap-1 text-green-500">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div className="text-2xl font-bold text-slate-800">{kpi?.closed ?? 0}</div>
              <div className="text-xs text-slate-500">{t('unitHome', 'kpiClosed')}</div>
            </div>
          </div>
```

AFTER:
```jsx
          <div className="grid grid-cols-3 divide-x divide-slate-100" dir="ltr">
            <StatCard label={t('unitHome', 'kpiOpen')}       value={kpi?.open ?? 0} />
            <StatCard label={t('unitHome', 'kpiInProgress')} value={kpi?.in_progress ?? 0} />
            <StatCard label={t('unitHome', 'kpiClosed')}     value={kpi?.closed ?? 0} />
          </div>
```

⚠️ שמור על ה-i18n calls — אל תחליף ל-strings קשיחים.

## File 4: `frontend/src/pages/ApartmentDashboardPage.js` שורות 389–411

הוסף import:
```jsx
import StatCard from '../components/StatCard';
```

BEFORE (שורות 389–411):
```jsx
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="space-y-1">
                  <div className="flex items-center justify-center gap-1 text-red-500">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div className="text-2xl font-bold text-slate-800">{openCount}</div>
                  <div className="text-xs text-slate-500">פתוחות</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-center gap-1 text-blue-500">
                    <Clock className="w-4 h-4" />
                  </div>
                  <div className="text-2xl font-bold text-slate-800">{inProgressCount}</div>
                  <div className="text-xs text-slate-500">בטיפול</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-center gap-1 text-green-500">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <div className="text-2xl font-bold text-slate-800">{closedCount}</div>
                  <div className="text-xs text-slate-500">סגורות</div>
                </div>
              </div>
```

AFTER:
```jsx
              <div className="grid grid-cols-3 divide-x divide-slate-100" dir="ltr">
                <StatCard label="פתוחות" value={openCount} />
                <StatCard label="בטיפול"  value={inProgressCount} />
                <StatCard label="סגורות" value={closedCount} />
              </div>
```

## DO NOT
- ❌ אל תיגע ב-`BuildingDefectsPage.js` או `ProjectControlPage.js` — הם לא משתמשים בדפוס הזה (`grid grid-cols-3 gap-3 text-center`). אישרתי זאת ב-grep.
- ❌ אל תמחק את ה-imports של `AlertTriangle`, `Clock`, `CheckCircle2` מהקבצים — ייתכן שהם בשימוש במקומות אחרים בקובץ. אם הם **לא** בשימוש בכלל אחרי השינוי (בדוק עם grep בקובץ עצמו), הסר את ה-import של אלה שלא נחוצים.
- ❌ אל תשנה ל-`StatCard` props מעבר ל-`label` ו-`value` — אין `icon`, אין `color`. הוא neutral בכוונה.
- ❌ אל תשנה את `dir="rtl"` על ה-page-level. ה-`dir="ltr"` הוא רק על ה-grid כדי ש-`divide-x` יצור dividers בכיוון הצפוי.
- ❌ אל תיצור tests חדשים, אל תוסיף Storybook, אל תוסיף `framer-motion`.
- ❌ אל תיגע ב-`Loader2` של submit, ה-FAB, הכותרות הכתומות, או כל אזור אחר בעמודים.

## VERIFY
1. `git status` — בדיוק 4 קבצים: 1 חדש (`StatCard.jsx`) + 3 modified (`UnitDetailPage.js`, `UnitHomePage.js`, `ApartmentDashboardPage.js`).
2. Build: `cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build` — חייב לעבור.
3. `grep -n "grid-cols-3 gap-3 text-center" frontend/src/pages/*.js` — חייב להחזיר **0 תוצאות** (כל המופעים הוחלפו).
4. `grep -n "import StatCard" frontend/src/pages/UnitDetailPage.js frontend/src/pages/UnitHomePage.js frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר 3 תוצאות.
5. בדפדפן (אחרי deploy): פתח דירה — צריך לראות 3 מספרים גדולים עם labels אפורים מתחת, **בלי אייקונים**, ועם קו אנכי דק בין השניים.

## Risks
🟡 בינוני-נמוך. יש שינוי ויזואלי משמעותי (אייקונים נעלמים). אם המשתמש לא יאהב — אפשר לשחזר את האייקונים בקלות. אבל ה-state / data flow לא משתנה.

## Relevant files
- `frontend/src/components/StatCard.jsx` (חדש)
- `frontend/src/pages/UnitDetailPage.js` שורות 149–171
- `frontend/src/pages/UnitHomePage.js` שורות 143–165
- `frontend/src/pages/ApartmentDashboardPage.js` שורות 389–411
