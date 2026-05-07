import {
  CheckCircle2, AlertCircle, Clock, SendHorizontal, PackageCheck,
  XCircle, MinusCircle, ShieldCheck,
} from 'lucide-react';

export const MATRIX_STATUSES = {
  completed: {
    id: 'completed',
    label: 'בוצע',
    Icon: CheckCircle2,
    bg: 'bg-green-100',
    text: 'text-green-700',
    border: 'border-green-200',
  },
  partial: {
    id: 'partial',
    label: 'חלקי',
    Icon: AlertCircle,
    bg: 'bg-amber-100',
    text: 'text-amber-700',
    border: 'border-amber-200',
  },
  ready_for_work: {
    id: 'ready_for_work',
    label: 'מוכן לעבודה',
    Icon: PackageCheck,
    bg: 'bg-cyan-50',
    text: 'text-cyan-700',
    border: 'border-cyan-200',
    // No syncOnly flag → manually selectable in StatusButtonGrid.
    // #503-followup-3 — planning state ("all materials on site,
    // contractor can start"). QC sync wins per D3 if QC starts
    // tracking the same stage.
  },
  in_progress: {
    id: 'in_progress',
    label: 'בעבודה',
    Icon: Clock,
    bg: 'bg-blue-100',
    text: 'text-blue-700',
    border: 'border-blue-200',
  },
  pending_review: {
    id: 'pending_review',
    label: 'ממתין לאישור',
    Icon: SendHorizontal,
    bg: 'bg-orange-100',
    text: 'text-orange-700',
    border: 'border-orange-200',
    syncOnly: true,
  },
  not_done: {
    id: 'not_done',
    label: 'לא בוצע',
    Icon: XCircle,
    bg: 'bg-red-100',
    text: 'text-red-700',
    border: 'border-red-200',
  },
  not_relevant: {
    id: 'not_relevant',
    label: 'לא רלוונטי',
    Icon: MinusCircle,
    bg: 'bg-slate-100',
    text: 'text-slate-500',
    border: 'border-slate-200',
  },
  no_findings: {
    id: 'no_findings',
    label: 'אין חוסרים',
    Icon: ShieldCheck,
    bg: 'bg-emerald-100',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
  },
};

export const MATRIX_STATUS_LIST = Object.values(MATRIX_STATUSES);

export const EMPTY_CELL_CONFIG = {
  id: null,
  label: 'לא סומן',
  bg: 'bg-slate-50',
  text: 'text-slate-300',
  border: 'border-slate-100',
};
