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
-   **UI/UX**: Leverages Radix UI, TailwindCSS, and shadcn/ui for a modern, responsive user experience. Features include dynamic dashboards, hierarchical navigation, a consistent color palette (amber for CTA/brand, slate for neutral, emerald for success, red for failure), multi-step task management with visual timelines and proof galleries, email/password and OTP-based authentication, and role-based dynamic routing.
-   **Key Pages**: ProjectControlPage, InnerBuildingPage, BuildingQCPage, UnitQCSelectionPage, ProjectPlansPage, ProjectPlansArchivePage, ProjectPlanHistoryPage, UnitPlansPage are designed with mobile-first principles, client-side search, discipline filters, and role-based actions.
-   **Onboarding Flow**: OnboardingPage creates org+project then redirects to `/projects/{id}/control?showQuickSetup=true`. ProjectControlPage shows an OnboardingChecklist component (below KPI) for new projects with 5 items: org/project, buildings, company, team member, first defect. Auto-dismisses when all complete; manual dismiss via "דלג לעת עתה". Backend `PUT /api/projects/{id}/onboarding-complete` marks project done. StructureTab shows welcome empty state during onboarding. Defects mode shows a nudge banner when buildings exist but no defects yet.
-   **Admin Panel**: Tab-based layout at `/admin` with סקירה/משתמשים/ארגונים/חיובים/יומן tabs. MyProjectsPage shows an "אדמין פאנל" banner link for SA users (replaces old 3-card grid). AdminPage has gradient header, stat cards, payment requests, audit activity, and system info. AdminOrgsPage at `/admin/orgs` provides dedicated org management with search, filter chips, and inline accordion drill-down showing projects, members, and subscription info per org. Includes core management actions: subscription overrides (activate/comp/suspend/unsuspend via existing billing override endpoint), inline org name editing (pencil icon → input + save/cancel), and org owner change (bottom sheet → confirmation dialog, stepup-protected). Backend endpoints: PUT /api/admin/orgs/{org_id} (name update) and PUT /api/admin/orgs/{org_id}/owner (owner change).
-   **Plans Read Tracking MVP**: Lightweight seen/unseen tracking for active project plans with manager-specific visibility and detailed user lists.
-   **Plans Archive & Replace System**: Implements an archive-first approach with automatic archival on plan replacement and a comprehensive version history/timeline view.

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: Modularized into sub-routers for better organization.
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Email/password, phone OTP, PM approval, WhatsApp Magic Link Login.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp (with SMS fallback).
    -   **Security**: JWT tokens with HS256, issuer enforcement, secret versioning, robust OTP flow hardening, webhook signature enforcement, and CORS hardening.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3).
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions.
    -   **Proof Management**: Multi-image proof uploads with client-side compression and validation.
    -   **Billing System**: Centralized billing management with RBAC — org owner/billing_admin/super_admin can edit; project_manager has read-only view; management_team/contractor/viewer have no billing access.
    -   **Admin & Member Management**: Tools for `super_admin`, PM, and owner-level team management.
    -   **QC (Quality Control) System**: Floor-level and unit-level quality control with template v6 (hardcoded constant as fallback), item management, RBAC, stage-based workflow, and an approver system. Supports scope model (`scope: 'floor'|'unit'`) on template stages and qc_runs. Unit-scoped stage: `stage_tiling` (9 items, scope='unit') — tiling is inspected per apartment. Each of the 7 floor-scope stages has a final "קומפלט" photo item (cp_complete, br_complete, etc.) — documentation points only, NOT approval gates. General backfill via `_backfill_missing_items()` ensures new template items appear in existing runs. Endpoints: `GET /api/qc/units/{unit_id}/run` (get/create unit run with backfill), `GET /api/qc/floors/{floor_id}/units-status` (per-unit tiling progress), `GET /api/qc/projects/{project_id}/execution-summary` (project-wide per-stage progress with building/floor/unit breakdown). Stages include `is_completable` computed field. MongoDB indexes on `qc_runs` for `floor_id+template_id` and `unit_id+template_id`. Batch-status only includes floor-scope stages. UnitQCSelectionPage lists units with progress; StageDetailPage supports unit mode via navigation state (returnTo, unitName, scope). ProjectDashboardPage shows "סטטוס ביצוע" section with overall project progress (stage-instance totals), per-stage progress bars (floor stages show "X/Y קומות", unit stages show "X/Y דירות"), and click-to-expand per-building breakdown with status badges.
    -   **QC Template Management**: `qc_templates` collection with family-based versioning — each edit creates a new immutable version document. Default template seeded from FLOOR_TEMPLATE constant on startup (idempotent). Admin CRUD endpoints: list families (with search, sort, include_archived params, `?type=qc|handover` filter), get version, create family, edit (new version), clone, assign to project, archive/restore family. `_get_template()` 3-tier resolution: run.template_version_id → project.qc_template_version_id (with legacy qc_template_id fallback) → default active → FLOOR_TEMPLATE. Project assignment stores `qc_template_version_id` + `qc_template_family_id`. GET endpoint (`/api/projects/{id}/qc-template`) returns assignment info + `newer_version_available` flag, accessible to PM/owner/management (not contractors). Admin UI at `/admin/qc-templates` with search, sort (name/version/date), archive toggle, and inline stage/item editor. Project control page has "תבנית QC" tab: super_admin can select family + version + save; PM/owner sees read-only view. Archive guard prevents archiving families assigned to active projects (checks both new and legacy fields). Templates now have `type` field: "qc" (default, migrated) or "handover". Migration auto-adds `type: "qc"` to existing templates on startup.
    -   **Handover Protocol System (Phase 1a)**: Unit-level handover protocol management for initial and final inspections. Backend-only (no UI yet). `handover_router.py` with 11 endpoints. Template resolution: project `handover_template_version_id` → DB default (type=handover, is_default=true) → HANDOVER_TEMPLATE constant (15 sections, ~145 items). Protocol status flow: draft→in_progress→signed. Auto-transitions draft→in_progress on first item update. Signed protocols are locked (403 on all mutations). Only super_admin can reopen with reason. `handover_protocols` collection with unique index on (project_id, unit_id, type). Initial protocols have no meters/delivered_items; final protocols include both. Legal text sourced from org fields (`default_handover_legal_text_initial`/`_final`). `create-defect` creates a task with `source: "handover_initial"|"handover_final"` and links back via `defect_id` on the item (409 if already exists). Summary endpoint provides per-building breakdown with status counts + open handover defects.
    -   **Identity System**: Manages user accounts, status, and audit logging. Includes WhatsApp notification opt-out preference (`whatsapp_notifications_enabled` field, `PUT /api/auth/me/whatsapp-notifications`).
    -   **Accessibility**: Public `/accessibility` route with Hebrew accessibility statement (הצהרת נגישות) per Israeli law. Links from login page and account settings. Skip-to-content link, login tab panel ARIA (role=tabpanel, aria-controls), password toggle a11y (aria-label/aria-pressed), progress bar/ring ARIA attributes, FAB aria-label/aria-expanded, Hebrew noscript fallback.
    -   **Structure Permissions**: Building/floor/unit mutations (create, archive, restore, bulk, import, resequence) restricted to org owner, billing_admin, or super_admin via `_check_structure_admin()`. Frontend hides mutation UI (FAB, archive buttons) when `canMutateStructure` is false.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements.
    -   **Defects V2**: Parallel building-level and apartment-level defect views.
    -   **Defects Export**: Supports Excel and PDF exports with Hebrew RTL formatting.
    -   **Observability**: Structured per-request logging with request ID correlation (X-Request-ID header), Hebrew error boundary for frontend crashes, `/health` (uptime) and `/ready` (DB connectivity with 503 on failure) endpoints.

### Deployment and Security
-   **Workflow Configuration**: Single-process mode where backend serves pre-built static frontend.
-   **Deploy Pipeline**: Automated build and deployment process with staleness detection, post-build verification, and fail-fast mechanisms.
-   **Cloud Deployment**: Frontend on Cloudflare Pages, Backend on AWS Elastic Beanstalk (Docker), Database on MongoDB Atlas, PDF services S3-aware. CI/CD via GitHub Actions.
-   **Security**: Enhanced JWT implementation, hardened OTP flow with MongoDB-backed rate limits and audit logging, strict webhook signature enforcement (fail-closed), configured CORS with explicit production origins, SHA-256 hashed password reset tokens, project-scoped task updates access control, session invalidation on password reset, and sanitized regex search inputs.

## External Dependencies

-   **MongoDB Atlas**: Primary database.
-   **Meta WhatsApp Cloud API v21.0**: For real-time task event notifications and OTP delivery.
-   **Twilio SMS API**: Fallback for OTP and task notifications.
-   **Uvicorn**: ASGI server for FastAPI.
-   **React**: Frontend core library.
-   **Radix UI, TailwindCSS, shadcn/ui**: Frontend component and styling libraries.
-   **openpyxl**: For Excel export functionality.
-   **reportlab, arabic_reshaper, python-bidi, Pillow**: For PDF export functionality.
-   **PyJWT**: For JWT token handling.