import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Eye, EyeOff, Trash2 } from 'lucide-react';

/**
 * Single stage row inside StageManagementDialog.
 *
 * Two modes by `mode` prop:
 *   'custom' → sortable (drag handle), with Trash2 delete button.
 *   'base'   → not sortable (template order is fixed), with Eye/EyeOff toggle.
 *
 * Props:
 *   stage: { id, title, type, source, scope? }
 *   mode: 'custom' | 'base'
 *   isHidden: bool (only meaningful for base stages)
 *   onToggleHide: () => void (base mode)
 *   onDelete: () => void (custom mode)
 */
export default function StageRow({ stage, mode, isHidden = false, onToggleHide, onDelete }) {
  const isCustom = mode === 'custom';

  // useSortable always called (rules-of-hooks); base rows pass disabled:true
  // so they keep the hook call stable without becoming draggable.
  const sortable = useSortable({
    id: stage.id,
    disabled: !isCustom,
  });
  const style = {
    transform: CSS.Transform.toString(sortable.transform),
    transition: sortable.transition,
    opacity: sortable.isDragging ? 0.5 : 1,
  };

  const typeLabel = stage.type === 'tag' ? 'תגית' : 'סטטוס';
  const typeColor = stage.type === 'tag'
    ? 'bg-amber-50 text-amber-800 border-amber-200'
    : 'bg-emerald-50 text-emerald-800 border-emerald-200';

  return (
    <div
      ref={sortable.setNodeRef}
      style={style}
      className={`
        flex items-center gap-2 py-2 px-2 rounded-lg
        ${isCustom ? 'bg-violet-50 border border-violet-200' : 'bg-slate-50 border border-slate-200'}
        ${isHidden ? 'opacity-60' : ''}
      `}
      dir="rtl"
    >
      {isCustom ? (
        <button
          type="button"
          className="p-2 -m-2 cursor-grab active:cursor-grabbing touch-none text-slate-400 hover:text-slate-600 min-w-[44px] min-h-[44px] inline-flex items-center justify-center"
          {...sortable.attributes}
          {...sortable.listeners}
          aria-label="גרור לשינוי סדר"
        >
          <GripVertical className="w-4 h-4" />
        </button>
      ) : (
        <span className="w-6 h-6 inline-flex items-center justify-center text-slate-300">
          <Eye className="w-4 h-4" />
        </span>
      )}

      <span className={`flex-1 text-sm font-medium truncate ${isHidden ? 'line-through text-slate-500' : 'text-slate-900'}`}>
        {stage.title}
      </span>

      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${typeColor} shrink-0`}>
        {typeLabel}
      </span>

      {isCustom ? (
        <button
          type="button"
          onClick={onDelete}
          className="p-2 -m-2 text-red-500 hover:bg-red-50 rounded-lg min-w-[44px] min-h-[44px] inline-flex items-center justify-center"
          aria-label="מחק עמודה"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      ) : (
        <button
          type="button"
          onClick={onToggleHide}
          className={`p-2 -m-2 rounded-lg min-w-[44px] min-h-[44px] inline-flex items-center justify-center ${
            isHidden
              ? 'text-slate-400 hover:text-slate-700 hover:bg-slate-100'
              : 'text-slate-700 hover:bg-slate-100'
          }`}
          aria-label={isHidden ? 'הצג עמודה' : 'הסתר עמודה'}
        >
          {isHidden ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      )}
    </div>
  );
}
