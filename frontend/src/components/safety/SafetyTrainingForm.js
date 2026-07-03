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

// Create + edit a safety training (safety_training). Mirrors SafetyTaskForm chrome
// 1:1. The workers list is passed as a prop (the page already holds it) — no
// self-fetch. On edit the backend Update model has NO worker_id, so the worker
// picker is disabled. certificate_url is out of scope (needs the durable-upload
// pattern; future).
const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

export default function SafetyTrainingForm({ projectId, training, open, onClose, onSaved, workers, lockedWorker }) {
  const isEdit = !!training;

  const [workerId, setWorkerId] = useState('');
  const [trainingType, setTrainingType] = useState('');
  const [trainedAt, setTrainedAt] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [instructorName, setInstructorName] = useState('');
  const [durationMinutes, setDurationMinutes] = useState('');
  const [location, setLocation] = useState('');
  const [cert, setCert] = useState({ key: null, preview: null, isPdf: false });
  const [certImgBroken, setCertImgBroken] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setWorkerId(training?.worker_id || lockedWorker?.id || '');
    setTrainingType(training?.training_type || '');
    setTrainedAt((training?.trained_at || '').slice(0, 10) || '');
    setExpiresAt((training?.expires_at || '').slice(0, 10) || '');
    setInstructorName(training?.instructor_name || '');
    setDurationMinutes(training?.duration_minutes != null ? String(training.duration_minutes) : '');
    setLocation(training?.location || '');
    const key = training?.certificate_url || null;
    setCert({
      key,
      preview: training?.certificate_display_url || null,
      isPdf: !!key && key.toLowerCase().endsWith('.pdf'),
    });
    setCertImgBroken(false);
  }, [open, training, lockedWorker]);

  const handleCert = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const isPdf = file.type === 'application/pdf' || file.name?.toLowerCase().endsWith('.pdf');
      const toUpload = file.type?.startsWith('image/') ? await compressImage(file) : file;
      const res = await safetyService.uploadDocumentFile(projectId, toUpload);
      setCert({ key: res.stored_ref, preview: res.url, isPdf });
      setCertImgBroken(false);
    } catch (err) {
      toast.error('העלאת התעודה נכשלה — נסה שוב');
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if (uploading) { toast.error('המתן לסיום העלאת התעודה'); return; }
    if (!isEdit && !workerId) { toast.error('יש לבחור עובד'); return; }
    const tt = trainingType.trim();
    if (tt.length < 2) { toast.error('סוג הדרכה הוא שדה חובה (2 תווים לפחות)'); return; }
    if (!trainedAt) { toast.error('יש לבחור תאריך הדרכה'); return; }

    const payload = {
      training_type: tt,
      trained_at: trainedAt,
      instructor_name: instructorName.trim() || null,
      duration_minutes: parseInt(durationMinutes, 10) || null,
      location: location.trim() || null,
      expires_at: expiresAt || null,
      certificate_url: cert.key || null,
    };
    if (!isEdit) payload.worker_id = workerId;

    setSubmitting(true);
    try {
      const result = isEdit
        ? await safetyService.updateTraining(projectId, training.id, payload)
        : await safetyService.createTraining(projectId, payload);
      toast.success(isEdit ? 'הדרכה עודכנה' : 'הדרכה נוספה');
      onSaved?.(result);
      onClose?.();
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'הפעולה נכשלה — רענן את הרשימה ונסה שוב');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafetyFormModal
      open={open}
      onOpenChange={(o) => { if (!o && !submitting) onClose?.(); }}
      title={isEdit ? 'עריכת הדרכה' : (lockedWorker ? `הדרכה לעובד ${lockedWorker.name}` : 'הדרכה חדשה')}
      onSubmit={handleSubmit}
      submitting={submitting}
    >
      <div className="space-y-1.5">
        <Label>עובד *</Label>
        <Select value={workerId} onValueChange={setWorkerId} dir="rtl" disabled={isEdit || !!lockedWorker}>
          <SelectTrigger><SelectValue placeholder="בחר עובד" /></SelectTrigger>
          <SelectContent>
            {workers.map((w) => (
              <SelectItem key={w.id} value={w.id}>{w.full_name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="tr-type">סוג הדרכה *</Label>
        <Input id="tr-type" value={trainingType} onChange={(e) => setTrainingType(e.target.value)} placeholder="לדוגמה: עבודה בגובה" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="tr-date">תאריך הדרכה *</Label>
          <Input id="tr-date" type="date" value={trainedAt} onChange={(e) => setTrainedAt(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="tr-expires">בתוקף עד</Label>
          <Input id="tr-expires" type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="tr-instructor">שם מדריך</Label>
          <Input id="tr-instructor" value={instructorName} onChange={(e) => setInstructorName(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="tr-duration">משך (דקות)</Label>
          <Input id="tr-duration" type="number" min="1" value={durationMinutes} onChange={(e) => setDurationMinutes(e.target.value)} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="tr-location">מיקום</Label>
        <Input id="tr-location" value={location} onChange={(e) => setLocation(e.target.value)} />
      </div>

      <div className="space-y-1.5">
        <Label>תעודת הדרכה (מומלץ)</Label>
        {!cert.key ? (
          <label
            className={`flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl border-2 border-dashed border-purple-300 bg-purple-50 text-purple-700 font-medium text-sm cursor-pointer hover:bg-purple-100 active:scale-[0.99] min-h-[52px] transition-colors ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
          >
            <Camera className="w-5 h-5" />
            {uploading ? 'מעלה…' : 'צרף תעודה (צילום / גלריה / PDF)'}
            <input
              type="file"
              accept="image/*,.pdf"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; handleCert(f); }}
            />
          </label>
        ) : (
          <div className="flex items-center gap-3">
            {cert.isPdf ? (
              isHttp(cert.preview) ? (
                <a href={cert.preview} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-purple-700 text-sm font-medium hover:underline">
                  <FileText className="w-5 h-5" /> תעודה (PDF)
                </a>
              ) : (
                <span className="flex items-center gap-2 text-slate-600 text-sm font-medium">
                  <FileText className="w-5 h-5" /> תעודה (PDF)
                </span>
              )
            ) : (isHttp(cert.preview) && !certImgBroken) ? (
              <a href={cert.preview} target="_blank" rel="noopener noreferrer" className="block w-16 h-16 rounded-lg overflow-hidden border border-slate-200 bg-slate-100">
                <img src={cert.preview} alt="תעודה" className="w-full h-full object-cover" onError={() => setCertImgBroken(true)} />
              </a>
            ) : (
              <div className="w-16 h-16 rounded-lg border border-slate-200 bg-slate-100 flex items-center justify-center text-slate-400">
                <FileText className="w-6 h-6" />
              </div>
            )}
            <button
              type="button"
              aria-label="הסר תעודה"
              onClick={() => { setCert({ key: null, preview: null, isPdf: false }); setCertImgBroken(false); }}
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
