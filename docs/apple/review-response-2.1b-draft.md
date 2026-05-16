# Apple App Review Response — Guideline 2.1(b) Information Needed

**Submission ID:** afa8bee9-b5f3-49bd-a0e4-a767940196da
**Review Date:** April 22, 2026
**Version:** 1.0
**Status:** Information requested (NOT a rejection)

---

## Where to paste the reply

App Store Connect → Apps → BrikOps → iOS App → left sidebar "App Review" → **Resolution Center** → find the review message → click **Reply** → paste the English text below.

---

## Reply text (English — paste this)

Hi Apple Review Team,

Thank you for the opportunity to clarify. BrikOps is a B2B SaaS tool for Israeli construction companies — on-site defect tracking, QC inspections, and apartment handover — comparable to Procore or PlanGrid. Operated by Zahi Shami, an Israeli licensed sole proprietor (עוסק מורשה, ID 203004767).

**1. Who are the paying users?**
Employees of construction companies — contractors, project managers, QC inspectors, site supervisors. Not consumers. Individual employees never pay; their employer pays an organization-level subscription.

**2. Where is the purchase made?**
Exclusively outside the iOS app. Organization admins purchase on our web app (https://app.brikops.com) and are redirected to an external PayPlus payment page (https://payments.payplus.co.il) for credit-card payment billed to the BrikOps operator. The iOS app has no StoreKit, no pricing, no "Buy" button, and does not link to the PayPlus page.

**3. What can users access in the app?**
Work data owned by their employer: projects, defect/QC tickets assigned to them, handover protocols, plans, report exports, and team activity. Only business productivity content — no consumer media, entertainment, or digital goods.

**4. What features are unlocked without IAP?**
The full SaaS feature set (defects, QC, handover, reports, exports) is gated by the employer's per-project subscription, billed monthly and paid on the external PayPlus page as in #2. Employees never see a paywall in the iOS app. This falls under **Guideline 3.1.3(a) — Business Services**, the same exemption used by Procore, Monday, Slack, and Asana.

**5. How do users obtain an account? Is there a signup fee?**
Free. The only mandatory step is verifying an Israeli mobile phone number via SMS OTP, required for legal attribution of on-site construction records. A phone number alone is sufficient to sign up and log in; optionally, a user may also link email + password, Sign in with Google, or Sign in with Apple as an additional login method. Every new organization gets an automatic 7-day free trial with full access. After the trial, the admin may pay via PayPlus for a new project or not — in either case, all existing project data is preserved (construction defect records carry legal and warranty weight for our customers). Employees are added by their admin and never see a paywall.

A demo account is available (see App Review notes).

Best regards,
Zahi Shami
Operator of BrikOps (Israeli עוסק מורשה, ID 203004767)

---

## Facts to verify before sending

| # | Claim | Verify |
|---|---|---|
| 1 | No IAP in iOS app | Search iOS project for `StoreKit`, `SKPaymentQueue`, `SKProduct` — should be zero results |
| 2 | No "Buy" button in iOS app | Check `PaywallModal.js` behavior on iOS — does it show pricing or just a "upgrade on web" message? |
| 3 | Free trial exists | Confirm in backend billing logic |
| 4 | Demo account already submitted | Verify in App Store Connect → App Information → Review Notes |

---

## Timeline

- Apple typically responds within 24-48 hours after you reply in Resolution Center.
- If they accept the explanation, review continues and you get approval within ~1-3 days.
- If they push back, they'll ask more specific questions — usually about IAP compliance. We respond again.

**Do NOT submit a new build** unless Apple asks you to. The reply is sufficient — the build already uploaded is fine.
