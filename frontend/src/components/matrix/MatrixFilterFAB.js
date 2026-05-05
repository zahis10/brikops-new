import React from 'react';
import { Filter } from 'lucide-react';

/**
 * Phase 2D-1 (#500) — Floating Action Button for matrix filters.
 *
 * Position: fixed bottom-right (RTL → left:16px so it sits visually right).
 * Respects safe-area on mobile. Active filter count rendered as red badge.
 * STEP 0.6 audit confirmed no fixed-bottom element on ExecutionMatrixPage.
 */
export default function MatrixFilterFAB({ activeCount = 0, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={activeCount > 0 ? `סינון (${activeCount} פעילים)` : 'סינון'}
      className="fixed z-40 w-14 h-14 rounded-full bg-violet-600 hover:bg-violet-700 active:bg-violet-800 text-white shadow-xl flex items-center justify-center transition-colors"
      style={{
        left: '16px',
        bottom: 'max(16px, calc(env(safe-area-inset-bottom, 0px) + 16px))',
      }}
    >
      <Filter className="w-6 h-6" />
      {activeCount > 0 && (
        <span
          className="absolute -top-1 -left-1 min-w-[22px] h-[22px] px-1.5 rounded-full bg-red-500 text-white text-[11px] font-bold flex items-center justify-center border-2 border-white"
          aria-hidden="true"
        >
          {activeCount > 99 ? '99+' : activeCount}
        </span>
      )}
    </button>
  );
}
