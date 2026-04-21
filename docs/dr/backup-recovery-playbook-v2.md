# BrikOps — Backup & Recovery Playbook v2 (Corrected)

**מטרה:** לוודא גיבוי + שחזור **לפני** שיש לקוחות אמיתיים.
**זמן:** 2–3 שעות לטסט המלא; 10 דקות ל-Pre-flight checks.
**מעודכן:** 2026-04-21 — מתוקן לפי הקוד האמיתי של BrikOps.

---

## 📋 תשתית אמיתית של BrikOps (לייחוס)

| רכיב | פרטים |
|---|---|
| **Frontend** | React 19 → Cloudflare Pages (`app.brikops.com`) |
| **Backend** | Python FastAPI → **AWS ECS** (לא Elastic Beanstalk!) — `api.brikops.com` |
| **Database** | MongoDB Atlas — **DB name: `contractor_ops`** |
| **Storage** | S3 — bucket `brikops-prod-files`, region `eu-central-1` |
| **IAM** | ECS Task Role (אין AWS_ACCESS_KEY ב-env) |
| **SMS** | Twilio |
| **WhatsApp** | Meta Cloud API |

### Collections עיקריים
`users`, `organizations`, `org_memberships`, `project_memberships`, `projects`, `tasks`, `task_updates`, `handover_protocols`, `qc_inspections`, `project_plans`, `project_companies`, `companies`, `counters`, `audit_events`, `otp_codes`, `otp_metrics`, `sms_events`.

### שדות קריטיים לזכור
- **משתמש**: `id`, `phone_e164`, `user_status` (`active`/`pending_deletion`/`deleted`)
- **מחיקה** (על user, לא על org!): `user_status`, `deletion_requested_at`, `deletion_scheduled_for`, `deletion_type` (`account_only` / `full_purge`), `deletion_org_id` (רק ב-full_purge)
- **OTP lockout** (ב-`otp_codes`, לא `users`!): `phone`, `attempts`, `locked_until`, `hashed_code`

---

## 🛫 Pre-flight Checks (חובה — 10 דקות)

בלי אלה, חצי מהטסטים ייכשלו כי ה-assumptions שגויים.

### Check 1 — Atlas Tier תומך ב-PITR?

PITR (Point-in-Time Recovery) דורש tier M10 ומעלה. M0/M2/M5 **לא תומכים**.

**פעולה:** MongoDB Atlas → Cluster overview → תבדוק את ה-tier.

```
מצב: _______ (M0/M2/M5/M10/M20/...)
תומך ב-PITR: כן/לא
```

אם M0 — **עצור את הטסט**. צריך לשדרג ל-M10 לפני שיש לקוחות (~$57/mo). אין PITR = אין שחזור גרעיני ב-bug scenario.

### Check 2 — S3 Versioning ON?

בלי versioning, מחיקת קובץ = אובדן סופי. המסמך הישן הניח שזה ON; צריך לאמת.

**פעולה:** AWS Console → S3 → `brikops-prod-files` → Properties → "Bucket Versioning".

```
Versioning: Enabled / Suspended / Disabled
```

אם לא Enabled → **הפעל עכשיו** (Edit → Enable → Save). **זה לא משחזר קבצים שכבר נמחקו** — רק מגן מעתה.

### Check 3 — Backend ECS Service Accessible?

```bash
# מה-Mac Terminal שלך (AWS CLI מותקן?)
aws ecs list-services --cluster brikops-prod
# או אם שם אחר — נבדוק ביחד
aws ecs list-clusters
```

```
Cluster name: _______
Service name: _______
Running tasks: ___
```

אם אין AWS CLI מוגדר — תגיד לי וננסה דרך Console.

### Check 4 — יש snapshot יומי אחרון (פחות מ-24 שעות)?

Atlas → Cluster → **...** → Backup → Snapshots tab.

```
Snapshot אחרון: _______ (תאריך+שעה)
Retention: ___ ימים (צריך להיות לפחות 7)
Cross-region backup: כן / לא
```

אם `last snapshot > 24h ago` → יש תקלה במנגנון הגיבוי. נחקור לפני שממשיכים.

---

## 🧪 הטסטים עצמם

⚠️ **אל תעשה את הטסטים האלה עד שכל 4 ה-Pre-flight checks עברו.**

### הכנות

```
תאריך בדיקה: _______________
פרויקט טסט (project_id): _______________
org_id: _______________
user_id (משתמש טסט עם טלפון שלך): _______________
```

מצב התחלתי (תעד את המספרים האלה — הם ה-baseline):
```bash
# ב-mongosh או Compass
db.tasks.countDocuments({ project_id: "YOUR_PROJECT_ID" })
db.task_updates.countDocuments({ project_id: "YOUR_PROJECT_ID" })
db.handover_protocols.countDocuments({ project_id: "YOUR_PROJECT_ID" })
# S3: ספור objects בbucket בparker של הפרויקט
aws s3 ls s3://brikops-prod-files/projects/YOUR_PROJECT_ID/ --recursive --summarize
```

---

### תרחיש 1 — DB Point-in-Time Restore (30 דק')

**מטרה:** אם מישהו מחק data בטעות — להוכיח שאנחנו יכולים להחזיר אותו בלי rollback של כל ה-DB.

#### שלב 1.1 — רשום state לפני
רשום בדיוק את הזמן + 3 task IDs שאתה הולך למחוק:
```
זמן לפני מחיקה (UTC): _______________
task_id 1: _______________
task_id 2: _______________
task_id 3: _______________
```

#### שלב 1.2 — בצע מחיקה מדומה ב-prod
Atlas → Browse Collections → `contractor_ops.tasks` → Filter: `{ project_id: "YOUR_PROJECT_ID" }`
→ בחר 3 tasks → Delete.

```
זמן מחיקה (UTC): _______________
```

רענן את BrikOps → ודא שהליקויים נעלמו מהמסך.

#### שלב 1.3 — PITR restore ל-cluster חדש
Atlas → Cluster → **...** → Backup → **Point in Time Restore**:
- Time: **דקה לפני** זמן המחיקה
- Target: **Restore to new cluster** (לא same!)
- Cluster name: `brikops-pitr-test`
- Tier: אותו tier כמו production (אחרת לא יתקבל)
- Region: eu-central-1

**זה לוקח 15–40 דקות.** אל תעזוב את הדף.

#### שלב 1.4 — אמת שהdata קיים ב-restore
```bash
# mongosh לחדש
mongosh "mongodb+srv://USER:PASS@brikops-pitr-test.XXX.mongodb.net/contractor_ops"

# ודא שהtasks הנמחקים קיימים
db.tasks.find({ id: { $in: ["task_id_1", "task_id_2", "task_id_3"] } }).count()
# אמור להחזיר 3
```

#### שלב 1.5 — יצא לקובץ
```bash
mongodump \
  --uri "mongodb+srv://USER:PASS@brikops-pitr-test.XXX.mongodb.net/contractor_ops" \
  --collection tasks \
  --query '{"id": {"$in": ["task_id_1","task_id_2","task_id_3"]}}' \
  --out /tmp/pitr-restore/

# תיווצר: /tmp/pitr-restore/contractor_ops/tasks.bson + metadata.json
```

#### שלב 1.6 — החזר ל-prod (רק את ה-3 שחסרים)
```bash
mongorestore \
  --uri "mongodb+srv://USER:PASS@prod.XXX.mongodb.net/contractor_ops" \
  --collection tasks \
  /tmp/pitr-restore/contractor_ops/tasks.bson
```

`mongorestore` כברירת מחדל לא דורס existing documents. אם יש ID clash — הוא ידלג. זה בטוח.

#### שלב 1.7 — ודא ב-UI
רענן את BrikOps → ודא ש-3 הליקויים חזרו.

#### שלב 1.8 — מחק cluster (יקר!)
Atlas → `brikops-pitr-test` → **...** → Terminate.

**תיעוד:**
```
✅/❌ tasks נמצאו ב-restore cluster
זמן שחזור (מלחיצה ועד cluster מוכן): ___ דק'
זמן restore-to-prod: ___ דק'
אובדן data: כן / לא
RPO אמיתי: ___ שניות
RTO אמיתי: ___ דקות
```

---

### תרחיש 2 — S3 Version Restore (15 דק')

**רק אם Pre-flight Check 2 עבר!**

#### שלב 2.1 — בחר תמונה
פתח BrikOps → ליקוי עם תמונה → Inspect Element → העתק URL של התמונה.
```
S3 key: _______________
```

#### שלב 2.2 — מחק מ-S3
```bash
aws s3api delete-object \
  --bucket brikops-prod-files \
  --key "projects/XXX/task-photos/YYY.jpg"
# S3 יחזיר VersionId של ה-delete marker
```

רענן ליקוי ב-BrikOps → תמונה שבורה.

#### שלב 2.3 — מצא את ה-delete marker
```bash
aws s3api list-object-versions \
  --bucket brikops-prod-files \
  --prefix "projects/XXX/task-photos/YYY.jpg"
# ראה IsLatest=true ל-DeleteMarker, ו-previous version של הקובץ
```

#### שלב 2.4 — שחזר (מחיקת delete marker)
```bash
aws s3api delete-object \
  --bucket brikops-prod-files \
  --key "projects/XXX/task-photos/YYY.jpg" \
  --version-id "<VersionId of delete marker>"
```

#### שלב 2.5 — ודא ב-UI
רענן ליקוי → תמונה חזרה.

**תיעוד:**
```
✅/❌ תמונה חזרה
זמן שחזור: ___ שניות
```

---

### תרחיש 3 — Account Deletion + Grace (15 דק')

⚠️ התיקון הגדול מהמסמך הישן: **ה-flag נמצא על ה-user, לא ה-org.**

#### שלב 3.1 — צור משתמש טסט חדש
עדיף משתמש עם טלפון שלך (מספר משני). **אל תשתמש ב-owner/super_admin!**

#### שלב 3.2 — בקש account deletion
BrikOps → Settings → מחק חשבון → בחר `account_only` (לא `full_purge`).

#### שלב 3.3 — אמת את הדגל על ה-user (לא org!)
```bash
db.users.findOne(
  { id: "TEST_USER_ID" },
  { id:1, user_status:1, deletion_requested_at:1, deletion_scheduled_for:1, deletion_type:1 }
)
```

ציפייה:
```json
{
  "user_status": "pending_deletion",
  "deletion_type": "account_only",
  "deletion_requested_at": "2026-04-21T10:00:00Z",
  "deletion_scheduled_for": "2026-04-28T10:00:00Z"  // +7 ימים
}
```

#### שלב 3.4 — בדוק gated access
התחבר שוב → אמור לראות מסך "החשבון מסומן למחיקה". נסה לגשת ל-`/projects` — אמור לחסום (דרך `get_current_user_allow_pending_deletion` בsrc).

#### שלב 3.5 — בטל מחיקה
BrikOps → "בטל מחיקה" → רענן.
```bash
db.users.findOne({ id: "TEST_USER_ID" }, { user_status:1, deletion_scheduled_for:1 })
# ציפייה: user_status: 'active', deletion_scheduled_for: ''
```

#### שלב 3.6 — בצע מחיקה סופית (ידני, כי אין cron!)
**תיקון קריטי:** **אין** `account_deletion_cron` בקוד. המחיקה מתבצעת דרך super-admin endpoint ב-deletion_router.py (חפש `_anonymize_user_db` סביב שורה 412).

כדי לבדוק את המחיקה בפועל:
1. בקש שוב מחיקה
2. קצר את ה-grace ל-DB:
   ```bash
   db.users.updateOne(
     { id: "TEST_USER_ID" },
     { $set: { deletion_scheduled_for: "2026-04-20T00:00:00Z" } }  # תאריך בעבר
   )
   ```
3. היכנס ל-super-admin → endpoint שמעבד את pending deletions (ראה שורה 786–800 ב-`deletion_router.py` — `GET /api/admin/pending-deletions` + POST להרצת ה-anonymize)

#### שלב 3.7 — ודא anonymize
```bash
db.users.findOne({ id: "TEST_USER_ID" })
# ציפייה: phone_e164 = null/masked, name מוחלף, user_status = 'deleted'
```

**תיעוד:**
```
✅/❌ pending_deletion על user (לא org)
✅/❌ ביטול החזיר ל-active
✅/❌ anonymize עבד אחרי grace
```

---

### תרחיש 4 — Daily Snapshots (20 דק')

כמו במקור — Atlas → Backup → Snapshots.
```
מספר snapshots זמינים: ___
הכי ישן: _______________
הכי חדש: _______________
Cross-region copy (Ireland/other): כן / לא
Retention (Daily/Weekly/Monthly): ______
```

אם `cross-region = לא` → **זה risk**. אירוע אזורי ב-eu-central-1 = אין fallback. שווה להפעיל.

---

### תרחיש 5 — Backend Failure (ECS, לא EB!)

⚠️ **תיקון:** הפקודות במסמך הישן היו ל-Elastic Beanstalk. הנה המקבילה ל-ECS:

#### שלב 5.1 — בדוק health
```bash
aws ecs describe-services \
  --cluster brikops-prod \
  --services brikops-api \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'
```

#### שלב 5.2 — סמלץ failure (stop task)
```bash
# רשום את task ARN
aws ecs list-tasks --cluster brikops-prod --service-name brikops-api

# עצור task אחד
aws ecs stop-task \
  --cluster brikops-prod \
  --task <task-arn> \
  --reason "DR test"
```

#### שלב 5.3 — ECS יעלה task חדש תוך 30-60 שניות
```bash
# עקוב
watch -n 5 'aws ecs describe-services --cluster brikops-prod --services brikops-api --query "services[0].{desired:desiredCount,running:runningCount}"'
```

#### שלב 5.4 — ודא שהאפליקציה עובדת
```bash
curl -s https://api.brikops.com/health
# או endpoint דומה
```

**תיעוד:**
```
✅/❌ ECS החליף task אוטומטית
Downtime (אם desiredCount=1): ___ שניות
Downtime (אם desiredCount≥2): אמור להיות 0
```

**המלצה:** אם `desiredCount=1` — שדרג ל-2 instances לפני לקוחות. עולה 2x, אבל zero-downtime deploys + auto-failover.

---

### תרחיש 6 — MongoDB Failover (10 דק')

כמו במקור — Atlas → Cluster → **...** → **Test Failover**.

**תיעוד:**
```
✅/❌ Failover עבד
הפרעה: ___ שניות
Backend auto-reconnect: כן / לא
```

אם היו errors ב-backend במהלך ה-failover → motor driver configuration בעייתי. בדוק `retryWrites=true` ב-connection string.

---

## 📊 סיכום + KPIs

| תרחיש | עבר? | זמן | הערות |
|---|---|---|---|
| Pre-flight 1 — Atlas tier | | | |
| Pre-flight 2 — S3 Versioning | | | |
| Pre-flight 3 — ECS access | | | |
| Pre-flight 4 — Daily snapshot | | | |
| 1 — DB PITR | | | |
| 2 — S3 Restore | | | |
| 3 — Deletion grace | | | |
| 4 — Daily snapshots | | | |
| 5 — Backend failure | | | |
| 6 — MongoDB failover | | | |

### RPO / RTO אמיתי (אחרי הטסט)
```
RPO (אובדן data מקסימלי): _______ (PITR מאפשר ~1 דק')
RTO (זמן התאוששות): _______ (משך מה-trigger ועד הכל עובד)
```

---

## 🤖 הערה ל-AI Agent עתידי

כל ה-playbook הזה אוטומטי בחלק גדול ממנו. Agent יכול:
- **Pre-flight checks 1–4**: לקרוא את ה-API של Atlas + AWS CLI
- **תרחיש 2 (S3)**: 100% אוטומטי עם boto3
- **תרחיש 5 (ECS)**: 100% אוטומטי עם boto3
- **תרחיש 6 (Failover)**: אוטומטי עם Atlas API

**לא אוטומטי (דורש שיקול דעת):**
- תרחיש 1 (PITR) — הבחירה מתי + איזה data להחזיר
- תרחיש 3 (deletion) — רגיש לנתוני משתמש

**Endpoints שצריך לבנות לAgent:**
- `GET /admin/backup-health` — החזר: latest_snapshot_ts, atlas_tier, s3_versioning_enabled, ecs_task_count
- `POST /admin/dr-test/s3-restore` — מחק+שחזר קובץ דמה
- `POST /admin/dr-test/ecs-restart` — stop+verify

**Monitoring מומלץ (אחרי שה-playbook עובר):**
- Alert אם `snapshot_age > 26h`
- Alert אם `s3_versioning ≠ Enabled`
- Alert אם `ecs_running_count < desired_count`
- Alert אם `mongodb_primary_elections > 0` ב-24h
