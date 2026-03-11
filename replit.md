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
-   **ProjectControlPage (redesigned)**: Workflow-first layout. Compact header → 4-tab work switcher (ליקויים|בקרת ביצוע|תוכניות|מבנה) → inline views. `workMode` state: 'structure' (default, shows KPI + buildings + secondary management pills) or 'defects' (building selector → V2 per-building defects). בקרת ביצוע/תוכניות navigate out to /qc and /plans. FAB replaces old bottom bar with add actions (building/floors/units/excel). הקמה מהירה only when hierarchy is empty.

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: The main `router.py` is refactored into sub-routers for modularity, each handling specific domains like configuration, debug, plans, invites, companies, stats, authentication, projects, tasks, administration, and billing.
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Supports email/password, phone OTP, PM approval, WhatsApp Magic Link Login, and comprehensive onboarding, including deep-link preservation.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp (with SMS fallback) using Meta-approved templates, configurable by user's preferred language, with robust image handling and error reporting.
    -   **Security**: Implements JWT tokens with HS256, issuer enforcement, and secret versioning.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3) with asynchronous operations.
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions.
    -   **Proof Management**: Multi-image proof uploads with client-side compression, audit logging, and strict validation.
    -   **Billing System**: Centralized billing management for organizations, including payment requests, renewals, plan management, and an anti-gaming policy.
    -   **Admin & Member Management**: Tools for `super_admin`, PM, and owner-level team management.
    -   **QC (Quality Control) System**: Floor-level quality control with a hardcoded template, detailed item management, strict RBAC, a stage-based workflow, and an approver system.
    -   **Identity System**: Manages user accounts, including account status, completion, and audit logging.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements with cascade operations.
    -   **Defects V2**: Parallel building-level and apartment-level defect views, gated by `ENABLE_DEFECTS_V2` feature flag. Includes `BuildingDefectsPage` and `ApartmentDashboardPage` with task defect count aggregation. Both pages use a generic `FilterDrawer` component (Radix Sheet, `sections` prop for arbitrary filter sections, draft pattern). `BuildingDefectsPage` filters: סטטוס (פתוחים/סגורים/חוסמי מסירה), תחום (category), קומה (floor), דירה (unit). `ApartmentDashboardPage` filters: status, category, company, assignee, created_by. Backend returns per-unit `categories` array in building defects summary. `NewDefectModal` includes "הוסף חברה" link, auto-select single company, and no-contractors helper UX.
    -   **Defects Export (Excel + PDF)**: `POST /api/defects/export` endpoint in `export_router.py`. Supports scope `unit` or `building` with `format` parameter (`excel` or `pdf`, validated). Server-side filtering matching frontend semantics (status groups differ by scope: building "open" = all non-closed; apartment "open" = open/assigned/reopened, "in_progress" = separate group). **Excel**: `.xlsx` with Hebrew headers, RTL sheet, amber header row, auto-filter, image URLs as clickable hyperlinks. **PDF**: A4 pages with Rubik font, Hebrew RTL via arabic_reshaper+bidi. Each defect rendered as a card container (outer Table with border/padding/background) wrapped in `KeepTogether` so defect+images stay on same page. Card includes amber header bar, details table, up to 2 embedded images (max 12×7cm normal, 7×4.5cm reduced fallback) with Hebrew captions ("תמונה 1", "תמונה 2") grouped with their images. Fallback strategy: if card exceeds page height, retry with reduced images; if still too tall, allow natural page split. SSRF-protected image fetching with host allowlist. Frontend: `exportService.exportDefects()` in `api.js` (blob download with format param), `ExportModal` component (Radix Dialog) with format picker (Excel/PDF toggle, amber highlight), export button ("ייצוא") on both defect pages. Dependencies: `openpyxl`, `reportlab`, `arabic_reshaper`, `python-bidi`, `Pillow`.

### Workflow Configuration
-   **Single-process mode**: Backend serves pre-built static frontend.

### Deploy Pipeline
-   **Staleness Detection**: Automatically forces frontend rebuild if source files are newer than the compiled bundle.
-   **Build Command**: Uses CRACO for React build.
-   **Post-build Verification**: Logs bundle details and aborts if build fails.
-   **Fail-fast**: `set -euo pipefail` and explicit checks ensure deployment integrity.
-   **Nginx Proxy Config**: Configures AWS EB nginx reverse proxy with `client_max_body_size`, `proxy_read_timeout`, `proxy_send_timeout`, `proxy_connect_timeout` and custom `log_format timed` for request timing.
-   **Paywall Middleware Safety**: Ensures `paywall_middleware` calls `call_next(request)` exactly once within a narrow `try/except` block.
-   **Change Detection**: Detects backend/platform changes for backend deploy and frontend changes for frontend deploy.
-   **Contractor Image Guard**: Backend enforces a policy that tasks must have at least one image before contractor assignment.
-   **Upload Image Validation**: Task attachment endpoint validates each file's content type, size, and image integrity.
-   **Mobile Upload Resilience**: `NewDefectModal` retries image uploads with exponential backoff and uses `createImageBitmap` for HEIC compression.
-   **Cloud Deployment**:
    -   **Frontend**: Cloudflare Pages.
    -   **Backend**: AWS Elastic Beanstalk (Docker).
    -   **Database**: MongoDB Atlas.
    -   **PDF Services**: S3-aware for reports.
    -   **CI/CD Pipeline**: Automatic deployment on `git push origin main` via GitHub Actions for backend and Cloudflare Pages for frontend.

## External Dependencies

-   **MongoDB Atlas**: Primary database.
-   **Meta WhatsApp Cloud API v21.0**: For real-time task event notifications and OTP delivery.
-   **Twilio SMS API**: Fallback for OTP and task notifications.
-   **Uvicorn**: ASGI server for FastAPI.
-   **React**: Frontend core library.
-   **Radix UI, TailwindCSS, shadcn/ui**: Frontend component and styling libraries.

## Security Remediations
-   **ecdsa dependency (2026-03)**: Removed `ecdsa==0.19.1` from direct `requirements.txt`. The package was a transitive dependency of `python-jose` (pure-python ECDSA with known timing side-channel vulnerabilities). Changed declaration to `python-jose[cryptography]==3.5.0` to explicitly require the safe `cryptography` backend. **Note**: `ecdsa` remains installed transitively because `python-jose==3.5.0` has it as a hard base dependency — but it is **never loaded at runtime**. All JWT operations use HS256 (HMAC) via the `cryptography` backend. The `ecdsa` fallback backend is never reached because `cryptography` is present and takes priority in `jose.backends`. Zero `ecdsa` modules appear in `sys.modules` during app execution.