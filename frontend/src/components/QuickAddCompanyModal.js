import React, { useState, useEffect } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { projectCompanyService } from '../services/api';
import ContactPickerButton from './ContactPickerButton';

export default function QuickAddCompanyModal({
  open,
  onOpenChange,
  projectId,
  categories = [],
  initialTrade = '',
  onSuccess,
}) {
  const [name, setName] = useState('');
  const [tradeValue, setTradeValue] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setName('');
      setTradeValue(initialTrade || '');
      setContactName('');
      setContactPhone('');
      setSaving(false);
    }
  }, [open, initialTrade]);

  const trimmedName = name.trim();
  const canSave = trimmedName.length > 0 && !!tradeValue && !saving;

  const handleSave = async () => {
    if (!canSave) return;
    if (!projectId) {
      toast.error('פרויקט לא זוהה');
      return;
    }
    if (!tradeValue) {
      toast.error('יש לבחור תחום');
      return;
    }
    setSaving(true);
    try {
      const payload = { name: trimmedName, trade: tradeValue };
      if (contactName.trim()) payload.contact_name = contactName.trim();
      if (contactPhone.trim()) payload.contact_phone = contactPhone.trim();
      const newCompany = await projectCompanyService.create(projectId, payload);
      toast.success('החברה נוספה');
      if (onSuccess) onSuccess(newCompany);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בהוספת חברה');
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (saving) return;
        onOpenChange(next);
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 bg-black/40 z-[9999]" />
        <DialogPrimitive.Content
          className="fixed inset-x-0 bottom-0 sm:bottom-auto sm:left-[50%] sm:top-[50%] sm:-translate-x-1/2 sm:-translate-y-1/2 z-[9999] bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-md sm:mx-auto max-h-[90vh] flex flex-col outline-none"
          dir="rtl"
          onEscapeKeyDown={(e) => { if (saving) e.preventDefault(); }}
          onPointerDownOutside={(e) => { if (saving) e.preventDefault(); }}
          onInteractOutside={(e) => { if (saving) e.preventDefault(); }}
        >
          <DialogPrimitive.Title className="sr-only">הוספת חברה מהירה</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">טופס מקוצר להוספת חברה חדשה לפרויקט</DialogPrimitive.Description>

          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between flex-shrink-0">
            <h3 className="font-bold text-slate-800 text-sm">הוסף חברה</h3>
            <button
              type="button"
              onClick={() => { if (!saving) onOpenChange(false); }}
              disabled={saving}
              className="p-1 hover:bg-slate-100 rounded-lg disabled:opacity-50"
              aria-label="סגור"
            >
              <X className="w-5 h-5 text-slate-400" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5">
                שם חברה <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={saving}
                placeholder="הזן שם חברה"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-200 focus:border-amber-300 disabled:opacity-50"
                dir="rtl"
                autoFocus
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5">
                תחום <span className="text-red-500">*</span>
              </label>
              <select
                value={tradeValue}
                onChange={(e) => setTradeValue(e.target.value)}
                disabled={saving}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-200 focus:border-amber-300 disabled:opacity-50"
                dir="rtl"
              >
                <option value="">בחר תחום</option>
                {categories.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5">שם איש קשר</label>
              <input
                type="text"
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                disabled={saving}
                placeholder="(אופציונלי)"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-200 focus:border-amber-300 disabled:opacity-50"
                dir="rtl"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5">טלפון</label>
              <input
                type="tel"
                inputMode="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                disabled={saving}
                placeholder="(אופציונלי)"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-200 focus:border-amber-300 disabled:opacity-50"
                dir="ltr"
              />
              <ContactPickerButton onPhonePicked={setContactPhone} disabled={saving} className="mt-1" />
            </div>
          </div>

          <div className="px-4 py-3 border-t border-slate-100 flex gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={() => { if (!saving) onOpenChange(false); }}
              disabled={saving}
              className="flex-1 py-2.5 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 active:bg-slate-100 min-h-[44px] disabled:opacity-50"
            >
              בטל
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={!canSave}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-bold transition-all min-h-[44px] ${
                canSave
                  ? 'bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              }`}
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {saving ? 'שומר...' : 'שמור'}
            </button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
