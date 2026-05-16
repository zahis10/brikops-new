# BrikOps — Codebase Documentation & Refactor Plan

**Owner:** Zahi
**Status:** Planning phase — to be executed across multiple batches over 3-6 months
**Priority:** MEDIUM — runs alongside feature work, not in place of it
**Last updated:** 2026-04-28

---

## Why this plan exists

The codebase works. Security audits passed (S1-S7). Billing flows are live.
41 internal testers are using it.

But:
- Several files are 1500-3680 lines
- No architecture documentation explains WHY the code looks this way
- No refactor backlog tracks known cleanup opportunities
- Future developers (paid hires post-revenue) will face onboarding friction

**This plan addresses documentation FIRST, refactor SECOND, in that order.**

---

## Guiding principles

1. **No "refactor sprint."** Every change happens inside a feature/bug batch
   that's already touching the same file. The Boy Scout Rule: leave the
   campsite cleaner than you found it.

2. **Documentation before refactor.** A 3000-line file with a clear ADR is
   easier to onboard onto than a 500-line file that's been refactored
   into 6 files with no explanation.

3. **Data, not feeling.** Refactor only when there's evidence: bugs
   recurring in the same area, batches taking 3x longer, features blocked
   by tight coupling. NOT because the file "feels big."

4. **Tests > refactor.** Every refactor needs a test as a safety net.
   No tests = no refactor.

5. **Pre-launch focus.** Until BrikOps has 10+ paying customers, feature
   work and customer acquisition take priority. Documentation can run
   in parallel; refactor cannot.

---

## Phase 1 — Documentation (Weeks 1-3, runs in parallel with feature batches)

### Phase 1A — Initial documentation pass (one-time, ~3-4 hours)

Create the following files. Cowork can do this in a single batch labeled
"docs: architecture decision records + refactor backlog."

#### File 1: `docs/architecture/README.md`

Purpose: Index for all architecture documentation.

Contents:
- Top 10 largest files with one-line description of what each does
- Link to each detailed ADR (one per major file/module)
- Quick conventions list (status fields, IDs, timestamps, Hebrew handling)
- Anti-patterns to avoid (with reasons)
- "When in doubt" guidance

#### File 2: `docs/architecture/adr-001-project-control-page.md`

Subject: Why ProjectControlPage.js is 3680 lines.

Should cover:
- The 7-tab architecture (Overview, Tasks, Companies, Team, Plans, Settings, Handover)
- Why state is lifted to parent (cross-tab dependencies)
- Why splitting to separate routes was rejected
- Where the natural seams are if splitting becomes necessary
- History of changes (Batch 5B lifted Companies state, etc.)

#### File 3: `docs/architecture/adr-002-billing-router.md`

Subject: Why `billing_router.py` is 2000+ lines and how it's organized.

Should cover:
- Why billing endpoints are co-located (shared transaction logic, PayPlus
  state management, GI invoice creation)
- The PayPlus integration constraints (no /Check endpoint, fragile webhooks)
- Why GI failures are caught and never block subscription activation
- Webhook idempotency strategy (S5a + S7-C)
- Auth model: `check_org_billing_role` + super_admin bypass

#### File 4: `docs/architecture/adr-003-tasks-router.md`

Subject: Task lifecycle, status semantics, and why two close paths exist.

Should cover:
- The full status state machine (open → assigned → in_progress → ...)
- Why force_close writes 'approved' and approve_proof writes 'closed'
  (the audit trail distinction)
- `STATUS_BUCKET_EXPANSION` (added in 5F) — single source of truth
- `handled_statuses` vs `open_statuses` (the dashboard KPI logic at line 363)
- The bucket-drift guard test (added 5F) and why it's launch-blocking

#### File 5: `docs/architecture/adr-004-status-system.md`

Subject: How status fields work everywhere.

Should cover:
- All status values (active, expired, cancelled, approved, closed, etc.)
- Where each is written (which endpoint sets which)
- Where each is read (display, aggregation, paywall)
- The 5C/5F lesson: keep DB values distinct, unify display
- Forbidden patterns (status comparisons in frontend without bucket logic)

#### File 6: `docs/architecture/adr-005-i18n.md`

Subject: How Hebrew/English/Arabic/Chinese work.

Should cover:
- Module-level `t(section, key)` pattern
- `he.json` as source of truth
- PM/admin forced Hebrew (regardless of user preference)
- RTL handling for all 4 languages
- Where to add new strings (always section-scoped)

#### File 7: `docs/refactor-backlog.md`

Purpose: Living document of known refactor opportunities.

Format: Each item should specify:
- File and line range affected
- What's wrong (data, not feeling)
- Proposed fix
- Estimated time
- "Fold into batch X" suggestion (when next-touched)

Initial items (Cowork should add these based on its codebase knowledge):
- Lift remaining duplicate states in ProjectControlPage (Batch 5B did Companies; what else?)
- Move `STATUS_BUCKET_EXPANSION` + `handled_statuses` + `open_statuses` to `constants.py`
- Extract handover endpoints from `billing_router.py` (if applicable)
- Split frontend STATUS map duplication (5 pages have similar logic)
- Audit the deferred Bug #3 (UserDrawer dropdown escape) — file as proper task
- Any TODO/FIXME comments older than 30 days

#### File 8: `CLAUDE.md` (project root)

Purpose: Standing instructions for Cowork on every batch.

Contents:
- Read `docs/architecture/README.md` before any spec implementation
- STEP 0 mandatory pre-flight grep audit (existing rule)
- When touching a file in `refactor-backlog.md`, propose folding the refactor
- Anti-patterns Zahi has flagged repeatedly (e.g., never use
  `WebkitOverflowScrolling: 'touch'`)
- Where to find existing helpers (e.g., `check_org_billing_role`,
  `send_invoice_email`) BEFORE building new ones
- The Hebrew commit message format Zahi prefers
- The standing rule: agent never runs `./deploy.sh`

---

### Phase 1B — Spec for Cowork

```
SPEC: docs(architecture): ADR + refactor backlog + CLAUDE.md

Scope:
- 8 new files in /docs/architecture/, /docs/, and project root
- No code changes, no logic changes
- Read-only investigation of the existing codebase

STEP 0 — Pre-flight investigation:
1. Run `find . -name "*.py" -not -path "./node_modules/*" | xargs wc -l | sort -n | tail -20`
   to identify the actual top 20 largest backend files.
2. Same for frontend: `find frontend/src -name "*.js" -o -name "*.jsx" | xargs wc -l | sort -n | tail -20`
3. Identify files >800 lines as ADR candidates.
4. For each ADR candidate, read the file once and summarize its
   responsibility in one paragraph. Document in review.txt.

Steps:
1. Run STEP 0 investigation, output findings.
2. Create docs/architecture/README.md with the index.
3. Create one ADR per major file (target: 5-8 ADRs total). Each ADR
   should be 200-400 lines, NOT exhaustive — capture the WHY only.
4. Scan for TODO / FIXME / XXX comments and add them to
   docs/refactor-backlog.md.
5. Create CLAUDE.md with standing instructions.
6. Generate review.txt summarizing what was created and any patterns
   Cowork noticed during investigation that Zahi should be aware of.

VERIFY:
- All 8 files created.
- Each ADR has: title, "Why this exists" section, "Conventions" section,
  "When to refactor" section.
- refactor-backlog.md has at least 10 actionable items.
- CLAUDE.md fits in <200 lines (must be readable quickly).

Out of scope:
- Any code changes
- Refactoring any existing file
- Adding new tests
- Changing any UI

Estimated: 3-4 hours.
```

---

## Phase 2 — Test coverage (Weeks 4-8, parallel to feature work)

Why: Refactor without tests is reckless. Build the safety net first.

### Phase 2A — Identify the 5 critical flows

These are the flows that, if broken, kill the product:

1. **User signup + first project setup**
   - Register → email verify → create org → create project
   - 3-5 integration tests covering happy path + edge cases

2. **Billing checkout (Founder + Standard)**
   - Pick plan → PayPlus checkout → webhook → subscription activated
   - 5+ tests covering all plan types, GI invoice creation, paid_until
     calculation, the founder ₪499 fix from this batch

3. **Defect lifecycle (create → assign → close)**
   - Two close paths: contractor-proof flow + force-close flow
   - 5+ tests covering status transitions, audit fields, KPI aggregation

4. **Handover protocol generation**
   - 90% completion gate, signing flow, PDF generation
   - 3-5 tests covering the complete flow + signing edge cases

5. **Subscription cancellation (when deployed)**
   - Cancel → renewal cron skip → expires_at → paywall blocks
   - 8+ tests already in the cancellation v1 spec; ensure they ship

### Phase 2B — Spec for Cowork (one batch per flow)

Each flow gets its own batch. Sample spec for flow #3:

```
SPEC: test(defects): integration tests for defect lifecycle

Scope:
- New file: backend/tests/test_defect_lifecycle.py
- Tests covering: create, assign, in_progress, close (both paths), reopen
- No production code changes

Steps:
1. Read existing test_billing.py and test_contractor_hardening.py to match
   their style (sync test functions, asyncio.run, MongoClient setup).
2. Write 8 tests:
   - test_create_defect_as_pm
   - test_assign_to_contractor
   - test_contractor_marks_in_progress
   - test_contractor_uploads_proof
   - test_pm_approves_proof_writes_status_closed
   - test_pm_force_closes_writes_status_approved
   - test_force_closed_appears_in_closed_kpi (the regression test from 5F)
   - test_reopen_from_either_closed_or_approved (S6 fix verification)
3. Run them: pytest backend/tests/test_defect_lifecycle.py -v
4. All must PASS.

VERIFY:
- 8 tests, all pass
- Each test independently runnable (no test depends on another)
- Setup uses fresh test org per test (teardown clean)

Out of scope:
- Refactoring tasks_router.py
- Changing status field semantics
- UI tests

Estimated: 4-6 hours.
```

5 flows × 4-6 hours = ~25-30 hours of test work, spread across 2-4 weeks.

---

## Phase 3 — Targeted refactor (Months 3-6, ONLY after 5+ paying customers)

Trigger conditions (don't start until at least 3 of 4 are true):

- 5+ paying customers
- Phase 1 docs complete and read by Zahi
- Phase 2 critical flow tests all green
- Specific pain point identified with data (e.g., "60% of bugs in last
  month came from billing_router.py")

### Phase 3A — Pick ONE refactor target

Don't refactor everything. Pick the file with the most pain.

Candidates (rank by data, not feeling):
- ProjectControlPage.js (3680 lines) — if user-facing bugs cluster here
- billing_router.py (2000+ lines) — if billing changes break unrelated things
- tasks_router.py (1500+ lines) — if status logic causes recurring bugs

### Phase 3B — Refactor methodology

For the chosen file:

1. **Add comprehensive tests first.** Don't touch the file until you have
   tests for every public function/endpoint it exposes.

2. **Refactor in small commits.** Each commit:
   - Touches ONE concern (e.g., "extract X helper")
   - Keeps all tests green
   - Can be deployed independently
   - Can be reverted independently

3. **Don't change behavior.** Refactor = move code without changing what
   it does. Bug fixes go in separate batches.

4. **Update ADR after.** Document what changed and why.

5. **Run for 1 week before next refactor.** Make sure nothing broke
   silently before moving to the next file.

### Phase 3C — Spec template (use when ready)

```
SPEC: refactor(<file>): extract <concern> to <new location>

Pre-requisites:
- Phase 1 docs complete
- Phase 2 tests covering this area: passing
- ADR for this file: written
- Issue tracker has data showing pain point

STEP 0 — Pre-flight:
1. Confirm tests for this file exist and pass:
   pytest <test_file> -v
2. Read the ADR for this file
3. Identify the EXACT scope of this refactor (1 concern, not many)

Steps:
1. Extract the chosen concern to a new file
2. Update imports in the original
3. Run tests after EACH extraction step (not just at the end)
4. Generate diff for review

VERIFY:
- All tests still pass
- File line count reduced by X (measure)
- No new circular imports
- ADR updated with the change

Out of scope:
- Any other refactor in this file
- Any behavior changes
- Any new features

Estimated: <hours per concern>
```

---

## Phase 4 — Hire (when ready)

Trigger conditions (all must be true):

- 50+ paying customers OR ₪25k MRR
- Phase 1, 2, 3 complete on at least the top-3 files
- Clear product roadmap with backlog of features Cowork can't build alone
- Burn-out signs in Zahi (e.g., spec writing taking too long, decisions
  delayed, customer support eating dev time)

### Onboarding spec for new developer

Day 1:
1. Read docs/architecture/README.md (30 min)
2. Read all ADRs (1 hour)
3. Read CLAUDE.md (10 min)
4. Run all tests locally (1 hour, including setup)
5. Pick first task from refactor-backlog.md (the smallest one)

Week 1:
- Pair with Zahi on 2-3 batches to learn the workflow
- Add their first ADR for a file they touched
- Ship one bug fix to staging

Month 1:
- Own one module end-to-end (e.g., handover flow, billing flow)
- Lead one refactor batch
- Mentor Cowork by improving CLAUDE.md based on their experience

---

## Timeline summary

| Phase | When | Effort | Outcome |
|-------|------|--------|---------|
| 1A — Docs creation | Week 1 | 3-4 hours (one batch) | All ADRs + backlog + CLAUDE.md |
| 1B — Docs maintenance | Ongoing | 15 min/batch | ADRs stay current |
| 2 — Critical flow tests | Weeks 4-8 | 25-30 hours total | Safety net for refactor |
| 3 — Targeted refactor | Months 3-6 | 20-40 hours | Top-3 files cleaner |
| 4 — Hire | Months 6-12 | N/A | Senior dev onboarded |

---

## Anti-patterns to avoid

1. **"Let's clean up the codebase this weekend."** Doesn't work. The
   weekend ends with half-finished refactor and broken staging.
   Refactor in batches, not sprints.

2. **"Let's rewrite this in TypeScript / framework X."** Rewrite is
   almost always a mistake for working software. Migrate file-by-file
   if at all.

3. **"Let's add types to all 200 files."** Premature. Add types to the
   5 critical flow files. Stop.

4. **"Let's hire a contractor to refactor for us."** Without docs,
   contractor will be slow and produce something that doesn't match
   product intent. Wait for Phase 4.

5. **"Let's wait until we have time to do this properly."** You'll
   never have time. Documentation work happens in parallel, not in
   place of, feature work.

---

## What this plan is NOT

- A pre-launch blocker. Soft launch happens BEFORE Phase 3 starts.
- An excuse to delay features. Phase 1A is one batch, not a project.
- A contract with Cowork. Cowork is the implementation tool; YOU are
  the architect making decisions.
- A guarantee. If post-launch you find different pain points than
  predicted, this plan adjusts.

---

## First action

**This week:** Send the Phase 1B spec to Cowork. Get the 8 documentation
files created. Read them. Sleep better at night knowing the debt is
documented even if not paid.

**Next month:** Start Phase 2 (tests). Don't touch refactor yet.

**Q3 2026:** Re-evaluate. If you have 5+ paying customers and tests
are green, move to Phase 3. If not, continue feature work and let the
plan wait.
