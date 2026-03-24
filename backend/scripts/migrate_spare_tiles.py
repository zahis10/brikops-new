#!/usr/bin/env python3
"""
Migration: Convert spare_tiles_count/spare_tiles_notes to spare_tiles array.

Usage:
  python migrate_spare_tiles.py              # dry-run (default)
  python migrate_spare_tiles.py --execute    # execute migration
"""
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'contractor_ops')

BASE_TYPES = [
    'ריצוף יבש',
    'ריצוף מרפסות',
    'חיפוי אמבטיות',
    'ריצוף אמבטיות',
    'חיפוי מטבח',
]


async def migrate(execute: bool = False):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    total = await db.units.count_documents({'archived': {'$ne': True}})
    already_migrated = await db.units.count_documents({
        'archived': {'$ne': True},
        'spare_tiles': {'$exists': True},
    })
    has_old_data = await db.units.count_documents({
        'archived': {'$ne': True},
        'spare_tiles': {'$exists': False},
        '$or': [
            {'spare_tiles_count': {'$ne': None, '$exists': True}},
            {'spare_tiles_notes': {'$ne': None, '$ne': '', '$exists': True}},
        ],
    })
    no_data = await db.units.count_documents({
        'archived': {'$ne': True},
        'spare_tiles': {'$exists': False},
        '$and': [
            {'$or': [{'spare_tiles_count': None}, {'spare_tiles_count': {'$exists': False}}]},
            {'$or': [{'spare_tiles_notes': None}, {'spare_tiles_notes': ''}, {'spare_tiles_notes': {'$exists': False}}]},
        ],
    })

    print(f"=== Spare Tiles Migration {'(DRY RUN)' if not execute else '(EXECUTING)'} ===")
    print(f"Total active units: {total}")
    print(f"Already migrated (have spare_tiles array): {already_migrated}")
    print(f"Units with old spare_tiles data to convert: {has_old_data}")
    print(f"Units with no spare tiles data (will get empty array): {no_data}")
    print()

    if not execute:
        print("Run with --execute to apply migration.")
        client.close()
        return

    migrated_with_data = 0
    migrated_empty = 0

    cursor = db.units.find(
        {'archived': {'$ne': True}, 'spare_tiles': {'$exists': False}},
        {'_id': 1, 'id': 1, 'spare_tiles_count': 1, 'spare_tiles_notes': 1},
    )

    async for unit in cursor:
        old_count = unit.get('spare_tiles_count')
        old_notes = unit.get('spare_tiles_notes') or ''

        has_count = old_count is not None and isinstance(old_count, int)
        has_notes = bool(old_notes.strip()) if isinstance(old_notes, str) else False

        if has_count or has_notes:
            spare_tiles = [{'type': 'ריצוף (כללי)', 'count': old_count if has_count else 0, 'notes': old_notes.strip() if has_notes else ''}]
            for bt in BASE_TYPES:
                spare_tiles.append({'type': bt, 'count': 0, 'notes': ''})
            migrated_with_data += 1
        else:
            spare_tiles = []
            migrated_empty += 1

        await db.units.update_one(
            {'_id': unit['_id']},
            {'$set': {'spare_tiles': spare_tiles}},
        )

    print(f"Migration complete:")
    print(f"  Converted with data: {migrated_with_data}")
    print(f"  Set empty array: {migrated_empty}")
    print(f"  Total migrated: {migrated_with_data + migrated_empty}")
    print()
    print("Old fields (spare_tiles_count, spare_tiles_notes) preserved for rollback.")

    client.close()


if __name__ == '__main__':
    do_execute = '--execute' in sys.argv
    asyncio.run(migrate(execute=do_execute))
