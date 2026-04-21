# BrikOps Backup & Recovery — Context Snapshot
**Saved:** 2026-04-21
**Last updated:** 2026-04-21 (post pre-flight verification)
**Status:** Pre-flight checks 1-4 ✅ passed. Ready for scenario 1.

---

## Files in this bundle
1. `backup-recovery-playbook-v2.md` — the corrected smoke-test playbook (6 scenarios + 4 pre-flight checks)
2. `emergency-runbook-v2.md` — the corrected real-incident runbook

Both are in this same folder: `/Users/zhysmy/brikops-new/docs/dr/`

---

## Why v2 was needed

The original playbook/runbook (built in another chat) had critical inaccuracies that would cause commands to silently fail in practice:

| Original (wrong) | Reality (from code) |
|---|---|
| `db.orgs.findOne` | Collection is `organizations` |
| `phone: "+972..."` field | Field is `phone_e164` |
| `db.users` → `otp_lockout_until` | OTP lockout lives in **`otp_codes`** collection: `locked_until`, `attempts` |
| `status: pending_deletion` on org | It's on the **user**: `user_status: 'pending_deletion'` |
| `scheduled_deletion_at` | Code uses `deletion_scheduled_for` |
| AWS Elastic Beanstalk commands | *(v2 mistakenly switched to ECS — see "v2-was-wrong" below. Reality: **Elastic Beanstalk with Docker platform**)* |
| `python3 -m contractor_ops.account_deletion_cron` | **No such cron exists.** Deletion is executed via super-admin endpoint in `deletion_router.py` (`_anonymize_user_db`) |
| DB name `brikops_prod` | Actual DB: `contractor_ops` |
| Assumed M10 Atlas tier | Unverified. If M0, there's no PITR at all. |
| Assumed S3 Versioning ON | Unverified. No app code toggles this. |

---

## When Zahi resumes, start here

Run these 4 pre-flight checks before any scenario. If any fails, the dependent scenario is pointless.

### Check 1 — Atlas tier supports PITR?
- URL: https://cloud.mongodb.com
- Cluster → overview → note tier (M0/M2/M5/M10+)
- **Required: M10+** for Point-in-Time Recovery

### Check 2 — S3 Versioning enabled?
- AWS Console → S3 → `brikops-prod-files` → Properties → Bucket Versioning
- **Required: Enabled** (otherwise scenario 2 is impossible)
- If Disabled → enable NOW before continuing

### Check 3 — Elastic Beanstalk environment naming
```bash
aws elasticbeanstalk describe-environments --region eu-central-1
```
- **Verified 2026-04-21:**
  - Application: `brikops-api`
  - Environment: `Brikops-api-env` (capital B)
  - Platform: Docker
  - Region: eu-central-1
  - Health: Ok
- Single environment — any restart = brief downtime. Mitigation in playbook scenario 5.

### Check 4 — Latest daily snapshot + cross-region
- Atlas → Cluster → Backup → Snapshots
- Latest should be < 24h old
- Cross-region copy should exist (Ireland or other) — if not, regional outage = no recovery

---

## Confirmed infrastructure (from codebase investigation)

```
Frontend:   React 19 → Cloudflare Pages → app.brikops.com
Backend:    FastAPI → AWS Elastic Beanstalk (Docker platform) → api.brikops.com
            App name: brikops-api
            Env name: Brikops-api-env
            Deploy:   GitHub Actions → EB (triggered by push to main when backend/** or .platform/** changes)
            EB artifact bucket: elasticbeanstalk-eu-central-1-457550570829 (do NOT delete)
DB:         MongoDB Atlas — cluster `brikops-eu`, tier M10, MongoDB 8.0.20
DB name:    contractor_ops
Atlas snapshots: every 6h (labeled "hourly" in Atlas UI), daily, weekly, monthly, yearly
                 Cross-region copy → eu-west-1 (Ireland)
                 PITR enabled (M10+)
Region:     eu-central-1 (Frankfurt)
S3 bucket:  brikops-prod-files (Bucket Versioning: Enabled)
S3 prefixes (flat, NOT nested by project): `qc/`, `attachments/`, `exports/{org}/`,
            `signatures/{user}/`, `billing-receipts/{user}/`
SMS:        Twilio
WhatsApp:   Meta Cloud API
IAM:        EB EC2 Instance Profile (no AWS_ACCESS_KEY in env)
```

### Collections
`users`, `organizations`, `org_memberships`, `project_memberships`, `projects`, `tasks`, `task_updates`, `handover_protocols`, `qc_inspections`, `project_plans`, `project_companies`, `companies`, `counters`, `audit_events`, `otp_codes`, `otp_metrics`, `sms_events`

### Critical field mappings (for queries under pressure)
- **users**: `id`, `phone_e164`, `user_status` (`active`/`pending_deletion`/`deleted`)
- **Deletion fields** (on user!): `user_status`, `deletion_requested_at`, `deletion_scheduled_for`, `deletion_type` (`account_only` / `full_purge`), `deletion_org_id` (only for full_purge)
- **OTP lockout** (in `otp_codes`, NOT users): `phone`, `attempts`, `locked_until`, `hashed_code`
- **Deletion execution**: `deletion_router.py` → `_anonymize_user_db()` ~line 412. No cron — triggered via super-admin endpoint.

---

## Verified findings (2026-04-21 pre-flight)

| Area | Status | Notes |
|---|---|---|
| Atlas tier | ✅ M10 | PITR available |
| Atlas cluster name | ✅ `brikops-eu` | us cluster = migration leftover, scheduled for deletion |
| Cross-region backup | ✅ eu-west-1 (Ireland) | currently 1-day retention → **recommend raise to 7 days** |
| S3 Versioning | ✅ Enabled | |
| Backend service | ✅ Elastic Beanstalk | App `brikops-api`, env `Brikops-api-env`, Docker platform |
| EB health | ✅ Ok | Single env — restart causes brief downtime |
| Snapshot age | ✅ < 24h | verified in Atlas Backup UI |
| Deletion cron | ❌ Does not exist | deletion at grace expiry = manual super-admin call |
| S3 structure | ⚠️ Flat, not project-scoped | restore-by-project requires DB lookup; see risk #2 below |

## Outstanding risks (post pre-flight)

1. **No automated deletion cron** — manual super-admin action required at grace expiry; risk of forgetting = PII retained past 30d. *Fix path:* build a daily cron or endpoint `POST /admin/deletion/tick`.
2. **S3 flat structure** — a "I lost project X's photos" request can't be served by S3 prefix alone; need DB lookup of task_updates / qc_inspections to find keys. *Fix path:* restructure NEW uploads to `orgs/{org_id}/projects/{project_id}/{type}/{uuid}.{ext}` + build `GET /admin/files?project_id=X`.
3. **Single EB environment** — any EB restart/deploy = brief downtime. *Fix path:* if/when traffic warrants, add second instance via EB load balancer config, or move to Fargate.
4. **Cross-region retention is only 1 day** — if regional outage in Frankfurt lasts > 24h and latest Ireland copy is corrupted, no recovery. *Fix path:* raise retention to 7 days in Atlas Backup Policy.

---

## Notes for future AI Agent

The playbooks explicitly call out which steps an agent can automate vs which require human judgment:

**Fully automatable:**
- All 4 pre-flight checks (AWS + Atlas APIs)
- S3 restore (boto3)
- Elastic Beanstalk restart (boto3: `elasticbeanstalk.restart_app_server`)
- MongoDB failover test (Atlas API)
- Monitoring alerts (snapshot_age, versioning, EB env health, primary elections)

**Human-in-the-loop required:**
- PITR (choosing target time)
- Deletion anonymize execution (sensitive)
- Customer communication
- Post-mortem writing

**Recommended Agent endpoints to build:**
- `GET /admin/backup-health` → `{ latest_snapshot_ts, atlas_tier, s3_versioning, eb_env_health, eb_instance_count }`
- `POST /admin/dr-test/s3-restore` → dummy file
- `POST /admin/dr-test/eb-restart` → restart EB env + verify /health
- `POST /admin/deletion/tick` → the missing cron (enumerate users where `user_status='pending_deletion'` AND `deletion_scheduled_for <= now`, call `_anonymize_user_db`)

---

## Resume prompt (for later)

> "בוא נחזור ל-smoke test של הגיבוי. פתח את `/Users/zhysmy/brikops-new/docs/dr/backup-recovery-CONTEXT.md` ונתחיל מ-Pre-flight Check 1."
