# Spec #380-FIX — FilterDrawer Phase 2 תיקונים

**Base commit:** `af3bac9`
**Scope:** תיקון באג קריטי אחד + 2 שיפורים קטנים. Merge אחרי ש-#380 כבר באוויר.

---

## 🔴 CRITICAL — preset דורס filters אחרים בלי שהמשתמש ביקש

### הבעיה

ב-`FilterDrawer.js`, הפונקציה `applyPreset` משכתבת את **כל** ה-draft:

```js
// הקוד הנוכחי — באג
const applyPreset = (preset) => {
  if (activePresetId === preset.id) {
    setDraft({ ...defaultFilters });
  } else {
    setDraft({ ...defaultFilters, ...preset.values });
  }
};
```

**תרחיש שבור (BuildingDefectsPage):**
1. משתמש פותח סינון ובוחר קטגוריה "מטבח" → `category: ['kitchen']`
2. משתמש לוחץ preset "פתוחים"
3. `activePresetId === null` (כי category לא ריק), לכן נכנסים לענף ה-`else`
4. `setDraft({ ...defaultFilters, status: ['open'] })` → **ה-category נמחק בלי אזהרה**

זה כישלון שקט בדאטה של המשתמש. המשתמש בטוח שהוא מוסיף פילטר סטטוס, ובפועל מאבד את הקטגוריה שהוא כבר בחר.

### התיקון

Preset צריך לגעת רק במפתחות שהוא מגדיר (`preset.values`), ולא לאפס שאר השדות.

**`frontend/src/components/FilterDrawer.js`** — החלף את `applyPreset`:

```js
const applyPreset = (preset) => {
  if (activePresetId === preset.id) {
    // deselect — אפס רק את המפתחות של ה-preset
    setDraft(prev => {
      const next = { ...prev };
      Object.keys(preset.values).forEach(key => {
        next[key] = defaultFilters[key];
      });
      return next;
    });
  } else {
    // apply — דרוס רק את המפתחות של ה-preset
    setDraft(prev => ({ ...prev, ...preset.values }));
  }
};
```

### VERIFY

1. פתח BuildingDefects, בחר category "מטבח" (או כל קטגוריה), לחץ preset "פתוחים"
   - ✅ צפוי: `status=['open']` + `category=['kitchen']` — שניהם פעילים
   - ❌ לא: `category` ריק
2. לחץ על preset "פתוחים" שוב (הוא active עכשיו)
   - ✅ צפוי: `status=[]` + `category=['kitchen']` — ה-category שורד
3. אותה בדיקה ב-ApartmentDashboard עם `company` במקום `category`

---

## 🟡 NICE-TO-HAVE #1 — aria-label על chip בגלל truncate

### הבעיה

כש-chip מקוצר עם `truncate` (קבלן/נושא עם שם ארוך), קורא מסך מקריא רק את החלק הנראה. למשל "בניית יוסי בע"מ בע..." → נשמע חתוך ולא ברור.

### התיקון

**`frontend/src/components/FilterDrawer.js`** — הוסף `aria-label` ו-`title` על כפתור ה-chip:

```jsx
<button
  key={`${chip.sectionKey}:${chip.value}`}
  type="button"
  onClick={() => toggleValue(chip.sectionKey, chip.value)}
  aria-label={`הסר ${chip.label}`}
  title={chip.label}
  className="inline-flex items-center gap-1 max-w-[140px] px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 active:bg-amber-200 transition-colors"
>
  <span className="truncate">{chip.label}</span>
  <X className="w-3 h-3 shrink-0" />
</button>
```

`title` נותן tooltip ב-hover במחשב, `aria-label` נותן קריאת מסך נכונה.

### VERIFY

- Hover על chip מקוצר → מופיע tooltip עם השם המלא
- VoiceOver/NVDA על chip → מקריא "הסר [שם מלא], button"

---

## 🟡 NICE-TO-HAVE #2 — dedupe `arraysEqualAsSets`

### הבעיה

הפונקציה `arraysEqualAsSets` מוגדרת פעמיים, זהה בדיוק:
- `ApartmentDashboardPage.js`
- `BuildingDefectsPage.js`

### התיקון

**צור קובץ חדש `frontend/src/utils/filterHelpers.js`:**

```js
export const arraysEqualAsSets = (a, b) => {
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every(v => set.has(v));
};
```

**מחק את ההגדרה הכפולה מ:**
- `frontend/src/pages/ApartmentDashboardPage.js` — השורות של `arraysEqualAsSets`
- `frontend/src/pages/BuildingDefectsPage.js` — השורות של `arraysEqualAsSets`

**והוסף import בשניהם:**
```js
import { arraysEqualAsSets } from '../utils/filterHelpers';
```

### VERIFY

```bash
grep -rn "arraysEqualAsSets" frontend/src/
```
צפוי: 1 הגדרה ב-`utils/filterHelpers.js` + 2 imports + 2 שימושים (אחד בכל דף).

---

## DO NOT

- **אל תיגע ב-`ExportModal` coercion shim** — זה נשאר ל-#382 כפי שתוכנן.
- **אל תוסיף presets חדשים** — הוספות UX ל-#381.
- **אל תשנה את ה-`selectedChips` building logic** — הוא עובד נכון.
- **אל תשנה את ה-CSS של ה-preset buttons** — הצבעים עקביים כרגע עם ה-pills הרגילים.

---

## סיכום Checklist

- [ ] `applyPreset` משתמש ב-`setDraft(prev => ...)` ולא דורס כל ה-draft
- [ ] preset active → deselect מאפס רק את המפתחות שלו
- [ ] preset inactive → apply דורס רק את המפתחות שלו, שאר הסינון נשמר
- [ ] chip button יש `aria-label="הסר ..."` ו-`title="..."`
- [ ] `arraysEqualAsSets` זז ל-`utils/filterHelpers.js`, 2 imports מעודכנים
- [ ] `npm run build` עובר בלי warnings חדשים
- [ ] בדיקה ידנית: category+preset שומר את ה-category
