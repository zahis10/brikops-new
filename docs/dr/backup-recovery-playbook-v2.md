# BrikOps — Backup & Recovery Playbook v2 (Corrected)

**מטרה:** לוודא גיבוי + שחזור **לפני** שיש לקוחות אמיתיים.
**זמן:** 2–3 שעות לטסט המלא; 10 דקות ל-Pre-flight checks.
**מעודכן:** 2026-04-21 — מתוקן פעמיים:
- פעם ראשונה: לפי ניתוח קוד (תיקן טעויות של המסמך הראשון).
- פעם שנייה (זו): לפי ממצאי pre-flight אמיתי ב-Console — תוקנה טעות קריטית: ה-backend רץ על **Elastic Beanstalk** (Docker), לא ECS. כל הפקודות בתרחיש 5 עודכנו.

---

## 📋 תשתית אמיתית של BrikOps (לייחוס)

| רכיב | פרטים |
|---|---|
| **Frontend** | React 19 → Cloudflare Pages (`app.brikops.com`) |
| **Backend** | Python FastAPI → **AWS Elastic Beanstalk** (Docker platform) — `api.brikops.com`<br>App: `brikops-api`, Env: `Brikops-api-env`<br>Deploy: GitHub Actions (paths `backend/**`, `.platform/**`)<br>Artifact bucket: `elasticbeanstalk-eu-central-1-457550570829` |
| **Database** | MongoDB Atlas — cluster `brikops-eu`, tier M10, MongoDB 8.0.20<br>**DB name: `contractor_ops`** |
| **Backups** | Atlas Continuous Cloud Backup: snapshots every 6h/daily/weekly/monthly/yearly<br>Cross-region copy → eu-west-1 (Ireland), 1-day retention (⚠ recommend raising to 7)<br>PITR: enabled (M10+) |
| **Storage** | S3 — bucket `brikops-prod-files`, region `eu-central-1`<br>Bucket Versioning: **Enabled**<br>Prefix structure (FLAT, not project-scoped): `qc/`, `attachments/`, `exports/{org}/`, `signatures/{user}/`, `billing-receipts/{user}/` |
| **IAM** | EB EC2 Instance Profile (אין AWS_ACCESS_KEY ב-env) |
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

### Check 3 — Backend Elastic Beanstalk Environment Accessible?

```bash
aws elasticbeanstalk describe-environments --region eu-central-1
# מציג את כל ה-environments + Health + InstancesHealth
```

**Values אמיתיים (מאומת 2026-04-21):**
```
Application name:   brikops-api
Environment name:   Brikops-api-env        ← שים לב: B גדולה בהתחלה
Platform:           Docker
Region:             eu-central-1 (Frankfurt)
Health:             Ok
```

אם אין AWS CLI מוגדר — Console: **Elastic Beanstalk → Environments** (region: Frankfurt).

### Check 4 — יש snapshot יומי אחרון (פחות מ-24 שעות)?

Atlas → Cluster `brikops-eu` → **...** → Backup → Snapshots tab.

**Values אמיתיים (מאומת 2026-04-21):**
```
Snapshot אחרון: < 24h ✅ (Continuous Cloud Backup)
Policy: hourly (=every 6h) / daily / weekly / monthly / yearly — כולם פעילים
Cross-region copy: eu-west-1 (Ireland) ✅ (retention: 1 day — מומלץ להעלות ל-7)
```

**הערה על שמות ב-Atlas UI:** מה ש-Atlas קורא לו "hourly" זה בפועל **אחת לשש שעות**, לא כל שעה. אם בתרחיש 1 אתה צריך PITR מתחת לרזולוציה הזו — זה עדיין אפשרי כי PITR עובד מה-oplog (רזולוציה של שניות), לא מה-snapshots.

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

# S3: הכי חשוב — *אין* תיקיית פרויקט ב-S3! המבנה שטוח:
# לכן כדי לספור את ה-objects של פרויקט ספציפי, צריך קודם כל לשלוף את ה-keys מ-DB:
db.task_updates.distinct("photo_url", { project_id: "YOUR_PROJECT_ID" })
db.qc_inspections.aggregate([
  { $match: { project_id: "YOUR_PROJECT_ID" } },
  { $unwind: "$photos" },
  { $project: { url: "$photos.url" } }
])
# ואז לוודא שכל URL באמת קיים ב-S3 (sample אקראי של 5-10).
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
פתח BrikOps → ליקוי עם תמונה → Inspect Element (או בקונסולת הנייד) → העתק URL של התמונה.

**הערה על המבנה האמיתי:** ה-S3 key יהיה משהו כמו:
- `qc/<uuid>.jpg` (תמונות של QC inspections)
- `attachments/<uuid>.jpg` (תמונות של ליקויים ב-task_updates)
- `signatures/<user_id>/<uuid>.png` (חתימות)

```
S3 key אמיתי: _______________ (לדוגמה: attachments/abc123-def456.jpg)
```

#### שלב 2.2 — מחק מ-S3
```bash
aws s3api delete-object \
  --bucket brikops-prod-files \
  --key "attachments/abc123-def456.jpg"      # השתמש ב-key האמיתי
# S3 יחזיר VersionId של ה-delete marker
```

רענן ליקוי ב-BrikOps → תמונה שבורה.

#### שלב 2.3 — מצא את ה-delete marker
```bash
aws s3api list-object-versions \
  --bucket brikops-prod-files \
  --prefix "attachments/abc123-def456.jpg"
# ראה IsLatest=true ל-DeleteMarker, ו-previous version של הקובץ
```

#### שלב 2.4 — שחזר (מחיקת delete marker)
```bash
aws s3api delete-object \
  --bucket brikops-prod-files \
  --key "attachments/abc123-def456.jpg" \
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

### תרחיש 5 — Backend Failure (Elastic Beanstalk)

⚠️ **תיקון כפול:** המסמך הראשון (v1) כתב EB. v2 שינה בטעות ל-ECS. **האמת: EB.** (ראה Pre-flight 3.)

כל הפקודות כאן משתמשות בשם הסביבה האמיתי: `Brikops-api-env` (B גדולה) ו-application name `brikops-api`.

#### שלב 5.1 — בדוק health של ה-environment
```bash
aws elasticbeanstalk describe-environment-health \
  --environment-name Brikops-api-env \
  --attribute-names All \
  --region eu-central-1 \
  --query '{Status:Status,Health:HealthStatus,Instances:InstancesHealth}'
```

רשום את מספר ה-instances הנוכחי (ברוב המקרים 1):
```
Instances: ___
Health: ___ (Ok / Warning / Degraded / Severe)
```

#### שלב 5.2 — סמלץ failure — Restart של ה-App Server
זו הדרך הבטוחה: EB עוצר את הקונטיינר ומפעיל מחדש על אותה EC2. ה-backend יורד, ואז חוזר.

```bash
aws elasticbeanstalk restart-app-server \
  --environment-name Brikops-api-env \
  --region eu-central-1
# הפקודה חוזרת מיד. ה-restart עצמו לוקח 30-90 שניות.
```

התחל לתזמן מיד. במקביל, פתח בטרמינל נוסף:
```bash
# poll את /health כל שנייה כדי למדוד downtime מדויק
while true; do
  ts=$(date +%H:%M:%S)
  code=$(curl -s -o /dev/null -w "%{http_code}" https://api.brikops.com/health)
  echo "$ts  $code"
  sleep 1
done
```

#### שלב 5.3 — מדוד downtime
הזרם של ה-`while` יחזיר `200`, ואז יתחיל להחזיר `502` או `503` או timeout, ואז יחזור ל-`200`. הפרש הזמנים בין ה-200 האחרון ל-200 הבא = ה-downtime.

```
Downtime (seconds): ___
```

#### שלב 5.4 — ודא שה-environment חזר ל-Ok
```bash
aws elasticbeanstalk describe-environment-health \
  --environment-name Brikops-api-env \
  --attribute-names HealthStatus,Status \
  --region eu-central-1
```

```
Status: Ready / Updating / ...
HealthStatus: Ok / ...
```

#### שלב 5.5 — (אופציונלי) סימולציה חמורה יותר — Terminate EC2 instance
זה מדמה crash של ה-VM (לא רק של ה-app). EB auto-scaling אמור להקפיץ instance חדש.

```bash
# מצא את ה-instance ID
aws elasticbeanstalk describe-environment-resources \
  --environment-name Brikops-api-env \
  --region eu-central-1 \
  --query 'EnvironmentResources.Instances[0].Id'

# Terminate אותו
aws ec2 terminate-instances --instance-ids i-XXXXX --region eu-central-1
```

**הזהרה:** אם `Instances=1`, ה-downtime כאן יהיה 3-8 דקות (auto-scaling + boot + Docker pull + health check). אל תעשה את זה על prod אחרי שיש משתמשים אמיתיים — רק בטסט.

**תיעוד:**
```
✅/❌ EB הפעיל מחדש את ה-app server
Downtime (restart-app-server): ___ שניות   (צפוי: 30-90)
Downtime (terminate EC2): ___ שניות        (צפוי: 180-480)
חזר ל-Health=Ok: ___ דקות אחרי ה-trigger
```

**המלצה מבצעית:** אם יש רק instance אחד — **כל deploy = downtime של ~30 שניות**. לפני שיש לקוחות רציניים, שדרג ל-2 instances + Application Load Balancer ב-EB config. עלות ~+$15/mo, תמורת zero-downtime deploys + auto-failover של EC2.

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
| Pre-flight 1 — Atlas tier | ✅ | 2026-04-21 | M10, PITR זמין |
| Pre-flight 2 — S3 Versioning | ✅ | 2026-04-21 | Enabled על `brikops-prod-files` |
| Pre-flight 3 — EB env access | ✅ | 2026-04-21 | `Brikops-api-env`, Docker, Health=Ok |
| Pre-flight 4 — Daily snapshot | ✅ | 2026-04-21 | < 24h, cross-region ל-Ireland |
| 1 — DB PITR | | | |
| 2 — S3 Restore | | | |
| 3 — Deletion grace | | | |
| 4 — Daily snapshots | | | |
| 5 — Backend failure (EB) | | | |
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
- **תרחיש 2 (S3)**: 100% אוטומטי עם boto3 (`s3.delete_object` + `s3.list_object_versions` + `s3.delete_object(VersionId=...)`)
- **תרחיש 5 (EB)**: 100% אוטומטי עם boto3 (`elasticbeanstalk.restart_app_server`) — פחות הרסני מ-stop_task ב-ECS
- **תרחיש 6 (Failover)**: אוטומטי עם Atlas API

**לא אוטומטי (דורש שיקול דעת):**
- תרחיש 1 (PITR) — הבחירה מתי + איזה data להחזיר
- תרחיש 3 (deletion) — רגיש לנתוני משתמש

**Endpoints שצריך לבנות לAgent:**
- `GET /admin/backup-health` — החזר: `latest_snapshot_ts`, `atlas_tier`, `s3_versioning_enabled`, `eb_env_health`, `eb_instance_count`, `cross_region_retention_days`
- `POST /admin/dr-test/s3-restore` — מחק+שחזר קובץ דמה
- `POST /admin/dr-test/eb-restart` — restart EB env + verify /health
- `POST /admin/deletion/tick` — **ה-cron החסר**: ירוץ על `users` ל-`user_status='pending_deletion' AND deletion_scheduled_for <= now`, יקרא `_anonymize_user_db`

**Monitoring מומלץ (אחרי שה-playbook עובר):**
- Alert אם `snapshot_age > 26h`
- Alert אם `s3_versioning ≠ Enabled`
- Alert אם `eb_env_health ≠ Ok` למשך > 5 דקות
- Alert אם `eb_instance_count < desired`
- Alert אם `mongodb_primary_elections > 0` ב-24h
- Alert אם יש user עם `user_status='pending_deletion' AND deletion_scheduled_for < now - 1day` (סימן שה-tick endpoint לא רץ)
