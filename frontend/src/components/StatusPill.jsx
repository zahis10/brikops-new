import React from 'react';

const STATUS_DOT = {
  open:                       'bg-red-500',
  assigned:                   'bg-orange-500',
  in_progress:                'bg-blue-500',
  pending_contractor_proof:   'bg-orange-500',
  pending_manager_approval:   'bg-indigo-500',
  returned_to_contractor:     'bg-rose-500',
  waiting_verify:             'bg-purple-500',
  closed:                     'bg-emerald-500',
  approved:                   'bg-emerald-500',
  reopened:                   'bg-amber-500',
};

const StatusPill = ({ status, label, className = '' }) => {
  const dot = STATUS_DOT[status] || 'bg-slate-400';
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[11px] font-medium whitespace-nowrap ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
};

export default StatusPill;
