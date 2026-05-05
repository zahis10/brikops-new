"""Tests for Batch #469 — Defect safety tag (`is_safety` field).

Schema-only tests covering Task / TaskCreate / TaskUpdate validation,
defaults, and the None-sentinel pattern on partial updates. No DB
touch; no asyncio needed for these schema validations.
"""


def test_task_create_accepts_is_safety_field():
    from contractor_ops.schemas import TaskCreate
    payload = TaskCreate(
        project_id="p1", building_id="b1", floor_id="f1", unit_id="u1",
        title="Test", is_safety=True,
    )
    assert payload.is_safety is True


def test_task_create_default_is_safety_false():
    from contractor_ops.schemas import TaskCreate
    payload = TaskCreate(
        project_id="p1", building_id="b1", floor_id="f1", unit_id="u1",
        title="Test",
    )
    assert payload.is_safety is False


def test_task_update_is_safety_optional():
    """TaskUpdate uses None sentinel for partial updates."""
    from contractor_ops.schemas import TaskUpdate
    payload = TaskUpdate(is_safety=True)
    assert payload.is_safety is True
    payload2 = TaskUpdate(title="just title")
    assert payload2.is_safety is None  # not set → don't update


def test_task_response_default_is_safety_false():
    from contractor_ops.schemas import Task
    t = Task(project_id="p1", title="x")
    assert t.is_safety is False


def test_task_existing_data_without_field_renders_as_false():
    """Backward compat: legacy Task docs without is_safety → False."""
    from contractor_ops.schemas import Task
    # Simulate doc loaded from DB without the field
    t = Task(**{"project_id": "p1", "title": "x"})
    assert t.is_safety is False


# =====================================================================
# #488 — defects-summary exposes per-unit safety_open_count
# =====================================================================

def test_defects_summary_includes_safety_open_count():
    """#488 — building defects-summary exposes safety_open_count per unit
    so BuildingDefectsPage can client-side filter to 'safety only'."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    from contractor_ops import projects_router as pr

    class _AsyncCursor:
        def __init__(self, items):
            self._items = list(items)
        def sort(self, *a, **k):
            return self
        async def to_list(self, _n=None):
            return list(self._items)

    async def run():
        building = {'id': 'b1', 'project_id': 'p1', 'name': 'A'}
        project = {'id': 'p1', 'name': 'Proj', 'code': 'P1'}
        floors = [{'id': 'f1', 'building_id': 'b1', 'name': '1', 'floor_number': 1}]
        units = [
            {'id': 'u1', 'floor_id': 'f1', 'unit_no': '1'},
            {'id': 'u2', 'floor_id': 'f1', 'unit_no': '2'},
        ]
        # u1 has 2 open safety defects + 1 closed safety; u2 has 1 open non-safety
        tasks = [
            {'unit_id': 'u1', 'status': 'open',     'category': 'electric', 'is_safety': True},
            {'unit_id': 'u1', 'status': 'in_progress', 'category': 'electric', 'is_safety': True},
            {'unit_id': 'u1', 'status': 'closed',   'category': 'electric', 'is_safety': True},
            {'unit_id': 'u2', 'status': 'open',     'category': 'paint',    'is_safety': False},
        ]
        db = MagicMock()
        db.buildings.find_one = AsyncMock(return_value=building)
        db.projects.find_one = AsyncMock(return_value=project)
        db.floors.find = MagicMock(return_value=_AsyncCursor(floors))
        db.units.find = MagicMock(return_value=_AsyncCursor(units))
        db.tasks.find = MagicMock(return_value=_AsyncCursor(tasks))

        with patch.object(pr, 'get_db', return_value=db), \
             patch.object(pr, '_check_project_read_access', new=AsyncMock()):
            res = await pr.building_defects_summary('b1', user={'id': 'u', 'role': 'super_admin'})

        unit_results = res['floors'][0]['units']
        by_id = {u['id']: u for u in unit_results}
        assert 'safety_open_count' in by_id['u1']
        assert by_id['u1']['safety_open_count'] == 2  # closed safety not counted
        assert by_id['u2']['safety_open_count'] == 0  # non-safety not counted

    asyncio.run(run())
