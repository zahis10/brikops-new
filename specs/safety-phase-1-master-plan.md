# BrikOps Safety Phase 1 — Master Plan

**Owner:** Zahi · **Generated:** 2026-04-22 · **Status:** APPROVED — Part 1 in progress

Canonical tracker for the Safety + Work Diary Phase 1 rollout. This plan splits the 1,993-line monolithic spec (`safety-feature-phase-1-spec.md`) into 5 sequential, testable parts. Each part produces a self-contained deliverable that can be handed to Replit in a single session.

---

## 1. Context (refresh without reading the full spec)

### What we're building
A regulatory-grade Safety module for BrikOps that matches/exceeds Cemento's feature depth on:
- **Documentation** — rich records with photos, severity 1-3, status, assignee, reporter, attached PDFs
- **Tasks** — corrective actions with due dates, assignees, status transitions
- **Workforce** — workers + trainings with expiry tracking + periodic inspections
- **Incidents** — safety events with medical record attachments (7yr retention)
- **Regulatory output** — פנקס כללי PDF per תקנות הבטיחות בעבודה (עבודות בנייה), התשע"ט-2019 (9 sections)

### Why now
Cemento is the incumbent; Zahi's field research (317-page report dump) confirmed they set the bar for data richness. BrikOps v2 mockup stopped short on (1) filter depth, (2) export integration, (3) Safety Score signal, (4) visual parity.

### Key locked decisions (from Task #29)
1. Feature flag `ENABLE_SAFETY_MODULE` — default off, per-env opt-in
2. RBAC adds `safety_officer` + `safety_assistant` to `ManagementSubRole` enum
3. 7-year retention — soft delete with `deleted_at` / `retention_until`
4. Audit every write via `_audit()` → audit_events
5. Extends existing `project_companies` — NO new `contractor_companies` collection
6. All filters server-side, URL-backed via useSearchParams

---

## 2. Design system reference (CANONICAL)

**Every part MUST open with:**
> Follows `specs/safety-design-system.md`. Semantic color tokens (industrial grey `#64748B` + safety orange `#EA580C` WCAG-adjusted), Heebo w/ `tnum`, Executive Dashboard hero + Data-Dense tabs, 44pt touch targets, 4/8pt spacing. See §11 checklist before merge.

**Source files (do not duplicate content in per-part specs):**
- `specs/safety-design-system.md` — 12 sections, design tokens, component specs, a11y rules, pre-delivery checklist
- `future-features/safety-phase-1-mockup-v2.html` — full 8-section visual reference
- `future-features/safety-phase-1-mockup-v3.html` — updated hero with gauge+sparklines (deltas over v2)

---

## 3. Pre-flight approval checklist (status)

| Item | Description | Status |
|------|-------------|--------|
| A1 | Reuse `project_companies` + 6-field extension | ✅ Approved |
| A2 | Server-side 7-dim filter + URL-backed state | ✅ Approved |
| A3 | Extend `ProjectDataExportTab` + ws7/8/9 + פנקס כללי PDF | ✅ Approved |
| A4 | Safety Score on home screen, formula 40/25/20/15 | ✅ Approved |
| A5a | Task count 17 → 20 tasks | ✅ Approved |
| A5b | ETA 8 → 10 working days | ✅ Approved |
| DS | Design system reference doc | ✅ Complete |
| UX | ui-ux-pro-max validation run (8 domain queries) | ✅ Complete |

All 8 approvals in. Green light for implementation.

---

## 4. The 5 parts — overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Part 1 — FOUNDATION                             [~3h Replit]  [Day 1-2] │
│ ├── Feature flag + RBAC subroles                                        │
│ ├── Migration: extend project_companies (+6 fields)                     │
│ ├── 5 new collections: safety_workers / trainings / documents /         │
│ │   tasks / incidents                                                   │
│ ├── 7 new MongoDB indices for filters                                   │
│ └── Deliverable: GET /api/safety/healthz returns 200                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Part 2 — BACKEND CORE                           [~5h Replit]  [Day 2-4] │
│ ├── safety_router.py with all CRUD endpoints                            │
│ ├── SafetyFilters Pydantic model + MongoDB filter application           │
│ ├── RBAC enforcement via require_roles + sub-role check                 │
│ ├── _audit() on all writes                                              │
│ ├── Soft-delete with retention_until (7 years)                          │
│ └── Deliverable: Postman collection 100% green                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Part 3 — BACKEND ADVANCED                       [~5h Replit]  [Day 4-6] │
│ ├── GET /api/safety/{project_id}/score (40/25/20/15, 5-min cache)       │
│ ├── Extend export_router.py: ws7/ws8/ws9 behind feature flag            │
│ ├── safety_pdf.py — פנקס כללי PDF (9 sections, reportlab + noto-       │
│ │   sans-hebrew)                                                        │
│ ├── Filtered export endpoint                                            │
│ └── Deliverable: Excel + PDF reports generate correctly, manual review  │
├─────────────────────────────────────────────────────────────────────────┤
│ Part 4 — FRONTEND CORE                          [~6h Replit]  [Day 6-8] │
│ ├── SafetyScoreGauge.jsx (SVG, role=meter, a11y-compliant)              │
│ ├── SafetyKPICard.jsx × 6 (with sparklines + trend delta)               │
│ ├── SafetyTab.jsx container + useSearchParams tab routing               │
│ ├── 3 internal tabs:                                                    │
│ │   ├── DocumentsList.jsx (rich cards, Cemento parity)                  │
│ │   ├── TasksList.jsx (status + severity + due date)                    │
│ │   └── WorkforceList.jsx (expandable worker + trainings chips)         │
│ ├── Empty states per tab (required)                                     │
│ └── Deliverable: 3 tabs render real data end-to-end                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Part 5 — FRONTEND POLISH                        [~4h Replit]  [Day 8-10]│
│ ├── SafetyFilterSheet.jsx — 7 dimensions, URL-backed                    │
│ ├── Applied-filter chips row with clear-all                             │
│ ├── Bulk-actions bar on Workforce (multi-select + undo toast)           │
│ ├── Extend ProjectDataExportTab.js (+2 cards: פנקס כללי + filtered)   │
│ ├── Toast feedback for all async ops                                    │
│ └── Deliverable: feature-complete, ready for QA + deploy                │
└─────────────────────────────────────────────────────────────────────────┘
```

**Total:** ~23 hours Replit work · 10 working days · 20 sub-tasks.

---

## 5. File map — what each part touches

### Part 1 — Foundation
**Create:**
- `backend/migrations/2026_04_22_safety_foundation.py` — single idempotent migration

**Modify:**
- `backend/config.py` — add `ENABLE_SAFETY_MODULE` env flag
- `backend/models/user.py` — extend `ManagementSubRole` enum
- `backend/routes/safety_router.py` — NEW, stub with healthz only
- `backend/main.py` — register safety_router conditionally

**Collections created:**
- `safety_workers`
- `safety_trainings`
- `safety_documents`
- `safety_tasks`
- `safety_incidents`

**Collections modified:**
- `project_companies` — add `registry_number`, `is_placeholder`, `safety_contact_id`, `deleted_at`, `deleted_by`, `deletion_reason`, `retention_until`

### Part 2 — Backend Core
**Expand:** `backend/routes/safety_router.py`
**Create:** `backend/services/safety_service.py`, `backend/models/safety.py` (Pydantic schemas)

### Part 3 — Backend Advanced
**Modify:** `backend/routes/export_router.py` (add ws7/ws8/ws9)
**Create:** `backend/services/safety_score.py`, `backend/services/safety_pdf.py`

### Part 4 — Frontend Core
**Create:**
- `frontend/src/components/safety/SafetyScoreGauge.jsx`
- `frontend/src/components/safety/SafetyKPICard.jsx`
- `frontend/src/components/safety/SafetyTab.jsx`
- `frontend/src/components/safety/DocumentsList.jsx`
- `frontend/src/components/safety/TasksList.jsx`
- `frontend/src/components/safety/WorkforceList.jsx`
- `frontend/src/components/safety/EmptyState.jsx`
- `frontend/src/services/api/safetyService.js`

**Modify:**
- `frontend/src/pages/ProjectControlPage.js` — add safety tab to SECONDARY_TABS

### Part 5 — Frontend Polish
**Create:**
- `frontend/src/components/safety/SafetyFilterSheet.jsx`
- `frontend/src/components/safety/AppliedFiltersRow.jsx`
- `frontend/src/components/safety/BulkActionsBar.jsx`

**Modify:**
- `frontend/src/components/ProjectDataExportTab.js` — add 2 cards

---

## 6. Dependencies (strict ordering)

```
Part 1 ──> Part 2 ──> Part 3 ──> Part 4 ──> Part 5
  │          │          │          │
  │          │          │          └─ needs /api/safety/* from P2
  │          │          └─ needs score endpoint + export from P3
  │          └─ needs collections from P1
  └─ needs feature flag + RBAC from P1
```

**No skipping.** Each part ends with a testable deliverable — do NOT start Part N+1 until Part N is verified.

---

## 7. Native build triggers

Per `CLAUDE.md`: any change to `frontend/capacitor.config.json`, `frontend/ios/*`, `frontend/android/*`, or addition/removal of Capacitor plugin → must run `./ship.sh` after `./deploy.sh --prod`.

**Phase 1 scope check:** NO native changes expected. All parts are React + FastAPI. Safe for `./deploy.sh --prod` only + Capgo OTA.

If any part accidentally needs a native change (e.g., new Capacitor plugin for PDF generation on device) — flag immediately and escalate to Zahi.

---

## 8. Risk log

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MongoDB index creation locks hot collection | Low | High | Create indices with `background=True`; run during low-traffic window |
| Migration fails mid-way on `project_companies` extension | Medium | Medium | Migration is idempotent — check field presence before `$set`; can re-run safely |
| Noto Sans Hebrew font too large for backend container | Low | Low | Bundle only the subset we need for PDF (Hebrew + digits + Latin); <200KB |
| Feature flag leaks — safety endpoints accessible when OFF | Medium | High | Router registration itself conditional on env flag; 404 when disabled |
| RBAC sub-role check bypass | Medium | Critical | Centralize via new `require_safety_role()` helper; 100% endpoint coverage before Part 3 |
| PDF generation blocks request thread | High | Medium | Async via same pattern as existing `dataExportService.startExport` (polling) |
| 50+ worker lists janky | Medium | Low | Virtualize with react-window when count ≥50 (Part 4 acceptance criteria) |

---

## 9. Success criteria (Phase 1 exit)

Before marking Task #29 complete:

- [ ] All 20 sub-tasks across 5 parts shipped to prod
- [ ] `ENABLE_SAFETY_MODULE=true` toggled on for 1 beta project
- [ ] Safety Score renders correctly on that project's home screen
- [ ] 7-dim filter produces correct result set (spot-check 5 queries)
- [ ] פנקס כללי PDF generates with all 9 sections populated
- [ ] Excel Full Export includes ws7/ws8/ws9 with correct data
- [ ] Zero P0/P1 bugs from QA pass
- [ ] SOC2 audit trail: every write has `_audit()` entry (spot-check 20 records)
- [ ] Lighthouse a11y score ≥95 on Safety home screen
- [ ] Beta user feedback captured (1 safety officer + 1 site manager)

---

## 10. Session continuity protocol

If a future Claude session picks up this work mid-stream:
1. **Read first:** this file + `specs/safety-design-system.md`
2. **Check:** `TaskList` for in_progress safety tasks (currently tracked as #33-#37)
3. **Read last completed part spec:** only the current part's detail is needed, not all 5
4. **Verify state:** run the "Deliverable" test from the last completed part before proceeding

Do NOT re-read the 1,993-line monolithic spec — it's been split. This master plan + per-part specs ARE the canonical source.

---

## 11. File ownership

| File | Purpose | Editable by |
|------|---------|-------------|
| `specs/safety-phase-1-master-plan.md` (this) | Overall tracker, status, file map | Zahi + Claude (update on progress) |
| `specs/safety-design-system.md` | Canonical design rules | Claude (additive only — approved changes) |
| `specs/safety-phase-1-part-{1-5}-*.md` | Per-part Replit-ready specs | Claude (generate) → Zahi (paste to Replit) |
| `specs/safety-feature-phase-1-spec.md` | Original 1,993-line monolithic spec | FROZEN — reference only, do not edit |
| `future-features/safety-phase-1-mockup-v{2,3}.html` | Visual reference | Claude (updates on design evolution) |

---

**Next up:** Part 1 — Foundation spec, hand-off format (file paths + line numbers + DO NOT + VERIFY).
