# BrikOps — Demo & Reviewer Access Guide

This document provides demo account credentials and review instructions for
Apple App Store, Google Play Store, and internal demo reviewers.

> **Security note:** Replace `<DEMO_PASSWORD>` placeholders below with the actual
> password configured in the `DEMO_DEFAULT_PASSWORD` environment variable before
> submitting to reviewers.

---

## Demo Accounts

| Email | Role | Purpose |
|---|---|---|
| `demo-pm@brikops.com` | Project Manager | Full project management: create/edit defects, assign contractors, approve work, manage QC, view billing |
| `demo-team@brikops.com` | Management Team (Site Manager) | Supervisory view: review defects, submit/approve QC stages, view project progress |
| `demo-contractor@brikops.com` | Contractor (Electrical) | Contractor perspective: see assigned defects, update status, submit proof of work |
| `demo-viewer@brikops.com` | Viewer | Read-only access: browse project, view defects and QC status without edit permissions |

**Password for all accounts:** `<DEMO_PASSWORD>`

---

## Demo Environment Contents

The demo organization ("חברת הדגמה") contains pre-seeded data:

- **1 project** — "פרויקט מגדלי הדמו" (Demo Towers Project)
- **2 buildings** — Building A, Building B
- **6 floors** — 3 per building
- **30 apartments** — 5 per floor
- **16 defects** — in various statuses (open, assigned, in progress, pending approval, closed)
- **3 contractor companies** — electrical, plumbing, flooring
- **QC execution data** — quality control checklists with mixed progress across floors
- **Billing** — Professional plan configured with 30 units

---

## Recommended Review Path

### As Project Manager (`demo-pm@brikops.com`)
1. Open the app and log in with email/password
2. Tap the demo project "פרויקט מגדלי הדמו"
3. Browse buildings and floors — tap into Building A
4. View defects list — observe mixed statuses and Hebrew descriptions
5. Tap a defect to see details (category, priority, assignment, timeline)
6. Navigate to QC section — view floor-level quality checklists with progress badges
7. Check billing/subscription from organization settings

### As Contractor (`demo-contractor@brikops.com`)
1. Log in — observe the contractor-specific view
2. See assigned electrical defects
3. View defect details and assignment status

### As Viewer (`demo-viewer@brikops.com`)
1. Log in — observe the read-only interface
2. Browse the same project data without edit controls

---

## Environment Setup (for deployment teams)

Required environment variables when `ENABLE_DEMO_USERS=true`:

| Variable | Required in Production | Description |
|---|---|---|
| `ENABLE_DEMO_USERS` | Yes (set to `true`) | Enables demo account seeding |
| `DEMO_DEFAULT_PASSWORD` | **Yes** (must be explicit) | Password for all demo accounts. In non-dev environments, the server will refuse to seed demo accounts if this is not explicitly set. |
| `DEMO_RESET_PASSWORDS` | No (default: `false`) | Set to `true` to force-reset demo passwords on restart |

---

## App Store Submission — Copy-Paste Text

### Apple App Store Connect

**Location:** App Store Connect → App → App Review Information → Sign-in required

**Demo Account — Full Name or Email:**
```
demo-pm@brikops.com
```

**Demo Account — Password:**
```
<DEMO_PASSWORD>
```

**Notes for Reviewer:**
```
BrikOps is a construction project management app for Israeli building contractors.

To review the app:
1. Log in using the email and password above (the login page opens on the Email/Password tab)
2. After login, tap the demo project "פרויקט מגדלי הדמו"
3. Browse buildings, floors, and apartments
4. View defects (construction issues) in various statuses
5. Check the QC (Quality Control) section for floor-level checklists

The app UI is in Hebrew (right-to-left). All demo data is pre-loaded — no additional setup is needed.

Additional demo accounts are available:
- demo-contractor@brikops.com (contractor view)
- demo-viewer@brikops.com (read-only view)
All accounts use the same password.
```

---

### Google Play Console

**Location:** Play Console → App → App access → Add instructions

**Instructions for Reviewers:**
```
BrikOps is a construction project management app.

Login credentials:
- Email: demo-pm@brikops.com
- Password: <DEMO_PASSWORD>

Steps to review:
1. Open the app — the login page defaults to Email/Password
2. Enter the credentials above and tap "כניסה" (Login)
3. Tap the demo project "פרויקט מגדלי הדמו"
4. Browse buildings, defects, and QC checklists
5. All demo data is pre-loaded in Hebrew

Additional accounts:
- demo-contractor@brikops.com (contractor view)
- demo-viewer@brikops.com (read-only view)
Same password for all accounts.
```
