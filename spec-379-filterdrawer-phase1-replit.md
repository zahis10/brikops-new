# Task #379 (Spec #26 — FilterDrawer Phase 1) — Multi-select + Counts + Live CTA

## What & Why
ה-FilterDrawer היום הוא **single-select**: כל סקשן עם "הכל" + אופציות, בחירה באחת מאפסת אחרות. בפועל מפקח רוצה "פתוחים + בטיפול" או "חברה A + חברה B" באותו זמן — אי אפשר.

בנוסף, אין שום סימון כמה ליקויים יתאימו לסינון שבחרת עד שסגרת את המגירה. חוזרים-לפתוח כדי לתקן בחירה.

**Phase 1 deliverables:**
1. **Multi-select** בכל סקשן — בחירות מצטברות, עם ✓ לצד כל אופציה נבחרת, לחיצה שוב מבטלת.
2. **Count לצד כל אופציה** — ("פתוחים 7"). נספר client-side בלי קריאת API.
3. **Footer CTA חי** — "הצג 12 ליקויים" שמתעדכן בזמן אמת עם הטיוטה.

Phase 2 (ספק #380) יוסיף chips פעילים + פריסטים. Phase 3 (#381) חיפוש + ליטוש.

## Done looks like
- משתמש פותח מגירה ב-ApartmentDashboard או BuildingDefects, בוחר "פתוחים" + "בטיפול" → שתיהן מסומנות עם ✓.
- כל אופציה מציגה "(N)" בצד הלייבל כשיש ספירה.
- כפתור ה-CTA מציג "הצג 12 ליקויים" (או "הצג 12 דירות" ב-BuildingDefects) ומתעדכן חי.
- לחיצה ב-CTA → מחיל ומסגור.
- "אפס" → מנקה את הטיוטה (כל הארייז חוזרים ל-`[]`).
- אפס שינוי ב-UI של ה-header/listing/badges בדפים הקונסומרים — רק מקור הנתונים השתנה.
- Build עובר נקי, אפס regression ב-filter semantics.

## Data shape change (CRITICAL)
**היום** (string):
```js
filters = { status: 'all', category: 'all', company: 'all', ... }
// 'all' או ערך בודד כמו 'open'
```

**אחרי** (array):
```js
filters = { status: [], category: [], company: [], ... }
// [] = הכל | ['open'] = בודד | ['open', 'in_progress'] = משולב
```

**כלל הזהב:** `filter_array.length === 0` שקול ל-`'all'` הישן. הסינון נעשה עם `.includes()`.

## Out of scope
- ❌ לא מוסיפים chips פעילים בראש המגירה — Phase 2.
- ❌ לא מוסיפים פריסטים — Phase 2.
- ❌ לא מוסיפים חיפוש בתוך סקשנים — Phase 3.
- ❌ לא משנים את ה-Sheet primitive, לא משנים את רוחב המגירה (320/360).
- ❌ לא נוגעים ב-ProjectTasksPage, UnitDetailPage, ProjectControlPage, MyProjectsPage, UnitHomePage, Handover, QC, Admin, Auth, Settings.
- ❌ לא נוגעים ב-backend (אפס endpoints חדשים, אפס שינוי schema).
- ❌ לא נוגעים ב-`frontend/src/i18n/`, `tailwind.config.js`, `shadcn/ui`.
- ❌ לא מוסיפים animations או transitions חדשים.
- ❌ לא מוסיפים "הכל" pill — array ריק = הכל (convention).
- ❌ לא משנים את ה-URL query params / deep linking (הדפים לא משתמשים בזה היום).
- ❌ לא מוסיפים accessibility attributes חדשים מעבר למה שכבר יש.
- ❌ `filters.status` בתוך ApartmentDashboardPage מוחל כרגע **אחרי** baseFilter (lines 321-323) כדי שהספירות `filterCounts` יהיו נכונות — **שמור על המבנה הזה**, רק החלף את ההשוואה משווה-יחיד למערך.

## Tasks

### 1 — `frontend/src/components/FilterDrawer.js` (REPLACE ENTIRE FILE)

מצא ב-grep:
```bash
grep -n "FilterDrawer" frontend/src/components/FilterDrawer.js | head -3
```

החלף את כל תוכן הקובץ (137 שורות) בתוכן הבא:

```jsx
import React, { useState, useEffect } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from './ui/sheet';
import { SlidersHorizontal, ChevronDown, ChevronUp, Check } from 'lucide-react';

const FilterSection = ({ label, values, onToggle, options, isOpen, onToggleOpen }) => (
  <div>
    <button
      type="button"
      onClick={onToggleOpen}
      className="w-full flex items-center justify-between py-1"
    >
      <h4 className="text-sm font-semibold text-slate-700">{label}</h4>
      {isOpen
        ? <ChevronUp className="w-4 h-4 text-slate-400" />
        : <ChevronDown className="w-4 h-4 text-slate-400" />
      }
    </button>
    {isOpen && (
      <div className="flex flex-wrap gap-2 mt-2">
        {options.map(opt => {
          const selected = values.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onToggle(opt.value)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors max-w-[200px] ${
                selected
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {selected && <Check className="w-3.5 h-3.5 shrink-0" />}
              <span className="truncate">{opt.label}</span>
              {typeof opt.count === 'number' && (
                <span className={`shrink-0 text-[11px] tabular-nums ${selected ? 'text-white/80' : 'text-slate-400'}`}>
                  {opt.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    )}
  </div>
);

const FilterDrawer = ({
  open,
  onOpenChange,
  filters,
  defaultFilters,
  onApply,
  sections,
  computeMatchCount,
  matchLabel = 'ליקויים',
}) => {
  const [draft, setDraft] = useState({ ...filters });
  const [wasOpen, setWasOpen] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState({});

  useEffect(() => {
    if (open && !wasOpen) {
      setDraft({ ...filters });
      setCollapsedSections({});
    }
    setWasOpen(open);
  }, [open, filters, wasOpen]);

  const toggleSection = (key) => {
    setCollapsedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleValue = (key, value) => {
    setDraft(prev => {
      const current = Array.isArray(prev[key]) ? prev[key] : [];
      const next = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value];
      return { ...prev, [key]: next };
    });
  };

  const handleApply = () => {
    onApply(draft);
    onOpenChange(false);
  };

  const handleReset = () => {
    setDraft({ ...defaultFilters });
  };

  const matchCount = typeof computeMatchCount === 'function'
    ? computeMatchCount(draft)
    : null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[320px] sm:w-[360px] flex flex-col p-0" dir="rtl">
        <SheetHeader className="px-5 pt-5 pb-3 border-b border-slate-200">
          <SheetTitle className="text-right text-base font-bold text-slate-800">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4" />
              סינון
            </div>
          </SheetTitle>
          <SheetDescription className="sr-only">בחר סינון לליקויים</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {sections.map(section => (
            section.options.length > 0 && (
              <FilterSection
                key={section.key}
                label={section.label}
                values={Array.isArray(draft[section.key]) ? draft[section.key] : []}
                onToggle={v => toggleValue(section.key, v)}
                options={section.options}
                isOpen={!collapsedSections[section.key]}
                onToggleOpen={() => toggleSection(section.key)}
              />
            )
          ))}
        </div>

        <div className="border-t border-slate-200 px-5 py-3 flex gap-3">
          <button
            type="button"
            onClick={handleReset}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 active:bg-slate-100 transition-colors"
          >
            אפס
          </button>
          <button
            type="button"
            onClick={handleApply}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-bold bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white shadow-sm transition-colors"
          >
            {matchCount === null ? 'סיים' : `הצג ${matchCount} ${matchLabel}`}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default FilterDrawer;
```

**הערות על השינוי:**
- `Check` מיובא מ-lucide-react.
- `FilterSection` מקבל `values` (מערך) + `onToggle(value)` (פונקציית toggle יחיד), במקום `value` + `onChange`.
- אין יותר `<button>` של "הכל" — מערך ריק = הכל.
- אופציה מציגה `opt.count` כטקסט `tabular-nums` רק כשה-count הוא number.
- `computeMatchCount` אופציונלי — כשלא מסופק, ה-CTA מציג "סיים" (backward compat אבל לא רלוונטי כי 2 הקונסומרים יעדכנו).
- `matchLabel` ברירת מחדל "ליקויים"; BuildingDefects יעביר "דירות".

### 2 — `frontend/src/pages/ApartmentDashboardPage.js`

**2a.** `APARTMENT_DEFAULT_FILTERS` (line 18–24) — החלף string → array.

מצא:
```bash
grep -n "APARTMENT_DEFAULT_FILTERS = " frontend/src/pages/ApartmentDashboardPage.js
```

BEFORE (lines 18–24):
```js
const APARTMENT_DEFAULT_FILTERS = {
  status: 'all',
  category: 'all',
  company: 'all',
  assignee: 'all',
  created_by: 'all',
};
```

AFTER:
```js
const APARTMENT_DEFAULT_FILTERS = {
  status: [],
  category: [],
  company: [],
  assignee: [],
  created_by: [],
};
```

**2b.** `filterSections` useMemo (line 206–232) — הוסף `count` לכל אופציה.

מצא:
```bash
grep -n "const filterSections = useMemo" frontend/src/pages/ApartmentDashboardPage.js
```

BEFORE:
```js
  const filterSections = useMemo(() => {
    const cats = {};
    const companies = {};
    const assignees = {};
    const creators = {};

    tasks.forEach(t => {
      if (t.category) cats[t.category] = tCategory(t.category);
      if (t.company_id) {
        companies[t.company_id] = t.company_name || t.assignee_company_name || t.company_id.slice(0, 8);
      }
      if (t.assignee_id) {
        assignees[t.assignee_id] = t.assignee_name || t.assigned_to_name || t.assignee_id.slice(0, 8);
      }
      if (t.created_by) {
        creators[t.created_by] = t.created_by_name || t.created_by.slice(0, 8);
      }
    });

    return [
      { key: 'status', label: 'סטטוס', options: STATUS_FILTER_OPTIONS },
      { key: 'category', label: 'תחום', options: Object.entries(cats).map(([v, l]) => ({ value: v, label: l })) },
      { key: 'company', label: 'חברה', options: Object.entries(companies).map(([v, l]) => ({ value: v, label: l })) },
      { key: 'assignee', label: 'אחראי', options: Object.entries(assignees).map(([v, l]) => ({ value: v, label: l })) },
      { key: 'created_by', label: 'נוצר על ידי', options: Object.entries(creators).map(([v, l]) => ({ value: v, label: l })) },
    ];
  }, [tasks]);
```

AFTER:
```js
  const filterSections = useMemo(() => {
    const cats = {};
    const companies = {};
    const assignees = {};
    const creators = {};

    tasks.forEach(t => {
      if (t.category) cats[t.category] = tCategory(t.category);
      if (t.company_id) {
        companies[t.company_id] = t.company_name || t.assignee_company_name || t.company_id.slice(0, 8);
      }
      if (t.assignee_id) {
        assignees[t.assignee_id] = t.assignee_name || t.assigned_to_name || t.assignee_id.slice(0, 8);
      }
      if (t.created_by) {
        creators[t.created_by] = t.created_by_name || t.created_by.slice(0, 8);
      }
    });

    const countBy = (predicate) => tasks.filter(predicate).length;

    return [
      {
        key: 'status',
        label: 'סטטוס',
        options: STATUS_FILTER_OPTIONS.map(o => ({
          ...o,
          count: countBy(t => STATUS_LABELS[t.status]?.key === o.value),
        })),
      },
      {
        key: 'category',
        label: 'תחום',
        options: Object.entries(cats).map(([v, l]) => ({
          value: v, label: l, count: countBy(t => t.category === v),
        })),
      },
      {
        key: 'company',
        label: 'חברה',
        options: Object.entries(companies).map(([v, l]) => ({
          value: v, label: l, count: countBy(t => t.company_id === v),
        })),
      },
      {
        key: 'assignee',
        label: 'אחראי',
        options: Object.entries(assignees).map(([v, l]) => ({
          value: v, label: l, count: countBy(t => t.assignee_id === v),
        })),
      },
      {
        key: 'created_by',
        label: 'נוצר על ידי',
        options: Object.entries(creators).map(([v, l]) => ({
          value: v, label: l, count: countBy(t => t.created_by === v),
        })),
      },
    ];
  }, [tasks]);
```

**2c.** `activeFilterCount` useMemo (line 234–243) — החלף comparison ל-`.length > 0`.

BEFORE:
```js
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.status !== 'all') count++;
    if (filters.category !== 'all') count++;
    if (filters.company !== 'all') count++;
    if (filters.assignee !== 'all') count++;
    if (filters.created_by !== 'all') count++;
    if (searchQuery.trim()) count++;
    return count;
  }, [filters, searchQuery]);
```

AFTER:
```js
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.status.length > 0) count++;
    if (filters.category.length > 0) count++;
    if (filters.company.length > 0) count++;
    if (filters.assignee.length > 0) count++;
    if (filters.created_by.length > 0) count++;
    if (searchQuery.trim()) count++;
    return count;
  }, [filters, searchQuery]);
```

**2d.** `filterSummaryText` useMemo (line 245–259) — החלף string לקחת את הלייבל של הערכים הנבחרים.

BEFORE:
```js
  const filterSummaryText = useMemo(() => {
    const parts = [];
    filterSections.forEach(section => {
      const val = filters[section.key];
      if (val && val !== 'all') {
        const opt = section.options.find(o => o.value === val);
        parts.push(`${section.label}: ${opt?.label || val}`);
      }
    });
    if (searchQuery.trim()) parts.push(`חיפוש: "${searchQuery.trim()}"`);

    if (parts.length === 0) return '';
    if (parts.length <= 3) return parts.join(' · ');
    return parts.slice(0, 2).join(' · ') + ` · עוד ${parts.length - 2}`;
  }, [filters, searchQuery, filterSections]);
```

AFTER:
```js
  const filterSummaryText = useMemo(() => {
    const parts = [];
    filterSections.forEach(section => {
      const vals = filters[section.key];
      if (Array.isArray(vals) && vals.length > 0) {
        const labels = vals.map(v => section.options.find(o => o.value === v)?.label || v);
        const joined = labels.length === 1 ? labels[0] : `${labels[0]} +${labels.length - 1}`;
        parts.push(`${section.label}: ${joined}`);
      }
    });
    if (searchQuery.trim()) parts.push(`חיפוש: "${searchQuery.trim()}"`);

    if (parts.length === 0) return '';
    if (parts.length <= 3) return parts.join(' · ');
    return parts.slice(0, 2).join(' · ') + ` · עוד ${parts.length - 2}`;
  }, [filters, searchQuery, filterSections]);
```

**2e.** `baseFilteredTasks` (line 302–312) — החלף string comparison ל-`.includes()`.

BEFORE:
```js
  const baseFilteredTasks = tasks.filter(t => {
    if (filters.category !== 'all' && t.category !== filters.category) return false;
    if (filters.company !== 'all' && t.company_id !== filters.company) return false;
    if (filters.assignee !== 'all' && t.assignee_id !== filters.assignee) return false;
    if (filters.created_by !== 'all' && t.created_by !== filters.created_by) return false;
    if (searchLower && !(
      (t.title || '').toLowerCase().includes(searchLower) ||
      (t.description || '').toLowerCase().includes(searchLower)
    )) return false;
    return true;
  });
```

AFTER:
```js
  const baseFilteredTasks = tasks.filter(t => {
    if (filters.category.length > 0 && !filters.category.includes(t.category)) return false;
    if (filters.company.length > 0 && !filters.company.includes(t.company_id)) return false;
    if (filters.assignee.length > 0 && !filters.assignee.includes(t.assignee_id)) return false;
    if (filters.created_by.length > 0 && !filters.created_by.includes(t.created_by)) return false;
    if (searchLower && !(
      (t.title || '').toLowerCase().includes(searchLower) ||
      (t.description || '').toLowerCase().includes(searchLower)
    )) return false;
    return true;
  });
```

**2f.** `filteredTasks` (line 321–323) — החלף single-status comparison ל-multi.

BEFORE:
```js
  const filteredTasks = filters.status === 'all'
    ? baseFilteredTasks
    : baseFilteredTasks.filter(t => STATUS_LABELS[t.status]?.key === filters.status);
```

AFTER:
```js
  const filteredTasks = filters.status.length === 0
    ? baseFilteredTasks
    : baseFilteredTasks.filter(t => filters.status.includes(STATUS_LABELS[t.status]?.key));
```

**2g.** `filterCounts` (line 314–319) — נשאר זהה (לא תלוי ב-filter values).

**2h.** הוסף `computeMatchCount` וה-JSX של ה-FilterDrawer (line ~758).

מצא:
```bash
grep -n "<FilterDrawer" frontend/src/pages/ApartmentDashboardPage.js
```

לפני ה-`return (` של הקומפוננטה (אחרי line 325, `const hasActiveFilters = activeFilterCount > 0;`), הוסף:

```js
  const computeMatchCount = useCallback((draft) => {
    const draftSearchLower = searchQuery.trim().toLowerCase();
    return tasks.filter(t => {
      if (draft.category.length > 0 && !draft.category.includes(t.category)) return false;
      if (draft.company.length > 0 && !draft.company.includes(t.company_id)) return false;
      if (draft.assignee.length > 0 && !draft.assignee.includes(t.assignee_id)) return false;
      if (draft.created_by.length > 0 && !draft.created_by.includes(t.created_by)) return false;
      if (draft.status.length > 0 && !draft.status.includes(STATUS_LABELS[t.status]?.key)) return false;
      if (draftSearchLower && !(
        (t.title || '').toLowerCase().includes(draftSearchLower) ||
        (t.description || '').toLowerCase().includes(draftSearchLower)
      )) return false;
      return true;
    }).length;
  }, [tasks, searchQuery]);
```

**2i.** עדכן את `<FilterDrawer />` JSX (line ~758–764):

מצא:
```bash
grep -n "computeMatchCount=\|matchLabel=" frontend/src/pages/ApartmentDashboardPage.js
```
(צריך להחזיר 0 לפני העריכה; 2 אחרי.)

BEFORE:
```jsx
      <FilterDrawer
        open={filterDrawerOpen}
        onOpenChange={setFilterDrawerOpen}
        filters={filters}
        defaultFilters={APARTMENT_DEFAULT_FILTERS}
        onApply={setFilters}
        sections={filterSections}
      />
```

AFTER:
```jsx
      <FilterDrawer
        open={filterDrawerOpen}
        onOpenChange={setFilterDrawerOpen}
        filters={filters}
        defaultFilters={APARTMENT_DEFAULT_FILTERS}
        onApply={setFilters}
        sections={filterSections}
        computeMatchCount={computeMatchCount}
        matchLabel="ליקויים"
      />
```

**2j.** ודא ש-`useCallback` מיובא. בראש הקובץ, בדוק ש-`useCallback` כבר ב-imports מ-'react'. אם לא, הוסף.

### 3 — `frontend/src/pages/BuildingDefectsPage.js`

**3a.** `BUILDING_DEFAULT_FILTERS` (line 15–20).

BEFORE:
```js
const BUILDING_DEFAULT_FILTERS = {
  status: 'all',
  category: 'all',
  floor: 'all',
  unit: 'all',
};
```

AFTER:
```js
const BUILDING_DEFAULT_FILTERS = {
  status: [],
  category: [],
  floor: [],
  unit: [],
};
```

**3b.** `useEffect` שמאפס filter שנהיה לא-תקף (line 83–109) — החלף comparison.

מצא:
```bash
grep -n "prev.floor !== 'all'" frontend/src/pages/BuildingDefectsPage.js
```

BEFORE:
```js
      if (prev.floor !== 'all' && !data.floors.some(f => f.id === prev.floor)) {
        next.floor = 'all';
        changed = true;
      }
      if (prev.unit !== 'all') {
        const allUnits = data.floors.flatMap(f => f.units || []);
        if (!allUnits.some(u => u.id === prev.unit)) {
          next.unit = 'all';
          changed = true;
        }
      }
      if (prev.category !== 'all') {
        const allCats = new Set();
        data.floors.forEach(f => (f.units || []).forEach(u => (u.categories || []).forEach(c => allCats.add(c))));
        if (!allCats.has(prev.category)) {
          next.category = 'all';
          changed = true;
        }
      }
```

AFTER:
```js
      if (prev.floor.length > 0) {
        const validFloorIds = new Set(data.floors.map(f => f.id));
        const filtered = prev.floor.filter(id => validFloorIds.has(id));
        if (filtered.length !== prev.floor.length) {
          next.floor = filtered;
          changed = true;
        }
      }
      if (prev.unit.length > 0) {
        const allUnitIds = new Set(data.floors.flatMap(f => (f.units || []).map(u => u.id)));
        const filtered = prev.unit.filter(id => allUnitIds.has(id));
        if (filtered.length !== prev.unit.length) {
          next.unit = filtered;
          changed = true;
        }
      }
      if (prev.category.length > 0) {
        const allCats = new Set();
        data.floors.forEach(f => (f.units || []).forEach(u => (u.categories || []).forEach(c => allCats.add(c))));
        const filtered = prev.category.filter(c => allCats.has(c));
        if (filtered.length !== prev.category.length) {
          next.category = filtered;
          changed = true;
        }
      }
```

**3c.** `unitPassesFilter` (line 151–167) — החלף comparison ל-`.includes()`.

BEFORE:
```js
  const unitPassesFilter = (unit) => {
    if (unitTypeFilter && unit.unit_type_tag !== unitTypeFilter) return false;
    if (filters.unit !== 'all' && unit.id !== filters.unit) return false;
    if (filters.category !== 'all' && !(unit.categories || []).includes(filters.category)) return false;
    if (filters.status !== 'all') {
      const c = unit.defect_counts || {};
      if (filters.status === 'open' && (c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0) === 0) return false;
      if (filters.status === 'closed' && (c.closed || 0) === 0) return false;
      if (filters.status === 'blocking' && (c.open || 0) + (c.in_progress || 0) === 0) return false;
    }
    const searchLower = searchQuery.trim().toLowerCase();
    if (searchLower) {
      const label = (unit.display_label || unit.unit_no || '').toLowerCase();
      if (!label.includes(searchLower)) return false;
    }
    return true;
  };
```

AFTER:
```js
  const unitPassesFilter = (unit) => {
    if (unitTypeFilter && unit.unit_type_tag !== unitTypeFilter) return false;
    if (filters.unit.length > 0 && !filters.unit.includes(unit.id)) return false;
    if (filters.category.length > 0) {
      const unitCats = unit.categories || [];
      if (!filters.category.some(c => unitCats.includes(c))) return false;
    }
    if (filters.status.length > 0) {
      const c = unit.defect_counts || {};
      const matchesAny =
        (filters.status.includes('open')     && ((c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0)) > 0) ||
        (filters.status.includes('closed')   && (c.closed || 0) > 0) ||
        (filters.status.includes('blocking') && ((c.open || 0) + (c.in_progress || 0)) > 0);
      if (!matchesAny) return false;
    }
    const searchLower = searchQuery.trim().toLowerCase();
    if (searchLower) {
      const label = (unit.display_label || unit.unit_no || '').toLowerCase();
      if (!label.includes(searchLower)) return false;
    }
    return true;
  };
```

**3d.** `getStatusCount` (line 169–175) — הספירה המוצגת בכל דירה. שמור על סמנטיקה: אם נבחר status יחיד → ספירה ייחודית, אחרת `c.total`.

BEFORE:
```js
  const getStatusCount = (c) => {
    if (!c) return 0;
    if (filters.status === 'open') return (c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0);
    if (filters.status === 'closed') return c.closed || 0;
    if (filters.status === 'blocking') return (c.open || 0) + (c.in_progress || 0);
    return c.total || 0;
  };
```

AFTER:
```js
  const getStatusCount = (c) => {
    if (!c) return 0;
    if (filters.status.length === 1) {
      const s = filters.status[0];
      if (s === 'open') return (c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0);
      if (s === 'closed') return c.closed || 0;
      if (s === 'blocking') return (c.open || 0) + (c.in_progress || 0);
    }
    if (filters.status.length > 1) {
      let sum = 0;
      if (filters.status.includes('open'))     sum += (c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0);
      if (filters.status.includes('closed'))   sum += (c.closed || 0);
      if (filters.status.includes('blocking')) sum += (c.open || 0) + (c.in_progress || 0);
      return sum;
    }
    return c.total || 0;
  };
```

**3e.** `getFilteredFloorData` (line 177–187) — החלף comparison.

BEFORE:
```js
  const getFilteredFloorData = () => {
    if (!data?.floors) return [];
    const hasFilters = filters.status !== 'all' || filters.category !== 'all' || filters.floor !== 'all' || filters.unit !== 'all' || searchQuery.trim();
    return (data.floors || [])
      .filter(f => filters.floor === 'all' || f.id === filters.floor)
      .map(floor => {
        const filteredUnits = (floor.units || []).filter(unitPassesFilter);
        return { ...floor, filteredUnits };
      })
      .filter(floor => !hasFilters || floor.filteredUnits.length > 0);
  };
```

AFTER:
```js
  const getFilteredFloorData = () => {
    if (!data?.floors) return [];
    const hasFilters = filters.status.length > 0 || filters.category.length > 0 || filters.floor.length > 0 || filters.unit.length > 0 || searchQuery.trim();
    return (data.floors || [])
      .filter(f => filters.floor.length === 0 || filters.floor.includes(f.id))
      .map(floor => {
        const filteredUnits = (floor.units || []).filter(unitPassesFilter);
        return { ...floor, filteredUnits };
      })
      .filter(floor => !hasFilters || floor.filteredUnits.length > 0);
  };
```

**3f.** `filterSections` (line 193–211) — הוסף `count` לכל אופציה.

BEFORE:
```js
  const filterSections = useMemo(() => {
    if (!data?.floors) return [];
    const cats = new Set();
    const floorOpts = [];
    const unitOpts = [];
    (data.floors || []).forEach(f => {
      floorOpts.push({ value: f.id, label: f.display_label || f.name || `קומה ${f.floor_number}` });
      (f.units || []).forEach(u => {
        (u.categories || []).forEach(c => cats.add(c));
        unitOpts.push({ value: u.id, label: formatUnitLabel(u.display_label || u.unit_no || '') });
      });
    });
    return [
      { key: 'status', label: 'סטטוס', options: STATUS_FILTER_OPTIONS },
      { key: 'category', label: 'תחום', options: [...cats].sort().map(c => ({ value: c, label: tCategory(c) })) },
      { key: 'floor', label: 'קומה', options: floorOpts },
      { key: 'unit', label: 'דירה', options: unitOpts },
    ];
  }, [data]);
```

AFTER:
```js
  const filterSections = useMemo(() => {
    if (!data?.floors) return [];
    const cats = new Set();
    const floorUnits = new Map(); // floorId -> unit count
    const unitHasDefects = new Map(); // unitId -> boolean any defects
    const catCounts = {};
    const statusCounts = { open: 0, closed: 0, blocking: 0 };
    const floorOpts = [];
    const unitOpts = [];

    (data.floors || []).forEach(f => {
      const fUnits = f.units || [];
      floorUnits.set(f.id, fUnits.length);
      floorOpts.push({
        value: f.id,
        label: f.display_label || f.name || `קומה ${f.floor_number}`,
        count: fUnits.length,
      });
      fUnits.forEach(u => {
        (u.categories || []).forEach(c => {
          cats.add(c);
          catCounts[c] = (catCounts[c] || 0) + 1;
        });
        const c = u.defect_counts || {};
        if ((c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0) > 0) statusCounts.open += 1;
        if ((c.closed || 0) > 0) statusCounts.closed += 1;
        if ((c.open || 0) + (c.in_progress || 0) > 0) statusCounts.blocking += 1;
        unitOpts.push({
          value: u.id,
          label: formatUnitLabel(u.display_label || u.unit_no || ''),
          count: c.total || 0,
        });
      });
    });

    return [
      {
        key: 'status',
        label: 'סטטוס',
        options: STATUS_FILTER_OPTIONS.map(o => ({ ...o, count: statusCounts[o.value] || 0 })),
      },
      {
        key: 'category',
        label: 'תחום',
        options: [...cats].sort().map(c => ({ value: c, label: tCategory(c), count: catCounts[c] || 0 })),
      },
      { key: 'floor', label: 'קומה', options: floorOpts },
      { key: 'unit', label: 'דירה', options: unitOpts },
    ];
  }, [data]);
```

**3g.** `activeFilterCount` (line 213–221).

BEFORE:
```js
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.status !== 'all') count++;
    if (filters.category !== 'all') count++;
    if (filters.floor !== 'all') count++;
    if (filters.unit !== 'all') count++;
    if (searchQuery.trim()) count++;
    return count;
  }, [filters, searchQuery]);
```

AFTER:
```js
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.status.length > 0) count++;
    if (filters.category.length > 0) count++;
    if (filters.floor.length > 0) count++;
    if (filters.unit.length > 0) count++;
    if (searchQuery.trim()) count++;
    return count;
  }, [filters, searchQuery]);
```

**3h.** `filterSummaryText` (line 223–236).

BEFORE:
```js
  const filterSummaryText = useMemo(() => {
    const parts = [];
    filterSections.forEach(section => {
      const val = filters[section.key];
      if (val && val !== 'all') {
        const opt = section.options.find(o => o.value === val);
        parts.push(`${section.label}: ${opt?.label || val}`);
      }
    });
    if (searchQuery.trim()) parts.push(`חיפוש: "${searchQuery.trim()}"`);
    if (parts.length === 0) return '';
    if (parts.length <= 3) return parts.join(' · ');
    return parts.slice(0, 2).join(' · ') + ` · עוד ${parts.length - 2}`;
  }, [filters, searchQuery, filterSections]);
```

AFTER:
```js
  const filterSummaryText = useMemo(() => {
    const parts = [];
    filterSections.forEach(section => {
      const vals = filters[section.key];
      if (Array.isArray(vals) && vals.length > 0) {
        const labels = vals.map(v => section.options.find(o => o.value === v)?.label || v);
        const joined = labels.length === 1 ? labels[0] : `${labels[0]} +${labels.length - 1}`;
        parts.push(`${section.label}: ${joined}`);
      }
    });
    if (searchQuery.trim()) parts.push(`חיפוש: "${searchQuery.trim()}"`);
    if (parts.length === 0) return '';
    if (parts.length <= 3) return parts.join(' · ');
    return parts.slice(0, 2).join(' · ') + ` · עוד ${parts.length - 2}`;
  }, [filters, searchQuery, filterSections]);
```

**3i.** הוסף `computeMatchCount` לפני ה-`return`. מצא את השורה `const hasActiveFilters = activeFilterCount > 0;` (line ~238). מיד אחריה הוסף:

```js
  const computeMatchCount = useCallback((draft) => {
    if (!data?.floors) return 0;
    const draftSearchLower = searchQuery.trim().toLowerCase();
    const unitPasses = (unit) => {
      if (unitTypeFilter && unit.unit_type_tag !== unitTypeFilter) return false;
      if (draft.unit.length > 0 && !draft.unit.includes(unit.id)) return false;
      if (draft.category.length > 0) {
        const unitCats = unit.categories || [];
        if (!draft.category.some(c => unitCats.includes(c))) return false;
      }
      if (draft.status.length > 0) {
        const c = unit.defect_counts || {};
        const matchesAny =
          (draft.status.includes('open')     && ((c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0)) > 0) ||
          (draft.status.includes('closed')   && (c.closed || 0) > 0) ||
          (draft.status.includes('blocking') && ((c.open || 0) + (c.in_progress || 0)) > 0);
        if (!matchesAny) return false;
      }
      if (draftSearchLower) {
        const label = (unit.display_label || unit.unit_no || '').toLowerCase();
        if (!label.includes(draftSearchLower)) return false;
      }
      return true;
    };
    let count = 0;
    (data.floors || [])
      .filter(f => draft.floor.length === 0 || draft.floor.includes(f.id))
      .forEach(f => {
        count += (f.units || []).filter(unitPasses).length;
      });
    return count;
  }, [data, searchQuery, unitTypeFilter]);
```

**3j.** עדכן את `<FilterDrawer />` JSX (line ~492).

BEFORE:
```jsx
      <FilterDrawer
        open={filterDrawerOpen}
        onOpenChange={setFilterDrawerOpen}
        filters={filters}
        defaultFilters={BUILDING_DEFAULT_FILTERS}
        onApply={setFilters}
        sections={filterSections}
      />
```

AFTER:
```jsx
      <FilterDrawer
        open={filterDrawerOpen}
        onOpenChange={setFilterDrawerOpen}
        filters={filters}
        defaultFilters={BUILDING_DEFAULT_FILTERS}
        onApply={setFilters}
        sections={filterSections}
        computeMatchCount={computeMatchCount}
        matchLabel="דירות"
      />
```

**3k.** ודא ש-`useCallback` מיובא מ-'react'.

## DO NOT
- ❌ אל תיגע בשום עמוד אחר (ProjectTasksPage, UnitDetailPage, ProjectControlPage, MyProjectsPage, UnitHomePage, HandoverRoomPage, QCPages, Admin, Auth, Settings).
- ❌ אל תוסיף props חדשים ל-Sheet primitive או שום קומפוננט ב-`ui/`.
- ❌ אל תשנה את ה-header/listing של 2 הדפים — רק filter internals.
- ❌ אל תוסיף חיפוש בתוך סקשנים ב-FilterDrawer — Phase 3.
- ❌ אל תוסיף active chips summary — Phase 2.
- ❌ אל תוסיף presets — Phase 2.
- ❌ אל תסיר את ה-`button` של "הכל" מוקדם מדי — בגרסה החדשה אין אותו בכלל, אבל וודא שה-state התחלתי של filters הוא `[]` ולא `'all'` בשום מקום.
- ❌ אל תיגע ב-`frontend/src/i18n/`.
- ❌ אל תיגע ב-`tailwind.config.js`.
- ❌ אל תיגע ב-`backend/`.
- ❌ אל תיגע ב-URL params / deep linking (הדפים לא משתמשים בזה).
- ❌ אל תשנה את צבעי ה-pills (amber-500 selected, slate-100 unselected) — רק מוסיפים ✓ ו-count.
- ❌ אל תוסיף `transition-*` חדשים — כבר יש `transition-colors`.
- ❌ אל תעשה rename ל-`draft` / `setDraft` / `collapsedSections` / `toggleSection` / `handleApply` / `handleReset`.
- ❌ אל תיגע ב-`searchQuery` logic בשני הדפים — הוא נפרד מ-filters ונשאר string.
- ❌ אל תיגע ב-`unitTypeFilter` ב-BuildingDefectsPage — הוא נפרד.
- ❌ אל תעשה find-and-replace global של `'all'` — יש מחרוזות אחרות שמשתמשות ב-`'all'` שלא קשורות (כמו `filters.status === 'all'` בדפים אחרים שלא נוגעים בהם).

## VERIFY

1. `git status` — בדיוק 3 קבצים modified: `FilterDrawer.js`, `ApartmentDashboardPage.js`, `BuildingDefectsPage.js`.

2. **Build נקי:**
   ```bash
   cd frontend && CI=true REACT_APP_BACKEND_URL="" NODE_OPTIONS="--max-old-space-size=2048" npx craco build
   ```

3. **FilterDrawer — ודא ש-Check מיובא:**
   ```bash
   grep -n "import.*Check.*from 'lucide-react'" frontend/src/components/FilterDrawer.js
   ```
   חייב להחזיר 1.

4. **FilterDrawer — ודא ש-"הכל" pill לא קיים יותר:**
   ```bash
   grep -c ">הכל<" frontend/src/components/FilterDrawer.js
   ```
   חייב להחזיר **0**.

5. **FilterDrawer — ודא ש-toggleValue קיים:**
   ```bash
   grep -c "toggleValue" frontend/src/components/FilterDrawer.js
   ```
   חייב להחזיר לפחות 2 (הגדרה + שימוש).

6. **FilterDrawer — ודא ש-computeMatchCount נקרא:**
   ```bash
   grep -c "computeMatchCount" frontend/src/components/FilterDrawer.js
   ```
   חייב להחזיר לפחות 2.

7. **FilterDrawer — ודא ש-CTA templated:**
   ```bash
   grep -c "הצג \${matchCount}" frontend/src/components/FilterDrawer.js
   ```
   חייב להחזיר **1**.

8. **ApartmentDashboard — ודא שה-default filters שונה ל-array:**
   ```bash
   grep -A1 "APARTMENT_DEFAULT_FILTERS = {" frontend/src/pages/ApartmentDashboardPage.js | head -3
   ```
   חייב להראות `status: [],` (לא `'all'`).

9. **ApartmentDashboard — ודא שאין יותר `!== 'all'` בלוגיקת ה-filter:**
   ```bash
   grep -n "filters\.\(status\|category\|company\|assignee\|created_by\) !== 'all'" frontend/src/pages/ApartmentDashboardPage.js
   ```
   חייב להחזיר **0**.

10. **ApartmentDashboard — ודא ש-.length > 0 בשימוש:**
    ```bash
    grep -c "filters\.\(status\|category\|company\|assignee\|created_by\)\.length" frontend/src/pages/ApartmentDashboardPage.js
    ```
    חייב להחזיר **לפחות 10** (5 ב-activeFilterCount + 4 ב-baseFilteredTasks + 1 ב-filteredTasks + שימושים ב-computeMatchCount).

11. **ApartmentDashboard — ודא ש-computeMatchCount מועבר ל-FilterDrawer:**
    ```bash
    grep -n "computeMatchCount={computeMatchCount}" frontend/src/pages/ApartmentDashboardPage.js
    ```
    חייב להחזיר **1**.

12. **ApartmentDashboard — ודא ש-matchLabel="ליקויים":**
    ```bash
    grep -n 'matchLabel="ליקויים"' frontend/src/pages/ApartmentDashboardPage.js
    ```
    חייב להחזיר **1**.

13. **BuildingDefects — ודא שה-default filters שונה ל-array:**
    ```bash
    grep -A1 "BUILDING_DEFAULT_FILTERS = {" frontend/src/pages/BuildingDefectsPage.js | head -3
    ```
    חייב להראות `status: [],` (לא `'all'`).

14. **BuildingDefects — ודא שאין יותר `!== 'all'` בלוגיקת ה-filter:**
    ```bash
    grep -n "filters\.\(status\|category\|floor\|unit\) !== 'all'" frontend/src/pages/BuildingDefectsPage.js
    ```
    חייב להחזיר **0**.

15. **BuildingDefects — ודא ש-`=== 'all'` גם נמחק:**
    ```bash
    grep -n "filters\.\(status\|category\|floor\|unit\) === 'all'" frontend/src/pages/BuildingDefectsPage.js
    ```
    חייב להחזיר **0**.

16. **BuildingDefects — ודא ש-computeMatchCount מועבר:**
    ```bash
    grep -n "computeMatchCount={computeMatchCount}" frontend/src/pages/BuildingDefectsPage.js
    ```
    חייב להחזיר **1**.

17. **BuildingDefects — ודא ש-matchLabel="דירות":**
    ```bash
    grep -n 'matchLabel="דירות"' frontend/src/pages/BuildingDefectsPage.js
    ```
    חייב להחזיר **1**.

18. **useCallback מיובא:**
    ```bash
    grep -n "^import.*useCallback" frontend/src/pages/ApartmentDashboardPage.js
    grep -n "^import.*useCallback" frontend/src/pages/BuildingDefectsPage.js
    ```
    שניהם חייבים להחזיר **1**.

19. **אפס שינוי ב-backend:**
    ```bash
    git diff --stat backend/
    ```
    חייב להיות ריק.

20. **אפס שינוי ב-i18n:**
    ```bash
    git diff --stat frontend/src/i18n/
    ```
    חייב להיות ריק.

21. **אפס שינוי ב-tailwind.config.js ו-ui/:**
    ```bash
    git diff frontend/tailwind.config.js frontend/src/components/ui/
    ```
    חייב להיות ריק.

22. **אפס שינוי בדפים אחרים:**
    ```bash
    git diff --stat frontend/src/pages/ | grep -v "ApartmentDashboardPage\|BuildingDefectsPage"
    ```
    חייב להיות ריק.

23. **בדיקה ידנית אחרי deploy (mobile DevTools או טלפון):**

    **ApartmentDashboardPage** (`/projects/[id]/units/[id]`):
    - לחץ על אייקון ה-slider → מגירה נפתחת.
    - בחר "פתוחים" — pill נצבע amber, ✓ מופיע משמאל ל-"פתוחים".
    - בחר גם "בטיפול" — שתיהן נבחרות, שתיהן עם ✓. כפתור CTA מראה "הצג N ליקויים" (N = open + in_progress counts).
    - לחץ שוב על "פתוחים" — ה-✓ נעלם, רק "בטיפול" נבחרת, N יורד.
    - כל אופציה מציגה "(N)" אחרי הלייבל (למשל "פתוחים 7").
    - לחץ "אפס" — כל הבחירות מתאפסות, CTA מחזיר ל-סך הכל.
    - לחץ CTA → רשימת ליקויים משתקפת, המגירה נסגרת.

    **BuildingDefectsPage** (`/projects/[id]/buildings/[id]/defects`):
    - אותה התנהגות אבל CTA אומר "הצג N דירות".
    - בחר "פתוחים" + "סגורים" → מראה דירות שיש בהן open OR closed.
    - הסינון של ה-status ברמת ה-unit (derived) עובד נכון — דירה עם רק closed defects מופיעה כשרק "סגורים" נבחר, לא כשרק "פתוחים" נבחר.

    **בדיקות רגרסיה:**
    - ProjectTasksPage, UnitDetailPage, MyProjectsPage, UnitHomePage — לא השתנו, נראים ומתנהגים כרגיל.
    - ProjectControlPage (`/projects/[id]/control`) — לא השתנה.
    - `searchQuery` (תיבת החיפוש בראש הדף) ב-2 הדפים — עדיין עובדת כמו קודם.
    - `unitTypeFilter` ב-BuildingDefects — עדיין עובד.

## Risks
🟡 Medium.

**מקורות סיכון:**
1. **Data shape migration** — 2 דפים כבר מחזיקים `filters` state. משתמש שטעון את האפליקציה עם state ישן (`'all'`) → כל ה-`.includes()` יזרוק. אבל `filters` מאותחל מ-`useState({ ...DEFAULT })`, ו-DEFAULT השתנה ל-array — אז state חדש יהיה array מלכתחילה. **אין localStorage/URL persistence ל-filters**, אז אין מקור לערכים ישנים. ✅ safe.

2. **BuildingDefectsPage multi-status semantics** — "open" + "closed" ב-multi-select מציג דירות עם OR של התנאים. זה שינוי סמנטי מעדין מה-single-select הקודם אבל בפועל מקביל לכוונת המשתמש. כן.

3. **ספירות option counts** — אם `tasks` ריק או data טרם נטען, `filterSections` מחזיר `options: []` וה-`section.options.length > 0` ב-FilterDrawer מונע רנדור. ✅ safe.

4. **matchCount re-compute performance** — נקרא על כל הקלקה ב-drawer. ל-tasks של עד ~500 זה <1ms. ל-data.floors עם אלפי units יכול להיות יקר — אבל זה CPU-side filter בלבד, וה-unit count ב-BrikOps הוא עד ~200. ✅ safe.

**Rollback:** 3 קבצים, הכל client-side. אם משהו שבור → revert.

## Relevant files
- `frontend/src/components/FilterDrawer.js` (full rewrite)
- `frontend/src/pages/ApartmentDashboardPage.js` (lines 18-24, 206-232, 234-243, 245-259, 302-312, 321-323, ~758-764 + new computeMatchCount)
- `frontend/src/pages/BuildingDefectsPage.js` (lines 15-20, 83-109, 151-167, 169-175, 177-187, 193-211, 213-221, 223-236, ~238 + new computeMatchCount, ~492)
