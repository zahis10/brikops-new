# Spec #345 — Follow-ups לטפל בסוף

## 1. Header bleed גם ב-UnitHomePage.js (ואולי ApartmentDashboardPage.js)

**הבעיה:** Task 2 תיקן את ה-gradient הכתום ב-`UnitDetailPage.js` ו-`BuildingDefectsPage.js`, אבל ה-URL `/projects/:projectId/units/:unitId` מוצג בפועל על ידי `UnitHomePage.js` (לא `UnitDetailPage`).

**הוכחה:**
- `frontend/src/App.js` שורות 348-354: `/projects/:projectId/units/:unitId` → `UnitHomePage`
- `frontend/src/pages/UnitHomePage.js` שורה 95: `<div className="bg-gradient-to-l from-amber-500 to-amber-600 text-white">` — אותו באג.

**תיקון נדרש (אחרי שכל 6 ה-Tasks יסתיימו):**

קובץ: `frontend/src/pages/UnitHomePage.js` שורה 95

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

**בדוק גם:** `grep -rn "bg-gradient-to-l from-amber-500 to-amber-600" frontend/src/pages/` — אם יש עוד עמודים עם אותו דפוס (למשל `ApartmentDashboardPage.js`), החל את אותו תיקון שם.
