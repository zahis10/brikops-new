---
name: yarn.lock Replit proxy URLs
description: External builds (Cloudflare Pages) fail when yarn.lock points at Replit's internal npm proxy
---
Rule: after adding any frontend dependency inside Replit, run `grep -n "replit.local" frontend/yarn.lock` and rewrite any `http://package-firewall.replit.local/npm/...` resolved URL to `https://registry.npmjs.org/...` (keep the integrity line unchanged — it is the standard public tarball hash).
**Why:** Cloudflare Pages builds fail with getaddrinfo ENOTFOUND package-firewall.replit.local; the proxy host only exists inside Replit.
**How to apply:** before every review/handoff that added a JS dependency; verify grep count is 0 and `yarn install` + CI build exit 0.
