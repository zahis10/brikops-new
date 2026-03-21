#!/usr/bin/env python3
"""
One-time backfill: populate task.proof_urls and protocol item.photos
from task_updates attachment records.

Before the fix in tasks_router.py, uploading a photo via
POST /tasks/{task_id}/attachments stored the URL in task_updates
but did NOT add it to task.proof_urls or protocol item.photos.

This script:
1. Finds tasks with attachments_count > 0 but empty proof_urls
2. Looks up task_updates with update_type=attachment for each task
3. Sets task.proof_urls from collected attachment_urls
4. Updates the linked protocol item.photos if handover fields exist

Usage:
  MONGO_URL=mongodb://localhost:27017 DB_NAME=contractor_ops python3 backend/scripts/backfill_defect_photos.py
"""
import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "contractor_ops")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    tasks = await db.tasks.find(
        {"attachments_count": {"$gt": 0}, "$or": [{"proof_urls": []}, {"proof_urls": {"$exists": False}}]},
        {"_id": 0, "id": 1, "handover_protocol_id": 1, "handover_item_id": 1, "attachments_count": 1}
    ).to_list(length=None)

    print(f"Found {len(tasks)} task(s) with attachments but empty proof_urls")

    fixed_tasks = 0
    fixed_items = 0

    for task in tasks:
        task_id = task["id"]
        updates = await db.task_updates.find(
            {"task_id": task_id, "update_type": "attachment"},
            {"_id": 0, "attachment_url": 1}
        ).to_list(length=None)

        urls = [u["attachment_url"] for u in updates if u.get("attachment_url")]
        if not urls:
            print(f"  Task {task_id[:8]}: no attachment URLs found in task_updates, skipping")
            continue

        await db.tasks.update_one(
            {"id": task_id},
            {"$addToSet": {"proof_urls": {"$each": urls}}}
        )
        fixed_tasks += 1
        print(f"  Task {task_id[:8]}: added {len(urls)} URL(s) to proof_urls")

        ho_protocol_id = task.get("handover_protocol_id")
        ho_item_id = task.get("handover_item_id")
        if ho_protocol_id and ho_item_id:
            result = await db.handover_protocols.update_one(
                {"id": ho_protocol_id, "sections.items.item_id": ho_item_id},
                {"$addToSet": {"sections.$[sec].items.$[itm].photos": {"$each": urls}}},
                array_filters=[
                    {"sec.items.item_id": ho_item_id},
                    {"itm.item_id": ho_item_id},
                ],
            )
            if result.modified_count > 0:
                fixed_items += 1
                print(f"    Protocol {ho_protocol_id[:8]} item {ho_item_id}: set photos to {len(urls)} URL(s)")

    print(f"\n=== Done: {fixed_tasks} task(s) fixed, {fixed_items} protocol item(s) updated")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
