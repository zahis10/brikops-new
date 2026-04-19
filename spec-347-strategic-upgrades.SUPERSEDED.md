# [SUPERSEDED 16/04/2026] #347 — Strategic Upgrades

> **⚠️ ספק זה הוחלף.** הוא פוצל ל‑4 ספקים נפרדים בעקבות סיכון גבוה לבצע אותם ביחד:
>
> - **#347 — DesktopShell + Sidebar** ראה `spec-347-desktop-shell.md`
> - **#348 — Dark Mode** ראה `spec-348-dark-mode.md`
> - **#349 — Onboarding Tour + Activity Feed** ראה `spec-349-onboarding-activity.md`
> - **#350 — PWA Manifest + Web Push** ראה `spec-350-pwa-push.md`
>
> אל תבצע את הספק הזה כמסמך אחד. הוא נשאר לתיעוד היסטורי בלבד.

---

# #347 — Strategic Upgrades (DesktopShell sidebar, Dark Mode, Onboarding tour, Activity feed, Empty‑state illustrations, PWA splash) [ORIGINAL — DO NOT EXECUTE]

## What & Why
ספק זה מעלה את BrikOps מ‑7.8 ל‑8.7 — מ"מוצר B2B מהשורה הראשונה" ל"מוצר שמתחרה ב‑Procore / Buildup ברמה החזותית והחווייתית". זה ספק ארוך ומסוכן יותר משני הקודמים — צפי ~120 שעות. **חובה לבצע בפאזות נפרדות**, עם merge ו‑QA בין כל פאזה. אין לבצע הכל ב‑PR אחד.

הפיצ'רים: layout דסקטופ עם סיידבר קבוע (במקום header‑only mobile UI על desktop), Dark Mode מלא דרך Tailwind dark:, Onboarding Tour אינטראקטיבי בכניסה ראשונה, Activity Feed widget בעמוד הפרויקט, איורי empty state בהתאמה אישית (3-5), ו‑PWA splash + push notifications iOS/Android.

## Done looks like
- במסך ≥1024px: סיידבר קבוע משמאל (RTL → ימין) ברוחב 240px עם ניווט ראשי. Header מצטמצם
- כל מסך באפליקציה תומך ב‑Dark Mode דרך toggle ב‑User Drawer; הבחירה נשמרת ב‑localStorage
- משתמש שנכנס פעם ראשונה לאפליקציה רואה Tour של 4 צעדים (פרויקט → בניין → דירה → ליקוי). אפשר לדלג ולא לחזור
- בעמוד פרויקט יש widget של "פעילות אחרונה" שמראה 5 הליקויים האחרונים שעודכנו עם timestamp יחסי
- ב‑3 empty states עיקריים (אין פרויקטים / אין ליקויים / אין דוחות) יש איור SVG inline מקצועי (לא Lucide גנרי)
- PWA: יש splash screen שמתאים לגודל המכשיר, manifest מוגדר, push notifications פועלות ל‑iOS Safari (PWA) ו‑Android Chrome
- אין רגרסיה מספקים 345 + 346

## Out of scope
- אין לבנות עדיין web push backend הדמיה (שלח דרך iOS APNs / Android FCM — דרוש backend חדש)
- אין לעשות migration של ה‑i18n ל‑i18next (נשאר עם ה‑helpers הקיימים)
- אין לבנות Theme Editor למשתמש (רק Light/Dark)
- אין לבנות עדיין offline mode (זה ספק בנפרד)
- אין לעשות migration של routing ל‑Next.js או Remix
- אין לגעת ב‑schema של MongoDB
- אין להוסיף Analytics SDK חדש

## Phased Execution

### Phase 1: DesktopShell + Sidebar (~40h)
Tasks 1, 2, 3.
**STOP. PR. QA. Merge. רק אז המשך.**

### Phase 2: Dark Mode (~25h)
Tasks 4, 5, 6.
**STOP. PR. QA. Merge.**

### Phase 3: Onboarding Tour + Activity Feed (~25h)
Tasks 7, 8.
**STOP. PR. QA. Merge.**

### Phase 4: Empty‑state Illustrations + PWA (~30h)
Tasks 9, 10, 11.

## Tasks

### PHASE 1 — Desktop Layout

### Task 1 — צור `DesktopShell` Layout Component
**File חדש:** `frontend/src/components/layout/DesktopShell.jsx`
**File חדש:** `frontend/src/components/layout/Sidebar.jsx`
**File חדש:** `frontend/src/components/layout/MobileHeader.jsx`

צור קומפוננטת layout שעוטפת את כל ה‑routes (פרט ל‑login):

```jsx
// DesktopShell.jsx
import React from 'react';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import Sidebar from './Sidebar';
import MobileHeader from './MobileHeader';

const DesktopShell = ({ children }) => {
  const isDesktop = useMediaQuery('(min-width: 1024px)');

  if (isDesktop) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex" dir="rtl">
        <Sidebar />
        <main className="flex-1 min-w-0">
          {children}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" dir="rtl">
      <MobileHeader />
      <main>{children}</main>
    </div>
  );
};

export default DesktopShell;
```

**Sidebar.jsx** — קומפוננטה רוחב 240px עם:
- לוגו BrikOps בראש
- ProjectSwitcher (העתק מהקיים, אבל בורציה אנכית)
- ניווט ראשי (Lucide icons + label):
  - דשבורד / Home
  - פרויקטים
  - ליקויים
  - דוחות
  - הגדרות
- Spacer
- User profile button בתחתית עם avatar + שם
- Theme toggle (Sun/Moon)

**MobileHeader.jsx** — נשאר בדיוק כמו ה‑header הקיים (העתק מ‑MyProjectsPage.js / ProjectControlPage.js). רק לוגיקה: מציגים אותו רק כש‑viewport < 1024px.

**`useMediaQuery` hook חדש** (`frontend/src/hooks/useMediaQuery.js`):
```js
import { useState, useEffect } from 'react';

export const useMediaQuery = (query) => {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e) => setMatches(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [query]);

  return matches;
};
```

### Task 2 — עטיפת Routes ב‑DesktopShell
**File:** `frontend/src/App.js`

עטוף את כל ה‑Routes שדורשים auth ב‑`<DesktopShell>`. לוגיקה: רק routes של post‑login (לא Login / Register / Forgot / WaLogin).

```bash
grep -n "<Routes>\|<Route" frontend/src/App.js | head -30
```

הוסף `import DesktopShell from './components/layout/DesktopShell';` בראש.

```jsx
// בתוך הקומפוננטה הראשית — סדר חדש:
<Routes>
  {/* Public routes - אין DesktopShell */}
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
  ...

  {/* Protected routes - תחת DesktopShell */}
  <Route path="/projects" element={<DesktopShell><MyProjectsPage /></DesktopShell>} />
  <Route path="/projects/:projectId" element={<DesktopShell><ProjectControlPage /></DesktopShell>} />
  ...
</Routes>
```

**אזהרה:** אל תעטוף את `LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`, `WaLoginPage`, `OnboardingPage`, `PendingApprovalPage`, `PendingDeletionPage`, `PaymentSuccessPage`, `PaymentFailurePage` — אלה דפים שעצמאיים מבחינה ויזואלית.

### Task 3 — הסר `max-w-lg mx-auto` בעמודי תוכן עיקריים על Desktop
**Files:** `frontend/src/pages/UnitDetailPage.js` line 127, 147, 175 וכו'
**Files:** `frontend/src/pages/BuildingDefectsPage.js` (אותו pattern)

על Desktop, `max-w-lg` (512px) נראה מגוחך — column צר במרכז של מסך 1440px.

החלף:
```jsx
// BEFORE
<div className="max-w-lg mx-auto px-4 py-3">

// AFTER
<div className="max-w-lg lg:max-w-4xl mx-auto px-4 lg:px-8 py-3">
```

עיקרון: עד 1024px נשאר כמו mobile (max‑w‑lg). מ‑1024px ומעלה — `max‑w‑4xl` (896px) או `max‑w‑5xl` בעמודים עם רשימות ארוכות.

```bash
grep -rn "max-w-lg mx-auto" frontend/src/pages/ | head -20
```

עדכן את כולם בהדרגה (קל ל‑search‑and‑replace).

---

### PHASE 2 — Dark Mode

### Task 4 — אפשר `darkMode: 'class'` ב‑Tailwind + Theme Provider
**File:** `frontend/tailwind.config.js`

הוסף:
```js
module.exports = {
  darkMode: 'class', // הוסף שורה זו בראש האובייקט
  content: [...],
  ...
};
```

**File חדש:** `frontend/src/contexts/ThemeContext.js`

```jsx
import React, { createContext, useContext, useEffect, useState } from 'react';

const ThemeContext = createContext({ theme: 'light', toggleTheme: () => {} });

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('brikops-theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('brikops-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
```

**File:** `frontend/src/App.js` — עטוף את כל ה‑app:
```jsx
<ThemeProvider>
  <AuthProvider>
    ...
  </AuthProvider>
</ThemeProvider>
```

הוסף ב‑Sidebar (Task 1) toggle button:
```jsx
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

// בתחתית ה‑sidebar
const { theme, toggleTheme } = useTheme();
<button onClick={toggleTheme} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
  {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
</button>
```

### Task 5 — הוסף `dark:` Variants ל‑5 דפים מרכזיים
**Files:**
- `frontend/src/pages/MyProjectsPage.js`
- `frontend/src/pages/ProjectControlPage.js` (חלקים עיקריים — לא הכל)
- `frontend/src/pages/UnitDetailPage.js`
- `frontend/src/pages/BuildingDefectsPage.js`
- `frontend/src/pages/AccountSettingsPage.js`

**מיפוי צבעים אחיד (חובה לעקוב!):**

| Light | Dark |
|---|---|
| `bg-white` | `dark:bg-slate-900` |
| `bg-slate-50` | `dark:bg-slate-950` |
| `bg-slate-100` | `dark:bg-slate-800` |
| `bg-amber-500` | `dark:bg-amber-500` (נשאר — accent) |
| `text-slate-900` | `dark:text-slate-50` |
| `text-slate-700` | `dark:text-slate-200` |
| `text-slate-500` | `dark:text-slate-400` |
| `border-slate-200` | `dark:border-slate-800` |
| `border-slate-300` | `dark:border-slate-700` |
| `from-amber-500 to-amber-600` | (נשאר זהה) |

דוגמה ל‑UnitDetailPage line 125:
```jsx
// BEFORE
<div className="min-h-screen bg-slate-50 pb-24" dir="rtl">

// AFTER
<div className="min-h-screen bg-slate-50 dark:bg-slate-950 pb-24" dir="rtl">
```

ולכרטיס (line 148):
```jsx
// BEFORE
<div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">

// AFTER
<div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 p-4">
```

**אסור** לעשות grep‑replace אוטומטי — חלק מה‑bg‑white הם בכוונה (מודלים, dropdowns) ודורשים shade שונה. לעבור ידנית קובץ אחד אחרי השני.

### Task 6 — Toaster + Sonner + ה‑Modals
**File:** `frontend/src/components/ui/sonner.jsx`
**Files:** `frontend/src/components/NewDefectModal.js`, `PaywallModal.js`, `UpgradeWizard.js`, `CompleteAccountModal.js`

ה‑Sonner toast חייב להחליף צבעים בהתאם ל‑theme. בדוק את ה‑initial setup ב‑`sonner.jsx` והחלף את ה‑theme prop:

```jsx
import { useTheme } from '@/contexts/ThemeContext';
const { theme } = useTheme();
<Sonner theme={theme} ... />
```

ה‑modals: עבור על כל אחד והחלף `bg-white` ל‑`bg-white dark:bg-slate-900`, וכו'. דורש attention ידנית לכל overlay (overlay opacity לא משתנה).

---

### PHASE 3 — Onboarding + Activity Feed

### Task 7 — Onboarding Tour 4 צעדים
**File חדש:** `frontend/src/components/OnboardingTour.jsx`
**File:** `frontend/src/contexts/AuthContext.js` (שדה `onboarding_completed` במשתמש)

השתמש בספרייה הקיימת (אם יש) — אחרת:
```bash
npm install react-joyride@2.7.x --save
```

צור ב‑`OnboardingTour.jsx`:
```jsx
import Joyride, { STATUS } from 'react-joyride';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const STEPS = [
  {
    target: '[data-tour="my-projects"]',
    content: 'כאן תראה את כל הפרויקטים שלך. כל פרויקט הוא בניין/בניינים שאתה אחראי עליהם.',
    disableBeacon: true,
  },
  {
    target: '[data-tour="project-card"]:first-of-type',
    content: 'לחץ על פרויקט כדי להיכנס לעמוד הניהול שלו — שם תוכל ליצור בניינים, קומות, דירות.',
  },
  {
    target: '[data-tour="create-defect-fab"]',
    content: 'הכפתור הצף הזה הוא הקיצור לרישום ליקוי חדש מכל מסך באפליקציה.',
  },
  {
    target: '[data-tour="notifications-bell"]',
    content: 'כאן תקבל התראות על ליקויים שטופלו או שינויים בסטטוס. סיימת!',
  },
];

const OnboardingTour = () => {
  const { user, refreshUser } = useAuth();
  const [run, setRun] = React.useState(false);

  React.useEffect(() => {
    if (user && !user.onboarding_completed) {
      setTimeout(() => setRun(true), 800); // delay לטעינת ה‑DOM
    }
  }, [user]);

  const handleCallback = async (data) => {
    if (data.status === STATUS.FINISHED || data.status === STATUS.SKIPPED) {
      setRun(false);
      // POST /me/onboarding-complete
      await fetch('/api/me/onboarding-complete', { method: 'POST', headers: { Authorization: `Bearer ${token}` }});
      await refreshUser();
    }
  };

  return (
    <Joyride
      steps={STEPS}
      run={run}
      continuous
      showProgress
      showSkipButton
      locale={{ back: 'הקודם', close: 'סגור', last: 'סיים', next: 'הבא', skip: 'דלג', open: 'פתח' }}
      styles={{ options: { primaryColor: '#F59E0B', zIndex: 10000 } }}
      callback={handleCallback}
    />
  );
};

export default OnboardingTour;
```

הוסף את ה‑attributes `data-tour="..."` ב:
- MyProjectsPage.js — header → `data-tour="my-projects"`
- MyProjectsPage.js — project card → `data-tour="project-card"`
- UnitDetailPage.js — submit button → `data-tour="create-defect-fab"`
- NotificationBell.js — `data-tour="notifications-bell"`

**Backend:** הוסף endpoint `POST /me/onboarding-complete` שמעדכן `users.onboarding_completed = True`. (זה השינוי היחיד ל‑backend בכל הספק — דרוש כי המצב שמור ב‑DB, לא רק ב‑localStorage.)

### Task 8 — Activity Feed Widget
**File חדש:** `frontend/src/components/ActivityFeed.jsx`
**File:** `frontend/src/pages/ProjectControlPage.js` (הוסף לעמוד הראשי)
**File:** `backend/contractor_ops/projects_router.py` (endpoint חדש)

**Backend:** הוסף `GET /projects/{id}/activity?limit=10` שמחזיר 10 task_updates האחרונים ל‑project, עם `{task_id, task_title, status_from, status_to, updated_by_name, updated_at}`.

```python
@router.get("/{project_id}/activity")
async def get_project_activity(project_id: str, user = Depends(get_current_user), limit: int = Query(10, le=50)):
    # query task_updates collection where task.project_id == project_id, sort updated_at desc
    ...
```

**Frontend:**
```jsx
const ActivityFeed = ({ projectId }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/projects/${projectId}/activity?limit=10`).then(r => {
      setItems(r.data.items || []);
      setLoading(false);
    });
  }, [projectId]);

  if (loading) return <ListSkeleton rows={4} />;
  if (items.length === 0) return null;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
      <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">פעילות אחרונה</h3>
      <ul className="space-y-2">
        {items.map(item => (
          <li key={item.id} className="text-xs flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-slate-700 dark:text-slate-300 truncate">
                <span className="font-medium">{item.updated_by_name}</span> עדכן: {item.task_title}
              </p>
              <p className="text-[10px] text-slate-400">{relativeTime(item.updated_at)}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};
```

הוסף `relativeTime` helper ב‑`utils/formatters.js`:
```js
export const relativeTime = (iso) => {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'לפני רגע';
  if (diff < 3600) return `לפני ${Math.floor(diff / 60)} דקות`;
  if (diff < 86400) return `לפני ${Math.floor(diff / 3600)} שעות`;
  if (diff < 604800) return `לפני ${Math.floor(diff / 86400)} ימים`;
  return new Date(iso).toLocaleDateString('he-IL');
};
```

הוסף `<ActivityFeed projectId={projectId} />` בעמוד ProjectControlPage באזור עליון‑ימני (אחרי ה‑KPI cards), grid 2 columns על desktop.

---

### PHASE 4 — Empty States Illustrations + PWA

### Task 9 — Empty State Illustrations
**File חדש:** `frontend/src/components/illustrations/EmptyProjects.jsx`
**File חדש:** `frontend/src/components/illustrations/EmptyDefects.jsx`
**File חדש:** `frontend/src/components/illustrations/EmptyReports.jsx`

צור 3 איורים SVG inline (לא תמונות). עיקרון: סגנון line‑art, עפרון 1.5px, צבעים `slate-300` + accent `amber-400`. גודל 200×160. דוגמה:

```jsx
const EmptyProjects = ({ className = '' }) => (
  <svg className={className} width="200" height="160" viewBox="0 0 200 160" fill="none">
    {/* בניין שלד */}
    <rect x="60" y="50" width="80" height="100" stroke="currentColor" strokeWidth="1.5" className="text-slate-300 dark:text-slate-700" />
    <line x1="60" y1="80" x2="140" y2="80" stroke="currentColor" strokeWidth="1.5" className="text-slate-300 dark:text-slate-700" />
    <line x1="60" y1="110" x2="140" y2="110" stroke="currentColor" strokeWidth="1.5" className="text-slate-300 dark:text-slate-700" />
    <line x1="100" y1="50" x2="100" y2="150" stroke="currentColor" strokeWidth="1.5" className="text-slate-300 dark:text-slate-700" />
    {/* עיגול accent */}
    <circle cx="155" cy="40" r="8" fill="currentColor" className="text-amber-400" />
    <path d="M152 40l3 3 6-6" stroke="white" strokeWidth="1.5" />
  </svg>
);
```

עדכן ב‑empty states הקיימים:
- MyProjectsPage.js — כשאין פרויקטים → `<EmptyProjects />` + "עוד אין פרויקטים. צור פרויקט ראשון לתחילת העבודה."
- UnitDetailPage.js + ProjectControlPage.js — כשאין ליקויים → `<EmptyDefects />` + "הדירה נקייה — לא דווחו ליקויים."
- ContractorDashboard.js — כשאין דוחות → `<EmptyReports />`

### Task 10 — PWA Manifest + Splash
**File:** `frontend/public/manifest.json`
**File:** `frontend/public/index.html`
**Files חדשים:** splash images (icons-192.png, icons-512.png + 8 גדלי iOS splash)

עדכן `manifest.json`:
```json
{
  "short_name": "BrikOps",
  "name": "BrikOps - ניהול ליקויי בנייה",
  "description": "פלטפורמת ניהול ליקויים, QC ומסירה לקבלנים",
  "icons": [
    { "src": "icons/icon-192.png", "type": "image/png", "sizes": "192x192", "purpose": "any" },
    { "src": "icons/icon-512.png", "type": "image/png", "sizes": "512x512", "purpose": "any" },
    { "src": "icons/icon-maskable.png", "type": "image/png", "sizes": "512x512", "purpose": "maskable" }
  ],
  "start_url": "/projects",
  "display": "standalone",
  "theme_color": "#F59E0B",
  "background_color": "#F8FAFC",
  "orientation": "portrait",
  "lang": "he",
  "dir": "rtl"
}
```

הוסף ל‑`index.html` <head>:
```html
<link rel="apple-touch-icon" href="%PUBLIC_URL%/icons/icon-192.png" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="BrikOps" />

<!-- iOS Splash screens (generated by tool) -->
<link rel="apple-touch-startup-image" href="%PUBLIC_URL%/splash/iphone15-portrait.png"
      media="(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3) and (orientation: portrait)" />
<!-- ... 7 more for iPhone SE / 12 / 14 / 15 Pro Max / iPad ... -->
```

**אין** ליצור את ה‑PNG עצמן — זה תהליך עיצוב נפרד. הקובץ הזה מגדיר את ה‑structure ומשאיר placeholder ל‑Designer.

### Task 11 — Web Push Notifications
**File:** `frontend/src/services/pushNotifications.js` (חדש)
**File:** `backend/contractor_ops/notifications_router.py` (חדש)

**Frontend** — בקש הרשאה אחרי שהמשתמש משלים את ה‑Onboarding Tour (Task 7):
```js
export const requestPushPermission = async () => {
  if (!('Notification' in window) || !('serviceWorker' in navigator)) return null;
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return null;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: VAPID_PUBLIC_KEY,
  });
  // POST /me/push-subscribe with sub
  await api.post('/me/push-subscribe', sub.toJSON());
};
```

**Backend** — שתי endpoints:
- `POST /me/push-subscribe` → שמור ב‑`users.push_subscriptions[]`
- worker שמשגר notification בכל יצירת ליקוי / שינוי סטטוס שמשפיע על המשתמש

**אזהרה ל‑iOS:** Web Push פועל על iOS רק כש‑PWA מותקן (Add to Home Screen). הוסף banner ב‑first‑visit ב‑Safari iOS שמסביר איך להתקין.

**זה ה‑backend היחיד שצריך שינוי בכל הספק** (חוץ מהקצר של onboarding ב‑Task 7). דרוש Phase נפרד עם backend dev.

## Relevant files

### חדשים
- `frontend/src/components/layout/DesktopShell.jsx`
- `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/components/layout/MobileHeader.jsx`
- `frontend/src/hooks/useMediaQuery.js`
- `frontend/src/contexts/ThemeContext.js`
- `frontend/src/components/OnboardingTour.jsx`
- `frontend/src/components/ActivityFeed.jsx`
- `frontend/src/components/illustrations/EmptyProjects.jsx`
- `frontend/src/components/illustrations/EmptyDefects.jsx`
- `frontend/src/components/illustrations/EmptyReports.jsx`
- `frontend/src/services/pushNotifications.js`
- `backend/contractor_ops/notifications_router.py`

### עריכות
- `frontend/tailwind.config.js` (darkMode + sizes)
- `frontend/src/App.js` (DesktopShell wrap + ThemeProvider + OnboardingTour)
- `frontend/src/pages/MyProjectsPage.js` (max-w + dark + data-tour + EmptyProjects)
- `frontend/src/pages/ProjectControlPage.js` (max-w + dark + ActivityFeed + EmptyDefects)
- `frontend/src/pages/UnitDetailPage.js` (max-w + dark + EmptyDefects)
- `frontend/src/pages/BuildingDefectsPage.js` (max-w + dark)
- `frontend/src/pages/AccountSettingsPage.js` (dark)
- `frontend/src/pages/ContractorDashboard.js` (EmptyReports)
- `frontend/src/components/NotificationBell.js` (data-tour)
- `frontend/src/components/ui/sonner.jsx` (theme prop)
- `frontend/src/utils/formatters.js` (+relativeTime)
- `frontend/public/manifest.json` (PWA fields)
- `frontend/public/index.html` (apple meta + splash links)
- `backend/contractor_ops/projects_router.py` (+activity endpoint)

## DO NOT
- ❌ אל תבצע את הפאזות במקביל — חובה sequential
- ❌ אל תעשה global search‑and‑replace של `bg-white` → `bg-white dark:bg-slate-900` — חלק בכוונה
- ❌ אל תוסיף Theme Editor למשתמש (רק Light/Dark)
- ❌ אל תיגע ב‑routing המבנה הכללי (BrowserRouter, lazy loading) — רק עטיפה ב‑DesktopShell
- ❌ אל תעשה migration ל‑i18next
- ❌ אל תוסיף offline mode
- ❌ אל תוסיף Analytics SDK
- ❌ אל תיגע ב‑schema של MongoDB (רק users.onboarding_completed + users.push_subscriptions[])
- ❌ אל תיגע ב‑PhotoAnnotation.js
- ❌ אל תוסיף framer‑motion (Tailwind transitions בלבד)
- ❌ אל תשבור את ה‑mobile UX — חובה לבדוק ב‑320px / 375px / 768px
- ❌ אל תיצור splash images עצמן בקוד — זה תהליך design ידני

## VERIFY

### Phase 1 (DesktopShell)
1. **Mobile (375px):** אין סיידבר. Header מוצג כרגיל. הכל פועל כמו לפני.
2. **Desktop (1440px):** סיידבר 240px קבוע מימין (RTL). header מצטמצם או נעלם.
3. **Resize live:** גרור מ‑1100 → 900 → סיידבר נעלם, header חוזר. אין flicker.
4. **Routing:** lazy routes נטענים ב‑Suspense בתוך ה‑shell, לא שובר אותו.
5. **Login page:** אין סיידבר. עיצוב כמו לפני.

### Phase 2 (Dark Mode)
1. לחץ על Moon icon ב‑sidebar → כל המסך הופך לכהה תוך 200ms.
2. רענן את הדף → נשאר במצב Dark (localStorage).
3. בדוק 5 דפים מרכזיים — אין רכיב לבן בולט / טקסט לא קריא / borders שחורים.
4. בדוק modals בכל אחד מהמצבים — overlay אטום, רקע modal `bg-slate-900` ב‑dark.
5. ניגודיות — בדוק עם Lighthouse ב‑Dark Mode → חייב להיות ≥4.5:1 על טקסט רגיל.

### Phase 3 (Onboarding + Activity)
1. צור משתמש חדש (או הסר `onboarding_completed` ב‑DB) → היכנס → רואה את הצעד הראשון.
2. עבור 4 צעדים → "סיים" → POST /me/onboarding-complete נשלח (בדוק ב‑Network).
3. רענן → לא רואה Tour יותר.
4. לחץ "דלג" באמצע → אותו flow (POST נשלח).
5. בעמוד פרויקט יש widget Activity Feed עם 10 last updates.
6. relativeTime: "לפני 5 דקות" / "לפני 3 ימים" וכו'.

### Phase 4 (Illustrations + PWA)
1. EmptyProjects רואים ב‑MyProjectsPage כשאין פרויקטים. SVG inline, RTL נכון, dark mode עובד.
2. EmptyDefects ב‑UnitDetailPage כשאין ליקויים.
3. PWA: open Chrome → DevTools → Application → Manifest → רואה את כל ה‑fields חדשים.
4. iOS: Safari → "הוסף למסך הבית" → אייקון מופיע נכון, splash screen מופיע.
5. Web Push: אחרי Onboarding מופיע prompt להרשאה. אישור → ב‑DB יש subscription. שלח ליקוי → notification מופיע.

## Risks
- **DesktopShell** עלול לשבור את הפריסה של דפים שמסתמכים על `min-h-screen` ראש העמוד. חובה לבדוק כל route.
- **Dark Mode** דורש attention ידנית לכל component — קל להחמיץ. סבירות גבוהה לבאגים בסבב QA. תכננו זמן ל‑bug fixing.
- **react-joyride** הוא תלות חדשה ~20kb gzipped. אם רוצים ללא תלות → אפשר לבנות ידנית עם Radix Popover, אבל יש זמן עבודה נוסף ~10h.
- **Web Push iOS** דורש PWA מותקן (לא רק Safari) — חוויית UX מורכבת. ייתכן שווה לדחות את החלק הזה לספק נפרד.
- **VAPID keys + service worker** דורשים backend deployment + secret management. וודא שהתשתית קיימת לפני התחלת Task 11.

---

**זמן עבודה משוער כולל:** ~120 שעות (40 + 25 + 25 + 30)
**תוצאה צפויה:** ציון UX יעלה מ‑7.8 ל‑8.7
**תלות:** ספקים 345 + 346 חייבים להיות merged קודם
**הערה אסטרטגית:** ייתכן ששווה לפצל ל‑2-3 ספקים נפרדים לפי פאזות. הצפי הזה נכון רק אם מבצעים phase‑by‑phase.
