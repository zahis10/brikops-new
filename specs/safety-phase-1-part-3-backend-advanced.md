# Task #35 — Safety Phase 1 Part 3 — Backend Advanced

**Scope:** Safety Score + Excel export + Hebrew PDF "פנקס כללי" + filtered export endpoint.
**Est:** ~5h Replit work · 1 file created (`safety_pdf.py`), 2 files edited (`safety_router.py`, `server.py`).
**Depends on:** Part 2 merged (commit `dcb31bda`). Flag `ENABLE_SAFETY_MODULE` still off in AWS.
**NO new deps.** All libraries already in `requirements.txt`.

---

## What & Why

Three regulatory deliverables for construction site safety:

1. **Safety Score** — single 0-100 metric per project, updated from live data, cached 5 minutes. Lets PMs see at a glance if their project is compliant.
2. **Excel export** — 3 sheets (workers / trainings / incidents) for site inspectors and insurance audits.
3. **פנקס כללי (General Register) PDF** — the regulatory Hebrew document required by תקנות הבטיחות בעבודה. 9 sections. RTL. Printable on A4.

All gated behind `ENABLE_SAFETY_MODULE`. All audited.

---

## Done looks like

- `GET /api/safety/{project_id}/score` returns `{score: 0-100, breakdown: {...}, computed_at, cache_age_seconds}`.
- `GET /api/safety/{project_id}/export/excel` streams an `.xlsx` file with 3 worksheets, names in Hebrew.
- `GET /api/safety/{project_id}/export/pdf-register` streams a Hebrew PDF (פנקס כללי) with 9 sections.
- `GET /api/safety/{project_id}/export/filtered` accepts the same 7-dim query params as `GET /documents` and streams an Excel of only the filtered documents.
- All 4 endpoints audit-logged via `_audit`.
- All 4 endpoints respect `_check_project_access` (management-only).
- `ENABLE_SAFETY_MODULE=false` → 404 on all 4 endpoints.
- No changes to Part 1/2 code.
- `requirements.txt` unchanged.

---

## Out of scope

- ❌ Frontend (Parts 4 & 5).
- ❌ Score cron job / background computation (score is computed on-demand, cached).
- ❌ Email/WhatsApp delivery of reports.
- ❌ Historical score trend (future Phase).
- ❌ Incident reporting to authority API (future Phase).
- ❌ Adding noto-sans-hebrew — we reuse the existing `Rubik-Regular.ttf` at `backend/fonts/`.

---

## PRE-READS (do this BEFORE writing code)

1. `backend/contractor_ops/safety_router.py` — the file you extend. Current state: 1289 lines, 25 CRUD endpoints + healthz + indexes.
2. `backend/services/pdf_service.py` — **existing** Hebrew PDF helpers. Shows the `hebrew()` reshape+bidi pattern and Rubik font registration. **Reuse this, do not duplicate.**
3. `backend/services/enhanced_pdf_service.py` — `HebrewPDFTemplate` class. Check if it's reusable for the register PDF.
4. `backend/services/handover_pdf_service.py` — a real multi-section Hebrew PDF example. Copy structure, not content.
5. `backend/contractor_ops/export_router.py` — existing `POST /api/data/export/start` pattern. Part 3 uses a simpler direct-stream approach (safety exports are small, no queue needed).
6. `backend/fonts/` — confirm `Rubik-Regular.ttf` and `Rubik-Bold.ttf` exist. If missing — STOP and ask.
7. `backend/contractor_ops/snapshot_cron.py` lines 58-81 — aggregation pattern using `$cond` + `$sum`. Copy this style.
8. `backend/server.py` — confirm `safety_router` is imported conditionally behind `ENABLE_SAFETY_MODULE` (should already be from Part 1/2).
9. `specs/safety-phase-1-part-2-backend-core.md` — RBAC constants `SAFETY_WRITERS = ("project_manager", "management_team")`. Reads are open to all management via `_check_project_access`.

---

## Tasks

### Task 3.1 — Safety Score endpoint

**File:** `backend/contractor_ops/safety_router.py`

Add a new section `# Safety Score` after the incidents CRUD (after line ~1138, before `# Photo / PDF upload helper`).

**Score formula (0-100, higher = safer):**

```
score = 100 - (doc_penalty + task_penalty + training_penalty + incident_penalty)
clamped to [0, 100]
```

**Sub-penalties (max 100 total):**
- `doc_penalty` — **40 pts max** — Open safety documents, weighted by severity:
  - critical: 10 pts each
  - high: 5 pts each
  - medium: 2 pts each
  - low: 0.5 pts each
  - Sum capped at 40.

- `task_penalty` — **25 pts max** — Overdue safety tasks (due_at < now, status in {open, in_progress}):
  - critical severity: 6 pts each
  - high: 3 pts each
  - medium: 1.5 pts each
  - low: 0.5 pts each
  - Sum capped at 25.

- `training_penalty` — **20 pts max** — Workers with expired training:
  - For each active worker (not soft-deleted), check if their most recent training of each required type has `expires_at < now`.
  - Required types for Phase 1: `{"safety_induction", "height_work", "electrical"}` — constants.
  - Each expired-required-training: 4 pts.
  - Workers with NO training record: 5 pts.
  - Sum capped at 20.

- `incident_penalty` — **15 pts max** — Incidents in last 90 days (occurred_at):
  - injury: 5 pts each
  - property_damage: 3 pts each
  - near_miss: 1 pt each
  - Sum capped at 15.

**Caching:** In-memory dict `_score_cache: dict[str, tuple[dict, datetime]]` keyed by project_id. TTL: **5 minutes** (300 seconds). On cache hit, return with `cache_age_seconds > 0`. On miss, recompute. **No external cache, no Redis** — this is per-process, per-worker, acceptable for Phase 1.

**Helper function signature:**
```python
REQUIRED_TRAINING_TYPES = frozenset({"safety_induction", "height_work", "electrical"})
SCORE_CACHE_TTL_SECONDS = 300
_score_cache: dict[str, tuple[dict, datetime]] = {}

async def _compute_safety_score(db, project_id: str) -> dict:
    """
    Returns:
    {
        "score": int 0-100,
        "breakdown": {
            "doc_penalty": float,
            "task_penalty": float,
            "training_penalty": float,
            "incident_penalty": float,
            "doc_counts": {"critical": N, "high": N, "medium": N, "low": N},
            "overdue_task_counts": {"critical": N, ...},
            "workers_with_expired_training": N,
            "workers_without_training": N,
            "incidents_last_90d": {"injury": N, "property_damage": N, "near_miss": N},
        },
        "computed_at": iso string,
    }
    """
```

**Endpoint:**
```python
@router.get("/{project_id}/score")
async def get_safety_score(
    project_id: str,
    refresh: bool = Query(False, description="Bypass cache and recompute"),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    now = datetime.now(timezone.utc)
    cached = _score_cache.get(project_id)
    if cached and not refresh:
        payload, computed_at = cached
        age = (now - computed_at).total_seconds()
        if age < SCORE_CACHE_TTL_SECONDS:
            return {**payload, "cache_age_seconds": int(age)}

    result = await _compute_safety_score(db, project_id)
    _score_cache[project_id] = (result, now)
    return {**result, "cache_age_seconds": 0}
```

**Implementation notes:**
- Use MongoDB aggregation (`$group` + `$cond`) for the document + task + incident counts. Copy the style from `snapshot_cron.py:58-81`.
- For training, a two-step query is simpler than aggregation: fetch all active workers, then for each worker fetch most-recent training per type. Accept N+1 for Phase 1 (typical project <50 workers). If it becomes slow, optimize in Phase 2.
- All queries MUST filter `deletedAt: None` (consistent with Part 2b fix).
- Audit the endpoint: `await _audit("safety_score", project_id, "computed", user["id"], {"score": score, "cache_hit": was_cached})`.

---

### Task 3.2 — Excel export (3 sheets)

**File:** `backend/contractor_ops/safety_router.py`

Add after the Score section.

**Endpoint:**
```python
@router.get("/{project_id}/export/excel")
async def export_safety_excel(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    wb = Workbook()
    # ... build sheets ...
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    await _audit("safety_export", project_id, "excel_exported", user["id"], {
        "project_id": project_id,
        "worker_count": worker_count,
        "training_count": training_count,
        "incident_count": incident_count,
    })

    filename = f"safety_{project_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**3 worksheets (Hebrew titles, RTL):**

**Sheet 1: "עובדים"** (Workers) — columns:
| שם מלא | חברה | מקצוע | טלפון | תאריך הוספה |
|---------|-------|--------|--------|-----------------|

Query: `db.safety_workers.find({"project_id": project_id, "deletedAt": None})`. Sort by `created_at`. For company — join to `project_companies` by `company_id` (one find per worker is OK; typical <50).

**DO NOT export `id_number_hash`** — PII rule.

**Sheet 2: "הדרכות"** (Trainings) — columns:
| עובד | סוג הדרכה | מדריך | תאריך | תוקף עד | סטטוס |
|-------|-------------|---------|---------|-----------|---------|

Query: `db.safety_trainings.find({"project_id": project_id, "deletedAt": None})`. Sort by `trained_at` desc.
- `סטטוס` column: if `expires_at` < now → "פג תוקף"; else "בתוקף"; else (no expires_at) → "קבוע".
- `עובד` column: worker full_name (batch-fetch workers, map by id).

**Sheet 3: "אירועים"** (Incidents) — columns:
| סוג | חומרה | תאריך ושעה | מיקום | תיאור | דווח לרשויות |
|------|--------|----------------|---------|---------|-----------------|

Query: `db.safety_incidents.find({"project_id": project_id, "deletedAt": None})`. Sort by `occurred_at` desc.
- `סוג`: translate `incident_type` via dict: `{"near_miss": "כמעט אירוע", "injury": "פציעה", "property_damage": "נזק לרכוש"}`.
- `חומרה`: translate `severity`: `{"critical": "קריטי", "high": "גבוה", "medium": "בינוני", "low": "נמוך"}`.
- `דווח לרשויות`: `"כן"` / `"לא"` from `reported_to_authority` bool.

**Formatting (apply to all 3 sheets):**
- Row 1 = header, bold, grey background (`PatternFill(fgColor="D0D0D0")`).
- Set `ws.sheet_view.rightToLeft = True` for RTL display.
- Column widths: auto-fit or manual `ws.column_dimensions['A'].width = 20`.
- Freeze row 1: `ws.freeze_panes = "A2"`.

---

### Task 3.3 — Filtered documents export

**File:** `backend/contractor_ops/safety_router.py`

Add right after Task 3.2.

**Endpoint:**
```python
@router.get("/{project_id}/export/filtered")
async def export_filtered_documents(
    project_id: str,
    category: Optional[SafetyCategory] = None,
    severity: Optional[SafetySeverity] = None,
    status_: Optional[SafetyDocumentStatus] = Query(None, alias="status"),
    company_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    reporter_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    ...
```

**Behavior:**
- Same 7-dim filter logic as `GET /documents` (copy the query-building code).
- Export 1 sheet named "ממצאי בטיחות" (Safety Findings).
- Columns: `כותרת | קטגוריה | חומרה | סטטוס | חברה | מצא | אחראי | תאריך מציאה | פתרון`.
- Hebrew translations for category/severity/status enum values (add a translation dict at the top of the file).
- If zero results → still return valid Excel with header row only, 200 OK. Do not 404.
- Filename: `safety_findings_{project_id}_{timestamp}.xlsx`.
- Audit: `"filtered_exported"` with `filters_applied` dict (same as list endpoint).

---

### Task 3.4 — Hebrew PDF "פנקס כללי" (General Register)

**Create new file:** `backend/services/safety_pdf.py`

**Why a new file, not inline:** The register is ~200 lines of reportlab code. Keeping it in a service file matches the pattern of `handover_pdf_service.py` / `enhanced_pdf_service.py`.

**Structure:**
```python
"""
Safety General Register ("פנקס כללי") — regulatory Hebrew PDF.
Required by תקנות הבטיחות בעבודה. 9 sections, A4, RTL, printable.

Fonts: reuses existing Rubik-Regular/Rubik-Bold from backend/fonts/.
Does NOT add noto-sans-hebrew (was considered, not needed — Rubik renders Hebrew cleanly).
"""
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.lib import colors
import os
import logging

# Reuse existing Hebrew helpers from pdf_service
from services.pdf_service import hebrew  # reshapes + bidi

logger = logging.getLogger(__name__)

# Portable font path — matches the pattern in backend/contractor_ops/export_router.py:1064
# __file__ = backend/services/safety_pdf.py  →  dirname(dirname(abspath(__file__))) = backend/
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

# Register fonts once at import. MUST log on failure — silent pass caused blank-glyph
# PDFs in pdf_service.py before. If the font isn't registered the PDF renders squares
# instead of Hebrew and you won't find out until QA.
try:
    pdfmetrics.registerFont(TTFont("Rubik", os.path.join(_FONTS_DIR, "Rubik-Regular.ttf")))
except Exception as e:
    logger.warning(f"[safety_pdf] Could not register Rubik-Regular: {e}")
try:
    pdfmetrics.registerFont(TTFont("Rubik-Bold", os.path.join(_FONTS_DIR, "Rubik-Bold.ttf")))
except Exception as e:
    logger.warning(f"[safety_pdf] Could not register Rubik-Bold: {e}")


async def generate_safety_register(db, project_id: str) -> bytes:
    """
    Build the 9-section "פנקס כללי" PDF for this project.
    Returns raw PDF bytes (caller wraps in StreamingResponse).
    """
    ...
```

**9 sections (in order, each on its own page or continuation):**

1. **שער (Cover)** — Project name, address, contractor/org name, PM name, date generated, "פנקס כללי — בטיחות באתר הבנייה".
2. **פרטי האתר** (Site Details) — project_id, city, start_date, expected_completion_date (fetch from `projects` collection).
3. **צוות ניהולי** (Management Team) — PM, safety officers (from `project_memberships` with sub_role=`safety_officer`). Name + phone + email.
4. **רשימת עובדים באתר** (Workers Roster) — table: שם | חברה | מקצוע | טלפון. All non-deleted workers.
5. **תיעוד הדרכות** (Training Records) — table: עובד | סוג הדרכה | תאריך | תוקף עד | מצב. All non-deleted trainings, grouped by worker.
6. **ממצאי בטיחות פתוחים** (Open Safety Findings) — table: כותרת | חומרה | מצא | תאריך. Documents where `status` in `{open, in_progress}`.
7. **משימות בטיחות פתוחות** (Open Safety Tasks) — table: כותרת | חומרה | אחראי | תאריך יעד. Tasks where `status` in `{open, in_progress}`.
8. **אירועי בטיחות** (Incident Log) — table: סוג | חומרה | תאריך | מיקום | תיאור מקוצר. All non-deleted incidents, sorted by occurred_at desc.
9. **הצהרת מנהל עבודה** (Work Manager Declaration) — 3-4 lines of fixed regulatory text + signature lines (use `Spacer` + `Paragraph` with underline for signature). TEXT:
   > "אני הח"מ מצהיר/ה בזאת כי הפנקס הכללי מתנהל באתר זה בהתאם לתקנות הבטיחות בעבודה, וכי כל האירועים, ההדרכות וממצאי הבטיחות המופיעים בו נרשמו בזמן אמת."
   >
   > "שם מנהל העבודה: _____________"
   > "תאריך: _____________"
   > "חתימה: _____________"

**Styling:**
- All paragraphs use `fontName="Rubik"`, `alignment=TA_RIGHT` (for RTL).
- Headers use `fontName="Rubik-Bold"`, size 14-18.
- Tables have grid lines, header row in light grey.
- Page footer: "עמוד X מתוך Y · פנקס כללי · פרויקט {name}".
- All Hebrew strings passed through `hebrew(text)` helper from `pdf_service.py`.

**Endpoint (add to safety_router.py):**
```python
@router.get("/{project_id}/export/pdf-register")
async def export_safety_pdf_register(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    from services.safety_pdf import generate_safety_register
    pdf_bytes = await generate_safety_register(db, project_id)

    await _audit("safety_export", project_id, "pdf_register_exported", user["id"], {
        "project_id": project_id, "size_bytes": len(pdf_bytes),
    })

    filename = f"safety_register_{project_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

---

### Task 3.5 — server.py wiring verification

**File:** `backend/server.py`

Already registered from Part 1 — no changes needed. **VERIFY only:**

```bash
grep -n "safety_router" backend/server.py
grep -n "ENABLE_SAFETY_MODULE" backend/server.py
```

Expected: `safety_router` is imported and included inside an `if os.getenv("ENABLE_SAFETY_MODULE"):` block. If not — STOP and ask.

---

## Relevant files

**Edit:**
- `backend/contractor_ops/safety_router.py` — add 4 endpoints + helpers at line ~1138 (before the upload helper) or ~1189 (after upload, before indexes). Keep `ensure_safety_indexes` at the bottom.

**Create:**
- `backend/services/safety_pdf.py` — ~250 lines, single function `generate_safety_register(db, project_id) -> bytes`.

**Do NOT touch:**
- `requirements.txt` — no new deps.
- `backend/fonts/` — reuse existing Rubik.
- `backend/services/pdf_service.py` — reuse `hebrew()`, do not modify.
- Part 1 / Part 2 endpoints — zero changes.
- Any frontend files.

---

## DO NOT

- ❌ Do NOT add `noto-sans-hebrew` — Rubik is sufficient. Zero new deps.
- ❌ Do NOT modify `requirements.txt` — all deps already present.
- ❌ Do NOT add Redis or any external cache — in-memory dict with 5-min TTL is enough for Phase 1.
- ❌ Do NOT put raw Hebrew in the source file without `hebrew()` wrapper in PDF code — reportlab needs pre-shaped text.
- ❌ Do NOT add PDF generation for other modules (handover already has its own).
- ❌ Do NOT export `id_number` or `id_number_hash` in ANY of the 4 endpoints (Excel, filtered, PDF). PII rule from Part 2.
- ❌ Do NOT create score persistence (no `safety_scores` collection) — score is computed on demand.
- ❌ Do NOT allow `include_deleted=true` on any export — always filter `deletedAt: None`.
- ❌ Do NOT add authentication middleware or role decorators beyond `_check_project_access` + `get_current_user`. Management-only read is already enforced by `_check_project_access`.
- ❌ Do NOT make score endpoint public — requires auth.
- ❌ Do NOT use `now_il()` or any Israel-specific timezone. All timestamps UTC ISO.
- ❌ Do NOT use `datetime.utcnow()` — use `datetime.now(timezone.utc)` per project convention.
- ❌ Do NOT add frontend changes — Part 3 is backend only.
- ❌ Do NOT modify the existing `snapshot_cron.py` pattern — just copy its aggregation style.
- ❌ Do NOT use a relative path like `"backend/fonts/Rubik-Regular.ttf"` for `registerFont` — cwd is not guaranteed on Elastic Beanstalk. Use the `__file__`-anchored `_FONTS_DIR` pattern shown above.
- ❌ Do NOT silently `except: pass` on font registration failure. Log it via `logger.warning` — otherwise the PDF renders as Hebrew-glyph squares and QA can't tell why.

---

## VERIFY (before `./deploy.sh --prod`)

### 1. No new deps
```bash
git diff requirements.txt
# Expected: empty output
```

### 2. Safety Score endpoint
```bash
# With flag on locally:
curl -H "Authorization: Bearer $TOKEN" \
  https://api.brikops.com/api/safety/PROJECT_ID/score | jq
# Expected: {score: 0-100, breakdown: {...}, computed_at, cache_age_seconds: 0}

# Call again immediately:
# Expected: cache_age_seconds > 0 (and < 300)

# Call with refresh=true:
curl "...?refresh=true" | jq
# Expected: cache_age_seconds: 0 (recomputed)
```

### 3. Excel export — opens cleanly
```bash
curl -o safety.xlsx -H "Authorization: Bearer $TOKEN" \
  https://api.brikops.com/api/safety/PROJECT_ID/export/excel
open safety.xlsx  # Mac
# Expected: 3 sheets with Hebrew names, RTL, data rows, bold header, frozen row 1.
# Expected: no id_number_hash column anywhere.
```

### 4. PDF register — opens cleanly
```bash
curl -o register.pdf -H "Authorization: Bearer $TOKEN" \
  https://api.brikops.com/api/safety/PROJECT_ID/export/pdf-register
open register.pdf
# Expected: 9 sections, Hebrew text readable (not mirrored, not garbled), page numbers in footer.

# Also grep the backend log for font-registration warnings:
grep "safety_pdf.*Could not register" /path/to/backend.log
# Expected: empty. If you see a warning — the _FONTS_DIR resolver is wrong for this env
# and the PDF is rendering without Hebrew support even if it "opens".
```

### 5. Filtered export
```bash
curl -o filtered.xlsx -H "Authorization: Bearer $TOKEN" \
  "https://api.brikops.com/api/safety/PROJECT_ID/export/filtered?severity=critical&status=open"
open filtered.xlsx
# Expected: only documents matching filter. 1 sheet "ממצאי בטיחות".
```

### 6. Flag-off behavior
```bash
# Set ENABLE_SAFETY_MODULE=false and restart:
curl -H "Authorization: Bearer $TOKEN" https://api.brikops.com/api/safety/PROJECT_ID/score
# Expected: 404 Not Found.
```

### 7. Audit trail check
```bash
# After a score computation + excel export:
# Query db.audit_events in Mongo — expect 2 new events:
#   - entity_type="safety_score", action="computed"
#   - entity_type="safety_export", action="excel_exported"
```

### 8. PII check (critical)
```bash
# Unzip the Excel file and grep the XML:
unzip -p safety.xlsx xl/worksheets/sheet1.xml | grep -c "id_number_hash"
# Expected: 0 (PII must not leak through Excel).
```

### 9. Regression — Part 1/2 endpoints still work
```bash
curl -H "Authorization: Bearer $TOKEN" https://api.brikops.com/api/safety/healthz
# Expected: 200 {"ok": true, ...}

curl -H "Authorization: Bearer $TOKEN" https://api.brikops.com/api/safety/PROJECT_ID/workers
# Expected: 200 {items: [...], total, limit, offset}
```

---

## Deploy

```bash
./deploy.sh --prod
```

Flag `ENABLE_SAFETY_MODULE` stays **off** in AWS. Deploy is safe — all new endpoints 404 until flag flipped. After deploy, send Zahi:
- `git log -1 --stat`
- Unified diff of the commit
- Result of the 9 VERIFY steps above (from local/staging with flag on)

---

## Definition of Done

- [ ] 4 new endpoints in `safety_router.py`: `/score`, `/export/excel`, `/export/filtered`, `/export/pdf-register`
- [ ] `backend/services/safety_pdf.py` created with `generate_safety_register()` function
- [ ] All endpoints audit-logged
- [ ] All endpoints respect `_check_project_access`
- [ ] All queries filter `deletedAt: None`
- [ ] No `id_number` / `id_number_hash` anywhere in exports
- [ ] `requirements.txt` UNCHANGED (zero new deps)
- [ ] `server.py` UNCHANGED (flag wiring already done in Part 1)
- [ ] 9 VERIFY steps pass
- [ ] `./deploy.sh --prod` ran successfully
- [ ] Post-deploy diff sent to Zahi
