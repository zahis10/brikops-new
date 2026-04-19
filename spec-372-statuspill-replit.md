# Task #372 (Spec #346 Task 3) — StatusPill עם dot

## What & Why
היום ה-status pills של ליקויים (פתוח / שויך / בביצוע / ממתין לאימות / סגור / נפתח מחדש) צבועים בצבעים שונים של pastel רקע (אדום, כתום, כחול, סגול, ירוק, ענבר). כשיש 4–5 ליקויים בקלף, התוצאה הויזואלית היא קרנבל. המעבר: pill אחיד עם **רקע אפור slate-100 + dot צבעוני קטן (1.5×1.5) משמאל ל-label** — הצבע נשמר כסיגנל, אבל קטן ולא דומיננטי.

זה Task ויזואלי בלבד. **הקומפוננטה מקבלת `status` (לצבע ה-dot) + `label` (טקסט)** — ה-pages ממשיכות לשלוט במיפוי label דרך STATUS_LABELS שלהן (שיש בו וריאציות שונות בכל page).

## Done looks like
- קובץ חדש: `frontend/src/components/StatusPill.jsx`
- 3 קריאות בקוד מוחלפות מה-pill הצבעוני ל-`<StatusPill status={task.status} label={statusInfo.label} />`
- STATUS_LABELS המקומי בכל page **נשאר כמו שהוא** — לא נמחק. ממשיכים להשתמש ב-`statusInfo.label` ו-`statusInfo.color` במקומות אחרים בקוד אם יש.
- Build עובר.
- ויזואלית: כל pill הופך ל-`bg-slate-100 text-slate-700` עם dot קטן.

## File 1: צור `frontend/src/components/StatusPill.jsx` (חדש)

```jsx
import React from 'react';

const STATUS_DOT = {
  open:                       'bg-red-500',
  assigned:                   'bg-orange-500',
  in_progress:                'bg-blue-500',
  pending_contractor_proof:   'bg-orange-500',
  pending_manager_approval:   'bg-indigo-500',
  returned_to_contractor:     'bg-rose-500',
  waiting_verify:             'bg-purple-500',
  closed:                     'bg-emerald-500',
  reopened:                   'bg-amber-500',
};

const StatusPill = ({ status, label, className = '' }) => {
  const dot = STATUS_DOT[status] || 'bg-slate-400';
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[11px] font-medium whitespace-nowrap ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
};

export default StatusPill;
```

⚠️ ה-9 statuses ב-STATUS_DOT מכסים את האיחוד המלא של מה ש-UnitDetailPage ו-ApartmentDashboardPage משתמשים בו. אם status לא ידוע — fallback ל-slate.

## File 2: `frontend/src/pages/UnitDetailPage.js`

הוסף import בראש הקובץ (אחרי שאר ה-imports של components):
```jsx
import StatusPill from '../components/StatusPill';
```

החלף שורות 280–282:

BEFORE:
```jsx
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
```

AFTER:
```jsx
                        <StatusPill status={task.status} label={statusInfo.label} />
```

⚠️ **אסור** למחוק את `STATUS_LABELS` בראש הקובץ (שורה 14) — הוא הולך להמשיך לספק את `statusInfo.label`. רק ה-render משתנה.

## File 3: `frontend/src/pages/ApartmentDashboardPage.js`

הוסף import:
```jsx
import StatusPill from '../components/StatusPill';
```

יש 2 מופעים, **שניהם עם class נוסף `whitespace-nowrap`** — זה כבר ב-default של StatusPill, אז אפשר פשוט לוותר עליו.

החלף שורות 443–445:

BEFORE:
```jsx
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
```

AFTER:
```jsx
                        <StatusPill status={task.status} label={statusInfo.label} />
```

החלף שורות 695–697 (אותו דפוס בדיוק):

BEFORE:
```jsx
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
```

AFTER:
```jsx
                        <StatusPill status={task.status} label={statusInfo.label} />
```

⚠️ **אסור** למחוק את `STATUS_LABELS` בראש הקובץ (שורה 26) — נשאר.

## DO NOT
- ❌ אל תיגע ב-`HandoverTabPage.js` או `HandoverProtocolPage.js` — שם יש `STATUS_LABELS` עם vocabulary שונה (draft / signed / etc) ושיוך של אייקונים מורכב יותר. **לא בסקופ של הספק הזה.**
- ❌ אל תיגע ב-status pills של admin (`AdminUsersPage.js`, `AdminDashboardPage.js`, `OrgBillingPage.js`) — שם זה subscription status, vocabulary שונה.
- ❌ אל תמחק את ה-STATUS_LABELS בכל קובץ — הם נשארים. הם מספקים את ה-label לקומפוננטה.
- ❌ אל תוסיף props ל-StatusPill מעבר ל-`status`, `label`, `className` (אופציונלי לעקיפות עתידיות).
- ❌ אל תיגע ב-PRIORITY_CONFIG, ב-tCategory, או ב-pills אחרים.
- ❌ אל תוסיף i18n ל-StatusPill — ה-labels מגיעים מבחוץ.

## VERIFY
1. `git status` — בדיוק 3 קבצים: 1 חדש (`StatusPill.jsx`) + 2 modified (`UnitDetailPage.js`, `ApartmentDashboardPage.js`).
2. `cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build` — חייב לעבור.
3. `grep -n "px-2 py-0.5 rounded-full font-medium.*statusInfo" frontend/src/pages/UnitDetailPage.js frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר **0 תוצאות** (כל ה-pills הוחלפו ב-StatusPill).
4. `grep -n "import StatusPill" frontend/src/pages/UnitDetailPage.js frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר 2 תוצאות.
5. `grep -n "STATUS_LABELS" frontend/src/pages/UnitDetailPage.js frontend/src/pages/ApartmentDashboardPage.js` — חייב להחזיר את אותן תוצאות כמו לפני (לא נמחקו).
6. `git diff backend/` — ריק.
7. אחרי deploy: פתח דירה עם ליקויים → כל ה-pills באותו רקע אפור עם נקודה צבעונית קטנה משמאל לטקסט.

## Risks
🟡 בינוני-נמוך. שינוי ויזואלי בולט (כל pills בעמוד הליקויים משתנים). אם המשתמש לא יאהב — easy revert. data flow לא משתנה.

## Relevant files
- `frontend/src/components/StatusPill.jsx` (חדש)
- `frontend/src/pages/UnitDetailPage.js` שורות 280–282
- `frontend/src/pages/ApartmentDashboardPage.js` שורות 443–445, 695–697
