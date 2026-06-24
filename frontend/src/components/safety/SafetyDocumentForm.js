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

const todayIso = () => new Date().toISOString().slice(0, 10);

// Create + edit a safety defect (safety_document). Fields mirror
// SafetyDocumentCreate / SafetyDocumentUpdate exactly. NO photo upload this
// batch — we always send photo_urls:[] / attachment_urls:[] (photos = batch 1b,
// which needs a backend display-url regeneration touch to avoid presigned-URL expiry).
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
          (m.status === 'accepted' || !m.status)
        );
        setMembers(mgmt);
      }
    });
    return () => { cancelled = true; };
  }, [open, projectId]);

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
      photo_urls: [],
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
    </SafetyFormModal>
  );
}
