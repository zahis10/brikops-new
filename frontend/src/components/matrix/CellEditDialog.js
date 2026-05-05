import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import StatusButtonGrid from './StatusButtonGrid';
import CellHistoryList from './CellHistoryList';
import { matrixService } from '../../services/matrixService';

/**
 * Cell edit dialog — bottom sheet on mobile, centered popover on desktop.
 *
 * Props:
 *   open: bool — controls visibility
 *   onClose: () => void — fires when dialog closes
 *   onSave: (payload) => Promise<{ok, error?}> — wired to useMatrixData.updateCell
 *   projectId: string
 *   unit: { id, unit_no, building_id, floor_id }
 *   stage: { id, title, type } — type='status' or 'tag'
 *   cell: existing cell or null
 *   building: optional { name } for header
 *   floor: optional { floor_number } for header
 *   canEdit: bool (from permissions.can_edit)
 */
export default function CellEditDialog({
  open, onClose, onSave, projectId, unit, stage, cell, building, floor, canEdit,
}) {
  const isTag = stage?.type === 'tag';
  const [status, setStatus] = useState(cell?.status || null);
  const [note, setNote] = useState(cell?.note || '');
  const [textValue, setTextValue] = useState(cell?.text_value || '');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // AbortController for in-flight history request — prevents
  // setState-on-unmounted-component warning when user closes
  // dialog mid-fetch (or saves before history returns).
  const abortRef = useRef(null);

  // Reset form when opening with a different cell
  useEffect(() => {
    if (open) {
      setStatus(cell?.status || null);
      setNote(cell?.note || '');
      setTextValue(cell?.text_value || '');
      setHistoryOpen(false);
      setHistory(null);
    }
  }, [open, cell]);

  // Cleanup: abort any in-flight history fetch on unmount/close
  useEffect(() => {
    if (!open && abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, [open]);

  const fetchHistory = useCallback(async () => {
    if (!projectId || !unit || !stage) return;
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setHistoryLoading(true);
    try {
      const result = await matrixService.getCellHistory(
        projectId, unit.id, stage.id,
        { signal: controller.signal },
      );
      if (!controller.signal.aborted) {
        setHistory(result.history || []);
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        setHistory([]);
        toast.error('שגיאה בטעינת היסטוריה');
      }
    } finally {
      if (!controller.signal.aborted) {
        setHistoryLoading(false);
      }
    }
  }, [projectId, unit, stage]);

  const toggleHistory = () => {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (next && history === null) fetchHistory();
  };

  const hasChange = isTag
    ? textValue !== (cell?.text_value || '') || note !== (cell?.note || '')
    : status !== (cell?.status || null) || note !== (cell?.note || '');

  const handleSave = async () => {
    if (!hasChange || !canEdit || saving) return;
    setSaving(true);
    const payload = isTag
      ? { text_value: textValue, note }
      : { status, note };
    const result = await onSave(payload);
    setSaving(false);
    if (result.ok) {
      onClose();
    } else {
      toast.error(result.error || 'שגיאה בשמירה. נסה שוב');
    }
  };

  if (!open) return null;

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50 data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content
          className="
            fixed z-50 bg-white shadow-2xl
            inset-x-0 bottom-0 rounded-t-2xl max-h-[85vh]
            md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2
            md:rounded-2xl md:max-w-md md:w-full md:max-h-[85vh]
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
            <div className="flex-1 min-w-0">
              <div className="text-xs text-slate-500">
                {building?.name && <span>{building.name}</span>}
                {floor && <span> • קומה {floor.floor_number}</span>}
                {unit && <span> • דירה {unit.unit_no}</span>}
              </div>
              <Dialog.Title className="text-base font-bold text-slate-900 mt-0.5 truncate">
                {stage?.title || 'שלב'}
              </Dialog.Title>
            </div>
            <Dialog.Close asChild>
              <button
                className="p-1.5 -m-1.5 hover:bg-slate-100 rounded-lg transition-colors shrink-0"
                aria-label="סגור"
              >
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </Dialog.Close>
          </div>

          {/* Read-only banner */}
          {!canEdit && (
            <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-800">
              צפייה בלבד — אין לך הרשאת עריכה
            </div>
          )}

          {/* Body — scrollable */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {isTag ? (
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-2">
                  ערך:
                </label>
                <input
                  type="text"
                  value={textValue}
                  onChange={(e) => setTextValue(e.target.value)}
                  disabled={!canEdit}
                  maxLength={200}
                  className="w-full px-3 py-3 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-violet-500 disabled:bg-slate-50 disabled:text-slate-500"
                  placeholder="הזן ערך..."
                  dir="rtl"
                />
                <div className="text-[11px] text-slate-400 mt-1 text-left">
                  {textValue.length}/200
                </div>
              </div>
            ) : (
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-2">
                  סטטוס:
                </label>
                <StatusButtonGrid
                  value={status}
                  onChange={setStatus}
                  disabled={!canEdit}
                />
              </div>
            )}

            {/* Note */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-2">
                הערה:
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={!canEdit}
                maxLength={500}
                rows={3}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-violet-500 disabled:bg-slate-50 disabled:text-slate-500 resize-none"
                placeholder="הוסף הערה (אופציונלי)..."
                dir="rtl"
              />
              <div className="text-[11px] text-slate-400 mt-1 text-left">
                {note.length}/500
              </div>
            </div>

            {/* History — collapsible. Backend cell summary doesn't return
                audit_count; count shown only after expand (history.length). */}
            <div className="border-t border-slate-100 pt-3">
              <button
                type="button"
                onClick={toggleHistory}
                className="w-full flex items-center justify-between gap-2 py-2 text-xs font-medium text-slate-600 hover:text-slate-900"
              >
                <span>
                  {historyOpen
                    ? `היסטוריה${history?.length != null ? ` (${history.length})` : ''}`
                    : 'היסטוריה'}
                </span>
                {historyOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {historyOpen && (
                <div className="mt-2">
                  <CellHistoryList history={history} loading={historyLoading} />
                </div>
              )}
            </div>
          </div>

          {/* Footer — sticky */}
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
              disabled={!canEdit || !hasChange || saving}
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
