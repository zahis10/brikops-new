import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { buildingService, configService } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Loader2, Building2, ChevronDown, ChevronUp,
  Home, AlertTriangle, Clock, CheckCircle2, Filter
} from 'lucide-react';

const BuildingDefectsPage = () => {
  const { projectId, buildingId } = useParams();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [flagChecked, setFlagChecked] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(true);
  const [filterMode, setFilterMode] = useState('all');
  const [expandedFloors, setExpandedFloors] = useState({});

  useEffect(() => {
    let cancelled = false;
    const checkFlag = async () => {
      try {
        const features = await configService.getFeatures();
        if (cancelled) return;
        if (!features?.feature_flags?.defects_v2) {
          navigate(`/projects/${projectId}/tasks`, { replace: true });
          return;
        }
        setFlagChecked(true);
      } catch {
        if (!cancelled) {
          navigate(`/projects/${projectId}/tasks`, { replace: true });
        }
      }
    };
    checkFlag();
    return () => { cancelled = true; };
  }, [projectId, navigate]);

  const loadData = useCallback(async () => {
    if (!flagChecked) return;
    setLoading(true);
    try {
      const result = await buildingService.defectsSummary(buildingId);
      setData(result);
      const allFloors = {};
      (result.floors || []).forEach((_, i) => { allFloors[i] = true; });
      setExpandedFloors(allFloors);
    } catch (err) {
      console.error('Failed to load building defects summary:', err);
      if (err?.response?.status === 403) {
        toast.error('אין לך הרשאה לצפות בנתוני בניין זה');
        navigate(`/projects/${projectId}/tasks`);
        return;
      }
      toast.error('שגיאה בטעינת סיכום ליקויים');
    } finally {
      setLoading(false);
    }
  }, [buildingId, projectId, navigate, flagChecked]);

  useEffect(() => { loadData(); }, [loadData]);

  const toggleFloor = (idx) => {
    setExpandedFloors(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const getUnitBadgeColor = (unit) => {
    const open = (unit.defect_counts?.open || 0) + (unit.defect_counts?.in_progress || 0);
    if (open >= 3) return 'bg-red-500 text-white';
    if (open >= 1) return 'bg-amber-500 text-white';
    if ((unit.defect_counts?.total || 0) > 0) return 'bg-green-500 text-white';
    return 'bg-slate-200 text-slate-500';
  };

  const getUnitIconColor = (unit) => {
    const open = (unit.defect_counts?.open || 0) + (unit.defect_counts?.in_progress || 0);
    if (open >= 3) return 'text-red-500';
    if (open >= 1) return 'text-amber-500';
    if ((unit.defect_counts?.total || 0) > 0) return 'text-green-500';
    return 'text-slate-300';
  };

  const getFloorDefectCount = (floor, mode) => {
    return (floor.units || []).reduce((sum, u) => {
      const c = u.defect_counts || {};
      if (mode === 'blocking') {
        return sum + (c.open || 0) + (c.in_progress || 0);
      }
      return sum + (c.total || 0);
    }, 0);
  };

  const getTotalCounts = () => {
    if (!data?.floors) return { total: 0, pending: 0, followUp: 0 };
    let total = 0, pending = 0, followUp = 0;
    data.floors.forEach(floor => {
      (floor.units || []).forEach(u => {
        const c = u.defect_counts || {};
        total += c.total || 0;
        pending += (c.open || 0) + (c.in_progress || 0);
        followUp += c.waiting_verify || 0;
      });
    });
    return { total, pending, followUp };
  };

  if (!flagChecked || (loading && !data)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="w-10 h-10 text-amber-500 animate-spin mx-auto" />
          <p className="text-slate-500 mt-4 text-sm">טוען סיכום ליקויים...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <Building2 className="w-12 h-12 text-slate-300" />
        <p className="text-slate-500">לא נמצאו נתונים לבניין זה</p>
        <button onClick={() => navigate(`/projects/${projectId}/tasks`)} className="text-amber-600 hover:text-amber-700 font-medium text-sm">
          חזרה לליקויים
        </button>
      </div>
    );
  }

  const counts = getTotalCounts();

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="bg-gradient-to-l from-amber-500 to-amber-600 text-white">
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}/control?tab=structure`)}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-amber-200" />
                <h1 className="text-lg font-bold truncate">{data.building?.name || 'בניין'}</h1>
              </div>
              <p className="text-xs text-amber-100 mt-0.5">
                {data.project?.name || ''} • סיכום ליקויים
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 -mt-2 space-y-3">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button
            onClick={() => setSummaryOpen(!summaryOpen)}
            className="w-full flex items-center justify-between p-3 text-right"
          >
            <span className="text-sm font-semibold text-slate-700">סיכום מהיר</span>
            {summaryOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {summaryOpen && (
            <div className="px-3 pb-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-slate-50 rounded-lg p-2.5 text-center">
                  <div className="text-xl font-bold text-slate-800">{counts.total}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">סה״כ</div>
                </div>
                <div className="bg-red-50 rounded-lg p-2.5 text-center">
                  <div className="text-xl font-bold text-red-600">{counts.pending}</div>
                  <div className="text-[10px] text-red-500 mt-0.5">ממתינים</div>
                </div>
                <div className="bg-amber-50 rounded-lg p-2.5 text-center">
                  <div className="text-xl font-bold text-amber-600">{counts.followUp}</div>
                  <div className="text-[10px] text-amber-500 mt-0.5">לאימות</div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setFilterMode('all')}
            className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${
              filterMode === 'all'
                ? 'bg-slate-700 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            כל הליקויים
          </button>
          <button
            onClick={() => setFilterMode('blocking')}
            className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${
              filterMode === 'blocking'
                ? 'bg-red-600 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            חוסמי מסירה
          </button>
        </div>

        <div className="space-y-2 pb-6">
          {(data.floors || []).length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
              <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">אין קומות בבניין זה</p>
            </div>
          ) : (
            (data.floors || []).map((floor, idx) => {
              const floorCount = getFloorDefectCount(floor, filterMode);
              const isExpanded = expandedFloors[idx];

              return (
                <div key={floor.id || idx} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                  <button
                    onClick={() => toggleFloor(idx)}
                    className="w-full flex items-center gap-3 p-3 text-right hover:bg-slate-50 transition-colors"
                  >
                    <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
                      <span className="text-sm font-bold text-amber-700">{floor.name || floor.floor_number || idx}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-semibold text-slate-800">
                        {floor.display_label || floor.name || `קומה ${floor.floor_number ?? idx}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {floorCount > 0 && (
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                          filterMode === 'blocking' ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {floorCount}
                        </span>
                      )}
                      {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="px-3 pb-3 border-t border-slate-100">
                      {(floor.units || []).length === 0 ? (
                        <p className="text-xs text-slate-400 text-center py-3">אין דירות בקומה זו</p>
                      ) : (
                        <div className="grid grid-cols-4 sm:grid-cols-5 gap-2 pt-3">
                          {(floor.units || []).map(unit => {
                            const badgeCount = filterMode === 'blocking'
                              ? (unit.defect_counts?.open || 0) + (unit.defect_counts?.in_progress || 0)
                              : (unit.defect_counts?.total || 0);

                            return (
                              <button
                                key={unit.id}
                                onClick={() => navigate(`/projects/${projectId}/units/${unit.id}/defects`)}
                                className="flex flex-col items-center gap-1 p-2 rounded-xl hover:bg-slate-50 transition-colors active:scale-95"
                              >
                                <div className="relative">
                                  <Home className={`w-8 h-8 ${getUnitIconColor(unit)}`} />
                                  {badgeCount > 0 && (
                                    <span className={`absolute -top-1.5 -left-1.5 text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center ${getUnitBadgeColor(unit)}`}>
                                      {badgeCount}
                                    </span>
                                  )}
                                </div>
                                <span className="text-[11px] text-slate-600 font-medium truncate max-w-full">
                                  {unit.display_label || unit.unit_no || ''}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default BuildingDefectsPage;
