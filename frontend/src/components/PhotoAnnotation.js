import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Stage, Layer, Image as KonvaImage, Arrow, Circle, Text, Transformer } from 'react-konva';
import { X, ArrowUpRight, CircleIcon, Type, Undo2, Save, Palette } from 'lucide-react';

const MAX_CANVAS_WIDTH = 1280;
const COLORS = [
  { value: '#ef4444', label: 'אדום' },
  { value: '#3b82f6', label: 'כחול' },
  { value: '#000000', label: 'שחור' },
];
const TOOLS = [
  { id: 'arrow', icon: ArrowUpRight, label: 'חץ' },
  { id: 'circle', icon: CircleIcon, label: 'עיגול' },
  { id: 'text', icon: Type, label: 'טקסט' },
];

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

const PhotoAnnotation = ({ imageSrc, onSave, onCancel }) => {
  const stageRef = useRef(null);
  const layerRef = useRef(null);
  const transformerRef = useRef(null);
  const [bgImage, setBgImage] = useState(null);
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 });
  const [tool, setTool] = useState('arrow');
  const [color, setColor] = useState('#ef4444');
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [shapes, setShapes] = useState([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [textInput, setTextInput] = useState({ visible: false, x: 0, y: 0, value: '' });
  const containerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    loadImage(imageSrc).then(img => {
      if (cancelled) return;
      setBgImage(img);
      const containerW = Math.min(window.innerWidth, MAX_CANVAS_WIDTH);
      const containerH = window.innerHeight - 140;
      const scale = Math.min(containerW / img.width, containerH / img.height, 1);
      setStageSize({
        width: Math.round(img.width * scale),
        height: Math.round(img.height * scale),
        scaleX: scale,
        scaleY: scale,
        originalWidth: img.width,
        originalHeight: img.height,
      });
    }).catch(() => {
      if (!cancelled) onCancel();
    });
    return () => { cancelled = true; };
  }, [imageSrc, onCancel]);

  useEffect(() => {
    if (!transformerRef.current) return;
    const stage = stageRef.current;
    if (!stage) return;
    const node = selectedId ? stage.findOne('#' + selectedId) : null;
    if (node) {
      transformerRef.current.nodes([node]);
    } else {
      transformerRef.current.nodes([]);
    }
    transformerRef.current.getLayer()?.batchDraw();
  }, [selectedId, shapes]);

  const getPointerPos = useCallback(() => {
    const stage = stageRef.current;
    if (!stage) return null;
    const pos = stage.getPointerPosition();
    if (!pos) return null;
    return { x: pos.x / (stageSize.scaleX || 1), y: pos.y / (stageSize.scaleY || 1) };
  }, [stageSize]);

  const handleStageMouseDown = useCallback((e) => {
    const clickedOnEmpty = e.target === e.target.getStage() ||
      e.target.getParent()?.attrs?.id === 'bg-layer' ||
      e.target.attrs?.id === 'bg-image';

    if (!clickedOnEmpty) return;

    setSelectedId(null);

    if (tool === 'text') {
      const pos = getPointerPos();
      if (!pos) return;
      setTextInput({ visible: true, x: pos.x, y: pos.y, value: '' });
      return;
    }

    const pos = getPointerPos();
    if (!pos) return;
    setIsDrawing(true);
    setDrawStart(pos);
  }, [tool, getPointerPos]);

  const handleStageMouseUp = useCallback(() => {
    if (!isDrawing || !drawStart) {
      setIsDrawing(false);
      return;
    }
    const pos = getPointerPos();
    if (!pos) { setIsDrawing(false); return; }

    const dx = pos.x - drawStart.x;
    const dy = pos.y - drawStart.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 5) { setIsDrawing(false); setDrawStart(null); return; }

    const id = 'shape-' + Date.now();
    if (tool === 'arrow') {
      setShapes(prev => [...prev, {
        type: 'arrow', id, color,
        points: [drawStart.x, drawStart.y, pos.x, pos.y],
      }]);
    } else if (tool === 'circle') {
      const cx = (drawStart.x + pos.x) / 2;
      const cy = (drawStart.y + pos.y) / 2;
      const rx = Math.abs(dx) / 2;
      const ry = Math.abs(dy) / 2;
      setShapes(prev => [...prev, {
        type: 'circle', id, color,
        x: cx, y: cy, radiusX: rx, radiusY: ry,
      }]);
    }

    setIsDrawing(false);
    setDrawStart(null);
  }, [isDrawing, drawStart, tool, color, getPointerPos]);

  const handleStageMouseMove = useCallback(() => {
    if (!isDrawing) return;
  }, [isDrawing]);

  const handleTextSubmit = useCallback(() => {
    if (!textInput.value.trim()) {
      setTextInput({ visible: false, x: 0, y: 0, value: '' });
      return;
    }
    const id = 'shape-' + Date.now();
    setShapes(prev => [...prev, {
      type: 'text', id, color,
      x: textInput.x, y: textInput.y, text: textInput.value.trim(),
    }]);
    setTextInput({ visible: false, x: 0, y: 0, value: '' });
  }, [textInput, color]);

  const handleUndo = useCallback(() => {
    setShapes(prev => prev.slice(0, -1));
    setSelectedId(null);
  }, []);

  const handleDeleteSelected = useCallback(() => {
    if (!selectedId) return;
    setShapes(prev => prev.filter(s => s.id !== selectedId));
    setSelectedId(null);
  }, [selectedId]);

  const handleSave = useCallback(async () => {
    if (!stageRef.current || !bgImage) return;
    setSelectedId(null);

    await new Promise(r => setTimeout(r, 50));

    const exportStage = stageRef.current;
    const pixelRatio = bgImage.width / stageSize.width;
    const dataURL = exportStage.toDataURL({
      pixelRatio,
      mimeType: 'image/jpeg',
      quality: 0.85,
    });

    const res = await fetch(dataURL);
    const blob = await res.blob();
    const file = new File([blob], 'annotated.jpg', { type: 'image/jpeg' });
    onSave(file);
  }, [bgImage, stageSize, onSave]);

  if (!bgImage || !stageSize.width) {
    return (
      <div className="fixed inset-0 z-[10000] bg-black flex items-center justify-center">
        <div className="text-white text-sm">טוען תמונה...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[10000] bg-black flex flex-col" dir="rtl">
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-700 shrink-0">
        <div className="flex items-center gap-1">
          {TOOLS.map(t => (
            <button
              key={t.id}
              onClick={() => { setTool(t.id); setSelectedId(null); }}
              className={`flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                tool === t.id ? 'bg-amber-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}

          <div className="relative">
            <button
              onClick={() => setShowColorPicker(!showColorPicker)}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
            >
              <div className="w-4 h-4 rounded-full border-2 border-white" style={{ backgroundColor: color }} />
            </button>
            {showColorPicker && (
              <div className="absolute top-full right-0 mt-1 bg-slate-800 rounded-lg p-2 flex gap-1.5 shadow-xl z-10">
                {COLORS.map(c => (
                  <button
                    key={c.value}
                    onClick={() => { setColor(c.value); setShowColorPicker(false); }}
                    className={`w-8 h-8 rounded-full border-2 transition-transform ${
                      color === c.value ? 'border-white scale-110' : 'border-slate-600'
                    }`}
                    style={{ backgroundColor: c.value }}
                    title={c.label}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          {selectedId && (
            <button
              onClick={handleDeleteSelected}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
            >
              <X className="w-4 h-4" />
              מחק
            </button>
          )}
          <button
            onClick={handleUndo}
            disabled={shapes.length === 0}
            className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Undo2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center overflow-hidden touch-none"
        style={{ WebkitUserSelect: 'none', userSelect: 'none' }}
      >
        <Stage
          ref={stageRef}
          width={stageSize.width}
          height={stageSize.height}
          scaleX={stageSize.scaleX}
          scaleY={stageSize.scaleY}
          onMouseDown={handleStageMouseDown}
          onMouseUp={handleStageMouseUp}
          onMouseMove={handleStageMouseMove}
          onTouchStart={handleStageMouseDown}
          onTouchEnd={handleStageMouseUp}
          onTouchMove={handleStageMouseMove}
          style={{ touchAction: 'none' }}
        >
          <Layer id="bg-layer">
            <KonvaImage
              id="bg-image"
              image={bgImage}
              width={bgImage.width}
              height={bgImage.height}
              listening={true}
            />
          </Layer>
          <Layer ref={layerRef}>
            {shapes.map(shape => {
              if (shape.type === 'arrow') {
                return (
                  <Arrow
                    key={shape.id}
                    id={shape.id}
                    points={shape.points}
                    stroke={shape.color}
                    fill={shape.color}
                    strokeWidth={4}
                    pointerLength={14}
                    pointerWidth={12}
                    hitStrokeWidth={20}
                    draggable
                    onClick={() => setSelectedId(shape.id)}
                    onTap={() => setSelectedId(shape.id)}
                  />
                );
              }
              if (shape.type === 'circle') {
                return (
                  <Circle
                    key={shape.id}
                    id={shape.id}
                    x={shape.x}
                    y={shape.y}
                    radiusX={shape.radiusX}
                    radiusY={shape.radiusY}
                    radius={Math.max(shape.radiusX, shape.radiusY)}
                    stroke={shape.color}
                    strokeWidth={3}
                    hitStrokeWidth={20}
                    draggable
                    onClick={() => setSelectedId(shape.id)}
                    onTap={() => setSelectedId(shape.id)}
                  />
                );
              }
              if (shape.type === 'text') {
                return (
                  <Text
                    key={shape.id}
                    id={shape.id}
                    x={shape.x}
                    y={shape.y}
                    text={shape.text}
                    fontSize={24}
                    fill={shape.color}
                    fontFamily="Arial, sans-serif"
                    fontStyle="bold"
                    draggable
                    onClick={() => setSelectedId(shape.id)}
                    onTap={() => setSelectedId(shape.id)}
                    padding={4}
                  />
                );
              }
              return null;
            })}
            <Transformer
              ref={transformerRef}
              rotateEnabled={false}
              borderStrokeWidth={2}
              anchorSize={12}
              anchorCornerRadius={6}
              anchorStrokeWidth={2}
              boundBoxFunc={(oldBox, newBox) => {
                if (newBox.width < 10 || newBox.height < 10) return oldBox;
                return newBox;
              }}
            />
          </Layer>
        </Stage>

        {textInput.visible && (
          <div
            className="absolute z-10"
            style={{
              left: textInput.x * (stageSize.scaleX || 1) + (containerRef.current?.getBoundingClientRect().left || 0) + ((window.innerWidth - stageSize.width) / 2),
              top: textInput.y * (stageSize.scaleY || 1) + (containerRef.current?.getBoundingClientRect().top || 0),
            }}
          >
            <div className="flex items-center gap-1 bg-white rounded-lg shadow-xl p-1">
              <input
                autoFocus
                dir="rtl"
                value={textInput.value}
                onChange={e => setTextInput(prev => ({ ...prev, value: e.target.value }))}
                onKeyDown={e => { if (e.key === 'Enter') handleTextSubmit(); if (e.key === 'Escape') setTextInput({ visible: false, x: 0, y: 0, value: '' }); }}
                className="px-2 py-1.5 text-sm border border-slate-300 rounded-md w-40 focus:outline-none focus:ring-2 focus:ring-amber-500"
                placeholder="הקלד טקסט..."
              />
              <button
                onClick={handleTextSubmit}
                className="px-2 py-1.5 bg-amber-500 text-white rounded-md text-xs font-medium hover:bg-amber-600"
              >
                ✓
              </button>
              <button
                onClick={() => setTextInput({ visible: false, x: 0, y: 0, value: '' })}
                className="px-2 py-1.5 bg-slate-200 text-slate-600 rounded-md text-xs font-medium hover:bg-slate-300"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-t border-slate-700 shrink-0">
        <button
          onClick={handleSave}
          disabled={shapes.length === 0}
          className="flex items-center gap-2 px-6 py-2.5 bg-amber-500 text-white rounded-xl font-medium text-sm hover:bg-amber-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Save className="w-4 h-4" />
          שמור
        </button>
        <button
          onClick={onCancel}
          className="flex items-center gap-2 px-5 py-2.5 bg-slate-700 text-slate-300 rounded-xl text-sm hover:bg-slate-600 transition-colors"
        >
          ביטול
        </button>
      </div>
    </div>
  );
};

export default PhotoAnnotation;
