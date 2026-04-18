import React, { useState, useEffect } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from './ui/sheet';
import { SlidersHorizontal, ChevronDown, ChevronUp, Check, X } from 'lucide-react';

const FilterSection = ({ label, values, onToggle, options, isOpen, onToggleOpen }) => (
  <div>
    <button
      type="button"
      onClick={onToggleOpen}
      className="w-full flex items-center justify-between py-1"
    >
      <h4 className="text-sm font-semibold text-slate-700">{label}</h4>
      {isOpen
        ? <ChevronUp className="w-4 h-4 text-slate-400" />
        : <ChevronDown className="w-4 h-4 text-slate-400" />
      }
    </button>
    {isOpen && (
      <div className="flex flex-wrap gap-2 mt-2">
        {options.map(opt => {
          const selected = values.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onToggle(opt.value)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors max-w-[200px] ${
                selected
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {selected && <Check className="w-3.5 h-3.5 shrink-0" />}
              <span className="truncate">{opt.label}</span>
              {typeof opt.count === 'number' && (
                <span className={`shrink-0 text-[11px] tabular-nums ${selected ? 'text-white/80' : 'text-slate-400'}`}>
                  {opt.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    )}
  </div>
);

const FilterDrawer = ({
  open,
  onOpenChange,
  filters,
  defaultFilters,
  onApply,
  sections,
  computeMatchCount,
  matchLabel = 'ליקויים',
  presets,
  getActivePresetId,
}) => {
  const [draft, setDraft] = useState({ ...filters });
  const [wasOpen, setWasOpen] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState({});

  useEffect(() => {
    if (open && !wasOpen) {
      setDraft({ ...filters });
      setCollapsedSections({});
    }
    setWasOpen(open);
  }, [open, filters, wasOpen]);

  const toggleSection = (key) => {
    setCollapsedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleValue = (key, value) => {
    setDraft(prev => {
      const current = Array.isArray(prev[key]) ? prev[key] : [];
      const next = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value];
      return { ...prev, [key]: next };
    });
  };

  const handleApply = () => {
    onApply(draft);
    onOpenChange(false);
  };

  const handleReset = () => {
    setDraft({ ...defaultFilters });
  };

  const matchCount = typeof computeMatchCount === 'function'
    ? computeMatchCount(draft)
    : null;

  const activePresetId = typeof getActivePresetId === 'function'
    ? getActivePresetId(draft)
    : null;

  const applyPreset = (preset) => {
    if (activePresetId === preset.id) {
      setDraft(prev => {
        const next = { ...prev };
        Object.keys(preset.values).forEach(key => {
          next[key] = defaultFilters[key];
        });
        return next;
      });
    } else {
      setDraft(prev => ({ ...prev, ...preset.values }));
    }
  };

  const selectedChips = [];
  sections.forEach(section => {
    const vals = Array.isArray(draft[section.key]) ? draft[section.key] : [];
    vals.forEach(v => {
      const opt = section.options.find(o => o.value === v);
      selectedChips.push({
        sectionKey: section.key,
        value: v,
        label: opt?.label || v,
      });
    });
  });

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
          {Array.isArray(presets) && presets.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-500 mb-2">תבניות מהירות</h4>
              <div className="flex flex-wrap gap-2">
                {presets.map(preset => {
                  const active = activePresetId === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => applyPreset(preset)}
                      className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                        active
                          ? 'bg-amber-500 text-white shadow-sm'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {selectedChips.length > 0 && (
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-slate-500 shrink-0">נבחרו:</span>
                {selectedChips.map(chip => (
                  <button
                    key={`${chip.sectionKey}:${chip.value}`}
                    type="button"
                    onClick={() => toggleValue(chip.sectionKey, chip.value)}
                    aria-label={`הסר ${chip.label}`}
                    title={chip.label}
                    className="inline-flex items-center gap-1 max-w-[140px] px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 active:bg-amber-200 transition-colors"
                  >
                    <span className="truncate">{chip.label}</span>
                    <X className="w-3 h-3 shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {sections.map(section => (
            section.options.length > 0 && (
              <FilterSection
                key={section.key}
                label={section.label}
                values={Array.isArray(draft[section.key]) ? draft[section.key] : []}
                onToggle={v => toggleValue(section.key, v)}
                options={section.options}
                isOpen={!collapsedSections[section.key]}
                onToggleOpen={() => toggleSection(section.key)}
              />
            )
          ))}
        </div>

        <div className="border-t border-slate-200 px-5 py-3 flex gap-3">
          <button
            type="button"
            onClick={handleReset}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 active:bg-slate-100 transition-colors"
          >
            אפס
          </button>
          <button
            type="button"
            onClick={handleApply}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-bold bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white shadow-sm transition-colors"
          >
            {matchCount === null ? 'סיים' : `הצג ${matchCount} ${matchLabel}`}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default FilterDrawer;
