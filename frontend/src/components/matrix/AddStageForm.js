import React, { useState } from 'react';
import { Plus, ChevronUp } from 'lucide-react';

/**
 * Inline expandable form for adding a new custom stage.
 * Default collapsed; "+ הוסף עמודה חדשה" expands the form.
 *
 * Props:
 *   onAdd: ({ title, type }) => void
 */
export default function AddStageForm({ onAdd }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [type, setType] = useState('tag'); // default tag for metadata

  const canSubmit = title.trim().length > 0;

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!canSubmit) return;
    onAdd({ title: title.trim(), type });
    setTitle('');
    setType('tag');
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full flex items-center justify-center gap-2 py-3 px-3 rounded-lg border-2 border-dashed border-violet-300 text-violet-700 hover:bg-violet-50 active:bg-violet-100 transition-colors text-sm font-medium min-h-[44px]"
        dir="rtl"
      >
        <Plus className="w-4 h-4" />
        הוסף עמודה חדשה
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-violet-50 border border-violet-200 rounded-lg p-3 space-y-3"
      dir="rtl"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-violet-900">עמודה חדשה</span>
        <button
          type="button"
          onClick={() => { setOpen(false); setTitle(''); setType('tag'); }}
          className="text-xs text-slate-500 hover:text-slate-900"
          aria-label="סגור טופס"
        >
          <ChevronUp className="w-4 h-4" />
        </button>
      </div>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="שם העמודה"
        maxLength={80}
        autoFocus
        className="w-full px-3 py-2 rounded-lg border border-violet-300 text-sm focus:outline-none focus:border-violet-500 bg-white"
      />
      <div className="flex gap-3 text-xs">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="stageType"
            value="tag"
            checked={type === 'tag'}
            onChange={() => setType('tag')}
          />
          <span>📝 מידע כללי (טקסט חופשי)</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="stageType"
            value="status"
            checked={type === 'status'}
            onChange={() => setType('status')}
          />
          <span>🔨 שלב בקרת ביצוע</span>
        </label>
      </div>
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full py-2.5 rounded-lg bg-violet-600 hover:bg-violet-700 active:bg-violet-800 disabled:bg-slate-300 disabled:cursor-not-allowed text-white text-sm font-bold transition-colors min-h-[44px]"
      >
        הוסף לרשימה
      </button>
    </form>
  );
}
