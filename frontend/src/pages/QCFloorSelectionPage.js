import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, qcService } from '../services/api';
import { qcFloorStatusLabel } from '../utils/qcLabels';
import {
  ArrowRight, Loader2, ClipboardCheck, Building2, Search,
  AlertCircle, ChevronLeft
} from 'lucide-react';

const getFloorBadge = (qcData) => {
  if (!qcData) return 'not_started';
  if (typeof qcData === 'string') return qcData;
  return qcData.badge || 'not_started';
};

const STATUS_KEYS = ['rejected', 'pending_review', 'in_progress', 'approved', 'not_started'];

export default function QCFloorSelectionPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [hierarchy, setHierarchy] = useState([]);
  const [qcStatuses, setQcStatuses] = useState({});
  const [projectName, setProjectName] = useState('');
  const [search, setSearch] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [batchStatusError, setBatchStatusError] = useState(false);
  const abortRef = useRef(null);
  const seqRef = useRef(0);

  const load = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const seq = ++seqRef.current;
    const signal = controller.signal;

    setHierarchy([]);
    setQcStatuses({});
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
      setHierarchy(buildings);

      if (data?.project_name) setProjectName(data.project_name);

      const floorIds = [];
      buildings.forEach(b => (b.floors || []).forEach(f => floorIds.push(f.id)));
      if (floorIds.length > 0) {
        try {
          const statuses = await qcService.getFloorsBatchStatus(floorIds, { projectId, signal });
          if (signal.aborted || seqRef.current !== seq) return;
          setQcStatuses(statuses);
        } catch (batchErr) {
          if (signal.aborted || seqRef.current !== seq) return;
          console.error('[QC] batch-status failed', batchErr);
          setBatchStatusError(true);
        }
      }
    } catch (err) {
      if (signal.aborted || seqRef.current !== seq) return;
      console.error('Failed to load hierarchy', err);
      const status = err?.response?.status;
      setLoadError(status === 403 ? 'forbidden' : 'error');
    } finally {
      if (!signal.aborted && seqRef.current === seq) setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
    return () => { if (abortRef.current) abortRef.current.abort(); };
  }, [load]);

  const buildingStats = useMemo(() => {
    const stats = {};
    hierarchy.forEach(b => {
      const floors = b.floors || [];
      const counts = {};
      let totalItems = 0;
      let passItems = 0;
      let hasItemData = false;
      floors.forEach(f => {
        const qd = qcStatuses[f.id];
        const st = getFloorBadge(qd);
        const normalized = st === 'submitted' ? 'pending_review' : st;
        counts[normalized] = (counts[normalized] || 0) + 1;
        if (qd && typeof qd === 'object' && qd.total > 0) {
          hasItemData = true;
          totalItems += qd.total;
          passItems += qd.pass_count || 0;
        }
      });
      const floorCount = floors.length;
      let progressPct;
      if (hasItemData && totalItems > 0) {
        progressPct = Math.round((passItems / totalItems) * 100);
      } else {
        const approved = counts['approved'] || 0;
        progressPct = floorCount > 0 ? Math.round((approved / floorCount) * 100) : 0;
      }
      const accentBorder = progressPct === 100 ? 'border-r-4 border-green-400' : progressPct > 50 ? 'border-r-4 border-blue-400' : progressPct > 0 ? 'border-r-4 border-amber-400' : 'border-r-4 border-slate-300';
      const ringColor = progressPct === 100 ? '#22C55E' : progressPct > 50 ? '#3B82F6' : progressPct > 0 ? '#F59E0B' : '#CBD5E1';
      stats[b.id] = { floorCount, counts, progressPct, accentBorder, ringColor };
    });
    return stats;
  }, [hierarchy, qcStatuses]);

  const filteredBuildings = useMemo(() => {
    if (!search.trim()) return hierarchy;
    const q = search.trim().toLowerCase();
    return hierarchy.filter(b => (b.name || '').toLowerCase().includes(q));
  }, [hierarchy, search]);

  const globalStats = useMemo(() => {
    let pending = 0, inProgress = 0, approved = 0, rejected = 0;
    hierarchy.forEach(b => {
      const s = buildingStats[b.id]?.counts || {};
      approved += s.approved || 0;
      inProgress += (s.in_progress || 0) + (s.pending_review || 0);
      rejected += s.rejected || 0;
      pending += s.not_started || 0;
    });
    return { pending, inProgress, approved, rejected };
  }, [hierarchy, buildingStats]);

  const totalFloors = hierarchy.reduce((s, b) => s + (b.floors?.length || 0), 0);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50" dir="rtl">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  const headerBlock = (
    <div className="bg-slate-800 text-white sticky top-0 z-30">
      <div className="max-w-2xl mx-auto px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(`/projects/${projectId}/control`)} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="min-w-0">
            <h1 className="text-base font-bold flex items-center gap-2">
              <ClipboardCheck className="w-4 h-4 text-amber-400" />
              בקרת ביצוע
            </h1>
            {projectName && (
              <p className="text-[11px] text-slate-400 truncate">{projectName}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (loadError) {
    return (
      <div className="min-h-screen bg-slate-50" dir="rtl">
        {headerBlock}
        <div className="max-w-2xl mx-auto px-4 py-12 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          {loadError === 'forbidden' ? (
            <p className="text-slate-600 font-medium">אין הרשאה לצפייה בבקרת ביצוע</p>
          ) : (
            <>
              <p className="text-slate-600 font-medium mb-4">לא הצלחנו לטעון מבנים</p>
              <button onClick={load} className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-bold text-sm shadow-sm transition-colors">
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
      <div className="min-h-screen bg-slate-50" dir="rtl">
        {headerBlock}
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
    <div className="min-h-screen bg-slate-50" dir="rtl">
      {headerBlock}

      <div className="max-w-2xl mx-auto px-4 py-3 space-y-3">
        <div className="grid grid-cols-4 gap-2 text-center">
          <div className="bg-slate-50 rounded-lg p-2">
            <div className="text-lg font-bold text-slate-500">{globalStats.pending}</div>
            <div className="text-[10px] text-slate-500 font-medium">בהמתנה</div>
          </div>
          <div className="bg-red-50 rounded-lg p-2">
            <div className="text-lg font-bold text-red-500">{globalStats.rejected}</div>
            <div className="text-[10px] text-red-500 font-medium">נכשלו</div>
          </div>
          <div className="bg-amber-50 rounded-lg p-2">
            <div className="text-lg font-bold text-amber-500">{globalStats.inProgress}</div>
            <div className="text-[10px] text-amber-600 font-medium">בביצוע</div>
          </div>
          <div className="bg-emerald-50 rounded-lg p-2">
            <div className="text-lg font-bold text-emerald-600">{globalStats.approved}</div>
            <div className="text-[10px] text-emerald-600 font-medium">הושלמו</div>
          </div>
        </div>

        <p className="text-[11px] text-slate-400 px-1">
          {hierarchy.length} מבנים · {totalFloors} קומות
        </p>

        {hierarchy.length > 3 && (
          <div className="relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="חיפוש מבנה..."
              className="w-full pr-9 pl-3 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-amber-300"
              dir="rtl"
            />
          </div>
        )}

        {batchStatusError && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700" dir="rtl">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>סטטוסים לא זמינים כרגע</span>
          </div>
        )}

        <div className="space-y-2">
          {filteredBuildings.map(building => {
            const stats = buildingStats[building.id] || { floorCount: 0, counts: {}, progressPct: 0, ringColor: '#CBD5E1' };
            const r = 16, sw = 3, cx = 18, circ = 2 * Math.PI * r;
            const offset = circ - (stats.progressPct / 100) * circ;

            return (
              <button
                key={building.id}
                onClick={() => navigate(`/projects/${projectId}/buildings/${building.id}/qc`)}
                className={`w-full bg-white rounded-xl border border-slate-100 ${stats.accentBorder} px-4 py-3.5 hover:border-amber-200 hover:shadow transition-all text-right`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-[38px] h-[38px] bg-emerald-50 rounded-[10px] flex items-center justify-center flex-shrink-0">
                      <Building2 className="w-5 h-5 text-emerald-600" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[15px] font-bold text-slate-700 truncate block">{building.name}</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(stats.counts.approved || 0) > 0 && (
                          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600">✓ {stats.counts.approved} הושלמו</span>
                        )}
                        {(stats.counts.in_progress || 0) > 0 && (
                          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600">◐ {stats.counts.in_progress} בביצוע</span>
                        )}
                        {(stats.counts.not_started || 0) > 0 && (
                          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500">{stats.counts.not_started} לא התחיל</span>
                        )}
                        {(stats.counts.rejected || 0) > 0 && (
                          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-red-50 text-red-600">✗ {stats.counts.rejected} נכשלו</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <svg width="36" height="36" viewBox="0 0 36 36">
                      <circle cx={cx} cy={cx} r={r} fill="none" stroke="#E2E8F0" strokeWidth={sw} />
                      <circle cx={cx} cy={cx} r={r} fill="none" stroke={stats.ringColor} strokeWidth={sw}
                        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
                        transform={`rotate(-90 ${cx} ${cx})`} style={{ transition: 'stroke-dashoffset 0.5s' }} />
                      <text x={cx} y={cx} textAnchor="middle" dominantBaseline="central"
                        fill="#334155" fontSize="10" fontWeight="bold">{stats.progressPct}%</text>
                    </svg>
                    <ChevronLeft className="w-4 h-4 text-slate-300" />
                  </div>
                </div>
              </button>
            );
          })}

          {filteredBuildings.length === 0 && search.trim() && (
            <div className="text-center py-8">
              <p className="text-sm text-slate-400">לא נמצאו מבנים תואמים</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
