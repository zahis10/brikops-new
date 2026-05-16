# 🦺 BrikOps Safety Module — Status & Roadmap

> **⚠️ קלוד — אם אני מבקש ממך לעבוד על בטיחות, תקרא את הקובץ הזה קודם.**
>
> **Last updated:** 2026-04-23
> **Status:** Phase 1 shipped. Gap to Cemento = ~75%. Before Phase 2: closed-beta fixes.

---

## TL;DR for any future Claude session

**Don't ask Zahi design questions about safety without reading:**
1. This file (overview + current state)
2. `future-features/safety-and-worklog-concept.md` (850+ lines — full concept, 6 locked decisions)
3. `future-features/HANDOFF-safety-feature-2026-04-22.md` (handoff summary)
4. `specs/safety-phase-1-master-plan.md` (what was actually built)
5. `future-features/cemento-research/CEMENTO_ANALYSIS.md` (competitor analysis)
6. `future-features/safety-phase-1-mockup-v3.html` (visual reference)

**The decisions are DONE. Don't re-litigate. Use `brikops-spec-writer` skill to write the next spec.**

---

## Where we are today (Phase 1 = ~25% of Cemento parity)

### ✅ Shipped to production (behind `ENABLE_SAFETY_MODULE` flag)

**Backend** (`backend/contractor_ops/safety_router.py`, `backend/services/safety_pdf.py`):
- 5 collections with 7-year retention + soft delete:
  - `safety_workers` (with SHA-256 hashed id_number, never exposed)
  - `safety_trainings`
  - `safety_documents` (defects + documentation **混ed together** — should be split per concept §7)
  - `safety_tasks` (corrective actions)
  - `safety_incidents`
- 25 CRUD endpoints + 7-dim filter on documents
- Safety Score (0-100) with weighted formulas: docs(40)+tasks(25)+training(20)+incidents(15), 5-min cache
- 3 exports: full Excel (3 sheets), filtered Excel, פנקס כללי PDF (9 sections, Hebrew RTL)
- `_audit()` on every write, `ENABLE_SAFETY_MODULE` flag, RBAC via `SAFETY_WRITERS = ("project_manager", "management_team")`

**Frontend** (`frontend/src/pages/SafetyHomePage.js`, `frontend/src/components/safety/*`):
- Home page with score gauge + 6 KPI cards + 3 tabs (ליקויים / משימות / עובדים)
- Top-nav tab "בטיחות" at position 6 in ProjectControlPage
- 7-dim filter drawer (documents tab only)
- Bulk select + bulk delete (documents tab only)
- Export dropdown menu with 3 options
- Hebrew RTL, mobile-first, shadcn/ui
- Route gated to `['project_manager', 'management_team', 'owner', 'admin']`

### ❌ Missing (the gap — why closed-beta users say "there's nothing to do here")

| Feature | Why it matters | Phase |
|---|---|---|
| **Safety Tours / Walkarounds** (סיורי בטיחות) | THE central daily workflow in Cemento — morning/evening assistant reports + safety officer report with checklist + linked defects/documentation + signature | **Phase 2** |
| **Create/Edit modals** for all 5 entities | Without these the page is read-only. Users can't add workers, log defects, record trainings, etc. | **Phase 2** |
| **Documentation as separate entity** from Defects | Cemento separates observational documentation (110 items in test project) from actionable defects (11). Concept decision §7. Currently混ed in `safety_documents`. | **Phase 2** |
| **Equipment catalog** (כשירות ציוד) | 10 categories × N instances × multiple inspection types with expiry dates. Renewal flow with signed document upload. 41 items in real test project. | **Phase 3** |
| **Training renewal flow with signed docs** | "חידוש" button → either sign-in-app via canvas OR upload scanned PDF. Currently trainings are static records. | **Phase 3** |
| **Identification Records** (רישומי זיהוי) | Formal regulatory company data for פנקס כללי §1: שם היזם, מספר בפנקס הקבלנים, כתובת משרד, מנהלי חברה. Currently tealims this section. | **Phase 4** |
| **Penalty-based score** with aging | Cemento shows `N workers × 10 = 910 pts + N defects × days_overdue × multiplier`. No cap. Day-aging. Much more informative than our 0-100. | **Phase 4** |

---

## Roadmap to Cemento parity (and beyond)

| Phase | Scope | Est. effort | Parity % after |
|---|---|---|---|
| **Phase 1** (DONE) | DB + backend CRUD + read-only UI + score + PDF exports | ~10 working days | 25% |
| **Closed-beta fixes** (next) | User-reported issues from real usage | TBD after Zahi lists them | — |
| **Phase 2** | Tours/walkarounds + Create/Edit modals + Documentation separation | 3-4 weeks | ~70% |
| **Phase 3** | Equipment catalog + renewal flow + inspection tracking | 2-3 weeks | ~95% |
| **Phase 4** | Identification records + penalty-aging score + BrikOps differentiators (daily briefing, vision AI auto-fill) | 2 weeks | 100%+ |

**Total remaining: 7-9 weeks of Replit work.**

---

## 6 locked decisions (from concept doc — DO NOT re-litigate)

| # | Topic | Decision |
|---|---|---|
| 1 | רשם הקבלנים | Manual entry ב-MVP + autocomplete organic מה-DB. אין scraping. |
| 2 | קטגוריות ציוד | Cemento's 10 + "+ הוסף קטגוריה מותאמת" (לא ב-Safety Score). |
| 3 | Safety Score weights | Cemento 1:1. `worker×10 + equipment×10 + medium(sum_days×1 + count×5) + high(sum_days×2 + count×10)`. |
| 4 | UI collapsibility | כל בלוק collapsible. ריק → collapsed, <3 פריטים → expanded, ≥3 → collapsed. |
| 5 | חתימות Tour | **מנהל עבודה + עוזר בטיחות** (לא ממונה — אופציונלי). |
| 6 | Migration מ-Cemento | Hybrid: Concierge → Training Form Auto-Importer → Tasks Parser + Manual Review. |
| 7 | Defect vs Documentation | **2 collections נפרדות.** Defect closeable, Documentation archival. |

**Architectural rule (from concept):** בטיחות כ-module נפרד לחלוטין מהליקויים הקיימים. Collections נפרדים, routes נפרדים, components נפרדים. אל תשבור QC/handover.

---

## Current production state

- **Flag:** `ENABLE_SAFETY_MODULE = true` (enabled by Zahi 2026-04-23 for closed beta)
- **Users seeing the module:** closed beta PMs on real projects
- **Feedback received:** "דף לא שמיש — אי אפשר ליצור כלום, חסר סיורים" → blocking issues
- **Rollback plan:** set flag to `false` in EB env vars → module becomes 404 for all users (tested)

---

## Before Phase 2 starts: closed-beta fix queue

Zahi will deliver the list of fixes requested by closed-beta users. Those get patched first. Only after the fixes are deployed and stable, Phase 2 planning begins.

**When Zahi says "start Phase 2":**
1. Re-read this file + concept doc + master plan
2. Read `CEMENTO_ANALYSIS.md` and the 3 mockup HTML files
3. Use `brikops-spec-writer` skill to author Phase 2 spec
4. Phase 2 scope (per concept doc Phase 2-3 order):
   - Tours (walkarounds) data model + UI flow — **the central workflow, highest priority**
   - Create/Edit modals for workers/defects/tasks/trainings/incidents — **makes the page usable**
   - Documentation separation from defects — **concept decision §7**
5. DO NOT ask Zahi to re-decide things that are in the 6 locked decisions
6. Present plan → get approval → ship to Replit

---

## Key planning artifacts (read these before writing specs)

| File | What's in it | When to read |
|---|---|---|
| `future-features/HANDOFF-safety-feature-2026-04-22.md` | Clean summary of concept + 6 decisions | Always first |
| `future-features/safety-and-worklog-concept.md` | 850+ lines — full concept, schemas, Phase 1-4 roadmap, 6 decisions, SOC2 addendum | When designing any safety feature |
| `future-features/cemento-research/CEMENTO_ANALYSIS.md` | Cemento PDF teardown, what data exports expose | When thinking about migration or parity |
| `specs/safety-phase-1-master-plan.md` | What Phase 1 actually built (5 parts, 23 hours) | For context on current state |
| `specs/safety-design-system.md` | Colors, typography, components, a11y rules | Every UI spec must reference |
| `future-features/safety-phase-1-mockup-v3.html` | Visual reference with gauge + sparklines | For any UI spec |

---

## How to enable/disable the flag on AWS

**Enable (current state):**
1. AWS Console → Elastic Beanstalk → application → prod env
2. Configuration → Software → Environment properties
3. `ENABLE_SAFETY_MODULE = true`
4. Apply → ~2-3 min rolling restart
5. Verify: `curl https://api.brikops.com/api/safety/healthz` returns 200

**Disable (emergency rollback):**
Same steps, set to `false`. All `/api/safety/*` return 404 within 2-3 min. Frontend shows "module disabled" card gracefully.

---

## Tasks in the tracker

- `#29 בטיחות + יומן עבודה Phase 1` → completed (with documented gap)
- `#33-#38` → individual Phase 1 sub-parts, all completed
- `#27 Vision AI Phase 1` → pending (Phase 4 candidate: auto-fill ליקויים מתמונה)

**Next task to create when Phase 2 starts:** `Safety Phase 2 — Tours + CRUD modals + Documentation separation`.

---

## Summary for Zahi to reference in future sessions

> קלוד, קרא את `/Users/zhysmy/brikops-new/SAFETY-STATUS.md` לפני שאתה עובד על בטיחות. ההחלטות כבר סגורות, התכנית קיימת, אל תשאל שאלות עיצוב מחדש.
