# TODO — ספק נפרד: איחוד Dropdowns + RTL

## סטטוס: ממתין לטיפול

## מה נמצא בסריקה (11.4.2026)

### 3 סוגי dropdown באפליקציה:

1. **MobileSelect** (`components/ui/mobile-select.js`)
   - Custom component, h-12, font-size 16px, touch-friendly
   - **לא בשימוש באף דף** — אף אחד לא עושה import

2. **Radix Select** (`components/ui/select.jsx`)
   - shadcn wrapper, h-9 (36px), קטן למובייל
   - בשימוש רק ב-`OrgBillingPage.js` שורה 1947

3. **Native `<select>`** (`ProjectPlansPage.js` שורות 1031, 1040, 1051)
   - 3 selects לעריכת תוכנית (discipline, floor, unit)
   - index.css שורות 90-103 כופה appearance: menulist + font-size 16px

### DropdownMenu (לא בשימוש)
- `components/ui/dropdown-menu.jsx` קיים אבל אף דף לא מייבא אותו

### בעיות RTL:
- select.jsx: check indicator ב-`right-2`, padding `pl-2 pr-8` — hardcoded LTR
- dropdown-menu.jsx: chevron `ChevronRight` (שורה 29), indicators ב-`left-2` (שורות 83, 102)
- MobileSelect: check icon ב-צד שמאל — צריך בדיקה חיה

### מה צריך לעשות:
- [ ] להחליט על pattern: native select למובייל, MobileSelect/Radix לדסקטופ
- [ ] לתקן RTL ב-select.jsx (pl/pr → ps/pe, left/right → start/end)
- [ ] לתקן RTL ב-dropdown-menu.jsx
- [ ] להכניס MobileSelect לשימוש או למחוק
- [ ] לכתוב ספק מפורט כשמגיע הזמן
