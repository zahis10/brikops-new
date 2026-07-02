import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safetyService, projectCompanyService, projectService } from '../../services/api';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import SafetyFormModal from './SafetyFormModal';
import { SEVERITY_HE, TASK_STATUS_HE } from './safetyLabels';

// Create + edit a corrective safety task (safety_task). Mirrors SafetyDocumentForm
// structure/chrome 1:1. Self-fetches companies + memberships (memberships filtered
// role∈{project_manager,management_team} & status!==pending, same as the defect
// assignee) rather than taking them as props, because the page's `users` state is
// mapped to {id,name} and lacks the role/status needed for that filter.
//
// The status block MIRRORS the server transitions (safety_router
// _assert_transition_allowed) exactly — the UI must never submit a transition the
// server will 409 on:
//   open -> in_progress (+cancelled if PM)
//   in_progress -> completed (+cancelled if PM)
//   completed -> (cancelled if PM, else none)
//   cancelled -> none
// "completed" additionally REQUIRES a non-empty corrective_action in the same payload.
const NEXT_BASE = {
  open: ['in_progress'],
  in_progress: ['completed'],
  completed: [],
  cancelled: [],
};

const allowedNext = (current, myRole) => {
  const base = NEXT_BASE[current] || [];
  if (current !== 'cancelled' && myRole === 'project_manager') {
    return [...base, 'cancelled'];
  }
  return base;
};

export default function SafetyTaskForm({ projectId, task, open, onClose, onSaved, myRole }) {
  const isEdit = !!task;

  const [title, setTitle] = useState('');
  const [severity, setSeverity] = useState('');
  const [description, setDescription] = useState('');
  const [assigneeId, setAssigneeId] = useState('');
  const [companyId, setCompanyId] = useState('');
  const [dueAt, setDueAt] = useState('');
  const [statusChoice, setStatusChoice] = useState('__nochange__');
  const [correctiveAction, setCorrectiveAction] = useState('');

  const [companies, setCompanies] = useState([]);
  const [members, setMembers] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle(task?.title || '');
    setSeverity(task?.severity || '');
    setDescription(task?.description || '');
    setAssigneeId(task?.assignee_id || '');
    setCompanyId(task?.company_id || '');
    setDueAt((task?.due_at || '').slice(0, 10) || '');
    setStatusChoice('__nochange__');
    setCorrectiveAction('');
  }, [open, task]);

  useEffect(() => {
    if (!open || !projectId) return;
    let cancelled = false;
    // Fail-soft: a memberships failure must never blank the companies picker.
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

  const currentStatus = task?.status || 'open';
  const nextStatuses = isEdit ? allowedNext(currentStatus, myRole) : [];
  const showStatusSelect = isEdit && nextStatuses.length > 0;
  const completing = statusChoice === 'completed';

  const handleSubmit = async () => {
    const t = title.trim();
    if (t.length < 2 || t.length > 200) {
      toast.error('כותרת היא שדה חובה (2-200 תווים)');
      return;
    }
    if (!severity) { toast.error('יש לבחור חומרה'); return; }
    if (completing && !correctiveAction.trim()) {
      toast.error('יש לתאר את הפעולה המתקנת כדי לסמן משימה כהושלמה');
      return;
    }

    const payload = {
      title: t,
      severity,
      description: description.trim() || null,
      assignee_id: assigneeId || null,
      company_id: companyId || null,
      due_at: dueAt || null,
    };
    if (isEdit && statusChoice !== '__nochange__') {
      payload.status = statusChoice;
      if (statusChoice === 'completed') {
        payload.corrective_action = correctiveAction.trim();
      }
    }

    setSubmitting(true);
    try {
      const result = isEdit
        ? await safetyService.updateTask(projectId, task.id, payload)
        : await safetyService.createTask(projectId, payload);
      toast.success(isEdit ? 'משימה עודכנה' : 'משימה נוספה');
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
      title={isEdit ? 'עריכת משימה' : 'משימה חדשה'}
      onSubmit={handleSubmit}
      submitting={submitting}
    >
      <div className="space-y-1.5">
        <Label htmlFor="st-title">כותרת *</Label>
        <Input id="st-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="תיאור קצר של המשימה" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
        <div className="space-y-1.5">
          <Label htmlFor="st-due">תאריך יעד</Label>
          <Input id="st-due" type="date" value={dueAt} onChange={(e) => setDueAt(e.target.value)} />
        </div>
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

      <div className="space-y-1.5">
        <Label>חברה</Label>
        <Select
          value={companyId || '__none__'}
          onValueChange={(v) => setCompanyId(v === '__none__' ? '' : v)}
          dir="rtl"
        >
          <SelectTrigger><SelectValue placeholder="בחר חברה" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">ללא חברה</SelectItem>
            {companies.map((c) => (
              <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="st-desc">תיאור</Label>
        <Textarea id="st-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </div>

      {isEdit && (
        <div className="space-y-1.5">
          <Label>סטטוס</Label>
          <div>
            <Badge className="bg-slate-100 text-slate-700 font-normal">
              {TASK_STATUS_HE[currentStatus] || currentStatus}
            </Badge>
          </div>
          {showStatusSelect && (
            <Select value={statusChoice} onValueChange={setStatusChoice} dir="rtl">
              <SelectTrigger><SelectValue placeholder="עדכון סטטוס" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__nochange__">ללא שינוי</SelectItem>
                {nextStatuses.map((s) => (
                  <SelectItem key={s} value={s}>{TASK_STATUS_HE[s] || s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      )}

      {completing && (
        <div className="space-y-1.5">
          <Label htmlFor="st-corrective">פעולה מתקנת שבוצעה *</Label>
          <Textarea
            id="st-corrective"
            value={correctiveAction}
            onChange={(e) => setCorrectiveAction(e.target.value)}
            rows={3}
            placeholder="תיאור הפעולה המתקנת שבוצעה"
          />
        </div>
      )}
    </SafetyFormModal>
  );
}
