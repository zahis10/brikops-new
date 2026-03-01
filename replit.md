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
-   **Key Modules & Features**:
    -   **Data Models**: Uses Pydantic models and enums.
    -   **RBAC-Protected API**: Approximately 30 API endpoints with two-tier RBAC (platform-level and project-level roles).
    -   **Authentication & Onboarding**: Supports email/password, phone OTP, PM approval for new users, and WhatsApp Magic Link Login. Includes comprehensive onboarding and unified management registration. Dev-only `POST /api/auth/dev-login` endpoint for demo users (accepts role, returns token). `ensure_demo_users()` runs on dev startup to guarantee demo accounts exist. Phone number change is consolidated into Account Settings (`/settings/account#phone`) via `PhoneChangeModal` reuse; phone icon in projects toolbar navigates to settings.
    -   **Multi-channel Communication**: Automated notifications for task creation via WhatsApp (with SMS fallback) and a robust notification service. WhatsApp uses Meta-approved templates: login via `brikops_login_link` (en, URL button with token param extracted via `urllib.parse`), defect notifications via language-specific templates (`brikops_defect_new` en, `brikops_defect_new_he` he→en Meta quirk, `brikops_defect_new_ar` ar) with header image (public HTTPS), 3 named body params (`location`, `issue`, `ref` with `parameter_name` field), and URL button (task_id only). Template config in `config.py` (`WA_DEFECT_TEMPLATES` map). Per-user `preferred_language` field (he/en/ar/zh, default he) drives template selection: `_resolve_target_phone` returns `{phone_e164, preferred_language}`, stored as `defect_lang` in notification job payload, passed to `send_message(defect_lang=...)`. zh→en fallback with explicit log. SA-only `PUT /api/admin/users/{user_id}/preferred-language` endpoint with audit event (`admin_preferred_language_change`, old/new values). Admin UI dropdown in `AdminUsersPage` drawer and `UserDrawer` (SA-only via `currentUserPlatformRole` prop).
    -   **Security**: Implements JWT tokens with HS256, issuer enforcement, and secret versioning.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3).
    -   **Unit Plans**: Manages unit plans organized by discipline.
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions, including categorization and bucketing.
    -   **Proof Management**: Multi-image proof uploads with audit logging.
    -   **Billing System (Single Source of Truth)**: `/billing/org/{org_id}` is the sole page for all billing actions (payment requests, renewals, mark-paid, receipts, approvals). All other locations (ProjectBillingCard, TrialBanner, PaywallModal) are read-only status displays with a single CTA "מעבר לניהול חיוב" linking to the central billing page via `getBillingHubUrl()` helper (`frontend/src/utils/billingHub.js`). Organization-level access control (trial/active/read_only), plan management, per-project billing, and a defined setup state workflow. Includes features for billing responsibility delegation, plan merchandising, monthly invoicing processes, and display of billing validity. Payment request lifecycle: requested/sent → pending_review → paid/rejected. PM users can create and view own payment requests (server-filtered). SA has cross-org open payment requests summary on admin dashboard (`GET /api/admin/billing/payment-requests-summary`). Anti-spam: only one open payment request per org (any cycle); cancel endpoint (`POST .../cancel`) with 409 on non-cancelable statuses. SA UI shows only approve/reject controls on org billing page (no customer renewal panel). Admin billing page uses generation-guarded data loading with concurrency guard (prevents race conditions, stale responses, and data collapse on rapid refresh). Rate limits: GET 30/60s, mutations 10/60s per admin user. Payment requests persist `requested_by_kind` (billing_manager/pm_handoff) based on RBAC path; admin summary shows requester kind labels and DD.MM.YYYY dates with RTL-safe `<bdi dir="ltr">` wrapping. SA can view payment requests on OrgBillingPage (`canViewRequests` includes `isSA`). Admin summary "פתח חיוב ארגון" deep-links with `?highlight={request_id}#requests` for auto-expand + scroll + highlight flash. Billing management authority (`can_manage_billing`) requires owner, org_admin, billing_admin, or SA role. Only PMs see the fallback "בקש שדרוג מבעלים" section; regular team members (contractor, site_manager, viewer) see no payment request UI. OrgBillingPage supports `?project_id={id}` query param for project context banner ("הגעת מפרויקט") with back-link.
    -   **Admin & Member Management**: Tools for `super_admin`, PM, and owner-level team management, including role changes, member removal, and admin password reset with audit events.
    -   **QC (Quality Control) System**: Floor-level quality control with a hardcoded template, detailed item management, strict RBAC, a stage-based workflow, and an approver system with scope management.
    -   **Identity System**: Manages user accounts, including account status, completion, and audit logging.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements (buildings, floors, units) with cascade operations.
    -   **Role Conflict Guard**: Prevents a user from holding both `contractor` (project-level) and any org management role (`owner`, `org_admin`, `billing_admin`) within the same organization. Both directions enforced: contractor→management blocked and management→contractor blocked. Unified audit event (`role_conflict_blocked`) with fields: `actor_id`, `target_user_id`, `org_id`, `attempted_role`, `current_roles`, `reason`. HTTP 409 with message "לא ניתן לשלב תפקיד קבלן עם תפקיד ניהולי בארגון". Frontend disables conflicting choices with tooltip in both `UserDrawer` and `AdminUsersPage`.
    -   **Contractor Company+Trade Assignment (Membership-level)**: Company and trade are now stored on `project_memberships` (not user doc). Source of truth for assignment: `membership.company_id` (references `project_companies`) + `membership.contractor_trade_key`. `InviteCreate` schema accepts `company_id`; required for contractor invites. All invite accept flows (onboarding, register auto-link, PM auto-link) carry `company_id` + `trade_key` to membership. `PUT /api/projects/{project_id}/members/{user_id}/contractor-profile` edit endpoint (RBAC: PM/owner/org_admin/SA) with audit event `member_contractor_profile_changed` (old/new values). Assignment guardrail: 409 `CONTRACTOR_UNASSIGNED` if contractor lacks company_id or trade. Backwards compatible: existing members without company_id shown as "לא משויך לחברה/תחום". Frontend: AddTeamMemberForm requires company for contractors, UserDrawer shows/edits contractor profile, assignee pickers filter out unassigned contractors. **Project Company creation**: Only `name` is required; `trade`, `contact_name`, `contact_phone` are optional (stored as null when empty). Inline quick-add "+ הוסף חברה חדשה" button in both AddTeamMemberForm and UserDrawer creates company with name-only and auto-selects it. Single `loadCompanies` callback from `ProjectControlPage` refreshes company list across all sub-components. UserDrawer uses `silentRefresh` (no loading spinner) after contractor profile save to prevent blank page. **Auto-focus trade**: After quick-add company, trade dropdown auto-focuses/opens (AddTeamMemberForm clicks SelectField button via ref, UserDrawer focuses native select via ref). Timer refs with `clearTimeout` on unmount prevent leaks/double-fire. **No-companies CTA**: NewDefectModal and TaskDetailPage show amber CTA banner "אין חברות בפרויקט" with "הוסף חברה" button (navigates to `/projects/{pid}/control?tab=companies`) when `companies.length === 0`. NewDefectModal closes modal before navigating; button disabled if `projectId` is empty.

### Workflow Configuration
-   **Single-process mode**: Backend serves pre-built static frontend.

### Cloud Deployment Prep
-   **Target Architecture**: Frontend on Cloudflare Pages, Backend API on AWS App Runner, Files on S3.

## External Dependencies

-   **MongoDB Atlas**: Primary database.
-   **Meta WhatsApp Cloud API v21.0**: For real-time task event notifications and OTP delivery.
-   **Twilio SMS API**: Fallback for OTP and task notifications.
-   **Uvicorn**: ASGI server for FastAPI.
-   **React (Create React App)**: Frontend core library.
-   **Radix UI, TailwindCSS, shadcn/ui**: Frontend component and styling libraries.