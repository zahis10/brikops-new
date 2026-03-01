#!/usr/bin/env bash
set -euo pipefail

PASS=0
FAIL=0
RESULTS=()

check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "PASS" ]; then
        PASS=$((PASS + 1))
        RESULTS+=("PASS  $name")
        echo "[PASS] $name"
    else
        FAIL=$((FAIL + 1))
        RESULTS+=("FAIL  $name")
        echo "[FAIL] $name"
    fi
}

echo "============================================"
echo "  BedekPro Isolation Verification Script"
echo "============================================"
echo ""

echo "--- 1. Hardcoded Secret Scan ---"
FOUND_DEFAULT=$(grep -rn "default_secret_key" backend/*.py backend/**/*.py 2>/dev/null | grep -v "verify_isolation" | grep -v ".pyc" | grep -v "__pycache__" || true)
if [ -z "$FOUND_DEFAULT" ]; then
    check "No 'default_secret_key' in code" "PASS"
else
    echo "  Found: $FOUND_DEFAULT"
    check "No 'default_secret_key' in code" "FAIL"
fi

FOUND_BEDEK=$(grep -rn "bedekpro_secret_key_2024" backend/*.py backend/**/*.py 2>/dev/null | grep -v "verify_isolation" | grep -v ".pyc" | grep -v "__pycache__" || true)
if [ -z "$FOUND_BEDEK" ]; then
    check "No 'bedekpro_secret_key_2024' in code" "PASS"
else
    echo "  Found: $FOUND_BEDEK"
    check "No 'bedekpro_secret_key_2024' in code" "FAIL"
fi

echo ""
echo "--- 2. Config Module Exists ---"
if [ -f "backend/config.py" ]; then
    check "backend/config.py exists" "PASS"
else
    check "backend/config.py exists" "FAIL"
fi

echo ""
echo "--- 3. Required Env Vars ---"
for VAR in APP_ID APP_MODE JWT_SECRET JWT_SECRET_VERSION MONGO_URL DB_NAME; do
    VAL=$(grep "^${VAR}=" backend/.env 2>/dev/null | head -1 || true)
    if [ -n "$VAL" ]; then
        check "Env var $VAR defined in .env" "PASS"
    else
        check "Env var $VAR defined in .env" "FAIL"
    fi
done

echo ""
echo "--- 4. JWT Issuer Enforcement ---"
ISS_CREATE=$(grep -c "'iss': APP_ID" backend/server.py 2>/dev/null || echo 0)
ISS_VERIFY=$(grep -c "issuer=APP_ID" backend/server.py 2>/dev/null || echo 0)
if [ "$ISS_CREATE" -ge 1 ] && [ "$ISS_VERIFY" -ge 1 ]; then
    check "JWT issuer (iss=APP_ID) enforced" "PASS"
else
    check "JWT issuer (iss=APP_ID) enforced" "FAIL"
fi

echo ""
echo "--- 5. JWT Secret Version ---"
SV_CREATE=$(grep -c "secret_version.*JWT_SECRET_VERSION" backend/server.py 2>/dev/null || echo 0)
SV_VERIFY=$(grep -c "secret_version.*JWT_SECRET_VERSION" backend/server.py 2>/dev/null || echo 0)
if [ "$SV_CREATE" -ge 1 ] && [ "$SV_VERIFY" -ge 1 ]; then
    check "JWT secret version enforcement" "PASS"
else
    check "JWT secret version enforcement" "FAIL"
fi

echo ""
echo "--- 6. Algorithm Allowlist ---"
ALG_LIST=$(grep -c "JWT_ALLOWED_ALGORITHMS" backend/server.py 2>/dev/null || echo 0)
if [ "$ALG_LIST" -ge 1 ]; then
    check "JWT algorithm allowlist (HS256 only)" "PASS"
else
    check "JWT algorithm allowlist (HS256 only)" "FAIL"
fi

echo ""
echo "--- 7. .env.example exists ---"
if [ -f "backend/.env.example" ]; then
    REAL_SECRET=$(grep "bedekpro_secret_key_2024" backend/.env.example 2>/dev/null || true)
    if [ -z "$REAL_SECRET" ]; then
        check ".env.example has no real secrets" "PASS"
    else
        check ".env.example has no real secrets" "FAIL"
    fi
else
    check ".env.example exists" "FAIL"
fi

echo ""
echo "--- 8. Startup Guard (config.py) ---"
GUARD_APPID=$(grep -c "_require('APP_ID')" backend/config.py 2>/dev/null || echo 0)
GUARD_JWT=$(grep -c "_require('JWT_SECRET'" backend/config.py 2>/dev/null || echo 0)
if [ "$GUARD_APPID" -ge 1 ] && [ "$GUARD_JWT" -ge 1 ]; then
    check "Startup guard enforces APP_ID + JWT_SECRET" "PASS"
else
    check "Startup guard enforces APP_ID + JWT_SECRET" "FAIL"
fi

echo ""
echo "--- 9. ISOLATION_REPORT.md ---"
if [ -f "ISOLATION_REPORT.md" ]; then
    check "ISOLATION_REPORT.md exists" "PASS"
else
    check "ISOLATION_REPORT.md exists" "FAIL"
fi

echo ""
echo "============================================"
echo "  RESULTS: $PASS passed, $FAIL failed"
echo "============================================"
for r in "${RESULTS[@]}"; do
    echo "  $r"
done
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo "VERDICT: PASS"
    exit 0
else
    echo "VERDICT: FAIL"
    exit 1
fi
