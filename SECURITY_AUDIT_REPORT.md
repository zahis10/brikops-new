# BrikOps Security Audit Report

**Audit Date:** 2026-03-14
**Scope:** Full application — 39 backend + frontend files
**Auditor:** Automated code review (read-only)
**Application:** BrikOps — Construction task management (FastAPI + React + MongoDB)

---

## Executive Summary

BrikOps demonstrates **solid foundational security practices** for an application at this stage: bcrypt password hashing, SHA-256 token hashing for magic links, session versioning for invalidation, OTP rate limiting backed by MongoDB (persistent across restarts), step-up authentication for sensitive admin operations, role-conflict enforcement, comprehensive audit trails, and dev-only endpoints blocked in production.

The audit identified **2 Critical, 5 High, 7 Medium, and 5 Low** findings. The critical issues are an unauthenticated debug endpoint leaking infrastructure details and user-input passed unsanitized into MongoDB `$regex` queries. Both are straightforward to fix.

No evidence of SQL/NoSQL injection via `$where` or `eval()`, no hardcoded credentials in source (secrets come from env vars), and no plaintext password storage (legacy plaintext passwords are migrated to bcrypt on login).

---

## Findings

### CRITICAL

#### C-1: Unauthenticated `/api/debug/db-ping` leaks infrastructure details
- **File:** `server.py:117-147`
- **Description:** The `/api/debug/db-ping` endpoint has **no authentication**. It returns the MongoDB host address, database name, pool size, and collection count. This information aids targeted attacks against the database.
- **Impact:** Information disclosure; attackers can fingerprint the database technology, hosting provider, and cluster topology.
- **Remediation:** Add `Depends(require_super_admin)` or remove the endpoint entirely. At minimum, gate it behind `ENABLE_DEBUG_ENDPOINTS`.

#### C-2: Regex injection via unescaped `q` parameter in task search
- **File:** `tasks_router.py:198-199`
- **Description:** The `q` query parameter is passed directly to MongoDB `$regex` without `re.escape()`:
  ```python
  {'title': {'$regex': q, '$options': 'i'}},
  {'description': {'$regex': q, '$options': 'i'}},
  ```
  A malicious user can inject regex patterns like `.*` (data extraction via timing), or catastrophic backtracking patterns like `(a+)+$` (ReDoS), causing server CPU exhaustion.
- **Impact:** Denial of service; potential data extraction via timing side-channels.
- **Contrast:** `admin_router.py:343` correctly uses `re.escape(q_stripped)` for the same pattern.
- **Remediation:** Apply `re.escape(q)` before passing to `$regex`, consistent with admin_router.

---

### HIGH

#### H-1: CORS allows all origins by default
- **File:** `server.py:828-832`
- **Description:** `allow_origins` defaults to `*` when `CORS_ORIGINS` env var is unset:
  ```python
  allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
  ```
  Combined with `allow_credentials=True`, this is a dangerous combination. Browsers will block `credentials: true` with `origin: *`, but if a specific origin is reflected, cross-origin credential theft becomes possible.
- **Impact:** If the app ever reflects the `Origin` header (FastAPI's CORS middleware does NOT do this with `*`), authenticated requests from attacker-controlled origins could steal data. Current risk is mitigated by browser enforcement, but the configuration is fragile.
- **Remediation:** Set `CORS_ORIGINS` explicitly in production to the actual app domain(s). Never rely on `*` as default.

#### H-2: JWT stored in `localStorage` — XSS exfiltration risk
- **Files:** `frontend/src/context/AuthContext.js:29`, `frontend/src/api/api.js:26`
- **Description:** The JWT is stored in `localStorage.setItem('token', ...)` and read back with `localStorage.getItem('token')`. Any XSS vulnerability in the application (e.g., unsanitized user content rendered as HTML) allows an attacker to steal the JWT and impersonate the user.
- **Impact:** Full account takeover if XSS is present anywhere in the app.
- **Remediation:** Migrate to `HttpOnly` + `Secure` + `SameSite=Strict` cookies for token storage. This makes the token inaccessible to JavaScript.

#### H-3: JWT token passed via URL query parameter `_token`
- **File:** `frontend/src/context/AuthContext.js:20-28`
- **Description:** The app accepts `?_token=<JWT>` in the URL query string, stores it in `localStorage`, then removes it from the URL. However:
  1. The token appears in browser history before removal.
  2. The token appears in HTTP `Referer` headers if the user clicks an external link.
  3. The token may be logged by intermediate proxies, CDNs, or browser extensions.
- **Impact:** Token leakage via browser history, referrer headers, or proxy logs.
- **Remediation:** Use URL fragment (`#token=`) instead of query params (already done for WA login in `wa_login.py:323`), or use a one-time code that exchanges for a token server-side.

#### H-4: Password reset tokens stored in plaintext in database
- **File:** `onboarding_router.py:1568-1576`
- **Description:** The password reset token is stored as-is in `password_reset_tokens.token`. If the database is compromised (or via any admin read access), an attacker can use these tokens to reset any user's password.
- **Contrast:** Magic link tokens in `wa_login.py:128` are properly hashed with SHA-256 before storage.
- **Remediation:** Hash the reset token with SHA-256 before storing, and compare hashes during verification (same pattern as `wa_login.py`).

#### H-5: WhatsApp webhook accepts all messages when `META_APP_SECRET` is unset
- **File:** `notification_router.py:44-50`
- **Description:** When `META_APP_SECRET` is not configured, the webhook signature verification is skipped entirely:
  ```python
  if not META_APP_SECRET:
      return True  # Accept everything
  ```
  An attacker can forge webhook payloads to trigger application logic (e.g., marking messages as delivered, triggering status updates).
- **Impact:** Webhook spoofing; potential for manipulating notification delivery status or triggering unintended side effects.
- **Remediation:** Fail closed — reject webhook requests when `META_APP_SECRET` is not configured. Log a critical warning at startup if it's missing.

---

### MEDIUM

#### M-1: In-memory rate limiting for admin login and WA login resets on restart
- **Files:** `router.py:190-200` (admin login), `wa_login.py:69-83` (magic link requests)
- **Description:** Both admin login and WA magic link request rate limits use in-memory `dict`/`defaultdict`. These reset to zero on every server restart, allowing an attacker to bypass rate limits by timing attacks around deployments.
- **Contrast:** OTP rate limits in `onboarding_router.py:113-153` correctly use MongoDB-backed persistent rate limiting.
- **Remediation:** Migrate to MongoDB-backed rate limiting (same pattern as `_check_rate_limit_mongo`).

#### M-2: No file upload size limit enforced at application level
- **Files:** `storage_service.py:58-63`, `tasks_router.py:815`
- **Description:** The only validation on uploaded files is `file_size == 0` (empty check). There is no maximum file size limit, allowing users to upload arbitrarily large files that consume storage and memory (the entire file is read into memory with `await file.read()`).
- **Exception:** QC photo uploads (`qc_router.py:1004`) enforce a 10MB `MAX_PHOTO_SIZE` limit, but task attachments and contractor proof uploads do not.
- **Remediation:** Add a configurable `MAX_UPLOAD_SIZE` (e.g., 10MB) to the `StorageService.upload_file_with_details()` method, or use FastAPI's built-in request size limiting.

#### M-3: Step-up OTP code logged to application logs on SMTP failure
- **File:** `stepup_service.py:201-203`
- **Description:** When email delivery fails, the plaintext step-up OTP code is logged:
  ```python
  logger.warning(f"[STEPUP] email_send_failed ... Use code: {code}")
  ```
  Anyone with access to application logs (log aggregation services, CI/CD, support staff) can see the admin OTP code.
- **Impact:** Step-up authentication bypass for anyone with log access.
- **Remediation:** Remove the plaintext code from log output. Log only a reference ID.

#### M-4: Storage service trusts client-provided `content_type` without verification
- **File:** `storage_service.py:73`
- **Description:** The file's MIME type is taken directly from the client-provided `file.content_type` and passed to S3 as the `ContentType`. A user could upload a malicious HTML/SVG file disguised as an image.
- **Mitigating factor:** Task attachments (`tasks_router.py:811-827`) validate images using PIL `verify()`, which catches non-image content. However, the `StorageService` itself has no validation, and other upload paths (contractor proof, QC photos) may not have the same PIL check.
- **Remediation:** Add content-type verification in `StorageService` by checking magic bytes or using `python-magic`.

#### M-5: `list_task_updates` endpoint does not verify project membership
- **File:** `tasks_router.py:784-791`
- **Description:** The `GET /api/tasks/{task_id}/updates` endpoint requires authentication (`get_current_user`) but does **not** verify that the user has access to the task's project. Any authenticated user can read the update history (including comments and attachments) of any task if they know the task ID.
- **Contrast:** `get_task` (`tasks_router.py:232-288`) correctly checks project membership and contractor assignment.
- **Remediation:** Add the same membership/access check used in `get_task`.

#### M-6: `updates_feed` endpoint with no `project_id` returns all updates across all projects
- **File:** `tasks_router.py:880-896`
- **Description:** When `project_id` is not provided, the endpoint returns task updates from **all projects** with no access filtering. Any authenticated user sees all task comments/attachments across the entire platform.
- **Remediation:** Require `project_id` parameter, or filter to only projects the user has membership in.

#### M-7: Password reset rate limiting uses in-memory store
- **File:** `onboarding_router.py:1610` (uses `_check_rate_limit` at line 102-110)
- **Description:** The `forgot-password` and `reset-password` endpoints use the in-memory `_rate_limits` dict. Rate limits reset on server restart.
- **Remediation:** Use `_check_rate_limit_mongo` (same file, line 113) for persistence.

---

### LOW

#### L-1: Debug OTP code returned in dev mode
- **File:** `onboarding_router.py:262-263`
- **Description:** When `APP_MODE == 'dev'`, the OTP debug code is returned in the API response. This is intentional for development but must be verified it cannot activate in production.
- **Status:** `config.py` sets `APP_MODE` from env var. **Verified safe** as long as `APP_MODE` is not set to `dev` in production.

#### L-2: WA login magic link URL logged
- **File:** `wa_login.py:145`
- **Description:** The magic link URL (containing the raw token) is logged at INFO level: `Magic link created for user=..., prefix=...`. The URL itself is not logged (only the prefix), so this is **low risk**.
- **Status:** Acceptable — only the 6-character prefix is logged, not the full token.

#### L-3: Join code is a 4-digit numeric code
- **File:** `projects_router.py:106`
- **Description:** Project join codes are `BRK-{1000..9999}`, giving only 9000 possible values. This could be brute-forced to discover projects.
- **Mitigating factor:** Join codes appear to be used only for display/identification, not as an authentication mechanism. The actual join flow requires phone verification + PM approval.
- **Remediation:** Consider using longer alphanumeric codes if join codes ever become a direct access mechanism.

#### L-4: MongoDB connection string may contain credentials
- **File:** `server.py:30-37`
- **Description:** `MONGO_URL` is read from environment and used directly. If the connection string contains embedded credentials (as with MongoDB Atlas), they could appear in error messages or stack traces.
- **Status:** Standard practice; credentials in connection strings are expected for MongoDB. Ensure error handlers don't leak the full URL.

#### L-5: Session version not incremented on password change
- **File:** `onboarding_router.py:1656-1658`, `identity_router.py:80-97`
- **Description:** When a password is changed or reset, `session_version` is not incremented. This means existing JWT tokens remain valid until they expire naturally, even after a password change.
- **Impact:** If credentials are compromised and the user changes their password, the attacker's existing token continues to work.
- **Remediation:** Increment `session_version` on password change/reset to invalidate all existing sessions.

---

## Endpoint Authorization Matrix

| Endpoint Pattern | Auth Required | Role Check | Notes |
|---|---|---|---|
| `GET /api/debug/db-ping` | **NO** | **NO** | **C-1: Must fix** |
| `GET /api/debug/*` (other) | Yes | `require_super_admin` | Properly protected |
| `POST /api/auth/request-otp` | No | N/A | Public, rate-limited (MongoDB) |
| `POST /api/auth/verify-otp` | No | N/A | Public, rate-limited |
| `POST /api/auth/register-with-phone` | No | N/A | Public, creates pending user |
| `POST /api/auth/login` | No | N/A | Public, rate-limited (in-memory) |
| `POST /api/auth/login-phone` | No | N/A | Public |
| `POST /api/auth/wa/request-login` | No | N/A | Public, rate-limited (in-memory) |
| `GET /api/auth/wa/verify` | No | N/A | Token-based verification |
| `POST /api/auth/wa/create-link` | No | Debug-only guard | Gated by `ENABLE_DEBUG_ENDPOINTS` |
| `POST /api/auth/forgot-password` | No | N/A | Public, rate-limited (in-memory) |
| `POST /api/auth/reset-password` | No | N/A | Token-based, rate-limited (in-memory) |
| `POST /api/auth/set-password` | Yes | `get_current_user` | Authenticated |
| `GET /api/auth/account-status` | Yes | `get_current_user` | Authenticated |
| `POST /api/auth/complete-account` | Yes | `get_current_user` | Authenticated |
| `GET /api/projects` | Yes | `get_current_user` | Returns only user's projects |
| `POST /api/projects` | Yes | `require_roles('project_manager')` | PM only |
| `GET /api/projects/{id}` | Yes | `_check_project_read_access` | Membership check |
| `POST /api/tasks` | Yes | `require_roles('project_manager')` | PM only |
| `GET /api/tasks` | Yes | `get_current_user` | Contractor sees only assigned tasks |
| `GET /api/tasks/{id}` | Yes | Membership + assignee check | Proper access control |
| `GET /api/tasks/{id}/updates` | Yes | **`get_current_user` only** | **M-5: Missing membership check** |
| `GET /api/updates/feed` | Yes | **`get_current_user` only** | **M-6: Cross-project data leak** |
| `PATCH /api/tasks/{id}` | Yes | `MANAGEMENT_ROLES` check | Proper |
| `PATCH /api/tasks/{id}/assign` | Yes | `MANAGEMENT_ROLES` check | Proper |
| `POST /api/tasks/{id}/status` | Yes | Role-based status transitions | Proper |
| `POST /api/tasks/{id}/contractor-proof` | Yes | Contractor + assignee check | Proper |
| `POST /api/tasks/{id}/manager-decision` | Yes | `MANAGEMENT_ROLES` check | Proper |
| `POST /api/tasks/{id}/attachments` | Yes | `get_current_user` + viewer check | Image validation with PIL |
| `POST /api/projects/{id}/invites` | Yes | RBAC role hierarchy | Proper |
| `GET /api/projects/{id}/invites` | Yes | PM/management_team check | Proper |
| `POST /api/projects/{id}/export` | Yes | `_check_project_read_access` | Proper |
| `GET /api/qc/*` | Yes | `_check_qc_access` (MANAGEMENT_ROLES) | Proper |
| `POST /api/qc/*` | Yes | `_check_qc_access` | Proper |
| `GET /api/users` | Yes | `require_roles('project_manager')` | PM only |
| `DELETE /api/projects/{id}/members/{uid}` | Yes | `_require_pm_or_owner` | Proper |
| `PUT /api/projects/{id}/members/{uid}/role` | Yes | `_require_pm_or_owner` | Proper + role conflict checks |
| `DELETE /api/org/members/{uid}` | Yes | Owner or super_admin | Proper |
| `GET /api/orgs/{id}/members` | Yes | Owner, org_admin, billing_admin, SA | Proper |
| `PUT /api/orgs/{id}/members/{uid}/org-role` | Yes | Owner or SA | Proper |
| `POST /api/admin/*` | Yes | `require_super_admin` | Proper |
| Admin sensitive ops (revoke, override, etc.) | Yes | `require_stepup` | Step-up auth required |
| `POST /api/webhook/whatsapp` | Signature check | **Skipped if no secret** | **H-5** |
| `POST /api/buildings/{id}/archive` | Yes | `require_roles('project_manager')` | Proper |
| `POST /api/ownership-transfer/*` | Yes | Various owner checks | Proper |

---

## Areas With No Issues Found

1. **Password hashing** — bcrypt with salt, async executor to avoid blocking. Legacy plaintext passwords migrated on login.
2. **OTP system** — SHA-256 code hashing, MongoDB-backed rate limits (for OTP specifically), time-based expiry, lockout after failed attempts.
3. **Magic link tokens** (WA login) — `secrets.token_urlsafe(32)`, SHA-256 hashed before storage, single-use with atomic `find_one_and_update`, TTL expiry.
4. **Session invalidation** — `session_version` checked on every request; admin can revoke sessions.
5. **Role conflict enforcement** — Contractor cannot hold management roles simultaneously; enforced at invite, role-change, ownership transfer, and registration paths.
6. **Audit trail** — Comprehensive audit events for role changes, member removal, session revocation, ownership transfers, login events.
7. **Step-up authentication** — Sensitive admin operations require time-limited secondary OTP via email.
8. **Dev-login guard** — `POST /api/auth/login` blocked when `APP_MODE != 'dev'` (server.py + config.py).
9. **Path traversal protection** — `export_router.py:396-407` validates local file paths using `resolve()` and `relative_to()`.
10. **Image validation** — Task attachments validated with PIL `verify()` to prevent non-image file upload.
11. **Phone normalization** — Consistent `normalize_israeli_phone()` used across all phone input paths.
12. **Org owner protection** — Cannot remove org owner from project, cannot change owner role without transfer flow.

---

## Areas Not Verified (Out of Scope)

1. **Infrastructure security** — MongoDB network access rules, TLS configuration, server hardening.
2. **Deployment configuration** — Environment variable values in production, reverse proxy settings.
3. **Third-party dependencies** — No `pip audit` or dependency vulnerability scan performed.
4. **Client-side React security** — No XSS audit of React component rendering (React escapes by default, but `dangerouslySetInnerHTML` or other bypasses were not checked).
5. **Rate of JWT secret rotation** — `JWT_SECRET_VERSION` mechanism exists but rotation policy not verified.
6. **S3 bucket permissions** — Whether the S3 bucket is publicly accessible was not verified.
7. **SMS/WhatsApp delivery security** — Twilio/Meta API key permissions and scoping not reviewed.

---

## Prioritized Action Plan

### Immediate (This Sprint)
| # | Finding | Effort | Priority |
|---|---------|--------|----------|
| 1 | **C-1**: Add auth to `/api/debug/db-ping` or remove it | 5 min | Critical |
| 2 | **C-2**: Add `re.escape(q)` in task search `$regex` | 5 min | Critical |
| 3 | **H-3**: Change `_token` query param to URL fragment `#token=` | 30 min | High |
| 4 | **M-5**: Add project membership check to `list_task_updates` | 15 min | Medium |
| 5 | **M-6**: Require `project_id` or filter `updates_feed` by membership | 15 min | Medium |

### Next Sprint
| # | Finding | Effort | Priority |
|---|---------|--------|----------|
| 6 | **H-1**: Set explicit `CORS_ORIGINS` in production | 10 min (config) | High |
| 7 | **H-4**: Hash password reset tokens with SHA-256 | 1 hour | High |
| 8 | **H-5**: Fail closed when `META_APP_SECRET` is unset | 15 min | High |
| 9 | **M-1**: Migrate admin/WA rate limits to MongoDB | 2 hours | Medium |
| 10 | **M-3**: Remove plaintext OTP from step-up fallback logs | 5 min | Medium |
| 11 | **L-5**: Increment `session_version` on password change | 30 min | Low |

### Backlog
| # | Finding | Effort | Priority |
|---|---------|--------|----------|
| 12 | **H-2**: Migrate JWT from localStorage to HttpOnly cookies | 4-8 hours | High (long-term) |
| 13 | **M-2**: Add max file size limit for uploads | 30 min | Medium |
| 14 | **M-4**: Content-type verification via magic bytes | 1 hour | Medium |
| 15 | **M-7**: MongoDB-backed rate limit for password reset | 30 min | Medium |

---

## Summary Statistics

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 5 |
| Medium | 7 |
| Low | 5 |
| **Total** | **19** |
| Areas with no issues | 12 |
| Areas not verified | 7 |

**Overall Assessment:** The application has a strong security foundation with appropriate authentication, authorization, and audit mechanisms. The critical and high findings are all fixable with modest effort. The most impactful quick wins are C-1 (5 minutes), C-2 (5 minutes), and M-5/M-6 (15 minutes each) — these four fixes address the most serious vulnerabilities in under an hour.
