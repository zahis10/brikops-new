"""QC → Matrix continuous sync (one-way, item-level).

Batch #503 — Phase A. Per Zahi 2026-05-06: PMs maintain duplicate state
in QC and the Execution Matrix today, and inevitably abandon one. This
module bridges them: any QC item update for a unit-scope stage is
projected into the matrix cell for (unit_id, stage_id).

Direction lock (D1, PERMANENT): QC → Matrix only. The reverse direction
will never be implemented — QC carries photo-evidence requirements that
matrix edits would compromise.

Mapping (D2, item-level continuous):
  stage_closed (approved/override) AND any item failed → not_done
  stage_closed AND no failures                          → completed
  stage open AND any item failed                        → not_done
  stage open AND no items touched                       → None  (no-op /
                                                                 delete
                                                                 sync-only
                                                                 cell)
  stage open AND all items pass                         → completed
  stage open AND mix of pass + pending (no fail)        → in_progress

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


def _compute_matrix_status_from_qc_items(items, stage_closed: bool):
    """Pure function — compute matrix status from a list of QC items.

    Returns one of {"completed", "in_progress", "not_done"} or None if
    no sync should happen (untouched stage, no items).

    NOTE on QC item status values: codebase uses "pass" / "fail" /
    "pending" (NOT "passed" / "failed" as the original spec drafted).
    Authoritative source: VALID_QC_STATUSES in qc_router.py L1191.
    Spec-drift A documented in review.txt + plan.

    `stage_closed` semantics (spec-drift B): True iff the stage is
    approved (natural close OR override-close per #478). The original
    spec used `run.get("closed")` but the codebase tracks closure
    per-stage in `run["stage_statuses"][stage_id] == "approved"`.
    Caller derives the bool. Closed always overrides item-level
    continuous logic — override-close marks every item "pass", but a
    stage that closed with at least one fail still surfaces as
    not_done so the matrix mirrors reality.
    """
    if stage_closed:
        if any(i.get("status") == "fail" for i in items):
            return "not_done"
        return "completed"

    # Stage is open — item-level continuous logic
    if any(i.get("status") == "fail" for i in items):
        return "not_done"  # red on first failure
    if not items:
        return None
    passed = [i for i in items if i.get("status") == "pass"]
    if not passed:
        return None  # all pending — leave cell empty
    if len(passed) == len(items):
        return "completed"
    return "in_progress"


async def sync_qc_stage_to_matrix(
    db,
    *,
    project_id: str,
    unit_id: str,
    stage_id: str,
    actor: dict,
    qc_items: list,
    stage_closed: bool = False,
    stage_scope: str = "unit",
):
    """Compute matrix status from QC items and upsert into
    execution_matrix_cells. Returns the resulting cell dict, or None
    if no sync was applied (flag off, floor-scope stage, or empty
    state with no existing sync-only cell to delete).

    Idempotent — safe to call multiple times for the same state.
    Audit array is pruned to the last 50 entries to prevent unbounded
    growth from rapid-fire QC updates.
    """
    # FEATURE FLAG — default OFF for phased rollout (V6 of spec).
    # Code path is fully wired but never executes until ops sets
    # MATRIX_QC_SYNC_ENABLED=true in env. Allows safe deploy.
    if os.getenv("MATRIX_QC_SYNC_ENABLED", "false").lower() != "true":
        return None

    # D5 — only unit-scope stages sync. Floor-scope stages (e.g.
    # "אישור סומסום בקומה") deferred to a follow-up batch — they need
    # multi-cell update logic.
    if stage_scope != "unit":
        return None

    new_status = _compute_matrix_status_from_qc_items(qc_items, stage_closed)

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
