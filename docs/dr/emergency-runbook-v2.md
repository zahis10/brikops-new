# BrikOps — Emergency Runbook v2

**מתי להשתמש:** אירוע אמת בפרודקשן.
**עודכן:** 2026-04-21 — שמות collections, hosting, ו-fields מתוקנים לפי הקוד האמיתי.

---

## תשתית אמיתית (זכור ברגע לחץ!)

| רכיב | ערך |
|---|---|
| Hosting | **AWS ECS** (לא Elastic Beanstalk) |
| Cluster | `brikops-prod` (אמת) |
| Service | `brikops-api` (אמת) |
| DB | `contractor_ops` ב-MongoDB Atlas |
| Region | `eu-central-1` (Frankfurt) |
| S3 bucket | `brikops-prod-files` |
| Frontend | Cloudflare Pages → `app.brikops.com` |
| Backend URL | `api.brikops.com` |

---

## 🚨 הצעד הראשון — תמיד

1. נשום. תגיד: "אני לוקח 2 דקות להבין."
2. אל תיכנס לפאניקה ב-WhatsApp. תגיד "אני על זה, חוזר אלייך תוך 10 דקות" ותכבד את הזמן.
3. תעד שעה: `14:23 — Yossi דיווח: "הפרויקט ריק"`
4. צלם screenshots של הכל (המסך של הלקוח, לוגים, DB results).
5. אל תפעיל פעולות הפיכות. תסתכל לפני שתפעל.

---

## שלב 1 — אבחון (5–10 דק')

### מה מדווח הלקוח?
- [ ] לא יכול להיכנס → **auth issue** (שלב 2A)
- [ ] נכנס אבל לא רואה data → **DB/display issue** (שלב 2B)
- [ ] רואה data אבל תמונות שבורות → **S3 issue** (שלב 2C)
- [ ] האפליקציה לאה מאוד → **performance** (שלב 2E)
- [ ] שגיאה ספציפית → בקש screenshot

### מי מושפע?
- [ ] רק לקוח אחד — בעיה על ה-data שלו (לא תשתית)
- [ ] כמה לקוחות — אולי feature-specific
- [ ] כולם — התשתית נפלה

### Infrastructure status (3 tabs)
1. **MongoDB Atlas** → Cluster → Metrics
2. **AWS ECS** → Cluster `brikops-prod` → Service `brikops-api` → Tasks
3. **Cloudflare** → status.cloudflare.com

---

## שלב 2A — "לא יכול להיכנס"

1. בקש screenshot של השגיאה
2. בדוק logs (CloudWatch, לא EB!):
```bash
aws logs tail /ecs/brikops-api --follow --since 30m --filter-pattern "ERROR"
# או חפש לפי טלפון (אבל מוצפן ב-mask_phone — חפש 4 ספרות אחרונות)
aws logs tail /ecs/brikops-api --since 30m --filter-pattern "1234"  # 4 ספרות אחרונות
```

3. בדוק ב-DB:
```javascript
db.users.findOne({ phone_e164: "+9725..." })  // ⚠️ phone_e164, לא phone!
// האם user_status === 'pending_deletion'? (אז נעול ל-deletion)
// האם user_status === 'deleted'? (anonymized — לא יכול להיכנס)
```

4. אם OTP — בדוק lockout **ב-otp_codes** (לא users!):
```javascript
db.otp_codes.findOne({ phone: "+9725..." })
// אם locked_until > now → נעול

// אפס lockout:
db.otp_codes.updateOne(
  { phone: "+9725..." },
  { $set: { attempts: 0, locked_until: null, hashed_code: null } }
)
```

5. אם לא מצליח ב-10 דק' → עזור דרך super-admin reset או מייל magic link.

---

## שלב 2B — "Data נעלם / הפרויקט ריק"

**99% מהפעמים ה-data קיים — רק בעיית תצוגה.**

1. בדוק ב-DB:
```javascript
db.projects.findOne({ id: "PROJECT_ID" })
db.tasks.countDocuments({ project_id: "PROJECT_ID" })
db.task_updates.countDocuments({ project_id: "PROJECT_ID" })
```

2. אם count תואם ← display bug:
   - Browser console (F12) אצל הלקוח
   - Network tab — האם ה-API מחזיר data?
   - JWT expired? (refresh)
   - `CORS_ORIGINS` missing?

3. אם count = 0 ← data loss → **שלב 3** (שחזור PITR)

---

## שלב 2C — "תמונות שבורות"

1. רק אחד → בעיה רשת אצלו (WiFi→4G)
2. לכולם:
```bash
# בדוק באמצעות key S3 ספציפי
aws s3 ls s3://brikops-prod-files/projects/XXX/task-photos/YYY.jpg

# בדוק את האובייקט
aws s3api head-object --bucket brikops-prod-files --key "projects/XXX/..."

# בדוק signed URL מה-API
curl -i "https://api.brikops.com/api/tasks/XXX/attachments" \
  -H "Authorization: Bearer TOKEN"
```

3. אם 404:
```bash
# האם יש version קודם?
aws s3api list-object-versions \
  --bucket brikops-prod-files \
  --prefix "projects/XXX/task-photos/YYY.jpg"

# מחק את ה-delete marker לשחזור
aws s3api delete-object \
  --bucket brikops-prod-files \
  --key "..." \
  --version-id "<DeleteMarker_VersionId>"
```

4. אם 403:
   - IAM Task Role ב-ECS אולי איבד permissions
   - בדוק ECS → Task Definition → Task Role → policy על s3:GetObject

---

## שלב 2E — "האפליקציה לא מגיבה"

1. ECS Health:
```bash
aws ecs describe-services \
  --cluster brikops-prod \
  --services brikops-api \
  --query 'services[0].{desired:desiredCount,running:runningCount,events:events[0:3]}'
```

2. אם `running < desired` → tasks נופלים:
```bash
# ראה למה
aws ecs describe-tasks \
  --cluster brikops-prod \
  --tasks $(aws ecs list-tasks --cluster brikops-prod --service-name brikops-api --desired-status STOPPED --max-results 3 --query 'taskArns[]' --output text) \
  --query 'tasks[].{reason:stoppedReason,exitCode:containers[0].exitCode}'
```

3. תיקונים נפוצים:
   - **OOMKilled** → Task definition → Memory up (768→1536 MB)
   - **Container exited with non-zero code** → `aws logs tail /ecs/brikops-api` לפני ה-stop
   - **HealthCheck failed** → בדוק `/health` endpoint

4. Force redeploy (ECS equivalent של restart):
```bash
aws ecs update-service \
  --cluster brikops-prod \
  --service brikops-api \
  --force-new-deployment
# ECS יעלה task חדש → drain ישן → switch
```

5. Rollback (אחרי deploy רע):
```bash
# ראה revisions של task definition
aws ecs list-task-definitions --family-prefix brikops-api --sort DESC --max-items 5

# חזור ל-revision קודם
aws ecs update-service \
  --cluster brikops-prod \
  --service brikops-api \
  --task-definition brikops-api:<PREVIOUS_REVISION>
```

---

## שלב 3 — שחזור DB (Data Loss אמיתי)

### ⚠️ קרא הכל לפני שתעשה משהו

1. **קבע זמן המחיקה:**
   - שאל: "מתי פתחת אחרון פעם וראית את ה-data?"
   - audit_events:
     ```javascript
     db.audit_events.find({ org_id: "X" }).sort({ at: -1 }).limit(20)
     ```

2. **אל תשנה כלום ב-prod** — שמור על ה-state להשוואה.

3. **תגיד ללקוח:** "אני משחזר, אל תעבוד 20 דקות"

4. **PITR ל-new cluster:**
   - Atlas → Cluster → **...** → Backup → Point in Time Restore
   - Time: **דקה לפני** זמן המחיקה
   - Target: **NEW cluster** (שם: `brikops-emergency-<date>`)
   - Tier: identical to prod (חייב)
   - Region: eu-central-1

5. **המתן 15–40 דק'.** עדכן את הלקוח.

6. **Connect + חלץ data ספציפי:**
```bash
# mongosh לdry-run
mongosh "mongodb+srv://USER:PASS@brikops-emergency.XXX.mongodb.net/contractor_ops"
db.tasks.countDocuments({ project_id: "X" })

# mongodump של רק מה שצריך
mongodump \
  --uri "mongodb+srv://USER:PASS@brikops-emergency.XXX.mongodb.net/contractor_ops" \
  --collection tasks \
  --query '{"project_id": "X"}' \
  --out /tmp/emergency-restore/
```

7. **השווה מול prod:**
```bash
# כמה tasks ב-restore
mongosh "RESTORE_URI" --eval 'db.tasks.countDocuments({project_id:"X"})'
# כמה ב-prod
mongosh "PROD_URI" --eval 'db.tasks.countDocuments({project_id:"X"})'
```

8. **השלם ל-prod (merge חלקי):**
```bash
# mongorestore לא דורס existing — בטוח
mongorestore \
  --uri "PROD_URI" \
  --collection tasks \
  /tmp/emergency-restore/contractor_ops/tasks.bson
```

9. **אמת:** רענן BrikOps → ודא data חזר.

10. **מחק emergency cluster** (יקר!):
    ```bash
    # או דרך Console
    ```

11. **Post-mortem** (ראה טמפלט למטה).

---

## החלטות אסורות תחת לחץ

- ❌ למחוק data נוסף "לנקות"
- ❌ להריץ scripts ידניים ב-prod (עלול למחוק)
- ❌ rollback של deployment בלי להבין למה
- ❌ "זה אצלך, לא אצלנו" ללקוח (גם אם נכון — תחקור קודם)
- ❌ להבטיח זמן תיקון שאתה לא בטוח בו
- ❌ `db.collection.drop()` או `db.runCommand({ dropDatabase: 1 })` — אף פעם בפרוד

**תמיד:**
- ✅ 2 דק' לחשוב
- ✅ תעד בזמן שאתה עובד
- ✅ dry-run ב-test cluster קודם
- ✅ ETA מדויק ללקוח

---

## Post-Mortem Template

שמור ב-`/docs/incidents/YYYY-MM-DD-short-title.md`:

```markdown
# Post-Mortem: 2026-04-21 — Login broken for all users

## Timeline (UTC)
- 10:23 — Alert from StatusCake
- 10:25 — Zahi started diagnosis
- 10:28 — Identified: ECS service scaled to 0 accidentally
- 10:31 — Fixed: `aws ecs update-service --desired-count 2`
- 10:34 — Verified: /health returning 200

## Impact
- Users affected: ~45 (all logged-in sessions)
- Duration: 11 min
- Data loss: none

## Root Cause
Accidental click on "Stop Service" in AWS Console while exploring.

## Timeline to recovery
- Detection: 2 min
- Diagnosis: 3 min
- Fix: 3 min
- Verification: 3 min
- Total MTTR: 11 min

## Prevention
- [ ] IAM: remove ecs:UpdateService from dev user
- [ ] CloudWatch alert: alarm if runningCount < 1
- [ ] StatusCake: already in place (triggered correctly)

## Customer comms
Sent WhatsApp broadcast at 10:35 with apology + 3-sentence explanation.
```

---

## תקשורת ללקוח — טמפלטים

### ראשונה (5 דק' מהדיווח)
```
שלום [שם],
קיבלתי. אני בודק. חוזר אליך תוך 15 דק' עם עדכון.
```

### אמצע (אם > 15 דק')
```
שלום [שם],
בתיקון. [משפט אחד ללא טכניקה]. ETA: עוד [X] דק'.
```

### סיום
```
שלום [שם],
תוקן. [משפט אחד על מה היה + מה נעשה].
נא ודא שהכל עובד אצלך. אני חוקר למה זה קרה.
```

### Post-mortem (יום אחרי)
```
שלום [שם], הנה סיכום אתמול:
• מה קרה: [משפט]
• סיבה: [משפט]
• תיקון: [משפט]
• מניעה: [משפט]
תודה על הסבלנות.
```

---

## Metrics לשמירה

| מדד | ערך |
|---|---|
| Time to detect (דיווח→התחלת טיפול) | ___ דק' |
| Time to diagnose | ___ דק' |
| Time to fix (MTTR) | ___ דק' |
| User downtime | ___ דק' |
| Data loss (rows/files) | ___ |
| SLA breach? | כן/לא |

---

## מתי לקרוא לעזרה חיצונית

- אירוע > 30 דק' וקטיור לא מתקדם → **Atlas chat (24/7)** + **AWS Business Support**
- Data loss > שעה של עבודה → קרא לעוד זוג עיניים
- חשד לחדירת אבטחה → **עצור הכל**, rotate JWT_SECRET, בדוק audit_events
- Billing incident → הקפא billing webhook/cron מיד

---

## 🤖 הערה ל-AI Agent עתידי

ה-agent יכול להריץ לבד:
- **שלב 1 אבחון**: 100% אוטומטי — זה רק קריאת APIs
- **שלב 2A (OTP lockout)**: אוטומטי — DB update פשוט
- **שלב 2C (S3 restore)**: אוטומטי (עם confirmation)
- **שלב 2E (ECS redeploy)**: אוטומטי (עם confirmation)

דורש human-in-the-loop:
- **שלב 3 (PITR)** — בחירת time + target בעלי עלות גבוהה
- **כל תקשורת ללקוח** — ניסוח + timing
- **Post-mortem** — ניתוח סיבה שורש

**Webhooks ל-Agent:**
- CloudWatch Alarm → Agent → auto-diagnose → Slack notification ל-Zahi
- Agent מציע פעולה + מחכה ל-approval → מבצע
- אחרי: Agent כותב draft של post-mortem

**Guardrails חשובים לAgent:**
- לעולם לא להריץ `drop` / `deleteMany` בלי 2FA
- אף פעם לא לשנות JWT_SECRET בלי approval
- תמיד dry-run ב-test cluster לפני prod
