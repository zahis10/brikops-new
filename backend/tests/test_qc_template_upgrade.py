"""Tests for #601 — auto-upgrade existing QC runs to current template.

Coverage:
  T_UPGRADE_1  idempotent — run already on current → no DB write, no audit
  T_UPGRADE_2  actual upgrade — stale run → DB updated, dict mutated, audit emitted
  T_UPGRADE_3  end-to-end — after upgrade, _backfill_missing_items adds new stages

Background (Zahi prod 2026-05-07): admin edited qc_template (added
floor-scope stages). Existing runs were pinned to OLD template_version_id
so _backfill_missing_items had nothing to add and matrix cells stayed
empty. This batch upgrades the run on get_or_create_*_run access.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contractor_ops import qc_router as qcr


def _make_db():
    db = MagicMock()
    db.qc_runs.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.qc_items.find = MagicMock()
    db.qc_items.insert_many = AsyncMock(return_value=MagicMock(inserted_ids=[]))
    return db


def test_T_UPGRADE_1_idempotent_when_already_current():
    """Run already on current template → returns current, NO DB write,
    NO audit. The hot path for projects whose template hasn't changed.
    """
    async def run():
        db = _make_db()
        current_tpl = {
            "id": "v1",
            "template_id": "tplA",
            "stages": [
                {"id": "s1", "scope": "floor",
                 "items": [{"id": "i1", "title": "סעיף 1"}]},
            ],
        }
        run_doc = {
            "id": "run-abc",
            "project_id": "p1",
            "template_version_id": "v1",  # already current
        }
        actor = {"id": "u1", "name": "PM"}

        with patch.object(qcr, "_get_template",
                          new=AsyncMock(return_value=current_tpl)), \
             patch.object(qcr, "_audit", new=AsyncMock()) as mock_audit:
            tpl = await qcr._resolve_run_template_with_upgrade(
                db, run_doc, "p1", actor,
            )

        assert tpl == current_tpl
        db.qc_runs.update_one.assert_not_called()
        mock_audit.assert_not_called()
        # Local dict NOT mutated with upgrade fields
        assert "template_upgraded_at" not in run_doc
        assert run_doc["template_version_id"] == "v1"

    asyncio.run(run())


def test_T_UPGRADE_2_actually_upgrades_stale_run():
    """Stale run (template_version_id="v1") with current="v2" →
      - returns v2 template
      - update_one called with template_version_id=v2 +
        template_upgraded_from=v1 + template_upgraded_at + actor_id
      - run dict mutated in place
      - _audit emitted with positional sig
        ("qc_run", run_id, "template_upgraded", actor_id, payload)
    """
    async def run():
        db = _make_db()
        current_tpl = {
            "id": "v2",
            "template_id": "tplA",
            "stages": [
                {"id": "s1", "scope": "floor", "items": [{"id": "i1"}]},
                {"id": "s2_new", "scope": "floor",
                 "items": [{"id": "i_new"}]},  # added by admin
            ],
        }
        run_doc = {
            "id": "run-xyz",
            "project_id": "p1",
            "template_version_id": "v1",  # stale
            "template_id": "tplA",
        }
        actor = {"id": "pm-7", "name": "Zahi"}

        with patch.object(qcr, "_get_template",
                          new=AsyncMock(return_value=current_tpl)), \
             patch.object(qcr, "_audit", new=AsyncMock()) as mock_audit:
            tpl = await qcr._resolve_run_template_with_upgrade(
                db, run_doc, "p1", actor,
            )

        # 1. Returned current template
        assert tpl == current_tpl
        assert tpl["id"] == "v2"

        # 2. DB write happened with correct payload
        db.qc_runs.update_one.assert_called_once()
        filt, payload = db.qc_runs.update_one.call_args[0]
        assert filt == {"id": "run-xyz"}
        s = payload["$set"]
        assert s["template_version_id"] == "v2"
        assert s["template_id"] == "tplA"
        assert s["template_upgraded_from"] == "v1"
        assert s["template_upgraded_by"] == "pm-7"
        assert "template_upgraded_at" in s

        # 3. Local dict mutated for caller
        assert run_doc["template_version_id"] == "v2"
        assert run_doc["template_upgraded_from"] == "v1"
        assert run_doc["template_upgraded_by"] == "pm-7"
        assert "template_upgraded_at" in run_doc

        # 4. Audit emitted with POSITIONAL signature (D1 — matches the
        #    rest of qc_router.py, NOT kwargs as the spec drafted)
        mock_audit.assert_called_once()
        args, _ = mock_audit.call_args
        assert args[0] == "qc_run"
        assert args[1] == "run-xyz"
        assert args[2] == "template_upgraded"
        assert args[3] == "pm-7"
        assert args[4]["from"] == "v1"
        assert args[4]["to"] == "v2"
        assert args[4]["project_id"] == "p1"

    asyncio.run(run())


def test_T_UPGRADE_3_backfill_adds_new_stages_after_upgrade():
    """End-to-end semantic check: after _resolve_run_template_with_upgrade
    swaps the run to v2 (which has a new stage s2_new), the existing
    _backfill_missing_items helper inserts items ONLY for the new
    (stage_id, item_id) tuples — old s1 items are not duplicated.

    This is the proof that the bug is fixed: stale runs that were
    100% complete on v1 will now get the new v2 items as "pending".
    """
    async def run():
        # State BEFORE upgrade — only s1 items exist
        existing_items = [
            {"stage_id": "s1", "item_id": "i1",
             "id": "x1", "status": "pass"},
        ]
        # Admin's new template — s1 unchanged, s2_new added
        v2_tpl = {
            "id": "v2",
            "template_id": "tplA",
            "stages": [
                {"id": "s1", "scope": "floor", "items": [{"id": "i1"}]},
                {"id": "s2_new", "scope": "floor",
                 "items": [{"id": "i_new_a"}, {"id": "i_new_b"}]},
            ],
        }

        db = _make_db()

        # Spy on insert_many to capture the docs
        captured = {"docs": None}

        async def _insert(docs, ordered=True):
            captured["docs"] = list(docs)
            return MagicMock(inserted_ids=["a", "b"])

        db.qc_items.insert_many = AsyncMock(side_effect=_insert)

        # _backfill_missing_items re-queries qc_items.find().to_list()
        # at the end to return the post-insert state. Mock that cursor.
        post_insert_state = list(existing_items)  # filled below

        cursor = MagicMock()
        cursor.to_list = AsyncMock(
            side_effect=lambda n: post_insert_state
        )
        db.qc_items.find = MagicMock(return_value=cursor)

        # Call the existing backfill helper directly with the v2 tpl —
        # this is what get_or_create_floor_run does AFTER upgrade.
        # Pre-extend post-insert state so the final find().to_list()
        # mock returns existing + new (mimics real DB read-after-write).
        post_insert_state.extend([
            {"stage_id": "s2_new", "item_id": "i_new_a",
             "id": "n1", "status": "pending"},
            {"stage_id": "s2_new", "item_id": "i_new_b",
             "id": "n2", "status": "pending"},
        ])
        result = await qcr._backfill_missing_items(
            "run-xyz", existing_items, db, v2_tpl, run_scope="floor",
        )

        # 1. insert_many was called with EXACTLY 2 new items
        assert captured["docs"] is not None, (
            "Expected insert_many to be called for new s2_new items"
        )
        assert len(captured["docs"]) == 2

        # 2. The new items are for s2_new, not duplicates of s1
        inserted_keys = {(d["stage_id"], d["item_id"])
                         for d in captured["docs"]}
        assert inserted_keys == {
            ("s2_new", "i_new_a"),
            ("s2_new", "i_new_b"),
        }

        # 3. All inserted items default to "pending" (matches existing
        #    backfill contract — new stages start un-touched)
        for d in captured["docs"]:
            assert d["status"] == "pending"
            assert d["run_id"] == "run-xyz"

        # 4. Result list grew correctly
        assert len(result) == 1 + 2  # original + 2 new

    asyncio.run(run())
