import React, { useState, useEffect } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from './ui/sheet';
import { SlidersHorizontal } from 'lucide-react';

const FilterSection = ({ label, value, onChange, options }) => (
  <div className="space-y-2">
    <h4 className="text-sm font-semibold text-slate-700">{label}</h4>
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onChange('all')}
        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
          value === 'all'
            ? 'bg-amber-500 text-white shadow-sm'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
        }`}
      >
        הכל
      </button>
      {options.map(opt => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors max-w-[200px] truncate ${
            value === opt.value
              ? 'bg-amber-500 text-white shadow-sm'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  </div>
);

const FilterDrawer = ({ open, onOpenChange, filters, defaultFilters, onApply, sections }) => {
  const [draft, setDraft] = useState({ ...filters });
  const [wasOpen, setWasOpen] = useState(false);

  useEffect(() => {
    if (open && !wasOpen) {
      setDraft({ ...filters });
    }
    setWasOpen(open);
  }, [open, filters, wasOpen]);

  const updateDraft = (key, value) => {
    setDraft(prev => ({ ...prev, [key]: value }));
  };

  const handleApply = () => {
    onApply(draft);
    onOpenChange(false);
  };

  const handleReset = () => {
    setDraft({ ...defaultFilters });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[320px] sm:w-[360px] flex flex-col p-0" dir="rtl">
        <SheetHeader className="px-5 pt-5 pb-3 border-b border-slate-200">
          <SheetTitle className="text-right text-base font-bold text-slate-800">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4" />
              סינון
            </div>
          </SheetTitle>
          <SheetDescription className="sr-only">בחר סינון לליקויים</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {sections.map(section => (
            section.options.length > 0 && (
              <FilterSection
                key={section.key}
                label={section.label}
                value={draft[section.key]}
                onChange={v => updateDraft(section.key, v)}
                options={section.options}
              />
            )
          ))}
        </div>

        <div className="border-t border-slate-200 px-5 py-3 flex gap-3">
          <button
            type="button"
            onClick={handleReset}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
          >
            אפס
          </button>
          <button
            type="button"
            onClick={handleApply}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-bold bg-amber-500 hover:bg-amber-600 text-white shadow-sm transition-colors"
          >
            סיים
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default FilterDrawer;
