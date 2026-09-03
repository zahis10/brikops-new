---
name: Spare-profile write serialization
description: Why spare-profile settings and unit assignments use a strict non-expiring per-project mutex.
---

Serialize spare-profile settings writes and unit-assignment writes with the same
strict per-project mutex. Do not replace it with an expiring or automatically
stolen lease unless the replacement provides true atomic fencing or database
transactions across both project and unit mutations.

**Why:** Profile deletion and assignment touch different Mongo collections.
An expiring lease leaves a pause-after-ownership-check window where a stale
writer can resume after a successor and create dangling assignments. The chosen
tradeoff prioritizes data integrity; a hard crash can leave an abandoned mutex
that needs explicit operational recovery.

**How to apply:** Any future write path that creates, removes, or assigns spare
profiles must take the same project mutex and reload authoritative state after
acquisition. Safe automatic recovery requires proving the old writer cannot
resume, not merely checking lock age.