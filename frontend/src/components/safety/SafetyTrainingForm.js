import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
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
export default function SafetyTrainingForm({ projectId, training, open, onClose, onSaved, workers }) {
  const isEdit = !!training;

  const [workerId, setWorkerId] = useState('');
  const [trainingType, setTrainingType] = useState('');
  const [trainedAt, setTrainedAt] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [instructorName, setInstructorName] = useState('');
  const [durationMinutes, setDurationMinutes] = useState('');
  const [location, setLocation] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setWorkerId(training?.worker_id || '');
    setTrainingType(training?.training_type || '');
    setTrainedAt((training?.trained_at || '').slice(0, 10) || '');
    setExpiresAt((training?.expires_at || '').slice(0, 10) || '');
    setInstructorName(training?.instructor_name || '');
    setDurationMinutes(training?.duration_minutes != null ? String(training.duration_minutes) : '');
    setLocation(training?.location || '');
  }, [open, training]);

  const handleSubmit = async () => {
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
      title={isEdit ? 'עריכת הדרכה' : 'הדרכה חדשה'}
      onSubmit={handleSubmit}
      submitting={submitting}
    >
      <div className="space-y-1.5">
        <Label>עובד *</Label>
        <Select value={workerId} onValueChange={setWorkerId} dir="rtl" disabled={isEdit}>
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
    </SafetyFormModal>
  );
}
