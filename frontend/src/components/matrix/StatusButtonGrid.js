import React from 'react';
import { MATRIX_STATUS_LIST } from './STATUS_CONFIG';

/**
 * 2×3 grid of status buttons. Tap to select.
 * Selected state: full opacity + 2px border.
 * Disabled state: 50% opacity + cursor-not-allowed.
 *
 * Props:
 *   value: current status id (string or null)
 *   onChange: (statusId) => void
 *   disabled: bool (read-only mode)
 */
export default function StatusButtonGrid({ value, onChange, disabled = false }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2" dir="rtl">
      {MATRIX_STATUS_LIST.map((s) => {
        const Icon = s.Icon;
        const isSelected = value === s.id;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => !disabled && onChange(s.id)}
            disabled={disabled}
            className={`
              flex flex-col items-center justify-center gap-1
              px-3 py-3 min-h-[56px] rounded-lg transition-all
              ${isSelected
                ? `${s.bg} ${s.text} border-2 ${s.border} font-bold`
                : 'bg-white border border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50'
              }
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
          >
            <Icon className={`w-5 h-5 ${isSelected ? s.text : 'text-slate-400'}`} />
            <span className="text-xs">{s.label}</span>
          </button>
        );
      })}
    </div>
  );
}
