# #UX-001-v2 — תיקוני UX קריטיים + בינוניים (עם נתיבים מדויקים)

## What & Why
ביקורת UX מ-8.4.2026 חשפה בעיות שפוגעות באמינות האפליקציה ובזרימת המשתמש. הממצאים כוללים שטח לבן עצום בדשבורד, חוסר cursor-pointer בליקויים, תצוגת סיסמה הפוכה ב-RTL, ו-touch targets קטנים מדי. ספק זה מבוסס על סריקת קוד מדויקת עם line numbers אמיתיים.

## Done looks like
- דשבורד פרויקט לא מראה שטח לבן מתחת לתוכן
- כרטיסי ליקוי מציגים cursor-pointer ו-chevron
- סיסמה מוצגת LTR בשדה התחברות
- כרטיסי פרויקט מראים hover effect ברור עם active state למובייל
- Badge "לא עודכן" מופיע בכחול (כבר מתוקן) — רק לוודא
- כל כפתורי הדר עוברים 44px minimum
- טאבים במובייל עם scroll indicator

## Out of scope
- שינוי לוגיקת API
- שינוי צבע אמבר ראשי (#F59E0B)
- שינוי סדר טאבים
- שינוי grid מסירות
- שינוי breadcrumbs
- שינוי כפתור sticky "פתח ליקוי"

## Tasks

### 1. דשבורד — הסרת שטח לבן (קריטי)
**קובץ:** `frontend/src/pages/ProjectDashboardPage.js` שורה 242

```jsx
// שורה 242 — המצב הנוכחי:
<div className="min-h-screen bg-slate-50 pb-24" dir="rtl">
```

**שנה ל:**
```jsx
<div className="min-h-0 bg-slate-50 pb-24" dir="rtl">
```

**grep:**
```bash
grep -n "min-h-screen" frontend/src/pages/ProjectDashboardPage.js
```

**VERIFY:** בדסקטופ 1440px, לאחר אזור "פעילות צוות" אין שטח לבן מעבר ל-padding רגיל.

---

### 2. כרטיס ליקוי — הוספת cursor-pointer + chevron (קריטי)
**קובץ:** `frontend/src/pages/UnitDetailPage.js` שורות 268-271

הכרטיס כבר `<button>` עם `onClick` שמנווט ל-`/tasks/{id}`, אבל חסר `cursor-pointer` ו-chevron.

```jsx
// שורה 271 — המצב הנוכחי:
className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right hover:shadow-md transition-shadow active:bg-slate-50"
```

**שנה ל:**
```jsx
className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right cursor-pointer hover:shadow-md transition-shadow active:bg-slate-50"
```

**הוסף** chevron בצד שמאל של הכרטיס (כי RTL — שמאל = Forward):
בתוך ה-`<button>`, אחרי ה-div הראשי, הוסף:
```jsx
<ChevronLeft className="w-4 h-4 text-slate-400 flex-shrink-0 mt-1" />
```

**import:** ודא ש-`ChevronLeft` מיובא מ-`lucide-react` (שורה 9 — כבר יש imports, פשוט הוסף `ChevronLeft` לרשימה).

**grep:**
```bash
grep -n "hover:shadow-md" frontend/src/pages/UnitDetailPage.js
```

**VERIFY:** לחיצה על כרטיס ליקוי מציגה cursor-pointer, chevron בצד שמאל, ומנווטת לפרטי ליקוי.

---

### 3. שדה סיסמה — תיקון כיוון RTL (קריטי)
**קובץ:** `frontend/src/pages/LoginPage.js` שורה 628

```jsx
// שורות 627-632 — המצב הנוכחי:
<input
  id="password" type={showPassword ? 'text' : 'password'} value={password}
  onChange={(e) => { setPassword(e.target.value); ... }}
  placeholder="לפחות 8 תווים"
  className={`w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border rounded-lg...`}
/>
```

**שנה ל:**
```jsx
<input
  id="password" type={showPassword ? 'text' : 'password'} value={password}
  onChange={(e) => { setPassword(e.target.value); ... }}
  placeholder="לפחות 8 תווים"
  dir="ltr"
  className={`w-full h-11 px-3 py-2 pl-10 text-left text-slate-900 bg-white border rounded-lg...`}
/>
```

**שינויים:**
1. הוסף `dir="ltr"` ל-input
2. שנה `text-right` ל-`text-left` ב-className

**grep:**
```bash
grep -n 'id="password"' frontend/src/pages/LoginPage.js
```

**VERIFY:** בלחיצה על אייקון העין, הסיסמה מוצגת `BrikOpsDemo2026!` (סימן קריאה בסוף, לא בהתחלה).

---

### 4. כרטיס פרויקט — active state למובייל (בינוני)
**קובץ:** `frontend/src/pages/MyProjectsPage.js` שורה 335

```jsx
// שורה 335 — המצב הנוכחי:
className="p-4 cursor-pointer hover:shadow-md transition-shadow border border-slate-200 hover:border-amber-300 active:bg-slate-50"
```

**הכרטיס כבר טוב!** יש `cursor-pointer`, `hover:shadow-md`, `hover:border-amber-300`, ו-`active:bg-slate-50`.

**שיפור אופציונלי — הוסף chevron:**
בתוך ה-Card, אחרי ה-div של `flex-1 min-w-0` (שורה 342), הוסף:
```jsx
<ChevronLeft className="w-5 h-5 text-slate-400 flex-shrink-0 self-center" />
```

**import:** הוסף `ChevronLeft` ל-imports (שורה 5 — כבר יש imports מ-lucide-react).

**VERIFY:** ב-hover על כרטיס פרויקט, יש שינוי ויזואלי + chevron שמרמז על ניווט.

---

### 5. Badge "לא עודכן" — צבע (בינוני)
**קבצים:**
- `frontend/src/pages/ApartmentDashboardPage.js` שורה 465

```jsx
// שורה 465 — המצב הנוכחי:
<span className="text-[10px] bg-blue-400 text-white px-2 py-0.5 rounded-full font-bold">לא עודכן</span>
```

**סטטוס:** הצבע כבר `bg-blue-400` (כחול), לא ירוק כפי שדווח בביקורת. ייתכן שתוקן בינתיים. **ודא שלא ירוק בשום מקום אחר.**

**grep:**
```bash
grep -rn "לא עודכן" frontend/src/ | grep -v node_modules
```

**VERIFY:** Badge "לא עודכן" מופיע בכחול או אפור בכל מקום, לא בירוק.

---

### 6. הדר דשבורד — Touch targets (בינוני)
**קובץ:** `frontend/src/pages/ProjectDashboardPage.js` שורה 245

```jsx
// שורה 245 — המצב הנוכחי:
className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors"
```

`p-1.5` = 6px padding + 20px icon = 32px total. מתחת ל-44px minimum.

**שנה ל:**
```jsx
className="p-2.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors"
```

`p-2.5` = 10px padding + 20px icon = 40px. עם border 1px = 42px. כמעט 44px.

**חלופה טובה יותר:** שנה ל-`p-3` (12px + 20px + 2px border = 46px ✅).

**בדוק גם** את כפתור "היכנס" בבאנר: `frontend/src/pages/MyProjectsPage.js` שורה 280-283. הכפתור משתמש ב-Button component עם `px-5` — צריך לוודא שגובהו לפחות 44px. אם Button default הוא `h-9` (36px), שנה ל-`h-11`.

**grep:**
```bash
grep -n "p-1.5" frontend/src/pages/ProjectDashboardPage.js
```

**VERIFY:** כל כפתורי הדר לפחות 44×44px.

---

### 7. טאבים במובייל — scroll indicator (בינוני)
**קובץ:** `frontend/src/pages/ProjectControlPage.js` שורות 3366-3376 (אזור רינדור הטאבים)

**הוסף** gradient fade מצד שמאל (RTL — שמאל = כיוון הגלילה):

אחרי ה-div של הטאבים, הוסף pseudo-element:
```jsx
<div className="relative">
  <div className="overflow-x-auto scrollbar-hide flex gap-1 ...">
    {/* tabs */}
  </div>
  <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-white to-transparent pointer-events-none md:hidden" />
</div>
```

**grep:**
```bash
grep -n "overflow-x-auto" frontend/src/pages/ProjectControlPage.js | head -5
```

**VERIFY:** במובייל 375px, ברור שיש עוד טאבים מעבר למה שנראה.

---

## Relevant files
| קובץ | שורות | שינוי |
|-------|--------|-------|
| `frontend/src/pages/ProjectDashboardPage.js` | 242, 245 | min-h-screen, p-1.5 |
| `frontend/src/pages/UnitDetailPage.js` | 268-271 | cursor-pointer, chevron |
| `frontend/src/pages/LoginPage.js` | 628 | dir="ltr" |
| `frontend/src/pages/MyProjectsPage.js` | 335, 280 | chevron, button height |
| `frontend/src/pages/ApartmentDashboardPage.js` | 465 | badge color verify |
| `frontend/src/pages/ProjectControlPage.js` | 3366-3376 | scroll indicator |

## DO NOT
- ❌ אל תשנה את צבע האמבר הראשי (#F59E0B)
- ❌ אל תשנה את סדר הטאבים (דשבורד, מבנה, בקרת ביצוע, ליקויים, מסירות)
- ❌ אל תיגע בלוגיקת ה-Grid של המסירות
- ❌ אל תשנה את ה-breadcrumbs
- ❌ אל תסיר את הכפתור sticky "פתח ליקוי"
- ❌ אל תשנה את לוגיקת ה-API או ה-backend
- ❌ אל תוסיף ספריות חדשות — רק Lucide icons שכבר מותקן
- ❌ אל תשנה את הפונט (Rubik)

## VERIFY
בסיום, בדוק ברזולוציות:
1. מובייל: 375×812 (iPhone SE/13 mini)
2. טאבלט: 768×1024 (iPad)
3. דסקטופ: 1440×900
4. ודא שאין רגרסיה ב-RTL
5. ודא שכל כפתורי פעולה ≥ 44×44px
