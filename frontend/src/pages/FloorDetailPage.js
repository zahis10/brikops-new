import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { qcService } from '../services/api';
import {
  ArrowRight, Loader2, ClipboardCheck,
  CheckCircle2, XCircle, Clock, Building2, Layers, RefreshCw, Lock,
  AlertCircle, RotateCcw, ShieldCheck, FileText
} from 'lucide-react';
import { qcStageStatusLabel } from '../utils/qcLabels';
import { getStageVisualStatusLite, getFloorVisualStatus, getQualityBadge, getReviewBadge, getFloorQualityBadge } from '../utils/qcVisualStatus';

const STAGE_STATUS_ICONS = {
  approved: ShieldCheck,
  rejected: XCircle,
  pending_review: Lock,
  reopened: RotateCcw,
  ready: CheckCircle2,
  draft: null,
};

const SummaryCard = ({ summary, floorVisual }) => {
  if (!summary) return null;
  const { total, pass, fail, pending } = summary;
  const donePct = total > 0 ? Math.round(((pass + fail) / total) * 100) : 0;

  return (
    <div className={`bg-white rounded-xl border p-4 shadow-sm ${floorVisual.borderColor}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-700">סיכום קומה</h3>
        <span className={`text-lg font-bold ${floorVisual.pctColor}`}>{donePct}%</span>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2.5 mb-3">
        <div className={`h-2.5 rounded-full transition-all ${floorVisual.barColor}`} style={{ width: `${donePct}%` }} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-emerald-50 rounded-lg p-2">
          <div className="text-lg font-bold text-emerald-600">{pass}</div>
          <div className="text-[10px] text-emerald-600 font-medium flex items-center justify-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> הושלמו
          </div>
        </div>
        <div className="bg-red-50 rounded-lg p-2">
          <div className="text-lg font-bold text-red-600">{fail}</div>
          <div className="text-[10px] text-red-600 font-medium flex items-center justify-center gap-1">
            <XCircle className="w-3 h-3" /> נכשלו
          </div>
        </div>
        <div className="bg-slate-50 rounded-lg p-2">
          <div className="text-lg font-bold text-slate-500">{pending}</div>
          <div className="text-[10px] text-slate-500 font-medium flex items-center justify-center gap-1">
            <Clock className="w-3 h-3" /> בהמתנה
          </div>
        </div>
      </div>
    </div>
  );
};

const StageCard = ({ stage, onClick, isActive }) => {
  const pct = stage.total > 0 ? Math.round((stage.done / stage.total) * 100) : 0;
  const status = stage.computed_status || 'draft';
  const vs = getStageVisualStatusLite(stage);
  const Icon = STAGE_STATUS_ICONS[status] || null;
  const qBadge = getQualityBadge(stage);
  const rBadge = getReviewBadge(stage);
  const stageAccent = isActive ? ''
    : status === 'approved' ? 'border-r-4 border-green-400'
    : status === 'rejected' ? 'border-r-4 border-red-400'
    : status === 'pending_review' ? 'border-r-4 border-blue-400'
    : status === 'reopened' ? 'border-r-4 border-amber-400'
    : (status === 'draft' || status === 'ready') && stage.done > 0 ? 'border-r-4 border-amber-300'
    : '';
  return (
    <button
      onClick={onClick}
      className={`w-full text-right p-3 rounded-xl border transition-all ${
        isActive ? 'border-amber-300 bg-amber-50 shadow-sm' : `border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm ${stageAccent}`
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-bold text-slate-700 leading-tight">{stage.title}</span>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${vs.chipColor}`}>
          {stage.done}/{stage.total}
        </span>
      </div>
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        {stage.has_prework_items && (
          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
            <FileText className="w-3 h-3" />
            כולל תיעוד לפני עבודה
          </span>
        )}
        <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${qBadge.color}`}>
          {qBadge.label}
        </span>
        {rBadge && (
          <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${rBadge.color}`}>
            {Icon && <Icon className="w-3 h-3" />}
            {rBadge.label}
          </span>
        )}
        {!rBadge && (
          <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${vs.badgeColor}`}>
            {Icon && <Icon className="w-3 h-3" />}
            {qcStageStatusLabel(status)}
          </span>
        )}
      </div>
      <div className="w-full bg-slate-100 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${vs.barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </button>
  );
};

export default function FloorDetailPage() {
  const { projectId, floorId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await qcService.getFloorRun(floorId);
      setData(result);
    } catch (err) {
      if (err.response?.status === 403) {
        setError('אין הרשאה לצפות בבקרת ביצוע');
      } else {
        setError(err.response?.data?.detail || 'שגיאה בטעינת בקרת ביצוע');
      }
    } finally {
      setLoading(false);
    }
  }, [floorId]);

  useEffect(() => { load(); }, [load]);

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
          <button onClick={() => { if (window.history.length > 2) { navigate(-1); } else { navigate(`/projects/${projectId}/qc`); } }} className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm">חזרה לבקרת ביצוע</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { stages, building_name, floor_name, template_name, summary } = data;
  const totalDone = stages.reduce((s, st) => s + st.done, 0);
  const totalItems = stages.reduce((s, st) => s + st.total, 0);
  const totalPct = totalItems > 0 ? Math.round((totalDone / totalItems) * 100) : 0;
  const floorVisual = getFloorVisualStatus(stages);
  const floorQBadge = getFloorQualityBadge(stages);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-slate-800 text-white sticky top-0 z-30">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button onClick={() => { if (window.history.length > 2) { navigate(-1); } else { navigate(`/projects/${projectId}/qc`); } }} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
                <ArrowRight className="w-5 h-5" />
              </button>
              <div>
                <div className="flex items-center gap-2 text-xs text-slate-300">
                  <Building2 className="w-3 h-3" />
                  <span>{building_name}</span>
                  <span>›</span>
                  <Layers className="w-3 h-3" />
                  <span>{floor_name}</span>
                </div>
                <h1 className="text-base font-bold flex items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-amber-400" />
                  בקרת ביצוע
                </h1>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${floorQBadge.color}`}>
                    איכות: {floorQBadge.label}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => load()} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
                <RefreshCw className="w-4 h-4" />
              </button>
              <div className="text-left">
                <div className={`text-lg font-bold ${floorVisual.pctColor}`}>{totalPct}%</div>
                <div className="text-[10px] text-slate-400">{totalDone}/{totalItems}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-4 space-y-4">
        <SummaryCard summary={summary} floorVisual={floorVisual} />

        <div className="text-xs text-slate-400 font-medium">{template_name}</div>

        <div className="grid grid-cols-2 gap-2">
          {stages.map(stage => (
            <StageCard
              key={stage.id}
              stage={stage}
              isActive={false}
              onClick={() => navigate(`/projects/${projectId}/qc/floors/${floorId}/run/${data.run.id}/stage/${stage.id}`)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
