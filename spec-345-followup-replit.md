# Spec #345 Follow-up — Header bleed עוד 2 עמודים

ב-Task 2 תיקנו את ה-header bleed (gradient כתום נשפך לכל הרוחב במקום להישאר במסגרת mobile של max-w-lg) ב-`UnitDetailPage.js` ו-`BuildingDefectsPage.js`. אבל יש 2 עמודים נוספים עם אותו באג בדיוק שלא תוקנו.

## File 1: `frontend/src/pages/UnitHomePage.js`

**שורה 95:**

BEFORE:
```jsx
<div className="bg-gradient-to-l from-amber-500 to-amber-600 text-white">
  <div className="max-w-lg mx-auto px-4 py-3">
```

AFTER:
```jsx
<div className="bg-slate-50">
  <div className="max-w-lg mx-auto bg-gradient-to-l from-amber-500 to-amber-600 text-white rounded-b-2xl px-4 py-3">
```

## File 2: `frontend/src/pages/ApartmentDashboardPage.js`

**שורה 329:**

BEFORE:
```jsx
<div className="bg-gradient-to-l from-amber-500 to-amber-600 text-white">
  <div className="max-w-lg mx-auto px-4 py-3">
```

AFTER:
```jsx
<div className="bg-slate-50">
  <div className="max-w-lg mx-auto bg-gradient-to-l from-amber-500 to-amber-600 text-white rounded-b-2xl px-4 py-3">
```

## DO NOT
- אל תיגע בשום קובץ אחר
- אל תשנה את ה-padding/margin של ה-content מתחת ל-header
- אל תשנה את צבעי הטקסט בתוך ה-header

## VERIFY
1. `grep -rn "bg-gradient-to-l from-amber-500 to-amber-600" frontend/src/pages/` — צריך להחזיר רק את 4 הקבצים: `UnitDetailPage.js`, `BuildingDefectsPage.js`, `UnitHomePage.js`, `ApartmentDashboardPage.js` — וכולם צריכים להיות בתוך `max-w-lg` עם `rounded-b-2xl`.
2. בדיפלוי: פתח unit page (`/projects/X/units/Y`) ב-mobile width — ה-gradient צריך להיות במסגרת max-w-lg עם פינות עגולות למטה, לא נשפך לכל הרוחב.
3. אותו דבר ל-apartment dashboard.

## Context
זה אותו fix מדויק כמו ב-Task 2. הקבצים שכבר תוקנו לרפרנס:
- `frontend/src/pages/UnitDetailPage.js` שורה 127
- `frontend/src/pages/BuildingDefectsPage.js` שורה 283
