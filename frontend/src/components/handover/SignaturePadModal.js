import React, { useState, useRef, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import {
  Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerDescription,
} from '../ui/drawer';
import { Loader2, X, Eraser } from 'lucide-react';

const ROLE_LABELS = {
  manager: t('handover', 'signatureManager'),
  tenant: t('handover', 'signatureTenant'),
  tenant_2: 'רוכש/ת נוסף/ת',
  contractor_rep: t('handover', 'signatureContractorRep'),
};

const SignaturePadModal = ({
  open, onClose, role, projectId, protocolId, currentUserName, tenantData, onSigned, signFn,
}) => {
  const [tab, setTab] = useState('canvas');
  const [typedName, setTypedName] = useState('');
  const [signerName, setSignerName] = useState(currentUserName || '');
  const [idNumber, setIdNumber] = useState('');
  const [saving, setSaving] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const canvasRef = useRef(null);
  const ctxRef = useRef(null);
  const isDrawingRef = useRef(false);
  const hasDrawnRef = useRef(false);

  useEffect(() => {
    if (open) {
      setTab('canvas');
      setTypedName('');
      const isTenantRole = role === 'tenant' || role === 'tenant_2';
      setSignerName(isTenantRole ? (tenantData?.name || '') : (currentUserName || ''));
      setIdNumber(isTenantRole ? (tenantData?.id_number || '') : '');
      setSaving(false);
      setShowConfirm(false);
      hasDrawnRef.current = false;
    }
  }, [open, role, currentUserName, tenantData]);

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

  const handleSubmitAttempt = () => {
    if (tab === 'canvas' && !hasDrawnRef.current) {
      toast.error(t('handover', 'drawBeforeConfirm'));
      return;
    }
    if (tab === 'typed' && !typedName.trim()) {
      toast.error(t('handover', 'typeNameRequired'));
      return;
    }
    if (!signerName.trim()) {
      toast.error(t('handover', 'typeNameRequired'));
      return;
    }
    setShowConfirm(true);
  };

  const handleConfirmSign = async () => {
    setShowConfirm(false);
    try {
      setSaving(true);
      const formData = new FormData();
      formData.append('signer_name', signerName.trim());
      formData.append('signature_type', tab);
      if (idNumber.trim()) {
        formData.append('id_number', idNumber.trim());
      }

      if (tab === 'canvas') {
        const canvas = canvasRef.current;
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        formData.append('signature_image', blob, `${role}.png`);
      } else {
        formData.append('typed_name', typedName.trim());
      }

      if (signFn) {
        await signFn(formData);
      } else {
        await handoverService.signRole(projectId, protocolId, role, formData);
      }
      toast.success(t('handover', 'signatureSaved'));
      onSigned?.();
      onClose();
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.error(t('handover', 'signatureExists'));
        onSigned?.();
        onClose();
      } else if (err?.response?.status === 403) {
        toast.error(t('handover', 'protocolLocked'));
        onSigned?.();
        onClose();
      } else {
        toast.error(t('handover', 'updateError'));
        console.error(err);
      }
    } finally {
      setSaving(false);
    }
  };

  if (!role) return null;

  return (
    <Drawer open={open} onOpenChange={(o) => { if (!o && !saving) onClose(); }}>
      <DrawerContent className="max-h-[90vh]" dir="rtl">
        <DrawerHeader className="text-right">
          <div className="flex items-center justify-between">
            <DrawerTitle className="text-base font-bold text-slate-800">
              {t('handover', 'signatureTitle').replace('{role}', ROLE_LABELS[role] || role)}
            </DrawerTitle>
            <button onClick={onClose} disabled={saving} className="p-1.5 hover:bg-slate-100 rounded-lg">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>
          <DrawerDescription className="sr-only">
            {t('handover', 'signatureTitle').replace('{role}', ROLE_LABELS[role] || role)}
          </DrawerDescription>
        </DrawerHeader>

        <div className="px-4 pb-6 space-y-4 overflow-y-auto">
          <div className="flex bg-slate-100 rounded-lg p-0.5">
            <button
              onClick={() => setTab('canvas')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all
                ${tab === 'canvas' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
            >
              {t('handover', 'tabCanvas')}
            </button>
            <button
              onClick={() => setTab('typed')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all
                ${tab === 'typed' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
            >
              {t('handover', 'tabTyped')}
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
                {t('handover', 'clearCanvas')}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <input
                type="text"
                value={typedName}
                onChange={(e) => setTypedName(e.target.value)}
                placeholder={t('handover', 'signerName')}
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
            <label className="text-sm font-medium text-slate-700">{t('handover', 'signerName')}</label>
            <input
              type="text"
              value={signerName}
              onChange={(e) => setSignerName(e.target.value)}
              placeholder={t('handover', 'signerName')}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
                focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-400"
              dir="rtl"
            />
          </div>

          {(role === 'tenant' || role === 'tenant_2') && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700">ת.ז.</label>
              <input
                type="text"
                value={idNumber}
                onChange={(e) => setIdNumber(e.target.value)}
                placeholder="מספר תעודת זהות"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
                  focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-400"
                dir="ltr"
                inputMode="numeric"
              />
            </div>
          )}

          {showConfirm ? (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 space-y-2">
              <p className="text-sm text-amber-800 font-medium text-center">
                {t('handover', 'confirmSignatureText')}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleConfirmSign}
                  disabled={saving}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-amber-500 text-white rounded-lg
                    text-sm font-bold hover:bg-amber-600 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {t('handover', 'confirmSignature')}
                </button>
                <button
                  onClick={() => setShowConfirm(false)}
                  disabled={saving}
                  className="px-4 py-2.5 bg-slate-100 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-200"
                >
                  ביטול
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={handleSubmitAttempt}
              disabled={saving}
              className="w-full py-3 bg-amber-500 text-white rounded-xl text-sm font-bold
                hover:bg-amber-600 active:scale-[0.98] disabled:opacity-50"
            >
              {t('handover', 'confirmSignature')}
            </button>
          )}

          <p className="text-[10px] text-slate-400 text-center leading-relaxed">
            {t('handover', 'legalDisclaimer')}
          </p>
        </div>
      </DrawerContent>
    </Drawer>
  );
};

export default SignaturePadModal;
