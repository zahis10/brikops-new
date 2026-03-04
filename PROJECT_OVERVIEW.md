# BrikOps — Project Overview

## Table of Contents
1. [Directory Tree](#directory-tree)
2. [Architecture Summary](#architecture-summary)
3. [Tech Stack](#tech-stack)
4. [API Endpoints](#api-endpoints)
5. [MongoDB Collections & Schemas](#mongodb-collections--schemas)
6. [Known Bugs & Issues](#known-bugs--issues)
7. [Planned Features](#planned-features)

---

## Directory Tree

```
brikops/
├── backend/
│   ├── contractor_ops/              # Core application modules
│   │   ├── __init__.py
│   │   ├── router.py                # Shared helpers, constants, auth middleware, 2 notification endpoints (~552 lines)
│   │   ├── admin_router.py          # 20 admin endpoints
│   │   ├── auth_router.py           # 7 auth endpoints
│   │   ├── billing_router.py        # 27 billing/orgs endpoints
│   │   ├── billing.py               # Billing business logic
│   │   ├── billing_plans.py         # Billing plan definitions
│   │   ├── companies_router.py      # 9 company/trade endpoints
│   │   ├── debug_router.py          # 16 debug/health/admin endpoints
│   │   ├── excel_router.py          # 3 excel/migration endpoints
│   │   ├── invites_router.py        # 7 invite/user/contractor-profile endpoints
│   │   ├── plans_router.py          # 7 plans/disciplines endpoints
│   │   ├── projects_router.py       # 18 project/building/floor/unit endpoints
│   │   ├── stats_router.py          # 6 stats/dashboard/membership endpoints
│   │   ├── tasks_router.py          # 14 task endpoints
│   │   ├── archive_router.py        # 9 archive/restore endpoints
│   │   ├── identity_router.py       # 5 identity/account endpoints
│   │   ├── member_management.py     # 5 member management endpoints
│   │   ├── notification_router.py   # 5 notification/webhook endpoints
│   │   ├── notification_service.py  # WhatsApp/SMS notification logic
│   │   ├── onboarding_router.py     # 16 onboarding/registration endpoints
│   │   ├── qc_router.py             # 18 QC (quality control) endpoints
│   │   ├── wa_login.py              # 4 WhatsApp login endpoints
│   │   ├── ownership_transfer.py    # 6 ownership transfer endpoints
│   │   ├── identity_service.py      # Identity/account management logic
│   │   ├── invoicing.py             # Invoice generation logic
│   │   ├── otp_service.py           # OTP generation/verification
│   │   ├── stepup_service.py        # Step-up authentication
│   │   ├── phone_utils.py           # Phone number normalization
│   │   ├── bucket_utils.py          # Task categorization/bucketing
│   │   ├── sms_service.py           # SMS sending service
│   │   ├── msg_logger.py            # Message logging
│   │   ├── schemas.py               # Pydantic models (610 lines)
│   │   ├── seed.py                  # Database seeding
│   │   └── test_*.py                # Unit/integration tests (8 files)
│   ├── services/                    # Supporting services
│   │   ├── ai_service.py
│   │   ├── audit_service.py
│   │   ├── document_vault_service.py
│   │   ├── enhanced_pdf_service.py
│   │   ├── enhanced_pdf_service_v2.py
│   │   ├── object_storage.py        # S3/local file storage abstraction
│   │   ├── pdf_service.py
│   │   ├── pdf_template_service.py
│   │   ├── regulation_service.py
│   │   └── storage_service.py
│   ├── document_vault/              # Document vault module (scaffolded)
│   ├── schemas/                     # Additional schema definitions
│   ├── utils/                       # Backend utility modules
│   ├── tests/                       # Test suite (21 files)
│   │   ├── test_billing.py
│   │   ├── test_billing_v1.py
│   │   ├── test_financial_calculations.py
│   │   ├── test_buckets.py
│   │   ├── test_contractor_hardening.py
│   │   ├── test_cross_trade_hardening.py
│   │   ├── test_deterministic_pagination.py
│   │   ├── test_evidence_upload.py
│   │   ├── test_invite_custom_trade.py
│   │   ├── test_m4_hotfix.py
│   │   ├── test_m6_manager_panel.py
│   │   ├── test_membership_phone_rbac.py
│   │   ├── test_phone_change.py
│   │   ├── test_project_isolation.py
│   │   ├── test_s3_mode.py
│   │   ├── test_storage_migration.py
│   │   ├── test_unit_plans_integration.py
│   │   ├── test_unit_plans_rbac.py
│   │   ├── test_viewer_rbac.py
│   │   └── test_whatsapp_fixes.py
│   ├── scripts/                     # Utility scripts
│   │   ├── backfill_password_hash.py
│   │   ├── backup_restore.py
│   │   ├── backup_restore.sh
│   │   ├── identity_audit.py
│   │   ├── normalize_phones.py
│   │   └── test_intelligence_*.py
│   ├── models.py                    # Extended data models
│   ├── models_extended.py
│   ├── config.py                    # App configuration / env vars
│   ├── server.py                    # FastAPI app, middleware, router registration (~755 lines)
│   ├── seed_data.py                 # Demo/seed data
│   ├── api_intelligence_routes.py   # AI-powered API routes
│   ├── Dockerfile                   # Production Docker image
│   ├── requirements.txt             # Python dependencies
│   ├── start.sh                     # Dev startup script (mongod + uvicorn)
│   ├── build.sh                     # Build script
│   ├── uploads/                     # Local file uploads (dev)
│   ├── reports/                     # Generated reports
│   └── fonts/                       # Custom fonts for PDF generation
├── frontend/
│   ├── src/
│   │   ├── App.js                   # Root component, routing
│   │   ├── App.css
│   │   ├── index.js                 # Entry point
│   │   ├── index.css                # Global styles (Tailwind)
│   │   ├── setupProxy.js            # Dev proxy config
│   │   ├── components/              # Reusable components (16 files)
│   │   │   ├── ui/                  # shadcn/ui primitives (47 files)
│   │   │   ├── BillingPlanComparison.js
│   │   │   ├── CompleteAccountBanner.js
│   │   │   ├── CompleteAccountModal.js
│   │   │   ├── ManagementPanel.js
│   │   │   ├── NewDefectModal.js
│   │   │   ├── NotificationBell.js
│   │   │   ├── PaywallModal.js
│   │   │   ├── PhoneChangeModal.js
│   │   │   ├── ProjectBillingCard.js
│   │   │   ├── ProjectBillingEditModal.js
│   │   │   ├── ProjectSwitcher.js
│   │   │   ├── QCApproversTab.js
│   │   │   ├── TrialBanner.js
│   │   │   ├── UserDrawer.js
│   │   │   └── WhatsAppRejectionModal.js
│   │   ├── pages/                   # Page components (29 files)
│   │   │   ├── LoginPage.js
│   │   │   ├── RegisterPage.js
│   │   │   ├── RegisterManagementPage.js
│   │   │   ├── OnboardingPage.js
│   │   │   ├── MyProjectsPage.js
│   │   │   ├── ProjectDashboardPage.js
│   │   │   ├── ProjectTasksPage.js
│   │   │   ├── ProjectControlPage.js
│   │   │   ├── ProjectPlansPage.js
│   │   │   ├── FloorDetailPage.js
│   │   │   ├── UnitDetailPage.js
│   │   │   ├── UnitHomePage.js
│   │   │   ├── UnitPlansPage.js
│   │   │   ├── TaskDetailPage.js
│   │   │   ├── ContractorDashboard.js
│   │   │   ├── AdminPage.js
│   │   │   ├── AdminBillingPage.js
│   │   │   ├── AdminUsersPage.js
│   │   │   ├── OrgBillingPage.js
│   │   │   ├── AccountSettingsPage.js
│   │   │   ├── OwnershipTransferPage.js
│   │   │   ├── QCFloorSelectionPage.js
│   │   │   ├── StageDetailPage.js
│   │   │   ├── JoinRequestsPage.js
│   │   │   ├── PendingApprovalPage.js
│   │   │   ├── PhoneLoginPage.js
│   │   │   ├── WaLoginPage.js
│   │   │   ├── ForgotPasswordPage.js
│   │   │   └── ResetPasswordPage.js
│   │   ├── contexts/                # React contexts
│   │   │   ├── AuthContext.js
│   │   │   ├── BillingContext.js
│   │   │   └── IdentityContext.js
│   │   ├── hooks/
│   │   │   └── use-toast.js
│   │   ├── services/
│   │   │   └── api.js               # Axios API client
│   │   ├── i18n/                    # Internationalization
│   │   │   ├── index.js
│   │   │   ├── he.json              # Hebrew translations
│   │   │   └── en.json              # English translations
│   │   ├── lib/
│   │   │   └── utils.js             # Utility functions
│   │   ├── utils/                   # Frontend utilities
│   │   └── __tests__/               # Frontend tests
│   ├── package.json
│   ├── craco.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
├── deploy/                          # Deployment configs
├── .github/
│   └── workflows/
│       └── deploy-backend.yml       # CI/CD: GitHub Actions → ECR → Elastic Beanstalk
├── scripts/                         # Root-level utility scripts
├── .gitignore
├── main.py                          # Replit entry point
├── pyproject.toml
├── replit.md                        # Agent memory / project docs
└── PROJECT_OVERVIEW.md              # This file
```

---

## Architecture Summary

### Overview
BrikOps is a full-stack construction task management platform designed for the Israeli market (Hebrew RTL interface). It manages the entire lifecycle of construction defects/tasks from creation through assignment, proof submission, manager approval, and closure.

### Design Principles
- **Strict RBAC**: Every endpoint enforces role-based access control. Roles include `super_admin`, `project_manager`, `management_team`, `contractor`, and `viewer`.
- **Task Lifecycle**: Tasks follow a defined state machine with validated transitions (open → assigned → in_progress → proof → approval → closed).
- **Multi-tenancy**: Organizations own projects; users have per-project memberships with distinct roles.
- **Audit Trail**: All significant actions are logged to `audit_events` with actor, entity, and payload.
- **Billing Enforcement**: Paywall middleware gates write operations for unpaid subscriptions.

### Backend Architecture
- **Framework**: Python FastAPI with Uvicorn ASGI server.
- **Database**: MongoDB (Motor async driver).
- **Router Pattern**: Main `router.py` has been refactored into 11+ dedicated sub-routers, each using `APIRouter(prefix="/api")`. Sub-routers import shared helpers from `contractor_ops.router` (one-way dependency, no circular imports).
- **Authentication**: JWT (HS256) with secret versioning, issuer enforcement, and configurable expiration. Supports email/password, phone OTP, and WhatsApp Magic Link login.
- **File Storage**: Abstracted dual backend — local filesystem (dev) or AWS S3 (production) via `services/object_storage.py`.
- **Notifications**: Multi-channel via WhatsApp (Meta Cloud API v21.0) with SMS fallback (Twilio).

### Frontend Architecture
- **Framework**: React 19 (Create React App with CRACO override).
- **Styling**: TailwindCSS + shadcn/ui (47 primitives) + Radix UI.
- **State Management**: React Context (AuthContext, BillingContext, IdentityContext).
- **Routing**: react-router-dom v7 with role-based dynamic routing.
- **i18n**: Hebrew (primary) and English, with RTL support.
- **API Client**: Axios with auth token injection.

### Deployment Architecture
- **Frontend**: Cloudflare Pages at `app.brikops.com`.
- **Backend**: AWS Elastic Beanstalk (Docker) at `api.brikops.com`.
- **Database**: MongoDB Atlas.
- **CI/CD**: `git push origin main` triggers GitHub Actions → ECR Docker build → EB deployment (OIDC auth).
- **Dev Environment**: Replit with local MongoDB, single-process mode (backend serves static frontend).

### Data Flow
```
Browser → Cloudflare Pages (SPA) → api.brikops.com (FastAPI)
                                        ↓
                                   MongoDB Atlas
                                        ↓
                              AWS S3 (file storage)
                                        ↓
                         WhatsApp / Twilio (notifications)
```

---

## Tech Stack

### Backend
| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.11 |
| Framework | FastAPI | 0.110.1 |
| ASGI Server | Uvicorn | 0.25.0 |
| Database Driver | Motor (async MongoDB) | 3.3.1 |
| Auth | python-jose (JWT) | 3.5.0 |
| Password Hashing | bcrypt | 4.1.3 |
| Validation | Pydantic | 2.12.5 |
| HTTP Client | httpx | 0.28.1 |
| Cloud Storage | boto3 (AWS S3) | 1.42.42 |
| PDF Generation | WeasyPrint + ReportLab | 68.1 / 4.4.10 |
| Payments (planned) | Stripe | 14.3.0 |
| AI | OpenAI + Google GenAI | 1.99.9 / 1.62.0 |
| Testing | pytest | 9.0.2 |

### Frontend
| Component | Technology | Version |
|-----------|-----------|---------|
| Language | JavaScript (JSX) | ES2022 |
| Framework | React | 19.0.0 |
| Build Tool | CRACO (CRA override) | 7.1.0 |
| UI Components | shadcn/ui + Radix UI | Latest |
| Styling | TailwindCSS | 3.x |
| Charts | Recharts | 3.6.0 |
| Forms | react-hook-form + Zod | 7.56.2 / 3.24.4 |
| Routing | react-router-dom | 7.5.1 |
| HTTP Client | Axios | 1.8.4 |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Database | MongoDB Atlas |
| Backend Hosting | AWS Elastic Beanstalk (Docker) |
| Frontend Hosting | Cloudflare Pages |
| File Storage | AWS S3 (`brikops-prod-files`) |
| Container Registry | AWS ECR |
| CI/CD | GitHub Actions (OIDC) |
| Notifications | Meta WhatsApp Cloud API v21.0 + Twilio SMS |

---

## API Endpoints

All endpoints are prefixed with `/api` unless otherwise noted.

### Auth (`auth_router.py`) — 7 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/auth/register` | `register` | Email/password registration |
| POST | `/auth/login` | `login` | Email/password login |
| POST | `/auth/dev-login` | `dev_login` | Dev-only login for demo users |
| GET | `/auth/me` | `get_me` | Get current user info |
| POST | `/auth/logout-all` | `logout_all` | Invalidate all sessions |
| POST | `/auth/change-phone/request` | `change_phone_request` | Request phone change OTP |
| POST | `/auth/change-phone/verify` | `change_phone_verify` | Verify phone change OTP |

### Onboarding (`onboarding_router.py`) — 18 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/auth/request-otp` | `request_otp` | Request phone OTP |
| POST | `/auth/verify-otp` | `verify_otp` | Verify phone OTP |
| POST | `/auth/register-with-phone` | `register_with_phone` | Phone-based registration |
| POST | `/auth/login-phone` | `login_phone` | Phone/password login |
| POST | `/auth/set-password` | `set_password` | Set password for phone user |
| GET | `/auth/management-roles` | `management_roles` | List management roles |
| GET | `/auth/subcontractor-roles` | `subcontractor_roles` | List subcontractor roles |
| POST | `/auth/register-management` | `register_management` | Register management user |
| GET | `/onboarding/status` | `onboarding_status` | Get onboarding progress |
| POST | `/onboarding/create-org` | `create_org` | Create organization |
| POST | `/onboarding/accept-invite` | `accept_invite` | Accept team invite |
| GET | `/invites/{invite_id}/info` | `invite_info` | Get invite details |
| POST | `/onboarding/join-by-code` | `join_by_code` | Join project by code |
| GET | `/projects/{project_id}/join-requests` | `list_join_requests` | List join requests |
| POST | `/join-requests/{request_id}/approve` | `approve_join_request` | Approve join request |
| POST | `/join-requests/{request_id}/reject` | `reject_join_request` | Reject join request |
| POST | `/auth/forgot-password` | `forgot_password` | Request password reset |
| POST | `/auth/reset-password` | `reset_password` | Reset password with token |

### Projects (`projects_router.py`) — 18 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/projects` | `create_project` | Create project |
| GET | `/projects` | `list_projects` | List user's projects |
| GET | `/projects/{project_id}` | `get_project` | Get project details |
| POST | `/projects/{project_id}/buildings` | `create_building` | Create building |
| GET | `/projects/{project_id}/buildings` | `list_buildings` | List buildings |
| GET | `/projects/{project_id}/hierarchy` | `get_hierarchy` | Get full building/floor/unit tree |
| POST | `/buildings/{building_id}/floors` | `create_floor` | Create floor |
| POST | `/buildings/{building_id}/floors/bulk` | `bulk_create_floors` | Bulk create floors |
| GET | `/buildings/{building_id}/floors` | `list_floors` | List floors |
| POST | `/floors/{floor_id}/units` | `create_unit` | Create unit |
| POST | `/floors/{floor_id}/units/bulk` | `bulk_create_units` | Bulk create units |
| GET | `/floors/{floor_id}/units` | `list_units` | List units |
| GET | `/floors/{floor_id}` | `get_floor` | Get floor details |
| GET | `/units/{unit_id}/tasks` | `list_unit_tasks` | List tasks in unit |
| GET | `/units/{unit_id}` | `get_unit` | Get unit details |
| POST | `/buildings/{building_id}/resequence` | `resequence_building` | Re-order floors/units |
| POST | `/projects/{project_id}/insert-floor` | `insert_floor` | Insert floor at position |

### Tasks (`tasks_router.py`) — 14 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/tasks` | `create_task` | Create task/defect |
| GET | `/tasks` | `list_tasks` | List tasks (filtered) |
| GET | `/tasks/{task_id}` | `get_task` | Get task details |
| PATCH | `/tasks/{task_id}` | `update_task` | Update task fields |
| PATCH | `/tasks/{task_id}/assign` | `assign_task` | Assign to contractor |
| POST | `/tasks/{task_id}/status` | `change_status` | Change task status |
| POST | `/tasks/{task_id}/reopen` | `reopen_task` | Reopen closed task |
| POST | `/tasks/{task_id}/contractor-proof` | `upload_contractor_proof` | Upload proof images |
| DELETE | `/tasks/{task_id}/proof/{proof_id}` | `delete_proof` | Delete proof image |
| POST | `/tasks/{task_id}/manager-decision` | `manager_decision` | Approve/reject proof |
| POST | `/tasks/{task_id}/updates` | `add_update` | Add comment/update |
| GET | `/tasks/{task_id}/updates` | `list_updates` | List task updates |
| POST | `/tasks/{task_id}/attachments` | `upload_attachment` | Upload attachment |
| GET | `/updates/feed` | `updates_feed` | Real-time updates feed |

### Stats (`stats_router.py`) — 6 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| GET | `/projects/{project_id}/memberships` | `list_memberships` | List project members |
| GET | `/my-memberships` | `my_memberships` | List current user's memberships |
| GET | `/projects/{project_id}/stats` | `project_stats` | Get project statistics |
| GET | `/projects/{project_id}/dashboard` | `dashboard` | Get dashboard data |
| GET | `/projects/{project_id}/tasks/contractor-summary` | `contractor_summary` | Contractor task summary |
| GET | `/projects/{project_id}/task-buckets` | `task_buckets` | Task categorization buckets |

### Companies (`companies_router.py`) — 9 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/projects/{project_id}/companies` | `create_company` | Create company |
| GET | `/projects/{project_id}/companies` | `list_companies` | List companies |
| GET | `/projects/{project_id}/trades` | `list_trades` | List available trades |
| POST | `/projects/{project_id}/trades` | `create_trade` | Create custom trade |
| PATCH | `/projects/{project_id}/companies/{company_id}` | `update_company` | Update company |
| DELETE | `/projects/{project_id}/companies/{company_id}` | `delete_company` | Delete company |
| GET | `/projects/{project_id}/company-assignments` | `list_company_assignments` | List assignments |
| PUT | `/projects/{project_id}/members/{user_id}/company-trade` | `update_company_trade` | Update member company/trade |
| GET | `/projects/{project_id}/companies/{company_id}/members` | `list_company_members` | List company members |

### Invites (`invites_router.py`) — 7 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/projects/{project_id}/invites` | `create_invite` | Create team invite |
| GET | `/projects/{project_id}/invites` | `list_invites` | List project invites |
| POST | `/projects/{project_id}/invites/{invite_id}/cancel` | `cancel_invite` | Cancel invite |
| POST | `/projects/{project_id}/invites/{invite_id}/resend` | `resend_invite` | Resend invite |
| GET | `/users/by-phone` | `get_user_by_phone` | Look up user by phone |
| GET | `/contractor-profiles` | `list_contractor_profiles` | List contractor profiles |
| PUT | `/contractor-profiles/{user_id}` | `update_contractor_profile` | Update contractor profile |

### Billing (`billing_router.py`) — 27 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| GET | `/billing/me` | `billing_me` | Get current user billing info |
| GET | `/billing/plans/active` | `billing_plans_active` | List active billing plans |
| GET | `/billing/org/{org_id}` | `billing_org` | Get org billing details |
| POST | `/billing/org/{org_id}/checkout` | `billing_checkout` | Initiate checkout (501 — planned) |
| GET | `/billing/preview-renewal` | `billing_preview_renewal` | Preview renewal pricing |
| POST | `/billing/org/{org_id}/payment-request` | `billing_payment_request` | Create payment request |
| GET | `/billing/org/{org_id}/payment-requests` | `billing_list_payment_requests` | List payment requests |
| GET | `/billing/org/{org_id}/payment-config` | `billing_get_payment_config` | Get payment config |
| PUT | `/billing/org/{org_id}/payment-config` | `billing_update_payment_config` | Update payment config (SA only) |
| POST | `/billing/org/{org_id}/payment-requests/{request_id}/mark-paid-by-customer` | `billing_customer_mark_paid` | Customer marks payment |
| POST | `/billing/org/{org_id}/payment-requests/{request_id}/receipt` | `billing_upload_receipt_form` | Upload payment receipt |
| GET | `/billing/org/{org_id}/payment-requests/{request_id}/receipt` | `billing_get_receipt` | Get receipt URL |
| POST | `/billing/org/{org_id}/payment-requests/{request_id}/cancel` | `billing_cancel_request` | Cancel payment request |
| POST | `/billing/org/{org_id}/payment-requests/{request_id}/reject` | `billing_reject_request` | Reject payment request (SA only) |
| POST | `/billing/org/{org_id}/mark-paid` | `billing_mark_paid` | Admin mark as paid (SA only) |
| GET | `/billing/project/{project_id}` | `billing_project` | Get project billing |
| PATCH | `/billing/project/{project_id}` | `billing_project_update` | Update project billing |
| POST | `/billing/project/{project_id}/handoff-request` | `billing_handoff_request` | Request billing handoff |
| POST | `/billing/project/{project_id}/handoff-ack` | `billing_handoff_ack` | Acknowledge handoff |
| POST | `/billing/project/{project_id}/setup-complete` | `billing_setup_complete` | Mark setup complete |
| GET | `/billing/org/{org_id}/invoice/preview` | `invoice_preview` | Preview invoice |
| POST | `/billing/org/{org_id}/invoice/generate` | `invoice_generate` | Generate invoice |
| GET | `/billing/org/{org_id}/invoices` | `invoice_list` | List invoices |
| GET | `/billing/org/{org_id}/invoices/{invoice_id}` | `invoice_detail` | Get invoice details |
| POST | `/billing/org/{org_id}/invoices/{invoice_id}/mark-paid` | `invoice_mark_paid` | Mark invoice paid |
| GET | `/orgs/{org_id}/billing-contact` | `get_billing_contact_endpoint` | Get billing contact |
| PUT | `/orgs/{org_id}/billing-contact` | `update_billing_contact_endpoint` | Update billing contact |

### Admin (`admin_router.py`) — 20 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/admin/stepup/request` | `stepup_request` | Request step-up auth |
| POST | `/admin/stepup/verify` | `stepup_verify` | Verify step-up auth |
| POST | `/admin/revoke-session/{user_id}` | `admin_revoke_session` | Revoke user sessions |
| POST | `/admin/billing/override` | `admin_override` | Override billing status |
| POST | `/admin/billing/apply-pending-decreases` | `admin_apply_pending_decreases` | Apply pending unit decreases |
| GET | `/admin/billing/payment-requests-summary` | `admin_payment_requests_summary` | Payment requests summary |
| GET | `/admin/billing/orgs` | `admin_list_orgs` | List all organizations |
| GET | `/admin/billing/audit` | `admin_billing_audit` | Billing audit trail |
| GET | `/admin/billing/plans` | `admin_list_plans` | List all billing plans |
| POST | `/admin/billing/plans` | `admin_create_plan` | Create billing plan |
| PUT | `/admin/billing/plans/{plan_id}` | `admin_update_plan` | Update billing plan |
| PATCH | `/admin/billing/plans/{plan_id}/deactivate` | `admin_deactivate_plan` | Deactivate plan |
| GET | `/admin/billing/migration/dry-run` | `admin_migration_dry_run` | Billing migration dry run |
| POST | `/admin/billing/migration/apply` | `admin_migration_apply` | Apply billing migration |
| GET | `/admin/users` | `admin_list_users` | List all users |
| GET | `/admin/users/{user_id}` | `admin_get_user` | Get user details |
| PUT | `/admin/users/{user_id}/phone` | `admin_change_user_phone` | Change user phone |
| PUT | `/admin/users/{user_id}/preferred-language` | `admin_update_preferred_language` | Update preferred language |
| POST | `/admin/users/{user_id}/reset-password` | `admin_reset_user_password` | Reset user password |
| PUT | `/admin/users/{user_id}/projects/{project_id}/role` | `admin_change_user_role` | Change user project role |

### Archive (`archive_router.py`) — 9 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/buildings/{building_id}/archive` | `archive_building` | Soft-delete building |
| POST | `/floors/{floor_id}/archive` | `archive_floor` | Soft-delete floor |
| POST | `/units/{unit_id}/archive` | `archive_unit` | Soft-delete unit |
| POST | `/buildings/{building_id}/restore` | `restore_building` | Restore building |
| POST | `/floors/{floor_id}/restore` | `restore_floor` | Restore floor |
| POST | `/units/{unit_id}/restore` | `restore_unit` | Restore unit |
| POST | `/batches/{batch_id}/undo` | `undo_batch` | Undo batch operation |
| GET | `/projects/{project_id}/archived` | `list_archived` | List archived entities |
| DELETE | `/admin/entities/{entity_type}/{entity_id}/permanent` | `permanent_delete` | Permanent delete (SA only) |

### Identity (`identity_router.py`) — 5 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| GET | `/account-status` | `account_status` | Get account completion status |
| POST | `/complete-account` | `complete_account` | Complete account setup |
| POST | `/identity-event` | `identity_event` | Log identity event |
| POST | `/change-password` | `change_password` | Change password |
| POST | `/change-email` | `change_email` | Change email |

### Member Management (`member_management.py`) — 5 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| PUT | `/projects/{project_id}/members/{target_user_id}/role` | `change_member_role` | Change member's project role |
| DELETE | `/projects/{project_id}/members/{target_user_id}` | `remove_member` | Remove project member |
| DELETE | `/org/members/{target_user_id}` | `remove_org_member` | Remove org member |
| GET | `/orgs/{org_id}/members` | `list_org_members` | List org members |
| PUT | `/orgs/{org_id}/members/{target_user_id}/org-role` | `change_org_role` | Change org role |

### Notifications (`notification_router.py` + `router.py`) — 7 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/tasks/{task_id}/notify` | `notify_task` | Send task notification |
| GET | `/tasks/{task_id}/notifications` | `list_task_notifications` | List task notifications |
| POST | `/notifications/{job_id}/retry` | `retry_notification` | Retry failed notification |
| GET | `/webhooks/whatsapp` | `whatsapp_webhook_verify` | WhatsApp webhook verification |
| POST | `/webhooks/whatsapp` | `whatsapp_webhook` | WhatsApp webhook handler |
| GET | `/notifications` | `list_notifications` | List user notifications |
| GET | `/notifications/stats` | `notification_stats` | Notification statistics |

### QC — Quality Control (`qc_router.py`) — 18 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| GET | `/templates` | `list_templates` | List QC templates |
| GET | `/floors/{floor_id}/run` | `get_or_create_run` | Get/create QC run |
| GET | `/run/{run_id}` | `get_run` | Get QC run details |
| GET | `/run/{run_id}/team-contacts` | `team_contacts` | Get team contacts for run |
| PATCH | `/run/{run_id}/item/{item_id}` | `update_item` | Update QC item |
| POST | `/run/{run_id}/item/{item_id}/reject` | `reject_item` | Reject QC item |
| POST | `/run/{run_id}/item/{item_id}/photo` | `upload_photo` | Upload QC photo |
| POST | `/run/{run_id}/stage/{stage_id}/submit` | `submit_stage` | Submit stage for review |
| GET | `/floors/batch-status` | `batch_status` | Batch floor QC status |
| GET | `/meta/stages` | `list_stages` | List QC stages |
| GET | `/projects/{project_id}/approvers` | `list_approvers` | List project approvers |
| POST | `/projects/{project_id}/approvers` | `add_approver` | Add approver |
| DELETE | `/projects/{project_id}/approvers/{target_user_id}` | `remove_approver` | Remove approver |
| POST | `/run/{run_id}/stage/{stage_id}/approve` | `approve_stage` | Approve stage |
| POST | `/run/{run_id}/stage/{stage_id}/reject` | `reject_stage` | Reject stage |
| POST | `/run/{run_id}/stage/{stage_id}/notify-rejection` | `notify_rejection` | Notify rejection |
| GET | `/run/{run_id}/my-approver-status` | `my_approver_status` | Get my approver status |
| POST | `/run/{run_id}/stage/{stage_id}/reopen` | `reopen_stage` | Reopen stage |
| GET | `/run/{run_id}/stage/{stage_id}/timeline` | `stage_timeline` | Stage approval timeline |

### WhatsApp Login (`wa_login.py`) — 4 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/request-login` | `request_login` | Request WhatsApp login link |
| POST | `/create-link` | `create_link` | Create magic login link |
| GET | `/verify` | `verify` | Verify login token |
| POST | `/send-login-link` | `send_login_link` | Send login link via WhatsApp |

### Ownership Transfer (`ownership_transfer.py`) — 6 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/initiate` | `initiate_transfer` | Start ownership transfer |
| POST | `/cancel` | `cancel_transfer` | Cancel transfer |
| GET | `/pending` | `get_pending` | Get pending transfers |
| GET | `/verify/{token}` | `verify_token` | Verify transfer token |
| POST | `/request-otp` | `transfer_request_otp` | Request OTP for transfer |
| POST | `/accept` | `accept_transfer` | Accept ownership transfer |

### Plans (`plans_router.py`) — 7 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/projects/{project_id}/plans/upload` | `upload_plan` | Upload floor plan |
| GET | `/projects/{project_id}/plans` | `list_plans` | List floor plans |
| DELETE | `/projects/{project_id}/plans/{plan_id}` | `delete_plan` | Delete floor plan |
| GET | `/projects/{project_id}/disciplines` | `list_disciplines` | List disciplines |
| POST | `/projects/{project_id}/disciplines` | `create_discipline` | Create discipline |
| DELETE | `/projects/{project_id}/disciplines/{discipline_id}` | `delete_discipline` | Delete discipline |
| PATCH | `/projects/{project_id}/disciplines/{discipline_id}` | `update_discipline` | Update discipline |

### Debug (`debug_router.py`) — 16 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| GET | `/debug/routes` | `list_routes` | List all registered routes |
| GET | `/debug/config` | `debug_config` | Show configuration |
| GET | `/debug/db-status` | `db_status` | Database status |
| GET | `/debug/sms-status` | `sms_status` | SMS service status |
| POST | `/debug/test-sms` | `test_sms` | Test SMS sending |
| GET | `/debug/sms-events` | `sms_events` | List SMS events |
| POST | `/debug/reset-sms-events` | `reset_sms_events` | Reset SMS events |
| POST | `/debug/test-whatsapp` | `test_whatsapp` | Test WhatsApp sending |
| GET | `/debug/whatsapp-events` | `whatsapp_events` | List WhatsApp events |
| GET | `/debug/msg-log` | `msg_log` | Message log |
| GET | `/debug/otp-metrics` | `otp_metrics` | OTP metrics |
| POST | `/debug/otp-metrics/reset` | `reset_otp_metrics` | Reset OTP metrics |
| GET | `/debug/audit-events` | `audit_events` | List audit events |
| GET | `/debug/system-info` | `system_info` | System information |
| GET | `/debug/role-conflicts` | `role_conflicts` | Detect role conflicts |
| GET | `/debug/storage-config` | `storage_config` | Storage configuration |

### Excel (`excel_router.py`) — 3 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| POST | `/projects/{project_id}/import-excel` | `import_excel` | Import from Excel |
| GET | `/projects/{project_id}/export-excel` | `export_excel` | Export to Excel |
| POST | `/projects/{project_id}/migrate-units` | `migrate_units` | Migrate units data |

### Server-level (`server.py`) — 2 endpoints
| Method | Path | Function | Description |
|--------|------|----------|-------------|
| GET | `/health` | `health` | Health check |
| GET | `/api/debug/db-ping` | `db_ping` | Database ping |

**Total: ~210 API endpoints** (207 from sub-routers + 3 from server.py)

---

## MongoDB Collections & Schemas

### Core Collections

#### `users`
```json
{
  "id": "uuid",
  "email": "string|null",
  "name": "string",
  "phone": "string|null",
  "phone_e164": "string|null",
  "role": "project_manager|management_team|contractor|viewer",
  "platform_role": "none|super_admin",
  "password_hash": "string",
  "user_status": "active|pending_pm_approval|rejected|suspended",
  "company_id": "string|null",
  "specialties": ["string"],
  "preferred_language": "he|en",
  "account_complete": "boolean",
  "session_version": "int",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `projects`
```json
{
  "id": "uuid",
  "name": "string",
  "code": "string",
  "description": "string|null",
  "status": "draft|payment_pending|active|suspended",
  "client_name": "string|null",
  "org_id": "string|null",
  "join_code": "string|null",
  "start_date": "string|null",
  "end_date": "string|null",
  "created_by": "user_id",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `buildings`
```json
{
  "id": "uuid",
  "project_id": "string",
  "name": "string",
  "code": "string|null",
  "floors_count": "int",
  "archived": "boolean",
  "archived_at": "datetime|null",
  "archive_batch_id": "string|null",
  "created_at": "datetime"
}
```

#### `floors`
```json
{
  "id": "uuid",
  "building_id": "string",
  "project_id": "string",
  "name": "string",
  "floor_number": "int",
  "sort_index": "int",
  "display_label": "string|null",
  "kind": "residential|technical|service|roof|basement|ground|parking|commercial|null",
  "unit_count": "int",
  "archived": "boolean",
  "created_at": "datetime"
}
```

#### `units`
```json
{
  "id": "uuid",
  "floor_id": "string",
  "building_id": "string",
  "project_id": "string",
  "unit_no": "string",
  "unit_type": "apartment|commercial|parking|storage",
  "status": "available|occupied",
  "sort_index": "int",
  "display_label": "string|null",
  "archived": "boolean",
  "created_at": "datetime"
}
```

#### `tasks`
```json
{
  "id": "uuid",
  "project_id": "string",
  "building_id": "string",
  "floor_id": "string",
  "unit_id": "string",
  "title": "string",
  "description": "string|null",
  "category": "electrical|plumbing|hvac|painting|flooring|carpentry|...",
  "priority": "low|medium|high|critical",
  "status": "open|assigned|in_progress|waiting_verify|pending_contractor_proof|pending_manager_approval|returned_to_contractor|closed|reopened",
  "company_id": "string|null",
  "assignee_id": "string|null",
  "due_date": "string|null",
  "proof_images": [{"id": "uuid", "url": "string", "uploaded_at": "datetime"}],
  "attachments_count": "int",
  "comments_count": "int",
  "created_by": "user_id",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `task_updates`
```json
{
  "id": "uuid",
  "task_id": "string",
  "user_id": "string",
  "user_name": "string",
  "content": "string",
  "update_type": "comment|status_change|attachment",
  "attachment_url": "string|null",
  "old_status": "string|null",
  "new_status": "string|null",
  "created_at": "datetime"
}
```

#### `task_status_history`
```json
{
  "id": "uuid",
  "task_id": "string",
  "old_status": "string",
  "new_status": "string",
  "changed_by": "user_id",
  "note": "string|null",
  "created_at": "datetime"
}
```

### Membership & Organization Collections

#### `organizations`
```json
{
  "id": "uuid",
  "name": "string",
  "slug": "string",
  "owner_user_id": "string",
  "billing_contact": {"name": "string", "email": "string", "phone": "string"},
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `organization_memberships`
```json
{
  "id": "uuid",
  "org_id": "string",
  "user_id": "string",
  "role": "member|project_manager|org_admin|billing_admin",
  "created_at": "datetime"
}
```

#### `project_memberships`
```json
{
  "id": "uuid",
  "project_id": "string",
  "user_id": "string",
  "role": "project_manager|management_team|contractor|viewer",
  "sub_role": "string|null",
  "company_id": "string|null",
  "contractor_trade_key": "string|null",
  "created_at": "datetime"
}
```

#### `companies` / `project_companies`
```json
{
  "id": "uuid",
  "project_id": "string",
  "name": "string",
  "trade": "string|null",
  "contact_name": "string|null",
  "contact_phone": "string|null",
  "contact_email": "string|null",
  "created_at": "datetime"
}
```

### Billing Collections

#### `subscriptions`
```json
{
  "id": "uuid",
  "org_id": "string",
  "plan_id": "string|null",
  "status": "trial|active|suspended|canceled",
  "cycle": "monthly|yearly",
  "total_contracted_units": "int",
  "cycle_peak_units": "int",
  "pending_contracted_units": "int|null",
  "pending_effective_from": "datetime|null",
  "trial_ends_at": "datetime|null",
  "current_period_start": "datetime",
  "current_period_end": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `project_billing`
```json
{
  "id": "uuid",
  "project_id": "string",
  "org_id": "string",
  "plan_id": "string|null",
  "plan_snapshot": "object|null",
  "contracted_units": "int",
  "observed_units": "int",
  "status": "active|suspended",
  "setup_state": "pending_handoff|pending_setup|complete",
  "billing_contact_note": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `billing_plans`
```json
{
  "id": "uuid",
  "name": "string",
  "version": "int",
  "is_active": "boolean",
  "project_fee_monthly": "number",
  "unit_tiers": [{"up_to": "int|null", "price_per_unit": "number"}],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `billing_payment_requests`
```json
{
  "id": "uuid",
  "org_id": "string",
  "status": "requested|sent|paid|canceled|pending_review|rejected",
  "cycle": "monthly|yearly",
  "billing_breakdown": "object",
  "requested_by_user_id": "string",
  "requested_by_kind": "billing_manager|pm_handoff",
  "note": "string",
  "contact_email": "string",
  "paid_note": "string|null",
  "customer_paid_note": "string|null",
  "rejection_reason": "string|null",
  "receipt_key": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `invoices` / `invoice_line_items`
```json
{
  "id": "uuid",
  "org_id": "string",
  "period": "string (YYYY-MM)",
  "status": "draft|issued|paid",
  "total_amount": "number",
  "line_items": ["ref to invoice_line_items"],
  "generated_by": "user_id",
  "created_at": "datetime"
}
```

### Communication Collections

#### `notification_jobs`
```json
{
  "id": "uuid",
  "task_id": "string",
  "event_type": "task_created|task_assigned|status_waiting_verify|...",
  "target_phone": "string",
  "payload": "object",
  "status": "queued|skipped_dry_run|sent|delivered|read|failed",
  "attempts": "int",
  "max_attempts": "int",
  "provider_message_id": "string|null",
  "last_error": "string|null",
  "idempotency_key": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### `invites` / `team_invites`
```json
{
  "id": "uuid",
  "project_id": "string",
  "inviter_user_id": "string",
  "target_phone": "string",
  "role": "project_manager|management_team|contractor",
  "sub_role": "string|null",
  "token": "string",
  "status": "pending|accepted|expired|cancelled",
  "expires_at": "datetime",
  "accepted_by_user_id": "string|null",
  "created_at": "datetime"
}
```

#### `join_requests`
```json
{
  "id": "uuid",
  "project_id": "string",
  "user_id": "string",
  "track": "management|subcontractor",
  "requested_role": "string",
  "requested_company_id": "string|null",
  "status": "pending|approved|rejected",
  "reason": "string|null",
  "reviewed_by": "string|null",
  "created_at": "datetime"
}
```

### Auth & Security Collections

#### `otp_codes`
```json
{
  "phone_e164": "string",
  "code": "string",
  "attempts": "int",
  "created_at": "datetime",
  "expires_at": "datetime"
}
```

#### `stepup_challenges` / `stepup_grants`
```json
{
  "id": "uuid",
  "user_id": "string",
  "method": "email",
  "code_hash": "string",
  "expires_at": "datetime",
  "created_at": "datetime"
}
```

#### `wa_login_tokens`
```json
{
  "token": "string",
  "user_id": "string",
  "phone_e164": "string",
  "expires_at": "datetime",
  "used": "boolean",
  "created_at": "datetime"
}
```

#### `password_reset_tokens`
```json
{
  "id": "uuid",
  "user_id": "string",
  "token_hash": "string",
  "expires_at": "datetime",
  "used": "boolean",
  "created_at": "datetime"
}
```

### Audit & Events Collections

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

#### `sms_events` / `whatsapp_events`
```json
{
  "id": "uuid",
  "phone": "string",
  "message_type": "string",
  "status": "string",
  "provider_id": "string|null",
  "error": "string|null",
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
- `ownership_transfer_requests` — Ownership transfer tracking
- `project_trades` / `project_disciplines` — Trade/discipline definitions
- `unit_plans` / `project_plans` — Uploaded floor plans
- `qc_notifications` — QC notification tracking
- `otp_metrics` — OTP usage metrics

---

## Known Bugs & Issues

### Pre-existing Test Infrastructure
1. **`test_s3_mode.py`**: Crashes pytest with `sys.exit()` at module level. Not a code bug — test file uses a script-style runner incompatible with pytest's import mechanism.
2. **`test_billing.py` / `test_billing_v1.py`**: 47 tests error with `httpx.ConnectError: Connection refused`. These are integration tests that require a separate test server to be running. Not related to application code.

### Minor Issues
3. **Step-up index conflict**: Warning on startup — `IndexOptionsConflict` for `expires_at_1` TTL index. The index exists but with different options. Non-blocking; step-up auth works correctly.
4. **Checkout endpoint**: `POST /billing/org/{org_id}/checkout` returns 501 (Not Implemented). Placeholder for future Stripe integration.

---

## Planned Features

1. **Stripe Payment Integration**: Credit card checkout flow (endpoint stub already exists at `/billing/org/{org_id}/checkout`).
2. **AI-Powered Features**: AI service module exists (`ai_service.py`, `api_intelligence_routes.py`) with OpenAI and Google GenAI dependencies installed. Infrastructure ready for intelligent task suggestions, report generation, etc.
3. **Document Vault**: Document management service (`document_vault_service.py`) scaffolded for property document storage and retrieval.
4. **Enhanced PDF Reports**: PDF generation services (v1 and v2) with WeasyPrint and ReportLab for construction reports with citations.
5. **Regulation Compliance**: Regulation service module (`regulation_service.py`) for building code compliance checking.
6. **Multi-language Expansion**: i18n infrastructure supports Hebrew and English; additional languages can be added via JSON translation files.
7. **Real-time Notifications**: WebSocket support for live updates (WebSocket dependencies installed).
