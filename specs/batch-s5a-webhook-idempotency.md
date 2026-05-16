# #420 — Batch S5a — WhatsApp webhook idempotency (code-audit CRITICAL)

## What & Why

**Pre-launch security + data-integrity fix.** Code audit 2026-04-24 found `S5-CRIT-1`: WhatsApp webhook at `backend/contractor_ops/notification_router.py:153-269` has NO idempotency mechanism. If Meta retries a webhook (standard behavior on 5xx, network blips, ACK timeouts — real-world frequency ~2-5% of webhook batches), BrikOps:

1. Inserts a duplicate event record in `whatsapp_events`
2. **Calls `engine.process_webhook()` a second time** → generates a duplicate `audit_events` entry, re-processes the same state transition

**Same framing as S1/S2:** internal testers, not paying customers. No active breach. Fix before wider release.

### The bug in detail

**File:** `backend/contractor_ops/notification_router.py:153-269`

**Current flow per status update event:**
```python
# ~line 214 — INSERT (no dedup)
try:
    await db.whatsapp_events.insert_one(event_doc)
    events_saved += 1
except Exception as e:
    logger.error(f"[WA] failed to save status event: {e}")

# ~line 230 — PROCESS (runs even if insert was a duplicate)
result = await engine.process_webhook(provider_id, mapped_status)
```

**Same pattern at line 260** for incoming message events.

**What gets duplicated if Meta retries:**
- 2 rows in `whatsapp_events` with same `wa_message_id` + `event_type` + `status`
- 2 calls to `process_webhook` → 2 `audit_events` entries
- 2 `notification_jobs.update_one` calls (idempotent at DB level, but still wasted cycles)
- Analytics / reporting queries double-count events

**What does NOT get duplicated (lucky):**
- No outbound SMS or WhatsApp message is sent (status updates don't trigger outbound)
- No customer-visible spam
- No payment double-charge (no payment webhook exists)

So the severity is **DATA INTEGRITY + AUDIT TRAIL**, not customer harm. Still worth fixing before scale.

### Data-model nuance — the correct dedup key

One WhatsApp message generates **multiple status events** over its lifetime:
- `sent` → `delivered` → `read` (or `failed`)

So `wa_message_id` alone is NOT unique — each status transition is a separate valid event.

**The correct dedup key is the tuple `(wa_message_id, event_type, status)`:**
- Status events: `(msg_id, 'status', 'sent')` / `(msg_id, 'status', 'delivered')` / etc.
- Incoming messages: `(msg_id, 'message', '')` (status is empty string for messages per line 252)

### Other webhook endpoints

Investigation confirmed **no other webhook endpoints exist** in the backend. No PayPlus, Green Invoice, or billing webhooks — billing renewal is cron-based. So this patch covers the entire webhook attack surface.

### Solution (atomic upsert + unique index)

**Race-safety requires BOTH:**

1. **Atomic upsert** (`update_one` with `$setOnInsert` + `upsert=True`) — replaces `insert_one`. Duplicate-resistant at the application level.
2. **Compound unique index** on `(wa_message_id, event_type, status)` — race-safe at DB level. If two concurrent webhooks race on the same event, only one insert wins; the other is caught by MongoDB's unique constraint and retried as a no-op update.

Without the index, concurrent upserts both see "no match" and both insert. With the index, the race is properly serialized.

**Gate `process_webhook` on the upsert result:**

```python
result = await db.whatsapp_events.update_one(
    {'wa_message_id': provider_id, 'event_type': 'status', 'status': wa_status},
    {'$setOnInsert': event_doc},
    upsert=True,
)
if result.upserted_id is None:
    # Duplicate — already processed, skip
    duplicates_skipped += 1
    continue
# Not a duplicate — proceed with process_webhook as before
```

This closes both ends of the loophole: DB side AND processing side.

---

## Done looks like

### Happy path (new webhook event)

1. Meta sends first webhook for `msg_id_X` with status `delivered`
2. Server verifies signature → passes
3. `update_one(filter, $setOnInsert, upsert=True)` returns `result.upserted_id != None` → new event
4. `process_webhook(msg_id_X, 'delivered')` runs → job status updated + audit_events row added
5. Returns 200 OK

### Duplicate path (Meta retries same event)

1. Meta retries same webhook for `msg_id_X` / `delivered` (network retry)
2. Server verifies signature → passes
3. `update_one(filter, $setOnInsert, upsert=True)` returns `result.upserted_id == None` (document already exists)
4. Loop skips to next event; no `process_webhook` call; increments `duplicates_skipped` counter
5. Returns 200 OK

### Race path (two concurrent identical webhooks within 100ms)

1. Both requests pass signature verification simultaneously
2. Request A: `update_one` with `upsert=True` → inserts (wins)
3. Request B: `update_one` with `upsert=True` → MongoDB attempts to insert, DuplicateKeyError raised by unique index, driver retries as update → matches existing doc → no-op. `result.upserted_id == None`
4. Both requests return 200 OK, but only ONE triggers `process_webhook`

### Regressions (MUST NOT BREAK)

1. ✅ Signature verification flow unchanged
2. ✅ First-occurrence events still insert normally
3. ✅ `process_webhook` still runs once per unique event
4. ✅ Counter reporting (`events_saved`, `jobs_updated`) still increments correctly
5. ✅ Existing `try/except` around operations still catches unrelated errors
6. ✅ No change to any other endpoint
7. ✅ No frontend change
8. ✅ No new dependencies

---

## Out of scope

- ❌ Adding PayPlus/Green Invoice webhook handlers (they don't exist today; when added, they'll need their own idempotency — separate batches)
- ❌ Moving the webhook handler to a queue-based processing model
- ❌ Changing the webhook signature verification mechanism
- ❌ Fixing TOCTOU on signature verification (Batch S5b — separate)
- ❌ Fixing MEDIUM code-audit findings (Batch S5c)
- ❌ Retiring the `whatsapp_events` collection or changing its schema beyond the index
- ❌ Feature-flagging this fix
- ❌ Backfilling `wa_message_id` / `event_type` / `status` fields on legacy rows

---

## Tasks

### Task 1 — STEP 0 investigation (mandatory before coding)

Run these grep checks and Mongo queries. Report all findings in `review.txt` before any code change.

```bash
# (a) Confirm handler location + line numbers:
grep -n "whatsapp_webhook_receive\|@router.post(\"/webhooks/whatsapp\"" backend/contractor_ops/notification_router.py
# Expected: handler around line 153.

# (b) Find both insert_one call sites:
grep -n "db.whatsapp_events.insert_one" backend/contractor_ops/notification_router.py
# Expected: 2 hits (status event + message event, around lines 214 and 260).

# (c) Check for existing index creation on whatsapp_events:
grep -rn "whatsapp_events" backend/contractor_ops/ | grep -iE "create_index|ensure_index"
# Expected: zero hits per audit. If any hits — document what index exists.

# (d) Check if there's a central index-creation module (startup hook):
grep -rn "def.*ensure_indexes\|def.*create_indexes\|def.*init_indexes" backend/contractor_ops/
# Likely there's a function called at startup. We'll add our index there.

# (e) Verify process_webhook location for reference:
grep -n "async def process_webhook" backend/contractor_ops/notification_service.py
# Expected: around line 965. We don't modify this function, just report line number.

# (f) Check whatsapp_events for existing duplicate (wa_message_id, event_type, status) tuples.
# This MUST be done in MongoDB Atlas before creating a unique index.
# Run in Atlas UI → whatsapp_events collection → Aggregation pipeline tab:
#
# [
#   { $group: {
#       _id: { wa_message_id: "$wa_message_id", event_type: "$event_type", status: "$status" },
#       count: { $sum: 1 },
#       ids: { $push: "$_id" }
#     }
#   },
#   { $match: { count: { $gt: 1 } } }
# ]
#
# Report the count of duplicate groups. If >0, we need a cleanup step before creating the unique index.

# (g) Count rows with null event_type OR null status.
# A unique index on (wa_message_id, event_type, status) treats null as a value —
# multiple null/null docs would be considered "the same key" → index build fails.
# Run in Atlas Mongo shell or Compass:
#
#   db.whatsapp_events.countDocuments({ event_type: null })
#   db.whatsapp_events.countDocuments({ status: null })
#   db.whatsapp_events.countDocuments({ event_type: { $exists: false } })
#   db.whatsapp_events.countDocuments({ status: { $exists: false } })
#
# Report all 4 counts. If ANY are >0:
#   → those legacy rows have missing fields and must be either:
#     (a) backfilled — set event_type='unknown', status='' (or similar safe defaults)
#     (b) deleted — if known to be junk/test data
#   → Task 2.5 MUST handle these BEFORE index creation, otherwise build fails.

# (h) Confirm exact webhook path for accurate post-deploy testing.
# The Tests A-E in this spec use a path placeholder — derive the exact one here:
grep -n "@router.post" backend/contractor_ops/notification_router.py
# Look for the line with "/webhooks/whatsapp" or similar. The full URL for testing is:
#   https://api.brikops.com<APP_PREFIX><router.prefix><handler.path>
# If router has prefix "/api" and handler is @router.post("/webhooks/whatsapp"),
# then the test URL is https://api.brikops.com/api/webhooks/whatsapp
# Document the exact URL in review.txt — Tests A-E will copy-paste from there.

# (i) Estimate index build duration to decide deploy timing.
# Run in Atlas Mongo shell or Compass:
#
#   db.whatsapp_events.countDocuments({})
#
# Decision tree:
#   <10k rows  → background build completes in <10 sec. Deploy any time, no concern.
#   10k-100k   → background build takes 10-60 sec. Still OK during normal hours; just don't deploy during a known traffic spike.
#   >100k      → background build may take minutes. Schedule deploy during low-traffic window
#               (early morning IDT preferred). Even with background=True, the index build
#               consumes IO and could slow concurrent writes.
#
# Report current count. We expect <1k rows at current scale (~41 users in beta).
```

**Do NOT proceed to Task 2 until STEP 0 passes AND any blockers (duplicates, nulls) are documented.**

**Decision tree after STEP 0:**
- If (f) returns zero duplicates AND (g) returns all zeros → proceed directly to Task 2 + Task 3 + Task 4
- If (f) returns some duplicates OR (g) returns any nonzero → **pause and report all counts**. Zahi decides: clean up via Task 2.5 (script handles BOTH duplicates AND nulls), OR clean up manually first.
- If (i) shows >100k rows → coordinate deploy timing with Zahi (low-traffic window).
- (h) is documentation-only — Tests A-E will use the exact path discovered.

---

### Task 2 — Add compound unique index on `whatsapp_events`

**File:** wherever index creation lives (identified in STEP 0 check d).

If there's a central `ensure_indexes()` function, add the index there. Example code pattern (adapt to the existing file location):

```python
# In the indexes module (likely db.py or a startup hook)
await db.whatsapp_events.create_index(
    [('wa_message_id', 1), ('event_type', 1), ('status', 1)],
    unique=True,
    name='wa_message_id_event_type_status_unique',
    background=True,  # non-blocking index build
)
```

**If no central index module exists** (unlikely but possible per STEP 0): add the `create_index` call inside the notification_router's startup hook, OR in the main app startup code. Use the exact same pattern other collections follow.

**Why this index:**
- Enforces at-most-one row per `(wa_message_id, event_type, status)` tuple
- Makes upsert race-safe (concurrent inserts get DuplicateKeyError → driver retries as update)
- Speeds up upsert queries (the query filter is exactly the index key)
- `background=True` so index build doesn't block writes on existing collections

**Migration caveat:** If STEP 0 (f) found existing duplicates, the unique index build WILL FAIL. You must resolve duplicates first (Task 2.5 if needed).

**Do NOT:**
- ❌ Use a partial index (`partialFilterExpression`) — we want strict uniqueness
- ❌ Drop any existing indexes on `whatsapp_events` — we ADD, not replace
- ❌ Index on `wa_message_id` alone — not unique for status transitions

---

### Task 2.5 (CONDITIONAL) — Clean up duplicates AND nulls before index creation

**Run if STEP 0 (f) found duplicate groups OR STEP 0 (g) found rows with null `event_type` / null `status`.**

A unique compound index on `(wa_message_id, event_type, status)` will fail to build if EITHER condition exists. Both must be resolved first.

One-time script (run from Replit shell before index creation):

```python
# cleanup_whatsapp_events.py — one-time, deleted after use
import asyncio
from contractor_ops.db import get_db

async def main():
    db = get_db()

    # ─── STEP 1: Backfill missing event_type and status fields ───
    # Strategy: rows with missing fields are pre-fix legacy data with no
    # safe way to reconstruct the original Meta payload. Mark them
    # explicitly so they participate in the unique index without colliding.
    
    backfill_event_type = await db.whatsapp_events.update_many(
        {'$or': [{'event_type': None}, {'event_type': {'$exists': False}}]},
        {'$set': {'event_type': 'legacy_unknown'}}
    )
    print(f"Backfilled event_type='legacy_unknown' on {backfill_event_type.modified_count} rows")

    backfill_status = await db.whatsapp_events.update_many(
        {'$or': [{'status': None}, {'status': {'$exists': False}}]},
        {'$set': {'status': ''}}  # empty string is the canonical "no status" marker per the message-event shape
    )
    print(f"Backfilled status='' on {backfill_status.modified_count} rows")

    # ─── STEP 2: Delete duplicate (wa_message_id, event_type, status) groups, keep earliest ───
    pipeline = [
        {'$group': {
            '_id': {'wa_message_id': '$wa_message_id', 'event_type': '$event_type', 'status': '$status'},
            'count': {'$sum': 1},
            'ids': {'$push': '$_id'},
            'received_at_list': {'$push': '$received_at'}
        }},
        {'$match': {'count': {'$gt': 1}}},
    ]
    total_deleted = 0
    async for group in db.whatsapp_events.aggregate(pipeline):
        # Keep the earliest received_at, delete the rest
        ids_by_time = sorted(zip(group['received_at_list'], group['ids']))
        ids_to_delete = [gid for _, gid in ids_by_time[1:]]
        if ids_to_delete:
            result = await db.whatsapp_events.delete_many({'_id': {'$in': ids_to_delete}})
            total_deleted += result.deleted_count
            print(f"Group {group['_id']}: deleted {result.deleted_count} duplicates")
    print(f"Total duplicates deleted: {total_deleted}")

    # ─── STEP 3: Verification — confirm no nulls or duplicates remain ───
    null_event_type = await db.whatsapp_events.count_documents({'event_type': None})
    null_status = await db.whatsapp_events.count_documents({'status': None})
    missing_event_type = await db.whatsapp_events.count_documents({'event_type': {'$exists': False}})
    missing_status = await db.whatsapp_events.count_documents({'status': {'$exists': False}})
    
    remaining_dupes = 0
    async for _ in db.whatsapp_events.aggregate(pipeline):
        remaining_dupes += 1

    print(f"\n=== Cleanup verification ===")
    print(f"null event_type:    {null_event_type}")
    print(f"null status:        {null_status}")
    print(f"missing event_type: {missing_event_type}")
    print(f"missing status:     {missing_status}")
    print(f"remaining dup groups: {remaining_dupes}")
    
    if any([null_event_type, null_status, missing_event_type, missing_status, remaining_dupes]):
        print("\n❌ CLEANUP INCOMPLETE — DO NOT proceed to index creation")
        return
    print("\n✅ CLEANUP COMPLETE — safe to create unique index (Task 2)")

asyncio.run(main())
```

**Run once, check the verification block at the end shows all zeros, then proceed to Task 2 (index creation).**

**Notes:**
- Backfill uses `'legacy_unknown'` for missing event_type so legacy rows are bucketed together but distinguishable from real data.
- Backfill uses `''` for missing status (matches message-event shape per line 252 of notification_router.py).
- Duplicate deletion keeps earliest `received_at` (preserves chronological audit trail).
- `audit_events` from prior duplicate processing is NOT rolled back (can't safely reconstruct). Acceptable data-cleanup loss for pre-launch test data.
- After this script runs, **delete it** — it's a one-time tool, not committed to the repo.

---

### Task 3 — Replace `insert_one` with atomic upsert (status events)

**File:** `backend/contractor_ops/notification_router.py`

**Find with:** `grep -n "db.whatsapp_events.insert_one" backend/contractor_ops/notification_router.py` — identify the status-event insert (around line 214).

**Current code (around line 213-232):**
```python
try:
    await db.whatsapp_events.insert_one(event_doc)
    events_saved += 1
except Exception as e:
    logger.error(f"[WA] failed to save status event: {e}")

# ... process_webhook call follows around line 230 ...
```

**Replace with:**
```python
try:
    # Atomic upsert — race-safe dedup.
    # Matches audit recommendation: (wa_message_id, event_type, status) is the unique key.
    # See Batch S5a fix for code-audit CRITICAL finding 2026-04-24.
    result = await db.whatsapp_events.update_one(
        {
            'wa_message_id': provider_id,
            'event_type': 'status',
            'status': wa_status,
        },
        {'$setOnInsert': event_doc},
        upsert=True,
    )
    if result.upserted_id is None:
        # Duplicate event (Meta retry or network race) — skip outbound processing.
        duplicates_skipped += 1
        logger.info(f"[WA] duplicate status event skipped: {provider_id}/{wa_status}")
        continue  # skip process_webhook + everything below in this iteration
    events_saved += 1
except Exception as e:
    logger.error(f"[WA] failed to save status event: {e}")
    continue  # match existing error-recovery: skip this iteration on DB failure
```

**Initialize `duplicates_skipped` counter** at the top of the loop block (same place as `events_saved`). Return it in the final response JSON as a new field (for observability).

**Critical:** the `continue` statement after duplicate detection means `process_webhook` is skipped for duplicates. This is the main behavioral fix.

**Do NOT:**
- ❌ Do NOT remove or restructure the existing `except Exception` catch — keep error-resilience
- ❌ Do NOT call `process_webhook` before the upsert check — it MUST be gated behind `upserted_id is not None`
- ❌ Do NOT add a new DB query before the upsert (e.g., `find_one` "check first") — that introduces TOCTOU. Atomic upsert is the whole point.

---

### Task 4 — Replace `insert_one` with atomic upsert (incoming messages)

**File:** `backend/contractor_ops/notification_router.py`

**Find with:** same grep as Task 3 — identify the message-event insert (around line 260).

**Current code (around line 259-264):**
```python
try:
    await db.whatsapp_events.insert_one(event_doc)
    events_saved += 1
except Exception as e:
    logger.error(f"[WA] failed to save message event: {e}")
```

**Replace with:**
```python
try:
    result = await db.whatsapp_events.update_one(
        {
            'wa_message_id': msg_id,
            'event_type': 'message',
            'status': '',  # messages have empty status per the doc shape (line 252)
        },
        {'$setOnInsert': event_doc},
        upsert=True,
    )
    if result.upserted_id is None:
        duplicates_skipped += 1
        logger.info(f"[WA] duplicate message event skipped: {msg_id}")
        continue
    events_saved += 1
except Exception as e:
    logger.error(f"[WA] failed to save message event: {e}")
    continue
```

**Notes:**
- For messages, there's usually no downstream `process_webhook` call (messages are stored for manual review). Verify in STEP 0 by reading lines 260-269 — if there IS a downstream action, ensure it's inside the "new event" branch only.
- Use empty-string `status: ''` in the filter to match the doc shape (line 252 has `'status': '',`).

**Do NOT:**
- ❌ Use a different dedup key than Task 3. Consistency matters.
- ❌ Split this into a separate commit from Task 3 — they're the same bug, same file.

---

## Relevant files

### Modified:
- `backend/contractor_ops/notification_router.py` — 2 insert blocks replaced with atomic upsert (lines ~214, ~260). New `duplicates_skipped` counter returned in the response JSON.
- Index module (location TBD per STEP 0 — likely `db.py` or a startup hook) — new `create_index` call for `whatsapp_events`.

### Untouched (CRITICAL):
- `backend/contractor_ops/notification_service.py` — `process_webhook()` unchanged (line ~965)
- `_verify_signature` function in notification_router.py — TOCTOU issue belongs to S5b, not this batch
- All other backend files — zero diff
- All frontend files — zero diff
- `requirements.txt`, `package.json` — zero diff
- Response JSON shape — minor addition (`duplicates_skipped` field); no removed fields

---

## DO NOT

- ❌ Do NOT feature-flag this. Security/integrity fix.
- ❌ Do NOT modify `_verify_signature` — that's S5b.
- ❌ Do NOT modify `process_webhook` in notification_service.py.
- ❌ Do NOT use `find_one + insert_one` (TOCTOU race).
- ❌ Do NOT create the unique index if duplicates exist — run Task 2.5 cleanup first.
- ❌ Do NOT skip Task 2 (index creation) and rely only on application-level upsert — without the index, concurrent upserts can still both insert.
- ❌ Do NOT change the response JSON structure beyond adding `duplicates_skipped`.
- ❌ Do NOT add `process_webhook` invocation inside an else-branch of the upsert check — it should stay where it is today (right after the try block), but the `continue` on duplicate skips to next iteration BEFORE reaching process_webhook.
- ❌ Do NOT backfill missing `event_type` or `status` on legacy rows — out of scope.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) Atomic upsert present (2 hits — one per insert site):
grep -n "update_one" backend/contractor_ops/notification_router.py | head -10
# Expected: 2 NEW hits for whatsapp_events.update_one (status + message).

# (b) Old insert_one calls are gone:
grep -n "db.whatsapp_events.insert_one" backend/contractor_ops/notification_router.py
# Expected: 0 hits.

# (c) $setOnInsert present twice:
grep -n "\$setOnInsert" backend/contractor_ops/notification_router.py
# Expected: 2 hits.

# (d) upserted_id check present twice:
grep -n "upserted_id is None" backend/contractor_ops/notification_router.py
# Expected: 2 hits.

# (e) duplicates_skipped counter introduced:
grep -n "duplicates_skipped" backend/contractor_ops/notification_router.py
# Expected: at least 4 hits (initialize + 2 increments + return field).

# (f) Unique compound index created:
grep -rn "wa_message_id_event_type_status_unique\|wa_message_id.*event_type.*status.*unique" backend/contractor_ops/
# Expected: 1 hit in the index module.

# (g) process_webhook call unchanged:
grep -n "engine.process_webhook" backend/contractor_ops/notification_router.py
# Expected: same count as before (we don't remove or duplicate this call, just skip past it on duplicates).

# (h) _verify_signature unchanged:
grep -n "def _verify_signature\|_verify_signature(" backend/contractor_ops/notification_router.py
# Expected: same count and content as before.

# (i) No frontend change:
git diff --stat frontend/
# Expected: empty.

# (j) No schema change:
git diff --stat backend/contractor_ops/schemas.py
# Expected: empty.

# (k) No new deps:
git diff backend/requirements.txt frontend/package.json
# Expected: empty.
```

### 2. Python import check

```bash
cd backend
python -c "from contractor_ops.notification_router import router; print('OK')"
# Expected: no import errors.
```

### 3. Frontend build (sanity — should be untouched)

```bash
cd frontend && REACT_APP_BACKEND_URL=https://example.com CI=true npm run build
```

Expected: same 3 pre-existing apple-sign-in warnings only. No new warnings.

### 4. Manual tests (post-deploy)

#### Test A — First webhook succeeds (happy path)

Simulate a valid webhook from Meta. Easiest: use a real status event from the WhatsApp Business API sandbox, OR manually curl with proper signature:

```bash
# Generate a signed payload (requires META_APP_SECRET)
PAYLOAD='{"object":"whatsapp_business_account","entry":[...]}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$META_APP_SECRET" | cut -d' ' -f2)

curl -X POST https://api.brikops.com/api/webhooks/whatsapp \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
```

- ✅ Returns 200
- ✅ `events_saved: 1` in response
- ✅ `duplicates_skipped: 0`
- ✅ Row appears in `whatsapp_events` collection

#### Test B — Replay same webhook immediately (dedup works)

Run the exact same curl command again (same payload, same signature) within 2 seconds:

- ✅ Returns 200
- ✅ `events_saved: 0`
- ✅ `duplicates_skipped: 1`
- ✅ NO new row in `whatsapp_events` (count unchanged)
- ✅ NO new row in `audit_events` (process_webhook was skipped)

**This is the main test — confirms both the DB-side dedup AND the processing-side skip.**

#### Test C — Different status on same message = new event

Send a webhook with same `wa_message_id` but different `status` (e.g., was `sent`, now `delivered`):

- ✅ Returns 200
- ✅ `events_saved: 1`
- ✅ `duplicates_skipped: 0`
- ✅ New row inserted (dedup key is the TUPLE, not just wa_message_id)

#### Test D — Index enforces uniqueness at DB level

Attempt manual insert of duplicate directly in Mongo shell:

```javascript
db.whatsapp_events.insertOne({
  id: "test-uuid",
  wa_message_id: "<existing_wa_message_id>",
  event_type: "status",
  status: "delivered",
  // ... other fields
})
```

- ✅ MongoDB returns `DuplicateKeyError`
- ✅ No row inserted

#### Test E — Signature verification still works (regression)

Send a webhook with INVALID signature:

```bash
curl -X POST https://api.brikops.com/api/webhooks/whatsapp \
  -H "X-Hub-Signature-256: sha256=0000000000000000000000000000000000000000000000000000000000000000" \
  -d '{}'
```

- ✅ Returns 401
- ✅ No insert, no processing

#### Test F — Production traffic smoke test (24h observation)

After deploy, monitor `whatsapp_events` collection growth rate:

- ✅ Growth is linear with actual WA message volume (not doubled)
- ✅ If prior duplicates existed (Task 2.5 was run), total doc count is net-smaller
- ✅ `notification_jobs` table shows no anomalous status oscillations

---

## Commit message (exactly)

```
fix(security): idempotent WhatsApp webhook via atomic upsert + unique index (Batch S5a)

Pre-launch code-audit fix. 2026-04-24 audit found S5-CRIT-1: WhatsApp
webhook at notification_router.py:153-269 had no idempotency mechanism.
Meta retries on 5xx / network blips / ACK timeouts (standard Meta
behavior, ~2-5% of webhook batches). Each retry produced:
- Duplicate whatsapp_events row
- Duplicate call to engine.process_webhook → duplicate audit_events row
- Duplicate (idempotent but wasteful) notification_jobs update

Fix: atomic upsert at both webhook insert sites (status + message)
with compound unique index on (wa_message_id, event_type, status).
Skip outbound process_webhook when upsert returns None (duplicate
detected). Race-safe via MongoDB unique-constraint retry semantics.

Other webhooks audited: no PayPlus/Green Invoice/billing webhooks
exist. This patch covers the full webhook attack surface.

One file modified (notification_router.py). One index added via
existing ensure_indexes pattern. No schema migration. No frontend.
No new deps.
```

---

## Deploy

### 2-phase rollout (same as S1/S2)

#### Phase 1 — Capture revert anchor

```bash
git log -1 --format="%H %s" > /tmp/pre-s5a-head.txt
cat /tmp/pre-s5a-head.txt
# Paste SHA at top of review.txt
```

**Revert is one command:**
```bash
git revert <SHA> --no-edit
./deploy.sh --prod
```

Note: revert will NOT drop the unique index automatically. If index is causing issues (unlikely), manually drop via Mongo:
```javascript
db.whatsapp_events.dropIndex("wa_message_id_event_type_status_unique")
```

#### Phase 2 — Deploy to prod

```bash
./deploy.sh --prod
```

Backend-only change. EB health check green in ~5-10 min. Index is built in background — no downtime.

**After EB green:**
1. Verify index exists: `db.whatsapp_events.getIndexes()` — should show `wa_message_id_event_type_status_unique`
2. Run Tests A-E.
3. If anything fails → revert (code) + drop index manually if needed.

---

## Post-deploy monitoring (first 24h)

### Monitor #1 — Webhook success rate

- Before fix: ~100% succeed (just sometimes saving duplicates)
- After fix: ~100% still succeed; `duplicates_skipped` counter non-zero if retries are happening

### Monitor #2 — `whatsapp_events` growth

- Should grow LINEARLY with actual WA traffic, not faster
- If growth suddenly slows dramatically after deploy → confirms duplicates were being written before and are now being prevented

### Monitor #3 — `audit_events` growth

- Should track 1:1 with `whatsapp_events` unique inserts (each new event → one audit)
- If audit growth is lower than before → confirms duplicate processing is now prevented

### Monitor #4 — Error logs

- `"duplicate status event skipped"` and `"duplicate message event skipped"` are informational, not errors
- Watch for any new error patterns around `whatsapp_events` — if there's a burst of DuplicateKeyError in logs, driver is handling them via retry (good), but high frequency means lots of concurrent retries (investigate Meta retry behavior)

---

## Definition of Done

- [ ] STEP 0 all 6 grep/query checks pass
- [ ] If duplicates found in STEP 0 (f) → Task 2.5 cleanup ran and zero remain
- [ ] Task 2: unique compound index created on `whatsapp_events`
- [ ] Task 3 + Task 4: both insert sites replaced with atomic upsert + process_webhook gated on new-event
- [ ] `duplicates_skipped` counter returned in response JSON
- [ ] All 11 VERIFY grep checks pass
- [ ] Python import check clean
- [ ] Frontend build clean (unchanged warnings only)
- [ ] Tests A-E pass on prod
- [ ] `./deploy.sh --prod` succeeded
- [ ] EB health check green
- [ ] 24h post-deploy monitoring shows healthy growth of both collections
