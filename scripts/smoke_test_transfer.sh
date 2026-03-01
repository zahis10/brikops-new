#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# BrikOps — Post-Deploy Smoke Test: Ownership Transfer
# ═══════════════════════════════════════════════════════════════
#
# Usage:
#   export BASE=https://brikops.com
#   export PM_EMAIL=pm@contractor-ops.com
#   export PM_PASS=pm123
#   export TARGET_PHONE=05XXXXXXXX   # recipient's real phone
#   bash scripts/smoke_test_transfer.sh
#
# After initiate, SMS arrives on recipient phone with accept link.
# You'll be prompted to paste the TOKEN from the link and the OTP.
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

BASE="${BASE:-https://brikops.com}"
API="$BASE/api"

echo "═══ SMOKE TEST: Ownership Transfer ═══"
echo "Target: $BASE"
echo ""

# ─── Step 0: Login PM ───
echo "▶ Logging in PM..."
PM_TOKEN=$(curl -sf "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${PM_EMAIL}\",\"password\":\"${PM_PASS}\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
echo "  ✓ PM logged in"

# ─── 1) Billing BEFORE ───
echo ""
echo "━━━ 1) /api/billing/me BEFORE ━━━"
echo "--- Owner (PM) ---"
curl -sf "$API/billing/me" -H "Authorization: Bearer $PM_TOKEN" | python3 -c '
import sys,json; d=json.load(sys.stdin)
print(f"  is_owner={d.get(\"is_owner\")}  owner_user_id={d.get(\"owner_user_id\")}")'

# ─── 2) Initiate ───
echo ""
echo "━━━ 2) Initiate transfer ━━━"
INIT=$(curl -sf -X POST "$API/org/transfer/initiate" \
  -H "Authorization: Bearer $PM_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"target_phone\":\"${TARGET_PHONE}\"}")
echo "$INIT" | python3 -c '
import sys,json; d=json.load(sys.stdin)
d.pop("_debug_token",None)
print(json.dumps(d, indent=2, ensure_ascii=False))'

echo ""
echo "📱 SMS was sent to recipient. Open the link from the SMS."
echo ""
read -p "Paste the TOKEN from the link (the part after /org/transfer/): " TOKEN

# ─── 3) Verify ───
echo ""
echo "━━━ 3) Verify token ━━━"
VERIFY=$(curl -sf "$API/org/transfer/verify/$TOKEN")
echo "$VERIFY" | python3 -c '
import sys,json; d=json.load(sys.stdin)
print(json.dumps(d, indent=2, ensure_ascii=False))'
ORG_NAME=$(echo "$VERIFY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["org_name"])')

# ─── 4) Request OTP ───
echo ""
echo "━━━ 4) Request OTP ━━━"
curl -sf -X POST "$API/org/transfer/request-otp" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$TOKEN\"}" | python3 -m json.tool

echo ""
read -p "Enter OTP code from SMS: " OTP_CODE

# ─── 5) Accept ───
echo ""
echo "━━━ 5) Accept transfer ━━━"
echo "  Org name: $ORG_NAME"
ACCEPT=$(curl -sf -X POST "$API/org/transfer/accept" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$TOKEN\",\"otp_code\":\"$OTP_CODE\",\"typed_org_name\":\"$ORG_NAME\"}")
echo "$ACCEPT" | python3 -c '
import sys,json; d=json.load(sys.stdin)
print(json.dumps(d, indent=2, ensure_ascii=False))'

# ─── 6) Billing AFTER ───
echo ""
echo "━━━ 6) /api/billing/me AFTER (PM with OLD token) ━━━"
HTTP_CODE=$(curl -s -o /tmp/smoke_billing.json -w "%{http_code}" \
  "$API/billing/me" -H "Authorization: Bearer $PM_TOKEN")
echo "  HTTP status: $HTTP_CODE"
cat /tmp/smoke_billing.json | python3 -m json.tool 2>/dev/null

if [ "$HTTP_CODE" = "401" ]; then
    echo "  ✓ Session invalidated — old owner gets 401"
else
    echo "  ⚠ Expected 401 but got $HTTP_CODE"
fi

# ─── 7) Fresh PM login to check billing ───
echo ""
echo "━━━ 7) Fresh PM login — billing AFTER ━━━"
PM_TOKEN2=$(curl -sf "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${PM_EMAIL}\",\"password\":\"${PM_PASS}\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
curl -sf "$API/billing/me" -H "Authorization: Bearer $PM_TOKEN2" | python3 -c '
import sys,json; d=json.load(sys.stdin)
print(f"  is_owner={d.get(\"is_owner\")}  owner_user_id={d.get(\"owner_user_id\")}")'

echo ""
echo "═══ SMOKE TEST COMPLETE ═══"
