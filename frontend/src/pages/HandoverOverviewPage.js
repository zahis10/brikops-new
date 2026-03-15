import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { handoverService } from '../services/api';
import {
  ChevronRight, Loader2, Building2, FileSignature, ChevronDown, ChevronUp,
  AlertTriangle, CheckCircle2, Clock, Edit3
} from 'lucide-react';
import ProjectSwitcher from '../components/ProjectSwitcher';
import NotificationBell from '../components/NotificationBell';
import UserDrawer from '../components/UserDrawer';

const STATUS_CONFIG = {
  signed: { label: 'חתום', color: 'bg-green-100 text-green-700', icon: CheckCircle2 },
  partially_signed: { label: 'חתום חלקית', color: 'bg-amber-100 text-amber-700', icon: Edit3 },
  in_progress: { label: 'בביצוע', color: 'bg-blue-100 text-blue-700', icon: Clock },
  draft: { label: 'טיוטה', color: 'bg-slate-100 text-slate-500', icon: Clock },
};

const StatusBadge = ({ status, count }) => {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.draft;
  if (!count) return null;
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${config.color}`}>
      <Icon className="w-3 h-3" />
      {count} {config.label}
    </span>
  );
};

const ProgressBar = ({ label, signed, partial, inProgress, draft, total }) => {
  if (total === 0) return null;
  const signedPct = (signed / total) * 100;
  const partialPct = (partial / total) * 100;
  const inProgressPct = (inProgress / total) * 100;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-600">{label}</span>
        <span className="text-xs text-slate-400">{signed + partial + inProgress + draft} / {total} דירות</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden flex">
        {signedPct > 0 && <div className="bg-green-500 h-full" style={{ width: `${signedPct}%` }} />}
        {partialPct > 0 && <div className="bg-amber-400 h-full" style={{ width: `${partialPct}%` }} />}
        {inProgressPct > 0 && <div className="bg-blue-400 h-full" style={{ width: `${inProgressPct}%` }} />}
      </div>
    </div>
  );
};

export default function HandoverOverviewPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedBuildings, setExpandedBuildings] = useState({});

  const loadSummary = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await handoverService.getSummary(projectId);
      setSummary(data);
    } catch (err) {
      console.error('[HandoverOverview] Failed to load summary', err);
      setError('שגיאה בטעינת נתוני מסירות');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  const toggleBuilding = (id) => {
    setExpandedBuildings(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const initialTotal = summary
    ? summary.initial_draft + summary.initial_in_progress + summary.initial_partially_signed + summary.initial_signed
    : 0;
  const finalTotal = summary
    ? summary.final_draft + summary.final_in_progress + summary.final_partially_signed + summary.final_signed
    : 0;
  const hasData = initialTotal > 0 || finalTotal > 0;

  return (
    <div className="min-h-screen bg-slate-50 pb-20" dir="rtl">
      <header className="bg-gradient-to-br from-slate-900 to-slate-800 text-white sticky top-0 z-50 shadow-md">
        <div className="max-w-[1100px] mx-auto px-4 py-3 flex items-center gap-2">
          <button onClick={() => navigate(`/projects/${projectId}`)} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors">
            <ChevronRight className="w-4 h-4" />
          </button>
          <ProjectSwitcher currentProjectId={projectId} />
          <div className="flex-1" />
          <NotificationBell />
          <UserDrawer user={user} />
        </div>
      </header>

      <div className="max-w-[560px] mx-auto px-4 pt-4">
        <div className="flex items-center gap-2 mb-4">
          <FileSignature className="w-5 h-5 text-amber-500" />
          <h1 className="text-lg font-bold text-slate-800">מסירות</h1>
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
            <p className="text-sm text-red-600">{error}</p>
            <button onClick={loadSummary} className="mt-3 text-xs text-red-500 underline">נסה שוב</button>
          </div>
        ) : !hasData ? (
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center">
            <FileSignature className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <h2 className="text-sm font-semibold text-slate-600 mb-1">אין נתוני מסירות</h2>
            <p className="text-xs text-slate-400">טרם נוצרו פרוטוקולי מסירה בפרויקט זה</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
              <h2 className="text-sm font-bold text-slate-700">סיכום כללי</h2>

              <ProgressBar
                label="מסירה ראשונית"
                signed={summary.initial_signed}
                partial={summary.initial_partially_signed}
                inProgress={summary.initial_in_progress}
                draft={summary.initial_draft}
                total={summary.total_units}
              />

              <ProgressBar
                label="מסירה סופית"
                signed={summary.final_signed}
                partial={summary.final_partially_signed}
                inProgress={summary.final_in_progress}
                draft={summary.final_draft}
                total={summary.total_units}
              />

              <div className="flex flex-wrap gap-1.5 pt-1">
                <StatusBadge status="signed" count={summary.initial_signed + summary.final_signed} />
                <StatusBadge status="partially_signed" count={summary.initial_partially_signed + summary.final_partially_signed} />
                <StatusBadge status="in_progress" count={summary.initial_in_progress + summary.final_in_progress} />
                <StatusBadge status="draft" count={summary.initial_draft + summary.final_draft} />
              </div>

              {summary.open_handover_defects > 0 && (
                <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <span className="text-xs text-red-700 font-medium">{summary.open_handover_defects} ליקויי מסירה פתוחים</span>
                </div>
              )}
            </div>

            {summary.buildings && summary.buildings.length > 0 && (
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-100">
                  <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-slate-400" />
                    לפי מבנה
                  </h2>
                </div>

                <div className="divide-y divide-slate-100">
                  {summary.buildings.map(b => {
                    const bInitial = b.initial_draft + b.initial_in_progress + b.initial_partially_signed + b.initial_signed;
                    const bFinal = b.final_draft + b.final_in_progress + b.final_partially_signed + b.final_signed;
                    const expanded = expandedBuildings[b.building_id];

                    return (
                      <div key={b.building_id}>
                        <button
                          onClick={() => toggleBuilding(b.building_id)}
                          className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <Building2 className="w-4 h-4 text-slate-400" />
                            <span className="text-sm font-medium text-slate-700">{b.building_name}</span>
                            <span className="text-[10px] text-slate-400">({bInitial + bFinal} פרוטוקולים)</span>
                          </div>
                          {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                        </button>

                        {expanded && (
                          <div className="px-4 pb-3 space-y-2 bg-slate-50/50">
                            {bInitial > 0 && (
                              <div className="space-y-1">
                                <span className="text-[11px] font-medium text-slate-500">מסירה ראשונית</span>
                                <div className="flex flex-wrap gap-1">
                                  <StatusBadge status="signed" count={b.initial_signed} />
                                  <StatusBadge status="partially_signed" count={b.initial_partially_signed} />
                                  <StatusBadge status="in_progress" count={b.initial_in_progress} />
                                  <StatusBadge status="draft" count={b.initial_draft} />
                                </div>
                              </div>
                            )}
                            {bFinal > 0 && (
                              <div className="space-y-1">
                                <span className="text-[11px] font-medium text-slate-500">מסירה סופית</span>
                                <div className="flex flex-wrap gap-1">
                                  <StatusBadge status="signed" count={b.final_signed} />
                                  <StatusBadge status="partially_signed" count={b.final_partially_signed} />
                                  <StatusBadge status="in_progress" count={b.final_in_progress} />
                                  <StatusBadge status="draft" count={b.final_draft} />
                                </div>
                              </div>
                            )}
                            {bInitial === 0 && bFinal === 0 && (
                              <p className="text-xs text-slate-400 py-1">אין פרוטוקולי מסירה במבנה זה</p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
