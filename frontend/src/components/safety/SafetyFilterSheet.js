import React, { useEffect, useState } from 'react';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '../ui/sheet';

const CATEGORY_OPTIONS = [
  { value: 'scaffolding',         label: 'פיגומים' },
  { value: 'heights',             label: 'עבודה בגובה' },
  { value: 'electrical_safety',   label: 'בטיחות חשמל' },
  { value: 'lifting',             label: 'הרמה וציוד' },
  { value: 'excavation',          label: 'חפירות' },
  { value: 'fire_safety',         label: 'אש ובטיחות אש' },
  { value: 'ppe',                 label: 'ציוד מגן אישי' },
  { value: 'site_housekeeping',   label: 'סדר וניקיון' },
  { value: 'hazardous_materials', label: 'חומרים מסוכנים' },
  { value: 'other',               label: 'אחר' },
];

const SEVERITY_OPTIONS = [
  { value: '3', label: 'גבוהה' },
  { value: '2', label: 'בינונית' },
  { value: '1', label: 'נמוכה' },
];

const DOC_STATUS_OPTIONS = [
  { value: 'open',        label: 'פתוח' },
  { value: 'in_progress', label: 'בביצוע' },
  { value: 'resolved',    label: 'נפתר' },
  { value: 'verified',    label: 'אומת' },
];

export const EMPTY_FILTER = {
  category: null,
  severity: null,
  status: null,
  company_id: null,
  assignee_id: null,
  reporter_id: null,
  date_from: null,
  date_to: null,
};

export function countActiveFilters(filter) {
  if (!filter) return 0;
  return Object.values(filter).filter((v) => v != null && v !== '').length;
}

const fieldLabel = 'block text-xs font-medium text-slate-700 mb-1';
const fieldInput =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 ' +
  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[44px]';

export default function SafetyFilterSheet({
  open,
  onOpenChange,
  value,
  onApply,
  onClear,
  companies,
  users,
}) {
  const [local, setLocal] = useState(value || EMPTY_FILTER);

  useEffect(() => {
    if (open) setLocal(value || EMPTY_FILTER);
  }, [open, value]);

  const set = (k, v) => setLocal((s) => ({ ...s, [k]: v === '' ? null : v }));

  const handleApply = () => {
    onApply && onApply(local);
  };

  const handleClear = () => {
    setLocal(EMPTY_FILTER);
    onClear && onClear();
  };

  const renderSelect = (k, options, placeholderLabel) => (
    <select
      className={fieldInput}
      value={local[k] ?? ''}
      onChange={(e) => set(k, e.target.value)}
    >
      <option value="">{placeholderLabel}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );

  const renderEntitySelect = (k, list, placeholderLabel, loadingLabel) => {
    if (!list || list.length === 0) {
      return (
        <select className={fieldInput} disabled value="">
          <option value="">{loadingLabel}</option>
        </select>
      );
    }
    return (
      <select
        className={fieldInput}
        value={local[k] ?? ''}
        onChange={(e) => set(k, e.target.value)}
      >
        <option value="">{placeholderLabel}</option>
        {list.map((it) => (
          <option key={it.id} value={it.id}>{it.name}</option>
        ))}
      </select>
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        dir="rtl"
        className="w-full sm:max-w-md flex flex-col gap-0 p-0"
      >
        <SheetHeader className="px-5 pt-5 pb-3 border-b border-slate-100 text-right">
          <SheetTitle className="text-right">סינון ליקויים</SheetTitle>
          <SheetDescription className="text-right">
            בחר ערכים והקש על "החל". ניתן לאפס בכל עת.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          <div>
            <label className={fieldLabel}>קטגוריה</label>
            {renderSelect('category', CATEGORY_OPTIONS, 'הכל')}
          </div>
          <div>
            <label className={fieldLabel}>חומרה</label>
            {renderSelect('severity', SEVERITY_OPTIONS, 'הכל')}
          </div>
          <div>
            <label className={fieldLabel}>סטטוס</label>
            {renderSelect('status', DOC_STATUS_OPTIONS, 'הכל')}
          </div>
          <div>
            <label className={fieldLabel}>חברה</label>
            {renderEntitySelect('company_id', companies, 'הכל', 'טוען...')}
          </div>
          <div>
            <label className={fieldLabel}>אחראי</label>
            {renderEntitySelect('assignee_id', users, 'הכל', 'טוען...')}
          </div>
          <div>
            <label className={fieldLabel}>מדווח</label>
            {renderEntitySelect('reporter_id', users, 'הכל', 'טוען...')}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={fieldLabel}>מתאריך</label>
              <input
                type="date"
                className={fieldInput}
                value={local.date_from ?? ''}
                onChange={(e) => set('date_from', e.target.value)}
              />
            </div>
            <div>
              <label className={fieldLabel}>עד תאריך</label>
              <input
                type="date"
                className={fieldInput}
                value={local.date_to ?? ''}
                onChange={(e) => set('date_to', e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-slate-100 flex items-center gap-3 bg-white">
          <button
            type="button"
            onClick={handleApply}
            className="flex-1 min-h-[44px] px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
          >
            החל
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="flex-1 min-h-[44px] px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
          >
            נקה
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
