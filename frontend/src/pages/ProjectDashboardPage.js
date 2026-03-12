import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, buildingService, qcService } from '../services/api';
import { qcFloorStatusLabel } from '../utils/qcLabels';
import { useAuth } from '../contexts/AuthContext';
import ProjectSwitcher from '../components/ProjectSwitcher';
import NotificationBell from '../components/NotificationBell';
import { tRole } from '../i18n';
import { toast } from 'sonner';
import {
  ArrowRight, AlertTriangle, Clock, CheckCircle2, Users, Timer,
  ChevronLeft, Building2, HardHat, Loader2, RefreshCw,
  ExternalLink, TrendingUp, BarChart3, AlertCircle, Shield, ClipboardCheck, Settings
} from 'lucide-react';

const formatHours = (h) => {
  if (!h || h === 0) return '—';
  if (h < 1) return `${Math.round(h * 60)} דק׳`;
  if (h < 24) return `${Math.round(h)} שע׳`;
  const days = Math.round(h / 24 * 10) / 10;
  return `${days} ימים`;
};

const KpiCard = ({ icon: Icon, label, value, sub, color, onClick, accent }) => (
  <div
    onClick={onClick}
    className={`bg-white rounded-xl border p-3 shadow-sm transition-all ${
      onClick ? 'cursor-pointer hover:shadow-md hover:border-amber-200 active:scale-[0.98]' : ''
    }`}
  >
    <div className="flex items-center justify-between mb-1">
      <Icon className={`w-4 h-4 ${color}`} />
      {onClick && <ExternalLink className="w-3 h-3 text-slate-300" />}
    </div>
    <p className={`text-2xl font-bold ${accent || 'text-slate-800'}`}>{value ?? 0}</p>
    <p className="text-xs text-slate-500 mt-0.5">{label}</p>
    {sub && <p className="text-[10px] text-slate-400 mt-0.5">{sub}</p>}
  </div>
);

const SectionHeader = ({ icon: Icon, title, count, color }) => (
  <div className="flex items-center gap-2 mb-2">
    <Icon className={`w-4 h-4 ${color}`} />
    <h3 className="text-sm font-bold text-slate-700">{title}</h3>
    {count > 0 && (
      <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-full">{count}</span>
    )}
  </div>
);

const EmptySection = ({ text }) => (
  <div className="text-center py-6 text-sm text-slate-400">{text}</div>
);

const statusLabels = {
  pending_manager_approval: 'ממתין לאישור',
  waiting_verify: 'ממתין לאימות',
  open: 'פתוח',
  assigned: 'שויך',
  in_progress: 'בביצוע',
  pending_contractor_proof: 'ממתין להוכחה',
  returned_to_contractor: 'הוחזר לקבלן',
  reopened: 'נפתח מחדש',
  closed: 'סגור',
};

const statusColors = {
  pending_manager_approval: 'bg-amber-100 text-amber-700',
  waiting_verify: 'bg-blue-100 text-blue-700',
  open: 'bg-red-100 text-red-700',
  in_progress: 'bg-blue-100 text-blue-700',
  returned_to_contractor: 'bg-orange-100 text-orange-700',
};

const EMPTY_KPIS = {
  open_total: 0, open_last7: 0, in_progress: 0, closed_total: 0, closed_last7: 0,
  pending_approval: 0, overdue: 0, team_count: 0,
  sla_response_7d: 0, sla_close_7d: 0, sla_response_30d: 0, sla_close_30d: 0,
};

export default function ProjectDashboardPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [qcSummary, setQcSummary] = useState(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    setError(null);
    setQcSummary(null);
    try {
      const [dashData, projData] = await Promise.all([
        projectService.getDashboard(projectId),
        projectService.get(projectId),
      ]);
      setData(dashData);
      setProject(projData);

      try {
        const hierarchy = await buildingService.getHierarchy(projectId);
        const floorIds = [];
        (hierarchy || []).forEach(b => (b.floors || []).forEach(f => floorIds.push(f.id)));
        if (floorIds.length > 0) {
          const statuses = await qcService.getFloorsBatchStatus(floorIds);
          const counts = { not_started: 0, in_progress: 0, pending_review: 0, submitted: 0, total: floorIds.length };
          Object.values(statuses).forEach(raw => { const s = typeof raw === 'string' ? raw : raw?.badge || 'not_started'; if (counts[s] !== undefined) counts[s]++; });
          setQcSummary(counts);
        }
      } catch {}
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error('אין לך הרשאה למרכז ניהול זה');
        navigate('/projects');
      } else {
        setError('שגיאה בטעינת מרכז ניהול');
        toast.error('שגיאה בטעינת מרכז ניהול');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [projectId, navigate]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center" dir="rtl">
        <div className="text-center space-y-3">
          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
          <p className="text-slate-600">{error}</p>
          <button onClick={() => load()} className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 transition-colors">
            נסה שוב
          </button>
        </div>
      </div>
    );
  }

  if (!data || !project) return null;

  const kpis = data.kpis || EMPTY_KPIS;
  const pending_approvals = data.pending_approvals || [];
  const stuck_contractors = data.stuck_contractors || [];
  const load_by_building = data.load_by_building || [];
  const contractor_quality = data.contractor_quality || [];
  const role = data.role || '';
  const isPmOrOwner = role === 'project_manager';
  const showPendingApprovals = isPmOrOwner && pending_approvals.length > 0;

  return (
    <div className="min-h-screen bg-slate-50 pb-24" dir="rtl">
      <header className="bg-slate-800 text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate(`/projects/${projectId}/control`)} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors" title="חזרה">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <ProjectSwitcher currentProjectId={projectId} currentProjectName={project.name} />
            <div className="flex items-center gap-2">
              <p className="text-xs text-slate-400">מרכז ניהול</p>
              {role && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-1 ${
                  isPmOrOwner ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-600 text-slate-300'
                }`}>
                  <Shield className="w-2.5 h-2.5" />
                  {tRole(role)}
                </span>
              )}
            </div>
          </div>
          <NotificationBell />
          <button
            onClick={() => navigate('/settings/account')}
            className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors"
            title="הגדרות חשבון"
          >
            <Settings className="w-4 h-4" />
          </button>
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors"
            title="רענן"
          >
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 pt-4 space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
          <KpiCard
            icon={AlertTriangle}
            label="ליקויים פתוחים"
            value={kpis.open_total}
            sub={`+${kpis.open_last7} בשבוע האחרון`}
            color="text-red-500"
            accent={kpis.open_total > 0 ? 'text-red-600' : 'text-slate-800'}
            onClick={() => navigate(`/projects/${projectId}/tasks?statusChip=open&from=dashboard`)}
          />
          <KpiCard
            icon={TrendingUp}
            label="בביצוע"
            value={kpis.in_progress}
            color="text-blue-500"
            onClick={() => navigate(`/projects/${projectId}/tasks?statusChip=in_progress&from=dashboard`)}
          />
          <KpiCard
            icon={CheckCircle2}
            label="נסגרו"
            value={kpis.closed_total}
            sub={`${kpis.closed_last7} בשבוע האחרון`}
            color="text-green-500"
            onClick={() => navigate(`/projects/${projectId}/tasks?statusChip=closed&from=dashboard`)}
          />
          {isPmOrOwner && (
            <KpiCard
              icon={Clock}
              label="ממתינות לאישור"
              value={kpis.pending_approval}
              color="text-amber-500"
              accent={kpis.pending_approval > 0 ? 'text-amber-600' : 'text-slate-800'}
              onClick={() => navigate(`/projects/${projectId}/tasks?statusChip=pending_manager_approval&from=dashboard`)}
            />
          )}
          <KpiCard
            icon={AlertCircle}
            label="באיחור"
            value={kpis.overdue}
            color="text-orange-500"
            accent={kpis.overdue > 0 ? 'text-orange-600' : 'text-slate-800'}
            onClick={() => navigate(`/projects/${projectId}/tasks?overdue=true&from=dashboard`)}
          />
          <KpiCard
            icon={Users}
            label="חברי צוות"
            value={kpis.team_count}
            color="text-purple-500"
            onClick={() => navigate(`/projects/${projectId}/control?tab=team`)}
          />
        </div>

        <div className="bg-white rounded-xl border shadow-sm p-3">
          <div className="flex items-center gap-2 mb-2">
            <Timer className="w-4 h-4 text-indigo-500" />
            <h3 className="text-sm font-bold text-slate-700">לוחות זמנים</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center p-2 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500 mb-1">זמן תגובה ממוצע</p>
              <p className="text-lg font-bold text-slate-800">{formatHours(kpis.sla_response_7d)}</p>
              <p className="text-[10px] text-slate-400">7 ימים</p>
            </div>
            <div className="text-center p-2 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500 mb-1">זמן סגירה ממוצע</p>
              <p className="text-lg font-bold text-slate-800">{formatHours(kpis.sla_close_7d)}</p>
              <p className="text-[10px] text-slate-400">7 ימים</p>
            </div>
            <div className="text-center p-2 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500 mb-1">זמן תגובה ממוצע</p>
              <p className="text-lg font-bold text-slate-800">{formatHours(kpis.sla_response_30d)}</p>
              <p className="text-[10px] text-slate-400">30 ימים</p>
            </div>
            <div className="text-center p-2 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500 mb-1">זמן סגירה ממוצע</p>
              <p className="text-lg font-bold text-slate-800">{formatHours(kpis.sla_close_30d)}</p>
              <p className="text-[10px] text-slate-400">30 ימים</p>
            </div>
          </div>
        </div>

        {qcSummary && qcSummary.total > 0 && (
          <div className="bg-white rounded-xl border shadow-sm p-3">
            <div className="flex items-center justify-between mb-2">
              <SectionHeader icon={ClipboardCheck} title="בקרת ביצוע" count={null} color="text-amber-500" />
              <button
                onClick={() => navigate(`/projects/${projectId}/qc`)}
                className="text-xs font-medium text-amber-600 hover:text-amber-700 flex items-center gap-1"
              >
                פתח <ChevronLeft className="w-3 h-3" />
              </button>
            </div>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="bg-slate-50 rounded-lg p-2">
                <div className="text-lg font-bold text-slate-500">{qcSummary.not_started}</div>
                <div className="text-[10px] text-slate-400 font-medium">{qcFloorStatusLabel('not_started')}</div>
              </div>
              <div className="bg-amber-50 rounded-lg p-2">
                <div className="text-lg font-bold text-amber-600">{qcSummary.in_progress}</div>
                <div className="text-[10px] text-amber-500 font-medium">{qcFloorStatusLabel('in_progress')}</div>
              </div>
              <div className="bg-slate-50 rounded-lg p-2">
                <div className="text-lg font-bold text-slate-600">{qcSummary.pending_review}</div>
                <div className="text-[10px] text-slate-400 font-medium">{qcFloorStatusLabel('pending_review')}</div>
              </div>
              <div className="bg-slate-50 rounded-lg p-2">
                <div className="text-lg font-bold text-slate-600">{qcSummary.submitted}</div>
                <div className="text-[10px] text-slate-400 font-medium">{qcFloorStatusLabel('submitted')}</div>
              </div>
            </div>
            {qcSummary.total > 0 && (
              <div className="mt-2">
                <div className="w-full bg-slate-100 rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-amber-400 transition-all"
                    style={{ width: `${Math.round((qcSummary.submitted / qcSummary.total) * 100)}%` }}
                  />
                </div>
                <p className="text-[10px] text-slate-400 mt-1 text-center">
                  {qcSummary.submitted}/{qcSummary.total} קומות נבדקו
                </p>
              </div>
            )}
          </div>
        )}

        {showPendingApprovals && (
          <div className="bg-white rounded-xl border shadow-sm p-3">
            <SectionHeader icon={Clock} title="ממתין לאישור שלי" count={pending_approvals.length} color="text-amber-500" />
            <div className="space-y-1.5">
              {pending_approvals.slice(0, 10).map(task => (
                <button
                  key={task.id}
                  onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: `/projects/${projectId}/dashboard` } })}
                  className="w-full flex items-center gap-2 p-2.5 rounded-lg hover:bg-amber-50 border border-transparent hover:border-amber-200 transition-all text-right"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-700 truncate">{task.title}</p>
                    <p className="text-xs text-slate-400">{task.updated_at ? new Date(task.updated_at).toLocaleDateString('he-IL') : ''}</p>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap ${statusColors[task.status] || 'bg-slate-100 text-slate-600'}`}>
                    {statusLabels[task.status] || task.status}
                  </span>
                  <ChevronLeft className="w-4 h-4 text-slate-300 shrink-0" />
                </button>
              ))}
              {pending_approvals.length > 10 && (
                <button
                  onClick={() => navigate(`/projects/${projectId}/tasks?statusChip=pending_manager_approval&from=dashboard`)}
                  className="w-full text-center text-xs text-amber-600 hover:text-amber-700 py-2 font-medium"
                >
                  הצג את כל {pending_approvals.length} המשימות →
                </button>
              )}
            </div>
          </div>
        )}

        {stuck_contractors.length > 0 && (
          <div className="bg-white rounded-xl border shadow-sm p-3">
            <SectionHeader icon={AlertCircle} title="תקוע אצל קבלנים" count={stuck_contractors.reduce((sum, c) => sum + c.stuck_count, 0)} color="text-orange-500" />
            <div className="space-y-2">
              {stuck_contractors.map(contractor => (
                <div key={contractor.contractor_id} className="border border-orange-100 rounded-lg p-2.5 bg-orange-50/50">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <HardHat className="w-4 h-4 text-orange-500" />
                      <span className="text-sm font-medium text-slate-700">{contractor.contractor_name || 'קבלן'}</span>
                    </div>
                    <span className="text-xs font-bold text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full">
                      {contractor.stuck_count} תקועות
                    </span>
                  </div>
                  <div className="space-y-1">
                    {contractor.tasks.slice(0, 3).map(task => (
                      <button
                        key={task.id}
                        onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: `/projects/${projectId}/dashboard` } })}
                        className="w-full flex items-center gap-2 text-right text-xs text-slate-600 hover:text-amber-700 py-0.5"
                      >
                        <span className="truncate flex-1">• {task.title}</span>
                        <ChevronLeft className="w-3 h-3 text-slate-300 shrink-0" />
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {load_by_building.length > 0 && (
          <div className="bg-white rounded-xl border shadow-sm p-3">
            <SectionHeader icon={Building2} title="עומס לפי מבנה" count={null} color="text-blue-500" />
            <div className="space-y-1.5">
              {load_by_building.map((b, i) => {
                const max = load_by_building[0]?.open_count || 1;
                const pct = Math.round((b.open_count / max) * 100);
                return (
                  <div key={b.building_id} className="flex items-center gap-3">
                    <span className="text-xs text-slate-600 w-24 truncate font-medium">{b.building_name || `מבנה ${i + 1}`}</span>
                    <div className="flex-1 h-6 bg-slate-100 rounded-full overflow-hidden relative">
                      <div
                        className="h-full bg-gradient-to-l from-blue-500 to-blue-400 rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-slate-700">
                        {b.open_count}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="bg-white rounded-xl border shadow-sm p-3">
          <SectionHeader icon={BarChart3} title="קבלנים — איכות" count={contractor_quality.length} color="text-purple-500" />
          {contractor_quality.length === 0 ? (
            <EmptySection text="אין נתוני קבלנים" />
          ) : (
            <div className="overflow-x-auto -mx-1">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-slate-500 border-b">
                    <th className="text-right py-2 px-1 font-medium">קבלן</th>
                    <th className="text-center py-2 px-1 font-medium">פתוח</th>
                    <th className="text-center py-2 px-1 font-medium">סגור</th>
                    <th className="text-center py-2 px-1 font-medium">דחיות</th>
                  </tr>
                </thead>
                <tbody>
                  {contractor_quality.slice(0, 15).map(c => (
                    <tr key={c.contractor_id} className="border-b border-slate-50 hover:bg-slate-50">
                      <td className="py-2 px-1 font-medium text-slate-700 truncate max-w-[120px]">
                        {c.contractor_name || 'קבלן'}
                      </td>
                      <td className="text-center py-2 px-1">
                        <span className={`text-xs font-bold ${c.open > 0 ? 'text-red-600' : 'text-slate-400'}`}>{c.open}</span>
                      </td>
                      <td className="text-center py-2 px-1">
                        <span className="text-xs font-bold text-green-600">{c.closed}</span>
                      </td>
                      <td className="text-center py-2 px-1">
                        <span className={`text-xs font-bold ${c.rework > 0 ? 'text-orange-600' : 'text-slate-400'}`}>{c.rework}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {kpis.open_total === 0 && kpis.closed_total === 0 && (
          <div className="bg-white rounded-xl border shadow-sm p-8 text-center">
            <CheckCircle2 className="w-12 h-12 text-green-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">אין ליקויים בפרויקט זה עדיין</p>
            <p className="text-slate-400 text-xs mt-1">צרו ליקוי ראשון כדי לראות נתוני מרכז ניהול</p>
          </div>
        )}
      </div>
    </div>
  );
}
