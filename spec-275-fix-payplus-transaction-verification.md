# #275 — Fix PayPlus Transaction Verification Endpoint

## What & Why
The `get_transaction()` function in `payplus_service.py` calls `POST /Transactions/{uid}/Check` — an endpoint that does not exist in PayPlus's API. It returns 403 in production. The correct endpoint for verifying a transaction is `POST /PaymentPages/ipn`, which accepts `transaction_uid` or `payment_request_uid` or `more_info` in the request body. This is confirmed by PayPlus's official WooCommerce plugin (GitHub: PayPlus-Gateway/payplus-payment-gateway). Currently we use a workaround that skips `get_transaction()` entirely and trusts the webhook `more_info` field. This task fixes `get_transaction()` to use the correct endpoint, then wires it back into the webhook as the primary verification path with the current `more_info` approach as fallback.

## Done looks like
- `get_transaction()` calls `POST {base_url}/PaymentPages/ipn` with `{"transaction_uid": "...", "related_transaction": true}`
- Production webhook uses `get_transaction()` as primary verification
- If `get_transaction()` fails, falls back to current `more_info` verification (no behavior change from today)
- Logs show `[PAYPLUS] get_transaction tx=xxx status=200` instead of `status=403`
- PAYPLUS_CHECK_TEST logging line removed (it did its job)

## Out of scope
- No changes to sandbox/dev mode flow
- No changes to `charge_token()` or `create_payment_page()` or `refund_transaction()`
- No changes to frontend billing pages
- No changes to invoice generation
- No changes to `set_org_plan()`

## Tasks

### Phase 1 — Fix `get_transaction()` endpoint

1. In `backend/contractor_ops/payplus_service.py` line 147-166, replace the `get_transaction()` function:

**BEFORE (line 148):**
```python
url = f"{_base_url()}/Transactions/{transaction_uid}/Check"
payload = {"terminal_uid": PAYPLUS_TERMINAL_UID}
```

**AFTER:**
```python
url = f"{_base_url()}/PaymentPages/ipn"
payload = {
    "transaction_uid": transaction_uid,
    "related_transaction": True,
}
```

2. Update the response parsing in the same function. The `/PaymentPages/ipn` response structure is:
```json
{
  "results": {"status": "success", "code": 0, "description": "..."},
  "data": {
    "status_code": "000",
    "transaction_uid": "...",
    "four_digits": "1234",
    "amount": 1.0,
    "more_info": "org_id_here",
    "related_transactions": [...]
  }
}
```
Keep returning the full `data` dict as today. No change needed to return value.

3. Remove the `terminal_uid` import if it's no longer used anywhere else:
```
grep -rn "PAYPLUS_TERMINAL_UID" backend/contractor_ops/ | grep -v .pyc
```
If `charge_token()` (line 119) still uses it — keep the import. Only remove if unused.

### Phase 2 — Wire back into webhook as primary verification with fallback

4. In `backend/contractor_ops/billing_router.py` lines 1372-1400 (the production verification block), replace the current `more_info`-only path with:

```python
if PAYPLUS_ENV == "production":
    # Primary: verify via PayPlus IPN endpoint
    try:
        verified_data = await get_transaction(transaction_uid)
        verified_tx = verified_data.get("data", {})
        verified_status = verified_tx.get("status_code", "")
        if verified_status != "000":
            logger.info("[PAYPLUS-WH] Non-success status=%s tx=%s — skipping", verified_status, transaction_uid)
            await db.payplus_webhook_log.update_one({'id': log_id}, {'$set': {'result': 'non_success', 'status_code': verified_status}})
            return {"status": "ok"}
        logger.info("[PAYPLUS-WH] Verified via IPN endpoint tx=%s", transaction_uid)
    except Exception as e:
        # Fallback: verify via more_info org_id match (current workaround)
        logger.warning("[PAYPLUS-WH] IPN verify failed tx=%s: %s — falling back to more_info", transaction_uid, e)
        wh_org_id = (
            body.get("more_info", "") or
            body.get("transaction", {}).get("more_info", "")
        ).strip()
        if wh_org_id.startswith("org_id="):
            wh_org_id = wh_org_id.split("=", 1)[1]
        if not wh_org_id:
            logger.error("[PAYPLUS-WH] No org_id in more_info tx=%s", transaction_uid)
            await db.payplus_webhook_log.update_one({'id': log_id}, {'$set': {'result': 'rejected_no_org_id'}})
            raise HTTPException(status_code=500, detail="Missing org identifier")
        sub = await db.subscriptions.find_one(
            {"org_id": wh_org_id, "checkout_created_at": {"$exists": True}},
            {"_id": 0})
        if not sub:
            logger.error("[PAYPLUS-WH] No pending checkout org=%s tx=%s", wh_org_id, transaction_uid)
            await db.payplus_webhook_log.update_one({'id': log_id}, {'$set': {'result': 'rejected_no_pending_checkout'}})
            raise HTTPException(status_code=400, detail="No pending checkout")
        verified_tx = body.get("transaction", {})
        verified_status = verified_tx.get("status_code", "")
        if verified_status != "000":
            logger.info("[PAYPLUS-WH] Non-success status=%s tx=%s — skipping", verified_status, transaction_uid)
            await db.payplus_webhook_log.update_one({'id': log_id}, {'$set': {'result': 'non_success', 'status_code': verified_status}})
            return {"status": "ok"}
        logger.info("[PAYPLUS-WH] Verified via more_info fallback org_id=%s tx=%s", wh_org_id, transaction_uid)
```

5. Remove the PAYPLUS_CHECK_TEST logging line (search for it):
```
grep -rn "PAYPLUS_CHECK_TEST" backend/ | grep -v .pyc
```
Delete that line — it did its job.

6. Remove the `# ⚠️ TEMPORARY` and `# TODO: Contact PayPlus support` comments (lines 1374-1376) — no longer needed.

## Relevant files
- `backend/contractor_ops/payplus_service.py:147-166` — `get_transaction()` function
- `backend/contractor_ops/billing_router.py:1343-1410` — webhook handler, production verification block

## DO NOT
- ❌ Don't change `charge_token()`, `create_payment_page()`, or `refund_transaction()`
- ❌ Don't change the sandbox/dev mode flow (lines 1401-1408)
- ❌ Don't change the rest of the webhook handler after the verification block
- ❌ Don't change any frontend code
- ❌ Don't add new dependencies
- ❌ Don't change the `_auth_headers()` format — PayPlus requires the Authorization header as a JSON string
- ❌ Don't remove the `more_info` fallback path — it's our safety net
- ❌ Don't change how `more_info` is set in `create_payment_page()` or `charge_token()`

## VERIFY

Phase 1 — Unit test `get_transaction()`:
1. In sandbox: call `get_transaction("some-known-transaction-uid")` manually
2. Check logs: should see `[PAYPLUS] get_transaction tx=xxx status=200` (not 403)
3. Response should contain `data.status_code` and `data.transaction_uid`

Phase 2 — End-to-end:
1. Make a test payment in sandbox
2. Check webhook logs: should see `[PAYPLUS-WH] Verified via IPN endpoint tx=xxx`
3. If IPN fails for any reason: should see `falling back to more_info` and payment still completes
4. Verify payment flow works end-to-end — subscription updated, invoice created

STOP after Phase 1. Report the response from `/PaymentPages/ipn`. Wait for approval before Phase 2.
