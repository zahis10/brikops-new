# #413 — Closed-Beta Batch 2a Patch — Fix nested Dialog dismiss

## What & Why

**Critical production bug** introduced in #410 (Batch 2a deploy). Clicking "+ הוסף חברה" in NewDefectModal **closes the defect modal** entirely instead of opening the inline `QuickAddCompanyModal`. Users lose all typed defect content and are left on the defects list page — **worse than the original behavior** (which at least navigated them somewhere).

### Root cause

`NewDefectModal` is rendered as a non-modal Radix Dialog:
```jsx
// frontend/src/components/NewDefectModal.js:650
<DialogPrimitive.Root modal={false} open={true} onOpenChange={(open) => {
  if (!open && (pendingFile || annotatingIndex !== null)) return;
  if (!open) handleClose();   // ← closes parent via onClose()
}}>
```

The Content at line 656-659 only guards against `onPointerDownOutside`:
```jsx
<DialogPrimitive.Content
  className="..."
  onPointerDownOutside={(e) => e.preventDefault()}
>
```

When `QuickAddCompanyModal` opens (default `modal={true}` — Radix default), focus transfers into the nested dialog. Radix fires `onFocusOutside` on the parent (**not prevented**), which triggers `onOpenChange(false)` → `handleClose()` → `onClose()` → parent unmounts NewDefectModal → child `QuickAddCompanyModal` also unmounts (it's a child in the React tree) → user sees the underlying page.

### The fix

Add `onInteractOutside={(e) => e.preventDefault()}` to the same Content. `onInteractOutside` is Radix's catch-all for pointer AND focus dismiss events. Preventing it blocks the nested dialog's focus transfer from closing the parent.

**Scope: 1 file, 1 line added.**

## Done looks like

1. Open NewDefectModal on a project with no companies (or filtered by a category with no matches).
2. Fill in title "בדיקה 1" + description + pick a location.
3. Click "+ הוסף חברה".
4. ✅ `QuickAddCompanyModal` opens **on top of** NewDefectModal.
5. ✅ NewDefectModal stays mounted behind the nested modal (still visible, still holds all typed content).
6. Fill the quick-add form → save.
7. ✅ Nested modal closes, NewDefectModal still there with title + description + location intact, new company selected in dropdown.
8. Regression: ESC key / X button / ביטול button on NewDefectModal all still close the modal properly (they call `onClose()` directly, bypassing Radix's dismiss events).

## Out of scope

- ❌ Any change to `QuickAddCompanyModal.js` — it's fine.
- ❌ Any change to `NewDefectModal.js` beyond the one line.
- ❌ Any change to the 3 onClick handlers from #410 — they're correct.
- ❌ Any change to `modal={false}` — keep it as-is (other flows may depend on it).
- ❌ Any change to backend.
- ❌ Any new deps.

## Tasks

### Task 1 — Add `onInteractOutside` guard to NewDefectModal

**File:** `frontend/src/components/NewDefectModal.js`
**Line:** 656-659 (find with `grep -n "onPointerDownOutside" frontend/src/components/NewDefectModal.js`)

**Change:**
```diff
  <DialogPrimitive.Content
    className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 outline-none"
    onPointerDownOutside={(e) => e.preventDefault()}
+   onInteractOutside={(e) => e.preventDefault()}
  >
```

**Why:** `onInteractOutside` is Radix's catch-all dismiss event (pointer AND focus). Preventing it blocks the nested QuickAddCompanyModal's focus transfer from closing the parent.

**Why this is safe:** NewDefectModal is only closed via explicit paths:
- X button at top (line ~665, calls `onClose()` directly)
- "ביטול" button at bottom (line ~975, calls `handleClose()` directly)
- ESC key (Radix's `onEscapeKeyDown` — not affected by this change)

Radix's auto-dismiss on interaction-outside was never the intended closure mechanism — it was an unintended side effect that broke when we added a nested modal. Preventing it is the correct behavior.

## DO NOT

- ❌ Do NOT change `modal={false}` to `modal={true}` on the parent Dialog. Other behaviors (photo annotation overlay, pendingFile flow) may depend on the non-modal behavior.
- ❌ Do NOT touch `QuickAddCompanyModal.js`.
- ❌ Do NOT add other event prevents (e.g., `onEscapeKeyDown`) — ESC should still work to close the modal.
- ❌ Do NOT change the `onPointerDownOutside` line — keep it, just add `onInteractOutside` after it.
- ❌ Do NOT change any other file.

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) Only one file changed:
git diff --stat | grep -v "frontend/src/components/NewDefectModal.js"
# Expected: empty.

# (b) The new guard is present:
grep -n "onInteractOutside" frontend/src/components/NewDefectModal.js
# Expected: 1 hit.

# (c) The old guard is still present:
grep -n "onPointerDownOutside" frontend/src/components/NewDefectModal.js
# Expected: 1 hit.

# (d) Backend untouched:
git diff --stat backend/
# Expected: empty.

# (e) No package changes:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (f) QuickAddCompanyModal.js not touched:
git diff --stat frontend/src/components/QuickAddCompanyModal.js
# Expected: empty.
```

### 2. Build clean

```bash
cd frontend
npm run build
```
Expected: no new warnings.

### 3. Manual tests

After deploy + hard refresh:

**Test A — Main fix:**
1. Open NewDefectModal (click "+ פתח ליקוי" on any unit)
2. Fill title "בדיקה 2" + category=מיזוג + location
3. Click "+ הוסף חברה" (the button will appear since no company matches מיזוג)
4. ✅ Quick-add modal opens on top. NewDefectModal visible behind it.
5. Type name "חברת בדיקה מיזוג 1", pick trade=מיזוג, save.
6. ✅ Quick-add closes, NewDefectModal still there with "בדיקה 2" + מיזוג intact, new company selected.
7. Submit the defect.
8. ✅ Defect saves normally.

**Test B — ESC regression:**
1. Open NewDefectModal, don't fill anything.
2. Press ESC.
3. ✅ NewDefectModal closes (normal behavior preserved).

**Test C — Cancel nested:**
1. Open NewDefectModal, fill title.
2. Click "+ הוסף חברה" → quick-add opens.
3. Click ביטול (or X) inside quick-add.
4. ✅ Quick-add closes, NewDefectModal still there with title intact.

**Test D — Outside click still doesn't close parent:**
1. Open NewDefectModal.
2. Click on the dark area outside the modal.
3. ✅ NewDefectModal does NOT close (existing behavior via `onPointerDownOutside`).

## Commit message (exactly)

```
fix(ui): NewDefectModal stays open when nested QuickAddCompanyModal opens

Root cause: NewDefectModal uses Radix Dialog with modal={false}, which
makes the DismissableLayer fire onFocusOutside when focus transfers
into a nested modal. The parent's Content only guarded against
onPointerDownOutside, not the broader onInteractOutside, so opening
QuickAddCompanyModal (default modal={true}) caused focus to leave the
parent Dialog's layer → parent's onOpenChange(false) fired →
handleClose() → parent unmounted entirely, taking the nested modal
with it.

Fix: add onInteractOutside={(e) => e.preventDefault()} to
NewDefectModal's DialogPrimitive.Content. This catch-all prevents
pointer AND focus dismiss events from closing the parent when a
nested Dialog opens. Safe because NewDefectModal closes via explicit
paths only (X button, ביטול button, ESC — all unaffected).

One-line addition. QuickAddCompanyModal unchanged. No backend changes.
No new deps.
```

## Deploy

```bash
./deploy.sh --prod
```

OTA only.

**Before declaring fix complete, Zahi should:**
1. Hard refresh browser (Cmd+Shift+R) OR close/reopen the native app.
2. Run Test A above end-to-end.
3. If Test A passes → fix verified. If it fails → send a console log screenshot.

## Definition of Done

- [ ] One-line change applied: `onInteractOutside={(e) => e.preventDefault()}` added to NewDefectModal's Content
- [ ] All 6 grep checks from VERIFY §1 pass
- [ ] `npm run build` clean
- [ ] Test A passes (main fix — quick-add opens, parent stays, save works)
- [ ] Test B passes (ESC still closes — regression check)
- [ ] Test C passes (cancel nested modal — parent stays)
- [ ] Test D passes (click outside parent — parent still doesn't close — regression check)
- [ ] `./deploy.sh --prod` succeeded
