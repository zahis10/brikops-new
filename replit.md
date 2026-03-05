# BrikOps - Construction Task Management System

## Overview
BrikOps is an MVP full-stack application designed to streamline construction task management. Its main purpose is to enhance workflows, improve communication, and provide comprehensive oversight for all stakeholders in construction projects. Key capabilities include robust Role-Based Access Control (RBAC), a defined task lifecycle with strict status transitions, detailed audit logging, file attachment capabilities, and a real-time updates feed. The project's vision is to become a leading solution in the construction management software market by offering essential task management and user-centric functionalities.

## User Preferences
- This app is NOT BedekPro. Do NOT add inspection-report logic.
- Hebrew content in demo data
- Strict RBAC enforcement
- Task status transitions must follow defined workflow

## System Architecture

### Core Design Principles
BrikOps is a full-stack application with a clear separation between frontend and backend. It emphasizes secure access via RBAC, a meticulously defined task workflow, and real-time communication capabilities. The system is designed for deployment in VM environments, with the backend serving both the API and static frontend assets.

### Frontend
-   **Framework**: React (Create React App with CRACO).
-   **UI/UX**: Leverages Radix UI, TailwindCSS, and shadcn/ui for a modern, responsive user experience. Features include dynamic dashboards, hierarchical navigation, consistent color palette (amber for CTA/brand, slate for neutral, emerald for success, red for failure), multi-step task management with visual timelines and proof galleries, email/password and OTP-based authentication, and role-based dynamic routing.

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: The main `router.py` has been refactored into sub-routers (all use `prefix="/api"`):
    -   `config_router.py`: 1 public endpoint (`/api/config/features`) returning feature flags (no auth required).
    -   `debug_router.py`: 18 debug/health/admin endpoints (all gated behind `require_super_admin` except `/api/health`). Includes `POST /debug/whatsapp-test` (SA-only, bypasses WHATSAPP_ENABLED flag for testing) and `GET /debug/notification-lookup?phone=<fragment>` (debug-access-gated, returns notification jobs matching a phone number).
    -   `excel_router.py`: 3 excel/migration endpoints.
    -   `plans_router.py`: 7 plans/disciplines endpoints.
    -   `invites_router.py`: 7 invite/user/contractor-profile endpoints.
    -   `companies_router.py`: 9 company/trade endpoints + `_slugify_hebrew` helper.
    -   `stats_router.py`: 6 stats/dashboard/membership endpoints (project stats, dashboard, contractor-summary, task-buckets, memberships, my-memberships).
    -   `auth_router.py`: 7 auth endpoints (register, login, dev-login, get_me, logout-all, change-phone/request, change-phone/verify).
    -   `projects_router.py`: 18 project/building/floor/unit endpoints + helpers (`_is_numeric_unit`, `_compute_building_resequence`, `_natural_sort_key`).
    -   `tasks_router.py`: 14 task endpoints (create, list, get, update, assign, status-change, reopen, contractor-proof, delete-proof, manager-decision, add-update, list-updates, upload-attachment, updates-feed) + `_build_bucket_maps` helper.
    -   `admin_router.py`: 20 admin endpoints (stepup request/verify, revoke-session, billing override/apply-pending/payment-requests-summary/orgs/audit/plans CRUD/migration, users list/get/phone/preferred-language/reset-password/role-change).
    -   `billing_router.py`: 27 billing/orgs endpoints (billing/me, plans/active, org CRUD, checkout, preview-renewal, payment-request CRUD, payment-config, mark-paid, receipt, cancel/reject, project billing GET/PATCH, handoff-request/ack, setup-complete, invoice preview/generate/list/detail/mark-paid, billing-contact GET/PUT).
    -   Sub-routers import shared helpers from `contractor_ops.router` (one-way dependency).
    -   `router.py` now contains only shared helpers, constants, auth/security middleware, and 2 notification endpoints (~552 lines).
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Supports email/password, phone OTP, PM approval, WhatsApp Magic Link Login, and comprehensive onboarding. Includes a dev-only login endpoint for demo users.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp (with SMS fallback) using Meta-approved templates, configurable by user's preferred language. Fallback image (`WA_FALLBACK_IMAGE_URL = https://app.brikops.com/logo192.png`) is used when a defect has no attached photo, ensuring the required IMAGE header is always included in template messages.
    -   **Security**: Implements JWT tokens with HS256, issuer enforcement, and secret versioning.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3). S3 uploads use `asyncio.to_thread()` to avoid blocking the async event loop. Timing logs added for S3 operations (`[UPLOAD:STAGE3:S3_TIME]`, `[UPLOAD:STAGE4:S3_TIME]`).
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions, including categorization and bucketing.
    -   **Proof Management**: Multi-image proof uploads with audit logging.
    -   **Billing System**: Centralized billing management for organizations, including payment requests, renewals, plan management, and access control based on subscription status. Enforces a single open payment request per organization and provides administrative oversight. Implements anti-gaming policy: unit increases are immediate (with peak tracking via `cycle_peak_units`), decreases are deferred to the next billing cycle (`pending_contracted_units` + `pending_effective_from`), and payment requests use peak-based pricing with immutable `billing_breakdown`. Pending decreases are lazily applied on billing reads, server startup, and via SA endpoint. PM can edit project billing (plan + units) for projects they manage via `ProjectBillingEditModal` — available on both OrgBillingPage and ProjectBillingCard. Amount=0 payment request errors guide users to edit project pricing first. `PATCH /billing/project/{id}` uses upsert: creates a billing record via `create_project_billing` if none exists. **UpgradeWizard** component (`frontend/src/components/UpgradeWizard.js`): inline 3-step wizard (project → plan+units → summary) shown on OrgBillingPage when `needsUpgrade === true`; submits via `updateProjectBilling` then `createPaymentRequest`; handles single/multi project, projects with/without existing billing. Old payment request section on OrgBillingPage hidden when wizard is active.
    -   **Admin & Member Management**: Tools for `super_admin`, PM, and owner-level team management, including role changes, member removal, and admin password reset with audit events.
    -   **QC (Quality Control) System**: Floor-level quality control with a hardcoded template, detailed item management, strict RBAC, a stage-based workflow, and an approver system with scope management.
    -   **Identity System**: Manages user accounts, including account status, completion, and audit logging.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements with cascade operations.
    -   **Role Conflict Guard**: Prevents users from holding conflicting `contractor` and organizational management roles within the same organization.
    -   **Contractor Company+Trade Assignment**: Manages contractor assignments to companies and trades at the project membership level, including invite flows and editing capabilities, with validation to ensure contractors are assigned. Defect creation modal loads contractor list from project memberships (not users collection) to correctly match project-scoped company assignments. `assign_task` requires `company_id` in the request body and validates it exists in `project_companies` for the task's project (400 if invalid). No fallback to org-level companies or user.company_id. `contractor_trade_key` is required on the contractor's membership (409 if missing).

### Workflow Configuration
-   **Single-process mode**: Backend serves pre-built static frontend.

### Cloud Deployment (LIVE)
-   **Frontend**: Cloudflare Pages (`app.brikops.com`).
-   **Backend**: AWS Elastic Beanstalk (Docker, `api.brikops.com`).
-   **Database**: MongoDB Atlas.
-   **PDF Services**: S3-aware for reports, generating presigned URLs.
-   **CI/CD Pipeline**: Automatic deployment on `git push origin main` via GitHub Actions for backend (triggered by `backend/**` or `.platform/**` changes) and Cloudflare Pages for frontend. AWS authentication uses OIDC. Deploy bundle includes `Dockerrun.aws.json` + `.platform/` directory.
-   **EB Nginx Config**: `.platform/nginx/conf.d/proxy.conf` sets `client_max_body_size 20M` on the EB host nginx proxy.

## External Dependencies

-   **MongoDB Atlas**: Primary database.
-   **Meta WhatsApp Cloud API v21.0**: For real-time task event notifications and OTP delivery.
-   **Twilio SMS API**: Fallback for OTP and task notifications.
-   **Uvicorn**: ASGI server for FastAPI.
-   **React (Create React App)**: Frontend core library.
-   **Radix UI, TailwindCSS, shadcn/ui**: Frontend component and styling libraries.