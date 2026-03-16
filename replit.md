# BrikOps - Construction Task Management System

## Overview
BrikOps is an MVP full-stack application designed to streamline construction task management in construction projects. Its core purpose is to enhance workflows, improve communication, and provide comprehensive oversight. Key capabilities include robust Role-Based Access Control (RBAC), a defined task lifecycle with strict status transitions, detailed audit logging, file attachment capabilities, and a real-time updates feed. The project aims to become a leading solution in the construction management software market.

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
-   **Code Splitting**: Route-based lazy loading via `React.lazy()` + `Suspense`. Auth pages (Login, Register, ForgotPassword, ResetPassword, Accessibility, WaLogin, Onboarding, PendingApproval) are static imports; all other pages are lazy-loaded chunks. Main bundle: ~568KB raw / ~151KB gzipped. 40 lazy chunks. Build command: `cd frontend && REACT_APP_BACKEND_URL="" npx craco build`.
-   **UI/UX**: Leverages Radix UI, TailwindCSS, and shadcn/ui for a modern, responsive user experience. Features include dynamic dashboards, hierarchical navigation, a consistent color palette, multi-step task management with visual timelines and proof galleries, email/password and OTP-based authentication, and role-based dynamic routing. Key pages are designed with mobile-first principles, client-side search, discipline filters, and role-based actions.
-   **Onboarding Flow**: Guided onboarding creates an organization and project, followed by a checklist for initial setup.
-   **Admin Panel**: Provides comprehensive management for organizations, users, billing, and audit activity, including subscription overrides and organization owner changes.
-   **Plans Management**: Includes lightweight seen/unseen tracking for active plans, an archive and replace system with version history.
-   **Accessibility**: Implements accessibility features per Israeli law, including a public accessibility statement, skip-to-content links, ARIA attributes, and Hebrew noscript fallback.

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: Modularized into sub-routers.
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Supports email/password, phone OTP, PM approval, and WhatsApp Magic Link Login.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp with SMS fallback.
    -   **Security**: JWT tokens with HS256, robust OTP flow hardening, webhook signature enforcement, and CORS hardening.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3).
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions.
    -   **Proof Management**: Multi-image proof uploads with client-side compression and validation.
    -   **Billing System**: Centralized billing management with RBAC.
    -   **Admin & Member Management**: Tools for super_admin, PM, and owner-level team management.
    -   **QC (Quality Control) System**: Floor-level and unit-level quality control with template versioning, item management, RBAC, stage-based workflow, and an approver system. Supports scope models for templates and QC runs.
    -   **QC Template Management**: `qc_templates` collection with family-based versioning. Admin CRUD for templates, including assignment to projects. QC templates use `stages[]` format; handover templates use `sections[]` format with `visible_in_initial`/`visible_in_final` flags, trade, and input_type per item. Dedicated `AdminHandoverTemplateEditor` component at `/admin/templates/handover/:templateId/edit` for editing handover templates — 4-tab UI: sections/items, default delivered items, property field schema, and signature labels. All saved in one request. Backend create/update/clone endpoints handle both formats based on `type` field. Assignment to projects supported for both QC and handover templates (type-aware endpoints). **Full Template Defaults (Task #89)**: Templates can include `default_delivered_items` (list of items with name/quantity/notes), `default_property_fields` (list of {key, label} — key validated as lowercase alphanumeric+underscore, no duplicates), and `signature_labels` (exactly 3 keys: manager/tenant/contractor_rep). On protocol creation, these are snapshotted: `property_fields_schema` stores field schema, `property_details` stores values built from schema keys, `signature_labels` stored on protocol. HandoverPropertyForm checks `protocol.property_fields_schema` first (dynamic fields), falls back to hardcoded FIELDS for old protocols. SignatureSection shows editable labels above sign buttons, locked per-role after signing. `fix_empty_handover_template` in server.py adds missing defaults to existing templates without overwriting. **Auto-repin (Task #85)**: When admin saves a template, `admin_router.py` runs `update_many` on projects to repoint `handover_template_version_id` / `qc_template_version_id` from old version to new. `_resolve_handover_template` logs a warning and falls back to default if a project references a missing version.
    -   **Handover Protocol System**: Unit-level handover protocol management for initial and final inspections. Includes engine-managed forms, status flows (draft→in_progress→partially_signed→signed), and digital signatures for multiple roles. Overview endpoint (`GET /projects/{id}/handover/overview`) returns all units grouped by building→floor→unit with summary stats, building-level progress, defect counts, and filter support (?building, ?status, ?type). Initial and final protocols are independent (no sequential enforcement). Frontend: HandoverOverviewPage is a 3-zone command center (stats bar, filter bar, building grid) with color-coded unit cells, stat-card dimming, mobile bottom sheet filters. HandoverTabPage shows both create buttons (initial + final) independently — no #73 sequential gate. **Item Modal (Task #83)**: Redesigned HandoverItemModal with 4 status buttons (ok/partial/defective/not_relevant). Fail/partial status shows expanded section with photo upload (camera/gallery, client-side compression), description textarea, severity selector (critical/normal/cosmetic, no default, required). Backend auto-creates defects in tasks collection when items are marked fail/partial — idempotent (updates open defect, creates new if closed). Defect title format: `{section_name} > {item_name} — {status_label}`. Photos uploaded to defect via taskService.uploadAttachment after creation. Pass/not_relevant auto-save on status click with auto-advance. Defect indicator badge links to task detail. UnitDetailPage shows amber "מסירה" badge for handover-sourced tasks. **Legal Sections (Task #88a)**: Org-level `handover_legal_sections` array (CRUD via `PUT/GET /organizations/{org_id}/handover-legal-sections`). Each section has title, body, requires_signature, signature_role (constrained to manager/tenant/contractor_rep), applies_to (array of "initial"/"final"), order. On protocol creation, matching sections are snapshotted into `protocol.legal_sections` (filtered by `protocol_type in applies_to`). PM can edit body (`PUT .../legal-sections/{id}`) — sets edited=true, logs to legal_text_edit_log; blocked if signed. Legal section signing (`PUT .../legal-sections/{id}/sign`) supports canvas/typed, role-checked. `_is_protocol_fully_signed` checks BOTH all 3 protocol-level signatures AND all `requires_signature` legal sections are signed — only then does protocol become signed+locked. Old protocols without `legal_sections` field are backward compatible (empty array default). Atomic guards on sign/edit prevent concurrent race conditions.
    -   **Identity System**: Manages user accounts, status, and audit logging, including WhatsApp notification opt-out.
    -   **Structure Permissions**: Role-based restrictions for building/floor/unit mutations.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements.
    -   **Defects V2**: Parallel building-level and apartment-level defect views.
    -   **Defects Export**: Supports Excel and PDF exports with Hebrew RTL formatting.
    -   **Observability**: Structured per-request logging, Hebrew error boundary for frontend crashes, and health/readiness endpoints.

### Deployment and Security
-   **Workflow Configuration**: Single-process mode where backend serves pre-built static frontend.
-   **Deploy Pipeline**: Automated build and deployment process with staleness detection, post-build verification, and fail-fast mechanisms.
-   **Cloud Deployment**: Frontend on Cloudflare Pages, Backend on AWS Elastic Beanstalk (Docker), Database on MongoDB Atlas, PDF services S3-aware. CI/CD via GitHub Actions.
-   **Security**: Enhanced JWT implementation, hardened OTP flow with MongoDB-backed rate limits, strict webhook signature enforcement, configured CORS, SHA-256 hashed password reset tokens, project-scoped task updates access control, session invalidation on password reset, and sanitized regex search inputs.

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