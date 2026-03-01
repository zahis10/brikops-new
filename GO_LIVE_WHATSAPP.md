# GO LIVE — WhatsApp Notifications

**Status**: PENDING CREDENTIALS
**Last Updated**: 2026-02-17
**Build**: m1-dryrun-ready (12c4657)

---

## Pre-Requisites

Before starting, you must have:

- [ ] Meta Business account verified
- [ ] WhatsApp Business API access approved
- [ ] A dedicated WhatsApp Business phone number
- [ ] Message templates approved on Meta Business platform

---

## Step 1: Obtain Meta Credentials

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Navigate to your WhatsApp Business App
3. Under **API Setup**, copy:
   - **Temporary/Permanent Access Token** → `WA_ACCESS_TOKEN`
   - **Phone Number ID** → `WA_PHONE_NUMBER_ID`
4. Generate a random webhook verify token:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   → `WA_WEBHOOK_VERIFY_TOKEN`

---

## Step 2: Set Environment Variables

In the Replit Secrets panel (or production environment), set:

```
WA_ACCESS_TOKEN=<token from Step 1>
WA_PHONE_NUMBER_ID=<phone number ID from Step 1>
WA_WEBHOOK_VERIFY_TOKEN=<random token from Step 1>
WHATSAPP_ENABLED=true
```

**WARNING**: Do NOT set `WHATSAPP_ENABLED=true` in development/staging.
The code defaults to `false` — only override in production.

---

## Step 3: Create WhatsApp Message Templates

In Meta Business Manager → WhatsApp → Message Templates, create:

### Template 1: `contractor_new_defect`
- **Category**: Utility
- **Language**: Hebrew (he)
- **Header**: Media (Image)
- **Body**: `{{1}} — משימה חדשה הוקצתה אליך בפרויקט {{2}}. תיאור: {{3}}`
- **Variables**:
  1. Task title
  2. Project name
  3. Task description

### Template 2: `contractor_proof_submitted`
- **Category**: Utility
- **Language**: Hebrew (he)
- **Header**: Media (Image)
- **Body**: `קבלן {{1}} שלח הוכחת תיקון למשימה {{2}}. נא לאשר או לדחות.`

Wait for Meta to approve templates (usually 24-48 hours).

---

## Step 4: Configure Webhook

1. In Meta App Dashboard → WhatsApp → Configuration → Webhook:
   - **Callback URL**: `https://<your-domain>/api/notifications/webhook`
   - **Verify Token**: Same value as `WA_WEBHOOK_VERIFY_TOKEN`
2. Subscribe to webhook fields:
   - `messages`
   - `message_deliveries` (for delivery status tracking)
3. Click **Verify and Save**

The backend handles verification automatically via:
```
GET /api/notifications/webhook?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>
```

---

## Step 5: Test Send (Single Message)

1. Restart the application to pick up new environment variables
2. Verify the health endpoint shows WhatsApp enabled:
   ```bash
   curl https://<your-domain>/api/debug/version
   # Should show: "whatsapp_enabled": true
   ```
3. Create a test task with a real contractor phone number
4. Trigger a notification:
   ```bash
   curl -X POST https://<your-domain>/api/notifications/send/<task_id> \
     -H "Authorization: Bearer <admin_token>"
   ```
5. Verify:
   - [ ] Contractor receives WhatsApp message
   - [ ] Message contains correct task details
   - [ ] Image URL is accessible (absolute URL with domain)
   - [ ] Delivery status webhook fires (check `/api/notifications/stats`)

---

## Step 6: Verify Image URLs

Proof images must use absolute URLs for WhatsApp media headers.

1. Check that `REPLIT_DOMAINS` environment variable is set (auto-set by Replit)
   or set a custom domain
2. Image URLs should resolve to:
   ```
   https://<domain>/api/uploads/<uuid>.png
   ```
3. Test by opening an image URL in browser — should display the proof photo

---

## Step 7: Monitor & Validate

After enabling, monitor for 24 hours:

```bash
# Check notification stats
curl https://<your-domain>/api/notifications/stats \
  -H "Authorization: Bearer <admin_token>"
```

Expected response:
```json
{
  "total": 10,
  "sent": 8,
  "delivered": 7,
  "failed": 1,
  "skipped_dry_run": 0
}
```

- `skipped_dry_run` should be **0** (WhatsApp is active)
- `failed` should be minimal — check logs for failure reasons
- `delivered` confirms webhook is working

---

## Rollback Plan

If WhatsApp sending causes issues:

### Immediate (< 1 minute):
1. Set `WHATSAPP_ENABLED=false` in environment variables
2. Restart the application
3. Verify: `GET /api/debug/version` shows `whatsapp_enabled: false`

### Effect of rollback:
- All new notification jobs will get status `skipped_dry_run`
- Task lifecycle continues normally (no impact on workflow)
- Audit trail still records all events
- Previously sent messages are not affected

### After rollback, investigate:
1. Check notification stats: `GET /api/notifications/stats`
2. Review failed notifications in MongoDB:
   ```
   db.notification_jobs.find({status: "failed"}).sort({created_at: -1}).limit(10)
   ```
3. Check server logs for WhatsApp API errors
4. Common issues:
   - Expired access token → regenerate in Meta dashboard
   - Rate limiting → Meta allows ~80 messages/second for business tier
   - Template not approved → check template status in Meta Business
   - Phone number not verified → complete Meta Business verification

---

## Checklist Summary

| Step | Action | Status |
|------|--------|--------|
| 1 | Obtain Meta credentials | ☐ |
| 2 | Set environment variables | ☐ |
| 3 | Create & approve message templates | ☐ |
| 4 | Configure webhook | ☐ |
| 5 | Test send (single message) | ☐ |
| 6 | Verify image URLs | ☐ |
| 7 | Monitor for 24 hours | ☐ |

---

**Contact**: For Meta WhatsApp API issues, see [Meta WhatsApp Business Documentation](https://developers.facebook.com/docs/whatsapp/cloud-api)
