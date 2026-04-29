import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, buildingService, qcService, handoverService } from '../services/api';
import { qcFloorStatusLabel } from '../utils/qcLabels';
import { useAuth } from '../contexts/AuthContext';
import ProjectSwitcher from '../components/ProjectSwitcher';
import NotificationBell from '../components/NotificationBell';
import HamburgerMenu from '../components/HamburgerMenu';
import { tRole } from '../i18n';
import { toast } from 'sonner';
import {
  ArrowRight, AlertTriangle, Clock, CheckCircle2, Users, Timer,
  ChevronLeft, ChevronDown, Building2, HardHat, Loader2, RefreshCw,
  ExternalLink, BarChart3, AlertCircle, Shield, ClipboardCheck,
  Construction, FileSignature, Send, MessageSquare
} from 'lucide-react';

import OfflineState from '../components/OfflineState';
import { useOnlineStatus } from '../hooks/useOnlineStatus';

const TeamActivitySection = React.lazy(() => import('../components/TeamActivitySection'));

const formatHours = (h) => {
  if (!h || h === 0) return '—';
  if (h < 1) return `${Math.round(h * 60)} דק׳`;
  if (h < 24) return `${Math.round(h)} שע׳`;
  const days = Math.round(h / 24 * 10) / 10;
  return `${days} ימים`;
};

const KpiCard = ({ icon: Icon, label, value, sub, onClick, bg, borderColor, numberColor, urgent, title }) => (
  <div
    onClick={onClick}
    title={title}
    className={`rounded-xl p-3 transition-all border-r-4 ${bg} ${
      onClick ? 'cursor-pointer hover:shadow-md hover:-translate-y-0.5 active:scale-[0.98]' : ''
    }`}
    style={{ borderRightColor: borderColor }}
  >
    <div className="flex items-center justify-between mb-1">
      <Icon className="w-4 h-4" style={{ color: borderColor }} />
      <div className="flex items-center gap-1.5">
        {urgent && <span className="relative flex h-2.5 w-2.5"><span className="animate-pulse absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span></span>}
        {onClick && <ExternalLink className="w-3 h-3 text-slate-300" />}
      </div>
    </div>
    <p className={`${urgent ? 'text-4xl' : 'text-3xl'} font-black ${numberColor}`}>{value ?? 0}</p>
    <p className={`text-xs mt-0.5 ${urgent ? 'text-white/80 font-medium' : 'text-slate-500'}`}>{label}</p>
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

const getSlaBoxBg = (hours) => {
  if (!hours || hours === 0) return 'bg-slate-50';
  if (hours < 24) return 'bg-green-50';
  if (hours > 48) return 'bg-orange-50';
  return 'bg-slate-50';
};

const getBarColor = (index, total) => {
  if (total <= 1) return 'from-red-500 to-red-400';
  const ratio = index / (total - 1);
  if (ratio < 0.33) return 'from-red-500 to-red-400';
  if (ratio < 0.66) return 'from-orange-500 to-amber-400';
  return 'from-green-500 to-emerald-400';
};

const getBarTextColor = (index, total) => {
  if (total <= 1) return 'text-red-600';
  const ratio = index / (total - 1);
  if (ratio < 0.33) return 'text-red-600';
  if (ratio < 0.66) return 'text-orange-600';
  return 'text-green-600';
};

export default function ProjectDashboardPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [data, setData] = useState(null);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [qcSummary, setQcSummary] = useState(null);
  const [execSummary, setExecSummary] = useState(null);
  const [expandedStages, setExpandedStages] = useState({});
  const [alertsExpanded, setAlertsExpanded] = useState(false);
  const [highlightEntity, setHighlightEntity] = useState(null);
  const [handoverSummary, setHandoverSummary] = useState(null);
  const [sendingDigest, setSendingDigest] = useState(false);
  const [sendingReminder, setSendingReminder] = useState({});
  const stageRefs = useRef({});
  const online = useOnlineStatus();

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    setError(null);
    setQcSummary(null);
    setExecSummary(null);
    setHandoverSummary(null);
    try {
      const [dashResult, projResult, hierarchyResult, execResult, handoverResult] = await Promise.allSettled([
        projectService.getDashboard(projectId),
        projectService.get(projectId),
        (async () => {
          const hierarchy = await buildingService.getHierarchy(projectId);
          const floorIds = [];
          (hierarchy || []).forEach(b => (b.floors || []).forEach(f => floorIds.push(f.id)));
          if (floorIds.length > 0) {
            const statuses = await qcService.getFloorsBatchStatus(floorIds);
            const counts = { not_started: 0, in_progress: 0, pending_review: 0, submitted: 0, total: floorIds.length };
            Object.values(statuses).forEach(raw => { const s = typeof raw === 'string' ? raw : raw?.badge || 'not_started'; if (counts[s] !== undefined) counts[s]++; });
            return counts;
          }
          return null;
        })(),
        qcService.getExecutionSummary(projectId),
        handoverService.getSummary(projectId),
      ]);

      if (dashResult.status === 'rejected' || projResult.status === 'rejected') {
        const err = dashResult.reason || projResult.reason;
        throw err;
      }
      setData(dashResult.value);
      setProject(projResult.value);
      if (hierarchyResult.status === 'fulfilled') setQcSummary(hierarchyResult.value);
      if (execResult.status === 'fulfilled') setExecSummary(execResult.value);
      if (handoverResult.status === 'fulfilled') setHandoverSummary(handoverResult.value);
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

  const handleSendDigest = async () => {
    setSendingDigest(true);
    try {
      await projectService.sendDigest(projectId);
      toast.success('סיכום יומי נשלח בהצלחה');
    } catch (err) {
      const msg = err.response?.data?.detail || 'שגיאה בשליחת סיכום';
      toast.error(msg);
    } finally {
      setSendingDigest(false);
    }
  };

  const handleSendReminder = async (companyId, contractorName) => {
    setSendingReminder(prev => ({ ...prev, [companyId]: true }));
    try {
      await projectService.sendContractorReminder(projectId, companyId);
      toast.success(`תזכורת נשלחה ל${contractorName}`);
    } catch (err) {
      const msg = err.response?.data?.detail || 'שגיאה בשליחת תזכורת';
      toast.error(msg);
    } finally {
      setSendingReminder(prev => ({ ...prev, [companyId]: false }));
    }
  };

  if (!online && !data) {
    return <OfflineState onRetry={() => load()} />;
  }

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
  const isPmOrOwner = role === 'project_manager' || role === 'owner' || role === 'management_team';
  const showPendingApprovals = isPmOrOwner && pending_approvals.length > 0;
  const qcProgress = qcSummary && qcSummary.total > 0 ? Math.round((qcSummary.submitted / qcSummary.total) * 100) : 0;

  return (
    <div className="min-h-0 bg-slate-50 pb-24" dir="rtl">
      <header className="text-white sticky top-0 z-50" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', boxShadow: '0 2px 12px rgba(0,0,0,0.15)' }}>
        <div className="max-w-[1100px] mx-auto px-4 py-3 flex items-center gap-2">
          <button onClick={() => navigate(`/projects/${projectId}/control?workMode=structure`)} className="p-3 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="חזרה">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <ProjectSwitcher currentProjectId={projectId} currentProjectName={project.name} />
            <div className="flex items-center gap-2">
              <p className="text-xs text-slate-400">דשבורד ניהול</p>
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
          <HamburgerMenu slim onNavigate={(path) => navigate(path)} onLogout={() => { logout(); navigate('/login'); }} />
          {isPmOrOwner && (
            <button
              onClick={handleSendDigest}
              disabled={sendingDigest}
              className="p-3 bg-emerald-500/20 border border-emerald-400/30 rounded-[10px] hover:bg-emerald-500/30 transition-colors"
              title="סיכום עכשיו"
            >
              {sendingDigest ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4 text-emerald-300" />}
            </button>
          )}
          <button onClick={() => load(true)} disabled={refreshing} className="p-3 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="רענן">
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      <div className="max-w-[1100px] mx-auto px-4 pt-4 space-y-4">
        <div className="grid grid-cols-3 md:grid-cols-5 gap-2.5">
          <KpiCard
            icon={AlertTriangle}
            label="פתוחים"
            value={kpis.open_total}
            sub={kpis.open_last7 > 0 ? `+${kpis.open_last7} השבוע` : undefined}
            bg="bg-red-50"
            borderColor="#f87171"
            numberColor={kpis.open_total > 0 ? 'text-red-600' : 'text-slate-800'}
            title="כולל משימות שממתינות לאישור מנהל"
            onClick={() => navigate(`/projects/${projectId}/control?workMode=defects&statusChip=open&from=dashboard`)}
          />
          <KpiCard
            icon={CheckCircle2}
            label="נסגרו"
            value={kpis.closed_total}
            sub={kpis.closed_last7 > 0 ? `${kpis.closed_last7} השבוע` : undefined}
            bg="bg-green-50"
            borderColor="#4ade80"
            numberColor="text-green-600"
            onClick={() => navigate(`/projects/${projectId}/control?workMode=defects&statusChip=closed&from=dashboard`)}
          />
          {isPmOrOwner && (
            <KpiCard
              icon={Clock}
              label="לאישורי"
              value={kpis.pending_approval}
              bg={kpis.pending_approval > 0 ? 'bg-gradient-to-br from-orange-500 to-red-500 shadow-lg shadow-orange-500/25' : 'bg-amber-50'}
              borderColor={kpis.pending_approval > 0 ? '#dc2626' : '#fbbf24'}
              numberColor={kpis.pending_approval > 0 ? 'text-white' : 'text-slate-800'}
              urgent={kpis.pending_approval > 0}
              onClick={() => navigate(`/projects/${projectId}/control?workMode=defects&statusChip=pending_manager_approval&from=dashboard`)}
            />
          )}
          <KpiCard
            icon={AlertCircle}
            label="באיחור"
            value={kpis.overdue}
            bg="bg-orange-50"
            borderColor="#fb923c"
            numberColor={kpis.overdue > 0 ? 'text-orange-600' : 'text-slate-800'}
            onClick={() => navigate(`/projects/${projectId}/control?workMode=defects&overdue=true&from=dashboard`)}
          />
          <KpiCard
            icon={Users}
            label="צוות"
            value={kpis.team_count}
            bg="bg-purple-50"
            borderColor="#c084fc"
            numberColor="text-purple-600"
            onClick={() => navigate(`/projects/${projectId}/control?workMode=structure&tab=team&from=dashboard`)}
          />
        </div>

        {isPmOrOwner && (
          <React.Suspense fallback={null}>
            <TeamActivitySection projectId={projectId} />
          </React.Suspense>
        )}

        {execSummary && execSummary.stages && execSummary.stages.length > 0 && (
          <div className="bg-white rounded-xl border shadow-sm p-4">
            <div className="flex items-center justify-between mb-4">
              <SectionHeader icon={ClipboardCheck} title="סטטוס ביצוע" count={null} color="text-indigo-500" />
              <button
                onClick={() => navigate(`/projects/${projectId}/qc`)}
                className="text-xs font-medium text-amber-600 hover:text-amber-700 flex items-center gap-1"
              >
                בקרת ביצוע <ChevronLeft className="w-3 h-3" />
              </button>
            </div>

            <div className="flex items-center gap-3 mb-4 p-3 bg-gradient-to-l from-indigo-50 to-slate-50 rounded-xl">
              <div className="text-3xl font-black text-indigo-600">{execSummary.overall.completion_pct}%</div>
              <div className="flex-1">
                <p className="text-xs text-slate-500 mb-1">התקדמות כללית</p>
                <div className="w-full bg-slate-200 rounded-full h-2.5">
                  <div
                    className="h-2.5 rounded-full transition-all"
                    style={{
                      width: `${execSummary.overall.completion_pct}%`,
                      background: execSummary.overall.completion_pct === 100
                        ? 'linear-gradient(90deg, #10b981, #34d399)'
                        : execSummary.overall.completion_pct >= 50
                          ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
                          : 'linear-gradient(90deg, #6366f1, #818cf8)',
                    }}
                  />
                </div>
                <p className="text-[10px] text-slate-400 mt-1">{execSummary.overall.completed}/{execSummary.overall.total} שלבים הושלמו</p>
              </div>
            </div>

            {execSummary.alerts && execSummary.alerts.length > 0 && (() => {
              const visibleAlerts = alertsExpanded ? execSummary.alerts : execSummary.alerts.slice(0, 3);
              const hiddenCount = execSummary.alerts.length - 3;
              return (
                <div className="mb-4 space-y-2">
                  {visibleAlerts.map((alert, idx) => {
                    const cfg = alert.severity === 'high'
                      ? { bg: 'bg-red-50', border: 'border-red-200', prefix: '⚠️ צוואר בקבוק', text: 'text-red-800' }
                      : alert.severity === 'medium'
                        ? { bg: 'bg-amber-50', border: 'border-amber-200', prefix: '🔶 שלב תקוע', text: 'text-amber-800' }
                        : { bg: 'bg-slate-50', border: 'border-slate-200', prefix: 'ℹ️', text: 'text-slate-700' };
                    return (
                      <button
                        key={idx}
                        className={`w-full text-right ${cfg.bg} border ${cfg.border} rounded-lg p-3 transition-colors hover:opacity-90`}
                        onClick={() => {
                          if (alert.type === 'bottleneck' && alert.stage_id) {
                            const el = stageRefs.current[alert.stage_id];
                            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                          } else if (alert.type === 'stuck' && alert.stage_id) {
                            setExpandedStages(prev => ({ ...prev, [alert.stage_id]: true }));
                            if (alert.entity_id) setHighlightEntity(alert.entity_id);
                            setTimeout(() => {
                              const el = stageRefs.current[alert.stage_id];
                              if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            }, 100);
                            setTimeout(() => setHighlightEntity(null), 3000);
                          }
                        }}
                      >
                        <div className={`text-sm font-semibold ${cfg.text}`}>{cfg.prefix}</div>
                        <p className={`text-sm ${cfg.text} mt-0.5`}>{alert.message}</p>
                        {alert.detail && <p className="text-xs text-slate-500 mt-0.5">{alert.detail}</p>}
                      </button>
                    );
                  })}
                  {!alertsExpanded && hiddenCount > 0 && (
                    <button
                      onClick={() => setAlertsExpanded(true)}
                      className="w-full text-center text-xs font-medium text-indigo-600 hover:text-indigo-700 py-1"
                    >
                      הצג עוד ({hiddenCount})
                    </button>
                  )}
                </div>
              );
            })()}

            <div className="space-y-1">
              {execSummary.stages.map(stage => {
                const isExpanded = expandedStages[stage.stage_id];
                const pct = stage.completion_pct;
                const barBg = pct === 100 ? '#10b981' : pct >= 50 ? '#f59e0b' : pct > 0 ? '#6366f1' : '#cbd5e1';
                const statusIcon = pct === 100 ? '✅' : pct > 0 ? '🟡' : '⚪';

                return (
                  <div key={stage.stage_id} ref={el => stageRefs.current[stage.stage_id] = el}>
                    <button
                      onClick={() => setExpandedStages(prev => ({ ...prev, [stage.stage_id]: !prev[stage.stage_id] }))}
                      className="w-full flex items-center gap-2 p-2.5 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      <span className="text-lg w-7 text-center shrink-0">{stage.icon}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-semibold text-slate-700 truncate">{stage.title}</span>
                          <span className="text-xs text-slate-400 whitespace-nowrap mr-2">
                            {statusIcon} {stage.completed}/{stage.total} {stage.entity_label}
                          </span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-1.5">
                          <div
                            className="h-1.5 rounded-full transition-all"
                            style={{ width: `${pct}%`, backgroundColor: barBg }}
                          />
                        </div>
                      </div>
                      <ChevronDown className={`w-4 h-4 text-slate-300 shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                    </button>

                    {isExpanded && stage.buildings && (
                      <div className="mr-9 mb-2 space-y-2">
                        {stage.buildings.map(bld => (
                          <div key={bld.building_id} className="bg-slate-50 rounded-lg p-2.5">
                            <div className="flex items-center gap-1.5 mb-1.5">
                              <Building2 className="w-3.5 h-3.5 text-slate-400" />
                              <span className="text-xs font-bold text-slate-600">{bld.building_name}</span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {bld.children.map(child => {
                                const badge = child.status === 'completed' ? 'bg-green-100 text-green-700 border-green-200'
                                  : child.status === 'in_progress' ? 'bg-amber-100 text-amber-700 border-amber-200'
                                  : child.status === 'failed' ? 'bg-red-100 text-red-700 border-red-200'
                                  : 'bg-slate-100 text-slate-500 border-slate-200';
                                const icon = child.status === 'completed' ? '✅'
                                  : child.status === 'in_progress' ? '🟡'
                                  : child.status === 'failed' ? '🔴'
                                  : '⚪';
                                const label = child.type === 'unit'
                                  ? `${child.floor_name ? child.floor_name + ' / ' : ''}${child.name}`
                                  : child.name;
                                const isHighlighted = highlightEntity === child.id;
                                return (
                                  <span
                                    key={child.id}
                                    className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md border font-medium ${badge} ${isHighlighted ? 'ring-2 ring-amber-400 ring-offset-1 animate-pulse' : ''}`}
                                  >
                                    {icon} {label}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {handoverSummary && handoverSummary.total_units > 0 && (() => {
          const hs = handoverSummary;
          const initialTotal = (hs.initial_draft || 0) + (hs.initial_in_progress || 0) + (hs.initial_partially_signed || 0) + (hs.initial_signed || 0);
          const finalTotal = (hs.final_draft || 0) + (hs.final_in_progress || 0) + (hs.final_partially_signed || 0) + (hs.final_signed || 0);
          const initialSigned = hs.initial_signed || 0;
          const finalSigned = hs.final_signed || 0;
          const initialPct = initialTotal > 0 ? Math.round((initialSigned / initialTotal) * 100) : 0;
          const finalPct = finalTotal > 0 ? Math.round((finalSigned / finalTotal) * 100) : 0;
          const hasAny = initialTotal > 0 || finalTotal > 0;
          if (!hasAny) return null;
          return (
            <div className="bg-white rounded-xl border shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <SectionHeader icon={FileSignature} title="מסירות" count={initialTotal + finalTotal} color="text-amber-500" />
                <button
                  onClick={() => navigate(`/projects/${projectId}/handover`)}
                  className="text-xs font-medium text-amber-600 hover:text-amber-700 flex items-center gap-1"
                >
                  צפה <ChevronLeft className="w-3 h-3" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {initialTotal > 0 && (
                  <div className="bg-slate-50 rounded-xl p-3">
                    <p className="text-xs text-slate-500 mb-1">מסירה ראשונית</p>
                    <div className="flex items-end gap-1 mb-2">
                      <span className="text-2xl font-black text-slate-800">{initialSigned}</span>
                      <span className="text-sm text-slate-400 mb-0.5">/ {initialTotal}</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-1.5 mb-1">
                      <div className="h-1.5 rounded-full transition-all" style={{
                        width: `${initialPct}%`,
                        background: initialPct === 100 ? '#22c55e' : '#f59e0b'
                      }} />
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {(hs.initial_in_progress || 0) > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">בתהליך {hs.initial_in_progress}</span>}
                      {(hs.initial_partially_signed || 0) > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">חתום חלקית {hs.initial_partially_signed}</span>}
                      {initialSigned > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">חתום {initialSigned}</span>}
                    </div>
                  </div>
                )}
                {finalTotal > 0 && (
                  <div className="bg-slate-50 rounded-xl p-3">
                    <p className="text-xs text-slate-500 mb-1">מסירה סופית</p>
                    <div className="flex items-end gap-1 mb-2">
                      <span className="text-2xl font-black text-slate-800">{finalSigned}</span>
                      <span className="text-sm text-slate-400 mb-0.5">/ {finalTotal}</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-1.5 mb-1">
                      <div className="h-1.5 rounded-full transition-all" style={{
                        width: `${finalPct}%`,
                        background: finalPct === 100 ? '#22c55e' : '#f59e0b'
                      }} />
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {(hs.final_in_progress || 0) > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">בתהליך {hs.final_in_progress}</span>}
                      {(hs.final_partially_signed || 0) > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">חתום חלקית {hs.final_partially_signed}</span>}
                      {finalSigned > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">חתום {finalSigned}</span>}
                    </div>
                  </div>
                )}
              </div>
              {(hs.open_handover_defects || 0) > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-2 text-red-600 text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  <span>{hs.open_handover_defects} ליקויי מסירה פתוחים</span>
                </div>
              )}
            </div>
          );
        })()}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border shadow-sm p-4">
            <div className="flex items-center gap-2 mb-3">
              <Timer className="w-4 h-4 text-indigo-500" />
              <h3 className="text-sm font-bold text-slate-700">לוחות זמנים</h3>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className={`text-center p-3 rounded-lg ${getSlaBoxBg(kpis.sla_response_7d)}`}>
                <p className="text-xs text-slate-500 mb-1">זמן תגובה ממוצע</p>
                <p className="text-2xl font-extrabold text-slate-800">{formatHours(kpis.sla_response_7d)}</p>
                <p className="text-[10px] text-slate-400">7 ימים</p>
              </div>
              <div className={`text-center p-3 rounded-lg ${getSlaBoxBg(kpis.sla_close_7d)}`}>
                <p className="text-xs text-slate-500 mb-1">זמן סגירה ממוצע</p>
                <p className="text-2xl font-extrabold text-slate-800">{formatHours(kpis.sla_close_7d)}</p>
                <p className="text-[10px] text-slate-400">7 ימים</p>
              </div>
              <div className={`text-center p-3 rounded-lg ${getSlaBoxBg(kpis.sla_response_30d)}`}>
                <p className="text-xs text-slate-500 mb-1">זמן תגובה ממוצע</p>
                <p className="text-2xl font-extrabold text-slate-800">{formatHours(kpis.sla_response_30d)}</p>
                <p className="text-[10px] text-slate-400">30 ימים</p>
              </div>
              <div className={`text-center p-3 rounded-lg ${getSlaBoxBg(kpis.sla_close_30d)}`}>
                <p className="text-xs text-slate-500 mb-1">זמן סגירה ממוצע</p>
                <p className="text-2xl font-extrabold text-slate-800">{formatHours(kpis.sla_close_30d)}</p>
                <p className="text-[10px] text-slate-400">30 ימים</p>
              </div>
            </div>
          </div>

          {qcSummary && qcSummary.total > 0 && (
            <div className="bg-white rounded-xl border shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <SectionHeader icon={ClipboardCheck} title="בקרת ביצוע" count={null} color="text-emerald-500" />
                <button
                  onClick={() => navigate(`/projects/${projectId}/qc`)}
                  className="text-xs font-medium text-amber-600 hover:text-amber-700 flex items-center gap-1"
                >
                  פתח <ChevronLeft className="w-3 h-3" />
                </button>
              </div>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-lg font-extrabold text-emerald-600">{qcProgress}%</span>
                <span className="text-xs text-slate-400">התקדמות כללית</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2.5 mb-3">
                <div
                  className="h-2.5 rounded-full transition-all"
                  style={{ width: `${qcProgress}%`, background: 'linear-gradient(90deg, #10b981, #34d399)' }}
                />
              </div>
              <div className="grid grid-cols-4 gap-2 text-center">
                <div className="bg-slate-50 rounded-lg p-2">
                  <div className="text-lg font-bold text-slate-500">{qcSummary.not_started}</div>
                  <div className="text-[10px] text-slate-400 font-medium">◷ {qcFloorStatusLabel('not_started')}</div>
                </div>
                <div className="bg-amber-50 rounded-lg p-2">
                  <div className="text-lg font-bold text-amber-600">{qcSummary.in_progress}</div>
                  <div className="text-[10px] text-amber-500 font-medium">◐ {qcFloorStatusLabel('in_progress')}</div>
                </div>
                <div className="bg-blue-50 rounded-lg p-2">
                  <div className="text-lg font-bold text-blue-600">{qcSummary.pending_review}</div>
                  <div className="text-[10px] text-blue-500 font-medium">{qcFloorStatusLabel('pending_review')}</div>
                </div>
                <div className="bg-green-50 rounded-lg p-2">
                  <div className="text-lg font-bold text-green-600">{qcSummary.submitted}</div>
                  <div className="text-[10px] text-green-500 font-medium">✓ {qcFloorStatusLabel('submitted')}</div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {showPendingApprovals && (
            <div className="bg-white rounded-xl border shadow-sm p-4">
              <SectionHeader icon={Clock} title="ממתין לאישור שלי" count={pending_approvals.length} color="text-amber-500" />
              <div className="space-y-1.5">
                {pending_approvals.slice(0, 10).map(task => (
                  <button
                    key={task.id}
                    onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: `/projects/${projectId}/dashboard` } })}
                    className="w-full flex items-center gap-2 p-2.5 rounded-lg hover:bg-amber-50 border border-transparent hover:border-amber-200 transition-all text-right border-r-[3px] border-r-amber-400"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-700 truncate">{task.title}</p>
                      <p className="text-xs text-slate-400">{task.updated_at ? new Date(task.updated_at).toLocaleDateString('he-IL') : ''}</p>
                    </div>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap font-medium ${statusColors[task.status] || 'bg-slate-100 text-slate-600'}`}>
                      {statusLabels[task.status] || task.status}
                    </span>
                    <ChevronLeft className="w-4 h-4 text-slate-300 shrink-0" />
                  </button>
                ))}
                {pending_approvals.length > 10 && (
                  <button
                    onClick={() => navigate(`/projects/${projectId}/control?workMode=defects&statusChip=pending_manager_approval&from=dashboard`)}
                    className="w-full text-center text-xs text-amber-600 hover:text-amber-700 py-2 font-medium"
                  >
                    הצג את כל {pending_approvals.length} המשימות →
                  </button>
                )}
              </div>
            </div>
          )}

          {stuck_contractors.length > 0 && (
            <div className="bg-white rounded-xl border shadow-sm p-4">
              <SectionHeader icon={AlertCircle} title="תקוע אצל קבלנים" count={stuck_contractors.reduce((sum, c) => sum + c.stuck_count, 0)} color="text-orange-500" />
              <div className="space-y-2">
                {stuck_contractors.map(contractor => (
                  <div
                    key={contractor.contractor_id}
                    className={`rounded-lg p-2.5 bg-white border border-slate-100 border-r-[3px] ${
                      contractor.stuck_count > 5 ? 'border-r-red-400' : 'border-r-orange-400'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <HardHat className="w-4 h-4 text-orange-500" />
                        <span className="text-sm font-bold text-slate-700">{contractor.contractor_name || 'קבלן'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleSendReminder(contractor.company_id || contractor.contractor_id, contractor.contractor_name || 'קבלן'); }}
                          disabled={sendingReminder[contractor.company_id || contractor.contractor_id]}
                          className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors flex items-center gap-0.5"
                          title="שלח תזכורת"
                        >
                          {sendingReminder[contractor.company_id || contractor.contractor_id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                          תזכורת
                        </button>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                          contractor.stuck_count > 5 ? 'text-red-600 bg-red-100' : 'text-orange-600 bg-orange-100'
                        }`}>
                          {contractor.stuck_count} תקועות
                        </span>
                      </div>
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
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {load_by_building.length > 0 && (
            <div className="bg-white rounded-xl border shadow-sm p-4">
              <SectionHeader icon={Building2} title="עומס לפי מבנה" count={null} color="text-blue-500" />
              <div className="space-y-2.5">
                {load_by_building.map((b, i) => {
                  const max = load_by_building[0]?.open_count || 1;
                  const pct = Math.round((b.open_count / max) * 100);
                  const barColor = getBarColor(i, load_by_building.length);
                  const textColor = getBarTextColor(i, load_by_building.length);
                  return (
                    <div key={b.building_id} className="flex items-center gap-3">
                      <span className="text-xs text-slate-700 w-24 truncate font-semibold">{b.building_name || `מבנה ${i + 1}`}</span>
                      <div className="flex-1 bg-slate-100 rounded-full overflow-hidden" style={{ height: '10px' }}>
                        <div
                          className={`h-full bg-gradient-to-l ${barColor} rounded-full transition-all`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className={`text-sm font-extrabold ${textColor} w-8 text-center`}>{b.open_count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl border shadow-sm p-4">
            <SectionHeader icon={BarChart3} title="קבלנים — איכות" count={contractor_quality.length} color="text-purple-500" />
            {contractor_quality.length === 0 ? (
              <EmptySection text="אין נתוני קבלנים" />
            ) : (
              <div className="overflow-x-auto -mx-1">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-500 border-b">
                      <th className="text-right py-2.5 px-2 font-medium">קבלן</th>
                      <th className="text-center py-2.5 px-2 font-medium">פתוח</th>
                      <th className="text-center py-2.5 px-2 font-medium">סגור</th>
                      <th className="text-center py-2.5 px-2 font-medium">דחיות</th>
                      {isPmOrOwner && <th className="text-center py-2.5 px-2 font-medium w-16"></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {contractor_quality.slice(0, 15).map((c, idx) => (
                      <tr key={c.contractor_id} className={`border-b border-slate-50 hover:bg-amber-50 transition-colors ${idx % 2 === 1 ? 'bg-slate-50' : ''}`}>
                        <td className="py-2.5 px-2 font-medium text-slate-700 truncate max-w-[140px]">
                          {c.contractor_name || 'קבלן'}
                        </td>
                        <td className="text-center py-2.5 px-2">
                          <span className={`text-sm ${c.open > 5 ? 'font-bold text-red-600' : c.open > 0 ? 'font-bold text-red-500' : 'text-slate-400'}`}>{c.open}</span>
                        </td>
                        <td className="text-center py-2.5 px-2">
                          <span className={`text-sm ${c.closed > 0 ? 'font-bold text-green-600' : 'text-slate-400'}`}>{c.closed}</span>
                        </td>
                        <td className="text-center py-2.5 px-2">
                          <span className={`text-sm ${c.rework > 2 ? 'font-bold text-orange-600' : c.rework > 0 ? 'font-bold text-orange-500' : 'text-slate-400'}`}>{c.rework}</span>
                        </td>
                        {isPmOrOwner && c.open > 0 && (
                          <td className="text-center py-2.5 px-1">
                            <button
                              onClick={() => handleSendReminder(c.company_id || c.contractor_id, c.contractor_name || 'קבלן')}
                              disabled={sendingReminder[c.company_id || c.contractor_id]}
                              className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors inline-flex items-center gap-0.5"
                              title="שלח תזכורת"
                            >
                              {sendingReminder[c.company_id || c.contractor_id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                            </button>
                          </td>
                        )}
                        {isPmOrOwner && c.open === 0 && <td></td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {kpis.open_total === 0 && kpis.closed_total === 0 && (
          <div className="bg-white rounded-xl border shadow-sm p-8 text-center">
            <Construction className="w-14 h-14 text-amber-300 mx-auto mb-4" />
            <p className="text-slate-700 text-base font-semibold mb-1">הפרויקט מוכן לפעולה</p>
            <p className="text-slate-400 text-sm mb-4">צרו את הליקוי הראשון כדי לראות את הנתונים כאן</p>
            <button
              onClick={() => navigate(`/projects/${projectId}/control`)}
              className="px-5 py-2.5 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 transition-colors shadow-sm"
            >
              מעבר לפרויקט
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
