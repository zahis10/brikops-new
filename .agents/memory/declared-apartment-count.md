---
name: Declared apartment count
description: Product rule for permit-based apartment quantity and trial corrections.
---

The declared apartment count is the building-permit quantity and remains the sole cap and pricing basis. Never auto-extend it. During trial, an authorized structure administrator may explicitly confirm an increase, with an audit record. Product updates must strictly increase the current declaration: equal or lower values are rejected. Lowering is admin-only. Outside trial, retain the admin quota-request path. The wizard must stop before creating a building when its projected apartment count exceeds the declaration.

**Why:** The user rejected allowing trial users to freely expand structures and quantities; they must verify the actual permit quantity instead. The upward-only payment policy prevents raising quantities and lowering them before month-end. A quota error must not leave the user with a building and floors but no apartments.

**How to apply:** Preserve this distinction in future building-wizard and quota changes; do not replace explicit confirmation with automatic extension.

Trial declaration increases may synchronize billing only when the contracted quantity is None, zero, or equal to the previous declaration. A different contracted quantity is an admin agreement and must remain unchanged. Billing synchronization failure must not fail the declaration update; report synchronization status and contracted quantity in the audit and response.

**Why:** Trial creation can already create billing records with the initial declaration; leaving those unchanged undercharges after an increase. The user explicitly approved this bounded synchronization while protecting separately agreed quantities.

**How to apply:** Use existing billing update and organization recalculation helpers, without changing billing calculation policy.
