import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { templateService } from '../services/api';
import { toast } from 'sonner';
import {
  ChevronRight, ChevronDown, ChevronUp, ChevronLeft,
  Plus, Trash2, Copy, Save, Loader2, AlertTriangle,
  Camera, FileText, GripVertical, Edit2, Check, X,
  ArrowUp, ArrowDown, Star, Search, Archive, Undo2
} from 'lucide-react';

const SCOPE_OPTIONS = [
  { value: 'floor', label: 'קומה' },
  { value: 'unit', label: 'דירה' },
];

const EMOJI_OPTIONS = ['🏗️', '🧱', '🔧', '⚡', '🧹', '💧', '🔊', '🏠', '📋', '🔨', '🪟', '🚪', '🎨', '🔩', '🪣', '🧰'];

const AdminQCTemplatesPage = () => {
  const navigate = useNavigate();
  const [families, setFamilies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [editingTemplate, setEditingTemplate] = useState(null);
  const [editingStages, setEditingStages] = useState([]);
  const [editingName, setEditingName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [expandedStages, setExpandedStages] = useState({});
  const [editingField, setEditingField] = useState(null);
  const [editingFieldValue, setEditingFieldValue] = useState('');

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [archiving, setArchiving] = useState(null);

  const loadFamilies = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await templateService.list({
        search: searchQuery,
        include_archived: showArchived,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      setFamilies(data);
    } catch (e) {
      setError('שגיאה בטעינת תבניות');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, showArchived, sortBy, sortDir]);

  useEffect(() => { loadFamilies(); }, [loadFamilies]);

  const openEditor = async (templateId) => {
    try {
      setLoading(true);
      const tpl = await templateService.get(templateId);
      setEditingTemplate(tpl);
      setEditingName(tpl.name);
      setEditingStages(JSON.parse(JSON.stringify(tpl.stages)));
      setExpandedStages({});
      setSaveError(null);
      setSaveSuccess(false);
    } catch (e) {
      setError('שגיאה בטעינת תבנית');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!editingTemplate) return;
    try {
      setSaving(true);
      setSaveError(null);
      setSaveSuccess(false);
      const result = await templateService.update(editingTemplate.id, {
        name: editingName,
        stages: editingStages,
      });
      setEditingTemplate(result);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      await loadFamilies();
    } catch (e) {
      setSaveError(e.response?.data?.detail || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleClone = async () => {
    if (!editingTemplate) return;
    try {
      setSaving(true);
      const result = await templateService.clone(editingTemplate.id, {
        name: `${editingName} — עותק`,
      });
      await loadFamilies();
      setEditingTemplate(result);
      setEditingName(result.name);
      setEditingStages(JSON.parse(JSON.stringify(result.stages)));
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      setSaveError(e.response?.data?.detail || 'שגיאה בשכפול');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateNew = async () => {
    try {
      setSaving(true);
      const result = await templateService.create({
        name: 'תבנית חדשה',
        stages: [{
          id: `stage_${Date.now()}`,
          title: 'שלב חדש',
          order: 1,
          scope: 'floor',
          icon: '📋',
          items: [{
            id: `item_${Date.now()}`,
            title: 'פריט חדש',
            order: 1,
            required_photo: false,
            required_note: false,
          }],
        }],
      });
      await loadFamilies();
      openEditor(result.id);
    } catch (e) {
      setError(e.response?.data?.detail || 'שגיאה ביצירת תבנית');
    } finally {
      setSaving(false);
    }
  };

  const toggleStageExpanded = (stageId) => {
    setExpandedStages(prev => ({ ...prev, [stageId]: !prev[stageId] }));
  };

  const updateStageField = (stageIdx, field, value) => {
    setEditingStages(prev => {
      const next = [...prev];
      next[stageIdx] = { ...next[stageIdx], [field]: value };
      return next;
    });
  };

  const updateItemField = (stageIdx, itemIdx, field, value) => {
    setEditingStages(prev => {
      const next = [...prev];
      const items = [...next[stageIdx].items];
      items[itemIdx] = { ...items[itemIdx], [field]: value };
      next[stageIdx] = { ...next[stageIdx], items };
      return next;
    });
  };

  const moveStage = (idx, direction) => {
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= editingStages.length) return;
    setEditingStages(prev => {
      const next = [...prev];
      [next[idx], next[newIdx]] = [next[newIdx], next[idx]];
      return next.map((s, i) => ({ ...s, order: i + 1 }));
    });
  };

  const moveItem = (stageIdx, itemIdx, direction) => {
    const stage = editingStages[stageIdx];
    const newIdx = itemIdx + direction;
    if (newIdx < 0 || newIdx >= stage.items.length) return;
    setEditingStages(prev => {
      const next = [...prev];
      const items = [...next[stageIdx].items];
      [items[itemIdx], items[newIdx]] = [items[newIdx], items[itemIdx]];
      next[stageIdx] = { ...next[stageIdx], items: items.map((it, i) => ({ ...it, order: i + 1 })) };
      return next;
    });
  };

  const addStage = () => {
    setEditingStages(prev => [
      ...prev,
      {
        id: `stage_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        title: 'שלב חדש',
        order: prev.length + 1,
        scope: 'floor',
        icon: '📋',
        items: [],
      },
    ]);
  };

  const removeStage = (stageIdx) => {
    setEditingStages(prev => prev.filter((_, i) => i !== stageIdx).map((s, i) => ({ ...s, order: i + 1 })));
    setShowDeleteConfirm(null);
  };

  const addItem = (stageIdx) => {
    setEditingStages(prev => {
      const next = [...prev];
      const items = [...next[stageIdx].items];
      items.push({
        id: `item_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        title: 'פריט חדש',
        order: items.length + 1,
        required_photo: false,
        required_note: false,
      });
      next[stageIdx] = { ...next[stageIdx], items };
      return next;
    });
  };

  const removeItem = (stageIdx, itemIdx) => {
    setEditingStages(prev => {
      const next = [...prev];
      const items = next[stageIdx].items.filter((_, i) => i !== itemIdx).map((it, i) => ({ ...it, order: i + 1 }));
      next[stageIdx] = { ...next[stageIdx], items };
      return next;
    });
    setShowDeleteConfirm(null);
  };

  const startInlineEdit = (key, currentValue) => {
    setEditingField(key);
    setEditingFieldValue(currentValue);
  };

  const commitInlineEdit = (stageIdx, itemIdx, field) => {
    if (itemIdx !== null && itemIdx !== undefined) {
      updateItemField(stageIdx, itemIdx, field, editingFieldValue);
    } else {
      updateStageField(stageIdx, field, editingFieldValue);
    }
    setEditingField(null);
    setEditingFieldValue('');
  };

  const cancelInlineEdit = () => {
    setEditingField(null);
    setEditingFieldValue('');
  };

  if (editingTemplate) {
    return (
      <div className="min-h-screen bg-slate-50" dir="rtl">
        <div className="sticky top-0 z-20 bg-white border-b border-slate-200 px-4 py-3">
          <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
            <button onClick={() => { setEditingTemplate(null); loadFamilies(); }} className="flex items-center gap-1 text-sm text-slate-600">
              <ChevronRight className="w-4 h-4" />
              חזרה
            </button>
            <div className="flex items-center gap-2">
              {saveSuccess && <span className="text-xs text-green-600 font-medium">נשמר!</span>}
              {saveError && <span className="text-xs text-red-600">{saveError}</span>}
              <button
                onClick={handleClone}
                disabled={saving}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
              >
                <Copy className="w-3.5 h-3.5" />
                שכפל
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                שמור כגרסה חדשה
              </button>
            </div>
          </div>
        </div>

        <div className="max-w-3xl mx-auto px-4 py-4 space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <label className="text-xs text-slate-500 font-medium mb-1 block">שם התבנית</label>
            <input
              type="text"
              value={editingName}
              onChange={e => setEditingName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
              <span>גרסה: {editingTemplate.version}</span>
              <span>משפחה: {editingTemplate.family_id?.slice(0, 8)}</span>
              {editingTemplate.is_default && <span className="text-amber-600 font-medium flex items-center gap-1"><Star className="w-3 h-3" /> ברירת מחדל</span>}
            </div>
          </div>

          {editingStages.map((stage, si) => {
            const isExpanded = expandedStages[stage.id];
            return (
              <div key={stage.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div
                  className="flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-slate-50"
                  onClick={() => toggleStageExpanded(stage.id)}
                >
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronLeft className="w-4 h-4 text-slate-400" />}
                  <span className="text-lg">{stage.icon || '📋'}</span>
                  {editingField === `stage_title_${si}` ? (
                    <div className="flex items-center gap-1 flex-1" onClick={e => e.stopPropagation()}>
                      <input
                        autoFocus
                        value={editingFieldValue}
                        onChange={e => setEditingFieldValue(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') commitInlineEdit(si, null, 'title'); if (e.key === 'Escape') cancelInlineEdit(); }}
                        className="flex-1 px-2 py-0.5 border border-blue-400 rounded text-sm focus:outline-none"
                      />
                      <button onClick={() => commitInlineEdit(si, null, 'title')} className="text-green-600"><Check className="w-4 h-4" /></button>
                      <button onClick={cancelInlineEdit} className="text-slate-400"><X className="w-4 h-4" /></button>
                    </div>
                  ) : (
                    <span className="flex-1 text-sm font-medium text-slate-800">{stage.title}</span>
                  )}
                  <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">{stage.scope === 'unit' ? 'דירה' : 'קומה'}</span>
                  <span className="text-xs text-slate-400">{stage.items?.length || 0} פריטים</span>
                </div>

                {isExpanded && (
                  <div className="border-t border-slate-100 px-4 py-3 space-y-3">
                    <div className="flex items-center gap-3 flex-wrap">
                      <button
                        onClick={(e) => { e.stopPropagation(); startInlineEdit(`stage_title_${si}`, stage.title); }}
                        className="text-xs text-blue-600 flex items-center gap-1 hover:underline"
                      >
                        <Edit2 className="w-3 h-3" /> שנה שם
                      </button>
                      <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                        <span className="text-xs text-slate-500">סוג:</span>
                        <select
                          value={stage.scope || 'floor'}
                          onChange={e => updateStageField(si, 'scope', e.target.value)}
                          className="text-xs border border-slate-300 rounded px-1 py-0.5"
                        >
                          {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      </div>
                      <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                        <span className="text-xs text-slate-500">אייקון:</span>
                        <select
                          value={stage.icon || '📋'}
                          onChange={e => updateStageField(si, 'icon', e.target.value)}
                          className="text-xs border border-slate-300 rounded px-1 py-0.5"
                        >
                          {EMOJI_OPTIONS.map(e => <option key={e} value={e}>{e}</option>)}
                        </select>
                      </div>
                      <div className="flex items-center gap-1 mr-auto" onClick={e => e.stopPropagation()}>
                        <button onClick={() => moveStage(si, -1)} disabled={si === 0} className="p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"><ArrowUp className="w-3.5 h-3.5" /></button>
                        <button onClick={() => moveStage(si, 1)} disabled={si === editingStages.length - 1} className="p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"><ArrowDown className="w-3.5 h-3.5" /></button>
                        <button
                          onClick={() => setShowDeleteConfirm(`stage_${si}`)}
                          className="p-0.5 text-red-400 hover:text-red-600"
                        ><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </div>

                    {showDeleteConfirm === `stage_${si}` && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center justify-between">
                        <span className="text-xs text-red-700">למחוק את השלב "{stage.title}"?</span>
                        <div className="flex gap-2">
                          <button onClick={() => removeStage(si)} className="text-xs bg-red-600 text-white px-3 py-1 rounded">מחק</button>
                          <button onClick={() => setShowDeleteConfirm(null)} className="text-xs bg-white text-slate-600 px-3 py-1 rounded border">ביטול</button>
                        </div>
                      </div>
                    )}

                    <div className="space-y-1">
                      {(stage.items || []).map((item, ii) => (
                        <div key={item.id} className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-slate-50 group">
                          <span className="text-xs text-slate-300 w-5 text-center">{ii + 1}</span>
                          {editingField === `item_title_${si}_${ii}` ? (
                            <div className="flex items-center gap-1 flex-1">
                              <input
                                autoFocus
                                value={editingFieldValue}
                                onChange={e => setEditingFieldValue(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') commitInlineEdit(si, ii, 'title'); if (e.key === 'Escape') cancelInlineEdit(); }}
                                className="flex-1 px-2 py-0.5 border border-blue-400 rounded text-xs focus:outline-none"
                              />
                              <button onClick={() => commitInlineEdit(si, ii, 'title')} className="text-green-600"><Check className="w-3.5 h-3.5" /></button>
                              <button onClick={cancelInlineEdit} className="text-slate-400"><X className="w-3.5 h-3.5" /></button>
                            </div>
                          ) : (
                            <span
                              className="flex-1 text-xs text-slate-700 cursor-pointer hover:text-blue-600"
                              onClick={() => startInlineEdit(`item_title_${si}_${ii}`, item.title)}
                            >
                              {item.title}
                              {item.pre_work_documentation && <span className="mr-1 text-amber-500 text-[10px]">📝 פתיחת מלאכה</span>}
                            </span>
                          )}
                          <button
                            onClick={() => updateItemField(si, ii, 'required_photo', !item.required_photo)}
                            className={`p-1 rounded ${item.required_photo ? 'text-blue-600 bg-blue-50' : 'text-slate-300'}`}
                            title="תמונה חובה"
                          >
                            <Camera className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => updateItemField(si, ii, 'required_note', !item.required_note)}
                            className={`p-1 rounded ${item.required_note ? 'text-blue-600 bg-blue-50' : 'text-slate-300'}`}
                            title="הערה חובה"
                          >
                            <FileText className="w-3.5 h-3.5" />
                          </button>
                          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={() => moveItem(si, ii, -1)} disabled={ii === 0} className="p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"><ArrowUp className="w-3 h-3" /></button>
                            <button onClick={() => moveItem(si, ii, 1)} disabled={ii === stage.items.length - 1} className="p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"><ArrowDown className="w-3 h-3" /></button>
                            <button
                              onClick={() => setShowDeleteConfirm(`item_${si}_${ii}`)}
                              className="p-0.5 text-red-400 hover:text-red-600"
                            ><Trash2 className="w-3 h-3" /></button>
                          </div>
                          {showDeleteConfirm === `item_${si}_${ii}` && (
                            <div className="absolute left-4 bg-red-50 border border-red-200 rounded p-2 shadow-lg z-10 flex items-center gap-2">
                              <span className="text-[10px] text-red-700">למחוק?</span>
                              <button onClick={() => removeItem(si, ii)} className="text-[10px] bg-red-600 text-white px-2 py-0.5 rounded">מחק</button>
                              <button onClick={() => setShowDeleteConfirm(null)} className="text-[10px] bg-white text-slate-600 px-2 py-0.5 rounded border">לא</button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    <button
                      onClick={() => addItem(si)}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 mt-2"
                    >
                      <Plus className="w-3.5 h-3.5" /> הוסף פריט
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          <button
            onClick={addStage}
            className="w-full flex items-center justify-center gap-2 py-3 text-sm text-blue-600 border-2 border-dashed border-blue-300 rounded-xl hover:bg-blue-50"
          >
            <Plus className="w-4 h-4" /> הוסף שלב
          </button>
        </div>
      </div>
    );
  }

  const handleArchiveFamily = async (e, familyId, archive) => {
    e.stopPropagation();
    try {
      setArchiving(familyId);
      await templateService.archiveFamily(familyId, archive);
      toast.success(archive ? 'התבנית הועברה לארכיון' : 'התבנית שוחזרה');
      await loadFamilies();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה');
    } finally {
      setArchiving(null);
    }
  };

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="sticky top-0 z-20 bg-white border-b border-slate-200 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/admin')} className="text-slate-600">
              <ChevronRight className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-bold text-slate-800">תבניות QC</h1>
          </div>
          <button
            onClick={handleCreateNew}
            disabled={saving}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700"
          >
            <Plus className="w-3.5 h-3.5" /> תבנית חדשה
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-4 space-y-3">
        <div className="flex items-center gap-2">
          <div className="flex-1 relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="חיפוש תבנית..."
              className="w-full pr-9 pl-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={() => setShowArchived(prev => !prev)}
            className={`flex items-center gap-1 px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${showArchived ? 'bg-amber-50 border-amber-300 text-amber-700' : 'bg-white border-slate-300 text-slate-600 hover:bg-slate-50'}`}
          >
            <Archive className="w-3.5 h-3.5" />
            {showArchived ? 'הסתר ארכיון' : 'הצג ארכיון'}
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500">מיון:</span>
          {[{ key: 'name', label: 'שם' }, { key: 'last_modified', label: 'עדכון אחרון' }, { key: 'created_at', label: 'תאריך יצירה' }].map(s => (
            <button
              key={s.key}
              onClick={() => toggleSort(s.key)}
              className={`px-2 py-1 rounded-md border transition-colors ${sortBy === s.key ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}
            >
              {s.label} {sortBy === s.key && (sortDir === 'asc' ? '↑' : '↓')}
            </button>
          ))}
        </div>

        {loading && (
          <div className="flex justify-center py-12">
            <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
          </div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
            <AlertTriangle className="w-5 h-5 text-red-500 mx-auto mb-2" />
            <p className="text-sm text-red-700">{error}</p>
            <button onClick={loadFamilies} className="mt-2 text-xs text-blue-600 hover:underline">נסה שוב</button>
          </div>
        )}
        {!loading && !error && families.length === 0 && (
          <div className="text-center py-12 text-slate-400">
            <p className="text-sm">{searchQuery ? 'לא נמצאו תבניות' : 'אין תבניות עדיין'}</p>
          </div>
        )}
        {!loading && !error && families.length > 0 && (
          <div className="space-y-3">
            {families.map(f => (
              <div
                key={f.family_id}
                onClick={() => !f.archived && openEditor(f.latest_id)}
                className={`bg-white rounded-xl border p-4 transition-all ${f.archived ? 'border-slate-200 opacity-60' : 'border-slate-200 cursor-pointer hover:shadow-md hover:-translate-y-0.5'}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-800 truncate">{f.name}</h3>
                      {f.is_default && (
                        <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium flex items-center gap-0.5">
                          <Star className="w-2.5 h-2.5" /> ברירת מחדל
                        </span>
                      )}
                      {f.archived && (
                        <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-medium">ארכיון</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                      <span>גרסה {f.latest_version}</span>
                      <span>{f.stage_count} שלבים</span>
                      <span>{f.versions?.length || 1} גרסאות</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {f.archived ? (
                      <button
                        onClick={(e) => handleArchiveFamily(e, f.family_id, false)}
                        disabled={archiving === f.family_id}
                        className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-md bg-green-50 text-green-700 border border-green-200 hover:bg-green-100"
                      >
                        {archiving === f.family_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Undo2 className="w-3 h-3" />}
                        שחזר
                      </button>
                    ) : (
                      <button
                        onClick={(e) => handleArchiveFamily(e, f.family_id, true)}
                        disabled={archiving === f.family_id}
                        className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-md bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100"
                        title="העבר לארכיון"
                      >
                        {archiving === f.family_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Archive className="w-3 h-3" />}
                      </button>
                    )}
                    {!f.archived && <ChevronLeft className="w-4 h-4 text-slate-400" />}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminQCTemplatesPage;
