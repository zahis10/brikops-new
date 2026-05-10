import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
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
  const [scale, setScale] = useState(1.0);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef(null);

  useEffect(() => {
    setNumPages(null);
    setPageNumber(1);
    setScale(1.0);
    setLoadError(null);
    setLoading(true);
  }, [plan?.id, plan?.file_url]);

  const handleLoadSuccess = useCallback(({ numPages }) => {
    setNumPages(numPages);
    setLoading(false);
  }, []);

  const handleLoadError = useCallback((error) => {
    console.error('[PlanViewer] PDF load error:', error);
    setLoadError(error?.message || 'שגיאה בטעינת התוכנית');
    setLoading(false);
  }, []);

  const isPdf = plan?.file_type === 'application/pdf';
  const isImage = (plan?.file_type || '').startsWith('image/');

  const zoomIn = useCallback(() => setScale(s => Math.min(s + 0.25, 4.0)), []);
  const zoomOut = useCallback(() => setScale(s => Math.max(s - 0.25, 0.5)), []);
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
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-slate-700"
        style={{ touchAction: 'pan-x pan-y pinch-zoom' }}
      >
        <div className="min-w-full min-h-full flex items-center justify-center p-4">
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
              <Page
                pageNumber={pageNumber}
                scale={scale}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
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
          disabled={scale <= 0.5}
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
          disabled={scale >= 4.0}
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
