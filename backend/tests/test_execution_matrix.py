"""Tests for Execution Matrix Phase 1 backend (Batch Execution Matrix, 2026-05-04).

Covers: stage resolution, RBAC (view + edit + approver D4), cell update + audit
chain, saved views per-user isolation, defensive status validation.

Pattern mirrors test_qc_override_close.py — AsyncMock + MagicMock + patch.object.
No real DB / FastAPI client — direct call to router functions with mocked deps.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import pytest

from contractor_ops import execution_matrix_router as emr
from contractor_ops.schemas import (
    MatrixStagesUpdate,
    MatrixStageCreate,
    MatrixCellUpdate,
    MatrixSavedViewCreate,
    MatrixSavedViewFilters,
)


# =====================================================================
# Cursor / DB mocks
# =====================================================================

class _AsyncCursor:
    """Minimal async cursor — supports `async for`, .to_list, .sort."""
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        async def gen():
            for it in self._items:
                yield it
        return gen()

    async def to_list(self, _n=None):
        return list(self._items)

    def sort(self, *_args, **_kwargs):
        return self


def _mk_db(
    *,
    matrix_config=None,
    units=None,
    floors=None,
    buildings=None,
    cells=None,
    approvers=None,
    views=None,
    existing_view=None,
):
    """Build a MagicMock DB with all collections used by the matrix router."""
    db = MagicMock()

    db.execution_matrix.find_one = AsyncMock(return_value=matrix_config)
    db.execution_matrix.insert_one = AsyncMock()
    db.execution_matrix.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    db.units.find = MagicMock(return_value=_AsyncCursor(units or []))
    db.units.find_one = AsyncMock(return_value=({"id": "u1", "project_id": "p1"} if units is None else (units[0] if units else None)))

    db.floors.find = MagicMock(return_value=_AsyncCursor(floors or []))
    db.buildings.find = MagicMock(return_value=_AsyncCursor(buildings or []))

    db.execution_matrix_cells.find = MagicMock(return_value=_AsyncCursor(cells or []))
    db.execution_matrix_cells.find_one = AsyncMock(return_value=None)
    db.execution_matrix_cells.insert_one = AsyncMock()
    db.execution_matrix_cells.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    db.project_approvers.find = MagicMock(return_value=_AsyncCursor(approvers or []))

    db.execution_matrix_views.find = MagicMock(return_value=_AsyncCursor(views or []))
    db.execution_matrix_views.find_one = AsyncMock(return_value=existing_view)
    db.execution_matrix_views.insert_one = AsyncMock()
    db.execution_matrix_views.update_one = AsyncMock(return_value=MagicMock(matched_count=(1 if existing_view else 0)))

    return db


def _mk_tpl(stages):
    return {"id": "tpl1", "stages": stages}


# =====================================================================
# 1. GET /matrix — stage resolution
# =====================================================================

def test_get_matrix_returns_resolved_stages():
    """Base + custom merged, sorted by order; base_stages_removed filtered out."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [
                {"id": "c1", "title": "תוספת", "type": "status", "order": 50},
            ],
            "base_stages_removed": ["s2"],
            "deletedAt": None,
        }
        tpl = _mk_tpl([
            {"id": "s1", "title": "ריצוף", "scope": "unit", "order": 10},
            {"id": "s2", "title": "אינסטלציה", "scope": "unit", "order": 20},
            {"id": "s3", "title": "חשמל", "scope": "floor", "order": 30},
        ])
        db = _mk_db(matrix_config=matrix_config, units=[], floors=[], cells=[])
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            res = await emr.get_matrix("p1", user={"id": "pm1"})

        stage_ids = [s["id"] for s in res["stages"]]
        # orders: s1=10, s3=30, c1=50 → sort by order ascending
        assert stage_ids == ["s1", "s3", "c1"], f"expected [s1,s3,c1] got {stage_ids}"
        assert res["stages"][0]["source"] == "base"
        assert res["stages"][2]["source"] == "custom"
        assert res["permissions"]["can_view"] is True
        assert res["permissions"]["can_edit"] is True
        # #485 — backend exposes floors metadata for frontend
        assert "floors" in res, "Response must include floors metadata"
        assert isinstance(res["floors"], list)
        # #486 — backend exposes buildings metadata for frontend
        assert "buildings" in res, "Response must include buildings metadata"
        assert isinstance(res["buildings"], list)
    asyncio.run(run())


def test_get_matrix_unit_sort_by_building():
    """#486 — units sorted by (building_sort_index, floor_number, unit_no_num).
    Building dimension takes precedence: all of building A renders first,
    then all of building B."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([
            {"id": "s1", "title": "ריצוף", "scope": "unit", "order": 10},
        ])
        # Buildings: A (sort_index=1), B (sort_index=2)
        buildings = [
            {"id": "bA", "project_id": "p1", "name": "מגדל A", "sort_index": 1},
            {"id": "bB", "project_id": "p1", "name": "מגדל B", "sort_index": 2},
        ]
        # Floors: 2 per building
        floors = [
            {"id": "f-a1", "project_id": "p1", "building_id": "bA", "floor_number": 1},
            {"id": "f-a2", "project_id": "p1", "building_id": "bA", "floor_number": 2},
            {"id": "f-b1", "project_id": "p1", "building_id": "bB", "floor_number": 1},
            {"id": "f-b2", "project_id": "p1", "building_id": "bB", "floor_number": 2},
        ]
        # Units: interleaved insertion order
        units = [
            {"id": "u1", "project_id": "p1", "building_id": "bB", "floor_id": "f-b1", "unit_no": "1"},
            {"id": "u2", "project_id": "p1", "building_id": "bA", "floor_id": "f-a1", "unit_no": "1"},
            {"id": "u3", "project_id": "p1", "building_id": "bA", "floor_id": "f-a2", "unit_no": "1"},
            {"id": "u4", "project_id": "p1", "building_id": "bB", "floor_id": "f-b2", "unit_no": "1"},
        ]
        db = _mk_db(matrix_config=matrix_config, units=units, floors=floors,
                    buildings=buildings, cells=[])
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            res = await emr.get_matrix("p1", user={"id": "pm1"})

        ids = [u["id"] for u in res["units"]]
        # Building A first (floors 1→2), then Building B (floors 1→2)
        assert ids == ["u2", "u3", "u1", "u4"], \
            f"expected ['u2','u3','u1','u4'] got {ids}"
        assert "buildings" in res
        assert len(res["buildings"]) == 2
    asyncio.run(run())


def test_get_matrix_unit_sort_numeric():
    """#485 — units sorted numerically by unit_no, not lexicographically.
    Expected: '1', '2', '10', '11', '20' — NOT '1', '10', '11', '2', '20'."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([
            {"id": "s1", "title": "ריצוף", "scope": "unit", "order": 10},
        ])
        units = [
            {"id": "u-20", "project_id": "p1", "floor_id": "f1", "unit_no": "20"},
            {"id": "u-2",  "project_id": "p1", "floor_id": "f1", "unit_no": "2"},
            {"id": "u-11", "project_id": "p1", "floor_id": "f1", "unit_no": "11"},
            {"id": "u-1",  "project_id": "p1", "floor_id": "f1", "unit_no": "1"},
            {"id": "u-10", "project_id": "p1", "floor_id": "f1", "unit_no": "10"},
        ]
        floors = [{"id": "f1", "project_id": "p1", "floor_number": 1}]
        db = _mk_db(matrix_config=matrix_config, units=units, floors=floors, cells=[])
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            res = await emr.get_matrix("p1", user={"id": "pm1"})

        order = [u["unit_no"] for u in res["units"]]
        assert order == ["1", "2", "10", "11", "20"], \
            f"expected numeric sort ['1','2','10','11','20'] got {order}"
    asyncio.run(run())


def test_get_matrix_unit_sort_numeric_building_names():
    """#489 — buildings named with pure digits ("8","9","10","11") sort
    numerically, not lexicographically. Regression guard mirroring #485's
    unit_no fix at the building-name level. All buildings share the same
    sort_index so the numeric tiebreak is what's exercised."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([
            {"id": "s1", "title": "ריצוף", "scope": "unit", "order": 10},
        ])
        # Buildings inserted in lex order ("10" first) — without the fix
        # the matrix would render them in that order.
        buildings = [
            {"id": "b10", "project_id": "p1", "name": "10", "sort_index": 0},
            {"id": "b11", "project_id": "p1", "name": "11", "sort_index": 0},
            {"id": "b8",  "project_id": "p1", "name": "8",  "sort_index": 0},
            {"id": "b9",  "project_id": "p1", "name": "9",  "sort_index": 0},
        ]
        floors = [
            {"id": "f-10", "project_id": "p1", "building_id": "b10", "floor_number": 1},
            {"id": "f-11", "project_id": "p1", "building_id": "b11", "floor_number": 1},
            {"id": "f-8",  "project_id": "p1", "building_id": "b8",  "floor_number": 1},
            {"id": "f-9",  "project_id": "p1", "building_id": "b9",  "floor_number": 1},
        ]
        units = [
            {"id": "u-10", "project_id": "p1", "building_id": "b10", "floor_id": "f-10", "unit_no": "1"},
            {"id": "u-11", "project_id": "p1", "building_id": "b11", "floor_id": "f-11", "unit_no": "1"},
            {"id": "u-8",  "project_id": "p1", "building_id": "b8",  "floor_id": "f-8",  "unit_no": "1"},
            {"id": "u-9",  "project_id": "p1", "building_id": "b9",  "floor_id": "f-9",  "unit_no": "1"},
        ]
        db = _mk_db(matrix_config=matrix_config, units=units, floors=floors,
                    buildings=buildings, cells=[])
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            res = await emr.get_matrix("p1", user={"id": "pm1"})

        ids = [u["id"] for u in res["units"]]
        # Numeric building order: 8, 9, 10, 11 (NOT 10, 11, 8, 9)
        assert ids == ["u-8", "u-9", "u-10", "u-11"], \
            f"expected numeric building sort ['u-8','u-9','u-10','u-11'] got {ids}"
    asyncio.run(run())


def test_get_matrix_blocks_contractor():
    """Contractor → 403 on GET /matrix."""
    async def run():
        db = _mk_db(matrix_config=None)
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="contractor")), \
             patch.object(emr, "_is_super_admin", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await emr.get_matrix("p1", user={"id": "c1"})
            assert exc_info.value.status_code == 403
    asyncio.run(run())


# =====================================================================
# 2. PATCH /stages
# =====================================================================

def test_update_stages_adds_custom():
    """custom_stages_added → DB write contains new custom with assigned id+order."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([{"id": "s1", "title": "ריצוף", "order": 10}])
        db = _mk_db(matrix_config=matrix_config)
        captured = {}

        async def _capture_update(filt, payload):
            captured["filt"] = filt
            captured["payload"] = payload
            return MagicMock(matched_count=1)
        db.execution_matrix.update_one = AsyncMock(side_effect=_capture_update)

        payload = MatrixStagesUpdate(
            custom_stages_added=[MatrixStageCreate(title="תוספת חדשה", type="status")]
        )
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)), \
             patch.object(emr, "_audit", new=AsyncMock()):
            await emr.update_stages("p1", payload, user={"id": "pm1"})

        sets = captured["payload"]["$set"]
        assert "custom_stages" in sets
        assert len(sets["custom_stages"]) == 1
        cs = sets["custom_stages"][0]
        assert cs["title"] == "תוספת חדשה"
        assert cs["type"] == "status"
        assert cs["created_by"] == "pm1"
        assert cs["id"].startswith("custom_")
    asyncio.run(run())


def test_update_stages_removes_base():
    """base_stages_removed → next GET filters them out."""
    async def run():
        config_before = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        config_after = {**config_before, "base_stages_removed": ["s2"]}
        tpl = _mk_tpl([
            {"id": "s1", "title": "ריצוף", "order": 10},
            {"id": "s2", "title": "אינסטלציה", "order": 20},
        ])

        db = _mk_db(matrix_config=config_before)
        db.execution_matrix.find_one = AsyncMock(side_effect=[config_before, config_after])

        payload = MatrixStagesUpdate(base_stages_removed=["s2"])
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)), \
             patch.object(emr, "_audit", new=AsyncMock()):
            res = await emr.update_stages("p1", payload, user={"id": "pm1"})

        stage_ids = [s["id"] for s in res["stages"]]
        assert stage_ids == ["s1"], f"expected [s1] got {stage_ids}"
    asyncio.run(run())


def test_update_stages_blocks_non_approver():
    """site_manager (not PM, not in approvers) → 403."""
    async def run():
        db = _mk_db(matrix_config=None, approvers=[])
        payload = MatrixStagesUpdate(custom_stages_added=[MatrixStageCreate(title="x")])
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="site_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await emr.update_stages("p1", payload, user={"id": "sm1"})
            assert exc_info.value.status_code == 403
    asyncio.run(run())


# =====================================================================
# 3. PUT /cells
# =====================================================================

def test_update_cell_creates_with_audit():
    """No existing cell → INSERT with 1 audit entry, status set."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([{"id": "s1", "title": "ריצוף", "order": 10}])
        db = _mk_db(matrix_config=matrix_config)
        db.units.find_one = AsyncMock(return_value={"id": "u1", "project_id": "p1"})
        db.execution_matrix_cells.find_one = AsyncMock(return_value=None)
        captured = {}

        async def _capture_insert(doc):
            captured["doc"] = doc
        db.execution_matrix_cells.insert_one = AsyncMock(side_effect=_capture_insert)

        payload = MatrixCellUpdate(status="completed", note="גמור")
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            res = await emr.update_cell("p1", "u1", "s1", payload, user={"id": "pm1", "name": "דני"})

        assert res["status"] == "completed"
        assert res["note"] == "גמור"
        assert captured["doc"]["status"] == "completed"
        assert len(captured["doc"]["audit"]) == 1
        a = captured["doc"]["audit"][0]
        assert a["actor_id"] == "pm1"
        assert a["actor_name"] == "דני"
        assert a["status_before"] is None
        assert a["status_after"] == "completed"
    asyncio.run(run())


def test_update_cell_appends_audit_on_change():
    """Existing cell → UPDATE with audit grown by +1, status_before/after correct."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([{"id": "s1", "title": "ריצוף", "order": 10}])
        existing_cell = {
            "id": "cell1", "project_id": "p1", "unit_id": "u1", "stage_id": "s1",
            "status": "in_progress", "note": "התחלנו",
            "audit": [{"actor_id": "pm1", "actor_name": "דני", "timestamp": "t0",
                       "status_before": None, "status_after": "in_progress",
                       "note_before": None, "note_after": "התחלנו",
                       "text_before": None, "text_after": None}],
        }
        db = _mk_db(matrix_config=matrix_config)
        db.units.find_one = AsyncMock(return_value={"id": "u1", "project_id": "p1"})
        db.execution_matrix_cells.find_one = AsyncMock(return_value=existing_cell)
        captured = {}

        async def _capture_update(filt, payload):
            captured["filt"] = filt
            captured["payload"] = payload
            return MagicMock(matched_count=1)
        db.execution_matrix_cells.update_one = AsyncMock(side_effect=_capture_update)

        payload = MatrixCellUpdate(status="completed", note="גמור")
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            await emr.update_cell("p1", "u1", "s1", payload, user={"id": "pm1", "name": "דני"})

        sets = captured["payload"]["$set"]
        assert sets["status"] == "completed"
        assert len(sets["audit"]) == 2
        new_entry = sets["audit"][-1]
        assert new_entry["status_before"] == "in_progress"
        assert new_entry["status_after"] == "completed"
        assert new_entry["note_before"] == "התחלנו"
        assert new_entry["note_after"] == "גמור"
    asyncio.run(run())


def test_invalid_status_value_rejected_400():
    """Bogus status (bypassing Pydantic) → 400. DB unchanged. No audit written."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([{"id": "s1", "title": "ריצוף", "order": 10}])
        db = _mk_db(matrix_config=matrix_config)
        db.units.find_one = AsyncMock(return_value={"id": "u1", "project_id": "p1"})

        # Bypass Pydantic Literal validation by constructing valid then overriding
        payload = MatrixCellUpdate(status=None)
        payload.status = "nonsense_value"  # type: ignore

        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            with pytest.raises(HTTPException) as exc_info:
                await emr.update_cell("p1", "u1", "s1", payload, user={"id": "pm1"})
            assert exc_info.value.status_code == 400

        db.execution_matrix_cells.insert_one.assert_not_called()
        db.execution_matrix_cells.update_one.assert_not_called()
    asyncio.run(run())


def test_cell_history_returns_full_audit_chain():
    """3 sequential updates → 3 audit entries chronological with correct before/after pairs."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([{"id": "s1", "title": "ריצוף", "order": 10}])
        cell_state = {"value": None}

        db = _mk_db(matrix_config=matrix_config)
        db.units.find_one = AsyncMock(return_value={"id": "u1", "project_id": "p1"})

        async def _do_find_one(*_a, **_k):
            return cell_state["value"]
        db.execution_matrix_cells.find_one = AsyncMock(side_effect=_do_find_one)

        async def _do_insert(doc):
            cell_state["value"] = dict(doc)
        db.execution_matrix_cells.insert_one = AsyncMock(side_effect=_do_insert)

        async def _do_update(filt, payload):
            cur = cell_state["value"] or {}
            cur.update(payload["$set"])
            cell_state["value"] = cur
            return MagicMock(matched_count=1)
        db.execution_matrix_cells.update_one = AsyncMock(side_effect=_do_update)

        async def _drive(status):
            with patch.object(emr, "get_db", return_value=db), \
                 patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
                 patch.object(emr, "_is_super_admin", return_value=False), \
                 patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
                await emr.update_cell("p1", "u1", "s1", MatrixCellUpdate(status=status),
                                      user={"id": "pm1", "name": "דני"})

        await _drive("in_progress")
        await _drive("partial")
        await _drive("completed")

        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False):
            res = await emr.get_cell_history("p1", "u1", "s1", user={"id": "pm1"})

        history = res["history"]
        assert len(history) == 3
        assert history[0]["status_before"] is None
        assert history[0]["status_after"] == "in_progress"
        assert history[1]["status_before"] == "in_progress"
        assert history[1]["status_after"] == "partial"
        assert history[2]["status_before"] == "partial"
        assert history[2]["status_after"] == "completed"
    asyncio.run(run())


# =====================================================================
# 4. Saved views — per-user isolation
# =====================================================================

def test_saved_view_create_list_delete_per_user():
    """User A creates → A lists sees it → B lists empty → A deletes → A lists empty."""
    async def run():
        store = {}

        def _list_for(user_id):
            return [v for v in store.values() if v["user_id"] == user_id and v.get("deletedAt") is None]

        db = MagicMock()

        async def _insert(doc):
            store[(doc["user_id"], doc["id"])] = dict(doc)
        db.execution_matrix_views.insert_one = AsyncMock(side_effect=_insert)

        def _find(filt, _proj=None):
            uid = filt["user_id"]
            return _AsyncCursor(_list_for(uid))
        db.execution_matrix_views.find = MagicMock(side_effect=_find)

        async def _find_one(filt, _proj=None):
            for v in store.values():
                if (v["id"] == filt.get("id") and v["user_id"] == filt["user_id"]
                        and v.get("deletedAt") is None):
                    return v
            return None
        db.execution_matrix_views.find_one = AsyncMock(side_effect=_find_one)

        async def _update(filt, payload):
            for v in store.values():
                if (v["id"] == filt.get("id") and v["user_id"] == filt["user_id"]
                        and v.get("deletedAt") is None):
                    v.update(payload["$set"])
                    return MagicMock(matched_count=1)
            return MagicMock(matched_count=0)
        db.execution_matrix_views.update_one = AsyncMock(side_effect=_update)

        payload = MatrixSavedViewCreate(
            title="המבט שלי", icon="⭐",
            filters=MatrixSavedViewFilters(building_ids=["b1"]),
        )
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="project_manager")), \
             patch.object(emr, "_is_super_admin", return_value=False):
            view = await emr.create_view("p1", payload, user={"id": "userA"})
            assert view["title"] == "המבט שלי"

            res_a = await emr.list_views("p1", user={"id": "userA"})
            assert len(res_a["views"]) == 1
            view_id = res_a["views"][0]["id"]

            res_b = await emr.list_views("p1", user={"id": "userB"})
            assert len(res_b["views"]) == 0

            await emr.delete_view("p1", view_id, user={"id": "userA"})

            res_a_after = await emr.list_views("p1", user={"id": "userA"})
            assert len(res_a_after["views"]) == 0
    asyncio.run(run())


# =====================================================================
# 5. Approver edit access — D4 verification
# =====================================================================

def test_approver_can_edit_matrix():
    """Active project_approver (non-PM) can edit cells — confirms D4."""
    async def run():
        matrix_config = {
            "id": "m1", "project_id": "p1",
            "custom_stages": [], "base_stages_removed": [], "deletedAt": None,
        }
        tpl = _mk_tpl([{"id": "s1", "title": "ריצוף", "order": 10}])
        db = _mk_db(
            matrix_config=matrix_config,
            approvers=[{"user_id": "approver1"}],
        )
        db.units.find_one = AsyncMock(return_value={"id": "u1", "project_id": "p1"})

        payload = MatrixCellUpdate(status="completed")
        with patch.object(emr, "get_db", return_value=db), \
             patch.object(emr, "_get_project_role", new=AsyncMock(return_value="management_team")), \
             patch.object(emr, "_is_super_admin", return_value=False), \
             patch.object(emr, "_get_template", new=AsyncMock(return_value=tpl)):
            res = await emr.update_cell("p1", "u1", "s1", payload, user={"id": "approver1", "name": "מאשר"})
        assert res["status"] == "completed"
    asyncio.run(run())
