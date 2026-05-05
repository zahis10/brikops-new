"""
Execution Matrix routes — Phase 1 backend (Batch Execution Matrix, 2026-05-04).

Implements the project-level matrix grid (units × stages) with:
  - Stage list customization (base from qc_template + custom additions)
  - Per-cell status + note + audit history
  - Per-user saved views

Architectural anchors (Zahi 2026-05-04):
  - Matrix is INDEPENDENT data store (own collections, own state).
  - NO modification of qc_template, qc_runs, or qc_items.
  - READS qc_template stages live (computed render time, no migration).
  - READS qc_runs.stage_statuses for annotations only in PHASE 2.

Divergences from spec (documented here for code-survival, not just review.txt):

  D1. Imports from contractor_ops.router (not via qc_router).
      Spec imported _get_project_role / _is_super_admin / MANAGEMENT_ROLES
      from qc_router (re-exports). We import from router.py directly —
      cleaner dependency graph, qc_router (2,936 LOC) is the consumer
      of these helpers, not the source.

  D2. _get_matrix_approver_user_ids filter includes "active": True.
      Spec's placeholder query omitted it. The canonical pattern across
      qc_router L80, L1153, L1853 always filters by active. Inactive
      approvers (revoked) must NOT get matrix-edit access — same trust
      semantics as QC approval.

  D3. "viewer" role removed from _check_matrix_view.
      Spec mentioned a "viewer" role; no such role exists in the codebase
      (MANAGEMENT_ROLES = ('project_manager', 'management_team');
      QC_VIEW_ROLES = PM_ROLES | {'management_team'}). View access
      aligned to the existing QC_VIEW_ROLES pattern: super_admin +
      project_manager + owner + management_team. Contractor blocked
      explicitly.

  D4. Stage-scoped approvers (mode="stages") get full matrix-edit access.
      Approval semantics (Zahi 2026-05-04): trust given for any stage
      approval = trust given for matrix annotation. Matrix is project-
      level (not stage-specific), so stage-scope on the approver doc
      is irrelevant here. Both mode="all" and mode="stages" approvers
      can edit all matrix cells.
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from contractor_ops.router import (
    _now,
    _audit,
    get_db,
    get_current_user,
    _get_project_role,
    _is_super_admin,
    MANAGEMENT_ROLES,
)
from contractor_ops.qc_router import _get_template
from contractor_ops.schemas import (
    MATRIX_STATUS_VALUES,
    MatrixStagesUpdate,
    MatrixCellUpdate,
    MatrixSavedViewCreate,
)

router = APIRouter(prefix="/api/execution-matrix", tags=["execution-matrix"])


MATRIX_VIEW_ROLES = set(MANAGEMENT_ROLES) | {"owner"}


# =====================================================================
# RBAC helpers
# =====================================================================

async def _get_matrix_approver_user_ids(db, project_id: str) -> set:
    """Return set of user_ids that are active project_approvers.

    Per D2 + D4: filters by active=True (matches canonical qc_router
    pattern); ANY active approver — regardless of mode — gets edit
    access. Stage-scope on the approver doc is irrelevant for the
    project-level matrix.
    """
    cursor = db.project_approvers.find(
        {"project_id": project_id, "active": True},
        {"_id": 0, "user_id": 1},
    )
    return {a["user_id"] async for a in cursor}


async def _check_matrix_view(user, project_id):
    """Per D3: super_admin + PM + owner + management_team. Contractor blocked."""
    if _is_super_admin(user):
        return "super_admin"
    role = await _get_project_role(user, project_id)
    if role == "contractor":
        raise HTTPException(
            status_code=403,
            detail="קבלן אינו רשאי לצפות במטריצת ביצוע",
        )
    if role not in MATRIX_VIEW_ROLES:
        raise HTTPException(
            status_code=403,
            detail="אין הרשאה לצפות במטריצת ביצוע",
        )
    return role


async def _check_matrix_edit(user, project_id):
    """Edit allowed for: super_admin, project_manager, OR any active approver (D4)."""
    if _is_super_admin(user):
        return "super_admin"
    role = await _get_project_role(user, project_id)
    if role == "project_manager":
        return role
    db = get_db()
    approver_ids = await _get_matrix_approver_user_ids(db, project_id)
    if user["id"] in approver_ids:
        return "approver"
    raise HTTPException(
        status_code=403,
        detail="עריכה במטריצת ביצוע מותרת רק למנהל פרויקט או מאשרי בקרת ביצוע",
    )


# =====================================================================
# Lazy init + stage resolution
# =====================================================================

async def _get_or_init_matrix_config(db, project_id: str) -> dict:
    """Fetch the project's matrix config doc, create empty one if missing."""
    existing = await db.execution_matrix.find_one(
        {"project_id": project_id, "deletedAt": None},
        {"_id": 0},
    )
    if existing:
        return existing
    now = _now()
    doc = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "custom_stages": [],
        "base_stages_removed": [],
        "created_at": now,
        "created_by": None,
        "updated_at": now,
        "updated_by": None,
        "deletedAt": None,
    }
    await db.execution_matrix.insert_one(doc)
    return doc


def _resolve_visible_stages(matrix_config: dict, tpl: dict) -> List[dict]:
    """Compute visible stage list = qc_template.stages (minus base_stages_removed)
    + matrix_config.custom_stages, sorted by .order."""
    base_removed = set(matrix_config.get("base_stages_removed", []) or [])
    base_stages = []
    for s in tpl.get("stages", []) or []:
        if s["id"] in base_removed:
            continue
        base_stages.append({
            "id": s["id"],
            "title": s.get("title", ""),
            "type": "status",
            "order": s.get("order", 0),
            "source": "base",
            "scope": s.get("scope"),
        })
    custom_stages = []
    for cs in matrix_config.get("custom_stages", []) or []:
        custom_stages.append({
            "id": cs["id"],
            "title": cs.get("title", ""),
            "type": cs.get("type", "status"),
            "order": cs.get("order", 9999),
            "source": "custom",
            "scope": None,
        })
    merged = sorted(base_stages + custom_stages, key=lambda x: x["order"])
    return merged


# =====================================================================
# ENDPOINTS — matrix view
# =====================================================================

@router.get("/{project_id}")
async def get_matrix(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Return matrix view: stages (resolved), units (sorted), cells, permissions."""
    db = get_db()
    role = await _check_matrix_view(user, project_id)
    can_edit = False
    try:
        await _check_matrix_edit(user, project_id)
        can_edit = True
    except HTTPException:
        pass

    matrix_config = await _get_or_init_matrix_config(db, project_id)
    tpl = await _get_template(db, project_id=project_id)
    stages = _resolve_visible_stages(matrix_config, tpl)

    units = await db.units.find(
        {"project_id": project_id, "archived": {"$ne": True}},
        {"_id": 0},
    ).to_list(2000)

    floor_ids = list({u["floor_id"] for u in units if u.get("floor_id")})
    floors = []
    if floor_ids:
        floors = await db.floors.find(
            {"id": {"$in": floor_ids}, "archived": {"$ne": True}},
            {"_id": 0},
        ).to_list(500)
    floors_by_id = {f["id"]: f for f in floors}

    def _unit_sort_key(u):
        f = floors_by_id.get(u.get("floor_id"), {})
        unit_no_str = u.get("unit_no", "") or ""
        try:
            unit_no_num = int(unit_no_str)
        except (ValueError, TypeError):
            unit_no_num = 9999  # non-numeric unit_no sorts to end
        return (f.get("floor_number", 0), unit_no_num, unit_no_str)
    units.sort(key=_unit_sort_key)

    stage_ids = [s["id"] for s in stages]
    cells_docs = []
    if stage_ids:
        cells_docs = await db.execution_matrix_cells.find(
            {"project_id": project_id, "stage_id": {"$in": stage_ids}},
            {"_id": 0},
        ).to_list(50000)

    def _summarize_cell(c):
        last_audit = (c.get("audit") or [])[-1] if c.get("audit") else None
        return {
            "unit_id": c["unit_id"],
            "stage_id": c["stage_id"],
            "status": c.get("status"),
            "text_value": c.get("text_value"),
            "note": c.get("note"),
            "last_updated_at": c.get("last_updated_at"),
            "last_updated_by": c.get("last_updated_by"),
            "last_actor_name": last_audit.get("actor_name") if last_audit else None,
        }
    cells_summary = [_summarize_cell(c) for c in cells_docs]

    return {
        "project_id": project_id,
        "stages": stages,
        "units": units,
        "cells": cells_summary,
        "floors": floors,
        "permissions": {
            "role": role,
            "can_view": True,
            "can_edit": can_edit,
        },
        "matrix_config_id": matrix_config["id"],
    }


# =====================================================================
# ENDPOINTS — stage list
# =====================================================================

@router.patch("/{project_id}/stages")
async def update_stages(
    project_id: str,
    payload: MatrixStagesUpdate,
    user: dict = Depends(get_current_user),
):
    """Edit project stage list: add/remove custom + hide/show base."""
    db = get_db()
    await _check_matrix_edit(user, project_id)

    matrix_config = await _get_or_init_matrix_config(db, project_id)
    updates_in = payload.dict(exclude_unset=True)
    db_updates = {}

    if "custom_stages_added" in updates_in:
        max_existing_order = max(
            (s.get("order", 0) for s in matrix_config.get("custom_stages", []) or []),
            default=999,
        )
        new_custom = []
        for i, s in enumerate(updates_in["custom_stages_added"] or []):
            new_custom.append({
                "id": s.get("id") or f"custom_{uuid.uuid4().hex[:12]}",
                "title": (s["title"] or "").strip(),
                "type": s.get("type", "status"),
                "order": s.get("order") if s.get("order") is not None else max_existing_order + i + 1,
                "created_by": user["id"],
                "created_at": _now(),
            })
        db_updates["custom_stages"] = new_custom

    if "base_stages_removed" in updates_in:
        db_updates["base_stages_removed"] = [str(s) for s in (updates_in["base_stages_removed"] or [])]

    db_updates["updated_at"] = _now()
    db_updates["updated_by"] = user["id"]

    await db.execution_matrix.update_one(
        {"project_id": project_id, "deletedAt": None},
        {"$set": db_updates},
    )

    await _audit(
        "execution_matrix",
        project_id,
        "matrix_stages_updated",
        user["id"],
        {"updates": list(db_updates.keys())},
    )

    refreshed = await _get_or_init_matrix_config(db, project_id)
    tpl = await _get_template(db, project_id=project_id)
    return {
        "project_id": project_id,
        "stages": _resolve_visible_stages(refreshed, tpl),
    }


# =====================================================================
# ENDPOINTS — cells
# =====================================================================

@router.put("/{project_id}/cells/{unit_id}/{stage_id}")
async def update_cell(
    project_id: str,
    unit_id: str,
    stage_id: str,
    payload: MatrixCellUpdate,
    user: dict = Depends(get_current_user),
):
    """Update a single cell, append audit entry."""
    db = get_db()
    await _check_matrix_edit(user, project_id)

    matrix_config = await _get_or_init_matrix_config(db, project_id)
    tpl = await _get_template(db, project_id=project_id)
    visible_stages = _resolve_visible_stages(matrix_config, tpl)
    visible_stage_ids = {s["id"] for s in visible_stages}
    if stage_id not in visible_stage_ids:
        raise HTTPException(status_code=404, detail="שלב לא קיים במטריצה")

    unit = await db.units.find_one({"id": unit_id, "project_id": project_id})
    if not unit:
        raise HTTPException(status_code=404, detail="דירה לא נמצאה בפרויקט")

    new_status = payload.status
    if new_status is not None and new_status not in MATRIX_STATUS_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Status not in {MATRIX_STATUS_VALUES}",
        )

    stage = next((s for s in visible_stages if s["id"] == stage_id), None)
    stage_type = (stage or {}).get("type", "status")
    if stage_type == "status" and payload.text_value not in (None, ""):
        raise HTTPException(
            status_code=400,
            detail="שלב מסוג סטטוס לא מקבל ערך טקסט (text_value)",
        )
    if stage_type == "tag" and payload.status is not None:
        raise HTTPException(
            status_code=400,
            detail="שלב מסוג תגית לא מקבל ערך סטטוס (status)",
        )

    existing = await db.execution_matrix_cells.find_one(
        {"project_id": project_id, "unit_id": unit_id, "stage_id": stage_id}
    )
    now = _now()
    actor_name = user.get("name") or user.get("email") or user["id"]

    audit_entry = {
        "actor_id": user["id"],
        "actor_name": actor_name,
        "timestamp": now,
        "status_before": existing.get("status") if existing else None,
        "status_after": new_status,
        "note_before": existing.get("note") if existing else None,
        "note_after": payload.note,
        "text_before": existing.get("text_value") if existing else None,
        "text_after": payload.text_value,
    }

    if existing:
        new_audit = (existing.get("audit") or []) + [audit_entry]
        await db.execution_matrix_cells.update_one(
            {"project_id": project_id, "unit_id": unit_id, "stage_id": stage_id},
            {"$set": {
                "status": new_status,
                "note": payload.note,
                "text_value": payload.text_value,
                "audit": new_audit,
                "last_updated_at": now,
                "last_updated_by": user["id"],
            }},
        )
    else:
        await db.execution_matrix_cells.insert_one({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "unit_id": unit_id,
            "stage_id": stage_id,
            "status": new_status,
            "note": payload.note,
            "text_value": payload.text_value,
            "audit": [audit_entry],
            "last_updated_at": now,
            "last_updated_by": user["id"],
            "created_at": now,
        })

    return {
        "project_id": project_id,
        "unit_id": unit_id,
        "stage_id": stage_id,
        "status": new_status,
        "note": payload.note,
        "text_value": payload.text_value,
        "last_updated_at": now,
        "last_updated_by": user["id"],
        "last_actor_name": actor_name,
    }


@router.get("/{project_id}/cells/{unit_id}/{stage_id}/history")
async def get_cell_history(
    project_id: str,
    unit_id: str,
    stage_id: str,
    user: dict = Depends(get_current_user),
):
    """Return full audit chain for a single cell."""
    db = get_db()
    await _check_matrix_view(user, project_id)
    cell = await db.execution_matrix_cells.find_one(
        {"project_id": project_id, "unit_id": unit_id, "stage_id": stage_id},
        {"_id": 0},
    )
    if not cell:
        return {"history": []}
    return {"history": cell.get("audit", [])}


# =====================================================================
# ENDPOINTS — saved views (per-user)
# =====================================================================

@router.get("/{project_id}/views")
async def list_views(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """List the current user's saved views for this project."""
    db = get_db()
    await _check_matrix_view(user, project_id)
    views = await db.execution_matrix_views.find(
        {"project_id": project_id, "user_id": user["id"], "deletedAt": None},
        {"_id": 0},
    ).sort([("created_at", 1)]).to_list(100)
    return {"views": views}


@router.post("/{project_id}/views", status_code=201)
async def create_view(
    project_id: str,
    payload: MatrixSavedViewCreate,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_matrix_view(user, project_id)
    now = _now()
    view = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "user_id": user["id"],
        "title": payload.title.strip(),
        "icon": (payload.icon or "").strip() or None,
        "filters": payload.filters.dict(exclude_none=True),
        "created_at": now,
        "updated_at": now,
        "deletedAt": None,
    }
    await db.execution_matrix_views.insert_one(view)
    view.pop("_id", None)
    return view


@router.patch("/{project_id}/views/{view_id}")
async def update_view(
    project_id: str,
    view_id: str,
    payload: MatrixSavedViewCreate,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_matrix_view(user, project_id)
    existing = await db.execution_matrix_views.find_one(
        {"id": view_id, "project_id": project_id, "user_id": user["id"], "deletedAt": None}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="תצוגה לא נמצאה")
    updates = {
        "title": payload.title.strip(),
        "icon": (payload.icon or "").strip() or None,
        "filters": payload.filters.dict(exclude_none=True),
        "updated_at": _now(),
    }
    await db.execution_matrix_views.update_one(
        {"id": view_id, "user_id": user["id"]},
        {"$set": updates},
    )
    refreshed = await db.execution_matrix_views.find_one(
        {"id": view_id, "user_id": user["id"]},
        {"_id": 0},
    )
    return refreshed


@router.delete("/{project_id}/views/{view_id}", status_code=204)
async def delete_view(
    project_id: str,
    view_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_matrix_view(user, project_id)
    result = await db.execution_matrix_views.update_one(
        {"id": view_id, "project_id": project_id, "user_id": user["id"], "deletedAt": None},
        {"$set": {"deletedAt": _now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="תצוגה לא נמצאה")
    return None
