"""
Safety module router — Phase 1 Part 1 (Foundation).

Only exposes healthz. All CRUD + filters arrive in Part 2.

Registration in server.py is GATED by ENABLE_SAFETY_MODULE env flag.
When flag is off, this module is never imported and endpoints 404.
"""
from fastapi import APIRouter, Depends
from contractor_ops.router import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.get("/healthz")
async def healthz(user: dict = Depends(get_current_user)):
    """
    Liveness check for Safety module.
    Requires auth — never expose module existence to unauthenticated scanners.
    """
    return {"ok": True, "module": "safety", "enabled": True}


# =====================================================================
# Index management — called from server.py startup when module enabled.
# =====================================================================
async def ensure_safety_indexes(db) -> None:
    """
    Create MongoDB indices for Safety collections.
    Idempotent: `create_index` is a no-op if the same spec already exists.
    Safe to run on every startup.

    All indices use background=True to avoid locking hot collections.
    """
    # -----------------------------------------------------------------
    # safety_workers — 3 indices
    # -----------------------------------------------------------------
    await db.safety_workers.create_index(
        [("project_id", 1), ("deletedAt", 1)],
        background=True,
        name="idx_sw_project_deleted",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True,
        name="idx_sw_project_company",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("id_number", 1)],
        background=True,
        sparse=True,
        name="idx_sw_project_idnum",
    )

    # -----------------------------------------------------------------
    # safety_trainings — 3 indices
    # -----------------------------------------------------------------
    await db.safety_trainings.create_index(
        [("project_id", 1), ("worker_id", 1)],
        background=True,
        name="idx_st_project_worker",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("expires_at", 1)],
        background=True,
        sparse=True,
        name="idx_st_project_expires",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("training_type", 1)],
        background=True,
        name="idx_st_project_type",
    )

    # -----------------------------------------------------------------
    # safety_documents — 5 filter-critical indices
    # -----------------------------------------------------------------
    await db.safety_documents.create_index(
        [("project_id", 1), ("deletedAt", 1), ("created_at", -1)],
        background=True,
        name="idx_sd_project_deleted_created",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("status", 1)],
        background=True,
        name="idx_sd_project_status",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True,
        name="idx_sd_project_severity",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("category", 1)],
        background=True,
        name="idx_sd_project_category",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True,
        sparse=True,
        name="idx_sd_project_company",
    )

    # -----------------------------------------------------------------
    # safety_tasks — 4 indices
    # -----------------------------------------------------------------
    await db.safety_tasks.create_index(
        [("project_id", 1), ("deletedAt", 1), ("due_at", 1)],
        background=True,
        name="idx_stk_project_deleted_due",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("status", 1)],
        background=True,
        name="idx_stk_project_status",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("assignee_id", 1)],
        background=True,
        sparse=True,
        name="idx_stk_project_assignee",
    )
    await db.safety_tasks.create_index(
        [("document_id", 1)],
        background=True,
        sparse=True,
        name="idx_stk_document",
    )

    # -----------------------------------------------------------------
    # safety_incidents — 3 indices (7yr retention-critical)
    # -----------------------------------------------------------------
    await db.safety_incidents.create_index(
        [("project_id", 1), ("occurred_at", -1)],
        background=True,
        name="idx_si_project_occurred",
    )
    await db.safety_incidents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True,
        name="idx_si_project_severity",
    )
    await db.safety_incidents.create_index(
        [("retention_until", 1)],
        background=True,
        sparse=True,
        name="idx_si_retention",
    )

    # -----------------------------------------------------------------
    # project_companies — 2 new safety-related indices
    # (safe to add — collection is shared with other modules)
    # -----------------------------------------------------------------
    await db.project_companies.create_index(
        [("project_id", 1), ("safety_contact_id", 1)],
        background=True,
        sparse=True,
        name="idx_pc_project_safety_contact",
    )
    await db.project_companies.create_index(
        [("project_id", 1), ("is_placeholder", 1)],
        background=True,
        sparse=True,
        name="idx_pc_project_placeholder",
    )

    logger.info("Safety indices ensured (20 total across 6 collections)")
