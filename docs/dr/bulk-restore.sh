#!/usr/bin/env bash
# BrikOps — Bulk Restore from temp cluster to prod
# תכלית: לשחזר הרבה מסמכים במכה אחת (עשרות עד מאות), בלי Data Explorer ידני
# נוצר: 2026-04-22 אחרי תרחיש 1 (PITR) — פתר את בעיית ה-scale של UI restore
#
# שימוש:
#   1. ערוך את המשתנים למטה (credentials + IDs)
#   2. chmod +x bulk-restore.sh
#   3. ./bulk-restore.sh
#
# דרישות מוקדמות:
#   brew tap mongodb/brew
#   brew install mongosh mongodb-database-tools

set -euo pipefail

# ═══════════════════════════════════════════════════════════════
#  משתנים — ערוך אותם כל פעם מחדש
# ═══════════════════════════════════════════════════════════════

# Source: temp cluster שנוצר ע"י PITR (ראה playbook תרחיש 1.3)
SRC_URI="mongodb+srv://<dr-user>:<dr-pass>@brikops-pitr-test.XXXXX.mongodb.net"

# Destination: prod
DST_URI="mongodb+srv://<dr-user>:<dr-pass>@brikops-eu.YYYYY.mongodb.net"

DB_NAME="brikops_prod"
OUT_DIR="$HOME/dr-restore-$(date +%Y%m%d-%H%M%S)"

# ─── IDs לשחזור ──────────────────────────────────────────────
# אם אתה לא יודע את ה-IDs → ראה restore-toolkit.md → "איך מוצאים מה נמחק"
# אפשר להשתמש ב-diff עם comm -23 וליצור TASK_IDS אוטומטית מקובץ:
#   jq -R . /tmp/missing-ids.txt | jq -s -c .

TASK_IDS='[
  "4ea3e7e4-40e7-42d9-8c3f-502f73279db6",
  "485ac43a-54ea-45d8-a28a-e3c9b83401fe",
  "561c6aa5-6f31-4616-a354-5d00042f4134"
]'

HANDOVER_IDS='["b12d0129-d8ba-4313-ad99-93d1e1c8a495"]'

QC_RUN_IDS='["52bb9d0b-fefa-45dd-91b3-df75be3ccf07"]'

# אם אתה רוצה לשחזר גם qc_items/qc_notifications — הוסף למטה

# ═══════════════════════════════════════════════════════════════
#  התהליך — אל תשנה מכאן למטה אלא אם אתה יודע מה אתה עושה
# ═══════════════════════════════════════════════════════════════

echo "════════════════════════════════════════════════"
echo "  BrikOps DR Bulk Restore"
echo "════════════════════════════════════════════════"
echo "  Source: $(echo "$SRC_URI" | sed 's/:[^:]*@/:***@/')"
echo "  Target: $(echo "$DST_URI" | sed 's/:[^:]*@/:***@/')"
echo "  Output: $OUT_DIR"
echo "════════════════════════════════════════════════"

mkdir -p "$OUT_DIR"

# ─── 1. Dump ──────────────────────────────────────────

echo ""
echo "▶ [1/2] Dumping from SOURCE (temp cluster)..."
echo ""

if [[ "$TASK_IDS" != "[]" && -n "$TASK_IDS" ]]; then
  echo "  → tasks"
  mongodump --uri="$SRC_URI/$DB_NAME" \
    --collection=tasks \
    --query="{\"id\":{\"\$in\":$TASK_IDS}}" \
    --out="$OUT_DIR"
fi

if [[ "$HANDOVER_IDS" != "[]" && -n "$HANDOVER_IDS" ]]; then
  echo "  → handover_protocols"
  mongodump --uri="$SRC_URI/$DB_NAME" \
    --collection=handover_protocols \
    --query="{\"id\":{\"\$in\":$HANDOVER_IDS}}" \
    --out="$OUT_DIR"
fi

if [[ "$QC_RUN_IDS" != "[]" && -n "$QC_RUN_IDS" ]]; then
  echo "  → qc_runs"
  mongodump --uri="$SRC_URI/$DB_NAME" \
    --collection=qc_runs \
    --query="{\"id\":{\"\$in\":$QC_RUN_IDS}}" \
    --out="$OUT_DIR"
fi

echo ""
echo "▶ Dump complete. Contents:"
ls -la "$OUT_DIR/$DB_NAME/" 2>/dev/null || echo "  (empty — nothing was dumped)"

# ─── 2. Confirmation ──────────────────────────────────

echo ""
echo "════════════════════════════════════════════════"
echo "  READY TO RESTORE TO PROD"
echo "════════════════════════════════════════════════"
read -rp "Type 'YES' to restore to PROD, anything else to abort: " confirm
if [[ "$confirm" != "YES" ]]; then
  echo ""
  echo "❌ Aborted. Dump preserved at: $OUT_DIR"
  echo "   (If you want to retry the restore later — run mongorestore manually)"
  exit 0
fi

# ─── 3. Restore ───────────────────────────────────────

echo ""
echo "▶ [2/2] Restoring to PROD..."
echo ""
mongorestore --uri="$DST_URI/$DB_NAME" \
  --dir="$OUT_DIR/$DB_NAME" \
  --verbose

# הערה: mongorestore עושה insert. אם _id קיים ב-target → error + skip (בטוח).
# אם רצית force overwrite → הוסף --drop (מוחק את כל ה-collection! מסוכן)

echo ""
echo "════════════════════════════════════════════════"
echo "  ✅ RESTORE COMPLETE"
echo "════════════════════════════════════════════════"
echo ""
echo "▶ Next steps:"
echo "  1. Verify in prod:"
echo "     mongosh \"$DST_URI/$DB_NAME\""
echo "     db.tasks.countDocuments({project_id:'...'})"
echo ""
echo "  2. Terminate temp cluster to stop billing:"
echo "     Atlas → Clusters → brikops-pitr-test → Terminate"
echo ""
echo "  3. Dump location (keep as safety backup, delete after 7 days):"
echo "     $OUT_DIR"
echo ""
