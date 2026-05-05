import React, { useMemo, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Bookmark, Plus } from 'lucide-react';
import { MATRIX_STATUS_LIST } from './STATUS_CONFIG';
import MatrixFilterSection from './MatrixFilterSection';
import SavedViewSaveDialog from './SavedViewSaveDialog';

const EMPTY_SENTINEL = '__empty__';
const EMPTY_LABEL = '(ריק)';

/**
 * Phase 2D-1 (#500) — Right-anchored filter drawer (Radix Dialog).
 *
 * Layout: Header → Saved Views → Search → 📍 מיקום → 📝 מידע כללי
 *         (only if any tag stages) → 🔨 שלבי בקרת ביצוע (only if any
 *         status stages) → Footer.
 *
 * Filter state lives in the parent's useMatrixFilters hook — this
 * component is fully controlled. Sections start COLLAPSED per Zahi
 * 2026-05-05; auto-expand when their activeCount > 0 (saved-view load).
 *
 * Includes minimal saved-view delete-pill (× button) per ADDENDUM #1.
 */
export default function MatrixFilterDrawer({
  open,
  onClose,
  filters,
  filteredCount,
  activeCount,
  toggleBuilding,
  toggleStageStatus,
  toggleTagValue,
  setApartmentSearch,
  setSearchText,
  reset,
  loadSavedView,
  distinctTagValues,
  buildings = [],
  stages = [],
  savedViews = [],
  onSaveCurrentView,
  onDeleteSavedView,
}) {
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);

  const tagStages = useMemo(
    () => (stages || []).filter(s => s.type === 'tag'),
    [stages]
  );
  const statusStages = useMemo(
    () => (stages || []).filter(s => s.type === 'status'),
    [stages]
  );

  const buildingOptions = useMemo(
    () => (buildings || []).map(b => ({ value: b.id, label: b.name || b.id })),
    [buildings]
  );

  const statusOptionsBase = useMemo(
    () => MATRIX_STATUS_LIST.map(s => ({ value: s.id, label: s.label })),
    []
  );
  const statusOptions = useMemo(
    () => [...statusOptionsBase, { value: EMPTY_SENTINEL, label: EMPTY_LABEL }],
    [statusOptionsBase]
  );

  const tagOptionsFor = (stageId) => {
    const values = distinctTagValues(stageId);
    return values.map(v =>
      v === EMPTY_SENTINEL ? { value: EMPTY_SENTINEL, label: EMPTY_LABEL } : { value: v, label: v }
    );
  };

  const clearStageStatus = (stageId) => {
    const cur = filters.stage_status_filters?.[stageId] || [];
    cur.forEach(v => toggleStageStatus(stageId, v));
  };
  const clearTagValue = (stageId) => {
    const cur = filters.tag_value_filters?.[stageId] || [];
    cur.forEach(v => toggleTagValue(stageId, v));
  };
  const clearBuildings = () => {
    [...(filters.building_ids || [])].forEach(b => toggleBuilding(b));
  };

  const total = activeCount?.total || 0;
  const applyLabel = total > 0 ? `החל (${total})` : 'סגור';

  return (
    <>
      <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content
            className="fixed z-50 top-0 bottom-0 right-0 bg-white shadow-2xl outline-none flex flex-col w-[90vw] sm:w-[380px] border-l border-slate-200"
            dir="rtl"
          >
            {/* Header */}
            <div className="flex items-center justify-between gap-2 px-4 pt-3 pb-3 border-b border-slate-200 shrink-0">
              <div className="flex items-center gap-2">
                <Dialog.Title className="text-base font-bold text-slate-900">
                  סינון
                </Dialog.Title>
                {total > 0 && (
                  <span className="inline-flex items-center justify-center text-[11px] font-bold min-w-[22px] h-5 px-1.5 rounded-full bg-violet-600 text-white">
                    {total}
                  </span>
                )}
                {typeof filteredCount === 'number' && (
                  <span className="text-xs text-slate-500">
                    · {filteredCount} דירות
                  </span>
                )}
              </div>
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="p-1.5 -m-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                  aria-label="סגור"
                >
                  <X className="w-5 h-5 text-slate-500" />
                </button>
              </Dialog.Close>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto">
              {/* Saved views row */}
              <div className="px-3 pt-3 pb-2 border-b border-slate-100">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Bookmark className="w-3.5 h-3.5 text-slate-500" />
                  <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wide">
                    תצוגות שמורות
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(savedViews || []).map(view => (
                    <span
                      key={view.id}
                      className="inline-flex items-center gap-1 pr-2 pl-1 py-1 text-xs rounded-full bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100 transition-colors"
                    >
                      <button
                        type="button"
                        onClick={() => loadSavedView(view)}
                        className="font-medium"
                        aria-label={`טען תצוגה ${view.title}`}
                      >
                        {view.title}
                      </button>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onDeleteSavedView?.(view.id); }}
                        className="opacity-60 hover:opacity-100 hover:text-red-600 text-sm leading-none px-1"
                        aria-label={`מחק תצוגה ${view.title}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <button
                    type="button"
                    onClick={() => setSaveDialogOpen(true)}
                    disabled={total === 0}
                    className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full border border-dashed border-slate-300 text-slate-600 hover:border-violet-400 hover:text-violet-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    title={total === 0 ? 'בחר לפחות פילטר אחד' : 'שמור תצוגה'}
                  >
                    <Plus className="w-3 h-3" /> שמור
                  </button>
                </div>
              </div>

              {/* Global search */}
              <div className="px-3 pt-3 pb-2 border-b border-slate-100">
                <input
                  type="text"
                  value={filters.search_text || ''}
                  onChange={(e) => setSearchText(e.target.value)}
                  placeholder="🔍 חיפוש חופשי..."
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-300 focus:border-violet-400 outline-none min-h-[40px]"
                  dir="rtl"
                />
              </div>

              {/* 📍 מיקום */}
              <SectionGroupDivider label="📍 מיקום" />
              <MatrixFilterSection
                mode="building"
                title="בניין"
                activeCount={activeCount?.building || 0}
                options={buildingOptions}
                selectedValues={filters.building_ids || []}
                onToggle={toggleBuilding}
                onClear={clearBuildings}
                emptyLabel="אין בניינים"
              />
              <MatrixFilterSection
                mode="apartment"
                title="דירה"
                activeCount={activeCount?.apartment || 0}
                textValue={filters.apartment_search || ''}
                onTextChange={setApartmentSearch}
                placeholder="מספר דירה מכיל..."
                onClear={() => setApartmentSearch('')}
              />

              {/* 📝 מידע כללי */}
              {tagStages.length > 0 && (
                <>
                  <SectionGroupDivider label="📝 מידע כללי" />
                  {tagStages.map(stage => (
                    <MatrixFilterSection
                      key={stage.id}
                      mode="tag"
                      title={stage.title}
                      activeCount={activeCount?.tag_value?.[stage.id] || 0}
                      options={tagOptionsFor(stage.id)}
                      selectedValues={filters.tag_value_filters?.[stage.id] || []}
                      onToggle={(v) => toggleTagValue(stage.id, v)}
                      onClear={() => clearTagValue(stage.id)}
                    />
                  ))}
                </>
              )}

              {/* 🔨 שלבי בקרת ביצוע */}
              {statusStages.length > 0 && (
                <>
                  <SectionGroupDivider label="🔨 שלבי בקרת ביצוע" />
                  {statusStages.map(stage => (
                    <MatrixFilterSection
                      key={stage.id}
                      mode="status"
                      title={stage.title}
                      activeCount={activeCount?.stage_status?.[stage.id] || 0}
                      options={statusOptions}
                      selectedValues={filters.stage_status_filters?.[stage.id] || []}
                      onToggle={(v) => toggleStageStatus(stage.id, v)}
                      onClear={() => clearStageStatus(stage.id)}
                    />
                  ))}
                </>
              )}
            </div>

            {/* Footer */}
            <div
              className="flex items-center justify-between gap-2 px-3 py-3 border-t border-slate-200 bg-white shrink-0"
              style={{ paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}
            >
              <button
                type="button"
                onClick={reset}
                disabled={total === 0}
                className="px-3 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg min-h-[44px]"
              >
                נקה הכל
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2.5 text-sm font-bold text-white bg-violet-600 hover:bg-violet-700 active:bg-violet-800 rounded-lg min-h-[44px]"
              >
                {applyLabel}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <SavedViewSaveDialog
        open={saveDialogOpen}
        onClose={() => setSaveDialogOpen(false)}
        onSave={async (title) => {
          const res = await onSaveCurrentView?.(title);
          return res || { ok: true };
        }}
      />
    </>
  );
}

function SectionGroupDivider({ label }) {
  return (
    <div className="px-3 pt-3 pb-1.5 mt-1 border-t border-slate-200 bg-slate-50/50">
      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
        {label}
      </div>
    </div>
  );
}
