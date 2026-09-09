import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { escalationService } from '../../services/api';
import { buildSpareContext, contextLine, defaultText } from '../../utils/escalationDraft';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';

export default function EscalationSheet({ open, onClose, projectId, unit, buildingName, spareStatus, mode = 'new', onSent }) {
  const context = useMemo(() => buildSpareContext(spareStatus), [spareStatus]);
  const [urgency, setUrgency] = useState(context.short.length ? 'urgent' : 'normal');
  const [text, setText] = useState('');
  const [edited, setEdited] = useState(false);
  const [sending, setSending] = useState(false);
  useEffect(() => {
    if (open) { const initialUrgency = context.short.length ? 'urgent' : 'normal'; setUrgency(initialUrgency); setText(mode === 'note' ? '' : defaultText(initialUrgency, unit?.label || '', context)); setEdited(false); }
  }, [open, mode, unit?.label, context]);
  const chooseUrgency = (next) => { setUrgency(next); if (!edited) setText(defaultText(next, unit?.label || '', context)); };
  const submit = async (event) => {
    event.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    try {
      const result = await escalationService.create(projectId, { unit_id: unit.id, urgency, text: text.trim() });
      toast.success(result.appended_note ? 'ההערה נוספה' : 'ההקפצה נשלחה');
      onSent(result);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בשליחת ההקפצה');
    } finally { setSending(false); }
  };
  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-md p-0 overflow-hidden" dir="rtl">
      <form onSubmit={submit}>
        <DialogHeader className="p-5 pb-3 text-right">
          <DialogTitle>הקפצה למנהל הפרויקט</DialogTitle>
          <DialogDescription>ריצוף ספייר · {buildingName} · דירה {unit?.label}</DialogDescription>
        </DialogHeader>
        <div className="px-5 space-y-4">
          {mode === 'new' && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950"><p className="font-bold mb-1">מה מצורף אוטומטית</p>{contextLine(context) || 'ללא פרטים נוספים'}</div>}
          {mode === 'new' && <div className="grid grid-cols-2 gap-2"><button type="button" onClick={() => chooseUrgency('urgent')} className={`min-h-[44px] rounded-lg py-2 text-sm font-bold border ${urgency === 'urgent' ? 'bg-red-600 text-white border-red-600' : 'border-slate-200 text-slate-600'}`}>דחוף</button><button type="button" onClick={() => chooseUrgency('normal')} className={`min-h-[44px] rounded-lg py-2 text-sm font-bold border ${urgency === 'normal' ? 'bg-amber-500 text-white border-amber-500' : 'border-slate-200 text-slate-600'}`}>רגיל</button></div>}
          <label className="block text-sm font-semibold text-slate-700">{mode === 'note' ? 'הערה' : 'הודעה (אפשר לשנות)'}<textarea value={text} onChange={e => { setEdited(true); setText(e.target.value); }} maxLength={500} rows={4} className="mt-1.5 w-full resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" /></label>
          <p className="text-left text-[11px] text-slate-400">{text.length}/500</p>
          <p className="text-xs leading-relaxed text-slate-500">{mode === 'note' ? 'ההערה תצורף להקפצה הפתוחה.' : 'ההקפצה תופיע למנהל הפרויקט באפליקציה — בפעמון וברשימת "לטיפולי" בדשבורד. לא נשלח וואטסאפ.'}</p>
        </div>
        <DialogFooter className="p-5 pt-4"><button disabled={sending || !text.trim()} className="min-h-[44px] w-full rounded-lg bg-amber-500 py-2.5 text-sm font-bold text-white disabled:opacity-50">{sending ? 'שולח...' : mode === 'note' ? 'הוסף הערה' : 'שלח למנהל הפרויקט'}</button></DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}