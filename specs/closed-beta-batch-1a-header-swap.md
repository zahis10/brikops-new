# #410 — Closed-Beta Batch 1a — TaskDetailPage header side swap

## What & Why

Zahi reviewed the Batch 1 deploy and wants the header layout on TaskDetailPage reversed: **"BrikOps" text on the LEFT, "חזרה לרשימת ליקויים + →" on the RIGHT**. This is a simple JSX children swap — one commit, 3 lines moved.

No other changes, no logic changes, no new imports.

## Done looks like

On any defect detail page (`/tasks/:id` or equivalent contractor view):

- **Left side of header:** `BrikOps` text
- **Right side of header:** `→ חזרה לרשימת ליקויים` (arrow on the right of the text within the button — **keep the arrow placement from Batch 1**)

## Out of scope

- ❌ Any other header change (no logo image, no color change, no font change)
- ❌ Any change outside `TaskDetailPage.js`
- ❌ Any change to the back button's onClick logic or dynamic label function
- ❌ Any change to the `dir="rtl"` attribute (it stays)

## Tasks

### Single task — Swap JSX order of the two header children

**File:** `frontend/src/pages/TaskDetailPage.js`
**Line:** ~778-806 (the header block modified in #409)

**Find with:**
```bash
grep -n 'max-w-2xl mx-auto px-4 py-3 flex items-center justify-between' frontend/src/pages/TaskDetailPage.js
```

**Current state (after #409):**

```jsx
<div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between" dir="rtl">
  <div className="flex items-center gap-2">
    <span className="font-bold text-slate-800">BrikOps</span>
  </div>
  <button
    onClick={...}
    className="flex items-center gap-1 text-sm text-slate-500 hover:text-amber-600 transition-colors"
  >
    <ArrowRight className="w-4 h-4" />
    {(() => { /* dynamic label */ })()}
  </button>
</div>
```

**Change — swap the order of the two direct children** (BrikOps div and back button):

```jsx
<div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between" dir="rtl">
  <button
    onClick={...}
    className="flex items-center gap-1 text-sm text-slate-500 hover:text-amber-600 transition-colors"
  >
    <ArrowRight className="w-4 h-4" />
    {(() => { /* dynamic label */ })()}
  </button>
  <div className="flex items-center gap-2">
    <span className="font-bold text-slate-800">BrikOps</span>
  </div>
</div>
```

**Why this works:** In RTL flex, the first child renders at the start (right), the second child at the end (left). Before: BrikOps was first (right), button was second (left). After: button is first (right), BrikOps is second (left) — BUT Zahi wants BrikOps on LEFT and button on RIGHT. Wait…

**Re-verification.** In a `dir="rtl"` + `flex` container with `justify-between`:
- First JSX child → visual RIGHT
- Second JSX child → visual LEFT

So the fix above puts:
- Button (first child) → visual RIGHT ✓ (Zahi wants back link on right)
- BrikOps (second child) → visual LEFT ✓ (Zahi wants BrikOps on left)

**Inside the button**, `dir="rtl"` is inherited from the parent:
- `<ArrowRight />` (first child) → visual RIGHT of the button
- Text (second child) → visual LEFT of the button

Visual result: `→ חזרה לרשימת ליקויים` with arrow on the right of the text — exactly what Batch 1 established and what Zahi asked to keep.

## Architectural constraints

- Relative imports only
- No new deps, no new imports — just reordering existing JSX
- No backend changes — `git diff backend/` must be empty
- `dir="rtl"` on outer flex container stays (do not remove)

## DO NOT

- ❌ Do NOT remove `dir="rtl"` from the outer container — it's required for the arrow inside the button to stay on the right.
- ❌ Do NOT touch any file other than `TaskDetailPage.js`.
- ❌ Do NOT touch the button's onClick logic or the dynamic label IIFE `{(() => ...)()}`.
- ❌ Do NOT touch the `<ArrowRight />` component — keep it; do not swap for `<ArrowLeft />`.
- ❌ Do NOT touch anything in the page body below the header (the main content with its own `dir="rtl"`).
- ❌ Do NOT add new classes or change className strings on the button or BrikOps div.
- ❌ Do NOT add `gap-2` / `gap-4` changes — the existing `gap-1` on the button and `gap-2` on the BrikOps div stay as-is.

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) Scope — only one file touched:
git diff --stat | grep -v "frontend/src/pages/TaskDetailPage.js"
# Expected: empty (only TaskDetailPage.js modified).

# (b) dir="rtl" still present on the header:
grep -n 'max-w-2xl mx-auto px-4 py-3 flex items-center justify-between" dir="rtl"' frontend/src/pages/TaskDetailPage.js
# Expected: 1 hit.

# (c) BrikOps span still present (unchanged):
grep -n 'font-bold text-slate-800">BrikOps' frontend/src/pages/TaskDetailPage.js
# Expected: 1 hit.

# (d) ArrowRight still present (unchanged):
grep -n 'ArrowRight className="w-4 h-4"' frontend/src/pages/TaskDetailPage.js
# Expected: 1 hit (in the header) + possibly others elsewhere.

# (e) HardHat still NOT present (sanity check — was removed in #409):
grep -n "HardHat" frontend/src/pages/TaskDetailPage.js
# Expected: empty.

# (f) No backend changes:
git diff --stat backend/
# Expected: empty.
```

### 2. Build clean

```bash
cd frontend
npm run build
```
Expected: no new warnings.

### 3. Manual test

- Open any defect detail page in the browser (e.g. `/tasks/<any_task_id>`)
- **Header top row (RTL rendering):**
  - **LEFT side:** `BrikOps` text
  - **RIGHT side:** `→ חזרה לרשימת ליקויים` (arrow on the right, text to its left)
- Tap the back link → navigation still works correctly (no regression)
- The rest of the page below the header is unchanged

## Commit message (exactly)

```
fix(ui): Batch 1a — swap TaskDetailPage header sides

Swap the JSX order of the two direct children of the TaskDetailPage
header flex container so that in the RTL layout:
- BrikOps text ends up on the visual LEFT
- Back link + arrow ends up on the visual RIGHT

dir="rtl" stays on the container so the arrow inside the button
continues to render on the right of the Hebrew label (which Batch 1
established). No other changes.

One file, one JSX reorder, no logic changes.
```

## Deploy

```bash
./deploy.sh --prod
```

OTA only.

Send to Zahi after deploy:
- `git log -1 --stat` (expected: 1 file changed, ~10 lines moved)
- Unified diff
- Screenshot of the defect detail page showing BrikOps on LEFT, back link on RIGHT

## Definition of Done

- [ ] JSX children swapped — button is now first, BrikOps div is second
- [ ] `dir="rtl"` unchanged on the outer container
- [ ] `<ArrowRight />` still inside the button, still first child of the button
- [ ] All 6 grep checks from VERIFY §1 pass
- [ ] `git diff --stat` shows only `TaskDetailPage.js`
- [ ] Manual test confirms BrikOps on left, back link on right with arrow on right of text
- [ ] `./deploy.sh --prod` succeeded
- [ ] Screenshot sent to Zahi
