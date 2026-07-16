---
name: Global IP rate limiter shadows endpoint throttles
description: App-wide unauthenticated per-IP limiter fires before any module-level throttle on public endpoints.
---
The backend has an app-wide middleware rate limiter: 30 req/min per IP for unauthenticated requests (300/min per user), Mongo-backed in `otp_rate_limits` (kind `global_ip`), so counts persist across process restarts.

**Why:** A probe bursting a public endpoint saw 429s far earlier than the endpoint's own 60/min throttle — the global limiter fires first, and leftover Mongo counters from prior runs make "fresh" bursts fail at request 0.

**How to apply:** When probing/rate-testing public endpoints, first `delete_many({"kind": "global_ip"})` on `otp_rate_limits`; test module throttles as unit calls, and treat any burst 429 as valid defense-in-depth. Also clean up probe-seeded users/docs (fixed phone numbers collide with unique indexes on reruns).
