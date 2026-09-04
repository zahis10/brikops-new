import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { spareTilesService } from '../services/api';
import { toast } from 'sonner';
import { ArrowRight, Building2, Check, Loader2, Minus, Plus, Save, SlidersHorizontal, Tag, Users } from 'lucide-react';

const MEASURES = { tiles: 'אריחים', sqm: 'מ"ר' };
const blankProfile = () => ({ clientKey: `profile-${Date.now()}-${Math.random()}`, name: '', targets: {}, assigned_units: 0 });
const categoriesWithClientKeys = (categories) => (categories || []).map((category, index) => ({
  ...category,
  clientKey: `cat-${index}-${category.name}`,
}));

export default function SpareTilesPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState('settings');
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState(null);
  const [assignments, setAssignments] = useState(null);
  const [buildingId, setBuildingId] = useState('');
  const [profileId, setProfileId] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const canWrite = settings?.can_write === true;
  const loadSettings = useCallback(async () => {
    const data = await spareTilesService.getSpareSettings(projectId);
    setSettings(data);
    setDraft({ categories: categoriesWithClientKeys(data.categories), profiles: data.profiles || [], margin_pct: data.margin_pct ?? 10, updated_at: data.updated_at });
    setProfileId(current => current || data.profiles?.[0]?.id || '');
  }, [projectId]);
  const loadAssignments = useCallback(async (id) => {
    const data = await spareTilesService.getSpareAssignments(projectId, id || undefined);
    setAssignments(data);
    if (!id && data.buildings?.[0]) setBuildingId(data.buildings[0].id);
  }, [projectId]);
  const load = useCallback(async () => {
    try { setLoading(true); setError(''); await Promise.all([loadSettings(), loadAssignments()]); }
    catch (err) { setError(err.response?.data?.detail || 'לא ניתן לטעון את נתוני ריצוף הספייר'); }
    finally { setLoading(false); }
  }, [loadAssignments, loadSettings]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (buildingId) loadAssignments(buildingId).catch(() => toast.error('לא ניתן לטעון את הבניין')); }, [buildingId, loadAssignments]);

  const profiles = draft?.profiles || [];
  const savedProfiles = useMemo(
    () => (draft?.profiles || []).filter(profile => profile.id),
    [draft?.profiles]
  );
  const names = useMemo(() => Object.fromEntries((settings?.profiles || []).map(p => [p.id, p.name])), [settings]);
  const baseline = useMemo(() => new Set((assignments?.floors || []).flatMap(f => f.units || []).filter(u => u.spare_profile_id === profileId).map(u => u.id)), [assignments, profileId]);
  const addCount = [...selected].filter(id => !baseline.has(id)).length;
  const removeCount = [...baseline].filter(id => !selected.has(id)).length;

  const updateDraft = (fn) => setDraft(prev => fn(prev));
  const saveSettings = async () => {
    if (!canWrite) return;
    const categories = draft.categories
      .filter(c => c.name.trim())
      .map(({ name, measure }) => ({ name: name.trim(), measure }));
    if (!categories.length) return toast.error('נדרשת לפחות קטגוריה אחת');
    if (categories.length > 20 || draft.profiles.length > 10) return toast.error('חריגה ממספר הקטגוריות או הפרופילים המותר');
    try {
      setSaving(true);
      const payload = {
        categories,
        profiles: draft.profiles.map(({ assigned_units, clientKey, ...p }) => p),
        margin_pct: draft.margin_pct,
        ...(draft.updated_at ? { updated_at: draft.updated_at } : {}),
      };
      const saved = await spareTilesService.saveSpareSettings(projectId, payload);
      setSettings(saved); setDraft({ categories: categoriesWithClientKeys(saved.categories), profiles: saved.profiles || [], margin_pct: saved.margin_pct ?? 10, updated_at: saved.updated_at });
      toast.success('הגדרות ריצוף הספייר נשמרו');
    } catch (err) { toast.error(err.response?.data?.detail || 'השמירה נכשלה'); }
    finally { setSaving(false); }
  };
  const saveAssignments = async () => {
    if (!profileId || !canWrite) return;
    try {
      setSaving(true);
      await spareTilesService.patchSpareProfileUnits(projectId, profileId, { add: [...selected].filter(id => !baseline.has(id)), remove: [...baseline].filter(id => !selected.has(id)) });
      await Promise.all([loadAssignments(buildingId), loadSettings()]);
      toast.success('שיוך הדירות עודכן');
    } catch (err) { toast.error(err.response?.data?.detail || 'עדכון השיוך נכשל'); }
    finally { setSaving(false); }
  };
  const switchProfile = (id) => { setProfileId(id); setSelected(new Set()); };
  useEffect(() => { setSelected(new Set(baseline)); }, [baseline]);
  useEffect(() => {
    if (profileId && !savedProfiles.some(profile => profile.id === profileId)) {
      setProfileId('');
      setSelected(new Set());
    }
  }, [profileId, savedProfiles]);
  if (loading) return <div className="min-h-screen bg-slate-50 p-5" dir="rtl"><div className="max-w-5xl mx-auto space-y-3 animate-pulse"><div className="h-20 bg-slate-200 rounded-2xl" /><div className="h-64 bg-slate-200 rounded-2xl" /></div></div>;
  if (error) return <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6" dir="rtl"><div className="text-center bg-white p-7 rounded-2xl border border-amber-200"><p className="text-slate-700 mb-4">{error}</p><button onClick={load} className="px-4 py-2 bg-amber-500 text-white rounded-lg">נסה שוב</button></div></div>;

  return <main className="min-h-screen bg-[#f4f5f3] pb-24" dir="rtl">
    <header className="bg-[#202d38] text-white border-b-4 border-amber-500">
      <div className="max-w-5xl mx-auto px-4 py-4 flex gap-3 items-center">
        <button onClick={() => navigate(`/projects/${projectId}/dashboard`)} className="p-2 rounded-lg bg-white/10 hover:bg-white/20"><ArrowRight className="w-5 h-5" /></button>
        <div className="flex-1"><p className="text-[11px] text-amber-300 tracking-wide">ניהול מלאי באתר</p><h1 className="text-xl font-bold">ריצוף ספייר</h1></div>
        <span className={`text-xs px-2.5 py-1 rounded-full ${canWrite ? 'bg-amber-400 text-slate-900' : 'bg-slate-600 text-slate-200'}`}>{canWrite ? 'עריכה פעילה' : 'צפייה בלבד — עריכה למנהל פרויקט'}</span>
      </div>
    </header>
    <div className="max-w-5xl mx-auto px-4 pt-5">
      <nav className="grid grid-cols-2 bg-[#e4e8e6] rounded-xl p-1 mb-5">
        <button onClick={() => setTab('settings')} className={`py-2.5 text-sm font-bold rounded-lg transition ${tab === 'settings' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}><SlidersHorizontal className="inline w-4 h-4 ml-1" />הגדרות</button>
        <button onClick={() => setTab('assignments')} className={`py-2.5 text-sm font-bold rounded-lg transition ${tab === 'assignments' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}><Users className="inline w-4 h-4 ml-1" />שיוך דירות</button>
      </nav>
      {tab === 'settings' ? <section className="space-y-4">
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-100"><h2 className="font-bold text-slate-800">קטגוריות מדידה</h2><p className="text-xs text-slate-500 mt-1">היעדים מוגדרים עבור כל פרופיל דירה.</p></div>
          <div className="p-3 space-y-2">{draft.categories.map((cat, i) => <div key={cat.clientKey || `cat-${i}`} className="flex gap-2 items-center bg-slate-50 p-2 rounded-xl">
            {cat.new ? <input disabled={!canWrite} value={cat.name} onChange={e => updateDraft(d => ({ ...d, categories: d.categories.map((c, x) => x === i ? { ...c, name: e.target.value } : c) }))} placeholder="שם קטגוריה" className="flex-1 min-w-0 border rounded-lg px-2 py-2 text-sm" /> : <span className="flex-1 text-sm font-semibold text-slate-700">{cat.name}</span>}
            <select disabled={!canWrite} value={cat.measure} onChange={e => updateDraft(d => ({ ...d, categories: d.categories.map((c, x) => x === i ? { ...c, measure: e.target.value } : c) }))} className="w-28 border rounded-lg py-2 text-xs"><option value="tiles">אריחים</option><option value="sqm">מ"ר</option></select>
            <button disabled={!canWrite || draft.categories.length <= 1} onClick={() => updateDraft(d => ({ ...d, categories: d.categories.filter((_, x) => x !== i) }))} className="p-2 text-slate-400 disabled:opacity-30"><Minus className="w-4 h-4" /></button>
          </div>)}</div>
          <button disabled={!canWrite || draft.categories.length >= 20} onClick={() => updateDraft(d => ({ ...d, categories: [...d.categories, { name: '', measure: 'tiles', new: true, clientKey: `cat-${Date.now()}-${Math.random()}` }] }))} className="m-3 text-sm text-amber-700 font-bold disabled:opacity-40"><Plus className="inline w-4 h-4 ml-1" />הוסף קטגוריה</button>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex justify-between"><div><h2 className="font-bold text-slate-800">פרופילי דירות</h2><p className="text-xs text-slate-500 mt-1">הגדרה מפורשת של יעד לכל סוג דירה.</p></div><span className="text-xs bg-slate-100 text-slate-600 rounded-full px-2 py-1 h-fit">אחר: {settings?.unassigned_units || 0}</span></div>
          <div className="p-3 space-y-3">{profiles.map((profile, pi) => <article key={profile.id || profile.clientKey} className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="p-3 bg-[#fbfcfa] flex gap-2 items-center"><Tag className="w-4 h-4 text-amber-600" /><input disabled={!canWrite} value={profile.name} onChange={e => updateDraft(d => ({ ...d, profiles: d.profiles.map((p, x) => x === pi ? { ...p, name: e.target.value } : p) }))} placeholder="שם הפרופיל" className="flex-1 font-bold bg-transparent min-w-0 outline-none" /><span className="text-[11px] text-slate-500">{profile.assigned_units || 0} דירות</span><button disabled={!canWrite} onClick={() => updateDraft(d => ({ ...d, profiles: d.profiles.filter((_, x) => x !== pi) }))} className="text-slate-400 disabled:opacity-30"><Minus className="w-4 h-4" /></button></div>
            <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">{draft.categories.map(cat => <label key={cat.clientKey || cat.name} className="flex items-center gap-2 text-xs bg-slate-50 p-2 rounded-lg"><span className="flex-1 text-slate-600">{cat.name}<small className="block text-slate-400">{MEASURES[cat.measure]}</small></span><input disabled={!canWrite || !cat.name.trim()} type="number" min="0" max="10000" value={profile.targets?.[cat.name] || ''} onChange={e => updateDraft(d => ({ ...d, profiles: d.profiles.map((p, x) => x === pi ? { ...p, targets: { ...p.targets, [cat.name]: e.target.value === '' ? 0 : Number(e.target.value) } } : p) }))} className="w-20 border rounded-md py-1 text-center" /></label>)}</div>
          </article>)}</div>
          <button disabled={!canWrite || profiles.length >= 10} onClick={() => updateDraft(d => ({ ...d, profiles: [...d.profiles, blankProfile()] }))} className="m-3 text-sm text-amber-700 font-bold disabled:opacity-40"><Plus className="inline w-4 h-4 ml-1" />הוסף פרופיל</button>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4"><div className="font-bold text-slate-800">מקרא</div><div className="mt-3 flex gap-3 text-[11px]"><span className="text-red-700">חסר — להזמין</span><span className="text-amber-700">גבולי</span><span className="text-emerald-700">מספיק</span><span className="text-slate-500">לא הוזן / ללא יעד</span></div></div>
        <button disabled={!canWrite || saving} onClick={saveSettings} className="w-full py-3 rounded-xl bg-[#d78b26] text-white font-bold disabled:opacity-40">{saving ? <Loader2 className="inline w-4 h-4 animate-spin ml-2" /> : <Save className="inline w-4 h-4 ml-2" />}שמור הגדרות</button>
      </section> : <section className="space-y-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-4 grid gap-3 sm:grid-cols-2"><label className="text-xs font-bold text-slate-600">פרופיל<select disabled={!canWrite} value={profileId} onChange={e => switchProfile(e.target.value)} className="mt-1 block w-full border rounded-lg p-2.5"><option value="">בחר פרופיל</option>{savedProfiles.map(p => <option key={p.id} value={p.id}>{p.name || 'פרופיל ללא שם'}</option>)}</select></label><label className="text-xs font-bold text-slate-600">בניין<select disabled={!canWrite} value={buildingId} onChange={e => setBuildingId(e.target.value)} className="mt-1 block w-full border rounded-lg p-2.5">{assignments?.buildings?.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label></div>
        {!profileId ? <div className="text-center p-10 bg-white border rounded-2xl text-slate-500">יש ליצור ולבחור פרופיל לפני שיוך דירות.</div> : (assignments?.floors || []).map(floor => <article key={floor.id} className="bg-white rounded-2xl border border-slate-200 overflow-hidden"><div className="p-3 flex justify-between border-b"><div><h2 className="font-bold text-slate-800">{floor.name}</h2><p className="text-xs text-slate-500">{floor.units?.length || 0} דירות</p></div><button disabled={!canWrite} onClick={() => { const ids = floor.units.map(u => u.id); const all = ids.every(id => selected.has(id)); setSelected(prev => { const next = new Set(prev); ids.forEach(id => all ? next.delete(id) : next.add(id)); return next; }); }} className="text-xs font-bold text-amber-700 disabled:opacity-40">בחר הכל בקומה</button></div><div className="p-3 flex flex-wrap gap-2">{floor.units?.map(unit => { const active = selected.has(unit.id); const label = unit.display_label || unit.unit_no; const assigned = unit.spare_profile_id ? names[unit.spare_profile_id] : null; return <button key={unit.id} disabled={!canWrite} onClick={() => setSelected(prev => { const next = new Set(prev); active ? next.delete(unit.id) : next.add(unit.id); return next; })} className={`min-w-[78px] p-2 rounded-lg border text-right transition ${active ? 'bg-amber-50 border-amber-400 text-amber-900' : 'bg-slate-50 border-slate-200 text-slate-600'} disabled:opacity-70`}><span className="block text-sm font-bold">{active && <Check className="inline w-3.5 h-3.5 ml-1" />}{label}</span><span className="block text-[10px] mt-1 text-slate-500">{assigned || 'אחר'}</span></button>; })}</div></article>)}
        <div className="sticky bottom-3 bg-[#202d38] text-white rounded-xl p-3 flex items-center gap-3 shadow-lg"><Building2 className="w-5 h-5 text-amber-300" /><div className="flex-1 text-xs"><b>{selected.size} נבחרו</b><span className="mr-2 text-emerald-300">+{addCount}</span><span className="mr-2 text-rose-300">−{removeCount}</span></div><button disabled={!canWrite || saving || (!addCount && !removeCount)} onClick={saveAssignments} className="bg-amber-400 text-slate-900 px-3 py-2 rounded-lg text-sm font-bold disabled:opacity-40">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'שמור שיוך'}</button></div>
      </section>}
    </div>
  </main>;
}