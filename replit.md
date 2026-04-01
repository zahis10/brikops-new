# BrikOps - Construction Task Management System

## Overview
BrikOps is an MVP full-stack application designed to streamline construction task management. Its core purpose is to enhance workflows, improve communication, and provide comprehensive oversight in construction projects. Key capabilities include robust Role-Based Access Control (RBAC), a defined task lifecycle with strict status transitions, detailed audit logging, file attachment capabilities, and a real-time updates feed. The project aims to become a leading solution in the construction management software market.

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
-   **UI/UX**: Radix UI, TailwindCSS, and shadcn/ui provide a modern, responsive user experience with dynamic dashboards, hierarchical navigation, multi-step task management, and role-based dynamic routing. Key features include mobile-first design, client-side search, discipline filters, guided onboarding, and a comprehensive admin panel.
-   **Plans Management**: Features a card grid layout with filters, search, upload capabilities with metadata, detail modals with inline editing, version history, bulk upload, and auto-generated thumbnails.
-   **Accessibility**: Implements accessibility features per Israeli law.

### Backend
-   **Framework**: Python FastAPI, using Uvicorn.
-   **Database**: MongoDB.
-   **Router Architecture**: Modularized into sub-routers.
-   **Key Modules & Features**:
    -   **Authentication & Onboarding**: Supports multiple login methods including email/password, phone OTP, and WhatsApp Magic Link.
    -   **Multi-channel Communication**: Automated notifications via WhatsApp with SMS fallback.
    -   **Security**: JWT tokens, robust OTP flow, webhook signature enforcement, and CORS hardening.
    -   **File Storage**: Abstracted dual storage backend (local filesystem or AWS S3).
    -   **Task Workflow Enforcement**: Strict status transitions and role-based permissions.
    -   **Proof Management**: Multi-image proof uploads with client-side compression and validation, including photo annotation capabilities.
    -   **Billing System**: Simplified license + per-unit pricing (₪900 first project + ₪450 additional + ₪20/unit/month; founder_6m=₪500 flat; manual_override passthrough). PayPlus payment gateway for credit card payments (sandbox-first), Green Invoice for invoice generation, and recurring renewal infrastructure.
    -   **Admin & Member Management**: Tools for super_admin, PM, and owner-level team management.
    -   **QC (Quality Control) System**: Floor-level and unit-level quality control with template versioning, RBAC, stage-based workflow, and an approver system.
    -   **Handover Protocol System**: Unit-level handover protocol management for inspections, including engine-managed forms, status flows, digital signatures, and defect creation.
    -   **G4 Tenant Data Import**: Excel/CSV import of tenant data for handover protocols.
    -   **Admin CS Dashboard**: Read-only analytics dashboard for super_admin providing KPIs and activity data.
    -   **WhatsApp Auto-Reminders**: Automated and manual WhatsApp reminders with cooldowns, Shabbat protection, and per-user preferences.
    -   **Account & Org Deletion**: Self-service account deletion with a grace period and full purge options.
    -   **Identity System**: Manages user accounts, status, and audit logging.
    -   **Structure Permissions**: Role-based restrictions for building/floor/unit mutations.
    -   **Unit Type Tags & Notes**: Optional `unit_type_tag` and `unit_note` fields on units.
    -   **Spare Tiles Multi-Type**: Units support multiple tile types via an array field.
    -   **Login Redirect Cookie**: `brikops_logged_in` cookie used for landing page redirects.
    -   **Archive/Restore System**: Soft-delete functionality for hierarchy elements.
    -   **Defects V2**: Parallel building-level and apartment-level defect views with Excel and PDF exports.
    -   **Handover PDF Export**: Generates PDF of signed handover protocols.
    -   **Contractor i18n System**: Multi-language support for contractor-facing UI.
    -   **Analytics Infrastructure**: Login tracking and daily project snapshots collecting various activity data.
    -   **PM Team Activity Dashboard**: Provides per-member activity data, scores, and trends.
    -   **Admin Analytics**: Provides platform-wide user activity and feature usage statistics.
    -   **Observability**: Structured per-request logging, Hebrew error boundary, and health/readiness endpoints.
    -   **Performance Optimization**: Task list endpoint pagination, MongoDB indexes, S3 presigned URL TTL cache, and feature flags.

### Deployment and Security
-   **Workflow Configuration**: Single-process mode where backend serves pre-built static frontend.
-   **Deploy Pipeline**: Automated build and deployment with staleness detection and verification using GitHub Actions.
-   **Cloud Deployment**: Frontend on Cloudflare Pages, Backend on AWS Elastic Beanstalk (Docker), Database on MongoDB Atlas.
-   **Security**: Enhanced JWT with sliding auto-renewal, hardened OTP flow, strict webhook signature enforcement, configured CORS, SHA-256 hashed password reset tokens, project-scoped access control, session invalidation, sanitized regex search inputs, and upload rate limiting.

## External Dependencies

-   **MongoDB Atlas**: Primary database.
-   **Meta WhatsApp Cloud API v21.0**: For real-time task event notifications and OTP delivery.
-   **Twilio SMS API**: Fallback for OTP and task notifications.
-   **Uvicorn**: ASGI server for FastAPI.
-   **React**: Frontend core library.
-   **Radix UI, TailwindCSS, shadcn/ui**: Frontend component and styling libraries.
-   **openpyxl**: For Excel export and G4 tenant data import.
-   **WeasyPrint**: For handover protocol PDF generation.
-   **PyJWT**: For JWT token handling.
-   **Pillow + pdf2image**: For thumbnail generation.