import React, { useState } from 'react';
import { unitService } from '../services/api';
import { formatUnitLabel } from '../utils/formatters';
import { toast } from 'sonner';
import { X, Loader2 } from 'lucide-react';

export const UNIT_TYPE_TAGS = [
  { value: 'mekhir_lemishtaken', label: 'מחיר למשתכן', color: 'bg-blue-100 text-blue-700' },
  { value: 'shuk_hofshi', label: 'שוק חופשי', color: 'bg-amber-100 text-amber-700' },
];

export const TAG_MAP = Object.fromEntries(UNIT_TYPE_TAGS.map(t => [t.value, t]));

export const UNIT_TYPE_TAG_HEADER_COLORS = Object.fromEntries(
  UNIT_TYPE_TAGS.map(t => [t.value, t.value === 'mekhir_lemishtaken'
    ? 'bg-white/20 text-white'
    : 'bg-white/20 text-white'
  ])
);

export default function UnitTypeEditModal({ unit, onClose, onSaved }) {
  const [unitTypeTag, setUnitTypeTag] = useState(unit?.unit_type_tag || '');
  const [unitNote, setUnitNote] = useState(unit?.unit_note || '');
  const [saving, setSaving] = useState(false);

  if (!unit) return null;

  const label = formatUnitLabel(unit.effective_label || unit.display_label || unit.unit_no || '');

  const handleSave = async () => {
    setSaving(true);
    try {
      await unitService.patch(unit.id, {
        unit_type_tag: unitTypeTag || null,
        unit_note: unitNote || null,
      });
      toast.success('דירה עודכנה');
      onSaved({
        unitId: unit.id,
        unit_type_tag: unitTypeTag || null,
        unit_note: unitNote || null,
      });
      onClose();
    } catch {
      toast.error('שגיאה בעדכון דירה');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50" onClick={onClose} />
      <div className="fixed inset-x-4 top-1/2 -translate-y-1/2 z-50 bg-white rounded-2xl shadow-xl p-5 max-w-sm mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-slate-800">עריכת דירה {label}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">סוג דירה</label>
            <select
              value={unitTypeTag}
              onChange={e => setUnitTypeTag(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
            >
              <option value="">(ריק)</option>
              {UNIT_TYPE_TAGS.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">הערה</label>
            <input
              type="text"
              value={unitNote}
              onChange={e => setUnitNote(e.target.value.slice(0, 200))}
              placeholder="הערה (עד 200 תווים)"
              maxLength={200}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
            <p className="text-[10px] text-slate-400 mt-0.5 text-left">{unitNote.length}/200</p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full bg-amber-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'שמור'}
          </button>
        </div>
      </div>
    </>
  );
}
