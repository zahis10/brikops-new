---
name: Partial apartment payment rules
description: Approved product semantics for fractional apartment-stage payments
---

The payment percentage belongs in the execution matrix, not in an independent monthly-account input. An apartment-stage is worth at most 100%; monthly accounts pay only the difference from earlier paid shares, including negative corrections when the share decreases.

**Why:** The user wants to release part of an apartment's agreed amount now and the remainder later without paying twice.

**How to apply:** Completed means 100%; not_done/not_relevant mean zero; intermediate QC states preserve the stored partial share. Partial changes enter the applying month, or any month before the first account closure. Preserve these semantics when adding the frontend or extending account calculations.
