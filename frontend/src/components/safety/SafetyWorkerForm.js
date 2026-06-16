import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
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

  const handleSubmit = async () => {
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
    </SafetyFormModal>
  );
}
