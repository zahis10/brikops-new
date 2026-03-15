import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { templateService } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Loader2, Save, Plus, Trash2, ChevronDown, ChevronUp,
  AlertTriangle, X, Eye, EyeOff, GripVertical
} from 'lucide-react';

const TRADES = [
  'אלומיניום', 'דלתות', 'חשמל', 'טיח', 'ריצוף', 'צביעה',
  'אינסטלציה', 'מטבחים', 'שיש', 'ברזל', 'כללי',
];

const INPUT_TYPES = [
  { value: 'status', label: 'תקין/לא תקין' },
  { value: 'text', label: 'טקסט חופשי' },
  { value: 'photo', label: 'צילום' },
];

const genId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

const AdminHandoverTemplateEditor = () => {
  const { templateId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [templateData, setTemplateData] = useState(null);
  const [name, setName] = useState('');
  const [sections, setSections] = useState([]);
  const [expandedSections, setExpandedSections] = useState({});
  const [malformedWarning, setMalformedWarning] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const loadTemplate = useCallback(async () => {
    try {
      setLoading(true);
      const tpl = await templateService.get(templateId);
      setTemplateData(tpl);
      setName(tpl.name || '');

      if (tpl.sections && tpl.sections.length > 0) {
        setSections(JSON.parse(JSON.stringify(tpl.sections)));
      } else if (tpl.stages && tpl.stages.length > 0) {
        setMalformedWarning(true);
        const mapped = tpl.stages.map((stage, idx) => ({
          id: stage.id || genId('section'),
          name: stage.title || stage.name || `סקשן ${idx + 1}`,
          visible_in_initial: true,
          visible_in_final: true,
          order: stage.order || idx + 1,
          items: (stage.items || []).map((item, iIdx) => ({
            id: item.id || genId('item'),
            name: item.title || item.name || `פריט ${iIdx + 1}`,
            trade: item.trade || 'כללי',
            input_type: item.input_type || 'status',
            order: item.order || iIdx + 1,
          })),
        }));
        setSections(mapped);
      } else {
        setSections([]);
      }

      const expanded = {};
      const secs = tpl.sections || tpl.stages || [];
      if (secs.length <= 5) {
        secs.forEach(s => { expanded[s.id] = true; });
      }
      setExpandedSections(expanded);
    } catch (err) {
      console.error(err);
      toast.error('שגיאה בטעינת תבנית');
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => { loadTemplate(); }, [loadTemplate]);

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error('שם התבנית לא יכול להיות ריק');
      return;
    }
    for (let i = 0; i < sections.length; i++) {
      if (!sections[i].name.trim()) {
        toast.error(`שם סקשן ${i + 1} לא יכול להיות ריק`);
        return;
      }
      for (let j = 0; j < sections[i].items.length; j++) {
        if (!sections[i].items[j].name.trim()) {
          toast.error(`שם פריט ${j + 1} בסקשן "${sections[i].name}" לא יכול להיות ריק`);
          return;
        }
      }
    }

    try {
      setSaving(true);
      const orderedSections = sections.map((s, idx) => ({
        ...s,
        order: idx + 1,
        items: s.items.map((item, iIdx) => ({
          ...item,
          trade: item.trade || 'כללי',
          input_type: item.input_type || 'status',
          order: iIdx + 1,
        })),
      }));

      await templateService.update(templateId, {
        name: name.trim(),
        type: 'handover',
        sections: orderedSections,
      });
      setMalformedWarning(false);
      toast.success('התבנית נשמרה בהצלחה');
    } catch (err) {
      console.error(err);
      toast.error(err.response?.data?.detail || 'שגיאה בשמירת תבנית');
    } finally {
      setSaving(false);
    }
  };

  const toggleSection = (sectionId) => {
    setExpandedSections(prev => ({ ...prev, [sectionId]: !prev[sectionId] }));
  };

  const updateSectionField = (sectionIdx, field, value) => {
    setSections(prev => {
      const next = [...prev];
      next[sectionIdx] = { ...next[sectionIdx], [field]: value };
      return next;
    });
  };

  const addSection = () => {
    const newSection = {
      id: genId('section'),
      name: '',
      visible_in_initial: true,
      visible_in_final: true,
      order: sections.length + 1,
      items: [{
        id: genId('item'),
        name: '',
        trade: 'כללי',
        input_type: 'status',
        order: 1,
      }],
    };
    setSections(prev => [...prev, newSection]);
    setExpandedSections(prev => ({ ...prev, [newSection.id]: true }));
  };

  const removeSection = (sectionIdx) => {
    setDeleteConfirm(null);
    setSections(prev => prev.filter((_, i) => i !== sectionIdx));
  };

  const moveSectionUp = (idx) => {
    if (idx <= 0) return;
    setSections(prev => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  };

  const moveSectionDown = (idx) => {
    if (idx >= sections.length - 1) return;
    setSections(prev => {
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
  };

  const updateItemField = (sectionIdx, itemIdx, field, value) => {
    setSections(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[sectionIdx].items[itemIdx][field] = value;
      return next;
    });
  };

  const addItem = (sectionIdx) => {
    setSections(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[sectionIdx].items.push({
        id: genId('item'),
        name: '',
        trade: 'כללי',
        input_type: 'status',
        order: next[sectionIdx].items.length + 1,
      });
      return next;
    });
  };

  const removeItem = (sectionIdx, itemIdx) => {
    setSections(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[sectionIdx].items.splice(itemIdx, 1);
      return next;
    });
  };

  const moveItemUp = (sectionIdx, itemIdx) => {
    if (itemIdx <= 0) return;
    setSections(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const items = next[sectionIdx].items;
      [items[itemIdx - 1], items[itemIdx]] = [items[itemIdx], items[itemIdx - 1]];
      return next;
    });
  };

  const moveItemDown = (sectionIdx, itemIdx) => {
    setSections(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const items = next[sectionIdx].items;
      if (itemIdx >= items.length - 1) return prev;
      [items[itemIdx], items[itemIdx + 1]] = [items[itemIdx + 1], items[itemIdx]];
      return next;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center" dir="rtl">
        <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    );
  }

  const totalItems = sections.reduce((sum, s) => sum + s.items.length, 0);

  return (
    <div className="min-h-screen bg-slate-50 pb-24" dir="rtl">
      <header className="bg-gradient-to-br from-purple-900 to-purple-800 text-white sticky top-0 z-40 shadow-md">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => navigate('/admin/qc-templates')}
            className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors"
          >
            <ArrowRight className="w-4 h-4" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-bold truncate">עריכת תבנית מסירה</h1>
            <p className="text-[11px] text-purple-200">{sections.length} סקשנים · {totalItems} פריטים</p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-white text-purple-800 rounded-lg text-sm font-bold hover:bg-purple-50 transition-colors disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            שמור
          </button>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 pt-4 space-y-4">
        {malformedWarning && (
          <div className="bg-amber-50 border border-amber-300 rounded-xl p-3 flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-bold text-amber-800">תבנית זו נשמרה בפורמט ישן.</p>
              <p className="text-xs text-amber-700 mt-0.5">שמרו מחדש כדי לתקן את הפורמט.</p>
            </div>
            <button onClick={() => setMalformedWarning(false)} className="p-1 text-amber-500 hover:text-amber-700">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">שם תבנית</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="תבנית מסירה — סטנדרטית"
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded font-medium">תבנית מסירה</span>
            {templateData?.family_id && <span>משפחה: {templateData.family_id.slice(0, 8)}</span>}
            {templateData?.version && <span>גרסה: {templateData.version}</span>}
          </div>
        </div>

        {sections.map((section, sIdx) => {
          const isExpanded = expandedSections[section.id];
          return (
            <div key={section.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div
                className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-100 cursor-pointer"
                onClick={() => toggleSection(section.id)}
              >
                <GripVertical className="w-4 h-4 text-slate-300 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-bold">{sIdx + 1}</span>
                    <span className="text-sm font-bold text-slate-700 truncate">{section.name || 'סקשן חדש'}</span>
                    <span className="text-[10px] text-slate-400">{section.items.length} פריטים</span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    {section.visible_in_initial && (
                      <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">ראשונית</span>
                    )}
                    {section.visible_in_final && (
                      <span className="text-[10px] bg-green-50 text-green-600 px-1.5 py-0.5 rounded">חזקה</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); moveSectionUp(sIdx); }}
                    disabled={sIdx === 0}
                    className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); moveSectionDown(sIdx); }}
                    disabled={sIdx === sections.length - 1}
                    className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteConfirm(sIdx); }}
                    className="p-1 text-red-400 hover:text-red-600"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </div>

              {deleteConfirm === sIdx && (
                <div className="px-4 py-2 bg-red-50 border-b border-red-100 flex items-center gap-2">
                  <span className="text-xs text-red-700">למחוק את הסקשן "{section.name || 'סקשן חדש'}"?</span>
                  <button onClick={() => removeSection(sIdx)} className="text-xs bg-red-500 text-white px-2 py-1 rounded hover:bg-red-600">מחק</button>
                  <button onClick={() => setDeleteConfirm(null)} className="text-xs text-slate-500 hover:text-slate-700">ביטול</button>
                </div>
              )}

              {isExpanded && (
                <div className="p-4 space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-[11px] font-medium text-slate-500 mb-1 block">שם סקשן</label>
                      <input
                        type="text"
                        value={section.name}
                        onChange={(e) => updateSectionField(sIdx, 'name', e.target.value)}
                        placeholder="כניסה לדירה"
                        className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                    </div>
                    <div className="flex items-end gap-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={section.visible_in_initial}
                          onChange={(e) => updateSectionField(sIdx, 'visible_in_initial', e.target.checked)}
                          className="rounded border-slate-300 text-blue-500 focus:ring-blue-500"
                        />
                        <span className="text-xs text-slate-600">ראשונית</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={section.visible_in_final}
                          onChange={(e) => updateSectionField(sIdx, 'visible_in_final', e.target.checked)}
                          className="rounded border-slate-300 text-green-500 focus:ring-green-500"
                        />
                        <span className="text-xs text-slate-600">חזקה</span>
                      </label>
                    </div>
                  </div>

                  <div className="border border-slate-100 rounded-lg overflow-hidden">
                    <div className="bg-slate-50 px-3 py-1.5 border-b border-slate-100">
                      <span className="text-[11px] font-medium text-slate-500">פריטים</span>
                    </div>
                    <div className="divide-y divide-slate-50">
                      {section.items.map((item, iIdx) => (
                        <div key={item.id} className="px-3 py-2 flex items-center gap-2 hover:bg-slate-50/50">
                          <span className="text-[10px] text-slate-400 w-4 text-center flex-shrink-0">{iIdx + 1}</span>
                          <input
                            type="text"
                            value={item.name}
                            onChange={(e) => updateItemField(sIdx, iIdx, 'name', e.target.value)}
                            placeholder="שם פריט"
                            className="flex-1 min-w-0 text-sm border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-500"
                          />
                          <select
                            value={item.trade}
                            onChange={(e) => updateItemField(sIdx, iIdx, 'trade', e.target.value)}
                            className="text-xs border border-slate-200 rounded px-1.5 py-1.5 bg-white text-slate-600 w-[90px]"
                          >
                            {TRADES.map(t => (
                              <option key={t} value={t}>{t}</option>
                            ))}
                          </select>
                          <select
                            value={item.input_type}
                            onChange={(e) => updateItemField(sIdx, iIdx, 'input_type', e.target.value)}
                            className="text-xs border border-slate-200 rounded px-1.5 py-1.5 bg-white text-slate-600 w-[100px]"
                          >
                            {INPUT_TYPES.map(t => (
                              <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                          </select>
                          <div className="flex items-center gap-0.5">
                            <button
                              onClick={() => moveItemUp(sIdx, iIdx)}
                              disabled={iIdx === 0}
                              className="p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"
                            >
                              <ChevronUp className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => moveItemDown(sIdx, iIdx)}
                              disabled={iIdx === section.items.length - 1}
                              className="p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"
                            >
                              <ChevronDown className="w-3.5 h-3.5" />
                            </button>
                          </div>
                          <button
                            onClick={() => removeItem(sIdx, iIdx)}
                            className="p-0.5 text-red-400 hover:text-red-600"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={() => addItem(sIdx)}
                      className="w-full px-3 py-2 text-xs text-purple-600 hover:bg-purple-50 flex items-center gap-1 justify-center border-t border-slate-100"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      הוסף פריט
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        <button
          onClick={addSection}
          className="w-full py-3 border-2 border-dashed border-purple-200 rounded-xl text-sm text-purple-600 font-medium hover:bg-purple-50 hover:border-purple-300 transition-colors flex items-center gap-1 justify-center"
        >
          <Plus className="w-4 h-4" />
          הוסף סקשן
        </button>

        <div className="pt-2 pb-8">
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full py-3 bg-purple-600 text-white rounded-xl text-sm font-bold hover:bg-purple-700 transition-colors disabled:opacity-50 flex items-center gap-2 justify-center"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            שמור תבנית
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminHandoverTemplateEditor;
