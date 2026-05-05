import React, { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  DndContext, closestCenter, PointerSensor, KeyboardSensor,
  useSensor, useSensors,
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import StageRow from './StageRow';
import AddStageForm from './AddStageForm';

/**
 * Stage management dialog — modal/sheet for adding/hiding/reordering matrix columns.
 *
 * Props:
 *   open: bool
 *   onClose: () => void
 *   onSave: (payload) => Promise<{ok, error?}>
 *     payload: { custom_stages_added, base_stages_removed }
 *   stages: [{ id, title, type, source, scope?, order }]
 *   initialBaseRemoved: [stage_id, ...] — base stage IDs currently hidden
 *     (from /matrix response — hydrates the hide-toggle state correctly).
 */
export default function StageManagementDialog({
  open, onClose, onSave, stages, initialBaseRemoved = [],
  initialAllBaseStages = [],   // ← NEW (#497)
}) {
  // #497 — section 2 must show ALL base stages (including hidden)
  // so PM can toggle hide/show. Falls back to filtered `stages`
  // when older response shape (pre-#497).
  const initialBase = initialAllBaseStages.length > 0
    ? initialAllBaseStages
    : (stages || []).filter(s => s.source === 'base');
  const initialCustom = (stages || []).filter(s => s.source === 'custom');

  const [customStages, setCustomStages] = useState([]);
  const [hiddenBaseIds, setHiddenBaseIds] = useState(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setCustomStages(initialCustom.map(s => ({ ...s })));
      // Bug 2 fix — hydrate from response, NOT empty. Without this,
      // every save un-hides previously hidden base stages.
      setHiddenBaseIds(new Set(initialBaseRemoved));
      setSaving(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, stages, initialBaseRemoved]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setCustomStages((prev) => {
      const oldIndex = prev.findIndex(s => s.id === active.id);
      const newIndex = prev.findIndex(s => s.id === over.id);
      if (oldIndex < 0 || newIndex < 0) return prev;
      return arrayMove(prev, oldIndex, newIndex);
    });
  };

  const handleDeleteCustom = (stageId) => {
    setCustomStages((prev) => prev.filter(s => s.id !== stageId));
  };

  const handleToggleHideBase = (stageId) => {
    setHiddenBaseIds((prev) => {
      const next = new Set(prev);
      if (next.has(stageId)) next.delete(stageId);
      else next.add(stageId);
      return next;
    });
  };

  const handleAdd = ({ title, type }) => {
    const tempId = `__new_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setCustomStages((prev) => [
      ...prev,
      { id: tempId, title, type, source: 'custom', _isNew: true },
    ]);
  };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);

    // Negative orders so custom stages render BEFORE template stages
    // (right side in RTL display). i=0 → most negative, last → -1.
    const N = customStages.length;
    const custom_stages_added = customStages.map((s, i) => ({
      // Bug 1 fix — preserve existing custom stage IDs so their cells
      // stay reachable. Only NEW stages (added in this dialog session,
      // marker `_isNew: true`) get fresh backend IDs.
      ...(s._isNew ? {} : { id: s.id }),
      title: s.title,
      type: s.type,
      order: i - N,
    }));
    const base_stages_removed = Array.from(hiddenBaseIds);

    const result = await onSave({ custom_stages_added, base_stages_removed });
    setSaving(false);
    if (result.ok) {
      onClose();
    } else {
      toast.error(result.error || 'שגיאה בשמירת העמודות');
    }
  };

  if (!open) return null;

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content
          className="
            fixed z-50 bg-white shadow-2xl
            inset-x-0 bottom-0 rounded-t-2xl max-h-[90vh]
            md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2
            md:rounded-2xl md:max-w-lg md:w-full md:max-h-[85vh]
            flex flex-col overflow-hidden
          "
          dir="rtl"
        >
          {/* Mobile drag handle */}
          <div className="md:hidden flex justify-center py-2">
            <div className="w-10 h-1 bg-slate-300 rounded-full" />
          </div>

          {/* Header */}
          <div className="flex items-start justify-between gap-2 px-4 pt-2 pb-3 border-b border-slate-200">
            <Dialog.Title className="text-base font-bold text-slate-900">
              ניהול עמודות
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                className="p-1.5 -m-1.5 hover:bg-slate-100 rounded-lg transition-colors shrink-0"
                aria-label="סגור"
              >
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </Dialog.Close>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {/* Section 1: Custom (metadata) stages */}
            <section>
              <h3 className="text-xs font-bold text-slate-700 mb-2">
                📋 עמודות מותאמות
                <span className="text-[10px] font-normal text-slate-500 mr-2 block sm:inline">
                  תגיות (טקסט חופשי) או סטטוסים (6 ערכים — כמו עמודות בקרת ביצוע)
                </span>
              </h3>
              <div className="mb-3">
                <AddStageForm onAdd={handleAdd} />
              </div>
              {customStages.length === 0 ? (
                <div className="text-xs text-slate-400 py-4 text-center leading-relaxed">
                  אין עדיין עמודות מותאמות.
                  <br />
                  הוסף עמודה ראשונה למעלה ↑
                </div>
              ) : (
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleDragEnd}
                >
                  <SortableContext
                    items={customStages.map(s => s.id)}
                    strategy={verticalListSortingStrategy}
                  >
                    <div className="space-y-2">
                      {customStages.map((stage) => (
                        <StageRow
                          key={stage.id}
                          stage={stage}
                          mode="custom"
                          onDelete={() => handleDeleteCustom(stage.id)}
                        />
                      ))}
                    </div>
                  </SortableContext>
                </DndContext>
              )}
            </section>

            <div className="border-t border-slate-200" />

            {/* Section 2: Template (base) stages */}
            <section>
              <h3 className="text-xs font-bold text-slate-700 mb-2">
                🔨 עמודות בקרת ביצוע
                <span className="text-[10px] font-normal text-slate-500 mr-2 block sm:inline">
                  (מהתבנית — סדר קבוע, אפשר להציג/להסתיר. שלבים מוסתרים יוצגו עמומים)
                </span>
              </h3>
              {initialBase.length === 0 ? (
                <div className="text-xs text-slate-400 py-3 text-center">
                  אין שלבים בתבנית
                </div>
              ) : (
                <div className="space-y-2">
                  {initialBase.map((stage) => (
                    <StageRow
                      key={stage.id}
                      stage={stage}
                      mode="base"
                      isHidden={hiddenBaseIds.has(stage.id)}
                      onToggleHide={() => handleToggleHideBase(stage.id)}
                    />
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Footer */}
          <div
            className="flex items-center justify-end gap-2 px-4 py-3 border-t border-slate-200 bg-white"
            style={{ paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}
          >
            <Dialog.Close asChild>
              <button
                type="button"
                className="px-4 py-3 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors min-h-[44px]"
              >
                ביטול
              </button>
            </Dialog.Close>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-3 rounded-lg text-sm font-bold text-white bg-violet-600 hover:bg-violet-700 active:bg-violet-800 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors min-h-[44px] inline-flex items-center gap-2"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {saving ? 'שומר...' : 'שמור'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
