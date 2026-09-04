import React from 'react';

const STATUS_CONFIG = {
  short: {
    label: 'חסר',
    classes: 'bg-red-100 text-red-700 border-red-200',
  },
  borderline: {
    label: 'גבולי',
    classes: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  ok: {
    label: 'מספיק',
    classes: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  },
  not_entered: {
    label: 'לא הוזן',
    classes: 'bg-slate-100 text-slate-600 border-slate-200',
  },
  no_target: {
    label: 'ללא יעד',
    classes: 'bg-slate-100 text-slate-500 border-slate-200',
  },
  no_profile: {
    label: 'אחר',
    classes: 'bg-slate-50 text-slate-400 border-slate-200',
  },
};

const measureLabel = (measure) => {
  if (measure === 'tiles') return 'אריחים';
  if (measure === 'sqm') return 'מ"ר';
  return '';
};

export default function SparePill({
  summary,
  size = 'sm',
  onClick = null,
  label = '',
}) {
  const config = summary ? STATUS_CONFIG[summary.overall] || STATUS_CONFIG.no_profile : null;
  const shortRows = Array.isArray(summary?.short) ? summary.short : [];
  const notEntered = Array.isArray(summary?.not_entered) ? summary.not_entered : [];
  const borderline = Array.isArray(summary?.borderline) ? summary.borderline : [];
  const baseText = config
    ? `${config.label}${summary?.overall === 'short' && shortRows.length > 1 ? ` (${shortRows.length})` : ''}`
    : '—';
  const text = `${baseText}${['short', 'not_entered'].includes(summary?.overall) && borderline.length ? ' · גבולי' : ''}`;
  const titleParts = [
    summary?.profile ? `פרופיל: ${summary.profile}` : 'ללא פרופיל',
    ...shortRows.map(row => {
      const measure = measureLabel(row.measure);
      return `${row.name}: חסר ${row.missing}${measure ? ` ${measure}` : ''}`;
    }),
  ];
  if (borderline.length) titleParts.push(`גבולי: ${borderline.join(', ')}`);
  if (notEntered.length) titleParts.push(`לא הוזן: ${notEntered.join(', ')}`);

  const inner = (
    <span
      className={`inline-flex items-center justify-center rounded-md border px-2 font-medium whitespace-nowrap ${
        size === 'sm' ? 'h-8 text-[11px]' : 'h-10 text-xs'
      } ${config ? config.classes : 'bg-slate-50 text-slate-400 border-slate-200'}`}
      title={titleParts.join('\n')}
      dir="rtl"
    >
      {text}
    </span>
  );

  if (!onClick) return inner;
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      className="cursor-pointer hover:opacity-80 active:scale-95 transition-all"
      aria-label={`ריצוף ספייר — דירה ${label}`}
    >
      {inner}
    </button>
  );
}