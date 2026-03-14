import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, qcService } from '../services/api';
import { qcFloorStatusLabel } from '../utils/qcLabels';
import { getFloorBadgeVisualStatus } from '../utils/qcVisualStatus';
import {
  ArrowRight, Loader2, Layers, Search,
  Clock, AlertCircle, Lock, ShieldCheck, XCircle, WifiOff, ChevronLeft
} from 'lucide-react';

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && typeof data === 'object') {
    const arrKey = Object.keys(data).find(k => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
  }
  return [];
};

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
  if (pass_count > 0) return { label: 'בביצוע', color: 'bg-amber-100 text-amber-700' };
  return null;
};

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

export default function BuildingQCPage() {
  const { projectId, buildingId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(null);
  const [projectName, setProjectName] = useState('');
  const [qcStatuses, setQcStatuses] = useState({});
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [loadError, setLoadError] = useState(null);
  const [batchStatusError, setBatchStatusError] = useState(false);
  const abortRef = useRef(null);
  const seqRef = useRef(0);

  const handleBack = useCallback(() => {
    if (window.history.length > 2) {
      navigate(-1);
    } else {
      navigate(`/projects/${projectId}/buildings/${buildingId}`);
    }
  }, [navigate, projectId, buildingId]);

  const load = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const seq = ++seqRef.current;
    const signal = controller.signal;

    setLoading(true);
    setLoadError(null);
    setBatchStatusError(false);

    try {
      const data = await projectService.getHierarchy(projectId, { signal });
      if (signal.aborted || seqRef.current !== seq) return;

      const pName = data?.project_name || '';
      setProjectName(pName);
      const buildings = normalizeList(data);
      const found = buildings.find(b => b.id === buildingId);
      setBuilding(found || null);

      if (!found) {
        setLoading(false);
        return;
      }

      const floorIds = (found.floors || []).map(f => f.id);
      if (floorIds.length > 0) {
        try {
          const statuses = await qcService.getFloorsBatchStatus(floorIds, { projectId, signal });
          if (signal.aborted || seqRef.current !== seq) return;
          setQcStatuses(statuses);
        } catch (batchErr) {
          if (signal.aborted || seqRef.current !== seq) return;
          setBatchStatusError(true);
        }
      }
    } catch (err) {
      if (signal.aborted || seqRef.current !== seq) return;
      const status = err?.response?.status;
      if (status === 403 || status === 401) {
        setLoadError('forbidden');
      } else {
        setLoadError('error');
      }
    } finally {
      if (!signal.aborted && seqRef.current === seq) {
        setLoading(false);
      }
    }
  }, [projectId, buildingId]);

  useEffect(() => {
    load();
    return () => { if (abortRef.current) abortRef.current.abort(); };
  }, [load]);

  const floors = useMemo(() => building?.floors || [], [building]);

  const statusCounts = useMemo(() => {
    const counts = {};
    floors.forEach(f => {
      const st = getFloorBadge(qcStatuses[f.id]);
      const normalized = st === 'submitted' ? 'pending_review' : st;
      counts[normalized] = (counts[normalized] || 0) + 1;
    });
    return counts;
  }, [floors, qcStatuses]);

  const summaryParts = useMemo(() => {
    const parts = [];
    if (statusCounts.approved) parts.push(`${statusCounts.approved} הושלמו`);
    if (statusCounts.in_progress) parts.push(`${statusCounts.in_progress} בביצוע`);
    if (statusCounts.pending_review) parts.push(`${statusCounts.pending_review} ממתין לאישור`);
    if (statusCounts.rejected) parts.push(`${statusCounts.rejected} נדחה`);
    if (statusCounts.not_started) parts.push(`${statusCounts.not_started} לא התחיל`);
    return parts.length > 0 ? parts.join(' · ') : `${floors.length} קומות`;
  }, [floors.length, statusCounts]);

  const filteredFloors = useMemo(() => {
    let result = floors;

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(f =>
        (f.name || '').toLowerCase().includes(q) ||
        (f.floor_number?.toString() || '').includes(q)
      );
    }

    if (filter !== 'all') {
      if (filter === 'pending_review') {
        result = result.filter(f => {
          const s = getFloorBadge(qcStatuses[f.id]);
          return s === 'pending_review' || s === 'submitted';
        });
      } else {
        result = result.filter(f => getFloorBadge(qcStatuses[f.id]) === filter);
      }
    }

    result.sort((a, b) => {
      const orderA = QC_STATUS_ORDER[getFloorBadge(qcStatuses[a.id])] ?? 3;
      const orderB = QC_STATUS_ORDER[getFloorBadge(qcStatuses[b.id])] ?? 3;
      return orderA - orderB;
    });

    return result;
  }, [floors, search, filter, qcStatuses]);

  if (loading) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-amber-500 mx-auto" />
          <p className="text-sm text-slate-500 mt-3">טוען בקרת ביצוע...</p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50">
        <div className="sticky top-0 z-30 bg-slate-800 px-4 py-3 flex items-center gap-3">
          <button onClick={handleBack} className="text-white hover:text-amber-300 transition-colors" aria-label="חזרה">
            <ArrowRight className="w-5 h-5" />
          </button>
          <h1 className="text-white font-bold text-base">בקרת ביצוע</h1>
        </div>
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            {loadError === 'forbidden' ? (
              <>
                <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
                <p className="text-slate-600 font-medium">אין הרשאה לצפייה בבקרת ביצוע</p>
              </>
            ) : (
              <>
                <WifiOff className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-lg font-medium text-slate-600 mb-1">שגיאת תקשורת</p>
                <p className="text-sm text-slate-400 mb-4">לא ניתן לטעון את נתוני הבניין</p>
                <div className="flex gap-2 justify-center">
                  <button
                    onClick={load}
                    className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 transition-colors"
                  >
                    נסה שוב
                  </button>
                  <button
                    onClick={handleBack}
                    className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-300 transition-colors"
                  >
                    חזרה
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!building || floors.length === 0) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50">
        <div className="sticky top-0 z-30 bg-slate-800 px-4 py-3 flex items-center gap-3">
          <button onClick={handleBack} className="text-white hover:text-amber-300 transition-colors" aria-label="חזרה">
            <ArrowRight className="w-5 h-5" />
          </button>
          <h1 className="text-white font-bold text-base">בקרת ביצוע</h1>
        </div>
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            <Layers className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-lg font-medium text-slate-600 mb-1">אין קומות בבניין זה</p>
            <p className="text-sm text-slate-400 mb-4">צריך להקים קומות כדי להתחיל בקרת ביצוע</p>
            <button
              onClick={handleBack}
              className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 transition-colors"
            >
              חזרה לבניין
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50">
      <div className="sticky top-0 z-30 bg-slate-800 px-4 py-3 flex items-center gap-3">
        <button onClick={handleBack} className="text-white hover:text-amber-300 transition-colors" aria-label="חזרה">
          <ArrowRight className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-white font-bold text-base truncate leading-tight">בקרת ביצוע</h1>
          <p className="text-slate-300 text-xs truncate">{building.name}{projectName ? ` — ${projectName}` : ''}</p>
        </div>
      </div>

      <div className="px-4 pt-2.5 pb-1">
        <p className="text-[11px] text-slate-400">{summaryParts}</p>
        {(() => {
          const approvedCount = statusCounts.approved || 0;
          const remaining = floors.length - approvedCount;
          const approvedRatio = floors.length > 0 ? approvedCount / floors.length : 0;
          if (approvedRatio >= 0.7 && remaining > 0 && remaining <= 3) {
            return (
              <div className="mt-2 bg-green-50 border border-green-200 rounded-xl px-3 py-2 text-center">
                <span className="text-sm font-bold text-green-700">🎯 עוד {remaining} קומות והבניין מושלם!</span>
              </div>
            );
          }
          return null;
        })()}
      </div>

      <div className="px-4 pt-1.5 space-y-2">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="חיפוש קומה..."
            className="w-full pr-9 pl-3 py-2 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-amber-300"
          />
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {FILTER_OPTIONS.map(opt => (
            <button
              key={opt.id}
              onClick={() => setFilter(opt.id)}
              className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === opt.id
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'bg-white border border-slate-200 text-slate-500 hover:border-slate-300'
              }`}
            >
              {opt.id === 'all' ? 'הכל' : qcFloorStatusLabel(opt.id)}
              {opt.id === 'all'
                ? ` (${floors.length})`
                : statusCounts[opt.id] ? ` (${statusCounts[opt.id]})` : ''}
            </button>
          ))}
        </div>

        {batchStatusError && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>סטטוסים לא זמינים כרגע — הקומות מוצגות ללא סטטוס</span>
          </div>
        )}
      </div>

      <div className="px-4 pt-2.5 pb-6 space-y-1.5">
        {filteredFloors.length === 0 ? (
          <div className="text-center py-8">
            <Layers className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">אין קומות מתאימות לפילטר</p>
          </div>
        ) : (
          filteredFloors.map(floor => {
            const status = getFloorBadge(qcStatuses[floor.id]);
            const quality = getFloorQuality(qcStatuses[floor.id]);
            const vs = getFloorBadgeVisualStatus(status);
            const Icon = QC_STATUS_ICONS[status] || Clock;
            const showQuality = quality && quality.label !== qcFloorStatusLabel(status);
            const qd = qcStatuses[floor.id];
            const failCount = qd?.fail_count || 0;
            const floorTotal = qd?.total || 0;
            const floorPass = qd?.pass_count || 0;
            const floorPct = floorTotal > 0 ? Math.round((floorPass / floorTotal) * 100) : 0;
            const floorAccent = failCount > 0 ? 'border-r-4 border-red-400'
              : status === 'in_progress' ? 'border-r-4 border-amber-400'
              : status === 'not_started' ? 'border-r-4 border-slate-300'
              : status === 'approved' ? 'border-r-4 border-green-400'
              : (status === 'pending_review' || status === 'submitted') ? 'border-r-4 border-blue-400'
              : '';
            const badgePrefix = status === 'in_progress' ? '◐ '
              : status === 'not_started' ? '◷ '
              : status === 'approved' ? '✓ '
              : failCount > 0 ? '⚠ '
              : '';

            return (
              <button
                key={floor.id}
                onClick={() => navigate(`/projects/${projectId}/floors/${floor.id}`)}
                className={`w-full flex items-center justify-between px-3.5 py-3 bg-white rounded-xl border border-slate-100 ${floorAccent} hover:border-amber-200 hover:shadow active:bg-slate-50 transition-all text-right`}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <Layers className="w-3.5 h-3.5 text-slate-300 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold text-slate-700 block">
                      {floor.display_label || floor.name || `קומה ${floor.floor_number}`}
                    </span>
                    {floorTotal > 0 && (
                      <div className="flex items-center gap-1.5 mt-1">
                        <div className="flex-1 bg-slate-100 rounded-full h-1" role="progressbar" aria-valuenow={floorPct} aria-valuemin={0} aria-valuemax={100} aria-label={`התקדמות קומה ${floorPct}%`}>
                          <div className={`h-1 rounded-full transition-all ${floorPct === 100 ? 'bg-green-400' : floorPct > 50 ? 'bg-blue-400' : 'bg-amber-400'}`}
                            style={{ width: `${floorPct}%` }} />
                        </div>
                        <span className="text-[10px] text-slate-400 font-medium flex-shrink-0">{floorPass}/{floorTotal} שלבים</span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {showQuality && (
                    <span className={`text-[11px] font-medium px-2.5 py-1 rounded-full ${quality.color}`}>
                      {quality.label}
                    </span>
                  )}
                  <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full ${vs.bg} ${vs.color}`}>
                    <span>{badgePrefix}</span>
                    <Icon className="w-3 h-3" />
                    {qcFloorStatusLabel(status)}
                  </span>
                  <ChevronLeft className="w-3.5 h-3.5 text-slate-300" />
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
