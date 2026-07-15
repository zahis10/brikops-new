import React, { useEffect, useState } from 'react';
import { X, FileText, GraduationCap, AlertCircle, ChevronLeft } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { INCIDENT_TYPE_HE, SEVERITY_HE } from './safetyLabels';
import { safetyService } from '../../services/api';

// Read-only worker card. Mirrors SafetyDocumentDetail's chrome (Dialog
// modal={false} + outside-close prevention + [&>button]:hidden). Fetches the
// worker's trainings + incidents fail-soft (a rejected call -> [], never blanks
// the other). NEVER renders id_number / id_number_hash (PII) even though the
// list_workers projection returns them.
const SEVERITY_COLOR = {
  '1': 'bg-blue-100 text-blue-800',
  '2': 'bg-amber-100 text-amber-800',
  '3': 'bg-red-100 text-red-800',
};

const initialsOf = (name) => (name || '').trim().split(/\s+/).slice(0, 2)
  .map((w) => w[0]).join('').toUpperCase() || '?';

// Same idiom as SafetyWorkerForm — only open a real http(s) display URL in a
// new tab (a relative/blank ref is a no-op).
const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

function Field({ label, children }) {
  if (children == null || children === '') return null;
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <div className="text-sm text-slate-900">{children}</div>
    </div>
  );
}

// ind3-fix2 F2: the induction training type — must match backend
// INDUCTION_TRAINING_TYPE (same constant as SafetyHomePage).
const INDUCTION_TYPE = 'הדרכת אתר';

export default function SafetyWorkerCard({
  projectId, worker, open, onClose, isWriter, companies = [], onEditWorker, onAddTraining,
  onOpenEvidence, onOpenTraining,
}) {
  const [trainings, setTrainings] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [avatarBroken, setAvatarBroken] = useState(false);

  useEffect(() => {
    if (!open || !worker?.id) return undefined;
    let cancelled = false;
    setTrainings([]);
    setIncidents([]);
    setAvatarBroken(false);
    setLoading(true);
    Promise.allSettled([
      safetyService.listTrainings(projectId, { worker_id: worker.id, limit: 100 }),
      safetyService.listIncidents(projectId, { injured_worker_id: worker.id, limit: 100 }),
    ]).then(([tr, inc]) => {
      if (cancelled) return;
      setTrainings(tr.status === 'fulfilled' ? (tr.value?.items || []) : []);
      setIncidents(inc.status === 'fulfilled' ? (inc.value?.items || []) : []);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [open, worker?.id, projectId]);

  if (!worker) return null;

  const companyName = worker.company_id
    ? (companies.find((c) => c.id === worker.company_id)?.name
      || companies.find((c) => c.id === worker.company_id)?.company_name
      || null)
    : null;

  const today = new Date().toISOString().slice(0, 10);

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
          <DialogTitle className="text-base font-bold text-right">כרטיס עובד</DialogTitle>
        </DialogHeader>

        <div className="px-5 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          <div className="flex items-center gap-3">
            {worker.photo_display_url && !avatarBroken ? (
              <button
                type="button"
                onClick={() => { if (isHttp(worker.photo_display_url)) window.open(worker.photo_display_url, '_blank'); }}
                className="shrink-0 rounded-full"
                aria-label="הצג תמונת עובד"
              >
                <img
                  src={worker.photo_display_url}
                  alt={worker.full_name}
                  className="w-14 h-14 rounded-full object-cover border border-slate-200"
                  onError={() => setAvatarBroken(true)}
                />
              </button>
            ) : (
              <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 font-semibold shrink-0">
                {initialsOf(worker.full_name)}
              </div>
            )}
            <div className="min-w-0">
              <h3 className="text-lg font-bold text-slate-900">{worker.full_name}</h3>
              {worker.profession && <p className="text-sm text-slate-500 mt-0.5">{worker.profession}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            <Field label="חברה">{companyName}</Field>
            <Field label="טלפון">{worker.phone || null}</Field>
            <Field label="תאריך כניסה">{(worker.created_at || '').slice(0, 10) || null}</Field>
          </div>

          {worker.notes && (
            <Field label="הערות">
              <p className="whitespace-pre-wrap">{worker.notes}</p>
            </Field>
          )}

          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-slate-500" />
              <p className="text-sm font-semibold text-slate-700">הדרכות ({trainings.length})</p>
            </div>
            {trainings.length === 0 ? (
              <p className="text-sm text-slate-400">{loading ? 'טוען…' : 'אין הדרכות'}</p>
            ) : (
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
                {trainings.map((tr) => {
                  const expired = tr.expires_at && tr.expires_at.slice(0, 10) < today;
                  // ind3-fix2 F2: signed induction → evidence modal; anything
                  // else → jump to the trainings tab focused on this row.
                  const isSignedInduction = (tr.training_type || '').trim() === INDUCTION_TYPE
                    && !!tr.worker_signature;
                  const navigate = () => {
                    if (isSignedInduction) onOpenEvidence && onOpenEvidence(tr);
                    else onOpenTraining && onOpenTraining(tr);
                  };
                  return (
                    <li key={tr.id}>
                      <button
                        type="button"
                        onClick={navigate}
                        aria-label={isSignedInduction
                          ? `צפייה בראיות — ${tr.training_type}`
                          : `מעבר להדרכה — ${tr.training_type}`}
                        className="w-full text-right px-3 py-2 hover:bg-slate-50 transition-colors flex items-center gap-2 group"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-slate-900 text-sm">{tr.training_type}</p>
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            <span className="text-xs text-slate-500">{(tr.trained_at || '').slice(0, 10)}</span>
                            {tr.expires_at && (
                              <span className="text-xs text-slate-500">בתוקף עד {tr.expires_at.slice(0, 10)}</span>
                            )}
                            {expired && <Badge className="bg-red-100 text-red-800">פג תוקף</Badge>}
                            {tr.certificate_display_url && (
                              /* span (not <a>) — nested anchors inside the row
                                 button are invalid HTML; same isHttp guard as
                                 the photo link above. */
                              <span
                                role="link"
                                tabIndex={0}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (isHttp(tr.certificate_display_url)) window.open(tr.certificate_display_url, '_blank', 'noopener');
                                }}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' || e.key === ' ') {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    if (isHttp(tr.certificate_display_url)) window.open(tr.certificate_display_url, '_blank', 'noopener');
                                  }
                                }}
                                className="inline-flex items-center gap-1 text-xs text-purple-700 hover:underline cursor-pointer"
                              >
                                <FileText className="w-3.5 h-3.5" /> תעודה
                              </span>
                            )}
                          </div>
                        </div>
                        <ChevronLeft className="w-4 h-4 text-slate-300 group-hover:text-slate-500 shrink-0" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-slate-500" />
              <p className="text-sm font-semibold text-slate-700">אירועים ({incidents.length})</p>
            </div>
            {incidents.length === 0 ? (
              <p className="text-sm text-slate-400">{loading ? 'טוען…' : 'אין אירועים'}</p>
            ) : (
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
                {incidents.map((inc) => (
                  <li key={inc.id} className="px-3 py-2 flex items-start gap-2">
                    <Badge className={SEVERITY_COLOR[inc.severity] || 'bg-slate-100 text-slate-700'}>
                      {SEVERITY_HE[inc.severity] || '—'}
                    </Badge>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-900 text-sm truncate">
                        {INCIDENT_TYPE_HE[inc.incident_type] || inc.incident_type}
                      </p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-xs text-slate-500">{(inc.occurred_at || '').slice(0, 10)}</span>
                        {inc.location && <span className="text-xs text-slate-500">{inc.location}</span>}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {isWriter && (
          <DialogFooter className="px-5 py-3 border-t border-slate-100 bg-slate-50 flex flex-row-reverse gap-2 sm:justify-start">
            <Button type="button" onClick={() => onAddTraining(worker)} className="min-h-[44px] min-w-[96px]">
              הוסף הדרכה
            </Button>
            <Button type="button" variant="outline" onClick={() => onEditWorker(worker)} className="min-h-[44px]">
              ערוך עובד
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
