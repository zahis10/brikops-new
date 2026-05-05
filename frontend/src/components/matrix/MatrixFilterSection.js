import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronLeft } from 'lucide-react';

/**
 * Phase 2D-1 (#500) — Single collapsible filter section.
 *
 * Re-usable across 5 modes: building / apartment / status / tag / search.
 * NO state except local `expanded`. All filter state lives in
 * useMatrixFilters in the parent.
 *
 * Auto-expands when activeCount > 0 (i.e. when loading a saved view that
 * has values in this section). Otherwise default-collapsed per Zahi:
 * "תוודא שיש חץ לקיפול נושאים... שלא יהיה עמוס מדי".
 */
const MODE_COLORS = {
  building:  { letter: 'B', pillBg: 'bg-teal-100',   pillText: 'text-teal-700' },
  apartment: { letter: 'D', pillBg: 'bg-teal-100',   pillText: 'text-teal-700' },
  tag:       { letter: 'T', pillBg: 'bg-amber-100',  pillText: 'text-amber-800' },
  status:    { letter: 'S', pillBg: 'bg-violet-100', pillText: 'text-violet-700' },
  search:    { letter: '🔍', pillBg: 'bg-slate-100', pillText: 'text-slate-700' },
};

export default function MatrixFilterSection({
  mode,
  title,
  activeCount = 0,
  options = [],
  selectedValues = [],
  onToggle,
  onClear,
  defaultExpanded = false,
  textValue = '',
  onTextChange,
  emptyLabel = 'אין ערכים בעמודה זו',
  placeholder = 'חיפוש...',
}) {
  const [expanded, setExpanded] = useState(defaultExpanded || activeCount > 0);

  // Auto-expand when activeCount transitions from 0 → >0 (saved-view load).
  useEffect(() => {
    if (activeCount > 0) setExpanded(true);
  }, [activeCount]);

  const palette = MODE_COLORS[mode] || MODE_COLORS.tag;
  const isCheckbox = mode === 'building' || mode === 'status' || mode === 'tag';
  const isText = mode === 'apartment' || mode === 'search';

  return (
    <div className="border-b border-slate-100 last:border-b-0">
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 py-2.5 px-2 hover:bg-slate-50 active:bg-slate-100 transition-colors min-h-[44px] text-right"
        aria-expanded={expanded}
      >
        <span
          className={`shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-[11px] font-bold ${palette.pillBg} ${palette.pillText}`}
          aria-hidden="true"
        >
          {palette.letter}
        </span>
        <span className="flex-1 text-sm font-medium text-slate-800 truncate text-right">
          {title}
        </span>
        {activeCount > 0 && (
          <span
            className="shrink-0 inline-flex items-center justify-center text-[10px] font-bold min-w-[20px] h-5 px-1.5 rounded-full bg-violet-600 text-white"
            aria-label={`${activeCount} פילטרים פעילים`}
          >
            {activeCount}
          </span>
        )}
        {activeCount > 0 && onClear && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onClear(); }}
            className="shrink-0 text-[11px] text-slate-500 hover:text-red-600 px-1.5 py-1 rounded hover:bg-red-50 transition-colors"
            aria-label={`נקה ${title}`}
          >
            נקה
          </button>
        )}
        <span className="shrink-0 text-slate-400" aria-hidden="true">
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </span>
      </button>

      {/* Body */}
      {expanded && (
        <div className="pr-9 pl-2 pb-3 pt-1">
          {isText && (
            <input
              type="text"
              value={textValue || ''}
              onChange={(e) => onTextChange?.(e.target.value)}
              placeholder={placeholder}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-300 focus:border-violet-400 outline-none min-h-[40px]"
              dir="rtl"
            />
          )}
          {isCheckbox && options.length === 0 && (
            <div className="text-xs text-slate-400 text-center py-3">
              {emptyLabel}
            </div>
          )}
          {isCheckbox && options.length > 0 && (
            <div className="space-y-0.5">
              {options.map(opt => {
                const checked = selectedValues.includes(opt.value);
                return (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 py-2 px-1.5 rounded hover:bg-slate-50 active:bg-slate-100 cursor-pointer min-h-[40px]"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggle?.(opt.value)}
                      className="w-4 h-4 rounded border-slate-300 text-violet-600 focus:ring-violet-400"
                    />
                    <span className="text-sm text-slate-800 flex-1 truncate text-right">
                      {opt.label}
                    </span>
                    {opt.color && (
                      <span
                        className={`shrink-0 w-2.5 h-2.5 rounded-full ${opt.color}`}
                        aria-hidden="true"
                      />
                    )}
                  </label>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
