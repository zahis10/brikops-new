import React from 'react';
import { Loader2 } from 'lucide-react';
import { MATRIX_STATUSES } from './STATUS_CONFIG';

/**
 * Reverse-chronological audit history for a cell.
 *
 * Props:
 *   history: [{ actor_id, actor_name, timestamp, status_before,
 *               status_after, note_before, note_after,
 *               text_before, text_after }]
 *   loading: bool
 */
export default function CellHistoryList({ history, loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-4 text-slate-500" dir="rtl">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-xs">טוען היסטוריה...</span>
      </div>
    );
  }
  if (!history || history.length === 0) {
    return (
      <div className="text-center py-4 text-xs text-slate-400" dir="rtl">
        אין עדיין שינויים
      </div>
    );
  }
  // Reverse-chronological (newest first)
  const sorted = [...history].reverse();
  return (
    <div className="space-y-2 max-h-[200px] overflow-y-auto" dir="rtl">
      {sorted.map((entry, idx) => {
        const before = entry.status_before
          ? MATRIX_STATUSES[entry.status_before]?.label || entry.status_before
          : '—';
        const after = entry.status_after
          ? MATRIX_STATUSES[entry.status_after]?.label || entry.status_after
          : '—';
        const dt = entry.timestamp ? new Date(entry.timestamp) : null;
        const dtStr = dt
          ? dt.toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' })
          : '';
        return (
          <div key={idx} className="border-r-2 border-slate-200 pr-3 py-1">
            <div className="text-xs text-slate-700 font-medium">
              {entry.actor_name || 'משתמש לא ידוע'}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">{dtStr}</div>
            <div className="text-xs text-slate-600 mt-1">
              {before} → <span className="font-medium">{after}</span>
              {entry.note_after && entry.note_after !== entry.note_before && (
                <div className="text-[11px] text-slate-500 mt-0.5">
                  הערה: {entry.note_after}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
