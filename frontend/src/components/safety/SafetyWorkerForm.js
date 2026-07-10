import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Camera, X } from 'lucide-react';
import { compressImage } from '../../utils/imageCompress';
import { safetyService, projectCompanyService } from '../../services/api';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import SafetyFormModal from './SafetyFormModal';

// Sentinel for the "free-text new company" option (create only). Radix Select
// values must be non-empty strings, so we use an explicit token rather than ''.
const NEW_COMPANY = '__new__';
const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

// Create + edit a safety worker. Fields mirror SafetyWorkerCreate / SafetyWorkerUpdate
// exactly. id_number is WRITE-ONLY: the server hashes it and we never receive or
// display the stored hash — on edit we leave the field blank and only send it if
// the user types a new value.
export default function SafetyWorkerForm({ projectId, worker, open, onClose, onSaved }) {
  const isEdit = !!worker;

  const [fullName, setFullName] = useState('');
  const [profession, setProfession] = useState('');
  const [phone, setPhone] = useState('');
  const [companyId, setCompanyId] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [idNumber, setIdNumber] = useState('');
  const [notes, setNotes] = useState('');
  // photo: key = permanent stored_ref sent to the server; preview = display URL
  const [photo, setPhoto] = useState({ key: null, preview: null });
  const [photoBroken, setPhotoBroken] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [companies, setCompanies] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  // (Re)seed the form whenever it opens or the target row changes.
  useEffect(() => {
    if (!open) return;
    setFullName(worker?.full_name || '');
    setProfession(worker?.profession || '');
    setPhone(worker?.phone || '');
    setCompanyId(worker?.company_id || '');
    setCompanyName('');
    setIdNumber(''); // never prefill — stored value is a hash
    setNotes(worker?.notes || '');
    setPhoto({ key: worker?.photo_ref || null, preview: worker?.photo_display_url || null });
    setPhotoBroken(false);
  }, [open, worker]);

  // Best-effort company list (same PII-trimmed source NewDefectModal uses).
  useEffect(() => {
    if (!open || !projectId) return;
    let cancelled = false;
    projectCompanyService.list(projectId)
      .then((res) => {
        if (cancelled) return;
        const list = Array.isArray(res) ? res : (res?.items || []);
        setCompanies(list.map((c) => ({ id: c.id, name: c.name || c.id })));
      })
      .catch(() => { /* picker just stays empty — not fatal */ });
    return () => { cancelled = true; };
  }, [open, projectId]);

  const companyValue = useMemo(() => {
    if (companyName) return NEW_COMPANY;
    return companyId || '';
  }, [companyId, companyName]);

  const handleCompanyChange = (v) => {
    if (v === NEW_COMPANY) {
      setCompanyId('');
      setCompanyName(' '); // mark "new company" mode; trimmed before send
      return;
    }
    setCompanyName('');
    setCompanyId(v);
  };

  const handlePhoto = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      // worker photos are always images — always compress (no PDF branch)
      const toUpload = await compressImage(file);
      const res = await safetyService.uploadDocumentFile(projectId, toUpload);
      setPhoto({ key: res.stored_ref, preview: res.url });
      setPhotoBroken(false);
    } catch (err) {
      toast.error('העלאת התמונה נכשלה — נסה שוב');
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if (uploading) { toast.error('המתן לסיום העלאת התמונה'); return; }
    const name = fullName.trim();
    if (name.length < 2 || name.length > 120) {
      toast.error('שם מלא הוא שדה חובה (2-120 תווים)');
      return;
    }

    const payload = {
      full_name: name,
      profession: profession.trim() || null,
      phone: phone.trim() || null,
      notes: notes.trim() || null,
      company_id: companyId || null,
      photo_ref: photo.key || null,  // null clears the photo (create + edit)
    };
    if (idNumber.trim()) payload.id_number = idNumber.trim();
    // company_name is create-only (SafetyWorkerUpdate has no company_name field).
    if (!isEdit && companyName.trim()) {
      payload.company_name = companyName.trim();
      payload.company_id = null;
    }

    setSubmitting(true);
    try {
      const result = isEdit
        ? await safetyService.updateWorker(projectId, worker.id, payload)
        : await safetyService.createWorker(projectId, payload);
      toast.success(isEdit ? 'עובד עודכן' : 'עובד נוסף');
      onSaved?.(result);
      onClose?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שמירה נכשלה');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafetyFormModal
      open={open}
      onOpenChange={(o) => { if (!o && !submitting) onClose?.(); }}
      title={isEdit ? 'עריכת עובד' : 'עובד חדש'}
      onSubmit={handleSubmit}
      submitting={submitting}
    >
      <div className="space-y-1.5">
        <Label htmlFor="sw-name">שם מלא *</Label>
        <Input id="sw-name" value={fullName} onChange={(e) => setFullName(e.target.value)} maxLength={120} placeholder="שם העובד" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="sw-profession">מקצוע</Label>
          <Input id="sw-profession" value={profession} onChange={(e) => setProfession(e.target.value)} placeholder="לדוגמה: חשמלאי" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sw-phone">טלפון</Label>
          <Input id="sw-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="050-0000000" />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>חברה</Label>
        <Select value={companyValue} onValueChange={handleCompanyChange} dir="rtl">
          <SelectTrigger>
            <SelectValue placeholder="בחר חברה" />
          </SelectTrigger>
          <SelectContent>
            {companies.map((c) => (
              <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
            ))}
            {!isEdit && <SelectItem value={NEW_COMPANY}>+ חברה חדשה</SelectItem>}
          </SelectContent>
        </Select>
        {!isEdit && companyName && (
          <Input
            value={companyName.trimStart() === '' ? '' : companyName}
            onChange={(e) => setCompanyName(e.target.value || ' ')}
            placeholder="שם החברה החדשה"
            className="mt-2"
          />
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="sw-id">ת"ז</Label>
        <Input
          id="sw-id"
          value={idNumber}
          onChange={(e) => setIdNumber(e.target.value)}
          placeholder={isEdit ? 'השאר ריק כדי לא לשנות' : 'מספר תעודת זהות'}
          inputMode="numeric"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="sw-notes">הערות</Label>
        <Textarea id="sw-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
      </div>

      <div className="space-y-1.5">
        <Label>תמונת עובד</Label>
        <div className="flex items-center gap-3">
          {photo.preview && !photoBroken ? (
            <button
              type="button"
              onClick={() => { if (isHttp(photo.preview)) window.open(photo.preview, '_blank'); }}
              className="w-[88px] h-[88px] rounded-full overflow-hidden border border-slate-200 bg-slate-100 shrink-0"
              aria-label="תצוגת תמונת העובד"
            >
              <img src={photo.preview} alt="תמונת עובד" className="w-full h-full object-cover" onError={() => setPhotoBroken(true)} />
            </button>
          ) : (
            <div className="w-[88px] h-[88px] rounded-full border border-dashed border-slate-300 bg-slate-50 flex items-center justify-center shrink-0">
              <Camera className="w-6 h-6 text-slate-300" />
            </div>
          )}
          <div className="flex flex-col gap-2">
            <label
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-medium cursor-pointer hover:bg-slate-50 ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
            >
              <Camera className="w-4 h-4" />
              {uploading ? 'מעלה…' : (photo.key ? 'החלף תמונה' : 'הוסף תמונה')}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; handlePhoto(f); }}
              />
            </label>
            {photo.key && !uploading && (
              <button
                type="button"
                onClick={() => { setPhoto({ key: null, preview: null }); setPhotoBroken(false); }}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"
              >
                <X className="w-3.5 h-3.5" /> הסר תמונה
              </button>
            )}
          </div>
        </div>
      </div>
    </SafetyFormModal>
  );
}
