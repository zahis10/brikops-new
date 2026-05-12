import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { Undo2, Save, Loader2 } from 'lucide-react';

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
// BATCH F.1 (2026-05-12) — size picker: 3 fixed sizes mapped to
// display px. Default 'M' matches v1's TEXT_FONT_SIZE=18 exactly so
// v1 strokes without `size` field render identically.
const TEXT_SIZE_PX = { S: 14, M: 18, L: 24 };
const TEXT_SIZE_LABELS = { S: 'ק', M: 'ב', L: 'ג' };  // קטן/בינוני/גדול
const TEXT_DEFAULT_SIZE = 'M';
const TEXT_PADDING_X = 10;
const TEXT_PADDING_Y = 6;
const TEXT_PILL_RADIUS = 8;
// BATCH F.1 (2026-05-12) — drag threshold = 10px in canvas coords.
// 5px was too sensitive: Android budget devices (~5-8px jitter) +
// field conditions (gloves, dirty hands, ~10-15px jitter) would
// turn every tap into a drag → user can't tap-to-edit. Asymmetric
// risk favors edit-friendly threshold: too low = broken UX, too
// high = slight friction. Tune down if field reports show users
// can't move labels easily.
const DRAG_THRESHOLD_PX = 10;
// BATCH F (kept for back-compat with stored strokes that pre-date F.1)
const TEXT_FONT_SIZE = TEXT_SIZE_PX[TEXT_DEFAULT_SIZE];

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

const PhotoAnnotation = ({ imageFile, onSave }) => {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const urlRef = useRef(null);
  const containerRef = useRef(null);
  const [color, setColor] = useState('#ef4444');
  const colorRef = useRef('#ef4444');
  const onSaveRef = useRef(onSave);
  const [strokes, setStrokes] = useState([]);
  const strokesRef = useRef([]);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const scaleRef = useRef(1);
  const drawingRef = useRef(false);
  const currentStrokeRef = useRef(null);

  // BATCH F (2026-05-12) — tool mode + pending text input state.
  // tool: 'draw' (existing freehand) | 'text' (new label).
  // pendingText: null | { x, y, value, size, editIndex? } where (x,y) are CANVAS coords.
  //   - editIndex absent: creating new text (existing v1 flow)
  //   - editIndex present: editing existing stroke; commit updates
  //     instead of appending; "מחק" button visible.
  const [tool, setTool] = useState('draw');
  const toolRef = useRef('draw');
  const [pendingText, setPendingText] = useState(null);

  // BATCH F.1 (2026-05-12) — drag tracking + edit mode.
  // dragRef: { index, startPos, hasMoved } | null
  //   - index: which stroke in strokesRef is being dragged
  //   - startPos: tap start position (canvas coords) for threshold
  //   - hasMoved: true once movement exceeded DRAG_THRESHOLD_PX
  const dragRef = useRef(null);
  // BATCH F.1 (2026-05-12) — save the global color before edit-mode
  // syncs the picker to the target's color. Restored when overlay
  // commits/cancels/deletes so user's "current" color choice isn't
  // silently overwritten by editing a label of a different color.
  const savedColorRef = useRef(null);

  useEffect(() => { colorRef.current = color; }, [color]);
  useEffect(() => { onSaveRef.current = onSave; }, [onSave]);
  useEffect(() => { strokesRef.current = strokes; }, [strokes]);
  useEffect(() => { toolRef.current = tool; }, [tool]);

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

      const containerW = window.innerWidth;
      const containerH = window.innerHeight - 120;
      const displayScale = Math.min(containerW / w, containerH / h, 1);
      scaleRef.current = displayScale;

      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = w;
      canvas.height = h;
      canvas.style.width = Math.round(w * displayScale) + 'px';
      canvas.style.height = Math.round(h * displayScale) + 'px';

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
  }, [imageFile]);

  const getLineWidth = useCallback(() => {
    const scale = scaleRef.current;
    return scale > 0 ? VISUAL_LINE_WIDTH / scale : VISUAL_LINE_WIDTH;
  }, []);

  // BATCH F.1 (2026-05-12) — compute text-pill bbox in canvas coords.
  // Used by both redraw (rendering) and hit testing (tap on existing
  // text). Mutates ctx font but always restores via save/restore.
  // Reads `stroke.size` with default 'M' for backward compat with v1
  // strokes that pre-date the size picker.
  const getTextBBox = useCallback((ctx, stroke) => {
    const scale = scaleRef.current || 1;
    const sizeKey = stroke.size || TEXT_DEFAULT_SIZE;
    const fontSize = TEXT_SIZE_PX[sizeKey] / scale;
    const padX = TEXT_PADDING_X / scale;
    const padY = TEXT_PADDING_Y / scale;

    ctx.save();
    ctx.font = `bold ${fontSize}px ${FONT_STACK}`;
    const textWidth = ctx.measureText(stroke.text || '').width;
    ctx.restore();

    const width = textWidth + padX * 2;
    const height = fontSize + padY * 2;
    return {
      x: stroke.x - width / 2,
      y: stroke.y - height / 2,
      width,
      height,
      fontSize,
      padX,
      padY,
    };
  }, []);

  // BATCH F.1 (2026-05-12) — hit test: returns stroke index of the
  // top-most text label containing the point, or -1 if none. Iterates
  // strokesRef in REVERSE so labels drawn on top win over earlier ones.
  const hitTestText = useCallback((pos) => {
    const canvas = canvasRef.current;
    if (!canvas) return -1;
    const ctx = canvas.getContext('2d');
    const all = strokesRef.current;
    for (let i = all.length - 1; i >= 0; i--) {
      const s = all[i];
      if (s.type !== 'text') continue;
      const bbox = getTextBBox(ctx, s);
      if (
        pos.x >= bbox.x && pos.x <= bbox.x + bbox.width &&
        pos.y >= bbox.y && pos.y <= bbox.y + bbox.height
      ) {
        return i;
      }
    }
    return -1;
  }, [getTextBBox]);

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
        // BATCH F.1 (2026-05-12) — bbox sourced from getTextBBox helper
        // (DRY shared with hitTestText). Reads stroke.size, default 'M'.
        const bbox = getTextBBox(ctx, stroke);
        const scale = scaleRef.current || 1;
        const radius = TEXT_PILL_RADIUS / scale;

        ctx.save();
        ctx.font = `bold ${bbox.fontSize}px ${FONT_STACK}`;
        ctx.direction = 'rtl';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'center';

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        if (typeof ctx.roundRect === 'function') {
          ctx.roundRect(bbox.x, bbox.y, bbox.width, bbox.height, radius);
        } else {
          ctx.rect(bbox.x, bbox.y, bbox.width, bbox.height);
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
  }, [getLineWidth, getTextBBox]);

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
        // BATCH F.1 (2026-05-12) — first check if tap landed on an
        // existing text label. If yes → enter "possible drag/edit"
        // state. If no → continue F's create-new flow.
        const hitIndex = hitTestText(pos);
        if (hitIndex >= 0) {
          dragRef.current = {
            index: hitIndex,
            startPos: { x: pos.x, y: pos.y },
            hasMoved: false,
          };
          return;
        }
        setPendingText(prev =>
          prev
            ? { ...prev, x: pos.x, y: pos.y }
            : { x: pos.x, y: pos.y, value: '', size: TEXT_DEFAULT_SIZE }
        );
        return;
      }
      const newStroke = { type: 'stroke', color: colorRef.current, points: [pos] };
      currentStrokeRef.current = newStroke;
      drawingRef.current = true;
    };

    const moveStroke = (pos) => {
      // BATCH F.1 (2026-05-12) — if dragging an existing text, update
      // its x/y in place (perf — avoids array re-creation at 60Hz).
      if (dragRef.current) {
        const drag = dragRef.current;
        const dx = pos.x - drag.startPos.x;
        const dy = pos.y - drag.startPos.y;
        if (!drag.hasMoved && Math.hypot(dx, dy) > DRAG_THRESHOLD_PX) {
          drag.hasMoved = true;
        }
        if (drag.hasMoved) {
          const all = strokesRef.current;
          const target = all[drag.index];
          if (target && target.type === 'text') {
            target.x = pos.x;
            target.y = pos.y;
            redraw([...all]);
          }
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
      // BATCH F.1 (2026-05-12) — drag/tap-edit handling for text mode.
      if (dragRef.current) {
        const drag = dragRef.current;
        const targetIndex = drag.index;
        const wasDrag = drag.hasMoved;
        dragRef.current = null;

        if (wasDrag) {
          // Position already mutated in moveStroke. Sync React state.
          setStrokes([...strokesRef.current]);
          return;
        }
        // Quick tap (no movement) → open edit overlay for that stroke.
        const target = strokesRef.current[targetIndex];
        if (target && target.type === 'text') {
          setPendingText({
            x: target.x,
            y: target.y,
            value: target.text || '',
            size: target.size || TEXT_DEFAULT_SIZE,
            editIndex: targetIndex,
          });
          // BATCH F.1 — sync color picker to target's color so user
          // sees which color is "current" while editing. SAVE the
          // user's previously-selected color first so it can be
          // restored on commit/cancel/delete (prevents silent global
          // state mutation).
          if (target.color) {
            savedColorRef.current = colorRef.current;
            setColor(target.color);
          }
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

  // BATCH F.1 (2026-05-12) — restore saved color after edit overlay
  // closes. Called from commit, cancel, AND delete paths so the
  // global picker returns to whatever the user had selected before
  // tapping a label.
  const restoreSavedColor = useCallback(() => {
    if (savedColorRef.current !== null) {
      setColor(savedColorRef.current);
      savedColorRef.current = null;
    }
  }, []);

  // BATCH F (2026-05-12) — commit pending text label.
  // DESIGN DECISION: color is captured at COMMIT time (not at tap
  // time). User can change color while typing — the "אישור" press
  // is their final intent. Avoids surprising "I selected red after
  // I tapped!" behavior.
  // BATCH F.1 — also handles edit-in-place (when curr.editIndex set)
  // and restores the user's pre-edit global color.
  const commitPendingText = useCallback(() => {
    setPendingText(curr => {
      if (!curr || !curr.value.trim()) {
        restoreSavedColor();  // cancel-like exit if value is empty
        return null;
      }
      const textStroke = {
        type: 'text',
        color: colorRef.current,
        size: curr.size || TEXT_DEFAULT_SIZE,
        x: curr.x,
        y: curr.y,
        text: curr.value.trim(),
      };
      // BATCH F.1 — edit-in-place vs append-new.
      if (Number.isInteger(curr.editIndex)) {
        const all = strokesRef.current.slice();
        all[curr.editIndex] = textStroke;
        strokesRef.current = all;
        setStrokes(all);
      } else {
        strokesRef.current = [...strokesRef.current, textStroke];
        setStrokes(prev => [...prev, textStroke]);
      }
      redraw([...strokesRef.current]);
      restoreSavedColor();  // BATCH F.1 — restore user's pre-edit color
      return null;
    });
  }, [redraw, restoreSavedColor]);

  // BATCH F.1 (2026-05-12) — cancel the overlay (ביטול button OR
  // Escape key). Closes overlay, restores saved color, no stroke change.
  const cancelPendingText = useCallback(() => {
    setPendingText(null);
    restoreSavedColor();
  }, [restoreSavedColor]);

  // BATCH F.1 (2026-05-12) — delete the currently-edited text stroke.
  // Caller (delete button) wraps with window.confirm to prevent
  // accidental clicks. Per Zahi's UX call 2026-05-12: confirmation
  // is sufficient for v1.5; richer undo-aware delete deferred.
  const deletePendingText = useCallback(() => {
    setPendingText(curr => {
      if (!curr || !Number.isInteger(curr.editIndex)) return null;
      const all = strokesRef.current.filter((_, i) => i !== curr.editIndex);
      strokesRef.current = all;
      setStrokes(all);
      redraw([...all]);
      restoreSavedColor();  // BATCH F.1 — restore user's pre-edit color
      return null;
    });
  }, [redraw, restoreSavedColor]);

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
      </div>

      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center overflow-hidden"
        style={{ touchAction: 'none', WebkitUserSelect: 'none', userSelect: 'none', WebkitTouchCallout: 'none' }}
      >
        <canvas
          ref={canvasRef}
          style={{ touchAction: 'none', display: 'block' }}
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
                cancelPendingText();
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

          {/* BATCH F.1 (2026-05-12) — size picker. 3 buttons. Active highlighted. */}
          <div className="flex items-center gap-1">
            {['S', 'M', 'L'].map(sz => {
              const isActive = (pendingText.size || TEXT_DEFAULT_SIZE) === sz;
              return (
                <button
                  key={sz}
                  onClick={(e) => {
                    e.stopPropagation();
                    setPendingText(p => p ? { ...p, size: sz } : p);
                  }}
                  aria-label={`גודל ${TEXT_SIZE_LABELS[sz]}`}
                  className={`w-9 h-9 rounded-lg text-sm font-bold transition-colors ${
                    isActive
                      ? 'bg-amber-500 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {TEXT_SIZE_LABELS[sz]}
                </button>
              );
            })}
          </div>

          <button
            onClick={(e) => { e.stopPropagation(); commitPendingText(); }}
            disabled={!pendingText.value.trim()}
            className="px-4 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium disabled:opacity-40"
          >
            אישור
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); cancelPendingText(); }}
            className="px-3 py-2 rounded-lg bg-slate-700 text-slate-300 text-sm"
          >
            ביטול
          </button>

          {/* BATCH F.1 (2026-05-12) — delete button, ONLY in edit mode.
              window.confirm guards against accidental click (label has
              user's full context: text + size + color + position — too
              costly to lose to a mistap). */}
          {Number.isInteger(pendingText.editIndex) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm('למחוק את התווית?')) {
                  deletePendingText();
                }
              }}
              aria-label="מחק תווית"
              className="px-3 py-2 rounded-lg bg-red-700 text-white text-sm hover:bg-red-800"
            >
              מחק
            </button>
          )}
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
