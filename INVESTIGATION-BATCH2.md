# 🔍 Investigation Report — Batch 2 (3 fixes)

**Date:** 2026-04-23
**For:** Zahi's review before writing spec for Replit

---

## Summary of findings

| Fix | Complexity | Surprise factor | Ready to spec? |
|---|---|---|---|
| #2 Default landing tab | **Trivial** (1 line) | ✅ no surprises | Yes |
| #3 Inline "הוסף חברה" modal | **Medium** (extract form to reusable) | ⚠️ inline in ProjectControlPage | Yes, after Zahi picks approach |
| #4 Inline "הוסף קבלן" modal | **Medium-Large** (no existing contractor form) | 🚨 MAJOR: no standalone contractor entity | Needs Zahi's decision |

---

## Fix #2 — Default landing tab = "מבנה"

### Verified location
**File:** `frontend/src/utils/navigation.js:3-15`

**Current code:**
```javascript
export function navigateToProject(project, navigate) {
  const id = project.id || project._id;
  const role = project.my_role;
  localStorage.setItem('lastProjectId', id);

  if (MANAGEMENT_ROLES.includes(role)) {
    navigate(`/projects/${id}/control`);   // ← THIS LINE
  } else if (role === 'contractor') {
    navigate('/projects');
  } else {
    navigate(`/projects/${id}/tasks`);
  }
}
```

### Why the current behavior is "not always structure"
**`ProjectControlPage.js:3164-3171`** — on mount:
1. Read URL `?workMode=...` → if set, use it
2. Else read `localStorage['brikops_workMode_${projectId}']` → if set (from user's last tab click), use it
3. Else default to `'structure'`

**The problem:** if a user previously clicked "ליקויים" tab in the project, localStorage saved `'defects'`. Next time they click that project from the list, they land on `/control` (no URL param) → localStorage wins → they see defects, not structure.

### The fix (1 line, surgical)

**File:** `frontend/src/utils/navigation.js:9`

```diff
  if (MANAGEMENT_ROLES.includes(role)) {
-   navigate(`/projects/${id}/control`);
+   navigate(`/projects/${id}/control?workMode=structure`);
```

That's the whole fix. The URL param wins over localStorage (verified in ProjectControlPage.js:3167), so every project click lands on structure tab regardless of past state. If the user navigates to another tab, localStorage still saves that tab's state, so deep-links from notifications still work correctly.

### Risks
- ✅ Non-management users (contractor, other) unchanged.
- ✅ Deep links from notifications (`/control?workMode=defects&statusChip=...`) unchanged — they set their own URL param.
- ✅ The "חזרה" button in `ProjectDashboardPage.js:254` already uses `?workMode=structure`, so consistent with existing pattern.
- ✅ No impact on `ProjectControlPage`'s internal tab-switching behavior.

### Ready to spec: **YES** — trivial.

---

## Fix #3 — Inline "הוסף חברה" modal in NewDefectModal

### Verified locations

**NewDefectModal.js — 4 navigate calls:**

| # | Line | Trigger condition |
|---|---|---|
| 1 | 809 | Empty state: no companies in the project at all → "+ הוסף חברה" |
| 2 | 822 | Category selected, no companies in that category → "+ הוסף חברה" |
| 3 | 849 | Small inline link "+ הוסף חברה" after category is picked but before company selection |
| 4 | 876 | Company selected, no contractors under it → "+ הוסף קבלן" |

All 4 currently call `navigate('/projects/${projectId}/control?tab=companies')`. Destroys all form state.

### The AddCompanyForm — inline in ProjectControlPage

**File:** `frontend/src/pages/ProjectControlPage.js:965-1160` (~195 lines)

⚠️ **NOT a separate component.** It's an inline JSX block inside `ProjectControlPage`. Uses `BottomSheetModal` wrapper. Fields:
- `name` (required)
- `trade` (optional, with suggestions dropdown searching existing companies)
- `contact_name` (optional)
- `contact_phone` (optional)
- "+ הוסף תחום חדש" inline flow for adding custom trades

**API call:** `projectCompanyService.create(projectId, payload)` at line 1073.

### The challenge
The current form lives inside ProjectControlPage and uses its local state + handlers. To reuse it inside NewDefectModal, we need to either:
- **Option A:** Extract `AddCompanyForm` as a standalone component (`frontend/src/components/AddCompanyForm.js`). ProjectControlPage and NewDefectModal both consume it. ~250 lines refactor.
- **Option B:** Create a simpler `QuickAddCompanyModal` in NewDefectModal — just name + trade + contact fields, no trade suggestions / no edit. ~60 lines new component. Doesn't reuse the full-featured form.
- **Option C:** Pass props/callbacks and duplicate the JSX. Ugly, not recommended.

### Risks

- ⚠️ **Option A** risk: touching ProjectControlPage to wire the new component = risk of regression on the companies management page. Mitigated by keeping props identical.
- ⚠️ **Option B** risk: two forms for same domain — users might notice feature gap (e.g., no suggestions dropdown). But acceptable for the defect-creation quick-add flow.
- ✅ Either option: need to refresh `projectCompanies` list in NewDefectModal after save + auto-select the newly created company. That's a small state update.
- ⚠️ **No existing nested-modal pattern in the codebase.** Would be the first. Need to carefully stack z-indexes: NewDefectModal is `z-[9998]`, nested modal needs `z-[9999]` or higher. Radix DialogPrimitive supports nested dialogs.

### My recommendation: **Option B** — build a slim `QuickAddCompanyModal`
Simpler, safer, no touching ProjectControlPage. Trade-off: duplicate form. Mitigation: keep it minimal (just the 4 core fields), skip suggestions, skip "add new trade" — if user needs those, they still have the original page.

### Open question for Zahi (before I spec)
A / B / C?

---

## Fix #4 — Inline "הוסף קבלן" modal + contractor↔company investigation

### 🚨 Major surprise: **there is no standalone "Contractor" entity or form**

**Contractors in BrikOps = project members with `role="contractor"`.**

- Stored in `project_memberships` collection (not a separate `contractors` collection)
- Added via `AddTeamMemberForm` inside the TeamTab of ProjectControlPage (lines 1217-1422)
- Fields: name, phone, role, trade_key, company_id
- API: `PUT /projects/:id/members/:uid/contractor-profile`

So when Zahi said "הוסף קבלן", technically what he means is "add a team member with role=contractor, trade_key=X, company_id=Y". Not a new entity — a new member.

### Contractor ↔ Company enforcement model (answer to Zahi's earlier question)

| Question | Answer |
|---|---|
| Is company classified by trade? | **Yes** — `company.trade` (free-form string up to 50 chars) |
| Is contractor classified by trade? | **Yes** — `project_membership.contractor_trade_key` (enum from `BUCKET_LABELS`) |
| Can electrician contractor be linked to a plumbing company? | **Yes** — no validation at member-company linking time |
| When does the trade mismatch matter? | **At task assignment time** — `_trades_match()` in `tasks_router.py:599` returns **409** if mismatch |
| Can user bypass the 409? | **Yes** — `force_category_change=true` changes the task's category to match the contractor's trade |

**So the current system is:** contractors CAN belong to any company (even a "wrong trade" one), but they can't be ASSIGNED tasks in categories they don't match, unless the task category is forced.

### Implications for Fix #4

When user opens NewDefectModal and gets to the "no contractors under this company" state (line 876), they click "+ הוסף קבלן". What should happen?

**Currently in the codebase:** the only way to add a contractor is via TeamTab's AddTeamMemberForm — a full form with role selection, company selection, trade selection, permission toggles. Overkill for the quick-add-while-logging-defect flow.

### Three options for the quick-add contractor flow

**Option B1 — Full AddTeamMemberForm extracted + reused**
Extract `AddTeamMemberForm` to standalone component. Use it inside NewDefectModal with defaults: role=contractor, company_id=<currently selected>, trade_key=<from selected category>. Large refactor (~400 lines touched).

**Option B2 — Slim QuickAddContractorModal (recommended)**
New small component that only captures:
- Name (required)
- Phone (required)
- Trade — auto-set from the category selected in NewDefectModal, not editable
- Company — auto-set from the company selected in NewDefectModal, not editable

Form submits to `PUT /projects/:id/members/:uid/contractor-profile` (or the relevant invite endpoint — need to verify which flow creates the contractor's user account too; there may be a register-by-phone step).

**Option B3 — Don't allow inline contractor add; instead show "use team page" tooltip**
Simplest. But Zahi explicitly wants this flow.

### 🚨 Complication: contractor account creation

Looking at `invites_router.py:19-99`, adding a contractor requires:
1. The contractor's user account to exist (probably via invite → register)
2. OR inviting them by phone → they receive an SMS → they register

**The TeamTab flow may have built-in invite-by-phone.** This means the "quick add" inline flow in NewDefectModal would need to replicate that invite pipeline. If we try to just "create a contractor" without inviting, we'd fail the API call.

**Need to verify** (before writing spec):
- Can a contractor be created immediately without SMS invite? (Probably not — user accounts need phone-verified login)
- Does AddTeamMemberForm auto-send an SMS invite on submit?

### Risks

- 🚨 **Contractor creation may require SMS invite flow** — can't just POST a name+phone.
- ⚠️ Trade enforcement on task assignment (409) means if the user inline-adds a contractor with `trade_key=electrical` to a `plumbing` category, they still can't assign the task. So the inline add must auto-set `trade_key` based on the defect's category.
- ⚠️ Duplicate contractor risk — if the user's phone is already in the system as a different role, we need to handle that. AddTeamMemberForm probably has logic for this.

### My recommendation

**Split Fix #4 into two sub-tasks:**

1. **#4a (in Batch 2):** Change the #876 navigate in NewDefectModal so that instead of `/control?tab=companies`, it goes to `/control?tab=team&role=contractor&prefill_company=<id>` (team tab, with filter and prefilled form). Still navigates away, still loses the defect form state — BUT at least lands on the right page directly, not the companies page which is wrong.

2. **#4b (defer to future batch):** Full inline "quick add contractor" modal with invite flow. Requires backend investigation on invite pipeline, coordination with how phone-invites work, SMS cost implications, etc.

OR alternatively: **Option B2 lite** — capture name + phone + role=contractor + trade + company, submit to a NEW backend endpoint that handles the invite transparently. Requires backend work.

Either way, #4 is NOT a simple 1-spec fix. Zahi needs to decide the scope.

### Open questions for Zahi (before I spec)

1. **#3 approach:** Option A (extract full AddCompanyForm), B (slim QuickAddCompanyModal), or C (duplicate)?
2. **#4 approach:**
   - **Simple option:** navigate to `/control?tab=team&prefill_role=contractor&prefill_company=<id>` — lands on the right page, but still loses the defect form state. Fast to implement.
   - **Full inline option:** build QuickAddContractorModal + figure out invite flow. Bigger scope, needs backend work, better UX.
   - **Defer:** skip #4 from Batch 2, include it in a later batch after proper scoping.

---

## Recommended Batch 2 scope (narrowed)

Based on findings, here's what I think ships together in Batch 2:

**Ready now (small, safe):**
1. **Fix #2** — 1-line change in navigation.js. Clear.
2. **Fix #3 Option B** — new QuickAddCompanyModal component, invoked from NewDefectModal's 3 navigate calls that go to companies tab. Clear, moderate size.

**Partial or deferred:**
3. **Fix #4** — depends on Zahi's decision:
   - If "simple option": 1-line change in NewDefectModal (fix the #876 navigate destination) + add "role=contractor" query param handling in ProjectControlPage's TeamTab. Small.
   - If "full inline option": separate investigation + spec. Defer from Batch 2.

### Investigation also revealed

**Companies in the system are already trade-classified.** This means the "שיוך קבלן" filtering in NewDefectModal (line 236-254) filters contractors by company_id only — NOT by trade. A contractor linked to a plumbing company via TeamTab can be in that company's contractor list even if their trade_key says "electrical". The task-assignment validation prevents actual task assignment but the dropdown will show them.

**This might be a Zahi-level UX concern** beyond Batch 2 scope. Flagging for awareness.

---

## Open questions for Zahi

**Answer these 2, I write the spec:**

1. **Fix #3 approach:** A (extract form, cleanest), B (slim QuickAddCompanyModal, smallest), C (duplicate, not recommended)?
2. **Fix #4 approach:** Simple (navigate-to-team-tab-with-prefill), Full (inline QuickAddContractorModal + invite flow), or Defer (skip Batch 2)?

Also nice-to-know (informational, not blocking Batch 2):

3. **Zahi awareness check:** Current system allows contractors to be linked to "wrong trade" companies. Is this a bug or a feature? (I think it's fine because the real enforcement happens at task assignment — but good to confirm your intent.)
