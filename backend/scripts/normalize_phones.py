"""
One-time phone normalization backfill script.
Normalizes existing phone numbers in users, invites, and memberships to E.164 format.
Idempotent: safe to re-run (skips already-normalized values).

Usage:
    cd backend && python scripts/normalize_phones.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from contractor_ops.phone_utils import normalize_israeli_phone

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'brikops_prod')


async def normalize_collection(db, collection_name, phone_field, report):
    """Normalize phone numbers in a collection."""
    coll = db[collection_name]
    cursor = coll.find({phone_field: {'$exists': True, '$ne': None}})
    
    scanned = 0
    updated = 0
    skipped = 0
    failed = 0
    failures = []
    
    async for doc in cursor:
        scanned += 1
        raw_phone = doc.get(phone_field, '')
        if not raw_phone:
            skipped += 1
            continue
        
        try:
            result = normalize_israeli_phone(raw_phone)
            canonical = result['phone_e164']
        except ValueError as e:
            failed += 1
            failures.append({
                'id': doc.get('id', str(doc.get('_id', '?'))),
                'field': phone_field,
                'value': raw_phone,
                'error': str(e),
            })
            continue
        
        if raw_phone == canonical:
            skipped += 1
            continue
        
        update_fields = {phone_field: canonical}
        if phone_field == 'phone_e164':
            update_fields['phone_raw'] = raw_phone
        elif phone_field == 'target_phone':
            update_fields['phone_raw'] = raw_phone
        
        await coll.update_one(
            {'_id': doc['_id']},
            {'$set': update_fields}
        )
        updated += 1
    
    entry = {
        'collection': collection_name,
        'field': phone_field,
        'scanned': scanned,
        'updated': updated,
        'skipped': skipped,
        'failed': failed,
        'failures': failures,
    }
    report.append(entry)
    return entry


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    report = []
    
    print("=" * 60)
    print("PHONE NORMALIZATION BACKFILL")
    print(f"Database: {DB_NAME}")
    print("=" * 60)
    
    tasks = [
        ('users', 'phone_e164'),
        ('invites', 'target_phone'),
    ]
    
    for collection_name, phone_field in tasks:
        print(f"\n--- {collection_name}.{phone_field} ---")
        entry = await normalize_collection(db, collection_name, phone_field, report)
        print(f"  Scanned: {entry['scanned']}")
        print(f"  Updated: {entry['updated']}")
        print(f"  Skipped: {entry['skipped']} (already normalized)")
        print(f"  Failed:  {entry['failed']}")
        if entry['failures']:
            for f in entry['failures']:
                print(f"    ! {f['id']}: {f['value']} -> {f['error']}")
    
    total_scanned = sum(e['scanned'] for e in report)
    total_updated = sum(e['updated'] for e in report)
    total_skipped = sum(e['skipped'] for e in report)
    total_failed = sum(e['failed'] for e in report)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Total scanned: {total_scanned}")
    print(f"  Total updated: {total_updated}")
    print(f"  Total skipped: {total_skipped} (already E.164)")
    print(f"  Total failed:  {total_failed}")
    print("=" * 60)
    
    if total_failed > 0:
        print("\nFAILURES (require manual review):")
        for entry in report:
            for f in entry['failures']:
                print(f"  [{entry['collection']}] id={f['id']}: '{f['value']}' -> {f['error']}")
    
    client.close()
    return total_failed


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(1 if exit_code > 0 else 0)
