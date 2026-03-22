# BrikOps - Construction Task Management System

## Overview
BrikOps is an MVP full-stack application designed to streamline construction task management in construction projects. Its core purpose is to enhance workflows, improve communication, and provide comprehensive oversight. Key capabilities include robust Role-Based Access Control (RBAC), a defined task lifecycle with strict status transitions, detailed audit logging, file attachment capabilities, and a real-time updates feed. The project aims to become a leading solution in the construction management software market with significant market potential.

## User Preferences
- This app is NOT BedekPro. Do NOT add inspection-report logic.
- Hebrew content in demo data
- Strict RBAC enforcement
- Task status transitions must follow defined workflow

## System Architecture

### Core Design Principles
BrikOps is a full-stack application with a clear separation between frontend and backend, emphasizing secure access via RBAC, a meticulously defined task workflow, and real-time communication capabilities. The system is designed for deployment in VM environments, with the backend serving both the API and static frontend assets.

### Frontend
-   **Framework**: React (Create React App with CRACO).
-   **UI/UX**: Radix UI, TailwindCSS, and shadcn/ui provide a modern, responsive user experience with dynamic dashboards, hierarchical navigation, multi-step task management, and role-based dynamic routing. Mobile-first design, client-side search, and discipline filters are key.
-   **Onboarding Flow**: Guided onboarding for organization and project creation, followed by a setup checklist.
-   **Admin Panel**: Comprehensive management for organizations, users, billing, and audit activities.
-   **Plans Management**: Card grid layout with discipline/floor filters, search, upload with name/plan_type/floor/unit metadata, detail modal with inline editing, file type icons, tenant_changes display badge, seen/unseen tracking, archive, version history, versioning (v1/v2/v3 badges, version history in detail modal, upload new version), bulk upload (up to 20 files, 50MB each, default discipline, per-file overrides, batched concurrency=3, partial success with retry), and auto-generated thumbnails (image resize + PDF first-page via Pillow/pdf2image, async non-blocking).
    -   **Unit Plans Page**: Card grid layout with thumbnails, two-section design (שינויי דיירים / תוכניות כלליות), plan_type selector in upload modal, discipline filter + search, detail modal with preview/download.
-   **Accessibility**: Implements accessibility features per Israeli law, including ARIA attributes and Hebrew noscript fallback.

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: Modularized into sub-routers.
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Supports email/password, phone OTP, PM approval, and WhatsApp Magic Link Login.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp with SMS fallback.
    -   **Security**: JWT tokens, robust OTP flow, webhook signature enforcement, and CORS hardening.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3).
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions.
    -   **Proof Management**: Multi-image proof uploads with client-side compression and validation.
    -   **Photo Annotation**: Konva.js-based canvas markup for defect photos (arrow, circle, text tools with color picker). Lazy-loaded via React.lazy to avoid bundle impact. V1 integrated in NewDefectModal only. Original photos preserved alongside annotated versions.
    -   **Billing System**: Centralized billing management with RBAC.
    -   **Admin & Member Management**: Tools for super_admin, PM, and owner-level team management.
    -   **QC (Quality Control) System**: Floor-level and unit-level quality control with template versioning, item management, RBAC, stage-based workflow, and an approver system. Supports scope models for templates and QC runs.
    -   **Handover Protocol System**: Unit-level handover protocol management for initial and final inspections, including engine-managed forms, status flows, and digital signatures for multiple roles. Includes defect creation from handover items and legal section management.
    -   **G4 Tenant Data Import**: Excel/CSV import of tenant (buyer) data for handover protocols with preview and upsert functionality.
    -   **Admin CS Dashboard**: Read-only analytics dashboard for super_admin providing KPIs, alerts, activity charts, and organization data.
    -   **WhatsApp Auto-Reminders**: Automated and manual WhatsApp reminders for contractors with open defects and PM daily digests, with cooldowns, Shabbat protection, and per-user reminder preferences (enable/disable per type + weekday selection, stored on user document as `reminder_preferences`). Preferences only apply to cron/automated triggers; manual sends always bypass. Company contacts (is_company=True) always receive regardless of preferences.
    -   **Identity System**: Manages user accounts, status, and audit logging.
    -   **Structure Permissions**: Role-based restrictions for building/floor/unit mutations.
    -   **Unit Type Tags & Notes**: Optional `unit_type_tag` (mekhir_lemishtaken / shuk_hofshi) and `unit_note` (max 200 chars) fields on units. Supported in create and PATCH endpoints. Displayed as colored badges and gray text in InnerBuildingPage and BuildingDefectsPage with client-side filter chips and inline edit modal.
    -   **Login Redirect Cookie**: `brikops_logged_in` cookie set on `.brikops.com` domain on all login paths, cleared on logout/auth failure, refreshed on token renewal. Used as hint for landing page redirect (not authentication).
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements.
    -   **Defects V2**: Parallel building-level and apartment-level defect views.
    -   **Defects Export**: Supports Excel and PDF exports with Hebrew RTL formatting.
    -   **Handover PDF Export**: Generates PDF of signed handover protocols using WeasyPrint.
    -   **Observability**: Structured per-request logging (two-tier: WARNING ≥800ms, DEBUG ≥500ms), Hebrew error boundary, and health/readiness endpoints.
    -   **Performance Optimization**: Task list endpoint pagination (limit/offset query params, default 50, max 200, returns envelope `{items, total, limit, offset}`). MongoDB indexes on `project_plans` and `unit_plans` collections. S3 presigned URL TTL cache (10min, max 5000 entries, thread-safe). Feature flags fetched once at login via AuthContext (eliminates per-page waterfall requests).
    -   **Deploy Checklist**: If backend response format changes (e.g. array → envelope), frontend MUST be rebuilt (`cd frontend && CI=true REACT_APP_BACKEND_URL="" npx craco build`) and deployed in the same release. `taskService.list()` has defensive guards for both formats.

### Deployment and Security
-   **Workflow Configuration**: Single-process mode where backend serves pre-built static frontend.
-   **Deploy Pipeline**: Automated build and deployment with staleness detection and verification.
-   **Cloud Deployment**: Frontend on Cloudflare Pages, Backend on AWS Elastic Beanstalk (Docker), Database on MongoDB Atlas, CI/CD via GitHub Actions.
-   **Security**: Enhanced JWT with sliding 30-day auto-renewal (active users never logout; renewal triggers silently when <15 days remain; super_admin 30-min tokens exempt), hardened OTP flow, strict webhook signature enforcement, configured CORS, SHA-256 hashed password reset tokens, project-scoped access control, session invalidation, and sanitized regex search inputs.

## External Dependencies

-   **MongoDB Atlas**: Primary database.
-   **Meta WhatsApp Cloud API v21.0**: For real-time task event notifications and OTP delivery.
-   **Twilio SMS API**: Fallback for OTP and task notifications.
-   **Uvicorn**: ASGI server for FastAPI.
-   **React**: Frontend core library.
-   **Radix UI, TailwindCSS, shadcn/ui**: Frontend component and styling libraries.
-   **openpyxl**: For Excel export and G4 tenant data import functionality.
-   **WeasyPrint**: For handover protocol PDF generation.
-   **PyJWT**: For JWT token handling.
-   **Pillow + pdf2image**: For thumbnail generation (image resize, PDF first-page extraction).