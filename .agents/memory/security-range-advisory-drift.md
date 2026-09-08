---
name: Security range vs advisory drift
description: How to handle a security-upgrade specification whose approved version ceiling no longer clears the current advisory database.
---

If the latest version inside an approved major/minor ceiling still has current advisories and the published fixes are outside that ceiling, keep the approved version, report the gate as blocked, and request a separate decision to widen the range. Do not hide or ignore the findings to make the audit appear green.

**Why:** Vulnerability databases change after a specification is written. A previously sufficient target can become incapable of satisfying a “no findings” requirement while still obeying its version constraint.

**How to apply:** Re-check package indexes and the live advisory database immediately before editing. Record both the allowed ceiling and every published fix version in the review evidence.