# BrikOps Backup & Recovery — Context Snapshot
**Saved:** 2026-04-21
**Status:** Paused. To be resumed later when Zahi is ready for the smoke test.

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
| AWS Elastic Beanstalk commands | Backend runs on **AWS ECS** (per `.env.production.template`) |
| `aws elasticbeanstalk restart-app-server` | ECS uses `aws ecs update-service --force-new-deployment` |
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

### Check 3 — ECS cluster + service naming
```bash
aws ecs list-clusters
aws ecs list-services --cluster <name>
```
- Playbook assumes `brikops-prod` / `brikops-api` — verify actual names.

### Check 4 — Latest daily snapshot + cross-region
- Atlas → Cluster → Backup → Snapshots
- Latest should be < 24h old
- Cross-region copy should exist (Ireland or other) — if not, regional outage = no recovery

---

## Confirmed infrastructure (from codebase investigation)

```
Frontend:   React 19 → Cloudflare Pages → app.brikops.com
Backend:    FastAPI → AWS ECS (not EB!) → api.brikops.com
DB:         MongoDB Atlas
DB name:    contractor_ops
Region:     eu-central-1 (Frankfurt)
S3 bucket:  brikops-prod-files
SMS:        Twilio
WhatsApp:   Meta Cloud API
IAM:        ECS Task Role (no AWS_ACCESS_KEY in env)
```

### Collections
`users`, `organizations`, `org_memberships`, `project_memberships`, `projects`, `tasks`, `task_updates`, `handover_protocols`, `qc_inspections`, `project_plans`, `project_companies`, `companies`, `counters`, `audit_events`, `otp_codes`, `otp_metrics`, `sms_events`

### Critical field mappings (for queries under pressure)
- **users**: `id`, `phone_e164`, `user_status` (`active`/`pending_deletion`/`deleted`)
- **Deletion fields** (on user!): `user_status`, `deletion_requested_at`, `deletion_scheduled_for`, `deletion_type` (`account_only` / `full_purge`), `deletion_org_id` (only for full_purge)
- **OTP lockout** (in `otp_codes`, NOT users): `phone`, `attempts`, `locked_until`, `hashed_code`
- **Deletion execution**: `deletion_router.py` → `_anonymize_user_db()` ~line 412. No cron — triggered via super-admin endpoint.

---

## Outstanding risks (unverified, flagged for smoke-test)

1. **Atlas tier unknown** — if M0, entire DR story is broken
2. **S3 Versioning unknown** — could lose any deleted file forever
3. **No automated deletion cron** — means manual super-admin action required at grace expiry
4. **Cross-region backup unknown** — regional outage in eu-central-1 might mean total loss
5. **Single ECS task?** — if `desiredCount=1`, any task restart = downtime

---

## Notes for future AI Agent

The playbooks explicitly call out which steps an agent can automate vs which require human judgment:

**Fully automatable:**
- All 4 pre-flight checks (AWS + Atlas APIs)
- S3 restore (boto3)
- ECS restart (boto3)
- MongoDB failover test (Atlas API)
- Monitoring alerts (snapshot_age, versioning, task count, primary elections)

**Human-in-the-loop required:**
- PITR (choosing target time)
- Deletion anonymize execution (sensitive)
- Customer communication
- Post-mortem writing

**Recommended Agent endpoints to build:**
- `GET /admin/backup-health` → `{ latest_snapshot_ts, atlas_tier, s3_versioning, ecs_task_count }`
- `POST /admin/dr-test/s3-restore` → dummy file
- `POST /admin/dr-test/ecs-restart` → stop+verify

---

## Resume prompt (for later)

> "בוא נחזור ל-smoke test של הגיבוי. פתח את `/Users/zhysmy/brikops-new/docs/dr/backup-recovery-CONTEXT.md` ונתחיל מ-Pre-flight Check 1."
