import React, { useState, useRef, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../ui/dialog';
import { Loader2, Eraser } from 'lucide-react';

/**
 * Safety tour signature pad (batch 4c). Modeled on the handover SignaturePadModal
 * canvas mechanics, but Radix Dialog (not Vaul Drawer), NO id_number field, and
 * it does NOT call the API itself — it collects input and hands the result to the
 * parent via onSave({ signerName, signatureType, typedName, blob }). The parent
 * owns the request + the `saving` flag.
 *
 * Props: { open, onClose, slotLabel, defaultName, saving, onSave }
 */
const SafetySignaturePad = ({ open, onClose, slotLabel, defaultName, saving, onSave }) => {
  const [tab, setTab] = useState('canvas');
  const [typedName, setTypedName] = useState('');
  const [signerName, setSignerName] = useState(defaultName || '');

  const canvasRef = useRef(null);
  const ctxRef = useRef(null);
  const isDrawingRef = useRef(false);
  const hasDrawnRef = useRef(false);

  useEffect(() => {
    if (open) {
      setTab('canvas');
      setTypedName('');
      setSignerName(defaultName || '');
      hasDrawnRef.current = false;
    }
  }, [open, defaultName]);

  const initCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctxRef.current = ctx;
    hasDrawnRef.current = false;
  }, []);

  useEffect(() => {
    if (open && tab === 'canvas') {
      const timer = setTimeout(initCanvas, 100);
      return () => clearTimeout(timer);
    }
  }, [open, tab, initCanvas]);

  const getPos = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    if (e.touches && e.touches.length > 0) {
      return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
    }
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const startDraw = (e) => {
    e.preventDefault();
    isDrawingRef.current = true;
    const ctx = ctxRef.current;
    if (!ctx) return;
    const pos = getPos(e);
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
  };

  const draw = (e) => {
    e.preventDefault();
    if (!isDrawingRef.current) return;
    const ctx = ctxRef.current;
    if (!ctx) return;
    hasDrawnRef.current = true;
    const pos = getPos(e);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
  };

  const endDraw = (e) => {
    e.preventDefault();
    isDrawingRef.current = false;
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    const ctx = ctxRef.current;
    if (canvas && ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      hasDrawnRef.current = false;
    }
  };

  const handleSubmit = async () => {
    if (!signerName.trim()) {
      toast.error('יש להזין שם החותם');
      return;
    }
    if (tab === 'canvas' && !hasDrawnRef.current) {
      toast.error('יש לצייר חתימה לפני אישור');
      return;
    }
    if (tab === 'typed' && !typedName.trim()) {
      toast.error('יש להקליד שם לחתימה');
      return;
    }

    let blob = null;
    if (tab === 'canvas') {
      const canvas = canvasRef.current;
      blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    }
    onSave?.({
      signerName: signerName.trim(),
      signatureType: tab,
      typedName: tab === 'typed' ? typedName.trim() : null,
      blob,
    });
  };

  return (
    <Dialog open={open} modal={false} onOpenChange={(o) => { if (!o && !saving) onClose(); }}>
      <DialogContent className="max-w-md" dir="rtl">
        <DialogHeader className="text-right">
          <DialogTitle className="text-base font-bold text-slate-800">
            חתימה — {slotLabel}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex bg-slate-100 rounded-lg p-0.5">
            <button
              onClick={() => setTab('canvas')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all
                ${tab === 'canvas' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
            >
              ציור
            </button>
            <button
              onClick={() => setTab('typed')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all
                ${tab === 'typed' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
            >
              הקלדה
            </button>
          </div>

          {tab === 'canvas' ? (
            <div className="space-y-2">
              <div className="border-2 border-slate-200 rounded-xl overflow-hidden bg-white">
                <canvas
                  ref={canvasRef}
                  style={{ width: '100%', height: '180px', touchAction: 'none' }}
                  className="cursor-crosshair"
                  onMouseDown={startDraw}
                  onMouseMove={draw}
                  onMouseUp={endDraw}
                  onMouseLeave={endDraw}
                  onTouchStart={startDraw}
                  onTouchMove={draw}
                  onTouchEnd={endDraw}
                />
              </div>
              <button
                onClick={clearCanvas}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 font-medium px-2 py-1"
              >
                <Eraser className="w-3.5 h-3.5" />
                נקה
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <input
                type="text"
                value={typedName}
                onChange={(e) => setTypedName(e.target.value)}
                placeholder="שם לחתימה"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
                  focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-400"
                dir="rtl"
              />
              {typedName.trim() && (
                <div className="border-2 border-slate-200 rounded-xl p-4 bg-white min-h-[80px] flex items-center justify-center">
                  <div className="text-center">
                    <div style={{ fontFamily: "'Caveat', cursive", fontSize: '32px', lineHeight: '1.2' }}
                      className="text-slate-800">
                      {typedName}
                    </div>
                    <div className="border-t border-slate-300 mt-2 pt-1 w-48 mx-auto" />
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">שם החותם</label>
            <input
              type="text"
              value={signerName}
              onChange={(e) => setSignerName(e.target.value)}
              placeholder="שם החותם"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
                focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-400"
              dir="rtl"
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={saving}
            className="w-full flex items-center justify-center gap-1.5 py-3 bg-amber-500 text-white rounded-xl text-sm font-bold
              hover:bg-amber-600 active:scale-[0.98] disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            אישור חתימה
          </button>

          <p className="text-[10px] text-slate-400 text-center leading-relaxed">
            החתימה מהווה אישור לנכונות תוכן הדוח במועד החתימה.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SafetySignaturePad;
