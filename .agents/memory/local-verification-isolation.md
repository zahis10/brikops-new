---
name: Local verification isolation
description: Avoid accidentally verifying published UI when a local server redirects or sends restrictive CSP
---

Browser route interception alone does not prove that frontend assets stayed local: a route-fetch helper may follow a canonical redirect outside the interception handler.

**Why:** A local staging verification displayed a published bundle despite local API interception, producing misleading guard failures.

**How to apply:** Disable canonical redirects only in the disposable runtime, prohibit redirects in forwarding clients, and verify the actual script fingerprint against local build output. If CSP blocks a preserved cross-origin API target, document any browser-only bypass and keep outbound routing constrained; do not call that a production CSP test.

Temporary snapshots can disappear during an environment restart while Mongo persists.

**Why:** A restart erased the original verification snapshot, making an exact comparison with that baseline impossible.

**How to apply:** Never claim that lost comparison succeeded. Remove only clearly fixture-owned recovery data, take a new clean baseline before any replacement fixture work, and state precisely which baseline was compared.