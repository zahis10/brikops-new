// ind2-fix4 E4 — read-only evidence view of a SIGNED induction training:
// exactly what the worker read (snapshot sections), the attestation text
// and the signature. No edit affordances by design.
import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../ui/dialog';
import { Badge } from '../ui/badge';
import { safetyService } from '../../services/api';

export default function InductionEvidenceModal({ projectId, training, workers, open, onClose }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!open || !training) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    safetyService.getInductionEvidence(projectId, training.id)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => {
        if (cancelled) return;
        const d = e?.response?.data?.detail;
        setError(typeof d === 'string' ? d : 'שגיאה בטעינת ראיות ההדרכה');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, training, projectId]);

  const workerName = (workers || []).find((w) => w.id === training?.worker_id)?.full_name || '';

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent dir="rtl" className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>ראיות הדרכת אתר{workerName ? ` — ${workerName}` : ''}</DialogTitle>
        </DialogHeader>
        {loading && (
          <div className="flex items-center justify-center py-10 text-slate-500">
            <Loader2 className="w-5 h-5 animate-spin ml-2" /> טוען…
          </div>
        )}
        {!loading && error && (
          <p className="text-sm text-red-600 py-4">{error}</p>
        )}
        {!loading && !error && data && (
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap gap-2 items-center">
              <Badge className="bg-emerald-100 text-emerald-800">חתום</Badge>
              {data.trained_at && (
                <span className="text-xs text-slate-500">בוצעה: {String(data.trained_at).slice(0, 10)}</span>
              )}
              {data.expires_at && (
                <span className="text-xs text-slate-500">בתוקף עד: {String(data.expires_at).slice(0, 10)}</span>
              )}
              {data.content_version != null && (
                <span className="text-xs text-slate-500">גרסת תוכן: {data.content_version}</span>
              )}
            </div>

            <div>
              <h4 className="font-semibold text-slate-900 mb-2">התוכן שהוצג לעובד</h4>
              <ol className="space-y-2 pr-4 list-decimal">
                {(data.sections || []).map((s, i) => (
                  <li key={i}>
                    <p className="font-medium text-slate-800">{s.title}</p>
                    <p className="text-slate-600 whitespace-pre-wrap">{s.body}</p>
                  </li>
                ))}
              </ol>
            </div>

            {data.attestation_text && (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                <h4 className="font-semibold text-slate-900 mb-1">הצהרת העובד</h4>
                <p className="text-slate-700 whitespace-pre-wrap">{data.attestation_text}</p>
              </div>
            )}

            <div className="border-t border-slate-100 pt-3 space-y-1">
              <h4 className="font-semibold text-slate-900">חתימה</h4>
              <p className="text-slate-600">
                {data.signer_name}
                {data.signed_at && ` · ${String(data.signed_at).slice(0, 10)}`}
                {data.via_interpreter && data.interpreter_name && ` · באמצעות מתורגמן: ${data.interpreter_name}`}
                {data.worker_language && data.language_read !== data.worker_language && ` · שפת העובד: ${data.worker_language}`}
              </p>
              {data.signature_display_url ? (
                <img
                  src={data.signature_display_url}
                  alt="חתימת העובד"
                  className="max-h-28 border border-slate-200 rounded-lg bg-white p-2"
                />
              ) : data.typed_name ? (
                <p className="text-slate-800 italic">"{data.typed_name}" (חתימה מוקלדת)</p>
              ) : null}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
