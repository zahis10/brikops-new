---
name: Dev preview for safety UI screenshots
description: Gotchas when screenshotting safety-module pages on the dev workflow
---
- Safety routers are mounted only when ENABLE_SAFETY_MODULE=true; the dev workflow reads backend/.env (flag added 2026-07-18). Symptom when off: 405/404 "Not found" on /api/safety/*.
- The CRA build bakes REACT_APP_BACKEND_URL; craco guard forbids empty. For local Playwright shots build with http://localhost:5000, then restore the standard https://api.brikops.com build afterwards.
- UI login form enforces 8-char min password client-side; seed users (pm123) fail silently. **How to apply:** login via API, then localStorage.setItem('token', ...) and navigate — works once the build points at localhost.
