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
const TEXT_FONT_SIZE = 18;
const TEXT_PADDING_X = 10;
const TEXT_PADDING_Y = 6;
const TEXT_PILL_RADIUS = 8;
// BATCH F.1a (2026-05-12) — text size multipliers. Applied to
// TEXT_FONT_SIZE in the redraw text branch. Pill padding scales
// with the same multiplier (already proportional to font size via
// padX/padY math + metrics.width).
const SIZE_MULTIPLIERS = { small: 0.7, medium: 1.0, large: 1.4 };

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
  // pendingText: null | { x, y, value } where (x,y) are CANVAS coords.
  const [tool, setTool] = useState('draw');
  const toolRef = useRef('draw');
  const [pendingText, setPendingText] = useState(null);
  // BATCH F.1a (2026-05-12) — text size state. Default 'medium'
  // preserves F behavior. Captured at COMMIT time (same as color)
  // so changing size while typing is reflected in the final render.
  const [textSize, setTextSize] = useState('medium');
  const textSizeRef = useRef('medium');

  useEffect(() => { colorRef.current = color; }, [color]);
  useEffect(() => { onSaveRef.current = onSave; }, [onSave]);
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
  }, [loaded, getPos, redraw]);

  const handleUndo = useCallback(() => {
    setStrokes(prev => {
      const next = prev.slice(0, -1);
      redraw(next);
      return next;
    });
  }, [redraw]);

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
      strokesRef.current = [...strokesRef.current, textStroke];
      setStrokes(prev => [...prev, textStroke]);
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
              setPendingText(null);
              // BATCH F.1a — reset size to default after cancel.
              setTextSize('medium');
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
