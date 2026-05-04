"""Tests for execution-control unit-scope-fix — per-stage rollup on /floors/{id}/units-status."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from contractor_ops import qc_router as qcr


def test_floor_units_status_returns_per_stage_rollup():
    """Endpoint returns array of unit-scope stages in template `order`, not just the first."""
    async def run():
        tpl = {
            "id": "tpl1",
            "stages": [
                {"id": "stage_floor_blocks", "title": "בלוקים", "scope": "floor", "order": 1, "items": [{"id": "i1"}]},
                {"id": "stage_kitchen", "title": "מטבחים", "scope": "unit", "order": 10, "items": [{"id": "k1"}]},
                {"id": "stage_tiling", "title": "ריצוף דירה", "scope": "unit", "order": 8, "items": [{"id": "tl_1"}, {"id": "tl_2"}]},
                {"id": "stage_bath", "title": "אמבטיה", "scope": "unit", "order": 9, "items": [{"id": "b1"}]},
            ],
        }
        units = [
            {"id": "u1", "name": "1", "unit_no": "1", "floor_id": "f1", "archived": False},
            {"id": "u2", "name": "2", "unit_no": "2", "floor_id": "f1", "archived": False},
        ]
        unit_runs = [
            {"id": "r1", "unit_id": "u1", "scope": "unit", "stage_statuses": {"stage_tiling": "in_progress"}},
        ]
        items = [
            {"run_id": "r1", "stage_id": "stage_tiling", "status": "pass"},
            {"run_id": "r1", "stage_id": "stage_tiling", "status": "fail"},
        ]

        db = MagicMock()
        db.floors.find_one = AsyncMock(return_value={"id": "f1", "name": "1", "building_id": "b1"})
        db.buildings.find_one = AsyncMock(return_value={"id": "b1", "name": "B1", "project_id": "p1"})

        units_cursor = MagicMock()
        units_cursor.to_list = AsyncMock(return_value=units)
        db.units.find = MagicMock(return_value=units_cursor)

        class _AsyncIter:
            def __init__(self, items):
                self._items = list(items)
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self._items:
                    raise StopAsyncIteration
                return self._items.pop(0)

        db.qc_runs.find = MagicMock(return_value=_AsyncIter(unit_runs))

        items_cursor = MagicMock()
        items_cursor.to_list = AsyncMock(return_value=items)
        db.qc_items.find = MagicMock(return_value=items_cursor)

        with patch.object(qcr, "get_db", return_value=db), \
             patch.object(qcr, "_check_qc_access", new=AsyncMock()), \
             patch.object(qcr, "_get_template", new=AsyncMock(return_value=tpl)):
            res = await qcr.get_floor_units_status("f1", user={"id": "admin", "role": "super_admin"})

        # 3 unit-scope stages (floor-scope filtered out)
        assert len(res["stages"]) == 3, f"expected 3 unit-scope stages, got {len(res['stages'])}"

        # Order by `order` field: tiling(8) → bath(9) → kitchen(10)
        assert res["stages"][0]["stage_id"] == "stage_tiling"
        assert res["stages"][1]["stage_id"] == "stage_bath"
        assert res["stages"][2]["stage_id"] == "stage_kitchen"

        # tiling: u1 has 2 handled items → in_progress; u2 has no run → not_started
        tiling = res["stages"][0]
        assert tiling["stage_title"] == "ריצוף דירה"
        assert tiling["items_per_unit"] == 2
        assert tiling["is_empty"] is False
        assert tiling["total_units"] == 2
        assert tiling["total_items_handled"] == 2
        assert tiling["total_items_possible"] == 4
        assert tiling["completion_pct"] == 50
        assert len(tiling["units"]) == 2

        u1_breakdown = next(u for u in tiling["units"] if u["unit_id"] == "u1")
        assert u1_breakdown["status"] == "in_progress"
        assert u1_breakdown["pass_count"] == 1
        assert u1_breakdown["fail_count"] == 1
        assert u1_breakdown["handled_count"] == 2
        assert u1_breakdown["total"] == 2

        u2_breakdown = next(u for u in tiling["units"] if u["unit_id"] == "u2")
        assert u2_breakdown["status"] == "not_started"
        assert u2_breakdown["handled_count"] == 0

        # bath + kitchen: no items in qc_items → all units not_started, 0 handled
        bath = res["stages"][1]
        assert bath["stage_title"] == "אמבטיה"
        assert bath["is_empty"] is False
        assert bath["total_items_handled"] == 0
        assert bath["completion_pct"] == 0
        assert all(u["status"] == "not_started" for u in bath["units"])

        kitchen = res["stages"][2]
        assert kitchen["stage_title"] == "מטבחים"
        assert kitchen["total_items_handled"] == 0

        # response top-level shape
        assert res["floor_id"] == "f1"
        assert res["building_id"] == "b1"
        assert "stages" in res
        assert "units" not in res, "old `units` key must be gone — replaced by `stages`"

    asyncio.run(run())
