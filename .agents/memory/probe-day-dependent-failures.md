---
name: Day-dependent safety probe failures
description: WhatsApp reminder/alert probes fail on Fri/Sat due to user reminder-day prefs and Shabbat guards; leftover collection docs also break count-based checks.
---
- The reminder-prefs day gate (skip reason `day_N_not_in_user_days`) skips sends when the Israel weekday (0=Sun..5=Fri) isn't in the user's reminder days; defaults exclude Friday, so alert-send probes (e.g. w1_alerts) fail on Fridays with `sent: 0, skipped: N`.
- **Why:** wasted a debugging cycle suspecting a regression when no reminder code was touched; the Shabbat guard (Fri≥14:00 IL, Sat) is a separate second gate.
- **How to apply:** before treating alert-probe failures as regressions, check the `[SAFETY-EXPIRY]`/reminder skip-reason logs and the Israel weekday. Rerun Sun–Thu or seed users with all-days prefs.
- Also: probes asserting "0 docs" in shared collections (e.g. induction_content_snapshots) fail on leftovers from earlier runs — clean the collection first.
