# BrikOps — Project Overview

**Last updated:** March 11, 2026

## Table of Contents
1. [Directory Tree](#directory-tree)
2. [Architecture Summary](#architecture-summary)
3. [Tech Stack](#tech-stack)
4. [API Endpoints](#api-endpoints)
5. [MongoDB Collections & Schemas](#mongodb-collections--schemas)
6. [Known Bugs & Issues](#known-bugs--issues)
7. [Planned Features](#planned-features)
8. [Recent Changes](#recent-changes)

---

## Directory Tree

```
brikops/
├── PROJECT_OVERVIEW.md
├── replit.md
├── README.md
├── RELEASE_NOTES.md
├── pyproject.toml
├── main.py
├── deploy.sh
├── build.sh
├── run.sh
├── design_guidelines.json
├── .platform/
│   └── nginx/conf.d/proxy.conf         # EB Nginx: client_max_body_size 20M
│
├── backend/
│   ├── server.py                        # FastAPI app, middleware, SPA serving, startup init
│   ├── config.py                        # All env vars, SA phone parsing, feature flags
│   ├── models.py                        # Extended model definitions
│   ├── models_extended.py               # Additional model schemas
│   ├── seed_data.py                     # Demo/seed data definitions
│   ├── start.sh / run.sh / build.sh     # Boot scripts
│   │
│   ├── contractor_ops/                  # Core application modules
│   │   ├── router.py                    # Shared helpers, auth middleware, notification endpoints (~552 lines)
│   │   ├── schemas.py                   # Pydantic models (UserCreate, UserLogin, UserResponse, Role, etc.)
│   │   ├── seed.py                      # Database seeding logic
│   │   │
│   │   │── # ── Sub-routers (all prefix="/api") ──
│   │   ├── auth_router.py              # 7 auth endpoints (register, login, dev-login, get_me, logout-all, change-phone)
│   │   ├── onboarding_router.py        # 18 onboarding/registration endpoints (OTP, phone login, join requests, forgot/reset password)
│   │   ├── tasks_router.py             # 14 task endpoints (CRUD, assign, status, proof, manager-decision, updates, attachments, feed)
│   │   ├── projects_router.py          # 18 project/building/floor/unit endpoints + hierarchy, bulk ops, resequence
│   │   ├── admin_router.py             # 20 admin endpoints (stepup, billing admin, user management, role changes)
│   │   ├── billing_router.py           # 27 billing/org endpoints (plans, checkout, payment requests, invoices, billing-contact)
│   │   ├── invites_router.py           # 7 invite/user/contractor-profile endpoints
│   │   ├── companies_router.py         # 9 company/trade endpoints + _slugify_hebrew helper
│   │   ├── stats_router.py             # 6 stats/dashboard/membership endpoints
│   │   ├── config_router.py            # 1 public endpoint (/api/config/features, no auth)
│   │   ├── debug_router.py             # 20 debug/health/admin endpoints (SA-gated except /health)
│   │   ├── export_router.py             # 3 defects export endpoints (Excel + PDF)
│   │   ├── excel_router.py             # 3 excel import/export endpoints
│   │   ├── plans_router.py             # 7 plans/disciplines endpoints
│   │   ├── task_image_guard.py         # Image validation middleware for task attachments
│   │   ├── identity_router.py          # 5 identity/account endpoints (account-status, complete-account, change-password)
│   │   ├── archive_router.py           # 9 archive/restore endpoints (buildings, floors, units)
│   │   ├── qc_router.py                # 18 QC (quality control) endpoints
│   │   ├── notification_router.py      # 5 notification/webhook endpoints
│   │   ├── member_management.py        # 5 member management endpoints
│   │   ├── ownership_transfer.py       # 6 ownership transfer endpoints
│   │   ├── wa_login.py                 # 4 WhatsApp login endpoints
│   │   │
│   │   │── # ── Services & Logic ──
│   │   ├── notification_service.py     # WhatsApp/SMS notification logic, template resolution
│   │   ├── identity_service.py         # Identity/account management logic
│   │   ├── billing.py                  # Billing business logic
│   │   ├── billing_plans.py            # Billing plan definitions & tier configs
│   │   ├── invoicing.py                # Invoice generation logic
│   │   ├── otp_service.py              # OTP generation/verification
│   │   ├── stepup_service.py           # Step-up authentication service
│   │   ├── sms_service.py              # SMS sending (Twilio)
│   │   ├── phone_utils.py              # Phone normalization (E.164, Israeli mobile)
│   │   ├── bucket_utils.py             # Task categorization/bucketing
│   │   ├── msg_logger.py               # Message logging utility
│   │   │
│   │   │── # ── Tests ──
│   │   ├── test_e2e.py
│   │   ├── test_invites.py
│   │   ├── test_notifications.py
│   │   ├── test_onboarding.py
│   │   ├── test_phone_normalization.py
│   │   ├── test_phone_normalization_e2e.py
│   │   ├── test_audit_immutability.py
│   │   ├── test_cross_project_rbac.py
│   │   └── test_e2e_invite_proof.py
│   │
│   ├── services/                        # Infrastructure services
│   │   ├── object_storage.py            # Dual backend: local FS or AWS S3 (s3v4 + virtual addressing)
│   │   ├── pdf_service.py               # PDF report generation
│   │   ├── enhanced_pdf_service.py      # Enhanced PDF with citations (v1)
│   │   ├── enhanced_pdf_service_v2.py   # Enhanced PDF v2
│   │   ├── pdf_template_service.py      # PDF template management
│   │   ├── ai_service.py               # AI service (OpenAI/Google GenAI)
│   │   ├── audit_service.py            # Audit logging service
│   │   ├── document_vault_service.py   # Document vault (scaffolded)
│   │   └── regulation_service.py       # Regulation compliance (scaffolded)
│   │
│   ├── scripts/                         # Utility/migration scripts
│   │   ├── backfill_password_hash.py
│   │   ├── backup_restore.py / .sh
│   │   ├── normalize_phones.py
│   │   ├── identity_audit.py
│   │   └── ...
│   │
│   ├── reports/                         # Demo/test report JSON files
│   └── schemas/                         # JSON schemas
│       └── report_schema.json
│
├── frontend/
│   ├── package.json
│   ├── craco.config.js                  # CRA override config (path aliases)
│   ├── tailwind.config.js               # TailwindCSS configuration
│   ├── postcss.config.js
│   ├── jsconfig.json
│   ├── .env                             # REACT_APP_BACKEND_URL (empty = relative for dev)
│   │
│   ├── public/
│   │   └── index.html
│   │
│   └── src/
│       ├── App.js                       # Root component, routing, ProtectedRoute
│       ├── App.css / index.css          # Global styles
│       ├── index.js                     # Entry point
│       ├── setupProxy.js               # Dev proxy (/api → localhost:8000)
│       │
│       ├── services/
│       │   └── api.js                   # Centralized API client (axios), BACKEND_URL export
│       │
│       ├── contexts/
│       │   ├── AuthContext.js           # Auth state, token management
│       │   └── BillingContext.js        # Billing state, paywall
│       │
│       ├── i18n/
│       │   ├── index.js                # Translation loader
│       │   ├── he.json                 # Hebrew translations
│       │   └── en.json                 # English translations
│       │
│       ├── components/
│       │   ├── ui/                     # shadcn/ui primitives (button, card, dialog, etc.)
│       │   ├── CameraModal.js          # Inline camera capture (iOS-compatible)
│       │   ├── NewDefectModal.js        # Defect creation wizard (3-step: create→upload→assign)
│       │   ├── ExportModal.js           # Defects export (Excel/PDF format selector)
│       │   ├── FilterDrawer.js          # Slide-out filter panel (collapsible sections)
│       │   ├── UpgradeWizard.js         # Billing upgrade wizard
│       │   ├── ProjectBillingEditModal.js
│       │   ├── ProjectBillingCard.js
│       │   ├── WhatsAppRejectionModal.js
│       │   ├── QCApproversTab.js
│       │   ├── NotificationBell.js
│       │   └── ...
│       │
│       ├── pages/
│       │   ├── LoginPage.js            # Email/Phone login, demo quick access
│       │   ├── RegisterPage.js
│       │   ├── OnboardingPage.js        # Phone-first onboarding flow
│       │   ├── AdminPage.js             # SA admin panel
│       │   ├── AdminUsersPage.js
│       │   ├── ProjectDashboardPage.js
│       │   ├── ProjectTasksPage.js
│       │   ├── TaskDetailPage.js        # Task detail with proof gallery, notification history
│       │   ├── UnitDetailPage.js
│       │   ├── UnitHomePage.js
│       │   ├── FloorDetailPage.js       # Smart back navigation
│       │   ├── InnerBuildingPage.js     # Building workspace (3-tab, KPI, add-floor/unit)
│       │   ├── BuildingQCPage.js        # Building-scoped QC floor selection
│       │   ├── BuildingDefectsPage.js   # Building-level defect list (V2, feature-flagged)
│       │   ├── ApartmentDashboardPage.js # Unit-level defect dashboard (V2, feature-flagged)
│       │   ├── ContractorDashboard.js
│       │   ├── OrgBillingPage.js
│       │   ├── StageDetailPage.js       # QC stage inspection
│       │   ├── QCFloorSelectionPage.js  # Rewritten as building selector for QC
│       │   ├── ProjectPlansPage.js      # Refreshed: dark header, discipline chips, search
│       │   ├── UnitPlansPage.js         # Refreshed: matches ProjectPlansPage design
│       │   ├── MyProjectsPage.js
│       │   ├── ProjectControlPage.js    # 4-tab work switcher, amber palette, RTL
│       │   ├── JoinRequestsPage.js
│       │   ├── PhoneLoginPage.js
│       │   ├── WaLoginPage.js
│       │   ├── ForgotPasswordPage.js
│       │   ├── ResetPasswordPage.js
│       │   ├── PendingApprovalPage.js
│       │   ├── RegisterManagementPage.js
│       │   └── OwnershipTransferPage.js
│       │
│       └── utils/
│           ├── phoneUtils.js           # Client-side phone normalization
│           ├── formatters.js           # Display formatters
│           ├── navigation.js           # Navigation helpers
│           ├── billingHub.js / billingLabels.js / billingPlanCatalog.js
│           ├── roleLabels.js / actionLabels.js
│           ├── qcLabels.js / qcVisualStatus.js
│           └── ...
│
├── Proof/audit markdown files
│   ├── FINAL_UAT_PROOF.md
│   ├── HANDOFF.md
│   ├── GO_LIVE_WHATSAPP.md
│   ├── ATLAS_SETUP.md
│   ├── INVITE_PROOF.md
│   ├── PROOF_PACKAGE.md
│   ├── PROOF_SECURITY.md
│   └── ...
│
└── brikops-source.zip                   # Project source archive
```

---

## Architecture Summary

### Overview
BrikOps is a full-stack construction task management platform with Hebrew RTL UI. It features strict RBAC, a defined task lifecycle with status transitions, multi-channel notifications (WhatsApp + SMS), billing/subscription management, and quality control workflows.

### Runtime Modes

| Mode | Frontend | Backend | Database |
|------|----------|---------|----------|
| **Replit (dev)** | Pre-built static files served by backend on port 5000 | FastAPI/Uvicorn on port 5000 | Local MongoDB on 27017 |
| **Production** | Cloudflare Pages (`app.brikops.com`) | AWS Elastic Beanstalk Docker (`api.brikops.com`) | MongoDB Atlas |

### Key Architecture Decisions
- **Single-process dev mode**: Backend serves both API (`/api/*`) and pre-built frontend static files
- **API base URL centralized**: `frontend/src/services/api.js` is the single source of truth; all other files import `BACKEND_URL` from it
- **Dev mode**: `REACT_APP_BACKEND_URL` is empty → relative URLs (`/api/...`) → same origin → local backend
- **Production**: Cloudflare Pages sets `REACT_APP_BACKEND_URL=https://api.brikops.com` at build time
- **Canonical redirect**: `server.py` middleware redirects non-canonical hosts to `PUBLIC_APP_URL` in production; skipped in dev mode (`APP_MODE=dev`)
- **Sub-router architecture**: Main `router.py` contains shared helpers/auth; 15+ sub-routers handle domain-specific endpoints

### Authentication Flow
1. Email/password login → JWT token (HS256, issuer enforcement, secret versioning)
2. Phone OTP login → WhatsApp or SMS OTP → JWT token
3. WhatsApp Magic Link → one-time token → JWT token
4. Dev-only: `POST /api/auth/dev-login` with role name

### Super Admin Detection
- `SUPER_ADMIN_PHONES` (plural) or `SUPER_ADMIN_PHONE` (singular) env var, comma-separated
- Phones normalized to E.164 via `normalize_israeli_phone()` at startup
- `is_super_admin_phone()` normalizes incoming phone before comparison; returns `{matched, norm, reason}` (no raw fallback)
- `[SA_PHONES]` startup log shows count + source + masked phones
- `[SA_CHECK]` log on every login shows `user_phone_raw`, `norm`, `matched`, `list_count`, `source`

### WhatsApp Notification System
- Meta WhatsApp Cloud API v21.0
- Template names configurable via ENV: `WA_DEFECT_TEMPLATE_HE/EN/AR/ZH` (v1 defaults)
- Body params order: `{{1}}=ref, {{2}}=location, {{3}}=issue`
- `WA_TEMPLATE_PARAM_MODE`: `named` (v1 compat) or `positional` (v2)
- Login template: `WA_LOGIN_TEMPLATE_HE` env var (default: `brikops_login_link_he`)
- Fallback image: S3 presigned URL generated at send time
- All links use `PUBLIC_APP_URL=https://app.brikops.com`

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | Python FastAPI |
| Server | Uvicorn (ASGI) |
| Database | MongoDB (Motor async driver) |
| Auth | JWT (HS256, PyJWT), OTP (WhatsApp/SMS) |
| File Storage | AWS S3 (boto3, s3v4 + virtual addressing) or local FS |
| Notifications | Meta WhatsApp Cloud API v21.0, Twilio SMS |
| PDF | WeasyPrint, ReportLab |
| AI (scaffolded) | OpenAI, Google GenAI |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 18 (Create React App + CRACO) |
| Styling | TailwindCSS, Radix UI, shadcn/ui |
| HTTP Client | Axios |
| Routing | React Router v6 |
| State | React Context (Auth, Billing) |
| Toasts | Sonner |
| Icons | Lucide React |
| i18n | Custom JSON-based (Hebrew primary, English) |
| Image Compression | Client-side canvas (>800KB → max 1600px, JPEG 0.7) |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Frontend Hosting | Cloudflare Pages |
| Backend Hosting | AWS Elastic Beanstalk (Docker) |
| Database | MongoDB Atlas |
| File Storage | AWS S3 (`brikops-prod-files`, `eu-central-1`) |
| CI/CD | GitHub Actions (OIDC auth), Cloudflare Pages auto-deploy |
| EB Nginx | `.platform/nginx/conf.d/proxy.conf` → `client_max_body_size 20M` |

---

## API Endpoints

All endpoints prefixed with `/api`.

### Authentication (`auth_router.py`) — 7 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Register with email/password |
| POST | `/auth/login` | No | Email/password login |
| POST | `/auth/dev-login` | No | Dev-only demo login by role |
| GET | `/auth/me` | Yes | Current user profile |
| POST | `/auth/logout-all` | Yes | Invalidate all sessions |
| POST | `/auth/change-phone/request` | Yes | Request phone change (sends OTP) |
| POST | `/auth/change-phone/verify` | Yes | Verify and complete phone change |

### Onboarding (`onboarding_router.py`) — 18 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/request-otp` | No | Request WhatsApp/SMS OTP |
| POST | `/auth/verify-otp` | No | Verify OTP code |
| POST | `/auth/register-with-phone` | No | Register via verified phone |
| POST | `/auth/login-phone` | No | Login via verified phone |
| POST | `/auth/set-password` | Yes | Set password for phone account |
| POST | `/auth/forgot-password` | No | Initiate password reset |
| POST | `/auth/reset-password` | No | Complete password reset |
| GET | `/auth/management-roles` | No | Available management roles |
| GET | `/auth/subcontractor-roles` | No | Available subcontractor roles |
| POST | `/auth/register-management` | No | Management user registration |
| GET | `/onboarding/status` | No | Check onboarding status for phone |
| POST | `/onboarding/create-org` | Yes | Create organization during onboarding |
| POST | `/onboarding/accept-invite` | Yes | Accept invite during onboarding |
| POST | `/onboarding/join-by-code` | Yes | Join project/org by code |
| GET | `/invites/{invite_id}/info` | No | Get invite details |
| GET | `/projects/{project_id}/join-requests` | Yes | List join requests |
| POST | `/join-requests/{request_id}/approve` | Yes | Approve join request |
| POST | `/join-requests/{request_id}/reject` | Yes | Reject join request |

### Tasks (`tasks_router.py`) — 14 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/tasks` | Yes | Create task (PM only) |
| GET | `/tasks` | Yes | List tasks with filters |
| GET | `/tasks/{task_id}` | Yes | Get task details |
| PATCH | `/tasks/{task_id}` | Yes | Update task fields |
| PATCH | `/tasks/{task_id}/assign` | Yes | Assign task to contractor (triggers WhatsApp) |
| POST | `/tasks/{task_id}/status` | Yes | Change task status |
| POST | `/tasks/{task_id}/reopen` | Yes | Reopen closed task |
| POST | `/tasks/{task_id}/contractor-proof` | Yes | Submit contractor proof |
| DELETE | `/tasks/{task_id}/proof/{proof_id}` | Yes | Delete proof |
| POST | `/tasks/{task_id}/manager-decision` | Yes | PM approve/reject completion |
| POST | `/tasks/{task_id}/updates` | Yes | Add comment/update |
| GET | `/tasks/{task_id}/updates` | Yes | List task updates |
| POST | `/tasks/{task_id}/attachments` | Yes | Upload file attachment |
| GET | `/updates/feed` | Yes | Global updates feed |

### Projects (`projects_router.py`) — 18 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/projects` | Yes | Create project |
| GET | `/projects` | Yes | List accessible projects |
| GET | `/projects/{project_id}` | Yes | Get project metadata |
| POST | `/projects/{project_id}/assign-pm` | Yes | Assign PM |
| GET | `/projects/{project_id}/available-pms` | Yes | List available PMs |
| GET | `/projects/{project_id}/hierarchy` | Yes | Full building→floor→unit tree |
| POST | `/projects/{project_id}/buildings` | Yes | Add building |
| GET | `/projects/{project_id}/buildings` | Yes | List buildings |
| POST | `/buildings/{building_id}/floors` | Yes | Add floor |
| GET | `/buildings/{building_id}/floors` | Yes | List floors |
| POST | `/floors/{floor_id}/units` | Yes | Add unit |
| GET | `/floors/{floor_id}/units` | Yes | List units |
| POST | `/floors/bulk` | Yes | Bulk create floors |
| POST | `/units/bulk` | Yes | Bulk create units |
| GET | `/units/{unit_id}` | Yes | Get unit details |
| GET | `/units/{unit_id}/tasks` | Yes | List unit tasks |
| POST | `/buildings/{building_id}/resequence` | Yes | Reorder buildings/floors |
| POST | `/projects/{project_id}/insert-floor` | Yes | Insert floor in sequence |

### Admin (`admin_router.py`) — 20 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/admin/stepup/request` | SA | Request elevated privileges |
| POST | `/admin/stepup/verify` | SA | Verify step-up OTP |
| POST | `/admin/revoke-session/{user_id}` | SA | Force logout user |
| POST | `/admin/billing/override` | SA | Manual billing adjustment |
| POST | `/admin/billing/apply-pending-decreases` | SA | Process scheduled downgrades |
| GET | `/admin/billing/payment-requests-summary` | SA | Payment requests summary |
| GET | `/admin/billing/orgs` | SA | List orgs with billing status |
| GET | `/admin/billing/audit` | SA | Billing audit logs |
| GET | `/admin/billing/plans` | SA | List plan templates |
| POST | `/admin/billing/plans` | SA | Create plan template |
| PUT | `/admin/billing/plans/{plan_id}` | SA | Update plan template |
| PATCH | `/admin/billing/plans/{plan_id}/deactivate` | SA | Deactivate plan |
| GET | `/admin/billing/migration/dry-run` | SA | Preview billing migration |
| POST | `/admin/billing/migration/apply` | SA | Execute billing migration |
| GET | `/admin/users` | SA | List all users |
| GET | `/admin/users/{user_id}` | SA | Get user details |
| PUT | `/admin/users/{user_id}/phone` | SA | Force-update phone |
| PUT | `/admin/users/{user_id}/preferred-language` | SA | Update language preference |
| POST | `/admin/users/{user_id}/reset-password` | SA | Admin password reset |
| PUT | `/admin/users/{user_id}/projects/{project_id}/role` | SA | Override user project role |

### Billing (`billing_router.py`) — 27 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/billing/me` | Yes | Current user billing context |
| GET | `/billing/plans/active` | Yes | List active subscription plans |
| GET | `/billing/org/{org_id}` | Yes | Org subscription status |
| POST | `/billing/org/{org_id}/checkout` | Yes | Initiate plan purchase (stub) |
| GET | `/billing/preview-renewal` | Yes | Preview renewal costs |
| POST | `/billing/org/{org_id}/payment-request` | Yes | Create payment request |
| GET | `/billing/org/{org_id}/payment-requests` | Yes | List payment requests |
| GET | `/billing/org/{org_id}/payment-config` | Yes | Get payment settings |
| PUT | `/billing/org/{org_id}/payment-config` | Yes | Update payment settings |
| POST | `/billing/org/{org_id}/payment-requests/{id}/mark-paid-by-customer` | Yes | Customer reports payment |
| GET | `/billing/org/{org_id}/payment-requests/{id}/receipt` | Yes | Get receipt |
| POST | `/billing/org/{org_id}/payment-requests/{id}/receipt` | Yes | Upload receipt |
| POST | `/billing/org/{org_id}/payment-requests/{id}/cancel` | Yes | Cancel payment request |
| POST | `/billing/org/{org_id}/payment-requests/{id}/reject` | Yes | Reject payment |
| POST | `/billing/org/{org_id}/mark-paid` | SA | Admin mark org as paid |
| GET | `/billing/project/{project_id}` | Yes | Project billing status |
| PATCH | `/billing/project/{project_id}` | Yes | Update project billing (upsert) |
| POST | `/billing/project/{project_id}/handoff-request` | Yes | Request project handoff |
| POST | `/billing/project/{project_id}/handoff-ack` | Yes | Acknowledge handoff |
| POST | `/billing/project/{project_id}/setup-complete` | Yes | Finalize billing setup |
| GET | `/billing/org/{org_id}/invoice/preview` | Yes | Preview next invoice |
| POST | `/billing/org/{org_id}/invoice/generate` | Yes | Generate invoice |
| GET | `/billing/org/{org_id}/invoices` | Yes | List invoices |
| GET | `/billing/org/{org_id}/invoices/{id}` | Yes | Invoice detail |
| POST | `/billing/org/{org_id}/invoices/{id}/mark-paid` | Yes | Mark invoice paid |
| GET | `/orgs/{org_id}/billing-contact` | Yes | Get billing contact |
| PUT | `/orgs/{org_id}/billing-contact` | Yes | Update billing contact |

### Invites (`invites_router.py`) — 7 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users` | Yes | Search users to invite |
| POST | `/projects/{project_id}/invites` | Yes | Create invitation |
| GET | `/projects/{project_id}/invites` | Yes | List active invitations |
| POST | `/projects/{project_id}/invites/{id}/resend` | Yes | Resend invite email |
| POST | `/projects/{project_id}/invites/{id}/resend-sms` | Yes | Resend invite SMS |
| POST | `/projects/{project_id}/invites/{id}/cancel` | Yes | Cancel invitation |
| PUT | `/projects/{project_id}/members/{user_id}/contractor-profile` | Yes | Update contractor profile |

### Companies & Trades (`companies_router.py`) — 9 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/companies` | Yes | Create company |
| GET | `/companies` | Yes | List companies |
| POST | `/projects/{project_id}/companies` | Yes | Link company to project |
| GET | `/projects/{project_id}/companies` | Yes | List project companies |
| PUT | `/projects/{project_id}/companies/{id}` | Yes | Update project-company link |
| DELETE | `/projects/{project_id}/companies/{id}` | Yes | Remove company from project |
| GET | `/projects/{project_id}/trades` | Yes | List project trades |
| POST | `/projects/{project_id}/trades` | Yes | Add/configure trade |
| GET | `/trades` | Yes | List all trade types |

### Stats & Dashboard (`stats_router.py`) — 6 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/projects/{project_id}/stats` | Yes | Project progress stats |
| GET | `/projects/{project_id}/dashboard` | Yes | Aggregated PM dashboard |
| GET | `/projects/{project_id}/tasks/contractor-summary` | Yes | Contractor task summary |
| GET | `/projects/{project_id}/task-buckets` | Yes | Task counts by status/priority |
| GET | `/projects/{project_id}/memberships` | Yes | Project member stats |
| GET | `/my-memberships` | Yes | User's project memberships |

### WhatsApp Login (`wa_login.py`) — 4 endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/wa-login/request-login` | No | Initiate WhatsApp login flow |
| POST | `/wa-login/create-link` | No | Generate login link |
| GET | `/wa-login/verify` | No | Validate login token |
| POST | `/wa-login/send-login-link` | No | Send login link to phone |

### Config (`config_router.py`) — 1 endpoint
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/config/features` | No | Feature flags (app_mode, quick_login, etc.) |

### Notifications (`router.py`, `notification_router.py`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications` | Yes | User notifications |
| GET | `/notifications/stats` | Yes | Notification stats |
| POST | `/webhooks/whatsapp` | No | WhatsApp webhook receiver |
| GET | `/webhooks/whatsapp` | No | WhatsApp webhook verification |

### Debug (`debug_router.py`) — 20 endpoints (SA-gated except /health)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| GET | `/debug/version` | No | Git SHA + feature flags |
| GET | `/admin/system-info` | SA | System diagnostics |
| POST | `/debug/whatsapp-send-test` | SA | Test WhatsApp send (3 modes) |
| GET | `/debug/whatsapp-latest` | SA | Recent WA notifications + events |
| POST | `/debug/whatsapp-test` | SA | Legacy WA test |
| GET | `/debug/notification-lookup` | SA | Lookup by phone fragment |
| ... | ... | SA | Additional debug/diagnostic endpoints |

### Other Routers
- **Identity** (`identity_router.py`): `GET /account-status`, `POST /complete-account`, `POST /change-password`
- **Archive** (`archive_router.py`): Archive/restore for buildings, floors, units (9 endpoints)
- **Excel** (`excel_router.py`): `GET /excel-template`, `POST /excel-import`, migration endpoints (3 endpoints)
- **Plans** (`plans_router.py`): Floor plan management (7 endpoints)
- **QC** (`qc_router.py`): Quality control runs, stages, items, approvers (18 endpoints)
- **Member Management** (`member_management.py`): Role changes, member removal (5 endpoints)
- **Ownership Transfer** (`ownership_transfer.py`): Transfer project ownership (6 endpoints)

---

## MongoDB Collections & Schemas

### Core Management

#### `users`
```json
{
  "id": "uuid",
  "email": "string (unique, sparse)",
  "password_hash": "string",
  "name": "string",
  "phone": "string",
  "phone_e164": "string (unique, sparse)",
  "role": "project_manager|management_team|contractor|viewer",
  "platform_role": "super_admin|none",
  "user_status": "active|pending_pm_approval|suspended",
  "company_id": "string|null",
  "specialties": ["string"],
  "preferred_language": "he|en|ar|zh",
  "session_version": "int",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```
Indexes: `email` (unique, sparse), `phone_e164` (unique, sparse), `[role, company_id]`, `specialties`

#### `projects`
```json
{
  "id": "uuid",
  "name": "string",
  "code": "string (unique)",
  "description": "string",
  "status": "active|suspended",
  "client_name": "string",
  "start_date": "string",
  "end_date": "string",
  "created_by": "user_id",
  "org_id": "string",
  "join_code": "string (unique, sparse)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```
Indexes: `code` (unique), `join_code` (unique, sparse)

#### `buildings`
```json
{
  "id": "uuid",
  "project_id": "string",
  "name": "string",
  "code": "string",
  "floors_count": "int",
  "archived": "boolean",
  "created_at": "datetime"
}
```
Indexes: `project_id`

#### `floors`
```json
{
  "id": "uuid",
  "building_id": "string",
  "project_id": "string",
  "name": "string",
  "floor_number": "int",
  "sort_index": "int",
  "display_label": "string",
  "kind": "residential|technical",
  "unit_count": "int",
  "created_at": "datetime"
}
```
Indexes: `building_id`, `[building_id, sort_index]`

#### `units`
```json
{
  "id": "uuid",
  "floor_id": "string",
  "building_id": "string",
  "project_id": "string",
  "unit_no": "string",
  "unit_type": "apartment|commercial",
  "status": "available|occupied",
  "sort_index": "int",
  "display_label": "string",
  "archived": "boolean",
  "created_at": "datetime"
}
```
Indexes: `[project_id, building_id, floor_id, unit_no]` (unique), `[floor_id, sort_index]`

#### `tasks`
```json
{
  "id": "uuid",
  "project_id": "string",
  "building_id": "string",
  "floor_id": "string",
  "unit_id": "string",
  "title": "string",
  "description": "string",
  "category": "string (trade key)",
  "priority": "low|medium|high|critical",
  "status": "open|assigned|in_progress|pending_review|closed|rejected",
  "company_id": "string",
  "assignee_id": "user_id",
  "due_date": "string|null",
  "created_by": "user_id",
  "attachments_count": "int",
  "comments_count": "int",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```
Indexes: `[project_id, building_id, floor_id, unit_id, status, due_date]`, `[company_id, assignee_id, status]`, `[project_id, status, updated_at]`

#### `companies`
```json
{
  "id": "uuid",
  "name": "string",
  "trade": "string",
  "contact_name": "string",
  "contact_phone": "string",
  "contact_email": "string",
  "specialties": ["string"],
  "phone_e164": "string",
  "whatsapp_enabled": "boolean",
  "whatsapp_opt_in": "boolean",
  "created_at": "datetime"
}
```
Indexes: `specialties`

#### `project_memberships`
```json
{
  "id": "uuid",
  "project_id": "string",
  "user_id": "string",
  "role": "string",
  "company_id": "string|null",
  "contractor_trade_key": "string|null",
  "created_at": "datetime"
}
```
Indexes: `[project_id, user_id]` (unique), `user_id`

#### `project_companies`
```json
{
  "id": "uuid",
  "project_id": "string",
  "company_id": "string",
  "trade_key": "string",
  "created_at": "datetime"
}
```

### Billing & Organizations

#### `organizations`
```json
{
  "id": "uuid",
  "name": "string",
  "owner_user_id": "string",
  "owner_set_at": "datetime",
  "created_at": "datetime"
}
```

#### `organization_memberships`
```json
{
  "id": "uuid",
  "org_id": "string",
  "user_id": "string",
  "role": "org_admin|billing_admin|member",
  "created_at": "datetime"
}
```
Indexes: `[org_id, user_id]` (unique), `user_id`

#### `subscriptions`
```json
{
  "id": "uuid",
  "org_id": "string",
  "status": "trialing|active|past_due|suspended|cancelled",
  "trial_end_at": "datetime",
  "paid_until": "datetime",
  "grace_until": "datetime",
  "billing_cycle": "string",
  "auto_renew": "boolean",
  "manual_override": {
    "is_comped": "boolean",
    "is_suspended": "boolean"
  },
  "cycle_peak_units": "int",
  "pending_contracted_units": "int|null",
  "pending_effective_from": "datetime|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```
Indexes: `org_id` (unique)

#### `project_billing`
```json
{
  "id": "uuid",
  "project_id": "string (unique)",
  "org_id": "string",
  "plan_id": "string",
  "contracted_units": "int",
  "observed_units": "int",
  "tier_code": "string",
  "monthly_total": "number",
  "status": "string",
  "setup_state": "trial|ready|active",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```
Indexes: `project_id` (unique), `org_id`

#### `billing_plans`
```json
{
  "id": "string (unique)",
  "name": "string",
  "project_fee_monthly": "number",
  "unit_tiers": [{"up_to": "int", "price_per_unit": "number"}],
  "version": "int",
  "is_active": "boolean",
  "created_at": "datetime"
}
```

#### `payment_requests`
```json
{
  "id": "uuid",
  "org_id": "string",
  "amount": "number",
  "currency": "string",
  "status": "pending|paid|cancelled|rejected",
  "billing_breakdown": "object (immutable snapshot)",
  "created_by": "user_id",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `invoices`
```json
{
  "id": "uuid",
  "org_id": "string",
  "period_ym": "string (e.g. 2024-05)",
  "status": "issued|paid|past_due",
  "total_amount": "number",
  "currency": "string",
  "issued_at": "datetime",
  "due_at": "datetime",
  "paid_at": "datetime|null",
  "created_by": "user_id",
  "created_at": "datetime"
}
```
Indexes: `[org_id, period_ym]` (unique), `[org_id, status]`

#### `invoice_line_items`
```json
{
  "id": "uuid",
  "invoice_id": "string",
  "project_id": "string",
  "project_name_snapshot": "string",
  "monthly_total_snapshot": "number",
  "created_at": "datetime"
}
```
Indexes: `invoice_id`

### Infrastructure & Security

#### `audit_events`
```json
{
  "id": "uuid",
  "entity_type": "string",
  "entity_id": "string",
  "action": "string",
  "actor_id": "user_id",
  "payload": "object",
  "created_at": "datetime"
}
```
Indexes: `[entity_type, entity_id, created_at]`

#### `notification_jobs`
```json
{
  "id": "uuid",
  "task_id": "string",
  "event_type": "string",
  "target_phone": "string",
  "status": "queued|sent|delivered|failed",
  "attempts": "int",
  "max_attempts": "int",
  "provider_message_id": "string|null",
  "idempotency_key": "string (unique)",
  "next_retry_at": "datetime|null",
  "created_at": "datetime"
}
```
Indexes: `idempotency_key` (unique), `[status, next_retry_at]`, `[task_id, created_at]`

#### `whatsapp_events`
```json
{
  "id": "uuid",
  "wa_message_id": "string",
  "event_type": "string",
  "payload": "object",
  "received_at": "datetime"
}
```

#### `otp_codes`
```json
{
  "phone": "string (unique)",
  "code": "string",
  "expires_at": "datetime (TTL: 600s)",
  "attempts": "int"
}
```
Indexes: `phone` (unique), `expires_at` (TTL)

#### `stepup_challenges` / `stepup_grants`
```json
{
  "challenge_id": "string (unique)",
  "user_id": "string",
  "code_hash": "string",
  "expires_at": "datetime (TTL)",
  "used": "boolean"
}
```

#### `invites`
```json
{
  "id": "uuid",
  "project_id": "string",
  "inviter_user_id": "string",
  "target_phone": "string",
  "role": "string",
  "token": "string (unique)",
  "status": "pending|accepted",
  "expires_at": "datetime",
  "created_at": "datetime"
}
```
Indexes: `token` (unique), `[target_phone, status]`

#### `join_requests`
```json
{
  "id": "uuid",
  "project_id": "string",
  "user_id": "string",
  "status": "pending|approved|rejected",
  "requested_role": "string",
  "created_at": "datetime"
}
```
Indexes: `[project_id, status]`, `user_id`

#### `wa_login_tokens`
```json
{
  "token_hash": "string (unique)",
  "user_id": "string",
  "expires_at": "datetime",
  "used": "boolean",
  "created_at": "datetime"
}
```

### QC Collections

#### `qc_runs`
```json
{
  "id": "uuid",
  "floor_id": "string",
  "project_id": "string",
  "template_id": "string",
  "stages": ["object"],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `qc_items`
```json
{
  "id": "uuid",
  "run_id": "string",
  "stage_id": "string",
  "name": "string",
  "status": "pending|ok|fail|na",
  "photos": ["string"],
  "notes": "string|null",
  "updated_by": "user_id",
  "updated_at": "datetime"
}
```

#### `project_approvers`
```json
{
  "id": "uuid",
  "project_id": "string",
  "user_id": "string",
  "scope": ["stage_id"],
  "created_by": "user_id",
  "created_at": "datetime"
}
```

### Other Collections
- `task_updates` / `task_status_history` — Task change history
- `sms_events` — Outgoing SMS tracking
- `ownership_transfer_requests` — Ownership transfer tracking
- `project_trades` / `project_disciplines` — Trade/discipline definitions
- `unit_plans` / `project_plans` — Uploaded floor plans
- `qc_notifications` — QC notification tracking
- `otp_metrics` — OTP usage metrics

---

## Known Bugs & Issues

### Active Issues
1. **Meta template SSL**: Button URL in Meta WhatsApp templates points to `www.brikops.com` (no SSL). Must update template URLs to `https://app.brikops.com/tasks/{{1}}` in Meta Business Suite — requires Meta re-approval. Code is ready for the switch.
2. **Meta template 404**: Error 132001 "template name does not exist in en" seen during testing for `brikops_defect_new_he`. Possibly Meta temporary issue or template modification. Separate from code changes.
3. **Step-up index conflict**: Warning on startup — `IndexOptionsConflict` for `expires_at_1` TTL index. Non-blocking; step-up auth works correctly.
4. **Checkout endpoint**: `POST /billing/org/{org_id}/checkout` returns 501 (Not Implemented). Placeholder for future Stripe integration.

### Pre-existing Test Infrastructure
5. **`test_s3_mode.py`**: Crashes pytest with `sys.exit()` at module level. Not a code bug.
6. **`test_billing.py` / `test_billing_v1.py`**: 47 tests error with `httpx.ConnectError`. Integration tests requiring separate test server.

---

## Planned Features

1. **V2 WhatsApp Templates**: After Meta approval — switch via env vars only (`WA_DEFECT_TEMPLATE_HE=brikops_defect_new_he_v2`, `WA_TEMPLATE_PARAM_MODE=positional`). No code deploy needed.
2. **Stripe Payment Integration**: Credit card checkout flow (endpoint stub exists at `/billing/org/{org_id}/checkout`).
3. **AI-Powered Features**: AI service module exists (`ai_service.py`) with OpenAI and Google GenAI dependencies. Ready for task suggestions, report generation.
4. **Document Vault**: Document management service scaffolded for property document storage.
5. **Enhanced PDF Reports**: PDF generation v1/v2 with WeasyPrint and ReportLab for construction reports with citations.
6. **Regulation Compliance**: Regulation service module for building code compliance checking.
7. **Multi-language Expansion**: i18n infrastructure supports Hebrew and English; Arabic and Chinese templates ready.
8. **Real-time Notifications**: WebSocket support for live updates (dependencies installed).

---

## Recent Changes (March 4–11, 2026)

### Security Hardening
- **PyJWT migration**: Replaced `ecdsa`/`python-jose` with `PyJWT==2.11.0`. HS256 enforcement, issuer validation, secret versioning.
- **OTP flow hardened**: Rate limits (per-IP, per-phone, per-phone+IP combo), brute-force lockout, SHA-256 hashed 6-digit codes, one-time use, generic error messages, structured audit logging.
- **OTP rate limits persistent**: Moved from in-memory dicts to MongoDB — survives restarts, multi-process safe.
- **Dependency security updates**: Python and frontend packages updated for CVE patches.

### Bug Fixes
- **Billing crash**: `GET /billing/org/{org_id}` crashed on missing `manual_override` — added safe `.get()` fallback.
- **PDF export**: Large defect cards breaking page layout — added card-aware page breaking and image caching.
- **Excel export**: Hebrew filenames garbled — fixed `Content-Disposition` with RFC 5987 `filename*`.
- **Contractor selection**: Company→contractor cascade broken in `NewDefectModal` — rewrote with proper state management.
- **iOS image uploads**: HEIC format failures — added `createImageBitmap` compression, retry with backoff, content-type detection.
- **iOS camera**: Permission crashes — new `CameraModal` with error handling and gallery fallback.
- **API URL**: Replit preview failures — centralized `BACKEND_URL` in `api.js` with relative URL default.
- **WhatsApp delivery**: Phone normalization and fallback image fixes.
- **Feature flags**: Missing `/api/config/features` endpoint — added `config_router.py`.
- **Duplicate payments**: Idempotency check added to payment request endpoint.
- **Cache control**: Added `no-cache` headers for HTML in dev mode.

### New Features
- **Defects Export (Excel + PDF)**: Full export at building/unit scope. Excel with Hebrew RTL headers; PDF A4 with Rubik font, defect cards with images, pagination. `ExportModal` UI component.
- **Defects V2**: `BuildingDefectsPage` + `ApartmentDashboardPage` behind `ENABLE_DEFECTS_V2` flag. `FilterDrawer` with collapsible multi-select filters.
- **InnerBuildingPage**: Mobile-first building workspace — sticky header, 3-tab switcher, KPI strip, collapsible floor→unit hierarchy, FAB with add-floor/add-unit inline forms.
- **BuildingQCPage**: Building-scoped QC floor selection with status badges, search, filter chips.
- **QC navigation unified**: `/qc` rewritten as building selector → BuildingQCPage → FloorDetailPage. Smart back navigation throughout.
- **ProjectPlansPage refresh**: Dark header, horizontal discipline chips (amber), client-side search, plan row hierarchy, upload modal.
- **UnitPlansPage refresh**: Matched to ProjectPlansPage design. No-delete policy (product decision).
- **ProjectControlPage redesign**: 4-tab work switcher, amber palette, RTL, building QC progress indicators.
- **NewDefectModal rewrite**: 3-step flow (create→upload→assign), retry logic, HEIC compression, category-based company filtering, draft save on failure.
- **UpgradeWizard**: Billing plan management with renewal preview.
- **Legal pages**: Terms, Privacy, Data Deletion (Hebrew, static HTML).
- **Task image guard**: Backend enforces at least one image before contractor assignment.

### Architecture
- **Mockup sandbox**: Vite-based component preview environment (`mockup/` directory) for isolated UI prototyping.
- **Feature flags endpoint**: Public `/api/config/features` (no auth) via `config_router.py`.
- **Export system**: New `export_router.py` (834 lines) for Excel/PDF defect exports.
- **Deploy script rewrite**: Staleness detection, frontend rebuild verification, change detection, fail-fast.

### Previous (pre-March 4)
- WhatsApp delivery confirmed working (S3 fallback image, s3v4+virtual addressing)
- Template names configurable via ENV (`WA_DEFECT_TEMPLATE_HE/EN/AR/ZH`)
- `WA_TEMPLATE_PARAM_MODE` env var (named/positional)
- Super admin detection hardened: normalized phone comparison, `{matched, norm, reason}` return
- `BACKEND_URL` centralized in `api.js` with relative URL default
- Canonical redirect middleware skipped in dev mode
