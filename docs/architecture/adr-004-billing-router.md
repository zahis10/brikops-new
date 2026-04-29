# ADR-004 — billing_router.py

**Status:** Accepted
**Date:** 2026-04-29
**File:** `backend/contractor_ops/billing_router.py` (2068 lines as of 2026-04-29)

## Why this exists

`billing_router.py` is the **HTTP surface** of the billing system —
endpoints for plan listing, plan switching, invoice retrieval, the
PayPlus webhook, the GI (government identity) verification webhook,
and the cron-triggered renewal job. The **business logic** lives in
the sibling `billing.py` (2200 lines) — `billing_router.py` just wires
the FastAPI endpoints to that logic, plus auth and request shaping.

The file is large because billing has many surfaces:
- Per-user billing summary (`/billing/me`)
- Per-org billing summary (`/billing/org/{org_id}`)
- Plan listing (active plans, available plans, founder eligibility)
- Plan switch endpoints (with locked-until logic)
- PayPlus checkout-create + webhook + status check
- GI verification webhook (S5a/S7-C — CompanyHouse / IRS-style ID
  validation gate)
- Project license create/update/cancel
- Cron jobs (`/cron/billing/...`) protected by `CRON_SECRET`
- Super-admin overrides on every endpoint

PayPlus's webhook contract requires signature verification + idempotent
handling, and the GI gate has a deliberate **fail-open** semantic
(GI failure does NOT block subscription activation, just flags it for
manual review). Both invariants are tricky enough that splitting before
documenting the WHY risks silently breaking activations.

## Architectural decisions

- **Decision: split surface from logic.** `billing_router.py` is
  endpoints + auth; `billing.py` is helpers like `get_billing_info`,
  `check_org_billing_role`, `check_org_pm_role`,
  `is_founder_enabled`. Why: the same business function gets called
  from cron, webhook, and user-facing endpoints — keeps logic in one
  place.
- **Decision: every billing endpoint has a `BILLING_V1_ENABLED` gate.**
  Why: feature flag for staged rollout. When the flag is off, the
  endpoint returns 404 (looks unimplemented) rather than 403 (looks
  forbidden) — avoids leaking the existence of the feature.
- **Decision: `check_org_billing_role()` is the auth helper for every
  org-billing endpoint.** Defined in `billing.py:532`. Returns the
  user's billing role (`org_admin`, `billing_admin`, `owner`, or
  `None`). Endpoints fall back to `check_org_pm_role()` for
  read-only views. **Never inline this auth check** — the role
  hierarchy has changed twice and inlining caused 5C-era 403 bugs.
- **Decision: GI failure is non-blocking (S5a/S7-C pattern).** When a
  payment succeeds but GI verification fails or times out, the
  subscription is activated and a flag (`gi_status: "manual_review"`)
  is set. Why: blocking on GI would lose paying customers due to a
  third-party outage. Trade-off: super-admin sees a manual-review
  queue.
- **Decision: PayPlus webhook is idempotent via
  `payplus_webhook_log` collection.** Every incoming webhook is keyed
  on `payplus_transaction_id + event_type`; duplicates are no-ops.
  Why: PayPlus retries failed webhooks aggressively — without
  idempotency, double-charges or double-activations would occur.
- **Decision: invoice creation is asynchronous to checkout.**
  Checkout returns once PayPlus confirms the charge; invoice document
  is created on the webhook handler. Why: keeps the user-facing
  checkout latency low (no synchronous PDF generation in the request
  path).
- **Decision: cron router is separate (`cron_router`)**, mounted on a
  different prefix without the `/api` namespace, protected by
  `CRON_SECRET` header. Why: separation of concerns — cron jobs are
  internal infrastructure, not part of the public API surface.
- **Decision: founder slot logic at line 81-117**. The "founder_6m"
  plan has a hard cap (`FOUNDER_MAX_SLOTS`) and gets disabled once
  reached, OR if the org has too many projects, OR if the org has
  prior payment history. Why: founder pricing is a one-time launch
  promotion; the logic is co-located here so eligibility is computed
  in the same place plan-availability is reported.

## Conventions used here

- Routes prefixed `/api` (user-facing), `cron_router` separately.
- Every endpoint validates `_is_super_admin(user)` first as an
  override gate; super-admins bypass org-membership checks.
- Org-membership checks use `check_org_billing_role()` —
  never inline.
- `BILLING_V1_ENABLED` flag-check at the top of each endpoint.
- All money values stored in **agorot** (1 ILS = 100 agorot) as
  integers — never floats. PayPlus and invoicing both expect ints.
- Webhook handlers return 200 even on duplicate events (idempotency
  via `payplus_webhook_log` / `gi_webhook_log`).
- All audit writes via `_audit()` for every plan-change / activation /
  cancellation.

## Natural seams (where to split if/when refactor happens)

- **PayPlus webhook + checkout endpoints**. Could move to
  `payplus_router.py`. **~500 lines saved.** This is the most natural
  split — payment-provider-specific code that would change wholesale
  if we added a second processor.
- **GI verification endpoints**. Could move to `gi_router.py`.
  **~250 lines saved.** Same logic — third-party-specific.
- **Cron router**. Already separate as `cron_router` in this file but
  could live in its own `billing_cron_router.py`. **~200 lines saved.**
- **Founder-eligibility helper** (line 102-117). Could move to
  `billing.py` next to `is_founder_enabled()`. **~50 lines saved.**

## When to refactor

- **Trigger:** when adding a second payment processor (e.g. Stripe
  for international markets). The PayPlus webhook handler would need
  to become one of N processor handlers, and that's the right moment
  to extract `payplus_router.py`.
- **Trigger:** when GI verification is replaced or augmented by a
  different verification provider (currently a single hardcoded
  endpoint).
- **Pre-requisite:** integration test for the full
  checkout → webhook → activation → invoice flow. Today this is
  validated manually on staging via Zahi's smoke test card.
- **Pre-requisite:** ledger of every billing-state field across
  `subscriptions`, `invoices`, `project_billing` so the split doesn't
  lose any.

## Recent changes

- 2026-04-29 (BATCH 5I): No change here. The org-billing back-button
  fix was on `OrgBillingPage.js` (frontend).
- 2026-04 (BATCH 4 series): Founder plan + GI gate shipped.
- 2026-Q1 (M6): Per-org billing dashboard, project-license model.
- 2025-Q4 (M5): PayPlus integration first shipped.

## Related files

- `backend/contractor_ops/billing.py` — business logic
  (`get_billing_info`, `check_org_billing_role`,
  `is_founder_enabled`, etc.). 2200 lines; deserves its own ADR
  when next touched.
- `backend/contractor_ops/billing_plans.py` — plan catalog
  (`PROJECT_LICENSE_FIRST`, `PROJECT_LICENSE_ADDITIONAL`,
  `PRICE_PER_UNIT`).
- `backend/contractor_ops/invoicing.py` — invoice PDF generation.
- `backend/services/pdf_service.py` — generic PDF builder used by
  invoicing.

## Refactor backlog items touching this file

- `#15` (low) Future ADR for `billing.py` (2200 lines, sibling to this
  router).
- `#16` (low) Future split of PayPlus webhook into `payplus_router.py`
  when a second payment processor is added.

See [`../refactor-backlog.md`](../refactor-backlog.md) for full details.
