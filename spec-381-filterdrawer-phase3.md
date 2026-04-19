# Spec #381 — FilterDrawer Phase 3: search + polish

**Base commit:** `cea17b1` (#380-FIX merged)
**Scope:** שלב אחרון של ה-makeover — חיפוש בתוך sections ארוכים + 2 פולישים קטנים (badge של כמות נבחרים + empty state).
**Files:** רק `frontend/src/components/FilterDrawer.js`. אפס שינוי בדפי הצריכה.

---

## המצב היום

ב-BuildingDefects ו-ApartmentDashboard יש sections עם הרבה אפשרויות (company עם 20-50 קבלנים, unit עם 100+ דירות, assignee עם 10-30 משתמשים). המשתמש צריך לגלול וגם לסרוק בעיניים כדי למצוא ערך. אין דרך לחפש.

בנוסף: כשמשתמש מכווץ section שיש בו בחירות, הוא לא רואה שיש שם סינון פעיל — המידע רק בתוך chips ה"נבחרו" שלמעלה.

## מה נוסיף

1. **Search input אוטומטי ב-sections עם ≥8 אפשרויות** (threshold קבוע — לא per-section).
2. **Badge של כמות נבחרים** בכותרת ה-section (בולט במיוחד כשהוא מכווץ).
3. **Empty state** "אין תוצאות מתאימות" כשהחיפוש לא מחזיר כלום.
4. **כפתור X** בתוך ה-input לניקוי מהיר.
5. **State חיפוש מתאפס** כשה-drawer נסגר ונפתח מחדש (כמו ה-draft).

---

## TASK #381 — שינויים ב-`frontend/src/components/FilterDrawer.js`

### 1. imports

הוסף `Search` לרשימת ה-imports מ-`lucide-react`:

```js
import { SlidersHorizontal, ChevronDown, ChevronUp, Check, X, Search } from 'lucide-react';
```

### 2. קבוע מודול למעלה (מעל `FilterSection`)

```js
const SEARCH_THRESHOLD = 8;
```

### 3. החלפה מלאה של `FilterSection`

```jsx
const FilterSection = ({
  label,
  values,
  onToggle,
  options,
  isOpen,
  onToggleOpen,
  searchQuery,
  onSearchChange,
}) => {
  const selectedCount = values.length;
  const needsSearch = options.length >= SEARCH_THRESHOLD;

  const filteredOptions = needsSearch && searchQuery.trim()
    ? options.filter(opt =>
        opt.label.toLowerCase().includes(searchQuery.trim().toLowerCase())
      )
    : options;

  return (
    <div>
      <button
        type="button"
        onClick={onToggleOpen}
        className="w-full flex items-center justify-between py-1"
      >
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-semibold text-slate-700">{label}</h4>
          {selectedCount > 0 && (
            <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-700 tabular-nums">
              {selectedCount}
            </span>
          )}
        </div>
        {isOpen
          ? <ChevronUp className="w-4 h-4 text-slate-400" />
          : <ChevronDown className="w-4 h-4 text-slate-400" />
        }
      </button>

      {isOpen && (
        <div className="mt-2 space-y-2">
          {needsSearch && (
            <div className="relative">
              <Search className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="חפש..."
                className="w-full pr-8 pl-8 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400 placeholder:text-slate-400"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => onSearchChange('')}
                  aria-label="נקה חיפוש"
                  className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          )}

          {filteredOptions.length === 0 ? (
            <div className="text-xs text-slate-400 py-2 text-center">אין תוצאות מתאימות</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {filteredOptions.map(opt => {
                const isSelected = values.includes(opt.value);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => onToggle(opt.value)}
                    title={opt.label}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors max-w-[200px] ${
                      isSelected
                        ? 'bg-amber-500 text-white shadow-sm'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {isSelected && <Check className="w-3.5 h-3.5 shrink-0" />}
                    <span className="truncate">{opt.label}</span>
                    {typeof opt.count === 'number' && (
                      <span className={`text-[10px] tabular-nums ${isSelected ? 'text-white/80' : 'text-slate-400'}`}>
                        {opt.count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
```

**שינויים לעומת הקיים:**
- נוספו props `searchQuery`, `onSearchChange`
- נוסף badge של `selectedCount` בכותרת
- החיפוש מופיע רק כש-`options.length >= SEARCH_THRESHOLD`
- נוסף empty state
- נוסף `title={opt.label}` על כל pill (tooltip למצב מקוצר)
- ה-pill עצמו עבר מ-`max-w-[200px] truncate` ל-`max-w-[200px]` עם `<span className="truncate">` כדי לתת מקום ל-icon Check ולמספר count בלי לקצץ אותם

### 4. הוספת state ב-`FilterDrawer`

בתוך `FilterDrawer` (ליד `collapsedSections`):

```js
const [sectionSearch, setSectionSearch] = useState({});
```

ה-useEffect שמתאפס בפתיחה — הוסף שורה נוספת:

```js
useEffect(() => {
  if (open && !wasOpen) {
    setDraft({ ...filters });
    setCollapsedSections({});
    setSectionSearch({});   // <-- חדש
  }
  setWasOpen(open);
}, [open, filters, wasOpen]);
```

הוסף helper:

```js
const setSearchFor = (key, value) => {
  setSectionSearch(prev => ({ ...prev, [key]: value }));
};
```

### 5. עדכון הקריאה ל-`<FilterSection>`

```jsx
{sections.map(section => (
  section.options.length > 0 && (
    <FilterSection
      key={section.key}
      label={section.label}
      values={draft[section.key]}
      onToggle={v => toggleValue(section.key, v)}
      options={section.options}
      isOpen={!collapsedSections[section.key]}
      onToggleOpen={() => toggleSection(section.key)}
      searchQuery={sectionSearch[section.key] || ''}
      onSearchChange={(value) => setSearchFor(section.key, value)}
    />
  )
))}
```

---

## DO NOT

- **אל תיגע ב-`ExportModal`** — עדיין scope של #382.
- **אל תעביר את `SEARCH_THRESHOLD` ל-prop per-section** — יהיה אוחד לעת עתה.
- **אל תוסיף קיצורי מקלדת** (Escape/slash/Cmd+F) — החוצה מהסקופ של השלב הזה.
- **אל תשנה את התנהגות ה-presets, ה-chips, או ה-CTA התחתון** — הם עובדים.
- **אל תוסיף fuzzy search או highlight** — substring match בלבד, ללא דגשים.
- **אל תשנה את `defaultFilters` או את ה-prop signatures של הדפים** — השינוי כאן מקומי לקומפוננטה.
- **אל תפרק את `FilterSection` לקבצים נפרדים** — נשאר באותו קובץ.
- **אל תוסיף `useMemo` מיותר** — ה-`filteredOptions` חישוב זול, לא צריך memoization.

---

## VERIFY

### בדיקות build

1. `cd frontend && npm run build` — עובר בלי warnings חדשים.
2. `grep -c "Search" frontend/src/components/FilterDrawer.js` — צריך להיות ≥2 (import + שימוש).

### בדיקות UI ב-BuildingDefectsPage

3. פתח drawer. Section "status" (4 אפשרויות) — **אין** search input.
4. Section "category" אם יש ≤7 — **אין** search. אם יש ≥8 — יש.
5. Section "unit" עם הרבה דירות (לרוב ≥8) — **יש** search input.
6. הקלד בשדה החיפוש → הרשימה מסתננת בזמן אמת.
7. הקלד משהו שלא קיים ("zzzzz") → "אין תוצאות מתאימות".
8. לחץ על ה-X הקטן שבקצה ה-input → החיפוש מתאפס, כל האפשרויות חוזרות.
9. בחר 3 דירות → כווץ את ה-section → בכותרת מופיע badge עם "3" (עיגול אמבר).
10. סגור drawer ופתח מחדש → שדה החיפוש ריק שוב.
11. Draft שומר על השפעת החיפוש: גם אחרי חיפוש + בחירה + ניקוי חיפוש → הבחירה נשמרת.

### בדיקות UI ב-ApartmentDashboardPage

12. Section "company" (בדרך כלל ≥8) → יש search.
13. בחר 2 חברות → Search אחריהן → הן עדיין מסומנות עם ✓ גם בתצוגת הסינון.

### בדיקות RTL/נגישות

14. ה-Search icon בצד ימין של ה-input, ה-X בצד שמאל — נכון ל-RTL.
15. Tab מה-input → מדלג לאפשרויות → לא נתקע.
16. VoiceOver על כפתור ה-X של החיפוש → מקריא "נקה חיפוש, button".

### בדיקות בבאנדל אחרי deploy

17. `grep "אין תוצאות מתאימות" בבאנדל FilterDrawer` — נמצא.
18. `grep "חפש..." בבאנדל` — נמצא.
19. `grep "נקה חיפוש" בבאנדל` — נמצא.
20. `main.js` hash השתנה.

---

## סיכום Checklist

- [ ] `Search` יובא מ-`lucide-react`
- [ ] `SEARCH_THRESHOLD = 8` מוגדר ברמת המודול
- [ ] `FilterSection` מקבל `searchQuery`, `onSearchChange`
- [ ] Badge של selected count בכותרת (עיגול אמבר)
- [ ] Search input מופיע רק כש-`options.length >= 8`
- [ ] X clear button בתוך ה-input
- [ ] Empty state "אין תוצאות מתאימות"
- [ ] `FilterDrawer` מנהל `sectionSearch` state
- [ ] search מתאפס כשה-drawer נפתח מחדש
- [ ] `npm run build` עובר
- [ ] בדיקות ידניות 3-16 עברו
