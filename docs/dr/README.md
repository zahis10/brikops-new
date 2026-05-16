# 📘 תיקיית DR — מדריך פשוט

**מה זה DR?** Disaster Recovery — מה עושים כשמחק משהו בטעות / נעלמו נתונים / הפרודקשן נפל.

**למי זה נועד?** לי (זהי), מתישהו בעתיד בלחץ, שלא זוכר כלום ממה שעשינו.

---

## 📂 מה יש בתיקייה הזו

| קובץ | למה הוא משמש | מתי לפתוח אותו |
|---|---|---|
| **README.md** (זה) | סקירה כללית בעברית פשוטה | **תמיד קודם** |
| `backup-recovery-CONTEXT.md` | הסטטוס הנוכחי — מה נבדק, מה עבר, מה תקוע | אחרי README, כדי לדעת איפה אנחנו |
| `backup-recovery-playbook-v2.md` | ה-smoke test — 6 תרחישי בדיקה שאני עובר לפני שיש לקוחות | לפני כל סיבוב בדיקות |
| `emergency-runbook-v2.md` | ספר הפעולה כשיש **אסון אמיתי** בפרודקשן | רק באסון |
| `restore-toolkit.md` | 🆕 מסמך טכני — איך מוצאים מה נמחק + איך משחזרים בכמויות | רק כשצריך לשחזר נתונים |
| `bulk-restore.sh` | 🆕 סקריפט bash שמשחזר הרבה מסמכים במכה אחת (MongoDB) | רק בשחזור של 10+ פריטים מה-DB |
| `s3-bulk-restore.sh` | 🆕 סקריפט bash שמוחק delete markers בכמויות (S3) | רק בשחזור של 10+ קבצים מ-S3 |

---

## 🌍 Cross-Region Replication (CRR) — הגיבוי האוטומטי ל-Ireland

**הוקם:** 2026-04-22 | **סטטוס:** ✅ LIVE

### מה זה בפשטות

יש לך **שני bucket-ים זהים** שרצים במקביל:

```
📦 Frankfurt  (הראשי — פה האפליקציה עובדת)
   brikops-prod-files
   └── כל הקבצים של המשתמשים

📦 Ireland    (הגיבוי — יושב בצד, לא נגיש לאפליקציה)
   brikops-prod-files-backup-ireland
   └── עותק אוטומטי של כל קובץ מ-Frankfurt
```

### מתי הגיבוי נכנס לפעולה? **אוטומטית, תוך שניות.**

אתה לא צריך לעשות כלום ידני יותר. זה רץ ברקע, לנצח.

**הזרימה כשמשתמש מעלה תמונה:**
```
1. משתמש מצלם ליקוי בשטח → מעלה באפליקציה
         ↓
2. האפליקציה שולחת ל-S3 Frankfurt
         ↓
3. S3 שומר את הקובץ ב-Frankfurt ✅
         ↓
4. ⚡ AWS מזהה: "קובץ חדש + כלל replication פעיל"
         ↓
5. AWS מעתיק אוטומטית ל-Ireland (תוך 15-60 שניות)
         ↓
6. הקובץ יושב בשני רגיונות — מוגן
```

### מה קורה אם משתמש **מוחק** קובץ?

זה החלק המעניין שהגדרנו לטובתנו במיוחד:

```
Frankfurt:  🗑️ משתמש מוחק תמונה  →  Delete marker מופיע
                                      (הקובץ הישן נשאר ב-Versions — כמו בתרחיש 2)

Ireland:    🛡️ הקובץ נשאר במקום, לא מושפע!
            (כי הגדרנו "Delete marker replication: OFF")
```

**למה זה חשוב?** אם מחר יש אירוע אבטחה — האקר פורץ, עובד ממורמר, באג שמוחק הכל — **Ireland שומרת עליך**. אפילו אם כל Frankfurt נמחק, ב-Ireland הכל קיים.

### שימוש בגיבוי — 3 תרחישים

**מצב 1 — קובץ בודד נמחק בטעות:**
→ לא נוגעים ב-Ireland. פותחים Show versions ב-Frankfurt, מוחקים את ה-Delete marker. (מה שעשינו בתרחיש 2 — מצב 4 למטה)

**מצב 2 — מחקו 100 קבצים במכה:**
→ לא נוגעים ב-Ireland. מריצים `./s3-bulk-restore.sh` שבנינו.

**מצב 3 — כל Frankfurt נהרס / לא זמין (region outage, אסון גדול):**
→ מפעילים את Ireland:
1. משנים ב-env vars של Replit: `AWS_BUCKET` ו-`AWS_REGION` ל-Ireland
2. deploy מחדש
3. האפליקציה ממשיכה לעבוד תוך דקות
→ זה **Failover Region** — גיבוי אמיתי.

### פרמטרים חשובים

| פריט | ערך |
|---|---|
| **Source** | `brikops-prod-files` (eu-central-1, Frankfurt) |
| **Destination** | `brikops-prod-files-backup-ireland` (eu-west-1, Ireland) |
| **Replication rule name** | `brikops-prod-files-backup-ireland` |
| **Storage class ביעד** | `Standard-IA` (~45% זול יותר) |
| **Delete marker replication** | **OFF** (הגנה מפני מחיקה מכוונת) |
| **KMS encryption** | לא פעיל |
| **IAM role** | נוצר אוטומטית ע"י AWS |
| **השהיה טיפוסית** | 15-60 שניות |
| **השהיה במקרה קיצון** | עד 15 דקות |
| **עלות** | ~$0.02 ל-GB שנכתב + אחסון Standard-IA ב-Ireland |

### הקמה ראשונית (2026-04-22) — מה עשינו

**שלב 1 — יצירת bucket יעד:** `brikops-prod-files-backup-ireland` ב-region **eu-west-1 (Ireland)**, Versioning מופעל.

**שלב 2 — Replication rule:** ב-source bucket → Management → Replication rules → Create. הגדרות: Apply to all objects, Destination = הbucket החדש, IAM = Create new, KMS = off, Storage class = Standard-IA, Delete marker replication = OFF.

**שלב 3 — Batch Operations למילוי היסטורי:** CRR משכפל רק uploads חדשים מרגע ההפעלה. לקבצים הישנים (727 קבצים שהיו לפני) → Create Batch Operations job with Replicate operation. ה-job רץ ~5 דקות, שכפל 727/727 עם 0 כשלים.

**הוכחה לעבודה:** Ireland bucket מכיל עכשיו את אותם prefixes — `attachments/`, `qc/`, `signatures/`, `exports/`, `billing-receipts/`, `handover/`, `org_logos/`, `public/` — עם 727 קבצים.

### תחזוקה שוטפת

**מה צריך לעשות שוטף?** שום דבר. רץ לבד.

**פעם ב-3 חודשים:** להיכנס ל-S3 Ireland ולראות שהספירה עולה בקצב דומה ל-Frankfurt (וידוא שה-replication עוד חי).

**אם מוסיפים bucket חדש בעתיד:** צריך להגדיר replication rule משלו. זה לא מועבר אוטומטית.

---

## 🎯 4 מצבים שעלולים לקרות לי במציאות

### מצב 1 — "מחקתי לעצמי משהו בטעות ואני יודע בדיוק מה"

דוגמה: מחקתי 3 ליקויים לפני שעה, זה היה בטעות, אני זוכר את ה-titles שלהם.

**מה לעשות (פשוט, 25 דקות):**

1. **Atlas → `brikops-eu` → Backup → Point in Time Restore**
   - בחר זמן **דקה לפני** שמחקת
   - Target: Restore to new cluster → שם: `brikops-pitr-test`, tier M10
   - לחץ Restore ← ממתינים ~3 דקות

2. **אחרי שה-cluster החדש מוכן** — פותחים **Data Explorer** שלו
   - מחפשים את המסמכים לפי title או date
   - לוחצים **Clone Document** → חלון נפתח עם ה-JSON → מעתיקים (Cmd+C) → **Cancel** (חשוב — לא ליצור clone בפועל)

3. **Data Explorer של `brikops-eu`** (הפרודקשן)
   - אותו collection → **Insert Document** → מדביקים → Insert

4. **מוחקים את `brikops-pitr-test`** (אחרת ממשיכים לשלם)

**זה מה שעשינו היום בתרחיש 1.** עבד מצוין, לקח 25 דקות.

---

### מצב 2 — "משתמש מתלונן שנעלמו לו המון דברים, אני לא יודע מה בדיוק"

דוגמה: קבלן מתקשר — "כל 50 הליקויים שהזנתי אתמול בקומה 5 נעלמו!"

**הבעיה:** אתה לא יודע את ה-IDs של ה-50 הנעלמים. אי אפשר פשוט לחפש ולהעתיק אחד-אחד.

**מה לעשות (שיטה בשתי שלבים, ~15 דקות):**

#### שלב א' — מוצאים מה נמחק בעזרת "diff"

הרעיון: אחרי PITR ל-cluster זמני, יש לך 2 cluster-ים:
- **`brikops-eu` (prod)**: 58 ליקויים בקומה 5 (מה שנשאר)
- **`brikops-pitr-test`**: 108 ליקויים בקומה 5 (איך שזה היה אתמול)

ההבדל ביניהם = 50 הנעלמים.

הפקודות נמצאות ב-`restore-toolkit.md` תחת **"שיטה 1 — Diff בין temp cluster ל-prod"**. בגדול:

```bash
# שלוף IDs מ-prod
mongosh prod_uri --eval "db.tasks.find({project_id:'X', floor_id:'5'}, {id:1}).toArray()..." > prod.txt

# שלוף IDs מ-temp
mongosh temp_uri --eval "db.tasks.find({project_id:'X', floor_id:'5'}, {id:1}).toArray()..." > temp.txt

# מצא את ההפרש
comm -23 <(sort temp.txt) <(sort prod.txt) > missing.txt
```

עכשיו ב-`missing.txt` יש את כל 50 ה-IDs שנמחקו.

#### שלב ב' — משחזרים את כולם במכה אחת

פותחים את הקובץ `bulk-restore.sh`, עורכים את המשתנים בראש שלו:
- connection string של ה-cluster הזמני (`SRC_URI`)
- connection string של הפרודקשן (`DST_URI`)
- ה-50 IDs מ-`missing.txt` (מעתיקים כ-JSON array)

מריצים:
```bash
./bulk-restore.sh
```

הסקריפט יעשה הכל לבד: mongodump מהזמני → אישור → mongorestore לפרודקשן. ~5 דקות ל-50 פריטים.

---

### מצב 3 — "אסון מלא, הפרודקשן נפל / corrupted"

**אל תשתמש במדריך הזה.** תפתח את `emergency-runbook-v2.md` ותעקוב משם. זה ספר הפעולה לאסונות אמיתיים — כולל איך מטפלים ב-EB שהתרסק, איך מודיעים למשתמשים, ואיך עושים PITR ישירות ל-prod (דורס הכל).

---

### מצב 4 — "נמחקה תמונה / קובץ מ-S3" 🆕

דוגמה: משתמש אומר "התמונות של הליקוי ב-Bdika נעלמו", או שקובץ PDF של פרוטוקול מסירה חסר.

**הידיעה החשובה:** על ה-bucket `brikops-prod-files` מופעל **S3 Versioning** — זה אומר שאף קובץ לא באמת נמחק לצמיתות. מחיקה היא **delete marker** שמסתיר את הקובץ המקורי. מחיקת ה-delete marker = שחזור.

**מה לעשות (פשוט, 3 דקות לקובץ אחד):**

1. **AWS Console → S3 → `brikops-prod-files`** → נווט לתיקייה (למשל `attachments/`)
2. **חפש את הקובץ** בחיפוש (מספיק ה-UUID — `e6bfaf96-...`)
3. **הפעל את ה-toggle "Show versions"** ליד תיבת החיפוש — יהפוך לכחול
4. עכשיו תראה **2 שורות** לקובץ:
   - **Delete marker** (0 B, תאריך המחיקה) — זה מה שצריך למחוק
   - **jpg / pdf** (עם גודל אמיתי) — הקובץ עצמו, עדיין קיים
5. **סמן רק את ה-Delete marker** ⚠️ (אל תסמן את הקובץ האמיתי)
6. **Delete → הקלד "permanently delete"** → Delete marker נמחק
7. רענן את הדף — נשארה רק שורה אחת (הקובץ חזר)
8. רענן ב-BrikOps — התמונה חזרה מיד (אין cache בין האפליקציה ל-S3)

**זה מה שעשינו בתרחיש 2.** עבד מושלם, לקח 3 דקות.

**⚠️ חשוב לזכור:**
- לעולם אל תסמן את שורת ה-jpg/pdf עצמה — מחיקה שלה = אובדן לצמיתות, אין שחזור
- השיטה עובדת יפה ל-1-10 קבצים. ל-100+ קבצים → ראה "מה עדיין חסר" למטה

---

## 🧰 הכלים שבנינו היום (2026-04-22)

### 1. `restore-toolkit.md` — המסמך הטכני

מכיל 3 דברים:

**(א) שיטות למצוא מה נמחק** — 3 אפשרויות:
- **diff** (הכי אמין — מה שתיארתי במצב 2 למעלה)
- **audit_events** — שאילתה על טבלת ה-audit ב-BrikOps (אבל עדיין לא בטוח שהיא מתעדת deletes — יש משימה לבדוק)
- **oplog scan** — scan של ה-MongoDB oplog (fallback אחרון)

**(ב) טבלת החלטה** — מתי להשתמש במה:
- 1-10 מסמכים → Data Explorer ידני (מצב 1)
- 10-500 מסמכים → `bulk-restore.sh` (מצב 2)
- לא יודעים מה נמחק → קודם diff, אז `bulk-restore.sh`

**(ג) דוגמה מלאה** — תרחיש מסודר של 50 ליקויים שנעלמו, מהתלונה ועד האימות.

### 2. `bulk-restore.sh` — הסקריפט ההרצה (MongoDB)

קובץ bash **שכבר executable** (יש לו `chmod +x`). מה שהוא עושה:

1. מתחבר ל-cluster הזמני → מוציא את המסמכים שביקשת ל-3 קבצי BSON במק (tasks + handovers + qc_runs)
2. מציג לך מה נורד ושואל "YES?" כדי להמשיך
3. מתחבר לפרודקשן → מעלה את ה-BSON-ים
4. מדפיס סיכום

**חשוב:** כל פעם שאתה רוצה להשתמש בו, פותחים אותו עם עורך טקסט ומעדכנים 5-6 שורות בראש הקובץ (credentials + רשימת IDs). אחרי זה מריצים. **זה לא אוטומטי לחלוטין — אבל הרבה יותר מהיר מ-UI.**

### 3. `s3-bulk-restore.sh` — הסקריפט ההרצה (S3)

קובץ bash **executable** שמשחזר מאות קבצי S3 שנמחקו במכה אחת. בניגוד ל-`bulk-restore.sh`, הוא **לא דורש עריכה ידנית** — מקבל הכל כדגלים בשורת הפקודה.

**דוגמאות שימוש:**

```bash
# ברירת מחדל — מוצא delete markers מהשעה האחרונה על כל ה-bucket
./s3-bulk-restore.sh

# תרחיש אמת — נמחקו קבצים בין 10:00 ל-12:00 בבוקר
./s3-bulk-restore.sh --from 2026-04-22T10:00:00Z --to 2026-04-22T12:00:00Z

# רק תמונות של ליקויים (prefix מסוים)
./s3-bulk-restore.sh --prefix attachments/ --from 2026-04-22T10:00:00Z

# תצוגה מקדימה — לא מוחק כלום, רק מציג מה ישוחזר
./s3-bulk-restore.sh --dry-run --from 2026-04-22T10:00:00Z
```

**איך זה עובד:**
1. `aws s3api list-object-versions` — מוציא את כל ה-versions של ה-bucket
2. מסנן רק delete markers בחלון הזמן שביקשת
3. מציג תצוגה מקדימה (20 ראשונים + 5 אחרונים)
4. שואל "YES" לאישור
5. מוחק כל delete marker אחד-אחד → הקבצים חוזרים

**דרישות מוקדמות:**
```bash
brew install awscli jq
aws configure      # IAM user עם s3:ListBucketVersions + s3:DeleteObjectVersion
```

**זמן:** ~10 קבצים/שנייה. ל-500 קבצים → דקה.

---

## ⚠️ מה עדיין חסר (משימות פתוחות)

כדי להגיע ל"כפתור אחד" אמיתי בעתיד — צריך:

1. **Endpoint ב-BrikOps שמחזיר deletes מה-audit** — `GET /admin/audit/deletes?from=...&to=...`. בלי זה, הגישה היחידה למצוא IDs היא diff ידני (= שני חיבורי mongosh).

2. **לאמת ש-audit_events באמת מתעד deletes** עם `resource_id` ברור. אם לא — להוסיף audit logging בכל המקומות שמוחקים tasks / handover / qc.

3. **לבנות soft-delete** — במקום למחוק באמת, לסמן `deleted_at`. אז שום דבר לא באמת נעלם, ו"שחזור" זה פשוט לאפס את השדה.

4. ✅ ~~`s3-bulk-restore.sh`~~ — **נבנה 2026-04-22.** סקריפט bash מלא, מקבל דגלים (`--from`, `--to`, `--prefix`, `--dry-run`), סורק את ה-bucket, מוצא delete markers בחלון הזמן, ומשחזר. ראה "כלים" למעלה.

5. ✅ ~~**S3 Cross-Region Replication (CRR) ל-eu-west-1**~~ — **הוקם 2026-04-22.** Destination: `brikops-prod-files-backup-ireland`. Delete marker replication: OFF. Storage class: Standard-IA. 727 קבצים היסטוריים שוכפלו דרך Batch Operations (0 כשלים). **מעתה — כל upload חדש משתכפל אוטומטית תוך שניות.** פרטים מלאים בסעיף "🌍 Cross-Region Replication" למעלה.

המשימות פתוחות ב-TodoList — כשאני אחזור לפיתוח אני יכול לבקש מ-Replit לבנות, או לעשות את S3 CRR ידנית ב-AWS Console (20 דקות עבודה).

---

## 📋 Cheat Sheet — 4 סיטואציות בטבלה אחת

| הסיטואציה | הכלי | הזמן |
|---|---|---|
| מחקתי 1-10 פריטים ב-DB, יודע מה | PITR ל-temp + Data Explorer Clone | 25 דק' |
| מחקו הרבה ב-DB, אני לא יודע מה | PITR + diff + `bulk-restore.sh` | 15-30 דק' |
| נמחק קובץ/תמונה מ-S3 | S3 Console → Show versions → מוחק delete marker | 3 דק' |
| אסון מלא | `emergency-runbook-v2.md` | תלוי |

---

## 🔗 הפרומפט לאיחור שינה, אני מתוח ולא זוכר כלום

פשוט תעתיק לקלוד:

> "יש לי בעיה ב-BrikOps. קרא את `/Users/zhysmy/brikops-new/docs/dr/README.md` ותנחה אותי צעד-צעד. הסיטואציה שלי היא: [תאר פה]."
