---
name: Floor payment semantics
description: Product rule for cast-floor and concrete-per-floor contractor payments
---

A stage may be paid per floor instead of per apartment. The floor's payable share is the mean of its apartments' completion shares, excluding apartments marked not relevant. Support both a lump sum per floor and quantities per floor with floor-specific exceptions.

**Why:** The user's specification says skeleton contractors may be paid for a cast floor or concrete quantity per floor; seven completed apartments out of ten count as 0.7 floors.

**How to apply:** Keep this calculation within contract items. Preserve the existing monthly-account engine, partial-share rules, previous-account differences, matrix and QC behavior.
