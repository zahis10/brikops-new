import React, { useMemo } from 'react';
import { SelectField } from './BottomSheetSelect';

// SelectField (BottomSheetSelect.js) reads `opt.value` and `opt.label` only.
// `opt.label` is rendered directly inside JSX, so React nodes are accepted.
// SelectField has NO per-option `disabled` support, so header rows are made
// inert by intercepting onChange in this wrapper and ignoring header values.
//
// Input option shape:
//   - Normal:  { value, label }
//   - Header:  { value: '__header_X', label: 'תחום: מיזוג', isHeader: true, muted?: true }
//   - Muted:   { value, label, muted: true }

const GroupedSelectField = ({ options = [], onChange, value, ...rest }) => {
  const { transformed, headerValues } = useMemo(() => {
    const headers = new Set();
    const out = options.map(opt => {
      if (opt?.isHeader) {
        headers.add(opt.value);
        const isMuted = !!opt.muted;
        const wrapperCls = isMuted
          ? 'block w-full px-3 py-1.5 text-sm font-bold text-slate-500 bg-slate-50 border-t border-slate-200 pointer-events-none'
          : 'block w-full px-3 py-1.5 text-sm font-bold text-slate-700 bg-slate-100 pointer-events-none';
        return {
          value: opt.value,
          label: (
            <span className={wrapperCls}>
              {opt.label}
            </span>
          ),
        };
      }
      if (opt?.muted) {
        return {
          value: opt.value,
          label: <span className="opacity-70">{opt.label}</span>,
        };
      }
      return { value: opt.value, label: opt.label };
    });
    return { transformed: out, headerValues: headers };
  }, [options]);

  const handleChange = (val) => {
    if (headerValues.has(val)) return;
    if (typeof onChange === 'function') onChange(val);
  };

  return (
    <SelectField
      {...rest}
      value={value}
      options={transformed}
      onChange={handleChange}
    />
  );
};

export default GroupedSelectField;
