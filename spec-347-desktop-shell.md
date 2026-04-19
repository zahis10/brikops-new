# #347 — DesktopShell Layout + Sidebar (Phase 1 of 4 from old #347)

> **שינוי הסקופ (16/04/2026):** הספק המקורי #347 (Strategic Upgrades) פוצל ל‑4 ספקים נפרדים בעקבות סיכון גבוה לבצע אותם ביחד. ספק זה הוא רק **שלב 1: DesktopShell + Sidebar**. שלבים 348 (Dark Mode), 349 (Onboarding+Activity), 350 (PWA+Push) הם ספקים נפרדים שמתבצעים אחר כך.

## What & Why
היום BrikOps נראה רק כמובייל גם כשהוא רץ במסך 1440px. כל header/footer מוגבלים ל‑`max-w-lg` (512px) באמצע מסך לבן ענק — בזבוז קיצוני של real estate. ספק זה מוסיף **DesktopShell** — layout shell שכאשר ה‑viewport ≥1024px מציג סיידבר קבוע מימין (RTL) ברוחב 240px עם ניווט ראשי, ובמובייל נשאר ה‑header הקיים ללא שינוי. זהו שינוי **ארכיטקטוני** ויש בו סיכון גבוה — לכן הוא לבד בספק אחד. צפי ~40 שעות. אין שינויי backend.

## Done looks like
- ב‑viewport ≥1024px מוצג סיידבר קבוע מימין ברוחב 240px עם:
  - לוגו BrikOps בראש
  - ProjectSwitcher (גרסה אנכית)
  - 5 קישורי ניווט עם Lucide icons + labels
  - User profile button בתחתית
- ב‑viewport <1024px נשאר ה‑MobileHeader הקיים ללא שינוי
- כל הדפים שדורשים auth (post‑login) עטופים ב‑`<DesktopShell>` ב‑App.js
- דפים פומביים (Login, Register, Forgot, WaLogin, Onboarding, PendingApproval, Payment success/failure) **לא** עטופים — נראים בדיוק כמו עכשיו
- בעמודי תוכן (UnitDetail, BuildingDefects) ה‑`max-w-lg` משתנה ל‑`max-w-lg lg:max-w-4xl` כדי שלא יראה צר במרכז של מסך רחב
- Routes המבוססים `React.lazy` + `Suspense` ממשיכים לעבוד בתוך ה‑shell ללא שבירה
- אין רגרסיות ב‑Capacitor build (iOS/Android native)

## Out of scope
- אין Dark Mode — זה ספק 348
- אין Onboarding Tour או Activity Feed — זה ספק 349
- אין PWA או Push Notifications — זה ספק 350
- אין שינויים של routing (paths, lazy loading עצמה)
- אין שינויי תוכן בסיידבר (רק 5 קישורים בסיסיים)
- אין סיידבר קולפס (collapsible) — נשאר 240px קבוע
- אין שינוי של ProjectSwitcher logic (רק רנדור אנכי)
- אין הוספה של search bar ב‑sidebar
- אין theme toggle ב‑sidebar (נוסף ב‑ספק 348)

## Tasks

### Task 1 — Hook: `useMediaQuery`
**File חדש:** `frontend/src/hooks/useMediaQuery.js`

```jsx
import { useState, useEffect } from 'react';

export const useMediaQuery = (query) => {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e) => setMatches(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [query]);

  return matches;
};
```

**הערה:** Hook זה משמש **רק ב‑DesktopShell**. אל תפזר אותו במקומות אחרים בספק הזה — סקופ אחר.

### Task 2 — Component: `Sidebar.jsx`
**File חדש:** `frontend/src/components/layout/Sidebar.jsx`

```jsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Home, Building2, AlertTriangle, FileText, Settings, LogOut } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import ProjectSwitcher from '../ProjectSwitcher';

const NAV_ITEMS = [
  { to: '/projects',          icon: Home,           label: 'הפרויקטים שלי' },
  { to: '/projects/control',  icon: Building2,      label: 'ניהול בניין' },
  { to: '/tasks',             icon: AlertTriangle,  label: 'ליקויים' },
  { to: '/reports',           icon: FileText,       label: 'דוחות' },
  { to: '/account',           icon: Settings,       label: 'הגדרות' },
];

const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside
      className="w-60 flex-shrink-0 bg-slate-900 text-white flex flex-col h-screen sticky top-0"
      dir="rtl"
      role="navigation"
      aria-label="ניווט ראשי"
    >
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-800">
        <h1 className="text-2xl font-bold text-amber-400">BrikOps</h1>
      </div>

      {/* Project Switcher */}
      <div className="px-3 py-3 border-b border-slate-800">
        <ProjectSwitcher variant="vertical" />
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm
              ${isActive
                ? 'bg-amber-500 text-slate-900 font-medium'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'}`
            }
          >
            <Icon className="w-5 h-5 flex-shrink-0" strokeWidth={1.75} />
            <span className="truncate">{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User profile */}
      <div className="px-3 py-3 border-t border-slate-800">
        <button
          onClick={() => navigate('/account')}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-800 transition-colors text-right"
        >
          <div className="w-9 h-9 rounded-full bg-amber-500 flex items-center justify-center text-slate-900 font-bold text-sm flex-shrink-0">
            {user?.name?.[0] || '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.name || 'משתמש'}</p>
            <p className="text-xs text-slate-400 truncate">{user?.email}</p>
          </div>
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-2 mt-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 text-xs transition-colors"
        >
          <LogOut className="w-4 h-4" />
          התנתק
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
```

**הערה לגבי ProjectSwitcher:** הקומפוננטה הקיימת מציגה rendering אופקי בכותרת. הוסף לה prop חדש `variant` (default = 'horizontal', אופציונלי 'vertical') שמשנה רק את ה‑className של הקונטיינר. **אל תיצור** ProjectSwitcher חדש.

ב‑`frontend/src/components/ProjectSwitcher.js` (line ~XX — אזור שורש הקומפוננטה):
```jsx
const ProjectSwitcher = ({ variant = 'horizontal' }) => {
  const containerClass = variant === 'vertical'
    ? 'w-full'  // sidebar context
    : 'flex items-center gap-2'; // header context
  ...
};
```

### Task 3 — Component: `DesktopShell.jsx`
**File חדש:** `frontend/src/components/layout/DesktopShell.jsx`

```jsx
import React from 'react';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import Sidebar from './Sidebar';

const DesktopShell = ({ children }) => {
  const isDesktop = useMediaQuery('(min-width: 1024px)');

  if (!isDesktop) {
    // Mobile: render children as‑is — they have their own headers
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex" dir="rtl">
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-x-hidden">
        {children}
      </main>
    </div>
  );
};

export default DesktopShell;
```

**עיקרון חשוב:** ב‑mobile **לא עוטפים בכלום** — מחזירים את ה‑children ישירות. זה מבטיח אפס שינוי בחוויית המובייל. ב‑desktop בלבד מוסיפים את ה‑Sidebar והוא flex container.

### Task 4 — עטיפת Routes ב‑App.js
**File:** `frontend/src/App.js`

הוסף import:
```jsx
import DesktopShell from './components/layout/DesktopShell';
```

זהה את כל ה‑Routes שדורשים auth (post‑login). ב‑App.js הקיים יש סביב שורה 100+ קבוצה של `<Route>`. עטוף **כל route מוגן** ב‑DesktopShell:

```jsx
// BEFORE
<Route path="/projects" element={<MyProjectsPage />} />

// AFTER
<Route path="/projects" element={<DesktopShell><MyProjectsPage /></DesktopShell>} />
```

**ROUTES שעוטפים (POST‑LOGIN):**
- `/projects` → MyProjectsPage
- `/projects/:projectId` → ProjectControlPage
- `/projects/:projectId/dashboard` → ProjectDashboardPage
- `/projects/:projectId/tasks` → ProjectTasksPage
- `/projects/:projectId/plans` → ProjectPlansPage
- `/projects/:projectId/buildings/:buildingId` → BuildingDefectsPage / InnerBuildingPage
- `/projects/:projectId/buildings/:buildingId/floors/:floorId` → FloorDetailPage
- `/projects/:projectId/units/:unitId` → UnitDetailPage / UnitHomePage / UnitPlansPage
- `/projects/:projectId/stages/:stageId` → StageDetailPage
- `/projects/:projectId/qc/...` → BuildingQCPage / QCFloorSelectionPage / UnitQCSelectionPage
- `/projects/:projectId/handover/...` → HandoverOverviewPage / HandoverTabPage / HandoverProtocolPage / HandoverSectionPage
- `/contractor` → ContractorDashboard
- `/account` → AccountSettingsPage
- `/admin/*` → AdminPage / AdminBillingPage / AdminUsersPage / AdminOrgsPage / AdminDashboardPage / AdminActivityPage / AdminQCTemplatesPage / AdminHandoverTemplateEditor
- `/orgs/billing` → OrgBillingPage
- `/join-requests` → JoinRequestsPage
- `/transfer-ownership/:projectId` → OwnershipTransferPage
- `/apartment/:unitId` → ApartmentDashboardPage
- `/tasks/:taskId` → TaskDetailPage

**ROUTES שלא עוטפים (PUBLIC / SPECIAL):**
- `/login` → LoginPage
- `/register` → RegisterPage
- `/register-management` → RegisterManagementPage
- `/onboarding` → OnboardingPage
- `/pending-approval` → PendingApprovalPage
- `/forgot-password` → ForgotPasswordPage
- `/reset-password` → ResetPasswordPage
- `/wa-login` → WaLoginPage
- `/pending-deletion` → PendingDeletionPage
- `/payment-success` → PaymentSuccessPage
- `/payment-failure` → PaymentFailurePage
- `/accessibility` → AccessibilityPage

```bash
grep -n "<Route\b" frontend/src/App.js | head -50
```

### Task 5 — Responsive `max-w` בעמודי תוכן
**Files:**
- `frontend/src/pages/UnitDetailPage.js` (lines 127, 147, 175 וכל מקום אחר עם `max-w-lg mx-auto`)
- `frontend/src/pages/BuildingDefectsPage.js`
- `frontend/src/pages/MyProjectsPage.js`
- `frontend/src/pages/ProjectControlPage.js`
- `frontend/src/pages/AccountSettingsPage.js`

```bash
grep -rn "max-w-lg mx-auto" frontend/src/pages/ | head -30
```

**Pattern החלפה אחיד:**
```jsx
// BEFORE
<div className="max-w-lg mx-auto px-4 py-3">

// AFTER
<div className="max-w-lg lg:max-w-4xl mx-auto px-4 lg:px-8 py-3">
```

**עיקרון:** עד 1024px נשאר כמו mobile (max‑w‑lg = 512px). מ‑1024px ומעלה — `max‑w‑4xl` (896px) — מתאים גם ל‑sidebar 240px + 4xl content בתוך מסך 1440px.

**יוצאי דופן:**
- מודלים (`max-w-md`, `max-w-xl` וכו') — אל תיגע, הם בקונטקסט שונה (פתוחים מעל הכל)
- ProjectControlPage tabs נשארים ב‑`max-w-lg` כי הם בתוך header sticky — עדכן רק את ה‑content area למטה

**קבצים שצריך לבדוק ידנית:** ProjectControlPage.js הוא הכי גדול (>3700 שורות) — כנראה יש שם 5+ הופעות של max‑w‑lg. עבור על כולן.

### Task 6 — בדיקת Capacitor
**File:** `frontend/capacitor.config.json` (או .ts) + `frontend/ios/`, `frontend/android/`

ב‑Capacitor, האפליקציה תמיד רצה ב‑mobile viewport (≤768px בדרך כלל). זה אומר ש:
- DesktopShell לעולם לא יציג sidebar ב‑native
- `useMediaQuery('(min-width: 1024px)')` תמיד מחזיר false ב‑Capacitor
- אין צורך בשינוי ב‑Capacitor config

**בדיקה ידנית:**
```bash
cd frontend
npm run build
npx cap sync
npx cap run ios   # או npx cap open ios
```

ודא שב‑native build:
1. אין flash של sidebar בעת טעינה
2. כל הניווט נשאר זהה
3. status bar יישור לא נשבר

### Task 7 — Loading State לכשנמצאים בין breakpoints
**File:** `frontend/src/components/layout/DesktopShell.jsx`

ב‑first render לפני שה‑media query נטען, ייתכן ש‑isDesktop = false (default state) למסך desktop, מה שגורם flash של mobile layout ל‑frame אחד. הפתרון:

```jsx
const useMediaQuery = (query) => {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(query).matches; // initial state נכון
  });
  ...
};
```

זה כבר פתור בקוד שלי ב‑Task 1 (lazy initial state עם `() =>`). וודא שה‑JS executes לפני ה‑first paint — ב‑React 18 זה happens automatically עם Suspense.

## Relevant files

### חדשים (3 קבצים)
- `frontend/src/hooks/useMediaQuery.js`
- `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/components/layout/DesktopShell.jsx`

### עריכה ראשית (1 קובץ)
- `frontend/src/App.js` — Task 4 (עטיפת ~30 routes)

### עריכה משנית (1 קובץ)
- `frontend/src/components/ProjectSwitcher.js` — Task 2 (variant prop)

### עריכת max-w (5 קבצים)
- `frontend/src/pages/UnitDetailPage.js`
- `frontend/src/pages/BuildingDefectsPage.js`
- `frontend/src/pages/MyProjectsPage.js`
- `frontend/src/pages/ProjectControlPage.js`
- `frontend/src/pages/AccountSettingsPage.js`

## DO NOT
- ❌ אל תוסיף Dark Mode בספק הזה — זה ספק 348
- ❌ אל תוסיף Onboarding Tour — זה ספק 349
- ❌ אל תוסיף PWA — זה ספק 350
- ❌ אל תיגע ב‑MobileHeader הקיים (ב‑mobile DesktopShell מחזיר children ישירות)
- ❌ אל תעשה sidebar collapsible — נשאר 240px קבוע
- ❌ אל תוסיף search bar ב‑sidebar
- ❌ אל תיצור ProjectSwitcher חדש — תוסיף variant ל‑קיים
- ❌ אל תעשה refactor של i18n / locale switching בסיידבר
- ❌ אל תוסיף animations מסיביים על mount/unmount של sidebar
- ❌ אל תיגע ב‑routing (BrowserRouter, lazy, Suspense) — רק עטיפה
- ❌ אל תיגע ב‑Capacitor config
- ❌ אל תוסיף תלויות חיצוניות חדשות (אין `react-pro-sidebar` או דומה)

## VERIFY

### Mobile (375px)
1. `/projects` — נראה בדיוק כמו לפני. Header למעלה, אין sidebar, אין שינוי.
2. כל route post‑login — אותה התנהגות. אין flash, אין layout shift.
3. Login page — ללא sidebar (לא עטוף).

### Desktop (1440px)
4. `/projects` — sidebar 240px מימין (RTL), content מצד שמאל.
5. סיידבר sticky — בעת scroll נשאר במקום.
6. לחיצה על "ליקויים" בסיידבר → `<NavLink>` מסמן active state ב‑amber‑500.
7. ProjectSwitcher בסיידבר עובד — לחיצה פותחת dropdown עם רשימת פרויקטים.
8. User avatar בתחתית — לחיצה ניווט ל‑/account.
9. כפתור התנתק — מבצע logout ומחזיר ל‑/login (ללא sidebar).

### Tablet (768–1023px)
10. עדיין mobile experience (לא נכנס ל‑sidebar mode עד 1024).
11. במעבר ידני 1023→1024 (drag DevTools) — מעבר חלק עם רענון של state, ללא crash.

### Routing
12. `/login` → `/projects` אחרי login → sidebar מופיע מיד (בdesktop).
13. lazy routes (TaskDetailPage, AdminPage וכו') טוענים ב‑Suspense בתוך ה‑shell, לא שובר.
14. PaywallModal פותח בתוך ProjectControlPage — מוצג מעל ה‑sidebar (z-index גבוה יותר).

### Capacitor (אם רלוונטי)
15. `npm run build && npx cap sync && npx cap run ios` — ב‑native: אין sidebar, אין שינוי.
16. אותו דבר ב‑android.

### Accessibility
17. סיידבר עם `role="navigation"` + `aria-label="ניווט ראשי"` — מזוהה ב‑screen reader.
18. Tab navigation מ‑login → sidebar (Tab עובר על קישורים ב‑סדר הנכון).
19. Focus visible על כל NavLink (יש focus-visible ring מ‑Tailwind defaults).

### Performance
20. בדוק bundle size: `npm run build` — צפי תוספת של ~3kb gzipped בלבד (Sidebar + DesktopShell + hook).

## Risks
- **גבוה: רגרסיה ב‑PaywallModal** — אם BillingProvider לא במקום הנכון ב‑provider tree, PaywallModal לא יעבוד מתוך ה‑shell. בדוק שה‑order ב‑App.js הוא: BrowserRouter > AuthProvider > BillingProvider > Routes > DesktopShell > Page.
- **גבוה: Capacitor StatusBar** — App.js כבר מכיל `import { StatusBar, Style } from '@capacitor/status-bar'`. ה‑sidebar הוא `bg-slate-900` (כהה), אבל ה‑status bar נשאר light style. ב‑native זה יוצר ניגודיות לא טובה. הפתרון לעכשיו: לא להפעיל native ב‑desktop layout (ב‑native ממילא לא רץ). ב‑ספק 348 (Dark Mode) נטפל ב‑status bar update.
- **בינוני: i18n RTL/LTR** — Sidebar מימין נכון לעברית/ערבית. אבל אם יש משתמש סיני (LTR), הסיידבר צריך להיות משמאל. לא נטפל בזה בספק הזה — מסומן בהערה "הוסף בעתיד" אם יש משתמשים סיניים בפרודקשן.
- **בינוני: ProjectSwitcher variant prop** — אם הקומפוננטה הזו משמשת במקומות נוספים (חיפוש: `grep -rn "import.*ProjectSwitcher" frontend/src`) ולא רק בכותרת, יכולה להיווצר קונפליקט.
- **נמוך: Flash of Mobile Layout (FOML)** — בטעינה ראשונה ייתכן frame אחד של mobile לפני זיהוי desktop. הפתרון ב‑lazy initial state כבר ב‑hook.
- **נמוך: Scroll behavior** — ה‑main content הוא overflow‑x‑hidden + min-w-0. זה מונע double scrollbar. לא צפויה בעיה.

## Rollback Plan
אם אחרי merge מתגלה משהו שובר (PaywallModal, routing, native build):
1. revert ה‑PR (single commit)
2. `App.js` חוזר למצב לפני (בלי `<DesktopShell>` wrappers)
3. הקבצים החדשים (`Sidebar.jsx`, `DesktopShell.jsx`, `useMediaQuery.js`) יישארו אבל לא ייעטפו — אין השפעה
4. השינויים ב‑`max-w-lg → max-w-lg lg:max-w-4xl` נשארים — הם neutral ללא sidebar (פשוט תכולה רחבה יותר ב‑desktop, עדיין נראה סביר)

---

**זמן עבודה משוער:** ~40 שעות
**תוצאה צפויה:** ציון UX יעלה מ‑7.6 ל‑8.0 (מובייל≠desktop בעיה נפתרת)
**תלות:** ספקים 345 + 346 חייבים להיות merged קודם
**ספקים עוקבים אחרי הזה:** 348 (Dark Mode), 349 (Onboarding+Activity), 350 (PWA+Push)
**זמן QA אחרי merge:** יום וחצי (יש 30+ routes לבדוק)
