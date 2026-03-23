import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Undo2, Save } from 'lucide-react';

const MAX_CANVAS_SIZE = 1280;
const LINE_WIDTH = 3;
const COLORS = [
  { value: '#ef4444', label: 'אדום' },
  { value: '#3b82f6', label: 'כחול' },
  { value: '#000000', label: 'שחור' },
];

const PhotoAnnotation = ({ imageFile, onSave, onSkip }) => {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const containerRef = useRef(null);
  const [color, setColor] = useState('#ef4444');
  const colorRef = useRef('#ef4444');
  const onSkipRef = useRef(onSkip);
  const [strokes, setStrokes] = useState([]);
  const [currentStroke, setCurrentStroke] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const scaleRef = useRef(1);

  useEffect(() => { colorRef.current = color; }, [color]);
  useEffect(() => { onSkipRef.current = onSkip; }, [onSkip]);

  useEffect(() => {
    let cancelled = false;

    const loadImage = async () => {
      let bitmap;
      try {
        bitmap = await createImageBitmap(imageFile);
      } catch (_) {
        const url = URL.createObjectURL(imageFile);
        const img = new Image();
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          img.src = url;
        });
        bitmap = img;
        URL.revokeObjectURL(url);
      }

      if (cancelled) return;

      let w = bitmap.width;
      let h = bitmap.height;
      if (w > MAX_CANVAS_SIZE || h > MAX_CANVAS_SIZE) {
        const ratio = Math.min(MAX_CANVAS_SIZE / w, MAX_CANVAS_SIZE / h);
        w = Math.round(w * ratio);
        h = Math.round(h * ratio);
      }

      imgRef.current = bitmap;

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
      ctx.drawImage(bitmap, 0, 0, w, h);
      setLoaded(true);
    };

    loadImage().catch(() => {
      if (!cancelled) onSkipRef.current();
    });

    return () => { cancelled = true; };
  }, [imageFile]);

  const redraw = useCallback((allStrokes) => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    for (const stroke of allStrokes) {
      if (stroke.points.length < 2) continue;
      ctx.beginPath();
      ctx.strokeStyle = stroke.color;
      ctx.lineWidth = LINE_WIDTH;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      ctx.stroke();
    }
  }, []);

  const getTouchPos = useCallback((touch) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scale = scaleRef.current;
    return {
      x: (touch.clientX - rect.left) / scale,
      y: (touch.clientY - rect.top) / scale,
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !loaded) return;

    const handleTouchStart = (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      if (!touch) return;
      const pos = getTouchPos(touch);
      if (!pos) return;
      const newStroke = { color: colorRef.current, points: [pos] };
      setCurrentStroke(newStroke);
    };

    const handleTouchMove = (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      if (!touch) return;
      const pos = getTouchPos(touch);
      if (!pos) return;

      setCurrentStroke(prev => {
        if (!prev) return null;
        const updated = { ...prev, points: [...prev.points, pos] };
        setStrokes(allStrokes => {
          redraw([...allStrokes, updated]);
          return allStrokes;
        });
        return updated;
      });
    };

    const handleTouchEnd = (e) => {
      e.preventDefault();
      setCurrentStroke(prev => {
        if (!prev || prev.points.length < 2) return null;
        setStrokes(allStrokes => {
          const newAll = [...allStrokes, prev];
          redraw(newAll);
          return newAll;
        });
        return null;
      });
    };

    const handleMouseDown = (e) => {
      const rect = canvas.getBoundingClientRect();
      const scale = scaleRef.current;
      const pos = { x: (e.clientX - rect.left) / scale, y: (e.clientY - rect.top) / scale };
      const newStroke = { color: colorRef.current, points: [pos] };
      setCurrentStroke(newStroke);
    };

    const handleMouseMove = (e) => {
      if (!(e.buttons & 1)) return;
      const rect = canvas.getBoundingClientRect();
      const scale = scaleRef.current;
      const pos = { x: (e.clientX - rect.left) / scale, y: (e.clientY - rect.top) / scale };

      setCurrentStroke(prev => {
        if (!prev) return null;
        const updated = { ...prev, points: [...prev.points, pos] };
        setStrokes(allStrokes => {
          redraw([...allStrokes, updated]);
          return allStrokes;
        });
        return updated;
      });
    };

    const handleMouseUp = () => {
      setCurrentStroke(prev => {
        if (!prev || prev.points.length < 2) return null;
        setStrokes(allStrokes => {
          const newAll = [...allStrokes, prev];
          redraw(newAll);
          return newAll;
        });
        return null;
      });
    };

    canvas.addEventListener('touchstart', handleTouchStart, { passive: false });
    canvas.addEventListener('touchmove', handleTouchMove, { passive: false });
    canvas.addEventListener('touchend', handleTouchEnd, { passive: false });
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);

    return () => {
      canvas.removeEventListener('touchstart', handleTouchStart);
      canvas.removeEventListener('touchmove', handleTouchMove);
      canvas.removeEventListener('touchend', handleTouchEnd);
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseup', handleMouseUp);
    };
  }, [loaded, getTouchPos, redraw]);

  const handleUndo = useCallback(() => {
    setStrokes(prev => {
      const next = prev.slice(0, -1);
      redraw(next);
      return next;
    });
  }, [redraw]);

  const handleSave = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], 'annotated.jpg', { type: 'image/jpeg' });
        onSave(file);
      },
      'image/jpeg',
      0.85
    );
  }, [onSave]);

  return (
    <div className="fixed inset-0 z-[10000] bg-black flex flex-col" dir="rtl">
      {!loaded && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black"
             style={{ pointerEvents: 'none' }}>
          <div className="text-white text-sm">טוען תמונה...</div>
        </div>
      )}

      <div className="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-700 shrink-0">
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

        <button
          onClick={onSkip}
          className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
        >
          <X className="w-4 h-4" />
          דלג
        </button>
      </div>

      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center overflow-hidden"
        style={{ touchAction: 'none', WebkitUserSelect: 'none', userSelect: 'none' }}
      >
        <canvas
          ref={canvasRef}
          style={{ touchAction: 'none' }}
        />
      </div>

      <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-t border-slate-700 shrink-0">
        <button
          onClick={handleSave}
          disabled={!loaded}
          className="flex items-center gap-2 px-6 py-2.5 bg-amber-500 text-white rounded-xl font-medium text-sm hover:bg-amber-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Save className="w-4 h-4" />
          שמור
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
};

export default PhotoAnnotation;
