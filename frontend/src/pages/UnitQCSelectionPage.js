import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { qcService } from '../services/api';
import {
  ArrowRight, Loader2, Home, CheckCircle2, Clock, AlertCircle, RefreshCw
} from 'lucide-react';

const STATUS_CONFIG = {
  approved: { label: 'הושלם', color: 'bg-emerald-50 text-emerald-700 border-emerald-200', accent: 'border-r-4 border-green-400' },
  in_progress: { label: 'בביצוע', color: 'bg-amber-50 text-amber-700 border-amber-200', accent: 'border-r-4 border-amber-400' },
  not_started: { label: 'לא התחיל', color: 'bg-slate-50 text-slate-500 border-slate-200', accent: '' },
};

const STATUS_ICONS = {
  approved: CheckCircle2,
  in_progress: Clock,
  not_started: AlertCircle,
};

export default function UnitQCSelectionPage() {
  const { projectId, buildingId, floorId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [navigatingUnit, setNavigatingUnit] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await qcService.getUnitsStatus(floorId);
      setData(result);
    } catch (err) {
      if (err.response?.status === 403) {
        setError('אין הרשאה לצפות בבקרת ביצוע');
      } else {
        setError(err.response?.data?.detail || 'שגיאה בטעינת נתוני דירות');
      }
    } finally {
      setLoading(false);
    }
  }, [floorId]);

  useEffect(() => { load(); }, [load]);

  const handleUnitClick = async (unit) => {
    try {
      setNavigatingUnit(unit.unit_id);
      const runData = await qcService.getUnitRun(unit.unit_id);
      const run = runData.run;
      const stageId = runData.stages?.[0]?.id || 'stage_tiling';
      navigate(
        `/projects/${projectId}/qc/floors/${floorId}/run/${run.id}/stage/${stageId}`,
        {
          state: {
            returnTo: `/projects/${projectId}/buildings/${buildingId}/floors/${floorId}/qc/units`,
            unitName: unit.unit_name || unit.unit_no,
            scope: 'unit',
          }
        }
      );
    } catch (err) {
      setError('שגיאה בטעינת דירה');
      setNavigatingUnit(null);
    }
  };

  const goBack = () => {
    if (window.history.length > 2) {
      navigate(-1);
    } else {
      navigate(`/projects/${projectId}/floors/${floorId}`);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="text-center">
          <p className="text-red-500 mb-3">{error}</p>
          <button onClick={goBack} className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm">חזרה לקומה</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { units, floor_name } = data;
  const completedCount = units.filter(u => u.status === 'approved').length;
  const totalHandled = units.reduce((s, u) => s + u.handled_count, 0);
  const totalItems = units.reduce((s, u) => s + u.total, 0);
  const overallPct = totalItems > 0 ? Math.round((totalHandled / totalItems) * 100) : 0;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-slate-800 text-white sticky top-0 z-30">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button onClick={goBack} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
                <ArrowRight className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-base font-bold flex items-center gap-2">
                  🟫 ריצוף — {floor_name}
                </h1>
                <p className="text-xs text-slate-300 mt-0.5">
                  {completedCount}/{units.length} דירות הושלמו
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => load()} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
                <RefreshCw className="w-4 h-4" />
              </button>
              <div className="text-left">
                <div className={`text-lg font-bold ${overallPct === 100 ? 'text-emerald-400' : overallPct > 0 ? 'text-amber-400' : 'text-slate-400'}`}>{overallPct}%</div>
                <div className="text-[10px] text-slate-400">{totalHandled}/{totalItems}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-4 space-y-2">
        {units.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <Home className="w-10 h-10 mx-auto mb-3 opacity-50" />
            <p className="text-sm">לא נמצאו דירות בקומה זו</p>
          </div>
        ) : (
          units.map(unit => {
            const cfg = STATUS_CONFIG[unit.status] || STATUS_CONFIG.not_started;
            const Icon = STATUS_ICONS[unit.status] || AlertCircle;
            const pct = unit.total > 0 ? Math.round((unit.handled_count / unit.total) * 100) : 0;
            const isNavigating = navigatingUnit === unit.unit_id;
            const barColor = unit.status === 'approved' ? 'bg-emerald-400' : pct > 0 ? 'bg-amber-400' : 'bg-slate-200';

            return (
              <button
                key={unit.unit_id}
                onClick={() => handleUnitClick(unit)}
                disabled={isNavigating}
                className={`w-full text-right p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm transition-all ${cfg.accent} ${isNavigating ? 'opacity-60' : ''}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {isNavigating ? (
                      <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                    ) : (
                      <Home className="w-4 h-4 text-slate-400" />
                    )}
                    <span className="text-sm font-bold text-slate-700">
                      {unit.unit_name || `דירה ${unit.unit_no}`}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ${cfg.color}`}>
                      <Icon className="w-3 h-3" />
                      {cfg.label}
                    </span>
                    <span className="text-xs font-medium text-slate-500">{unit.handled_count}/{unit.total}</span>
                  </div>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-1.5" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`התקדמות דירה ${pct}%`}>
                  <div
                    className={`h-1.5 rounded-full transition-all ${barColor}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
