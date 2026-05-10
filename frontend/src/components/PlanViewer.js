import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { usePinch } from '@use-gesture/react';
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight, Loader2, X, Download, Eye } from 'lucide-react';

// 2026-05-10 — react-pdf worker setup. CRITICAL: bundle the worker
// LOCALLY (not via CDN) for two reasons:
//   1. Capacitor native app fails CDN fetches when offline (and
//      may also fail under Capacitor CSP). P1.4 requires offline,
//      so we MUST self-host the worker.
//   2. Removing external CDN dependency = no single-point-of-failure
//      and no CDN cold-start latency.
//
// The worker file is copied to frontend/public/pdf.worker.min.mjs by
// the postinstall-copy-pdfworker script in package.json (see
// frontend/.gitignore — the file is gitignored so it tracks the
// installed pdfjs-dist version automatically).
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

/**
 * PlanViewer — full-screen modal viewer for plan files.
 *
 * Phase 1.1 scope: pure viewer. NO pin/coordinate/defect-linkage
 * (that's P1.2). NO context-aware opening (P1.3). NO offline (P1.4).
 *
 * Renders:
 *   - PDF: via react-pdf (PDF.js + Web Worker). Zoom + pan + page nav.
 *   - Image (jpg/png/heic/webp): native <img> with width-based scaling.
 *   - Other (dwg/dxf/xlsx): fallback message + "open in new tab" link.
 *
 * Coordinate system note (for P1.2): pin coordinates will be stored
 * as proportional values in [0,1] so they survive scale changes
 * and re-renders at different pixel resolutions.
 */
const PlanViewer = ({ plan, onClose }) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  // 2026-05-10 hotfix — start at null, set to fit-to-width on first
  // PDF load. Avoids flash-of-wrong-scale before fit calc completes.
  // While null, render placeholder (loading spinner already covers
  // this — don't render <Page> until scale is set).
  const [scale, setScale] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef(null);

  useEffect(() => {
    setNumPages(null);
    setPageNumber(1);
    setScale(null); // recomputed in handleLoadSuccess
    setLoadError(null);
    setLoading(true);
  }, [plan?.id, plan?.file_url]);

  // 2026-05-10 hotfix-4 — native pinch-to-zoom on touch devices.
  // Captures the pinch gesture on the scroll container and updates
  // `scale` state, so react-pdf re-renders the page at the new scale
  // (sharp text, not CSS-scaled rasterized canvas). Solves both the
  // "no pinch on iPhone" bug and the "browser pinch = pixelated text"
  // bug with one change.
  //
  // PATTERN A — `from` config: offset[0] is treated as the absolute
  // current pinch state, anchored to the scale value at gesture start
  // (returned by `from`). NOT a multiplier. This avoids the
  // exponential-drift bug where `scale * offset[0]` compounds each
  // frame because offset is itself cumulative-from-gesture-start.
  // Bounds [0.1, 4.0] match the +/- button bounds (hotfix-1). Rubberband
  // gives soft-bounce feedback at the edges. eventOptions.passive=false
  // is required so we can preventDefault to suppress browser-native
  // pinch on iOS Safari edge cases.
  usePinch(
    ({ offset: [s], event }) => {
      if (event && event.cancelable) event.preventDefault();
      setScale(Math.min(Math.max(s, 0.1), 4.0));
    },
    {
      target: containerRef,
      eventOptions: { passive: false },
      scaleBounds: { min: 0.1, max: 4.0 },
      rubberband: true,
      from: () => [scale ?? 1.0, 0],
    }
  );

  // 2026-05-10 hotfix — react-pdf onLoadSuccess passes the full
  // PDFDocumentProxy (not just {numPages}). We use it to compute a
  // fit-to-width scale on load so users see the whole plan edge-to-edge
  // by default. They can zoom in for details via the + button or pinch.
  const handleLoadSuccess = useCallback(async (pdf) => {
    setNumPages(pdf.numPages);
    setLoading(false);
    try {
      if (!containerRef.current) {
        setScale(1.0);
        return;
      }
      // Subtract p-4 padding (16px each side = 32px) so content
      // doesn't immediately overflow.
      const containerWidth = containerRef.current.clientWidth - 32;
      const containerHeight = containerRef.current.clientHeight - 32;
      // Defensive guard: container may not be laid out yet when
      // handleLoadSuccess fires (modal still animating in,
      // display:none transition, mobile keyboard pushing viewport).
      // clientWidth=0 → containerWidth=-32 → fitScale=negative →
      // clamped to 0.1 → mystery "tiny PDF" bug. Fall back to 1.0
      // if dimensions look invalid; user can zoom in/out manually.
      if (containerWidth <= 0 || containerHeight <= 0) {
        setScale(1.0);
        return;
      }
      const page = await pdf.getPage(1);
      const viewport = page.getViewport({ scale: 1.0 });
      const widthScale = containerWidth / viewport.width;
      const heightScale = containerHeight / viewport.height;
      // Use min so the WHOLE page fits (both dimensions). Cap at 1.0
      // — small PDFs (e.g. apartment-only sketch) shouldn't upscale
      // above native size.
      const fitScale = Math.min(widthScale, heightScale, 1.0);
      // 2026-05-10 hotfix-2 — Math.floor (not Math.round) so we never
      // round UP past the true fit-scale. Math.round(11.7)=12 → 0.60
      // when actual fit is 0.585 → 0.60 already overflows by ~3%.
      // floor(11.7)=11 → 0.55 → strictly within fit. User can zoom IN
      // to show full-width if they want.
      const rounded = Math.max(0.1, Math.floor(fitScale * 20) / 20);
      setScale(rounded);
    } catch (err) {
      console.warn('[PlanViewer] fit-scale calculation failed, falling back to 1.0:', err);
      setScale(1.0);
    }
  }, []);

  const handleLoadError = useCallback((error) => {
    console.error('[PlanViewer] PDF load error:', error);
    setLoadError(error?.message || 'שגיאה בטעינת התוכנית');
    setLoading(false);
  }, []);

  const isPdf = plan?.file_type === 'application/pdf';
  const isImage = (plan?.file_type || '').startsWith('image/');

  // 2026-05-10 hotfix — multiplicative steps (×1.25 / ×0.8) so each
  // click feels equally significant regardless of starting scale. With
  // additive +/- 0.25 and a fit-scale of (e.g.) 0.4, clicking + once
  // jumps 62% but clicking again jumps 38% — uneven. Multiplicative
  // keeps each click ~25%. Lower bound 0.1 — A0 plans on phone screens
  // legitimately need ~20% to fit.
  const zoomIn = useCallback(() => setScale(s => Math.min((s ?? 1.0) * 1.25, 4.0)), []);
  const zoomOut = useCallback(() => setScale(s => Math.max((s ?? 1.0) * 0.8, 0.1)), []);
  const prevPage = useCallback(() => setPageNumber(p => Math.max(p - 1, 1)), []);
  const nextPage = useCallback(() => setPageNumber(p => Math.min(p + 1, numPages || 1)), [numPages]);

  if (!plan) return null;

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-slate-900" dir="rtl">
      {/* Top bar — title + page counter + external open + download + close */}
      <div className="flex items-center justify-between gap-2 px-4 py-3 bg-slate-800 text-white shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="text-sm font-bold truncate">
            {plan.name || plan.original_filename}
          </h3>
          {isPdf && numPages > 1 && (
            <span className="text-xs text-slate-300 bg-slate-700 px-2 py-0.5 rounded shrink-0">
              {pageNumber} / {numPages}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <a
            href={plan.file_url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
            title="פתח בכרטיסייה חדשה"
            aria-label="פתח בכרטיסייה חדשה"
          >
            <Eye className="w-5 h-5" />
          </a>
          <a
            href={plan.file_url}
            download={plan.original_filename || plan.name}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
            title="הורד"
            aria-label="הורד"
          >
            <Download className="w-5 h-5" />
          </a>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
            aria-label="סגור"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Viewer area — outer container scrolls, inner container centers
           content when it fits, allows pan to corners when it overflows.
           Two-layer pattern (outer overflow-auto + inner min-w-full
           min-h-full flex center) is critical: putting `flex
           items-center justify-center` on the scrolling container fights
           overflow when content > viewport and breaks pan-to-corners. */}
      {/* 2026-05-10 hotfix-2 — three fixes layered here:
           a) dir="ltr" on the scroll container so RTL inheritance from
              the outer modal doesn't mess up Chrome's RTL scroll
              handling with `flex justify-center`. PDF canvas content
              is intrinsically LTR; only the chrome (top/bottom bars)
              needs RTL.
           b) Tailwind arbitrary `[&::-webkit-scrollbar]` modifiers so
              macOS users see scrollbars permanently — visual cue that
              pan is possible. Pattern aligned with calendar.jsx /
              table.jsx (project convention, Tailwind 3.4+). No JS
              injection, no module side-effect.
           c) touchAction kept for native pinch-zoom on mobile. */}
      {/* 2026-05-10 hotfix-4 — `touch-action: pan-x pan-y` (without
           pinch-zoom) tells the browser: "allow ONE-finger pan/scroll
           on this element, but DON'T handle pinch yourself." Pinch is
           now captured by the usePinch hook above, which calls setScale
           to trigger react-pdf to re-render at higher resolution =
           sharp text (instead of CSS-scaled raster = pixelated). */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-slate-700 [&::-webkit-scrollbar]:w-3 [&::-webkit-scrollbar]:h-3 [&::-webkit-scrollbar-thumb]:bg-white/35 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-transparent [&::-webkit-scrollbar-thumb]:bg-clip-content [&::-webkit-scrollbar-thumb]:hover:bg-white/55 [&::-webkit-scrollbar-track]:bg-black/20 [&::-webkit-scrollbar-corner]:bg-black/20"
        dir="ltr"
        style={{ touchAction: 'pan-x pan-y' }}
      >
        {/* 2026-05-10 hotfix-3 — `w-fit` (width: fit-content) added so
             the wrapper grows with the canvas when canvas is wider than
             the viewport. Without this, the wrapper was pinned at 100%
             (min-w-full) and the canvas overflowed it on both sides
             with no way for the outer overflow-auto to see/scroll the
             overflow. With w-fit + min-w-full, computed width is
             max(content, viewport) — centered when content fits,
             content-sized (and scrollable via outer) when overflows. */}
        <div className="min-w-full min-h-full w-fit flex items-center justify-center p-4">
          {loading && isPdf && (
            <div className="flex flex-col items-center gap-2 text-white">
              <Loader2 className="w-8 h-8 animate-spin" />
              <span className="text-sm">טוען תוכנית…</span>
            </div>
          )}

          {loadError && (
            <div className="flex flex-col items-center gap-3 text-white p-6 text-center">
              <span className="text-sm text-red-300">{loadError}</span>
              <a
                href={plan.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 underline text-sm"
              >
                פתח בכרטיסייה חדשה
              </a>
            </div>
          )}

          {isPdf && !loadError && (
            <Document
              file={plan.file_url}
              onLoadSuccess={handleLoadSuccess}
              onLoadError={handleLoadError}
              loading=""
              error=""
            >
              {scale !== null && (
                <Page
                  pageNumber={pageNumber}
                  scale={scale}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                />
              )}
            </Document>
          )}

          {/* For images: width-based scaling lets the image REFLOW the
               container so the outer overflow-auto can scroll. CSS
               `transform: scale()` looks zoomed but breaks scroll
               because the layout box stays the original size.
               maxWidth:none overrides the object-contain default that
               would clamp the image. */}
          {isImage && (
            <img
              src={plan.file_url}
              alt={plan.name || ''}
              style={{
                width: `${scale * 100}%`,
                maxWidth: 'none',
                height: 'auto',
                display: 'block',
              }}
            />
          )}

          {!isPdf && !isImage && !loadError && (
            <div className="flex flex-col items-center gap-3 text-white p-6 text-center">
              <span className="text-sm">סוג קובץ לא נתמך לתצוגה מקדימה.</span>
              <a
                href={plan.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 underline text-sm"
              >
                פתח בכרטיסייה חדשה
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar — zoom + page nav (PDF only) */}
      <div className="flex items-center justify-center gap-2 px-4 py-3 bg-slate-800 text-white shrink-0">
        <button
          onClick={zoomOut}
          disabled={!scale || scale <= 0.1}
          className="p-2 hover:bg-slate-700 disabled:opacity-30 rounded-lg transition-colors"
          aria-label="זום אאוט"
        >
          <ZoomOut className="w-5 h-5" />
        </button>
        <span className="text-xs text-slate-300 min-w-[3rem] text-center">
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={zoomIn}
          disabled={!scale || scale >= 4.0}
          className="p-2 hover:bg-slate-700 disabled:opacity-30 rounded-lg transition-colors"
          aria-label="זום אין"
        >
          <ZoomIn className="w-5 h-5" />
        </button>

        {isPdf && numPages > 1 && (
          <>
            <div className="w-px h-6 bg-slate-600 mx-2" />
            <button
              onClick={prevPage}
              disabled={pageNumber <= 1}
              className="p-2 hover:bg-slate-700 disabled:opacity-30 rounded-lg transition-colors"
              aria-label="עמוד קודם"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
            <span className="text-xs text-slate-300 min-w-[4rem] text-center">
              {pageNumber} / {numPages}
            </span>
            <button
              onClick={nextPage}
              disabled={pageNumber >= numPages}
              className="p-2 hover:bg-slate-700 disabled:opacity-30 rounded-lg transition-colors"
              aria-label="עמוד הבא"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default PlanViewer;
