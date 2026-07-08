---
name: Draft-only mutation race pattern
description: Status-gated writes must re-assert the status inside the update filter, not just at read time
---
Rule: For any "only while status X" mutation (draft-only PATCH, unsigned-only sign, etc.), the status guard must live INSIDE the `update_one` filter (`{..., "status": "draft"}`), with `matched_count == 0` → 409. A read-time check alone leaves a read→write race window.

**Why:** Architect review of the work-diary batch caught exactly this: PATCH/refresh checked "signed" at read time, so a concurrent signer between read and write could mutate a just-signed (legally immutable) record.

**How to apply:** Every state-transition or state-gated write in this codebase should follow the atomic-claim pattern (filter re-asserts the precondition; 0 matches → deterministic localized 409). Lock it with a probe that feeds a stale snapshot to the handler while the DB doc is already in the terminal state.
