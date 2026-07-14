import React, { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../ui/dialog';
import { Loader2, GraduationCap, ChevronLeft, X } from 'lucide-react';
import SafetySignaturePad from './SafetySignaturePad';
import { safetyService } from '../../services/api';

/**
 * Batch safety-ind2 — the induction CONDUCT ceremony (concept rulings
 * ה-5/ה-9/ה-11/ה-12). Three steps: language → read (scroll-to-bottom
 * gate) → sign (attestation shown verbatim above the pad; SafetySignaturePad
 * reused exactly like the training-signature UX). Picking "אחרת" makes
 * worker_language + interpreter_name REQUIRED (FE mirror of the 422).
 * No template → empty-state inside the dialog.
 */

function workerInitials(name) {
  return (name || '')
    .split(/\s+/).filter(Boolean).slice(0, 2)
    .map((p) => p[0]).join('') || '?';
}

const EMPTY_STATE_COPY =
  "לא הוגדר תוכן הדרכת אתר — מנהל הארגון מגדיר אותו בכרטיס 'תוכן הדרכת אתר' שבטאב הסקירה";

const SafetyInductionConduct = ({ projectId, worker, open, onClose, onConducted }) => {
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState(null);   // GET .../induction/content
  const [noTemplate, setNoTemplate] = useState(false);
  const [step, setStep] = useState(1);
  const [languageChoice, setLanguageChoice] = useState(null); // 'he' | 'other'
  const [workerLanguage, setWorkerLanguage] = useState('');
  const [interpreterName, setInterpreterName] = useState('');
  const [readDone, setReadDone] = useState(false);
  const [expiresAt, setExpiresAt] = useState('');
  const [padOpen, setPadOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [photoBroken, setPhotoBroken] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setStep(1);
    setLanguageChoice(null);
    setWorkerLanguage('');
    setInterpreterName('');
    setReadDone(false);
    setPadOpen(false);
    setPhotoBroken(false);
    setContent(null);
    setNoTemplate(false);
    setLoading(true);
    safetyService.getInductionContent(projectId)
      .then((data) => {
        setContent(data);
        const days = data?.default_validity_days || 365;
        const d = new Date();
        d.setDate(d.getDate() + days);
        setExpiresAt(d.toISOString().slice(0, 10));
      })
      .catch((e) => {
        if (e?.response?.status === 404) setNoTemplate(true);
        else toast.error('שגיאה בטעינת תוכן ההדרכה');
      })
      .finally(() => setLoading(false));
  }, [open, projectId]);

  const isOther = languageChoice === 'other';
  const otherBlocked = isOther && (!workerLanguage.trim() || !interpreterName.trim());

  const attestationText = isOther
    ? (content?.legal_text_interpreter || '')
        .replace('{worker_language}', workerLanguage.trim())
        .replace('{interpreter_name}', interpreterName.trim())
    : (content?.legal_text || '');

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el || readDone) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 24) setReadDone(true);
  }, [readDone]);

  // Short content may not scroll at all — check once when step 2 renders.
  useEffect(() => {
    if (step !== 2) return;
    const t = setTimeout(() => {
      const el = scrollRef.current;
      if (el && el.scrollHeight <= el.clientHeight + 8) setReadDone(true);
    }, 150);
    return () => clearTimeout(t);
  }, [step]);

  const submit = async ({ signerName, signatureType, typedName, blob }) => {
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append('worker_id', worker.id);
      fd.append('language_choice', languageChoice);
      if (isOther) {
        fd.append('worker_language', workerLanguage.trim());
        fd.append('interpreter_name', interpreterName.trim());
      } else if (interpreterName.trim()) {
        fd.append('interpreter_name', interpreterName.trim());
      }
      if (expiresAt) fd.append('expires_at', expiresAt);
      fd.append('signer_name', signerName || '');
      fd.append('signature_type', signatureType || '');
      if (typedName) fd.append('typed_name', typedName);
      if (blob) fd.append('signature_image', blob, 'signature.png');
      await safetyService.conductInduction(projectId, fd);
      toast.success('ההדרכה נרשמה');
      setPadOpen(false);
      onClose();
      onConducted?.();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'שגיאה ברישום ההדרכה');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={(v) => { if (!v && !saving) onClose(); }} modal={false}>
        <DialogContent
          dir="rtl"
          className="max-w-lg w-[95vw] h-[92dvh] max-h-[92dvh] flex flex-col p-0 gap-0 [&>button]:hidden"
          onInteractOutside={(e) => e.preventDefault()}
        >
          {/* ind2-fix1 E3: default Radix X hidden ([&>button]:hidden) — it
              overlapped the title icon in RTL. House pattern: our own X at
              the inline-end of a justify-between header row. */}
          <DialogHeader className="px-4 py-3 border-b border-slate-100 shrink-0 flex flex-row-reverse items-center justify-between space-y-0">
            <button
              type="button"
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors shrink-0"
              aria-label="סגור"
              onClick={() => { if (!saving) onClose(); }}
            >
              <X className="w-5 h-5" />
            </button>
            <DialogTitle className="flex items-center gap-2 text-base text-right">
              <GraduationCap className="w-5 h-5 text-purple-600" />
              ביצוע הדרכת אתר
            </DialogTitle>
          </DialogHeader>

          {loading && (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          )}

          {!loading && noTemplate && (
            <div className="flex-1 flex items-center justify-center p-6">
              <p className="text-sm text-slate-600 text-center leading-relaxed">{EMPTY_STATE_COPY}</p>
            </div>
          )}

          {!loading && content && step === 1 && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <p className="text-sm text-slate-700 font-medium">באיזו שפה תועבר ההדרכה לעובד?</p>
              <div className="space-y-2">
                {(content.languages_filled || []).map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => setLanguageChoice(lang)}
                    className={`w-full text-right px-4 py-3 rounded-xl border text-sm font-medium transition-colors ${
                      languageChoice === lang
                        ? 'border-purple-500 bg-purple-50 text-purple-800'
                        : 'border-slate-200 hover:bg-slate-50 text-slate-700'
                    }`}
                  >
                    {lang === 'he' ? 'עברית' : lang}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setLanguageChoice('other')}
                  className={`w-full text-right px-4 py-3 rounded-xl border text-sm font-medium transition-colors ${
                    isOther
                      ? 'border-purple-500 bg-purple-50 text-purple-800'
                      : 'border-slate-200 hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  אחרת (אין תרגום זמין)
                </button>
              </div>

              {isOther && (
                <div className="space-y-3 pt-1">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">
                      שפת העובד <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={workerLanguage}
                      onChange={(e) => setWorkerLanguage(e.target.value)}
                      placeholder="למשל: טיגרינית"
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">
                      שם המתורגמן/ית <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={interpreterName}
                      onChange={(e) => setInterpreterName(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                    />
                    <p className="text-[11px] text-slate-500 mt-1">
                      כשאין תוכן בשפת העובד, ההדרכה מועברת בעל-פה באמצעות מתורגמן — שם המתורגמן חובה.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {!loading && content && step === 2 && (
            <>
              <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3 shrink-0">
                {worker?.photo_display_url && !photoBroken ? (
                  <img
                    src={worker.photo_display_url}
                    alt=""
                    onError={() => setPhotoBroken(true)}
                    className="w-10 h-10 rounded-full object-cover shrink-0"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 text-sm font-semibold shrink-0">
                    {workerInitials(worker?.full_name)}
                  </div>
                )}
                <div className="min-w-0">
                  <p className="font-medium text-slate-900 truncate">{worker?.full_name}</p>
                  <p className="text-xs text-slate-500">
                    {isOther ? `הקראה באמצעות מתורגמן (${workerLanguage.trim()})` : 'קריאת תוכן ההדרכה'}
                  </p>
                </div>
              </div>
              <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto p-4 space-y-4">
                {(content.sections || []).map((s, i) => (
                  <div key={i}>
                    <h3 className="text-sm font-semibold text-slate-900 mb-1">{i + 1}. {s.title}</h3>
                    <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{s.body}</p>
                  </div>
                ))}
                <p className="text-[11px] text-slate-400 pt-2">גרסת תוכן {content.template_version}</p>
              </div>
            </>
          )}

          {!loading && content && step === 3 && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                <p className="text-sm text-slate-800 leading-relaxed font-medium">{attestationText}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">בתוקף עד</label>
                <input
                  type="date"
                  value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  ברירת מחדל: {content.default_validity_days} ימים. ניתן לעריכה.
                </p>
              </div>
              <button
                type="button"
                disabled={saving}
                onClick={() => setPadOpen(true)}
                className="w-full py-3 rounded-xl bg-purple-600 text-white text-sm font-semibold hover:bg-purple-700 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin inline" /> : 'חתימת העובד'}
              </button>
            </div>
          )}

          {!loading && content && (
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between shrink-0">
              <button
                type="button"
                disabled={saving}
                onClick={() => (step === 1 ? onClose() : setStep(step - 1))}
                className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100"
              >
                {step === 1 ? 'ביטול' : 'חזרה'}
              </button>
              {step < 3 && (
                <button
                  type="button"
                  disabled={
                    (step === 1 && (!languageChoice || otherBlocked)) ||
                    (step === 2 && !readDone)
                  }
                  onClick={() => setStep(step + 1)}
                  className="inline-flex items-center gap-1 px-5 py-2 rounded-lg bg-purple-600 text-white text-sm font-semibold hover:bg-purple-700 disabled:opacity-40"
                >
                  המשך <ChevronLeft className="w-4 h-4" />
                </button>
              )}
              {step === 2 && !readDone && (
                <span className="text-[11px] text-slate-400">יש לגלול עד סוף התוכן</span>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <SafetySignaturePad
        open={padOpen}
        onClose={() => { if (!saving) setPadOpen(false); }}
        slotLabel={`חתימת העובד — ${worker?.full_name || ''}`}
        defaultName={worker?.full_name || ''}
        saving={saving}
        onSave={submit}
      />
    </>
  );
};

export default SafetyInductionConduct;
