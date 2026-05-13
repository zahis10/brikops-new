import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { Undo2, Save, Loader2, X } from 'lucide-react';

const MAX_CANVAS_SIZE = 1280;
const VISUAL_LINE_WIDTH = 4;
const COLORS = [
  { value: '#ef4444', label: 'אדום' },
  { value: '#3b82f6', label: 'כחול' },
  { value: '#000000', label: 'שחור' },
];

// BATCH F (2026-05-12) — text label rendering constants. Sizes are
// "visual" (display px) and divided by scaleRef before drawing on
// canvas, matching the convention used by getLineWidth/getPos.
const FONT_STACK = '"Heebo", "Arial Hebrew", "Noto Sans Hebrew", system-ui, sans-serif';
const TEXT_FONT_SIZE = 18;
const TEXT_PADDING_X = 10;
const TEXT_PADDING_Y = 6;
const TEXT_PILL_RADIUS = 8;
// BATCH F.1a (2026-05-12) — text size multipliers. Applied to
// TEXT_FONT_SIZE in the redraw text branch. Pill padding scales
// with the same multiplier (already proportional to font size via
// padX/padY math + metrics.width).
const SIZE_MULTIPLIERS = { small: 0.7, medium: 1.0, large: 1.4 };
// BATCH F.1b (2026-05-12) — drag threshold in canvas-space pixels.
// Below this distance from start tap = treated as a tap (reserved
// for F.1c edit). At or above = drag commits and mutates stroke
// position. Matches CLAUDE.md drag-threshold rule.
const DRAG_THRESHOLD_PX = 10;

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new window.Image();
    img.onload = () => {
      resolve({ img, url });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Image load failed'));
    };
    img.src = url;
  });
}

const PhotoAnnotation = ({ imageFile, onSave, onDiscard }) => {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const urlRef = useRef(null);
  const containerRef = useRef(null);
  const [color, setColor] = useState('#ef4444');
  const colorRef = useRef('#ef4444');
  const onSaveRef = useRef(onSave);
  // BATCH F.2 (2026-05-13) — onDiscard is OPTIONAL. If provided,
  // the X button calls it directly (no upload). If absent, the X
  // button falls back to onSave(null, false) for backward compat
  // — though all current 7 render sites pass onDiscard explicitly.
  const onDiscardRef = useRef(onDiscard);
  const [strokes, setStrokes] = useState([]);
  const strokesRef = useRef([]);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const scaleRef = useRef(1);
  const drawingRef = useRef(false);
  const currentStrokeRef = useRef(null);

  // BATCH F (2026-05-12) — tool mode + pending text input state.
  // tool: 'draw' (existing freehand) | 'text' (new label).
  // pendingText: null | { x, y, value } where (x,y) are CANVAS coords.
  const [tool, setTool] = useState('draw');
  const toolRef = useRef('draw');
  const [pendingText, setPendingText] = useState(null);
  // BATCH F.1a (2026-05-12) — text size state. Default 'medium'
  // preserves F behavior. Captured at COMMIT time (same as color)
  // so changing size while typing is reflected in the final render.
  const [textSize, setTextSize] = useState('medium');
  const textSizeRef = useRef('medium');
  // BATCH F.1b (2026-05-12) — drag state for text labels.
  // null = no drag interaction. Otherwise:
  //   { strokeIndex, startTapX, startTapY,
  //     origStrokeX, origStrokeY, hasMovedPastThreshold }
  // strokeIndex points into strokesRef.current array.
  // (start, orig) captured at tap. Drag delta = (currentPos - startTap).
  // hasMovedPastThreshold: once true, stays true for this interaction.
  const draggingTextRef = useRef(null);

  useEffect(() => { colorRef.current = color; }, [color]);
  useEffect(() => { onSaveRef.current = onSave; }, [onSave]);
  useEffect(() => { onDiscardRef.current = onDiscard; }, [onDiscard]);
  useEffect(() => { strokesRef.current = strokes; }, [strokes]);
  useEffect(() => { toolRef.current = tool; }, [tool]);
  useEffect(() => { textSizeRef.current = textSize; }, [textSize]);

  const savingRef = useRef(false);
  useEffect(() => { savingRef.current = saving; }, [saving]);

  useEffect(() => {
    const viewport = document.querySelector('meta[name="viewport"]');
    const originalViewport = viewport?.content;
    if (viewport) {
      viewport.content = 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no';
    }
    return () => {
      document.body.style.pointerEvents = '';
      document.body.style.overflow = '';
      if (viewport && originalViewport !== undefined) viewport.content = originalViewport;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const doLoad = async () => {
      const { img, url } = await loadImageFromFile(imageFile);

      if (cancelled) {
        URL.revokeObjectURL(url);
        return;
      }

      urlRef.current = url;

      let w = img.naturalWidth || img.width;
      let h = img.naturalHeight || img.height;
      if (w > MAX_CANVAS_SIZE || h > MAX_CANVAS_SIZE) {
        const ratio = Math.min(MAX_CANVAS_SIZE / w, MAX_CANVAS_SIZE / h);
        w = Math.round(w * ratio);
        h = Math.round(h * ratio);
      }

      imgRef.current = img;

      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = w;
      canvas.height = h;

      // BATCH F-keyboard — apply initial scale via the same callback
      // that listens to viewport resize. Keeps the math in one place.
      applyDisplayScale();

      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      setLoaded(true);
    };

    doLoad().catch(() => {
      if (!cancelled) onSaveRef.current(null, false);
    });

    return () => {
      cancelled = true;
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    };
    // BATCH F-keyboard — DO NOT add applyDisplayScale to deps.
    //
    // doLoad uses applyDisplayScale, but the const is declared LATER
    // in the file (after redraw, which is after this useEffect).
    // Adding it to the deps array would evaluate the binding at this
    // line, in TDZ → ReferenceError at first render. v1 of this
    // batch tried that and crashed staging — reverted 2026-05-12.
    //
    // SAFE because: applyDisplayScale identity is STABLE
    // (deps chain: getLineWidth[] → redraw[getLineWidth] →
    // applyDisplayScale[redraw]). The closure inside doLoad captures
    // it lexically; by commit phase all consts are initialized.
    //
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageFile]);

  const getLineWidth = useCallback(() => {
    const scale = scaleRef.current;
    return scale > 0 ? VISUAL_LINE_WIDTH / scale : VISUAL_LINE_WIDTH;
  }, []);

  const redraw = useCallback((allStrokes) => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    const lw = getLineWidth();
    for (const stroke of allStrokes) {
      // BATCH F (2026-05-12) — type discriminator. Default 'stroke'
      // for backward compat with any in-memory strokes that pre-date
      // the migration (existing strokes have no `type` field).
      const strokeType = stroke.type || 'stroke';

      if (strokeType === 'text') {
        // Render centered white-pill at (x, y) with colored text.
        // Sizes are display-px values divided by scaleRef so visual
        // size stays consistent across image-resize ratios.
        const scale = scaleRef.current || 1;
        // BATCH F.1a — apply size multiplier. Default 'medium' for old
        // text strokes that pre-date this batch (backward compat).
        const sizeMultiplier = SIZE_MULTIPLIERS[stroke.size || 'medium'] || 1.0;
        const fontSize = (TEXT_FONT_SIZE * sizeMultiplier) / scale;
        const padX = TEXT_PADDING_X / scale;
        const padY = TEXT_PADDING_Y / scale;
        const radius = TEXT_PILL_RADIUS / scale;

        ctx.save();
        ctx.font = `bold ${fontSize}px ${FONT_STACK}`;
        ctx.direction = 'rtl';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'center';

        const metrics = ctx.measureText(stroke.text || '');
        const textWidth = metrics.width;
        const textHeight = fontSize;
        const rectWidth = textWidth + padX * 2;
        const rectHeight = textHeight + padY * 2;
        const rectX = stroke.x - rectWidth / 2;
        const rectY = stroke.y - rectHeight / 2;

        // BATCH F.1b-hotfix-1 (2026-05-12) — cache bbox on stroke object
        // so hitTestText reads the EXACT same rect that was rendered.
        // Avoids font/direction-sensitive measureText re-computation and
        // any platform-specific WebKit drift.
        stroke._bbox = { x: rectX, y: rectY, width: rectWidth, height: rectHeight };

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        if (typeof ctx.roundRect === 'function') {
          ctx.roundRect(rectX, rectY, rectWidth, rectHeight, radius);
        } else {
          ctx.rect(rectX, rectY, rectWidth, rectHeight);
        }
        ctx.fill();

        ctx.lineWidth = Math.max(1, 1.5 / scale);
        ctx.strokeStyle = '#1f2937';
        ctx.stroke();

        ctx.fillStyle = stroke.color || '#000000';
        ctx.fillText(stroke.text || '', stroke.x, stroke.y);
        ctx.restore();
        continue;
      }

      if (!stroke.points || stroke.points.length < 2) continue;
      ctx.beginPath();
      ctx.strokeStyle = stroke.color;
      ctx.lineWidth = lw;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      ctx.stroke();
    }
  }, [getLineWidth]);

  // BATCH F-keyboard (2026-05-12) — recompute canvas display
  // dimensions based on the current visual viewport. Called on
  // image load AND on viewport resize (mobile keyboard pop). The
  // intrinsic canvas resolution (canvas.width / canvas.height)
  // stays fixed — we only update CSS display size + scaleRef.
  // After resize, redraw refreshes the bbox cache for hit-testing.
  const applyDisplayScale = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    const w = canvas.width;
    const h = canvas.height;
    if (!w || !h) return;
    const vv = window.visualViewport;
    const containerW = vv ? vv.width : window.innerWidth;
    const containerH = (vv ? vv.height : window.innerHeight) - 120;
    const displayScale = Math.min(containerW / w, containerH / h, 1);
    scaleRef.current = displayScale;
    canvas.style.width = Math.round(w * displayScale) + 'px';
    canvas.style.height = Math.round(h * displayScale) + 'px';
    redraw(strokesRef.current);
  }, [redraw]);

  // BATCH F-keyboard (2026-05-12) — listen for viewport changes
  // (mobile keyboard appearance is the primary use case) and
  // recompute the canvas display scale. Without this, the canvas
  // keeps its original dimensions and gets clipped behind the
  // keyboard, appearing zoomed-in.
  useEffect(() => {
    if (!loaded) return;

    const vv = window.visualViewport;
    if (vv) {
      vv.addEventListener('resize', applyDisplayScale);
    }
    window.addEventListener('resize', applyDisplayScale);

    return () => {
      if (vv) {
        vv.removeEventListener('resize', applyDisplayScale);
      }
      window.removeEventListener('resize', applyDisplayScale);
    };
  }, [loaded, applyDisplayScale]);

  // BATCH F.1b (2026-05-12) — hit-test against existing text labels.
  // Given a canvas-space position, return the index of the topmost
  // text stroke whose pill bbox contains the position, or -1 if none.
  // Iterates strokesRef in REVERSE order — last drawn = topmost = first to hit.
  // Math mirrors redraw's text-branch exactly (same scale, font, padding).
  const hitTestText = useCallback((pos) => {
    // BATCH F.1b-hotfix-1 (2026-05-12) — read cached bbox from the
    // last redraw instead of re-measuring. Guarantees hit-test
    // matches the visible pill exactly. Falls back to a 44-display-
    // pixel minimum touch area around the stroke center for finger-
    // friendly tap targets (CLAUDE.md touch-target rule).
    const scale = scaleRef.current || 1;
    const minTouchCanvas = 44 / scale; // 44 display px → canvas px

    for (let i = strokesRef.current.length - 1; i >= 0; i--) {
      const s = strokesRef.current[i];
      if ((s.type || 'stroke') !== 'text') continue;

      let bx, by, bw, bh;
      if (s._bbox) {
        bx = s._bbox.x;
        by = s._bbox.y;
        bw = s._bbox.width;
        bh = s._bbox.height;

        // Expand to at least the minimum touch area if pill is small.
        if (bw < minTouchCanvas) {
          bx = s.x - minTouchCanvas / 2;
          bw = minTouchCanvas;
        }
        if (bh < minTouchCanvas) {
          by = s.y - minTouchCanvas / 2;
          bh = minTouchCanvas;
        }
      } else {
        // No cached bbox (shouldn't happen — redraw runs after every
        // commit). Defensive fallback: 44×44 around stroke center.
        bx = s.x - minTouchCanvas / 2;
        by = s.y - minTouchCanvas / 2;
        bw = minTouchCanvas;
        bh = minTouchCanvas;
      }

      if (
        pos.x >= bx && pos.x <= bx + bw &&
        pos.y >= by && pos.y <= by + bh
      ) {
        return i;
      }
    }
    return -1;
  }, []);

  const getPos = useCallback((clientX, clientY) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scale = scaleRef.current;
    return {
      x: (clientX - rect.left) / scale,
      y: (clientY - rect.top) / scale,
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !loaded) return;

    const startStroke = (pos) => {
      // BATCH F (2026-05-12) — branch on tool. In text mode, tap
      // opens the inline overlay at the tap position. If a
      // pendingText already exists (user tapped, started typing,
      // then tapped a different spot before committing), preserve
      // the typed value and only update position — intuitive
      // "let me move it before saving". To start fresh, user must
      // tap "ביטול" first.
      if (toolRef.current === 'text') {
        // BATCH F.1b — hit-test FIRST. If user tapped on an existing
        // text label, start a drag interaction instead of opening
        // pendingText. Drag commits only if movement >= threshold,
        // otherwise it's a tap (reserved for F.1c edit — no-op for now).
        const hitIndex = hitTestText(pos);
        if (hitIndex >= 0) {
          const s = strokesRef.current[hitIndex];
          draggingTextRef.current = {
            strokeIndex: hitIndex,
            startTapX: pos.x,
            startTapY: pos.y,
            origStrokeX: s.x,
            origStrokeY: s.y,
            hasMovedPastThreshold: false,
          };
          return;
        }
        setPendingText(prev =>
          prev
            ? { ...prev, x: pos.x, y: pos.y }
            : { x: pos.x, y: pos.y, value: '' }
        );
        return;
      }
      const newStroke = { type: 'stroke', color: colorRef.current, points: [pos] };
      currentStrokeRef.current = newStroke;
      drawingRef.current = true;
    };

    const moveStroke = (pos) => {
      // BATCH F.1b — text drag branch (precedes the freehand path).
      if (draggingTextRef.current) {
        const drag = draggingTextRef.current;
        const dx = pos.x - drag.startTapX;
        const dy = pos.y - drag.startTapY;

        if (!drag.hasMovedPastThreshold) {
          // Squared distance check — avoids Math.sqrt per move event.
          const threshSq = DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX;
          if (dx * dx + dy * dy < threshSq) return;
          drag.hasMovedPastThreshold = true;
        }

        // Mutate in place — avoids per-frame re-render (Mode B lesson
        // from P1.1 pinch saga). Final state sync happens in endStroke.
        const stroke = strokesRef.current[drag.strokeIndex];
        if (stroke && (stroke.type || 'stroke') === 'text') {
          stroke.x = drag.origStrokeX + dx;
          stroke.y = drag.origStrokeY + dy;
          redraw(strokesRef.current);
        }
        return;
      }

      if (!drawingRef.current || !currentStrokeRef.current) return;
      currentStrokeRef.current = {
        ...currentStrokeRef.current,
        points: [...currentStrokeRef.current.points, pos],
      };
      setStrokes(allStrokes => {
        redraw([...allStrokes, currentStrokeRef.current]);
        return allStrokes;
      });
    };

    const endStroke = () => {
      // BATCH F.1b — text drag branch (precedes the freehand path).
      if (draggingTextRef.current) {
        const drag = draggingTextRef.current;
        draggingTextRef.current = null;

        if (drag.hasMovedPastThreshold) {
          // BATCH F.1b — strokesRef was mutated in place — sync to React
          // state so undo stack + parent re-renders see the new position.
          setStrokes([...strokesRef.current]);
          return;
        }

        // BATCH F.1c (2026-05-12) — pure tap on an existing label (no
        // movement past threshold) = open edit overlay prefilled with
        // the label's current text/color/size. editingIndex tells
        // commitPendingText to REPLACE (not append). Color/size set
        // via state setters so the toolbar UI also reflects the
        // edited label's properties.
        const stroke = strokesRef.current[drag.strokeIndex];
        if (stroke && (stroke.type || 'stroke') === 'text') {
          setPendingText({
            x: stroke.x,
            y: stroke.y,
            value: stroke.text || '',
            editingIndex: drag.strokeIndex,
          });
          setColor(stroke.color || '#ef4444');
          setTextSize(stroke.size || 'medium');
        }
        return;
      }

      if (!drawingRef.current) return;
      drawingRef.current = false;
      const stroke = currentStrokeRef.current;
      currentStrokeRef.current = null;
      if (stroke && stroke.points.length >= 2) {
        setStrokes(prev => {
          const newAll = [...prev, stroke];
          redraw(newAll);
          return newAll;
        });
      }
    };

    const handleTouchStart = (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      if (!touch) return;
      const pos = getPos(touch.clientX, touch.clientY);
      if (pos) startStroke(pos);
    };

    const handleTouchMove = (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      if (!touch) return;
      const pos = getPos(touch.clientX, touch.clientY);
      if (pos) moveStroke(pos);
    };

    const handleTouchEnd = (e) => {
      e.preventDefault();
      endStroke();
    };

    const handleMouseDown = (e) => {
      const pos = getPos(e.clientX, e.clientY);
      if (pos) startStroke(pos);
    };

    const handleMouseMove = (e) => {
      if (!(e.buttons & 1)) return;
      const pos = getPos(e.clientX, e.clientY);
      if (pos) moveStroke(pos);
    };

    const handleMouseUp = () => {
      endStroke();
    };

    canvas.addEventListener('touchstart', handleTouchStart, { passive: false });
    canvas.addEventListener('touchmove', handleTouchMove, { passive: false });
    canvas.addEventListener('touchend', handleTouchEnd, { passive: false });
    canvas.addEventListener('touchcancel', handleTouchEnd, { passive: false });
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);

    return () => {
      canvas.removeEventListener('touchstart', handleTouchStart);
      canvas.removeEventListener('touchmove', handleTouchMove);
      canvas.removeEventListener('touchend', handleTouchEnd);
      canvas.removeEventListener('touchcancel', handleTouchEnd);
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseup', handleMouseUp);
    };
  }, [loaded, getPos, redraw, hitTestText]);

  const handleUndo = useCallback(() => {
    setStrokes(prev => {
      const next = prev.slice(0, -1);
      redraw(next);
      return next;
    });
  }, [redraw]);

  // BATCH F.2 (2026-05-13) — discard handler. Confirms before
  // closing if user has made annotations. Prefers onDiscard
  // callback (no upload); falls back to onSave(null, false) for
  // backward compat with any consumer that didn't wire onDiscard
  // (NOTE: as of this batch, all 7 known consumers do).
  const handleDiscard = useCallback(() => {
    if (strokesRef.current.length > 0) {
      if (!window.confirm('לבטל את כל השינויים ולסגור?')) return;
    }
    if (onDiscardRef.current) {
      onDiscardRef.current();
    } else {
      // Fallback: legacy abandonment signal. Consumer may interpret
      // as "upload raw photo" — that's the v1 bug we're fixing here
      // by adding onDiscard to all known consumers. Future-proof
      // fallback only.
      onSaveRef.current(null, false);
    }
  }, []);

  // BATCH F (2026-05-12) — commit pending text label.
  // DESIGN DECISION: color is captured at COMMIT time (not at tap
  // time). User can change color while typing — the "אישור" press
  // is their final intent. Avoids surprising "I selected red after
  // I tapped!" behavior.
  const commitPendingText = useCallback(() => {
    setPendingText(curr => {
      if (!curr || !curr.value.trim()) return null;
      const textStroke = {
        type: 'text',
        color: colorRef.current,
        // BATCH F.1a — capture size at commit time (same pattern as color).
        size: textSizeRef.current,
        x: curr.x,
        y: curr.y,
        text: curr.value.trim(),
      };

      // BATCH F.1c (2026-05-12) — branch on editingIndex. If set,
      // REPLACE the stroke at that index (preserves array order
      // + undo stack semantics). Else APPEND (F behavior).
      // _bbox is intentionally omitted from the new stroke — the
      // next redraw populates it freshly with the updated dimensions.
      if (typeof curr.editingIndex === 'number') {
        strokesRef.current = strokesRef.current.map((s, i) =>
          i === curr.editingIndex ? textStroke : s
        );
        setStrokes([...strokesRef.current]);
      } else {
        strokesRef.current = [...strokesRef.current, textStroke];
        setStrokes(prev => [...prev, textStroke]);
      }
      redraw([...strokesRef.current]);
      return null;
    });
    // BATCH F.1a — reset to default for next label.
    setTextSize('medium');
  }, [redraw]);

  const handleSave = useCallback(() => {
    if (currentStrokeRef.current && drawingRef.current) {
      const stroke = currentStrokeRef.current;
      currentStrokeRef.current = null;
      drawingRef.current = false;
      if (stroke.points.length >= 1) {
        strokesRef.current = [...strokesRef.current, stroke];
        setStrokes(prev => [...prev, stroke]);
        redraw([...strokesRef.current]);
      }
    }
    if (saving) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    setSaving(true);

    const hasAnnotations = strokesRef.current.length > 0;
    if (!hasAnnotations) {
      onSaveRef.current(null, false);
      return;
    }

    canvas.toBlob(
      (blob) => {
        if (!blob || blob.size === 0) {
          setSaving(false);
          return;
        }

        const file = new File([blob], 'annotated.jpg', { type: 'image/jpeg' });
        onSaveRef.current(file, true);
      },
      'image/jpeg',
      0.70
    );
  }, [saving, redraw]);

  const content = (
    <div className="fixed inset-0 bg-black flex flex-col h-dvh-fallback" dir="rtl"
         style={{ zIndex: 10001, pointerEvents: 'auto' }}
>
      {!loaded && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black"
             style={{ pointerEvents: 'none' }}>
          <div className="text-white text-sm">טוען תמונה...</div>
        </div>
      )}

      <div className="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-700 shrink-0"
           style={{ position: 'relative', zIndex: 20 }}>
        <div className="flex items-center gap-2">
          {COLORS.map(c => (
            <button
              key={c.value}
              onClick={(e) => { e.stopPropagation(); setColor(c.value); }}
              className={`w-8 h-8 rounded-full border-2 transition-transform ${
                color === c.value ? 'border-white scale-110' : 'border-slate-600'
              }`}
              style={{ backgroundColor: c.value }}
              title={c.label}
            />
          ))}
          {/* BATCH F (2026-05-12) — text tool toggle. */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setTool(prev => (prev === 'text' ? 'draw' : 'text'));
            }}
            aria-label={tool === 'text' ? 'מצב ציור' : 'מצב טקסט'}
            title={tool === 'text' ? 'מצב טקסט פעיל — לחץ למצב ציור' : 'הוסף תווית טקסט'}
            className={`w-8 h-8 rounded-full border-2 flex items-center justify-center font-bold text-sm transition-transform ${
              tool === 'text'
                ? 'border-white bg-white text-slate-900 scale-110'
                : 'border-slate-600 bg-slate-700 text-white'
            }`}
          >
            T
          </button>
        </div>

        {/* BATCH F.2 (2026-05-13) — discard button. Closes the modal
            without saving. Confirmation only when user has drawn or
            added text. RTL places this on the visual LEFT, opposite
            the color/T cluster. */}
        <button
          onClick={(e) => { e.stopPropagation(); handleDiscard(); }}
          aria-label="סגור ללא שמירה"
          title="סגור ללא שמירה"
          className="w-8 h-8 rounded-full flex items-center justify-center text-slate-300 hover:bg-slate-700 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center overflow-hidden"
        style={{ touchAction: 'none', WebkitUserSelect: 'none', userSelect: 'none', WebkitTouchCallout: 'none' }}
      >
        <canvas
          ref={canvasRef}
          style={{
            touchAction: 'none',
            display: 'block',
            // BATCH F.1b — desktop cursor hint: grab in text mode,
            // grabbing during active drag. Mobile has no hover so this
            // only affects desktop preview. Note: ref doesn't trigger
            // re-render so live grab→grabbing flip is best-effort.
            cursor: tool === 'text'
              ? (draggingTextRef.current?.hasMovedPastThreshold ? 'grabbing' : 'grab')
              : 'crosshair',
          }}
        />
      </div>

      {/* BATCH F (2026-05-12) — pending text input overlay.
          Renders above the action bar when user has tapped in text mode.
          Input has font-size >= 16px to prevent iOS auto-zoom. */}
      {pendingText && (
        <div className="flex items-center gap-2 px-4 py-2 bg-slate-800 border-t border-slate-700 shrink-0"
             style={{ position: 'relative', zIndex: 20 }}>
          <input
            type="text"
            autoFocus
            maxLength={30}
            value={pendingText.value}
            onChange={(e) => setPendingText(p => p ? { ...p, value: e.target.value } : p)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && pendingText.value.trim()) {
                commitPendingText();
              } else if (e.key === 'Escape') {
                setPendingText(null);
              }
            }}
            placeholder="תווית קצרה (עד 30 תווים)"
            dir="auto"
            className="flex-1 px-3 py-2 rounded-lg bg-slate-900 text-white border border-slate-600 focus:border-amber-500 focus:outline-none"
            style={{
              fontSize: '16px',
              fontFamily: 'Heebo, "Arial Hebrew", system-ui, sans-serif',
            }}
          />
          {/* BATCH F.1a (2026-05-12) — text size picker. 3 discrete sizes;
              capture at commit (same pattern as color). Each button shows
              "א" at its actual relative size for visual preview. */}
          <div className="flex items-center gap-1 shrink-0">
            {[
              { key: 'small',  fontPx: 12, label: 'קטן' },
              { key: 'medium', fontPx: 16, label: 'בינוני' },
              { key: 'large',  fontPx: 20, label: 'גדול' },
            ].map(opt => (
              <button
                key={opt.key}
                onClick={(e) => { e.stopPropagation(); setTextSize(opt.key); }}
                aria-label={opt.label}
                title={opt.label}
                className={`w-8 h-8 rounded-full border-2 flex items-center justify-center font-bold transition-transform ${
                  textSize === opt.key
                    ? 'border-white bg-white text-slate-900 scale-110'
                    : 'border-slate-600 bg-slate-700 text-white'
                }`}
                style={{ fontSize: `${opt.fontPx}px`, lineHeight: 1 }}
              >
                א
              </button>
            ))}
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); commitPendingText(); }}
            disabled={!pendingText.value.trim()}
            className="px-4 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium disabled:opacity-40"
          >
            אישור
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              // BATCH F.1c — capture whether we were editing BEFORE
              // clearing pendingText. If editing, don't reset picker
              // state (user might still want to apply their selected
              // color/size to the next interaction).
              const wasEditing = typeof pendingText?.editingIndex === 'number';
              setPendingText(null);
              if (!wasEditing) {
                // BATCH F.1a — reset size to default after cancel
                // of a NEW label only.
                setTextSize('medium');
              }
            }}
            className="px-3 py-2 rounded-lg bg-slate-700 text-slate-300 text-sm"
          >
            ביטול
          </button>
        </div>
      )}

      <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-t border-slate-700 shrink-0"
           style={{ position: 'relative', zIndex: 20 }}>
        <button
          onClick={(e) => { e.stopPropagation(); handleSave(); }}
          disabled={!loaded || saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-amber-500 text-white rounded-xl font-medium text-sm hover:bg-amber-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'שומר...' : 'שמור'}
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); handleUndo(); }}
          disabled={strokes.length === 0}
          className="flex items-center gap-2 px-4 py-2.5 bg-slate-700 text-slate-300 rounded-xl text-sm hover:bg-slate-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Undo2 className="w-4 h-4" />
          בטל
        </button>
      </div>
    </div>
  );

  return ReactDOM.createPortal(content, document.body);
};

export default PhotoAnnotation;
