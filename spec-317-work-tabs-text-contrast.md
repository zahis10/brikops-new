# #317 — Improve Work Tabs Text Contrast (Inactive State)

## What & Why
The inactive work tabs (דשבורד, מבנה, בקרת ביצוע, מסירות, תוכניות) use `text-slate-400` which is too faint — especially on construction sites in direct sunlight. They look almost invisible next to the now-colorful management tabs below. Bumping to `text-slate-600` with a darker hover makes them feel clickable without competing with the active amber tab.

## Done looks like
- Inactive work tabs are clearly readable (darker gray, not washed out)
- Hover state darkens text further — feels interactive
- Active tab unchanged (amber background, white text)
- No other visual changes

## Out of scope
- Changing active tab color (amber)
- Adding background color or tint to work tabs
- Changing management tabs (bottom row) — they're done
- Changing tab labels, icons, order, or functionality
- Backend/API changes

## Tasks

### Task 1 — Darken inactive work tab text

**File:** `frontend/src/pages/ProjectControlPage.js` ~line 3356

**Current code:**
```jsx
className={`flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-lg text-sm font-semibold transition-all touch-manipulation ${isActive ? 'bg-amber-500 text-white shadow-md shadow-amber-500/25' : 'text-slate-400 hover:bg-slate-50'}`}
```

**Change the inactive state from:**
```
text-slate-400 hover:bg-slate-50
```

**To:**
```
text-slate-600 hover:text-slate-800 hover:bg-slate-50
```

That's it. One line, two classes.

```bash
grep -n "text-slate-400 hover:bg-slate-50" frontend/src/pages/ProjectControlPage.js
```

## Relevant files

| File | Line | Change |
|------|------|--------|
| `frontend/src/pages/ProjectControlPage.js` | ~3356 | `text-slate-400` → `text-slate-600 hover:text-slate-800` |

## DO NOT
- ❌ Don't change the active tab styling (`bg-amber-500 text-white shadow-md shadow-amber-500/25`)
- ❌ Don't add background colors or tints to inactive work tabs
- ❌ Don't touch the management tabs (MGMT_TABS / SECONDARY_TABS)
- ❌ Don't touch LoginPage.js
- ❌ Don't touch any other file

## VERIFY
1. Open `/projects/{id}/control` → inactive tabs (דשבורד, מבנה, etc.) are readable dark gray
2. Hover over inactive tab → text darkens further
3. Click a tab → amber active state still works, white text still works
4. Active tab stands out clearly against the darker inactive tabs
5. Check on mobile 375px — tabs still fit, no overflow
