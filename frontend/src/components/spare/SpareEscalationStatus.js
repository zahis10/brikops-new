import React from 'react';
import { Bell } from 'lucide-react';
import { canEscalate } from '../../utils/escalationDraft';
import { formatRelativeHe } from '../../utils/relativeTime';

export default function SpareEscalationStatus({ unitData, onOpenSheet }) {
  const esc = unitData.spare_escalation;
  const canSend = unitData.spare_can_escalate && canEscalate(unitData.spare_status);
  if (esc?.status === 'open') return <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800"><span>נשלחה הקפצה{esc.urgency === 'urgent' ? ' דחופה' : ''} {formatRelativeHe(esc.created_at)} · ממתינה אצל {esc.assigned_to?.name || 'מנהל הפרויקט'}</span>{(unitData.spare_can_escalate || unitData.spare_can_assign) && <button onClick={() => onOpenSheet('note')} className="mr-2 min-h-[44px] font-bold underline">הוסף הערה</button>}</div>;
  return <div className="mb-3 flex flex-wrap items-center gap-2">{esc && <p className="text-xs text-slate-500">{esc.status === 'done' ? 'טופל' : 'סומן כלא רלוונטי'} ע״י {esc.resolved_by?.name} · {esc.resolved_at ? new Date(esc.resolved_at).toLocaleDateString('he-IL') : ''}{esc.resolution_note ? ` · "${esc.resolution_note}"` : ''}</p>}{canSend && <button onClick={() => onOpenSheet('new')} className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-amber-300 px-2.5 py-1.5 text-xs font-bold text-amber-700 hover:bg-amber-50"><Bell className="h-3.5 w-3.5" />הקפץ למנהל הפרויקט</button>}</div>;
}