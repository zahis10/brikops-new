import React from 'react';
import { ChevronDown, ChevronUp, Trash2, Plus } from 'lucide-react';

const ROLE_ORDER = [
  'site_manager',
  'execution_engineer',
  'safety_assistant',
  'work_manager',
  'safety_officer',
];

const ROLE_LABELS = {
  site_manager: 'מנהל אתר',
  execution_engineer: 'מהנדס ביצוע',
  safety_assistant: 'עוזר בטיחות',
  work_manager: 'מנהל עבודה',
  safety_officer: 'ממונה בטיחות',
};

const EMPTY_PERSON = {
  first_name: '',
  last_name: '',
  id_number: '',
  license_number: '',
  notes: '',
};

export default function SafetyProjectPersonnelSection({
  personnel,
  onChange,
  isOpen,
  onToggle,
}) {
  const list = Array.isArray(personnel) ? personnel : [];
  const totalCount = list.length;

  const addPerson = (role) => {
    onChange([...list, { ...EMPTY_PERSON, role }]);
  };

  const removePerson = (absoluteIdx) => {
    if (!window.confirm('להסיר את האחראי הזה?')) return;
    onChange(list.filter((_, i) => i !== absoluteIdx));
  };

  const setPersonField = (absoluteIdx, field, value) => {
    onChange(
      list.map((p, i) => (i === absoluteIdx ? { ...p, [field]: value } : p))
    );
  };

  const indexedByRole = ROLE_ORDER.map((role) => ({
    role,
    items: list
      .map((p, idx) => ({ p, idx }))
      .filter(({ p }) => p.role === role),
  }));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-3">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <span className="font-bold text-slate-800">
          4. אחראי בטיחות בפרויקט ({totalCount})
        </span>
        {isOpen ? (
          <ChevronUp className="w-5 h-5 text-slate-500" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-500" />
        )}
      </button>
      {isOpen && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3" dir="rtl">
          {indexedByRole.map(({ role, items }) => (
            <div key={role} className="mb-5">
              <div className="flex items-center justify-between mb-2 py-3">
                <span className="font-semibold text-slate-800">
                  {ROLE_LABELS[role]} ({items.length})
                </span>
              </div>

              {items.map(({ p, idx }, posIdx) => (
                <div
                  key={idx}
                  className="bg-slate-50 rounded-lg px-3 py-3 mb-3"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-slate-700">
                      {ROLE_LABELS[role]} #{posIdx + 1}
                    </span>
                    <button
                      onClick={() => removePerson(idx)}
                      className="text-red-500 hover:text-red-700 px-3 py-3"
                      aria-label="הסר"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        שם פרטי
                      </label>
                      <input
                        type="text"
                        value={p.first_name || ''}
                        onChange={(e) =>
                          setPersonField(idx, 'first_name', e.target.value)
                        }
                        dir="rtl"
                        className="w-full px-3 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        שם משפחה
                      </label>
                      <input
                        type="text"
                        value={p.last_name || ''}
                        onChange={(e) =>
                          setPersonField(idx, 'last_name', e.target.value)
                        }
                        dir="rtl"
                        className="w-full px-3 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                  </div>

                  <div className="mb-3">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      ת.ז
                    </label>
                    <input
                      type="text"
                      value={p.id_number || ''}
                      onChange={(e) =>
                        setPersonField(idx, 'id_number', e.target.value)
                      }
                      placeholder="9 ספרות (יוצפן בשמירה)"
                      dir="rtl"
                      className="w-full px-3 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  <div className="mb-3">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      מספר רישיון / הסמכה
                    </label>
                    <input
                      type="text"
                      value={p.license_number || ''}
                      onChange={(e) =>
                        setPersonField(idx, 'license_number', e.target.value)
                      }
                      dir="rtl"
                      className="w-full px-3 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  <div className="mb-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      הערות
                    </label>
                    <textarea
                      rows={2}
                      value={p.notes || ''}
                      onChange={(e) =>
                        setPersonField(idx, 'notes', e.target.value)
                      }
                      dir="rtl"
                      className="w-full px-3 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>
              ))}

              <button
                onClick={() => addPerson(role)}
                className="w-full py-3 px-3 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-blue-500 hover:text-blue-600 flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" /> הוסף {ROLE_LABELS[role]}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
