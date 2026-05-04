"""Tests for PM Override close — POST /qc/run/{run_id}/stage/{stage_id}/override-approve.

Spec: project_manager (membership.role) OR super_admin only. Owner / management_team
without project_manager role are rejected with 403. Side effects:
- All items in stage marked 'pass' with marked_via_override=true
- stage_statuses[stage_id] = 'approved'
- stage_actors[stage_id] populated with override metadata + via_override=true
- Audit event 'qc_stage_override_approved'
- Notifications sent (actor filtered out)
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import pytest

from contractor_ops import qc_router as qcr


def _build_db(run_doc, stage_actors_after=None):
    """Common DB mock builder. Returns (db, captured_calls_dict)."""
    captured = {"items_update": None, "run_update": None}
    db = MagicMock()
    db.qc_runs.find_one = AsyncMock(return_value=run_doc)

    async def _items_update(filt, payload):
        captured["items_update"] = (filt, payload)
        return MagicMock(modified_count=3)
    db.qc_items.update_many = AsyncMock(side_effect=_items_update)

    async def _runs_update(filt, payload):
        captured["run_update"] = (filt, payload)
        return MagicMock(modified_count=1)
    db.qc_runs.update_one = AsyncMock(side_effect=_runs_update)

    return db, captured


def test_override_approve_succeeds_for_project_manager():
    """PM (membership.role='project_manager') closes stage with override; items + statuses + audit fired."""
    async def run():
        run_doc = {
            "id": "r1", "project_id": "p1", "floor_id": "f1", "building_id": "b1",
            "template_id": "tpl1", "stage_statuses": {"s1": "draft"}, "stage_actors": {},
        }
        tpl = {"id": "tpl1", "stages": [{"id": "s1", "title": "ריצוף", "items": [{"id": "i1"}, {"id": "i2"}]}]}
        body = qcr.OverrideApproveBody(reason="נכנסתי לפרויקט באמצע — השלב הסתיים פיזית לפני התיעוד")
        user = {"id": "pm1", "name": "מנהל פרויקט", "role": "user"}

        db, captured = _build_db(run_doc)
        audit_calls = []
        async def _audit_capture(*args, **kwargs):
            audit_calls.append((args, kwargs))
        notif_calls = []
        async def _notif_capture(*args, **kwargs):
            notif_calls.append((args, kwargs))

        with patch.object(qcr, "get_db", return_value=db), \
             patch.object(qcr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(qcr, "_is_super_admin", return_value=False), \
             patch.object(qcr, "_get_template", new=AsyncMock(return_value=tpl)), \
             patch.object(qcr, "_audit", new=AsyncMock(side_effect=_audit_capture)), \
             patch.object(qcr, "_get_stage_recipients", new=AsyncMock(return_value=[{"user_id": "other1"}])), \
             patch.object(qcr, "_create_qc_notification", new=AsyncMock(side_effect=_notif_capture)):
            res = await qcr.override_approve_stage("r1", "s1", body, user=user)

        assert res == {"status": "approved", "stage_id": "s1", "via_override": True}

        # Items bulk-updated to pass + marked_via_override
        items_filt, items_payload = captured["items_update"]
        assert items_filt == {"run_id": "r1", "stage_id": "s1"}
        assert items_payload["$set"]["status"] == "pass"
        assert items_payload["$set"]["marked_via_override"] is True
        assert items_payload["$set"]["updated_by"] == "pm1"

        # Run doc updated: stage approved + actors populated with via_override
        run_filt, run_payload = captured["run_update"]
        assert run_filt == {"id": "r1"}
        sets = run_payload["$set"]
        assert sets["stage_statuses.s1"] == "approved"
        assert sets["stage_actors.s1.approved_by"] == "pm1"
        assert sets["stage_actors.s1.via_override"] is True
        assert "נכנסתי לפרויקט" in sets["stage_actors.s1.override_reason"]

        # Audit fired with override action
        assert len(audit_calls) == 1
        a_args, _ = audit_calls[0]
        assert a_args[0] == "qc_stage"
        assert a_args[1] == "s1"
        assert a_args[2] == "qc_stage_override_approved"

        # Notification sent to non-actor recipient with override action
        assert len(notif_calls) == 1
        _, n_kwargs = notif_calls[0]
        assert n_kwargs["action"] == "approved_via_override"

    asyncio.run(run())


def test_override_approve_rejects_owner_and_management_team():
    """role='owner' and role='management_team' both 403 — only strict project_manager permitted."""
    async def run():
        run_doc = {"id": "r1", "project_id": "p1", "floor_id": "f1", "building_id": "b1",
                   "template_id": "tpl1", "stage_statuses": {"s1": "draft"}, "stage_actors": {}}
        body = qcr.OverrideApproveBody(reason="ten chars at least here yes")

        for blocked_role in ("owner", "management_team", "site_manager", "viewer"):
            db, _ = _build_db(run_doc)
            with patch.object(qcr, "get_db", return_value=db), \
                 patch.object(qcr, "_get_project_role", new=AsyncMock(return_value=blocked_role)), \
                 patch.object(qcr, "_is_super_admin", return_value=False):
                with pytest.raises(HTTPException) as exc_info:
                    await qcr.override_approve_stage("r1", "s1", body, user={"id": "u1", "role": "user"})
                assert exc_info.value.status_code == 403, f"role={blocked_role} should be 403"

    asyncio.run(run())


def test_override_approve_blocks_already_approved_and_super_admin_bypass():
    """Already-approved stage → 400. Super_admin (non-PM project role) → succeeds."""
    async def run():
        # Case A: already approved
        run_approved = {"id": "r1", "project_id": "p1", "floor_id": "f1", "building_id": "b1",
                        "template_id": "tpl1", "stage_statuses": {"s1": "approved"}, "stage_actors": {}}
        body = qcr.OverrideApproveBody(reason="ten chars at least here yes")
        db, _ = _build_db(run_approved)
        with patch.object(qcr, "get_db", return_value=db), \
             patch.object(qcr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(qcr, "_is_super_admin", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await qcr.override_approve_stage("r1", "s1", body, user={"id": "pm1", "role": "user"})
            assert exc_info.value.status_code == 400

        # Case B: super_admin bypasses non-PM project role
        run_doc = {"id": "r1", "project_id": "p1", "floor_id": "f1", "building_id": "b1",
                   "template_id": "tpl1", "stage_statuses": {"s1": "ready"}, "stage_actors": {}}
        tpl = {"id": "tpl1", "stages": [{"id": "s1", "title": "ריצוף", "items": [{"id": "i1"}]}]}
        db2, captured = _build_db(run_doc)
        with patch.object(qcr, "get_db", return_value=db2), \
             patch.object(qcr, "_get_project_role", new=AsyncMock(return_value="viewer")), \
             patch.object(qcr, "_is_super_admin", return_value=True), \
             patch.object(qcr, "_get_template", new=AsyncMock(return_value=tpl)), \
             patch.object(qcr, "_audit", new=AsyncMock()), \
             patch.object(qcr, "_get_stage_recipients", new=AsyncMock(return_value=[])), \
             patch.object(qcr, "_create_qc_notification", new=AsyncMock()):
            res = await qcr.override_approve_stage("r1", "s1", body, user={"id": "admin1", "role": "super_admin"})
            assert res["status"] == "approved"
            assert res["via_override"] is True
            assert captured["run_update"][1]["$set"]["stage_actors.s1.via_override"] is True

    asyncio.run(run())
