# BrikOps — Weekly Changelog
**Period:** March 4–11, 2026
**Total commits:** ~95 (excluding mode transitions)
**Files changed:** 139 | **Lines added:** ~18,884 | **Lines removed:** ~2,248

---

## Bugs Fixed

### 1. Billing endpoint crash on missing manual override
- **Problem:** `GET /billing/org/{org_id}` crashed with `KeyError` when an org subscription had no `manual_override` field.
- **Fix:** Added safe `.get()` access with default fallback in billing logic.
- **Files:** `backend/contractor_ops/billing.py`
- **Commit:** `71b40ec` (Mar 11)

### 2. PDF export — large defect cards breaking page layout
- **Problem:** Defect cards with many images or long descriptions overflowed PDF pages, causing cut-off content.
- **Fix:** Implemented card-aware page breaking and image caching to prevent repeated downloads of the same image across pages.
- **Files:** `backend/contractor_ops/export_router.py`
- **Commits:** `0b49e7a`, `10a4204`, `5ff63e9` (Mar 10)

### 3. PDF export — image security and handling
- **Problem:** S3 presigned URLs expired during long PDF generation; some images failed silently.
- **Fix:** Added image caching layer, proper error handling for failed image downloads, and security headers for exported documents.
- **Files:** `backend/contractor_ops/export_router.py`
- **Commit:** `10a4204` (Mar 10)

### 4. Excel export — Hebrew filename encoding
- **Problem:** Downloaded Excel files had garbled Hebrew filenames in the browser.
- **Fix:** Corrected `Content-Disposition` header encoding for Hebrew characters using RFC 5987 `filename*` parameter.
- **Files:** `backend/contractor_ops/export_router.py`
- **Commit:** `15a2fe1` (Mar 10)

### 5. Contractor selection broken in defect creation
- **Problem:** Selecting a contractor in `NewDefectModal` did not work correctly — company/contractor cascade was broken.
- **Fix:** Rewrote company→contractor selection cascade with proper state management and category-based filtering.
- **Files:** `frontend/src/components/NewDefectModal.js`
- **Commit:** `b661595` (Mar 4)

### 6. Contractor assignment — missing company handling
- **Problem:** Task assignment failed when contractor had no linked company, or company had mismatched trade.
- **Fix:** Added trade-mismatch guard, company validation before assignment, and clear Hebrew error messages.
- **Files:** `backend/contractor_ops/tasks_router.py`, `frontend/src/components/NewDefectModal.js`
- **Commits:** `22667d6`, `848ca7e` (Mar 5)

### 7. Image upload failures on iOS (HEIC format)
- **Problem:** iOS camera images (HEIC format) failed to upload or resulted in empty files.
- **Fix:** Added `createImageBitmap`-based HEIC compression, retry logic with exponential backoff, and content-type auto-detection.
- **Files:** `frontend/src/components/NewDefectModal.js`, `frontend/src/utils/imageCompress.js`, `backend/services/storage_service.py`
- **Commits:** `94b70f0`, `c118d85`, `f19b7b9`, `526f22d` (Mar 5)

### 8. Camera access failure on iOS Safari
- **Problem:** Camera modal crashed on iOS when camera permissions were denied or unavailable.
- **Fix:** Created dedicated `CameraModal` component with proper error handling, fallback to gallery, and iOS-compatible permission flow.
- **Files:** `frontend/src/components/CameraModal.js`
- **Commits:** `3256cfe`, `4faf6c7` (Mar 5)

### 9. API URL handling for Replit preview
- **Problem:** Frontend API calls failed in Replit preview because `BACKEND_URL` defaulted to production URL.
- **Fix:** Centralized `BACKEND_URL` in `api.js` with empty string default (relative URLs); all 7 consumer files updated to import from single source.
- **Files:** `frontend/src/services/api.js`, `frontend/src/contexts/AuthContext.js`, `frontend/src/contexts/BillingContext.js`, plus 5 page files
- **Commit:** `2b3a723` (Mar 5)

### 10. WhatsApp notification delivery failures
- **Problem:** WhatsApp messages failed due to incorrect phone normalization and missing fallback images.
- **Fix:** Fixed phone normalization for Israeli numbers, added S3 presigned fallback image URL, improved webhook logging.
- **Files:** `backend/contractor_ops/notification_service.py`, `backend/contractor_ops/notification_router.py`
- **Commits:** `7b5e2d9`, `a9d8435`, `dbe12d3` (Mar 5–6)

### 11. Feature flag endpoint missing
- **Problem:** Frontend called `/api/config/features` but endpoint didn't exist, causing console errors.
- **Fix:** Created `config_router.py` with public (no-auth) feature flags endpoint.
- **Files:** `backend/contractor_ops/config_router.py`
- **Commit:** `8679f73` (Mar 4)

### 12. Duplicate payment requests
- **Problem:** Rapid clicks on payment request button created duplicate records.
- **Fix:** Added idempotency check in billing endpoint.
- **Files:** `backend/contractor_ops/billing_router.py`
- **Commit:** `3c0bb5d` (Mar 4)

### 13. Demo login buttons hidden
- **Problem:** Dev login buttons were accidentally hidden on the login page.
- **Fix:** Restored visibility of demo login buttons.
- **Files:** `frontend/src/pages/LoginPage.js`
- **Commit:** `34ea1d1` (Mar 4)

### 14. Cache control — stale content after deploys
- **Problem:** Users saw outdated frontend content after deployments due to aggressive browser caching.
- **Fix:** Added `Cache-Control: no-cache` headers for HTML responses in dev mode, gated on `NODE_ENV`.
- **Files:** `backend/server.py`
- **Commit:** `f87a64d` (Mar 10)

---

## New Features

### 1. Defects Export (Excel + PDF)
- Full export system for defects at building or unit scope.
- **Excel:** `.xlsx` with Hebrew headers, RTL layout, all defect fields.
- **PDF:** A4 pages with Rubik font, Hebrew RTL, defect cards with images kept together, proper pagination.
- UI: `ExportModal` component with format selection (Excel/PDF).
- **Files:** `backend/contractor_ops/export_router.py`, `frontend/src/components/ExportModal.js`, `frontend/src/services/api.js`
- **Commits:** `6c46dcb` → `5ff63e9` (Mar 10)

### 2. Defects V2 — Building & Apartment Views
- Parallel defect views gated by `ENABLE_DEFECTS_V2` feature flag.
- `BuildingDefectsPage`: building-level defect list with filter drawer, status chips, KPI summary.
- `ApartmentDashboardPage`: unit-level defect dashboard with stats and export.
- `FilterDrawer`: slide-out filter panel with collapsible sections, multi-select status/category/priority filters.
- **Files:** `frontend/src/pages/BuildingDefectsPage.js`, `frontend/src/pages/ApartmentDashboardPage.js`, `frontend/src/components/FilterDrawer.js`
- **Commits:** `5bf575e`, `c2eda1d`, `2728c49` (Mar 10)

### 3. InnerBuildingPage — Building Workspace
- New mobile-first building workspace at `/projects/:projectId/buildings/:buildingId`.
- Sticky dark header, 3-tab work switcher (דירות/קומות, ליקויים, בקרת ביצוע).
- KPI strip with unit/floor/defect counts.
- Collapsible floor→apartment hierarchy with inline status indicators.
- FAB with add-floor (amber form) and add-unit (blue form) flows.
- Per-floor "+" button for adding units, auto-expand/scroll on new floor creation.
- **Files:** `frontend/src/pages/InnerBuildingPage.js`, `frontend/src/App.js`
- **Commits:** `558cd2c`, `56ae3bd` (Mar 11)

### 4. BuildingQCPage — Building-Scoped QC
- New page at `/projects/:projectId/buildings/:buildingId/qc`.
- Shows only target building's floors with QC status badges and quality indicators.
- Client-side search, status filter chips (amber active state), compact summary line.
- Smart back navigation, no duplicate status chips per row.
- **Files:** `frontend/src/pages/BuildingQCPage.js`, `frontend/src/App.js`
- **Commit:** `98ae495` (Mar 11)

### 5. QC Navigation Unified
- `/projects/:projectId/qc` rewritten from floor-list to lightweight building selector.
- All QC entry points (ProjectControlPage tab, ProjectDashboardPage link, InnerBuildingPage QC tab) converge into: building selector → BuildingQCPage → FloorDetailPage.
- FloorDetailPage back button changed to smart `navigate(-1)` with fallback.
- **Files:** `frontend/src/pages/QCFloorSelectionPage.js`, `frontend/src/pages/FloorDetailPage.js`
- **Commit:** `1fa0e68` (Mar 11)

### 6. ProjectPlansPage Refresh
- Complete UX rewrite: compact dark header with project name subtitle, horizontal scrollable discipline chips (amber active, `text-[11px]`, `gap-1`), client-side search.
- Plan rows: title primary (`font-bold text-[13px] line-clamp-2`), action icons secondary (`w-3.5 h-3.5 text-slate-400`), delete in `text-red-300`.
- Upload modal with amber accents, inline add-discipline, smart back navigation.
- **Files:** `frontend/src/pages/ProjectPlansPage.js`
- **Commits:** `5d70a51`, `d3a2b82` (Mar 11)

### 7. UnitPlansPage Refresh
- Aligned to match ProjectPlansPage visual language.
- Dark slate header with unit label + breadcrumb subtitle, amber accents, horizontal chips, client-side search, same row hierarchy.
- Amber upload modal, smart back navigation.
- No delete on unit plans (intentional product decision).
- Permission logic uses project-scoped role (`unitData?.project?.my_role || user?.role`).
- **Files:** `frontend/src/pages/UnitPlansPage.js`
- **Commit:** `747d735` (Mar 11)

### 8. ProjectControlPage — Full Redesign
- Compact header with amber palette, 4-tab work switcher (ליקויים|בקרת ביצוע|תוכניות|מבנה).
- RTL support throughout, building QC progress indicators per building card.
- Active tab states with amber underline, visual polish across all tabs.
- **Files:** `frontend/src/pages/ProjectControlPage.js`
- **Commits:** `941c139`, `27a54b7`, `cd42675`, `39e08af` (Mar 11)

### 9. NewDefectModal — Robust 3-Step Flow
- Rewrote defect creation as a 3-step process: create task → upload images → assign contractor.
- Image upload with retry logic (exponential backoff), upload error recovery with draft save.
- HEIC compression via `createImageBitmap`, camera/gallery split buttons.
- Category-based company filtering, trade-mismatch warnings.
- Progress indicators per step (creating → uploading → assigning).
- **Files:** `frontend/src/components/NewDefectModal.js`
- **Commits:** `4881cd1`, `526f22d`, `94b70f0` (Mar 5)

### 10. UpgradeWizard — Billing Plan Management
- New component for managing billing plans and renewals.
- Plan selection, renewal preview, payment flow integration.
- **Files:** `frontend/src/components/UpgradeWizard.js`
- **Commit:** `6fa8047` (Mar 4)

### 11. Legal Pages
- Three static legal pages added: Terms of Service, Privacy Policy, Data Deletion.
- Hebrew content, served as static HTML from `/legal/`.
- **Files:** `frontend/public/legal/terms.html`, `frontend/public/legal/privacy.html`, `frontend/public/legal/data-deletion.html`
- **Commit:** `3d870e5` (Mar 5)

### 12. Mockup Sandbox
- Vite-based component preview environment for developing UI components in isolation.
- Separate `mockup/` directory with its own build tooling, shadcn/ui components, preview plugin.
- **Files:** `mockup/` directory (entire)
- **Commit:** `7872926` (Mar 11)

### 13. Task Image Guard
- Backend enforces at least one image before contractor assignment.
- New middleware module for image validation on task attachment endpoint.
- **Files:** `backend/contractor_ops/task_image_guard.py`, `backend/contractor_ops/tasks_router.py`

---

## Security Hardening

### 1. PyJWT Migration
- Replaced `ecdsa`-based JWT handling with `PyJWT==2.11.0`.
- HS256 algorithm enforcement, issuer validation, consistent secret versioning.
- Removed vulnerable `ecdsa` and `python-jose` dependencies.
- **Files:** `backend/requirements.txt`, `backend/contractor_ops/router.py`, `backend/contractor_ops/onboarding_router.py`, `backend/server.py`
- **Commit:** `b9e270d` (Mar 11)

### 2. OTP Flow Hardening
- Rate limits: per-IP, per-phone, per-phone+IP combo.
- Brute-force lockout after excessive failed attempts.
- SHA-256 hashed 6-digit codes, one-time use enforcement.
- Generic error messages (no information leakage).
- Structured audit logging for all OTP events.
- **Files:** `backend/contractor_ops/onboarding_router.py`, `backend/contractor_ops/otp_service.py`
- **Commits:** `08a62aa`, `7f52083` (Mar 11)

### 3. OTP Rate Limits Persistent in MongoDB
- Moved rate limit counters from in-memory dicts to MongoDB collections.
- Survives server restarts, works correctly across multiple processes.
- **Files:** `backend/contractor_ops/onboarding_router.py`, `backend/server.py`
- **Commit:** `b5bd593` (Mar 11)

### 4. Python Dependency Security Updates
- Updated multiple Python packages to address known vulnerabilities.
- **Files:** `backend/requirements.txt`
- **Commit:** `2745dc8` (Mar 11)

### 5. Frontend Dependency Updates
- Updated frontend packages for security patches.
- **Files:** `frontend/package.json`, `frontend/yarn.lock`
- **Commit:** `a8d295c` (Mar 10)

---

## Architecture Changes

### 1. Sub-router for Feature Flags
- New `config_router.py` — public endpoint at `/api/config/features` (no auth required).
- Allows frontend to check feature flags without authentication.

### 2. Export System
- New `export_router.py` (834 lines) — handles Excel and PDF export of defects.
- Supports building-scope and unit-scope exports, Hebrew RTL formatting.

### 3. Mockup Sandbox Environment
- Separate Vite-based environment (`mockup/`) for prototyping UI components.
- Independent from main app build pipeline, uses pnpm.

### 4. Deploy Script Improvements
- `deploy.sh` rewritten with staleness detection, frontend rebuild verification, fail-fast error handling.
- Change detection for backend vs frontend deploys.

---

## Still Open / Known Issues

### Active Bugs
1. **Meta WhatsApp template SSL** — Button URL in Meta templates still points to `www.brikops.com` (no SSL). Must update to `https://app.brikops.com/tasks/{{1}}` in Meta Business Suite. Code is ready; waiting for Meta re-approval.
2. **Meta template 404** — Error 132001 "template name does not exist in en" for `brikops_defect_new_he`. Likely Meta-side issue or template modification.
3. **Step-up index conflict** — `IndexOptionsConflict` warning on startup for `expires_at_1` TTL index. Non-blocking; step-up auth works.
4. **Checkout endpoint stub** — `POST /billing/org/{org_id}/checkout` returns 501. Placeholder for Stripe integration.

### Test Infrastructure Issues
5. **`test_s3_mode.py`** — Crashes pytest with `sys.exit()` at module level. Not a code bug; test infrastructure issue.
6. **`test_billing.py` / `test_billing_v1.py`** — 47 tests fail with `httpx.ConnectError`. Integration tests that require a separate test server.

### Planned / Not Yet Implemented
7. **Stripe payment integration** — Endpoint stub exists, no implementation yet.
8. **V2 WhatsApp templates** — Ready in code, pending Meta approval. Switch is env-var only.
9. **AI features** — Service module exists (`ai_service.py`), not yet connected to UI.
10. **Document Vault** — Service scaffolded, not yet functional.

---

## Changed Files (Complete List)

### Backend (30 files)
```
backend/api_intelligence_routes.py          (removed)
backend/config.py
backend/contractor_ops/auth_router.py
backend/contractor_ops/billing.py
backend/contractor_ops/billing_router.py
backend/contractor_ops/config_router.py     (new)
backend/contractor_ops/debug_router.py
backend/contractor_ops/export_router.py     (new)
backend/contractor_ops/msg_logger.py
backend/contractor_ops/notification_router.py
backend/contractor_ops/notification_service.py
backend/contractor_ops/onboarding_router.py
backend/contractor_ops/otp_service.py
backend/contractor_ops/projects_router.py
backend/contractor_ops/qc_router.py
backend/contractor_ops/router.py
backend/contractor_ops/schemas.py
backend/contractor_ops/stats_router.py
backend/contractor_ops/task_image_guard.py  (new)
backend/contractor_ops/tasks_router.py
backend/contractor_ops/wa_login.py
backend/fonts/Rubik-Bold.ttf
backend/requirements.txt
backend/server.py
backend/services/object_storage.py
backend/services/storage_service.py
```

### Frontend (33 files)
```
frontend/package.json
frontend/yarn.lock
frontend/public/legal/data-deletion.html    (new)
frontend/public/legal/privacy.html          (new)
frontend/public/legal/terms.html            (new)
frontend/src/App.js
frontend/src/components/CameraModal.js      (new)
frontend/src/components/ExportModal.js      (new)
frontend/src/components/FilterDrawer.js     (new)
frontend/src/components/NewDefectModal.js
frontend/src/components/UpgradeWizard.js    (new)
frontend/src/contexts/AuthContext.js
frontend/src/contexts/BillingContext.js
frontend/src/pages/AdminPage.js
frontend/src/pages/ApartmentDashboardPage.js (new)
frontend/src/pages/BuildingDefectsPage.js   (new)
frontend/src/pages/BuildingQCPage.js        (new)
frontend/src/pages/ContractorDashboard.js
frontend/src/pages/FloorDetailPage.js
frontend/src/pages/InnerBuildingPage.js     (new)
frontend/src/pages/LoginPage.js
frontend/src/pages/OnboardingPage.js
frontend/src/pages/OrgBillingPage.js
frontend/src/pages/PhoneLoginPage.js
frontend/src/pages/ProjectControlPage.js
frontend/src/pages/ProjectPlansPage.js
frontend/src/pages/ProjectTasksPage.js
frontend/src/pages/QCFloorSelectionPage.js
frontend/src/pages/StageDetailPage.js
frontend/src/pages/TaskDetailPage.js
frontend/src/pages/UnitPlansPage.js
frontend/src/pages/WaLoginPage.js
frontend/src/services/api.js
frontend/src/utils/imageCompress.js
```

### Mockup Sandbox (71 files — all new)
```
mockup/.npmrc
mockup/components.json
mockup/index.html
mockup/mockupPreviewPlugin.ts
mockup/package.json
mockup/pnpm-lock.yaml
mockup/tsconfig.json
mockup/vite.config.ts
mockup/src/App.tsx
mockup/src/main.tsx
mockup/src/index.css
mockup/src/lib/utils.ts
mockup/src/hooks/use-mobile.tsx
mockup/src/hooks/use-toast.ts
mockup/src/.generated/mockup-components.ts
mockup/src/components/mockups/building-qc/BuildingQCPage.tsx
mockup/src/components/ui/  (55 UI component files: accordion, alert, alert-dialog,
    aspect-ratio, avatar, badge, breadcrumb, button, button-group, calendar, card,
    carousel, chart, checkbox, collapsible, command, context-menu, dialog, drawer,
    dropdown-menu, empty, field, form, hover-card, input, input-group, input-otp,
    item, kbd, label, menubar, navigation-menu, pagination, popover, progress,
    radio-group, resizable, scroll-area, select, separator, sheet, sidebar,
    skeleton, slider, sonner, spinner, switch, table, tabs, textarea, toast,
    toaster, toggle, toggle-group, tooltip)
```

### Infrastructure (6 files)
```
.github/workflows/deploy-backend.yml
.gitignore
.platform/nginx/conf.d/proxy.conf
deploy.sh
fix-git-push.sh                            (new)
frontend/public/_redirects                  (removed)
```

### Documentation (2 files)
```
PROJECT_OVERVIEW.md
replit.md
```
