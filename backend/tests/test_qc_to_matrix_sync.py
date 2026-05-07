"""Tests for #503 QC → Matrix continuous sync (one-way, stage-level).

Coverage (#503 + followup-1 + followup-2):
  T1   compute: no items + no stage_status → None
  T2   compute: any item touched (pass/fail) + no status → in_progress
  T3   compute: stage_status="pending_review" → pending_review (NEW)
  T4   compute: stage_status="approved" → completed
  T5   compute: stage_status="approved_via_override" → completed
  T13  compute: stage_status="rejected" → not_done (NEW)
  T16  compute: pass-then-fail with no status STAYS in_progress (NEW)

  T6   helper: floor-scope single-unit syncs (followup-1 — skip removed)
  T12  helper: floor-scope multi-cell aggregation at helper boundary
  T7   helper: PM manual edit overwritten by sync, audit appended
  T8   helper: feature flag default OFF → no sync
  T8b  helper: flag explicit "FALSE" → no sync (case-insensitive)
  T10  helper: no items, no existing cell → graceful no-op
  T10b helper: items pending + cell synced → DELETE
  T10c helper: items pending + cell MANUAL → preserved (NOT deleted)
  T11  helper: actor.name=None → audit actor_name="QC sync" (or-fallback)
  extra DB-level smoke for insert path

  T14  router: _resolve_unit_ids_for_sync — floor-scope with no item
       unit_ids falls back to db.units.find by floor_id (NEW)
  T15  router: _resolve_unit_ids_for_sync — unit-scope returns [run.unit_id] (NEW)

  T9   ⭐ endpoint: sync failure does NOT block QC write (BackgroundTasks)
"""
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contractor_ops import qc_router as qcr
from contractor_ops.qc_to_matrix_sync import (
    _compute_matrix_status_from_qc,
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
# Pure compute tests — fast assertions on the stage-level mapping
# =====================================================================

def test_T1_compute_no_items_no_status_returns_none():
    """No items + no decision → empty cell."""
    assert _compute_matrix_status_from_qc([], stage_status=None) is None


def test_T2_compute_any_item_touched_in_progress():
    """Any pass/fail item with no stage decision → in_progress (blue)."""
    items = [{"status": "pass"}, {"status": "pending"}]
    assert _compute_matrix_status_from_qc(items, stage_status=None) == "in_progress"
    items_fail = [{"status": "fail"}]
    # #503-followup-2 D1: a single failing item NO LONGER paints red.
    # Red appears only after an official stage rejection.
    assert _compute_matrix_status_from_qc(items_fail, stage_status=None) == "in_progress"


def test_T3_compute_pending_review_status():
    """Submitted for senior approval → orange "ממתין לאישור" (NEW)."""
    items = [{"status": "pass"}] * 3
    assert _compute_matrix_status_from_qc(items, stage_status="pending_review") == "pending_review"
    # Also works with no items present
    assert _compute_matrix_status_from_qc([], stage_status="pending_review") == "pending_review"


def test_T4_compute_approved_status_completed():
    """Senior approved → completed."""
    items = [{"status": "pass"}, {"status": "fail"}]
    # Even with a fail among items, stage-level decision wins.
    assert _compute_matrix_status_from_qc(items, stage_status="approved") == "completed"


def test_T5_compute_approved_via_override_completed():
    """Override-approve (#478) → completed regardless of items."""
    items = [{"status": "pending"}] * 3
    assert _compute_matrix_status_from_qc(items, stage_status="approved_via_override") == "completed"


def test_T13_compute_rejected_status_not_done():
    """Senior rejected → not_done. NEW (#503-followup-2).
    Was Bug 1 in Zahi smoke 2026-05-06 — reject didn't sync at all.
    """
    items = [{"status": "pass"}] * 3
    assert _compute_matrix_status_from_qc(items, stage_status="rejected") == "not_done"
    # Empty items also map to not_done if stage was rejected
    assert _compute_matrix_status_from_qc([], stage_status="rejected") == "not_done"


def test_T16_compute_in_progress_stable_on_item_flip():
    """Once stage is in flight, item flips between pass↔fail keep
    it blue. Red appears ONLY after stage rejection (D1 from Zahi
    quote 2026-05-06).
    """
    # PM marks one item pass → in_progress
    assert _compute_matrix_status_from_qc(
        [{"status": "pass"}], stage_status=None
    ) == "in_progress"
    # PM then marks another item fail → STILL in_progress (no flip to red)
    assert _compute_matrix_status_from_qc(
        [{"status": "pass"}, {"status": "fail"}], stage_status=None
    ) == "in_progress"
    # Stage in_progress as recorded value → still in_progress
    assert _compute_matrix_status_from_qc(
        [{"status": "fail"}], stage_status="in_progress"
    ) == "in_progress"


# =====================================================================
# Helper tests with feature flag ON
# =====================================================================

def test_T6_floor_scope_single_unit_syncs(monkeypatch):
    """#503-followup: floor-scope stages sync correctly when caller
    provides unit_id (drift C aggregation in approve/override; per-
    item unit_id in update_qc_item). Helper is scope-agnostic — the
    D5 skip was removed because 7 of 8 base QC stages defaulted to
    floor scope and never synced.
    """
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        db, captured = _build_cells_db()
        result = await sync_qc_stage_to_matrix(
            db,
            project_id="p1", unit_id="apt1", stage_id="stage_plaster",
            actor={"id": "u1", "name": "PM"},
            qc_items=[{"status": "pass"}, {"status": "pass"}, {"status": "pass"}],
            stage_status="approved",
            stage_scope="floor",  # floor scope must NOT block sync any more
        )
        # Cell created
        assert captured["insert"] is not None
        doc = captured["insert"]
        assert doc["status"] == "completed"
        assert doc["synced_from_qc"] is True
        assert doc["unit_id"] == "apt1"
        assert doc["stage_id"] == "stage_plaster"
        assert result is not None  # helper returns the inserted cell

    asyncio.run(run())


def test_T12_floor_scope_multi_cell_via_caller_aggregation(monkeypatch):
    """#503-followup: when approve/override fires on a floor-scope
    stage with items spanning N units, caller calls helper N times
    (one per distinct unit_id). Each call upserts a separate cell —
    they're independent. Verifies multi-cell aggregation works
    end-to-end at the helper boundary.
    """
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        units = ["apt1", "apt2", "apt3"]
        items_by_unit = {
            "apt1": [{"status": "pass"}, {"status": "pass"}],
            "apt2": [{"status": "pass"}, {"status": "pass"}],
            "apt3": [{"status": "pass"}, {"status": "pass"}],
        }

        inserted_docs = []
        for uid in units:
            db, captured = _build_cells_db(existing_cell=None)
            await sync_qc_stage_to_matrix(
                db,
                project_id="p1",
                unit_id=uid,
                stage_id="stage_plumbing",
                actor={"id": "pm1", "name": "PM"},
                qc_items=items_by_unit[uid],
                stage_status="rejected",  # #503-followup-2: reject path
                stage_scope="floor",
            )
            assert captured["insert"] is not None, f"unit {uid} did not insert"
            inserted_docs.append(captured["insert"])

        # 3 distinct cells, all not_done (rejected), audit per-cell
        assert len(inserted_docs) == 3
        for doc, uid in zip(inserted_docs, units):
            assert doc["unit_id"] == uid
            assert doc["status"] == "not_done"  # stage_status=rejected
            assert doc["synced_from_qc"] is True
            assert doc["stage_id"] == "stage_plumbing"
            assert len(doc["audit"]) == 1
            assert doc["audit"][0]["source"] == "qc_sync"
            assert doc["audit"][0]["status_after"] == "not_done"
            assert doc["audit"][0]["stage_status"] == "rejected"

        # All cell IDs are unique (independent docs)
        assert len({d["id"] for d in inserted_docs}) == 3

    asyncio.run(run())


def test_T7_pm_manual_edit_overwritten_by_next_qc_with_audit_preserved(monkeypatch):
    """Existing manual cell + sync(rejected) → status flips to not_done,
    original audit preserved via $push (not $set), pruned to last 50.
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
            stage_status="rejected",
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
        assert appended["stage_status"] == "rejected"
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
            stage_status="approved",
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
            qc_items=[{"status": "pass"}], stage_status=None, stage_scope="unit",
        )
        db.execution_matrix_cells.find_one.assert_not_called()

    asyncio.run(run())


def test_extra_insert_new_cell_when_first_qc_activity(monkeypatch):
    """DB-level smoke — inserts new cell shape correctly."""
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        db, captured = _build_cells_db(existing_cell=None)
        await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC"},
            qc_items=[{"status": "pass"}] * 3,
            stage_status="approved", stage_scope="unit",
        )
        assert captured["insert"] is not None
        doc = captured["insert"]
        assert doc["status"] == "completed"
        assert doc["synced_from_qc"] is True
        assert doc["last_qc_sync_at"] is not None
        assert doc["audit"][0]["source"] == "qc_sync"
        assert doc["audit"][0]["status_before"] is None
        assert doc["audit"][0]["status_after"] == "completed"
        assert doc["audit"][0]["stage_status"] == "approved"
        assert "id" in doc and len(doc["id"]) > 0

    asyncio.run(run())


def test_T10_no_items_no_existing_cell_graceful(monkeypatch):
    """No items, no existing cell, no decision → no DB writes."""
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        db, captured = _build_cells_db(existing_cell=None)
        result = await sync_qc_stage_to_matrix(
            db, project_id="p1", unit_id="u1", stage_id="s1",
            actor={"id": "qc1", "name": "QC"},
            qc_items=[],
            stage_status=None, stage_scope="unit",
        )
        assert result is None
        assert captured["insert"] is None
        assert captured["update"] is None
        assert captured["delete"] is None

    asyncio.run(run())


def test_T10b_delete_synced_only_cell_when_items_clear(monkeypatch):
    """All items pending + no decision + existing sync-only cell → DELETE."""
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
            stage_status=None, stage_scope="unit",
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
            stage_status=None, stage_scope="unit",
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
            stage_status=None, stage_scope="unit",
        )
        assert captured["insert"] is not None
        audit_entry = captured["insert"]["audit"][0]
        assert audit_entry["actor_name"] == "QC sync", (
            f"Expected 'QC sync' fallback for None name, got {audit_entry['actor_name']!r}"
        )

    asyncio.run(run())


# =====================================================================
# T14/T15 — _resolve_unit_ids_for_sync helper (#503-followup-2)
# =====================================================================

def test_T14_resolve_unit_ids_floor_scope_falls_back_to_db_units(monkeypatch):
    """Bug 2 from Zahi smoke: floor-scope items have no unit_id, run
    has no unit_id either. Helper must query db.units by floor_id.
    """
    async def run():
        db = MagicMock()
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[
            {"id": "apt-101"}, {"id": "apt-102"}, {"id": "apt-103"},
        ])
        db.units.find = MagicMock(return_value=cursor)

        run_doc = {"id": "run1", "floor_id": "f1"}  # no unit_id
        items = [
            {"id": "i1", "status": "pass"},  # no unit_id field
            {"id": "i2", "status": "pass"},
        ]

        result = await qcr._resolve_unit_ids_for_sync(db, run_doc, items, "floor")

        assert sorted(result) == ["apt-101", "apt-102", "apt-103"]
        # Verify the find query shape
        call_args = db.units.find.call_args
        assert call_args[0][0] == {"floor_id": "f1", "archived": {"$ne": True}}

    asyncio.run(run())


def test_T15_resolve_unit_ids_unit_scope_returns_run_unit(monkeypatch):
    """Unit-scope: helper returns just [run.unit_id]. No DB query."""
    async def run():
        db = MagicMock()
        db.units.find = MagicMock()  # should NOT be called

        run_doc = {"id": "run2", "unit_id": "apt-7", "floor_id": "f2"}
        items = [{"id": "i1", "status": "pass"}]

        result = await qcr._resolve_unit_ids_for_sync(db, run_doc, items, "unit")

        assert result == ["apt-7"]
        db.units.find.assert_not_called()

        # Floor-scope with items carrying unit_id should also skip DB
        items_with_uid = [
            {"id": "i1", "unit_id": "apt-A", "status": "pass"},
            {"id": "i2", "unit_id": "apt-B", "status": "fail"},
        ]
        result2 = await qcr._resolve_unit_ids_for_sync(
            db, run_doc, items_with_uid, "floor"
        )
        assert sorted(result2) == ["apt-A", "apt-B"]
        db.units.find.assert_not_called()

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
            "stage_statuses": {"s1": "in_progress"},
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


# =====================================================================
# #503-followup-3 — Submit hook + item-level fix + ready_for_work
# =====================================================================

def test_T17_compute_reopened_with_items_falls_through_to_in_progress():
    """STOP-GATE 0.6 — stage_status="reopened" (set by reject_qc_item
    cascade and reopen_stage endpoint) intentionally falls through to
    item-level activity. If any item is touched (pass/fail), cell goes
    BLUE. This verifies followup-3 D5 fall-through behavior — no
    special case in the mapping is needed.
    """
    # Reopened + at least one item touched → in_progress (BLUE)
    assert _compute_matrix_status_from_qc(
        [{"status": "pass"}], stage_status="reopened"
    ) == "in_progress"
    assert _compute_matrix_status_from_qc(
        [{"status": "fail"}], stage_status="reopened"
    ) == "in_progress"
    assert _compute_matrix_status_from_qc(
        [{"status": "pass"}, {"status": "fail"}, {"status": "pending"}],
        stage_status="reopened",
    ) == "in_progress"


def test_T18_compute_reopened_with_no_items_returns_none():
    """Reopened + nothing touched yet → empty cell. Tests that
    reopening a stage does NOT leave a stale color. The fall-through
    correctly returns None when no item has pass/fail status.
    """
    # Reopened + no items at all
    assert _compute_matrix_status_from_qc(
        [], stage_status="reopened"
    ) is None
    # Reopened + only pending items (e.g. PM cleared all answers)
    assert _compute_matrix_status_from_qc(
        [{"status": "pending"}, {"status": "pending"}],
        stage_status="reopened",
    ) is None


def test_T19_ready_for_work_is_manual_only_never_a_sync_output():
    """ready_for_work is a MANUAL planning state — _compute never
    returns it. PMs set it via CellEditDialog. If QC starts tracking
    the same stage later, sync OVERWRITES per D3 ("QC always wins").

    Also asserts the constant landed in MATRIX_STATUS_VALUES so the
    matrix PATCH validator accepts it.
    """
    from contractor_ops.schemas import MATRIX_STATUS_VALUES, MatrixCellUpdate

    # Constant present
    assert "ready_for_work" in MATRIX_STATUS_VALUES
    assert "pending_review" in MATRIX_STATUS_VALUES  # followup-2 sanity

    # MatrixCellUpdate Literal accepts ready_for_work …
    assert MatrixCellUpdate(status="ready_for_work").status == "ready_for_work"
    # … but REJECTS pending_review (sync-only, manual PATCH must not set)
    with pytest.raises(Exception):  # ValidationError
        MatrixCellUpdate(status="pending_review")

    # Sync mapping never produces ready_for_work
    sync_outputs = {
        _compute_matrix_status_from_qc([], stage_status=None),
        _compute_matrix_status_from_qc([], stage_status="approved"),
        _compute_matrix_status_from_qc([], stage_status="rejected"),
        _compute_matrix_status_from_qc([], stage_status="pending_review"),
        _compute_matrix_status_from_qc([], stage_status="reopened"),
        _compute_matrix_status_from_qc([{"status": "pass"}], stage_status=None),
        _compute_matrix_status_from_qc(
            [{"status": "pass"}], stage_status="reopened"
        ),
    }
    assert "ready_for_work" not in sync_outputs


def test_T20_excel_export_has_ready_for_work_label_and_cyan_fill():
    """followup-3 PART D — Excel export STATUS_LABELS + STATUS_FILLS
    must include ready_for_work with Hebrew label and cyan-100 fill.
    """
    from contractor_ops.execution_matrix_export import (
        STATUS_LABELS, STATUS_FILLS,
    )

    assert STATUS_LABELS.get("ready_for_work") == "מוכן לעבודה"
    fill = STATUS_FILLS.get("ready_for_work")
    assert fill is not None, "ready_for_work missing from STATUS_FILLS"
    # openpyxl PatternFill stores fgColor as Color object; rgb attr is "00CFFAFE"
    fg = fill.fgColor
    rgb = getattr(fg, "rgb", None) or getattr(fg, "value", None) or ""
    assert "CFFAFE" in str(rgb).upper(), (
        f"Expected cyan-100 (CFFAFE), got: {rgb}"
    )


def test_T21_bug_b_floor_shared_items_sync_per_unit(monkeypatch):
    """followup-3 Bug B — floor-shared template items (no unit_id
    field on qc_items docs) must sync to ALL units on the floor, not
    just the one a PATCH happened on. The hook now passes items_all
    when no item carries unit_id.

    Verifies sync_qc_stage_to_matrix is callable per-unit with the
    SHARED items list and produces an identical cell for each unit.
    """
    monkeypatch.setenv("MATRIX_QC_SYNC_ENABLED", "true")

    async def run():
        # Shared items — NO unit_id field (floor-shared template items)
        shared_items = [
            {"id": "i1", "stage_id": "s1", "status": "pass"},
            {"id": "i2", "stage_id": "s1", "status": "pending"},
        ]
        actor = {"id": "pm1", "name": "PM"}

        # Simulate hook behavior — call helper once per unit with
        # the SAME items_all list (since items_have_unit_id is False).
        captured_inserts = []
        for uid in ["apt-101", "apt-102", "apt-103"]:
            db, captured = _build_cells_db()
            await sync_qc_stage_to_matrix(
                db,
                project_id="p1",
                unit_id=uid,
                stage_id="s1",
                actor=actor,
                qc_items=shared_items,
                stage_status=None,  # in_progress flow
                stage_scope="floor",
            )
            captured_inserts.append((uid, captured["insert"]))

        # All 3 units got cells inserted with status=in_progress
        for uid, doc in captured_inserts:
            assert doc is not None, f"unit {uid} got no insert"
            assert doc["unit_id"] == uid
            assert doc["stage_id"] == "s1"
            assert doc["status"] == "in_progress", (
                f"unit {uid} got {doc['status']!r} not 'in_progress'"
            )
            assert doc.get("synced_from_qc") is True

    asyncio.run(run())
