"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 3264-3397). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    logger,
)

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
    # safety_workers — 3
    await db.safety_workers.create_index(
        [("project_id", 1), ("deletedAt", 1)],
        background=True, name="idx_sw_project_deleted",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True, name="idx_sw_project_company",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("id_number", 1)],
        background=True, sparse=True, name="idx_sw_project_idnum",
    )
    # safety_trainings — 3
    await db.safety_trainings.create_index(
        [("project_id", 1), ("worker_id", 1)],
        background=True, name="idx_st_project_worker",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("expires_at", 1)],
        background=True, sparse=True, name="idx_st_project_expires",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("training_type", 1)],
        background=True, name="idx_st_project_type",
    )
    # safety_documents — 5
    await db.safety_documents.create_index(
        [("project_id", 1), ("deletedAt", 1), ("created_at", -1)],
        background=True, name="idx_sd_project_deleted_created",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("status", 1)],
        background=True, name="idx_sd_project_status",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True, name="idx_sd_project_severity",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("category", 1)],
        background=True, name="idx_sd_project_category",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True, sparse=True, name="idx_sd_project_company",
    )
    # safety_tasks — 4
    await db.safety_tasks.create_index(
        [("project_id", 1), ("deletedAt", 1), ("due_at", 1)],
        background=True, name="idx_stk_project_deleted_due",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("status", 1)],
        background=True, name="idx_stk_project_status",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("assignee_id", 1)],
        background=True, sparse=True, name="idx_stk_project_assignee",
    )
    await db.safety_tasks.create_index(
        [("document_id", 1)],
        background=True, sparse=True, name="idx_stk_document",
    )
    # safety_incidents — 3 (7yr retention-critical)
    await db.safety_incidents.create_index(
        [("project_id", 1), ("occurred_at", -1)],
        background=True, name="idx_si_project_occurred",
    )
    await db.safety_incidents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True, name="idx_si_project_severity",
    )
    await db.safety_incidents.create_index(
        [("retention_until", 1)],
        background=True, sparse=True, name="idx_si_retention",
    )
    # project_companies — 2 safety-related (shared collection)
    await db.project_companies.create_index(
        [("project_id", 1), ("safety_contact_id", 1)],
        background=True, sparse=True, name="idx_pc_project_safety_contact",
    )
    await db.project_companies.create_index(
        [("project_id", 1), ("is_placeholder", 1)],
        background=True, sparse=True, name="idx_pc_project_placeholder",
    )
    # safety_tours — 3
    await db.safety_tours.create_index(
        [("project_id", 1), ("tour_date", -1)],
        background=True, name="idx_str_project_date",
    )
    await db.safety_tours.create_index(
        [("project_id", 1), ("status", 1)],
        background=True, name="idx_str_project_status",
    )
    await db.safety_tours.create_index(
        [("project_id", 1), ("deletedAt", 1)],
        background=True, name="idx_str_project_deleted",
    )
    # safety_equipment — 3
    await db.safety_equipment.create_index(
        [("project_id", 1), ("category", 1)],
        background=True, name="idx_seq_project_category",
    )
    await db.safety_equipment.create_index(
        [("project_id", 1), ("internal_code", 1)],
        background=True, name="idx_seq_project_code",
    )
    await db.safety_equipment.create_index(
        [("project_id", 1), ("deletedAt", 1)],
        background=True, name="idx_seq_project_deleted",
    )
    # safety_equipment_checks — 2 (7yr retention-critical)
    await db.safety_equipment_checks.create_index(
        [("project_id", 1), ("equipment_id", 1), ("performed_at", -1)],
        background=True, name="idx_seqc_project_equip_performed",
    )
    await db.safety_equipment_checks.create_index(
        [("equipment_id", 1), ("check_name", 1)],
        background=True, name="idx_seqc_equip_checkname",
    )
    # induction (batch safety-ind1) — 2 across 2 collections.
    # ONE versioned template doc per org.
    await db.induction_templates.create_index(
        [("org_id", 1)],
        background=True, unique=True, name="uidx_it_org",
    )
    # Snapshots collection stays EMPTY until IND-2 — the unique index
    # existing NOW pins the dedup contract for the snapshot writer.
    await db.induction_content_snapshots.create_index(
        [("org_id", 1), ("template_version", 1), ("language", 1)],
        background=True, unique=True, name="uidx_ics_org_version_lang",
    )

    # qrg1-entry-gate — 3 across 2 collections.
    await db.worker_entry_tokens.create_index(
        [("token", 1)],
        background=True, unique=True, name="uidx_wet_token",
    )
    await db.worker_entry_tokens.create_index(
        [("project_id", 1), ("worker_id", 1)],
        background=True, name="idx_wet_project_worker",
    )
    # single ACTIVE token per (project, worker) — DB-level race guard
    await db.worker_entry_tokens.create_index(
        [("project_id", 1), ("worker_id", 1), ("status", 1)],
        background=True, unique=True, name="uidx_wet_active",
        partialFilterExpression={"status": "active"},
    )
    await db.gate_scan_log.create_index(
        [("project_id", 1), ("ts", -1)],
        background=True, name="idx_gsl_project_ts",
    )
    # qrg1-fix1 B3c — per-worker filtered scan-log queries
    await db.gate_scan_log.create_index(
        [("project_id", 1), ("worker_id", 1), ("ts", -1)],
        background=True, name="idx_gsl_project_worker_ts",
    )

    logger.info("Safety indices ensured (35 total across 13 collections)")
