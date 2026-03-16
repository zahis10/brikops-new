import React, { useState, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { Plus, Trash2, ChevronUp, ChevronDown, Loader2, Scale, AlertTriangle } from 'lucide-react';

const ROLE_OPTIONS = [
  { value: 'manager', label: 'מנהל פרויקט / מפקח' },
  { value: 'tenant', label: 'רוכש/ת ראשי/ת' },
  { value: 'tenant_2', label: 'רוכש/ת נוסף/ת' },
  { value: 'contractor_rep', label: 'נציג קבלן' },
];

const emptySection = () => ({
  id: null,
  title: '',
  body: '',
  requires_signature: false,
  signature_role: null,
  applies_to: ['initial', 'final'],
  order: 0,
});

const OrgLegalSectionsEditor = ({ orgId }) => {
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await handoverService.getOrgLegalSections(orgId);
      setSections(data.sections || []);
    } catch (err) {
      console.error(err);
      toast.error('שגיאה בטעינת נסחים משפטיים');
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = () => {
    setSections(prev => [...prev, { ...emptySection(), order: prev.length + 1 }]);
  };

  const handleChange = (idx, field, value) => {
    setSections(prev => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], [field]: value };
      if (field === 'requires_signature' && !value) {
        updated[idx].signature_role = null;
      }
      return updated;
    });
  };

  const handleAppliesTo = (idx, type, checked) => {
    setSections(prev => {
      const updated = [...prev];
      const current = updated[idx].applies_to || [];
      if (checked) {
        updated[idx] = { ...updated[idx], applies_to: [...new Set([...current, type])] };
      } else {
        const filtered = current.filter(t => t !== type);
        if (filtered.length === 0) return prev;
        updated[idx] = { ...updated[idx], applies_to: filtered };
      }
      return updated;
    });
  };

  const handleMoveUp = (idx) => {
    if (idx === 0) return;
    setSections(prev => {
      const updated = [...prev];
      [updated[idx - 1], updated[idx]] = [updated[idx], updated[idx - 1]];
      return updated.map((s, i) => ({ ...s, order: i + 1 }));
    });
  };

  const handleMoveDown = (idx) => {
    setSections(prev => {
      if (idx >= prev.length - 1) return prev;
      const updated = [...prev];
      [updated[idx], updated[idx + 1]] = [updated[idx + 1], updated[idx]];
      return updated.map((s, i) => ({ ...s, order: i + 1 }));
    });
  };

  const handleDelete = (idx) => {
    setSections(prev => prev.filter((_, i) => i !== idx).map((s, i) => ({ ...s, order: i + 1 })));
    setConfirmDelete(null);
  };

  const validate = () => {
    for (let i = 0; i < sections.length; i++) {
      const s = sections[i];
      if (!(s.title || '').trim()) {
        toast.error(`נסח #${i + 1}: כותרת נדרשת`);
        return false;
      }
      if (!(s.body || '').trim()) {
        toast.error(`נסח #${i + 1}: תוכן נדרש`);
        return false;
      }
      if (s.requires_signature && !s.signature_role) {
        toast.error(`נסח #${i + 1}: יש לבחור חותם`);
        return false;
      }
      if (!s.applies_to || s.applies_to.length === 0) {
        toast.error(`נסח #${i + 1}: יש לבחור לפחות סוג אחד (ראשונית/חזקה)`);
        return false;
      }
    }
    return true;
  };

  const handleSave = async () => {
    if (!validate()) return;
    try {
      setSaving(true);
      const payload = sections.map((s, i) => ({
        ...(s.id ? { id: s.id } : {}),
        title: s.title.trim(),
        body: s.body.trim(),
        requires_signature: s.requires_signature,
        signature_role: s.requires_signature ? s.signature_role : null,
        applies_to: s.applies_to,
        order: i + 1,
      }));
      const data = await handoverService.putOrgLegalSections(orgId, payload);
      setSections(data.sections || []);
      toast.success('נסחים משפטיים נשמרו');
    } catch (err) {
      console.error(err);
      toast.error(err?.response?.data?.detail || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full"
      >
        <div className="flex items-center gap-2">
          <Scale className="w-5 h-5 text-indigo-500" />
          <h2 className="text-lg font-semibold text-slate-800">נסחים משפטיים למסירה</h2>
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
      </button>

      {expanded && (
        <div className="space-y-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : sections.length === 0 ? (
            <div className="text-center py-6 space-y-2">
              <p className="text-sm text-slate-400">לא הוגדרו נסחים משפטיים.</p>
              <p className="text-xs text-slate-400">הוסיפו נסחים כדי שיופיעו בפרוטוקולי מסירה.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sections.map((section, idx) => (
                <div key={section.id || idx} className="border border-slate-200 rounded-xl p-4 space-y-3 bg-slate-50/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">נסח {idx + 1}</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleMoveUp(idx)}
                        disabled={idx === 0}
                        className="p-1 hover:bg-slate-200 rounded disabled:opacity-30"
                        title="הזז למעלה"
                      >
                        <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
                      </button>
                      <button
                        onClick={() => handleMoveDown(idx)}
                        disabled={idx === sections.length - 1}
                        className="p-1 hover:bg-slate-200 rounded disabled:opacity-30"
                        title="הזז למטה"
                      >
                        <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
                      </button>
                      {confirmDelete === idx ? (
                        <div className="flex items-center gap-1 mr-1">
                          <button
                            onClick={() => handleDelete(idx)}
                            className="text-[10px] text-red-600 hover:text-red-800 font-medium px-2 py-0.5 bg-red-50 rounded"
                          >
                            מחק
                          </button>
                          <button
                            onClick={() => setConfirmDelete(null)}
                            className="text-[10px] text-slate-500 px-2 py-0.5"
                          >
                            ביטול
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDelete(idx)}
                          className="p-1 hover:bg-red-100 rounded text-slate-400 hover:text-red-500"
                          title="מחק נסח"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">כותרת</label>
                    <input
                      type="text"
                      value={section.title}
                      onChange={(e) => handleChange(idx, 'title', e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
                        focus:outline-none focus:ring-2 focus:ring-indigo-300"
                      dir="rtl"
                      placeholder="שם הנסח"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">תוכן</label>
                    <textarea
                      value={section.body}
                      onChange={(e) => handleChange(idx, 'body', e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none
                        focus:outline-none focus:ring-2 focus:ring-indigo-300 leading-relaxed min-h-[80px]"
                      dir="rtl"
                      placeholder="תוכן הנסח המשפטי..."
                    />
                  </div>

                  <div className="flex items-center gap-4 flex-wrap">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={section.requires_signature}
                        onChange={(e) => handleChange(idx, 'requires_signature', e.target.checked)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-slate-700">דורש חתימה</span>
                    </label>

                    {section.requires_signature && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">חותם:</span>
                        <select
                          value={section.signature_role || ''}
                          onChange={(e) => handleChange(idx, 'signature_role', e.target.value || null)}
                          className="text-sm border border-slate-200 rounded-lg px-2 py-1.5
                            focus:outline-none focus:ring-2 focus:ring-indigo-300"
                        >
                          <option value="">— בחר —</option>
                          {ROLE_OPTIONS.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-4">
                    <span className="text-xs text-slate-500">חל על:</span>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(section.applies_to || []).includes('initial')}
                        onChange={(e) => handleAppliesTo(idx, 'initial', e.target.checked)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-slate-700">ראשונית</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(section.applies_to || []).includes('final')}
                        onChange={(e) => handleAppliesTo(idx, 'final', e.target.checked)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-slate-700">חזקה</span>
                    </label>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={handleAdd}
              className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 font-medium px-3 py-1.5 border border-indigo-200 rounded-lg hover:bg-indigo-50"
            >
              <Plus className="w-3.5 h-3.5" />
              הוסף נסח
            </button>
            {sections.length > 0 && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-sm font-medium
                  hover:bg-indigo-700 active:scale-[0.98] disabled:opacity-50"
              >
                {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {saving ? 'שומר...' : 'שמור'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default OrgLegalSectionsEditor;
