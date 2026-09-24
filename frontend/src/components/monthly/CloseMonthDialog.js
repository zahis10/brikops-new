import React, { useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { monthlyCloseService } from '../../services/monthlyCloseService';

export default function CloseMonthDialog({ open, onOpenChange, projectId, account, onClosed }) {
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const close = async () => {
    setSubmitting(true);
    try {
      await monthlyCloseService.closeMonth(projectId, account.month, { note: note.trim() });
      setNote('');
      onOpenChange(false);
      onClosed();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'לא ניתן לסגור את החודש');
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent dir="rtl" className="max-w-md text-right">
        <DialogHeader className="text-right">
          <DialogTitle>לסגור את {account?.label}?</DialogTitle>
          <DialogDescription className="text-right">
            {account?.kpis?.this_month || 0} שלבי-דירה · {account?.contractors?.length || 0} קבלנים · {account?.kpis?.corrections || 0} תיקונים
          </DialogDescription>
        </DialogHeader>
        <label className="text-sm font-medium text-slate-700" htmlFor="close-note">הערה (לא חובה)</label>
        <textarea id="close-note" value={note} onChange={(e) => setNote(e.target.value)}
          maxLength={500} rows={3} className="w-full rounded-lg border border-slate-200 p-3 text-right"
          placeholder="הערה לסגירת החודש" />
        <p className="text-sm font-medium text-red-600">פעולה בלתי הפיכה — החודש יוקפא ותיקונים יופיעו בחודש הבא.</p>
        <DialogFooter className="gap-2 sm:justify-start">
          <button type="button" onClick={close} disabled={submitting}
            className="min-h-[44px] rounded-lg bg-amber-500 px-5 font-semibold text-white disabled:opacity-50">
            {submitting ? 'סוגר חודש…' : 'סגור חודש'}
          </button>
          <button type="button" onClick={() => onOpenChange(false)} disabled={submitting}
            className="min-h-[44px] rounded-lg border border-slate-200 px-5">ביטול</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}