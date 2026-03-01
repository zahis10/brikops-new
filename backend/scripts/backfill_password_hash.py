#!/usr/bin/env python3
"""
Phase 2.7 — Backfill password_hash for legacy users.

Handles two cases:
1. Users with `password` but no `password_hash` → migrate bcrypt, block plaintext
2. Users with both `password` and `password_hash` → remove redundant `password` field

Usage:
    python backfill_password_hash.py              # dry-run
    python backfill_password_hash.py --apply      # apply migration
"""

import os
import argparse
import uuid
from datetime import datetime, timezone

import pymongo


def is_bcrypt(value: str) -> bool:
    return isinstance(value, str) and value.startswith(('$2a$', '$2b$', '$2y$'))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description='Backfill password_hash for legacy users')
    parser.add_argument('--apply', action='store_true', help='Apply migration (default is dry-run)')
    args = parser.parse_args()

    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'contractor_ops')

    client = pymongo.MongoClient(mongo_url)
    db = client[db_name]

    migrate_query = {'password': {'$exists': True}, 'password_hash': {'$exists': False}}
    migrate_users = list(db.users.find(migrate_query, {'_id': 0, 'id': 1, 'name': 1, 'phone_e164': 1, 'email': 1, 'password': 1}))

    cleanup_query = {'password': {'$exists': True}, 'password_hash': {'$exists': True}}
    cleanup_users = list(db.users.find(cleanup_query, {'_id': 0, 'id': 1, 'phone_e164': 1, 'email': 1}))

    if not migrate_users and not cleanup_users:
        print('No users need migration or cleanup.')
        return

    if migrate_users:
        bcrypt_users = [u for u in migrate_users if is_bcrypt(u.get('password', ''))]
        plaintext_users = [u for u in migrate_users if not is_bcrypt(u.get('password', ''))]

        print(f'Migration: {len(migrate_users)} users with legacy `password` only:')
        print(f'  - {len(bcrypt_users)} with bcrypt hash (safe to migrate)')
        print(f'  - {len(plaintext_users)} with non-bcrypt value (BLOCKED)')
        for u in bcrypt_users:
            print(f'  [BCRYPT] id={u["id"]} phone={u.get("phone_e164", "N/A")} email={u.get("email", "N/A")}')
        for u in plaintext_users:
            print(f'  [BLOCKED] id={u["id"]} phone={u.get("phone_e164", "N/A")} email={u.get("email", "N/A")}')
        print()

    if cleanup_users:
        print(f'Cleanup: {len(cleanup_users)} users with both `password` and `password_hash` (remove redundant `password`):')
        for u in cleanup_users:
            print(f'  [CLEANUP] id={u["id"]} phone={u.get("phone_e164", "N/A")} email={u.get("email", "N/A")}')
        print()

    if not args.apply:
        print('Dry-run complete. Use --apply to execute.')
        return

    print('Applying...')
    migrated = 0
    blocked = 0
    cleaned = 0

    if migrate_users:
        bcrypt_users = [u for u in migrate_users if is_bcrypt(u.get('password', ''))]
        plaintext_users = [u for u in migrate_users if not is_bcrypt(u.get('password', ''))]

        for u in bcrypt_users:
            db.users.update_one(
                {'id': u['id']},
                {'$set': {'password_hash': u['password']}, '$unset': {'password': ''}}
            )
            db.audit_events.insert_one({
                'id': str(uuid.uuid4()),
                'entity_type': 'user',
                'entity_id': u['id'],
                'action': 'auth_password_hash_backfilled',
                'actor_id': 'system',
                'payload': {'source': 'script', 'had_plaintext': False},
                'created_at': now_iso(),
            })
            migrated += 1
            print(f'  Migrated: {u["id"]}')

        for u in plaintext_users:
            db.audit_events.insert_one({
                'id': str(uuid.uuid4()),
                'entity_type': 'user',
                'entity_id': u['id'],
                'action': 'auth_password_migration_blocked_plaintext',
                'actor_id': 'system',
                'payload': {'source': 'script'},
                'created_at': now_iso(),
            })
            blocked += 1
            print(f'  Blocked (plaintext): {u["id"]}')

    for u in cleanup_users:
        db.users.update_one({'id': u['id']}, {'$unset': {'password': ''}})
        cleaned += 1
        print(f'  Cleaned up: {u["id"]}')

    print(f'\nDone. Migrated: {migrated}, Blocked: {blocked}, Cleaned: {cleaned}')


if __name__ == '__main__':
    main()
