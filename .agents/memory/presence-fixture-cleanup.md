---
name: Presence fixture cleanup
description: Ordering browser shutdown and local presence-fixture restoration
---
Close all test browser contexts before restoring backed-up last-seen fields and deleting temporary presence records. Deleting the session file or restoring a non-admin role does not stop a browser that already holds a token.

**Why:** An open admin activity page recreated a just-deleted hourly bucket during cleanup. Authentication stamps presence before the endpoint rejects the user's restored non-admin role, so a 403 is not evidence that polling is side-effect-free.

**How to apply:** Capture screenshots, close the browser, then restore exact auth/presence preimages and verify zero fixture counts. Existing live probes written before hourly tracking may also need external cleanup of buckets for their exact synthetic user IDs without modifying the probe.