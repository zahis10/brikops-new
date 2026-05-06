import React from 'react';
import { MATRIX_STATUSES, EMPTY_CELL_CONFIG } from './STATUS_CONFIG';

export default function MatrixCell({ cell, stage, size = 'sm', onClick = null }) {
  const isTag = stage?.type === 'tag';
  const status = cell?.status;
  const textValue = cell?.text_value;

  const inner = (() => {
    if (isTag) {
      return (
        <div
          className={`flex items-center justify-center rounded-md border ${
            textValue
              ? 'bg-violet-50 text-violet-700 border-violet-200'
              : `${EMPTY_CELL_CONFIG.bg} ${EMPTY_CELL_CONFIG.text} ${EMPTY_CELL_CONFIG.border}`
          } ${size === 'sm' ? 'h-8 w-8' : 'h-10 w-10'}`}
          title={(textValue || 'ללא תגית') + (cell?.note ? `\n"${cell.note}"` : '')}
          dir="rtl"
        >
          <span className="text-[10px] font-medium truncate px-1">
            {textValue ? textValue.slice(0, 3) : '—'}
          </span>
        </div>
      );
    }

    const cfg = status ? MATRIX_STATUSES[status] : null;
    if (cfg) {
      const Icon = cfg.Icon;
      return (
        <div
          className={`relative flex items-center justify-center rounded-md border ${cfg.bg} ${cfg.text} ${cfg.border} ${
            size === 'sm' ? 'h-8 w-8' : 'h-10 w-10'
          }`}
          title={
            cfg.label
            + (cell?.last_actor_name ? ` • ${cell.last_actor_name}` : '')
            + (cell?.synced_from_qc ? ' • מסונכרן מ-QC' : '')
            + (cell?.note ? `\n"${cell.note}"` : '')
          }
          dir="rtl"
        >
          <Icon className={size === 'sm' ? 'w-4 h-4' : 'w-5 h-5'} />
          {/* #503 — blue dot bottom-left when value came from QC sync. */}
          {cell?.synced_from_qc && (
            <span
              aria-hidden="true"
              className="absolute bottom-0.5 left-0.5 w-1.5 h-1.5 rounded-full bg-blue-500 ring-1 ring-white"
            />
          )}
        </div>
      );
    }

    return (
      <div
        className={`flex items-center justify-center rounded-md border ${EMPTY_CELL_CONFIG.bg} ${EMPTY_CELL_CONFIG.text} ${EMPTY_CELL_CONFIG.border} ${
          size === 'sm' ? 'h-8 w-8' : 'h-10 w-10'
        }`}
        title="לא סומן"
        dir="rtl"
      >
        <span className="text-xs">—</span>
      </div>
    );
  })();

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="cursor-pointer hover:opacity-80 active:scale-95 transition-all"
        aria-label={`ערוך ${stage?.title || ''}`}
      >
        {inner}
      </button>
    );
  }
  return inner;
}
