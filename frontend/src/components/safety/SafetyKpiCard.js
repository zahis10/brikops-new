import React from 'react';

/**
 * KPI tile for safety home.
 * @param {Component} icon        lucide-react icon component
 * @param {string} label          Hebrew label
 * @param {number|string} value   big number or text
 * @param {string} sub            small sub-line (e.g., "מתוך 12")
 * @param {string} tone           'neutral' | 'info' | 'warning' | 'danger' | 'success'
 * @param {function} onClick      optional — click to switch tab or open drawer
 */
export default function SafetyKpiCard({ icon: Icon, label, value, sub, tone = 'neutral', onClick }) {
  const toneMap = {
    neutral: { bg: 'bg-white',      border: 'border-slate-200',   iconBg: 'bg-slate-100',    iconFg: 'text-slate-600',  num: 'text-slate-900' },
    info:    { bg: 'bg-blue-50',    border: 'border-blue-200',    iconBg: 'bg-blue-100',     iconFg: 'text-blue-700',   num: 'text-blue-900' },
    warning: { bg: 'bg-amber-50',   border: 'border-amber-200',   iconBg: 'bg-amber-100',    iconFg: 'text-amber-700',  num: 'text-amber-900' },
    danger:  { bg: 'bg-red-50',     border: 'border-red-200',     iconBg: 'bg-red-100',      iconFg: 'text-red-700',    num: 'text-red-900' },
    success: { bg: 'bg-emerald-50', border: 'border-emerald-200', iconBg: 'bg-emerald-100',  iconFg: 'text-emerald-700', num: 'text-emerald-900' },
  };
  const t = toneMap[tone] || toneMap.neutral;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-right ${t.bg} ${t.border} border rounded-xl p-4 shadow-sm transition-all hover:shadow-md active:scale-[0.98] disabled:opacity-60 min-h-[96px] w-full`}
      disabled={!onClick}
    >
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${t.iconBg}`}>
          {Icon && <Icon className={`w-5 h-5 ${t.iconFg}`} />}
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-2xl font-black ${t.num} leading-none`}>{value ?? '—'}</p>
          <p className="text-xs text-slate-600 mt-1 font-medium truncate">{label}</p>
          {sub && <p className="text-[11px] text-slate-500 mt-0.5 truncate">{sub}</p>}
        </div>
      </div>
    </button>
  );
}
