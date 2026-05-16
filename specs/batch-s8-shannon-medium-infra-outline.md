# #428 — Batch S8 — Shannon MEDIUM + INFRA hardening (OUTLINE)

## What & Why

**Hardening, not blocker.** Shannon scan 2026-04-26 found 2 MEDIUM findings + 5 INFRA findings that are NOT launch-blockers but should ship within 30 days of public launch.

This file is an **outline** rather than a full spec. Each item is a 5-30 minute fix. We can either:
- Send all 7 to Replit as one S8 spec when ready, OR
- Send them as 7 mini-specs over a quarter

---

## MEDIUM Findings

### MED-A — Phone enumeration via `/api/auth/login-phone`
- **Issue:** Returns `מספר טלפון לא רשום` for unregistered, `סיסמה שגויה` for registered → tells attacker if phone exists
- **File:** `backend/contractor_ops/onboarding_router.py:570 vs 586`
- **Fix:** Return identical generic error for both cases (`"Invalid credentials"` like the email login already does)
- **Effort:** 10 min
- **Same fix needed for:** `/api/auth/register-management` (also leaks email/phone existence)

### MED-B — `auto-login.html` should not exist in builds
- **Issue:** Hardcoded credentials (`admin@contractor-ops.com:admin123`) + open-redirect via `?redirect` param + javascript: XSS (CSP-mitigated for now)
- **File:** `frontend/public/auto-login.html`
- **Fix:** Delete the file. It has no production purpose (was dev convenience).
- **Effort:** 2 min (delete + redeploy)
- **Verify:** `curl https://app.brikops.com/auto-login.html` → 404

### MED-C — OAuth flow leaks masked phone number
- **Issue:** When attacker presents matching Google/Apple OAuth token, server reveals victim's masked phone (`+972-50-***-1234`). Currently mitigated by OTP requirement for full account takeover.
- **Fix:** Don't return phone hint in OAuth lookup response. Force the user to re-enter their phone on the linking screen.
- **Effort:** 30 min (change response shape + frontend update)
- **Note:** This was MED-only because OTP requirement prevents full ATO. But fix anyway — defense in depth.

### MED-E — CORS allowlist includes `https://brikops-new.pages.dev` (covers all preview deployments)
- **Issue:** Cloudflare Pages preview URLs follow pattern `<commit>.brikops-new.pages.dev` — all of these are inadvertently in CORS allowlist
- **File:** AWS EB env var `CORS_ORIGINS`
- **Fix:** Remove `https://brikops-new.pages.dev` from prod CORS_ORIGINS (keep on staging only). Use exact subdomains: `app.brikops.com` for prod.
- **Effort:** 5 min (change env var, no code change)
- **Risk if not fixed:** A compromised preview deployment could call prod API from a user's browser

---

## INFRA Findings

### INFRA-A — Backend Docker container runs as root
- **Issue:** No `USER` directive in `backend/Dockerfile` → root inside container → privilege escalation if container escape happens
- **File:** `backend/Dockerfile`
- **Fix:** Add `USER appuser` after creating the user, before `CMD`
- **Effort:** 15 min (Dockerfile change + verify writes still work for any /tmp paths)

### INFRA-B — `ALLOWED_HOSTS` not set on prod EB
- **Issue:** `TrustedHostMiddleware` is registered but doesn't enforce because `ALLOWED_HOSTS` env var is unset on prod
- **Fix:** Set `ALLOWED_HOSTS=api.brikops.com` on prod EB (and `api-staging.brikops.com` on staging)
- **Effort:** 2 min via `eb setenv`
- **Risk if not fixed:** Host header injection / cache poisoning attacks

### INFRA-C — `/api/uploads/` static mount serves files without auth
- **Issue:** Any uploaded file is publicly accessible if the URL is enumerable
- **Fix:** Replace static file mount with authenticated endpoint that streams from S3 with a presigned URL (which already expires)
- **Effort:** 1-2 hours (refactor mount → endpoint, update frontend to use new URL)
- **Note:** Most files are already in S3 with presigned URLs. The static mount was for legacy local-dev paths.

### INFRA-D — MongoDB rate limiter fails open on DB error
- **Issue:** The 30 req/min unauthenticated rate limit is silently bypassed when the rate-limit collection is unavailable (e.g., Atlas brief blip)
- **Fix:** On rate-limit-collection error, fail CLOSED (return 503 instead of allowing all traffic through)
- **Effort:** 30 min
- **Risk if not fixed:** During Atlas hiccups, attackers can flood

### INFRA-E — HSTS missing `preload` directive
- **Issue:** Not on Chrome's HSTS preload list → first-time visitor on a hostile WiFi could be MITM'd before HSTS kicks in
- **Fix:** Add `preload` to HSTS header. Then submit `brikops.com` to https://hstspreload.org/
- **Effort:** 5 min for header change + ~weeks for Chrome inclusion (but immediate effect for repeat visitors)

---

## Suggested batching

**S8.1 (5-min wins, send first):**
- MED-A (phone enumeration)
- MED-B (delete auto-login.html)
- MED-E (remove preview from CORS)
- INFRA-B (set ALLOWED_HOSTS)
- INFRA-E (HSTS preload)

**S8.2 (medium effort):**
- INFRA-A (Dockerfile USER directive)
- INFRA-D (rate limiter fail-closed)
- MED-C (OAuth phone leak)

**S8.3 (larger refactor, can be later):**
- INFRA-C (replace `/api/uploads/` static mount)

---

## When to ship

- **Within 30 days of public launch:** S8.1 + S8.2 (all small/medium items)
- **Within 90 days of public launch:** S8.3 (larger refactor)

---

## Out of scope

- Anything in S6 or S7 (already covered)
- Rebuilding the auth system (these are surgical fixes)
- Changing the frontend auth UX

---

## Reference

All findings from Shannon scan report at `secrets/shannon-reports-2026-04-26/comprehensive_security_assessment_report.md` (gitignored).

Each item maps to a regression test in [`security/pentest-regression-checklist.md`](../security/pentest-regression-checklist.md) — tests will move from "OPEN" to "FIXED" as each batch ships.
