import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowRight, RefreshCw, X, Plus, PenLine, Check, FileDown, ImagePlus,
} from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../ui/dialog';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import { useAuth } from '../../contexts/AuthContext';
import { diaryService, safetyService } from '../../services/api';
import { compressImage } from '../../utils/imageCompress';
import SafetySignaturePad from '../safety/SafetySignaturePad';
import {
  WEATHER_OPTIONS, STATUS_HE, SECTION_TITLES, DERIVED_HINT,
} from './diaryLabels';

/**
 * Work Diary entry editor (batch diary-d2). Draft mode = everything editable
 * with debounced autosave; signed mode = read-only + addendums. The derived
 * sections carry the locked transparency line (DERIVED_HINT) — derived data
 * is a suggestion, never a gate (concept decisions 6+9).
 */
export default function WorkDiaryEntryView({ projectId, entry, isWriter, onChanged, onBack }) {
  const { user } = useAuth();
  const editable = isWriter && entry.status === 'draft';

  // Local working copy for smooth typing; server truth flows back via onChanged.
  const [local, setLocal] = useState(entry);
  const [saveState, setSaveState] = useState('idle'); // idle | saving | saved
  const [refreshing, setRefreshing] = useState(false);
  const [padOpen, setPadOpen] = useState(false);
  const [signing, setSigning] = useState(false);
  const [addendumOpen, setAddendumOpen] = useState(false);
  const [addendumText, setAddendumText] = useState('');
  const [addingAddendum, setAddingAddendum] = useState(false);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);
  const [exporting, setExporting] = useState(false);
  const photoInputRef = useRef(null);
  // "+ הוסף שורה" scratch inputs
  const [newWorkerName, setNewWorkerName] = useState('');
  const [newWorkerCount, setNewWorkerCount] = useState('');
  const [newSub, setNewSub] = useState('');
  const [newEquip, setNewEquip] = useState('');
  const [newMaterial, setNewMaterial] = useState('');

  const pendingRef = useRef({});
  const timerRef = useRef(null);
  const savedFadeRef = useRef(null);
  const inFlightRef = useRef(null); // promise lock — serializes autosave vs sign/refresh

  useEffect(() => { setLocal(entry); }, [entry]);
  useEffect(() => () => {
    clearTimeout(timerRef.current);
    clearTimeout(savedFadeRef.current);
  }, []);

  const detailToast = (err, fallback) => {
    const d = err?.response?.data?.detail;
    toast.error(typeof d === 'string' ? d : fallback);
  };

  const flush = async () => {
    clearTimeout(timerRef.current);
    // Wait for any in-flight PATCH first — sign/refresh must never race a
    // timer-fired autosave (architect finding #2).
    if (inFlightRef.current) {
      try { await inFlightRef.current; } catch (e) { /* handled inside */ }
    }
    const payload = pendingRef.current;
    if (!Object.keys(payload).length) return true;
    pendingRef.current = {};
    setSaveState('saving');
    const run = (async () => {
      try {
        const resp = await diaryService.updateEntry(projectId, entry.id, payload);
        onChanged(resp);
        setSaveState('saved');
        clearTimeout(savedFadeRef.current);
        savedFadeRef.current = setTimeout(() => setSaveState('idle'), 2000);
        return true;
      } catch (err) {
        setSaveState('idle');
        detailToast(err, 'שגיאה בשמירה');
        if (err?.response?.status === 409) {
          // signed meanwhile — pull server truth and flip read-only
          try { onChanged(await diaryService.getEntry(projectId, entry.id)); } catch (e) { /* keep last */ }
        } else {
          // Durable autosave (architect finding #1): restore the failed
          // payload so the next flush retries it; newer edits win per key.
          pendingRef.current = { ...payload, ...pendingRef.current };
        }
        return false;
      } finally {
        inFlightRef.current = null;
      }
    })();
    inFlightRef.current = run;
    return run;
  };

  // One debounced PATCH per touched section (800ms) — no per-section save buttons.
  const queueSave = (partial) => {
    setLocal((prev) => ({ ...prev, ...partial }));
    pendingRef.current = { ...pendingRef.current, ...partial };
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(flush, 800);
  };

  const refreshDerived = async () => {
    setRefreshing(true);
    try {
      await flush(); // don't let a pending edit race the refresh
      const resp = await diaryService.refreshDerived(projectId, entry.id);
      onChanged(resp);
      toast.success('הנתונים עודכנו');
    } catch (err) {
      detailToast(err, 'שגיאה ברענון הנתונים');
    } finally {
      setRefreshing(false);
    }
  };

  const openSign = async () => {
    if (uploadingPhotos) {
      toast.error('המתן לסיום העלאת התמונות');
      return;
    }
    if (!local.no_work && !(local.work_description || '').trim()) {
      toast.error('יש למלא תיאור עבודות לפני חתימה');
      return;
    }
    const ok = await flush();
    if (ok) setPadOpen(true);
  };

  // ---------- D3: photos (reuses safety upload → keys under safety/{pid}/) ----------
  const MAX_PHOTOS = 12;

  const handlePhotoFiles = async (fileList) => {
    const files = Array.from(fileList || []).filter((f) => f.type?.startsWith('image/'));
    if (!files.length) return;
    const room = MAX_PHOTOS - (local.photo_refs || []).length;
    if (room <= 0) { toast.error(`הגעת למגבלת ${MAX_PHOTOS} תמונות`); return; }
    const batch = files.slice(0, room);
    if (batch.length < files.length) toast.error(`ניתן להוסיף עד ${MAX_PHOTOS} תמונות — הועלו הראשונות בלבד`);
    setUploadingPhotos(true);
    try {
      const refs = [];
      const urls = [];
      for (const file of batch) {
        const compressed = await compressImage(file);
        const res = await safetyService.uploadDocumentFile(projectId, compressed);
        refs.push(res.stored_ref);
        urls.push(res.url || null);
      }
      // Display URLs are per-GET only (never PATCHed) — merge locally so the
      // thumbs appear now; server truth returns the parallel list on next GET.
      setLocal((prev) => ({
        ...prev,
        photo_display_urls: [...(prev.photo_display_urls || []), ...urls],
      }));
      queueSave({ photo_refs: [...(local.photo_refs || []), ...refs] });
    } catch (err) {
      detailToast(err, 'העלאת התמונות נכשלה — נסה שוב');
    } finally {
      setUploadingPhotos(false);
      if (photoInputRef.current) photoInputRef.current.value = '';
    }
  };

  const removePhoto = (idx) => {
    setLocal((prev) => ({
      ...prev,
      photo_display_urls: (prev.photo_display_urls || []).filter((_, i) => i !== idx),
    }));
    queueSave({ photo_refs: (local.photo_refs || []).filter((_, i) => i !== idx) });
  };

  // ---------- D3: PDF export (mirrors SafetyTourRunner.onExportPdf) ----------
  const onExportPdf = async () => {
    setExporting(true);
    try {
      await flush(); // the PDF should reflect what the user sees
      const res = await diaryService.exportEntryPdf(projectId, entry.id);
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `diary_${local.diary_date}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('ייצוא PDF נכשל');
    } finally {
      setExporting(false);
    }
  };

  const doSign = async ({ signerName, signatureType, typedName, blob }) => {
    setSigning(true);
    try {
      const resp = await diaryService.signEntry(projectId, entry.id, { signerName, signatureType, typedName, blob });
      toast.success('היומן נחתם');
      setPadOpen(false);
      onChanged(resp);
    } catch (err) {
      detailToast(err, 'שגיאה בחתימה');
    } finally {
      setSigning(false);
    }
  };

  const submitAddendum = async () => {
    const text = addendumText.trim();
    if (!text) { toast.error('יש להזין טקסט'); return; }
    setAddingAddendum(true);
    try {
      const resp = await diaryService.addAddendum(projectId, entry.id, { text });
      setAddendumOpen(false);
      setAddendumText('');
      onChanged(resp);
    } catch (err) {
      detailToast(err, 'שגיאה בהוספת תוספת');
    } finally {
      setAddingAddendum(false);
    }
  };

  // ---------- section edit helpers (any edit marks the row manual) ----------
  const setWorkerCount = (idx, count) => {
    const rows = local.workers_by_company.map((r, i) => (
      i === idx ? { ...r, count: Math.max(0, Number(count) || 0), source: 'manual' } : r
    ));
    queueSave({ workers_by_company: rows });
  };
  const removeWorkerRow = (idx) => {
    queueSave({ workers_by_company: local.workers_by_company.filter((_, i) => i !== idx) });
  };
  const addWorkerRow = () => {
    const name = newWorkerName.trim();
    if (!name) { toast.error('הזן שם חברה'); return; }
    queueSave({
      workers_by_company: [
        ...local.workers_by_company,
        { company_id: null, company_name: name, count: Math.max(0, Number(newWorkerCount) || 0), source: 'manual' },
      ],
    });
    setNewWorkerName(''); setNewWorkerCount('');
  };

  const removeFromList = (field, idx) => {
    queueSave({ [field]: local[field].filter((_, i) => i !== idx) });
  };
  const addChip = (field, item, clear) => {
    queueSave({ [field]: [...local[field], item] });
    clear();
  };

  const d = new Date(`${local.diary_date}T00:00:00`);
  const dateTitle = d.toLocaleDateString('he-IL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const sig = local.worker_signature;

  const sectionCard = (titleKey, children, { derived = false } = {}) => (
    <Card className="p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900">{SECTION_TITLES[titleKey]}</h3>
      </div>
      {derived && editable && (
        <p className="text-xs text-slate-400">{DERIVED_HINT}</p>
      )}
      {children}
    </Card>
  );

  const chipList = (field, labelOf) => (
    <div className="flex flex-wrap gap-1.5">
      {(local[field] || []).map((it, idx) => (
        <span key={idx} className="inline-flex items-center gap-1 text-xs bg-slate-100 text-slate-700 rounded-full px-2.5 py-1">
          {labelOf(it)}
          {editable && (
            <button type="button" onClick={() => removeFromList(field, idx)} aria-label="הסר" className="text-slate-400 hover:text-slate-700">
              <X className="w-3 h-3" />
            </button>
          )}
        </span>
      ))}
      {!(local[field] || []).length && <p className="text-xs text-slate-400">—</p>}
    </div>
  );

  const addRow = (value, setValue, placeholder, onAdd) => editable && (
    <div className="flex gap-2 pt-1">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className="h-8 text-sm"
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onAdd(); } }}
      />
      <Button type="button" variant="outline" size="sm" className="h-8 shrink-0" onClick={onAdd}>
        <Plus className="w-3.5 h-3.5" />
        הוסף
      </Button>
    </div>
  );

  const readonlyLines = (field, lineOf) => (
    <ul className="space-y-1">
      {(local[field] || []).map((it, idx) => (
        <li key={idx} className="flex items-center gap-2 text-sm text-slate-700">
          <span className="flex-1 min-w-0 truncate">{lineOf(it)}</span>
          {editable && (
            <button type="button" onClick={() => removeFromList(field, idx)} aria-label="הסר" className="text-slate-400 hover:text-slate-700 shrink-0">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </li>
      ))}
      {!(local[field] || []).length && <p className="text-xs text-slate-400">אין רשומות</p>}
    </ul>
  );

  const inspector = local.inspector_visit || {};
  const setInspector = (key, val) => {
    queueSave({ inspector_visit: { ...inspector, [key]: val, source: 'manual' } });
  };

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 pb-28">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="flex items-center gap-2 px-4 py-3">
          <button onClick={onBack} className="p-2 rounded-lg hover:bg-slate-100" aria-label="חזור" type="button">
            <ArrowRight className="w-5 h-5 text-slate-700" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-base font-bold text-slate-900 truncate">{dateTitle}</h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${local.status === 'signed' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
                {STATUS_HE[local.status] || local.status}
              </span>
              {local.entered_late && (
                <span className="text-[11px] px-1.5 py-0.5 rounded-full border border-red-300 text-red-600">הוזן באיחור</span>
              )}
              {local.no_work && (
                <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600">לא עבדו</span>
              )}
            </div>
          </div>
          {editable && saveState !== 'idle' && (
            <span className="text-xs text-slate-400 flex items-center gap-1 shrink-0">
              {saveState === 'saving' ? 'שומר…' : (<><Check className="w-3.5 h-3.5 text-green-600" />נשמר</>)}
            </span>
          )}
          <button
            type="button"
            onClick={onExportPdf}
            disabled={exporting}
            className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-50 shrink-0"
            aria-label="הורד PDF"
            title="הורד PDF"
          >
            <FileDown className={`w-5 h-5 text-slate-700 ${exporting ? 'animate-pulse' : ''}`} />
          </button>
        </div>
        {local.status === 'signed' && (
          <div className="px-4 pb-3 flex items-center gap-3">
            {local.signed_at && (
              <p className="text-xs text-slate-500">
                נחתם {new Date(local.signed_at).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' })}
                {sig?.name && ` · ${sig.name}`}
              </p>
            )}
            {sig?.signature_display_url && (
              <button
                type="button"
                onClick={() => window.open(sig.signature_display_url, '_blank')}
                className="shrink-0"
                aria-label="הצג חתימה"
              >
                <img src={sig.signature_display_url} alt="חתימה" className="h-8 border border-slate-200 rounded bg-white" />
              </button>
            )}
            {sig?.signature_type === 'typed' && sig?.typed_name && (
              <span className="text-sm italic text-slate-600">{sig.typed_name}</span>
            )}
          </div>
        )}
      </header>

      <main className="p-4 space-y-3 max-w-2xl mx-auto">
        {local.no_work && local.no_work_reason && (
          <Card className="p-4 bg-slate-100 border-slate-200">
            <p className="text-sm text-slate-700">לא בוצעה עבודה — {local.no_work_reason}</p>
          </Card>
        )}

        {sectionCard('work_description', (
          editable ? (
            <>
              <Textarea
                value={local.work_description || ''}
                onChange={(e) => queueSave({ work_description: e.target.value })}
                placeholder="פרט את העבודות שבוצעו היום"
                rows={4}
                maxLength={2000}
              />
              {!local.no_work && <p className="text-xs text-slate-400">נדרש לפני חתימה</p>}
            </>
          ) : (
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{local.work_description || '—'}</p>
          )
        ))}

        {sectionCard('workers_by_company', (
          <>
            <ul className="space-y-2">
              {(local.workers_by_company || []).map((row, idx) => (
                <li key={idx} className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-800 truncate">{row.company_name || 'ללא חברה'}</p>
                    {row.source === 'derived' && editable && (
                      <p className="text-[11px] text-slate-400">{DERIVED_HINT}</p>
                    )}
                  </div>
                  {editable ? (
                    <>
                      <Input
                        type="number"
                        min="0"
                        value={row.count ?? 0}
                        onChange={(e) => setWorkerCount(idx, e.target.value)}
                        className="w-20 h-8 text-sm text-center shrink-0"
                        aria-label={`מספר עובדים — ${row.company_name || 'ללא חברה'}`}
                      />
                      <button type="button" onClick={() => removeWorkerRow(idx)} aria-label="הסר שורה" className="text-slate-400 hover:text-slate-700 shrink-0">
                        <X className="w-4 h-4" />
                      </button>
                    </>
                  ) : (
                    <span className="text-sm font-medium text-slate-700 shrink-0">{row.count ?? 0}</span>
                  )}
                </li>
              ))}
              {!(local.workers_by_company || []).length && <p className="text-xs text-slate-400">אין עובדים רשומים</p>}
            </ul>
            {editable && (
              <div className="flex gap-2 pt-1">
                <Input
                  value={newWorkerName}
                  onChange={(e) => setNewWorkerName(e.target.value)}
                  placeholder="שם חברה / קבוצה"
                  className="h-8 text-sm"
                />
                <Input
                  type="number"
                  min="0"
                  value={newWorkerCount}
                  onChange={(e) => setNewWorkerCount(e.target.value)}
                  placeholder="כמות"
                  className="w-20 h-8 text-sm text-center shrink-0"
                />
                <Button type="button" variant="outline" size="sm" className="h-8 shrink-0" onClick={addWorkerRow}>
                  <Plus className="w-3.5 h-3.5" />
                  הוסף שורה
                </Button>
              </div>
            )}
          </>
        ))}

        {sectionCard('subcontractors', (
          <>
            {chipList('subcontractors', (s) => s.name || s.company_name || '—')}
            {addRow(newSub, setNewSub, 'שם קבלן משנה', () => {
              const v = newSub.trim();
              if (!v) return;
              addChip('subcontractors', { company_id: null, name: v, source: 'manual' }, () => setNewSub(''));
            })}
          </>
        ), { derived: (local.subcontractors || []).some((s) => s.source === 'derived') })}

        {sectionCard('equipment_list', (
          <>
            {chipList('equipment_list', (eq) => eq.name || [eq.internal_code, eq.category].filter(Boolean).join(' · ') || '—')}
            {addRow(newEquip, setNewEquip, 'שם ציוד', () => {
              const v = newEquip.trim();
              if (!v) return;
              addChip('equipment_list', { name: v, source: 'manual' }, () => setNewEquip(''));
            })}
          </>
        ), { derived: (local.equipment_list || []).some((eq) => eq.source === 'derived') })}

        {sectionCard('materials_received', (
          <>
            {chipList('materials', (m) => m)}
            {addRow(newMaterial, setNewMaterial, 'חומר שהגיע לאתר', () => {
              const v = newMaterial.trim();
              if (!v) return;
              if ((local.materials || []).length >= 40) { toast.error('הגעת למגבלת החומרים'); return; }
              addChip('materials', v, () => setNewMaterial(''));
            })}
          </>
        ))}

        {sectionCard('weather', (
          editable ? (
            <Select
              value={local.weather?.desc || ''}
              onValueChange={(v) => queueSave({ weather: { desc: v, source: 'manual' } })}
              dir="rtl"
            >
              <SelectTrigger><SelectValue placeholder="בחר מזג אוויר (אופציונלי)" /></SelectTrigger>
              <SelectContent>
                {WEATHER_OPTIONS.map((w) => (
                  <SelectItem key={w} value={w}>{w}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <p className="text-sm text-slate-700">{local.weather?.desc || '—'}</p>
          )
        ))}

        {sectionCard('incidents_summary', readonlyLines('incidents_summary', (it) => (
          [it.incident_type, it.description].filter(Boolean).join(' — ') || '—'
        )), { derived: true })}

        {sectionCard('tours_summary', readonlyLines('tours_summary', (it) => (
          [it.tour_type, it.status].filter(Boolean).join(' · ') || '—'
        )), { derived: true })}

        {sectionCard('trainings_summary', readonlyLines('trainings_summary', (it) => (
          [it.worker_name, it.training_type].filter(Boolean).join(' — ') || '—'
        )), { derived: true })}

        {sectionCard('defect_counts', (
          <p className="text-sm text-slate-700">
            {local.defect_counts
              ? `נפתחו ${local.defect_counts.opened ?? 0} · נסגרו ${local.defect_counts.closed ?? 0}`
              : '—'}
          </p>
        ), { derived: true })}

        {sectionCard('inspector_visit', (
          editable ? (
            <div className="space-y-2">
              <Input
                value={inspector.visitor || ''}
                onChange={(e) => setInspector('visitor', e.target.value)}
                placeholder="מי ביקר"
                className="h-9 text-sm"
              />
              <Input
                value={inspector.checked || ''}
                onChange={(e) => setInspector('checked', e.target.value)}
                placeholder="מה נבדק"
                className="h-9 text-sm"
              />
              <Input
                value={inspector.notes || ''}
                onChange={(e) => setInspector('notes', e.target.value)}
                placeholder="הערות"
                className="h-9 text-sm"
              />
            </div>
          ) : (
            <p className="text-sm text-slate-700">
              {[inspector.visitor, inspector.checked, inspector.notes].filter(Boolean).join(' · ') || '—'}
            </p>
          )
        ))}

        {(editable || (local.photo_refs || []).length > 0) && sectionCard('photos', (
          <>
            <div className="flex flex-wrap gap-2">
              {(local.photo_refs || []).map((ref, idx) => {
                const url = (local.photo_display_urls || [])[idx];
                return (
                  <div key={`${ref}-${idx}`} className="relative">
                    {url ? (
                      <button
                        type="button"
                        onClick={() => window.open(url, '_blank')}
                        aria-label={`תמונה ${idx + 1}`}
                      >
                        <img
                          src={url}
                          alt={`תמונה ${idx + 1}`}
                          className="w-20 h-20 object-cover rounded-lg border border-slate-200 bg-white"
                        />
                      </button>
                    ) : (
                      <div className="w-20 h-20 rounded-lg border border-slate-200 bg-slate-100 flex items-center justify-center">
                        <ImagePlus className="w-5 h-5 text-slate-300" />
                      </div>
                    )}
                    {editable && (
                      <button
                        type="button"
                        onClick={() => removePhoto(idx)}
                        aria-label="הסר תמונה"
                        className="absolute -top-1.5 -left-1.5 bg-white border border-slate-200 rounded-full p-0.5 text-slate-500 hover:text-slate-800 shadow-sm"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                );
              })}
              {!(local.photo_refs || []).length && !editable && (
                <p className="text-xs text-slate-400">—</p>
              )}
            </div>
            {editable && (
              <>
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => handlePhotoFiles(e.target.files)}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 gap-1.5"
                  disabled={uploadingPhotos}
                  onClick={() => photoInputRef.current?.click()}
                >
                  <ImagePlus className="w-3.5 h-3.5" />
                  {uploadingPhotos ? 'מעלה…' : 'הוסף תמונות'}
                </Button>
              </>
            )}
          </>
        ))}

        {sectionCard('special_instructions', (
          editable ? (
            <Textarea
              value={local.special_instructions || ''}
              onChange={(e) => queueSave({ special_instructions: e.target.value })}
              placeholder="הוראות מיוחדות (אופציונלי)"
              rows={2}
              maxLength={1000}
            />
          ) : (
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{local.special_instructions || '—'}</p>
          )
        ))}

        {local.status === 'signed' && (
          <Card className="p-4 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900">{SECTION_TITLES.addendums}</h3>
              {isWriter && (
                <Button type="button" variant="outline" size="sm" className="h-8" onClick={() => setAddendumOpen(true)}>
                  <Plus className="w-3.5 h-3.5" />
                  הוספת תוספת
                </Button>
              )}
            </div>
            {(local.addendums || []).length ? (
              <ul className="space-y-2">
                {local.addendums.map((a, idx) => (
                  <li key={idx} className="border border-slate-100 rounded-lg p-2.5 bg-slate-50">
                    <p className="text-sm text-slate-800 whitespace-pre-wrap">{a.text}</p>
                    <p className="text-[11px] text-slate-400 mt-1">
                      {a.created_at && new Date(a.created_at).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' })}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400">אין תוספות</p>
            )}
          </Card>
        )}
      </main>

      {editable && (
        <div className="fixed bottom-0 inset-x-0 z-40 bg-white border-t border-slate-200 p-3">
          <div className="max-w-2xl mx-auto flex gap-2">
            <Button variant="outline" onClick={refreshDerived} disabled={refreshing} className="gap-1.5">
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              רענן נתונים
            </Button>
            <Button onClick={openSign} disabled={signing || refreshing} className="flex-1 gap-1.5">
              <PenLine className="w-4 h-4" />
              חתום וסגור את היום
            </Button>
          </div>
        </div>
      )}

      <SafetySignaturePad
        open={padOpen}
        onClose={() => { if (!signing) setPadOpen(false); }}
        slotLabel="חתימת מנהל העבודה"
        defaultName={user?.full_name || user?.name || ''}
        saving={signing}
        onSave={doSign}
      />

      <Dialog open={addendumOpen} onOpenChange={(o) => { if (!addingAddendum) setAddendumOpen(o); }}>
        <DialogContent dir="rtl" className="max-w-sm">
          <DialogHeader>
            <DialogTitle>הוספת תוספת</DialogTitle>
          </DialogHeader>
          <Textarea
            value={addendumText}
            onChange={(e) => setAddendumText(e.target.value)}
            placeholder="טקסט התוספת"
            rows={4}
            maxLength={1000}
          />
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setAddendumOpen(false)} disabled={addingAddendum}>ביטול</Button>
            <Button onClick={submitAddendum} disabled={addingAddendum}>
              {addingAddendum ? 'מוסיף…' : 'הוסף'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
