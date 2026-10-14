---
name: Declared apartment count
description: Product rule for permit-based apartment quantity and trial corrections.
---

The declared apartment count is the building-permit quantity and remains the sole cap and pricing basis. Never auto-extend it. During trial, an authorized structure administrator may explicitly confirm an increase, with an audit record. Product updates must strictly increase the current declaration: equal or lower values are rejected. Lowering is admin-only. Outside trial, retain the admin quota-request path. The wizard must stop before creating a building when its projected apartment count exceeds the declaration.

**Why:** The user rejected allowing trial users to freely expand structures and quantities; they must verify the actual permit quantity instead. The upward-only payment policy prevents raising quantities and lowering them before month-end. A quota error must not leave the user with a building and floors but no apartments.

**How to apply:** Preserve this distinction in future building-wizard and quota changes; do not replace explicit confirmation with automatic extension.
