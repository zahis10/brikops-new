# BrikOps Roadmap

**Last updated:** 2026-05-12 (PhotoAnnotation marathon — F + F.1 series + F-keyboard. 7 successful prod deploys + 2 revert-and-retry cycles + 1 hotfix.)
**Owner:** Zahi
**Status:** Closed-beta in prod. **MAY 12 — PhotoAnnotation feature complete: text labels with size/color/drag/edit + viewport-aware canvas for mobile keyboard.**

Today (2026-05-12):
1. **Batch K shipped (`900e802`)** — Trade-mismatch error message in contractor-proof endpoint. `tasks_router.py:867`: 404 "הליקוי לא נמצא" → 400 "לא ניתן לסגור — הליקוי שייך לקטגוריה אחרת. פנה למנהל." Status code reflects "request can't be honored" not "resource missing". Trade-match logic itself preserved (architectural rule). Assignee-mismatch 404 unchanged (security wording). Discovered during Batch J prod testing — old contractor assignments pre-trade-rule were showing misleading "not found" error.
2. **Batch F shipped (`c08e314`)** — Photo annotation text labels v1. PMs can now annotate defect photos with short Hebrew/English text labels (defect numbers like "5/27", measurements, apartment callouts) in addition to freehand strokes. T tool toggle in top toolbar; inline overlay input at bottom (NOT browser prompt) with `font-size: 16px` to prevent iOS auto-zoom; white-bg rounded-pill rendering with colored text. Storage extends existing `strokes` array with type discriminator (`type: 'stroke' | 'text'`). Hebrew font stack + `ctx.direction='rtl'`. Color captured at COMMIT time (not tap time — final intent). Reposition-while-typing pattern (2nd tap preserves typed value). +150 LOC to PhotoAnnotation.js (358 → 522).
3. **F.1 attempted + reverted** — Replit shipped `c553fef` with size + drag + edit combined in one batch (286 LOC). Broke staging (broken React bundle). Reverted at `89ac72f`. **Lesson: micro-batch the F.1 features.** Split into F.1a (size) + F.1b (drag) + F.1c (edit).
4. **F.1a shipped (`dee1879`)** — Size picker (small/medium/large). 3 buttons inside pendingText overlay showing "א" at relative font-size for instant preview. `SIZE_MULTIPLIERS = { small: 0.7, medium: 1.0, large: 1.4 }` applied to TEXT_FONT_SIZE in redraw. Captured at COMMIT time (mirror of color pattern). Resets to 'medium' between labels (intentional — each new label starts at default). +48 LOC.
5. **F.1b shipped (`29c23c0`)** — Drag-to-move existing text labels. `DRAG_THRESHOLD_PX = 10` (canvas-space) differentiates tap from drag. New `hitTestText(pos)` helper iterates reverse over strokes (last-drawn = topmost). `draggingTextRef` tracks drag state. **In-place mutation** of `strokesRef.current[i].x/y` during drag + `redraw` per move event; state sync happens ONCE at endStroke — avoids per-frame re-render (Mode B lesson from P1.1 pinch saga). +120 LOC.
6. **F.1b-hotfix-1 shipped (`a410b29`)** — Hit-test was returning -1 on every tap, even on labels. Root cause: `hitTestText` used `ctx.measureText` to compute bbox, but didn't set `ctx.direction='rtl' / textBaseline='middle' / textAlign='center'` like `redraw` did. iOS WebKit + Hebrew = narrower bbox than rendered pill. **Fix:** cache `_bbox` on stroke object during redraw (stroke._bbox = {x,y,width,height}); hit-test reads cached bbox. Plus 44×44 display-px minimum touch area for finger-friendly hit on small pills (CLAUDE.md touch-target rule). +19 LOC net.
7. **F.1c shipped (`b619a3c`)** — Tap-to-edit existing labels IN-SESSION. Pure tap (no drag past threshold) on label opens pendingText overlay prefilled with text/color/size. `commitPendingText` branches on optional `editingIndex` field: if set → REPLACE via `.map()` (preserves array index + undo stack semantics); else APPEND (F behavior). `setColor + setTextSize` on entering edit so toolbar UI reflects label properties. Cancel button preserves picker state when editing (don't reset to medium). +37 LOC. **F.1 series complete.**
8. **F-keyboard v1 attempted + reverted (`0fbbd35` → `a6ab26c`)** — Viewport-aware canvas to fix iPhone keyboard zoom-in. Spec deferred ESLint deps choice (Option A eslint-disable vs Option B add to deps) to Build mode. Replit chose Option B for cleanliness — but `applyDisplayScale` is declared LATER in source than the imageFile useEffect that referenced it. TDZ ReferenceError → "משהו השתבש" error boundary at first render. **Lesson: deps arrays are evaluated synchronously; const-in-TDZ = crash.** The closure inside doLoad would have worked fine (only deps array threw).
9. **F-keyboard v2 shipped** — Same logic as v1 + correct deps strategy. imageFile useEffect deps stays `[imageFile]` with `eslint-disable-next-line react-hooks/exhaustive-deps` + 14-line warning block citing v1's revert and proving stability of applyDisplayScale (deps chain: getLineWidth[] → redraw[getLineWidth] → applyDisplayScale[redraw]). VERIFY 6 grep guardrail: "deps array literally reads `[imageFile]`" — fail-fast for TDZ regression. +56 LOC. **Known minor issue:** canvas takes ~half the screen when keyboard up — accepted UX trade-off until negative feedback. If reported → polish batch (smaller canvas footprint OR separate fullscreen input overlay).
10. **CLAUDE.md additions (implicit, via this session):** TDZ trap pattern (const referenced in deps array before its declaration line); micro-batch discipline when a combined batch broke (F.1 → F.1a/b/c); bbox-cache > re-measure when redraw and hit-test must match exactly (iOS WebKit measureText drift); 44×44 minimum touch target for finger-friendly tap on small UI elements.

**PhotoAnnotation feature status — current state:**
- ✅ Freehand drawing (3 colors)
- ✅ Text labels — create, drag, edit (in-session)
- ✅ Size picker (small/medium/large)
- ✅ 44×44 min touch area for accurate hit-test on small pills
- ✅ Canvas resizes when mobile keyboard opens (full image visible, just smaller)
- ✅ Save → JPEG full intrinsic resolution preserved
- ⚠️ Canvas takes ~half screen when keyboard up — accepted, watch for feedback
- ⚠️ Re-edit AFTER save: photo opens clean (annotations rasterized only). **Architectural batch needed** to persist strokes as JSON server-side alongside JPEG.
- 📋 F.2 (X discard button to close modal without saving) — spec ready at `specs/batch-f2-photo-discard-button-2026-05-12.txt`, ~15 LOC, surgical.

Yesterday (2026-05-11):
1. **P1.1-hotfix-6 shipped (revert pinch)** — hotfix-4 + hotfix-5 attempted pinch via @use-gesture/react with re-render-per-frame. Both shipped but iPhone UX was jank-prone ("1% steps") because react-pdf re-render takes 50-100ms × 60Hz pinch rate = unavoidable frame drops. Architectural mismatch, not config bug. Decision: REVERT pinch entirely; keep @use-gesture/react in deps (P1.4 will re-use); ship P1.1 with +/- buttons + scrollbar pan as sole zoom UX. ~80 LOC removed from PlanViewer.js, tree-shook ~20KB of bundle. P1.1 now in stable foundation state.
2. **Batch A+C+D shipped (4 UX bugs closed):**
   - **#28** Unit lex sort fixed: `qc_router.py:1028` now uses `_natural_sort_key` (reuse from projects_router.py, no duplication). `UnitQCSelectionPage.js:165` adds explicit `localeCompare(b, 'he', { numeric: true })`. Floors with units 7-11 now display in natural order (7, 8, 9, 10, 11) not lex (10, 11, 7, 8, 9). Hebrew+mixed-alphanumeric unit numbers handled correctly. Confirmed live ✓.
   - **#30** Empty unit-scope stages hidden: single `.filter(s => (s.total_units || 0) > 0)` at `FloorDetailPage.js:301`. Floors with 0 units (e.g. floor -3 mechanical) now show only floor-scope stages. Confirmed live ✓.
   - **#31** Stage back-nav respects returnToPath: `StageDetailPage.js:1603` `goBack()` rebuilt with `URL.searchParams.set()` for idempotent query construction (defends against future returnTo with pre-existing query params — pattern already exists in codebase via ProjectControlPage/ProjectTasksPage). Try/catch fallback for malformed URLs. PM doing stage QC now returns to correct unit list with stage_id preserved. Refresh-tab limitation documented (deferred to future batch). Confirmed staging + live ✓.
   - **#34** iPhone header overflow fixed: `UnitQCSelectionPage.js:181` adds `overflow-x-hidden` (safety net) + L232 header row gets `min-w-0 flex-1 / truncate / flex-shrink-0` classes. Long unit names truncate with "…", badge + count always visible, no horizontal page scroll. Confirmed live on iPhone Capacitor app ✓.
3. **#29 cancelled** — "Floor sort broken with negative floors (מרתף)" turned out to be inferred not observed. Users already type "-3" / "-2" as floor names which backend parses correctly via `int()`. Hebrew keyword detection (Batch B) was over-engineering for a non-bug. Deleted Batch B spec. If a real user reports "I typed 'מרתף' and it appeared last", reopen.
4. **STEP 0 lesson reinforced** — Replit's pre-flight greps found that file line numbers had drifted ~20 lines from what my spec listed. Anchor-based greps (content-based, e.g. `units.sort` / `STATUS_ICONS[unit` / `goBack`) caught it without manual intervention. **Lesson: specs with content anchors > specs with line numbers alone.** Specs already followed this pattern but worth reinforcing.

Yesterday (2026-05-10):
1. **Discovery audit** — Plans feature (#113 + #115 + #117) audited end-to-end. Existing CRUD layer is solid (942 LOC backend + 2,904 LOC frontend, 18 endpoints, versioning, archive, restore, disciplines, thumbnails, floor/unit tagging). Gap: viewer was a 256px iframe that got CSP-blocked. ZERO defect↔plan linkage existed. See `/specs/discovery-plans-feature-audit-2026-05-10.txt`.
2. **Phase 1 plan locked** — 4 sub-batches × ~2 weeks each: P1.1 (viewer foundation), P1.2 (tap-to-pin + Task schema), P1.3 (context-aware opening + pin density overlay), P1.4 (Capacitor offline + polish + field test). Full scope per Zahi: speed + tap-to-pin + context + overlay + offline (no deferral).
3. **Q4 algorithm locked** — when defect created, plan resolution: trade-specific (electrical/plumbing/etc.) → match `floor_id + discipline` → fall back to architecture default (unit-specific architecture > floor-specific architecture > manual pick).
4. **Sample plans collected** — 13 real prod plans uploaded by Zahi (architecture, electrical, plumbing, HVAC, sprinklers, basement drainage, site, building 4 unit 35 tenant-changes set with HVAC/electrical/plumbing/construction).
5. **P1.1 shipped to prod** — react-pdf viewer foundation. Self-hosted PDF.js worker (Capacitor-ready). Lazy-loaded chunk (~150KB → ended up 391KB pdfjs 4.x heavier). z-60 modal above existing detail modal. Existing 256px iframe kept as graceful fallback.
6. **P1.1-hotfix-1 shipped** — fit-to-width default scale. A1 plans (~2000px wide) were rendering at scale 1.0, exceeding viewport. Fix: compute `min(containerWidth/pageWidth, containerHeight/pageHeight, 1.0)` on PDF load. Plus: multiplicative zoom (×1.25/×0.8) instead of additive (+0.25/-0.25) for consistent UX at any starting scale.
7. **P1.1-hotfix-2 shipped** — three layered fixes after staging smoke: (a) `Math.floor` instead of `Math.round` so fit-scale never overshoots (0.585 → 0.55, never 0.60). (b) `dir="ltr"` on scroll container — RTL inheritance broke Chrome scroll handling with flex-justify-center. (c) Force visible scrollbars via Tailwind arbitrary `[&::-webkit-scrollbar]:` modifiers — macOS hides scrollbars by default. Plus: thumbnail_url branch in ProjectPlansPage detail modal (CSP `frame-src` blocks S3 iframes; UnitPlansPage already had this pattern).
8. **P1.1-hotfix-3 shipped** — single Tailwind class `w-fit` added to inner wrapper so it grows with content. Bug: `min-w-full` set min but no width-grow → wrapper pinned at viewport width even when canvas was 2000px → canvas leaked OUT of wrapper but invisible to outer overflow-auto's scroll → "scrollbars visible but couldn't pan" pattern. With `w-fit + min-w-full`, computed width = max(content, viewport).
9. **CLAUDE.md additions** — 4 new entries under "🪤 Gotchas": RTL inheritance, macOS hidden scrollbars, Math.round in fit calculations, debugging principle (multi-layer cascade is healthy).

**Phase 1 Plans status — current state:**
- ✅ P1.1 — Viewer foundation **DONE** (shipped + 6 hotfixes — last one reverted pinch entirely, stable in prod 2026-05-11). Sole zoom UX: +/- buttons. Pan: scrollbar + native one-finger touch.
- 📋 P1.2 — Tap-to-pin + Task schema (~2 weeks) — NOT YET specced. Waits for Zahi field test of P1.1.
- 📋 P1.3 — Context-aware opening + pin density overlay (~2 weeks) — NOT YET specced.
- 📋 P1.4 — **Capacitor offline + polish + field test** (~2 weeks) — NOT YET specced. Includes pre-warm chunk + worker (#23). **Pinch REMOVED** from P1.4 scope (2026-05-11 — see below).

**Conditional batches (deferred until user request):**
- 📋 **P1.5 — Pinch-to-zoom via hybrid CSS-transform pattern.** ONLY ship if a real user reports needing pinch (after 3 days in prod with +/- buttons only, no such report yet). The hybrid approach (CSS `transform: scale()` during gesture + re-render once on release, à la Adobe Reader Mobile) is architecturally different from the re-render-per-frame approach that failed in P1.1-hotfix-4/5, so the Mode A/B rule from CLAUDE.md doesn't forbid it. But YAGNI: we don't ship complexity without a real user need. `@use-gesture/react` stays in `package.json` (tree-shaken from bundle currently) for instant re-use if needed.

**Backlog bugs status (post Batch A+C+D — 2026-05-11):**
- ✅ #28 — Unit lex sort — **CLOSED** (Batch A+C+D, live verified)
- ❌ #29 — Floor sort with negatives — **CANCELLED** (was inferred, not observed; users type "-3" directly)
- ✅ #30 — Empty unit-scope stages on 0-unit floors — **CLOSED** (Batch A+C+D, live verification pending)
- ✅ #31 — Back-nav from stage page — **CLOSED** (Batch A+C+D, live verified — uses URL.searchParams.set() for idempotency)
- ✅ #34 — iPhone progress bar / card overflow — **CLOSED** (Batch A+C+D, live verified)
- 📋 #35 — Multi-file plan upload + iOS document scan — feature, separate batch (deferred to post-P1.2)

**P1.1 iPhone issues (resolved via revert decision):**
- ❌ #32 — Pinch-to-zoom on iPhone — **CLOSED via revert** (P1.1-hotfix-6). Will re-implement in P1.4 with hybrid CSS-transform-during-gesture + re-render-on-release pattern.
- ❌ #33 — Pixelated text on browser pinch zoom — **CLOSED via revert** (same as #32).

**Next P1 bug to address (DATA ACCURACY — high priority):**
- 🐛 **NEW** — Floor summary `100% / 16/16 / תקין` ignores unit-scope stages entirely. PM sees floor as "approved" when 5 of 6 unit-scope stages have 0/5 דירות done. **Batch E spec ready** (`/specs/batch-e-floor-summary-includes-unit-stages-2026-05-11.txt`): backend `_compute_floor_badge` includes unit-scope stages aggregated by approval; frontend displays "X/Y שלבים" instead of items. ~95 LOC across 3 files. Awaiting Zahi approval to send to Replit.

**Yesterday (2026-05-09) — 5 batches shipped (auth + billing):**
505, 505-hotfix, 506, 506-hotfix, 510. Full details in earlier roadmap entry below.

**Queued next (priority order):**
1. **Batch E** — ✅ SHIPPED to prod 2026-05-11.
2. **Batch E.1** — ✅ SHIPPED to prod 2026-05-11.
3. **Batch G** — ✅ SHIPPED to prod 2026-05-11. Stop WhatsApp on defect-close (keep on reject/reopen).
4. **Batch I** — ✅ SHIPPED to prod 2026-05-11. P0 hotfix: contractor leak into management views (security).
5. **Batch I.1** — ✅ SHIPPED to prod 2026-05-11. Contractor landing page fix.
6. **Batch J Phase 1** — ✅ SHIPPED to prod 2026-05-11. Scope-aware paywall for multi-org PMs.
7. **Batch K** — ✅ SHIPPED to prod 2026-05-12. Clearer trade-mismatch error in contractor-proof.
8. **Batch F** — ✅ SHIPPED to prod 2026-05-12. Photo text labels v1.
9. **Batch F.1a/b/c + F.1b-hotfix-1** — ✅ ALL SHIPPED to prod 2026-05-12. Size picker, drag, tap-to-edit, bbox cache + min touch area. F.1 series complete.
10. **F-keyboard v2** — ✅ SHIPPED to prod 2026-05-12 (after v1 TDZ revert). Viewport-aware canvas.

**Now queued / pending:**
1. **Batch F.2** — Photo annotation discard "X" close button. Spec ready at `specs/batch-f2-photo-discard-button-2026-05-12.txt`. ~15 LOC, surgical. ALL F.1 ironed out — F.2 is the last small Photo polish before re-editable annotations.
2. **Re-editable annotations** — ARCHITECTURAL batch. Bug discovered 2026-05-12: re-opening a saved photo shows it cleanly (annotations were rasterized at save time, strokes array destroyed when modal closed). Fix: persist strokes as JSON server-side alongside JPEG. Backend schema change + frontend reload logic. Estimate: 1-2 day batch. Spec TBD.
3. **#9 P0 hotfix** — Override badges + audit block read wrong data path (stage_actors nested in run). Spec ready.
4. **#4 P1** — PM Override close (blocking real PM in production). Spec ready.
5. **GreenInvoice API migration** — ⚠️ Deadline 6/7/2026. Code analysis showed default fallback URL already uses new endpoint; main work is verifying env var configuration in AWS Elastic Beanstalk. NOT urgent yet but on the clock.
6. **Batch H — Multi-file plan upload (OTA only).** Selection of N files at once with metadata iteration. NO native dependency. ~80-150 LOC frontend. Spec TBD.
7. **P1.2 spec** (Tap-to-pin + Task schema) — P1.1 confirmed stable in prod 2026-05-11. Field test self-verified. Ready to proceed after Photo annotation polish (F.2 + re-editable) wraps.
8. **P1.3 spec** (Context-aware opening + pin density overlay) — after P1.2 ships.
9. **P1.4 spec** (Capacitor offline + polish + field test) — after P1.3 ships. **Pinch removed from scope** (deferred to conditional P1.5 batch only if a real user requests pinch).
10. **506-followup-link-invite** (backend: link flow + invite consumption)
11. **506-followup-email-fallback** (security investigation #18)
12. **510-Phase-2** (banner per-project subscription #20)
13. **#49** — Audit 4 endpoints using `_check_project_read_access` (Batch I follow-up).

**PhotoAnnotation polish backlog (lower priority, ship-when):**
- F-keyboard canvas-takes-half-screen UX issue — accepted for now, polish if negative feedback.
- Undo history per stroke — currently undo pops last array element; edit/drag are one-shot mutations not preserved in history.
- Delete label — tap → "X" button on pill for explicit single-label delete (not via undo).
- Cursor flip grab → grabbing live during drag (desktop only — ref-based doesn't trigger re-render).
- Long-press → context menu (alternative to multi-tap interactions).
- RAF throttling in applyDisplayScale (only if 50+ stroke density shows jank).

**Conditional / on-demand (only ship if user reports need OR explicit trigger):**
- **P1.5 — Pinch-to-zoom via hybrid CSS-transform pattern.** See "Phase 1 Plans status" above for the full architecture rationale. Trigger: real user reports needing pinch.
- **Stream B — Universal Links + App Links + Contact Picker + Document Scanner (Batch H.2).** See "Big features planned → 5. WhatsApp + Mobile Native Bundle → Stream B" (L705-810). Document Scanner now folded in (was task #35 second half). Trigger: paying customer asks, OR 2-week contiguous dev window opens, OR bundled with another native release.

**Conditional / on-demand (only ship if user reports need OR explicit trigger):**
- **P1.5 — Pinch-to-zoom via hybrid CSS-transform pattern.** See "Phase 1 Plans status" above for the full architecture rationale. Trigger: real user reports needing pinch.
- **Stream B — Universal Links + App Links + Contact Picker.** See "Big features planned → 5. WhatsApp + Mobile Native Bundle → Stream B" (L705-810). Trigger: paying customer asks, OR 2-week contiguous dev window opens, OR bundled with another native release.

**Plus longer-tail backlog:** WhatsApp notification bug (PM closes defect → contractor gets WA with their own proof photo), notification_router.py L105 hardcoded `'contractor'` check audit, auto-color tag values (Bug 2 from prod), defects outside units (lobby/common/פיתוח), Phase 2D-2 polish (list/grid toggle, פתח/סגור הכל), Phase 2E URL filter params, 11/12 progress widget calc bug (pre-existing #494 issue).

---

## 📋 OPEN ITEMS — MASTER DASHBOARD (2026-05-13, post Zahi confirmation)

**Comprehensive list of EVERYTHING open. Each section below links to its detailed entry deeper in this file (the ROADMAP is 1,654 lines — this dashboard is the index, NOT a substitute for browsing).**

### 🚨 Urgent — the ONE real blocker

| Item | Deadline | Action |
|---|---|---|
| **GreenInvoice API migration (tasks #54)** | **6 July 2026** (~8 weeks) | Get NEW URL from GreenInvoice notice → test on staging → update `GI_BASE_URL` in AWS EB prod → audit 2 hardcoded fallbacks if host differs |

### 🔵 In flight — at Replit / pending review

| Item | Status |
|---|---|
| **Batch H.2-Bundle — Native release** (Scanner + Universal Links + Contact Picker) | spec in progress |

### ✅ Recently shipped (context for the spike)

| Date | Batches | Notes |
|---|---|---|
| 2026-05-11 | E + E.1 + G + I + I.1 + J Phase 1 + A+C+D combined + P1.1-hotfix-6 | 8 ✅ prod |
| 2026-05-12 | K + F + F.1a + F.1b + F.1b-hotfix-1 + F.1c + F-keyboard v2 (after v1 TDZ revert) | 7 ✅ prod. F.1 series + viewport-aware canvas done. |
| 2026-05-13 | F.2 v3 + F.2-polish-1 | 2 ✅ prod. **PhotoAnnotation polish track COMPLETE.** Discard X button with onDiscard callback (9 LOCATIONS / 6 files) + custom Hebrew modal + re-edit preserves drawings (intermediate fix). |
| 2026-05-13 | H.1 — Multi-file plan upload (shared component) | ✅ prod. NEW `<BulkPlanUploadModal>` component extracted from ProjectPlansPage → reused on UnitPlansPage. ProjectPlansPage 1,543→1,320 LOC (-223). UnitPlansPage +34 LOC. Regression check passed on existing flow. |

### 🟠 Photo annotation polish (lower-priority follow-ups)

| Item | Estimate | Trigger / Notes |
|---|---|---|
| **Re-editable annotations** (persist strokes as JSON server-side alongside JPEG) | ~1-2 days, architectural | Bug Zahi found 2026-05-12: reopening saved photo loses annotations. **High priority** — real user-facing gap. |
| Custom Hebrew discard modal (replace window.confirm) | ~30 LOC, 1 file | Only if F.2 smoke shows English Cancel/OK on iOS jarring |
| F-keyboard polish — smaller canvas footprint when keyboard up | TBD | If negative feedback (canvas takes half screen) |
| Undo history per stroke (restore pre-edit/pre-drag) | ~50-80 LOC | Nice-to-have |
| Delete single label (tap → X on pill) | ~30 LOC | Future polish |
| Long-press → context menu | TBD | Future polish |
| Cursor flip grab → grabbing live (desktop) | ~10 LOC | Desktop-only nicety |
| RAF throttling in applyDisplayScale | ~15 LOC | Only if 50+ stroke density shows jank |

### 🟣 Plans feature (P1.x phase — major roadmap)

| Phase | Status | Estimate |
|---|---|---|
| **P1.2 — Tap-to-pin + Task schema** | not specced | ~2 weeks |
| **P1.3 — Context-aware opening + pin density overlay** | not specced | ~2 weeks |
| **P1.4 — Capacitor offline + polish + field test** | not specced | ~2 weeks. Includes pre-warm chunk + worker (#23). |
| P1.5 — Pinch-to-zoom hybrid CSS-transform pattern | **CONDITIONAL** | Only ship if real user reports needing pinch |
| **Batch H — Multi-file plan upload** (`מבנה > תוכניות > +` accepts ONE file; want N at once) | spec TBD | ~80-150 LOC frontend OTA-only, NO native dep |
| **iOS document scanner** (Capacitor plugin native dep) | spec TBD | ~50 LOC frontend + 1 native dep + 1 ship.sh, **needs native release window** |

### 📋 Truly pending (post Zahi 2026-05-13 confirmation)

| # | Item | Priority | Notes |
|---|---|---|---|
| #17 | 506-followup-link-invite (backend: link flow + invite consumption) | backlog | not urgent |
| #18 | 🔒 Investigate email-fallback in /auth/social | security | possible concern |
| #23 | P1.4 polish — pre-warm chunk + worker | optimization | part of P1.4 |
| #25 | Multi-page mixed-size PDF support | post-P1.2 | future |
| #35 | Multi-file plan upload (Batch H, OTA) + iOS doc scanner | spec TBD | Zahi flagged 2026-05-13 |
| #38 | Pinch-to-zoom hybrid CSS-transform (P1.4 conditional) | wait | only if user requests |
| #49 | Audit 4 endpoints using `_check_project_read_access` (Batch I follow-up) | security audit | **Zahi unsure if needed — to verify** |

### 🚀 Big features planned (deep work — see L539+ for the full details, NOT a summary)

| # | Feature | Estimate | Where in ROADMAP | Notes |
|---|---|---|---|---|
| 0 | **Handover PDF Phase 4** (QR Verification + 7-Year Retention + G4 Excel ID/property extension) | weeks | L541 | for closed-beta launch readiness |
| 1 | **Safety Phase 2** — close 75% gap to Cemento parity (the מודול בטיחות full version) | weeks | L608 | High priority strategic |
| 2 | **Vision AI Phase 1** — auto-fill defects from photo (the AI Vision feature) | weeks | L625 | Differentiator. Includes GPT-4V / Claude / fine-tuned model |
| 3 | **AI Assistant** — opt-in PM add-on (Path A pricing ₪399-499/mo). **Includes the support chatbot for end users** (same product, different audiences) | weeks | L639 | Revenue stream |
| 4 | ~~Scope-aware paywall + per-project access lock~~ | ✅ Phase 1 shipped 2026-05-11 | L704 | Phase 2 still open (#20 — see Recently resolved if Zahi confirmed) |
| 5 | **WhatsApp + Mobile Native Bundle** — 3 streams (Stream A done; Stream B covers Universal Links + App Links + Contact Picker + Doc Scanner — **this is the "WhatsApp link checks if app installed" Zahi asked about**; Stream C = Bell wiring + PM digest) | weeks | L774 | Engagement |
| 6 | **Manager assignment** — tag managers (not just contractors) on defects/tasks | days | L892 | **Safety Phase 2 prerequisite** |
| 7 | **Internal group chat** — project-scoped messaging for managers/team (Tier 1-3 progressive) | weeks-months | L1102 | Engagement |
| 8 | **Defects outside units** — lobby/common areas/פיתוח (tasks #2) | days | L1043 | Structural gap |
| 9 | ~~Execution Control Checklist mode~~ | ✅ SHIPPED as מטריצת ביצוע (22 batches) | L924 (stale entry) | Renamed during build. Should remove from "planned" |
| 10 | ~~PM Override close~~ | ✅ Shipped 2026-05-04 | L988 (stale entry) | |
| — | **Offline mode** — CRITICAL for field use | weeks | L1140 | Core flow gap |
| — | **Feature backlog Batch A** — Duplicate detection + Contractor perf dashboard + Auto-priority rules + Simple timeline v1 | 6-8 weeks total | L1178 | From 2026-04-22 brainstorm |
| — | **15 other ideas** from brainstorm (ship-later / defer-or-kill) | various | L1202 | Browse the full list |
| — | **Pentest 2026-04-22 + Batch S5 + Batch S6** (security/refactor) | various | L1307 / L1370 / L1426 | Doc-level concerns |
| — | **Multi-Market Architecture Standards** | strategic | L1498 | International expansion prep |
| — | **Refactor backlog (21 items)** | living doc | `docs/refactor-backlog.md` | #10 (force_close regression tests) **BLOCKS LAUNCH** |

### 🆕 Items Zahi flagged 2026-05-13 — RESOLUTION

| Item | Resolution |
|---|---|
| Support chatbot | **Integrated into #3 AI Assistant** (same feature, different audiences — PM-facing AND end-user-facing). NO separate item. |
| WhatsApp link app-detect (check if app installed → native, else browser) | **= Stream B in #5 WhatsApp Native Bundle** (Universal Links + App Links). Same feature. Already in roadmap. |

### 🔒 Security / Quality / Architecture

| Item | Status | Severity |
|---|---|---|
| **Pentest 2026-04-22 report** (Shannon) | doc only | review needed |
| **Batch S5** — code-level audit findings | partial scope | various |
| **Batch S6** — retire legacy `companies` collection | scoped, not started | medium |
| **Pre-public-launch gate** items (CRITICAL — added 2026-04-25) | partial | LAUNCH-BLOCKING |
| **Refactor backlog (21 items)** | living doc — see `docs/refactor-backlog.md` | various |
| #10 (refactor) **force_close regression tests** | open | **BLOCKS LAUNCH** |
| **Multi-Market Architecture Standards** | doc | strategic |

### 💡 Feature backlog (from brainstorm 2026-04-22 — 15 ideas evaluated)

| Tier | Items |
|---|---|
| 🎯 **Ship next** (Batch A, 6-8 weeks) | Duplicate detection, Contractor perf dashboard, Auto-priority rules, Simple timeline v1 |
| 🟡 **Ship later** (Q3-Q4 2026) | 8 items — see L1202+ |
| 🔴 **Defer or kill** | various — see L1223+ |

### ⚫ Longer-tail backlog (small items)

- WhatsApp notification bug (PM closes defect → contractor gets WA with own proof photo)
- `notification_router.py:L105` hardcoded `'contractor'` check audit
- Auto-color tag values (Bug 2 from prod)
- Phase 2D-2 polish (list/grid toggle, פתח/סגור הכל)
- Phase 2E URL filter params
- 11/12 progress widget calc bug (pre-existing #494)
- `deploy.sh` branch lock friction (errors when current is main)

### ⚠️ External deadlines

| Deadline | Item |
|---|---|
| **6/7/2026** | GreenInvoice API migration |

---

### ✅ Recently resolved — task list cleanup (confirmed 2026-05-13 with Zahi)

These items appear in the in-memory task list as "pending" but are actually shipped. Task IDs preserved for traceability.

| # | Item | Shipped | Evidence |
|---|---|---|---|
| #1 | 469 followup-2 (TaskDetailPage pill + sidebar filter) | ✅ | Zahi confirmed 2026-05-13 |
| #3 | Execution Control: Checklist mode | ✅ → renamed **מטריצת ביצוע** | 22 batches shipped (Phase 1, 2a/b/c, 2d-1, polish, excel export, qc sync) |
| #4 | PM Override close (P1) | ✅ commit `a9fab82` | 2026-05-04 |
| #5 | Replit #476 — Execution control floor view ALL unit-scope stages | ✅ commit `f63c4c9` | 2026-05-04 |
| #6 | UnitQCSelectionPage P0 hotfix (stages vs units shape) | ✅ commit `5887e08` | 2026-05-04 |
| #7 | #478 followup — Override audit block visible on StageDetailPage | ✅ | Zahi confirmed 2026-05-13 |
| #8 | QC back-navigation preserves ?from=qc through Floor round-trip | ✅ | Zahi confirmed 2026-05-13 |
| #9 | Override badges + audit block data path (stage_actors nested) | ✅ commit `98996b7` | 2026-05-04 |
| #20 | Banner Phase 2 — per-project org subscription | ✅ | Zahi confirmed 2026-05-13 |
| #24 | P1.1-hotfix-1: fit-to-width + defensive guard | ✅ | P1.1 series 2026-05-10 |
| #26 | P1.1-hotfix-2: Tailwind scrollbars + 3 fixes | ✅ | P1.1 series 2026-05-10 |
| #27 | P1.1-hotfix-3: w-fit on inner wrapper | ✅ | P1.1 series 2026-05-10 |
| #46 (partial) | Batch F (text labels) + Batch G (WA close) | ✅ | F shipped 2026-05-12; G shipped 2026-05-11. Only **H (multi-file plans)** still pending. |
| #53 | Batch F — photo text labels | ✅ commit `c08e314` | 2026-05-12 |
| #55 | Batch F.1 — size + drag + edit | ✅ | shipped as F.1a/b/c series 2026-05-12 |

**Items still under question:**
- **#49** — Audit 4 endpoints using `_check_project_read_access` (Batch I follow-up). Zahi unsure if needed. To verify if the security gap is real.

---

**How to use this dashboard:**
- 🚨 Urgent → ship next
- 🔵 In flight → wait for review.txt
- 🟠 Photo annotation polish → ship after F.2 lands (ordered by user-impact)
- 🟣 Plans feature → after Photo polish wraps (~3-4 weeks of work)
- 🚀 Big features → **see the full sections at L539+ for actual scoping. The dashboard above lists titles only — full details are in the body of this file.**
- 💡 Feature backlog → revisit when current sprint clears

---

**Don't forget to browse:**
- L539+ "🚀 Big features planned" — 11 feature sections with full scope, code anchors, and effort estimates.
- L1138+ "🆕 New items (added 2026-04-24)" — Offline mode + code quality.
- L1174+ "📚 Feature backlog (15 ideas)" — ship/defer/kill decisions from brainstorm.
- L1303+ "📋 Reports" — Pentest, Markets expansion, Audit findings.
- L1618+ "Priority ordering recommendation" — sequencing logic.

This dashboard is the INDEX. The body has the real content.

---

## 🔗 Quick navigation — all key documents

Click to open. Everything referenced below lives in `/Users/zhysmy/brikops-new/`.

### 📐 Strategy & architecture
| Document | Purpose |
|---|---|
| **Handover PDF v3.x** | **✅ Shipped 2026-04-30 — v3.8 + v461 + v462 stable in production. See [Shipped → Handover PDF v3.x](#handover-pdf-v3x-shipped-2026-04-30) below for full details. Outstanding: QR Verification (Phase 4a, when triggered) + 7-Year Retention Hardening (Phase 4b, deferred) + G4 Excel import extension to ID number + property fields (Phase 4c, ~1-2 days when prioritized) — all under Big features planned.** |
| **[Architecture docs index (ADRs + conventions + anti-patterns)](computer:///Users/zhysmy/brikops-new/docs/architecture/README.md)** | **✅ Shipped 2026-04-29 (Task #450, Phase 1A) — Entry point for any contributor. Top files inventory (14 files >1500 lines), conventions (IDs, timestamps, status, RTL, auth, pagination), 11 anti-patterns with reasons, helper-finder table, reading order for new contributors.** |
| [ADR-001 ProjectControlPage.js](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-001-project-control-page.md) | The 4115-line project home. 7 work-modes, why state is lifted, natural seams for extraction. |
| [ADR-002 qc_router.py](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-002-qc-router.md) | 2936 lines — largest backend file. QC stage workflow + approver notifications. |
| [ADR-003 handover_router.py](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-003-handover-router.md) | 2652 lines. Protocol lifecycle, BATCH 5C TERMINAL_TASK dedupe lesson. |
| [ADR-004 billing_router.py](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-004-billing-router.md) | 2068 lines. PayPlus webhook constraints, GI-failure-doesn't-block pattern, check_org_billing_role. |
| [ADR-005 tasks_router.py](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-005-tasks-router.md) | Task lifecycle state machine. STATUS_BUCKET_EXPANSION single source of truth. Drift-guard test from 5F. |
| [ADR-006 Status system (cross-cutting)](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-006-status-system.md) | 3 namespaces (task/handover/QC), forbidden patterns, lessons from 5C/5F/5G drift. |
| [ADR-007 i18n (cross-cutting)](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-007-i18n.md) | he.json source of truth, why en/ar/zh are deliberately frozen pre-launch. |
| [ADR-008 Navigation (cross-cutting)](computer:///Users/zhysmy/brikops-new/docs/architecture/adr-008-navigation.md) | getProjectBackPath helper, ?from= URL-param convention from 5H, broken /projects/:id pattern fixed in 5I. |
| **[Refactor backlog (21 items)](computer:///Users/zhysmy/brikops-new/docs/refactor-backlog.md)** | **Living document of known opportunities. Each item: file/severity/evidence/proposed fix/estimate/fold-into-batch trigger. #10 (force_close regression tests) BLOCKS LAUNCH.** |
| [Codebase Documentation & Refactor Plan](computer:///Users/zhysmy/brikops-new/docs/strategy/codebase-refactor-plan.md) | 4-phase plan (Docs → Tests → Refactor → Hire). Phase 1A ✅ done above. Working principle: opportunistic Boy Scout cleanup inside feature batches, never standalone "refactor sprints." |
| [Multi-market architecture standards](computer:///Users/zhysmy/brikops-new/docs/strategy/multi-market-architecture-standards.md) | Extension pattern, 3 golden rules, timeline for Q1 2027 UAE expansion |
| [SAFETY-STATUS.md](computer:///Users/zhysmy/brikops-new/SAFETY-STATUS.md) | Canonical status of Safety module (Phase 1 shipped, 25% Cemento parity) |
| [CLOSED-BETA-FIXES.md](computer:///Users/zhysmy/brikops-new/CLOSED-BETA-FIXES.md) | Master tracker of all closed-beta user feedback + fix batches |
| [CLAUDE.md](computer:///Users/zhysmy/brikops-new/CLAUDE.md) | Project instructions — deploy rules, `./ship.sh` gates, native vs OTA |

### 🔒 Security
| Document | Purpose |
|---|---|
| **[Pentest Regression Checklist](computer:///Users/zhysmy/brikops-new/security/pentest-regression-checklist.md)** | **Single source of truth — every test MUST pass after each backend deploy.** Maintained by `brikops-pen-tester` skill. |
| [Pentest report — 2026-04-22](computer:///Users/zhysmy/brikops-new/security/pentest-report-2026-04-22.md) | Original manual pentest (where S1, S2, S5 came from) |
| [Pentest interim report](computer:///Users/zhysmy/brikops-new/security/pentest-report-2026-04-22-interim.md) | Earlier interim snapshot of the same pentest run |
| Shannon scan reports — 2026-04-26 | 🔐 Stored in `secrets/shannon-reports-2026-04-26/` (gitignored — contains exploit details). Shannon found 2 CRIT + 4 HIGH + 3 MED + 5 INFRA. → S6, S7, S8 |
| **Shannon-grade Security Standard** in [`CLAUDE.md`](computer:///Users/zhysmy/brikops-new/CLAUDE.md) | Project-wide commitment: every release passes the same rigor as Shannon AI pentester. Includes 9 hard "never ship" code review red flags. |

### 🚀 Future features (concepts, not yet spec'd)
| Document | Purpose |
|---|---|
| [AI Assistant concept](computer:///Users/zhysmy/brikops-new/future-features/ai-assistant-concept.md) | Original AI Assistant concept doc (improved version summarized in this roadmap) |
| [Safety + Work Diary concept](computer:///Users/zhysmy/brikops-new/future-features/safety-and-worklog-concept.md) | Full Cemento-parity safety module concept (Phase 2+) |
| [Safety feature handoff](computer:///Users/zhysmy/brikops-new/future-features/HANDOFF-safety-feature-2026-04-22.md) | Handoff notes when Phase 1 shipped |
| [Cemento competitor analysis](computer:///Users/zhysmy/brikops-new/future-features/cemento-research/CEMENTO_ANALYSIS.md) | What Cemento does vs. what we have |
| [Safety Phase 1 mockup v3 (final)](computer:///Users/zhysmy/brikops-new/future-features/safety-phase-1-mockup-v3.html) | Interactive HTML mockup used to design Phase 1 |

### 📝 Recent specs (what was shipped)
| Spec | Status |
|---|---|
| **🆕 May 9 cluster — Unified auth + ToS consent + SSO on invite + billing banner project-aware (5 batches all to prod 2026-05-09)** | ✅ **All five batches (505, 505-hotfix, 506, 506-hotfix, 510) shipped to prod 2026-05-09**. **Three-part work in service of two product needs:** (1) commercial — open Google/Apple SSO to ALL roles (was PM-only) so contractors invited via WhatsApp can register one-click instead of password+OTP; (2) legal — capture explicit ToS+Privacy consent per Israeli Anti-Spam Law (חוק התקשורת תיקון 40) in MongoDB (`terms_accepted_at` + `consent_ip`) for audit defensibility. **Architectural lock added:** BrikOps will NEVER send marketing emails — only operational/transactional. Israeli Spam Law's explicit-consent regime applies to marketing only; transactional notifications (project assignments, defect reminders) are exempt. **Batch 505 — Unified auth + ToS consent** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-unified-auth-and-tos-consent-2026-05-08.txt)): removed 4 PM-only gates (`התחברות חברתית זמינה למנהלי פרויקט בלבד`) at onboarding_router.py L1798, L1851, L1935, L2029; extended `SocialAuthRequest` schema with `invite_token: Optional[str]` + plumbed through `/auth/social` (L1830 invite validation) + `/auth/social/verify-otp` register branch (L2122-2169 invite consume + role inheritance + project membership upsert). **CRITICAL security gate** at L2135: `if session_invite['target_phone'] != phone: raise HTTPException(400, 'הטלפון לא תואם להזמנה')` — prevents privilege escalation where contractor registered as PM by forwarding invite to themselves. POST `/auth/register` and `/onboarding/accept-invite` and `/auth/social/verify-otp` all enforce `terms_accepted=True` (Pydantic schemas extended). server.py L1227 `backfill_terms_accepted_at()` startup job for existing users (idempotent MongoDB pipeline-style update). 4 register/link forms got ToS checkboxes: renderInviteAccept (L869), renderPhoneStep socialFlow=otp (L1193), renderDetails (L1579), LoginPage SSO link (id="login-link-terms"). Privacy policy disclosed IP storage in advance ("פעולות שביצעתם באפליקציה, תאריכים, כתובות IP, סוג דפדפן ומכשיר") — verified on prod via `curl -L /legal/privacy.html`. 11 new tests in `test_unified_auth_consent.py` covering T1-T11 (T9 = phone mismatch security, T11 = legacy invite without expires_at). **Batch 505-hotfix — invite-login-needed ToS checkbox** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-505-hotfix-invite-login-needed-tos-2026-05-09.txt)): discovered during 505 staging smoke that `renderInviteLoginNeeded` (OnboardingPage.js L902-994 — the form rendered to NEW-PHONE invite recipients after OTP verify) was MISSED in initial 505. Form called `handleAcceptInvite` which enforces `termsAccepted` at L634, but no UI to flip the checkbox → every new contractor invite hit a 400 dead-end. Fix: ~17 LOC adding `id="onb-invite-newuser-terms"` checkbox + `disabled={loading || !termsAccepted}` on submit Button. No backend changes (gate already correct). E2E verified on prod 2026-05-09 with phone +972506723111 (Zahi's real test phone): invite created → SMS arrived → OTP verified → renderInviteLoginNeeded showed checkbox → button disabled when unchecked → button enabled after check → submit → joined project as electrical contractor scoped to company-id (visible only to "החברה שלי" defects). **Process lesson added to CLAUDE.md** (new iron rule "🚪 Backend gate חדש = exhaustive frontend audit"): pattern of "missed form/endpoint" recurred 4× in one month (#503 reject_stage hook, #503-followup-2 submit_stage hook, P0 contractor compound index, #505 renderInviteLoginNeeded). The fix: any backend gate addition requires 3-layer frontend grep (URL string + service method name + direct fetch/axios) + classification table BEFORE deploy. **Batch 506 — Google+Apple SSO buttons on invite landing** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-506-sso-on-invite-landing-2026-05-09.txt)): ✅ **Shipped 2026-05-09**. Added Google + Apple buttons to `renderInvitePhoneStep` (invite landing screen, L733-774) so contractors invited via WhatsApp get one-click SSO instead of password+OTP. ~50 LOC frontend, single backend-untouched change. The "linchpin" `setStep('phone')` in `handleSocialAuthResult` registration_required was a no-op (didn't actually transition rendering — see 506-hotfix below). **Batch 506-hotfix — renderCurrentStep socialFlow routing** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-506-hotfix-renderCurrentStep-socialFlow-2026-05-09.txt)): ✅ **Shipped 2026-05-09**. Discovered during prod E2E that 506's Google/Apple buttons fired OAuth correctly but UI got stuck on the original invite landing screen with no OTP-input field. Root cause: `renderCurrentStep` returned `renderInvitePhoneStep` for invite flow regardless of `socialFlow` state. The OTP+phone UIs for `socialFlow='link'/'register'/'otp'` live in `renderPhoneStep` (L1043+), not `renderInvitePhoneStep`. Fix: 1-line early return `if (socialFlow) return renderPhoneStep();` as first statement in `renderCurrentStep` — purely additive (socialFlow=null by default). Verified on prod: clicking Google on invite landing now correctly transitions to OTP-input UI (the `socialFlow='link'` branch when Google account already linked). **Verified end-to-end testing deferred**: full Test C (Google + invite + phone-match → 400) and Test B (Google + invite + match → joined) require a Google account never linked to any BrikOps user. Both Google accounts Zahi tried (zahithrone@gmail.com, zahi.amer@gmail.com) auto-resolved to existing users — first via link_required, second via authenticated (which surfaces a separate concern: possible email-fallback in /auth/social, tracked as task #18 to investigate). Decision: ship as-is, monitor, defer full E2E test until 506-followup-link-invite ships. **Cumulative day:** 6 backend files + 4 frontend files + 1 new test file (T1-T11), ~395 LOC, +4 demo accounts on prod (`demo-pm@brikops.com`/`demo-team@`/`demo-contractor@`/`demo-viewer@` all with password `BrikOpsDemo2026!` — saved to CLAUDE.md). Architectural lock + 1 new iron rule (backend gate frontend audit) added to CLAUDE.md. Privacy policy compliance gate (STEP 0.6b from 505) was already met before deploy — disclosed IP storage in /legal/privacy.html. **Batch 510 — Trial banner project-aware (Phase 1)** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-billing-banner-project-aware-2026-05-09.txt)): ✅ **Shipped 2026-05-09**. Bug discovered during 506 prod test: contractors invited to projects of OTHER orgs saw misleading "התשלום פג תוקף" banner because TrialBanner.js read the user's OWN org subscription via `/billing/me`, not the current project's owning org. User "צחי שמי" (Zahi's test account) was PM in expired Org 808 and contractor in active Org 810 — banner appeared on both. Fix: ~30 LOC frontend-only — extract projectId from URL via UUID regex, fetch `/api/projects/{id}` to read `my_role` (backend already returns this for contractors per `projects_router.py:389`), suppress banner when `my_role` is contractor or viewer. Hooks declared before early-returns per React rules. Cancellation flag prevents stale state writes on fast nav. Verified on prod with Zahi's accounts: Project 810 (contractor) → no banner ✅, Project 808 (PM, expired) → banner shows ✅. **Phase 2 deferred** (#20): the architectural fix is to drive banner from CURRENT PROJECT's org subscription, not user's own. Handles all edge cases (PM cross-org, viewer cross-org). Phase 1 covers ~90% of false-positive confusion (the contractor case); Phase 2 = the real fix. **Cumulative day:** 7 backend files + 5 frontend files + 1 new test file (T1-T11), ~425 LOC, +4 demo accounts on prod, 2 architectural locks (no marketing emails + auth-area soak rule), 2 new iron rules in CLAUDE.md (backend gate frontend audit + auth-area chain soak). **Deferred follow-ups (next session):** (1) 506-followup-link-invite: backend `/auth/social/verify-otp` link branch should consume invite_token (today: link auth succeeds but invited project isn't joined); (2) 506-followup-email-fallback: investigate possible email-matching fallback in `/auth/social` (account-takeover security concern from Zahi's zahi.amer@gmail.com auto-login surprise); (3) 510-Phase-2: banner driven by current project's org subscription rather than user's. **Process lesson:** 5 chained UI-impacting deploys in one day (505 → 505-hotfix → 506 → 506-hotfix → 510) showed fatigue accumulates fast. Auth-area cluster (4 of 5) overrode the 24h soak rule twice, and the second override surfaced a real bug in 506 that staging smoke would have caught (had staging Google Client ID been configured). Lesson added to CLAUDE.md: when chaining 3+ specs in one auth-area, force a clean staging soak before each prod deploy. |
| **🆕 May 8 cluster — Contractor access + UX overhaul (3 batches, all to prod same day)** | ✅ **All shipped to prod 2026-05-08**. Three production-blocking bugs reported by Zahi after AWS/EB log analysis on plot 810 (WUyoughong contractor) — fixed in 3 staged batches with smoke between each. **Batch 1 — P0 contractor visibility + company display + proof flow** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-contractor-visibility-fix-2026-05-08.txt)): three intertwined bugs. (1) Company name shows "לא שויך" to contractors — `getCompanyName()` only resolved from `projectCompanies` array which was loaded only inside MGMT branch (TaskDetailPage L240); contractors got empty array. Fix: backend GET /tasks/{id} now returns `task.company_name` directly via new `_resolve_task_company_name` helper. (2) Contractor sees ALL defects in projects — `tasks_router.py L287` strict `user['role']=='contractor'` check; contractors with user.role='user' AND membership.role='contractor' bypassed the filter on cross-project list. Fix: widen `is_contractor` to consider per-project memberships; build per-project `(project_id+company_id)` $or for cross-project requests; mixed-role mgmt fallback (a user who is contractor in A but PM in B still sees ALL B tasks). (3) Contractor in company can't close company-assigned defect — TaskDetailPage L786 + tasks_router.py L864 both required strict `isAssignee`. Fix: both widen to `(isAssignee OR isCompanyMember)`. assignee_id NEVER changes; WhatsApp/reminders still go to original assignee only. **Plus** UI badges in ContractorDashboard ("👤 משויך אלי" / "👥 החברה שלי" per task), new compound index `(user_id, role)` on project_memberships (was missing — 3 new queries needed it), 10 backend tests including T10 mixed-role coverage. **Batch 2 — P1 contractor nav fix + company-only dropdown** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-contractor-nav-and-company-dropdown-2026-05-08.txt)): immediately after Batch 1. (A) MyProjectsPage click on contractor project no-ops — `navigateToProject()` sent contractors to `/projects` (where they already are). For PM-globally-but-contractor-here users, ProjectsHome inspects `user.role='project_manager'` → returns same MyProjectsPage. Fix: pass `?src=contractor` extends existing `?src=wa` escape hatch from Batch 6C. (B) PM couldn't assign defect to "company-only" — `contactFallbacks` filter `!projectContractors.some(...)` excluded companies with any registered contractor. Fix: new `companyOnlyOptions` list emits "🏢 X — כל החברה" for every project_company. **Known limitation documented**: both contactFallbacks + companyOnlyOptions emit `__contact__${pc.id}`; on reload the label always shows "🏢 X — כל החברה" (functionally identical, both route to "any company member" P0 flow). **Batch 3 — P1 management panel split (company + contractor)** ([spec](computer:///Users/zhysmy/brikops-new/specs/batch-task-detail-management-panel-redesign-2026-05-08.txt)): Zahi feedback after Batch 2: "שהכל יהיה ברור וחלק" — single mixed dropdown was confusing. Mirrored NewDefectModal.js L888-922 dual-dropdown pattern. Split mgmt panel "קבלן" cell into TWO stacked cells: "חברה" (lists project_companies with 🏢 prefix) + "קבלן ספציפי" (filtered to selected company's contractors, "בחר חברה תחילה" placeholder when no company picked). Smart toast on company change clears assignee with explicit message ("חברה שויכה. הקבלן הוסר כי לא שייך לחברה החדשה."). Race protection — both dropdowns disabled during ANY save (`savingField !== null`). Backend: `assignee_name` resolver fallback chain extended to `name → phone → email` (fixes "קבלן משויך" generic display for legacy phone-only contractors). companyOnlyOptions + contactFallbacks REMOVED (superseded by separate חברה dropdown). **Cumulative day**: 5 backend files + 3 frontend files + 1 new test file (T1-T10) + 1 new compound index, ~270 LOC across 3 batches. Process win: STEP 0 STOP-GATE caught 4 hardcoded contractor checks for follow-up batch (only L105 in notification_router actually buggy; L432 in stats_router and L761 in tasks_router already correctly widened). All 3 batches deployed same-day per Zahi's "ship discipline" — P0 first (full smoke), P1 nav (skip staging deep test, code-only), P1 mgmt panel (staging quick smoke + prod). |
| **🆕 May 5 cluster — Execution Matrix Phase 2B + 2C + 2C polish + 2D-1 + UX labels + tooltip-note (7 batches)** | ✅ **All shipped to prod 2026-05-05**. Closes the CORE of the matrix-as-Excel replacement. **Phase 2B (#494)** — cell editing via popover/sheet with status select, free-text note, audit history. **Phase 2C (#495)** — stage management dialog: add custom columns (tag or status), hide/reorder template stages. Negative `order = i - N` trick keeps custom stages rendering before template stages without backend ordering changes. **Mobile row tap (#496)** — whole stage row in MatrixListView tappable (not just status icon). **Phase 2C polish (#497)** — CRITICAL data-loss fix: hidden template stages couldn't be unhidden because StageManagementDialog only saw filtered `stages` (excluded hidden ones). Backend now exposes `template_stages` (all base stages including hidden) so dialog can render hide/show toggles for all. Cells of hidden stages preserved in DB; round-trip integrity test added. **UX labels (#498)** — radio in custom-column form renamed: "תגית (טקסט חופשי)" → "📝 מידע כללי (טקסט חופשי)" and "סטטוס (6 ערכים — כמו עמודות בקרת ביצוע)" → "🔨 שלב בקרת ביצוע" + section subtitle gets concrete examples (מכור, מס׳ חדרים / טיח, גז). **Phase 2D-1 (#500)** — THE CORE per Zahi: "מערכת הסינון זה הלב והליבה של כל המערכת... טבלת אקסל משופרת". Excel-style drawer with dynamic per-column sections, AND between sections + OR within values, FAB with active-count badge, saved views (load/save/delete-pill UI ×) — all client-side filter; backend MatrixSavedViewFilters schema already designed in #483 supports the exact shape. ~958 LOC frontend, 7 logic tests including sentinel `'__empty__'` boundary + reset behavior, ZERO backend changes. **Cumulative:** ~1,400 LOC frontend across the 6 batches, +5 backend LOC (#497 only), 23+ new/passing tests, validated through 3-reviewer code review process (Cowork inline + Replit task plan + secondary code-review chat — all 3 surfaced same 3 gaps in original spec which were merged into ADDENDUM #1). |
| **🆕 May 6-7 cluster — QC↔Matrix sync feature complete (4 batches) + #601 template auto-upgrade** | ✅ **All shipped to prod 2026-05-07/08**. Includes #601 (auto-upgrade existing QC runs to current template version) — fixes long-standing template-immutability bug exposed by QC↔Matrix sync. Helper `_resolve_run_template_with_upgrade` in qc_router.py at 2 entry points (get_or_create_floor_run + get_or_create_unit_run); +76/-2 LOC + 3 unit tests (idempotent / upgrade / e2e backfill). When user opens a QC run, helper checks if pinned `template_version_id` matches current; if stale, upgrades run doc + emits audit + returns current template; existing `_backfill_missing_items` adds items for stages admin added after the run was created. Deployed prod 2026-05-07 — verified on plot 810 building 8 (Zahi's reproducer). #503 + 3 followups + #601 all in prod. ROADMAP Section 9 Bidirectional Sync vision delivered as one-way QC→Matrix (per Zahi 2026-05-06 architectural lock — reverse direction will never be implemented; QC photo-evidence requirements). PMs no longer maintain duplicate state in QC + matrix — any QC stage state change auto-syncs to matrix cells. **#503 core** — pure helper `qc_to_matrix_sync.py` with feature flag (default OFF), BackgroundTasks pattern (sync runs after HTTP response — zero QC perf impact), try/except so sync failures never block QC writes. 11 tests including T9 critical sync-failure-protection. **#503-followup-1** — staging smoke caught that 7 of 8 base QC stages defaulted to `scope:"floor"` (only `stage_tiling` was unit-scope) → 12% functional. Removed the over-defensive D5 skip; existing drift-C aggregation + per-item unit_id extraction handle floor-scope correctly. **#503-followup-2** — staging smoke caught 3 more issues: (a) reject-stage had no hook (missed in original #503), (b) floor-scope sync silently failed because items had no unit_id and run had no unit_id → for-loop iterated 0 times, (c) Zahi requested mapping change from item-level to stage-level. Added `_resolve_unit_ids_for_sync` helper with fallback chain (unit-scope → items.unit_id → db.units.find by floor_id), reject_stage hook, new `pending_review` matrix status (orange, sync-only). **#503-followup-3** — staging smoke caught 2 more bugs (item-level activity not propagating in floor-scope; submit-for-review unhooked) + STOP-GATE 0.6 audit found 2 MORE missed hooks (`reject_qc_item` per-item rejection + `reopen_stage` manual reopen — both set `stage_status="reopened"`). Final state: **7/7 user-facing stage_status mutation endpoints hooked** (V6 audit table proves it). New `ready_for_work` MANUAL-only matrix status (cyan, PackageCheck icon, MatrixCellUpdate Literal allows it; pending_review intentionally NOT in Literal — sync-only). Bug B fix: `items_have_unit_id = any(...)` flag in 4 hooks — when items lack unit_id (floor-shared template), pass items_all to each unit's sync rather than empty per-unit filter. Mapping is now `outcome-driven` per Zahi: "מבחינתי מרגע שיש סעיף אחד...זה בעבודה. רק אם...הסעיף הגדול אושר על ידי מי שיכול לאשר, מתעדכן למאושר. אותו דבר לגבי לא תקין, רק אחרי שבסעיף הראשי הגדול הוא לא תקין הוא יראה את זה." **Cumulative:** ~600 LOC backend + ~50 LOC frontend across 4 batches, 25 tests passing (was 11, +14 new). 3 phased rollout invocations (flag OFF default, staging smoke, prod deploy with flag flip). 8 statuses now in matrix: ready_for_work / in_progress / pending_review / completed / not_done / partial / not_relevant / no_findings. Process win: STEP 0 STOP-GATEs caught 2 missed hooks before deploy — critical to followup discipline. |
| **[#502-followup — Excel export polish (button label + auto-filter + sort)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-excel-export-followup.txt)** | ✅ **Shipped 2026-05-06** — Three fixes from Zahi staging smoke: (1) Download button now shows "[⬇ ייצוא Excel]" pill with text label (was icon-only — "לא מספיק מזמין ויפה"). (2) Excel auto-filter dropdown arrows on every header column via `ws.auto_filter.ref = ws.dimensions` (1 LOC). (3) Rows sorted by building (numeric) → floor → unit (numeric) — `_unit_sort_key` hoisted to module level (was nested inside `get_matrix`, unreachable from `/export.xlsx` endpoint). Hoist mirrors #502's `_summarize_cell` hoist pattern. ~25 LOC across 3 files. |
| **[#502 — Execution Matrix: Excel (.xlsx) export](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-excel-export.txt)** | ✅ **Shipped to prod 2026-05-06** — Per Zahi: "יש לנו עוד לעבוד על הוצאת excel או pdf להורדה". NEW backend module `execution_matrix_export.py` with pure `build_matrix_xlsx` function (RTL view, status colors per ramp, notes as Excel comments with author = `last_actor_name`, frozen panes 3 cols + header, auto-width). Endpoint POST `/api/execution-matrix/{id}/export.xlsx` accepts explicit `unit_ids` + `stage_ids` from frontend so the export reflects the active filter state exactly. Frontend Download icon in header → `matrixService.exportXlsx` → `downloadBlob()` helper (Capacitor-aware: native filesystem + Share sheet, web blob URL). Filename in Hebrew via RFC 5987 encoding (filename* UTF-8). 4 adjustments adopted from secondary code review: filename sanitize (`/\\:*?"<>\|` → `_`), 2000-unit cap with Hebrew error (instead of silent truncate), note whitespace strip, comment author from cell. **Note: Zahi accidentally deployed direct to prod from Replit Shell without staging** — but Replit's 22 pytest pass + yarn build clean meant zero impact. Process lesson: deploy.sh's `git add -A` sweeps Replit Agent's uncommitted working tree into the current branch's commit. ~340 LOC: 195 backend + 55 frontend + 110 tests. |
| **[#500-followup — Building numeric sort + apartment exact-match in filter](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2d-1-followup.txt)** | 📋 **Spec ready 2026-05-05, queued after #502** — Two issues Zahi found in mobile prod test of #500 (4-building × 203-unit real-scale project). (1) Building filter list rendered "8, 10, 9, 11" lex instead of "8, 9, 10, 11" numeric — drawer wasn't applying the `parseInt + NaN fallback` sort that backend uses in `_unit_sort_key` since #489. Frontend useMemo with mirrored logic. (2) Apartment search was substring (`includes`) so typing "2" matched 2 / 12 / 20 / 21 / 22 / 23. PMs expect exact match: "2" → only דירה 2; "22" → only דירה 22. Free-text substring search remains in the global חיפוש חופשי field at top of drawer. ~15 LOC across 3 files (MatrixFilterDrawer + useMatrixFilters + new T8 test). |
| **[#501 — MatrixCell tooltip: include cell.note on hover](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-cell-tooltip-note.txt)** | ✅ **Shipped to prod 2026-05-05** — Quick followup to #500 staging smoke. Native `title` attribute on status + tag cells now shows status + actor + note (in quotes on a new line) when present. Empty cells unchanged ("לא סומן"). PMs scanning the matrix see notes on hover without clicking each cell to open CellEditDialog. ~5 LOC, MatrixCell.js only, no backend, no tests. |
| **[#500 — Phase 2D-1: Excel-style filter drawer + saved views (THE CORE)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2d-1-filters-saved-views.txt)** | ✅ **Shipped to prod 2026-05-05** — Per Zahi: "מערכת הסינון זה הלב והליבה של כל המערכת... טבלת אקסל משופרת". 6 NEW frontend files (~958 LOC), 2 EDIT files. Drawer with dynamic per-column sections (📍 location / 📝 tag / 🔨 status), AND between sections + OR within values, FAB with active-count badge, live filtering (no Apply button — memoized 30 units × 11 stages), sections collapsed by default per Zahi explicit request ("שלא יהיה עמוס"), saved views with × delete-pill (added per ADDENDUM #1 — both code reviewers flagged that without delete UI users would accumulate clutter). Sentinel `'__empty__'` for "(ריק)" filter; converted to `""` at backend boundary. 7 logic tests including T6 sentinel round-trip + T7 reset. Backend ZERO changes — `MatrixSavedViewFilters` schema from #483 already had exact shape. Validated via 3-reviewer process (Cowork inline + Replit task plan + secondary code-review chat). Spec evolution: original 719 lines → 774 after ADDENDUM #1 merge. Smoke validated 2026-05-05: dynamic filter section detection works for newly-added columns (no code change needed), saved view round-trip preserves filters exactly, no regression on cell edit (#494) or stage management (#495+#497+#498). FAB conflict pre-flight grep (STEP 0.6) cleared. Capacitor compliance verified. Out of scope: Phase 2D-2 polish (manual list/grid toggle, פתח/סגור הכל, "חדש" pill removal), Phase 2E URL filter params. |
| **[#498 — Matrix dialog radio labels (UX clarity)](computer:///Users/zhysmy/brikops-new/specs/)** | ✅ **Shipped 2026-05-05** — Post-#497 prod feedback (Zahi mobile test): "איך מוסיף עמודות בקרת ביצוע?" — two places said "בקרת ביצוע" (section 2 header + section 1 status radio caption) so users didn't realize the section-1 radio IS the way. Renamed: "תגית (טקסט חופשי)" → "📝 מידע כללי (טקסט חופשי)"; "סטטוס (6 ערכים — כמו עמודות בקרת ביצוע)" → "🔨 שלב בקרת ביצוע"; section 1 subtitle gets concrete examples ("מכור, מס׳ חדרים / טיח, גז"). Dropped "(6 ערכים)" — number means nothing without context. Backend tag/status enum unchanged — pure UI label change. ~3 LOC across 2 files (AddStageForm + StageManagementDialog). |
| **[#497 — Phase 2C polish (CRITICAL data-loss fix)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2c-polish.txt)** | ✅ **Shipped 2026-05-05** — Hidden template stages couldn't be unhidden in StageManagementDialog because the dialog only saw filtered `stages` (which excluded hidden ones via `_resolve_visible_stages`). Cells of hidden stages were intact in DB but invisible to PM — looked like data loss. **Fix:** backend `/matrix` response now exposes `template_stages` (ALL base stages incl. hidden); dialog uses this for section 2 with hide state from `base_stages_removed`. Hide → save → reopen → unhide → save → cells reappear with all data intact. NEW backend test `test_hide_then_unhide_template_stage_preserves_cells` enforces data integrity. Discovery: initial deploy of fix appeared not to work — investigation revealed Cloudflare Pages deploy had failed (frontend cache stale, browser served old text). After re-deploy: confirmed working in 30-second Zahi smoke. Per-batch lesson: **always verify frontend deploy succeeded** when fix involves frontend changes (Cowork inline edit pattern doesn't push to Cloudflare; only Replit-Agent commit + Zahi deploy.sh does). ~20 LOC across 3 files. Backend additive only. |
| **[#496 — Mobile row tap on MatrixListView](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-mobile-row-tap.txt)** | ✅ **Shipped 2026-05-05** — Post-#494 prod mobile feedback: tapping the stage TITLE in a unit's expanded body did nothing — only the small status icon at the left was tappable. Per Zahi: "אינטואיטיבי שכשאני לוחץ בכל מקום ברובריקה למשל של הכנת ליציקת תקרה זה אמור לפתוח לי את הpopup". Fix: convert stage row `<div>` to `<button>` when `onCellClick` is provided; remove redundant `onClick` from MatrixCell inside ListView (avoids nested-button HTML invalid). Layout unchanged — same flex/gap/padding/border. Added hover/active feedback + cursor-pointer. MatrixGridView (desktop) untouched. ~12 LOC, 1 file. |
| **[#495 — Phase 2C: Stage management dialog (custom columns + hide/reorder)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2c-stage-management.txt)** | ✅ **Shipped 2026-05-05** (with #497 polish) — Adds the ⚙ settings icon to ExecutionMatrixPage opening a Radix dialog. Section 1: custom columns (drag-reorder + delete + add new). Section 2: template stages (hide/show toggle with eye icon). Negative `order = i - N` trick on save → custom stages render BEFORE template stages in RTL. 3 NEW components: StageManagementDialog (~310 LOC), StageRow (~125 LOC), AddStageForm (~80 LOC). Backend bug fixes: (1) ID preservation with hijack protection — Pydantic v1 was stripping unknown `id` field from `MatrixStageCreate` schema, so handler `s.get("id")` always returned None and custom stages got new IDs every save (orphaning their cells). Schema field added + handler validation. (2) Frontend always sent empty `base_stages_removed: []` because state reset on dialog open. Backend exposes `base_stages_removed` in /matrix response so frontend hydrates from server truth. **Drag-and-drop:** @dnd-kit/core + @dnd-kit/sortable installed (~12KB JS-only, no native plugins). |
| **[#494 — Phase 2B: Cell editing (popover/sheet + audit history)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2b-cell-editing.txt)** | ✅ **Shipped 2026-05-05** — Cells become tappable; opens CellEditDialog (Radix Dialog responsive: bottom sheet on mobile via `bottom-0 rounded-t-2xl`, centered modal on desktop via `md:top-1/2 md:left-1/2`). For status cells: 6-status grid picker + free-text note (max 500 chars, character counter) + collapsible history section showing last 10 audit entries. For tag cells: text input + note + history. Saves via PUT `/cells/{unit_id}/{stage_id}` with optimistic update (snapshot prevCells, mutate UI immediately, revert + toast on error). Audit chain populated server-side. D-svc finding: `API` constant already includes `/api`, so methods call `${API}/execution-matrix/...` not `${API}/api/execution-matrix/...`. ~497 LOC frontend across CellEditDialog + matrixService extensions. Backend untouched (#483 endpoints already serve this). |
| **🆕 May 4 mega-cluster — Execution Matrix Phase 1+2A + Override polish + Safety coverage + Nav fixes (18 batches)** | ✅ **All shipped to prod 2026-05-04**. Two intensive days of feature delivery + polish. **Three streams ran in parallel:** (1) **Execution Matrix** — net-new "מטריצת ביצוע" feature for 2D unit×stage tracking (replaces Eli's external Excel). Phase 1 backend (8 endpoints, 3 collections, 6 status values, 2 stage types, RBAC) + Phase 2A frontend (mobile-first ListView with collapsible cards + desktop GridView with sticky building/unit columns + StatusLegend + back-button + numeric sort by building name). (2) **PM Override** — full close-with-override flow (audit log, dialog with reason, badge in 3 surfaces) + multiple data-path hotfixes (`runData.run.stage_actors` nested correctly in 8 read sites). (3) **Safety tag coverage** — closed 4 surfaces (TaskDetailPage detail, UnitDetailPage list, ProjectTasksPage list, ApartmentDashboardPage list — last one was a spec discovery gap, route `/units/:u/defects` renders ApartmentDashboardPage not UnitDetailPage) + filter chip on BuildingDefectsPage (added `safety_open_count` to `/buildings/{id}/defects-summary` aggregate; D2a inline toggle pattern). **Plus** QC back-navigation chain (`?from=qc` preserved through Floor + Stage layers — fixes broken-fallback-to-`/buildings/{b}` UX) and Execution Control unit-scope stage rendering on FloorDetailPage. **Process improvements** — 2 new iron rules added to CLAUDE.md: (a) "API endpoint contract changes require 3-layer grep" (URL string + service method name + direct fetch — caught after #481 stage_actors data path bug); (b) "Verify actual API response shape, not just source code" (caught from #481 — backend `+1 line at qc_router.py:1120` was redundant; data was already nested in `run`). **Workflow improvement** — prod deploy command now ends with `&& git checkout staging` to prevent Replit from accidentally committing to `main` for next batch (was happening every batch before). 18 batches spanning ~70 LOC each on average; cumulative ~1,500 LOC frontend + ~700 LOC backend + 35+ new tests. See individual entries below. |
| **[#493 — Safety pill in ApartmentDashboardPage card list](computer:///Users/zhysmy/brikops-new/specs/batch-469-followup-4-apartment-dashboard-pill.txt)** | ✅ **Shipped 2026-05-04** — Closes the last safety-pill surface gap. ApartmentDashboardPage is the actual route component for `/projects/:projectId/units/:unitId/defects` (NOT UnitDetailPage — discovery error in #491 spec). Same byte-identical pill pattern as ProjectControlPage L3913. ~5 LOC, single file. Now 5 safety surfaces consistent: ProjectControlPage / TaskDetailPage / UnitDetailPage / ProjectTasksPage / ApartmentDashboardPage. |
| **[#492 — Back button on ExecutionMatrixPage](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-back-button.txt)** | ✅ **Shipped 2026-05-04** — Discovered during cluster smoke. Adds ArrowRight back button to top-right (RTL natural "back") of ExecutionMatrixPage header, navigating to `/projects/{p}/qc`. Also rendered in loading + error states. ARIA label `חזרה לבקרת ביצוע`. Hardcoded path (not `navigate(-1)`) — robust against direct-URL/bookmark entry. ~25 LOC. |
| **[#491 — Safety pill in UnitDetailPage + ProjectTasksPage card lists](computer:///Users/zhysmy/brikops-new/specs/batch-469-followup-3-list-pills.txt)** | ✅ **Shipped 2026-05-04** — Followup-3 to #469. Pill rendered in TaskDetailPage detail and ProjectControlPage list, but missed UnitDetailPage L327 + ProjectTasksPage L544. Same byte-identical Tailwind pattern. ~8 LOC across 2 files. |
| **[#490 — Mobile MatrixListView collapsible cards](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-mobile-collapsible.txt)** | ✅ **Shipped 2026-05-04** — Mobile UX redesign of `MatrixListView`. Default state: `~70px` card with badge + unit + floor + count + chevron + progress bar (no horizontal scroll). Tap header → expands vertical stage list with full Hebrew names at `text-[13px]` (readable) + `MatrixCell size="sm"` icons. Per-unit `Set` state — multiple expanded simultaneously. Touch targets ≥48px (Phase 2B tap-to-edit ready). Solves all 4 mobile UX pains: vertical scroll fatigue, horizontal scroll inside cards, unreadable 9px text, truncated stage names. Single file change (~50 LOC). Page height for 30 units: `~3,900px → ~2,100px` (default). |
| **[#489 — Numeric building name sort](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-numeric-building-sort.txt)** | ✅ **Shipped 2026-05-04** — Mirror of #485's `unit_no` fix at building name level. Buildings named `"8"`, `"9"`, `"10"`, `"11"` (string field, no `sort_index`) sorted lex as `"10" < "11" < "8" < "9"`. Added numeric `int()` parse with 9999 fallback to `_unit_sort_key` — sort tuple now 6-tuple `(sort_index, building_name_num, building_name_str, floor_number, unit_no_num, unit_no_str)`. Backward compatible (sort_index still wins; non-numeric names fall through to existing string tiebreak). ~30 LOC backend + 1 new regression test. |
| **[#488 — Safety #469 followup-2 (TaskDetailPage pill + BuildingDefectsPage filter)](computer:///Users/zhysmy/brikops-new/specs/batch-469-followup-2-coverage.txt)** | ✅ **Shipped 2026-05-04** — Originally spec'd 2026-05-03. Backend extended `/buildings/{id}/defects-summary` aggregate with `safety_open_count` per unit (D1a — additive, mirrors `categories[]` pattern; single fetch, instant client toggle). Frontend added: TaskDetailPage pill (was deferred per #469 spec) + BuildingDefectsPage inline toggle "🛡️ ליקויי בטיחות בלבד" (D2a — above filter drawer trigger, not a FilterDrawer extension; py-3 ≥44px touch target). Touch target compliant. ExportModal filters bridged. ~28 LOC + 1 new test. |
| **[#487 — Execution Matrix: full building name display](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2a-building-name-display.txt)** | ✅ **Shipped 2026-05-04** — Cosmetic fix to #486. Buildings named "בניין A" / "בניין B" both rendered as "ב" badge (Hebrew first-letter collision when `sort_index` unset). Replaced single-letter circle badge with full building name in violet pill (truncate + tooltip for long names). Widened "בניין" sticky column 80px → 120px in desktop grid. Same approach in mobile card header. Frontend-only, ~16 LOC across 2 files. No backend, sort order from #486 unchanged. |
| **[#486 — Execution Matrix: separate sticky building column](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2a-building-column.txt)** | ✅ **Shipped 2026-05-04** — Without showing building, "דירה 1, קומה 1" of Building A indistinguishable from "דירה 1, קומה 1" of Building B (unit_no is per-building). Added separate sticky "בניין" column in desktop GridView (RTL right-0, z-30) + building badge before "דירה N" in mobile ListView card header. Backend `_unit_sort_key` extended to 5-tuple with `(building_sort_index, building_name, floor_number, unit_no_num, unit_no_string)`. Backend exposes `buildings: [...]` in `/matrix` response (additive). Per Zahi mockup approval: Option B (separate column) chosen over Option A (merged) for future-readiness of Phase 2D filter UI. ~80 LOC across 5 files. |
| **[#485 — Execution Matrix Phase 2A polish (3 fixes)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2a-polish.txt)** | ✅ **Shipped 2026-05-04** — 3 polish issues from #484 staging smoke: (1) Header missing building count → frontend computes via `new Set(units.map(u => u.building_id)).size`. (2) Unit sort lex (1, 16, 17, 19, 2, 20, 3...) → numeric (1, 2, 3, ..., 30) by adding `int(unit_no)` parse with 9999 fallback to `_unit_sort_key` (3-tuple). (3) "קומה ?" everywhere → backend now exposes `floors: [...]` in `/matrix` response (already fetched internally for sort, just exposed). Backend ~10 LOC + frontend ~10 LOC + 1 new sort regression test. Backward compatible. |
| **[#484 — Execution Matrix Phase 2A frontend (read-only, mobile-first)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-2a-frontend-readonly.txt)** | ✅ **Shipped 2026-05-04** — User-visible foundation on top of #483 backend. **Mobile-first per Zahi** ("רוב המשתמשים מובייל"). 8 NEW files: `STATUS_CONFIG.js` (6 status types, Lucide icons not emoji per CLAUDE.md), `MatrixCell.js` (32×32 sm / 40×40 md), `StatusLegend.js` (collapsible), `MatrixListView.js` (mobile cards), `MatrixGridView.js` (desktop grid with sticky right column for RTL), `STATUS_CONFIG.js` constants, `matrixService.js`, `useMatrixData.js` hook (abort-on-unmount + retry). + `ExecutionMatrixPage.js` page. CSS-only view switching via `md:hidden`/`hidden md:block` (no JS media queries). New top-level route `/projects/:projectId/execution-matrix`. CTA card "🔲 מטריצת ביצוע" added to QC home page (above "סטטוס ביצוע כללי" card) per Zahi placement decision. Default render-time stage list: `qc_template.stages` (live read) + `custom_stages` − `base_stages_removed` (computed, no migration when admin edits template). 3 drifts vs spec: D-svc (matrixService uses axios+API+getAuthHeader pattern, not default api import — required exporting `getAuthHeader` from api.js, +1 LOC, establishes pattern for future external service files), D-cta-role (CTA visible to all per FALLBACK clause; backend RBAC handles 403 for contractors), D-lazy (App.js DOES use React.lazy — initial drift assumption was wrong, corrected during build). ~497 LOC across 8 NEW files + 3 small edits. |
| **[#483 — Execution Matrix Phase 1 Backend](computer:///Users/zhysmy/brikops-new/specs/batch-execution-matrix-phase-1-backend.txt)** | ✅ **Shipped 2026-05-04** — Net-new backend foundation for "מטריצת ביצוע" — a 2D unit×stage matrix replacing external Excel sheets. **Architectural anchors:** matrix is INDEPENDENT data store (3 NEW collections — execution_matrix, execution_matrix_cells, execution_matrix_views; lazy-init); annotations from qc_runs are READ-ONLY display hints (no state coupling); admin edits to qc_template auto-reflect in matrix base stages (computed at render time, no migration); engineers can ADD custom stages + REMOVE base stages per project. NEW `execution_matrix_router.py` (540 LOC) with 8 endpoints under `/api/execution-matrix`. 6 status values: completed/partial/in_progress/not_done/not_relevant/no_findings. 2 stage types: status (6 values) + tag (free text). Per-cell audit chain (actor + timestamp + before/after). Per-user saved views with location + per-stage + tag + search filters. **RBAC:** edit = PM + super_admin + ANY active project_approver (regardless of `mode`); view = super_admin + project_manager + owner + management_team; contractor blocked. **4 documented divergences** as docstring at top of router (D1: imports from `contractor_ops.router` not `qc_router`; D2: `"active": True` filter on approvers — caught spec placeholder gap; D3: "viewer" role removed — doesn't exist; D4: stage-scoped approvers get full matrix-edit). schemas.py +104 LOC (`MATRIX_STATUS_VALUES`, 11 Pydantic models). server.py +3 LOC for router registration. test_execution_matrix.py NEW with 11 tests passing in 2.38s. qc_router.py: 0 lines diff. |
| **[#482 — Stage layer back-navigation preserves ?from=qc](computer:///Users/zhysmy/brikops-new/specs/batch-stage-back-nav-preserve-from-qc.txt)** | ✅ **Shipped 2026-05-04** — Followup to #480. #480 fixed Floor round-trip but missed Stage layer. Real chain: `/qc → /buildings/{b}/qc?from=qc → /floors/{f}?from=qc → /qc/floors/{f}/run/{r}/stage/{s}` — `?from=qc` was DROPPED at the Floor → Stage hop, breaking the rest of the chain. Two transitions fixed: FloorDetailPage L289 (floor-scope stage card click forwards `?from=qc`) + StageDetailPage L1601 `goBack` body wrapped (covers all 3 callers atomically). 2 files, ~13 LOC. Now full chain `/qc → building → floor → stage → back×4 → /qc` closes correctly. |
| **[#481 — Override badges + audit block data path hotfix (P0)](computer:///Users/zhysmy/brikops-new/specs/batch-hotfix-stage-actors-data-path.txt)** | ✅ **Shipped 2026-05-04** — P0 hotfix to #478 + #479. Override functionality worked end-to-end (data persisted, audit log written, notifications fired) but ALL 3 visibility surfaces (top status badge, bottom action-bar badge, audit block with reason) DID NOT RENDER on staging because frontend read `runData.stage_actors` at top-level while actual API response has `stage_actors` nested inside `runData.run`. 8 read sites in StageDetailPage migrated atomically via `replace_all` with exact match string. Spec author defensive note triggered ("if STEP 0.1 finds MORE than 3 read sites, update ALL of them" — 8 found, 8 migrated). Process improvement: 2nd new iron rule added to CLAUDE.md ("verify actual API response shape, not just source code that generates it"). |
| **[#480 — QC back-navigation Floor round-trip preserves ?from=qc](computer:///Users/zhysmy/brikops-new/specs/batch-qc-back-nav-preserve-from.txt)** | ✅ **Shipped 2026-05-04** — Family of 5K (#451). The `?from=qc` URL param introduced by 5K survives `/qc → /buildings/{b}/qc?from=qc` but was dropped on the Floor round-trip. By the time user clicked back from BuildingQCPage, param was gone, and 5K's smart `handleBack` fell back to `/buildings/{b}` instead of `/projects/{p}/qc`. Fix: BuildingQCPage floor click + FloorDetailPage back nav both propagate `?from=qc`. 2 files, ~7 LOC. (Stage layer left for #482.) |
| **[#479 — PM Override audit block visible on StageDetailPage](computer:///Users/zhysmy/brikops-new/specs/batch-pm-override-followup-audit-block.txt)** | ✅ **Shipped 2026-05-04** — Followup to #478. Override functioned correctly but the UI didn't visibly show the override REASON or distinguish override-approval from normal approval prominently enough. Added: top status badge "🛡 אושר ב-Override על־ידי X" (amber pill) + new amber audit block below "סיכום פעולות" with אישר / תאריך / סיבה rows. Frontend-only ~25 LOC. All data already exposed by #478 via `stage_actors[stage_id]` (per-stage actor fields). |
| **[#478 — PM Override close (P1)](computer:///Users/zhysmy/brikops-new/specs/batch-pm-override-close.txt)** | ✅ **Shipped 2026-05-04** — Allows PM + super_admin to close stages that have unfilled items, with mandatory reason text field and full audit log. Adds POST `/qc/run/{r}/stage/{s}/override-close` endpoint, dialog with reason validation, audit log entry, badge "🛡 אושר ב-Override" on closed stages. Self-notification filter (PM doesn't notify themselves). Items bulk-marked pass + `via_override=true`. Backend +1 LOC at qc_router.py:1120 to expose `stage_actors` (later turned out redundant — see #481). 4 backend tests + visual smoke. |
| **[#477 — UnitQCSelectionPage hotfix (P0 — units vs stages shape mismatch)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-control-hotfix-unit-selection.txt)** | ✅ **Shipped 2026-05-04** — P0 hotfix to #476. Endpoint `/floors/{id}/units-status` shape changed from `{units: []}` to `{stages: []}` in #476 STEP 0 grep, but a SECOND consumer (`UnitQCSelectionPage` via `qcService.getUnitsStatus` service method) was missed. Page broke with "משהו השתבש" on staging. Fix: backend response now includes BOTH `units` (legacy shape for UnitQCSelectionPage) AND `stages` (new shape from #476). Process improvement: 1st new iron rule added to CLAUDE.md ("API endpoint contract changes require 3-layer grep — URL string + service method name + direct fetch"). |
| **[#476 — Execution control floor view shows ALL unit-scope stages (P1)](computer:///Users/zhysmy/brikops-new/specs/batch-execution-control-unit-scope-fix.txt)** | ✅ **Shipped 2026-05-04** — P1 bug fix. `/floors/{id}/units-status` aggregated unit-scope stages by `stage_id` only, collapsing duplicates across units. PMs saw only ONE "אמבטיה+אינטרפוץ" instead of one per unit. Reshaped response to `{stages: [{stage_id, unit_count, completed_count, ...}]}` with per-unit drill-down via `/qc/units?stage_id=X` route. Frontend FloorDetailPage updated to render unit-scope stage cards with completion progress + click-to-drill. 4 backend tests + 2 frontend updates. |
| **[Batch #469 followup-2 — Safety tag coverage gaps (TaskDetailPage pill + BuildingDefectsPage filter)](computer:///Users/zhysmy/brikops-new/specs/batch-469-followup-2-coverage.txt)** | ✅ **Shipped as #488 above.** Originally spec'd 2026-05-03; deployed 2026-05-04 with backend extension (D1a) and inline toggle (D2a). |
| **#469 + #473 (S2B v2) staging deploy + smoke test** | ✅ **DEPLOYED + VERIFIED 2026-05-03** — Combined deploy of both batches (independent, no coupling). Smoke test on staging: ✅ Section 4 personnel section works (5 role groups, multi-per-role, ID masking 1***789, save/reload persists, regression on sections 3+5 OK, PDF still works without personnel section as expected for S2B v2); ✅ #469 toggle in NewDefectModal works, pill renders on /control filtered view, filter chip works in /control?statusChip=open. **3 follow-up gaps identified** — all non-regressions, all deferred either per #469 spec or as new follow-up batches (#469-followup-2 above + #471 dashboard polish + S2B v3 PDF integration). PDF design batch still pending (Hebrew labels = boxes — same as 2026-05-03 morning discovery, not new). Awaiting Zahi prod deploy. |
| **[Batch #468 (S2A v3) — Safety Project Registration (Capacitor-aware)](computer:///Users/zhysmy/brikops-new/specs/batch-s2a-safety-project-registration.txt)** | 🟡 **Live in staging 2026-05-03** — First sub-batch finishing Safety Phase 1. Implements Israeli Ministry of Economy "פנקס הקבלנים" format. New collection `safety_project_settings`, lazy-init pattern. Frontend: 4-section collapsible form (כללי / מען / מנהלי החברה / אסמכתאות) with completion bar + PDF export. PII (id_number) hashed (SHA-256) + masked on display (`1***789`). V3 evolution captured 3 critical lessons: (V1→V2) helper name bug — used `_hash_id` (doesn't exist) instead of `_hash_id_number`; Hebrew font wrong — `'HebrewFont'` doesn't exist, must use `'Rubik'` + wrap all Hebrew with `hebrew()` helper. (V2→V3) Capacitor PDF download — `<a download>` is web-only; switched to `downloadBlob()` from utils/fileDownload.js + `safe-area-inset-bottom` on bottom action bar. Addendum #1 split routes into `safety_registration_router.py` (NEW file) instead of appending to safety_router.py (1,912 LOC). V9 visual smoke partial (a-c passed); known bug: Hebrew **labels** in PDF render as boxes (□□□□) while user-input text renders correctly — wrapper applied to inputs not statics. **Deferred to dedicated PDF design batch.** Awaiting smoke completion + prod deploy. |
| **[Batch #469 — Defect "בטיחות" tag](computer:///Users/zhysmy/brikops-new/specs/batch-469-defect-safety-tag.txt)** | 🟡 **Diff reviewed + APPROVED for staging 2026-05-03** — Second Safety Phase 1 finishing sub-batch. Adds manual `is_safety: bool` boolean tag to defects (tasks collection) so PMs can mark safety-related defects. Toggle in NewDefectModal + orange `🛡️ בטיחות` pill on defect cards + `🛡️ בטיחות בלבד` filter chip. Backend extends Task/TaskCreate/TaskUpdate schemas + adds query param to GET /tasks (None sentinel pattern on Update for partial updates). 5 schema-only unit tests. Per CLAUDE.md "new file per new domain" rule — does NOT create new router (extending existing tasks domain, not introducing new domain). Backward compat: existing defects render as `is_safety=false`. Code review found 0 MUST-FIX, 2 SHOULD-FIX (URL persistence + touch target), 1 NICE-TO-HAVE (3 orange shades = intentional emphasis hierarchy, not bug) — all bundled into separate followup polish batch. Pending Zahi `./deploy.sh --stag`. |
| **[Batch #473 (S2B v2) — Safety Project Personnel embedded on registration](computer:///Users/zhysmy/brikops-new/specs/batch-s2b-v2-safety-personnel-embedded.txt)** | 🟡 **Spec sent + Replit plan APPROVED 2026-05-03** — Third Safety Phase 1 finishing sub-batch. Adds project-level safety personnel section (5 canonical roles from VALID_SUB_ROLES: site_manager, execution_engineer, safety_assistant, work_manager, safety_officer). Multiple per role allowed. **Architecturally embedded** on existing `safety_project_settings` document (mirrors `managers` pattern from #468) — NO new collection, NO new router, NO new API surface. Document-only (regulatory) — does NOT grant any system permissions; for permissions use project_memberships + sub_role separately (decoupled to avoid risky touching of memberships/auth/RBAC). PDF integration deferred to S2B v3 (separate batch keeps risk isolated). Memberships sync deferred to Phase 2. **SUPERSEDES cancelled S2B v1** (which invented `safety_consultant` role + created risky separate collection). Approved with addition: include 2 mock tests (not skip them). Awaiting Replit review.txt. |
| **[Batch #469 followup polish — URL persistence + touch target + orange palette](computer:///Users/zhysmy/brikops-new/specs/batch-469-followup-polish.txt)** | 📋 **Spec ready 2026-05-03 — optional, P3** — Bundles 2 SHOULD-FIX + 1 NICE-TO-HAVE from #469 code review. SF1: replace local `useState` for safetyFilter with URL-derived pattern (matches existing urlStatusChip/urlOverdue pattern) — filter survives refresh + deep-linkable. SF2: enlarge safety chip from `px-3 py-1.5` (~28px) to `px-4 py-3` (~46px) to meet Apple HIG 44dp touch target (CLAUDE.md Capacitor rule). NTH: 2 brief comment blocks documenting the intentional 3-level orange emphasis hierarchy (icon / active / pill) — re-evaluation showed they're NOT a bug, just need devs to know not to "consolidate" them. 1 file required + 1 optional. Can ship with #469 or defer to #471 dashboard polish. |
| **[CANCELLED: Batch S2B v1](computer:///Users/zhysmy/brikops-new/specs/batch-s2b-safety-project-personnel.txt)** | ❌ **CANCELLED 2026-05-03** — Original S2B spec invented `safety_consultant` role (NOT in `VALID_SUB_ROLES` at invites_router.py:145) and missed `execution_engineer` + `work_manager` (both canonical). Also created separate `safety_project_personnel` collection + new router file — architecturally risky for Phase 1 (creates parallel role taxonomy + duplicate data). Replaced by S2B v2 (embedded approach above). Lesson: must always grep `VALID_SUB_ROLES` before defining new role enum — direct violation of CLAUDE.md "אל תמציא, תבדוק" rule. |
| **CLAUDE.md operational rule extensions (3 new iron rules)** | ✅ **Shipped 2026-05-03** — Three new iron rules added to project-level CLAUDE.md based on lessons learned during Safety Phase 1 finishing work: (1) **"לא לנחש, לבדוק בקוד תמיד"** — Cowork must never assume schema/fields/behavior; every spec needs STEP 0 pre-flight greps verifying line numbers + content anchors. Triggered by Stream A v2 production bug where I assumed all contractors had `role === 'contractor'` (false in prod data). (2) **"קבצים חדשים, לא להעמיס קיימים"** — every new sub-batch creates NEW router/component files instead of appending to existing 1,500+ LOC files. Triggered by safety_router.py reaching 2,070 LOC after #468 (now extracted addendum to safety_registration_router.py). (3) **"תמיד לזכור Capacitor"** — every frontend spec must consider WebView constraints: PDF downloads via `downloadBlob()` helper (not `<a download>`), bottom bars with `paddingBottom: env(safe-area-inset-bottom)`, touch targets ≥44px (`py-3`), `type="email"`/`type="tel"` for keyboards, native gesture preservation. Triggered by S2A spec V2→V3 evolution (PDF download was web-only). Also added staging credentials section + `demo-contractor@brikops.com` test user. |
| **PDF design backlog item — Hebrew labels render as boxes (□□□□)** | 🟡 **Discovered 2026-05-03 during #468 V9 visual smoke** — User-entered Hebrew text in `generate_registration_pdf` renders correctly (e.g. "ארזי הנגב", "צחי שמי") but static Hebrew labels (section headers like "כללי", "מען המשרד", field labels) render as boxes. Indicates `hebrew()` wrapper is applied to inputs but not to static strings, OR Rubik font fails to load for static path. Also: PDF typography/spacing/hierarchy needs polish. **Deferred to dedicated PDF design batch** (post Safety Phase 1 finish). Not blocking — PDF is functional, just not visually polished. |
| **[DOCS Phase 1A — Architecture ADRs + refactor backlog + CLAUDE.md extension](computer:///Users/zhysmy/brikops-new/docs/architecture/README.md)** | ✅ **Shipped 2026-04-29** (task #450, 11 files / ~96KB / zero code changes) — 8 ADRs documenting WHY for the largest files (ProjectControlPage 4115, qc_router 2936, handover_router 2652, billing_router 2068, tasks_router 1289) + 3 cross-cutting ADRs (status system, i18n, navigation conventions). Refactor backlog with 21 actionable items (severity-tagged, evidence-based, fold-into-batch suggestions). CLAUDE.md extended from 41 to 133 lines (original Hebrew operational doc preserved verbatim, added "🤖 Standing instructions for Cowork" section with anti-patterns + helper-finder + standing rules). STEP 0 caught 14 files >1500 lines (not 5-8 as originally assumed); 9 files without ADR flagged in backlog #20 as "future ADR triggers when next touched heavily." Foundation for any future contributor or refactor batch. |
| **[Batch 5J — OrgBilling 3 back buttons honor sourceProjectId](computer:///Users/zhysmy/brikops-new/specs/batch-5j-org-billing-back-source-project.txt)** | 📋 **Spec ready** — Same family as 5I but different surface. The 3 "חזרה" buttons at OrgBillingPage.js:795/860/880 ignore sourceProjectId → user from project context jumps to /admin instead of back to project. Fix: extract handleBackNav() helper that prefers sourceProjectId, falls back to existing isSA logic. 1 file, 1 helper add + 3 onClick swaps. |
| **[Batch 5K — BuildingQC back to /qc when arriving from there](computer:///Users/zhysmy/brikops-new/specs/batch-5k-qc-building-back.txt)** | 📋 **Spec ready** — Same ?from= URL-param convention as 5H. 3 entry paths to /buildings/:id/qc; only entry from /qc home was broken. Fix: append &from=qc at QCFloorSelectionPage:326 + smart handleBack in BuildingQCPage. 2 files, ~5 sub-edits. |
| **[Batch 5I — Handover + OrgBilling back arrows (broken /projects/:id pattern)](computer:///Users/zhysmy/brikops-new/specs/batch-5i-handover-back-button.txt)** | ✅ **Shipped 2026-04-29** (task #449, 2 files / 2 sub-edits) — STEP 0.2 found 2 instances of `navigate(/projects/${id})` pattern that fall through to /projects (no such route exists). Both edited to navigate to /control?workMode=structure with appropriate destination. Bonus regression sweep confirmed bug class fully eradicated from frontend (0 remaining hits). |
| **[Batch 5H — Smart back from /control to /dashboard via ?from=dashboard convention](computer:///Users/zhysmy/brikops-new/specs/batch-5h-dashboard-back-navigation.txt)** | ✅ **Shipped 2026-04-29** (task #448, 2 files / 8 sub-edits) — Mirrored existing ?from=dashboard URL-param convention from ProjectTasksPage. 6 KPI navigates on dashboard append &from=dashboard; ProjectControlPage back arrow checks the param + breadcrumb appears in defects view. KpiCard component extended to accept `title` prop for tooltip. Edge case at ProjectControlPage:3770 in-page לאישור shortcut drops `from` — filed as Task #36 follow-up. |
| **[Batch 5G — Dashboard simplify + i18n unification + bucket alignment](computer:///Users/zhysmy/brikops-new/specs/batch-5g-dashboard-simplify-and-i18n.txt)** | ✅ **Shipped 2026-04-29** (task #447, 4 files / 8 logical edits) — Closed 2 user-visible bugs found post-5F: (1) "13 פתוחים → click shows 9" — STATUS_BUCKET_EXPANSION['open'] expanded from 3 to 6 statuses to mirror dashboard open_statuses. (2) "אושר" still appearing on TaskDetailPage etc — i18n he.json:49 changed from "אושר" to "סגור". Also: removed standalone "בביצוע" KPI card (5 cards instead of 6), added tooltip to "פתוחים" explaining overlap with "לאישורי", extended KpiCard component to accept `title` prop. Drift-guard test updated (4/4 still passing). Bug #35 (back-navigation) discovered separately during smoke test, tracked as P2 follow-up. |
| **[Batch 5F — Status bucket expansion + 'אושר' label cleanup](computer:///Users/zhysmy/brikops-new/specs/batch-5f-status-bucket-expansion.txt)** | ✅ **Shipped 2026-04-28** (task #442, 7 files / 9 logical edits) — Architectural fix for KPI count vs chip-click mismatch + label confusion. Added STATUS_BUCKET_EXPANSION dict in tasks_router.py as single source of truth for what 'open'/'in_progress'/'closed' chips mean. Frontend unified "אושר" → "סגור" in 4 status maps. Reverted 5C statusIn workaround in ProjectTasksPage chips. New drift-guard test file (4 tests, all PASS) catches future contributors who add a status to dashboard buckets but forget the expansion. Replit's STEP 0 audit found 4 callers of taskService.list, all classified safe. |
| **[Batch 5C — status='approved' alignment + dropdown polish](computer:///Users/zhysmy/brikops-new/specs/batch-5c-approved-status-alignment.txt)** | ✅ **Shipped 2026-04-28** (task #442, 12 files / 16 logical fixes after Zahi pulled 2 EDIT-MISSED into scope) — REAL fix for Batch 5 Bug #2. force_close (פאנל ניהול) writes status='approved'; frontend + 8 backend aggregations only knew 'closed'. 6 backend (constants, projects_router, stats_router 5 sub-locations, export_router 4 sub-locations, tasks_router:416 KPI numerator, handover_router local-duplicate dedupe) + 4 frontend (UnitDetailPage, ProjectTasksPage, StatusPill, GroupedSelectField visual + ApartmentDashboardPage + ProjectControlPage DEFECT_STATUS_CONFIG). v2 STEP 0 audit caught EDIT-MISSED at projects_router:1229 (per-unit KPI feeding the original symptom) and ProjectControlPage:3313 — both pulled into scope. |
| **[Batch 5B — Reopen modal + UnitDetailPage refresh + companies dedupe](computer:///Users/zhysmy/brikops-new/specs/batch-5b-staging-followup.txt)** | ✅ **Shipped 2026-04-28** (task #439, +126/-25 across 3 frontend files) — Bug A: replaced native window.confirm in reopen with branded RTL Radix Dialog. Bug B (refresh part): added 4-ref refresh-on-focus pattern to UnitDetailPage matching ProjectTasksPage Batch 5#2. Bug C: dedupe duplicate `companies` state — single source of truth in parent, hardened parent's `loadCompanies` with toast.error + companiesLoading. Visual smoke confirmed Bug A + C work; Bug B refresh fires but root cause was status mismatch → Batch 5C. |
| **[Batch 5 — UX bug pack (3 of 4)](computer:///Users/zhysmy/brikops-new/specs/batch-5-ux-bug-pack.txt)** | ✅ **Shipped 2026-04-28** (task #437) — Bug #1 Reopen button (gated to project_manager + management_team), Bug #2 list refresh on focus/visibility (ProjectTasksPage only — UnitDetailPage missed, fixed in 5B), Bug #4 Trade required when adding company (enforced in QuickAddCompanyModal + AddTeamMemberForm + AddCompanyForm + AddTeamMemberForm "+ הוסף חברה חדשה" call site). Bug #3 (UserDrawer 3 native `<select>` escape on Desktop browsers) DEFERRED to future Batch 5D. |
| **[Subscription Cancellation v1](computer:///Users/zhysmy/brikops-new/specs/subscription-cancellation-v1.txt)** + 2 hotfixes ([state card for comped subs](computer:///Users/zhysmy/brikops-new/specs/hotfix-billing-state-card-comped.txt), [API response fields](computer:///Users/zhysmy/brikops-new/specs/hotfix-billing-cancel-fields-in-response.txt)) | ✅ **Shipped 2026-04-28** (commit ffc4715) — Israeli consumer-law compliance (חוק הגנת הצרכן 14ג2). 2 endpoints (cancel/reactivate), 3 emails (user confirm + Zahi alert + reactivate), 3-state UI card, 8 unit tests. ZERO PayPlus API calls. Demo org cancel→reactivate flow verified end-to-end on staging + prod. |
| **[Hotfix #429 — Founder plan checkout charges wrong amount](computer:///Users/zhysmy/brikops-new/specs/hotfix-founder-checkout-amount.txt)** | ✅ **Shipped 2026-04-27** (commit a4eb7eb) — `get_billable_amount` now accepts `plan_override`; checkout + webhook validator both pass `pending_plan_id`. Real customer impact (was charged ₪5,700 instead of ₪499). Founder+yearly guard added (would've underpaid). 1 regression test. |
| **[Batch S7 — Shannon HIGH fix (XSS upload + login lockout + paywall bypass)](computer:///Users/zhysmy/brikops-new/specs/batch-s7-shannon-high-fix.md)** | ✅ **Shipped 2026-04-27** (commit 930db89, 4 of 6 findings) — HIGH-A (XSS upload validator), HIGH-B (login lockout + Hebrew enumeration closure), MED-A (folded into HIGH-B), MED-D (paywall case-insensitive Bearer). HIGH-C (PayPlus webhook) and HIGH-D (GreenInvoice webhook) deferred to future batch — payment system requires dedicated test strategy. |
| **[Batch S6 — Shannon CRIT fix (role + 2 IDORs)](computer:///Users/zhysmy/brikops-new/specs/batch-s6-shannon-crit-fix.md)** | ✅ **Shipped 2026-04-26** (commit eae605f) — CRIT-A, B, C verified fixed on staging + prod |
| [Batch S8 — Shannon MED + INFRA hardening (outline)](computer:///Users/zhysmy/brikops-new/specs/batch-s8-shannon-medium-infra-outline.md) | 📋 Outline — schedule for first 30 days post-launch |
| [Batch S7.5 — Deferred PayPlus + GreenInvoice webhook fixes (HIGH-C + HIGH-D)](#batch-s75--deferred-payment-webhook-fixes) | 📋 Pending — needs zero-cost test strategy before touching payment webhooks |
| [Staging Phase 1-5 — EB env + DNS + deploy.sh --stag](computer:///Users/zhysmy/brikops-new/specs/staging-phase-1-eb-environment.md) | ✅ Shipped 2026-04-26 (full staging pipeline live) |
| [Phase 7 — Shannon (Keygraph) AI pentest](#-staging-environment--shannon-pentest-pipeline-added-2026-04-25) | ✅ First scan complete 2026-04-26 (~$30-40 spent) — see findings → S6, S7, S8 |
| [Batch S5b — TOCTOU + CORS fail-fast](computer:///Users/zhysmy/brikops-new/specs/batch-s5b-toctou-cors-fix.md) | ✅ Shipped 2026-04-25 (commit f38a538, EB ver 37e119678) |
| [Batch S5a — Webhook idempotency](computer:///Users/zhysmy/brikops-new/specs/batch-s5a-webhook-idempotency.md) | ✅ Shipped 2026-04-25 |
| [Batch S2 — Pentest HIGH-1 fix](computer:///Users/zhysmy/brikops-new/specs/batch-s2-pentest-high-fix.md) | ✅ Shipped |
| [Batch S1 — Pentest CRIT-1 + CRIT-2](computer:///Users/zhysmy/brikops-new/specs/batch-s1-pentest-crit-fix.md) | ✅ Shipped |
| [Batch 2b — contractor add + trade-sort](computer:///Users/zhysmy/brikops-new/specs/closed-beta-batch-2b-contractor-add-and-trade-sort.md) | ✅ Shipped |
| [Batch 2b Patch 1 — cross-project guard + toast duration](computer:///Users/zhysmy/brikops-new/specs/closed-beta-batch-2b-patch-cross-project-guard.md) | ✅ Shipped |
| [Batch 2b Patch 2 — return URL + cancel banner](computer:///Users/zhysmy/brikops-new/specs/closed-beta-batch-2b-patch2-return-url-and-cancel-banner.md) | ✅ Shipped |
| [Auth expiry UX — 401 interceptor](computer:///Users/zhysmy/brikops-new/specs/auth-expiry-ux-401-interceptor.md) | ✅ Shipped |
| [Batch 2a — nav + inline company](computer:///Users/zhysmy/brikops-new/specs/closed-beta-batch-2a-nav-and-inline-company.md) | ✅ Shipped |
| [Batch 2a Patch — nested dialog fix](computer:///Users/zhysmy/brikops-new/specs/closed-beta-batch-2a-patch-nested-dialog-fix.md) | ✅ Shipped |
| [Batch 1 — UI polish](computer:///Users/zhysmy/brikops-new/specs/closed-beta-batch-1-ui-polish.md) | ✅ Shipped |
| [Batch 1a — header swap](computer:///Users/zhysmy/brikops-new/specs/closed-beta-batch-1a-header-swap.md) | ✅ Shipped |
| [Safety Phase 1 — master plan](computer:///Users/zhysmy/brikops-new/specs/safety-phase-1-master-plan.md) | ✅ Shipped (Parts 1-5 + patches) |
| [Safety design system](computer:///Users/zhysmy/brikops-new/specs/safety-design-system.md) | ✅ Shipped |

### 📂 All specs folder
[`/Users/zhysmy/brikops-new/specs/`](computer:///Users/zhysmy/brikops-new/specs/) — full history of all specs sent to Replit

---

## ✅ Shipped

### Core platform
- Authentication (email + phone OTP + SSO)
- Projects, buildings, floors, units (hierarchy)
- Defects / tasks with photos, annotations, categories
- Companies + team members (invites via SMS/WhatsApp)
- QC protocols
- Handover protocols
- Plans / documents per unit
- Role-based access (PM, management, contractor, subrole)
- Billing (org-level, Green Invoice integration)
- Account deletion (7-day grace period)
- Backup & DR (S3 cross-region, MongoDB Atlas)

### Safety Module — **Phase 1 shipped (≈25% Cemento parity) + Phase 1 finishing in flight (2026-05-03)**

**Original Phase 1 (shipped earlier):**
- DB + RBAC + feature flag (backend)
- CRUD + filters + audit
- Score + exports + PDF
- Frontend: home + 3 tabs (open/in-progress/resolved)
- Filter + export + bulk actions
- Feature-flagged via `ENABLE_SAFETY_MODULE` in AWS EB env

**Phase 1 finishing batches (status 2026-05-03 EOD):**
- 🟢 **#468 (S2A v3) — Safety Project Registration form** — Live in staging, V9 smoke verified (data layer + UI). Awaiting prod deploy.
- 🟢 **#469 — Defect "בטיחות" tag** — Live in staging, smoke verified (toggle + pill + filter chip in /control filtered view). Awaiting prod deploy.
- 🟢 **#473 (S2B v2) — Safety Personnel embedded section** — Live in staging, smoke verified (5 role groups, multi-per-role, ID masking, regression on sections 3+5 OK). Awaiting prod deploy.
- 📋 **#469 followup-2 — Safety tag coverage** — Spec ready (TaskDetailPage pill + BuildingDefectsPage sidebar filter). Closes 2 gaps from #469 staging smoke.
- 📋 **#469 followup polish** — Spec ready (URL persistence + touch target + orange palette comment block)
- 📋 **#470 (Bottom nav)** — Not yet specified
- 📋 **#471 (Dashboard polish)** — Not yet specified — will reuse `is_safety` filter from #469 + add safety dashboard aggregation widget (closes the "no sync between defects and safety dashboard" gap from staging smoke)
- 📋 **S2B v3 (PDF integration of personnel)** — Deferred until S2B v2 stable in prod
- 🟡 **PDF design batch (Hebrew label rendering bug)** — Discovered 2026-05-03 during V9, deferred

**Operational rule extensions (CLAUDE.md):**
- "לא לנחש, לבדוק בקוד תמיד" (always verify in code)
- "קבצים חדשים, לא להעמיס קיימים" (new files for new sub-batches; #468 addendum extracted routes to `safety_registration_router.py`)
- "תמיד לזכור Capacitor" (every frontend spec considers WebView)

### <a name="handover-pdf-v3x-shipped-2026-04-30"></a>Handover PDF v3.x — **Shipped 2026-04-30** (~2 weeks of intensive iteration)

**Visual & rendering pipeline:** Full v2.6 mockup → Jinja template → WeasyPrint PDF, 64 existing context vars, no DB schema changes.

**Phase 1 — design + schema (v3.0):**
- Cover, TOC, Stats, Severity heatmap; 11 trade categories; 5 status states (ok/partial/defective/not_relevant/not_checked); 15 canonical rooms × 145 items; 8 property fields; 2 meters (water + electricity); ת״ז in every signature chip; ID Appendix page (placeholder mode); QR placeholder with "בקרוב" badge.

**Phase 2 — Hebrew + photo + pagination polish (v3.3 → v3.8):**
- **Hebrew rendering bugs:** Removed 8 `text-transform: uppercase` declarations causing DejaVu font fallback. Replaced static `Rubik-Bold.ttf` with variable Rubik (300-900) — static file kept on disk because `safety_pdf.py` still uses it via ReportLab.
- **Photo rendering:** `<img object-fit:cover>` → `background-image: cover` (WeasyPrint reliability). Photo cap 3 → 6 per defect. Source resolution 600 → 1100px, JPEG q 75 → 85, effective DPI ~76 → ~250.
- **Adaptive cell width:** v3.4 (1/2/3 = 50%/50%/33%) → v3.5 (40%/40%/33%) → v3.6 (40% + smart break) → v3.7 (30% all + count-4/5/6 24%/19%/16%) → **v3.7.1 hotfix** (width moved from `.cell` to `.photo-row` — was being silently ignored by WeasyPrint single-cell table-layout).
- **Pagination:** `defects-summary-block` page-break-inside avoid. Smart room break — first room can split, others get `keep-together`. Eliminated orphan pages 5+6.
- **Header:** `page_header()` Jinja macro (DRY across 7 sections). Contractor logo + delivery date in orange-bold + reference number. **v3.8** — CSS Paged Media `running()` element so header strip repeats on EVERY page (cover excluded).
- **Legal sections:** Canvas signatures rendered as `<img>` (was text-only). Caveat font for typed signatures.
- **Diagnostic:** `[PDF] Photo diag` + `[PDF] legal_sections diagnostic` logging — kept for now to aid future investigation.

**Phase 3 — Tenant ID Photo Upload (v461 + v462, front-only):**
- **Backend:** `POST` + `DELETE /projects/{p}/handover/protocols/{id}/tenants/{idx}/id-photo` — multipart upload, 8MB max, JPG/PNG/WEBP, S3 path `handover/{project_id}/{protocol_id}/tenant_{idx}_id.{ext}`. `_check_handover_management` + `_check_not_locked` guards. `[HANDOVER-PII]` audit log on every upload + delete.
- **PDF service:** Loads each tenant's `id_photo_url` at 1200px / q80 (court-grade, between defect 1100 and signature 300). GET + PUT protocol endpoints resolve `id_photo_display_url` via `generate_url()` (mirrors meter pattern — fixes a v461 bug where thumbnails broke after page reload in S3 mode).
- **Template:** `.tenant-id-photos` kept as `display: table-cell` (preserves tenant-row layout). `.id-photo` upgraded to 90×56 with `background-size: cover`. Front-only — back-side placeholder removed entirely. "ת.ז · אין תמונה" placeholder when missing.
- **UI (HandoverTenantForm.js):** Two side-by-side small buttons per tenant — "צלם" (purple, Camera, `capture="environment"` → mobile camera) + "העלה" (slate, Upload, gallery picker). Preview thumbnail (24×18) after upload, X delete in corner. Labels switch contextually. Disabled when protocol signed.

**Other handover-adjacent fixes:**
- ✅ **Excel import bug** — `_str_val()` in `import_router.py` handles int-as-float (openpyxl reads "1" as `1.0` → was producing "1.0" lookup keys that never matched DB "1"). Fixed 198/277 row failures on tenant Excel import.
- ✅ **Photo Lightbox in StageDetailPage** — clicking a QC inspection photo previously navigated to raw S3 URL in browser, taking user out of app. Now opens an in-app fullscreen modal with backdrop + ESC + body-scroll-lock.

**Outstanding (Phase 4 in Big features planned):**
- 🟡 **QR Verification** — placeholder still shows "בקרוב". 3 implementation tiers documented (basic/medium/full). Trigger-driven.
- 🟡 **7-Year Retention Hardening** — current state: Atlas M10 PITR + S3 versioning + cross-region replication to Ireland (delete-marker replication OFF for ransomware-proof). Missing: S3 Object Lock (immutability), Atlas cross-region retention bumped 1 → 7 days, code-level retention rule on `handover_protocols` collection. Trigger: legal/regulatory request or first ≥100 protocols milestone.

### Closed-beta fixes (Batches 1 → 2b + 3 patches → 5/5B)
- Batch 1 — 6 UI polish items
- Batch 2a — Navigation + inline company modal
- Batch 2a patch — Nested dialog dismiss fix (Radix `onInteractOutside`)
- Batch 2b — Contractor add flow + trade-sort
- Batch 2b Patch 1 — Cross-project draft guard + toast duration
- Batch 2b Patch 2 — Exact return URL + cancel banner
- Auth expiry UX — 401 interceptor + auto-logout
- Batch 5 (2026-04-28) — Reopen button + ProjectTasksPage refresh + Trade required on company create
- Batch 5B (2026-04-28) — Reopen modal (Radix Dialog vs window.confirm) + UnitDetailPage refresh + companies state dedupe

### Mobile apps
- iOS build 15 (under Apple review 2.1(b))
- Android build 15 with icon padding fix

---

## 🟡 In progress / Immediate

### 🚧 Active work (2026-04-29)
- **Handover PDF v3.x** — ✅ **Shipped 2026-04-30** (v3.8 + v461 + v462 stable in production). See [Shipped → Handover PDF v3.x](#handover-pdf-v3x-shipped-2026-04-30). Outstanding work folded into "Big features planned" below: QR Verification (Phase 4) + 7-Year Retention Hardening.
- **Next queue (this chat, updated 2026-05-01):** WhatsApp + Mobile Native Bundle (3 streams). **✅ Stream A SHIPPED to prod 2026-05-01** (Batch 6A v2, Replit task #464) — contractor reminder digest + multi-project URL routing. Now awaiting Meta template approval (24-48h). **Next:** Stream C (Bell wiring + PM digest, OTA, parallel-safe). **Then:** Stream B (Universal Links + Contact Picker, native ./ship.sh). Full plan + status in [Big features planned → 5. WhatsApp + Mobile Native Bundle](#5-whatsapp--mobile-native-bundle--3-streams).

### Mobile release housekeeping
- ✅ **Apple Review** — APPROVED for distribution 2026-04-25 (App ID 6762542628). Can take up to 24h after release click to be publicly available.
- ✅ **Google Play production access** — GRANTED 2026-04-25 (com.brikops.app). Needs explicit release to production track.

### 🧪 Staging environment + Shannon pentest pipeline (added 2026-04-25)

**Plan from Zahi 2026-04-25:**
1. ✅ **Phase 1**: Backend EB staging environment — **COMPLETE 2026-04-26** ([SPEC](computer:///Users/zhysmy/brikops-new/specs/staging-phase-1-eb-environment.md))
2. ✅ **Phase 2**: MongoDB `brikops_staging` DB + isolated user `brikops_staging_user` — **COMPLETE 2026-04-26** (readWrite scoped to brikops_staging only; cross-DB access to brikops_prod returns `not authorized` — defense-in-depth verified)
3. ✅ **Phase 3**: S3 `brikops-staging-files` bucket — **COMPLETE 2026-04-26** (CORS for 7 staging origins, versioning enabled, lifecycle policy delete noncurrent-versions after 30 days, public access blocked, IAM inline policy `BrikOps-S3-FileStorage` extended with 2 staging statements — verified via simulate-principal-policy)
4. ✅ **Phase 4**: Cloudflare Pages staging branch + DNS — **COMPLETE 2026-04-26**

   **🌐 STAGING URLS (USE THESE):**
   - **Frontend:** `https://staging.brikops-new.pages.dev`
   - **Backend API:** `https://api-staging.brikops.com`

   What shipped: Preview env vars set; `staging` branch pushed; CSP fix for `api-staging.brikops.com` + `brikops-staging-files.s3...` (commit 3aaa4fe); DNS `api-staging.brikops.com` → EB env via Cloudflare Proxied; CORS_ORIGINS updated; SUPER_ADMIN_PHONES set to `+972540000001` (demo super-admin user); end-to-end login verified — admin panel + demo project visible. Custom domain `staging.brikops.com` skipped (CF Pages custom domains default to production branch — would break the workflow). Use `staging.brikops-new.pages.dev` instead.

5. ✅ **Phase 5**: `./deploy.sh --stag` flag + staging GitHub workflow — **COMPLETE 2026-04-26** ([SPEC](computer:///Users/zhysmy/brikops-new/specs/staging-phase-5-deploy-stag-flag.md))

7. 🟡 **Phase 7**: Shannon (Keygraph) pentest — **SETUP COMPLETE 2026-04-26, scan pending Zahi**

   **Setup done:**
   - Docker Desktop installed via brew, daemon running
   - Shannon Lite cloned to `~/shannon`
   - Anthropic API key created and saved via `npx @keygraph/shannon setup` (config at `~/.shannon/config.toml`)
   - Custom config for BrikOps staging at `secrets/shannon-config.yaml` (gitignored): super_admin email login, focus paths on /api/users + /api/companies + /api/tasks + /api/auth + /api/defects + /api/webhooks/whatsapp, avoid logout + account deletion + payment endpoints, retry_preset=subscription + max_concurrent_pipelines=2 (rate-limit safe)

   **Run command (Zahi to execute when home, ~30-60 min):**
   ```bash
   sudo pmset -a sleep 0 displaysleep 60          # prevent Mac from sleeping
   mkdir -p ~/brikops-new/secrets/shannon-reports-2026-04-26

   cd ~/shannon
   npx @keygraph/shannon start \
     -u https://staging.brikops-new.pages.dev \
     -r ~/brikops-new \
     -c ~/brikops-new/secrets/shannon-config.yaml \
     -o ~/brikops-new/secrets/shannon-reports-2026-04-26 \
     -w brikops-staging-first-scan
   ```

   Monitor (optional): `open http://localhost:8233` (Temporal Web UI)
   Stop: `npx @keygraph/shannon stop`
   Resume: same command (Shannon detects partial workspaces and resumes from checkpoint)

   **Cost:** ~$40-55 in Anthropic API credits (Zahi has $70 loaded — ~$15-30 will remain)

   **After scan:** report goes to `secrets/shannon-reports-2026-04-26/`. Triage findings vs. existing pentest report (2026-04-22). Then run local `brikops-pen-tester` skill as second-pass check.

   What shipped (commit `cef882d` on main, merged to staging as `d9a2561`):
   - `deploy.sh` accepts `--stag` flag (`--stag` or `--staging`), enforces staging branch, sets FRONTEND_BACKEND_URL=https://api-staging.brikops.com at build time
   - New workflow `.github/workflows/deploy-backend-staging.yml` deploys to `Brikops-api-staging-env` on push to `staging` branch (Docker tag: `staging-latest`, version label: `staging-${sha}`)
   - Standard workflow now: edit code → `./deploy.sh --stag` → manual test on staging → `git merge staging into main` → `./deploy.sh --prod`
4. Phase 4: Frontend Cloudflare Pages staging branch + `staging.brikops.com` + red banner (20 min)
5. Phase 5: Update `deploy.sh` to support `--staging` flag (15 min)
6. Phase 6: First end-to-end test of staging flow (30 min)
7. Phase 7: Shannon (Keygraph) pentest setup + first scan (60 min)

**Phase 1 — what shipped (2026-04-26):**
- ✅ EB env `Brikops-api-staging-env` (eu-central-1, single-instance t3.small, Docker on AL2023)
- ✅ Internal URL: `Brikops-api-staging-env.eba-umpxaxyw.eu-central-1.elasticbeanstalk.com`
- ✅ EIP: `52.57.45.124`
- ✅ Running version `98c08a076b1fdcec0f30b8a3455ce3b58a192392` (S5b + config.py staging fix)
- ✅ APP_MODE=staging, DB_NAME=brikops_staging (empty DB, isolated from prod)
- ✅ Fresh secrets (JWT, META, CRON) different from prod
- ✅ CORS validators: accept staging origin, reject prod + evil
- ✅ All payment/SMS calls disabled (PayPlus sandbox+placeholder, Twilio test, SMS_MODE=stub)
- ✅ 9 demo accounts seeded (5 general + 4 reviewer org), all using password `StagingDemo2026!`
- ✅ Demo data: 1 project, 30 units, 16 defects, 3 companies, 165 QC items
- ✅ Hotfix #424 deployed to prod (config.py accepts 'staging' as valid APP_MODE — zero behavior change for prod)

**Phase 1 — credentials & operational docs:**
- 🔐 [`secrets/staging-demo-credentials.md`](computer:///Users/zhysmy/brikops-new/secrets/staging-demo-credentials.md) — 9 accounts, login methods, Shannon-ready accounts.yaml (gitignored)
- 🔐 `secrets/staging-secrets.env` — JWT/META/CRON/WA secrets (gitignored)
- 🔐 `secrets/eb-snapshots/prod-baseline-2026-04-25.json` — recovery snapshot (gitignored)

**Tooling:**
- ✅ EB CLI installed cleanly via AWS official installer (avoiding brew Python issues) — `~/.ebcli-virtual-env/bin/eb`

**Total: ~3.5 hours focused work**

**Critical safety items not in plan but MUST be added:**
- Separate secrets per env: `JWT_SECRET`, `META_APP_SECRET`, `PAYPLUS_*`, `GREEN_INVOICE_*` MUST be different in staging vs prod. Otherwise a leak in staging compromises prod.
- Visual differentiation: red banner + custom favicon + `[STAGING] BrikOps` document title — prevent "wrong env" confusion.
- `CORS_ORIGINS` for staging must include `https://staging.brikops.com`.

**Shannon (Keygraph) pentest tool:**
- AI-powered pentester using Claude Agent SDK, ~96% benchmark recall
- White-box mode (requires repo access — we have it)
- Real exploits (not just "maybe vulnerable")
- Cost: ~$50/run vs ₪10-30k for human pentest
- **MUST run on staging only** — performs actual exploits, can damage data
- First run validates all S-batches end-to-end
- Follow-up: quarterly runs as part of release routine

**Staging serves 3 purposes long-term:**
1. Pre-prod deploy validation (catch regressions before prod)
2. Shannon pentests (safe exploit environment)
3. Customer demos / Apple reviewers (without polluting prod data)

---

### 🚦 Pre-public-launch gate (CRITICAL — added 2026-04-25)

Both stores approved BrikOps. Zahi controls release timing. **Before clicking "Release" on either store, the following security batches MUST ship to prod:**

| Batch | Status | Why blocking |
|---|---|---|
| S1 (CRIT) | ✅ Shipped | PII cross-tenant — would be GDPR/חוק הגנת הפרטיות violation under public traffic |
| S2 (HIGH) | ✅ Shipped | Tasks cross-tenant leak |
| S5a (CRIT — webhook idempotency) | 🟡 In progress | Audit trail integrity; pre-public framing changes once paying customers exist |
| S5b (HIGH — TOCTOU + CORS) | ⏳ Next | Signature bypass + cookie leak in non-prod |

**Recommendation:** finish S5a today, S5b tomorrow, then release.

The pre-launch framing in S1/S2/S5a specs ("internal testers only, no breach notification") is **about to expire** the moment Zahi hits Release. Plan accordingly.

### Closed-beta polish remaining
- **Batch 3 — Team member tagging on defect** (CC-style — mention someone inside a defect's thread)
- **Batch 4 — Contact picker** (native plugin — requires `./ship.sh` + Apple/Google review)
- **Batch 5 — UX bug pack from manual S6 testing** ✅ **CLOSED — shipped in 8 waves over 2026-04-28/29:**
  - ✅ Wave 1 (Batch 5, task #437) — Reopen button, list refresh in ProjectTasksPage, Trade required on company create
  - ✅ Wave 2 (Batch 5B, task #439) — Reopen modal (replace window.confirm), UnitDetailPage refresh, companies state dedupe
  - ✅ Wave 3 (Batch 5C, task #442) — REAL fix for "closed defect appears open" via status='approved' alignment across 12 files
  - ✅ Wave 4 (Batch 5F, task #442) — Architectural fix: STATUS_BUCKET_EXPANSION single source of truth + drift-guard test
  - ✅ Wave 5 (Batch 5G, task #447) — Dashboard simplification (5 cards, not 6), i18n he.json אושר→סגור, KpiCard tooltip
  - ✅ Wave 6 (Batch 5H, task #448) — Smart back from /control to /dashboard via ?from=dashboard URL-param convention + breadcrumb
  - ✅ Wave 7 (Batch 5I, task #449) — Handover + OrgBilling broken `/projects/:id` route pattern fixed (2 files, bonus regression sweep eradicated bug class)
  - ✅ Wave 8 (Batch 5K, task #451) — BuildingQC back to /qc when arriving from there (?from=qc convention, 2 files / 4 sub-edits)
  - ✅ Bonus (Phase 1A docs, task #450) — 8 ADRs + 21-item refactor backlog + CLAUDE.md extension (96KB architecture documentation, ZERO code changes)
  - 📋 Spec ready (next) — Batch 5J (OrgBilling 3 back buttons honor sourceProjectId, 1 file)
  - 📋 Pending — handover_router:2336 $nin missing 'done' (Task #27, pre-existing latent bug surfaced during 5C audit)
  - 📋 Post-launch — force_close → aggregation → reopen regression test suite (Task #28, 4 tests; downgraded from BLOCKING per Zahi 2026-04-29 since the actual bugs are fixed in prod and ADR-006+SKILL.md updates document the prevention pattern)
  - ⏸️ Deferred — UserDrawer 3 native `<select>` escape (Desktop-only, mobile WebView fine; Task #21)
  - ⏸️ Deferred — Dashboard back-navigation architectural split (`/control/defects` as own route) — see "Architectural debt" entry below; 5H/5I/5J/5K are tactical band-aids in current architecture

### 💡 Field feedback queue (2026-05-11 — Zahi)
Feature requests / enhancements surfaced by Zahi from real-world use on plot 810 after Plans P1.1 + Batch A+C+D shipped. Not specced yet; queued for prioritization against Phase 1.2+ and existing big-features list.

- **📸 Photo annotation: text labels (in addition to freehand drawing)** — `PhotoAnnotation.js` today supports only freehand strokes in 3 colors (אדום/כחול/שחור). Zahi wants to tap a spot on the photo → input prompt opens → text renders as a clean pill (white rounded background, ~16-20px Hebrew text, see screenshot 2026-05-11 with "5/27" pill above defect circle). Use cases: labeling defect numbers (5/27 = "defect 5 of 27 on this floor"), marking measurement values, calling out specific apartments/floors in shared photos. **Decision 2026-05-11**: ship as STANDALONE batch (not folded into P1.4 — Plans-phase work is thematically separate from defect-photo work). Sequenced after Batch E ships clean. Code analysis: existing `PhotoAnnotation.js` cross-platform pitfalls already solved (viewport lock, passive event listeners, scale compensation, separate touch+mouse paths) so adding text mode doesn't risk reopening the iPhone↔Android wars from earlier. Main remaining risk = Hebrew text rendering on canvas (font fallback differs iOS vs Android) — mitigation via explicit font-family `"Heebo", "Arial Hebrew", "Noto Sans Hebrew", system-ui, sans-serif`. Implementation sketch: extend `strokes` state to include `type: 'text' | 'stroke'` discriminator + "T" tool button + inline overlay input (not `prompt()`); on save, render text into the same canvas-blob (raster, no schema change). Scope estimate: ~120-150 LOC frontend, single file, ~3-4 hours dev + cross-platform smoke. **v1 scope:** tap-then-text + pill rendering + color from existing picker + undo support. **OUT of v1:** edit/move/delete after placement, multi-line text, font size picker (these would require vector storage instead of raster blob, separate batch if requested).

- **🐛 WhatsApp on-close: stop notifying contractor when defect is closed** — Zahi reminded 2026-05-11; previously logged in "longer-tail backlog" L69 but never given a dedicated entry. **The bug:** when PM closes a defect, the system sends a WhatsApp notification to the contractor that includes the very photo the contractor uploaded as proof of fix. Confusing + zero value (contractor knows they uploaded it). **Decision (Zahi 2026-05-11): Option B — skip notifying the contractor entirely on close events.** Rationale: "אין צורך לעדכן אותו על סגירה זה סתם מציף בהודעות ווטסאפ" — contractor's work is done, additional WA just adds noise. **KEEP notification on REJECT/REOPEN events** (when PM rejects the proof photo and re-opens the defect): contractor still needs to know to come back. **Investigation needed:** find the close-defect dispatch path (likely `tasks_router.py` close endpoint calling `notification_router.py` event handler OR `reminder_service.py` direct WhatsApp send). Confirm reject-path remains separate. **Scope estimate:** ~10-20 LOC backend, 30 min investigation + 1 hour fix + tests. **No WA template change needed** (we're removing a send, not modifying message content) — no Meta re-approval cycle. Standalone batch after Batch F.

- **📱 WhatsApp links: app deep-link first, browser fallback (Stream B) — DEFERRED** — Zahi reminded 2026-05-11; ALREADY DOCUMENTED in detail at "Big features planned → 5. WhatsApp + Mobile Native Bundle → Stream B" (L705-810). **Decision (Zahi 2026-05-11): defer.** Rationale: "אפשר לדחות קצת את הווטסאפ לינק" — current state works (WA → browser → app via webview), UX gap is real but not blocking. Better to invest the 1-2 weeks + Apple/Google review elsewhere right now. **Revisit triggers:** (a) paying customer explicitly asks for native deep-link, (b) contiguous 2-week dev window opens with no higher-priority work, OR (c) bundled together with another native release that's already planned (Contact Picker, push notifications, etc.). Stream B docs remain at L705-810 — when re-prioritized, no spec re-write needed.

- **📂 Multi-file plan upload + iOS document scanner (#35)** — Zahi raised again 2026-05-11 (was originally in task #35 but only mentioned in passing in queued list — surfacing prominently here). **Two requirements bundled:**
  1. **Multi-file selection.** Today the upload modal at `מבנה > תוכניות > +` accepts ONE file (`<input type="file">`). PMs uploading a set of related plans (architecture sheet + electrical sheet + plumbing sheet for the same floor) have to repeat the upload 3 times — pick file, fill domain/type/name, upload, repeat. Want: select N files at once, then iterate through metadata for each (or apply same metadata to all).
  2. **iOS document scanner integration.** Today must take a photo via the camera button OR pick from photos. Want: native iOS document scanner (the one in Notes app — auto-detects edges, deskews, multi-page) so PM can grab a printed plan from the contractor and scan it cleanly without leaving BrikOps. Apple `VNDocumentCameraViewController` API exposed via `@capacitor-community/document-scanner` plugin. Android: `MLDocumentScanner` via the same plugin (works on most modern devices). Requires native build (`./ship.sh`) — same gate as Stream B.

  **Scope assessment:**
  - Multi-file UI: ~80-150 LOC frontend (`<input type="file" multiple>` + iterate metadata form). NO backend change required if we keep one-plan-per-row semantics. ~3-4 hours.
  - Document scanner: ~50 LOC frontend + 1 native dependency install + 1 ship.sh. Plugin maintenance status needs verification during spec. ~1 day work + 1-2 days for Apple/Android review.
  - **Bundle implication:** the scanner part REQUIRES native release. If we ship multi-file alone (OTA, no scanner), it's lower-risk and field-test ready immediately. If we bundle the scanner, we need to wait for one of the native release windows (currently planned: Stream B + Contact Picker).

  **Recommendation:** Split into two batches:
  - **Multi-file (OTA only, soon)** — ship right after Batch F/G complete the field-feedback sweep. Removes the biggest friction (the repeated upload).
  - **Document scanner (native bundle, deferred)** — fold into the next native release whenever it happens (either standalone if Stream B never triggers, or bundled with Stream B when it does).

### Known follow-ups (not yet in any batch)
- **Email cancellation message localization** — backend currently returns `"Authentication failed"` in English. Hebrew fallback needed for full UX consistency. Trivial 1-line fix when prioritized.
- **State card UX polish** — text in the new cancellation card is small / not bold enough per Zahi feedback 2026-04-28. UI polish batch candidate.
- **Comped sub state hidden by default** — comped/auto_renew=false subs now show "מנוי פעיל" without cancel button. Functionally correct; consider whether to surface anything actionable for these orgs.
- **deploy.sh branch lock friction** — `./deploy.sh --stag` errors when current branch is `main` (Replit's default checkpoint branch). User must manually `git checkout staging && git merge --ff-only main` before every staging deploy. Multiple times per day during active dev. Future improvement: auto-detect Replit's source branch and ff-merge into the target deploy branch.
- **`approved` vs `closed` status pattern audit** — Bug B in Batch 5C exposed that 8 places (5 backend + 3 frontend) silently treated 'approved' as non-terminal. Should add a `git pre-commit` hook or test that fails when a new status map adds 'closed' without 'approved'. Tech-debt task.
- **🧹 Working principle: Boy Scout opportunistic cleanup** — Per the [Codebase Refactor Plan](computer:///Users/zhysmy/brikops-new/docs/strategy/codebase-refactor-plan.md), when a batch is already touching a file, propose folding in a small refactor-backlog item from the same file. Never run standalone "refactor sprints." Never refactor without tests as a safety net. Document-first, refactor-second.
- **💾 Working principle: Backup reminders** — Per Zahi's standing ask 2026-04-30, Claude proactively reminds Zahi to take a snapshot backup before:
  - **Public launch** or any major milestone (major version bump, first paying customer push, regulatory deadline)
  - **Big architectural refactors** (e.g. ProjectControlPage extraction, /control split, DB schema change)
  - **Risky operations** (data migration, mass-deletion, retention rule changes, secrets rotation)
  - **After heavy dev clusters** — when 5+ batches shipped in a short window without a snapshot in between (e.g. the Batch 5/5B/5C/5F/5G/5H/5I/5J/5K cluster of 2026-04-28/29/30)
  - **Periodic** — at least once a month during active dev, even if no specific trigger
  Backup procedure: tag the prod commit (`git tag -a vX.Y-name -m "..." && git push origin vX.Y-name`) AND download a zip archive to external storage (Drive/iCloud/Mac). Both steps — GitHub tag is fast/free protection, external zip is real defense against GitHub-wide failure. Pre-launch snapshot taken 2026-04-30 = `v1.0-prelaunch` tag + zip on Zahi's Mac.
- **🏗️ Architectural debt — defects/structure share `/control` route while handover/QC have dedicated routes** — Discovered 2026-04-29 during 5H smoke test. The "ליקויים" and "מבנה" tabs are toggled via `?workMode=defects` vs `?workMode=structure` on the same `/control` route, while "מסירות" lives at `/handover` and "בקרת ביצוע" at `/qc`. Consequence: back-button behavior on `/control` can't distinguish between "user came from dashboard to view defects" vs "user came from dashboard to view structure" without query-param hints, leading to UX confusion that 5H tried to patch but hit edge cases. Proper fix would be to split `/control` into `/control/structure` + `/control/defects` (or `/defects` as a top-level route like `/handover`). Major refactor — explicitly NOT for pre-launch. Filed for post-launch consideration when paying customer feedback validates the priority.
- **🐛 P2 — Handover (`/handover`) back arrow goes to `/projects` instead of `/control` (מבנה)** — Discovered 2026-04-29. Same family as the dashboard→KPI→back issue. The handover page's header arrow always exits to project list. Should arguably return to `/control?workMode=structure`. Filed but not blocking — Zahi explicitly does not want to touch back-navigation again until product-level decision on architecture above.
- **🐛 P2 UX — Dashboard → KPI → no natural back to dashboard** — Status: 5H shipped a partial fix (smart back arrow + breadcrumb when `from=dashboard` in URL) but Zahi 2026-04-29 explicitly chose to STOP work in this area. The header back arrow continues to behave inconsistently across `/control`, `/handover`, `/qc` due to the architectural debt above. Re-evaluate post-launch.
- **🐛 P1 — "מנוי פג תוקף" banner + API blocking shown to PM users globally instead of per-org context** — Discovered 2026-04-28. **Investigation completed 2026-04-30** (Task #32): root cause confirmed = `get_effective_access(user_id)` is scope-blind, reads first org membership without ordering. **All 3 paywall layers** (`server.py:1346` middleware, `router.py:446` Depends(), `router.py:461` _check_paywall) call it without `org_id` → wrong org's status wins → both banner shown AND API actions blocked in the active org's projects. **Investigation also surfaced a sibling silent-revenue-leak bug**: `project_billing.status='cancelled'` reduces `recalc_org_total` correctly, but no code blocks edit access on a cancelled project — org keeps full read+write on something they stopped paying for. **Both bugs share the same architectural fix** (scope-aware `get_effective_access`). Full plan, scope, pytest matrix, and rollout strategy documented under [Big features planned → 4. Scope-aware paywall](#4-scope-aware-paywall--multi-org-pm-bug-fix--per-project-access-lock). Split into 2 batches (org_id first, project_id later — each independently shippable, each with feature flag for instant rollback). NOT urgent — no live customer hit. Re-evaluate when customer count grows or comping-projects becomes a sales motion.

### <a name="batch-s75--deferred-payment-webhook-fixes"></a>📋 Batch S7.5 — Deferred payment webhook fixes
**Status:** Spec not yet written. Pending zero-cost test strategy.

**Scope (Shannon HIGH-C + HIGH-D — deferred from S7 on 2026-04-27):**
- HIGH-C — PayPlus webhook HMAC bypass via `User-Agent: PayPlus` short-circuit + silent 200 on hash mismatch
- HIGH-D — GreenInvoice webhook auth skipped when `GI_WEBHOOK_SECRET` unset + token check after early-return branches

**Why deferred:** payment webhooks are fragile production paths; first attempt would have required real PayPlus / GreenInvoice transactions to test, which costs real money and accountant fees. Both endpoints have residual exploitability risk (attackers must guess our specific webhook URLs first), so deferring is acceptable.

**Test strategy required before this batch:** synthetic HMAC replay using saved `PAYPLUS_SECRET_KEY` + previously-logged `payplus_webhook_log` raw bodies. No live payment needed.

**Tracking tasks (also in TodoList):**
- #12 — Webhook correlation drift (PayPlus/GI race condition on overlapping checkouts)
- #13 — `manual_override` silently beats `founder_plan` (sales rep override would charge more than ₪499 to a customer expecting founder pricing)

---

## 🚀 Big features planned

### 0. Handover PDF Phase 4 — QR Verification + 7-Year Retention Hardening
**Why:** Phase 1 (visual + schema) and Phase 2/3 (polish + ID photo) shipped 2026-04-30. Two follow-ups deliberately deferred.

**Sub-feature 4a — QR Verification (when triggered):**
The QR code in every protocol currently shows "בקרוב" placeholder. Three implementation tiers:

| Tier | Effort | Value |
|---|---|---|
| **Basic** — QR → `brikops.com/p/{id}` → page showing protocol metadata pulled from API | 1-2 days | Traceability only, no anti-tampering |
| **Medium** — QR + hash in URL → `/api/verify/{id}?h=...` endpoint compares hash against `pdf_attestations` collection | ~1 week | Detects tampering at generation time — 80% of court value |
| **Full** — Medium + S3 Object Lock (Compliance mode) for immutable storage of original PDF | 2-3 weeks | Court-grade evidence, even AWS account compromise can't modify |

**Recommendation:** Medium tier. Basic too weak (no proof), full too expensive without explicit legal driver.

**Trigger:** Customer/developer request for verifiable handover, OR forgery incident, OR consultation with construction-law attorney.

**Sub-feature 4b — 7-Year Retention Hardening:**
Israeli construction handover protocols often need 7-year retention (regulatory + civil-suit window). Current state vs. gaps:

✅ **Live today:**
- MongoDB Atlas M10 with Continuous PITR backup, 3-min RTO
- S3 `brikops-prod-files` (Frankfurt) with Versioning ON
- S3 Cross-Region Replication → `brikops-prod-files-backup-ireland` (eu-west-1, Standard-IA, ~$2.70/mo)
- **Delete-marker replication: OFF** — most critical setting; delete in Frankfurt does NOT propagate to Ireland (ransomware-proof)
- DR runbook in `memory/BrikOps-DR-CRR.md`

⚠️ **Gaps for full 7-year compliance:**

| Gap | Risk | Fix | Effort |
|---|---|---|---|
| Atlas cross-region retention 1 day (should be 7) | If both regions fail simultaneously, lose last week of meta | Atlas Backup Policy edit | 30 min |
| **S3 Object Lock (WORM/immutable) missing** | Malicious admin or compromised AWS account could delete bucket itself | New bucket with Compliance mode + migration | 1-2 weeks |
| Lifecycle to Glacier after 2 years | Storage cost grows with no benefit | S3 console rule | 1 day |
| Code-level retention rule on `handover_protocols` | No enforcement (`archive_router` has hard-delete after 7 days in archive — same model could enforce 7-year minimum) | Mirror `INCIDENT_RETENTION_YEARS = 7` from `safety_router.py` | 1-2 days |
| `/admin/audit/deletes` endpoint | No tool to identify who deleted what (mentioned in DR doc as pending) | New admin endpoint | 2-3 days |

**Trigger:** Customer/developer asks for retention guarantee, OR first ≥100 protocols in prod, OR pre-court-case audit.

**Status:** Spec not yet written for either. Both are trigger-driven — system is stable and adequate for current scale.

**Sub-feature 4c — G4 Excel import: extend to ID number + property fields:**
The G4 (Gindi) Excel import on /handover currently auto-fills tenant `name`, `phone`, `email` per protocol — eliminating manual typing for tenant info across hundreds of units. **Outstanding columns NOT yet mapped:**

| Column to add | Target field | UX impact |
|---|---|---|
| ת.ז (ID number) | `tenant.id_number` | Eliminates manual typing of ID for every tenant; also feeds the tenant ID photos flow (Phase 2 ID upload) |
| מספר חדרים | `unit.rooms` | Currently typed manually per protocol in "פרטי נכס" |
| מספר חניה | `unit.parking_number` | Same — manual today |
| מספר מחסן | `unit.storage_number` | Same — manual today |

**Why:** A typical project has 50-200 units. Each missing column = 50-200 manual typing actions per import cycle. ID + 3 property fields = 200-800 fewer typing actions per project, plus eliminates typos in legally-significant data (ID numbers in particular).

**Scope:**
- Extend the G4 Excel parser to detect these 4 additional columns by header (Hebrew + English aliases)
- For ID: write to `tenant.id_number` (already exists in DB after handover Phase 1)
- For room count + parking + storage: write to corresponding unit fields (verify they exist; add to schema only if missing)
- Backwards-compatible: missing columns in Excel don't break import, just leave fields blank
- UI: show a confirmation modal listing what was auto-filled vs left blank, so user can spot-check before commit

**Effort:** ~1-2 days (parser extension + UI confirmation + tests). Low risk — existing G4 importer already handles the column-detection pattern.

**Trigger:** Either (a) Zahi prioritizes pre-launch QoL, OR (b) first paying customer with >50 units reports the manual typing pain.

**Status:** No spec yet. Documented here so it doesn't get lost.

---

### 1. Safety Phase 2 — Close the 75% gap to Cemento parity
**Why:** Phase 1 is ~25% of what Cemento offers. PM feedback during closed-beta shows we need to go further.

**Scope (high-level):**
- Full incident management workflow (open → investigate → report → close)
- Safety officer role + hierarchy
- Multi-organization safety scoring
- Regulatory compliance exports (ministerial forms)
- Inspection scheduling + reminders
- Near-miss tracking
- Safety training records per contractor
- Deep-link to OSHA-style investigation templates

**Status:** Spec not yet written. Mockups v1-v3 exist in `future-features/safety-phase-1-mockup-*.html`. Concept in `future-features/safety-and-worklog-concept.md`.

---

### 2. Vision AI Phase 1 — Auto-fill defects from photo
**Why:** Field users complain that typing defect title/description/category slows them down. A photo should ideally auto-populate those fields.

**Scope (high-level):**
- Vision API integration (Claude, GPT-4V, or custom fine-tuned model)
- On photo upload → suggest: category, title, description, severity
- User reviews and edits suggestions before saving
- Confidence score displayed
- Fallback: if AI fails or user rejects suggestions, manual flow unchanged

**Status:** Spec not yet written. Task #27 pending. Privacy + cost analysis needed before spec.

---

### 3. AI Assistant — opt-in add-on for PMs

**Framing (the real moat):** The LLM is a commodity (Claude/GPT/Bedrock). The moat is **BrikOps' data model** — defects × categories × trades × contractors × timelines × handover protocols. An assistant that speaks natural Hebrew over THAT data is something Cemento/PlanRadar can't copy in 6 months because they don't have it wired the same way. Position as "your data + AI", not "BrikOps has AI now".

**V1 scope (just 2 surfaces — NOT all 5 from the original concept):**
1. **Chat widget** — FAB (floating action button) on every page. PM asks natural-language questions about the project ("כמה ליקויים פתוחים בדירה 8?", "מה הסטטוס של קבלן הריצוף?"). Answers come with real numbers from the DB, formatted in Hebrew.
2. **Daily briefing** — shown when the PM opens the app in the morning (not push-notified at a fixed hour — respects each PM's workflow). 3-5 lines: urgent items, bottleneck contractor, positive movement. PM can dismiss or click into an item.

**Deferred to V2 (only if V1 proves adoption):**
- Risk predictor (and only if we make it actually smart with trend analysis, not just "close rate dropped 40%" templates — statistical anomaly doesn't need an LLM)
- Weekly report (templateable, low AI value-add)
- Decision support ("should we hand over next week?") — subset of chat, not separate
- Onboarding walkthrough — not really AI, just stats + 3 buttons

**Pricing model (TBD — 3 paths):**
- **Path A — higher add-on:** ₪399-499/month add-on, covers API + margin + support overhead. Net margin ~30%.
- **Path B — model mix:** Haiku for simple Q&A ($0.001/query), Sonnet only for briefings. 10× cheaper. Can sustain ₪250 add-on with decent margin.
- **Path C — smaller scope first:** Chat-only V1 at ₪149 add-on, expand to ₪399 tier when briefings ship.

Decision before Phase 1 spec. Needs actual cost benchmark, not estimates.

**Privacy / compliance (gate before any code):**
- ⚠️ Hebrew defect descriptions can contain PII ("דירת משפחת כהן"), contractor names, informal PM notes. NOT safe to send unfiltered to external LLM.
- Requires: DPA with customer, DPO or legal review, anonymization layer (strip names → "הדייר"), possibly Enterprise tier on AWS Bedrock for data residency.
- חוק הגנת הפרטיות compliance — specific call to a lawyer, not my judgment.

**Success metrics (define before building):**
- North star: Weekly Active AI Users (WAAIU) — % of AI-enabled PMs using the chat at least 1×/week
- Quality: thumbs up/down per answer, weekly quality score
- Business: AI add-on churn rate vs. base plan churn rate
- Retention proxy: is AI usage correlated with overall BrikOps retention?

**Hebrew quality benchmark (precondition):**
- 50 real queries from closed-beta PMs, evaluated by Zahi + one external domain expert
- Construction Hebrew jargon: שלד, גמר, ריצוף, טיח רבוד, ארגזים, מסד — must be handled accurately
- Run this BEFORE spec, not after. If Hebrew quality is bad, entire plan changes.

**Phased rollout (inverted from the original concept):**
- **Phase 0 — Scrappy MVP (2 weeks):** Chat only, 5 hand-picked closed-beta customers, no billing, no rate limits. Goal: learn what questions PMs actually ask and whether they keep asking after week 1. If usage tanks → cancel everything, save 7 weeks.
- **Phase 1 — Real foundation (3 weeks, only if Phase 0 shows adoption):** Backend AI service, context builder, usage tracking, billing add-on, project-level settings. Based on what Phase 0 taught.
- **Phase 2 — Daily briefing (1 week):** Morning briefing when PM opens the app.
- **Phase 3 — Scale & polish:** Caching, rate limits, analytics dashboard for admin, onboarding flow.

**Explicitly NOT in V1:**
- Offline mode — AI requires network. Documented limitation. User sees "אין חיבור" if offline.
- Risk predictor — defer until we can do it properly (real trend analysis, not templates).
- Voice input — nice-to-have, wait for demand signal.

**Competitive positioning:**
- NOT "Cemento alternative" (price-based framing → race to bottom)
- YES "premium differentiator" (value-based framing → holds margin)
- Pitch line: "אתה לא שוכר עוד SaaS. אתה שוכר מישהו שעובד 24/7 על הפרויקט שלך."

**Status:** Concept drafted, improved version in this roadmap. Full spec NOT written yet. Task #28 pending. 

**Open decisions before spec:**
1. Phase 0 scrappy MVP — approved? (my strong recommendation: yes)
2. Pricing path A/B/C?
3. Model: Haiku, Sonnet, mix, or Bedrock?
4. Hebrew benchmark timing — who runs it, when?
5. Privacy: who's the legal reviewer?
6. Success metric — North star definition?

---

### 4. Scope-aware paywall — multi-org PM bug fix + per-project access lock
**Why:** Discovered during Task #32 investigation 2026-04-30. The current `get_effective_access(user_id)` function is **scope-blind** — it picks the FIRST org membership found via `db.organization_memberships.find_one({'user_id': user_id})` without ordering, then returns access based on that org's subscription. Two real consequences:

1. **Multi-org PM bug (#32)** — A PM who belongs to Org A (trial expired) and is invited as PM to Org B (paid) will see "מנוי פג" everywhere AND get blocked from API actions in Org B's projects. The 3 paywall layers (`server.py:1346-1380` middleware, `router.py:446-453` Depends(), `router.py:461-472` _check_paywall) all call `get_effective_access(user['id'])` without `org_id`, so the wrong org wins.
2. **Silent revenue leak (per-project)** — Today `recalc_org_total` (`billing.py:1362`) already excludes `project_billing.status != 'active'` from the org's monthly total. So in theory you can mark one project as `cancelled` and the org pays less. BUT — there is NO code anywhere that blocks edit access to a `cancelled` project. The org keeps full read+write on a project they stopped paying for. Nobody who discovers this will report it; they'll just exploit it silently.

**Architecture:** Both bugs share the same root — `get_effective_access` needs to be **scope-aware**. Optional `org_id` parameter (Batch 1) and optional `project_id` parameter (Batch 2). Default behavior preserved when params not passed (so legacy single-org single-project users see zero change).

**Split into 2 batches per Zahi 2026-04-30** (so if something breaks in prod we know which fix caused it; staged rollout 3-4 days apart).

#### Batch 1 — Backend scope-aware paywall (org_id) — fixes #32

**Scope (~30-40 lines backend, zero frontend):**
- `get_effective_access(user_id, org_id=None)` — when `org_id` provided, look up THAT org's subscription instead of falling back to `get_user_org()`. When not provided, behavior stays identical to today.
- `server.py:paywall_middleware` — extract `org_id` from request context (URL path `/projects/{id}/...` → look up `project.org_id`; or `/billing/org/{id}/...` → direct; or request body `{org_id}`). Pass to `get_effective_access`.
- `router.py:require_full_access` Depends() — same context extraction.
- `router.py:_check_paywall` helper — same.
- New PAYWALL_EXEMPT_PATHS not needed; existing GET-only exemption still applies.

**Required pytest coverage (Replit MUST add, do not skip):**
- User with 2 orgs (A=expired, B=paid) → POST to project in A → 402 ✓
- Same user → POST to project in B → 200 ✓
- User with no orgs → no `org_id` resolvable → existing fallback behavior ✓
- User with 1 org (paid) → no regression vs today ✓
- User with 1 org (expired) → still blocked everywhere ✓
- Founder plan + comped + manual_override → all preserved ✓

**Logging requirement:** every paywall decision logs `user_id`, `resolved_org_id`, `decision`, `reason` so production debugging works without reproducing locally.

**Feature flag:** `PAYWALL_SCOPE_AWARE_ENABLED` env var → if false, function ignores `org_id` param and behaves like today. One Render dashboard toggle for instant rollback.

#### Batch 2 — Per-project access lock + UI (after Batch 1 stable)

**Scope (~20 lines backend + medium frontend):**
- Backend: `get_effective_access(user_id, org_id=None, project_id=None)` — when `project_id` provided, after resolving org-level access, ALSO check `project_billing.status` for that project. If `cancelled` → force `read_only` regardless of org status.
- Backend: paywall layers extract `project_id` from URL when present.
- Backend exempt list (do NOT block these even when project cancelled):
  - `PATCH /billing/project/{id}` — must be able to UN-cancel (set status='active' again)
  - `GET /handover/protocols/{id}/pdf` — customer paid for the protocol, deserves the PDF
  - All `GET *` — already covered by existing GET exemption
- Frontend: `BillingContext.fetchProjectBilling` already exists at `BillingContext.js:60`. Add derived `projectAccess` state. When inside a project route, `useBilling()` returns project-scoped access.
- Frontend: `TrialBanner.js` adds project-scoped variant — red banner "פרויקט סגור — צפייה בלבד" + reopen button (if user has billing role).
- Frontend: action buttons across project pages check `useBilling().projectAccess === 'read_only'` and show disabled state with tooltip "פרויקט סגור לחיוב".
- New UI element: in project settings, "סגור פרויקט וסיים חיוב" button + confirmation modal warning ("הפרויקט יישאר זמין לצפייה אבל לא תוכל לערוך אותו. הארגון יחויב פחות החל מהמחזור הבא").

**Required pytest coverage:**
- Org paid + project active → full access ✓
- Org paid + project cancelled → read_only on cancelled, full access on others ✓
- Org expired + project active → read_only (org wins, higher scope) ✓
- Newly created project without project_billing record → treat as active (legacy compat) ✓
- Founder plan (1 project allowed) → status changes work ✓
- `recalc_org_total` rerun after status flip → total decreases by exactly that project's monthly_total ✓

**Same logging + feature flag pattern as Batch 1.**

#### Compensating for "I can't physically test multi-org/multi-project scenarios"

Zahi flagged 2026-04-30 that he can't easily reproduce these edge cases (requires manual setup of test users with 2 orgs, etc.). Mitigations baked into both batches:
1. **Pytest is mandatory, not optional** — Replit cannot ship without all listed tests green.
2. **Structured logging** — every paywall decision is grep-able in Render logs (`grep paywall_blocked`).
3. **Feature flag for instant rollback** — no need for a hotfix deploy if something breaks.
4. **3-4 day staging bake** — even though staging traffic is mostly Zahi, that's still real exercise of the path.
5. **Counter for blocked requests** — if `paywall_blocked` rate spikes after deploy, sign of false positives.

**Status:** Documented 2026-04-30. NOT urgent — no live customer reported either bug. Plan to ship Batch 1 first when post-launch capacity allows; Batch 2 only after Batch 1 stable in prod 3-4 days. Both batches tracked under Task #32.

**When to prioritize:** before paid customer #5 (multi-org likelihood rises with adoption) OR before any sales motion that involves comping a project (per-project lock becomes operationally needed).

---

### 5. WhatsApp + Mobile Native Bundle — 3 streams
**Why:** Discovered through Zahi's recall 2026-04-30 of two pending items not previously documented (apologies — they only existed verbally). Investigation uncovered a logical 3-stream workplan that maximizes shipped value while minimizing native release frequency.

**The two original problems:**

1. **Contractor reminder flood** — `reminder_service.py:send_contractor_reminder` currently sends ONE WhatsApp message per defect, capped at 5 per batch. A contractor with 100 open defects gets up to 5 messages per project per day, every day. With multiple projects → noise that breaks trust. Plus the link inside is broken (Zahi confirmed).
2. **WhatsApp link → browser only** — both the daily contractor reminder AND the per-defect template (when PM opens a defect) currently route to `https://app.brikops.com/tasks/{id}` which always opens in the device browser, even when the user has the BrikOps app installed. Web works great (Zahi confirmed). Native deep-link is the gap.

**The 3-stream plan (split for risk isolation):**

#### Stream A — Contractor Reminder Digest — ✅ SHIPPED to prod 2026-05-01 (Batch 6A v2, Replit task #464)

**What was built (6 files, 14 pytest tests, all green):**
- `backend/config.py` — added `WA_REMINDER_DIGEST_TEMPLATES` dict (4 langs: he/en/ar/zh) + `WA_REMINDER_DIGEST_DEFAULT_LANG = 'he'`. Existing `WA_REMINDER_TEMPLATE_HE` preserved as safety net.
- `backend/contractor_ops/reminder_service.py` — `_send_wa_template` got new `lang_code` kwarg (default "he", backward-compat for `send_pm_digest:433`). New helper `_resolve_digest_template_for_user` picks template + lang per recipient with EN→HE fallback chain. `send_contractor_reminder` body refactored: removed per-defect loop + `MAX_MESSAGES_PER_BATCH = 5` + per-task body params. Now sends ONE digest per (contractor, project) with body = (name, count, project) + button URL = `{project_id}?src=wa`. Cooldown / Shabbat / scheduler_locks preserved. Log entry type changed to `"contractor_reminder_digest"` with new fields `open_count` + `lang_code`.
- `backend/.env.production.template` — documented 4 new env vars (`WA_REMINDER_DIGEST_TEMPLATE_{HE,EN,AR,ZH}`).
- **V2 frontend additions** (Option B per Zahi insight 2026-05-01): `frontend/src/App.js` — added route `/projects/:projectId` + rewrote `ProjectsHome` wrapper to read URL `projectId` param (contractors → ContractorDashboard with prop, PMs → redirect to `/projects/:id/dashboard`). `frontend/src/pages/ContractorDashboard.js` — accepts new `initialProjectId` prop, threads into `useState` init (URL > localStorage > 'all').
- `backend/tests/test_reminder_digest.py` (NEW, 374 LOC) — 14 tests covering: 8 sync resolver cases (he/en/ar/zh→zh_CN/no-pref/company/unknown→en/uppercase), 5 async digest cases (1-message-for-100-defects/button-url/lang-priority/empty-skip/log-shape), and 1 multi-project pin test (3 projects → 3 separate messages — PINS Zahi's intent so any future "aggregate across projects" optimization fails loudly).

**Smoke test on staging 2026-05-01 (all green):**
- ✅ Build loads clean
- ✅ Contractor `/projects` (existing) works — pill bar hidden for single-project contractor
- ✅ Contractor `/projects/{id}` route loads (no 404), edge case fallback to 'all' kicks in for invalid id
- ✅ Super admin `/projects/{id}` redirects to `/projects/{id}/dashboard` automatically
- ⚠️ Minor UX: bad project_id triggers a brief "שגיאה בטעינת נתונים" toast before fallback. Won't happen in real WA flow (we only send valid project_ids). Polish opportunity for future batch — silent recovery instead of toast.

**Awaiting after deploy (Zahi action):**
- Meta template approval (24-48h, started 2026-05-01) — 4 templates submitted
- After each language template approves: add `WA_REMINDER_DIGEST_TEMPLATE_{LANG}` env var to AWS Elastic Beanstalk
- Until Hebrew approves: cron runs new code, WA send fails gracefully (logged), contractors get nothing (preferred over the broken flood)
- After Hebrew approves + env var added: contractors start getting digests at next 08:00 IL cron run

**Cleanup deferred:** `WA_REMINDER_TEMPLATE_HE` constant in config.py is now dead code (no caller in `reminder_service.py`). Leave intact for 2-3 weeks safety margin, then delete in cleanup batch.

#### Stream B — Universal Links + App Links + Contact Picker (Native, ./ship.sh, ~1-2 weeks + Apple/Google review)

This is the ONE native release. All native changes bundled to avoid multiple App Store/Play Store cycles per Zahi 2026-04-30.

**Sub-stream B1 — Universal Links (iOS) + App Links (Android):**
- Create `frontend/public/.well-known/apple-app-site-association` (iOS file — JSON with team ID + bundle ID + paths)
- Create `frontend/public/.well-known/assetlinks.json` (Android file — JSON with package name + cert SHA-256 fingerprint)
- iOS: add `associatedDomains` to entitlements + Xcode capability
- Android: add `intent-filter` with `android:autoVerify="true"` to `AndroidManifest.xml`
- Capacitor: `@capacitor/app` already installed (verified `package.json:8`). Add `App.addListener('appUrlOpen', ...)` handler that parses URL path and routes via React Router internally.
- Verify: tapping `https://app.brikops.com/tasks/abc?src=wa` → app opens (if installed) → routes to `/tasks/abc` inside app → if app not installed → falls back to browser (existing behavior).

**Sub-stream B2 — Contact Picker:**
- Install `@capacitor-community/contacts` (or modern equivalent — verify maintenance status during spec).
- iOS: add `NSContactsUsageDescription` to `Info.plist` with clear privacy explanation in Hebrew. Per Zahi 2026-04-30: validated by user feedback ("מעצבן להכניס ידנית"), Cemento has the same feature.
- Android: add `READ_CONTACTS` permission to `AndroidManifest.xml` + runtime permission prompt.
- Frontend: "בחר מאנשי קשר" button next to name fields in 2 places — Add Team Member modal + Add Contractor/Company modal. On click → request permission → open native picker → autofill name + phone.
- Web fallback: button hidden (no Contacts API in browsers).
- Privacy commitment in Info.plist text: "BrikOps לא שולח את אנשי הקשר שלך לשרתי החברה. הגישה משמשת רק כדי לאפשר לך לבחור איש קשר ולהכניס אותו לפרויקט." This is what Apple's reviewer reads.

**Required for B (Zahi's pre-flight):**
- ✅ Apple Developer account active (yes, app already in store)
- ✅ Google Play Console access (yes, app already in store)
- ✅ Domain `app.brikops.com` controlled (yes, on Cloudflare)
- ✅ Team ID + Bundle ID known (`com.brikops.app` per Mobile release housekeeping section)
- ⚠️ Existing installed apps need ONE update from App Store / Play Store before deep-link works for those users. New users get it automatically on install.

**Native release process (for Zahi):**
1. Replit completes spec, ships review.txt
2. Zahi runs `./deploy.sh --stag` → backend + web deploy to staging
3. Zahi runs `./deploy.sh --prod` → backend + web deploy to prod
4. Zahi runs `./ship.sh` on Mac → opens Xcode + Android Studio → Archive → Upload to TestFlight + Play Internal Testing
5. Zahi tests on physical device (deep-link + Contact Picker)
6. Zahi releases to App Store + Play Store production tracks
7. Apple review ~1-3 days, Google review ~hours
8. After release: existing installed users get update prompt, deep-link starts working for them after they update

**Native: REQUIRED.** This is the one ship.sh of this bundle.

#### Stream C — Bell Wiring + WhatsApp PM Digest (OTA, parallel to Stream A, ~1 week)

**Bell UI already exists.** Zahi confirmed via screenshot 2026-04-30 — top header has bell icon, opens "התראות" panel, currently shows "אין התראות". Infrastructure is in place. Missing: events firing into it.

**Events to wire (per Zahi 2026-04-30):**
- User tagged in defect thread → bell notification for tagged user (also feeds Batch 3 — Team member tagging on defect, ROADMAP line 287)
- Contractor uploaded photo + requested defect close → bell notification for PM
- Defect status changed by someone other than current user → bell notification for assignee + PM
- Handover protocol signed by tenant → bell notification for PM
- Scope to be finalized during spec — start with the 4 above, add more if cheap

**WhatsApp PM digest (parallel benefit):**
- Daily 08:00 IL morning digest to PMs (separate from contractor digest in Stream A)
- Contents: "5 ליקויים נפתחו אתמול, 2 קבלנים סגרו, 1 דרוש את אישורך, 0 מסירות נחתמו"
- Same scheduler infrastructure as Stream A. Different template, different recipients, different content builder.
- Existing infrastructure already supports `send_pm_digest` (`reminder_service.py:339`) — verify what it does today, extend if needed.

**Native: NONE.** OTA only. Independent of Stream B.

#### Decision: Native Push Notifications — DEFERRED

Considered for inclusion in Stream B native bundle. Decision per Zahi 2026-04-30: **defer.**

**Rationale:**
- 2-3 weeks of focused work (Capacitor plugin + APNs/FCM setup + backend sender + permission UX + testing)
- Doesn't directly enable a paid customer
- Stream A (contractor digest) + Stream C (bell + PM digest) cover ~80% of the urgency need without native push
- Real Israeli construction users live on WhatsApp anyway
- Better to ship Stream A/B/C, get real users, learn what they actually want push for, then build it properly
- Re-evaluate after 5-10 paying customers OR when first user explicitly asks for push notifications

**If revisited:** would require new bundle: `@capacitor/push-notifications` plugin + APNs Auth Key (.p8) from Apple Developer + Firebase project setup + `google-services.json` for Android + backend `users.push_tokens[]` field + sender service (FCM HTTP API + APNs HTTP/2 API, OR unified via Firebase Admin SDK / AWS SNS Mobile Push) + permission UX + foreground/background handlers + token refresh handling + multi-device per user. Estimated 2-3 weeks of dedicated work, separate `./ship.sh` because it's another native plugin install.

#### Order of operations (for cross-chat clarity)

1. **Today:** Submit `wa_contractor_reminder_digest_he` template to Meta for approval (24-48h wait runs in parallel with everything else). ROADMAP entry done (this section).
2. **Day 1-3:** Spec + ship Stream A (contractor digest). Backend only, OTA. New WhatsApp template plugged in once Meta approves.
3. **Day 1-3 in parallel:** Spec + ship Stream C (bell wiring + PM digest). Backend + frontend, OTA, no overlap with A.
4. **Day 3-7:** Spec + ship Stream B (Universal Links + App Links + Contact Picker). Includes `./ship.sh` + App Store / Play Store re-submission. Apple review 1-3 days, Google review hours.
5. **Day 7-10 (passive):** Existing installed users update from stores. Deep-link starts working for them. The same WhatsApp links shipped in Stream A automatically begin opening the app. No code change needed at this step.

**Status:** Plan finalized 2026-04-30. ROADMAP entry written. Ready for spec writing — Stream A first.

---

### 6. Manager assignment — tag managers (not just contractors) on defects/tasks

**Why:** Today, defect assignment supports only contractors via `assignee_id` (typically a contractor user). But in real construction sites, **the responsible party is sometimes a manager, not a contractor**. A site manager might photograph a problem that's not theirs to fix — it's the project manager's job to order materials, or the execution engineer's job to schedule a subcontractor.

**Concrete example (from Zahi 2026-05-03):**
> "מהנדס ביצוע רואה שחסר קרמיקה, אבל באחריות מנהל פרויקט להזמין. הוא מצלם תמונה שיש חוסר, אבל מתייג במקום קבלן את אחד המנהלים."

The execution engineer sees missing ceramic tiles, but ordering materials is the PM's job. He needs to photograph the gap and **tag the PM (a manager)** instead of a contractor — so the PM gets the notification + sees the task in their queue.

**Why this matters NOW (not just a nice-to-have):** The Safety module specifically needs this. Per the concept doc + #468 work — the מנהל עבודה (site manager) directs the עוזר בטיחות (safety assistant) and מהנדסי ביצוע (execution engineers) to handle safety-related items. Without manager-tagging, the site manager has no in-app way to delegate safety work to the right team member; he has to call/WhatsApp them externally, defeating the purpose of the platform.

**Scope of MVP:**
- Extend `Task.assignee_id` semantics: today it's a contractor user_id; expand to allow ANY project member (any role).
- In `NewDefectModal` + `TaskDetailPage`, the assignee picker shows TWO grouped sections:
  1. **קבלנים** (current behavior — contractors with companies)
  2. **מנהלים** (NEW — management_team members with their sub_role visible: "מהנדס ביצוע", "ממונה בטיחות", etc.)
- Notification + WhatsApp digest (from #469's stream) extend to managers seamlessly — they're already in the project membership.
- Status flow stays the same. A manager-assigned task uses the same lifecycle as a contractor task; only the assignee identity changes.

**Out of scope (for the MVP):**
- Changing the contractor "פאנל ניהול" (admin panel) flow — manager-assigned tasks may not even need a פאנל ניהול since the manager IS the responsible party.
- Bulk re-assignment from one manager to another — defer.
- Per-task acceptance/decline by managers — defer.

**Effort estimate:** Backend ~1 day (assignee resolution + notification logic), frontend ~2 days (picker UI in 3 surfaces + display chips). Mobile OTA. ~3-4 days total.

**Triggers:** Phase 2 of Safety module ABSOLUTELY needs this for tour delegation. Also overlaps with general defect routing improvements. Consider speccing as part of Safety Phase 2 OR as a standalone "manager-assignment" batch shipped before Safety Phase 2 kicks off.

**Status:** Concept logged 2026-05-03. Spec not yet written. Pre-requisite for Safety Phase 2 tour-signature flow.

---

### 9. Execution Control — Checklist mode (table view, PM-driven boolean status)

**Why:** Today, "בקרת ביצוע" (Execution Control) is documentation-heavy — every stage requires evidence (photos, "תיעוד לפני עבודה" notes, etc.). This is the right design for AUDIT trail and quality assurance, but it's **too slow for management overview**. A PM today cannot answer the question "which apartments have been tiled?" without drilling into each apartment one by one.

Real construction PMs maintain spreadsheets externally (Google Sheets) where they track simple status per (unit × stage) — see [Eli's tracking sheet for buildings 8+9](computer:///Users/zhysmy/Library/Application%20Support/Claude/local-agent-mode-sessions/b3d9071b-e7e1-4c34-bfff-c72750a66275/e76c8532-9c6b-44ae-9bcd-3313116f72df/local_7bb2c44a-9f7b-4029-9b94-62e67ea45fed/uploads/טבלת%20מעקב%20בניין%208%2B9%20-אלי%20-%20Google%20Sheets.pdf). 50 units × 20 stages, simple status values (בוצע / לא בוצע / חלקי / אין צורך / אין חוסרים) plus per-cell free-text notes.

**Concept (Zahi 2026-05-04):**
> "צריך קודם כל צ׳ק ליסט פשוט לסימון של מנהלים, בוצע / לא בוצע לפי סעיפים ודירות... מה שכבר יצרנו יהיה יותר עבור תיעודים אמיתיים מהשטח, זה לא סותר, צריך להיות שילוב ביניהם."

The checklist is a **second view** on the same execution data — fast, table-driven, PM-friendly. NOT a replacement for the existing documentation flow.

**MVP scope:**

UI — Single table view per project:
- Rows = units (sorted by floor → unit)
- Columns = template stages (configurable per project)
- Each cell = single-tap status: בוצע / לא בוצע / חלקי / אין צורך
- Optional per-cell free-text note (matches Eli's "הערות" column pattern)
- Filter row at top: by floor, building, status, stage
- Editable inline (click → cycle status)
- Sticky first column (unit name) + sticky header row for usability on long tables

Bidirectional sync with existing בקרת ביצוע:
- PM marks "ריצוף" = בוצע in checklist → existing execution control marks the stage as completed (via override path — no documentation required, audit-logged)
- Documented completion in execution control → checklist auto-updates to בוצע
- Visual distinction in checklist: a small icon/color indicates "completed via documentation" vs "marked via checklist override" — so quality auditors can find the documented ones

RBAC:
- **Edit:** project_manager + management_team (with sub_role flexibility — site_manager / work_manager can sign off on stages too, per construction reality)
- **View:** all project members
- Override of "stricter" sub-role stages (e.g. safety-related items) follows the same Override rules as Feature 10 below

Backend:
- New OR extended collection: status flow on the existing `floor_qc_runs` / `unit_qc_runs` (TBD during spec — depends on bug #60 resolution)
- New endpoint: `PATCH /api/projects/{id}/checklist/{cell_id}` with status + optional note
- Existing template structure used for column definition (no new schema for stages)

**Out of scope for the MVP:**
- Bulk operations (mark a whole row as done) — defer to v2 if asked
- Custom column ordering per user — defer
- Excel export of the checklist — likely cheap to add but defer to first user request

**Effort estimate:** 2-3 weeks (depends on backend sync model decisions during spec).

**Hard dependency:** **🔴 Bug #60 (template → floor sync) MUST be fixed first.** The checklist relies on stages propagating correctly from template to per-unit cells. If template additions don't propagate, checklist is broken at root.

**Triggers:** Field PMs are already maintaining external spreadsheets (Eli's evidence). High demand. Spec immediately after bug #60 closes + Safety Phase 1 finishes prod.

**Status (UPDATED 2026-05-07):** ✅ **FULLY SHIPPED — checklist vision delivered.** All MVP scope + bidirectional sync + Excel export. Implemented as INDEPENDENT data store. Phases: Phase 1 backend (#483), Phase 2A read-only (#484-#492), Phase 2B cell editing (#494), Phase 2C stage management (#495 + #497 polish + #498 UX labels), Phase 2D-1 Excel-style filters + saved views (#500), tooltip-note (#501), Excel export (#502 + followup), QC→Matrix one-way sync (#503 + 3 followups). The matrix at `/projects/{p}/execution-matrix` IS the checklist concept — table, simple status, fast PM-driven, live mirror of QC. **MVP scope complete:**
- ✅ UI single table view per project
- ✅ Rows = units sorted by floor → unit (numeric sort #485+#489)
- ✅ Columns = stages (template + custom per project, hide/reorder)
- ✅ Single-tap status (CellEditDialog #494)
- ✅ Optional per-cell free-text note (#494)
- ✅ Filter row (Phase 2D-1 #500 — drawer per Zahi UX choice)
- ✅ Editable inline (#494 popover/sheet)
- ✅ Sticky first column on desktop (#486 + #487)
- ✅ **One-way QC→Matrix sync (#503 + 3 followups)** — PM doesn't maintain duplicate state. Item activity → blue, submit → orange, approved → green, rejected → red. 7/7 mutation endpoints hooked. Reverse direction (Matrix→QC) PERMANENTLY off the table — QC carries photo-evidence requirements that matrix edits would compromise.
- ✅ **Excel export (#502 + #502-followup)** — RTL .xlsx with notes as comments, sorted, auto-filter. Filename in Hebrew (RFC 5987).
- ✅ **8-status palette** — completed / partial / **ready_for_work** (NEW manual planning state) / in_progress / **pending_review** (NEW sync from QC submit) / not_done / not_relevant / no_findings
- 🚧 **PDF export** — for printing tour reports / archival. Not yet spec'd. Lower priority — Excel export covers most sharing needs.

---

### 10. PM Override close — manual completion with audit (RBAC-restricted)

**Why:** Today, every closure of a בקרת ביצוע item requires evidence/documentation. This blocks legitimate use cases:

**Concrete scenario (Zahi 2026-05-04):**
> "יש לי מנהל פרויקט שהתחבר לאפליקציה, אבל הוא כבר סיים את כל השלבים הראשוניים של יציקת תקרה בלוקים וכדומה, הוא לא יכול באמת לסגור את הסעיפים."

A PM joins an existing project mid-construction. Early stages (יציקת תקרה, בלוקים, etc.) were completed BEFORE the app existed. He has no photos, no documentation — but the work IS done. The system blocks closure → the project shows as 0% complete forever, unusable for management.

Other valid override scenarios:
- Documentation was uploaded to wrong unit/stage and needs cleanup
- Quality issue resolved verbally on-site, no photo taken
- Sub-role mismatch (e.g. work_manager closed a stage that the system thinks needs safety_officer signoff)

**MVP scope:**

UI — Override button on any open stage/item:
- Visible **only** to `project_manager` role (NOT management_team generally)
- Button: "סמן כהושלם (override)" with shield/warning icon
- Click opens confirm dialog with mandatory textarea: "סיבה לסגירה ידנית"
- Closing without reason rejected
- After close: stage marked as `completed`, audit fields populated

Backend:
- New fields on the relevant collection (depends on whether closing tasks, stages, or units):
  - `closed_via_override: bool` (default false)
  - `override_closed_by: str` (user_id)
  - `override_closed_at: ISO date`
  - `override_reason: str` (free-text, max 500 chars)
- New endpoint: `POST /api/.../override-close` with reason in body
- RBAC enforced server-side (NOT just hidden in UI) — `require_roles('project_manager')` + super_admin
- Audit log entry created in addition to the field updates (compliance trail)

Compliance / admin visibility:
- New page or section: "סגירות ידניות" (manual closures) — admin/PM can see list of all overrides for a project, sortable by date
- Optional: count of overrides shown as a metric on the project dashboard (visibility, not punishment)
- Export to CSV for legal/audit handoff

**Out of scope for the MVP:**
- Approval workflow (e.g. requires another PM to confirm) — defer to v2 if compliance demands
- Time-bound override (auto-expire if not validated) — defer
- Bulk override of multiple items at once — defer

**Effort estimate:** 3-4 days (small but RBAC + audit requires care).

**RBAC consideration:** This is a "powerful" action — restricting it to PM only (not management_team broadly) prevents accidental closures by junior staff. Super_admin can also do it (system override). DO NOT extend to contractor or viewer.

**Pre-requisite:** None — independent of Section 9 (Checklist) and bug #60. Can ship immediately after Safety Phase 1 finishes if prioritized.

**Triggers:** Already blocking real PM in production (Zahi reported 2026-05-04). Should be next in queue after Safety Phase 1 completes prod deploy.

**Status:** Concept logged 2026-05-04 from real production PM blocked. Spec not yet written. Recommended P0 once Safety Phase 1 is done.

---

### 8. Defects outside units — lobby / common areas / site development (פיתוח)

**Why:** Today, every defect must be tied to a unit (Project → Building → Floor → Unit → Defect). But real construction has defects that live in **non-unit locations**: lobbies, public corridors, stairwells, elevator halls, mechanical rooms, building exteriors, roofs, **and especially פיתוח** (site development — landscaping, paths, parking, gardens, fences). Currently PMs have no clean way to log these. Workarounds we've seen / expect:
- Logging the defect against an arbitrary unit (data pollution — searches/reports break)
- Logging in notes/free-text only (no status tracking, no aggregation)
- Skipping the platform entirely for these defects (feature gap → losing trust)

**Concrete examples (from Zahi 2026-05-04):**
> "ליקויים יכולים להיות בלובי, או בפיתוח, לא רק לפי דירה."

- Cracked tile in the lobby (Building-level)
- Damaged irrigation system in the garden (Project-level / פיתוח)
- Peeling paint in the stairwell of building B, floor 3 (Floor-level, no specific unit)
- Damaged barrier at parking entrance (Project-level / פיתוח)
- Roof leak above unit 3 but the leak source is the roof itself (Building-level, but affects a unit)

**Scope of MVP:**

The fundamental change is that `Task.unit_id` becomes optional. Defects gain a new `location_scope` field with possible values:
- `unit` (current behavior — tied to a specific apartment)
- `floor` (no unit, but tied to a floor — e.g. stairwell, corridor)
- `building` (lobby, mechanical rooms, exterior, roof — tied to building only)
- `project` (פיתוח — landscaping, parking, gardens, fences — tied to project only)

In the UI:
- NewDefectModal: location selector becomes hierarchical with "scope" chooser. Default = unit (current). Optional escalation to floor/building/project as needed.
- ProjectControlPage: defects view gains a category filter for "scope" (or implicit grouping — TBD UX decision).
- ProjectControlPage / BuildingDefectsPage / FloorDefectsPage: each surface knows which scope levels are relevant for it (e.g. on a floor page, show floor-scoped + unit-scoped defects from that floor).
- A NEW project-level page or section for project/building/floor-scoped defects that don't belong to a specific unit.

**Schema implications:**
- `Task.unit_id` → `Optional[str]` (was required)
- `Task.floor_id`, `Task.building_id` → `Optional[str]` (were already optional in some places, formalize)
- New: `Task.location_scope: Literal['unit','floor','building','project'] = 'unit'` with default
- Existing tasks → all `'unit'` (no migration data loss; new field defaults).
- Validation: each scope requires the corresponding ID(s) (unit-scope needs unit+floor+building; floor-scope needs floor+building; etc.).

**UI design opportunities:**
- "פיתוח" tab/filter on the project-level dashboard (shows project-scoped defects)
- "אזורים משותפים" (common areas) filter on building view (shows building-scoped + floor-scoped defects)
- Photos for non-unit defects can use the same camera flow — just save without unit reference

**Out of scope for the MVP:**
- Map/floorplan-based pinning of where exactly in the lobby/garden the defect is (defer — needs a separate plans-pinning batch).
- Splitting "פיתוח" into sub-zones (north-side, south-side, etc.) — defer until customers demand finer granularity.
- Re-categorizing existing unit-tied defects to a different scope (manual workaround: clone+delete).

**Effort estimate:**
- Backend: 2-3 days (schema migration + validation + endpoint updates + filter logic)
- Frontend: 4-5 days (NewDefectModal scope selector + 3 page surfaces' filter UI + new project-scope view)
- Tests: 2 days (covers new scopes + backward compat)
- Total: ~1.5-2 weeks

**Triggers:** Customer pain — closed-beta PMs are already accumulating "where do I put this lobby defect?" questions. Worth speccing within Q3 2026 once Safety Phase 1 finishes.

**Status:** Concept logged 2026-05-04. No mockups yet. Spec not yet written. Pre-requisite: nothing blocking — independent of Safety Phase 2 / Manager assignment.

---

### 7. Internal group chat — project-scoped messaging for managers/team

**Why:** Construction project teams currently coordinate via WhatsApp groups outside the app. This breaks the audit trail (no project record of decisions), forces context-switching, and means status updates/photos shared in WhatsApp don't link to specific defects/tasks. The closest pattern users want is "WhatsApp inside BrikOps, but project-scoped and integrated."

**Concrete vision (from Zahi 2026-05-03):**
> "אני גם חושב בעתיד להוסיף משהו כמו groupchat למנהלים בתוך האפליקציה, ככה יוכלו להתעדכן ולקבל עדכונים אחד מהשני, ממש כמו קבוצת ווטסאפ לפרויקט."

A WhatsApp-style group chat per project where the management team can post updates, share photos, ask questions, and coordinate — all while staying inside BrikOps with full audit history.

**MVP scope (when speccing — order from cheap-to-expensive):**

| Tier | Effort | What you get |
|---|---|---|
| **Tier 1 — Project feed** | ~1 week | Append-only project timeline. Members post text + photos. No threads, no replies, no @mentions. Backend = MongoDB collection `project_messages` (org_id, project_id, author_id, body, attachments[], created_at). Frontend = simple chronological view + post composer. |
| **Tier 2 — Threaded chat with @mentions** | ~2-3 weeks | Tier 1 + reply threads + @mention members + mention notifications wired into the existing bell + push system. Read receipts (last_read_at per user). |
| **Tier 3 — Realtime + WhatsApp parity** | ~1-2 months | Tier 2 + WebSocket (or SSE polling fallback) for realtime updates + typing indicators + message reactions + voice notes. Search across messages. Pin messages. |

**Recommendation:** Start with **Tier 1**. Prove the value (will managers actually use it?) before investing in realtime infra. Tier 2 is the natural follow-up if adoption is real.

**Integration opportunities (where chat ties into existing features):**
- **Task references** — paste a defect link into chat → render as inline preview card with status chip.
- **Photo from chat → defect** — long-press a photo in chat → "convert to defect" → opens NewDefectModal pre-filled with the photo.
- **Auto-post on key events** — defect created / status changed / handover signed → optional auto-post to chat as "system message" (toggleable per project).
- **WhatsApp digest replacement** — managers who prefer WhatsApp can keep getting the existing #469-stream digests; in-app chat is additional, not replacement.

**Privacy / RBAC considerations:**
- Project-scoped — only members of that project see/post.
- Optional: separate channels per role group (managers-only / managers+contractors). MVP = single project channel.
- Audit log — every message persisted forever (no edit/delete in MVP — keeps audit trail simple). Consider edit/delete in Tier 2 if needed, with audit trail of edits.

**Triggers:** No urgent driver. Start spec when 5+ closed-beta orgs ask for it OR when the WhatsApp digest stream proves insufficient for coordination.

**Status:** Concept logged 2026-05-03. No mockups yet. No tech spike done yet (WebSocket vs polling decision deferred to Tier 3 if reached).

---

## 🆕 New items (added 2026-04-24)

### Offline mode — **CRITICAL for field use**
**Why:** Construction sites frequently have no cellular coverage. Currently, a PM on the 10th floor of an unfinished building can't log a defect, view plans, or mark a protocol item. This is the #1 blocker for field adoption.

**Scope (to be refined — needs discovery phase):**
- Service worker / Capacitor cache strategies
- Offline-first data layer (IndexedDB or similar)
- Sync queue for mutations (defect create/update, photo upload, status change)
- Conflict resolution on reconnect (last-write-wins? manual merge?)
- UI for offline state (banner, sync indicator, queue depth)
- Photo upload resilience (chunked upload + retry)
- Which flows are supported offline? (priority: defect create + photo, view plans, mark tasks done)

**Status:** NOT scoped yet. Big feature — likely 3-5 batches. Needs a dedicated discovery spike before spec.

---

### Code quality / stability cleanup — **Minimum-risk improvements**
**Why:** After multiple batches, there's some accumulated tech debt. Zahi wants to clean up without introducing regressions.

**Scope (to be refined):**
- Remove Batch 2b `FEATURES` flags after 2 weeks of prod stability (Cleanup of `DEFECT_DRAFT_PRESERVATION` + `TRADE_SORT_IN_TEAM_FORM`)
- Dead code removal (unused imports, unreferenced helpers, old comments about removed features)
- Consistent error handling patterns across services
- Consolidate duplicate utility functions (formatters, date helpers, etc.)
- Standardize toast messages (currently mixed Hebrew/English in some error paths)
- Remove any remaining `console.log` with PII (audit before next external beta)
- Unused dependencies in `package.json` (run `depcheck`)
- Consolidate similar components (e.g., multiple "confirm dialog" patterns)
- Unit tests for critical helpers (`defectDraft`, `categoryBuckets`, auth interceptor)

**Status:** NOT scoped yet. Approach: one batch per quarter, minimum-risk changes only. Never mix cleanup with feature work.

---

## 📚 Feature backlog — evaluated (15 ideas from brainstorm)

Context: a separate brainstorm session produced 15 feature ideas across 3 categories (WOW effects, power-user efficiency, deal breakers). Evaluated below with realistic effort estimates and verdicts. **This is not a commitment list — it's a reference for prioritization.**

### 🎯 Ship these (chosen for Batch A — next 6-8 weeks)

**#8 — Duplicate detection (defect create)**
- PM creates "נזילה במקלחת" when "נזילה אמבטיה" exists in same unit within 7 days → flag as potential duplicate, show existing record, let user confirm or proceed.
- **Effort:** 1 week (rule-based: Levenshtein on title + same unit + same category + 7-day window). AI embeddings version: 2 weeks.
- **Verdict:** Quick win, high ROI, low risk. Start rule-based.

**#9 — Contractor performance dashboard**
- "Amnon completes 92% on time, avg quality 4.3/5, 2.1-day avg turnaround." Not AI — just analytics surfaced well.
- **Effort:** 2 weeks (UI + MongoDB aggregations).
- **Verdict:** Looks like AI to customers, isn't. High perceived value, low complexity. Ship early.

**#11 v1 — Simple timeline view** (NOT full Gantt)
- Phases + milestones + current progress + blockers. No dependencies, no critical path.
- **Effort:** 4 weeks. Full Gantt is 8-12 weeks — defer that to v2.
- **Verdict:** Enterprise-sales readiness without the rabbit hole. CEOs want to see progress bars; they don't need Microsoft Project complexity.

**#7 v1 — Auto-prioritization (rules, not AI)**
- Suggest severity based on category + location (post-handover unit? public area?) + keywords in description.
- **Effort:** 1 week rule-based. AI version (reading images too) = 2-3 weeks — defer.
- **Verdict:** Good QoL for PMs. Rules are cheaper and more predictable than LLM.

---

### 🟡 Ship later (Q3-Q4 2026, after parity + polish)

**#1 — Vision AI Phase 1 (photo → auto-fill defect)**
- Already Task #27. Strong differentiator.
- **Realistic effort:** 6-8 weeks (not the 3-4 stated in the brainstorm). Breakdown: Vision API + prompt (1w) + Hebrew construction jargon (1-2w) + category mapping to existing taxonomy (1w) + UI for "AI suggested / edit" (1w) + testing/edge cases (1-2w).
- **Precondition:** Accuracy benchmark on 100 real photos BEFORE spec. If <75% category accuracy, feature becomes friction — redesign or kill.
- **Cost:** $0.01/image with Haiku, $0.03-0.05 with Sonnet. Negligible at any scale.
- **Verdict:** Yes. But do the accuracy benchmark first.

**#12 — Defect on floor plan** ⚠️ **PARITY BLOCKER**
- Cemento has this. Every demo prospect asks for it. Without it we lose deals.
- **Realistic effort:** 8-12 weeks (brainstorm said 6-8 — too optimistic). Mobile pan/zoom + pin placement, desktop UX, PDF export with pins, radius search ("all kitchen defects"), scale handling.
- **Verdict:** Essential for retention and sales. Probably #1 priority after offline mode. Needs its own dedicated discovery phase before spec.

**#5 — Weekly summary** (simple version)
- Cron + DB aggregation + WhatsApp/email digest.
- **Effort:** 1 week templated (no AI), 2 weeks with AI narration.
- **Verdict:** Ship templated version first. AI prose is nice-to-have; PMs mostly skim numbers.

---

### 🔴 Defer or kill

**#4 — Before/after AI comparison ("was the repair done?")**
- Compelling but premature.
- **Problems:** angle/lighting differences between photos confuse AI. Contractors can game it (photograph a different repaired spot). "30 min/day saved per PM" is optimistic — most defects aren't visually verifiable.
- **Verdict:** V2 of Vision AI, after V1 (single-photo → defect) ships and we understand accuracy patterns. Probably 2027.

**#2 — WhatsApp voice → defect**
- Cool-sounding, niche in practice.
- **Problems:** WhatsApp Business API restrictions, noise on construction sites degrades voice-to-text, disambiguation nightmare ("דירה 12 קומה 3" — which project?), not a demonstrated PM pain point.
- **Verdict:** Defer indefinitely. Reconsider if AI Assistant launches and chat traction is high.

**#3 — "AI that remembers and learns"**
- Conflates 3 different things and calls them all AI:
  - "Top contractor per category" → SQL query, not AI
  - "Avg time to fix" → aggregate, not AI
  - "Floor 4 is problematic" → COUNT + threshold, not AI
- **Verdict:** Ship analytics layer as part of #9 (contractor performance). Drop the "AI" framing. ML model is over-engineering until we have 50+ completed projects as training data.

**#6 — Smart Search (NL → filter)**
- Natural-language search is usually slower and more error-prone than good filters with preset chips. PMs learn UI quickly; they don't need to type.
- **Verdict:** Skip. Invest in better filters + saved views instead.

**#10 — Thermal imaging (UAE)**
- Building for a market with zero validated customers. FLIR ONE is niche even in UAE.
- **Verdict:** Defer until there's an actual UAE dev partner asking for it. Markets expansion analysis should come first (Zahi is adding that report).

**#13 — QR per apartment (dayar-facing)**
- Interesting angle with hidden risks.
- **Problems:** tenants seeing ongoing defects create disputes and support load; contractor names exposed = legal implications; warranty info sharing needs product+legal review not scoped in concept.
- **Verdict:** Needs a separate product/legal review before any engineering. Maybe opt-in tenant portal instead of automatic QR.

**#14 — Contractor mobile app (separate)**
- This is a 2nd product, not a feature. Realistic effort: 3-4 months, not 6-10 weeks.
- Israeli contractors are often older, use outdated phones, have limited digital literacy. WhatsApp works for them today.
- **Verdict:** Defer. Strengthen WhatsApp flow + mobile web UI instead. Only build if a large developer explicitly requires it in an RFP.

**#15 — API integrations (Priority / SAP / Google Drive / Monday)**
- Real enterprise requirement, but speculative building is wasteful.
- **Effort reality:** 2-4 weeks per integration (brainstorm said 2 — unrealistic). Priority alone is 1 month due to its ERP quirks.
- **Verdict:** Build on demand. Don't pre-build.

---

### What's missing from the brainstorm (gaps I noticed)

1. **Offline mode** — not in the list, but #1 blocker for field adoption. Already in the "New items" section above.
2. **Code quality cleanup** — not in the list. Already in the "New items" section above.
3. **Security audit** — Zahi is adding this as a report.
4. **Accessibility (WCAG)** — missing. Enterprise RFPs will require it.
5. **Advanced filters / saved views** — cheaper and better than Smart Search (#6).
6. **Notifications digest** — opt-in daily/weekly email instead of per-event push spam.
7. **Bulk operations** — select 20 defects + assign/close/move. Power users will pay for it.

---

### Recommended sequencing

**Batch A — Next 6-8 weeks** (quick wins + enterprise readiness):
- #8 Duplicate detection (1w)
- #9 Contractor performance dashboard (2w)
- #7 Auto-prioritization rules (1w)
- #11 v1 Simple timeline (4w)

**Offline discovery spike** — 1 week scoping (see "New items" section above)

**Batch B — Q3 2026:**
- #12 Defect on floor plan (parity blocker, 8-12w) — probably its own quarter
- In parallel: #1 Vision AI v1 accuracy benchmark + spec

**Q4 2026+:**
- Vision AI v1 implementation
- Full Gantt (#11 v2) if enterprise demand materializes
- AI Assistant Phase 0 scrappy MVP (see section above)

**Never (or much later):**
- #2 WhatsApp voice, #3 ML learning, #6 Smart Search, #10 Thermal, #13 QR (needs redesign), #14 contractor app

---

## 📋 To add — 2 reports

Zahi to fill in details. Placeholders:

### Security report — Pentest 2026-04-22

**Full report:** `/Users/zhysmy/brikops-new/security/pentest-report-2026-04-22.md`
**Tester:** Claude (`brikops-pen-tester` skill) against production api.brikops.com + app.brikops.com
**Status:** Completed. 2 CRITICAL + 1 HIGH + 4 MEDIUM + 3 LOW + 5 INFO findings.

**Bottom line:** Internal defense-in-depth is strong — JWT validation, RBAC, mass-assignment protection, file-upload validation, workflow bypass all pass. **But** two list endpoints (`/api/users` + `/api/companies`) leak cross-tenant PII of 41 users and 8 companies to every authenticated user. OWASP A01 (Broken Access Control). **Framing:** all 41 users are internal testers recruited for closed beta — not paying customers. This is a pre-launch finding to fix before wider release, not an active data breach. No mandatory notification obligation applies.

#### 🔴 CRITICAL — fix within 24-48h (own batch)

**CRIT-1: `/api/users` exposes 41 users cross-tenant** (PM role only)
- `GET /api/users` with any PM JWT returns full name, email, phone_e164, user_id, role, platform_role for all 41 users across 4+ organizations. Includes super_admin identity + phone.
- Contractor role correctly gets 403 — bug is in PM route only.
- Fix: add `require_super_admin()` OR auto-scope by `current_user.organization_id`. 2-3 lines per endpoint.

**CRIT-2: `/api/companies` exposes 8 companies cross-tenant** (PM AND Contractor)
- `GET /api/companies` with ANY valid JWT returns name, contact_name, contact_phone, contact_email, tax_id, address for all 8 companies across organizations. Real contractor PII (phones of יוסי כהן, דוד לוי, משה אברהם).
- Worse than CRIT-1 because contractor tokens can also exploit — and there are more contractors than PMs in the system.
- Fix: same pattern — auto-scope by `organization_id`. Contractors should see only their own company.

**Immediate operational actions beyond code fix:**
- Pull API logs for past 7 days, identify any users who called `/api/users` or `/api/companies` heavily — potential data harvesting.
- Consider proactive notification to affected customers if log analysis suggests exploitation.

#### 🟠 HIGH — before next deploy

**HIGH-1: `/api/tasks` list leaks 30 tasks from 4 foreign projects** (PM only, list-view only — item GET/PATCH are correctly blocked with 403)
- Leaks: id, title, description, status, priority, project_id, building_id, floor_id, unit_id of projects the PM isn't a member of.
- Fix: add `query["project_id"] = {"$in": member_project_ids}` in the list handler.
- Audit similar list endpoints: `/api/units`, `/api/floors`, `/api/buildings`, `/api/invoices` — same pattern likely exists.

#### 🟡 MEDIUM — next sprint

- **MED-1:** No rate limiting on authenticated endpoints (40 GETs + 20 PATCHes all returned 200). Fix: per-user rate limits via `slowapi` or custom middleware with Redis/KV. 60/min writes, 120/min reads, 30/min list.
- **MED-2:** No request body size limit. Server parsed a 10MB payload on `/auth/verify-otp` before rejecting with 400. Fix: Content-Length middleware (1MB auth/CRUD, 50MB uploads).
- **MED-3:** Polyglot PNG uploads succeed (valid PNG + trailing `<script>` tag saved to S3). Low exploitability with current browser content-type handling, but latent risk. Fix: re-encode uploaded images with Pillow/Wand before saving.
- **MED-4:** `/api/uploads` trailing-slash redirect uses `http://` instead of `https://`. Currently protected by Cloudflare + HSTS, but fix: `HTTPSRedirectMiddleware` or explicit trailing-slash routes.

#### 🔸 LOW / Hardening (this quarter)

- **LOW-1:** OTP concurrent requests cause 500 instead of 429/409.
- **LOW-2:** `app_id` leaks in `/api/health` response (identifies JWT issuer).
- **LOW-3:** HSTS missing `preload` directive + not submitted to hstspreload.org.
- **INFO-4:** `/api/billing/me` exposes `owner_user_id` to contractors (low — could enable targeted IDOR).
- **INFO-5:** `/admin/*` endpoints inconsistent — 403 vs 404 allows enumeration.

#### ✅ Passed tests (confirming strong defense-in-depth)

JWT validation (alg:none, tampered sig, malformed), all mass-assignment attempts across tasks/members/units/reminders, per-item IDOR, billing isolation, admin endpoints, webhooks, NoSQL/XSS/path-traversal injection, file upload type/content/filename checks, CORS, TLS 1.3, HTTPS enforcement, concurrent PATCH last-write-wins, contractor role boundaries (16 privilege-escalation attempts all blocked with 403/404/405/422).

#### Next actions (sequence)

1. **Batch S1 (emergency — 1 day):** CRIT-1 + CRIT-2 fix. Hot deploy. Run grep-verify that no other global `/api/<resource>` list endpoints exist without org scoping. Pull logs.
2. **Batch S2 (with next deploy):** HIGH-1 + audit sibling list endpoints.
3. **Batch S5 (with same deploy window as S2):** Code-audit findings — see section below.
4. **Batch S3 (sprint):** All 4 MEDIUM pentest findings.
5. **Batch S4 (quarter):** LOW + INFO hardening.
6. **Retest:** CRIT/HIGH retest after fix. Full pentest re-run 2026-05-22 or 30 days after CRIT fix.

**These should be treated as above-the-line priority over feature work until at least Batch S2 + S5 ship.**

---

### Batch S5 — Code-level audit findings (added 2026-04-24)

Complementary audit to the 2026-04-22 pentest. Pentest was black-box (HTTP layer only); this is white-box (code review). Focus: vulnerabilities that don't show up as HTTP responses.

**Full agent report logs:** not saved to disk — see conversation history. Key findings:

#### 🔴 CRITICAL — Batch S5a

**S5-CRIT-1: Webhook idempotency missing** (`backend/contractor_ops/notification_router.py:153-269`)
- WhatsApp webhook stores events via `db.whatsapp_events.insert_one()` without checking if the event was already received.
- Attacker (or network retry) can replay the same webhook N times → N duplicate event records → N separate calls to `process_webhook()` → stale job updates, orphaned messages, or incorrect notification state.
- `wa_message_id` has a sparse index but no code-level dedup check.
- **Fix:** before insert, `find_one({'wa_message_id': provider_id})` and skip if exists. Or `upsert` atomically.

#### 🟠 HIGH — Batch S5b

**S5-HIGH-1: TOCTOU in WhatsApp signature verification** (`notification_router.py:43-53`)
- `_verify_signature()` uses `hmac.compare_digest()` correctly, BUT the caller checks `if not _meta_app_secret` AFTER accepting the webhook payload.
- If `META_APP_SECRET` is temporarily unset (deploy window, config error, feature-flag toggle), the webhook silently accepts unsigned payloads.
- **Attack:** during a deploy, attacker sends a crafted webhook while secret is unset → processed as authentic → fake status updates injected.
- **Fix:** fail-closed. Validate `_meta_app_secret` is set at middleware entry and reject webhook if missing. Log the rejection.

**S5-HIGH-2: CORS wildcard + credentials in non-prod** (`backend/contractor_ops/server.py:1414-1422`)
- `allow_origins` is `.split(',')` from `CORS_ORIGINS` env var. If unset in staging/dev, falls back to `'*'` AND `allow_credentials=True` remains.
- This is invalid per CORS spec and leaks cookies to any attacker origin that a staging user visits while authenticated.
- **Fix:** startup guard — if `allow_credentials=True` and any origin is `*` or list is empty, fail-fast with clear error. Force explicit origins in all environments.

**S5-HIGH-3: Webhook event storage swallows duplicates silently** (`notification_router.py:213-217, 259-263`)
- Related to S5-CRIT-1. Try-except around insert logs the error but continues. Duplicate events due to network retries accumulate without atomic insert-or-skip.
- **Fix:** use MongoDB `upsert` with `wa_message_id` as unique key (with unique index + sparse filter), or pre-check + conditional insert in a transaction.

#### 🟡 MEDIUM — Batch S5c (defer to sprint with S3)

**S5-MED-1: Timing oracle on webhook signature check** (`notification_router.py:160-170`)
- Missing header rejection returns faster than invalid-signature rejection. Attacker can distinguish the two via response-time measurement.
- **Fix:** always call `hmac.compare_digest()` with a dummy value if header is missing.

**S5-MED-2: Debug endpoints leak config details** (`backend/contractor_ops/debug_router.py:208-256`)
- `/debug/version`, `/debug/otp-status`, `/debug/whatsapp` return feature flags, token lengths, phone ID suffixes. Gated by `require_super_admin` + `ENABLE_DEBUG_ENDPOINTS`, but reduce verbosity further.
- **Fix:** return booleans (configured / not configured) instead of actual suffixes/lengths. Consider runtime warning if accessed in prod.

**S5-MED-3: CSP style-src too strict** (`server.py:1432`)
- `style-src 'self'` blocks inline styles and CDN fonts. Not a security vuln, but UX issue.
- **Fix:** add `'unsafe-inline'` or nonce-based CSP; add `https:` for CDN fonts if used.

#### ✅ What the code audit VERIFIED clean

- All 30 routers have proper `Depends(get_current_user)` or `require_roles(...)` decorators
- **No mass assignment** beyond what pentest tested — Pydantic models validate every request body
- **No NoSQL injection** — type coercion via Pydantic on every input
- **No unsafe deserialization** — zero `pickle.loads`, `yaml.load`, `eval`, `exec` in backend
- **Self-promotion to super_admin blocked** — no endpoint allows `platform_role` modification
- JWT handling robust: HS256 hardcoded (no alg:none), min 32-char secret, version tracking, 30-day sliding expiry
- All secrets properly env-based. **Zero exposed credentials in code, git history, or frontend bundle**
- `.gitignore` is comprehensive. `.env` files never committed

### Batch S6 — Retire the legacy `companies` collection (added 2026-04-24)

**Context:** investigation during Batch S1 planning revealed that the `companies` collection is **90% legacy**. Only 8 records exist, all created by `seed.py` and `demo_seed.py` during initial Replit-era setup. The real contractor data lives in `project_companies` (project-scoped, org-isolated via `projects.org_id`).

**Current fallback paths that reference `companies`:**
- `tasks_router.py:488-490` — assignee lookup falls back to `companies` if `project_companies` misses
- `notification_service.py:347, 366` — contact phone fallback for notifications
- `reminder_service.py:87, 241` — reminder lookup fallback
- `onboarding_router.py:403, 688` — subcontractor signup validates `requested_company_id` against global catalog
- `export_router.py:208, 518` — includes global companies in exports

**Why retire:**
1. **Reduces attack surface.** Fewer endpoints that could leak cross-tenant data.
2. **Simplifies mental model.** One source of truth (`project_companies`). No more "which collection am I querying?".
3. **Eliminates demo-data pollution.** The 8 seed records bleed into production queries via fallback paths.
4. **Prepares for multi-market.** Fewer places where data isolation has to be enforced.

**Scope (2-3 days):**
1. Audit all 5 fallback sites. Decide per-site:
   - If the fallback is genuinely needed → replace with `"משתמש לא ידוע"` / null / empty string
   - If the fallback is dead code (never triggers) → remove
2. Audit the onboarding `requested_company_id` flow. If subcontractors need a global catalog to pick from during signup, consider:
   - Option A: remove the feature (subcontractor registers without a company, PM links them later)
   - Option B: replace with per-org catalog (new collection, properly scoped)
3. Delete the 8 seed rows from `companies` collection.
4. Delete `POST /api/companies` and `GET /api/companies` endpoints.
5. Delete the `companies` collection (`db.companies.drop()`).
6. Remove `seed.py:60-67` and `demo_seed.py:39-61`.
7. Remove the Pydantic `Company` model from `schemas.py`.

**Precondition:** ship Batch S1 first (the projection-based PII fix). That closes the immediate bleeding. Retirement can then happen at leisure.

**DO NOT:** attempt this before Batch S1 ships. Do not mix security hotfix with architecture cleanup.

**Status:** Not yet spec'd. Task tracked separately.

---

#### Admin access — verification workflow for Zahi (operational, not code)

The code is safe against admin self-promotion. But operational verification is needed to confirm only Zahi has `super_admin`:

**Step 1:** Check env var in AWS Elastic Beanstalk Console:
- Configuration → Environment Properties → look for `SUPER_ADMIN_PHONES` and/or `SUPER_ADMIN_PHONE`
- Whose phones are listed? Only Zahi's?

**Step 2:** Run MongoDB query (read-only, via Atlas or mongo shell):
```javascript
db.users.find(
  { platform_role: 'super_admin' },
  { id: 1, name: 1, email: 1, phone_e164: 1, created_at: 1 }
)
```

**Step 3:** If unexpected admins found:
```javascript
// Option A (preferred): remove their phone from SUPER_ADMIN_PHONES env var and redeploy — next login demotes them
// Option B (immediate): manual demotion in DB
db.users.updateOne(
  { id: '<intruder_user_id>' },
  { $set: { platform_role: 'none' } }
)
```

**Step 4:** Audit recent admin access:
```javascript
db.audit_events.find({ event_type: 'admin_access' })
               .sort({ created_at: -1 }).limit(50)
```

---

### Markets expansion report — Multi-Market Architecture Standards

**Full doc:** `/Users/zhysmy/brikops-new/docs/strategy/multi-market-architecture-standards.md`
**Status:** Reference document. Not for immediate implementation.

#### Core principle

**Don't pay the cost of flexibility before you need it.** BrikOps stays Israel-only until there's a concrete expansion decision (recon trip done, local partner found, budget approved). No `/markets/` folder, no market field, no "market-aware refactor" before that moment.

#### The pattern is already proven — it's the same one as Batch 2b

This is NOT a new engineering philosophy. It's the SAME pattern we already implemented in `Batch 2b Patch` (April 2026) when we added `GroupedSelectField` and the `FEATURES.TRADE_SORT_IN_TEAM_FORM` / `FEATURES.DEFECT_DRAFT_PRESERVATION` flags.

**Same 2 safety layers Zahi defined for Batch 2b:**
1. **Feature flags** wrap new behavior, default `true`, falsy value falls back to existing behavior exactly
2. **Wrapper component** handles new behavior — **existing code stays 100% unchanged** (`git diff --stat frontend/src/components/BottomSheetSelect.js` MUST BE EMPTY)

**Mapping Batch 2b → Multi-market (component level → module level):**

| Batch 2b | Multi-market |
|---|---|
| `FEATURES.TRADE_SORT_IN_TEAM_FORM` flag | `project.market` field (`"il"` / `"uae"` / …) |
| `GroupedSelectField` wrapper | `/backend/markets/<code>/` folder |
| `SelectField` **unchanged** | `/backend/core/*` **unchanged** |
| Fallback if flag=false → `SelectField` | Fallback if market unknown → `core` (Israel) |
| Zero blast radius on SelectField callers | Zero blast radius on Israeli code |

**4 shared principles (identical at both scales):**
1. **Additive, not destructive** — always add on top, never modify below
2. **Existing code frozen** — the "deep" code (SelectField / core) doesn't move
3. **Dispatch at the edge** — routing decision happens as high as possible (render-time / router-handler)
4. **Default to existing** — any fallback returns to old code, never crashes

**The route-handler equivalent of our `{FEATURES.X ? <GroupedSelectField> : <SelectField>}`:**

```python
# backend/routes/handover_router.py — "the wrapper" — 7 lines per endpoint

async def create_handover(project_id: str, user: User):
    project = await get_project(project_id)
    market = project.market or "il"                              # the "flag"
    if market == "il":
        return await core.handover.create(project_id, user)      # Israeli = core, untouched
    if market == "uae":
        from markets.uae import handover as uae_handover
        return await uae_handover.create(project_id, user)       # UAE = wrapper file
    return await core.handover.create(project_id, user)          # fallback = Israeli
```

**Why this matters as a permanent anchor:**
- When we start UAE in Q1 2027, we're not learning new engineering — we're applying a pattern that already shipped and works
- Grep review checks transfer 1:1 — same `git diff --stat backend/core/ # empty` check on every market PR that we use today for `BottomSheetSelect.js`
- **Auto-veto rule:** if any dev/agent/Claude ever proposes "small refactor of core because market X needs it" — the pattern document is the automatic veto. Core stays frozen. Markets add, never modify.
- Batch 2b Patch is the proof-of-concept. Multi-market is the same pattern, bigger scope.

#### The architecture (when market #2 arrives — earliest Q1 2027)

**Extension Pattern, not Config-Driven.** New market = new folder under `/backend/markets/<code>/` with its own `config.py`, `handover.py`, `qc.py`, `validators.py`, `pdf_template.py`, `notifications.py`. Israeli core code (`/backend/core/*`) is NEVER modified. Router switches at the top of each endpoint route requests to the right module by `project.market`.

**Why extension over config-driven:**
- Cost of flexibility is paid only when it's needed
- Each new market ships in 2-3 months (not 6+)
- Israeli code stays frozen and stable
- Migration path to config-driven is clean IF the 3 golden rules are followed

#### 3 Golden Rules (must follow from market #1)

1. **Same structure in every extension** — same 6 files, same names, same directory layout. No exceptions.
2. **Data vs Logic separation** — `config.py` = data only (sections, validation patterns, currency, VAT, legal refs, template IDs). Logic files = logic only.
3. **Same function signatures** — every `handover.py` exposes `create/get/update/validate/generate_pdf/send_notification` with identical signatures. Enables generic router switches later.

**Following these rules → future migration to Config-Driven takes 3-4 months (mostly automated).**
**Breaking them → 8-12 months of manual refactoring + bug risk.**

#### Trigger for Config-Driven migration

Watch quarterly. Migrate when ANY of these hit:
- 5+ customers asking for a custom field in the same market
- New-market onboarding time exceeds 6 months
- Same bug fix needed in 4+ extensions

Until then: Extension pattern is correct.

#### Timeline

| Year | Quarter | Action |
|------|---------|--------|
| 2026 | Q1-Q3 | Israel only. Focus on feature + security work (above this section). |
| 2026 | Q4 | Recon trip (Dubai). Partner search. NO code change. |
| 2027 | Q1 | Extension infrastructure (3 days: `market` field, `/markets/` folder, router switches). |
| 2027 | Q1-Q2 | UAE extension build (2-3 months, following 3 rules). |
| 2027 | Q3-Q4 | UAE beta → scaling (3→20 customers). |
| 2028 | Q1-Q2 | Market #3 (Cyprus / Qatar / Saudi) if demand exists. Same pattern. |
| 2028 | Q3-Q4 | Decision point: Config-Driven migration needed? |
| 2029+ | — | If migrated: JSON-based, global scaling possible. |

#### Red flags to catch early

1. Duplicate code between extensions → move to `core/shared/`
2. Extension importing another extension → NEVER (copy instead, or promote to core)
3. Logic creeping into `config.py` → keep config data-only
4. Hardcoded Hebrew/Israel strings in `core/*` → extension's responsibility
5. Time to add new market growing → migration alarm

#### What to do NOW (Israel-only era)

For every new feature built today:
- Mark hardcoded Hebrew/Israeli specifics with comment `# MARKET-SPECIFIC: Israel`
- Use helper functions for currency (returns ₪ today, parameter later)
- Use helper for phone validation (accepts only 05X today, extensible)
- Use helper for date format (DD/MM/YYYY today, extensible)

These habits cost zero now and save weeks of refactoring later.

#### Integration with security strategy

Cross-tenant isolation (highlighted by pentest CRIT-1 + CRIT-2) becomes **even more critical** in multi-market. A data leak across Israeli org is bad; a data leak across Israeli org AND UAE org triggers cross-jurisdiction privacy law exposure (Israeli חוק הגנת הפרטיות + UAE PDPL + potentially EU GDPR if any customer is EU-resident). **Batch S1/S2 security fixes must ship before any multi-market work begins.**

---

## Priority ordering (my recommendation — subject to Zahi's approval)

| # | Item | Effort | Risk | Impact |
|---|------|--------|------|--------|
| **0** | **🔴 Batch S1 — CRIT-1 + CRIT-2 fix** (from 2026-04-22 pentest) | **Tiny (1 day)** | **Low code risk / CRITICAL security risk if not fixed** | **Emergency** |
| **0.3** | **🔴 Admin access verification** (operational — env var + Mongo query + audit logs) | **Tiny (30 min, no code)** | None | Medium (assurance) |
| **0.5** | **🟠 Batch S2 — HIGH-1 + audit sibling list endpoints** | Small (3-5 days) | Low | High |
| **0.7** | **🔴 Batch S5a — Webhook idempotency** (code-audit CRITICAL) | Small (1-2 days) | Low | High |
| **0.8** | **🟠 Batch S5b — TOCTOU + CORS + event dedup** (code-audit HIGH, 3 items) | Small (2-3 days) | Low | High |
| 1 | **Offline mode** discovery spike (scope first, don't build yet) | Medium | Low (scoping only) | Critical (field adoption) |
| 2 | **Batch S3 — MEDIUM pentest findings** (rate limit, request size, PNG re-encode, HTTPS redirect) | Small | Low | Medium |
| 2.5 | **Batch S5c — MEDIUM code-audit** (timing oracle, debug endpoints verbosity, CSP relaxation) | Small | Low | Low-Medium |
| 3 | **Feature Batch A** — Duplicate detection + Contractor perf dashboard + Auto-prio rules + Simple timeline v1 | Medium (6-8 weeks total) | Low | High |
| 4 | **Batch 3** — Team tagging on defect | Small | Low | Medium |
| 5 | **Defect on floor plan** (#12 — parity blocker, 8-12 weeks) | Large | Medium | High (retention + sales) |
| 6 | **Safety Phase 2** — Cemento parity | Large | Medium | High (retention) |
| 7 | **Code cleanup** — first batch (remove Batch 2b flags after 2 weeks prod) | Small | Low | Medium |
| 7.5 | **Batch S6 — Retire legacy `companies` collection** (only after Batch S1 ships) | Small (2-3 days) | Low-Medium | Medium (reduces attack surface + simplifies architecture) |
| 8 | **Vision AI Phase 1** (with accuracy benchmark first) | Large | Medium | High (differentiator) |
| 9 | **Markets expansion report** (once Zahi scopes it) | Small | Low | High (strategic) |
| 10a | **AI Assistant — Phase 0 scrappy MVP** (chat-only, 5 customers, 2 weeks) | Small | Low | High (learning) |
| 10b | **AI Assistant — Full V1** (only if Phase 0 validates) | Medium | Medium | Medium-High |
| 11 | **Batch S4 — Security LOW + hardening** (HSTS preload, app_id removal, etc.) | Small | Low | Low |
| 12 | **Batch 4** — Contact picker (native) | Small | Medium (native) | Small |
| 13 | **Security re-test** — full pentest re-run (30 days after CRIT fix) | Small | Low | High |

**Rationale:**
- Offline is #1 because it's blocking real-world field adoption
- Security report is #3 because it de-risks everything below
- Safety Phase 2 is #4 because Phase 1 alone is a half-built promise to users who saw Cemento
- Vision AI has the biggest "wow" factor but isn't a blocker
- Markets expansion report before any actual market expansion work
- Android v1.0.18 + App Privacy + Apple Review are orthogonal to all of this — they ship when ready

---

## How to update this file

- New items → add under appropriate section with a short "why" paragraph
- Shipped items → move to "Shipped" with date
- Changed priority → renumber the table at the bottom + note in git commit
- Keep it under ~300 lines
