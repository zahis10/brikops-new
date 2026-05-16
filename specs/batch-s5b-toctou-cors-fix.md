# #422 — Batch S5b — TOCTOU signature guard + CORS fail-fast (code-audit HIGH)

## What & Why

**Pre-launch security fix.** Code audit 2026-04-24 found 2 HIGH-severity issues that allow misconfiguration to silently weaken security:

1. **S5-HIGH-1 — Missing startup guard on `META_APP_SECRET`.** If `WHATSAPP_ENABLED=true` but `META_APP_SECRET` is unset (config drift, env var typo), the app boots silently. The first webhook returns 503, but by then the misconfig went unnoticed for hours/days. No customer harm in current state, but creates an attack window during deploy/config changes.

2. **S5-HIGH-2 — CORS wildcard + credentials in non-prod.** When `APP_MODE != 'prod'` AND `CORS_ORIGINS` env var isn't set, the app defaults to `allow_origins=['*']` with `allow_credentials=True`. This combo is invalid per CORS spec, browsers reject the response, but cookies may leak in error responses to attacker origins.

**Same framing as S1/S2/S5a:** internal testers only, no breach. Pre-launch hygiene before public release.

### Investigation findings (already verified)

**TOCTOU is actually mitigated at request time** — the webhook handler (`notification_router.py:162`) DOES check `if not _meta_app_secret` before calling `_verify_signature` and rejects with 503. The real bug is at **startup**: there's no check that fails the boot if WhatsApp is enabled but the secret is missing. The app starts, accepts traffic, and only complains when a webhook arrives.

**CORS misconfig** is a `server.py:1376-1384` issue:
```python
_cors_default = 'https://app.brikops.com,https://www.brikops.com' if APP_MODE == 'prod' else '*'
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', _cors_default).split(','),
    ...
)
```
The fallback `'*'` for non-prod is the bug — combined with `allow_credentials=True` it's a CORS spec violation.

### Solution

Both fixes are **startup-time fail-fast guards**, following existing codebase patterns (`config.py:29-36` `_require()`, `services/object_storage.py:180-182` `raise RuntimeError`):

**Fix 1 (TOCTOU):** in `server.py` after `set_meta_app_secret(META_APP_SECRET)` call (line ~354), add a guard:
```python
if WHATSAPP_ENABLED and not META_APP_SECRET:
    raise RuntimeError("WHATSAPP_ENABLED=true but META_APP_SECRET is not set. Refusing to start.")
```

**Fix 2 (CORS):** at `server.py:1376-1384`, replace the wildcard-fallback CORS setup with explicit validation:
- Change default for non-prod from `'*'` to safe localhost origins (`http://localhost:3000,http://localhost:5173`)
- Add explicit validator that rejects any `'*'` in the final list (regardless of source)
- Add explicit validator that rejects empty list

Both fixes are 5-10 lines each. No new imports, no schema, no migration, no frontend.

---

## Done looks like

### TOCTOU fix
1. ✅ Boot with `WHATSAPP_ENABLED=true` and valid `META_APP_SECRET` → starts normally (current behavior)
2. ✅ Boot with `WHATSAPP_ENABLED=false` and no `META_APP_SECRET` → starts normally (WhatsApp disabled, secret not needed)
3. ✅ Boot with `WHATSAPP_ENABLED=true` and missing/empty `META_APP_SECRET` → **`RuntimeError` at startup, app refuses to boot**, error visible in EB logs
4. ✅ Boot via `./deploy.sh --prod` with the current prod env (which has both set correctly) → starts normally

### CORS fix
1. ✅ Prod boot (`APP_MODE=prod`, `CORS_ORIGINS` set with current 6 origins) → starts normally with the 6 env-provided origins
2. ✅ Prod boot with `CORS_ORIGINS` UNSET (failure mode) → falls back to hardcoded 6-origin safe net (matches current env exactly)
3. ✅ Dev/staging boot with `CORS_ORIGINS` set explicitly → starts with those origins
4. ✅ Dev/staging boot WITHOUT `CORS_ORIGINS` → defaults to `http://localhost:3000,http://localhost:5173` (safe), no wildcard
5. ✅ Boot with `CORS_ORIGINS='*'` (any env, anywhere) → **`RuntimeError`, app refuses to boot** (explicit wildcard banned)
6. ✅ Boot with `CORS_ORIGINS=''` (empty string) → **`RuntimeError`** (empty list also banned)
7. ✅ Cloudflare Pages preview (`https://brikops-new.pages.dev`) keeps working in all scenarios — included in both env and code default
8. ✅ Mobile app (Capacitor iOS/Android — `capacitor://localhost`, `ionic://localhost`, `https://localhost`) keeps working in all scenarios

### Regressions (MUST NOT BREAK)

1. ✅ Prod deploy works without env var changes
2. ✅ Existing dev workflow (`localhost:3000` → backend) continues to work via the new default
3. ✅ Webhook signature verification logic unchanged (we only add a startup guard, not modify request flow)
4. ✅ All existing CORS-allowed origins continue to be allowed
5. ✅ No changes to frontend, schemas, migrations
6. ✅ EB health check still passes after deploy

---

## Out of scope

- ❌ Changing `_verify_signature` runtime logic (the request-time check is already correct)
- ❌ Adding new CORS origins (out of scope; just preventing misconfig)
- ❌ Removing `allow_credentials=True` (we WANT credentials for cookie auth)
- ❌ Switching CORS to a more sophisticated middleware
- ❌ Adding env var validation for OTHER misconfigured combos (Twilio, PayPlus, etc. — separate batches if needed)
- ❌ MEDIUM-severity code-audit items (S5c)
- ❌ MEDIUM pentest items (S3)
- ❌ Feature-flagging the fix
- ❌ Frontend changes

---

## Tasks

### Task 1 — STEP 0 verification (mandatory before code)

```bash
# (a) Confirm the WHATSAPP_ENABLED env var name and where it's read:
grep -rn "WHATSAPP_ENABLED" backend/ | grep -v __pycache__ | head -10
# Expected: imported from config.py, used in server.py and notification_router.py

# (b) Confirm META_APP_SECRET initialization location in server.py:
grep -n "set_meta_app_secret\|META_APP_SECRET" backend/server.py
# Expected: import at top + setter call around line 354

# (c) Confirm CORS configuration block in server.py (verify line numbers match spec):
grep -n "CORSMiddleware\|allow_origins\|CORS_ORIGINS\|_cors_default" backend/server.py
# Expected: middleware setup around line 1376-1384

# (d) Confirm config.py exposes WHATSAPP_ENABLED + META_APP_SECRET:
grep -n "WHATSAPP_ENABLED\|META_APP_SECRET" backend/config.py
# Expected: both defined as module-level constants

# (e) Find existing fail-fast patterns to mirror:
grep -rn "raise RuntimeError" backend/ | grep -v __pycache__ | head -10
# Expected: services/object_storage.py:180+ uses this pattern

# (f) Verify current prod CORS_ORIGINS env (informational — Zahi can check AWS EB):
# AWS Console → EB → Configuration → Environment properties → look for CORS_ORIGINS
# If set: starts normally regardless of our fallback change
# If not set: relies on hardcoded prod default (no change in behavior)
```

**Document line numbers in review.txt**. If anything differs from the spec (line numbers, function signatures), STOP and report.

---

### Task 2 — Add TOCTOU startup guard

**File:** `backend/server.py`

**Find with:** `grep -n "set_meta_app_secret(META_APP_SECRET)" backend/server.py`

**Location:** Immediately AFTER the existing `set_meta_app_secret(META_APP_SECRET)` line (around line 354).

**Add:**

```python
    set_meta_app_secret(META_APP_SECRET)

    # S5b — Startup guard: refuse to boot if WhatsApp is enabled but secret missing.
    # Prevents silent misconfiguration where webhook signature verification is
    # effectively disabled until the first webhook arrives and returns 503.
    # Code-audit fix 2026-04-24.
    if WHATSAPP_ENABLED and not META_APP_SECRET:
        raise RuntimeError(
            "Configuration error: WHATSAPP_ENABLED=true but META_APP_SECRET is not set. "
            "Set META_APP_SECRET env var or set WHATSAPP_ENABLED=false. Refusing to start."
        )
```

**Verify imports** at top of `server.py` already include `WHATSAPP_ENABLED` and `META_APP_SECRET` from `config.py`. They should — STEP 0 (b) and (d) confirm this.

**Why this approach:**
- Zero changes to runtime behavior — the existing handler check at line 162 stays
- Boot fails LOUD if misconfigured — engineer sees error in EB logs immediately
- Mirrors existing patterns (`raise RuntimeError` from `object_storage.py`)
- Idempotent — safe to redeploy

**Do NOT:**
- ❌ Modify `_verify_signature` function
- ❌ Modify the webhook handler check at line 162
- ❌ Change `set_meta_app_secret` function in `notification_router.py`
- ❌ Add `sys.exit(1)` — use `RuntimeError` so FastAPI/uvicorn handles it cleanly

---

### Task 3 — Replace CORS wildcard fallback with safe defaults + validators

**File:** `backend/server.py`

**Find with:** `grep -n "CORSMiddleware" backend/server.py`

**Location:** The `CORSMiddleware` block at lines ~1376-1384.

**Current code:**
```python
_cors_default = 'https://app.brikops.com,https://www.brikops.com' if APP_MODE == 'prod' else '*'
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', _cors_default).split(','),
    allow_methods=['*'],
    allow_headers=['*'],
    expose_headers=['x-request-id', 'x-response-time-ms'],
)
```

**Replace with:**
```python
# S5b — CORS defaults: explicit safe origins per env, NEVER wildcard with credentials.
# Code-audit fix 2026-04-24.
# Prod default mirrors the actual production CORS_ORIGINS env var (6 origins:
# web prod, Cloudflare Pages preview, web www, Capacitor iOS, Capacitor alt, https localhost).
# This default acts as a SAFETY NET: if CORS_ORIGINS env is ever cleared, the app still
# serves the same 6 origins instead of falling back to a smaller set that breaks Cloudflare
# Pages preview or the mobile app.
_cors_default = (
    'https://app.brikops.com,https://brikops-new.pages.dev,https://www.brikops.com,'
    'capacitor://localhost,ionic://localhost,https://localhost'
    if APP_MODE == 'prod'
    else 'http://localhost:3000,http://localhost:5173'
)
_cors_origins_raw = os.environ.get('CORS_ORIGINS', _cors_default)
_cors_origins = [o.strip() for o in _cors_origins_raw.split(',') if o.strip()]

# Validators: refuse to boot on invalid CORS configuration.
# allow_origins=['*'] with allow_credentials=True is invalid per CORS spec
# (RFC 6454) and leaks cookies in error responses.
if not _cors_origins:
    raise RuntimeError(
        "Configuration error: CORS_ORIGINS resolved to empty list. "
        "Set CORS_ORIGINS env var to explicit comma-separated origins. Refusing to start."
    )
if '*' in _cors_origins:
    raise RuntimeError(
        "Configuration error: CORS_ORIGINS contains '*' (wildcard) while "
        "allow_credentials=True. This is invalid per CORS spec and leaks cookies. "
        "Set CORS_ORIGINS to explicit comma-separated origins. Refusing to start."
    )

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=['*'],
    allow_headers=['*'],
    expose_headers=['x-request-id', 'x-response-time-ms'],
)
```

**Why these defaults for non-prod:**
- `http://localhost:3000` — Create React App default (BrikOps frontend)
- `http://localhost:5173` — Vite default (in case anyone uses it)
- Both are explicit, safe, and cover ~100% of legitimate dev workflows
- Engineers needing other ports set `CORS_ORIGINS` explicitly (already supported)

**Do NOT:**
- ❌ Change `allow_credentials=True` (cookie auth depends on it)
- ❌ Change `allow_methods` or `allow_headers`
- ❌ Change `expose_headers`
- ❌ Move CORS setup to a different location
- ❌ Add `*` to the safe defaults list (that's the whole bug)
- ❌ Use `partialFilterExpression` or any complex CORS regex matching

---

## Relevant files

### Modified (1 backend file):
- `backend/server.py` — TOCTOU guard near line ~354, CORS validators + safe defaults at lines ~1376-1384

### Untouched (CRITICAL):
- `backend/contractor_ops/notification_router.py` — `_verify_signature`, `set_meta_app_secret`, webhook handler unchanged
- `backend/config.py` — env var reads unchanged
- All other backend files — zero diff
- All frontend — zero diff
- DB schema, migrations, deps — zero diff

---

## DO NOT

- ❌ Do NOT feature-flag this. Security/config fix.
- ❌ Do NOT modify webhook handler runtime logic — only add startup guards.
- ❌ Do NOT change `allow_credentials=True` — cookie auth depends on it.
- ❌ Do NOT remove the localhost defaults for non-prod — would break local dev.
- ❌ Do NOT add wildcard to ANY default — that's the whole bug.
- ❌ Do NOT use `sys.exit(1)` — use `raise RuntimeError(...)` for clean FastAPI/uvicorn handling.
- ❌ Do NOT add the guards at request time — startup is the right place.
- ❌ Do NOT change CORS to use a wildcard subdomain pattern (e.g., `*.brikops.com`) — out of scope and CORSMiddleware doesn't support patterns natively.
- ❌ Do NOT touch other env-var validation logic in `config.py` or elsewhere.
- ❌ Do NOT log the secret value (even partial) in any error message.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) TOCTOU guard added:
grep -n "WHATSAPP_ENABLED and not META_APP_SECRET" backend/server.py
# Expected: 1 hit (our new guard)

# (b) RuntimeError text exact:
grep -n "WHATSAPP_ENABLED=true but META_APP_SECRET is not set" backend/server.py
# Expected: 1 hit

# (c) CORS validator for empty list:
grep -n "CORS_ORIGINS resolved to empty list" backend/server.py
# Expected: 1 hit

# (d) CORS validator for wildcard:
grep -n "CORS_ORIGINS contains '\*'" backend/server.py
# Expected: 1 hit

# (e) Safe non-prod default:
grep -n "http://localhost:3000,http://localhost:5173" backend/server.py
# Expected: 1 hit

# (f) OLD wildcard fallback gone:
grep -n "if APP_MODE == 'prod' else '\*'" backend/server.py
# Expected: empty (the wildcard fallback is removed)

# (g) Webhook handler logic unchanged:
git diff --stat backend/contractor_ops/notification_router.py
# Expected: empty (we only touch server.py)

# (h) Only one file changed:
git diff --name-only | sort
# Expected: backend/server.py

# (i) No frontend change:
git diff --stat frontend/
# Expected: empty

# (j) No deps change:
git diff backend/requirements.txt
# Expected: empty
```

### 2. Python imports

```bash
cd backend
python -c "import server; print('OK')"
# Expected: no import errors. The script tries to BOOT the server — this validates
# that current dev/Replit env has either CORS_ORIGINS set OR the new defaults work.
```

If this fails with our new RuntimeError → STEP 0 didn't catch a missing env var. Fix env BEFORE deploying.

### 3. Frontend build (sanity — should be untouched)

```bash
cd frontend && REACT_APP_BACKEND_URL=https://example.com CI=true npm run build
```

Expected: same 3 pre-existing apple-sign-in source-map warnings only.

### 4. Manual tests (post-deploy)

#### Test A — Normal boot with prod env
- After deploy, EB health check should turn green within 5 minutes.
- Logs should NOT contain any `RuntimeError` or `Refusing to start`.
- ✅ App accepts traffic normally.

#### Test B — Existing webhook still works (regression)
```bash
# (Optional, requires HMAC-signed payload — skip if no easy way)
curl -X POST https://api.brikops.com/api/webhooks/whatsapp \
  -H "X-Hub-Signature-256: sha256=<valid_signature>" \
  -H "Content-Type: application/json" \
  -d '<valid_payload>'
```
- ✅ Returns 200 with `events_saved: 1` (or 0 if duplicate, per S5a)

#### Test C — Existing API endpoint with CORS
```bash
curl -i -H "Origin: https://app.brikops.com" \
  https://api.brikops.com/api/health
```
- ✅ Response includes `Access-Control-Allow-Origin: https://app.brikops.com` (NOT `*`)
- ✅ Response includes `Access-Control-Allow-Credentials: true`

#### Test D — CORS rejection from disallowed origin
```bash
curl -i -H "Origin: https://evil.com" \
  https://api.brikops.com/api/health
```
- ✅ Response does NOT include `Access-Control-Allow-Origin: https://evil.com`
- (Browser would block; curl shows the headers anyway. Validates CORS scope.)

#### Test E (advanced — only if Zahi wants) — Misconfig fail-fast
- Locally OR in a sandbox: set `WHATSAPP_ENABLED=true` and unset `META_APP_SECRET`
- Run `python -c "import server"` or attempt boot
- ✅ App raises `RuntimeError("Configuration error: WHATSAPP_ENABLED=true but META_APP_SECRET is not set...")`

---

## Commit message (exactly)

```
fix(security): startup fail-fast for missing META_APP_SECRET + invalid CORS (Batch S5b)

Pre-launch code-audit fix. 2026-04-24 audit found 2 HIGH-severity
configuration safety gaps:

S5-HIGH-1: server.py boots silently when WHATSAPP_ENABLED=true but
META_APP_SECRET is unset. The webhook handler at notification_router.py:162
correctly returns 503 when this happens, but the misconfiguration goes
unnoticed until the first webhook arrives. Add a startup guard that
raises RuntimeError if WhatsApp is enabled but the secret is missing,
forcing the engineer to notice the error in EB logs immediately.

S5-HIGH-2: server.py:1376-1384 CORS configuration falls back to
allow_origins=['*'] with allow_credentials=True when APP_MODE != 'prod'
AND CORS_ORIGINS is unset. This combo is invalid per CORS spec (RFC 6454)
and leaks cookies in error responses. Replace the wildcard fallback with
safe localhost defaults (http://localhost:3000, http://localhost:5173)
and add explicit validators that raise RuntimeError if the final list
contains '*' or is empty.

Both fixes follow the existing fail-closed pattern from
services/object_storage.py:180-182 and config.py:29-36 (_require()).

One file modified (server.py). Webhook runtime logic unchanged. CORS
runtime behavior unchanged for prod and properly-configured dev. No
schema, no migration, no frontend, no new deps.
```

---

## Deploy

### 2-phase rollout (same as S1/S2/S5a)

#### Phase 1 — Capture revert anchor

```bash
git log -1 --format="%H %s" > /tmp/pre-s5b-head.txt
cat /tmp/pre-s5b-head.txt
# Paste SHA at top of review.txt
```

**Revert is one command:**
```bash
git revert <SHA> --no-edit
./deploy.sh --prod
```

#### Phase 2 — Deploy to prod

```bash
./deploy.sh --prod
```

Backend-only. EB health check green ~5 min.

**Critical pre-deploy check (Zahi to verify in AWS Console):**
- AWS EB → Configuration → Environment properties
- Confirm `META_APP_SECRET` is set with a non-empty value
- Confirm `WHATSAPP_ENABLED` matches reality (`true` if WhatsApp Cloud API in use)
- Confirm `CORS_ORIGINS` is either set explicitly OR `APP_MODE=prod` (in which case prod hardcoded defaults apply)

If any of these are misconfigured, the deploy will fail to boot with a clear RuntimeError in logs. That's the FEATURE — but Zahi should know to expect it.

**After EB green:**
1. Run Test A (verify boot succeeded)
2. Run Test C (verify CORS headers correct)
3. Run Test B (optional, regression on webhook)

If boot fails:
- Read EB logs for the RuntimeError message
- Fix the env var per the message
- Re-deploy

---

## Definition of Done

- [ ] STEP 0 grep checks pass (6 checks)
- [ ] Task 2: TOCTOU startup guard added
- [ ] Task 3: CORS validators + safe defaults added
- [ ] All 10 VERIFY grep checks pass
- [ ] Python import check clean
- [ ] Frontend build clean (unchanged warnings only)
- [ ] AWS EB env vars verified (META_APP_SECRET set, CORS_ORIGINS or prod-default OK)
- [ ] Tests A + C pass on prod
- [ ] EB health check green
- [ ] `./deploy.sh --prod` succeeded
