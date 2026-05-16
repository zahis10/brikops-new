# Staging Phase 1 — Backend EB Environment

> **Task #57.1** — Create `Brikops-api-staging-env` on AWS Elastic Beanstalk, fully isolated from prod, ready to receive deploys via `./deploy.sh --staging` (Phase 5).

## What & Why

**Pre-launch infrastructure.** We need a staging environment so we can:

1. Validate every prod-bound deploy on a real EB env with real Mongo + S3 first (catch regressions before users).
2. Run **Shannon (Keygraph)** active pentests — Shannon performs real exploits and CAN damage data. MUST run on staging only.
3. Practice rollbacks and DR scenarios safely.

**Today's gap:** We only have `Brikops-api-env`. Every Replit `./deploy.sh --prod` ships straight to users. Capgo `--prod` channel does the same for mobile. Zero buffer.

**Phase 1 scope (this spec):** Backend EB environment only. Out of scope (separate phases):
- Phase 2: MongoDB `brikops_staging` DB + isolated user
- Phase 3: S3 `brikops-staging-files` bucket + CORS + versioning
- Phase 4: Frontend Cloudflare Pages staging branch + `staging.brikops.com` red banner
- Phase 5: Update `deploy.sh` to support `--staging` flag
- Phase 6: First end-to-end staging test
- Phase 7: Shannon (Keygraph) setup + first scan

**Phase 1 done = `https://api-staging.brikops.com/health` returns `{"status":"ok",...}` and rejects unknown CORS origins.**

---

## Pre-flight (already verified — DO NOT re-run)

✅ AWS CLI v2 installed via official installer (brew failed on Python 3.14 libexpat)
✅ EB CLI installed via brew
✅ AWS configured with IAM user `zahi-cli` (root keys avoided)
✅ EB Application name: `brikops-api`
✅ EB Environment (prod): `Brikops-api-env`
✅ EB region: `eu-central-1`
✅ S3 buckets discovered: `brikops-prod-files`, `brikops-prod-files-backup-ireland`
✅ All 59 prod env var names cataloged into 7 categories (see "Env var matrix" below)

---

## Done looks like

After Phase 1 completes, all of these MUST pass:

```bash
# 1. EB env exists and is Green
aws elasticbeanstalk describe-environments \
  --region eu-central-1 \
  --environment-names Brikops-api-staging-env \
  --query 'Environments[0].[Status,Health]' \
  --output table
# Expected: Ready / Green

# 2. Backend responds on the EB-assigned URL
curl -i http://Brikops-api-staging-env.<random>.eu-central-1.elasticbeanstalk.com/health
# Expected: HTTP 200, {"status":"ok","uptime_seconds":N}

# 3. After DNS: backend responds on api-staging.brikops.com
curl -i https://api-staging.brikops.com/health
# Expected: HTTP 200, {"status":"ok","uptime_seconds":N}

# 4. CORS validator accepts staging origin
curl -i -H "Origin: https://staging.brikops.com" \
  https://api-staging.brikops.com/health 2>&1 | grep -i "access-control-allow-origin"
# Expected: access-control-allow-origin: https://staging.brikops.com

# 5. CORS validator REJECTS prod origin (proves env isolation)
curl -i -H "Origin: https://app.brikops.com" \
  https://api-staging.brikops.com/health 2>&1 | grep -i "access-control-allow-origin"
# Expected: NO access-control-allow-origin header (or different origin)

# 6. CORS validator REJECTS evil origin (proves S5b validators active)
curl -i -H "Origin: https://evil.com" \
  https://api-staging.brikops.com/health 2>&1 | grep -i "access-control-allow-origin"
# Expected: NO access-control-allow-origin: https://evil.com

# 7. Mongo isolation — staging logs show DB_NAME=brikops_staging, NOT brikops_prod
aws elasticbeanstalk describe-events \
  --region eu-central-1 \
  --environment-name Brikops-api-staging-env \
  --max-items 30 | grep -E "DB_NAME|DB-IDENTITY"
# Expected: DB_NAME=brikops_staging
```

---

## Env var matrix (59 vars in 7 categories)

This is the **complete plan** for which value each var gets in staging. The actual values are pasted in Step 4 below.

| # | Category | Strategy | Examples |
|---|----------|----------|----------|
| 1 | **Env-specific** (5 vars) | NEW staging values | `APP_MODE=staging`, `DB_NAME=brikops_staging`, `MONGO_URL=<staging cluster>`, `AWS_S3_BUCKET=brikops-staging-files`, `FRONTEND_BASE_URL=https://staging.brikops.com` |
| 2 | **Secrets** (8 vars) | FRESH per-staging — never reuse prod secrets | `JWT_SECRET`, `JWT_SECRET_VERSION`, `META_APP_SECRET`, `WA_WEBHOOK_VERIFY_TOKEN`, `CRON_SECRET`, `PAYPLUS_SECRET_KEY`, `GI_API_SECRET`, `GI_WEBHOOK_SECRET` |
| 3 | **Sandbox-mode** (12 vars) | Switch to test/sandbox endpoints + creds | `PAYPLUS_ENV=sandbox`, all `PAYPLUS_*_UID`, `GI_BASE_URL` (sandbox), Twilio test creds, WhatsApp staging numbers |
| 4 | **CORS** (1 var) | Staging-specific origin list | `CORS_ORIGINS=https://staging.brikops.com,https://brikops-new-staging.pages.dev,capacitor://localhost,ionic://localhost,https://localhost,http://localhost:3000,http://localhost:5173` |
| 5 | **Feature flags** (10 vars) | Mirror prod defaults, override by case | Most copy-as-is; override `ENABLE_DEBUG_ENDPOINTS=true` for QA |
| 6 | **Copy-as-is** (15 vars) | Identical to prod | SMTP host/port, Apple/Google client IDs, JWT_EXPIRATION_HOURS, OTP_TTL_SECONDS, regional config |
| 7 | **Demo/safety** (8 vars) | Tighter than prod (staging is for testing) | `DEMO_RESET_PASSWORDS=true`, `ENABLE_DEMO_USERS=true`, `OTP_PROVIDER=mock`, `SMS_MODE=stub` |

**Critical rule:** secrets in staging MUST be different from prod. If staging leaks, prod must remain unaffected.

---

## Steps

### Step 1 — Generate fresh staging secrets

Run on Mac:

```bash
mkdir -p ~/brikops-new/secrets
chmod 700 ~/brikops-new/secrets
cat > ~/brikops-new/secrets/staging-secrets.env << 'EOF'
# DO NOT COMMIT — already in .gitignore. Generated 2026-04-25.
# Each value is independent of prod. Rotate if leaked.
JWT_SECRET=$(openssl rand -hex 32)
JWT_SECRET_VERSION=v1-staging
META_APP_SECRET=$(openssl rand -hex 32)
WA_WEBHOOK_VERIFY_TOKEN=$(openssl rand -hex 16)
CRON_SECRET=$(openssl rand -hex 32)
EOF

# Now actually substitute (the heredoc above won't expand $() — re-run):
cd ~/brikops-new/secrets
{
  echo "JWT_SECRET=$(openssl rand -hex 32)"
  echo "JWT_SECRET_VERSION=v1-staging"
  echo "META_APP_SECRET=$(openssl rand -hex 32)"
  echo "WA_WEBHOOK_VERIFY_TOKEN=$(openssl rand -hex 16)"
  echo "CRON_SECRET=$(openssl rand -hex 32)"
} > staging-secrets.env
chmod 600 staging-secrets.env
cat staging-secrets.env
```

Verify:
- File has 5 lines
- `JWT_SECRET` is 64 hex chars
- File mode is `-rw-------` (only you can read)

**`secrets/` MUST be in `.gitignore`. Verify:**

```bash
cd ~/brikops-new
grep -q "^secrets/" .gitignore && echo "OK gitignored" || echo "secrets/" >> .gitignore
git status secrets/  # should show "untracked" or nothing
```

---

### Step 2 — Save current prod EB config as a baseline (for cloning)

```bash
cd ~/brikops-new
eb use Brikops-api-env --region eu-central-1
eb config save --cfg prod-baseline-2026-04-25
# This writes .elasticbeanstalk/saved_configs/prod-baseline-2026-04-25.cfg.yml
ls -la .elasticbeanstalk/saved_configs/
```

You now have a snapshot of prod env config. **Do not edit this file.** It's our recovery anchor.

---

### Step 3 — Create the staging EB environment (cloned from prod-baseline, NO env vars yet)

```bash
cd ~/brikops-new

# Clone the saved config but use a different env name and tier
eb create Brikops-api-staging-env \
  --region eu-central-1 \
  --cfg prod-baseline-2026-04-25 \
  --instance-type t3.small \
  --single \
  --envvars "APP_MODE=staging,APP_ID=brikops-staging-001"
```

Flags explained:
- `--single` = single instance, no load balancer (cheaper, ~$15/mo vs $50/mo). Switch to LB later if needed for Shannon load tests.
- `--instance-type t3.small` = matches prod, supports the same Python runtime.
- `--envvars` sets the **two minimum** vars EB needs to boot. The rest go in Step 4 to keep this command short.

This takes **5-10 minutes**. Monitor:

```bash
eb status Brikops-api-staging-env --region eu-central-1
# Wait until Status: Ready, Health: Red (Red is expected — missing env vars)
```

Expected first state: **Status: Ready, Health: Red** because the app will crash on boot (missing `JWT_SECRET`, `MONGO_URL`, etc.). That's fine — Step 4 fixes it.

---

### Step 4 — Set ALL 59 env vars on staging

**This step has 7 sub-batches matching the categories above.** Run them in order. Each batch is a single `eb setenv` command.

**Wait at least 60 seconds between batches** — every `setenv` triggers a config update on EB.

#### 4a — Env-specific (5 vars)

⚠️ Phase 2 will create `brikops_staging` Mongo DB. Until then, use the prod cluster but point at a NEW empty DB. No data sharing.

```bash
eb setenv \
  APP_MODE=staging \
  DB_NAME=brikops_staging \
  MONGO_URL='<COPY-FROM-PROD-EB-CONFIG-STEP-2>' \
  AWS_S3_BUCKET=brikops-staging-files \
  FRONTEND_BASE_URL=https://staging.brikops.com \
  --environment Brikops-api-staging-env \
  --region eu-central-1
```

To get prod `MONGO_URL` without exposing it in shell history:

```bash
# Read from the saved config (no echo to terminal):
grep MONGO_URL ~/brikops-new/.elasticbeanstalk/saved_configs/prod-baseline-2026-04-25.cfg.yml | head -1
# Copy that value into the eb setenv command above (paste once, don't save to file)
```

⚠️ **`AWS_S3_BUCKET=brikops-staging-files`** points at a bucket that does NOT YET EXIST. Phase 3 creates it. Until then, any S3 write from staging will fail loudly — that's intentional (no accidental writes to prod bucket).

#### 4b — Secrets (8 vars) — paste from `~/brikops-new/secrets/staging-secrets.env`

```bash
# Source the file then expand into eb setenv:
source ~/brikops-new/secrets/staging-secrets.env

eb setenv \
  JWT_SECRET="$JWT_SECRET" \
  JWT_SECRET_VERSION="$JWT_SECRET_VERSION" \
  META_APP_SECRET="$META_APP_SECRET" \
  WA_WEBHOOK_VERIFY_TOKEN="$WA_WEBHOOK_VERIFY_TOKEN" \
  CRON_SECRET="$CRON_SECRET" \
  --environment Brikops-api-staging-env \
  --region eu-central-1

# PayPlus + GI staging creds — get from PayPlus and Green Invoice sandbox dashboards.
# If you don't have sandbox accounts yet, set placeholders that fail loudly:
eb setenv \
  PAYPLUS_API_KEY=STAGING_PLACEHOLDER_REPLACE_ME \
  PAYPLUS_SECRET_KEY=STAGING_PLACEHOLDER_REPLACE_ME \
  GI_API_KEY_ID=STAGING_PLACEHOLDER_REPLACE_ME \
  GI_API_SECRET=STAGING_PLACEHOLDER_REPLACE_ME \
  GI_WEBHOOK_SECRET=STAGING_PLACEHOLDER_REPLACE_ME \
  --environment Brikops-api-staging-env \
  --region eu-central-1
```

#### 4c — Sandbox-mode (12 vars)

```bash
eb setenv \
  PAYPLUS_ENV=sandbox \
  PAYPLUS_PAYMENT_PAGE_UID=SANDBOX_PAGE_UID_REPLACE_ME \
  PAYPLUS_TERMINAL_UID=SANDBOX_TERMINAL_UID_REPLACE_ME \
  PAYPLUS_CASHIER_UID=SANDBOX_CASHIER_UID_REPLACE_ME \
  PAYPLUS_CALLBACK_URL=https://api-staging.brikops.com/api/billing/payplus/callback \
  GI_BASE_URL=https://api.greeninvoice.co.il/api/v1 \
  TWILIO_ACCOUNT_SID=AC_TEST_SID_REPLACE_ME \
  TWILIO_AUTH_TOKEN=TEST_TOKEN_REPLACE_ME \
  TWILIO_FROM_NUMBER='+15005550006' \
  TWILIO_MESSAGING_SERVICE_SID='' \
  WA_PHONE_NUMBER_ID=STAGING_WA_NUMBER_REPLACE_ME \
  WA_ACCESS_TOKEN=STAGING_WA_TOKEN_REPLACE_ME \
  --environment Brikops-api-staging-env \
  --region eu-central-1
```

Note: `+15005550006` is Twilio's official magic number that always succeeds in tests without sending real SMS. Keep that until you wire a real staging Twilio sub-account.

#### 4d — CORS (1 var)

```bash
eb setenv \
  CORS_ORIGINS='https://staging.brikops.com,https://brikops-new-staging.pages.dev,capacitor://localhost,ionic://localhost,https://localhost,http://localhost:3000,http://localhost:5173' \
  --environment Brikops-api-staging-env \
  --region eu-central-1
```

⚠️ This is the **#1 difference** from prod. If staging accidentally has prod's CORS list, a compromised staging frontend could call prod's APIs from the user's browser. Keep them strictly separated.

#### 4e — Feature flags (10 vars)

```bash
eb setenv \
  WHATSAPP_ENABLED=false \
  WA_INVITE_ENABLED=false \
  ENABLE_REMINDER_SCHEDULER=true \
  ENABLE_SAFETY_MODULE=false \
  ENABLE_ONBOARDING_V2=true \
  ENABLE_AUTO_TRIAL=true \
  ENABLE_DEFECTS_V2=true \
  ENABLE_COMPLETE_ACCOUNT_GATE=off \
  ENABLE_QUICK_LOGIN=false \
  ENABLE_DEBUG_ENDPOINTS=true \
  --environment Brikops-api-staging-env \
  --region eu-central-1
```

`WHATSAPP_ENABLED=false` until you have real Meta sandbox credentials. With S5b's TOCTOU guard, the app will refuse to boot if you set `WHATSAPP_ENABLED=true` without a real `META_APP_SECRET`.

`ENABLE_DEBUG_ENDPOINTS=true` — staging exposes diagnostic endpoints we deliberately don't expose in prod.

#### 4f — Copy-as-is (15 vars)

```bash
# Get values from the prod baseline file:
grep -E '^(SMTP_|GOOGLE_CLIENT_ID|APPLE_|JWT_EXPIRATION|OTP_|STEPUP_)' \
  ~/brikops-new/.elasticbeanstalk/saved_configs/prod-baseline-2026-04-25.cfg.yml

# Then run a single eb setenv with the values pasted in. Example template:
eb setenv \
  SMTP_HOST=smtp.gmail.com \
  SMTP_PORT=587 \
  SMTP_USER='<from-prod>' \
  SMTP_PASS='<from-prod>' \
  SMTP_FROM='<from-prod>' \
  SMTP_FROM_NAME='[STAGING] BrikOps' \
  SMTP_REPLY_TO=support@brikops.com \
  GOOGLE_CLIENT_ID_WEB='<from-prod>' \
  GOOGLE_CLIENT_ID_IOS='<from-prod>' \
  GOOGLE_CLIENT_ID_ANDROID='<from-prod>' \
  APPLE_BUNDLE_ID=com.brikops.app \
  APPLE_SERVICES_ID='<from-prod>' \
  JWT_EXPIRATION_HOURS=720 \
  OTP_TTL_SECONDS=600 \
  STEPUP_EMAIL='<from-prod>' \
  --environment Brikops-api-staging-env \
  --region eu-central-1
```

⚠️ **`SMTP_FROM_NAME='[STAGING] BrikOps'`** — this is the ONE override. Every email from staging will say `[STAGING]` so you instantly know it didn't come from prod.

#### 4g — Demo / safety (8 vars)

```bash
eb setenv \
  ENABLE_DEMO_USERS=true \
  DEMO_DEFAULT_PASSWORD='StagingDemo2026!' \
  DEMO_RESET_PASSWORDS=true \
  OTP_PROVIDER=mock \
  SMS_MODE=stub \
  SMS_ENABLED=false \
  ALLOWED_HOSTS='api-staging.brikops.com' \
  SUPER_ADMIN_PHONE='<your-phone-here-E164>' \
  --environment Brikops-api-staging-env \
  --region eu-central-1
```

⚠️ **`SMS_MODE=stub` is a config error in prod (forbidden by config.py:151).** It only works because `APP_MODE=staging`. Verified safe.

⚠️ `OTP_PROVIDER=mock` means OTP codes are logged instead of texted. Faster QA, but anyone with log access can log in. Acceptable for staging.

---

### Step 5 — Watch the deploy and verify the app boots

```bash
# Tail EB events in another terminal:
eb events Brikops-api-staging-env --region eu-central-1 --follow

# In the main terminal, watch health:
watch -n 5 "eb status Brikops-api-staging-env --region eu-central-1 | grep -E 'Status|Health'"
```

What to look for:
- ✅ `Status: Ready`
- ✅ `Health: Green` (Yellow is also OK — it goes Yellow during config updates)
- ✅ In events: `Successfully launched environment`
- ❌ If `Health: Red` after Step 4 finishes: read the events for the `RuntimeError` message. Most likely culprits:
  - `JWT_SECRET` too short (must be ≥32 chars)
  - `MONGO_URL` typo (should start with `mongodb://` or `mongodb+srv://`)
  - `CORS_ORIGINS` empty or contains `*` (S5b validators kill the boot)

---

### Step 6 — Verify on the EB-assigned URL (before DNS)

```bash
# Get the EB-assigned URL:
EB_URL=$(aws elasticbeanstalk describe-environments \
  --region eu-central-1 \
  --environment-names Brikops-api-staging-env \
  --query 'Environments[0].CNAME' --output text)
echo "Staging URL: http://$EB_URL"

# Hit health:
curl -i "http://$EB_URL/health"
# Expected: HTTP 200, {"status":"ok","uptime_seconds":N}

# CORS sanity (no DNS yet, so use the EB URL as Origin):
curl -i -H "Origin: https://staging.brikops.com" "http://$EB_URL/health" 2>&1 | grep -i "access-control"
# Expected: access-control-allow-origin: https://staging.brikops.com
```

If both pass, the env is functionally ready. DNS is the last step.

---

### Step 7 — DNS: `api-staging.brikops.com` → EB env

This depends on where `brikops.com` is managed. Most likely Cloudflare (since `app.brikops.com` is on Cloudflare).

**Cloudflare path:**

1. Log in to Cloudflare → `brikops.com` zone → **DNS** → **Add record**.
2. Type: `CNAME`
3. Name: `api-staging`
4. Target: `$EB_URL` (the value from Step 6, without `http://` or trailing slash)
5. Proxy status: **DNS only** (gray cloud — orange-cloud Cloudflare proxy interferes with EB health checks initially)
6. TTL: Auto
7. Save.

Wait 1-3 minutes for propagation, then:

```bash
dig +short api-staging.brikops.com
# Expected: returns the EB CNAME or IP

# But EB is HTTP-only on the assigned URL. The HTTPS termination needs to come from Cloudflare:
# Set Cloudflare → SSL/TLS → "Flexible" mode for api-staging.brikops.com
# (Same setup as api.brikops.com — verify via Cloudflare dashboard)

# After SSL is up:
curl -i https://api-staging.brikops.com/health
# Expected: HTTP 200, JSON body
```

⚠️ **If Cloudflare SSL is "Full (strict)" on the zone**, you must either:
- Use the same mode for the staging subdomain, AND attach a real cert to EB (extra cost), OR
- Add a **Page Rule** for `api-staging.brikops.com/*` that overrides SSL to `Flexible`.

The current prod setup (`api.brikops.com` → EB → Cloudflare Flexible) is the simpler path and matches.

---

### Step 8 — Final verification (the 7 checks from "Done looks like")

Run all 7 commands from the "Done looks like" section at the top of this spec. Every single one MUST pass. If any fails, **do not proceed to Phase 2** — fix the failing check first. The whole point of staging is being able to trust it.

---

## Cost estimate

| Component | Monthly cost (USD) |
|-----------|---------------------|
| t3.small EC2 (single instance) | ~$15 |
| EBS volume (8 GB gp3) | ~$0.80 |
| Elastic IP (if attached) | $0 (free if attached) |
| EB application metadata (S3) | ~$0.05 |
| Bandwidth (outbound, ~5 GB/mo) | ~$0.45 |
| **Phase 1 total** | **~$16/mo** |

Phases 2+3 add: Mongo M0 free tier ($0) + S3 staging bucket (~$1/mo for ~50 GB).

Total staging infra after all phases: **~$17/mo**. Well within budget for the value (no more "deploy directly to users" stress).

---

## Out of scope (do NOT do in this phase)

- ❌ Don't create `brikops_staging` Mongo DB yet — Phase 2 handles that with proper user isolation. Step 4a points at the prod cluster but uses a different DB name; Mongo will create the empty DB on first write, which is fine.
- ❌ Don't create the S3 staging bucket yet — Phase 3 handles that with CORS + versioning + lifecycle policies.
- ❌ Don't update `deploy.sh` yet — Phase 5 adds the `--staging` flag. For now, use raw `eb deploy Brikops-api-staging-env` from a feature branch.
- ❌ Don't run Shannon yet — Phase 7. Shannon needs Mongo + S3 isolated first or it will damage prod data.

---

## Rollback

If anything in Steps 4-8 goes wrong and you need a clean slate:

```bash
eb terminate Brikops-api-staging-env --region eu-central-1
# Confirms with the env name. Takes ~5 min. Removes EC2, EBS, security group.
# Saved config in .elasticbeanstalk/saved_configs/ is preserved — re-run Step 3 to recreate.
```

⚠️ `eb terminate` does NOT touch the Mongo cluster, S3 buckets, or DNS records. Manual cleanup needed for those if you've created them.

---

## After Phase 1 is done

Update `ROADMAP.md`:
- Mark Task #57.1 (Phase 1) ✅ in the staging section
- Capture the actual EB CNAME and document it (next to "EB Environment (staging)")
- Note any deviations from this spec (e.g., chose `t3.medium` instead of `t3.small`)

Then move to **Phase 2 spec** — Mongo `brikops_staging` DB + isolated user (different writeable DB, separate Atlas user with RBAC limited to that DB only).
