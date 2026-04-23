import React from 'react';
import { Trash2, X, Loader2 } from 'lucide-react';

export default function SafetyBulkActionBar({ count, onDelete, onClear, deleting }) {
  return (
    <div
      dir="rtl"
      className="fixed bottom-0 inset-x-0 z-30 bg-white border-t border-slate-200 shadow-lg"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onClear}
          disabled={deleting}
          className="min-h-[44px] px-3 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 flex items-center gap-1 disabled:opacity-60"
        >
          <X className="w-4 h-4" />
          נקה
        </button>

        <div className="flex-1 text-center text-sm font-medium text-slate-900">
          בחירה: {count}
        </div>

        <button
          type="button"
          onClick={onDelete}
          disabled={deleting}
          className="min-h-[44px] px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 flex items-center gap-1 disabled:opacity-60"
        >
          {deleting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
          מחק
        </button>
      </div>
    </div>
  );
}
