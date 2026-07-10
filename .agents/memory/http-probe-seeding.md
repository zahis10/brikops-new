---
name: In-process HTTP probe seeding
description: What must be seeded in local Mongo for full-stack ASGI probes to pass paywall + RBAC
---
Rule: when probing the real FastAPI app in-process (httpx ASGITransport) with real JWTs, seed ALL of:
- `project_memberships` (not `project_members`) — `_check_project_access` reads it, and it gates READS too (owner/admin 403 even on GET; safety + work-diary share this).
- `organization_memberships` row for the user — the paywall fast-path resolves org via `get_user_org`; without it writes get 402 (scoped URL fallback only covers projects/tasks/buildings/floors/units patterns).
- `subscriptions` doc with `status:"active"` and `paid_until` as an ISO **string** — `_resolve_access` compares against `_now()` which returns an isoformat string; inserting a datetime raises TypeError.
- Force `os.environ["MONGO_URL"]` (not setdefault) before importing server — the repl env carries an Atlas URI that otherwise wins.

**Why:** first d2 probe run failed 16/16 with 402/403 for exactly these reasons.
**How to apply:** any future probe that goes through the full middleware chain (paywall, RBAC) instead of calling router coroutines directly.

More seeding/env rules:
- Super-admin bypass keys off `platform_role == 'super_admin'` on the user doc, NOT `role` — seed both fields or the bypass 403s.
- Feature-gated routers are never imported when their flag is off (probes hitting them get 404/405). Set every flag the probe touches at the top of the file, e.g. a work-diary probe that reuses the safety upload endpoint must also set `ENABLE_SAFETY_MODULE=true`.
- The local storage backend returns `stored_ref` prefixed `/api/uploads/<key>`; S3 returns the bare key. Ref assertions must accept both (substring match, not `startswith`).
