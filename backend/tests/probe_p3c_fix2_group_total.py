"""FUNCTIONAL probe for safety-p3c-fix2 (trainings tab counter = groups).

Verification-only. Drives the REAL list_trainings coroutine against a REAL local
Mongo (mongodb://localhost:27017 / contractor_ops). Scaffolding NOT under test
and patched to no-op (disclosed): _check_project_access, router.get_db/sr.get_db.
"""
import os
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "contractor_ops")

import sys
import uuid
import asyncio
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from contractor_ops import safety_router as sr
from contractor_ops import router as cr
# Batch refactor-safety-split (Option A amendment, patch targets only): the
# trainings coroutines now live in contractor_ops.safety.trainings — patches
# must target the module where the functions are DEFINED, not the facade.
from contractor_ops.safety import trainings as st

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


PM = {"id": "probe-pm", "role": "project_manager"}


def _training(pid, wid, ttype, trained_at):
    return {
        "id": f"t-{uuid.uuid4().hex[:8]}", "project_id": pid, "worker_id": wid,
        "training_type": ttype, "trained_at": trained_at,
        "created_at": sr._now(), "created_by": PM["id"],
        "deletedAt": None, "deletedBy": None, "worker_signature": None,
    }


async def call_list(pid):
    return await sr.list_trainings(
        pid, worker_id=None, training_type=None, expires_before=None,
        include_deleted=False, limit=50, offset=0, user=PM,
    )


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pid = f"probe-fix2-{uuid.uuid4().hex[:8]}"
    wA, wB = f"wA-{uuid.uuid4().hex[:6]}", f"wB-{uuid.uuid4().hex[:6]}"

    patches = [
        patch.object(st, "get_db", return_value=db),
        patch.object(cr, "get_db", return_value=db),
        patch.object(st, "_check_project_access", new=AsyncMock()),
    ]
    for p in patches:
        p.start()
    try:
        # ---- V1: 5 records across 3 (worker,type) groups ----
        # groups: (wA,גובה)x2, (wA,עזרה ראשונה)x2, (wB,גובה)x1  → 5 records / 3 groups
        docs = [
            _training(pid, wA, "עבודה בגובה", "2026-01-10"),
            _training(pid, wA, "עבודה בגובה", "2026-06-10"),
            _training(pid, wA, "עזרה ראשונה", "2026-02-01"),
            _training(pid, wA, "עזרה ראשונה", "2026-07-01"),
            _training(pid, wB, "עבודה בגובה", "2026-03-01"),
        ]
        await db.safety_trainings.insert_many(docs)
        r1 = await call_list(pid)
        record("V1 total=5, group_total=3",
               r1["total"] == 5 and r1["group_total"] == 3,
               f"total={r1['total']} group_total={r1['group_total']}")

        # ---- V3a: add a record to an EXISTING group → total 6, group_total 3 ----
        await db.safety_trainings.insert_one(_training(pid, wA, "עבודה בגובה", "2026-07-05"))
        r3a = await call_list(pid)
        record("V3a add to existing group → total=6, group_total=3",
               r3a["total"] == 6 and r3a["group_total"] == 3,
               f"total={r3a['total']} group_total={r3a['group_total']}")

        # ---- V3b: add a NEW type → group_total 4 ----
        await db.safety_trainings.insert_one(_training(pid, wB, "חומרים מסוכנים", "2026-07-06"))
        r3b = await call_list(pid)
        record("V3b new type → total=7, group_total=4",
               r3b["total"] == 7 and r3b["group_total"] == 4,
               f"total={r3b['total']} group_total={r3b['group_total']}")
    finally:
        await db.safety_trainings.delete_many({"project_id": pid})
        for p in patches:
            p.stop()

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"RESULT: {passed}/{len(RESULTS)} probes passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
