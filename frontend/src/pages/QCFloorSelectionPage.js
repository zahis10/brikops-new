import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, qcService } from '../services/api';
import { qcFloorStatusLabel } from '../utils/qcLabels';
import { getFloorBadgeVisualStatus, getFloorQualityBadge } from '../utils/qcVisualStatus';

const getFloorBadge = (qcData) => {
  if (!qcData) return 'not_started';
  if (typeof qcData === 'string') return qcData;
  return qcData.badge || 'not_started';
};

const getFloorQuality = (qcData) => {
  if (!qcData || typeof qcData === 'string') return null;
  const { pass_count = 0, fail_count = 0, total = 0 } = qcData;
  if (total === 0) return null;
  if (fail_count > 0) return { label: 'נכשל', color: 'bg-red-100 text-red-700' };
  if (pass_count === total) return { label: 'תקין', color: 'bg-emerald-100 text-emerald-700' };
  if (pass_count > 0 || fail_count > 0) return { label: 'בביצוע', color: 'bg-amber-100 text-amber-700' };
  if (total > 0) return { label: 'בביצוע', color: 'bg-slate-100 text-slate-500' };
  return null;
};
import {
  ArrowRight, Loader2, ClipboardCheck, Building2, Layers, Search,
  CheckCircle2, Clock, Lock, AlertCircle, ChevronDown, ChevronRight,
  ChevronsUpDown, XCircle, ShieldCheck, RotateCcw
} from 'lucide-react';

const QC_STATUS_ICONS = {
  not_started: Clock,
  in_progress: AlertCircle,
  pending_review: Lock,
  submitted: Lock,
  approved: ShieldCheck,
  rejected: XCircle,
};

const QC_STATUS_ORDER = {
  rejected: 0,
  pending_review: 1,
  in_progress: 2,
  not_started: 3,
  submitted: 4,
  approved: 5,
};

const FILTER_OPTIONS = [
  { id: 'all' },
  { id: 'rejected' },
  { id: 'pending_review' },
  { id: 'in_progress' },
  { id: 'approved' },
  { id: 'not_started' },
];

const LS_KEY_PREFIX = 'qcSelectionCollapsedState:';

export default function QCFloorSelectionPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [hierarchy, setHierarchy] = useState([]);
  const [qcStatuses, setQcStatuses] = useState({});
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [expandedBuildings, setExpandedBuildings] = useState({});
  const [initialized, setInitialized] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [batchStatusError, setBatchStatusError] = useState(false);
  const abortRef = useRef(null);
  const seqRef = useRef(0);

  const saveExpandedState = useCallback((state) => {
    try {
      localStorage.setItem(LS_KEY_PREFIX + projectId, JSON.stringify(state));
    } catch {}
  }, [projectId]);

  const load = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const seq = ++seqRef.current;
    const signal = controller.signal;

    setHierarchy([]);
    setQcStatuses({});
    setExpandedBuildings({});
    setInitialized(false);
    setLoading(true);
    setLoadError(null);
    setBatchStatusError(false);

    try {
      const data = await projectService.getHierarchy(projectId, { signal });
      if (signal.aborted || seqRef.current !== seq) return;
      const buildings =
        Array.isArray(data) ? data :
        Array.isArray(data?.buildings) ? data.buildings :
        Array.isArray(data?.items) ? data.items :
        [];
      if (data && !Array.isArray(data) && buildings.length === 0) {
        console.warn('[QC] hierarchy response has no buildings array. Keys:', Object.keys(data));
      }
      setHierarchy(buildings);

      let savedState = null;
      try {
        const raw = localStorage.getItem(LS_KEY_PREFIX + projectId);
        if (raw) savedState = JSON.parse(raw);
      } catch {}

      if (savedState && typeof savedState === 'object') {
        const merged = {};
        buildings.forEach(b => { merged[b.id] = savedState[b.id] === true; });
        setExpandedBuildings(merged);
      } else {
        const allCollapsed = {};
        buildings.forEach(b => { allCollapsed[b.id] = false; });
        setExpandedBuildings(allCollapsed);
      }
      setInitialized(true);

      const floorIds = [];
      buildings.forEach(b => (b.floors || []).forEach(f => floorIds.push(f.id)));
      if (floorIds.length > 0) {
        try {
          const statuses = await qcService.getFloorsBatchStatus(floorIds, { projectId, signal });
          if (signal.aborted || seqRef.current !== seq) return;
          setQcStatuses(statuses);
        } catch (batchErr) {
          if (signal.aborted || seqRef.current !== seq) return;
          const bStatus = batchErr?.response?.status;
          const reqId = batchErr?.response?.headers?.['x-request-id'] || 'N/A';
          const path = '/api/qc/floors/batch-status';
          console.error(
            `[QC] batch-status failed | status=${bStatus || 'network_error'} | path=${path} | request_id=${reqId} | floors=${floorIds.length}`,
            batchErr
          );
          setBatchStatusError(true);
        }
      }
    } catch (err) {
      if (signal.aborted || seqRef.current !== seq) return;
      console.error('Failed to load hierarchy', err);
      const status = err?.response?.status;
      if (status === 403) {
        setLoadError('forbidden');
      } else {
        setLoadError('error');
      }
    } finally {
      if (!signal.aborted && seqRef.current === seq) {
        setLoading(false);
      }
    }
  }, [projectId]);

  useEffect(() => {
    load();
    return () => { if (abortRef.current) abortRef.current.abort(); };
  }, [load]);

  const toggleBuilding = (id) => {
    setExpandedBuildings(prev => {
      const next = { ...prev, [id]: !prev[id] };
      saveExpandedState(next);
      return next;
    });
  };

  const allExpanded = useMemo(() => Object.values(expandedBuildings).every(v => v), [expandedBuildings]);

  const toggleAll = () => {
    const newVal = !allExpanded;
    const next = {};
    hierarchy.forEach(b => { next[b.id] = newVal; });
    setExpandedBuildings(next);
    saveExpandedState(next);
  };

  const getFilteredFloors = (floors) => {
    let filtered = floors;

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      filtered = filtered.filter(f =>
        (f.name || '').toLowerCase().includes(q) ||
        (f.floor_number?.toString() || '').includes(q)
      );
    }

    if (filter !== 'all') {
      if (filter === 'pending_review') {
        filtered = filtered.filter(f => {
          const s = getFloorBadge(qcStatuses[f.id]);
          return s === 'pending_review' || s === 'submitted';
        });
      } else {
        filtered = filtered.filter(f => getFloorBadge(qcStatuses[f.id]) === filter);
      }
    }

    filtered.sort((a, b) => {
      const statusA = getFloorBadge(qcStatuses[a.id]);
      const statusB = getFloorBadge(qcStatuses[b.id]);
      const orderA = QC_STATUS_ORDER[statusA] ?? QC_STATUS_ORDER.not_started;
      const orderB = QC_STATUS_ORDER[statusB] ?? QC_STATUS_ORDER.not_started;
      return orderA - orderB;
    });

    return filtered;
  };

  const matchesSearch = (building) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    if ((building.name || '').toLowerCase().includes(q)) return true;
    return (building.floors || []).some(f =>
      (f.name || '').toLowerCase().includes(q) ||
      (f.floor_number?.toString() || '').includes(q)
    );
  };

  const totalFloors = hierarchy.reduce((s, b) => s + (b.floors?.length || 0), 0);
  const statusCounts = {};
  hierarchy.forEach(b => (b.floors || []).forEach(f => {
    const st = getFloorBadge(qcStatuses[f.id]);
    const normalizedSt = st === 'submitted' ? 'pending_review' : st;
    statusCounts[normalizedSt] = (statusCounts[normalizedSt] || 0) + 1;
  }));

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="bg-slate-800 text-white sticky top-0 z-30">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
            <button onClick={() => navigate(`/projects/${projectId}/control`)} className="p-1.5 hover:bg-slate-700 rounded-lg">
              <ArrowRight className="w-5 h-5" />
            </button>
            <h1 className="text-base font-bold flex items-center gap-2">
              <ClipboardCheck className="w-4 h-4 text-amber-400" />
              בקרת ביצוע
            </h1>
          </div>
        </div>
        <div className="max-w-2xl mx-auto px-4 py-12 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          {loadError === 'forbidden' ? (
            <p className="text-slate-600 font-medium">אין הרשאה לצפייה בבקרת ביצוע</p>
          ) : (
            <>
              <p className="text-slate-600 font-medium mb-4">לא הצלחנו לטעון מבנים וקומות</p>
              <button
                onClick={load}
                className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-bold text-sm shadow-sm transition-colors"
              >
                נסה שוב
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  if (hierarchy.length === 0 || totalFloors === 0) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="bg-slate-800 text-white sticky top-0 z-30">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
            <button onClick={() => navigate(`/projects/${projectId}/control`)} className="p-1.5 hover:bg-slate-700 rounded-lg">
              <ArrowRight className="w-5 h-5" />
            </button>
            <h1 className="text-base font-bold flex items-center gap-2">
              <ClipboardCheck className="w-4 h-4 text-amber-400" />
              בקרת ביצוע
            </h1>
          </div>
        </div>
        <div className="max-w-2xl mx-auto px-4 py-12 text-center">
          <Building2 className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 mb-4">צריך להקים מבנה וקומות כדי להתחיל בקרת ביצוע</p>
          <button
            onClick={() => navigate(`/projects/${projectId}/control?tab=structure`)}
            className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-bold text-sm shadow-sm transition-colors"
          >
            הקמה מהירה
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-slate-800 text-white sticky top-0 z-30">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button onClick={() => navigate(`/projects/${projectId}/control`)} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
                <ArrowRight className="w-5 h-5" />
              </button>
              <h1 className="text-base font-bold flex items-center gap-2">
                <ClipboardCheck className="w-4 h-4 text-amber-400" />
                בקרת ביצוע — בחירת קומה
              </h1>
            </div>
            <div className="text-xs text-slate-400">{totalFloors} קומות</div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-3 space-y-3">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="חיפוש בניין או קומה..."
            className="w-full pr-9 pl-3 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-amber-300"
            dir="rtl"
          />
        </div>

        <div className="flex items-center gap-2">
          <div className="flex gap-1.5 overflow-x-auto flex-1 pb-1">
            {FILTER_OPTIONS.map(opt => (
              <button
                key={opt.id}
                onClick={() => setFilter(opt.id)}
                className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  filter === opt.id
                    ? 'bg-slate-700 text-white'
                    : 'bg-white border border-slate-200 text-slate-500 hover:border-slate-300'
                }`}
              >
                {opt.id === 'all' ? 'הכל' : qcFloorStatusLabel(opt.id)}
                {opt.id !== 'all' && statusCounts[opt.id] ? ` (${statusCounts[opt.id]})` : ''}
                {opt.id === 'all' ? ` (${totalFloors})` : ''}
              </button>
            ))}
          </div>
          {initialized && hierarchy.length > 1 && (
            <button
              onClick={toggleAll}
              className="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-500 hover:border-slate-300 transition-all"
              title={allExpanded ? 'סגור הכל' : 'פתח הכל'}
            >
              <ChevronsUpDown className="w-3.5 h-3.5" />
              {allExpanded ? 'סגור הכל' : 'פתח הכל'}
            </button>
          )}
        </div>

        {batchStatusError && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700" dir="rtl">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>סטטוסים לא זמינים כרגע — הקומות מוצגות ללא סטטוס</span>
          </div>
        )}

        <div className="space-y-2">
          {hierarchy.filter(matchesSearch).map(building => {
            const floors = getFilteredFloors(building.floors || []);
            const isExpanded = expandedBuildings[building.id];

            if (floors.length === 0 && filter !== 'all') return null;

            return (
              <div key={building.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <button
                  onClick={() => toggleBuilding(building.id)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-slate-400" />
                    <span className="text-sm font-bold text-slate-700">{building.name}</span>
                    <span className="text-xs text-slate-400">({(building.floors || []).length} קומות)</span>
                  </div>
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                </button>

                {isExpanded && (
                  <div className="border-t border-slate-100 divide-y divide-slate-50">
                    {floors.length === 0 ? (
                      <div className="px-4 py-3 text-xs text-slate-400 text-center">אין קומות מתאימות לפילטר</div>
                    ) : (
                      floors.map(floor => {
                        const status = getFloorBadge(qcStatuses[floor.id]);
                        const quality = getFloorQuality(qcStatuses[floor.id]);
                        const vs = getFloorBadgeVisualStatus(status);
                        const Icon = QC_STATUS_ICONS[status] || Clock;
                        return (
                          <button
                            key={floor.id}
                            onClick={() => navigate(`/projects/${projectId}/floors/${floor.id}`)}
                            className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors text-right"
                          >
                            <div className="flex items-center gap-2">
                              <Layers className="w-3.5 h-3.5 text-slate-300" />
                              <span className="text-sm text-slate-600">{floor.name || `קומה ${floor.floor_number}`}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              {quality && (
                                <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${quality.color}`}>
                                  {quality.label}
                                </span>
                              )}
                              <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${vs.bg} ${vs.color}`}>
                                <Icon className="w-3 h-3" />
                                {qcFloorStatusLabel(status)}
                              </span>
                            </div>
                          </button>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
