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
-   **Plans Archive & Replace System**: Phase 1 (archive-first) and Phase 2 (replace) implemented. Archive replaces delete — plans never disappear. Replace flow: uploads new file as active, automatically archives the old plan with `archive_reason: "replaced"` and lightweight `replaces_plan_id`/`replaced_by_plan_id` linkage. Backend endpoints: `GET /plans` (active only), `GET /plans/archive`, `PATCH /plans/{id}/archive`, `PATCH /plans/{id}/restore`, `POST /plans/{id}/replace`. Permissions: same `PLAN_UPLOAD_ROLES` (project_manager, management_team) for archive/restore/replace; contractor/viewer read-only on both pages. Unit plans archive not yet implemented (intentional deferral).
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