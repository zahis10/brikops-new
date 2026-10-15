---
name: Defect AI rollout
description: Product intent and accepted first-paint limitation of the platform AI switch.
---
The user says defect AI mode is not ready; the platform default must be classic mode, with a super-admin switch enabling AI for everyone.
**Why:** The user wants controlled availability without deploying.
**How to apply:** Do not enable the flag or remove the classic default as part of unrelated work.

The approved behavior retains the context fallback before the per-open request resolves, without resetting the live value on each open or adding a strict loading gate.
**Why:** The user explicitly approved this tradeoff despite the temporary stale-enabled window.
**How to apply:** Report that the window can recur when the modal remounts; never describe it as limited to once per login. A stricter first-paint guarantee requires separate approval.
