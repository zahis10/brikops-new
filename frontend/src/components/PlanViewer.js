import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Document, pdfjs } from 'react-pdf';
import { ZoomIn, ZoomOut, Maximize, ChevronLeft, ChevronRight, Loader2, X, Download, Eye } from 'lucide-react';

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

// BATCH pdf-viewer-hebrew-fix (2026-05-23) — pdf.js needs CMap +
// standard-font data to render non-Latin (Hebrew) text. Without
// them Hebrew glyphs render garbled. The asset folders are
// self-hosted under public/ (copied from pdfjs-dist by the
// postinstall script — see package.json), same pattern as the
// worker above.
// MUST be a module-level constant: react-pdf reloads the whole
// document whenever the `options` object identity changes, so an
// inline `options={{...}}` would reload the PDF on every render.
const PDF_OPTIONS = {
  cMapUrl: '/cmaps/',
  cMapPacked: true,
  standardFontDataUrl: '/standard_fonts/',
  // BATCH pdf-viewer-hebrew-fix-v2 (2026-05-24) — THE operative
  // fix. pdf.js's default renders embedded-font text via the
  // browser @font-face engine, which garbles this PDF's Hebrew
  // (WeasyPrint / DejaVu-subset / Identity-H). disableFontFace
  // makes pdf.js draw glyph outlines as vector paths directly
  // (same as pdfium / poppler).
  disableFontFace: true,
};

const PAD = 16;          // the p-4 around the sheet
const STEP = 1.5;        // one tap on + / −
const SETTLE_MS = 250;   // quiet time after a zoom change before any re-render work starts
const CANVAS_CSS = 'display:block;width:100%;height:100%;';
const LOAD_ERROR = 'שגיאה בטעינת התוכנית';

/**
 * createPlanView — the zoom / pan engine of the viewer. Plain DOM code: nothing here goes through
 * React state, so a pinch never waits for a React render or for pdf.js.
 *
 * How zoom works
 *   - The sheet is one box (`stage`) inside a normal scrolling container (`scroller`). At rest its zoom is
 *     simply its CSS size. During a pinch / zoom animation the box is moved and scaled with a CSS transform
 *     only, and the real size + scroll position are written once when the move ends (see "Live moves").
 *     The canvas inside is only STRETCHED by the browser (GPU) — it is never re-rendered during a gesture.
 *     (The earlier pinch attempts re-rendered the PDF on every step, and react-pdf hides the canvas while it
 *     renders — that is what felt jerky.)
 *   - One finger = native scrolling, exactly as before (momentum included). Two fingers are handled here:
 *     the two-finger sequence is preventDefault-ed and native scrolling is frozen while it lasts.
 *   - Sharpness: the PDF page is rendered once at screen size ("base"). The first time the user zooms in, a
 *     second, sharp render is made in the background ("max" — as many pixels as the budget allows) and kept
 *     for as long as the page is open, plus a half-size copy of it for the zoom range in between. From then
 *     on every zoom level is instant. The render pauses while fingers are on the screen.
 *   - Pixel budget: iOS refuses canvases above 16.7M pixels (they stay blank), so touch devices are capped
 *     at 16M; beyond that zoom the sharp render is stretched (softer, never blank).
 *
 * Sizes are in "natural units": PDF points for a PDF page, pixels for an image. zoom = CSS px per unit.
 */
function createPlanView({ scroller, stage, host, label, isPdf, onChange, onReady, onError, onSharpening }) {
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  const coarse = !!window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
  let budget = coarse ? 16e6 : 64e6;
  let size = null; let fit = null; let zoom = null; let max = 4;
  let page = null; let levels = []; let shown = null; let job = null; let noMax = false;
  let ok = false; let dead = false; let busy = false; let img = false;
  let live = null; let lite = false; // a move in progress (see "Live moves") / "this device needs the lighter canvases while moving"
  let timer = 0; let chip = 0; let anim = 0; let target = null; let wheelEnd = 0; let wheel = null; let edge = '';

  // thickness of a space-taking scrollbar in this scroller: 12px on desktop, 0 on phones (overlay scrollbars)
  const ghost = scroller.cloneNode(false);
  ghost.style.cssText = 'position:absolute;inset:auto;width:100px;height:100px;overflow:scroll;visibility:hidden;';
  scroller.parentNode.appendChild(ghost);
  const bar = ghost.offsetWidth - ghost.clientWidth;
  scroller.parentNode.removeChild(ghost);

  const clamp = (z) => Math.min(Math.max(z, fit), max);
  const center = () => { const r = scroller.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; };
  const report = () => {
    const now = { atFit: zoom <= fit * 1.001, atMax: zoom >= max * 0.999 };
    const key = `${now.atFit}${now.atMax}`;
    if (key !== edge) { edge = key; onChange(now); }
  };

  // ---- canvases ---------------------------------------------------------------------------------
  const free = (c) => { if (c.parentNode) c.parentNode.removeChild(c); c.width = 0; c.height = 0; };

  // show the smallest canvas that is sharp enough for this zoom (a canvas may be stretched up to 20%).
  // The canvases sit in a pointer-events:none layer: a touch must never start ON a canvas, because swapping
  // that canvas out mid-gesture would take the rest of the touch events with it.
  const showBest = (z) => {
    // `lite`: this device moves the big canvas too slowly — while the sheet is moving, use the lighter ones
    const list = live && lite ? levels.filter(l => l.kind !== 'max') : levels;
    if (!list.length) return;
    const need = (z * dpr) / 1.2;
    let best = list[list.length - 1];
    for (const l of list) { if (l.res >= need) { best = l; break; } }
    if (best === shown) return;
    if (shown && shown.canvas.parentNode === host) host.replaceChild(best.canvas, shown.canvas);
    else host.appendChild(best.canvas);
    shown = best;
  };

  const put = (l) => {
    const old = levels.find(x => x.kind === l.kind);
    levels = levels.filter(x => x !== old).concat(l).sort((a, b) => a.res - b.res);
    showBest(zoom);
    if (old) free(old.canvas);
  };

  // ---- geometry ---------------------------------------------------------------------------------
  const paint = (z) => { zoom = z; label.textContent = `${Math.round((z / fit) * 100)}%`; showBest(z); };

  // the real size of the sheet (one reflow) — used at rest, never per frame
  const sizeTo = (z) => {
    stage.style.width = `${Math.round(size.w * z)}px`;
    stage.style.height = `${Math.round(size.h * z)}px`;
    paint(z);
  };

  // which point of the sheet (as fractions of its width / height) is under a viewport point
  const under = (pt) => {
    const a = stage.getBoundingClientRect();
    return { fx: a.width ? (pt.x - a.left) / a.width : 0.5, fy: a.height ? (pt.y - a.top) / a.height : 0.5 };
  };

  // Live moves. While fingers are down (or a zoom animation runs) the sheet is NOT laid out again: it is only moved
  // and scaled with a CSS transform (compositor work — no layout and no paint per frame). The transform is computed
  // so that the sheet sits exactly where the real layout would put it at that zoom: centered while it is smaller
  // than the screen, otherwise scrolled, never past its edges. When the move ends, the real size and scroll position
  // are written once (`commit`) and the transform is dropped — nothing moves on screen.
  // Native scrolling is switched off for the duration (overflow: hidden), so the browser cannot scroll under us.
  const begin = () => {
    if (live) return;
    scroller.style.overflow = 'hidden';
    const s = scroller.getBoundingClientRect(); const a = stage.getBoundingClientRect();
    live = { sx: s.left, sy: s.top, rw: scroller.offsetWidth, rh: scroller.offsetHeight, x0: a.left - s.left, y0: a.top - s.top, w0: a.width || 1, h0: a.height || 1, to: null, probe: 0, slow: 0 };
  };
  // one axis of the layout: sheet length, room on screen, anchor fraction, where the anchor should be (px from the start of the room)
  const axis = (len, room, f, p) => {
    const most = Math.max(0, len + PAD * 2 - room);    // scroll range at this size
    const start = most > 0 ? PAD : (room - len) / 2;   // where the sheet starts at scroll 0
    const scroll = Math.min(most, Math.max(0, Math.round(start + f * len - p)));
    return { scroll, pos: start - scroll };
  };
  // show the sheet at zoom z with its point `u` under the viewport point `to`
  const move = (z, u, to) => {
    const w = Math.round(size.w * z); const h = Math.round(size.h * z);
    let rw = live.rw; let rh = live.rh;
    if (bar) { // desktop: a scrollbar takes room once the sheet overflows — and one bar can make the other one necessary
      const tall = h + PAD * 2 > rh; if (tall) rw -= bar;
      if (w + PAD * 2 > rw) rh -= bar;
      if (!tall && h + PAD * 2 > rh) rw -= bar;
    }
    const x = axis(w, rw, u.fx, to.x - live.sx); const y = axis(h, rh, u.fy, to.y - live.sy);
    live.to = { w, h, left: x.scroll, top: y.scroll };
    stage.style.transform = `translate(${x.pos - live.x0}px, ${y.pos - live.y0}px) scale(${w / live.w0}, ${h / live.h0})`;
    paint(z);
    // Safety net: how long until the browser is ready for the next frame after this move? Six slow ones in a row
    // while the big canvas is on screen => `lite` (lighter canvases while moving) for the rest of this page.
    if (shown && shown.kind === 'max' && !live.probe) {
      const session = live; const t0 = performance.now();
      live.probe = requestAnimationFrame(() => {
        session.probe = 0;
        if (live !== session) return;
        session.slow = performance.now() - t0 > 34 ? session.slow + 1 : 0;
        if (session.slow >= 6) lite = true;
      });
    }
  };
  const commit = () => {
    if (!live) return;
    const t = live.to; live = null;
    stage.style.transform = ''; scroller.style.overflow = '';
    if (!t) return;
    stage.style.width = `${t.w}px`; stage.style.height = `${t.h}px`;
    scroller.scrollLeft = t.left; scroller.scrollTop = t.top;
    showBest(zoom);
  };

  // ---- rendering (PDF only) ---------------------------------------------------------------------
  const settle = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = 0;
      if (busy || dead) return;
      if (job && job.paused) { job.paused = false; const go = job.resume; job.resume = null; if (go) go(); }
      pump();
    }, SETTLE_MS);
  };

  const finish = () => { clearTimeout(chip); chip = 0; onSharpening(false); };

  const done = (j) => {
    if (job !== j) { free(j.canvas); return; }
    job = null; finish();
    put({ kind: j.kind, res: j.res, canvas: j.canvas });
    if (j.kind === 'max') {
      // a half-size copy for the zoom range between "base" and "max" (shrinking a canvas more than 2x breaks thin lines)
      const base = levels.find(l => l.kind === 'base');
      if (base && j.res / 2 > base.res * 1.3) {
        const c = document.createElement('canvas');
        c.width = Math.max(1, Math.round(j.canvas.width / 2)); c.height = Math.max(1, Math.round(j.canvas.height / 2));
        c.style.cssText = CANVAS_CSS;
        const ctx = c.getContext('2d', { alpha: false });
        if (ctx) { ctx.imageSmoothingQuality = 'high'; ctx.drawImage(j.canvas, 0, 0, c.width, c.height); put({ kind: 'half', res: j.res / 2, canvas: c }); }
      }
    }
    if (!ok) { ok = true; onReady(); }
    pump();
  };

  const fail = (j, err) => {
    free(j.canvas);
    if (job !== j) return; // cancelled on purpose (page change / close)
    job = null; finish();
    if (dead) return;
    if (j.kind === 'base') { onError(err); return; }
    // the sharp render did not fit in memory: keep the lighter canvas and try once more with half the pixels
    console.warn('[PlanViewer] sharp render failed, retrying smaller:', err);
    budget /= 2;
    if (budget < 4e6) noMax = true; else settle();
  };

  const render = (kind, res) => {
    const vp = page.getViewport({ scale: res });
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(vp.width)); canvas.height = Math.max(1, Math.round(vp.height));
    canvas.style.cssText = CANVAS_CSS;
    const j = { kind, res, canvas, paused: busy, resume: null, task: null };
    job = j;
    try {
      const ctx = canvas.getContext('2d', { alpha: false });
      if (!ctx) throw new Error('canvas context unavailable');
      j.task = page.render({ canvasContext: ctx, viewport: vp });
    } catch (err) { fail(j, err); return; }
    // pdf.js draws in ~15ms slices and asks before each next one: hold it while a gesture is running
    j.task.onContinue = (go) => { if (j.paused) j.resume = go; else go(); };
    if (kind === 'max') chip = setTimeout(() => onSharpening(true), 400);
    j.task.promise.then(() => done(j), (err) => fail(j, err));
  };

  function pump() {
    if (dead || job || !page || fit == null) return;
    const base = levels.find(l => l.kind === 'base');
    const want = fit * dpr;
    if (!base || Math.abs(base.res - want) > want * 0.1) { render('base', want); return; }
    const need = zoom * dpr; // pixels per unit this zoom asks for
    if (noMax || need <= base.res * 1.2) return;
    const cap = Math.min(Math.sqrt(budget / (size.w * size.h)), max * dpr);
    const sharp = levels.find(l => l.kind === 'max');
    if (sharp && (need <= sharp.res * 1.2 || sharp.res >= cap * 0.8)) return; // sharp enough, or as sharp as it gets
    // touch devices: straight to the budget (one render, then every zoom is instant).
    // desktop (4x the budget): only twice what is needed now; rendered again, larger, if the user goes deeper.
    let res = coarse ? cap : need * 2;
    if (res * 1.3 > cap) res = cap;
    if (res > base.res * 1.3) render('max', res);
  }

  const cancel = () => {
    if (!job) return;
    const j = job; job = null; finish();
    try { if (j.task) j.task.cancel(); } catch (e) { /* already finished */ }
  };

  // ---- gestures ---------------------------------------------------------------------------------
  const hold = () => { busy = true; clearTimeout(timer); timer = 0; if (job) job.paused = true; };
  const release = () => { busy = false; report(); settle(); };
  const stopAnim = () => { if (anim) cancelAnimationFrame(anim); anim = 0; target = null; };

  const animateTo = (to, at, ms) => {
    if (anim) cancelAnimationFrame(anim);
    anim = 0; target = null;
    const from = zoom;
    hold(); begin();
    const u = under(at);
    const stop = () => { anim = 0; target = null; commit(); release(); };
    if (Math.abs(to - from) < from * 0.001) { move(to, u, at); stop(); return; }
    target = to;
    const t0 = performance.now();
    const step = (now) => {
      const t = Math.min(1, Math.max(0, (now - t0) / ms));
      const e = 1 - (1 - t) ** 3;
      move(from * (to / from) ** e, u, at);
      if (t < 1) anim = requestAnimationFrame(step); else stop();
    };
    anim = requestAnimationFrame(step);
  };

  const deep = () => Math.min(max, isPdf ? Math.max(1.2, fit * 1.5) : fit * 3); // a comfortable reading zoom
  const toggleAt = (pt) => animateTo(zoom > fit * 1.1 ? fit : deep(), pt, 220);

  let g = null; let raf = 0; let next = null; let tap = null; let lastTap = null; let lastTouch = 0;
  const mid = (t) => ({ x: (t[0].clientX + t[1].clientX) / 2, y: (t[0].clientY + t[1].clientY) / 2 });
  const gap = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY) || 1;

  const frame = () => {
    raf = 0;
    const p = next; next = null;
    if (!g || !p) return;
    // after any change in the number of fingers the first move only sets the reference
    // (it also swallows the few px of "slop" browsers hold back at the start of a touch)
    if (g.mode !== p.n) { g.mode = p.n; g.z0 = zoom; g.d0 = p.d; g.u = under(p.at); return; }
    // the sheet point that was under the fingers when they landed stays under them:
    // two fingers zoom and drag together, a single finger that is left on the screen keeps dragging
    move(p.n === 2 ? clamp(g.z0 * (p.d / g.d0)) : zoom, g.u, p.at);
  };

  const endGesture = () => {
    if (raf) { cancelAnimationFrame(raf); frame(); }
    g = null; lastTap = null; commit(); release(); onResize();
  };

  const onTouchStart = (e) => {
    const t = e.touches;
    if (g && t.length === 1) endGesture(); // a new first finger: the previous sequence is over (its end got lost)
    if (t.length === 1) { tap = { t: e.timeStamp, x: t[0].clientX, y: t[0].clientY, still: true }; return; }
    tap = null;
    if (t.length < 2 || !ok) return;
    e.preventDefault(); // this touch sequence is ours now: no native scroll, no click
    if (!g) {
      stopAnim(); commit(); hold(); begin(); // native scrolling stays frozen until all fingers are up
      g = { mode: 0, z0: zoom, d0: 1, u: null };
    } else g.mode = 0; // a finger was added: take a new reference on the next move
  };

  const onTouchMove = (e) => {
    const t = e.touches;
    if (!g) {
      if (tap && Math.hypot(t[0].clientX - tap.x, t[0].clientY - tap.y) > 10) tap.still = false;
      return;
    }
    if (e.cancelable) e.preventDefault();
    next = t.length >= 2 ? { n: 2, d: gap(t), at: mid(t) } : { n: 1, d: 1, at: { x: t[0].clientX, y: t[0].clientY } };
    if (!raf) raf = requestAnimationFrame(frame);
  };

  const onTouchEnd = (e) => {
    const t = e.touches;
    lastTouch = Date.now();
    if (g) {
      if (t.length) { if (raf) { cancelAnimationFrame(raf); frame(); } g.mode = 0; return; } // fingers still down: two keep zooming, one keeps panning
      endGesture();
      return;
    }
    if (t.length || !tap) return;
    const c = e.changedTouches[0];
    const isTap = tap.still && e.timeStamp - tap.t < 350 && ok;
    tap = null;
    if (!isTap) { lastTap = null; return; }
    if (lastTap && e.timeStamp - lastTap.t < 350 && Math.hypot(c.clientX - lastTap.x, c.clientY - lastTap.y) < 32) {
      lastTap = null; toggleAt({ x: c.clientX, y: c.clientY });
    } else lastTap = { t: e.timeStamp, x: c.clientX, y: c.clientY };
  };

  // mouse: double-click = the same toggle (a touch double-tap also fires dblclick on some browsers — ignore that one)
  const onDblClick = (e) => { if (ok && !g && Date.now() - lastTouch > 800) toggleAt({ x: e.clientX, y: e.clientY }); };

  // trackpad pinch / ctrl+wheel on desktop
  const onWheel = (e) => {
    if (!e.ctrlKey || !ok || g) return;
    e.preventDefault();
    stopAnim(); commit(); hold(); begin();
    const at = { x: e.clientX, y: e.clientY };
    // one anchor for a whole run of wheel events (as long as the pointer stays put)
    if (!wheel || Math.hypot(at.x - wheel.at.x, at.y - wheel.at.y) > 2) wheel = { at, u: under(at) };
    move(clamp(zoom * Math.exp(-Math.max(-30, Math.min(30, e.deltaY)) * 0.01)), wheel.u, at);
    commit();
    clearTimeout(wheelEnd); wheelEnd = setTimeout(() => { wheel = null; release(); }, 120);
  };

  // ---- layout -----------------------------------------------------------------------------------
  const relayout = () => {
    if (!size || dead || g) return;
    if (anim) { stopAnim(); commit(); busy = false; }
    const cw = scroller.offsetWidth - PAD * 2; const ch = scroller.offsetHeight - PAD * 2;
    if (cw <= 0 || ch <= 0) return; // not laid out yet — the ResizeObserver calls again when it is
    const raw = Math.min(cw / size.w, ch / size.h);
    const wasFit = zoom == null || fit == null || zoom <= fit * 1.02;
    fit = Math.min(raw, 1); // small sheets are not blown up above their real size
    // deepest zoom: 400% of the real size, but no further than 4x past what the sharpest canvas can show
    const sharp = Math.sqrt(budget / (size.w * size.h)) / dpr;
    max = isPdf ? Math.min(4, Math.max(sharp * 4, raw * 4)) : Math.max(1, raw * 4);
    sizeTo(wasFit ? fit : clamp(zoom));
    report();
    if (img && !ok) { ok = true; onReady(); }
    if (page && !levels.length) pump(); else settle();
  };

  stage.style.width = '0px'; stage.style.height = '0px'; label.textContent = '';
  // the viewer was resized / the phone was rotated (a scrollbar appearing also fires the observer — that is not a resize)
  let seen = '';
  const onResize = () => {
    if (g) return; // looked at again when the fingers are up
    const now = `${scroller.offsetWidth}x${scroller.offsetHeight}`;
    if (now !== seen) { seen = now; relayout(); }
  };
  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(onResize) : null;
  if (ro) ro.observe(scroller);
  scroller.addEventListener('touchstart', onTouchStart, { passive: false });
  scroller.addEventListener('touchmove', onTouchMove, { passive: false });
  scroller.addEventListener('touchend', onTouchEnd);
  scroller.addEventListener('touchcancel', onTouchEnd);
  scroller.addEventListener('dblclick', onDblClick);
  scroller.addEventListener('wheel', onWheel, { passive: false });

  const clear = () => {
    cancel(); stopAnim(); g = null; commit(); busy = false;
    levels.forEach(l => free(l.canvas)); levels = []; shown = null;
    if (page) { try { page.cleanup(); } catch (e) { /* the document is already gone */ } } // let pdf.js drop what it kept for this page
    page = null; ok = false; noMax = false; lite = false;
  };

  return {
    // a PDF page (PDFPageProxy). The zoom the user chose is kept when moving between pages.
    setPage(p) {
      if (dead) return;
      clear(); page = p;
      const vp = p.getViewport({ scale: 1 });
      size = { w: vp.width, h: vp.height };
      scroller.scrollTop = 0;
      relayout();
    },
    setImage(w, h) {
      if (dead || !w || !h) return;
      img = true; size = { w, h }; relayout();
    },
    clear,
    zoomBy(f) { if (ok && !g) animateTo(clamp((anim ? target : zoom) * f), center(), 160); },
    fitView() { if (ok && !g) animateTo(fit, center(), 200); },
    destroy() {
      dead = true;
      clear(); clearTimeout(timer); clearTimeout(wheelEnd); wheel = null; if (raf) cancelAnimationFrame(raf);
      if (ro) ro.disconnect();
      scroller.removeEventListener('touchstart', onTouchStart);
      scroller.removeEventListener('touchmove', onTouchMove);
      scroller.removeEventListener('touchend', onTouchEnd);
      scroller.removeEventListener('touchcancel', onTouchEnd);
      scroller.removeEventListener('dblclick', onDblClick);
      scroller.removeEventListener('wheel', onWheel);
      scroller.style.overflow = '';
    },
  };
}

/**
 * PlanViewer — full-screen modal viewer for plan files.
 *
 * Renders:
 *   - PDF: loaded by react-pdf's <Document>, drawn by pdf.js onto our own canvases (see createPlanView).
 *   - Image (jpg/png/webp…): a plain <img> in the same zoomable box.
 *   - Other (dwg/dxf/xlsx): fallback message + "open in new tab" link.
 *
 * Zoom: pinch with two fingers, double-tap (in / back to the whole sheet), the + / − buttons, the
 * "whole sheet" button, and trackpad pinch / ctrl+wheel on desktop. The percentage is relative to the
 * whole-sheet view (100% = the whole sheet fits the screen).
 *
 * Coordinate system note (for P1.2): pin coordinates will be stored as proportional values in [0,1]
 * so they survive zoom changes and re-renders at different pixel resolutions.
 */
const PlanViewer = ({ plan, onClose }) => {
  const [pdf, setPdf] = useState(null);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [imgSize, setImgSize] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [sharpening, setSharpening] = useState(false);
  const [edge, setEdge] = useState({ atFit: true, atMax: false });
  const scrollerRef = useRef(null);
  const stageRef = useRef(null);
  const hostRef = useRef(null);
  const labelRef = useRef(null);
  const viewRef = useRef(null);

  const planId = plan?.id;
  const fileUrl = plan?.file_url;
  const isPdf = plan?.file_type === 'application/pdf';
  const isImage = (plan?.file_type || '').startsWith('image/');
  const canShow = isPdf || isImage;

  // one engine per opened file
  useEffect(() => {
    setPdf(null);
    setNumPages(null);
    setPageNumber(1);
    setImgSize(null);
    setLoadError(null);
    setLoading(true);
    setSharpening(false);
    setEdge({ atFit: true, atMax: false });
    if (!scrollerRef.current) return undefined;
    const view = createPlanView({
      scroller: scrollerRef.current,
      stage: stageRef.current,
      host: hostRef.current,
      label: labelRef.current,
      isPdf,
      onChange: setEdge,
      onReady: () => setLoading(false),
      onSharpening: setSharpening,
      onError: (err) => {
        console.error('[PlanViewer] render error:', err);
        setLoadError(LOAD_ERROR);
        setLoading(false);
      },
    });
    viewRef.current = view;
    return () => view.destroy();
  }, [planId, fileUrl, isPdf]);

  // PDF: hand the current page to the engine
  useEffect(() => {
    if (!pdf) return undefined;
    let stale = false;
    setLoading(true);
    if (viewRef.current) viewRef.current.clear();
    pdf.getPage(pageNumber).then(
      (page) => { if (!stale && viewRef.current) viewRef.current.setPage(page); },
      (err) => {
        if (stale) return;
        console.error('[PlanViewer] page load error:', err);
        setLoadError(LOAD_ERROR);
        setLoading(false);
      },
    );
    return () => { stale = true; };
  }, [pdf, pageNumber]);

  // image: hand its real size to the engine once it has loaded
  useEffect(() => {
    if (imgSize && viewRef.current) viewRef.current.setImage(imgSize.w, imgSize.h);
  }, [imgSize]);

  const handleLoadSuccess = useCallback((doc) => {
    setNumPages(doc.numPages);
    setPdf(doc);
  }, []);

  const handleLoadError = useCallback((error) => {
    console.error('[PlanViewer] PDF load error:', error);
    setLoadError(LOAD_ERROR);
    setLoading(false);
  }, []);

  const zoomIn = useCallback(() => { if (viewRef.current) viewRef.current.zoomBy(STEP); }, []);
  const zoomOut = useCallback(() => { if (viewRef.current) viewRef.current.zoomBy(1 / STEP); }, []);
  const fitView = useCallback(() => { if (viewRef.current) viewRef.current.fitView(); }, []);
  const prevPage = useCallback(() => setPageNumber(p => Math.max(p - 1, 1)), []);
  const nextPage = useCallback(() => setPageNumber(p => Math.min(p + 1, numPages || 1)), [numPages]);

  if (!plan) return null;

  const off = loading || !!loadError || !canShow;
  const barBtn = 'w-11 h-11 flex items-center justify-center hover:bg-slate-700 disabled:opacity-30 rounded-lg transition-colors';

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-slate-900" dir="rtl">
      {/* Top bar — title + page counter + external open + download + close */}
      <div className="flex items-center justify-between gap-2 px-2 py-2 bg-slate-800 text-white shrink-0">
        <div className="flex items-center gap-2 min-w-0 px-2">
          <h3 className="text-sm font-bold truncate">
            {plan.name || plan.original_filename}
          </h3>
          {isPdf && numPages > 1 && (
            <span className="text-xs text-slate-300 bg-slate-700 px-2 py-0.5 rounded shrink-0">
              {pageNumber} / {numPages}
            </span>
          )}
        </div>
        <div className="flex items-center shrink-0">
          <a
            href={plan.file_url}
            target="_blank"
            rel="noopener noreferrer"
            className={barBtn}
            title="פתח בכרטיסייה חדשה"
            aria-label="פתח בכרטיסייה חדשה"
          >
            <Eye className="w-5 h-5" />
          </a>
          <a
            href={plan.file_url}
            download={plan.original_filename || plan.name}
            className={barBtn}
            title="הורד"
            aria-label="הורד"
          >
            <Download className="w-5 h-5" />
          </a>
          <button onClick={onClose} className={barBtn} aria-label="סגור">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Viewer area. The scroller is a plain native scroll container (one-finger pan, scrollbars on desktop);
           the inner wrapper centers the sheet while it is smaller than the screen and grows with it otherwise
           (min-w-full + w-fit). direction is set INLINE: index.css has `* { direction: rtl }`, which beats the
           dir attribute, and the scroll math is simplest in ltr. touchAction 'pan-x pan-y' keeps the browser's
           own pinch-zoom and double-tap-zoom away; our two-finger handling lives in createPlanView. */}
      <div className="relative flex-1 min-h-0 bg-slate-700">
        <div
          ref={scrollerRef}
          className="absolute inset-0 overflow-auto overscroll-contain select-none [&::-webkit-scrollbar]:w-3 [&::-webkit-scrollbar]:h-3 [&::-webkit-scrollbar-thumb]:bg-white/35 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-transparent [&::-webkit-scrollbar-thumb]:bg-clip-content [&::-webkit-scrollbar-thumb]:hover:bg-white/55 [&::-webkit-scrollbar-track]:bg-black/20 [&::-webkit-scrollbar-corner]:bg-black/20"
          style={{ direction: 'ltr', touchAction: 'pan-x pan-y', WebkitTapHighlightColor: 'transparent' }}
        >
          <div className="min-w-full min-h-full w-fit flex items-center justify-center p-4">
            <div ref={stageRef} className={`relative flex-none origin-top-left will-change-transform ${off ? 'invisible' : ''}`}>
              {isImage && (
                <img
                  src={plan.file_url}
                  alt={plan.name || ''}
                  draggable={false}
                  onLoad={(e) => setImgSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
                  onError={() => { setLoadError(LOAD_ERROR); setLoading(false); }}
                  className="block w-full h-full pointer-events-none"
                  style={{ maxWidth: 'none' }}
                />
              )}
              <div ref={hostRef} className="absolute inset-0 pointer-events-none" />
            </div>
          </div>
        </div>

        {isPdf && !loadError && (
          <Document
            file={plan.file_url}
            options={PDF_OPTIONS}
            onLoadSuccess={handleLoadSuccess}
            onLoadError={handleLoadError}
            loading=""
            error=""
            className="hidden"
          />
        )}

        {loading && canShow && !loadError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white pointer-events-none">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm">טוען תוכנית…</span>
          </div>
        )}

        {sharpening && !off && (
          <div className="absolute top-3 inset-x-0 flex justify-center pointer-events-none">
            <span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 text-white text-xs">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              מחדד…
            </span>
          </div>
        )}

        {loadError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-white p-6 text-center">
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

        {!canShow && !loadError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-white p-6 text-center">
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

      {/* Bottom bar — zoom + whole sheet, and page nav for multi-page PDFs. Two groups: on a very narrow phone the
           page group moves to a second row as a whole. */}
      <div className="flex flex-wrap items-center justify-center gap-x-3 px-2 py-2 bg-slate-800 text-white shrink-0">
        <div className="flex items-center gap-1">
          <button onClick={zoomOut} disabled={off || edge.atFit} className={barBtn} aria-label="הקטנה">
            <ZoomOut className="w-5 h-5" />
          </button>
          <span ref={labelRef} className={`text-xs text-slate-300 min-w-[2.75rem] text-center ${off ? 'invisible' : ''}`} />
          <button onClick={zoomIn} disabled={off || edge.atMax} className={barBtn} aria-label="הגדלה">
            <ZoomIn className="w-5 h-5" />
          </button>
          <button onClick={fitView} disabled={off || edge.atFit} className={barBtn} title="כל התוכנית" aria-label="כל התוכנית">
            <Maximize className="w-5 h-5" />
          </button>
        </div>

        {isPdf && numPages > 1 && (
          <div className="flex items-center gap-1">
            <button onClick={prevPage} disabled={pageNumber <= 1} className={barBtn} aria-label="עמוד קודם">
              <ChevronRight className="w-5 h-5" />
            </button>
            <span className="text-xs text-slate-300 min-w-[2.5rem] text-center">
              {pageNumber} / {numPages}
            </span>
            <button onClick={nextPage} disabled={pageNumber >= numPages} className={barBtn} aria-label="עמוד הבא">
              <ChevronLeft className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default PlanViewer;
