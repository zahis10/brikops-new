---
name: Mongo partial-index null limits
description: Why soft-delete uniqueness uses a compound index instead of partialFilterExpression
---
Rule: MongoDB `partialFilterExpression` cannot express `{deletedAt: null}` (equality to null is rejected). For "unique among active docs" with a soft-delete field, use a compound unique index that INCLUDES the soft-delete field, e.g. `(scope_id, natural_key, deletedAt)`.

**Why:** All active docs carry `deletedAt: None` → uniqueness among active is exact. Deleted docs get distinct timestamps, so they don't collide.

**How to apply:** Pair the index with (1) a friendly pre-check returning a localized 409, and (2) a `DuplicateKeyError` catch mapping to the same 409 (the index closes the pre-check race). Caveat: if two docs could be deleted at the exact same timestamp with the same key, revisit — safe when there is no delete path or deletes are rare.
