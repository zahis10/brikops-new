#!/usr/bin/env bash
# BrikOps — S3 Bulk Restore (מחיקת delete markers בכמויות)
# תכלית: לשחזר מאות קבצים שנמחקו מ-S3 במכה אחת, בלי Console ידני.
# איך זה עובד: Versioning מופעל → מחיקה יוצרת "delete marker" שמסתיר את הקובץ.
#               מחיקת ה-delete marker = הקובץ חוזר.
# נוצר: 2026-04-22 אחרי תרחיש 2 (S3 Version Restore)
#
# דוגמאות שימוש:
#   ./s3-bulk-restore.sh                      # מוצא delete markers אחרונים + שואל לפני מחיקה
#   ./s3-bulk-restore.sh --dry-run            # רק מציג מה ישוחזר, לא מבצע כלום
#   ./s3-bulk-restore.sh --from 2026-04-22T10:00:00Z --to 2026-04-22T12:00:00Z
#   ./s3-bulk-restore.sh --prefix attachments/ --from 2026-04-22T10:00:00Z
#
# דרישות מוקדמות:
#   aws configure   (IAM user עם הרשאות s3:ListBucketVersions + s3:DeleteObject + s3:DeleteObjectVersion)
#   jq (brew install jq)

set -euo pipefail

# ═══════════════════════════════════════════════════════════════
#  ברירת מחדל — ניתן לעקוף עם דגלים
# ═══════════════════════════════════════════════════════════════

BUCKET="brikops-prod-files"
REGION="eu-central-1"
PREFIX=""                                # ריק = כל ה-bucket (attachments/, qc/, signatures/ וכו')
FROM="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)"
TO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DRY_RUN=false

# ═══════════════════════════════════════════════════════════════
#  Arg parsing
# ═══════════════════════════════════════════════════════════════

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help)
      grep '^#' "$0" | head -20
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ═══════════════════════════════════════════════════════════════
#  Sanity checks
# ═══════════════════════════════════════════════════════════════

command -v aws >/dev/null || { echo "❌ aws CLI not installed. brew install awscli"; exit 1; }
command -v jq >/dev/null || { echo "❌ jq not installed. brew install jq"; exit 1; }

echo "════════════════════════════════════════════════"
echo "  BrikOps S3 Bulk Restore"
echo "════════════════════════════════════════════════"
echo "  Bucket: $BUCKET"
echo "  Region: $REGION"
echo "  Prefix: ${PREFIX:-<entire bucket>}"
echo "  Window: $FROM  →  $TO"
echo "  Mode:   $([ "$DRY_RUN" = true ] && echo 'DRY RUN (no deletes)' || echo 'LIVE (will delete markers)')"
echo "════════════════════════════════════════════════"
echo ""

# ═══════════════════════════════════════════════════════════════
#  1. מציאת delete markers בחלון הזמן
# ═══════════════════════════════════════════════════════════════

TMP_JSON=$(mktemp)
trap "rm -f $TMP_JSON" EXIT

echo "▶ [1/3] Scanning for delete markers..."

aws s3api list-object-versions \
  --bucket "$BUCKET" \
  --region "$REGION" \
  ${PREFIX:+--prefix "$PREFIX"} \
  --output json \
  > "$TMP_JSON"

# סנן רק delete markers שנוצרו בחלון
MARKERS=$(jq --arg from "$FROM" --arg to "$TO" '
  (.DeleteMarkers // [])
  | map(select(.LastModified >= $from and .LastModified <= $to))
' "$TMP_JSON")

COUNT=$(echo "$MARKERS" | jq 'length')

echo "  → Found $COUNT delete markers in window"
echo ""

if [[ "$COUNT" -eq 0 ]]; then
  echo "✅ No delete markers to remove. Exiting."
  exit 0
fi

# ═══════════════════════════════════════════════════════════════
#  2. תצוגה מקדימה + אישור
# ═══════════════════════════════════════════════════════════════

echo "▶ [2/3] Preview (first 20 + last 5):"
echo ""
echo "$MARKERS" | jq -r '.[] | "  \(.LastModified)  \(.Key)  [vid=\(.VersionId | .[0:16])...]"' | head -20
if [[ "$COUNT" -gt 25 ]]; then
  echo "  ... ($((COUNT - 25)) more) ..."
  echo "$MARKERS" | jq -r '.[] | "  \(.LastModified)  \(.Key)  [vid=\(.VersionId | .[0:16])...]"' | tail -5
fi
echo ""

if [[ "$DRY_RUN" = true ]]; then
  echo "✅ DRY RUN complete. Would restore $COUNT files."
  echo "   To actually restore: re-run without --dry-run"
  exit 0
fi

echo "════════════════════════════════════════════════"
echo "  ⚠️  ABOUT TO RESTORE $COUNT FILES"
echo "════════════════════════════════════════════════"
read -rp "Type 'YES' to proceed, anything else to abort: " confirm
if [[ "$confirm" != "YES" ]]; then
  echo "❌ Aborted."
  exit 0
fi

# ═══════════════════════════════════════════════════════════════
#  3. מחיקת delete markers (= שחזור הקבצים)
# ═══════════════════════════════════════════════════════════════

echo ""
echo "▶ [3/3] Deleting $COUNT delete markers..."
echo ""

SUCCESS=0
FAILED=0

echo "$MARKERS" | jq -c '.[]' | while read -r row; do
  KEY=$(echo "$row" | jq -r '.Key')
  VID=$(echo "$row" | jq -r '.VersionId')

  if aws s3api delete-object \
       --bucket "$BUCKET" \
       --region "$REGION" \
       --key "$KEY" \
       --version-id "$VID" \
       --output text >/dev/null 2>&1; then
    echo "  ✅ $KEY"
    SUCCESS=$((SUCCESS + 1))
  else
    echo "  ❌ $KEY  (version $VID)"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "════════════════════════════════════════════════"
echo "  ✅ RESTORE COMPLETE"
echo "════════════════════════════════════════════════"
echo "  Processed: $COUNT"
echo ""
echo "▶ Next steps:"
echo "  1. Verify in BrikOps — pick a few keys and confirm images load"
echo "  2. Check S3 Console — re-search one of the keys, 'Show versions' off,"
echo "     should appear as regular file again"
echo ""
echo "▶ If any files failed to restore:"
echo "  - Check IAM permissions (s3:DeleteObjectVersion)"
echo "  - Re-run the script — already-restored files are skipped naturally"
