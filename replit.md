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
-   **ProjectControlPage**: Workflow-first layout with a compact header, a 4-tab work switcher (ליקויים|בקרת ביצוע|תוכניות|מבנה), and inline views.
-   **InnerBuildingPage**: A focused building workspace for mobile at `/projects/:projectId/buildings/:buildingId` with a sticky header, 3-tab work switcher (דירות/קומות, ליקויים, בקרת ביצוע), KPI strip, collapsible floor → apartment hierarchy, FAB with add-floor (amber inline form) and add-unit (blue inline form) flows, per-floor + button for adding units, safe-area-aware FAB positioning, and auto-expand/scroll on new floor creation. QC tab navigates to building-specific QC page.
-   **BuildingQCPage**: Building-scoped QC floor selection at `/projects/:projectId/buildings/:buildingId/qc`. Shows only the target building's floors with QC status badges and quality indicators, client-side search and status filter chips (amber active state), compact summary line, smart back navigation, and no duplicate status chips per row. Reuses existing qcLabels/qcVisualStatus utilities.
-   **QC Navigation Unified**: Project-level QC entry (`/projects/:projectId/qc`) is now a lightweight building selector that routes into BuildingQCPage. All QC entry points (ProjectControlPage tab, ProjectDashboardPage link, FloorDetailPage back button) converge into this unified flow. No legacy floor-list-per-building QC page remains in the main user path.
-   **ProjectPlansPage**: Refreshed project-level plans page at `/projects/:projectId/plans`. Header "תוכניות פעילות". Mobile-first layout with compact dark header (project name subtitle), client-side search, horizontal scrollable discipline filter chips (amber active state), clean plan rows with filename/discipline/date/note, upload modal, inline add-discipline, and smart back navigation. Per-row actions for authorized roles: view, download, replace (blue RefreshCw icon), archive (gray Archive icon). Link to archive page. No delete in UI. No sidebar.
-   **ProjectPlansArchivePage**: Dedicated archive page at `/projects/:projectId/plans/archive`. Header "ארכיון תוכניות". Lists all archived project plans sorted by archive date. Shows archive reason badges: "הוחלפה" (blue, for replaced plans) or "הועברה לארכיון" (gray, for manual archives). Discipline chips (only populated disciplines shown), search, view/download for all roles, restore (RotateCcw icon) for authorized roles only. Link back to active plans page.
-   **ProjectPlanHistoryPage**: Dedicated version history page at `/projects/:projectId/plans/:planId/history`. Timeline-style view showing the full version chain for one logical plan. Current version at top with amber "נוכחית" badge; previous versions below with blue "הוחלפה" badge and version numbers. Each version shows filename, discipline, uploader, upload/archive dates, notes, and view/download actions. Vertical timeline line connects all versions. Entry point: clock icon (Clock) on active plan rows that have been replaced at least once (plan.replaces_plan_id exists). All roles can view history; no permission changes.
-   **Plans Read Tracking MVP**: Lightweight seen/unseen tracking for active project plans. When any user views/downloads a plan, a read receipt is recorded (`plan_read_receipts` collection, upsert per user per plan version). Managers (super_admin, project_manager, management_team) see a "נצפה על ידי X/Y" indicator per plan row. Tapping it opens a modal with "צפו" (green, with timestamps) and "טרם צפו" (gray) user lists. Y = all project members with trackable roles (project_manager, management_team, contractor, viewer). Replacing a plan naturally resets tracking (new plan_id = fresh receipts). Frontend tracking uses `fetch({ keepalive: true })` for reliability. History page only tracks current active version views. Contractor/viewer remain read-only — no management UI visible to them.
-   **Plans Archive & Replace System**: Phases 1-3 implemented. Phase 1: archive-first (no delete). Phase 2: replace flow with automatic archival. Phase 3: version history/timeline view. Backend endpoints: `GET /plans` (active only, includes seen_count/total_members for managers), `GET /plans/archive`, `GET /plans/{id}/history`, `GET /plans/{id}/seen` (management-only breakdown), `POST /plans/{id}/seen` (mark as viewed), `PATCH /plans/{id}/archive`, `PATCH /plans/{id}/restore`, `POST /plans/{id}/replace`. History endpoint walks the `replaces_plan_id` chain backward with cycle guard (max 50). Permissions: same `PLAN_UPLOAD_ROLES` (project_manager, management_team) for archive/restore/replace; all roles can view history and trigger seen tracking; seen breakdown modal is management-only; contractor/viewer read-only on all pages. Unit plans archive/history not yet implemented (intentional deferral).
-   **UnitPlansPage**: Refreshed unit-level plans page at `/projects/:projectId/units/:unitId/plans`. Matches ProjectPlansPage visual language: compact dark header with unit label + breadcrumb subtitle, client-side search, horizontal discipline chips (amber active), plan rows with title primary/actions secondary, amber upload modal, smart back navigation. No delete on unit plans (intentional product decision). No sidebar.

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: Main `router.py` is refactored into sub-routers for modularity (configuration, debug, plans, invites, companies, stats, authentication, projects, tasks, administration, billing).
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Email/password, phone OTP, PM approval, WhatsApp Magic Link Login, comprehensive onboarding.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp (with SMS fallback) using Meta-approved templates.
    -   **Security**: JWT tokens with HS256, issuer enforcement, secret versioning.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3).
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions.
    -   **Proof Management**: Multi-image proof uploads with client-side compression and validation.
    -   **Billing System**: Centralized billing management for organizations.
    -   **Admin & Member Management**: Tools for `super_admin`, PM, and owner-level team management.
    -   **QC (Quality Control) System**: Floor-level quality control with a hardcoded template, item management, RBAC, stage-based workflow, and an approver system.
    -   **Identity System**: Manages user accounts, status, and audit logging.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements.
    -   **Defects V2**: Parallel building-level and apartment-level defect views, gated by `ENABLE_DEFECTS_V2` feature flag, including `BuildingDefectsPage` and `ApartmentDashboardPage`.
    -   **Defects Export (Excel + PDF)**: `POST /api/defects/export` endpoint supporting `unit` or `building` scope and `excel` or `pdf` format. Excel exports are `.xlsx` with Hebrew headers and RTL. PDF exports are A4 with Rubik font and Hebrew RTL, designed to keep defect cards and images together.

### Demo / Reviewer Access System
-   **Controlled enablement**: `ENABLE_DEMO_USERS` env var (defaults to `true` in dev, `false` in prod). Also supports `DEMO_DEFAULT_PASSWORD` and `DEMO_RESET_PASSWORDS`.
-   **Demo accounts**: 4 stable reviewer accounts (`demo-pm@brikops.com`, `demo-team@brikops.com`, `demo-contractor@brikops.com`, `demo-viewer@brikops.com`) — all with `is_demo: true`, email+password auth.
-   **Demo org**: "חברת הדגמה" with `is_demo: true`, owned by demo-pm, subscription comped until 2030-12-31 (uses existing `is_comped` mechanism — zero changes to billing logic).
-   **Demo data**: `ensure_demo_data()` seeds 1 project ("פרויקט מגדלי הדמו"), 2 buildings, 6 floors, 30 units, 16 defects (mixed statuses), 3 contractor companies, 3 QC runs with 165 items, and billing (plan_pro, 30 units, 2900 ILS/mo, setup_state=ready).
-   **Isolation**: All demo records tagged `is_demo: true`. Seeding is fully idempotent. No changes to billing.py, auth_router.py, or paywall middleware.
-   **Startup order**: Demo users/org first → migrations/billing plans → demo data seeding (ensures billing plans exist before demo billing snapshot).
-   **Login default**: When `ENABLE_DEMO_USERS=true`, login page defaults to Email/Password tab (via `enable_demo_users` feature flag in `/api/config/features`). Phone+OTP remains available.
-   **Password hardening**: In non-dev environments, `DEMO_DEFAULT_PASSWORD` must be explicitly set via env var or demo seeding is disabled (fail-safe, no crash).
-   **Reviewer guide**: `docs/demo-reviewer-guide.md` — template with `<DEMO_PASSWORD>` placeholder, includes Apple App Store Connect and Google Play Console copy-paste submission text.
-   **Module**: `backend/contractor_ops/demo_seed.py` — isolated demo seeding logic.

### Workflow Configuration
-   **Single-process mode**: Backend serves pre-built static frontend.

### Deploy Pipeline
-   **Staleness Detection**: Forces frontend rebuild if source files are newer.
-   **Build Command**: Uses CRACO for React build.
-   **Post-build Verification**: Logs bundle details and aborts on failure.
-   **Fail-fast**: `set -euo pipefail` and explicit checks.
-   **Nginx Proxy Config**: Configures AWS EB nginx reverse proxy with specific timeouts and logging.
-   **Paywall Middleware Safety**: Ensures `paywall_middleware` calls `call_next(request)` exactly once.
-   **Change Detection**: Detects backend/platform changes for backend deploy and frontend changes for frontend deploy.
-   **Contractor Image Guard**: Backend enforces at least one image before contractor assignment.
-   **Upload Image Validation**: Task attachment endpoint validates file content type, size, and image integrity.
-   **Mobile Upload Resilience**: `NewDefectModal` retries image uploads with exponential backoff and uses `createImageBitmap` for HEIC compression.
-   **Cloud Deployment**:
    -   **Frontend**: Cloudflare Pages.
    -   **Backend**: AWS Elastic Beanstalk (Docker).
    -   **Database**: MongoDB Atlas.
    -   **PDF Services**: S3-aware for reports.
    -   **CI/CD Pipeline**: Automatic deployment on `git push origin main` via GitHub Actions for backend and Cloudflare Pages for frontend.

### Security Enhancements
-   **JWT Implementation**: Migrated to `PyJWT==2.11.0` for all JWT encode/decode operations to address previous `ecdsa` dependency issues, ensuring HS256 algorithm usage and consistent validation.
-   **OTP Flow Hardening**: Implemented comprehensive protections including send and verify rate limits (per-IP, per-phone, per-phone+IP combo), brute-force lockout, one-time use of OTPs, 6-digit SHA-256 hashed codes, generic error messages, and structured audit logging. All OTP rate limits are persistent in MongoDB.
-   **Webhook Signature Enforcement**: When `META_APP_SECRET` is configured, all incoming webhook requests MUST include a valid `X-Hub-Signature-256` header. Missing signatures are rejected with 401 (previously only warned).
-   **CORS Hardening**: Production must set `CORS_ORIGINS` env var (e.g., `https://app.brikops.com,https://www.brikops.com`). Defaults to `*` only when unset (dev convenience).
-   **PASSWORD_RESET_BASE_URL**: Defaults to `https://app.brikops.com` (not `www`). Set explicitly in production env vars.
-   **/ready Endpoint Minimized**: Returns only `ready` boolean and `database` status. No user/project counts or app_id exposed.

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