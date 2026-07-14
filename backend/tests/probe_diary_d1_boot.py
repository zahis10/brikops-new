"""V7 probe for diary-d1 — flag off/on boot + unique-index dup-insert.

Run TWICE (fresh interpreter per flag value is mandatory — config.py reads
env at import time):
    ENABLE_WORK_DIARY=false python tests/probe_diary_d1_boot.py off
    ENABLE_WORK_DIARY=true  python tests/probe_diary_d1_boot.py on

`on` mode also creates the indexes for real and proves uniqueness with a
raw duplicate insert (expects DuplicateKeyError).
"""
import os
import sys
import asyncio
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
mode = sys.argv[1]  # "off" | "on"

from server import app  # noqa: E402  (flag read at import)

routes = sorted(
    (m, getattr(r, "path", ""))
    for r in app.routes
    for m in (getattr(r, "methods", None) or ["*"])
    if m not in ("HEAD", "OPTIONS")
)
wd_routes = [rt for rt in routes if rt[1].startswith("/api/work-diary")]
other = [rt for rt in routes if not rt[1].startswith("/api/work-diary")]
print(f"mode={mode}  total_routes={len(routes)}  work_diary_routes={len(wd_routes)}")
for m, p in wd_routes:
    print(f"  {m:6s} {p}")
print(f"non-diary route count (must be flag-invariant): {len(other)}")

if mode == "off":
    assert wd_routes == [], f"flag off but diary routes present: {wd_routes}"
    print("[PASS] V7 flag off → zero /api/work-diary routes (404), boot clean")
    sys.exit(0)

# batch safety-ind2 RIDER: count updated 7 → 10. Later diary batches added
# signature, addendums and refresh-derived endpoints on staging; the probe
# asserts CURRENT reality, not the original d1 spec.
assert len(wd_routes) == 10, f"expected 10 diary (method,path) routes, got {wd_routes}"
print("[PASS] V7 flag on → 10 /api/work-diary endpoints registered, boot clean")


async def dup_insert():
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo.errors import DuplicateKeyError
    from contractor_ops.work_diary_router import ensure_work_diary_indexes
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await ensure_work_diary_indexes(db)
    idx = await db.work_diary_entries.index_information()
    assert "uniq_wd_project_date_active" in idx and idx["uniq_wd_project_date_active"].get("unique"), idx
    print(f"[PASS] V7 unique index exists: {idx['uniq_wd_project_date_active']['key']} unique=True")
    pid = f"probe-boot-{uuid.uuid4().hex[:8]}"
    base = {"project_id": pid, "diary_date": "2026-07-08", "deletedAt": None}
    try:
        await db.work_diary_entries.insert_one({**base, "id": "a"})
        try:
            await db.work_diary_entries.insert_one({**base, "id": "b"})
            print("[FAIL] V7 dup insert did NOT raise DuplicateKeyError")
            sys.exit(1)
        except DuplicateKeyError:
            print("[PASS] V7 raw duplicate insert → DuplicateKeyError (index enforces)")
    finally:
        await db.work_diary_entries.delete_many({"project_id": pid})

asyncio.run(dup_insert())
