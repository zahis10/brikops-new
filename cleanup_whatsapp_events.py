"""
ONE-TIME cleanup for #421 / Batch S5a — WhatsApp webhook idempotency.

Backfills missing event_type/status fields, then deletes duplicate
(wa_message_id, event_type, status) groups keeping earliest received_at.

Aborts unless the prod DB matches Zahi's 2026-04-25 STEP 0 numbers
(total=401, missing event_type=10, dup groups=5).

DELETE THIS FILE AFTER A SUCCESSFUL RUN.
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient


EXPECTED_TOTAL = 401
EXPECTED_MISSING_ET = 10
EXPECTED_DUP_GROUPS = 5
TOLERANCE = 100  # accept growth/drift between Zahi's snapshot and our run


async def main():
    mongo_url = os.environ.get("MONGO_URL", "")
    if not mongo_url or "mongodb.net" not in mongo_url:
        print("ABORT: MONGO_URL is not an Atlas URL — refusing to run.")
        sys.exit(1)

    db_name = "brikops_prod"  # prod DB per MONGO_URL path
    print(f"Connecting to Atlas DB '{db_name}'...")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print("\n=== SANITY CHECK (read-only) ===")
    total = await db.whatsapp_events.count_documents({})
    null_et = await db.whatsapp_events.count_documents({"event_type": None})
    miss_et = await db.whatsapp_events.count_documents({"event_type": {"$exists": False}})
    null_st = await db.whatsapp_events.count_documents({"status": None})
    miss_st = await db.whatsapp_events.count_documents({"status": {"$exists": False}})

    pipeline_dup = [
        {"$group": {
            "_id": {"wa_message_id": "$wa_message_id",
                    "event_type": "$event_type",
                    "status": "$status"},
            "count": {"$sum": 1},
        }},
        {"$match": {"count": {"$gt": 1}}},
    ]
    dup_groups = 0
    async for _ in db.whatsapp_events.aggregate(pipeline_dup):
        dup_groups += 1

    print(f"  total whatsapp_events:    {total}")
    print(f"  event_type null:          {null_et}")
    print(f"  event_type missing:       {miss_et}")
    print(f"  status null:              {null_st}")
    print(f"  status missing:           {miss_st}")
    print(f"  duplicate-tuple groups:   {dup_groups}")

    if abs(total - EXPECTED_TOTAL) > TOLERANCE:
        print(f"\nABORT: total={total} differs from expected ~{EXPECTED_TOTAL} by more than {TOLERANCE}.")
        print("This DB does not look like the prod snapshot Zahi reported.")
        sys.exit(2)
    print(f"\n✓ Sanity check OK (within ±{TOLERANCE} of Zahi's snapshot). Proceeding.\n")

    print("=== STEP 1 — Backfill missing event_type and status ===")
    backfill_et = await db.whatsapp_events.update_many(
        {"$or": [{"event_type": None}, {"event_type": {"$exists": False}}]},
        {"$set": {"event_type": "legacy_unknown"}},
    )
    print(f"  Backfilled event_type='legacy_unknown' on {backfill_et.modified_count} rows")

    backfill_st = await db.whatsapp_events.update_many(
        {"$or": [{"status": None}, {"status": {"$exists": False}}]},
        {"$set": {"status": ""}},
    )
    print(f"  Backfilled status='' on {backfill_st.modified_count} rows")

    print("\n=== STEP 2 — Delete duplicate-tuple groups, keep earliest received_at ===")
    pipeline_dedup = [
        {"$group": {
            "_id": {"wa_message_id": "$wa_message_id",
                    "event_type": "$event_type",
                    "status": "$status"},
            "count": {"$sum": 1},
            "ids": {"$push": "$_id"},
            "received_at_list": {"$push": "$received_at"},
        }},
        {"$match": {"count": {"$gt": 1}}},
    ]
    total_deleted = 0
    groups_processed = 0
    async for group in db.whatsapp_events.aggregate(pipeline_dedup):
        groups_processed += 1
        # zip(received_at, _id) and sort to find earliest
        ids_by_time = sorted(zip(group["received_at_list"], group["ids"]))
        ids_to_delete = [gid for _, gid in ids_by_time[1:]]
        if ids_to_delete:
            result = await db.whatsapp_events.delete_many({"_id": {"$in": ids_to_delete}})
            total_deleted += result.deleted_count
            print(f"  Group key={group['_id']}: deleted {result.deleted_count} duplicates")
    print(f"\n  Groups processed: {groups_processed}")
    print(f"  Total duplicates deleted: {total_deleted}")

    print("\n=== STEP 3 — Verification (must show all zeros) ===")
    null_et2 = await db.whatsapp_events.count_documents({"event_type": None})
    null_st2 = await db.whatsapp_events.count_documents({"status": None})
    miss_et2 = await db.whatsapp_events.count_documents({"event_type": {"$exists": False}})
    miss_st2 = await db.whatsapp_events.count_documents({"status": {"$exists": False}})
    remaining_dupes = 0
    async for _ in db.whatsapp_events.aggregate(pipeline_dup):
        remaining_dupes += 1
    total_after = await db.whatsapp_events.count_documents({})

    print(f"  null event_type:    {null_et2}")
    print(f"  null status:        {null_st2}")
    print(f"  missing event_type: {miss_et2}")
    print(f"  missing status:     {miss_st2}")
    print(f"  remaining dup groups: {remaining_dupes}")
    print(f"  total rows after cleanup: {total_after}  (was {total}, delta {total_after - total})")

    if any([null_et2, null_st2, miss_et2, miss_st2, remaining_dupes]):
        print("\n❌ CLEANUP INCOMPLETE — DO NOT proceed to index creation")
        sys.exit(3)
    print("\n✅ CLEANUP COMPLETE — safe to create unique index (Task 2)")


asyncio.run(main())
