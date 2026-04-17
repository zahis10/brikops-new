import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { unitService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import { tCategory } from '../i18n';
import NewDefectModal from '../components/NewDefectModal';
import FilterDrawer from '../components/FilterDrawer';
import ExportModal from '../components/ExportModal';
import UnitTypeEditModal, { TAG_MAP } from '../components/UnitTypeEditModal';
import StatCard from '../components/StatCard';
import StatusPill from '../components/StatusPill';
import CategoryPill from '../components/CategoryPill';
import Breadcrumbs from '../components/Breadcrumbs';
import {
  ArrowRight, Loader2, AlertTriangle, CheckCircle2,
  ChevronDown, ChevronUp, ShieldAlert, Image as ImageIcon, Plus,
  SlidersHorizontal, Search, X, Download, Pencil, Save, Info, Trash2
} from 'lucide-react';

const APARTMENT_DEFAULT_FILTERS = {
  status: 'all',
  category: 'all',
  company: 'all',
  assignee: 'all',
  created_by: 'all',
};

const STATUS_LABELS = {
  open: { label: 'פתוח', color: 'bg-red-100 text-red-700', key: 'open' },
  assigned: { label: 'שויך', color: 'bg-orange-100 text-orange-700', key: 'open' },
  in_progress: { label: 'בביצוע', color: 'bg-blue-100 text-blue-700', key: 'in_progress' },
  pending_contractor_proof: { label: 'ממתין להוכחת קבלן', color: 'bg-orange-100 text-orange-700', key: 'in_progress' },
  pending_manager_approval: { label: 'ממתין לאישור מנהל', color: 'bg-indigo-100 text-indigo-700', key: 'in_progress' },
  returned_to_contractor: { label: 'הוחזר לקבלן', color: 'bg-rose-100 text-rose-700', key: 'in_progress' },
  waiting_verify: { label: 'ממתין לאימות', color: 'bg-purple-100 text-purple-700', key: 'in_progress' },
  closed: { label: 'סגור', color: 'bg-green-100 text-green-700', key: 'closed' },
  reopened: { label: 'נפתח מחדש', color: 'bg-amber-100 text-amber-700', key: 'open' },
};

const STATUS_FILTER_OPTIONS = [
  { value: 'open', label: 'פתוחים' },
  { value: 'in_progress', label: 'בטיפול' },
  { value: 'closed', label: 'סגורים' },
];

const PRIORITY_CONFIG = {
  low: { label: 'נמוך', color: 'text-slate-500' },
  medium: { label: 'בינוני', color: 'text-blue-600' },
  high: { label: 'גבוה', color: 'text-amber-600' },
  critical: { label: 'קריטי', color: 'text-red-600' },
};

const STATUS_LABEL_MAP = {
  open: 'פתוחים',
  in_progress: 'בטיפול',
  closed: 'סגורים',
};

const ApartmentDashboardPage = () => {
  const { projectId, unitId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, features } = useAuth();

  const [unitData, setUnitData] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [filters, setFilters] = useState({ ...APARTMENT_DEFAULT_FILTERS });
  const [searchQuery, setSearchQuery] = useState('');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(true);
  const [blockingOpen, setBlockingOpen] = useState(false);
  const [editingUnit, setEditingUnit] = useState(null);
  const [showDefectModal, setShowDefectModal] = useState(false);
  const [spareTilesOpen, setSpareTilesOpen] = useState(false);
  const [spareTilesEditing, setSpareTilesEditing] = useState(false);
  const [spareTilesEntries, setSpareTilesEntries] = useState([]);
  const [spareTilesSaving, setSpareTilesSaving] = useState(false);
  const canCreateDefect = user && (user.role === 'project_manager' || user.role === 'management_team');
  const flagChecked = !!features?.defects_v2;

  useEffect(() => {
    if (features && !features.defects_v2) {
      navigate(`/projects/${projectId}/units/${unitId}/tasks`, { replace: true });
    }
  }, [features, projectId, unitId, navigate]);

  const loadUnit = useCallback(async () => {
    try {
      setLoading(true);
      const data = await unitService.get(unitId);
      setUnitData(data);
    } catch (err) {
      toast.error('שגיאה בטעינת פרטי דירה');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [unitId]);

  const loadTasks = useCallback(async () => {
    try {
      setTasksLoading(true);
      const data = await unitService.getTasks(unitId);
      setTasks(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error('שגיאה בטעינת ליקויים');
      console.error(err);
    } finally {
      setTasksLoading(false);
    }
  }, [unitId]);

  useEffect(() => {
    if (flagChecked) {
      loadUnit();
      loadTasks();
    }
  }, [flagChecked, loadUnit, loadTasks]);

  const SPARE_TILES_BASE_TYPES = useMemo(() => [
    'ריצוף יבש', 'ריצוף מרפסות', 'חיפוי אמבטיות', 'ריצוף אמבטיות', 'חיפוי מטבח',
  ], []);

  const startSpareTilesEdit = useCallback(() => {
    const u = unitData?.unit;
    const saved = Array.isArray(u?.spare_tiles) ? u.spare_tiles : [];
    const savedMap = {};
    saved.forEach(e => { savedMap[e.type] = e; });
    const merged = SPARE_TILES_BASE_TYPES.map(bt => ({
      type: bt,
      count: savedMap[bt] ? String(savedMap[bt].count) : '0',
      notes: savedMap[bt]?.notes || '',
      isBase: true,
    }));
    saved.forEach(e => {
      if (!SPARE_TILES_BASE_TYPES.includes(e.type)) {
        merged.push({ type: e.type, count: String(e.count), notes: e.notes || '', isBase: false });
      }
    });
    setSpareTilesEntries(merged);
    setSpareTilesEditing(true);
  }, [unitData, SPARE_TILES_BASE_TYPES]);

  const spareTilesStatus = useMemo(() => {
    const u = unitData?.unit;
    const tiles = u?.spare_tiles;
    if (!Array.isArray(tiles) || tiles.length === 0) return 'not_updated';
    const totalCount = tiles.reduce((s, e) => s + (e.count || 0), 0);
    if (totalCount === 0) return 'none';
    const typesWithCount = tiles.filter(e => e.count > 0).length;
    return { status: 'has_tiles', totalCount, typesWithCount };
  }, [unitData]);

  const saveSpareTiles = useCallback(async () => {
    try {
      setSpareTilesSaving(true);
      const payload = [];
      for (const entry of spareTilesEntries) {
        const count = parseInt(entry.count, 10);
        if (isNaN(count) || count < 0) {
          toast.error('כמות חייבת להיות מספר חיובי');
          return;
        }
        if (entry.isBase || count > 0 || entry.notes.trim()) {
          payload.push({ type: entry.type, count: isNaN(count) ? 0 : count, notes: entry.notes.trim() });
        }
      }
      await unitService.updateSpareTiles(unitId, payload);
      const refreshed = await unitService.get(unitId);
      setUnitData(refreshed);
      setSpareTilesEditing(false);
      toast.success('ריצוף ספייר עודכן');
    } catch (err) {
      toast.error('שגיאה בשמירת ריצוף ספייר');
      console.error(err);
    } finally {
      setSpareTilesSaving(false);
    }
  }, [unitId, spareTilesEntries]);

  useEffect(() => {
    setFilters(prev => {
      const next = { ...prev };
      let changed = false;
      if (prev.category !== 'all' && !tasks.some(t => t.category === prev.category)) {
        next.category = 'all';
        changed = true;
      }
      if (prev.company !== 'all' && !tasks.some(t => t.company_id === prev.company)) {
        next.company = 'all';
        changed = true;
      }
      if (prev.assignee !== 'all' && !tasks.some(t => t.assignee_id === prev.assignee)) {
        next.assignee = 'all';
        changed = true;
      }
      if (prev.created_by !== 'all' && !tasks.some(t => t.created_by === prev.created_by)) {
        next.created_by = 'all';
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [tasks]);

  const filterSections = useMemo(() => {
    const cats = {};
    const companies = {};
    const assignees = {};
    const creators = {};

    tasks.forEach(t => {
      if (t.category) cats[t.category] = tCategory(t.category);
      if (t.company_id) {
        companies[t.company_id] = t.company_name || t.assignee_company_name || t.company_id.slice(0, 8);
      }
      if (t.assignee_id) {
        assignees[t.assignee_id] = t.assignee_name || t.assigned_to_name || t.assignee_id.slice(0, 8);
      }
      if (t.created_by) {
        creators[t.created_by] = t.created_by_name || t.created_by.slice(0, 8);
      }
    });

    return [
      { key: 'status', label: 'סטטוס', options: STATUS_FILTER_OPTIONS },
      { key: 'category', label: 'תחום', options: Object.entries(cats).map(([v, l]) => ({ value: v, label: l })) },
      { key: 'company', label: 'חברה', options: Object.entries(companies).map(([v, l]) => ({ value: v, label: l })) },
      { key: 'assignee', label: 'אחראי', options: Object.entries(assignees).map(([v, l]) => ({ value: v, label: l })) },
      { key: 'created_by', label: 'נוצר על ידי', options: Object.entries(creators).map(([v, l]) => ({ value: v, label: l })) },
    ];
  }, [tasks]);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.status !== 'all') count++;
    if (filters.category !== 'all') count++;
    if (filters.company !== 'all') count++;
    if (filters.assignee !== 'all') count++;
    if (filters.created_by !== 'all') count++;
    if (searchQuery.trim()) count++;
    return count;
  }, [filters, searchQuery]);

  const filterSummaryText = useMemo(() => {
    const parts = [];
    filterSections.forEach(section => {
      const val = filters[section.key];
      if (val && val !== 'all') {
        const opt = section.options.find(o => o.value === val);
        parts.push(`${section.label}: ${opt?.label || val}`);
      }
    });
    if (searchQuery.trim()) parts.push(`חיפוש: "${searchQuery.trim()}"`);

    if (parts.length === 0) return '';
    if (parts.length <= 3) return parts.join(' · ');
    return parts.slice(0, 2).join(' · ') + ` · עוד ${parts.length - 2}`;
  }, [filters, searchQuery, filterSections]);

  if (!flagChecked || loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  if (!unitData) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-slate-500">דירה לא נמצאה</p>
        <button onClick={() => navigate(`/projects/${projectId}/control`)} className="text-amber-600 hover:text-amber-700 font-medium">
          חזרה
        </button>
      </div>
    );
  }

  const { unit, floor, building, project, kpi } = unitData;
  const effectiveLabel = unit.effective_label || unit.unit_no || '';

  const openCount = (kpi?.open ?? 0) + (kpi?.reopened ?? 0);
  const inProgressCount = (kpi?.in_progress ?? 0) + (kpi?.waiting_verify ?? 0);
  const closedCount = kpi?.closed ?? 0;
  const totalCount = openCount + inProgressCount + closedCount;

  const blockingTasks = tasks.filter(t => t.priority === 'critical' || t.priority === 'high');
  const blockingCount = blockingTasks.length;

  const getSeverityBadge = () => {
    if (totalCount === 0) return { label: 'תקין', color: 'bg-green-100 text-green-700' };
    const ratio = openCount / totalCount;
    if (ratio >= 0.5) return { label: 'חמור', color: 'bg-red-100 text-red-700' };
    if (ratio >= 0.2) return { label: 'דורש טיפול', color: 'bg-amber-100 text-amber-700' };
    return { label: 'מצב טוב', color: 'bg-green-100 text-green-700' };
  };

  const severity = getSeverityBadge();

  const searchLower = searchQuery.trim().toLowerCase();
  const baseFilteredTasks = tasks.filter(t => {
    if (filters.category !== 'all' && t.category !== filters.category) return false;
    if (filters.company !== 'all' && t.company_id !== filters.company) return false;
    if (filters.assignee !== 'all' && t.assignee_id !== filters.assignee) return false;
    if (filters.created_by !== 'all' && t.created_by !== filters.created_by) return false;
    if (searchLower && !(
      (t.title || '').toLowerCase().includes(searchLower) ||
      (t.description || '').toLowerCase().includes(searchLower)
    )) return false;
    return true;
  });

  const filterCounts = {
    all: baseFilteredTasks.length,
    open: baseFilteredTasks.filter(t => STATUS_LABELS[t.status]?.key === 'open').length,
    in_progress: baseFilteredTasks.filter(t => STATUS_LABELS[t.status]?.key === 'in_progress').length,
    closed: baseFilteredTasks.filter(t => STATUS_LABELS[t.status]?.key === 'closed').length,
  };

  const filteredTasks = filters.status === 'all'
    ? baseFilteredTasks
    : baseFilteredTasks.filter(t => STATUS_LABELS[t.status]?.key === filters.status);

  const hasActiveFilters = activeFilterCount > 0;

  return (
    <div className={`min-h-screen bg-slate-50 ${canCreateDefect ? 'pb-24' : 'pb-6'}`} dir="rtl">
      <div className="bg-slate-50">
        <div className="max-w-lg mx-auto bg-gradient-to-l from-amber-500 to-amber-600 text-white rounded-b-2xl px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                const navState = location.state;
                if (navState?.from === 'unit-home') {
                  navigate(`/projects/${projectId}/units/${unitId}`);
                } else if (navState?.buildingId) {
                  navigate(`/projects/${projectId}/buildings/${navState.buildingId}/defects`);
                } else {
                  navigate(`/projects/${projectId}/units/${unitId}`);
                }
              }}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold truncate">{formatUnitLabel(effectiveLabel)}</h1>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${severity.color}`}>
                  {severity.label}
                </span>
                {TAG_MAP[unit.unit_type_tag] && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-white/20 text-white">
                    {TAG_MAP[unit.unit_type_tag].label}
                  </span>
                )}
                <button
                  onClick={() => setEditingUnit(unit)}
                  className="p-1 hover:bg-white/20 rounded-lg transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5 text-white" />
                </button>
              </div>
              <Breadcrumbs
                items={[project?.name, building?.name, floor?.name]}
                className="text-amber-100"
              />
              {unit.unit_note && (
                <p className="text-[11px] text-amber-100/80 mt-0.5 truncate">{unit.unit_note}</p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 -mt-2">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button
            onClick={() => setSummaryOpen(!summaryOpen)}
            className="w-full flex items-center justify-between p-3 text-right"
          >
            <span className="text-sm font-semibold text-slate-700">סיכום מהיר</span>
            {summaryOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {summaryOpen && (
            <div className="px-4 pb-4">
              <div className="grid grid-cols-3 divide-x divide-slate-100" dir="ltr">
                <StatCard label="פתוחות" value={openCount} />
                <StatCard label="בטיפול" value={inProgressCount} />
                <StatCard label="סגורות" value={closedCount} />
              </div>
            </div>
          )}
        </div>
      </div>

      {blockingCount > 0 && (
        <div className="max-w-lg mx-auto px-4 mt-3">
          <div className="bg-white rounded-xl shadow-sm border border-red-200 overflow-hidden">
            <button
              onClick={() => setBlockingOpen(!blockingOpen)}
              className="w-full flex items-center justify-between p-3 text-right"
            >
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-500" />
                <span className="text-sm font-semibold text-red-700">חוסמי מסירה</span>
                <span className="text-[10px] bg-red-500 text-white px-2 py-0.5 rounded-full font-bold">{blockingCount}</span>
              </div>
              {blockingOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>
            {blockingOpen && (
              <div className="px-3 pb-3 space-y-2">
                {blockingTasks.map(task => {
                  const statusInfo = STATUS_LABELS[task.status] || STATUS_LABELS.open;
                  return (
                    <button
                      key={task.id}
                      onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: `/projects/${projectId}/units/${unitId}/defects` } })}
                      className="w-full bg-red-50 rounded-lg p-2.5 text-right hover:bg-red-100 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-slate-800 truncate">{task.title}</span>
                        <StatusPill status={task.status} label={statusInfo.label} />
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="max-w-lg mx-auto px-4 mt-3">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button
            onClick={() => setSpareTilesOpen(!spareTilesOpen)}
            className="w-full flex items-center justify-between p-3 text-right"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">ריצוף ספייר</span>
              {spareTilesStatus === 'not_updated' && (
                <span className="text-[10px] bg-blue-400 text-white px-2 py-0.5 rounded-full font-bold">לא עודכן</span>
              )}
              {spareTilesStatus === 'none' && (
                <span className="text-[10px] bg-amber-500 text-white px-2 py-0.5 rounded-full font-bold">אין ספייר</span>
              )}
              {typeof spareTilesStatus === 'object' && spareTilesStatus.status === 'has_tiles' && (
                <span className="text-[10px] bg-green-500 text-white px-2 py-0.5 rounded-full font-bold">
                  {spareTilesStatus.totalCount} אריחים ב-{spareTilesStatus.typesWithCount} סוגים
                </span>
              )}
            </div>
            {spareTilesOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {spareTilesOpen && (
            <div className="px-4 pb-4">
              {spareTilesStatus === 'none' && !spareTilesEditing && (
                <div className="flex items-center gap-2 p-2 mb-3 rounded-lg bg-amber-50 border border-amber-200">
                  <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                  <span className="text-xs text-amber-700 font-medium">אין ריצוף ספייר</span>
                </div>
              )}
              {spareTilesStatus === 'not_updated' && !spareTilesEditing && (
                <div className="flex items-center gap-2 p-2 mb-3 rounded-lg bg-blue-50 border border-blue-200">
                  <Info className="w-4 h-4 text-blue-500 flex-shrink-0" />
                  <span className="text-xs text-blue-600 font-medium">לא עודכן מצב ריצוף ספייר</span>
                </div>
              )}

              {spareTilesEditing ? (
                <div className="space-y-3">
                  {spareTilesEntries.map((entry, idx) => (
                    <div key={idx} className="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-700">{entry.type}</span>
                        {!entry.isBase && (
                          <button
                            type="button"
                            onClick={() => setSpareTilesEntries(prev => prev.filter((_, i) => i !== idx))}
                            className="p-1 text-red-400 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <div className="w-20">
                          <label className="block text-[10px] text-slate-500 mb-0.5">כמות</label>
                          <input
                            type="number"
                            min="0"
                            value={entry.count}
                            onChange={e => {
                              const val = e.target.value;
                              setSpareTilesEntries(prev => prev.map((en, i) => i === idx ? { ...en, count: val } : en));
                            }}
                            className="w-full px-2 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
                          />
                        </div>
                        <div className="flex-1">
                          <label className="block text-[10px] text-slate-500 mb-0.5">הערות</label>
                          <input
                            type="text"
                            value={entry.notes}
                            onChange={e => {
                              const val = e.target.value;
                              setSpareTilesEntries(prev => prev.map((en, i) => i === idx ? { ...en, notes: val } : en));
                            }}
                            maxLength={500}
                            placeholder="הערה..."
                            className="w-full px-2 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                  {spareTilesEntries.length < 20 && (
                    <button
                      type="button"
                      onClick={() => {
                        const name = prompt('שם סוג ריצוף חדש:');
                        if (!name || !name.trim()) return;
                        const trimmed = name.trim().slice(0, 50);
                        if (spareTilesEntries.some(e => e.type.toLowerCase() === trimmed.toLowerCase())) {
                          toast.error('סוג ריצוף כבר קיים');
                          return;
                        }
                        setSpareTilesEntries(prev => [...prev, { type: trimmed, count: '0', notes: '', isBase: false }]);
                      }}
                      className="flex items-center gap-1.5 text-xs text-amber-600 font-medium hover:text-amber-700 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      הוסף סוג ריצוף
                    </button>
                  )}
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={saveSpareTiles}
                      disabled={spareTilesSaving}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors"
                    >
                      {spareTilesSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      שמור
                    </button>
                    <button
                      onClick={() => setSpareTilesEditing(false)}
                      className="px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      ביטול
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  {Array.isArray(unit?.spare_tiles) && unit.spare_tiles.length > 0 && (
                    <div className="space-y-1.5">
                      {unit.spare_tiles.filter(e => e.count > 0 || e.notes).map((entry, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm text-slate-700">
                          <span className="font-medium min-w-[100px]">{entry.type}:</span>
                          <span>{entry.count}</span>
                          {entry.notes && <span className="text-slate-500 text-xs truncate">({entry.notes})</span>}
                        </div>
                      ))}
                    </div>
                  )}
                  {canCreateDefect && (
                    <button
                      onClick={startSpareTilesEdit}
                      className="flex items-center gap-1.5 text-xs text-amber-600 font-medium hover:text-amber-700 transition-colors mt-1"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                      עריכה
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 mt-4 space-y-2">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="חפש לפי תיאור, קטגוריה או קבלן..."
              className="w-full pr-9 pl-3 py-2 rounded-xl border border-slate-200 bg-white text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
            />
          </div>
          <button
            type="button"
            onClick={() => setFilterDrawerOpen(true)}
            className="relative px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors flex items-center gap-1.5 text-sm font-medium text-slate-600"
          >
            <SlidersHorizontal className="w-4 h-4" />
            סינון
            {activeFilterCount > 0 && (
              <span className="absolute -top-1.5 -left-1.5 min-w-[18px] h-[18px] bg-amber-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                {activeFilterCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setExportModalOpen(true)}
            className="px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors flex items-center gap-1.5 text-sm font-medium text-slate-600"
          >
            <Download className="w-4 h-4" />
            ייצוא
          </button>
        </div>

        {hasActiveFilters && filterSummaryText && (
          <div className="flex items-center gap-2 text-xs text-slate-500 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            <span className="flex-1 truncate">{filterSummaryText}</span>
            <button
              type="button"
              onClick={() => { setFilters({ ...APARTMENT_DEFAULT_FILTERS }); setSearchQuery(''); }}
              className="text-amber-600 hover:text-amber-700 flex-shrink-0"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="max-w-lg mx-auto px-4 mt-3">
        {tasksLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="text-slate-400 mb-2">
              <CheckCircle2 className="w-10 h-10 mx-auto" />
            </div>
            <p className="text-sm text-slate-500">
              {hasActiveFilters ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים לדירה זו'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredTasks.map(task => {
              const statusInfo = STATUS_LABELS[task.status] || STATUS_LABELS.open;
              const priorityInfo = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
              const hasImage = task.attachments?.length > 0 || task.image_url;
              const dateStr = task.created_at ? new Date(task.created_at).toLocaleDateString('he-IL') : '';

              return (
                <button
                  key={task.id}
                  onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: `/projects/${projectId}/units/${unitId}/defects` } })}
                  className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right hover:shadow-md transition-shadow active:bg-slate-50"
                >
                  <div className="flex items-start gap-3">
                    {hasImage && (
                      <div className="w-12 h-12 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
                        {task.image_url ? (
                          <img src={task.image_url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <ImageIcon className="w-5 h-5 text-slate-300" />
                        )}
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-semibold text-slate-800 truncate">{task.title}</h3>
                        <StatusPill status={task.status} label={statusInfo.label} />
                      </div>
                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        <CategoryPill>{tCategory(task.category)}</CategoryPill>
                        <span className={`text-[10px] font-medium ${priorityInfo.color}`}>
                          {priorityInfo.label}
                        </span>
                        {task.location && (
                          <span className="text-[10px] text-slate-400">{task.location}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-400">
                        {dateStr && <span>{dateStr}</span>}
                        <span>{task.assigned_to_name || task.assignee_name || 'לא שויך'}</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {canCreateDefect && (
        <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-slate-200 p-3 z-40">
          <div className="max-w-lg mx-auto">
            <button
              onClick={() => setShowDefectModal(true)}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white font-bold py-3 px-6 rounded-xl flex items-center justify-center gap-2 shadow-lg transition-colors active:bg-amber-700"
            >
              <Plus className="w-5 h-5" />
              פתח ליקוי
            </button>
          </div>
        </div>
      )}

      {showDefectModal && (
        <NewDefectModal
          isOpen={showDefectModal}
          onClose={() => setShowDefectModal(false)}
          onSuccess={() => {
            loadUnit();
            loadTasks();
          }}
          prefillData={{
            project_id: project?.id || unit?.project_id || projectId,
            building_id: building?.id || unit?.building_id || '',
            floor_id: floor?.id || unit?.floor_id || '',
            unit_id: unitId,
            project_name: project?.name || '',
            building_name: building?.name || '',
            floor_name: floor?.name || '',
            unit_label: effectiveLabel,
          }}
        />
      )}

      <FilterDrawer
        open={filterDrawerOpen}
        onOpenChange={setFilterDrawerOpen}
        filters={filters}
        defaultFilters={APARTMENT_DEFAULT_FILTERS}
        onApply={setFilters}
        sections={filterSections}
      />

      <ExportModal
        open={exportModalOpen}
        onOpenChange={setExportModalOpen}
        scope="unit"
        unitId={unitId}
        filters={{ ...filters, search: searchQuery }}
        meta={{
          projectName: unitData?.project_name,
          unitLabel: formatUnitLabel(effectiveLabel),
        }}
      />

      {editingUnit && (
        <UnitTypeEditModal
          unit={editingUnit}
          onClose={() => setEditingUnit(null)}
          onSaved={({ unit_type_tag, unit_note }) => {
            setUnitData(prev => ({
              ...prev,
              unit: { ...prev.unit, unit_type_tag, unit_note },
            }));
          }}
        />
      )}
    </div>
  );
};

export default ApartmentDashboardPage;
