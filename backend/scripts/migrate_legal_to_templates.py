#!/usr/bin/env python3
"""
Migration script: Copy org-level handover_legal_sections to active handover templates.

For each org that has handover_legal_sections:
  - Find all active handover templates for that org's projects
  - For each template that does NOT already have legal_sections, copy from org
  - Creates a new template version with legal_sections added
  - Does NOT overwrite existing template legal_sections

Usage:
  MONGO_URL=mongodb://localhost:27017 DB_NAME=contractor_ops python3 backend/scripts/migrate_legal_to_templates.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "contractor_ops")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    orgs_cursor = db.organizations.find(
        {"handover_legal_sections": {"$exists": True, "$ne": []}},
        {"_id": 0, "id": 1, "name": 1, "handover_legal_sections": 1}
    )
    orgs = await orgs_cursor.to_list(length=None)
    print(f"Found {len(orgs)} org(s) with handover_legal_sections")

    total_migrated = 0
    total_skipped = 0

    for org in orgs:
        org_id = org["id"]
        org_name = org.get("name", org_id)
        legal_sections = org["handover_legal_sections"]
        print(f"\n--- Org: {org_name} ({org_id}) — {len(legal_sections)} legal section(s)")

        projects = await db.projects.find(
            {"org_id": org_id, "handover_template_version_id": {"$exists": True, "$ne": None}},
            {"_id": 0, "id": 1, "handover_template_version_id": 1}
        ).to_list(length=None)

        template_version_ids = list(set(p["handover_template_version_id"] for p in projects))
        if not template_version_ids:
            print(f"  No projects with handover templates, skipping")
            continue

        templates = await db.qc_templates.find(
            {"id": {"$in": template_version_ids}, "type": "handover", "is_active": True},
            {"_id": 0}
        ).to_list(length=None)

        seen_families = set()
        for tpl in templates:
            family_id = tpl["family_id"]
            if family_id in seen_families:
                continue
            seen_families.add(family_id)

            if tpl.get("legal_sections"):
                print(f"  Template family {family_id} (v{tpl['version']}) already has legal_sections, skipping")
                total_skipped += 1
                continue

            max_doc = await db.qc_templates.find_one(
                {"family_id": family_id},
                {"_id": 0, "version": 1},
                sort=[("version", -1)]
            )
            new_version = (max_doc["version"] if max_doc else tpl["version"]) + 1
            new_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            new_doc = {**tpl}
            new_doc.pop("_id", None)
            new_doc["id"] = new_id
            new_doc["version"] = new_version
            new_doc["created_at"] = now
            new_doc["created_by"] = "migration"
            new_doc["legal_sections"] = legal_sections

            await db.qc_templates.insert_one(new_doc)

            await db.qc_templates.update_many(
                {"family_id": family_id, "id": {"$ne": new_id}, "is_active": True},
                {"$set": {"is_active": False}}
            )

            old_id = tpl["id"]
            repin = await db.projects.update_many(
                {"handover_template_version_id": old_id},
                {"$set": {"handover_template_version_id": new_id}}
            )

            print(f"  Migrated template family {family_id}: v{tpl['version']}->v{new_version} new_id={new_id} repinned={repin.modified_count} project(s)")
            total_migrated += 1

    print(f"\n=== Done: {total_migrated} template(s) migrated, {total_skipped} skipped (already had legal_sections)")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
