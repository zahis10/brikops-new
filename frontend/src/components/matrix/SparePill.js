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
  recorded: {
    label: 'הוזן',
    classes: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  },
  not_entered: {
    label: 'לא הוזן',
    classes: 'bg-slate-100 text-slate-600 border-slate-200',
  },
  no_target: {
    label: 'לא הוזן',
    classes: 'bg-slate-100 text-slate-500 border-slate-200',
  },
  no_profile: {
    label: 'אחר',
    classes: 'bg-slate-50 text-slate-400 border-slate-200',
  },
};

export function spareSummaryText(summary) {
  const s = summary || {};
  const overall = s.overall ?? 'no_profile';
  const nShort = s.short?.length ?? 0;
  const nBorder = s.borderline?.length ?? 0;
  const x = s.entered_count ?? 0;
  const y = s.applicable_count ?? 0;
  const progress = y > 0 && x < y
    ? (x === 0 ? 'לא הוזן' : `הוזן ${x}/${y}`)
    : null;
  if (overall === 'no_profile') return x > 0 ? `אחר · הוזן ${x}/${y}` : 'אחר';
  const parts = [
    ...(nShort > 0 ? [`חסר ${nShort}`] : []),
    ...(nBorder > 0 ? [`גבולי ${nBorder}`] : []),
    ...(progress ? [progress] : []),
  ];
  if (parts.length) return parts.join(' · ');
  if (overall === 'ok') return 'מספיק';
  if (overall === 'recorded') return y > 0 ? `הוזן ${y}/${y}` : 'הוזן';
  return STATUS_CONFIG[overall]?.label ?? '—';
}

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
  const borderline = Array.isArray(summary?.borderline) ? summary.borderline : [];
  const unfilled = Array.isArray(summary?.unfilled) ? summary.unfilled : [];
  const text = summary ? spareSummaryText(summary) : '—';
  const titleParts = [
    summary?.profile ? `פרופיל: ${summary.profile}` : 'ללא פרופיל',
    ...shortRows.map(row => {
      const measure = measureLabel(row.measure);
      return row.missing == null
        ? `${row.name}: אין ספייר`
        : `${row.name}: חסר ${row.missing}${measure ? ` ${measure}` : ''}`;
    }),
  ];
  if (borderline.length) titleParts.push(`גבולי: ${borderline.join(', ')}`);
  if (unfilled.length) titleParts.push(`לא הוזן: ${unfilled.join(', ')}`);

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