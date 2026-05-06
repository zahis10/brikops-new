"""Tests for #503 QC → Matrix continuous sync (one-way, item-level).

Coverage (13 tests):
  T1   compute: all-pending → None
  T2   compute: one passed → in_progress
  T3   compute: all passed → completed
  T4   compute: any failed → not_done (red wins)
  T5   compute: stage_closed=True + pending → completed (#478 override)
  T5b  compute: stage_closed=True + fail → not_done (mirror reality)
  T6   helper: floor-scope stage → no sync (D5)
  T7   helper: PM manual edit overwritten by sync, audit appended
  T8   helper: feature flag default OFF → no sync
  T8b  helper: flag explicit "FALSE" → no sync (case-insensitive)
  T10  helper: no items, no existing cell → graceful no-op
  T10b helper: items pending + cell synced → DELETE
  T10c helper: items pending + cell MANUAL → preserved (NOT deleted)
  T11  helper: actor.name=None → audit actor_name="QC sync" (or-fallback)
  extra DB-level smoke for insert path (T2/T3 at write boundary)
  T9   ⭐ endpoint: sync failure does NOT block QC write (BackgroundTasks)
"""
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contractor_ops import qc_router as qcr
from contractor_ops.qc_to_matrix_sync import (
    _compute_matrix_status_from_qc_items,
    sync_qc_stage_to_matrix,
)


def _build_cells_db(existing_cell=None):
    """Build a MagicMock db with execution_matrix_cells methods.
    Captures insert/update/delete payloads in `captured` dict.
    """
    captured = {"insert": None, "update": None, "delete": None}
    db = MagicMock()
    after_state = dict(existing_cell) if existing_cell else None

    async def _find_one(query, projection=None):
        return after_state

    db.execution_matrix_cells.find_one = AsyncMock(side_effect=_find_one)

    async def _insert(doc):
        captured["insert"] = doc
        nonlocal after_state
        after_state = dict(doc)
        return MagicMock(inserted_id="x")
    db.execution_matrix_cells.insert_one = AsyncMock(side_effect=_insert)

    async def _update(filt, payload):
        captured["update"] = (filt, payload)
        return MagicMock(modified_count=1)
    db.execution_matrix_cells.update_one = AsyncMock(side_effect=_update)

    async def _delete(filt):
        captured["delete"] = filt
        return MagicMock(deleted_count=1)
    db.execution_matrix_cells.delete_one = AsyncMock(side_effect=_delete)

    return db, captured


# =====================================================================
# Pure compute tests — fast assertions on the mapping table
# =====================================================================

def test_T1_compute_all_pending_returns_none():
    items = [{"status": "pending"}] * 3
    assert _compute_matrix_status_from_qc_items(items, stage_closed=False) is None


def test_T2_compute_one_passed_in_progress():
    items = [{"status": "pass"}, {"status": "pending"}, {"status": "pending"}]
    assert _compute_matrix_status_from_qc_items(items, stage_closed=False) == "in_progress"


def test_T3_compute_all_passed_completed():
    items = [{"status": "pass"}] * 3
    assert _compute_matrix_status_from_qc_items(items, stage_closed=False) == "completed"


def test_T4_compute_any_failed_not_done():
    """Fail wins over pass + pending — PM sees red immediately."""
    items = [{"status": "pass"}, {"status": "fail"}, {"status": "pending"}]
    assert _compute_matrix_status_from_qc_items(items, stage_closed=False) == "not_done"


def test_T5_compute_override_close_marks_completed():
    """Override-close (#478): items still pending, stage closed → completed.
    Without the closed-branch precedence, sync would return None.
    """
    items = [{"status": "pending"}] * 3
    assert _compute_matrix_status_from_qc_items(items, stage_closed=True) == "completed"


def test_T5b_compute_closed_with_failure_remains_not_done():
    """Stage closed but with a fail → not_done. Mirror reality."""
    items = [{"status": "pass"}, {"status": "fail"}]
    assert _compute_matrix_status_from_qc_items(items, stage_closed=True) == "not_done"


# =====================================================================
# Helper tests with feature flag ON
# =====================================================================

def test_T6_floor_scope_stage_skipped(monkeypatch):
    """scope='floor' → returns None, NO DB calls (D5)."""
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        db, captured = _build_cells_db()
        result = await sync_qc_stage_to_matrix(
            db,
            project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "u1", "name": "PM"},
            qc_items=[{"status": "pass"}, {"status": "pass"}],
            stage_closed=False,
            stage_scope="floor",
        )
        assert result is None
        db.execution_matrix_cells.find_one.assert_not_called()
        assert captured["insert"] is None
        assert captured["update"] is None
        assert captured["delete"] is None

    asyncio.run(run())


def test_T7_pm_manual_edit_overwritten_by_next_qc_with_audit_preserved(monkeypatch):
    """Existing manual cell + sync(fail) → status flips, original audit
    preserved via $push (not $set), pruned to last 50.
    """
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        existing = {
            "id": "cell-1",
            "project_id": "p1", "unit_id": "u1", "stage_id": "s1",
            "status": "completed",
            "note": "PM said done",
            "synced_from_qc": False,
            "audit": [{
                "actor_id": "pm1", "actor_name": "PM",
                "timestamp": "2026-05-01T00:00:00Z",
                "status_before": None, "status_after": "completed",
            }],
        }
        db, captured = _build_cells_db(existing_cell=existing)

        await sync_qc_stage_to_matrix(
            db,
            project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC user"},
            qc_items=[{"status": "fail"}, {"status": "pending"}],
            stage_closed=False,
            stage_scope="unit",
        )

        assert captured["update"] is not None
        filt, payload = captured["update"]
        assert filt == {"id": "cell-1"}
        assert payload["$set"]["status"] == "not_done"
        assert payload["$set"]["synced_from_qc"] is True
        assert payload["$set"]["last_qc_sync_at"] is not None
        push = payload["$push"]["audit"]
        assert "$each" in push
        assert push["$slice"] == -50
        appended = push["$each"][0]
        assert appended["status_before"] == "completed"
        assert appended["status_after"] == "not_done"
        assert appended["source"] == "qc_sync"
        assert appended["actor_id"] == "qc1"

    asyncio.run(run())


def test_T8_feature_flag_off_no_sync(monkeypatch):
    """Flag unset (default 'false') → no sync. Critical safety."""
    monkeypatch.delenv("MATRIX_QC_SYNC_ENABLED", raising=False)

    async def run():
        db, captured = _build_cells_db()
        result = await sync_qc_stage_to_matrix(
            db,
            project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC"},
            qc_items=[{"status": "pass"}] * 3,
            stage_closed=True,
            stage_scope="unit",
        )
        assert result is None
        db.execution_matrix_cells.find_one.assert_not_called()
        assert captured["insert"] is None and captured["update"] is None

    asyncio.run(run())


def test_T8b_feature_flag_explicit_false_case_insensitive(monkeypatch):
    """Flag set to 'FALSE' (uppercase) → no sync. Case-insensitive."""
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "FALSE")

    async def run():
        db, _ = _build_cells_db()
        await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "u1", "name": "PM"},
            qc_items=[{"status": "pass"}], stage_closed=False, stage_scope="unit",
        )
        db.execution_matrix_cells.find_one.assert_not_called()

    asyncio.run(run())


def test_extra_insert_new_cell_when_first_qc_activity(monkeypatch):
    """DB-level smoke for T2/T3 — inserts new cell shape correctly."""
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        db, captured = _build_cells_db(existing_cell=None)
        await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC"},
            qc_items=[{"status": "pass"}] * 3,
            stage_closed=False, stage_scope="unit",
        )
        assert captured["insert"] is not None
        doc = captured["insert"]
        assert doc["status"] == "completed"
        assert doc["synced_from_qc"] is True
        assert doc["last_qc_sync_at"] is not None
        assert doc["audit"][0]["source"] == "qc_sync"
        assert doc["audit"][0]["status_before"] is None
        assert doc["audit"][0]["status_after"] == "completed"
        assert "id" in doc and len(doc["id"]) > 0

    asyncio.run(run())


def test_T10_no_items_no_existing_cell_graceful(monkeypatch):
    """No items, no existing cell → no DB writes."""
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        db, captured = _build_cells_db(existing_cell=None)
        result = await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC"},
            qc_items=[],
            stage_closed=False, stage_scope="unit",
        )
        assert result is None
        assert captured["insert"] is None
        assert captured["update"] is None
        assert captured["delete"] is None

    asyncio.run(run())


def test_T10b_delete_synced_only_cell_when_items_clear(monkeypatch):
    """All items pending + existing sync-only cell → DELETE."""
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        existing = {
            "id": "cell-2",
            "project_id": "p1", "unit_id": "u1", "stage_id": "s1",
            "status": "completed",
            "synced_from_qc": True,
            "audit": [],
        }
        db, captured = _build_cells_db(existing_cell=existing)
        await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC"},
            qc_items=[{"status": "pending"}],
            stage_closed=False, stage_scope="unit",
        )
        assert captured["delete"] == {"id": "cell-2"}

    asyncio.run(run())


def test_T10c_preserve_manual_cell_when_items_clear(monkeypatch):
    """All items pending + cell MANUAL (synced_from_qc=False) → NOT deleted.
    Critical safety: a sync-no-op must not nuke a PM's manual entry.
    """
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        existing = {
            "id": "cell-3",
            "project_id": "p1", "unit_id": "u1", "stage_id": "s1",
            "status": "partial",
            "synced_from_qc": False,
            "audit": [],
        }
        db, captured = _build_cells_db(existing_cell=existing)
        await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC"},
            qc_items=[{"status": "pending"}],
            stage_closed=False, stage_scope="unit",
        )
        assert captured["delete"] is None
        assert captured["update"] is None
        assert captured["insert"] is None

    asyncio.run(run())


def test_T11_actor_name_none_falls_back_to_qc_sync(monkeypatch):
    """actor={'id':'u1','name':None} → audit.actor_name='QC sync'.
    Catches dict.get(key, default) Python gotcha — only `or` handles
    explicit None values.
    """
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        db, captured = _build_cells_db(existing_cell=None)
        await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "u1", "name": None},
            qc_items=[{"status": "pass"}, {"status": "pass"}],
            stage_closed=False, stage_scope="unit",
        )
        assert captured["insert"] is not None
        audit_entry = captured["insert"]["audit"][0]
        assert audit_entry["actor_name"] == "QC sync", (
            f"Expected 'QC sync' fallback for None name, got {audit_entry['actor_name']!r}"
        )

    asyncio.run(run())


# =====================================================================
# T9 — ⭐ MOST CRITICAL: sync failure must NOT block QC writes
# =====================================================================

def test_T9_sync_failure_does_not_block_qc_write(monkeypatch, caplog):
    """When sync_qc_stage_to_matrix raises, the QC PATCH endpoint:
      - still returns the updated item dict (no HTTPException)
      - background task swallows the exception
      - logs warning '[#503] QC→matrix sync failed ...'
    Proves the BackgroundTasks try/except wrapper actually protects QC.
    """
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")
    caplog.set_level(logging.WARNING, logger="contractor_ops.qc_router")

    async def run():
        from fastapi import BackgroundTasks

        run_doc = {
            "id": "r1", "project_id": "p1", "floor_id": "f1",
            "unit_id": "u1",
            "template_id": "tpl1",
            "stage_statuses": {"s1": "draft"},
        }
        item_doc_pre = {
            "id": "i1", "run_id": "r1", "stage_id": "s1",
            "item_id": "ti1", "unit_id": "u1",
            "status": "pending", "note": "", "photos": ["url"],
        }
        item_doc_post = {**item_doc_pre, "status": "pass"}
        tpl = {
            "id": "tpl1",
            "stages": [{
                "id": "s1", "title": "ריצוף", "scope": "unit",
                "items": [{"id": "ti1", "title": "סעיף 1"}],
            }],
        }

        db = MagicMock()
        db.qc_runs.find_one = AsyncMock(return_value=run_doc)
        db.qc_items.find_one = AsyncMock(side_effect=[item_doc_pre, item_doc_post])
        db.qc_items.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[item_doc_post])
        db.qc_items.find = MagicMock(return_value=cursor)

        bg = BackgroundTasks()
        body = qcr.QCItemUpdate(status="pass")
        user = {"id": "pm1", "name": "PM", "role": "user"}

        async def _exploding_sync(*args, **kwargs):
            raise RuntimeError("simulated sync explosion")

        with patch.object(qcr, "get_db", return_value=db), \
             patch.object(qcr, "_check_qc_access", new=AsyncMock(return_value="project_manager")), \
             patch.object(qcr, "_get_template", new=AsyncMock(return_value=tpl)), \
             patch.object(qcr, "_audit", new=AsyncMock()), \
             patch.object(qcr, "sync_qc_stage_to_matrix", new=AsyncMock(side_effect=_exploding_sync)):
            result = await qcr.update_qc_item(
                run_id="r1", item_id="i1", update=body,
                background_tasks=bg, user=user,
            )

        # 1. Endpoint returned successfully
        assert result is not None
        assert result["status"] == "pass"

        # 2. A background task was queued
        assert len(bg.tasks) == 1

        # 3. Manually run the background tasks — must not raise
        await bg()

        # 4. logger.warning was called with the [#503] tag
        warning_messages = [
            r.message for r in caplog.records
            if r.levelno == logging.WARNING and "[#503]" in r.message
        ]
        assert len(warning_messages) >= 1, (
            f"Expected [#503] warning. Got records: "
            f"{[(r.levelname, r.message) for r in caplog.records]}"
        )

    asyncio.run(run())
