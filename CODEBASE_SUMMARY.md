# BrikOps — Codebase Summary

## 1. Frontend — Directory Tree

```
frontend/src/
├── App.js                          # Root component, router config, protected routes
├── index.js                        # Entry point
├── setupProxy.js                   # Dev proxy config
├── components/
│   ├── handover/                   # Handover protocol sub-components
│   │   ├── G4ImportModal.js
│   │   ├── HandoverDeliveredItems.js
│   │   ├── HandoverGeneralNotes.js
│   │   ├── HandoverItemModal.js
│   │   ├── HandoverLegalSections.js
│   │   ├── HandoverLegalText.js
│   │   ├── HandoverMeterForm.js
│   │   ├── HandoverPropertyForm.js
│   │   ├── HandoverTenantForm.js
│   │   ├── SignaturePadModal.js
│   │   └── SignatureSection.js
│   ├── org/
│   │   └── OrgLegalSectionsEditor.js
│   ├── ui/                         # shadcn/ui primitives (40+ components)
│   │   ├── accordion.jsx
│   │   ├── button.jsx
│   │   ├── dialog.jsx
│   │   ├── input.jsx
│   │   ├── select.jsx
│   │   ├── table.jsx
│   │   ├── toast.jsx
│   │   └── ... (30+ more)
│   ├── CompleteAccountBanner.js
│   ├── CompleteAccountModal.js
│   ├── ErrorBoundary.js
│   ├── ExportModal.js
│   ├── FilterDrawer.js
│   ├── NewDefectModal.js
│   ├── NotificationBell.js
│   ├── PaywallModal.js
│   ├── PhoneChangeModal.js
│   ├── PhotoAnnotation.js
│   ├── ProjectBillingCard.js
│   ├── ProjectBillingEditModal.js
│   ├── ProjectSwitcher.js
│   ├── QCApproversTab.js
│   ├── TeamActivitySection.js
│   ├── TrialBanner.js
│   ├── UnitTypeEditModal.js
│   ├── UpgradeWizard.js
│   ├── UserDrawer.js
│   └── WhatsAppRejectionModal.js
├── contexts/
│   ├── AuthContext.js              # JWT, user session, login/logout
│   ├── BillingContext.js           # Subscription state, paywall
│   └── IdentityContext.js          # Account completion status
├── hooks/
│   └── use-toast.js                # Toast notification hook
├── i18n/
│   ├── index.js                    # t(), setLanguage(), tStatus(), etc.
│   ├── he.json
│   ├── en.json
│   ├── ar.json
│   └── zh.json
├── lib/
│   └── utils.js                    # cn() classname merge helper
├── pages/                          # 40+ page components (see §2)
├── services/
│   └── api.js                      # Axios instance, all API wrapper functions
└── utils/
    ├── actionLabels.js             # Task action display labels
    ├── billingHub.js               # Billing navigation helpers
    ├── billingLabels.js            # Billing status/plan labels
    ├── billingPlanCatalog.js       # Available plan definitions
    ├── formatters.js               # Date/number formatters
    ├── imageCompress.js            # Client-side image compression
    ├── navigation.js               # Route navigation helpers
    ├── phoneUtils.js               # Phone number formatting
    ├── qcLabels.js                 # QC status display labels
    ├── qcVisualStatus.js           # QC visual status indicators
    └── roleLabels.js               # Role display labels
```

## 2. Frontend — Pages & Routes

### Public Routes
| Path | Component | File |
|------|-----------|------|
| `/login` | LoginPage | LoginPage.js |
| `/auth/wa` | WaLoginPage | WaLoginPage.js |
| `/register` | RegisterPage | RegisterPage.js |
| `/register-management` | RegisterManagementPage | RegisterManagementPage.js |
| `/forgot-password` | ForgotPasswordPage | ForgotPasswordPage.js |
| `/reset-password` | ResetPasswordPage | ResetPasswordPage.js |
| `/accessibility` | AccessibilityPage | AccessibilityPage.js |
| `/onboarding` | OnboardingPage | OnboardingPage.js |
| `/pending` | PendingApprovalPage | PendingApprovalPage.js |
| `/account/pending-deletion` | PendingDeletionPage | PendingDeletionPage.js |
| `/org/transfer/:token` | OwnershipTransferPage | OwnershipTransferPage.js |

### Protected Routes (logged in)
| Path | Component | File |
|------|-----------|------|
| `/` | Redirects to `/projects` | — |
| `/settings/account` | AccountSettingsPage | AccountSettingsPage.js |
| `/projects` | MyProjectsPage / ContractorDashboard | MyProjectsPage.js / ContractorDashboard.js |
| `/billing/org/:orgId` | OrgBillingPage | OrgBillingPage.js |
| `/projects/:projectId/control` | ProjectControlPage | ProjectControlPage.js |
| `/projects/:projectId/dashboard` | ProjectDashboardPage | ProjectDashboardPage.js |
| `/projects/:projectId/floors/:floorId` | FloorDetailPage | FloorDetailPage.js |
| `/projects/:projectId/buildings/:buildingId` | InnerBuildingPage | InnerBuildingPage.js |
| `/projects/:projectId/buildings/:buildingId/qc` | BuildingQCPage | BuildingQCPage.js |
| `/projects/:projectId/buildings/:buildingId/defects` | BuildingDefectsPage | BuildingDefectsPage.js |
| `/projects/:projectId/buildings/:buildingId/floors/:floorId/qc/units` | UnitQCSelectionPage | UnitQCSelectionPage.js |
| `/projects/:projectId/qc` | QCFloorSelectionPage | QCFloorSelectionPage.js |
| `/projects/:projectId/qc/floors/:floorId/run/:runId/stage/:stageId` | StageDetailPage | StageDetailPage.js |
| `/projects/:projectId/plans` | ProjectPlansPage | ProjectPlansPage.js |
| `/projects/:projectId/plans/archive` | ProjectPlansArchivePage | ProjectPlansArchivePage.js |
| `/projects/:projectId/plans/:planId/history` | ProjectPlanHistoryPage | ProjectPlanHistoryPage.js |
| `/projects/:projectId/tasks` | ProjectTasksPage | ProjectTasksPage.js |
| `/projects/:projectId/units/:unitId` | UnitHomePage | UnitHomePage.js |
| `/projects/:projectId/units/:unitId/tasks` | UnitDetailPage | UnitDetailPage.js |
| `/projects/:projectId/units/:unitId/plans` | UnitPlansPage | UnitPlansPage.js |
| `/projects/:projectId/units/:unitId/defects` | ApartmentDashboardPage | ApartmentDashboardPage.js |
| `/projects/:projectId/handover` | HandoverOverviewPage | HandoverOverviewPage.js |
| `/projects/:projectId/units/:unitId/handover` | HandoverTabPage | HandoverTabPage.js |
| `/projects/:projectId/units/:unitId/handover/:protocolId` | HandoverProtocolPage | HandoverProtocolPage.js |
| `/projects/:projectId/units/:unitId/handover/:protocolId/sections/:sectionId` | HandoverSectionPage | HandoverSectionPage.js |
| `/tasks/:id` | TaskDetailPage | TaskDetailPage.js |
| `/org/transfer/settings` | OwnershipTransferPage | OwnershipTransferPage.js |

### PM-Only Routes
| Path | Component |
|------|-----------|
| `/join-requests` | JoinRequestsPage |

### Super Admin Routes
| Path | Component |
|------|-----------|
| `/admin` | AdminPage |
| `/admin/dashboard` | AdminDashboardPage |
| `/admin/activity` | AdminActivityPage |
| `/admin/billing` | AdminBillingPage |
| `/admin/orgs` | AdminOrgsPage |
| `/admin/users` | AdminUsersPage |
| `/admin/qc-templates` | AdminQCTemplatesPage |
| `/admin/templates/handover/:templateId/edit` | AdminHandoverTemplateEditor |

### Fallback
`*` → redirect to `/projects`

## 3. Frontend — Shared Components

| Component | Purpose |
|-----------|---------|
| CompleteAccountBanner | Prompts user to finish account setup |
| CompleteAccountModal | Modal form for completing account details |
| ErrorBoundary | Global error catch with Hebrew message |
| ExportModal | PDF/Excel export dialog |
| FilterDrawer | Side drawer for task/defect filters |
| NewDefectModal | Create new defect form |
| NotificationBell | Header notification icon + dropdown |
| PaywallModal | Upgrade prompt for restricted features |
| PhoneChangeModal | Phone number change flow with OTP |
| PhotoAnnotation | Camera capture + drawing annotations (always top-level, outside Radix) |
| ProjectBillingCard | Billing status summary card |
| ProjectBillingEditModal | Edit project billing settings |
| ProjectSwitcher | Project selection dropdown in header |
| QCApproversTab | QC approver management tab |
| TeamActivitySection | PM team activity metrics display |
| TrialBanner | Trial period countdown banner |
| UnitTypeEditModal | Edit unit type tag |
| UpgradeWizard | Multi-step plan upgrade flow |
| UserDrawer | User profile side drawer |
| WhatsAppRejectionModal | WhatsApp rejection notification dialog |
| ui/* | 40+ shadcn/ui primitives (button, dialog, input, select, table, tabs, etc.) |

## 4. Frontend — API Layer

- **Axios instance**: `frontend/src/services/api.js` — creates `axios.create()` with `baseURL` from `REACT_APP_BACKEND_URL` (empty = relative paths).
- **API wrapper functions**: All in `api.js` — exported functions per endpoint (e.g., `fetchTasks()`, `createTask()`, `fetchProtocol()`).
- **Custom hooks**: `hooks/use-toast.js` (toast notifications). No dedicated API hooks — pages call `api.*` directly in `useEffect`/`useCallback`.
- **Base URL pattern**: `REACT_APP_BACKEND_URL` env var; empty string in production (frontend and backend on same origin via proxy), or explicit URL during development.

## 5. Frontend — i18n Structure

- **4 locale files**: `he.json`, `en.json`, `ar.json`, `zh.json`
- **19 sections** in Hebrew (primary): account (106 keys), handover (111), onboarding (106), taskDetail (48), dashboard (26), register (22), toasts (19), categories (17), trades (17), teamTab (16), unitPlans (16), statuses (12), myProjects (11), unitHome (11), roles (7), subRoles (5), priorities (4), settings (3), routing (2)
- **Total**: ~559 keys in Hebrew locale

Example section `"dashboard"`:
```json
{
  "contractor_fallback": "קבלן",
  "settings_aria": "הגדרות חשבון",
  "logout_aria": "יציאה",
  "total_handled": "סה\"כ טופלו"
}
```

- **`t(section, key)`** defined in `frontend/src/i18n/index.js` — looks up `currentLocale → section → key`, falls back to `he`, then to raw key.
- **Helper functions**: `tStatus()`, `tPriority()`, `tRole()`, `tTrade()`, `tCategory()`, `tSubRole()`.
- **`setLanguage(lang)`** called in `AuthContext.js` before `setUser()` — PM always forced to Hebrew.

## 6. Frontend — State Management

**Pattern**: React Context API + local `useState`/`useCallback`. No Redux/Zustand in use.

| Context | Purpose |
|---------|---------|
| **AuthContext** | JWT token, user object, login/logout/register, session refresh, feature flags, network error state. Persists token in `localStorage` + `brikops_logged_in` cookie. |
| **BillingContext** | Org/project billing state, `isReadOnly` flag, paywall modal control, `refreshBilling()`. |
| **IdentityContext** | Account completion status (`identityStatus`), `showCompleteForm` toggle. |

## 7. Backend — Directory Tree

```
backend/
├── server.py                       # FastAPI app factory, middleware, router mounting
├── config.py                       # Central env var config
├── models.py                       # Pydantic models (inspection-era, legacy)
├── models_extended.py              # Extended models (regulations, documents)
├── seed_data.py                    # Seed data constants
├── contractor_ops/                 # Main business logic
│   ├── __init__.py
│   ├── router.py                   # Main system router
│   ├── schemas.py                  # Core Pydantic schemas (Project, Task, User, etc.)
│   ├── constants.py                # TERMINAL_TASK_STATUSES, etc.
│   ├── auth_router.py              # Auth endpoints
│   ├── admin_router.py             # Super admin endpoints
│   ├── admin_analytics.py          # Admin analytics queries
│   ├── admin_dashboard.py          # Admin dashboard data
│   ├── tasks_router.py             # Defect/task CRUD
│   ├── handover_router.py          # Handover protocol engine
│   ├── qc_router.py                # Quality control system
│   ├── import_router.py            # G4 tenant data import
│   ├── plans_router.py             # Plans management
│   ├── projects_router.py          # Project hierarchy/structure
│   ├── companies_router.py         # Companies & trades
│   ├── billing_router.py           # Billing & payments
│   ├── billing.py                  # Billing business logic
│   ├── billing_plans.py            # Plan catalog
│   ├── stats_router.py             # Analytics & dashboards
│   ├── export_router.py            # PDF/Excel exports
│   ├── excel_router.py             # Structure Excel import/export
│   ├── notification_router.py      # Notifications & WA webhooks
│   ├── notification_service.py     # WA/SMS sending logic
│   ├── reminder_router.py          # Auto-reminders
│   ├── reminder_service.py         # Reminder scheduling logic
│   ├── identity_router.py          # Identity & account security
│   ├── identity_service.py         # Identity business logic
│   ├── invites_router.py           # Team invitations
│   ├── onboarding_router.py        # OTP, registration, join requests
│   ├── config_router.py            # Feature flags
│   ├── debug_router.py             # Health, diagnostics, proofs
│   ├── deletion_router.py          # Account deletion (GDPR/Apple)
│   ├── archive_router.py           # Soft-delete & restore
│   ├── ownership_transfer.py       # Org ownership transfer
│   ├── wa_login.py                 # WhatsApp magic link login
│   ├── otp_service.py              # OTP generation & verification
│   ├── sms_service.py              # SMS sending (Twilio)
│   ├── stepup_service.py           # Step-up auth for admin
│   ├── phone_utils.py              # Phone normalization (mobile + landline)
│   ├── bucket_utils.py             # S3 bucket helpers
│   ├── member_management.py        # Team member operations
│   ├── msg_logger.py               # Message delivery logging
│   ├── snapshot_cron.py            # Daily analytics snapshot cron
│   ├── task_image_guard.py         # Task image access guard
│   ├── upload_rate_limit.py        # Upload rate limiting
│   ├── invoicing.py                # Invoice generation logic
│   ├── green_invoice_service.py    # Green Invoice API integration
│   ├── demo_seed.py                # Demo data seeding
│   ├── seed.py                     # Production seed
│   ├── utils/
│   │   ├── __init__.py
│   │   └── timezone.py             # Shared IL timezone helper
│   └── test_*.py                   # Unit/integration tests (12 files)
├── services/
│   ├── ai_service.py               # LLM integration
│   ├── audit_service.py            # Audit event recording
│   ├── document_vault_service.py   # Document storage
│   ├── enhanced_pdf_service.py     # Enhanced PDF generation
│   ├── enhanced_pdf_service_v2.py  # PDF generation v2
│   ├── handover_pdf_service.py     # Handover protocol PDF
│   ├── object_storage.py           # S3/local file abstraction
│   ├── pdf_service.py              # Base PDF service
│   ├── pdf_template_service.py     # PDF template engine
│   ├── regulation_service.py       # Building regulation lookup
│   ├── storage_service.py          # Storage abstraction layer
│   └── thumbnail_service.py        # Image/PDF thumbnail generation
├── scripts/                        # One-off migration/utility scripts
│   ├── backfill_defect_photos.py
│   ├── backfill_password_hash.py
│   ├── backup_restore.py
│   ├── normalize_phones.py
│   ├── migrate_legal_to_templates.py
│   ├── migrate_spare_tiles.py
│   └── ... (6 more)
├── tests/                          # Additional test files (18 files)
└── utils/
    └── image_processor.py          # Server-side image processing
```

## 8. Backend — All Endpoints

### auth_router.py — Authentication & Profile
| Method | Path | Function |
|--------|------|----------|
| POST | `/auth/register` | register |
| POST | `/auth/login` | login |
| POST | `/auth/dev-login` | dev_login |
| GET | `/auth/me` | get_me |
| POST | `/auth/logout-all` | logout_all_sessions |
| POST | `/auth/change-phone/request` | request_phone_change |
| POST | `/auth/change-phone/verify` | verify_phone_change |
| PUT | `/auth/me/preferred-language` | update_my_preferred_language |
| PUT | `/auth/me/whatsapp-notifications` | update_my_whatsapp_notifications |

### onboarding_router.py — OTP & Registration
| Method | Path | Function |
|--------|------|----------|
| POST | `/auth/request-otp` | request_otp |
| POST | `/auth/verify-otp` | verify_otp |
| POST | `/auth/register-with-phone` | register_with_phone |
| POST | `/auth/login-phone` | login_with_phone |
| POST | `/auth/set-password` | set_password |
| POST | `/auth/register-management` | register_management |
| POST | `/auth/forgot-password` | forgot_password |
| POST | `/auth/reset-password` | reset_password |
| GET | `/auth/management-roles` | get_management_roles |
| GET | `/auth/subcontractor-roles` | get_subcontractor_roles |
| GET | `/projects/{project_id}/join-requests` | list_join_requests |
| POST | `/join-requests/{request_id}/approve` | approve_join_request |
| POST | `/join-requests/{request_id}/reject` | reject_join_request |
| GET | `/onboarding/status` | onboarding_status |
| POST | `/onboarding/create-org` | onboarding_create_org |
| POST | `/onboarding/accept-invite` | onboarding_accept_invite |
| GET | `/invites/{invite_id}/info` | get_invite_info |
| POST | `/onboarding/join-by-code` | onboarding_join_by_code |

### tasks_router.py — Defect/Task Management
| Method | Path | Function |
|--------|------|----------|
| POST | `/tasks` | create_task |
| GET | `/tasks` | list_tasks |
| GET | `/tasks/my-stats` | my_task_stats |
| GET | `/tasks/{task_id}` | get_task |
| PATCH | `/tasks/{task_id}` | update_task |
| PATCH | `/tasks/{task_id}/assign` | assign_task |
| POST | `/tasks/{task_id}/status` | change_task_status |
| POST | `/tasks/{task_id}/reopen` | reopen_task |
| POST | `/tasks/{task_id}/contractor-proof` | contractor_proof |
| DELETE | `/tasks/{task_id}/proof/{proof_id}` | delete_proof |
| POST | `/tasks/{task_id}/force-close` | force_close_task |
| POST | `/tasks/{task_id}/manager-decision` | manager_decision |
| POST | `/tasks/{task_id}/updates` | add_task_update |
| GET | `/tasks/{task_id}/updates` | list_task_updates |
| POST | `/tasks/{task_id}/attachments` | upload_task_attachment |
| GET | `/updates/feed` | updates_feed |

### handover_router.py — Handover Protocols
| Method | Path | Function |
|--------|------|----------|
| PUT | `/projects/{pid}/handover-template` | assign_handover_template |
| GET | `/projects/{pid}/handover-template` | get_handover_template |
| PUT | `/organizations/{oid}/handover-legal-sections` | put_org_legal_sections |
| GET | `/organizations/{oid}/handover-legal-sections` | get_org_legal_sections |
| PUT | `/organizations/{oid}/logo` | upload_org_logo |
| DELETE | `/organizations/{oid}/logo` | delete_org_logo |
| POST | `/projects/{pid}/handover/protocols` | create_protocol |
| GET | `/projects/{pid}/handover/protocols` | list_protocols |
| GET | `/projects/{pid}/handover/protocols/{id}` | get_protocol |
| PUT | `/projects/{pid}/handover/protocols/{id}` | update_protocol |
| PATCH | `.../sections/{sid}/batch-items` | batch_update_items |
| PUT | `.../items/{iid}` | update_item |
| POST | `.../items/{iid}/create-defect` | create_defect_from_item |
| PUT | `.../signatures/{role}` | sign_role |
| DELETE | `.../signatures/{role}` | delete_signature |
| GET | `.../signatures/{role}/image` | get_signature_image |
| GET | `.../pdf` | download_protocol_pdf |
| POST | `.../reopen` | reopen_protocol |
| GET | `/projects/{pid}/handover/overview` | handover_overview |
| GET | `/projects/{pid}/handover/summary` | handover_summary |
| PUT | `.../legal-sections/{sid}` | update_legal_section_body |
| PUT | `.../legal-sections/{sid}/sign` | sign_legal_section |
| GET | `.../legal-sections/{sid}/signature-image` | get_legal_section_signature_image |

### qc_router.py — Quality Control
| Method | Path | Function |
|--------|------|----------|
| GET | `/templates` | list_templates |
| GET | `/floors/{fid}/run` | get_or_create_floor_run |
| GET | `/units/{uid}/run` | get_or_create_unit_run |
| GET | `/floors/{fid}/units-status` | get_floor_units_status |
| GET | `/run/{rid}` | get_run_detail |
| GET | `/run/{rid}/team-contacts` | get_team_contacts |
| PATCH | `/run/{rid}/item/{iid}` | update_qc_item |
| POST | `/run/{rid}/item/{iid}/reject` | reject_qc_item |
| POST | `/run/{rid}/item/{iid}/photo` | upload_qc_photo |
| POST | `/run/{rid}/stage/{sid}/submit` | submit_stage |
| GET | `/floors/batch-status` | get_floors_qc_status |
| GET | `/meta/stages` | get_qc_stage_meta |
| GET | `/projects/{pid}/approvers` | list_approvers |
| POST | `/projects/{pid}/approvers` | add_approver |
| DELETE | `/projects/{pid}/approvers/{uid}` | revoke_approver |
| GET | `/projects/{pid}/execution-summary` | get_execution_summary |
| POST | `/run/{rid}/stage/{sid}/approve` | approve_stage |
| POST | `/run/{rid}/stage/{sid}/reject` | reject_stage |
| POST | `/run/{rid}/stage/{sid}/notify-rejection` | notify_rejection_whatsapp |
| GET | `/run/{rid}/my-approver-status` | get_my_approver_status |
| POST | `/run/{rid}/stage/{sid}/reopen` | reopen_stage |
| GET | `/run/{rid}/stage/{sid}/timeline` | get_stage_timeline |

### projects_router.py — Hierarchy & Structure
| Method | Path | Function |
|--------|------|----------|
| POST | `/projects` | create_project |
| GET | `/projects` | list_projects |
| GET | `/projects/{pid}` | get_project |
| PUT | `/projects/{pid}/onboarding-complete` | mark_onboarding_complete |
| POST | `/projects/{pid}/assign-pm` | assign_pm |
| GET | `/projects/{pid}/available-pms` | list_available_pms |
| POST | `/projects/{pid}/buildings` | create_building |
| GET | `/projects/{pid}/buildings` | list_buildings |
| POST | `/buildings/{bid}/floors` | create_floor |
| GET | `/buildings/{bid}/floors` | list_floors |
| POST | `/floors/{fid}/units` | create_unit |
| GET | `/floors/{fid}/units` | list_units_by_floor |
| PATCH | `/units/{uid}` | patch_unit |
| PATCH | `/units/{uid}/spare-tiles` | patch_unit_spare_tiles |
| POST | `/floors/bulk` | bulk_create_floors |
| POST | `/units/bulk` | bulk_create_units |
| GET | `/projects/{pid}/hierarchy` | get_project_hierarchy |
| GET | `/units/{uid}/tasks` | list_unit_tasks |
| GET | `/units/{uid}` | get_unit_detail |
| POST | `/buildings/{bid}/resequence` | resequence_building |
| POST | `/projects/{pid}/insert-floor` | insert_floor |
| GET | `/buildings/{bid}/defects-summary` | building_defects_summary |
| PUT | `/projects/{pid}/qc-template` | assign_project_qc_template |
| GET | `/projects/{pid}/qc-template` | get_project_qc_template |

### plans_router.py — Plans Management
| Method | Path | Function |
|--------|------|----------|
| GET | `/projects/{pid}/plans` | list_project_plans |
| GET | `/projects/{pid}/plans/archive` | list_project_plans_archive |
| POST | `/projects/{pid}/plans` | upload_project_plan |
| POST | `/projects/{pid}/plans/{id}/seen` | mark_plan_seen |
| GET | `/projects/{pid}/plans/{id}/seen` | get_plan_seen_status |
| POST | `/projects/{pid}/plans/{id}/versions` | upload_plan_version |
| GET | `/projects/{pid}/plans/{id}/versions` | get_plan_versions |
| GET | `/projects/{pid}/plans/{id}/history` | get_project_plan_history |
| POST | `/projects/{pid}/plans/{id}/replace` | replace_project_plan |
| PATCH | `/projects/{pid}/plans/{id}/archive` | archive_project_plan |
| PATCH | `/projects/{pid}/plans/{id}` | update_project_plan |
| PATCH | `/projects/{pid}/plans/{id}/restore` | restore_project_plan |
| DELETE | `/projects/{pid}/plans/{id}` | delete_project_plan |
| GET | `/projects/{pid}/units/{uid}/plans` | list_unit_plans |
| POST | `/projects/{pid}/units/{uid}/plans` | upload_unit_plan |
| GET | `/projects/{pid}/disciplines` | list_project_disciplines |
| POST | `/projects/{pid}/disciplines` | add_project_discipline |

### import_router.py — G4 Tenant Import
| Method | Path | Function |
|--------|------|----------|
| GET | `/template` | download_template |
| POST | `/preview` | preview_import |
| POST | `/execute` | execute_import |

### billing_router.py — Billing & Payments
| Method | Path | Function |
|--------|------|----------|
| GET | `/billing/me` | billing_me |
| GET | `/billing/plans/active` | billing_plans_active |
| GET | `/billing/org/{oid}` | billing_org |
| POST | `/billing/org/{oid}/checkout` | billing_checkout |
| GET | `/billing/preview-renewal` | billing_preview_renewal |
| POST | `/billing/org/{oid}/payment-request` | billing_payment_request |
| GET | `/billing/org/{oid}/payment-requests` | billing_list_payment_requests |
| GET | `/billing/org/{oid}/payment-config` | billing_get_payment_config |
| PUT | `/billing/org/{oid}/payment-config` | billing_update_payment_config |
| POST | `.../payment-requests/{rid}/mark-paid-by-customer` | billing_customer_mark_paid |
| POST | `.../payment-requests/{rid}/receipt` | billing_upload_receipt_form |
| GET | `.../payment-requests/{rid}/receipt` | billing_get_receipt |
| POST | `.../payment-requests/{rid}/cancel` | billing_cancel_request |
| POST | `.../payment-requests/{rid}/reject` | billing_reject_request |
| POST | `/billing/org/{oid}/mark-paid` | billing_mark_paid |
| GET | `/billing/project/{pid}` | billing_project |
| PATCH | `/billing/project/{pid}` | billing_project_update |
| POST | `/billing/project/{pid}/handoff-request` | billing_handoff_request |
| POST | `/billing/project/{pid}/handoff-ack` | billing_handoff_ack |
| POST | `/billing/project/{pid}/setup-complete` | billing_setup_complete |
| GET | `/billing/org/{oid}/invoice/preview` | invoice_preview |
| POST | `/billing/org/{oid}/invoice/generate` | invoice_generate |
| GET | `/billing/org/{oid}/invoices` | invoice_list |
| GET | `/billing/org/{oid}/invoices/{iid}` | invoice_detail |
| POST | `/billing/org/{oid}/invoices/{iid}/mark-paid` | invoice_mark_paid |
| GET | `/orgs/{oid}/billing-contact` | get_billing_contact_endpoint |
| PUT | `/orgs/{oid}/billing-contact` | update_billing_contact_endpoint |
| POST | `/billing/run-renewals` | billing_run_renewals |
| POST | `/billing/webhook/greeninvoice` | billing_webhook_greeninvoice |
| GET | `/billing/failed-renewals` | billing_failed_renewals |
| POST | `/billing/resolve-failed-renewal` | billing_resolve_failed_renewal |

### companies_router.py — Companies & Trades
| Method | Path | Function |
|--------|------|----------|
| POST | `/companies` | create_company |
| GET | `/companies` | list_companies |
| POST | `/projects/{pid}/companies` | create_project_company |
| GET | `/projects/{pid}/companies` | list_project_companies |
| PUT | `/projects/{pid}/companies/{cid}` | update_project_company |
| DELETE | `/projects/{pid}/companies/{cid}` | delete_project_company |
| GET | `/projects/{pid}/trades` | list_project_trades |
| POST | `/projects/{pid}/trades` | create_project_trade |
| GET | `/companies/search` | search_companies |
| GET | `/trades` | list_trades |

### stats_router.py — Analytics & Dashboards
| Method | Path | Function |
|--------|------|----------|
| GET | `/projects/{pid}/memberships` | list_project_memberships |
| GET | `/my-memberships` | get_my_memberships |
| GET | `/projects/{pid}/stats` | get_project_stats |
| GET | `/projects/{pid}/dashboard` | get_project_dashboard |
| GET | `/projects/{pid}/tasks/contractor-summary` | get_contractor_summary |
| GET | `/projects/{pid}/task-buckets` | get_task_buckets |
| GET | `/projects/{pid}/team-activity` | get_team_activity |
| GET | `/projects/{pid}/activity-trend` | get_activity_trend |

### invites_router.py — Team Invitations
| Method | Path | Function |
|--------|------|----------|
| PUT | `/projects/{pid}/members/{uid}/contractor-profile` | update_contractor_profile |
| GET | `/users` | list_users |
| POST | `/projects/{pid}/invites` | create_team_invite |
| GET | `/projects/{pid}/invites` | list_team_invites |
| POST | `/projects/{pid}/invites/{iid}/resend` | resend_team_invite |
| POST | `/projects/{pid}/invites/{iid}/resend-sms` | resend_invite_sms |
| POST | `/projects/{pid}/invites/{iid}/cancel` | cancel_team_invite |

### notification_router.py — Notifications & Webhooks
| Method | Path | Function |
|--------|------|----------|
| POST | `/tasks/{tid}/notify` | manual_notify |
| GET | `/tasks/{tid}/notifications` | task_notifications |
| POST | `/notifications/{jid}/retry` | retry_notification |
| GET | `/webhooks/whatsapp` | whatsapp_webhook_verify |
| POST | `/webhooks/whatsapp` | whatsapp_webhook_receive |

### reminder_router.py — Auto-Reminders
| Method | Path | Function |
|--------|------|----------|
| POST | `/projects/{pid}/reminders/contractor/{cid}` | manual_contractor_reminder |
| POST | `/projects/{pid}/reminders/digest` | manual_pm_digest |
| GET | `/users/me/reminder-preferences` | get_reminder_preferences |
| PUT | `/users/me/reminder-preferences` | update_reminder_preferences |

### identity_router.py — Identity & Security
| Method | Path | Function |
|--------|------|----------|
| GET | `/account-status` | account_status |
| POST | `/complete-account` | complete_account_endpoint |
| POST | `/identity-event` | log_identity_event |
| POST | `/change-password` | change_password |
| POST | `/change-email` | change_email |

### export_router.py — Defect Export
| Method | Path | Function |
|--------|------|----------|
| POST | `/defects/export` | export_defects |

### excel_router.py — Structure Import/Export
| Method | Path | Function |
|--------|------|----------|
| GET | `/projects/{pid}/excel-template` | download_excel_template |
| POST | `/projects/{pid}/excel-import` | import_excel |
| POST | `/projects/{pid}/migrate-sort-index` | migrate_sort_index |

### admin_router.py — Super Admin
| Method | Path | Function |
|--------|------|----------|
| POST | `/admin/stepup/request` | stepup_request |
| POST | `/admin/stepup/verify` | stepup_verify |
| POST | `/admin/revoke-session/{uid}` | admin_revoke_session |
| POST | `/admin/billing/override` | admin_override |
| POST | `/admin/billing/apply-pending-decreases` | admin_apply_pending_decreases |
| GET | `/admin/billing/payment-requests-summary` | admin_payment_requests_summary |
| GET | `/admin/billing/orgs` | admin_list_orgs |
| GET | `/admin/billing/invoices-summary` | admin_invoices_summary |
| GET | `/admin/orgs/{oid}/projects` | admin_org_projects |
| PUT | `/admin/orgs/{oid}` | admin_update_org |
| PUT | `/admin/orgs/{oid}/owner` | admin_change_org_owner |
| GET | `/admin/billing/audit` | admin_billing_audit |
| GET | `/admin/billing/plans` | admin_list_plans |
| POST | `/admin/billing/plans` | admin_create_plan |
| PUT | `/admin/billing/plans/{id}` | admin_update_plan |
| PATCH | `/admin/billing/plans/{id}/deactivate` | admin_deactivate_plan |
| GET | `/admin/billing/migration/dry-run` | admin_migration_dry_run |
| POST | `/admin/billing/migration/apply` | admin_migration_apply |
| GET | `/admin/users` | admin_list_users |
| GET | `/admin/users/{uid}` | admin_get_user |
| PUT | `/admin/users/{uid}/phone` | admin_change_user_phone |
| PUT | `/admin/users/{uid}/preferred-language` | admin_update_preferred_language |
| POST | `/admin/users/{uid}/reset-password` | admin_reset_user_password |
| PUT | `/admin/users/{uid}/projects/{pid}/role` | admin_change_user_role |
| GET | `/admin/qc/templates` | admin_list_qc_templates |
| PUT | `/admin/qc/templates/{fid}/archive` | admin_archive_qc_template_family |
| GET | `/admin/qc/templates/{tid}` | admin_get_qc_template |
| POST | `/admin/qc/templates` | admin_create_qc_template |
| PUT | `/admin/qc/templates/{tid}` | admin_update_qc_template |
| POST | `/admin/qc/templates/{tid}/clone` | admin_clone_qc_template |

### deletion_router.py — Account Deletion
| Method | Path | Function |
|--------|------|----------|
| POST | `/users/me/request-deletion-otp` | request_deletion_otp |
| POST | `/users/me/request-deletion` | request_account_deletion |
| POST | `/users/me/request-full-deletion` | request_full_deletion |
| POST | `/users/me/cancel-deletion` | cancel_deletion |
| GET | `/users/me/deletion-status` | get_deletion_status |
| POST | `/admin/execute-deletion/{uid}` | execute_deletion |
| POST | `/admin/resume-deletion-job/{jid}` | resume_deletion_job |
| GET | `/admin/deletion-jobs` | list_deletion_jobs |
| GET | `/admin/pending-deletions` | list_pending_deletions |
| POST | `/admin/process-overdue-deletions` | process_overdue_deletions |

### archive_router.py — Soft-Delete & Restore
| Method | Path | Function |
|--------|------|----------|
| POST | `/buildings/{bid}/archive` | archive_building |
| POST | `/floors/{fid}/archive` | archive_floor |
| POST | `/units/{uid}/archive` | archive_unit |
| POST | `/buildings/{bid}/restore` | restore_building |
| POST | `/floors/{fid}/restore` | restore_floor |
| POST | `/units/{uid}/restore` | restore_unit |
| POST | `/batches/{bid}/undo` | undo_batch |
| GET | `/projects/{pid}/archived` | get_archived_entities |
| DELETE | `/admin/entities/{type}/{eid}/permanent` | hard_delete_entity |

### debug_router.py — Health & Diagnostics
| Method | Path | Function |
|--------|------|----------|
| GET | `/health` | health_check |
| GET | `/ready` | readiness_check |
| GET | `/admin/system-info` | admin_system_info |
| GET | `/admin/diagnostics/role-conflicts` | admin_diagnostics_role_conflicts |
| GET | `/debug/version` | debug_version |
| GET | `/debug/otp-status` | debug_otp_status |
| GET | `/debug/whatsapp` | debug_whatsapp |
| GET | `/debug/whatsapp-template-inspect` | debug_whatsapp_template_inspect |
| POST | `/debug/whatsapp-send-test` | debug_whatsapp_send_test |
| POST | `/debug/whatsapp-test` | debug_whatsapp_test_legacy |
| GET | `/debug/whatsapp-latest` | debug_whatsapp_latest |
| GET | `/debug/notification-lookup` | debug_notification_lookup |
| GET | `/debug/whoami` | debug_whoami |
| GET | `/debug/*-proof` | Various integration proof endpoints |

### wa_login.py — WhatsApp Magic Links
| Method | Path | Function |
|--------|------|----------|
| POST | `/request-login` | request_login |
| POST | `/create-link` | create_magic_link |
| GET | `/verify` | verify_magic_link |
| POST | `/send-login-link` | send_login_link_debug |

### ownership_transfer.py — Org Ownership Transfer
| Method | Path | Function |
|--------|------|----------|
| POST | `/initiate` | initiate_transfer |
| POST | `/cancel` | cancel_transfer |
| GET | `/pending` | get_pending_transfer |
| GET | `/verify/{token}` | verify_transfer_token |
| POST | `/request-otp` | request_transfer_otp |
| POST | `/accept` | accept_transfer |

### config_router.py — Feature Flags
| Method | Path | Function |
|--------|------|----------|
| GET | `/config/features` | get_feature_flags |

### router.py — System
| Method | Path | Function |
|--------|------|----------|
| GET | `/notifications` | list_notifications |
| GET | `/notifications/stats` | notification_stats |

## 9. Backend — Models & Schemas

### Core Schemas (`contractor_ops/schemas.py`)
| Model | Key Fields |
|-------|------------|
| Project | id, name, code, status, org_id |
| Building | id, project_id, name, code, floors_count |
| Floor | id, building_id, name, floor_number, kind |
| Unit | id, floor_id, unit_no, unit_type, status, spare_tiles |
| Task | id, project_id, title, status, priority, company_id |
| TaskCreate | project_id, building_id, floor_id, unit_id, title, category |
| TaskUpdate | title, description, priority, due_date, company_id |
| UserCreate | email, name, phone, role, company_id |
| UserResponse | id, email, name, role, organization |
| TokenResponse | token, user |
| OTPRequest | phone_e164 |
| OTPVerify | phone_e164, code |
| InviteCreate | phone, role, full_name, trade_key, company_id |
| BulkFloorRequest | project_id, building_id, from_floor, to_floor |
| BulkUnitRequest | project_id, building_id, units_per_floor, unit_prefix |
| HierarchyResponse | project_id, project_name, buildings[] |

### Import Router Models
| Model | Key Fields |
|-------|------------|
| ImportRow | building_name, floor, apartment_number, tenant_name, tenant_phone |
| ExecuteImportRequest | rows[] |

### Export Router Models
| Model | Key Fields |
|-------|------------|
| ExportFilters | status, category, company, floor, unit, search |
| ExportRequest | scope, unit_id, building_id, filters, format |

### Identity Router Models
| Model | Key Fields |
|-------|------------|
| CompleteAccountRequest | password, full_name, preferred_language |
| ChangePasswordRequest | old_password, new_password |
| ChangeEmailRequest | new_email, password |

### QC Router Models
| Model | Key Fields |
|-------|------------|
| QCItemUpdate | status, note, photos |
| ApproverCreateBody | user_id, mode, stages |
| ApproveRejectBody | action, reason |

### Archive Router Models
| Model | Key Fields |
|-------|------------|
| ArchiveRequest | reason |
| HardDeleteRequest | confirmation_code |

## 10. Backend — Services & Utils

### `services/`
| File | Purpose |
|------|---------|
| object_storage.py | S3/local file storage abstraction |
| storage_service.py | Storage layer wrapper |
| handover_pdf_service.py | Handover protocol PDF generation (WeasyPrint) |
| pdf_service.py | Base PDF generation |
| pdf_template_service.py | PDF template engine |
| enhanced_pdf_service.py | Enhanced PDF with findings |
| enhanced_pdf_service_v2.py | PDF generation v2 |
| thumbnail_service.py | Image/PDF thumbnail generation (Pillow + pdf2image) |
| ai_service.py | LLM integration for AI features |
| audit_service.py | Audit event recording |
| document_vault_service.py | Document storage management |
| regulation_service.py | Building regulation lookup |

### `contractor_ops/` (services & utils within)
| File | Purpose |
|------|---------|
| notification_service.py | WhatsApp + SMS sending logic |
| sms_service.py | Twilio SMS delivery |
| otp_service.py | OTP generation & verification |
| reminder_service.py | Auto-reminder scheduling |
| identity_service.py | Identity management logic |
| green_invoice_service.py | Green Invoice API integration |
| invoicing.py | Invoice generation business logic |
| billing.py | Billing business logic |
| billing_plans.py | Plan catalog definitions |
| phone_utils.py | Phone normalization (mobile + landline, IL) |
| bucket_utils.py | S3 bucket helpers |
| member_management.py | Team member operations |
| msg_logger.py | Message delivery audit logging |
| snapshot_cron.py | Daily analytics snapshot cron |
| task_image_guard.py | Task image access validation |
| upload_rate_limit.py | Upload rate limiting middleware |
| stepup_service.py | Step-up authentication for admin |
| constants.py | TERMINAL_TASK_STATUSES, shared constants |
| utils/timezone.py | Shared Israel timezone helper |

### `utils/`
| File | Purpose |
|------|---------|
| image_processor.py | Server-side image processing |

## 11. MongoDB Collections

| Collection | Stores | Primary Module |
|------------|--------|----------------|
| users | User profiles, credentials, roles | auth_router, identity_router |
| organizations | Organization data, owners, settings | admin_router, billing_router |
| organization_memberships | User ↔ Org links with roles | admin_router, identity_service |
| projects | Project metadata | projects_router |
| project_memberships | User ↔ Project links with roles | router, invites_router |
| buildings | Building definitions in project | projects_router, excel_router |
| floors | Floor definitions in building | projects_router |
| units | Units/apartments on floors | projects_router |
| tasks | Defect tasks, assignments, status | tasks_router, qc_router |
| task_updates | Task change audit trail, proof images | tasks_router |
| task_status_history | Task status transition history | tasks_router |
| invites | Project invitations | invites_router |
| team_invites | Legacy invitation storage | invites_router |
| audit_events | Security/activity audit log | router, identity_router |
| notification_jobs | SMS/WhatsApp notification queue | notification_service |
| qc_templates | QC check templates | qc_router, admin_router |
| qc_runs | QC process instances | qc_router |
| qc_items | Individual QC check items | qc_router |
| handover_protocols | Handover records, signatures | handover_router |
| handover_items | Handover checklist items | handover_router |
| unit_tenant_data | G4-imported tenant data for prefill | import_router, handover_router |
| billing_plans | Pricing tiers/features | billing_router |
| subscriptions | Active billing subscriptions | billing_router |
| project_billing | Project-specific billing settings | billing_router |
| invoices | Billing invoices, payment status | billing_router |
| gi_webhook_log | Green Invoice webhook logs | billing_router |
| billing_renewal_attempts | Renewal process history | billing_router |
| project_plans | Blueprints and drawings | plans_router |
| plan_read_receipts | Plan view tracking | plans_router |
| project_companies | Companies in project | companies_router |
| project_trades | Trade/discipline categories | invites_router |
| project_disciplines | Specialized disciplines | plans_router |
| ownership_transfer_requests | Org transfer security tokens | ownership_transfer |
| otp_rate_limits | OTP attempt rate limiting | otp_service |
| msg_logger | Message delivery debug log | msg_logger |

## 12. Environment Variables

### Backend (`backend/config.py` + services)
| Variable | File | Purpose |
|----------|------|---------|
| APP_ID | config.py | Application identifier |
| APP_MODE | config.py, server.py | `dev` or `prod` |
| JWT_SECRET | config.py | JWT signing secret |
| JWT_SECRET_VERSION | config.py | JWT secret rotation version |
| JWT_EXPIRATION_HOURS | config.py | Token TTL (default: 720) |
| MONGO_URL | config.py | MongoDB connection string |
| DB_NAME | config.py | Database name |
| PUBLIC_APP_URL | server.py | Canonical public URL |
| ALLOWED_HOSTS | server.py | Allowed hosts list |
| CORS_ORIGINS | server.py | CORS allowed origins |
| ENABLE_API_DOCS | server.py | Toggle Swagger/Redoc |
| RUN_SEED | server.py | Run DB seeding on startup |
| WHATSAPP_ENABLED | config.py | Global WA toggle |
| WA_INVITE_ENABLED | config.py | WA invite toggle |
| WHATSAPP_PROVIDER | config.py | WA provider (e.g., `meta`) |
| WA_ACCESS_TOKEN | config.py | Meta WA API token |
| WA_PHONE_NUMBER_ID | config.py | Meta sender phone ID |
| WABA_ID | config.py | WhatsApp Business Account ID |
| META_APP_SECRET | config.py | Meta app secret |
| OWNER_PHONE | config.py | System owner phone |
| SUPER_ADMIN_PHONES | config.py | Comma-separated admin phones |
| OTP_PROVIDER | config.py | OTP provider (`mock`/`twilio`) |
| OTP_TTL_SECONDS | config.py | OTP expiration time |
| SMS_MODE | config.py | SMS mode (`live`/`stub`/`mock`) |
| SMS_ENABLED | config.py | SMS toggle |
| TWILIO_ACCOUNT_SID | config.py | Twilio SID |
| TWILIO_AUTH_TOKEN | config.py | Twilio auth token |
| FILES_STORAGE_BACKEND | object_storage.py | `local` or `s3` |
| AWS_S3_BUCKET | object_storage.py | S3 bucket name |
| AWS_REGION | object_storage.py | AWS region |
| AWS_ACCESS_KEY_ID | object_storage.py | AWS credentials |
| AWS_SECRET_ACCESS_KEY | object_storage.py | AWS credentials |
| EMERGENT_LLM_KEY | ai_service.py | AI/LLM API key |
| SMTP_HOST / SMTP_USER / SMTP_PASS | config.py | Email SMTP config |
| GI_BASE_URL / GI_API_KEY_ID | config.py | Green Invoice API config |
| RELEASE_SHA | start.sh | Git commit SHA for versioning |

### Frontend
| Variable | File | Purpose |
|----------|------|---------|
| REACT_APP_BACKEND_URL | services/api.js | API base URL (empty = relative) |
| REACT_APP_GIT_SHA | TaskDetailPage.js | Git SHA displayed in UI |
| REACT_APP_ENABLE_REGISTER_MANAGEMENT_REDIRECTS | LoginPage.js | Registration redirect toggle |
| NODE_ENV | i18n/index.js, craco.config.js | Standard env flag |

## 13. Key Patterns & Conventions

### File Naming
- **Pages**: `PascalCasePage.js` in `pages/`
- **Components**: `PascalCase.js` in `components/`
- **Backend routers**: `snake_case_router.py` in `contractor_ops/`
- **Services**: `snake_case_service.py` in `services/`
- **UI primitives**: `kebab-case.jsx` in `components/ui/` (shadcn convention)

### Error Handling
- Backend: FastAPI `HTTPException` with status codes; `try/except` with `logger.error(..., exc_info=True)` for unexpected failures
- Frontend: `ErrorBoundary` component with Hebrew error messages; toast notifications via `use-toast` hook

### Auth / Middleware
- JWT Bearer token in `Authorization` header
- `get_current_user` dependency injected in every protected endpoint
- Step-up OTP for super_admin sensitive operations
- Project-scoped RBAC via `project_memberships` collection

### Feature Structure
- Flat structure: one router file per module in `contractor_ops/`
- Large modules keep logic in same file (e.g., `handover_router.py` ~1500+ lines)
- Shared utilities extracted to `utils/`, `services/`, `constants.py`
- Frontend: one page component per route, shared components in `components/`

### i18n Pattern
- `setLanguage()` called before `setUser()` in AuthContext
- PM users forced to Hebrew regardless of preference
- Contractor language follows `preferred_language` from user profile
- All 4 locales: he (primary), en, ar, zh
- Lookup: current locale → Hebrew fallback → raw key

### RTL
- All languages render RTL (no `dir` changes)
- `document.documentElement.lang` set by `setLanguage()`

## 14. Recent Changes (Last Session)

| # | Summary |
|---|---------|
| #220 | Contractor i18n Phase 3 — QC + Handover + Unit modules |
| #221 | Android OTP autofill + `autocomplete="one-time-code"` |
| #222 | Admin billing perf — fix 3 N+1 queries + 2 indexes |
| #223 | Admin billing page performance — fix 3 N+1 patterns + 2 indexes |
| #224 | Fix overlapping layout on Structure page mobile |
| #225 | Smart G4 Import Phase 1 — header aliases, cross-reference, adaptive UI |
| #226 | Pre-deploy fixes for Smart G4 Import (batch tenant load, ambiguous unit case) |
| #227 | Fix tenant prefill — unit_id-first lookup + phone_2/handover_date in output |
| #228 | Debug & fix silent prefill failure — add logging to except block |
| #229 | Remove prefill debug logging (keep single info line) |

## 15. Known Issues & Backlog

### Broken
- **ProjectTasksPage** — currently broken (not investigated yet)

### Planned but not built
- **Billing flow** — waiting for Morning/Green Invoice support response
- **Capacitor wrapper** — needed for App Store submission
- **Logo creation** — no logo designed yet
- **ProjectControlPage refactor** — 3680 lines, needs splitting into sub-components

### Blocked
- **Billing flow**: blocked on Morning/Green Invoice support
- **WA v3 templates**: waiting for Meta template approval; when approved, update env vars `WA_DEFECT_TEMPLATE_HE/EN/AR/ZH` from `_v2` to `_v3`
