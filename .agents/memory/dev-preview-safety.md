---
name: Dev preview for authenticated UI screenshots
description: Gotchas when testing authenticated CRA pages through the proxied dev workflow
---
- Safety routers are mounted only when ENABLE_SAFETY_MODULE=true; the dev workflow reads backend/.env (flag added 2026-07-18). Symptom when off: 405/404 "Not found" on /api/safety/*.
- Build proxied preview/test bundles with `REACT_APP_BACKEND_URL=/`, not localhost or the bare dev domain.

  **Why:** The CRA build bakes this value, while the app CSP permits `connect-src 'self'`; an absolute URL becomes cross-origin when the tester reaches the app through a port-specific proxy and leaves authenticated pages stuck loading.

  **How to apply:** Use the slash value for same-origin `/api` calls, then restart the app workflow so it serves the new bundle. Do not treat the mockup workflow's default domain as the main app.
- UI login form enforces 8-char min password client-side; seed users (pm123) fail silently. **How to apply:** login via API, then localStorage.setItem('token', ...) and navigate — works once the build points at localhost.
