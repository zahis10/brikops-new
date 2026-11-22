import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { OptionsOverlay } from './BottomSheetSelect';

// A form field that opens the app's bottom-sheet list of options (the list the "new defect" form uses)
// instead of a native <select>. options: [{ value, label }]. While the value is empty the placeholder is shown.
export default function SheetPicker({ title, value, options, onChange, placeholder = '', invalid = false }) {
  const [open, setOpen] = useState(false);
  const selected = value ? options.find(o => o.value === value) : null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-label={selected ? `${title}: ${selected.label}` : title}
        className={`w-full min-h-[44px] px-3 flex items-center gap-2 bg-white border rounded-xl text-sm text-right focus:outline-none focus:ring-1 focus:ring-amber-300 ${invalid ? 'border-red-300' : 'border-slate-200'}`}
      >
        <span className={`flex-1 min-w-0 truncate ${selected ? 'text-slate-800' : 'text-slate-500'}`}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDown className="w-4 h-4 flex-shrink-0 text-slate-400" />
      </button>
      <OptionsOverlay
        open={open}
        options={options}
        value={value}
        onChange={onChange}
        onClose={() => setOpen(false)}
        label={title}
      />
    </>
  );
}
