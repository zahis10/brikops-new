# #346B — Button Component Base Size Audit & Resize (h-9 → h-11)

> **עודכן 17/04/2026:** Line numbers אומתו. button.jsx lines 7–8, 23–28 מאומתים. MyProjectsPage header ב‑226–260. bg-blue-500 custom buttons ב‑ProjectControlPage lines 2103, 2374, 3970.

## What & Why
ספק זה הוצא מ‑#346 כי הוא משפיע על **164 הופעות של `<Button>` באפליקציה**. שינוי ה‑base size של `button.jsx` מ‑`h-9` (36px) ל‑`h-11` (44px) הוא הצעד הוויזואלי החשוב ביותר ב‑accessibility — touch targets עומדים בתקן Apple HIG (44pt) ו‑Material (48dp). אבל זה **שינוי רוחב‑אפליקציה** עם פוטנציאל גבוה לרגרסיות ויזואליות (toolbars, modals, button groups, header rows). לכן הוא מבודד לספק נפרד עם audit ויזואלי שיטתי לכל אזור באפליקציה. צפי ~25 שעות. אין שינויי backend. אין logic חדש.

## Done looks like
- `frontend/src/components/ui/button.jsx` עודכן: default → `h-11`, icon → `h-11 w-11`, נוסף וריאנט `icon-sm` לאייקונים קטנים
- כל ה‑base classes מקבלים `transition-all duration-200`
- כל **5 הקבוצות הוויזואליות הקריטיות** עברו audit ידני ומוצגות תקין:
  1. Modals (NewDefectModal, PaywallModal, UpgradeWizard, CompleteAccountModal, FilterDrawer, UserDrawer, ExportModal)
  2. Headers (MyProjectsPage, ProjectControlPage, UnitDetailPage, BuildingDefectsPage)
  3. Form footers (כל מסכי Auth, AccountSettingsPage)
  4. Inline button groups (Filters, sort controls, action rows)
  5. CTA pages (TrialBanner, CompleteAccountBanner, empty states)
- אין כפתור שחורג מהקונטיינר שלו, אין באטון group ששובר שורה לא מתוכננת, אין modal שה‑footer שלו מתפוצץ
- כל `<Button>` שצריך להישאר בגודל ישן (h-9) עבר במפורש ל‑`size="sm"` או `size="icon-sm"` — לא הסתמך על default ישן
- `git diff` של ה‑PR לא נוגע באף קובץ של pages/ — רק `button.jsx` + ~15 קבצי components/modals שדרשו `size` מפורש

## Out of scope
- אין לשנות צבעי כפתורים (primary/secondary/destructive variants נשארים)
- אין להוסיף וריאנטים חדשים פרט ל‑`icon-sm`
- אין לגעת ב‑Radix primitives (Dialog, Sheet, Popover) — רק ה‑Button
- אין לגעת ב‑logic של ה‑button (onClick, disabled, loading)
- אין לעשות migration לכפתורי native (`<button>`) — נשאר shadcn Button
- אין לגעת ב‑inputs, selects, textareas — אם הם בקבוצה עם button, רק button משתנה
- אין להוסיף focus ring חדש או shadow חדש

## Tasks

### Task 1 — מיפוי כל ההופעות של Button
**File:** הרץ + שמור פלט ל‑`spec-346B-button-audit.txt` בתיקיית הספק

```bash
cd /workspace/brikops-new
grep -rn "<Button\b" frontend/src/ | grep -v node_modules > spec-346B-button-audit.txt
grep -rn "buttonVariants\b" frontend/src/ | grep -v node_modules >> spec-346B-button-audit.txt
wc -l spec-346B-button-audit.txt
```

**Expected count:** ~164 הופעות. אם המספר חורג משמעותית (>200 או <100), עצור והודע על שינוי בקודבייס.

קבץ ידנית את ההופעות ל‑5 קטגוריות (העתק לקובץ Notion / Asana):
1. **Modal footers** — שורת כפתורים בתחתית מודל (Cancel + Save)
2. **Header icon buttons** — כפתורי אייקון בכותרת (hamburger, bell, switcher)
3. **Inline form buttons** — כפתור עם input/select בשורה אחת (filter, search submit)
4. **Standalone CTAs** — כפתור יחיד באמצע כרטיס (Upgrade, Continue, Save)
5. **Button groups** — 2+ כפתורים זה לצד זה ללא input ביניהם (toolbar, sort)

### Task 2 — שנה את `button.jsx`
**File:** `frontend/src/components/ui/button.jsx`

**BEFORE (lines 7–8 — base classes):**
```jsx
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
```

**AFTER:**
```jsx
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.98]",
```

**הערה:** `transition-colors` → `transition-all` כדי לכלול שינוי גובה ו‑scale. `active:scale-[0.98]` מוסיף תחושת press טקטילית.

**BEFORE (lines 23–28 — size variants):**
```jsx
size: {
  default: "h-9 px-4 py-2",
  sm: "h-8 rounded-md px-3 text-xs",
  lg: "h-10 rounded-md px-8",
  icon: "h-9 w-9",
},
```

**AFTER:**
```jsx
size: {
  default: "h-11 px-5 py-2.5 text-sm",
  sm: "h-9 rounded-md px-3 text-xs",
  lg: "h-12 rounded-md px-8 text-base",
  icon: "h-11 w-11",
  'icon-sm': "h-9 w-9",
  'icon-xs': "h-8 w-8",
},
```

**הערה:** הוספנו 2 גדלי אייקון קטנים יותר (`icon-sm` = הגודל הישן של `icon`, `icon-xs` עבור compact UI). זה ה‑escape hatch.

### Task 3 — Audit Pass: Modals (קטגוריה 1)
**Files (כולם ב‑`frontend/src/components/`):**
- `NewDefectModal.js`
- `PaywallModal.js`
- `UpgradeWizard.js`
- `CompleteAccountModal.js`
- `FilterDrawer.js`
- `UserDrawer.js`
- `ExportModal.js`
- `PhoneChangeModal.js`
- `WhatsAppRejectionModal.js`
- `UnitTypeEditModal.js`
- `ProjectBillingEditModal.js`
- `PlanSelector.js`

**עבור כל קובץ:**
1. פתח את הקובץ ב‑Replit
2. חפש כל `<Button` בתוך הקובץ
3. הרץ ה‑modal בדפדפן (mobile + desktop) — בדוק שה‑footer לא נשבר
4. אם footer מציג Cancel + Save בשורה — בדוק שיש מספיק רוחב
5. אם הם נשברים לשתי שורות — שקול להוסיף `size="sm"` בכפתור Cancel
6. אם כפתור עם אייקון בלבד — בדוק האם 44×44 שולט יותר מדי. אם כן → `size="icon-sm"`

**נקודה ספציפית:** ב‑`NewDefectModal.js` (שזו השכבה הראשית של הזרימה) — אם יש כפתורי "מצלמה" / "מעלה תמונה" בקבוצה — הם עלולים להיות עכשיו 44px אחד ליד השני. בדוק שזה לא כובש 80% מהמודל.

### Task 4 — Audit Pass: Headers (קטגוריה 2)
**Files:**
- `frontend/src/pages/MyProjectsPage.js` lines 226–260 (Header + ProjectSwitcher + Bell + Hamburger)
- `frontend/src/pages/ProjectControlPage.js` lines 3548–3575 (header)
- `frontend/src/pages/UnitDetailPage.js` lines 125–145 (orange gradient header)
- `frontend/src/pages/BuildingDefectsPage.js` (אותו pattern)
- `frontend/src/components/HamburgerMenu.js`
- `frontend/src/components/NotificationBell.js`
- `frontend/src/components/ProjectSwitcher.js`

**שים לב:** ספק 345 כבר העלה את icon buttons בכותרת ל‑`h-11 w-11` ידנית. אם 345 כבר merged, אז ה‑`<Button size="icon">` בכותרת כבר עלה אוטומטית ל‑44 — וזה דווקא מה שרצינו. ודא שאין כפילות גובה (header עם padding של 16px + button של 44px = 76px header — אולי יותר מדי). אם כן, התאם padding של ה‑header ל‑`py-2` במקום `py-3`.

**נקודה ספציפית:** הכותרת הכתומה ב‑UnitDetailPage כוללת breadcrumbs + title + 2 icon buttons. בדוק ב‑mobile (375px) שלא נשבר.

### Task 5 — Audit Pass: Forms (קטגוריה 3)
**Files:**
- `frontend/src/pages/LoginPage.js`
- `frontend/src/pages/RegisterPage.js`
- `frontend/src/pages/RegisterManagementPage.js`
- `frontend/src/pages/ForgotPasswordPage.js`
- `frontend/src/pages/ResetPasswordPage.js`
- `frontend/src/pages/AccountSettingsPage.js`
- `frontend/src/pages/OnboardingPage.js`

ב‑forms, כפתור submit גדול (h-11) הוא דווקא **שיפור** — נראה יותר מקצועי וקליק יותר נוח. כאן בעיקר וודא:
- כפתור submit במלוא רוחב הטופס נראה טוב (`w-full`)
- "Login" / "Register" כפתורים גדולים עם text-base (לא text-sm) — אופציונלי `size="lg"`

**אסור** לשנות את `size="lg"` המפורש בקבצים — רק להוסיף איפה שאין size בכלל ועדיין רוצים default.

### Task 6 — Audit Pass: Inline Groups (קטגוריה 4 + 5)
**Files (Pages עם action toolbars):**
- `frontend/src/pages/ProjectControlPage.js` (יש שם הרבה toolbar rows)
- `frontend/src/pages/ProjectTasksPage.js`
- `frontend/src/pages/ContractorDashboard.js`
- `frontend/src/pages/AdminPage.js`
- `frontend/src/pages/HandoverProtocolPage.js`

```bash
grep -n "<Button\b" frontend/src/pages/ProjectControlPage.js | head -30
```

עבור על כל toolbar — אם יש 3+ כפתורים זה לצד זה:
- אם total width עם h-11 חורג מהקונטיינר → להחליף ל‑`size="sm"` כקבוצה
- אם אחד מהם הוא Primary CTA → אותו נשאיר default, היתר sm
- אם כולם אייקונים → כולם `icon-sm`

### Task 7 — Audit Pass: Custom Buttons (לא <Button>)
**Search:**
```bash
grep -rn "rounded-md.*bg-amber\|rounded-lg.*bg-blue\|rounded-md.*bg-emerald" frontend/src/pages/ | grep -v node_modules | head -30
```

יש מקומות שבהם משתמשים ב‑`<button>` HTML רגיל עם Tailwind classes (לא shadcn Button). דוגמאות ב‑ProjectControlPage.js lines 2103, 2374, 3970:
```jsx
className="bg-blue-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
```

**אל תמיר אותם ל‑shadcn Button** בספק הזה (זה ספק audit, לא refactor). אבל **כן** עדכן את ה‑padding ל‑44px touch target אם הכפתור פעיל ובסדר‑עדיפויות עליון:
```jsx
// BEFORE: px-3 py-1.5 (גובה ~30px)
// AFTER:  px-4 py-3   (גובה 44px)
```

תקן רק 5–10 הכפתורים הקריטיים ביותר. את היתר תעד ברשימה לספק עתידי "Button Migration to shadcn".

### Task 8 — בדיקת רגרסיה ויזואלית
**שיטה:** screenshots לפני/אחרי על 8 דפים מרכזיים, בשני viewports (375 + 1440).

```bash
# צור תיקייה
mkdir -p screenshots/before screenshots/after
```

**דפים לבדיקה:**
1. `/login`
2. `/projects` (MyProjectsPage)
3. `/projects/:id` (ProjectControlPage) — KPI + tabs + content
4. `/projects/:id/buildings/:bid` (BuildingDefectsPage)
5. `/projects/:id/units/:uid` (UnitDetailPage)
6. `/account` (AccountSettings)
7. NewDefectModal פתוח על UnitDetailPage
8. UpgradeWizard פתוח על ProjectControlPage

לכל דף — צילום בכל viewport. השווה side‑by‑side. סמן באדום כל אזור שנראה שונה לרעה.

## Relevant files

### עריכה ראשית (1 קובץ)
- `frontend/src/components/ui/button.jsx` — Tasks 2 (lines 7–8, 23–28)

### Audit + תיקונים נקודתיים בלבד (לא refactor)
- 12 קבצי modals תחת `frontend/src/components/`
- 4 קבצי headers תחת `frontend/src/pages/` + 3 קבצי components
- 7 קבצי forms תחת `frontend/src/pages/`
- 5 קבצי pages עם toolbars
- ~5–10 הופעות של custom `<button>` עם padding ידני

**צפי קבצים שיתעדכנו:** 15–25 קבצים. עריכה ממוצעת לכל קובץ: 1–3 שורות (`size="sm"` או `size="icon-sm"`).

## DO NOT
- ❌ אל תעשה global search‑and‑replace של `size="icon"` → `size="icon-sm"` — חלק מהמקומות **רוצים** את ה‑44 החדש
- ❌ אל תיגע ב‑variants של color (`destructive`, `outline`, `ghost`, `link`)
- ❌ אל תיגע ב‑`buttonVariants` export — הוא משמש ב‑components אחרים
- ❌ אל תוסיף וריאנטים חדשים פרט ל‑`icon-sm` ו‑`icon-xs`
- ❌ אל תחליף custom `<button>` HTML ל‑shadcn Button (סקופ אחר)
- ❌ אל תיגע ב‑Radix Dialog primitives (DialogClose, DialogTrigger וכו')
- ❌ אל תעשה את העבודה הזו במקביל לספק 346 (יוצר conflicts בקבצים)
- ❌ אל תעשה את הספק הזה ב‑PR אחד עם ספקים אחרים — הוא דורש PR נפרד עם review ויזואלי
- ❌ אל תעשה rebase של ספקים אחרים על ה‑branch הזה לפני merge
- ❌ אל תוסיף `framer-motion` או animation library — `transition-all duration-200` מספיק

## VERIFY

### ויזואלי
1. רענן `/login` — כפתור "התחברות" גדול ונוח ללחיצה במובייל. גובה 44px ב‑DevTools.
2. פתח NewDefectModal מ‑UnitDetailPage — Footer של Cancel + Save **לא נשבר** לשתי שורות.
3. כותרת ProjectControlPage — 3 icon buttons בימין, אין סקרול אופקי, אין נשירת אלמנטים.
4. UpgradeWizard — כפתורי Plans (3 כרטיסים זה לצד זה) — אם יש Button "בחר" בכל כרטיס — שלושתם נראים זהים.
5. FilterDrawer — כפתור "אפס" + "החל" בתחתית — מוצג נכון עם `gap-2`.

### Lighthouse
6. `npm run build && lighthouse --view ./build/index.html` (או דרך Chrome DevTools)
7. **Accessibility score** — חייב להיות ≥95 (היה לפני)
8. **Tap targets too small** — צריך להיעלם מהפלט (זה הפס שתיקנו)

### Diff Verification
9. `git diff HEAD~1 -- frontend/src/components/ui/button.jsx | wc -l` — צריך להיות בין 10–20 שורות שינוי
10. `git diff HEAD~1 -- frontend/src/pages/ | grep "^[+-]" | wc -l` — צריך להיות בין 30–80 שורות שינוי (איפה ש‑size הוסף ידנית)
11. אם החריגה גדולה משמעותית — סימן שמשהו רחב מדי שונה. עצור ובדוק.

### Mobile Native (Capacitor)
12. אם BrikOps נבנה גם דרך Capacitor (`npx cap run ios` / `npx cap run android`) — בדוק את ה‑build ב‑native.
13. ב‑iOS specifically — וודא שכפתורים בכותרת לא נחתכים מתחת ל‑status bar (44px button + 44px status bar = 88px header).

### Cross‑browser
14. Chrome desktop ✅
15. Safari desktop (אם יש זמן)
16. Mobile Safari iOS — viewport 375
17. Chrome mobile Android — viewport 412

## Risks
- **גבוה:** רגרסיות ויזואליות במודלים של 12 קבצים. הפתרון: הצוות עובר על כל מודל ידנית בסעיף Audit (Tasks 3–7). זה לוקח זמן אבל אין דרך קצרה.
- **בינוני:** Toolbars בעמודים גדולים (ProjectControlPage) עלולים לחרוג מהרוחב. הפתרון: הוסף `size="sm"` במקומות הספציפיים.
- **בינוני:** ב‑mobile native (Capacitor) ייתכן ויזואל שונה בגלל system font scaling. בדוק.
- **נמוך:** `transition-all` במקום `transition-colors` יוצר transition גם על properties כמו padding (אם משתנה דינמית). בפועל לא משתנה אצלנו — ביטחון.
- **נמוך:** `active:scale-[0.98]` יכול לגרום ל‑layout shift קטן ב‑1ms בכפתורים שצמודים זה לזה. בפועל לא נראה לעין.

## Rollback Plan
אם אחרי merge מתגלות 5+ רגרסיות ויזואליות שלא נתגלו ב‑audit:
1. revert ה‑PR
2. החזר את `button.jsx` ל‑default `h-9`
3. השאר את ה‑size מפורש שהוסף בקבצים אחרים — הוא לא מזיק (פשוט duplicate of default)
4. תכנן spec עוקב 346B‑v2 שמתחיל עם פיצול ל‑10 sub‑PRs (modal‑by‑modal)

---

**זמן עבודה משוער:** ~25 שעות (ירד מ‑10 שעות בספק 346 המקורי כי כאן ה‑audit הוא הסיבה המרכזית)
**תוצאה צפויה:** ציון UX יעלה ב‑0.2 נוסף (תרומה ספציפית של Touch Target compliance)
**תלות:** לא חייב את 346 (יכול להיעשות במקביל אם בצוות נפרד), אבל מומלץ לחכות ל‑345 שיהיה merged
**זמן QA אחרי merge:** יום עבודה לבדיקת רגרסיות
