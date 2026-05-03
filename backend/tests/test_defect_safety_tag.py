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
