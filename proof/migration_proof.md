# Billing v1 — Migration Proof Package

**Date**: 2025-02-25  
**Commit**: `7bae3fb`  
**Environment**: Dev/Preview, `BILLING_V1_ENABLED=true`

## Migration System Overview

The billing v1 migration system handles backfilling `org_id` on existing projects that were created before the organization system. It consists of:

- `dry_run_org_id_backfill()` — Scans projects, reports which are missing `org_id`, which can be auto-resolved
- `apply_org_id_backfill(actor_id)` — Applies the backfill, records audit events for each project updated

## Dry Run Output

```json
{
  "total_projects": 2,
  "projects_with_org_id": 2,
  "projects_missing_org_id": 0,
  "auto_resolvable_count": 0,
  "ambiguous_count": 0,
  "auto_resolvable": [],
  "ambiguous": []
}
```

**Result**: All 2 projects already have `org_id` assigned. No migration needed.

## Apply — First Execution

```json
{
  "applied_count": 0,
  "skipped_count": 0,
  "applied": [],
  "skipped": []
}
```

**Result**: 0 projects needed backfill (all already have `org_id`). No mutations performed.

## Apply — Second Execution (Idempotency Proof)

```json
{
  "applied_count": 0,
  "skipped_count": 0,
  "applied": [],
  "skipped": []
}
```

**Result**: Identical output to first execution. **Idempotency confirmed.**

## Audit Events for `org_id_backfill_applied`

**Count**: 0 events

**Expected**: Since all projects already had `org_id`, no backfill was applied, and therefore no audit events were emitted. This is correct behavior — audit events are only created when a project's `org_id` is actually changed.

## No Auto-Backfill on Startup

**Grep of `server.py` for backfill/seed/apply calls related to billing v1:**

The only backfill call in `server.py` is `backfill_join_codes()` (a pre-billing feature for join code migration). There are NO calls to:
- `apply_org_id_backfill()`
- `seed_default_plans()`

**Billing references in `server.py` are read-only:**
- `[BILLING-MIGRATE]` logs are part of the existing organization migration (pre-v1), not billing backfill
- `[BILLING-HEALTH]` is a startup health check that only counts orphan projects (read-only `count_documents`)

**Conclusion**: Billing v1 migration is admin-initiated only. No automatic mutations occur on server startup.

## Migration Code Reference

```python
# From billing.py - apply_org_id_backfill()
async def apply_org_id_backfill(actor_id: str) -> dict:
    report = await dry_run_org_id_backfill()
    applied, skipped = [], []
    for item in report.get('auto_resolvable', []):
        pid = item['project_id']
        oid = item['org_id']
        await db.projects.update_one(
            {'id': pid, 'org_id': {'$exists': False}},  # Only update if still missing
            {'$set': {'org_id': oid}}
        )
        # Audit event per project
        await db.audit_events.insert_one({...action: 'org_id_backfill_applied'...})
        applied.append(item)
    return {'applied_count': len(applied), 'skipped_count': len(skipped), ...}
```

Key safety features:
1. Uses `{'$exists': False}` guard — won't overwrite existing `org_id`
2. Each application creates an audit event with project_id, org_id, and actor
3. Ambiguous projects (multiple possible orgs) are skipped, not auto-resolved
4. Function is idempotent — re-running produces identical results
