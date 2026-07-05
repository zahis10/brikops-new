import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safetyService } from '../../services/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../ui/select';
import { CATEGORY_HE, SEVERITY_HE, TOUR_TYPE_HE, TOUR_STATUS_HE } from './safetyLabels';
import { compressImage } from '../../utils/imageCompress';
import { Camera, X, Loader2, Plus } from 'lucide-react';

const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

const STATUS_BADGE = {
  draft: 'bg-slate-100 text-slate-700',
  pending_signature: 'bg-amber-100 text-amber-800',
  signed: 'bg-green-100 text-green-800',
};

const EMPTY_FAIL = { severity: '', note: '', photos: [], defectTitle: '' };

// The checklist RUNNER (batch safety-p2-4b). Walk the site, mark each item
// תקין/נכשל/לא-רלוונטי. A failed item requires a severity and opens a linked
// defect SERVER-SIDE (4a) — so results are server-authoritative, never optimistic.
// modal={false} everywhere; the fail flow is an INLINE panel (no nested dialog).
export default function SafetyTourRunner({ projectId, tour, open, onClose, onChanged, isWriter }) {
  const [t, setT] = useState(tour);
  const [pendingItemId, setPendingItemId] = useState(null);
  const [expandedItemId, setExpandedItemId] = useState(null);
  const [failForm, setFailForm] = useState(EMPTY_FAIL);
  const [uploading, setUploading] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addLabel, setAddLabel] = useState('');
  const [addCategory, setAddCategory] = useState('other');
  const [adding, setAdding] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reopening, setReopening] = useState(false);

  // Re-init ONLY when a different tour opens — key on the id, not the object
  // reference, or the onChanged echo (runner → parent → prop) re-runs on every
  // save and wipes local UI state (expanded panel, fail form).
  useEffect(() => {
    if (open && tour) {
      setT(tour);
      setExpandedItemId(null);
      setFailForm(EMPTY_FAIL);
      setAddOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, tour?.id]);

  if (!open || !t) return null;

  const readOnly = t.status !== 'draft' || !isWriter;
  const items = t.items || [];
  const total = items.length;
  const answered = items.filter((it) => it.result != null).length;
  const unanswered = total - answered;
  const headerTitle = t.tour_type === 'custom' ? (t.custom_name || 'סיור מותאם') : (TOUR_TYPE_HE[t.tour_type] || 'סיור');

  const applyTour = (updated) => { setT(updated); onChanged?.(updated); };

  const patchItem = async (itemId, payload) => {
    setPendingItemId(itemId);
    try {
      const updated = await safetyService.updateTourItem(projectId, t.id, itemId, payload);
      applyTour(updated);
      return updated;
    } finally {
      setPendingItemId(null);
    }
  };

  const onSimpleResult = (item, result) => {
    if (readOnly || pendingItemId) return;
    if (expandedItemId === item.id) setExpandedItemId(null);
    // Server-authoritative: we do NOT flip local state first; on failure the row
    // simply keeps showing the server value (no "stuck" selection).
    patchItem(item.id, { result }).catch((err) => {
      toast.error(err?.response?.data?.detail || 'שמירת הפריט נכשלה');
    });
  };

  const onFailTap = (item) => {
    if (readOnly || pendingItemId) return;
    // Pre-fill from the item fields we have (severity lives on the defect, not
    // the item — re-choose it; idempotent server-side if a defect already exists).
    setFailForm({
      severity: '',
      note: item.note || '',
      photos: (item.photo_urls || []).map((k, i) => ({ key: k, preview: (item.photo_display_urls || [])[i] || null })),
      defectTitle: '',
    });
    setExpandedItemId(item.id);
  };

  const handleFailPhoto = async (file) => {
    if (!file) return;
    try {
      setUploading(true);
      const compressed = await compressImage(file);
      const res = await safetyService.uploadDocumentFile(projectId, compressed);
      if (res?.stored_ref) {
        setFailForm((f) => ({ ...f, photos: [...f.photos, { key: res.stored_ref, preview: res.url || null }] }));
      }
    } catch (e) {
      toast.error('העלאת תמונה נכשלה');
    } finally {
      setUploading(false);
    }
  };

  const removeFailPhoto = (idx) => setFailForm((f) => ({ ...f, photos: f.photos.filter((_, i) => i !== idx) }));

  const onFailSave = async (item) => {
    if (!failForm.severity || pendingItemId) return;   // client mirror of the 422
    try {
      await patchItem(item.id, {
        result: 'fail',
        severity: failForm.severity,
        note: failForm.note.trim() || null,
        photo_urls: failForm.photos.map((p) => p.key),
        defect_title: failForm.defectTitle.trim() || null,
      });
      setExpandedItemId(null);
      setFailForm(EMPTY_FAIL);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שמירת הפריט נכשלה');
    }
  };

  const onAddItem = async () => {
    const label = addLabel.trim();
    if (label.length < 2) { toast.error('יש להזין שם פריט (לפחות 2 תווים)'); return; }
    setAdding(true);
    try {
      const updated = await safetyService.addTourItem(projectId, t.id, { label, category: addCategory });
      applyTour(updated);
      setAddLabel(''); setAddCategory('other'); setAddOpen(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'הוספת פריט נכשלה');
    } finally {
      setAdding(false);
    }
  };

  const onSubmit = async () => {
    setSubmitting(true);
    try {
      const updated = await safetyService.submitTour(projectId, t.id);
      applyTour(updated);
      setConfirmSubmit(false);
      toast.success('הסיור הוגש לחתימה');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'ההגשה נכשלה');
    } finally {
      setSubmitting(false);
    }
  };

  const onReopen = async () => {
    setReopening(true);
    try {
      const updated = await safetyService.reopenTour(projectId, t.id);
      applyTour(updated);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'פתיחה מחדש נכשלה');
    } finally {
      setReopening(false);
    }
  };

  const resultBtn = (item, value, label, activeClass) => {
    const active = item.result === value;
    const disabled = readOnly || (pendingItemId && pendingItemId !== item.id) || (pendingItemId === item.id);
    const spinning = pendingItemId === item.id;
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => (value === 'fail' ? onFailTap(item) : onSimpleResult(item, value))}
        className={`flex-1 min-h-[44px] rounded-lg border text-sm font-medium px-2 flex items-center justify-center gap-1 transition-colors disabled:opacity-60 ${
          active ? activeClass : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
        }`}
      >
        {spinning && active && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        {label}
      </button>
    );
  };

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => { if (!o) onClose?.(); }} modal={false}>
        <DialogContent
          dir="rtl"
          className="max-w-lg w-[calc(100%-1.5rem)] max-h-[90vh] overflow-y-auto [&>button]:hidden p-0"
          onInteractOutside={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          <DialogHeader className="px-5 pt-5 pb-3 border-b sticky top-0 bg-white z-10">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <DialogTitle className="text-right truncate">{headerTitle}</DialogTitle>
                <p className="text-xs text-slate-500 mt-0.5">{t.tour_date}</p>
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <span className={`text-[11px] font-medium rounded-full px-2 py-0.5 ${STATUS_BADGE[t.status] || STATUS_BADGE.draft}`}>
                  {TOUR_STATUS_HE[t.status] || t.status}
                </span>
                <span className="text-xs text-slate-500">נענו {answered} מתוך {total}</span>
              </div>
            </div>
            <button
              type="button"
              aria-label="סגור"
              onClick={() => onClose?.()}
              className="absolute top-4 left-4 w-8 h-8 rounded-full hover:bg-slate-100 flex items-center justify-center text-slate-500"
            >
              <X className="w-4 h-4" />
            </button>
          </DialogHeader>

          <div className="px-5 py-4 space-y-3">
            {items.map((item) => (
              <div key={item.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-800">{item.label}</p>
                    <span className="inline-block mt-1 text-[10px] font-medium rounded-full bg-slate-100 text-slate-600 px-2 py-0.5">
                      {CATEGORY_HE[item.category] || item.category}
                    </span>
                    {item.defect_id && (
                      <Badge className="mr-1 mt-1 bg-red-100 text-red-700 hover:bg-red-100 align-middle">ליקוי נפתח</Badge>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  {resultBtn(item, 'pass', 'תקין', 'border-green-500 bg-green-500 text-white')}
                  {resultBtn(item, 'fail', 'נכשל', 'border-red-500 bg-red-500 text-white')}
                  {resultBtn(item, 'na', 'לא רלוונטי', 'border-slate-400 bg-slate-500 text-white')}
                </div>

                {expandedItemId === item.id && !readOnly && (
                  <div className="mt-3 rounded-lg bg-red-50 border border-red-100 p-3 space-y-3">
                    <div className="space-y-1.5">
                      <p className="text-xs font-medium text-slate-700">חומרה *</p>
                      <div className="flex gap-2">
                        {Object.entries(SEVERITY_HE).map(([val, he]) => (
                          <button
                            key={val}
                            type="button"
                            onClick={() => setFailForm((f) => ({ ...f, severity: val }))}
                            className={`flex-1 min-h-[40px] rounded-lg border text-sm font-medium transition-colors ${
                              failForm.severity === val
                                ? 'border-red-500 bg-red-500 text-white'
                                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                            }`}
                          >
                            {he}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <p className="text-xs font-medium text-slate-700">מה נמצא?</p>
                      <Textarea
                        value={failForm.note}
                        onChange={(e) => setFailForm((f) => ({ ...f, note: e.target.value }))}
                        rows={2}
                        placeholder="תיאור הממצא (רשות)"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <p className="text-xs font-medium text-slate-700">תמונות</p>
                      <label
                        className={`flex items-center justify-center gap-2 w-full px-3 py-2 rounded-lg border-2 border-dashed border-red-300 bg-white text-red-700 font-medium text-sm cursor-pointer hover:bg-red-50 min-h-[44px] ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
                      >
                        <Camera className="w-4 h-4" />
                        {uploading ? 'מעלה…' : 'צרף תמונה'}
                        <input
                          type="file"
                          accept="image/*"
                          className="hidden"
                          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; handleFailPhoto(f); }}
                        />
                      </label>
                      {failForm.photos.length > 0 && (
                        <div className="flex flex-wrap gap-2 pt-1">
                          {failForm.photos.map((p, idx) => (
                            <div key={p.key || idx} className="relative w-16 h-16 rounded-lg overflow-hidden border border-slate-200 bg-slate-100">
                              {isHttp(p.preview) ? (
                                <img src={p.preview} alt="" className="w-full h-full object-cover" />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-slate-400">
                                  <Camera className="w-5 h-5" />
                                </div>
                              )}
                              <button
                                type="button"
                                aria-label="הסר תמונה"
                                onClick={() => removeFailPhoto(idx)}
                                className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <p className="text-xs font-medium text-slate-700">כותרת הליקוי</p>
                      <Input
                        value={failForm.defectTitle}
                        onChange={(e) => setFailForm((f) => ({ ...f, defectTitle: e.target.value }))}
                        maxLength={200}
                        placeholder={`סיור בטיחות: ${item.label}`}
                      />
                    </div>

                    <div className="flex gap-2">
                      <Button
                        type="button"
                        className="flex-1 min-h-[44px]"
                        disabled={!failForm.severity || pendingItemId === item.id}
                        onClick={() => onFailSave(item)}
                      >
                        {pendingItemId === item.id ? 'שומר…' : 'שמור ופתח ליקוי'}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="min-h-[44px]"
                        disabled={pendingItemId === item.id}
                        onClick={() => { setExpandedItemId(null); setFailForm(EMPTY_FAIL); }}
                      >
                        ביטול
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {!readOnly && (
              addOpen ? (
                <div className="rounded-xl border border-dashed border-slate-300 p-3 space-y-2">
                  <Input
                    value={addLabel}
                    onChange={(e) => setAddLabel(e.target.value)}
                    maxLength={200}
                    placeholder="שם הפריט"
                  />
                  <Select value={addCategory} onValueChange={setAddCategory} dir="rtl">
                    <SelectTrigger><SelectValue placeholder="בחר קטגוריה" /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(CATEGORY_HE).map(([val, he]) => (
                        <SelectItem key={val} value={val}>{he}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="flex gap-2">
                    <Button type="button" className="flex-1 min-h-[44px]" disabled={adding} onClick={onAddItem}>
                      {adding ? 'מוסיף…' : 'הוסף'}
                    </Button>
                    <Button type="button" variant="outline" className="min-h-[44px]" disabled={adding} onClick={() => { setAddOpen(false); setAddLabel(''); setAddCategory('other'); }}>
                      ביטול
                    </Button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setAddOpen(true)}
                  className="w-full min-h-[44px] rounded-xl border border-dashed border-slate-300 text-sm text-slate-600 hover:bg-slate-50 flex items-center justify-center gap-1"
                >
                  <Plus className="w-4 h-4" /> הוסף פריט
                </button>
              )
            )}
          </div>

          <DialogFooter className="px-5 py-4 border-t sticky bottom-0 bg-white flex-col gap-2 sm:flex-col">
            {t.status === 'draft' && (
              <>
                {unanswered > 0 && (
                  <p className="text-xs text-slate-500 text-center w-full">נותרו {unanswered} פריטים ללא מענה</p>
                )}
                <Button
                  type="button"
                  className="w-full min-h-[48px]"
                  disabled={unanswered > 0 || !isWriter}
                  onClick={() => setConfirmSubmit(true)}
                >
                  הגש לחתימה
                </Button>
              </>
            )}
            {t.status === 'pending_signature' && (
              <>
                <p className="text-xs text-amber-700 text-center w-full">ממתין לחתימות — החתימות יתווספו בגרסה הבאה</p>
                {isWriter && (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full min-h-[44px]"
                    disabled={reopening}
                    onClick={onReopen}
                  >
                    {reopening ? 'פותח…' : 'פתח מחדש לעריכה'}
                  </Button>
                )}
              </>
            )}
            {t.status === 'signed' && (
              <p className="text-xs text-green-700 text-center w-full">הסיור חתום</p>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmSubmit} onOpenChange={(o) => { if (!o && !submitting) setConfirmSubmit(false); }} modal={false}>
        <DialogContent
          dir="rtl"
          className="max-w-sm w-[calc(100%-2rem)] [&>button]:hidden"
          onInteractOutside={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle className="text-right">הגשה לחתימה</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">לאחר ההגשה הסיור נעול לעריכה עד פתיחה מחדש. להגיש?</p>
          <DialogFooter className="flex-row-reverse gap-2 sm:gap-2">
            <Button type="button" className="min-h-[44px]" disabled={submitting} onClick={onSubmit}>
              {submitting ? 'מגיש…' : 'הגש'}
            </Button>
            <Button type="button" variant="outline" className="min-h-[44px]" disabled={submitting} onClick={() => setConfirmSubmit(false)}>
              ביטול
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
