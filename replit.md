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

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: The main `router.py` is refactored into sub-routers for modularity, each handling specific domains like configuration, debug, plans, invites, companies, stats, authentication, projects, tasks, administration, and billing.
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Supports email/password, phone OTP, PM approval, WhatsApp Magic Link Login, and comprehensive onboarding, including deep-link preservation across login flows.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp (with SMS fallback) using Meta-approved templates, configurable by user's preferred language (he/en/ar/zh), with robust image handling and error reporting for WhatsApp messages. Template mapping in `config.py`: `WA_DEFECT_TEMPLATES` (per-language defect templates, overridable via env vars `WA_DEFECT_TEMPLATE_HE/EN/AR/ZH`), `WA_QC_REJECT_TEMPLATE_HE` (dedicated QC rejection template with named params: project_name, location, stage_name, item_name, rejection_reason + URL button), `WA_LOGIN_TEMPLATE_HE` (login link template). Language codes match Meta registrations (HE=he, EN=en, AR=ar).
    -   **Security**: Implements JWT tokens with HS256, issuer enforcement, and secret versioning.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3) with asynchronous operations.
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions, including categorization and bucketing.
    -   **Proof Management**: Multi-image proof uploads with client-side compression, audit logging, and strict validation for contractor-facing notifications.
    -   **WhatsApp Notification Debug**: Provides detailed `notification_status` for sent messages, reflecting real delivery states in the frontend.
    -   **Billing System**: Centralized billing management for organizations, including payment requests, renewals, plan management, access control based on subscription status, and an anti-gaming policy for unit adjustments. Features an `UpgradeWizard` for project-based plan and unit management.
    -   **Admin & Member Management**: Tools for `super_admin`, PM, and owner-level team management, including role changes, member removal, and admin password reset with audit events.
    -   **QC (Quality Control) System**: Floor-level quality control with a hardcoded template, detailed item management, strict RBAC, a stage-based workflow, and an approver system with scope management.
    -   **Identity System**: Manages user accounts, including account status, completion, and audit logging.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements with cascade operations.
    -   **Role Conflict Guard**: Prevents users from holding conflicting roles within the same organization.
    -   **Contractor Company+Trade Assignment**: Manages contractor assignments at the project membership level with validation.

### Workflow Configuration
-   **Single-process mode**: Backend serves pre-built static frontend.

### Deploy Pipeline (`deploy.sh`)
-   **Staleness Detection**: Before deploy, `check_frontend_staleness()` compares timestamps of all frontend build inputs (`frontend/src/`, `frontend/public/`, `package.json`, `yarn.lock`, `craco.config.js`, `tailwind.config.js`, `postcss.config.js`) against the compiled bundle (`frontend/build/static/js/main*.js`). If source is newer or bundle is missing, a rebuild is forced automatically.
-   **Build Command**: `(cd frontend && REACT_APP_BACKEND_URL="$FRONTEND_BACKEND_URL" yarn build)` — uses CRACO (Create React App Configuration Override).
-   **Post-build Verification**: Logs bundle name, size (KB), and build timestamp. Aborts if no bundle is produced.
-   **Fail-fast**: `set -euo pipefail` + explicit bundle existence check ensure deploy never proceeds with a stale or broken build.
-   **Change Detection**: `check_files()` uses process substitution to detect changes by path: `backend/**` or `.platform/**` → backend deploy (GitHub Actions), `frontend/**` → frontend deploy (Cloudflare Pages). Matches the `paths` filter in `.github/workflows/deploy-backend.yml`.
-   **Post-push Summary**: Structured deploy summary showing changes detected (YES/NO), deploy expectations (EXPECTED/NOT EXPECTED with reasons), monitoring URLs, and a one-liner status.
-   **Contractor Image Guard**: Backend enforces `NO_TASK_IMAGE` policy — tasks must have at least one image before contractor assignment. Frontend flow: create → upload images → assign.
-   **Upload Image Validation**: Task attachment endpoint validates each file before storage: content_type must start with `image/`, file must be non-empty, and Pillow must decode+verify the image. Rejects with `INVALID_TASK_IMAGE` (400). Frontend skips retries for this error and shows Hebrew message.
-   **Mobile Upload Resilience**: `NewDefectModal` retries each image upload up to 3 times with exponential backoff (2s/4s). HEIC compression uses `createImageBitmap` with `new Image()` fallback. On total upload failure, modal stays open with retry button (reuses same task ID, no orphans). Partial upload success (≥1 image) proceeds to assign. Upload timeout is 120s.
    -   **Shared Image Compression**: `frontend/src/utils/imageCompress.js` — reusable utility (MAX_SIZE=800KB, MAX_WIDTH=1600, JPEG_QUALITY=0.7, HEIC support, createImageBitmap + Image fallback, 15s Promise.race timeout to prevent mobile browser hangs). Used by both `NewDefectModal` and `TaskDetailPage` (contractor proof flow).
    -   **Contractor Proof Hardening**: `TaskDetailPage.js` proof flow compresses images before upload, `api.js` `submitContractorProof` has 120s timeout. Error handling distinguishes timeout/400/500 with Hebrew messages.
    -   **Image Handler Safety**: All image selection handlers (`handleImageAdd`, `handleCameraCapture` in both `NewDefectModal` and `TaskDetailPage`) wrapped in try/catch/finally — prevents silent crashes, always clears file input/closes camera modal, shows Hebrew error toast on failure.

### Cloud Deployment (LIVE)
-   **Frontend**: Cloudflare Pages (`app.brikops.com`).
-   **Backend**: AWS Elastic Beanstalk (Docker, `api.brikops.com`).
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