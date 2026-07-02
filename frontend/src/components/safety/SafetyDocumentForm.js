import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safetyService, projectCompanyService, projectService } from '../../services/api';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import SafetyFormModal from './SafetyFormModal';
import { CATEGORY_HE, SEVERITY_HE, DOC_STATUS_HE } from './safetyLabels';
import { compressImage } from '../../utils/imageCompress';
import { Camera, X } from 'lucide-react';

const todayIso = () => new Date().toISOString().slice(0, 10);

const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

// Create + edit a safety defect (safety_document). Fields mirror
// SafetyDocumentCreate / SafetyDocumentUpdate exactly. Photos: we upload to
// /safety/{pid}/upload and persist ONLY the permanent stored_ref key in photo_urls
// (never the presigned url, which expires). The backend regenerates a parallel
// photo_display_urls per-GET, which we zip into the edit preview. attachment_urls
// (PDFs) remain out of scope → always sent as [].
export default function SafetyDocumentForm({ projectId, document, open, onClose, onSaved }) {
  const isEdit = !!document;

  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('');
  const [severity, setSeverity] = useState('');
  const [foundAt, setFoundAt] = useState(todayIso());
  const [status, setStatus] = useState('open');
  const [location, setLocation] = useState('');
  const [description, setDescription] = useState('');
  const [companyId, setCompanyId] = useState('');
  const [companies, setCompanies] = useState([]);
  const [assigneeId, setAssigneeId] = useState('');
  const [members, setMembers] = useState([]);
  const [photos, setPhotos] = useState([]);   // [{ key: stored_ref, preview: display_url }]
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle(document?.title || '');
    setCategory(document?.category || '');
    setSeverity(document?.severity || '');
    setFoundAt((document?.found_at || '').slice(0, 10) || todayIso());
    setStatus(document?.status || 'open');
    setLocation(document?.location || '');
    setDescription(document?.description || '');
    setCompanyId(document?.company_id || '');
    setAssigneeId(document?.assignee_id || '');
    const keys = document?.photo_urls || [];
    const prevs = document?.photo_display_urls || [];
    setPhotos(keys.map((k, i) => ({ key: k, preview: prevs[i] || null })));
  }, [open, document]);

  useEffect(() => {
    if (!open || !projectId) return;
    let cancelled = false;
    // Fail-soft: a memberships failure must never blank the companies picker (mirror NewDefectModal).
    Promise.allSettled([
      projectCompanyService.list(projectId),
      projectService.getMemberships(projectId),
    ]).then(([compRes, memRes]) => {
      if (cancelled) return;
      if (compRes.status === 'fulfilled') {
        const cv = compRes.value;
        const list = Array.isArray(cv) ? cv : (cv?.items || []);
        setCompanies(list.map((c) => ({ id: c.id, name: c.name || c.id })));
      }
      if (memRes.status === 'fulfilled') {
        const mv = memRes.value;
        const mlist = Array.isArray(mv) ? mv : (mv?.items || []);
        const mgmt = mlist.filter((m) =>
          (m.role === 'project_manager' || m.role === 'management_team') &&
          (m.status !== 'pending')
        );
        setMembers(mgmt);
      }
    });
    return () => { cancelled = true; };
  }, [open, projectId]);

  const handlePhoto = async (file) => {
    if (!file) return;
    try {
      setUploading(true);
      const compressed = await compressImage(file);
      const res = await safetyService.uploadDocumentFile(projectId, compressed);
      if (res?.stored_ref) {
        setPhotos((prev) => [...prev, { key: res.stored_ref, preview: res.url || null }]);
      }
    } catch (e) {
      toast.error('העלאת תמונה נכשלה');
    } finally {
      setUploading(false);
    }
  };

  const removePhoto = (idx) => setPhotos((prev) => prev.filter((_, i) => i !== idx));

  const handleSubmit = async () => {
    const t = title.trim();
    if (t.length < 2 || t.length > 200) {
      toast.error('כותרת היא שדה חובה (2-200 תווים)');
      return;
    }
    if (!category) { toast.error('יש לבחור קטגוריה'); return; }
    if (!severity) { toast.error('יש לבחור חומרה'); return; }
    if (!foundAt) { toast.error('יש לבחור תאריך גילוי'); return; }

    const payload = {
      title: t,
      category,
      severity,
      found_at: foundAt,
      location: location.trim() || null,
      description: description.trim() || null,
      company_id: companyId || null,
      assignee_id: assigneeId || null,
      photo_urls: photos.map((p) => p.key),
      attachment_urls: [],
    };
    if (isEdit) payload.status = status;

    setSubmitting(true);
    try {
      const result = isEdit
        ? await safetyService.updateDocument(projectId, document.id, payload)
        : await safetyService.createDocument(projectId, payload);
      toast.success(isEdit ? 'ליקוי עודכן' : 'ליקוי נוסף');
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
      title={isEdit ? 'עריכת ליקוי' : 'ליקוי חדש'}
      onSubmit={handleSubmit}
      submitting={submitting}
    >
      <div className="space-y-1.5">
        <Label htmlFor="sd-title">כותרת *</Label>
        <Input id="sd-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="תיאור קצר של הליקוי" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>קטגוריה *</Label>
          <Select value={category} onValueChange={setCategory} dir="rtl">
            <SelectTrigger><SelectValue placeholder="בחר קטגוריה" /></SelectTrigger>
            <SelectContent>
              {Object.entries(CATEGORY_HE).map(([val, he]) => (
                <SelectItem key={val} value={val}>{he}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>חומרה *</Label>
          <Select value={severity} onValueChange={setSeverity} dir="rtl">
            <SelectTrigger><SelectValue placeholder="בחר חומרה" /></SelectTrigger>
            <SelectContent>
              {Object.entries(SEVERITY_HE).map(([val, he]) => (
                <SelectItem key={val} value={val}>{he}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="sd-found">תאריך גילוי *</Label>
          <Input id="sd-found" type="date" value={foundAt} onChange={(e) => setFoundAt(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sd-location">מיקום</Label>
          <Input id="sd-location" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="לדוגמה: בניין א׳ קומה 3" />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>חברה</Label>
        <Select value={companyId || ''} onValueChange={setCompanyId} dir="rtl">
          <SelectTrigger><SelectValue placeholder="בחר חברה" /></SelectTrigger>
          <SelectContent>
            {companies.map((c) => (
              <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label>אחראי</Label>
        <Select
          value={assigneeId || '__none__'}
          onValueChange={(v) => setAssigneeId(v === '__none__' ? '' : v)}
          dir="rtl"
        >
          <SelectTrigger><SelectValue placeholder="בחר אחראי" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">ללא אחראי</SelectItem>
            {members.map((m) => (
              <SelectItem key={m.user_id} value={m.user_id}>{m.user_name || 'חבר צוות'}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isEdit && (
        <div className="space-y-1.5">
          <Label>סטטוס</Label>
          <Select value={status} onValueChange={setStatus} dir="rtl">
            <SelectTrigger><SelectValue placeholder="בחר סטטוס" /></SelectTrigger>
            <SelectContent>
              {Object.entries(DOC_STATUS_HE).map(([val, he]) => (
                <SelectItem key={val} value={val}>{he}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="sd-desc">תיאור</Label>
        <Textarea id="sd-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </div>

      <div className="space-y-1.5">
        <Label>תמונות</Label>
        <label
          className={`flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl border-2 border-dashed border-purple-300 bg-purple-50 text-purple-700 font-medium text-sm cursor-pointer hover:bg-purple-100 active:scale-[0.99] min-h-[52px] transition-colors ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
        >
          <Camera className="w-5 h-5" />
          {uploading ? 'מעלה…' : 'צרף תמונה (מומלץ)'}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; handlePhoto(f); }}
          />
        </label>
        {photos.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {photos.map((p, idx) => (
              <div key={p.key || idx} className="relative w-20 h-20 rounded-lg overflow-hidden border border-slate-200 bg-slate-100">
                {isHttp(p.preview) ? (
                  <img src={p.preview} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400">
                    <Camera className="w-6 h-6" />
                  </div>
                )}
                <button
                  type="button"
                  aria-label="הסר תמונה"
                  onClick={() => removePhoto(idx)}
                  className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </SafetyFormModal>
  );
}
