# #UX-002-v2 — מעבר ליטוש: אייקונים, עקביות, Placeholders, ו-Tooltip (עם נתיבים מדויקים)

## What & Why
ביקורת UX מ-8.4.2026 מצאה ממצאים קטנים שביחד משפיעים על תחושת המקצועיות: שימוש באימוג'ים במקום Lucide icons, placeholder חיפוש גנרי, info button קטן מדי ב-TeamActivity, ו-badge Emergent (כבר מוסתר ב-CSS). ספק זה מבוסס על סריקת קוד מדויקת.

## Done looks like
- כל כפתורי Admin בעמוד פרויקט משתמשים ב-Lucide icons במקום אימוג'ים
- כל שדות חיפוש מציגים placeholder ספציפי
- כפתור info ב-TeamActivity עובר 44px touch target
- Badge Emergent מוסתר (כבר מתוקן — רק לוודא)
- Empty state עובד בעמוד פרויקטים (כבר קיים — רק לוודא)

## Out of scope
- שינוי פונט ראשי (Rubik)
- שינוי מבנה טאבים
- הוספת אנימציות חדשות
- שינוי לוגו או צבע ראשי
- שינוי backend/API

## Tasks

### 1. החלפת אימוג'ים באייקוני Lucide (קטן → השפעה גדולה)
**קובץ:** `frontend/src/pages/ProjectControlPage.js` שורות 73-81

```jsx
// שורות 73-81 — המצב הנוכחי:
const SECONDARY_TABS = [
  { id: 'team', label: 'צוות', icon: '👥' },
  { id: 'companies', label: 'קבלנים וחברות', icon: '🏢' },
  { id: 'settings', label: 'מאשרי בקרת ביצוע', icon: '📋' },
  { id: 'qc-template', label: 'תבנית בקרת ביצוע', icon: '📝' },
  { id: 'handover-template', label: 'תבנית מסירה', icon: '🔑' },
];
const BILLING_TAB = { id: 'billing', label: 'מנוי ותשלום', icon: '💳' };
```

**שנה ל:**
```jsx
import { Users, Building2, ClipboardCheck, FileEdit, KeyRound, CreditCard } from 'lucide-react';

const SECONDARY_TABS = [
  { id: 'team', label: 'צוות', icon: Users },
  { id: 'companies', label: 'קבלנים וחברות', icon: Building2 },
  { id: 'settings', label: 'מאשרי בקרת ביצוע', icon: ClipboardCheck },
  { id: 'qc-template', label: 'תבנית בקרת ביצוע', icon: FileEdit },
  { id: 'handover-template', label: 'תבנית מסירה', icon: KeyRound },
];
const BILLING_TAB = { id: 'billing', label: 'מנוי ותשלום', icon: CreditCard };
```

**חשוב:** צריך גם לעדכן את הרינדור של ה-icon. חפש את המקום שבו `tab.icon` מוצג (כנראה בתוך JSX כ-`{tab.icon}` כ-string). שנה ל:
```jsx
{typeof tab.icon === 'string' ? tab.icon : <tab.icon className="w-4 h-4" />}
```

**או**, אם רוצים backwards-compatible, שנה את ה-icon ב-SECONDARY_TABS ל-JSX ישירות:
```jsx
{ id: 'team', label: 'צוות', icon: <Users className="w-4 h-4" /> },
```

**grep:**
```bash
grep -n "icon:" frontend/src/pages/ProjectControlPage.js | head -10
grep -n "tab.icon\|\.icon" frontend/src/pages/ProjectControlPage.js | grep -v "\/\/" | head -20
```

**VERIFY:** כל הכפתורים בשורת Admin מציגים Lucide icons. בדוק ב-Chrome (macOS) ו-Safari (iOS) שנראים זהים.

---

### 2. Placeholder חיפוש ספציפי
**קבצים וערכים:**

| קובץ | שורה | נוכחי | חדש |
|-------|-------|-------|-----|
| `frontend/src/i18n/he.json` | 167 | `"חיפוש פרויקט..."` | `"חפש לפי שם, קוד או כתובת..."` |
| `frontend/src/pages/BuildingDefectsPage.js` | 341 | `"חיפוש דירה..."` | `"חפש לפי מספר דירה..."` |
| `frontend/src/pages/ApartmentDashboardPage.js` | 613 | `"חיפוש ליקוי..."` | `"חפש לפי תיאור, קטגוריה או קבלן..."` |
| `frontend/src/pages/ProjectTasksPage.js` | 371 | `"חיפוש ליקויים..."` | `"חפש לפי תיאור, קטגוריה או קבלן..."` |

**הערה:** MyProjectsPage שורה 295 משתמש ב-`t('myProjects', 'searchPlaceholder')` שמגיע מ-he.json שורה 167. שנה שם.

**grep:**
```bash
grep -rn "חיפוש" frontend/src/pages/ | grep placeholder | grep -v node_modules
grep -rn "searchPlaceholder" frontend/src/i18n/he.json
```

**VERIFY:** כל שדות החיפוש מציגים placeholder ספציפי שעוזר למשתמש.

---

### 3. TeamActivity — הגדלת info button touch target
**קובץ:** `frontend/src/components/TeamActivitySection.js` שורות 69-76

```jsx
// שורות 69-76 — המצב הנוכחי:
<button
  type="button"
  onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
  className="p-0.5 rounded-full hover:bg-slate-200/60 transition-colors"
  aria-label="הסבר ציון"
>
  <Info className="w-3.5 h-3.5 text-slate-400" />
</button>
```

`p-0.5` (2px) + icon 14px = 18px total. מתחת ל-44px.

**שנה ל:**
```jsx
<button
  type="button"
  onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
  className="p-2 rounded-full hover:bg-slate-200/60 transition-colors"
  aria-label="הסבר ציון"
>
  <Info className="w-4 h-4 text-slate-400" />
</button>
```

`p-2` (8px × 2) + icon 16px = 32px. עדיין מתחת ל-44px, אבל הכפתור הזה בתוך טקסט ולא צריך להיות ענק. אם צריך 44px, שנה ל-`p-3.5` + `w-4 h-4` = 44px.

**הוסף גם tooltip** עם הסבר ציון:
הציון כבר מוצג ב-popover (שורות 77-91). זה מספיק — רק צריך להגדיל את ה-touch target.

**grep:**
```bash
grep -n "p-0.5" frontend/src/components/TeamActivitySection.js
```

**VERIFY:** כפתור info עובר 44px minimum; hover מציג tooltip מידעי.

---

### 4. הסבר צבע ציון פעילות (שיפור)
**קובץ:** `frontend/src/components/TeamActivitySection.js` שורות 104-105

```jsx
// שורות 104-105 — כבר קיים:
const color = s >= 60 ? '#22c55e' : s >= 30 ? '#f59e0b' : '#ef4444';
```

**סטטוס:** הצבע כבר דינמי — אדום 0-29, צהוב 30-59, ירוק 60+. ✅ כבר מיושם.

**VERIFY:** ציון 15 מוצג באדום, ציון 45 מוצג בצהוב, ציון 75 מוצג בירוק.

---

### 5. Badge Emergent — אימות הסתרה
**קובץ:** `frontend/src/index.css` שורות 19-27

```css
// כבר קיים:
iframe[src*="emergent"],
div[class*="emergent"],
a[href*="emergent"],
#emergent-badge,
.emergent-badge {
  display: none !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
```

**סטטוס:** כבר מוסתר ב-CSS. ✅ רק לוודא שזה עובד ב-production.

**VERIFY:** אין שום branding של Emergent גלוי באף עמוד.

---

### 6. Empty State — עמוד פרויקטים — אימות
**קובץ:** `frontend/src/pages/MyProjectsPage.js` שורות 312-326

```jsx
// כבר קיים:
{filteredProjects.length === 0 ? (
  <div className="flex flex-col items-center justify-center py-16 text-center">
    <FolderOpen className="w-16 h-16 text-slate-300 mb-4" />
    <h2 className="text-lg font-semibold text-slate-600">{t('myProjects', 'emptyState')}</h2>
    <p className="text-sm text-slate-400 mt-2 max-w-xs">{t('myProjects', 'emptyStateHint')}</p>
    {canCreate && (
      <Button onClick={() => setShowCreateDialog(true)}
        className="mt-6 bg-amber-500 hover:bg-amber-600 text-white h-12 px-8 text-base font-medium gap-2">
        <Plus className="w-5 h-5" />
        צור פרויקט חדש
      </Button>
    )}
  </div>
)}
```

**סטטוס:** כבר מיושם! ✅ אייקון FolderOpen (64px, slate-300), כותרת, תיאור, וכפתור CTA אמבר.

**שיפור קטן אפשרי:** הטקסט "אין לך פרויקטים עדיין" ו-"פנה למנהל המערכת כדי לקבל גישה לפרויקט" מגיע מ-i18n. בדוק אם זה מתאים גם למנהל שיוצר פרויקט ראשון (ולא רק לעובד).

**VERIFY:** צור משתמש חדש ללא פרויקטים — ודא שה-empty state מופיע.

---

### 7. UX Copy — שיפורים נוספים שנמצאו בסריקה

**7a. Badge תגיות — כבר עקביות**
`frontend/src/pages/UnitDetailPage.js` שורות 14-28: STATUS_LABELS ו-PRIORITY_CONFIG כבר מוגדרים עם צבעים סמנטיים נכונים (אדום ל-open, כתום ל-assigned, כחול ל-in_progress, סגול ל-waiting_verify, ירוק ל-closed, אמבר ל-reopened). ✅

שורה 280: `text-[10px] px-2 py-0.5 rounded-full` — אחיד. ✅

**7b. Badge.jsx — אין צורך בשינוי**
`frontend/src/components/ui/badge.jsx` הוא shadcn generic. כל ה-badges הספציפיים של BrikOps מוגדרים inline בקומפוננטות עם Tailwind classes ישירות. אין צורך לשנות את Badge.jsx.

**7c. Search Placeholders i18n — גם en, ar, zh**
אם יש תמיכה בשפות נוספות, עדכן גם:
- `frontend/src/i18n/en.json` שורה 149: `"Search by name, code or address..."`
- `frontend/src/i18n/ar.json` שורה 150: `"البحث حسب الاسم، الرمز أو العنوان..."`
- `frontend/src/i18n/zh.json` שורה 150: `"按名称、代码或地址搜索..."`

---

## Relevant files
| קובץ | שורות | שינוי |
|-------|--------|-------|
| `frontend/src/pages/ProjectControlPage.js` | 73-81 | emoji → Lucide icons |
| `frontend/src/i18n/he.json` | 167 | search placeholder |
| `frontend/src/pages/BuildingDefectsPage.js` | 341 | search placeholder |
| `frontend/src/pages/ApartmentDashboardPage.js` | 613 | search placeholder |
| `frontend/src/pages/ProjectTasksPage.js` | 371 | search placeholder |
| `frontend/src/components/TeamActivitySection.js` | 69-76 | info button touch target |
| `frontend/src/index.css` | 19-27 | Emergent badge (verify only) |
| `frontend/src/pages/MyProjectsPage.js` | 312-326 | Empty state (verify only) |

## DO NOT
- ❌ אל תשנה את הפונט הראשי (Rubik)
- ❌ אל תשנה את מבנה הטאבים
- ❌ אל תוסיף אנימציות חדשות — רק תתקן עקביות
- ❌ אל תשנה את הלוגו או הצבע הראשי
- ❌ אל תשנה את Badge.jsx — ה-badges הספציפיים מוגדרים inline
- ❌ אל תסיר את ה-CSS שמסתיר Emergent badge — הוא עובד
- ❌ אל תוסיף ספריות חדשות

## VERIFY
1. כל האימוג'ים בשורת Admin הוחלפו ב-Lucide icons
2. כל שדות חיפוש מציגים placeholder ספציפי
3. כפתור info ב-TeamActivity ≥ 32px (או 44px אם דרוש)
4. Badge Emergent לא מופיע (כבר מוסתר)
5. Empty state עובד (כבר מיושם)
6. בדוק ב-375px ו-1440px — אין רגרסיות
