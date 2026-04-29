# ADR-003 — handover_router.py

**Status:** Accepted
**Date:** 2026-04-29
**File:** `backend/contractor_ops/handover_router.py` (2652 lines as of 2026-04-29)

## Why this exists

`handover_router.py` owns the **handover protocol** — the legal
document and walkthrough that gets signed when a unit changes hands
from the contractor to the buyer/tenant. Two protocol types: `initial`
(at delivery) and `final` (at one-year warranty checkpoint), with the
same template structure but different defect-tracking semantics.

The file is large for two reasons:

1. **The default template is embedded.** `HANDOVER_TEMPLATE` (line 27)
   is a 600-line literal Python dict listing every section (entrance,
   lobby, kitchen, bedrooms, bathrooms, balcony, ...) and every item
   per section (תvitch, ריצוף, צבע, חשמל, ...) with trade tags. This
   is the seed template every new org starts from; orgs can override
   sections, but the Hebrew names + trade tags + section ordering
   ship from here.

2. **The protocol lifecycle has many edges.** Draft → in_progress →
   partially_signed → signed, multiplied by the two types, multiplied
   by per-tenant signatures (some sections require both buyer and
   seller signatures), multiplied by per-section legal text editing
   (orgs can override the default text per section per protocol type).

Co-locating org-default fallback, template snapshotting, signature
state machines, and defect spawning in one file keeps the
**snapshot-on-create** invariant readable: when a protocol is created,
it captures a deep copy of the org's template + legal text at that
moment, so future template changes don't retroactively rewrite signed
documents. Splitting risks losing that invariant.

## Architectural decisions

- **Decision: snapshot the template at protocol-create time.** Why:
  signed protocols are legal documents. The text the buyer signed is
  the text that must appear on the printed PDF five years later — even
  if the org has since edited the template. Trade-off: every protocol
  duplicates the template structure (~10KB JSON), but storage cost is
  trivial vs the legal correctness benefit.
- **Decision: import `TERMINAL_TASK_STATUSES` from
  `contractor_ops.constants` (line 8).** Why: BATCH 5C found a local
  duplicate in this file that had drifted from the canonical set
  (missing `'cancelled'`) and was causing closed handover defects to
  appear as still-open in the per-building breakdown. Removed the
  local copy. **Never re-add — this is the canonical drift-hazard
  story documented in ADR-006.**
- **Decision: org legal text fallback (line 919-925).** When a
  protocol is created, look up the org's `default_handover_legal_text_<type>`
  field. If empty, fall back to `org.handover_legal_sections` (legacy
  per-section format from M5). Marked with `# TODO: Remove org fallback
  after migration verified` (line 926). The migration to consolidate
  legal text into `default_handover_legal_text_*` fields was completed
  Q1 2026 but the fallback wasn't removed because there's no audit
  showing zero orgs still rely on the legacy field.
- **Decision: defect spawning is co-located.** When an item in a
  protocol is marked failed (`status="defect"`), this router writes a
  task with `source: "handover_initial"` or `source: "handover_final"`
  to `db.tasks` directly. Why: the defect lifecycle is identical to a
  regular task once spawned, so no separate collection — but the
  source field lets the dashboard aggregation count handover defects
  separately (see line 2333-2337).
- **Decision: dashboard aggregation excludes terminal statuses
  inline.** Line 2336: `"status": {"$nin": ["closed", "approved",
  "cancelled"]}`. **Spec drift:** this `$nin` is missing `'done'`,
  which means done-but-not-approved handover defects show as still-open.
  Tracked as Task #27 / refactor-backlog item #9.

## Conventions used here

- All routes prefixed `/api`.
- Every endpoint validates `_check_project_access(user, project_id)`
  (write) or `_check_project_read_access(user, project_id)` (read).
- Legal section editing requires `_check_legal_edit_permission(user,
  project_id)` — narrower than project access (org_admin / owner /
  project_manager only).
- Signatures stored as base64 PNG in the protocol document (acceptable
  for the volume; would migrate to object storage if signature volume
  grows).
- All timestamps `_now()` UTC.
- Defect tasks created here use `source` field to mark provenance,
  letting the tasks router treat them uniformly.

## Natural seams (where to split if/when refactor happens)

- **`HANDOVER_TEMPLATE` literal** (lines 27-600+). Move to
  `backend/contractor_ops/handover_template_default.py` as a single
  exported `HANDOVER_TEMPLATE` constant. **~600 lines saved.**
- **Legal section endpoints** (CRUD on legal sections per protocol).
  Could split to `handover_legal_router.py`. **~400 lines saved.**
- **PDF generation handlers** — already partially extracted to
  `services/handover_pdf_service.py` (645 lines). Confirm the router
  here only orchestrates, doesn't duplicate.
- **Building / project breakdown aggregations** (the dashboard endpoint
  at ~2333). Could split to `handover_stats_router.py` or merge into
  `stats_router.py`. **~150 lines saved.**

## When to refactor

- **Trigger:** when the default template needs versioning (today it's
  one shape; the moment we add a v2 with different sections, the
  literal needs to become a dict-of-templates and the snapshotting
  needs a `template_version` field).
- **Pre-requisite 1:** force_close → aggregation → reopen regression
  tests (Task #28 — **BLOCKING LAUNCH** per BATCH 5C spec; refactor-
  backlog item #10). Without these, splitting risks breaking the
  defect spawning path silently.
- **Pre-requisite 2:** verify the org legal text migration is complete
  and remove the fallback at line 926.

## Recent changes

- 2026-04-29 (BATCH 5I): No change here. The handover back-button fix
  was in `HandoverOverviewPage.js` (frontend).
- 2026-04-22 (BATCH 5C): Removed local `TERMINAL_TASK_STATUSES`
  duplicate. Now imports from `contractor_ops.constants`. Surfaced
  the `$nin missing 'done'` bug at line 2336 — flagged as Task #27,
  not yet fixed.
- M6 (Q1 2026): Per-section legal text editing per protocol per type.
  Added the org fallback at line 919-925.
- M5 (Q4 2025): Initial handover protocol shipped. `HANDOVER_TEMPLATE`
  embedded.

## Refactor backlog items touching this file

- `#5` Audit for any other constants that might still shadow `constants.py`.
- `#9` Line 2336 — `$nin` missing `'done'` (Task #27 from 5C audit).
- `#10` `force_close → aggregation → reopen` regression tests
  (Task #28, **BLOCKING LAUNCH**).
- `#13` Remove org legal fallback at line 926 after migration verified.
- `#14` Extract `HANDOVER_TEMPLATE` literal to its own file.

See [`../refactor-backlog.md`](../refactor-backlog.md) for full details.
