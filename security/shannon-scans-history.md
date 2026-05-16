# Shannon AI Pentest — Scan History

> **Public-safe summary** of all Shannon (Keygraph) AI pentest scans against BrikOps. Full reports with PoC exploits are stored in `secrets/shannon-reports-*/` (gitignored). This file is committable for compliance / enterprise audit trail purposes.

---

## Scan: 2026-04-26 (FIRST SCAN)

**Tool:** [Shannon Lite by Keygraph](https://github.com/KeygraphHQ/shannon) — open-source AI pentester powered by Claude
**Methodology:** White-box (source code + live exploitation)
**Target:** `https://staging.brikops-new.pages.dev` + `https://api-staging.brikops.com`
**Cost:** ~$30-40 in Anthropic API credits
**Workspace:** `brikops-staging-scan-v2`

### Findings summary

| Severity | Count | Categories |
|----------|-------|------------|
| 🔴 CRITICAL | 2 | Authentication bypass, IDOR |
| 🟠 HIGH | 4 | Stored XSS, brute force, webhook auth × 2 |
| 🟡 MEDIUM | 3 | Account enumeration, dev artifact, OAuth info leak |
| 🔵 INFRA | 5 | Container hardening, host validation, etc. |
| **Plus discovered via manual review:** | 1 | IDOR on `/tasks/{id}/attachments` |

### Successfully exploited

✅ Anonymous role escalation to `project_manager` via legacy `/api/auth/register`
✅ Cross-project task reopen via global role check bypass
✅ Stored XSS via contractor proof file upload (Level 4 — phishing overlay captured creds)
✅ 35-attempt login brute force with no lockout
✅ PayPlus webhook HMAC bypass via `User-Agent` header manipulation
✅ GreenInvoice webhook accepted unauthenticated payloads

### Did NOT find / blocked by existing controls

✅ No SQL injection vulnerabilities
✅ No command injection vulnerabilities
✅ No SSRF successfully exploited
✅ S1 fix (org-scoping on `/api/users` + `/api/companies`) — verified no regression
✅ S2 fix (org-scoping on `/api/tasks` GET) — verified no regression
✅ JWT signature validation — robust (alg:none, tampering both rejected)
✅ Login email enumeration on primary endpoint — properly hardened with generic error

### Remediation tracking

| Finding | Batch | Spec | Status |
|---------|-------|------|--------|
| Role escalation at `/api/auth/register` | S6 | `specs/batch-s6-shannon-crit-fix.md` | ✅ FIXED 2026-04-26 |
| IDOR on `/api/tasks/{id}/reopen` | S6 | `specs/batch-s6-shannon-crit-fix.md` | ✅ FIXED 2026-04-26 |
| IDOR on `/api/tasks/{id}/attachments` | S6 | (added during manual review) | ✅ FIXED 2026-04-26 |
| Stored XSS via contractor-proof upload | S7 | `specs/batch-s7-shannon-high-fix.md` | OPEN |
| No login lockout | S7 | same | OPEN |
| PayPlus webhook HMAC bypass | S7 | same | OPEN |
| GreenInvoice webhook auth | S7 | same | OPEN |
| Authorization case-sensitivity bypass | S7 | same | OPEN |
| Account enumeration via login-phone | S8 | `specs/batch-s8-shannon-medium-infra-outline.md` | OPEN |
| `auto-login.html` exposure | S8 | same | OPEN |
| OAuth phone leak | S8 | same | OPEN |
| CORS includes preview deployment domain | S8 | same | OPEN |
| Docker container runs as root | S8 | same | OPEN |
| `ALLOWED_HOSTS` not set on prod | S8 | same | OPEN |
| `/api/uploads/` no-auth static mount | S8 | same | OPEN |
| Mongo rate limiter fails open | S8 | same | OPEN |
| HSTS missing `preload` directive | S8 | same | OPEN |

### Test environment safety

- Scan ran exclusively against staging (`api-staging.brikops.com`, `brikops-staging-files`).
- Production was never touched.
- Demo data was modified by Shannon (test users created, one task reopened, fake webhook entries logged) — pollution is cosmetic and does not affect functionality.
- Real customer data: zero impact.

---

## Next planned scan

After S6 + S7 ship, re-run Shannon to verify:
1. All "OPEN" items above transition to "FIXED"
2. No new findings introduced by the patches

Frequency going forward: **quarterly** (or before any major release / public marketing campaign).
