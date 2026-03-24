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

  useEffect(() => { colorRef.current = color; }, [color]);
  useEffect(() => { onSaveRef.current = onSave; }, [onSave]);
  useEffect(() => { strokesRef.current = strokes; }, [strokes]);

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
      if (stroke.points.length < 2) continue;
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

  const startStroke = useCallback((pos) => {
    const newStroke = { color: colorRef.current, points: [pos] };
    currentStrokeRef.current = newStroke;
    drawingRef.current = true;
  }, []);

  const moveStroke = useCallback((pos) => {
    if (!drawingRef.current || !currentStrokeRef.current) return;
    currentStrokeRef.current = {
      ...currentStrokeRef.current,
      points: [...currentStrokeRef.current.points, pos],
    };
    setStrokes(allStrokes => {
      redraw([...allStrokes, currentStrokeRef.current]);
      return allStrokes;
    });
  }, [redraw]);

  const endStroke = useCallback(() => {
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
  }, [redraw]);

  const handleUndo = useCallback(() => {
    setStrokes(prev => {
      const next = prev.slice(0, -1);
      redraw(next);
      return next;
    });
  }, [redraw]);

  const handleSave = useCallback(() => {
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
  }, [saving]);

  const content = (
    <div className="fixed inset-0 bg-black flex flex-col h-dvh-fallback" dir="rtl"
         style={{ zIndex: 10001, pointerEvents: 'auto' }}>
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
              onClick={() => setColor(c.value)}
              className={`w-8 h-8 rounded-full border-2 transition-transform ${
                color === c.value ? 'border-white scale-110' : 'border-slate-600'
              }`}
              style={{ backgroundColor: c.value }}
              title={c.label}
            />
          ))}
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
          onPointerDown={(e) => {
            e.preventDefault();
            e.currentTarget.setPointerCapture(e.pointerId);
            const pos = getPos(e.clientX, e.clientY);
            if (pos) startStroke(pos);
          }}
          onPointerMove={(e) => {
            e.preventDefault();
            const pos = getPos(e.clientX, e.clientY);
            if (pos) moveStroke(pos);
          }}
          onPointerUp={(e) => {
            e.preventDefault();
            endStroke();
          }}
          onPointerCancel={(e) => {
            e.preventDefault();
            endStroke();
          }}
        />
      </div>

      <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-t border-slate-700 shrink-0"
           style={{ position: 'relative', zIndex: 20 }}>
        <button
          onClick={handleSave}
          disabled={!loaded || saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-amber-500 text-white rounded-xl font-medium text-sm hover:bg-amber-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'שומר...' : 'שמור'}
        </button>
        <button
          onClick={handleUndo}
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
