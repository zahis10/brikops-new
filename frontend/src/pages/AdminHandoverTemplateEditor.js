import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { templateService } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Loader2, Save, Plus, Trash2, ChevronDown, ChevronUp,
  AlertTriangle, X, GripVertical, Package, LayoutList, FileSignature, Scale
} from 'lucide-react';

const TABS = [
  { key: 'sections', label: 'סעיפי בדיקה', icon: LayoutList },
  { key: 'delivered', label: 'פריטים שנמסרו', icon: Package },
  { key: 'fields', label: 'שדות פרטי נכס', icon: LayoutList },
  { key: 'signatures', label: 'טקסט חתימות', icon: FileSignature },
  { key: 'legal', label: 'נסחים משפטיים', icon: Scale },
];

const TRADES = [
  'אלומיניום', 'דלתות', 'חשמל', 'טיח', 'ריצוף', 'צביעה',
  'אינסטלציה', 'מטבחים', 'שיש', 'ברזל', 'כללי',
];

function TradeCombobox({ value, onChange, suggestions }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState(value || '');
  const wrapRef = useRef(null);

  useEffect(() => { setSearch(value || ''); }, [value]);

  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = suggestions.filter(s =>
    !search || s.includes(search) || search.includes(s)
  );

  const commit = (val) => {
    setSearch(val);
    onChange(val);
    setOpen(false);
  };

  return (
    <div ref={wrapRef} className="relative w-full sm:w-auto sm:min-w-[160px]">
      <input
        type="text"
        value={search}
        onChange={(e) => { setSearch(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => { setTimeout(() => { if (search && search !== value) onChange(search); }, 150); }}
        placeholder="בחר מקצוע..."
        className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 min-h-[40px] focus:outline-none focus:ring-2 focus:ring-purple-500"
      />
      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg">
          {filtered.map(s => (
            <li
              key={s}
              onMouseDown={(e) => { e.preventDefault(); commit(s); }}
              className={`px-3 py-2 text-sm cursor-pointer hover:bg-purple-50 ${s === value ? 'bg-purple-50 font-medium text-purple-700' : 'text-slate-700'}`}
            >
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const genId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

const DEFAULT_SIG_LABELS = {
  manager: 'אני מאשר/ת את חתימתי על פרוטוקול המסירה כמנהל/ת הפרויקט',
  tenant: 'אני מאשר/ת את חתימתי על פרוטוקול המסירה כרוכש/ת ראשי/ת',
  tenant_2: 'אני מאשר/ת את חתימתי על פרוטוקול המסירה כרוכש/ת נוסף/ת',
  contractor_rep: 'אני מאשר/ת את חתימתי על פרוטוקול המסירה כנציג/ת הקבלן',
};

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
  const [activeTab, setActiveTab] = useState('sections');
  const [defaultDeliveredItems, setDefaultDeliveredItems] = useState([]);
  const [defaultPropertyFields, setDefaultPropertyFields] = useState([]);
  const [signatureLabels, setSignatureLabels] = useState({ ...DEFAULT_SIG_LABELS });
  const [legalSections, setLegalSections] = useState([]);
  const [legalDeleteConfirm, setLegalDeleteConfirm] = useState(null);

  const allTrades = useMemo(() => {
    const dynamic = new Set(TRADES);
    sections.forEach(s => s.items?.forEach(it => { if (it.trade) dynamic.add(it.trade); }));
    return [...dynamic];
  }, [sections]);

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

      setDefaultDeliveredItems(tpl.default_delivered_items || []);
      setDefaultPropertyFields(tpl.default_property_fields || []);
      setSignatureLabels({ ...DEFAULT_SIG_LABELS, ...(tpl.signature_labels || {}) });
      setLegalSections(tpl.legal_sections || []);

      const expanded = {};
      const secs = tpl.sections || tpl.stages || [];
      secs.forEach(s => { expanded[s.id] = true; });
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
    for (let i = 0; i < legalSections.length; i++) {
      const ls = legalSections[i];
      if (!(ls.title || '').trim()) {
        toast.error(`נסח משפטי ${i + 1}: כותרת נדרשת`);
        return;
      }
      if (!(ls.body || '').trim()) {
        toast.error(`נסח משפטי ${i + 1}: תוכן נדרש`);
        return;
      }
      if (ls.requires_signature && !ls.signature_role) {
        toast.error(`נסח משפטי ${i + 1}: יש לבחור חותם`);
        return;
      }
      if (!ls.applies_to || ls.applies_to.length === 0) {
        toast.error(`נסח משפטי ${i + 1}: יש לבחור לפחות סוג אחד`);
        return;
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

      const payload = {
        name: name.trim(),
        type: 'handover',
        sections: orderedSections,
      };
      if (defaultDeliveredItems.length > 0) {
        payload.default_delivered_items = defaultDeliveredItems;
      }
      if (defaultPropertyFields.length > 0) {
        payload.default_property_fields = defaultPropertyFields;
      }
      payload.signature_labels = {
        manager: signatureLabels.manager || '',
        tenant: signatureLabels.tenant || '',
        tenant_2: signatureLabels.tenant_2 || '',
        contractor_rep: signatureLabels.contractor_rep || '',
      };
      payload.legal_sections = legalSections.map((ls, i) => ({
        ...(ls.id ? { id: ls.id } : {}),
        title: (ls.title || '').trim(),
        body: (ls.body || '').trim(),
        requires_signature: !!ls.requires_signature,
        signature_role: ls.requires_signature ? ls.signature_role : null,
        requires_both_tenants: !!ls.requires_both_tenants,
        applies_to: ls.applies_to || ['initial', 'final'],
        order: i + 1,
      }));
      await templateService.update(templateId, payload);
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

  const collapseAll = () => {
    const collapsed = {};
    sections.forEach(s => { collapsed[s.id] = false; });
    setExpandedSections(collapsed);
  };

  const expandAll = () => {
    const expanded = {};
    sections.forEach(s => { expanded[s.id] = true; });
    setExpandedSections(expanded);
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
  const allExpanded = sections.length > 0 && sections.every(s => expandedSections[s.id]);

  return (
    <div className="min-h-screen bg-slate-50 pb-24" dir="rtl">
      <header className="bg-gradient-to-bl from-[#1e1b4b] to-[#312e81] text-white sticky top-0 z-40 shadow-md">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => navigate('/admin/qc-templates')}
            className="p-2 bg-white/[0.07] border border-white/10 rounded-xl hover:bg-white/[0.14] transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-base font-extrabold">עריכת תבנית מסירה</h1>
            <p className="text-[11px] text-indigo-300">{sections.length} סקשנים · {totalItems} פריטים</p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-white text-indigo-900 rounded-xl text-sm font-bold hover:bg-indigo-50 transition-colors disabled:opacity-50 min-h-[44px]"
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
            <label className="text-xs font-semibold text-slate-500 mb-1.5 block">שם תבנית</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="תבנית מסירה — סטנדרטית"
              className="w-full text-base border border-slate-200 rounded-xl px-3.5 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded-lg font-medium">תבנית מסירה</span>
            {templateData?.family_id && <span>משפחה: {templateData.family_id.slice(0, 8)}</span>}
            {templateData?.version && <span>גרסה: {templateData.version}</span>}
          </div>
        </div>

        <div className="flex gap-1 overflow-x-auto pb-1 -mx-1 px-1">
          {TABS.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors min-h-[40px] ${
                  activeTab === tab.key
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {activeTab === 'delivered' && (
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-700">פריטים שנמסרו ({defaultDeliveredItems.length})</h3>
            </div>
            <p className="text-xs text-slate-400">פריטים שייכנסו אוטומטית לכל פרוטוקול חדש שנוצר מתבנית זו.</p>
            <div className="space-y-2">
              {defaultDeliveredItems.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2 border border-slate-100 rounded-lg bg-slate-50/50">
                  <span className="text-xs text-slate-400 font-bold w-5 text-center">{idx + 1}</span>
                  <input
                    type="text"
                    value={item.name}
                    onChange={(e) => setDefaultDeliveredItems(prev => prev.map((it, i) => i === idx ? { ...it, name: e.target.value } : it))}
                    placeholder="שם פריט"
                    className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white min-h-[40px]"
                  />
                  <button
                    onClick={() => setDefaultDeliveredItems(prev => prev.filter((_, i) => i !== idx))}
                    className="p-1.5 text-red-400 hover:text-red-600 min-h-[36px] min-w-[36px] flex items-center justify-center"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={() => setDefaultDeliveredItems(prev => [...prev, { name: '', quantity: null, notes: '' }])}
              className="w-full py-2.5 text-sm text-purple-600 hover:bg-purple-50 flex items-center gap-1.5 justify-center rounded-xl border border-dashed border-purple-200 transition-colors font-medium"
            >
              <Plus className="w-4 h-4" />
              הוסף פריט
            </button>
          </div>
        )}

        {activeTab === 'fields' && (
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-700">שדות פרטי נכס ({defaultPropertyFields.length})</h3>
            </div>
            <p className="text-xs text-slate-400">שדות שיופיעו בטופס פרטי הנכס בכל פרוטוקול חדש.</p>
            <div className="space-y-2">
              {defaultPropertyFields.map((field, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2 border border-slate-100 rounded-lg bg-slate-50/50">
                  <span className="text-xs text-slate-400 font-bold w-5 text-center">{idx + 1}</span>
                  <input
                    type="text"
                    value={field.label}
                    onChange={(e) => setDefaultPropertyFields(prev => prev.map((f, i) => i === idx ? { ...f, label: e.target.value } : f))}
                    placeholder="תווית"
                    className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white min-h-[40px]"
                  />
                  <button
                    onClick={() => setDefaultPropertyFields(prev => prev.filter((_, i) => i !== idx))}
                    className="p-1.5 text-red-400 hover:text-red-600 min-h-[36px] min-w-[36px] flex items-center justify-center"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={() => setDefaultPropertyFields(prev => [...prev, { key: `field_${Date.now()}`, label: '' }])}
              className="w-full py-2.5 text-sm text-purple-600 hover:bg-purple-50 flex items-center gap-1.5 justify-center rounded-xl border border-dashed border-purple-200 transition-colors font-medium"
            >
              <Plus className="w-4 h-4" />
              הוסף שדה
            </button>
          </div>
        )}

        {activeTab === 'signatures' && (
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
            <div>
              <h3 className="text-sm font-bold text-slate-700">טקסט חתימות</h3>
              <p className="text-xs text-slate-400 mt-1">טקסט שיופיע מעל כפתור החתימה של כל תפקיד. ניתן לערוך גם בכל פרוטוקול בנפרד.</p>
            </div>
            {[
              { key: 'manager', label: 'מנהל פרויקט' },
              { key: 'tenant', label: 'רוכש/ת ראשי/ת' },
              { key: 'tenant_2', label: 'רוכש/ת נוסף/ת', optional: true },
              { key: 'contractor_rep', label: 'נציג קבלן', optional: true },
            ].map(role => (
              <div key={role.key} className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-500">
                  {role.label}
                  {role.optional && <span className="text-slate-400 font-normal mr-1">(אופציונלי)</span>}
                </label>
                <textarea
                  value={signatureLabels[role.key] || ''}
                  onChange={(e) => setSignatureLabels(prev => ({ ...prev, [role.key]: e.target.value }))}
                  placeholder={`טקסט הצהרה עבור ${role.label}...`}
                  rows={2}
                  className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
                />
              </div>
            ))}
          </div>
        )}

        {activeTab === 'legal' && (
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-700">נסחים משפטיים ({legalSections.length})</h3>
            </div>
            <p className="text-xs text-slate-400">נסחים משפטיים שייכללו בפרוטוקולי מסירה שנוצרים מתבנית זו. ניתן לסנן לפי סוג מסירה.</p>
            {legalSections.length === 0 ? (
              <div className="text-center py-6 space-y-2">
                <p className="text-sm text-slate-400">לא הוגדרו נסחים משפטיים.</p>
                <p className="text-xs text-slate-400">הוסיפו נסחים כדי שיופיעו בפרוטוקולי מסירה.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {legalSections.map((ls, idx) => (
                  <div key={ls.id || idx} className="border border-slate-200 rounded-xl p-4 space-y-3 bg-slate-50/50">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-500">נסח {idx + 1}</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => {
                            if (idx === 0) return;
                            setLegalSections(prev => {
                              const next = [...prev];
                              [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
                              return next;
                            });
                          }}
                          disabled={idx === 0}
                          className="p-1 hover:bg-slate-200 rounded disabled:opacity-30"
                        >
                          <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
                        </button>
                        <button
                          onClick={() => {
                            if (idx >= legalSections.length - 1) return;
                            setLegalSections(prev => {
                              const next = [...prev];
                              [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
                              return next;
                            });
                          }}
                          disabled={idx >= legalSections.length - 1}
                          className="p-1 hover:bg-slate-200 rounded disabled:opacity-30"
                        >
                          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
                        </button>
                        {legalDeleteConfirm === idx ? (
                          <div className="flex items-center gap-1 mr-1">
                            <button
                              onClick={() => {
                                setLegalSections(prev => prev.filter((_, i) => i !== idx));
                                setLegalDeleteConfirm(null);
                              }}
                              className="text-[10px] text-red-600 hover:text-red-800 font-medium px-2 py-0.5 bg-red-50 rounded"
                            >
                              מחק
                            </button>
                            <button
                              onClick={() => setLegalDeleteConfirm(null)}
                              className="text-[10px] text-slate-500 px-2 py-0.5"
                            >
                              ביטול
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setLegalDeleteConfirm(idx)}
                            className="p-1 hover:bg-red-100 rounded text-slate-400 hover:text-red-500"
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
                        value={ls.title}
                        onChange={(e) => setLegalSections(prev => prev.map((s, i) => i === idx ? { ...s, title: e.target.value } : s))}
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                        dir="rtl"
                        placeholder="שם הנסח"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-600">תוכן</label>
                      <textarea
                        value={ls.body}
                        onChange={(e) => setLegalSections(prev => prev.map((s, i) => i === idx ? { ...s, body: e.target.value } : s))}
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300 leading-relaxed min-h-[80px]"
                        dir="rtl"
                        placeholder="תוכן הנסח המשפטי..."
                      />
                    </div>

                    <div className="flex items-center gap-4 flex-wrap">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={ls.requires_signature}
                          onChange={(e) => setLegalSections(prev => prev.map((s, i) => i === idx ? { ...s, requires_signature: e.target.checked, ...(e.target.checked ? {} : { signature_role: null }) } : s))}
                          className="rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                        />
                        <span className="text-sm text-slate-700">דורש חתימה</span>
                      </label>

                      {ls.requires_signature && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-500">חותם:</span>
                          <select
                            value={ls.signature_role || ''}
                            onChange={(e) => setLegalSections(prev => prev.map((s, i) => i === idx ? { ...s, signature_role: e.target.value || null, ...(!['tenant', 'tenant_2'].includes(e.target.value) ? { requires_both_tenants: false } : {}) } : s))}
                            className="text-sm border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-purple-300"
                          >
                            <option value="">— בחר —</option>
                            <option value="manager">מנהל פרויקט / מפקח</option>
                            <option value="tenant">רוכש/ת ראשי/ת</option>
                            <option value="tenant_2">רוכש/ת נוסף/ת</option>
                            <option value="contractor_rep">נציג קבלן</option>
                          </select>
                        </div>
                      )}
                      {ls.requires_signature && ['tenant', 'tenant_2'].includes(ls.signature_role) && (
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={!!ls.requires_both_tenants}
                            onChange={(e) => setLegalSections(prev => prev.map((s, i) => i === idx ? { ...s, requires_both_tenants: e.target.checked } : s))}
                            className="rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                          />
                          <span className="text-sm text-slate-700">דורש חתימת שני הרוכשים</span>
                        </label>
                      )}
                    </div>

                    <div className="flex items-center gap-4">
                      <span className="text-xs text-slate-500">חל על:</span>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={(ls.applies_to || []).includes('initial')}
                          onChange={(e) => {
                            setLegalSections(prev => prev.map((s, i) => {
                              if (i !== idx) return s;
                              const cur = s.applies_to || [];
                              const next = e.target.checked ? [...new Set([...cur, 'initial'])] : cur.filter(t => t !== 'initial');
                              return next.length > 0 ? { ...s, applies_to: next } : s;
                            }));
                          }}
                          className="rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                        />
                        <span className="text-sm text-slate-700">ראשונית</span>
                      </label>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={(ls.applies_to || []).includes('final')}
                          onChange={(e) => {
                            setLegalSections(prev => prev.map((s, i) => {
                              if (i !== idx) return s;
                              const cur = s.applies_to || [];
                              const next = e.target.checked ? [...new Set([...cur, 'final'])] : cur.filter(t => t !== 'final');
                              return next.length > 0 ? { ...s, applies_to: next } : s;
                            }));
                          }}
                          className="rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                        />
                        <span className="text-sm text-slate-700">חזקה</span>
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={() => setLegalSections(prev => [...prev, { id: genId('legal'), title: '', body: '', requires_signature: false, signature_role: null, requires_both_tenants: false, applies_to: ['initial', 'final'], order: prev.length + 1 }])}
              className="w-full py-2.5 text-sm text-purple-600 hover:bg-purple-50 flex items-center gap-1.5 justify-center rounded-xl border border-dashed border-purple-200 transition-colors font-medium"
            >
              <Plus className="w-4 h-4" />
              הוסף נסח משפטי
            </button>
          </div>
        )}

        {activeTab === 'sections' && (
        <>
        <div className="flex items-center justify-between px-1">
          <h2 className="text-sm font-bold text-slate-600">סקשנים ({sections.length})</h2>
          <button
            onClick={allExpanded ? collapseAll : expandAll}
            className="text-xs text-purple-600 hover:text-purple-700 font-medium"
          >
            {allExpanded ? 'כווץ הכל' : 'הרחב הכל'}
          </button>
        </div>

        {sections.map((section, sIdx) => {
          const isExpanded = expandedSections[section.id];
          return (
            <div key={section.id} className="rounded-xl border border-slate-200 overflow-hidden shadow-sm">
              <div
                className="flex items-center gap-2.5 px-4 py-3.5 bg-purple-50 border-b border-purple-100 cursor-pointer"
                onClick={() => toggleSection(section.id)}
              >
                <GripVertical className="w-5 h-5 text-purple-300 flex-shrink-0" />
                <span className="text-xs bg-purple-200 text-purple-800 px-2 py-0.5 rounded-lg font-bold flex-shrink-0">{sIdx + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-purple-900 truncate">{section.name || 'סקשן חדש'}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[11px] text-purple-500 font-medium">{section.items.length} פריטים</span>
                    {section.visible_in_initial && (
                      <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-md font-medium">ראשונית</span>
                    )}
                    {section.visible_in_final && (
                      <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-md font-medium">חזקה</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-0.5">
                  <button
                    onClick={(e) => { e.stopPropagation(); moveSectionUp(sIdx); }}
                    disabled={sIdx === 0}
                    className="p-1.5 text-purple-400 hover:text-purple-700 disabled:opacity-30 min-h-[36px] min-w-[36px] flex items-center justify-center"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); moveSectionDown(sIdx); }}
                    disabled={sIdx === sections.length - 1}
                    className="p-1.5 text-purple-400 hover:text-purple-700 disabled:opacity-30 min-h-[36px] min-w-[36px] flex items-center justify-center"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteConfirm(sIdx); }}
                    className="p-1.5 text-red-400 hover:text-red-600 min-h-[36px] min-w-[36px] flex items-center justify-center"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {isExpanded ? <ChevronUp className="w-5 h-5 text-purple-400" /> : <ChevronDown className="w-5 h-5 text-purple-400" />}
              </div>

              {deleteConfirm === sIdx && (
                <div className="px-4 py-2.5 bg-red-50 border-b border-red-100 flex items-center gap-2">
                  <span className="text-sm text-red-700">למחוק את הסקשן "{section.name || 'סקשן חדש'}"?</span>
                  <button onClick={() => removeSection(sIdx)} className="text-xs bg-red-500 text-white px-3 py-1.5 rounded-lg hover:bg-red-600 font-medium">מחק</button>
                  <button onClick={() => setDeleteConfirm(null)} className="text-xs text-slate-500 hover:text-slate-700 font-medium">ביטול</button>
                </div>
              )}

              {isExpanded && (
                <div className="bg-white p-4 space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-slate-500 mb-1.5 block">שם סקשן</label>
                      <input
                        type="text"
                        value={section.name}
                        onChange={(e) => updateSectionField(sIdx, 'name', e.target.value)}
                        placeholder="כניסה לדירה"
                        className="w-full text-sm font-medium border border-slate-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                    </div>
                    <div className="flex items-end gap-4 pb-0.5">
                      <label className="flex items-center gap-2 cursor-pointer min-h-[44px]">
                        <input
                          type="checkbox"
                          checked={section.visible_in_initial}
                          onChange={(e) => updateSectionField(sIdx, 'visible_in_initial', e.target.checked)}
                          className="w-4 h-4 rounded border-slate-300 text-blue-500 focus:ring-blue-500"
                        />
                        <span className="text-sm text-slate-600">ראשונית</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer min-h-[44px]">
                        <input
                          type="checkbox"
                          checked={section.visible_in_final}
                          onChange={(e) => updateSectionField(sIdx, 'visible_in_final', e.target.checked)}
                          className="w-4 h-4 rounded border-slate-300 text-green-500 focus:ring-green-500"
                        />
                        <span className="text-sm text-slate-600">חזקה</span>
                      </label>
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-slate-500">פריטים ({section.items.length})</span>
                    </div>
                    <div className="space-y-1.5">
                      {section.items.map((item, iIdx) => (
                        <div key={item.id} className="flex items-start gap-2 p-3 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition-colors min-h-[56px]">
                          <span className="text-xs text-slate-400 font-bold mt-2.5 w-5 text-center flex-shrink-0">{iIdx + 1}</span>
                          <div className="flex-1 min-w-0 space-y-2">
                            <input
                              type="text"
                              value={item.name}
                              onChange={(e) => updateItemField(sIdx, iIdx, 'name', e.target.value)}
                              placeholder="שם פריט"
                              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 bg-white"
                              style={{ minHeight: '40px' }}
                            />
                            <TradeCombobox
                              value={item.trade}
                              onChange={(val) => updateItemField(sIdx, iIdx, 'trade', val)}
                              suggestions={allTrades}
                            />
                          </div>
                          <div className="flex flex-col items-center gap-0.5 pt-1">
                            <button
                              onClick={() => moveItemUp(sIdx, iIdx)}
                              disabled={iIdx === 0}
                              className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30 min-h-[32px] min-w-[32px] flex items-center justify-center"
                            >
                              <ChevronUp className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => moveItemDown(sIdx, iIdx)}
                              disabled={iIdx === section.items.length - 1}
                              className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30 min-h-[32px] min-w-[32px] flex items-center justify-center"
                            >
                              <ChevronDown className="w-3.5 h-3.5" />
                            </button>
                          </div>
                          <button
                            onClick={() => removeItem(sIdx, iIdx)}
                            className="p-1.5 text-red-400 hover:text-red-600 mt-1 min-h-[36px] min-w-[36px] flex items-center justify-center"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={() => addItem(sIdx)}
                      className="w-full mt-2 py-2.5 text-sm text-purple-600 hover:bg-purple-50 flex items-center gap-1.5 justify-center rounded-xl border border-dashed border-purple-200 transition-colors font-medium"
                    >
                      <Plus className="w-4 h-4" />
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
          className="w-full py-3.5 border-2 border-dashed border-purple-300 rounded-xl text-sm text-purple-600 font-bold hover:bg-purple-50 hover:border-purple-400 transition-colors flex items-center gap-1.5 justify-center"
        >
          <Plus className="w-5 h-5" />
          הוסף סקשן
        </button>
        </>
        )}

        <div className="pt-2 pb-8">
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full py-3.5 bg-gradient-to-l from-purple-600 to-indigo-600 text-white rounded-xl text-sm font-bold hover:from-purple-700 hover:to-indigo-700 transition-all disabled:opacity-50 flex items-center gap-2 justify-center shadow-lg shadow-purple-500/20 min-h-[48px]"
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
