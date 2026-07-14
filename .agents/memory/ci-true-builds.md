---
name: CI=true verification builds
description: Frontend build verification must use CI=true to match deploy pipeline
---
Rule: run `cd frontend && CI=true GENERATE_SOURCEMAP=false REACT_APP_BACKEND_URL=https://api.brikops.com npx craco build` for verification — must exit 0 with zero warnings.
**Why:** Deploy preflight runs CI=true, which promotes eslint warnings (e.g. react-hooks/exhaustive-deps) to errors; CI=false builds passed while deploy was blocked (2026-07-14).
**How to apply:** Every batch's V6 build step and any pre-review build check. Never eslint-disable to silence — fix the dep array.
