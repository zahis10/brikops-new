import React, { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Loader2 } from 'lucide-react';

/**
 * Phase 2D-1 (#500) — Modal-in-modal for saving the current filter set
 * as a named view. Triggered by "+ שמור" pill inside MatrixFilterDrawer.
 *
 * ESC closes ONLY this dialog, not the parent drawer (Radix nested
 * Root behavior — onOpenChange isolates the trees).
 */
export default function SavedViewSaveDialog({ open, onClose, onSave }) {
  const [title, setTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open) { setTitle(''); setSaving(false); setError(null); }
  }, [open]);

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    const trimmed = title.trim();
    if (!trimmed) { setError('שם התצוגה חובה'); return; }
    if (trimmed.length > 80) { setError('שם ארוך מדי (עד 80 תווים)'); return; }
    setSaving(true);
    setError(null);
    const res = await onSave(trimmed);
    setSaving(false);
    if (res?.ok) onClose();
    else setError(res?.error || 'שגיאה בשמירה');
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-[60]" />
        <Dialog.Content
          className="fixed z-[60] bg-white shadow-2xl inset-x-4 top-1/3 sm:inset-x-auto sm:left-1/2 sm:top-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 sm:w-full sm:max-w-sm rounded-2xl flex flex-col outline-none"
          dir="rtl"
        >
          <div className="flex items-center justify-between px-4 pt-4 pb-2">
            <Dialog.Title className="text-base font-bold text-slate-900">
              שמירת תצוגה
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="p-1.5 -m-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                aria-label="סגור"
              >
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </Dialog.Close>
          </div>
          <form onSubmit={handleSubmit} className="px-4 pb-4 pt-2">
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              שם התצוגה
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={80}
              autoFocus
              disabled={saving}
              placeholder="לדוגמה: שוק חופשי בא׳"
              className="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-300 focus:border-violet-400 outline-none min-h-[44px]"
              dir="rtl"
            />
            {error && (
              <div className="mt-2 text-xs text-red-600">{error}</div>
            )}
            <div className="mt-4 flex items-center justify-end gap-2">
              <Dialog.Close asChild>
                <button
                  type="button"
                  disabled={saving}
                  className="px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg min-h-[44px]"
                >
                  ביטול
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={saving || !title.trim()}
                className="px-4 py-2.5 text-sm font-bold text-white bg-violet-600 hover:bg-violet-700 active:bg-violet-800 disabled:bg-slate-300 disabled:cursor-not-allowed rounded-lg min-h-[44px] inline-flex items-center gap-2"
              >
                {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                {saving ? 'שומר...' : 'שמור'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
