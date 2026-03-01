#!/usr/bin/env python3
"""
Health Check: Orphan Data Scanner
Scans the database for orphan records (tasks, memberships, invites)
that reference non-existent projects.

Usage:
  python scripts/health_check_orphans.py                   # Report only (exit 0)
  python scripts/health_check_orphans.py --fail-on-orphans # Exit 1 if orphans found (CI mode)

Environment:
  MONGO_URL  - MongoDB connection string (required)
  DB_NAME    - Database name (default: contractor_ops)
"""
import os
import sys
import argparse
from pymongo import MongoClient


def main():
    parser = argparse.ArgumentParser(description="Orphan data health check")
    parser.add_argument("--fail-on-orphans", action="store_true",
                        help="Exit with code 1 if any orphans are found (for CI)")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "contractor_ops")

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[db_name]

    valid_project_ids = set(db.projects.distinct("id"))
    print(f"Database: {db_name}")
    print(f"Valid projects: {len(valid_project_ids)}")
    print("=" * 60)

    total_orphans = 0
    checks = [
        ("tasks", "project_id"),
        ("project_memberships", "project_id"),
        ("invites", "project_id"),
        ("buildings", "project_id"),
        ("floors", "building_id"),
        ("team_invites", "project_id"),
    ]

    valid_building_ids = set(db.buildings.distinct("id"))

    for collection, field in checks:
        all_ids = set(db[collection].distinct(field))
        if collection == "floors":
            orphan_ids = all_ids - valid_building_ids
            ref_label = "buildings"
        else:
            orphan_ids = all_ids - valid_project_ids
            ref_label = "projects"

        orphan_ids.discard(None)
        orphan_ids.discard("")

        count = 0
        if orphan_ids:
            count = db[collection].count_documents({field: {"$in": list(orphan_ids)}})

        total_orphans += count
        status = "OK" if count == 0 else "ORPHANS"
        print(f"\n[{status}] {collection}.{field} → {ref_label}")
        print(f"  Total distinct IDs: {len(all_ids)}")
        print(f"  Orphan IDs: {len(orphan_ids)}")
        print(f"  Orphan documents: {count}")

        if orphan_ids:
            samples = list(orphan_ids)[:5]
            for s in samples:
                doc_count = db[collection].count_documents({field: s})
                print(f"    - {s} ({doc_count} docs)")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {total_orphans} total orphan documents found")

    if total_orphans == 0:
        print("All data is properly linked. No orphans detected.")
    else:
        print(f"WARNING: {total_orphans} orphan documents need attention.")

    if args.fail_on_orphans and total_orphans > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
