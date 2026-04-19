# Spec — CORS fix for iOS Capacitor WebView

## Problem
iOS app (installed via TestFlight from Build 2) fails login with "network error" on mobile.
Same credentials work perfectly in Safari mobile browser (`https://app.brikops.com`).

Root cause: Capacitor WebView on iOS issues API requests from origin `capacitor://localhost`.
Backend CORS allowlist only includes `https://app.brikops.com, https://www.brikops.com`.
Preflight OPTIONS response omits `Access-Control-Allow-Origin` for Capacitor origin → WebView blocks the request before any network call.

## Scope
Single-line change in `backend/server.py` + env var update in Replit Secrets.

## File: `backend/server.py`

### Current (line 1386)
```python
_cors_default = 'https://app.brikops.com,https://www.brikops.com' if APP_MODE == 'prod' else '*'
```

### Change to
```python
_cors_default = (
    'https://app.brikops.com,'
    'https://www.brikops.com,'
    'capacitor://localhost,'
    'ionic://localhost,'
    'https://localhost'
) if APP_MODE == 'prod' else '*'
```

**Why 3 extra origins:**
- `capacitor://localhost` — iOS Capacitor WebView (THE fix for our case)
- `ionic://localhost` — legacy iOS origin (Capacitor 2.x, some plugins still use it)
- `https://localhost` — Android Capacitor + some iOS edge cases

## Replit Secrets — CHECK + UPDATE

**DO:**
1. In Replit → Secrets → search for `CORS_ORIGINS`
2. IF exists → update value to:
   ```
   https://app.brikops.com,https://www.brikops.com,capacitor://localhost,ionic://localhost,https://localhost
   ```
3. IF does not exist → no action needed (code default will be used)

**CRITICAL:** env var overrides code default. If `CORS_ORIGINS` is set in Secrets, code change alone WON'T fix the bug in production.

## Verify

### Test 1: curl from command line
```bash
curl -i -X OPTIONS https://api.brikops.com/auth/login \
  -H "Origin: capacitor://localhost" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,authorization"
```

**Expected response headers:**
```
HTTP/2 200
access-control-allow-origin: capacitor://localhost
access-control-allow-credentials: true
access-control-allow-methods: ...
```

**Fail signal:** no `access-control-allow-origin` header, or header equals `https://app.brikops.com` instead of `capacitor://localhost` → CORS still broken.

### Test 2: Real iOS test
1. Deploy backend
2. Force-close BrikOps on iPhone
3. Open → attempt login with test credentials
4. Expected: login succeeds, dashboard loads

## DO NOT
- Do NOT change `allow_credentials=True` — it's required for cookies
- Do NOT add `*` to allow_origins in prod — breaks credentials (browser blocks `*` with `allow_credentials`)
- Do NOT add any origin beyond the 5 listed above

## Rollback plan
If something breaks post-deploy → revert line 1386 to original, redeploy. iOS login stays broken but web login unaffected.

## After deploy
Zahi will verify from TestFlight app on real iPhone. Only after confirmed working → submit Build 2 to App Store Review.
