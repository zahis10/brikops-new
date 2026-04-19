# #348 — Dark Mode (Complete Coverage, no patches)

> **שינוי הסקופ (16/04/2026):** הספק המקורי #347 פוצל ל‑4 ספקים. ספק זה הוא **שלב 2: Dark Mode**. נכתב מחדש עם חוויה מלאה (לא patchy) — אם לא מוכנים להשקיע 50 שעות מלאות, **עדיף לא לבצע בכלל**.

## What & Why
Dark Mode הוא feature שאם עושים אותו חצי — נראה גרוע יותר מאם לא עושים בכלל. משתמש שלוחץ על Moon icon ואז רואה מודל לבן בוהק, dropdown לבן, toaster לבן — מאבד אמון במוצר. לכן הספק הזה מחייב **כיסוי מלא** של כל קומפוננטות ה‑shadcn (22 קבצים), כל ה‑modals (12 קבצים), כל ה‑page templates (14 דפים מרכזיים), ו‑integration עם Capacitor StatusBar ב‑iOS native. צפי **50 שעות**. אין שינויי backend.

## Done looks like
- Toggle Sun/Moon ב‑sidebar (ספק 347) הופך את כל המסך לכהה תוך 200ms
- בחירה נשמרת ב‑localStorage; default לפי `prefers-color-scheme` של המכשיר
- **כל** קומפוננטות shadcn UI תומכות (button, card, dialog, input, select, tabs, toast, sheet, popover, dropdown, alert, badge, ועוד)
- **כל** המודלים (12 קבצים ב‑components/) — overlay, content, footer
- **כל** ה‑page templates (14 דפים מרכזיים)
- Toaster (sonner) משנה theme בהתאם
- ב‑Capacitor iOS — StatusBar style מתעדכן ל‑Dark כשבוחרים Dark Mode (ולחזור ל‑Light)
- ניגודיות בכל הטקסט ≥4.5:1 (WCAG AA) ב‑Dark Mode
- אין רגרסיה ב‑Light Mode (זה אמור להישאר זהה לחלוטין)

## Out of scope
- אין Theme Editor למשתמש (רק 2 מצבים)
- אין Themes נוספים (Solarized, Dracula וכו')
- אין theme לפי שעה אוטומטית
- אין dark mode למסכי auth (Login, Register) — נשארים light
- אין שינוי של accent color ב‑dark mode (amber‑500 נשאר)
- אין שינוי של logo
- אין dark mode בעמודי Print / PDF export
- אין dark mode במיילים יוצאים מהמערכת

## Tasks

### Task 1 — `darkMode: 'class'` ב‑Tailwind
**File:** `frontend/tailwind.config.js`

הוסף בראש האובייקט:
```js
module.exports = {
  darkMode: 'class',
  content: [...],
  ...
};
```

זה כל ה‑setup הנדרש מצד Tailwind.

### Task 2 — `ThemeContext`
**File חדש:** `frontend/src/contexts/ThemeContext.js`

```jsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import { Capacitor } from '@capacitor/core';

const ThemeContext = createContext({ theme: 'light', toggleTheme: () => {}, setTheme: () => {} });

export const ThemeProvider = ({ children }) => {
  const [theme, setThemeState] = useState(() => {
    try {
      const saved = localStorage.getItem('brikops-theme');
      if (saved === 'dark' || saved === 'light') return saved;
      if (typeof window !== 'undefined' && window.matchMedia) {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
    } catch (e) {}
    return 'light';
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try { localStorage.setItem('brikops-theme', theme); } catch (e) {}

    // Capacitor StatusBar update
    if (Capacitor.isNativePlatform?.()) {
      import('@capacitor/status-bar').then(({ StatusBar, Style }) => {
        StatusBar.setStyle({ style: theme === 'dark' ? Style.Dark : Style.Light });
        StatusBar.setBackgroundColor?.({ color: theme === 'dark' ? '#0f172a' : '#f59e0b' });
      }).catch(() => {});
    }
  }, [theme]);

  const toggleTheme = () => setThemeState(prev => (prev === 'dark' ? 'light' : 'dark'));
  const setTheme = (t) => setThemeState(t === 'dark' ? 'dark' : 'light');

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
```

**File:** `frontend/src/App.js` — עטוף את כל ה‑app מעל ה‑Routes:
```jsx
import { ThemeProvider } from './contexts/ThemeContext';

// בתוך הקומפוננטה הראשית:
<ThemeProvider>
  <BrowserRouter>
    <AuthProvider>
      <BillingProvider>
        ...
      </BillingProvider>
    </AuthProvider>
  </BrowserRouter>
</ThemeProvider>
```

### Task 3 — Toggle Button ב‑Sidebar (Update from #347)
**File:** `frontend/src/components/layout/Sidebar.jsx` (נוצר ב‑#347)

הוסף בתחתית ה‑sidebar (מעל user profile):
```jsx
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

// בתוך Sidebar component:
const { theme, toggleTheme } = useTheme();

// JSX לפני user profile button:
<div className="px-3 pt-3 border-t border-slate-800">
  <button
    onClick={toggleTheme}
    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-800 transition-colors text-sm text-slate-300 hover:text-white"
    aria-label={theme === 'dark' ? 'מעבר למצב בהיר' : 'מעבר למצב כהה'}
  >
    {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
    <span>{theme === 'dark' ? 'מצב בהיר' : 'מצב כהה'}</span>
  </button>
</div>
```

### Task 4 — Color Mapping Convention (חובה לעקוב אחריו!)
תעד את ה‑mapping הזה בראש כל קובץ שמתעדכן ל‑dark, או צור `frontend/src/styles/dark-mode-tokens.md`:

| Light | Dark |
|---|---|
| `bg-white` | `dark:bg-slate-900` |
| `bg-slate-50` | `dark:bg-slate-950` |
| `bg-slate-100` | `dark:bg-slate-800` |
| `bg-slate-200` | `dark:bg-slate-800` |
| `text-slate-900` | `dark:text-slate-50` |
| `text-slate-800` | `dark:text-slate-100` |
| `text-slate-700` | `dark:text-slate-200` |
| `text-slate-600` | `dark:text-slate-300` |
| `text-slate-500` | `dark:text-slate-400` |
| `text-slate-400` | `dark:text-slate-500` |
| `border-slate-200` | `dark:border-slate-800` |
| `border-slate-300` | `dark:border-slate-700` |
| `bg-amber-500` | `dark:bg-amber-500` (נשאר — accent) |
| `text-amber-600` | `dark:text-amber-400` |
| `bg-amber-50` | `dark:bg-amber-950` |
| `bg-emerald-50` | `dark:bg-emerald-950` |
| `text-emerald-600` | `dark:text-emerald-400` |
| `bg-red-50` | `dark:bg-red-950` |
| `text-red-600` | `dark:text-red-400` |
| `bg-blue-50` | `dark:bg-blue-950` |
| `text-blue-600` | `dark:text-blue-400` |
| `from-slate-900 to-slate-800` (כותרות) | (נשאר זהה) |
| `from-amber-500 to-amber-600` (CTA) | (נשאר זהה) |

**עיקרון:** אין צבעי gradient של אקסנט משתנים. אקסנט (amber, emerald, red) נשאר זהה כדי לשמור על עקביות מותג.

### Task 5 — shadcn UI Components (22 קבצים)
**Files (כולם ב‑`frontend/src/components/ui/`):**

```bash
ls frontend/src/components/ui/
```

צפי תוכן: alert.jsx, badge.jsx, button.jsx, card.jsx, checkbox.jsx, dialog.jsx, dropdown-menu.jsx, input.jsx, label.jsx, popover.jsx, progress.jsx, radio-group.jsx, scroll-area.jsx, select.jsx, separator.jsx, sheet.jsx, skeleton.jsx, slider.jsx, sonner.jsx, switch.jsx, tabs.jsx, textarea.jsx, toast.jsx, tooltip.jsx (~24 קבצים).

**עבור כל אחד:**
1. פתח את הקובץ
2. חפש כל מחרוזת bg/text/border שצויינה ב‑Color Mapping (Task 4)
3. הוסף את ה‑variant `dark:`
4. אם הקובץ הוא wrapper סביב Radix — הוסף `dark:` ב‑className של ה‑outer element

**דוגמה ל‑`dialog.jsx`** (DialogContent):
```jsx
// BEFORE
className={cn(
  "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200",
  className
)}

// AFTER (אם משתמשים ב‑bg-background זה כבר מטופל ע"י CSS variables)
// ודא שב‑globals.css יש משתני dark mode מוגדרים
```

**File:** `frontend/src/index.css` (או globals.css) — וודא שיש:
```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --primary: 38 92% 50%;          /* amber-500 */
    --primary-foreground: 222 47% 11%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 38 92% 50%;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 217.2 32.6% 12%;
    --card-foreground: 210 40% 98%;
    --primary: 38 92% 50%;          /* amber-500 — same */
    --primary-foreground: 222 47% 11%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 50%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 38 92% 50%;
  }
}
```

אם המשתנים האלה כבר קיימים — ודא שהם תואמים ל‑mapping של Task 4. אם הם לא קיימים — הוסף אותם.

### Task 6 — Modals (12 קבצים)
**Files (`frontend/src/components/`):**
- `NewDefectModal.js` — overlay + form + footer
- `PaywallModal.js` — תמונה + tiers + CTAs
- `UpgradeWizard.js` — 3+ צעדים, כל אחד עם forms
- `CompleteAccountModal.js` — form
- `FilterDrawer.js` — sheet from side
- `UserDrawer.js` — sheet
- `ExportModal.js`
- `PhoneChangeModal.js`
- `WhatsAppRejectionModal.js`
- `UnitTypeEditModal.js`
- `ProjectBillingEditModal.js`
- `PlanSelector.js`
- `CompleteAccountBanner.js` (לא modal אבל overlay-like)
- `TrialBanner.js`

**עבור כל קובץ:**
1. אם משתמש ב‑shadcn `<Dialog>` — מטופל אוטומטית מ‑CSS variables ב‑Task 5
2. אם משתמש ב‑custom div עם `bg-white` — הוסף `dark:bg-slate-900`
3. בדוק overlay opacity — אם `bg-black/50` (50%) ב‑light, ב‑dark אפשר להגדיל ל‑`dark:bg-black/70` ליותר ניגודיות
4. כפתורי close (X) — `text-slate-500 dark:text-slate-400`
5. divider lines — `border-slate-200 dark:border-slate-800`

**דוגמה — NewDefectModal.js:**
```jsx
// container BEFORE
<div className="bg-white rounded-2xl ...">

// AFTER
<div className="bg-white dark:bg-slate-900 rounded-2xl ...">

// header BEFORE
<h2 className="text-lg font-bold text-slate-900">

// AFTER
<h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">
```

**אסור** לעשות חיפוש‑והחלפה אוטומטי. כל מודל צריך attention ידנית — חלק מה‑bg‑white דורש shade שונה (למשל אם זה כרטיס בתוך מודל אפור, ה‑inner card אולי `bg-slate-50 dark:bg-slate-800`).

### Task 7 — Page Templates (14 דפים)
**Files:**
1. `frontend/src/pages/MyProjectsPage.js`
2. `frontend/src/pages/ProjectControlPage.js` (3700+ lines — הכי כבד)
3. `frontend/src/pages/UnitDetailPage.js`
4. `frontend/src/pages/BuildingDefectsPage.js`
5. `frontend/src/pages/AccountSettingsPage.js`
6. `frontend/src/pages/ProjectTasksPage.js`
7. `frontend/src/pages/ProjectDashboardPage.js`
8. `frontend/src/pages/ContractorDashboard.js`
9. `frontend/src/pages/FloorDetailPage.js`
10. `frontend/src/pages/StageDetailPage.js`
11. `frontend/src/pages/InnerBuildingPage.js`
12. `frontend/src/pages/ApartmentDashboardPage.js`
13. `frontend/src/pages/HandoverOverviewPage.js`
14. `frontend/src/pages/AdminPage.js`

**עבור כל קובץ — שיטה:**
1. הרץ:
   ```bash
   grep -nE "bg-white|bg-slate-(50|100|200)|text-slate-(500|600|700|800|900)|border-slate-(200|300)" frontend/src/pages/<FILE>.js | wc -l
   ```
   זה מראה כמה הופעות צריך לטפל בקובץ.
2. עבור על כל הופעה והוסף `dark:` בהתאם ל‑Task 4 mapping.
3. בדוק שאין shorthand classes (`bg-card`, `text-foreground` וכו') — אם יש, הם כבר מטופלים מ‑CSS variables.
4. בדוק gradients (`from-slate-900 to-slate-800`) — אלה כותרות bbg‑slate‑900 שכבר עובדות נכון ב‑dark (נשארות כהות).
5. בדוק amber accents — נשארים זהים.

**הדפים הכבדים ביותר** (>1000 lines): ProjectControlPage, ProjectDashboardPage, AdminPage. תכנן ~4–6 שעות לכל אחד מהם.

### Task 8 — Sonner / Toaster Theme Sync
**File:** `frontend/src/components/ui/sonner.jsx`

```jsx
import { useTheme } from "@/contexts/ThemeContext";
import { Toaster as Sonner } from "sonner";

const Toaster = ({ ...props }) => {
  const { theme } = useTheme();
  return (
    <Sonner
      theme={theme}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-white group-[.toaster]:text-slate-900 group-[.toaster]:border-slate-200 group-[.toaster]:shadow-lg dark:group-[.toaster]:bg-slate-900 dark:group-[.toaster]:text-slate-50 dark:group-[.toaster]:border-slate-800",
          description: "group-[.toast]:text-slate-500 dark:group-[.toast]:text-slate-400",
          actionButton:
            "group-[.toast]:bg-amber-500 group-[.toast]:text-slate-900",
          cancelButton:
            "group-[.toast]:bg-slate-100 group-[.toast]:text-slate-500 dark:group-[.toast]:bg-slate-800 dark:group-[.toast]:text-slate-400",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
```

### Task 9 — Capacitor StatusBar Sync
זה כבר נעשה ב‑ThemeContext (Task 2). וודא שהקובץ `frontend/capacitor.config.json` מתיר StatusBar plugin:
```json
{
  "plugins": {
    "StatusBar": {
      "overlaysWebView": false,
      "style": "DEFAULT",
      "backgroundColor": "#F59E0B"
    }
  }
}
```

**בדיקה ב‑native:**
```bash
npm run build
npx cap sync
npx cap run ios
```

לחץ על Toggle Dark — StatusBar בiOS צריך להפוך לכהה (text לבן על רקע כהה).

### Task 10 — דפי Auth — נשארים Light בכוונה
**Files:**
- `LoginPage.js`, `RegisterPage.js`, `RegisterManagementPage.js`, `ForgotPasswordPage.js`, `ResetPasswordPage.js`, `WaLoginPage.js`, `OnboardingPage.js`, `PendingApprovalPage.js`, `PaymentSuccessPage.js`, `PaymentFailurePage.js`, `PendingDeletionPage.js`

**אסור** לגעת בהם — הם נשארים Light Mode קבוע. הסיבה: לפני login אין עדיין ThemeContext + אין משתמש שבחר preference. השארה light = consistency חזותית עם marketing site.

הוסף בכל אחד מהקבצים האלה (top‑level container) class `light:bg-* dark:bg-*` שלא משתנה לפי theme:
```jsx
// MyProjectsPage לדוגמה — לא נוגעים
// LoginPage — לא נוגעים בעקרון, אבל אם רוצים להבטיח שלא יושפע מ-class dark על html:
<div className="bg-slate-50 text-slate-900"> {/* ללא dark: */}
```

זה מבטיח שאם המשתמש logout כשהיה ב‑Dark, ה‑Login לא יהפוך לכהה.

### Task 11 — בדיקות ניגודיות (WCAG AA)
**Tool:** Chrome DevTools → Lighthouse → Accessibility audit, מצב Dark.

לכל אחד מ‑14 הדפים (Task 7):
1. הפעל Dark Mode
2. הרץ Lighthouse Accessibility
3. **דרישה:** Score ≥95 + 0 contrast issues
4. אם נכשל — תקן את הצבעים בעייתיים. בדרך כלל זה: 
   - `text-slate-400 on bg-slate-800` — ניגודיות 4.05 (נכשל, צריך 4.5)
   - תקן ל‑`text-slate-300` (5.74)
   - או רקע יותר כהה: `bg-slate-900` עם `text-slate-400` → 5.41 ✅

## Relevant files

### חדשים
- `frontend/src/contexts/ThemeContext.js`
- `frontend/src/styles/dark-mode-tokens.md` (תיעוד פנימי, אופציונלי)

### עריכה ראשית
- `frontend/tailwind.config.js` — Task 1
- `frontend/src/App.js` — Task 2 (provider wrap)
- `frontend/src/index.css` — Task 5 (CSS variables)
- `frontend/src/components/layout/Sidebar.jsx` — Task 3 (toggle button — דורש שספק 347 merged)
- `frontend/src/components/ui/sonner.jsx` — Task 8

### עריכה רוחבית (~22 קבצי UI components, ~12 modals, ~14 pages)
- כל קבצי `frontend/src/components/ui/*.jsx`
- כל קבצי modals ב‑`frontend/src/components/`
- 14 דפים מרכזיים ב‑`frontend/src/pages/`

### עריכה משנית
- `frontend/capacitor.config.json` — Task 9

## DO NOT
- ❌ אל תיגע בדפי Auth (LoginPage וכו') — הם נשארים Light בכוונה
- ❌ אל תוסיף Theme Editor למשתמש (רק toggle Light/Dark)
- ❌ אל תוסיף Themes נוספים (Solarized, Dracula)
- ❌ אל תעשה global search‑and‑replace של `bg-white` → `bg-white dark:bg-slate-900` — חלק בכוונה לבן (לדוגמה: כרטיסי plan עם accent)
- ❌ אל תשנה את הצבעים של accent (amber, emerald, red) — נשארים זהים בשני מצבים
- ❌ אל תיגע ב‑logo (נשאר זהה)
- ❌ אל תוסיף animation על מעבר theme שאורכת מעל 300ms (jarring)
- ❌ אל תיגע ב‑PhotoAnnotation.js (יש שם portal/event quirks)
- ❌ אל תוסיף תלות חדשה (`next-themes`, `theme-ui` וכו') — context idiomatic מספיק
- ❌ אל תעשה את הספק הזה במקביל לספק 347 — אם 347 לא merged, ה‑sidebar עדיין לא קיים, אין מקום ל‑toggle
- ❌ אל תיגע ב‑i18n strings — Dark Mode לא משנה תכנים
- ❌ אל תגזור פינות — אם מקבץ של 5 קומפוננטות UI לא ב‑Dark Mode, הוא יבלוט גרוע

## VERIFY

### Toggle
1. לחץ Sun/Moon ב‑sidebar (desktop) → המסך הופך לכהה תוך 200ms.
2. רענן → נשאר Dark (localStorage).
3. logout → login → עדיין Dark כשנכנסים שוב.

### Coverage
4. עבור על 14 הדפים (Task 7) — בדוק שאף אזור לא נשאר לבן בולט.
5. פתח כל אחד מ‑12 המודלים — overlay כהה, content כהה, footer כהה, כפתורים נראים תקין.
6. כל ה‑shadcn components: Input, Select, Checkbox, Radio, Switch, Tabs, Tooltip, Popover, Dropdown — כולם dark.
7. Sonner toast — מופיע כהה ב‑Dark Mode.

### Contrast (Lighthouse)
8. רץ Lighthouse על כל 14 הדפים, פעם ב‑Light פעם ב‑Dark
9. Accessibility ≥95 בשני מצבים
10. אין "Background and foreground colors do not have a sufficient contrast ratio" warnings

### Responsiveness
11. Mobile (375px) Dark — יפה, כל ה‑headers + content
12. Tablet (768px) Dark
13. Desktop (1440px) Dark עם sidebar

### Capacitor
14. iOS native: toggle Dark → status bar הופך כהה (text לבן)
15. iOS native: toggle Light → status bar חוזר ללבן (text כהה)
16. Android native: אותו דבר

### Edge Cases
17. PaywallModal פתוח → toggle Dark → המודל מתעדכן בלייב
18. UpgradeWizard באמצע צעד 2 → toggle Dark → לא מאבד state
19. Toaster פעיל (toast מוצג) → toggle Dark → ה‑toast קיים מתעדכן? (אם לא — לא קריטי)
20. כפתור disabled — נראה ב‑Dark Mode (לא מתערבב עם הרקע)

### Performance
21. bundle size — תוספת מינימלית (~2kb gzipped — רק ThemeContext)
22. אין lag במעבר theme

## Risks
- **גבוה: כיסוי לא שלם** — אם תבטל אפילו modal אחד, הוא ייראה לבן בוהק על רקע כהה. הפתרון: checklist רשמי של כל ~50 הקבצים, סימון V לכל אחד אחרי בדיקה ידנית.
- **גבוה: PhotoAnnotation.js** — הקומפוננטה הזו עם portals מוזרים. עוקפים אותה בספק הזה. תיעוד: התמונות שמצוירות עליהן יישארו תמיד עם רקע לבן (תמונה היא תמונה, לא ניתן לשנות).
- **בינוני: PaywallModal stripe** — אם יש אזור עם external script (Stripe Elements), הוא לא מתעדכן עם theme שלנו. זוהה והוסף `dark:bg-slate-900` רק לקונטיינר החיצוני.
- **בינוני: Capacitor StatusBar** — ב‑Android plugin שונה. בדוק ב‑native לפני merge.
- **בינוני: i18n direction** — `dir="rtl"` לא משתנה עם theme. אם יש user סיני (LTR) ב‑Dark Mode, ה‑dark צבעים נכונים, אבל ה‑direction נשארת מהבחירה של ה‑i18n. זה לא קשור לספק.
- **נמוך: Browsers ישנים** — `prefers-color-scheme` לא נתמך בכל הדפדפנים. fallback ל‑light עובד.

## Rollback Plan
אם אחרי merge יש 5+ אזורים לא מתורגמים נכון:
1. שנה `darkMode: 'class'` ל‑`darkMode: 'media'` זמנית — זה מבטל את ה‑toggle ידני אבל מאפשר auto לפי OS
2. או — הוסף ב‑Sidebar `disabled` attribute ל‑toggle button
3. או — revert ה‑PR. הקומפוננטות החדשות (ThemeContext) נשארות אבל לא משפיעות

---

**זמן עבודה משוער:** ~50 שעות
**תוצאה צפויה:** ציון UX יעלה מ‑8.0 ל‑8.3 (Dark Mode הוא feature שמעלה perception של "מקצועיות")
**תלות:** ספק 347 חייב להיות merged קודם (Sidebar קיים ל‑toggle)
**זמן QA אחרי merge:** 1.5 ימים (חצי יום לכל אחד מ‑3 platforms — web/iOS/android)
