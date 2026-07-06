import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { X, FileText, Loader2 } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogClose,
} from '../ui/dialog';
import { Badge } from '../ui/badge';
import { safetyService } from '../../services/api';
import { CHECK_RESULT_HE } from './safetyLabels';

// Read-only check history for an equipment item. Mirrors SafetyDocumentDetail
// chrome (Dialog modal={false} + outside-close prevention). No delete affordance
// (batch safety-p3b locked semantics #5).
const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);
const heDate = (v) => (v ? new Date(v).toLocaleDateString('he-IL') : '');
const RESULT_COLOR = {
  pass: 'bg-emerald-100 text-emerald-800',
  conditional: 'bg-amber-100 text-amber-800',
  fail: 'bg-red-100 text-red-800',
};

export default function SafetyEquipmentHistory({ projectId, equipment, open, onClose }) {
  const [loading, setLoading] = useState(false);
  const [checks, setChecks] = useState([]);

  useEffect(() => {
    if (!open || !equipment?.id) return;
    let cancelled = false;
    setLoading(true);
    setChecks([]);
    (async () => {
      try {
        const resp = await safetyService.listEquipmentChecks(projectId, equipment.id, { limit: 100 });
        if (!cancelled) setChecks(resp?.items || []);
      } catch (e) {
        if (!cancelled) toast.error('שגיאה בטעינת היסטוריה');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, equipment?.id, projectId]);

  if (!equipment) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }} modal={false}>
      <DialogContent
        dir="rtl"
        className="max-w-lg w-[calc(100%-2rem)] p-0 gap-0 overflow-hidden [&>button]:hidden"
        onInteractOutside={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="bg-slate-900 text-white px-5 py-4 flex flex-row items-center justify-between space-y-0">
          <DialogClose asChild>
            <button type="button" className="p-1 rounded-lg hover:bg-slate-700 transition-colors" aria-label="סגור">
              <X className="w-5 h-5" />
            </button>
          </DialogClose>
          <DialogTitle className="text-base font-bold text-right">{`היסטוריית בדיקות — ${equipment.internal_code}`}</DialogTitle>
        </DialogHeader>

        <div className="px-5 py-4 space-y-3 max-h-[70vh] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : checks.length === 0 ? (
            <p className="text-center text-sm text-slate-500 py-8">אין בדיקות רשומות לפריט זה</p>
          ) : (
            checks.map((c) => (
              <div key={c.id} className="rounded-lg border border-slate-200 p-3 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm">
                    <span className="font-bold text-slate-900">{heDate(c.performed_at)}</span>
                    <span className="text-slate-500 mr-2">{c.check_name}</span>
                  </div>
                  <Badge className={RESULT_COLOR[c.result] || 'bg-slate-100 text-slate-700'}>
                    {CHECK_RESULT_HE[c.result] || c.result}
                  </Badge>
                </div>
                {(c.performed_by_name || c.license_number) && (
                  <p className="text-xs text-slate-500">
                    {c.performed_by_name || ''}
                    {c.license_number ? ` · רישיון ${c.license_number}` : ''}
                  </p>
                )}
                {c.expires_at && (
                  <p className="text-xs text-slate-500">{`תוקף עד ${heDate(c.expires_at)}`}</p>
                )}
                {c.notes && <p className="text-xs text-slate-500">{c.notes}</p>}
                {isHttp(c.document_display_url) && (
                  <button
                    type="button"
                    onClick={() => window.open(c.document_display_url, '_blank', 'noopener')}
                    className="inline-flex items-center gap-1 text-xs text-purple-700 hover:underline"
                  >
                    <FileText className="w-4 h-4" /> תסקיר
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
