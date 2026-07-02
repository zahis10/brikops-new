import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safetyService } from '../../services/api';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Switch } from '../ui/switch';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import SafetyFormModal from './SafetyFormModal';
import { SEVERITY_HE, INCIDENT_TYPE_HE } from './safetyLabels';

// Create + edit a safety incident (safety_incident). Mirrors SafetyTaskForm chrome
// 1:1. workers passed as a prop (no self-fetch). occurred_at is a datetime-local
// string sent as-is (verified safe through every backend consumer). Incident
// photos / medical records / witnesses / status editing are OUT OF SCOPE here
// (incident GET endpoints don't regenerate display urls; PATCH exclude_unset
// preserves any untouched fields).
export default function SafetyIncidentForm({ projectId, incident, open, onClose, onSaved, workers }) {
  const isEdit = !!incident;

  const [incidentType, setIncidentType] = useState('');
  const [severity, setSeverity] = useState('');
  const [occurredAt, setOccurredAt] = useState('');
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [injuredWorkerId, setInjuredWorkerId] = useState('');
  const [reportedToAuthority, setReportedToAuthority] = useState(false);
  const [authorityReportRef, setAuthorityReportRef] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setIncidentType(incident?.incident_type || '');
    setSeverity(incident?.severity || '');
    setOccurredAt((incident?.occurred_at || '').slice(0, 16) || '');
    setDescription(incident?.description || '');
    setLocation(incident?.location || '');
    setInjuredWorkerId(incident?.injured_worker_id || '');
    setReportedToAuthority(!!incident?.reported_to_authority);
    setAuthorityReportRef(incident?.authority_report_ref || '');
  }, [open, incident]);

  const handleSubmit = async () => {
    if (!incidentType) { toast.error('יש לבחור סוג אירוע'); return; }
    if (!severity) { toast.error('יש לבחור חומרה'); return; }
    if (!occurredAt) { toast.error('יש לבחור מועד אירוע'); return; }
    const desc = description.trim();
    if (desc.length < 2) { toast.error('תיאור הוא שדה חובה (2 תווים לפחות)'); return; }

    const payload = {
      incident_type: incidentType,
      severity,
      occurred_at: occurredAt,
      description: desc,
      location: location.trim() || null,
      injured_worker_id: injuredWorkerId || null,
      reported_to_authority: reportedToAuthority,
      authority_report_ref: reportedToAuthority ? (authorityReportRef.trim() || null) : null,
    };

    setSubmitting(true);
    try {
      const result = isEdit
        ? await safetyService.updateIncident(projectId, incident.id, payload)
        : await safetyService.createIncident(projectId, payload);
      toast.success(isEdit ? 'אירוע עודכן' : 'אירוע נוסף');
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
      title={isEdit ? 'עריכת אירוע' : 'אירוע חדש'}
      onSubmit={handleSubmit}
      submitting={submitting}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>סוג אירוע *</Label>
          <Select value={incidentType} onValueChange={setIncidentType} dir="rtl">
            <SelectTrigger><SelectValue placeholder="בחר סוג" /></SelectTrigger>
            <SelectContent>
              {Object.entries(INCIDENT_TYPE_HE).map(([val, he]) => (
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

      <div className="space-y-1.5">
        <Label htmlFor="in-occurred">מועד האירוע *</Label>
        <Input id="in-occurred" type="datetime-local" value={occurredAt} onChange={(e) => setOccurredAt(e.target.value)} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="in-desc">תיאור *</Label>
        <Textarea id="in-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="in-location">מיקום</Label>
        <Input id="in-location" value={location} onChange={(e) => setLocation(e.target.value)} />
      </div>

      <div className="space-y-1.5">
        <Label>עובד נפגע</Label>
        <Select
          value={injuredWorkerId || '__none__'}
          onValueChange={(v) => setInjuredWorkerId(v === '__none__' ? '' : v)}
          dir="rtl"
        >
          <SelectTrigger><SelectValue placeholder="בחר עובד" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">ללא נפגע</SelectItem>
            {workers.map((w) => (
              <SelectItem key={w.id} value={w.id}>{w.full_name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center justify-between gap-3 py-1">
        <Label htmlFor="in-reported">דווח לרשות</Label>
        <Switch id="in-reported" checked={reportedToAuthority} onCheckedChange={setReportedToAuthority} />
      </div>

      {reportedToAuthority && (
        <div className="space-y-1.5">
          <Label htmlFor="in-ref">אסמכתא</Label>
          <Input id="in-ref" value={authorityReportRef} onChange={(e) => setAuthorityReportRef(e.target.value)} placeholder="מספר דיווח / אסמכתא" />
        </div>
      )}
    </SafetyFormModal>
  );
}
