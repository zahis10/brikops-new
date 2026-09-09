import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { escalationService, projectService } from '../../services/api';
import { contextLine } from '../../utils/escalationDraft';
import { formatRelativeHe } from '../../utils/relativeTime';
import { subRoleLabel } from '../../utils/roleLabels';

export default function EscalationsSection({ projectId, escalations, canAssign, currentUserId, onChanged }) {
  const navigate = useNavigate();
  const [doneId, setDoneId] = useState(null);
  const [note, setNote] = useState('');
  const [assignId, setAssignId] = useState(null);
  const [members, setMembers] = useState([]);
  const [resolved, setResolved] = useState(null);

  useEffect(() => {
    if (canAssign) projectService.getMemberships(projectId)
      .then(data => setMembers((data.items || data || []).filter(m => ['project_manager', 'management_team'].includes(m.role))))
      .catch(() => {});
  }, [canAssign, projectId]);

  const patch = async (esc, body, success) => {
    try {
      await escalationService.patch(esc.id, body);
      toast.success(success);
      onChanged();
      setDoneId(null);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בעדכון ההקפצה');
    }
  };

  const items = escalations?.items || [];
  const touch = 'min-h-[44px]';

  return <div className="space-y-2 pt-1">
    {items.map(esc => {
      const mayResolve = canAssign || esc.assigned_to?.id === currentUserId;
      const selectedAssignee = assignId?.id === esc.id ? assignId.value : '';
      return <article key={esc.id} className={`rounded-lg border bg-slate-50 p-3 ${esc.urgency === 'urgent' ? 'border-r-[3px] border-r-red-400 border-red-100' : 'border-slate-200'}`}>
        <div className="flex items-center gap-2 text-[11px]">
          <span className={`rounded-full px-2 py-0.5 font-bold ${esc.urgency === 'urgent' ? 'bg-red-100 text-red-700' : 'bg-slate-200 text-slate-600'}`}>{esc.urgency === 'urgent' ? 'דחוף' : 'רגיל'}</span>
          <span className="text-slate-400">{formatRelativeHe(esc.created_at)}</span>
        </div>
        <p className="mt-1.5 text-sm font-bold text-slate-800">{esc.text}</p>
        <p className="mt-1 text-xs text-slate-500">{esc.labels?.building} · דירה {esc.labels?.unit} · {contextLine(esc.context)}</p>
        <p className="mt-1 text-xs text-slate-500">{esc.requested_by?.name}{subRoleLabel(esc.requested_by?.sub_role) ? ` · ${subRoleLabel(esc.requested_by.sub_role)}` : ''}{esc.assigned_to ? ` · אצל ${esc.assigned_to.name}` : ''}</p>
        {esc.notes?.length > 0 && <div className="mt-2 border-t border-slate-200 pt-2">
          <p className="text-[11px] font-bold text-slate-600">הערות ({esc.notes.length})</p>
          {esc.notes.map((entry, index) => <p key={`${entry.at || index}-${index}`} className="mt-1 text-xs text-slate-600"><span className="font-semibold">{entry.by?.name}:</span> {entry.text}</p>)}
        </div>}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {mayResolve && <button onClick={() => setDoneId(esc.id)} className={`${touch} rounded-md bg-emerald-600 px-2.5 py-1.5 text-xs font-bold text-white`}>✓ טופל</button>}
          {mayResolve && <button onClick={() => window.confirm('לסמן את ההקפצה כלא רלוונטית?') && patch(esc, { action: 'dismiss' }, 'סומן כלא רלוונטי')} className={`${touch} rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-bold text-slate-700`}>לא רלוונטי</button>}
          {canAssign && <select aria-label="העבר ל" value={selectedAssignee} onChange={e => setAssignId({ id: esc.id, value: e.target.value })} className={`${touch} rounded-md border border-slate-300 px-2 py-1 text-xs`}>
            <option value="">העבר ל…</option>
            {members.filter(m => m.user_id !== esc.assigned_to?.id).map(m => <option key={m.user_id} value={m.user_id}>{m.user_name}{subRoleLabel(m.sub_role) ? ` · ${subRoleLabel(m.sub_role)}` : ''}</option>)}
          </select>}
          {canAssign && selectedAssignee && <button onClick={() => patch(esc, { action: 'assign', assignee_id: selectedAssignee }, `הועבר ל${members.find(m => m.user_id === selectedAssignee)?.user_name || ''}`)} className={`${touch} rounded-md bg-amber-500 px-2 py-1 text-xs font-bold text-white`}>העבר</button>}
          <button onClick={() => navigate(`/projects/${projectId}/units/${esc.unit_id}/defects`, { state: { returnTo: `/projects/${projectId}/dashboard` } })} className={`${touch} px-1 text-xs font-bold text-amber-700`}>פתח דירה ›</button>
        </div>
        {doneId === esc.id && <div className="mt-2 flex gap-2">
          <input aria-label="הערה קצרה (רשות)" maxLength={300} value={note} onChange={e => setNote(e.target.value)} placeholder="הערה קצרה (רשות)" className={`${touch} min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1 text-xs`} />
          <button onClick={() => patch(esc, { action: 'done', note }, 'סומן כטופל')} className={`${touch} rounded-md bg-emerald-600 px-3 text-xs font-bold text-white`}>אשר</button>
        </div>}
      </article>;
    })}
    {!items.length && <p className="py-4 text-center text-xs text-slate-400">אין הקפצות פתוחות</p>}
    {escalations?.resolved_week_count > 0 && <div className="border-t border-slate-200 pt-3">
      <button onClick={() => resolved ? setResolved(null) : escalationService.list(projectId, 'resolved').then(setResolved).catch(() => toast.error('שגיאה בטעינת היסטוריה'))} className={`${touch} text-xs font-bold text-amber-700`}>טופלו השבוע: {escalations.resolved_week_count} · הצג</button>
      {resolved?.items?.map(esc => <div key={esc.id} className="mt-2 rounded-lg border border-slate-200 p-2 text-xs text-slate-500 opacity-60">{esc.labels?.building} · דירה {esc.labels?.unit} · {esc.status === 'done' ? 'טופל' : 'לא רלוונטי'} ע״י {esc.resolved_by?.name} · {esc.resolved_at ? new Date(esc.resolved_at).toLocaleDateString('he-IL') : ''}{esc.resolution_note ? ` · "${esc.resolution_note}"` : ''}</div>)}
    </div>}
  </div>;
}