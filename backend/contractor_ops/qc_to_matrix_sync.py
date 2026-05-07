"""QC → Matrix continuous sync (one-way, stage-level).

Batch #503 — Phase A. Per Zahi 2026-05-06: PMs maintain duplicate state
in QC and the Execution Matrix today, and inevitably abandon one. This
module bridges them: any QC item update or stage decision projects
into the matrix cell for (unit_id, stage_id).

Direction lock (D1, PERMANENT): QC → Matrix only. The reverse direction
will never be implemented — QC carries photo-evidence requirements that
matrix edits would compromise.

Mapping (D1 #503-followup-2, stage-level — Zahi 2026-05-06):
  stage_status="approved"             → completed       (green)
  stage_status="approved_via_override"→ completed       (green)
  stage_status="rejected"             → not_done        (red)
  stage_status="pending_review"       → pending_review  (orange)
  stage_status="reopened"             → (fall-through)  see below
  stage_status="in_progress"          → (fall-through)  see below
  ANY item touched (pass|fail)        → in_progress     (blue)
  no items + no status                → None            (empty cell)

#503-followup-3 — "reopened" handling: when a senior reopens a
previously-decided stage (or PM rejects an individual item which
cascades stage to "reopened"), the stage decision is discarded and
the cell should reflect current item activity. The fall-through
below handles this correctly — no special case needed: if any item
is touched it returns "in_progress", otherwise None (empty cell).

NOTE: "ready_for_work" (#503-followup-3) is MANUAL-only — it never
appears as a sync output. PMs set it via CellEditDialog. If QC
later starts tracking the same stage, QC sync overwrites it per D3
("QC always wins").

Reasoning (Zahi quote): "מבחינתי מרגע שיש סעיף אחד בתוך בקרת הביצוע
שהוכנס, זה בעבודה. רק אם כל הסעיפים הסתיימו והסעיף הגדול אושר על ידי
מי שיכול לאשר, מתעדכן למאושר. אותו דבר לגבי לא תקין, רק אחרי שבסעיף
הראשי הגדול הוא לא תקין הוא יראה את זה."

→ Matrix is now outcome-driven (PM-level visibility) instead of
  item-detail-driven. A single failing item does NOT paint the cell red
  any more — red appears only after a senior officially rejects the
  stage.

Conflict resolution (D3): QC always wins. Manual matrix edits on
QC-template stages are transient — overwritten on next QC change.

Resilience: callers MUST wrap calls in try/except. Sync failure must
NEVER block QC writes — matrix is auxiliary, QC is the source of truth.

Feature flag: MATRIX_QC_SYNC_ENABLED (env var, default "false").
Phased rollout — code deploys safely with sync OFF, then ops flips
flag in staging → smoke 24h → flip in prod during low-traffic window.
"""
import os
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_matrix_status_from_qc(items, stage_status):
    """Pure function — compute matrix status from QC items + stage status.

    `items` — list of qc_item dicts (only the .status field is used).
    `stage_status` — value from run["stage_statuses"][stage_id].
                     One of {None, "in_progress", "pending_review",
                     "approved", "approved_via_override", "rejected"}.

    Returns one of {"completed", "in_progress", "not_done",
                    "pending_review"} or None (empty cell / no-op).

    Stage-level mapping (D1 #503-followup-2):
      approved / approved_via_override → completed
      rejected                         → not_done
      pending_review                   → pending_review (NEW)
      any item touched (pass|fail)     → in_progress
      nothing                          → None

    NOTE on QC item status values: codebase uses "pass" / "fail" /
    "pending" (NOT "passed" / "failed" as the original spec drafted).
    Authoritative source: VALID_QC_STATUSES in qc_router.py L1191.
    """
    # Stage-level outcome wins (D1)
    if stage_status in ("approved", "approved_via_override"):
        return "completed"
    if stage_status == "rejected":
        return "not_done"
    if stage_status == "pending_review":
        return "pending_review"

    # #503-followup-3 — "reopened" and "in_progress" stage statuses
    # intentionally fall through to the item-level activity check
    # below: a reopened stage is "back to work", so the cell should
    # reflect current item activity (in_progress if any item touched,
    # else None).

    # Open-work flow — any item activity at all means "in progress"
    if any(i.get("status") in ("pass", "fail") for i in items):
        return "in_progress"

    # Nothing touched
    return None


async def sync_qc_stage_to_matrix(
    db,
    *,
    project_id: str,
    unit_id: str,
    stage_id: str,
    actor: dict,
    qc_items: list,
    stage_status: str = None,
    stage_scope: str = "unit",
):
    """Compute matrix status from QC items + stage_status and upsert
    into execution_matrix_cells. Returns the resulting cell dict, or
    None if no sync was applied (flag off, untouched stage with no
    sync-only cell to delete, etc.).

    Idempotent — safe to call multiple times for the same state.
    Audit array is pruned to the last 50 entries to prevent unbounded
    growth from rapid-fire QC updates.

    `stage_status` (#503-followup-2) — caller passes the value from
    `run["stage_statuses"][stage_id]`. Replaces the previous
    `stage_closed: bool` parameter. None means no decision recorded
    yet (in which case mapping falls back to item-level activity).

    `stage_scope` retained for caller introspection / future logic;
    helper itself is scope-agnostic — caller is responsible for
    passing the right unit_id (resolved via _resolve_unit_ids_for_sync
    in qc_router for floor-scope stages).
    """
    # FEATURE FLAG — default OFF for phased rollout (V6 of spec).
    # Code path is fully wired but never executes until ops sets
    # MATRIX_QC_SYNC_ENABLED=true in env. Allows safe deploy.
    if os.getenv("MATRIX_QC_SYNC_ENABLED", "false").lower() != "true":
        return None

    new_status = _compute_matrix_status_from_qc(qc_items, stage_status)

    cell = await db.execution_matrix_cells.find_one({
        "project_id": project_id,
        "unit_id": unit_id,
        "stage_id": stage_id,
    })

    now = _now()
    actor_id = actor.get("id") or "system"
    # CRITICAL: use `or` not .get(default) — actor.get("name") returns
    # None if name=None was explicitly set (T11 catches this gotcha).
    actor_name = actor.get("name") or "QC sync"

    if new_status is None:
        # Untouched stage with sync-only cell → delete it (return cell
        # to "empty" UI). Manual cells (synced_from_qc=False) are
        # preserved — T10c verifies this branch.
        if cell and cell.get("synced_from_qc"):
            await db.execution_matrix_cells.delete_one({"id": cell["id"]})
        return None

    audit_entry = {
        "actor_id": actor_id,
        "actor_name": actor_name,
        "timestamp": now,
        "status_before": cell.get("status") if cell else None,
        "status_after": new_status,
        "source": "qc_sync",
        "stage_status": stage_status,  # #503-followup-2 — debug aid
    }

    if cell:
        await db.execution_matrix_cells.update_one(
            {"id": cell["id"]},
            {
                "$set": {
                    "status": new_status,
                    "synced_from_qc": True,
                    "last_qc_sync_at": now,
                    "last_updated_at": now,
                    "last_updated_by": actor_id,
                },
                # AUDIT PRUNING — keep last 50 entries (PMs may rapid-
                # fire QC updates, producing many audit entries per
                # cell over time).
                "$push": {
                    "audit": {"$each": [audit_entry], "$slice": -50},
                },
            },
        )
    else:
        await db.execution_matrix_cells.insert_one({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "unit_id": unit_id,
            "stage_id": stage_id,
            "status": new_status,
            "note": None,
            "text_value": None,
            "synced_from_qc": True,
            "last_qc_sync_at": now,
            "last_updated_at": now,
            "last_updated_by": actor_id,
            "created_at": now,
            "audit": [audit_entry],
        })

    return await db.execution_matrix_cells.find_one(
        {
            "project_id": project_id,
            "unit_id": unit_id,
            "stage_id": stage_id,
        },
        {"_id": 0},
    )
