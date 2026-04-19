# #349 — Onboarding Tour + Activity Feed Widget (Phase 3 of old #347)

> **שינוי הסקופ (16/04/2026):** הספק המקורי #347 פוצל ל‑4. ספק זה הוא **שלב 3: Onboarding Tour + Activity Feed**. שני features שמעלים engagement ראשוני ו‑awareness שוטף. צפי ~25 שעות.

## What & Why
משתמש חדש שנכנס ל‑BrikOps פעם ראשונה רואה רשימת פרויקטים ריקה / מסך לא מוכר ולא יודע מה לעשות. **Onboarding Tour** של 4 צעדים מוביל אותו דרך הזרימה הראשית (פרויקט → בניין → דירה → ליקוי). פעם נוסעים, לא חוזר. בנוסף, בעמוד פרויקט ראשי, **Activity Feed widget** מציג 10 הליקויים האחרונים שעודכנו עם timestamp יחסי — זה נותן למנהל פרויקט תחושה של "הדופק" של הפרויקט בלי שיצטרך להיכנס לכל ליקוי. שני features שמרגישים מקצועיים ו‑sticky. אין שינויי backend גדולים — רק 2 endpoints חדשים קלים.

## Done looks like
- משתמש שלא השלים onboarding (`users.onboarding_completed = false`) רואה Tour אוטומטית 800ms אחרי הטעינה הראשונה של `/projects`
- Tour כולל 4 צעדים עם tooltips (react‑joyride): My Projects → Project Card → Create Defect FAB → Notifications Bell
- אפשר לדלג בכל שלב (Skip)
- בסיום (Finish/Skip) — POST `/me/onboarding-complete` → DB מעודכן → לא רואים שוב
- כל צעד בעברית עם locale נכון של joyride
- ב‑ProjectControlPage יש widget "פעילות אחרונה" עם 10 update הכי חדשים
- כל item ב‑widget: `<DOT> {user_name} עדכן: {task_title}` + relativeTime
- לחיצה על item מנווטת ל‑task detail
- אם אין activity → ה‑widget לא מוצג (לא מציגים empty state)
- אין רגרסיות בספקים 345–348

## Out of scope
- אין notifications push (זה ספק 350)
- אין Activity Feed לכל הפרויקטים יחד (רק per‑project)
- אין filters ב‑Activity Feed
- אין realtime updates ב‑Activity Feed (polling ב‑mount בלבד)
- אין Re‑Tour אחרי שהמשתמש סיים (חד פעמי בלבד)
- אין Onboarding לכל role (admin / contractor / qc) — אותו tour לכולם בשלב הזה
- אין analytics על השלמת tour (יוסיפו בעתיד)
- אין export ל‑CSV של activity

## Tasks

### Backend Tasks (2 endpoints)

### Task 1 — Endpoint: `POST /me/onboarding-complete`
**File:** `backend/contractor_ops/users_router.py` (או דומה — חפש את הקובץ עם `/me` endpoints)

```bash
grep -rn "users_router\|@router.get.*\"/me\"" backend/contractor_ops/ | head -10
```

הוסף:
```python
@router.post("/me/onboarding-complete")
async def complete_onboarding(current_user = Depends(get_current_user)):
    """Mark current user as having completed onboarding tour."""
    await users_collection.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"onboarding_completed": True, "onboarding_completed_at": datetime.utcnow()}}
    )
    return {"ok": True}
```

**DB migration:** וודא ש‑`users` collection תומך בשדה (MongoDB schemaless — אין צורך ב‑migration formal). השדה ייווצר ב‑update הראשון.

ודא שב‑`get_current_user` או ב‑`/me` GET endpoint, השדה `onboarding_completed` מוחזר ל‑frontend (default `False`):
```python
return {
    ...,
    "onboarding_completed": user.get("onboarding_completed", False),
}
```

### Task 2 — Endpoint: `GET /projects/{id}/activity`
**File:** `backend/contractor_ops/projects_router.py`

```python
from typing import Optional
from fastapi import Query

@router.get("/{project_id}/activity")
async def get_project_activity(
    project_id: str,
    user = Depends(get_current_user),
    limit: int = Query(10, le=50),
):
    """Return last N task updates for project, sorted by updated_at desc."""
    # Verify access
    await assert_project_access(user, project_id)

    # Aggregate: tasks → updates with task title + user name
    pipeline = [
        {"$match": {"project_id": project_id}},
        {"$sort": {"updated_at": -1}},
        {"$limit": limit},
        {"$lookup": {
            "from": "users",
            "localField": "updated_by",
            "foreignField": "_id",
            "as": "user_doc"
        }},
        {"$unwind": {"path": "$user_doc", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "task_id": "$_id",
            "task_title": "$title",
            "status_from": 1,
            "status_to": "$status",
            "updated_by_name": "$user_doc.name",
            "updated_at": 1,
        }}
    ]
    items = await tasks_collection.aggregate(pipeline).to_list(length=limit)
    return {"items": items}
```

**אופציה אלטרנטיבית** אם יש collection נפרד `task_updates`:
```python
# match על task_updates ישירות
{"$match": {"project_id": project_id}}
```

**Index חובה ל‑performance:**
```python
# בקריאה ראשונה / migration script
await tasks_collection.create_index([("project_id", 1), ("updated_at", -1)])
```

בלי ה‑index, השאילתה תהיה איטית כש‑project_id יש לו 1000+ tasks.

### Frontend Tasks

### Task 3 — תלות: `react-joyride`
**File:** `frontend/package.json`

```bash
cd frontend
npm install react-joyride@2.7.x --save
```

**גודל:** ~20kb gzipped + popper.js peer dep (~5kb).

**אלטרנטיבה אם רוצים אפס תלות:** לבנות tour ידני עם Radix Popover. עלות: +10 שעות עבודה. **המלצה:** קח את joyride — זה standard.

### Task 4 — Component: `OnboardingTour.jsx`
**File חדש:** `frontend/src/components/OnboardingTour.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import Joyride, { STATUS } from 'react-joyride';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../services/api';

const STEPS = [
  {
    target: '[data-tour="my-projects"]',
    content: 'כאן תראה את כל הפרויקטים שלך — בניין או קבוצת בניינים שאתה אחראי עליהם.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tour="project-card"]',
    content: 'לחץ על פרויקט כדי להיכנס לעמוד הניהול שלו. שם תוכל ליצור בניינים, קומות, ודירות.',
    placement: 'top',
  },
  {
    target: '[data-tour="create-defect-fab"]',
    content: 'הכפתור הצף הזה הוא הקיצור לרישום ליקוי חדש — בכל מסך באפליקציה.',
    placement: 'left',
  },
  {
    target: '[data-tour="notifications-bell"]',
    content: 'כאן תקבל התראות על ליקויים שטופלו, תזכורות, ושינויי סטטוס. סיימת!',
    placement: 'bottom',
  },
];

const OnboardingTour = () => {
  const { user, refreshUser } = useAuth();
  const location = useLocation();
  const [run, setRun] = useState(false);

  useEffect(() => {
    // Trigger only:
    // 1. Logged in
    // 2. Onboarding NOT completed
    // 3. Currently on /projects (initial landing)
    if (user && !user.onboarding_completed && location.pathname === '/projects') {
      const t = setTimeout(() => setRun(true), 800); // wait for DOM mount
      return () => clearTimeout(t);
    }
  }, [user, location.pathname]);

  const handleCallback = async (data) => {
    const { status } = data;
    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      setRun(false);
      try {
        await api.post('/me/onboarding-complete');
        await refreshUser();
      } catch (e) {
        console.error('Failed to mark onboarding complete', e);
        // Even on failure, hide tour for this session via local state
      }
    }
  };

  return (
    <Joyride
      steps={STEPS}
      run={run}
      continuous
      showProgress
      showSkipButton
      hideCloseButton
      disableScrolling={false}
      locale={{
        back: 'הקודם',
        close: 'סגור',
        last: 'סיימתי',
        next: 'הבא',
        skip: 'דלג',
        open: 'פתח',
      }}
      styles={{
        options: {
          primaryColor: '#F59E0B',
          textColor: '#0F172A',
          backgroundColor: '#FFFFFF',
          overlayColor: 'rgba(15, 23, 42, 0.6)',
          arrowColor: '#FFFFFF',
          zIndex: 10000,
        },
        tooltipContainer: {
          textAlign: 'right',
        },
        buttonNext: {
          fontFamily: 'Heebo, sans-serif',
          fontSize: 14,
        },
        buttonBack: {
          fontFamily: 'Heebo, sans-serif',
          fontSize: 14,
          color: '#64748B',
        },
      }}
      callback={handleCallback}
    />
  );
};

export default OnboardingTour;
```

**File:** `frontend/src/App.js` — הוסף את ה‑Tour כ‑sibling ל‑Routes (אחרי Toaster):
```jsx
import OnboardingTour from './components/OnboardingTour';

// בתוך App component, אחרי Routes:
<OnboardingTour />
<Toaster />
```

### Task 5 — הוספת `data-tour` attributes
**Files:**
- `frontend/src/pages/MyProjectsPage.js` — בכותרת `<header>` הוסף `data-tour="my-projects"`. בכרטיס פרויקט הראשון (אם הוא בלולאה — `idx === 0` בלבד) הוסף `data-tour="project-card"`.
- `frontend/src/pages/UnitDetailPage.js` — בכפתור הוספת ליקוי (FAB?) או ב‑NewDefect button — הוסף `data-tour="create-defect-fab"`.
- `frontend/src/components/NotificationBell.js` — בעיגול התראות הוסף `data-tour="notifications-bell"`.

```bash
grep -n "<header" frontend/src/pages/MyProjectsPage.js
grep -n "NewDefectModal\|setShowNewDefect\|+ ליקוי" frontend/src/pages/UnitDetailPage.js
```

**אזהרה:** ה‑Tour פותח את הצעדים בסדר. אם משתמש לוחץ "הבא" בצעד 1 והוא עדיין ב‑/projects, הצעד 2 דורש שכרטיס פרויקט יהיה במסך. אם הרשימה ריקה (משתמש חדש בלי פרויקטים) — הצעד נכשל. הפתרון: זרוק skip אוטומטי על הצעד אם target לא קיים:
```jsx
// ב-Joyride props:
spotlightClicks={false}
disableOverlayClose={true}
```

או — הצג Tour רק אחרי שהמשתמש יצר פרויקט ראשון. תכנן לפי החלטה של מוצר.

### Task 6 — Component: `ActivityFeed.jsx`
**File חדש:** `frontend/src/components/ActivityFeed.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Skeleton } from './ui/skeleton';
import { Activity } from 'lucide-react';
import api from '../services/api';
import { relativeTime } from '../utils/formatters';

const ActivityFeed = ({ projectId }) => {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get(`/projects/${projectId}/activity?limit=10`)
      .then(r => {
        if (!cancelled) {
          setItems(r.data.items || []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setItems([]);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [projectId]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">פעילות אחרונה</h3>
        </div>
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-start gap-2">
              <Skeleton className="w-1.5 h-1.5 rounded-full mt-1.5" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-2 w-1/3" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (items.length === 0) return null;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-amber-500" />
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">פעילות אחרונה</h3>
      </div>
      <ul className="space-y-2">
        {items.map(item => (
          <li key={item.task_id || item._id}>
            <button
              onClick={() => navigate(`/tasks/${item.task_id || item._id}`)}
              className="w-full text-right flex items-start gap-2 p-2 -mx-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-700 dark:text-slate-300 truncate leading-5">
                  <span className="font-medium">{item.updated_by_name || 'משתמש'}</span>
                  {' '}עדכן:{' '}
                  <span className="text-slate-600 dark:text-slate-400">{item.task_title}</span>
                </p>
                <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                  {relativeTime(item.updated_at)}
                </p>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default ActivityFeed;
```

### Task 7 — Helper: `relativeTime`
**File:** `frontend/src/utils/formatters.js`

```bash
ls frontend/src/utils/
```

הוסף (אם הקובץ קיים, אחרת צור):
```js
export const relativeTime = (iso) => {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'לפני רגע';
  if (diff < 3600) return `לפני ${Math.floor(diff / 60)} דקות`;
  if (diff < 86400) return `לפני ${Math.floor(diff / 3600)} שעות`;
  if (diff < 604800) return `לפני ${Math.floor(diff / 86400)} ימים`;
  if (diff < 2592000) return `לפני ${Math.floor(diff / 604800)} שבועות`;
  return new Date(iso).toLocaleDateString('he-IL');
};
```

### Task 8 — Mount ActivityFeed ב‑ProjectControlPage
**File:** `frontend/src/pages/ProjectControlPage.js`

מצא את האזור של ה‑KPI cards (סביב line 200–250 בהתחלה של הדף הראשי) — שם שמתחת ל‑KPIs יש בדרך כלל מקום פנוי. הוסף:
```jsx
import ActivityFeed from '../components/ActivityFeed';

// בתוך ה‑JSX, אחרי KPI cards:
<div className="px-4 lg:px-8 mt-4">
  <ActivityFeed projectId={projectId} />
</div>
```

או אם יש grid layout — הוסף בעמודה צדדית:
```jsx
<div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
  <div className="lg:col-span-2">
    {/* existing main content */}
  </div>
  <aside>
    <ActivityFeed projectId={projectId} />
  </aside>
</div>
```

החלטת layout תלויה במבנה הקיים — בדוק ידנית.

## Relevant files

### חדשים (3 קבצים frontend)
- `frontend/src/components/OnboardingTour.jsx`
- `frontend/src/components/ActivityFeed.jsx`
- `frontend/src/utils/formatters.js` (אם לא קיים — אחרת רק עריכה)

### עריכה Backend (2 endpoints)
- `backend/contractor_ops/users_router.py` (POST /me/onboarding-complete)
- `backend/contractor_ops/projects_router.py` (GET /:id/activity)

### עריכה Frontend
- `frontend/src/App.js` (mount OnboardingTour)
- `frontend/src/pages/MyProjectsPage.js` (data-tour attrs)
- `frontend/src/pages/UnitDetailPage.js` (data-tour attr)
- `frontend/src/components/NotificationBell.js` (data-tour attr)
- `frontend/src/pages/ProjectControlPage.js` (mount ActivityFeed)
- `frontend/package.json` (+react-joyride)

## DO NOT
- ❌ אל תוסיף Push Notifications — זה ספק 350
- ❌ אל תוסיף realtime sync ל‑ActivityFeed (WebSocket / SSE) — polling at mount בלבד
- ❌ אל תוסיף analytics tracking ב‑Tour (תוסף בעתיד)
- ❌ אל תוסיף Tour שונה לכל role — אחד לכולם בשלב הזה
- ❌ אל תוסיף Re‑Tour אופציה
- ❌ אל תיגע ב‑existing notifications system
- ❌ אל תוסיף filters ל‑ActivityFeed
- ❌ אל תייצא activity ל‑CSV
- ❌ אל תיצור index בלי לקרוא לראשי DBOps שלך — יכול להאט write performance בזמן build
- ❌ אל תפתח את ה‑Tour אם המשתמש כבר ב‑onboarding מותאם (PendingApproval, OnboardingPage) — בדוק ב‑location.pathname
- ❌ אל תיגע ב‑Onboarding existing flow (`OnboardingPage.js`) — הוא pre‑login, זה post‑login

## VERIFY

### Onboarding Tour
1. צור משתמש חדש (או הסר ידנית `onboarding_completed` ב‑MongoDB)
2. logout → login → אחרי 800ms רואה את הצעד הראשון (overlay אפור + tooltip)
3. הצעד מסומן מסביב לכותרת My Projects (focus area)
4. לחץ "הבא" → צעד 2 (project card)
5. לחץ "הבא" → צעד 3 (FAB)
6. לחץ "הבא" → צעד 4 (Notifications)
7. לחץ "סיימתי" → POST /me/onboarding-complete (בדוק ב‑Network)
8. רענן → לא רואה Tour יותר
9. נסה תרחיש אלטרנטיבי: לחץ "דלג" באמצע → אותו flow (POST נשלח)
10. logout → login → עדיין לא רואה (DB מעודכן)

### ActivityFeed
11. היכנס ל‑project עם history (יש כמה task updates)
12. ה‑widget "פעילות אחרונה" מוצג עם 10 פריטים אחרונים
13. כל פריט: שם משתמש + טקסט "עדכן:" + שם task + relativeTime
14. relativeTime: "לפני 5 דקות", "לפני 3 ימים", וכו'
15. לחץ על פריט → ניווט ל‑/tasks/:id
16. רענן בזמן שיש loading — מוצג Skeleton עם dots פולסים
17. בפרויקט ללא activity — ה‑widget לא מוצג בכלל (לא empty state)
18. שגיאת רשת → catch → empty array → widget לא מוצג

### Backend
19. `curl POST /me/onboarding-complete -H "Authorization: Bearer ..."` → 200 + DB update
20. `curl GET /projects/:id/activity?limit=10 -H "Authorization: ..."` → 200 + מערך of items
21. limit > 50 → 422 / 400 (Query validation)
22. user without project access → 403

### Edge Cases
23. ProjectControlPage עם 0 tasks → ActivityFeed לא מוצג
24. ProjectControlPage עם 100+ tasks → ה‑aggregate מחזיר רק 10 (נבדק ב‑network — payload קטן)
25. משתמש ש‑updated_by שלו null (deleted user) → fallback ל‑'משתמש'
26. ה‑Tour פתוח, המשתמש לוחץ X פיזית → onboarding_complete נשלח (status === SKIPPED)

### Performance
27. bundle size — תוספת ~25kb gzipped (joyride + popper)
28. ActivityFeed query — תחת 100ms עם index

## Risks
- **גבוה: react‑joyride z-index conflicts** — joyride משתמש ב‑zIndex 10000. PaywallModal ייתכן שגם בסביבה דומה. בדוק שה‑Tour תמיד מעל כל overlay אחר.
- **גבוה: data-tour על element שלא קיים** — אם המשתמש החדש אין לו פרויקטים, אין `<div data-tour="project-card">` במסך, joyride משלב בעיה. הפתרון: בדוק ב‑STEPS אם target קיים לפני run, או דחה את הצגת ה‑Tour עד שיש פרויקט. אופציה: הצג Tour רק בpost‑onboarding שיוצרים ראשון.
- **גבוה: Activity Feed query ללא index** — ב‑production אם תורצו 1000+ tasks ל‑project, השאילתה תוריד את ה‑DB. **חובה ליצור index לפני merge.**
- **בינוני: Tour ב‑Capacitor mobile** — joyride לא תוכנן ל‑mobile native. ייתכן ויזואל שונה. בדוק.
- **בינוני: Tour translation** — locale strings פשוטות אבל לא יודעים אם user סיני יראה רק עברית. בעבר נשאר רק he/en/ar/zh — בעתיד לשקול.
- **נמוך: relativeTime locale** — `toLocaleDateString('he-IL')` תקין לעברית. למשתמש סיני יחזיר תאריך עברי — לא קריטי.

## Rollback Plan
אם משהו שובר:
1. revert ה‑PR
2. ה‑endpoints ב‑backend נשארים — לא משפיעים אם הם לא נקראים
3. הקבצים החדשים (`OnboardingTour.jsx`, `ActivityFeed.jsx`) נשארים אבל לא מועלים ב‑mount
4. תלות `react-joyride` נשארת ב‑package.json — לא מזיק (tree-shaken אם לא ב‑use)

---

**זמן עבודה משוער:** ~25 שעות (15h frontend + 10h backend + QA)
**תוצאה צפויה:** ציון UX יעלה מ‑8.3 ל‑8.5
**תלות:** ספקים 345, 346, 347 חייבים להיות merged. ספק 348 (Dark Mode) אופציונלי לפני (ה‑components כאן תומכים בdark כבר)
**זמן QA אחרי merge:** יום עבודה
