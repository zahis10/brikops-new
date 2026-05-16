# #427 — Batch S7 — Shannon HIGH fix (XSS upload + login lockout + webhook auth + paywall bypass)

## What & Why

**Public-launch blockers (HIGH severity).** Shannon (Keygraph) AI pentest scan on 2026-04-26 found 4 HIGH-severity vulnerabilities + 1 MEDIUM that's worth fixing alongside (paywall bypass — directly related to HIGH-A). All five must ship before public launch.

| # | Finding | Severity | Vulnerable file |
|---|---|---|---|
| HIGH-A | Stored XSS via contractor proof upload | HIGH | `tasks_router.py:838-855`, `storage_service.py:69` |
| HIGH-B | No per-account lockout on login (brute force) | HIGH | `auth_router.py:270` (`/login`), `onboarding_router.py:565` (`/login-phone`) |
| HIGH-C | PayPlus webhook HMAC bypass via User-Agent | HIGH | `billing_router.py:1444-1458` |
| HIGH-D | GreenInvoice webhook auth skipped when secret unset | HIGH | `billing_router.py:1279-1291` + `server.py` (startup guard) |
| MED-D | Authorization case-sensitivity bypasses paywall | MEDIUM | `server.py:1341` |
| MED-A (bonus) | Account enumeration via `/login-phone` Hebrew error messages | MEDIUM | `onboarding_router.py:565` (folded into HIGH-B fix) |

These 6 findings are independent fixes across 6 files (`tasks_router.py`, `storage_service.py`, `auth_router.py`, `onboarding_router.py`, `billing_router.py`, `server.py`). Group them in one spec for atomic deploy.

**Same framing as S1/S2/S5/S6:** internal testers only, no breach. Pre-launch hygiene before public marketing.

---

## Files to change

### 1. `backend/contractor_ops/tasks_router.py` — fix HIGH-A (XSS upload)

**Problem (line 838-855):** The contractor-proof upload endpoint has zero file type validation. The sibling endpoint at line 1148 already correctly calls `validate_upload(file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)`.

**Fix:** Mirror what line 1148 already does. Add `validate_upload(...)` call before the S3 upload.

The change (in the `contractor-proof` upload handler, immediately after the file is received and before the S3 upload):

```python
# S7 — SECURITY FIX: validate file type to block stored XSS via HTML upload.
# Mirrors the validation already in place for regular task attachments at line 1148.
from .upload_validators import validate_upload, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES
validate_upload(file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
```

(Use the same import pattern that line 1148 uses — adapt to whatever module the validators live in.)

**Also fix `storage_service.py:69`:** Currently derives extension from `file.filename.split('.')[-1]` and content-type from `file.content_type` — both attacker-controlled. Whitelist the extension based on validated MIME type:

```python
# S7 — SECURITY FIX: derive S3 key extension from validated content-type, not user input.
EXT_BY_MIME = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
    'application/pdf': 'pdf',
}
ext = EXT_BY_MIME.get(file.content_type, 'bin')
```

### 2. `backend/contractor_ops/auth_router.py` + `onboarding_router.py` — fix HIGH-B (login lockout)

**Problem:** No per-account failed-login counter on either password-based login endpoint. 35 consecutive failures = 0 lockout, 0 rate-limit.

**Verified scope (2026-04-27):**
- ✅ `/api/auth/login` (`auth_router.py:270`) — email + password, NEEDS lockout
- ✅ `/api/auth/login-phone` (`onboarding_router.py:565`) — phone + password, NEEDS lockout
- ❌ `/api/auth/verify-otp` (`onboarding_router.py:274`) — OTP-based, ALREADY has IP rate limit (20/15min via `_check_rate_limit_mongo`). DO NOT touch.
- ❌ `/api/auth/social/verify-otp` — already has rate limit. DO NOT touch.

**Fix design (incorporates 3 critical security concerns flagged during review):**

1. **No user enumeration via response codes:** Both "wrong password" and "lockout reached" must return identical status code (401) and identical detail message. Only the `Retry-After` header differs on lockout — and even that is fact attacker can learn but doesn't disclose existence.

2. **No DoS amplification via per-email lockout:** Lockout key is `(email, ip)` tuple — NOT just email. This way an attacker who tries 5 wrong passwords on the founder's email locks themselves out, not the founder. Trade-off: botnet attackers get fresh attempts per IP — mitigation is detect via WAF/Cloudflare rules separately. (Future S8 enhancement: exponential backoff to handle botnet too.)

3. **Track even non-existent emails:** When user doesn't exist OR password is wrong — both increment the counter. Otherwise attacker can probe "is email X registered?" by checking which emails enter lockout state vs which don't.

**Schema (new MongoDB collection `auth_failed_attempts`):**
```js
{
  email: "user@example.com",     // primary key (composite with ip)
  ip: "1.2.3.4",                  // client IP from X-Forwarded-For or request.client.host
  count: 5,
  first_failure: ISODate(),
  last_failure: ISODate(),
  lockout_until: ISODate() | null   // null = not locked
}
```

**Logic in login handler (apply to BOTH `/api/auth/login` and `/api/auth/login-phone`, with appropriate identifier — email for `/login`, phone_e164 for `/login-phone`):**

```python
# S7 — SECURITY FIX: per-(account, IP) brute-force lockout.
# Single 401 response code for both wrong-password AND lockout (no enumeration).
# Per-IP scope (not just email) prevents DoS via account lockout amplification.
LOCKOUT_THRESHOLD = 5       # failures before lockout
LOCKOUT_WINDOW_MIN = 15     # window for counting failures
LOCKOUT_DURATION_MIN = 15   # how long lockout persists
GENERIC_AUTH_FAIL = "Authentication failed"

now = datetime.now(timezone.utc)
window_start = now - timedelta(minutes=LOCKOUT_WINDOW_MIN)
client_ip = _resolve_client_ip(request)  # use existing helper if available, else request.client.host
identifier = email  # for /login. For /login-phone, use phone_e164.

# Check if currently locked
record = await db.auth_failed_attempts.find_one({"email": identifier, "ip": client_ip})
if record and record.get("lockout_until") and record["lockout_until"] > now:
    retry_after_seconds = int((record["lockout_until"] - now).total_seconds())
    # 401 (not 429) — same status code as wrong-password to prevent enumeration
    raise HTTPException(
        status_code=401,
        detail=GENERIC_AUTH_FAIL,
        headers={"Retry-After": str(retry_after_seconds)}
    )

# Attempt the actual login
user = await db.users.find_one({"email": identifier})
auth_failed = (not user) or (not bcrypt.checkpw(password.encode(), user["password_hash"].encode()))

if auth_failed:
    # Increment counter (creates record if doesn't exist — even for non-existent users, to prevent enumeration)
    await db.auth_failed_attempts.update_one(
        {"email": identifier, "ip": client_ip},
        {
            "$inc": {"count": 1},
            "$set": {"last_failure": now},
            "$setOnInsert": {"first_failure": now},
        },
        upsert=True
    )
    # Check if threshold reached
    record = await db.auth_failed_attempts.find_one({"email": identifier, "ip": client_ip})
    if record["count"] >= LOCKOUT_THRESHOLD and record["first_failure"] > window_start:
        await db.auth_failed_attempts.update_one(
            {"email": identifier, "ip": client_ip},
            {"$set": {"lockout_until": now + timedelta(minutes=LOCKOUT_DURATION_MIN)}}
        )
    # Same 401 detail as the lockout case — no enumeration possible
    raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAIL)

# Success — clear the failed-attempts record (only for the IP that succeeded)
await db.auth_failed_attempts.delete_one({"email": identifier, "ip": client_ip})
```

**Existing `/login-phone` Hebrew-text errors must be replaced:** the current code returns `'מספר טלפון לא רשום'` for unregistered phones and `'סיסמה שגויה'` for wrong password (this is account enumeration MED-A in Shannon report). After this fix, both should return the same generic English `'Authentication failed'` (matching the `/login` endpoint's existing behavior).

**Mongo index** (add to startup `ensure_indexes()`):
```python
# Compound unique index on (email, ip) so lockout is per-(user, IP) tuple
await db.auth_failed_attempts.create_index([("email", 1), ("ip", 1)], unique=True, name="auth_failed_email_ip_unique")
# TTL index — auto-cleanup records 24h after last failure (prevents collection bloat)
await db.auth_failed_attempts.create_index("last_failure", expireAfterSeconds=86400, name="auth_failed_ttl")
```

**Note on `/login-phone` existing rate limit:** The endpoint already returns generic 429 errors for IP-based rate limiting via `_check_rate_limit_mongo`. The new per-(phone, IP) lockout sits ALONGSIDE this — they don't conflict. The IP-rate-limit fires first if any IP sends too many requests overall; the new lockout fires only after this specific (phone, IP) combination fails 5 password attempts.

### 3. `backend/contractor_ops/billing_router.py` — fix HIGH-C (PayPlus webhook)

**Problem (line 1444-1458, verified 2026-04-27):**
```python
pp_user_agent = request.headers.get("user-agent", "")
pp_hash = request.headers.get("hash", "")  # ← lowercase header
if pp_user_agent == "PayPlus" and pp_hash:
    expected_hash = hmac_module.new(
        PAYPLUS_SECRET_KEY.encode(),
        raw_body,
        hashlib.sha256
    ).digest()
    expected_b64 = base64.b64encode(expected_hash).decode()  # ← base64, not hex
    if not hmac_module.compare_digest(expected_b64, pp_hash):
        logger.warning("[PAYPLUS-WH] Hash mismatch — rejecting webhook")
        return {"status": "ok"}  # ← returns OK on hash mismatch (silent fail)
    logger.info("[PAYPLUS-WH] Hash validated successfully")
elif pp_user_agent != "PayPlus":
    logger.warning("[PAYPLUS-WH] Unexpected user-agent: %s — processing anyway", pp_user_agent)
    # ← falls through to billing logic without HMAC check
```

Two bugs in one block:
- HMAC check only fires when `User-Agent: PayPlus` is present (Shannon HIGH-C)
- Hash mismatch returns `{"status":"ok"}` (200) instead of 401 — silent fail allows attacker probing

**Fix:** ALWAYS require HMAC validation. Reject with 401 if hash missing or invalid. User-Agent must NEVER be a security boundary.

**The change (replace the entire HMAC validation block, lines ~1443-1458):**

```python
from config import PAYPLUS_ENV, PAYPLUS_SECRET_KEY

# S7 — SECURITY FIX: HMAC verification is MANDATORY for all webhook requests.
# Previously only fired when User-Agent="PayPlus" (trivially bypassable) and
# silently returned 200 on hash mismatch (allowed attacker probing).
pp_hash = request.headers.get("hash", "")
if not pp_hash:
    logger.error("[PAYPLUS-WH] Missing 'hash' header — rejecting webhook")
    raise HTTPException(status_code=401, detail="Missing webhook signature")

expected_hash = hmac_module.new(
    PAYPLUS_SECRET_KEY.encode(),
    raw_body,
    hashlib.sha256
).digest()
expected_b64 = base64.b64encode(expected_hash).decode()
if not hmac_module.compare_digest(expected_b64, pp_hash):
    logger.warning("[PAYPLUS-WH] Hash mismatch — rejecting webhook (was tolerant pre-S7)")
    raise HTTPException(status_code=401, detail="Invalid webhook signature")

logger.info("[PAYPLUS-WH] Hash validated successfully")
```

Notes:
- Header name is `hash` (lowercase) per PayPlus spec — verified in current code
- HMAC encoded as base64 (not hex) — verified in current code
- Use `hmac_module.compare_digest` (not `==`) — already correct in current code
- Variable name is `PAYPLUS_SECRET_KEY` (verified in `config.py:227`)

### 4. `backend/contractor_ops/billing_router.py` — fix HIGH-D (GreenInvoice webhook)

**Problem (line 1279-1291):**
```python
if GI_WEBHOOK_SECRET:
    # auth check happens here
    ...
# ← if GI_WEBHOOK_SECRET is falsy, entire auth block is skipped
```

**Fix:** Two-step. (a) Startup guard fails fast if GI is enabled (`GI_BASE_URL` set) but secret missing — pattern matches S5b TOCTOU fix. (b) Remove `if GI_WEBHOOK_SECRET:` wrap from handler — secret is now guaranteed at runtime.

**Important naming clarification:** GreenInvoice uses **static token authentication** (not HMAC like PayPlus). The `compare_digest()` call is for constant-time comparison to prevent timing attacks on string equality, NOT for HMAC. This is weaker than HMAC (vulnerable to replay if token leaks once) but it's a limitation of GreenInvoice's webhook spec — they don't support HMAC.

**Step 1 — startup guard in `server.py`** (after `set_meta_app_secret(...)` call, near the S5b TOCTOU guard):

```python
# S7 — Startup guard: refuse to boot if GreenInvoice billing is enabled but token missing.
# Prevents silent bypass of webhook authentication when GI_WEBHOOK_SECRET is unconfigured.
from config import GI_WEBHOOK_SECRET, GI_BASE_URL

if GI_BASE_URL and not GI_WEBHOOK_SECRET:
    raise RuntimeError(
        "Configuration error: GI_BASE_URL is set but GI_WEBHOOK_SECRET is not. "
        "GreenInvoice webhook authentication would be silently bypassed. "
        "Set GI_WEBHOOK_SECRET env var or unset GI_BASE_URL. Refusing to start."
    )
```

**Step 2 — handler in `billing_router.py:1279`:** Remove the `if GI_WEBHOOK_SECRET:` wrap. The check is now mandatory.

```python
# S7 — SECURITY FIX: validate static webhook token (GreenInvoice doesn't support HMAC).
# Use compare_digest to prevent timing attacks on string comparison.
# Secret presence guaranteed by startup guard (server.py).
provided_token = request.headers.get('X-Webhook-Token', '')
if not provided_token or not hmac_module.compare_digest(provided_token, GI_WEBHOOK_SECRET):
    logger.warning("[GI-WH] Invalid or missing X-Webhook-Token — rejecting")
    raise HTTPException(status_code=401, detail="Invalid webhook token")
```

⚠️ **Side effect for staging:** the staging EB has `GI_WEBHOOK_SECRET=STAGING_PLACEHOLDER` and `GI_BASE_URL=` (unset). After this change, staging will continue to boot (because `GI_BASE_URL` is unset → guard doesn't fire). When we eventually configure GI sandbox in staging, we'll set both vars together. **No env var change required for this deploy.**

⚠️ **Production check:** Verify that prod EB env has BOTH `GI_BASE_URL` AND `GI_WEBHOOK_SECRET` set before deploying. If `GI_BASE_URL` is set but secret is empty, the new startup guard will refuse to boot. This is BY DESIGN (we want fail-fast over silent bypass). Verify with: `aws elasticbeanstalk describe-configuration-settings --environment-name Brikops-api-env --query 'ConfigurationSettings[0].OptionSettings[?OptionName==\`GI_WEBHOOK_SECRET\` || OptionName==\`GI_BASE_URL\`]' --output json` before deploy.

### 5. `backend/contractor_ops/server.py` — fix MED-D (paywall case-sensitivity)

**Problem (line 1341):**
```python
auth_header = request.headers.get('Authorization', '')
if auth_header.startswith('Bearer '):  # ← case-sensitive
    # paywall check
```

**Fix:** Use case-insensitive comparison to match FastAPI's `HTTPBearer` behavior.

**The change (line 1341):**

```python
# S7 — SECURITY FIX: case-insensitive Bearer match (FastAPI HTTPBearer is case-insensitive).
# Previously, "Authorization: bearer X" (lowercase b) bypassed paywall while still authenticating.
auth_header = request.headers.get('Authorization', '')
if auth_header.lower().startswith('bearer '):
```

---

## Why this is safe

### HIGH-A safety
- The validator (`validate_upload`) is already used at line 1148 for regular attachments. We're extending the same proven pattern to contractor-proof uploads.
- Legitimate contractor proofs (PDFs, photos) will be unaffected. Only HTML/JS/exe attempts will be rejected.
- The `EXT_BY_MIME` whitelist eliminates the attacker-controlled extension input entirely.

### HIGH-B safety
- Only AFFECTS users who fail login. Successful logins are unaffected.
- 5 attempts is generous (real users with sticky-keys problem rarely hit this).
- 15-minute lockout is short enough not to lock out forgetful users for hours.
- The `expireAfterSeconds` index auto-cleans the collection so it doesn't grow unboundedly.

### HIGH-C safety
- HMAC is the documented PayPlus webhook authentication method. Legitimate PayPlus calls always include the `hash` header (lowercase, base64-encoded HMAC-SHA256).
- Removing the `User-Agent` short-circuit doesn't break PayPlus integration — they ALWAYS send the HMAC header.
- Changing the silent-200-on-mismatch to 401 means PayPlus retry logic will kick in if our secret rotates incorrectly, which is what we want (rather than silent payment loss).

### HIGH-D safety
- The startup guard only fires when GI is actually being used (`GI_BASE_URL` set). Staging without GI configured continues to work.
- Production already has GI_WEBHOOK_SECRET set (verified in prod EB config), so prod won't fail to boot.

### MED-D safety
- Case-insensitive Bearer match is what FastAPI uses internally.
- Backwards-compatible — existing `Bearer X` requests work unchanged.

---

## Done looks like

After deploy, every regression test in [`security/pentest-regression-checklist.md`](../security/pentest-regression-checklist.md) covering HIGH-A through MED-D (and the bonus MED-A account-enumeration one) must PASS. Specifically:

| Test | Pre-fix expected | Post-fix expected |
|---|---|---|
| HIGH-A: HTML upload | 200 (accepted) | 415 or 422 (rejected) |
| HIGH-B: 10 failed logins from same (account, IP) | No lockout | 401 with `Retry-After` header from attempt 6 onward (same status code as wrong-password — no enumeration) |
| HIGH-C: PayPlus without `hash` header | 200 (processed) | 401 "Missing webhook signature" |
| HIGH-C: PayPlus with bad HMAC | 200 (processed silently) | 401 "Invalid webhook signature" |
| HIGH-D: GI without `X-Webhook-Token` | 200 (processed) | 401 "Invalid webhook token" |
| HIGH-D: boot with `GI_BASE_URL` set + `GI_WEBHOOK_SECRET` unset | App boots silently | `RuntimeError` at startup |
| MED-D: `bearer` lowercase | Different status from `Bearer` | Same status (paywall enforced both ways) |
| MED-A (bonus): `/login-phone` with unregistered vs registered phone | Different Hebrew error messages | Identical "Authentication failed" |

---

## Out of scope

- DO NOT touch CRIT-A or CRIT-B — those are S6 (already specced separately)
- DO NOT touch MEDIUM findings except MED-D (account enum, auto-login.html, OAuth — those are S8)
- DO NOT touch INFRA findings (Docker user, ALLOWED_HOSTS, etc.) — those are S8
- DO NOT touch any frontend code
- Per project rule: agent does NOT run `./deploy.sh`

---

## Steps

1. Edit `backend/contractor_ops/tasks_router.py` — add `validate_upload(...)` call to contractor-proof handler
2. Edit `backend/services/storage_service.py` — replace user-controlled extension with `EXT_BY_MIME` whitelist
3. Edit `backend/contractor_ops/auth_router.py` (line 270, `/login` handler) — add per-(email, IP) lockout block; replace any existing wrong-password / not-found responses with single `GENERIC_AUTH_FAIL` 401
4. Edit `backend/contractor_ops/onboarding_router.py` (line 565, `/login-phone` handler) — same per-(phone_e164, IP) lockout block; replace existing Hebrew enumeration messages (`'מספר טלפון לא רשום'`, `'סיסמה שגויה'`) with single `GENERIC_AUTH_FAIL` 401
5. Edit `backend/contractor_ops/server.py` (or wherever `ensure_indexes()` lives) — add the compound `(email, ip)` unique index and the `last_failure` TTL index to `auth_failed_attempts`
6. Edit `backend/contractor_ops/billing_router.py` (line 1444-1458) — replace User-Agent-conditional HMAC with always-required HMAC
7. Edit `backend/contractor_ops/server.py` — add startup guard for `GI_BASE_URL && !GI_WEBHOOK_SECRET`
8. Edit `backend/contractor_ops/billing_router.py` (line 1279-1291) — remove `if GI_WEBHOOK_SECRET:` wrap; always validate
9. Edit `backend/contractor_ops/server.py` (line 1341) — `auth_header.lower().startswith('bearer ')`
10. **VERIFY 1 — syntax:** `python3 -m compileall backend/ -q`
11. **VERIFY 2 — grep:** `grep -n "validate_upload" backend/contractor_ops/tasks_router.py | wc -l` should be ≥ 2 (was 1 — add 1 for contractor-proof)
12. **VERIFY 3 — grep:** `grep -n "EXT_BY_MIME" backend/services/storage_service.py` should show the new whitelist
13. **VERIFY 4 — grep:** `grep -rn "auth_failed_attempts" backend/contractor_ops/auth_router.py backend/contractor_ops/onboarding_router.py | wc -l` should be ≥ 6 (3 per file: check + upsert on fail + delete on success — index creation lives in server.py)
14. **VERIFY 5 — grep:** `grep -n "User-Agent" backend/contractor_ops/billing_router.py` should NOT show any `if pp_user_agent != "PayPlus"` short-circuit
15. **VERIFY 6 — grep:** `grep -n "if GI_WEBHOOK_SECRET:" backend/contractor_ops/billing_router.py` should return no results (the conditional wrap is gone)
16. **VERIFY 7 — grep:** `grep -n "auth_header.lower" backend/contractor_ops/server.py` should show 1 occurrence
17. **VERIFY 8 — workflow:** restart `Start application` workflow, confirm clean boot. Test: with `GI_BASE_URL` and `GI_WEBHOOK_SECRET` both unset (dev .env state), boot should succeed. With `GI_BASE_URL` set but `GI_WEBHOOK_SECRET` unset, boot should `RuntimeError`.
18. **VERIFY 9 — existing tests still pass:** Run the existing pytest suite for the surfaces we touched to catch regressions in legitimate flows (uploads, billing webhooks, auth, RBAC):
    ```bash
    cd backend && python -m pytest tests/test_billing.py tests/test_billing_v1.py tests/test_evidence_upload.py tests/test_membership_phone_rbac.py tests/test_contractor_hardening.py -v
    ```
    All tests must pass. If any test fails, **stop and report** — the fix likely broke an existing assumption (e.g. test mocks a webhook with no `hash` header, expects 200; now must expect 401). Update test expectations as part of this spec — do not deploy until tests are green. If a test file errors on import (missing fixtures, etc.) report that too; we may need to skip that file rather than fix unrelated infrastructure.
19. **review.txt** with rollback SHA, full diffs of all touched files (~6: tasks_router, storage_service, auth_router, onboarding_router, server, billing_router), all 9 VERIFY outputs (including pytest output for VERIFY 9), the canonical commit message, post-deploy checklist (mongosh: index will auto-create on first boot; AWS EB env: no env var changes required for staging; deploy command Zahi runs; post-deploy regression test commands). End with `AWAITING ZAHI APPROVAL — DO NOT DEPLOY`.
20. **Commit message** to `.local/.commit_message`: `fix(security): close S7 HIGH — XSS upload + login lockout + webhook auth + paywall bypass`

---

## Deploy after approval

1. Zahi reviews review.txt
2. Replies "approved"
3. Replit commits + pushes to `staging` branch
4. Zahi runs `./deploy.sh --stag`
5. Zahi runs the regression tests for HIGH-A through MED-D + bonus MED-A on staging (see "Done looks like" table — 8 scenarios)
6. If all PASS → merge to main, run `./deploy.sh --prod`
7. Re-run regression tests on prod
8. Update `security/pentest-regression-checklist.md` to mark HIGH-A, HIGH-B, HIGH-C, HIGH-D, MED-D, and MED-A as `Status: FIXED 2026-04-XX`

---

## Rollback

```bash
git revert <S7_commit_sha>
./deploy.sh --prod
```

All fixes are forward-compatible additions/replacements — safe to revert without data migration. The new `auth_failed_attempts` Mongo collection becomes orphan but has a TTL index that auto-cleans within 24h.
