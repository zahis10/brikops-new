import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';
import { MATRIX_STATUS_LIST } from './STATUS_CONFIG';

export default function StatusLegend({ defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" dir="rtl">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-slate-500" />
          <span className="text-sm font-medium text-slate-700">מקרא סטטוסים</span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
      </button>
      {open && (
        <div className="grid grid-cols-2 gap-2 px-4 pb-3 sm:grid-cols-3">
          {MATRIX_STATUS_LIST.map((s) => {
            const Icon = s.Icon;
            return (
              <div key={s.id} className="flex items-center gap-2">
                <div className={`flex items-center justify-center rounded-md border ${s.bg} ${s.text} ${s.border} h-7 w-7 shrink-0`}>
                  <Icon className="w-4 h-4" />
                </div>
                <span className="text-xs text-slate-700">{s.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
