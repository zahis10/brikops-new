# BrikOps — Restore Toolkit (real-world DR scripts)

**נוצר:** 2026-04-22 (אחרי תרחיש 1)
**מטרה:** לפתור את שתי הבעיות שהתגלו בתרחיש 1:
1. איך מוצאים מה נמחק כשלא יודעים את ה-IDs מראש
2. איך משחזרים בכמויות גדולות בלי לעבור ידני על כל מסמך

**עיקרון:** הכל כאן ניתן להרצה — כדי שלא תצטרך לזכור syntax תחת לחץ.

---

## 🎯 מתי להשתמש בכל גישה

| מצב | כמות מסמכים | גישה | זמן משוער |
|---|---|---|---|
| מסמכים בודדים, ה-IDs ידועים | 1-10 | **Data Explorer Clone → Insert** | 2 דק' לכל מסמך |
| הרבה מסמכים, ה-IDs ידועים | 10-500 | **bulk-restore.sh** (mongodump/mongorestore) | 5-15 דק' |
| לא יודעים מה נמחק | כל כמות | **קודם find-missing.js → אח"כ bulk-restore.sh** | +10 דק' לזיהוי |
| אסון מלא — כל ה-DB | הכל | **PITR ישירות ל-prod** (דורס הכל) | 5-15 דק' (downtime) |

---

## 🕵️ איך מוצאים מה נמחק (Problem A)

במציאות — משתמש מתלונן ש"הפרויקט נעלם" או "כל הליקויים מהקומה השישית אבדו". אין לך רשימת IDs. 3 גישות:

### שיטה 1 — Diff בין temp cluster ל-prod (הכי אמינה)

**רעיון:** אחרי PITR ל-temp cluster, שלוף את כל ה-IDs מכל cluster והשווה. כל ID שיש ב-temp אבל לא ב-prod = נמחק.

**תנאי:** חובה להתחבר ל-2 clusters בנפרד. ב-mongosh אי אפשר 2 חיבורים במקביל → נריץ 2 סשנים.

#### שלב 1 — ב-prod, שלוף את כל ה-IDs הנוכחיים:
```bash
# Terminal 1 — prod
mongosh "mongodb+srv://<prod-user>:<prod-pass>@brikops-eu.XXXXX.mongodb.net/brikops_prod" \
  --quiet \
  --eval 'db.tasks.find({project_id: "PROJECT_ID_HERE"}, {id:1, _id:0}).toArray().forEach(t => print(t.id))' \
  > /tmp/prod-task-ids.txt

wc -l /tmp/prod-task-ids.txt
# לדוגמה: 58 (אחרי שנמחקו 3)
```

#### שלב 2 — ב-temp cluster, שלוף את כל ה-IDs:
```bash
# Terminal 1 — temp cluster (אחרי PITR)
mongosh "mongodb+srv://<user>:<pass>@brikops-pitr-test.YYYYY.mongodb.net/brikops_prod" \
  --quiet \
  --eval 'db.tasks.find({project_id: "PROJECT_ID_HERE"}, {id:1, _id:0}).toArray().forEach(t => print(t.id))' \
  > /tmp/temp-task-ids.txt

wc -l /tmp/temp-task-ids.txt
# לדוגמה: 61 (לפני המחיקה)
```

#### שלב 3 — מצא את ההפרש:
```bash
# IDs שקיימים בtemp אבל לא ב-prod = אלה שנמחקו
comm -23 <(sort /tmp/temp-task-ids.txt) <(sort /tmp/prod-task-ids.txt) > /tmp/deleted-ids.txt
cat /tmp/deleted-ids.txt
# לדוגמה:
# 4ea3e7e4-40e7-42d9-8c3f-502f73279db6
# 485ac43a-54ea-45d8-a28a-e3c9b83401fe
# 561c6aa5-6f31-4616-a354-5d00042f4134
```

**תוצאה:** קובץ `/tmp/deleted-ids.txt` עם רשימת כל ה-IDs שנמחקו מהפרויקט. מכאן → bulk-restore.

### שיטה 2 — audit_events (הדרך "הנקייה")

ב-BrikOps יש collection בשם `audit_events`. אם שמרו בו delete events עם ה-ID + timestamp + user — אפשר לשלוף:

```javascript
// ב-mongosh על prod
use brikops_prod

db.audit_events.find({
  action: "delete",   // או "task.deleted" — בודקים פעם ראשונה
  created_at: {
    $gte: ISODate("2026-04-21T19:00:00Z"),   // 1 שעה לפני האסון
    $lte: ISODate("2026-04-21T20:00:00Z")    // 1 שעה אחרי
  }
}, {
  resource_type: 1, resource_id: 1, created_at: 1, user_id: 1
}).toArray()
```

**אזהרה:** כדאי לבדוק מראש האם ה-audit_events של BrikOps באמת מתעד delete בצורה שמישה (מה שם ה-action? האם שמור resource_id?). אם לא — תוסיף task ל-Replit לסדר את זה לפני שצריך.

### שיטה 3 — Oplog scan (אם יש גישה)

רק ל-Atlas M10+ עם oplog פעיל. בתוך PITR window:
```javascript
// ב-mongosh על prod, DB מיוחד
use local

db.oplog.rs.find({
  ns: "brikops_prod.tasks",
  op: "d",   // delete operation
  ts: { $gte: Timestamp(NUMBER_FROM_UNIX_EPOCH, 0) }
}, {
  o: 1, ts: 1   // o._id יראה איזה document נמחק
}).toArray()
```

ה-oplog מחזיק עד 24-48 שעות אחורה בד"כ. לא נשען על זה — אבל מועיל כ-fallback.

---

## 🔧 Bulk Restore Script (Problem B)

**ההקשר:** יש לך רשימת IDs (מ-`deleted-ids.txt` או ידועים מראש). אתה רוצה להחזיר אותם מ-temp cluster ל-prod בבת אחת.

### קובץ מוכן להרצה — `bulk-restore.sh`

שמור אותו ב-`/Users/zhysmy/brikops-new/docs/dr/bulk-restore.sh` וערוך כל פעם שצריך לפני הרצה:

```bash
#!/usr/bin/env bash
# BrikOps — Bulk Restore from temp cluster to prod
# Usage: ערוך את המשתנים למטה, הרץ ./bulk-restore.sh
set -euo pipefail

# ═══════════════════ משתני סביבה ═══════════════════
# תמלא את אלה כל פעם מחדש:

SRC_URI="mongodb+srv://<dr-user>:<dr-pass>@brikops-pitr-test.XXXXX.mongodb.net"
DST_URI="mongodb+srv://<dr-user>:<dr-pass>@brikops-eu.YYYYY.mongodb.net"
DB_NAME="brikops_prod"
OUT_DIR="$HOME/dr-restore-$(date +%Y%m%d-%H%M%S)"

# הגדר collection + query לכל סט מסמכים:
# אפשר להוסיף/להסיר בלוקים לפי הצורך.

# דוגמה 1 — tasks לפי רשימת IDs:
TASK_IDS='["4ea3e7e4-40e7-42d9-8c3f-502f73279db6","485ac43a-54ea-45d8-a28a-e3c9b83401fe","561c6aa5-6f31-4616-a354-5d00042f4134"]'

# דוגמה 2 — handover יחיד:
HANDOVER_ID="b12d0129-d8ba-4313-ad99-93d1e1c8a495"

# דוגמה 3 — qc_run יחיד:
QC_RUN_ID="52bb9d0b-fefa-45dd-91b3-df75be3ccf07"

# ═══════════════════ התהליך ═══════════════════

mkdir -p "$OUT_DIR"
echo "▶ Dumping to: $OUT_DIR"

# 1. Dump מה-temp cluster
echo ""
echo "=== [1/3] Dumping tasks from temp cluster ==="
mongodump --uri="$SRC_URI/$DB_NAME" \
  --collection=tasks \
  --query="{\"id\":{\"\$in\":$TASK_IDS}}" \
  --out="$OUT_DIR"

echo ""
echo "=== [2/3] Dumping handover_protocols from temp cluster ==="
mongodump --uri="$SRC_URI/$DB_NAME" \
  --collection=handover_protocols \
  --query="{\"id\":\"$HANDOVER_ID\"}" \
  --out="$OUT_DIR"

echo ""
echo "=== [3/3] Dumping qc_runs from temp cluster ==="
mongodump --uri="$SRC_URI/$DB_NAME" \
  --collection=qc_runs \
  --query="{\"id\":\"$QC_RUN_ID\"}" \
  --out="$OUT_DIR"

echo ""
echo "▶ Dump complete. Contents:"
ls -la "$OUT_DIR/$DB_NAME/"

# 2. אישור לפני restore ל-prod
echo ""
echo "═══════════════════════════════════════════════"
echo "  RESTORING TO PRODUCTION: $DST_URI"
echo "  Dump location: $OUT_DIR"
echo "═══════════════════════════════════════════════"
read -rp "Continue with restore to PROD? (type 'YES' to confirm): " confirm
if [[ "$confirm" != "YES" ]]; then
  echo "Aborted. Dump is preserved in $OUT_DIR if you want to retry."
  exit 0
fi

# 3. Restore ל-prod
echo ""
echo "=== Restoring to prod ==="
mongorestore --uri="$DST_URI/$DB_NAME" \
  --dir="$OUT_DIR/$DB_NAME" \
  --verbose

# הערה: mongorestore כברירת מחדל עושה insert. אם _id כבר קיים ב-target → יזרוק error וידלג
# (no --drop flag here on purpose — safer)

echo ""
echo "✅ Restore complete!"
echo ""
echo "▶ Next: verify in prod with mongosh:"
echo "    mongosh \"$DST_URI/$DB_NAME\""
echo "    db.tasks.countDocuments({project_id: '...'})"
```

### שימוש:

```bash
chmod +x /Users/zhysmy/brikops-new/docs/dr/bulk-restore.sh

# ערוך את המשתנים בראש הקובץ (SRC_URI, DST_URI, TASK_IDS וכו')
vim /Users/zhysmy/brikops-new/docs/dr/bulk-restore.sh

# הרץ
cd /Users/zhysmy/brikops-new/docs/dr/
./bulk-restore.sh
```

הסקריפט ישאל אישור לפני ה-restore ל-prod. ה-dump נשמר תחת `~/dr-restore-YYYYMMDD-HHMMSS/` כגיבוי.

---

## 🚨 התקנה חד-פעמית

כדי שהסקריפט יעבוד, צריך את הכלים האלה על המק (כנראה כבר מותקנים אצלך):

```bash
# mongosh + mongodump + mongorestore
brew tap mongodb/brew
brew install mongosh mongodb-database-tools

# ודא:
mongosh --version        # should show 2.x
mongodump --version      # 100.x
mongorestore --version   # 100.x
```

---

## 📋 Full worked example (תרחיש 1 אם היינו עושים אותו עם הסקריפט)

**תרחיש:** משתמש פונה ב-10:00 — "כל ליקויי הקומה השישית בפרויקט מגדלי הים נעלמו מאתמול בערב".

### שלב 1 — זיהוי (שיטה 1 — diff)

```bash
# מצא מתי נמחק (שעה משוערת)
# הקורבן דיווח שהכל היה בסדר אתמול בערב 22:00, ובבוקר 10:00 ריק

# PITR ל-temp cluster לזמן 22:00 אתמול
# (Atlas UI → Backup → Point in Time Restore → 2026-04-21 22:00 UTC)

# אחרי שה-temp cluster מוכן (~3 דק') — שלוף IDs
PROJECT_ID="c3e18b07-a7d8-411e-80f9-95028b15788a"
FLOOR_ID="77451bcb-5375-4269-9203-022f099f25a2"

# prod (תמצא filter פיזי שחי)
mongosh "$DST_URI/brikops_prod" --quiet --eval "
  db.tasks.find({project_id:'$PROJECT_ID', floor_id:'$FLOOR_ID'}, {id:1, _id:0})
    .toArray().forEach(t => print(t.id))
" > /tmp/prod-ids.txt

# temp
mongosh "$SRC_URI/brikops_prod" --quiet --eval "
  db.tasks.find({project_id:'$PROJECT_ID', floor_id:'$FLOOR_ID'}, {id:1, _id:0})
    .toArray().forEach(t => print(t.id))
" > /tmp/temp-ids.txt

# diff
comm -23 <(sort /tmp/temp-ids.txt) <(sort /tmp/prod-ids.txt) > /tmp/missing-ids.txt
wc -l /tmp/missing-ids.txt
# לדוגמה: 47
```

### שלב 2 — בניית TASK_IDS JSON מהקובץ

```bash
# הפוך את /tmp/missing-ids.txt ל-JSON array:
jq -R . /tmp/missing-ids.txt | jq -s -c .
# ["id1","id2",...,"id47"]

# העתק את הפלט ל-TASK_IDS בתוך bulk-restore.sh
```

### שלב 3 — הרץ את הסקריפט
```bash
./bulk-restore.sh
# יאשר לפני restore
```

### שלב 4 — אימות
```bash
mongosh "$DST_URI/brikops_prod" --eval "
  db.tasks.countDocuments({project_id:'$PROJECT_ID', floor_id:'$FLOOR_ID'})
"
# אם זה שווה ל-count ב-temp → שחזור מוצלח
```

**סה"כ זמן משוער:** 3 דק' (PITR) + 5 דק' (diff) + 5 דק' (dump/restore + אימות) = **~15 דק' ל-47 מסמכים.** לעומת 47 × 2 דק' = 94 דק' ב-UI.

---

## 🎓 מסקנות מתרחיש 1

**מה עבד טוב:**
- PITR מהיר מאוד (3 דק' ל-M10)
- Data Explorer Clone → Insert עובד יפה ל-1-10 מסמכים
- שום downtime בפרודקשן לאורך כל התהליך

**מה חסר:**
- **API/endpoint ב-BrikOps שיחזיר רשימת deletes מ-audit_events** — לבנות ב-Replit
- **להבטיח ש-audit_events מתעד שקיים מחיקות** עם resource_id + timestamp + user_id — לבדוק כרגע
- **להעלות cross-region retention ל-7 ימים** (כרגע 1)

**הוספה למעקב (tasks):**
- Build `GET /admin/audit/deletes?from=<ts>&to=<ts>&resource_type=<name>` endpoint
- Verify audit_events captures deletes (action name? includes resource_id?)
- Build soft-delete pattern (set `deleted_at` field instead of removing) for critical collections: tasks, handover_protocols, qc_runs
