import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Camera, FileText, X } from 'lucide-react';
import { compressImage } from '../../utils/imageCompress';
import { safetyService } from '../../services/api';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import SafetyFormModal from './SafetyFormModal';
import { CHECK_RESULT_HE } from './safetyLabels';

// Record a performed inspection ("חידוש") for an equipment item. Mirrors the
// SafetyTrainingForm cert-upload pattern (image → compress, pdf → as-is, keep
// stored_ref). Server computes expiry from period_days when expires_at is blank.
const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);
const today = () => new Date().toISOString().slice(0, 10);

export default function SafetyEquipmentCheckModal({ projectId, equipment, track, open, onClose, onSaved }) {
  const tracks = equipment?.check_status || [];

  const [checkName, setCheckName] = useState('');
  const [newName, setNewName] = useState('');
  const [periodDays, setPeriodDays] = useState(null);
  const [performedAt, setPerformedAt] = useState(today());
  const [performedBy, setPerformedBy] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [result, setResult] = useState('pass');
  const [expiresAt, setExpiresAt] = useState('');
  const [notes, setNotes] = useState('');
  const [doc, setDoc] = useState({ key: null, preview: null, isPdf: false });
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCheckName(track?.check_name || '');
    setNewName('');
    setPeriodDays(track ? (track.period_days ?? null) : null);
    setPerformedAt(today());
    setPerformedBy('');
    setLicenseNumber('');
    setResult('pass');
    setExpiresAt('');
    setNotes('');
    setDoc({ key: null, preview: null, isPdf: false });
  }, [open, track]);

  const onPickTrack = (name) => {
    setCheckName(name);
    if (name === '__new__') { setPeriodDays(null); return; }
    const t = tracks.find((x) => x.check_name === name);
    setPeriodDays(t ? (t.period_days ?? null) : null);
  };

  const handleDoc = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const isPdf = file.type === 'application/pdf' || file.name?.toLowerCase().endsWith('.pdf');
      const toUpload = file.type?.startsWith('image/') ? await compressImage(file) : file;
      const res = await safetyService.uploadDocumentFile(projectId, toUpload);
      setDoc({ key: res.stored_ref, preview: res.url, isPdf });
    } catch (err) {
      toast.error('העלאת המסמך נכשלה — נסה שוב');
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if (uploading) { toast.error('המתן לסיום העלאת המסמך'); return; }
    const isNewCheck = checkName === '__new__' || tracks.length === 0;
    const effectiveName = isNewCheck ? newName.trim() : checkName;
    if (!effectiveName) { toast.error('יש להזין שם בדיקה'); return; }
    if (!performedAt) { toast.error('יש להזין תאריך ביצוע'); return; }
    if (expiresAt && expiresAt <= performedAt) {
      toast.error('תאריך תפוגה חייב להיות אחרי תאריך הבדיקה');
      return;
    }

    const payload = {
      check_name: effectiveName,
      period_days: periodDays ?? null,
      performed_at: performedAt,
      performed_by_name: performedBy.trim() || null,
      license_number: licenseNumber.trim() || null,
      result,
      notes: notes.trim() || null,
      document_ref: doc.key || null,
    };
    if (expiresAt) payload.expires_at = expiresAt;

    setSubmitting(true);
    try {
      const res = await safetyService.createEquipmentCheck(projectId, equipment.id, payload);
      toast.success('הבדיקה נרשמה');
      onSaved?.(res);
      onClose?.();
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'שגיאה ברישום הבדיקה');
    } finally {
      setSubmitting(false);
    }
  };

  if (!equipment) return null;

  return (
    <SafetyFormModal
      open={open}
      onOpenChange={(o) => { if (!o && !submitting) onClose?.(); }}
      title={track ? `חידוש — ${track.check_name}` : `רישום בדיקה — ${equipment.internal_code}`}
      onSubmit={handleSubmit}
      submitting={submitting}
      submitLabel="רשום בדיקה"
    >
      {track ? (
        <div className="space-y-1.5">
          <Label>בדיקה</Label>
          <div className="px-3 py-2 rounded-lg bg-slate-100 text-sm text-slate-800">
            {track.check_name}
            <span className="text-xs text-slate-400 mr-2">
              {track.period_days ? `כל ${track.period_days} ימים` : 'לפי אירוע'}
            </span>
          </div>
        </div>
      ) : (
        <div className="space-y-1.5">
          {tracks.length > 0 && (
            <>
              <Label>בדיקה *</Label>
              <Select value={checkName} onValueChange={onPickTrack} dir="rtl">
                <SelectTrigger><SelectValue placeholder="בחר בדיקה" /></SelectTrigger>
                <SelectContent>
                  {tracks.map((t) => (
                    <SelectItem key={t.check_name} value={t.check_name}>{t.check_name}</SelectItem>
                  ))}
                  <SelectItem value="__new__">בדיקה חדשה…</SelectItem>
                </SelectContent>
              </Select>
            </>
          )}
          {(checkName === '__new__' || tracks.length === 0) && (
            <div className="space-y-3 pt-1">
              <div className="space-y-1.5">
                <Label htmlFor="chk-newname">שם הבדיקה *</Label>
                <Input id="chk-newname" value={newName} maxLength={120} onChange={(e) => setNewName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="chk-period">תקופה בימים</Label>
                <Input
                  id="chk-period"
                  type="number"
                  min={1}
                  max={3650}
                  value={periodDays ?? ''}
                  onChange={(e) => { const n = parseInt(e.target.value, 10); setPeriodDays(Number.isNaN(n) ? null : n); }}
                />
                <p className="text-xs text-slate-400">ריק = ללא תקופה קבועה</p>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="chk-performed">תאריך ביצוע *</Label>
        <Input id="chk-performed" type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="chk-by">שם הבודק</Label>
          <Input id="chk-by" value={performedBy} maxLength={120} onChange={(e) => setPerformedBy(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="chk-license">מספר רישיון</Label>
          <Input id="chk-license" value={licenseNumber} maxLength={60} onChange={(e) => setLicenseNumber(e.target.value)} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>תוצאה</Label>
        <Select value={result} onValueChange={setResult} dir="rtl">
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {Object.entries(CHECK_RESULT_HE).map(([k, v]) => (
              <SelectItem key={k} value={k}>{v}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="chk-expires">תוקף עד</Label>
        <Input id="chk-expires" type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
        <p className="text-xs text-slate-400">
          ריק = חישוב אוטומטי לפי תקופת הבדיקה
          {periodDays ? ` (תקופה: כל ${periodDays} ימים)` : ''}
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="chk-notes">הערות</Label>
        <Input id="chk-notes" value={notes} maxLength={500} onChange={(e) => setNotes(e.target.value)} />
      </div>

      <div className="space-y-1.5">
        <Label>תסקיר (מסמך)</Label>
        {!doc.key ? (
          <label
            className={`flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl border-2 border-dashed border-purple-300 bg-purple-50 text-purple-700 font-medium text-sm cursor-pointer hover:bg-purple-100 active:scale-[0.99] min-h-[52px] transition-colors ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
          >
            <Camera className="w-5 h-5" />
            {uploading ? 'מעלה…' : 'צרף תסקיר (צילום / גלריה / PDF)'}
            <input
              type="file"
              accept="image/*,.pdf"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; handleDoc(f); }}
            />
          </label>
        ) : (
          <div className="flex items-center gap-3">
            {doc.isPdf ? (
              <span className="flex items-center gap-2 text-purple-700 text-sm font-medium">
                <FileText className="w-5 h-5" /> תסקיר (PDF)
              </span>
            ) : (isHttp(doc.preview)) ? (
              <div className="w-16 h-16 rounded-lg overflow-hidden border border-slate-200 bg-slate-100">
                <img src={doc.preview} alt="תסקיר" className="w-full h-full object-cover" />
              </div>
            ) : (
              <div className="w-16 h-16 rounded-lg border border-slate-200 bg-slate-100 flex items-center justify-center text-slate-400">
                <FileText className="w-6 h-6" />
              </div>
            )}
            <button
              type="button"
              aria-label="הסר מסמך"
              onClick={() => setDoc({ key: null, preview: null, isPdf: false })}
              className="w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </SafetyFormModal>
  );
}
