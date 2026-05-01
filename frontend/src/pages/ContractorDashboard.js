import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectService, taskService } from '../services/api';
import { tCategory, tStatus, tPriority, t, getLanguage } from '../i18n';
import { toast } from 'sonner';
import {
  LogOut, Clock, CheckCircle2, AlertTriangle,
  Camera, Eye, Settings, ChevronLeft, Flame
} from 'lucide-react';
import { Card } from '../components/ui/card';
import CategoryPill from '../components/CategoryPill';

const PAGE_SIZE = 50;

const STATUS_COLORS = {
  open: 'bg-blue-100 text-blue-700',
  assigned: 'bg-purple-100 text-purple-700',
  in_progress: 'bg-amber-100 text-amber-700',
  waiting_verify: 'bg-orange-100 text-orange-700',
  pending_contractor_proof: 'bg-orange-100 text-orange-700',
  pending_manager_approval: 'bg-indigo-100 text-indigo-700',
  closed: 'bg-green-100 text-green-700',
  reopened: 'bg-red-100 text-red-700',
};

const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
const PRIORITY_BORDER = { critical: 'border-r-red-500', high: 'border-r-orange-500', medium: 'border-r-blue-400', low: 'border-r-slate-300' };
const PRIORITY_BADGE_CLS = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-blue-100 text-blue-600',
  low: 'bg-slate-100 text-slate-500',
};

const OPEN_STATUSES = ['open', 'assigned', 'in_progress', 'pending_contractor_proof', 'reopened', 'waiting_verify'];
const WAITING_FOR_ME_STATUSES = ['assigned', 'in_progress', 'pending_contractor_proof'];
const HANDLED_STATUSES = ['closed', 'pending_manager_approval'];

function getInitials(name) {
  if (!name) return '??';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function getWaitingTime(task) {
  const ref = task.assigned_at || task.updated_at || task.created_at;
  if (!ref) return null;
  const diff = Date.now() - new Date(ref).getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return t('dashboard', 'time_now');
  if (hours < 24) return `${hours} ${t('dashboard', 'time_hours')}`;
  const days = Math.floor(hours / 24);
  if (days === 1) return t('dashboard', 'time_day');
  return `${days} ${t('dashboard', 'time_days')}`;
}

function getWaitingHours(task) {
  const ref = task.assigned_at || task.updated_at || task.created_at;
  if (!ref) return 0;
  return (Date.now() - new Date(ref).getTime()) / (1000 * 60 * 60);
}

function ProgressRing({ percentage, size = 90, strokeWidth = 8 }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;
  return (
    <svg width={size} height={size} className="transform -rotate-90" role="progressbar" aria-valuenow={Math.round(percentage)} aria-valuemin={0} aria-valuemax={100} aria-label={t('dashboard', 'progress_aria').replace('{pct}', Math.round(percentage))}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
        stroke="#e2e8f0" strokeWidth={strokeWidth} />
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
        stroke="#3b82f6" strokeWidth={strokeWidth}
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round" className="transition-all duration-700" />
    </svg>
  );
}

function TaskCardSkeleton() {
  return (
    <Card className="p-0 overflow-hidden border-r-4 border-r-slate-200">
      <div className="p-3 animate-pulse">
        <div className="flex items-start justify-between mb-1.5">
          <div className="h-4 bg-slate-200 rounded w-3/4"></div>
          <div className="h-5 bg-slate-200 rounded w-14 mr-2"></div>
        </div>
        <div className="h-3 bg-slate-100 rounded w-1/2 mb-1.5"></div>
        <div className="flex items-center gap-2 mb-3">
          <div className="h-4 bg-slate-100 rounded w-12"></div>
          <div className="h-4 bg-slate-100 rounded w-16"></div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-10 bg-slate-200 rounded-lg"></div>
          <div className="h-10 bg-slate-100 rounded-lg w-20"></div>
        </div>
      </div>
    </Card>
  );
}

const ContractorDashboard = ({ initialProjectId } = {}) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const lang = getLanguage();
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedProjectId, setSelectedProjectId] = useState(() => {
    // Priority: URL param (from /projects/:projectId) → localStorage → 'all'
    return initialProjectId || localStorage.getItem('lastProjectId') || 'all';
  });
  const urgentRef = useRef(null);

  const [offset, setOffset] = useState(0);
  const [totalTasks, setTotalTasks] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const taskIdsRef = useRef(new Set());
  const loaderRef = useRef(null);
  const abortRef = useRef(null);

  const loadMoreRef = useRef(false);
  const loadMore = useCallback(async (fromOffset = 0, projectFilter = null) => {
    if (loadMoreRef.current && fromOffset !== 0) return;
    loadMoreRef.current = true;
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();
    const { signal } = abortRef.current;

    setLoadingMore(true);
    try {
      const params = { limit: PAGE_SIZE, offset: fromOffset };
      const effectiveProject = projectFilter !== null ? projectFilter : selectedProjectId;
      if (effectiveProject && effectiveProject !== 'all') {
        params.project_id = effectiveProject;
      }

      const data = await taskService.list({ ...params, signal });
      if (signal.aborted) return;

      const rawItems = Array.isArray(data?.items) ? data.items : [];
      const rawTotal = typeof data?.total === 'number' ? data.total : rawItems.length;

      const newItems = rawItems.filter(
        item => !taskIdsRef.current.has(item.id)
      );
      newItems.forEach(item => taskIdsRef.current.add(item.id));

      if (fromOffset === 0) {
        setTasks(newItems);
      } else {
        setTasks(prev => [...prev, ...newItems]);
      }
      setTotalTasks(rawTotal);

      const nextOffset = fromOffset + rawItems.length;
      setOffset(nextOffset);
      setHasMore(nextOffset < rawTotal);
    } catch (err) {
      if (err.name === 'AbortError' || err?.code === 'ERR_CANCELED') return;
      console.error('Failed to load tasks:', err);
      toast.error(t('dashboard', 'load_error'));
    } finally {
      loadMoreRef.current = false;
      if (!signal.aborted) {
        setLoadingMore(false);
        setInitialLoading(false);
      }
    }
  }, [selectedProjectId]);

  useEffect(() => {
    let cancelled = false;
    const fetchStats = async () => {
      try {
        const [projectList, statsData] = await Promise.all([
          projectService.list(),
          taskService.myStats(
            selectedProjectId && selectedProjectId !== 'all'
              ? { project_id: selectedProjectId }
              : {}
          ),
        ]);
        if (cancelled) return;
        setProjects(Array.isArray(projectList) ? projectList : []);
        setStats(statsData);
      } catch (error) {
        if (cancelled) return;
        console.error('Failed to load stats:', error);
      }
    };
    fetchStats();
    return () => { cancelled = true; };
  }, [selectedProjectId]);

  useEffect(() => {
    let cancelled = false;
    const fetchTasks = async () => {
      setLoading(true);
      taskIdsRef.current.clear();
      setTasks([]);
      setOffset(0);
      setTotalTasks(null);
      setHasMore(true);
      setInitialLoading(true);
      try {
        await loadMore(0, selectedProjectId);
      } catch (error) {
        if (cancelled) return;
        console.error('Failed to load tasks:', error);
        toast.error(t('dashboard', 'load_error'));
        setInitialLoading(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchTasks();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId]);

  useEffect(() => {
    if (!loading && projects.length > 0 && selectedProjectId !== 'all') {
      const exists = projects.some(p => p.id === selectedProjectId);
      if (!exists) setSelectedProjectId('all');
    }
  }, [loading, projects, selectedProjectId]);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && hasMore && !loadingMore && !initialLoading) {
        loadMore(offset, selectedProjectId);
      }
    }, { threshold: 0.1 });
    if (loaderRef.current) observer.observe(loaderRef.current);
    return () => observer.disconnect();
  }, [hasMore, offset, loadingMore, initialLoading, loadMore, selectedProjectId]);

  const handleLogout = () => { logout(); navigate('/login'); };

  const membership = useMemo(() => {
    const summaries = user?.project_memberships_summary;
    if (!summaries || summaries.length === 0) return null;
    return summaries[0];
  }, [user]);

  const companyName = membership?.company_name || '';
  const tradeName = membership?.contractor_trade_key ? tCategory(membership.contractor_trade_key) : '';

  const openTasks = useMemo(() =>
    tasks.filter(t => OPEN_STATUSES.includes(t.status)),
    [tasks]
  );

  const completedTasks = useMemo(() =>
    tasks
      .filter(t => HANDLED_STATUSES.includes(t.status))
      .sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))
      .slice(0, 10),
    [tasks]
  );

  const sortedOpenTasks = useMemo(() =>
    [...openTasks].sort((a, b) => {
      const pa = PRIORITY_ORDER[a.priority] ?? 2;
      const pb = PRIORITY_ORDER[b.priority] ?? 2;
      if (pa !== pb) return pa - pb;
      return getWaitingHours(b) - getWaitingHours(a);
    }),
    [openTasks]
  );

  const urgentCount = stats?.urgent || 0;

  const headerStats = useMemo(() => {
    if (!stats) return { totalHandled: 0, successRate: 0, waiting: 0 };
    return {
      totalHandled: stats.resolved || 0,
      successRate: stats.success_rate || 0,
      waiting: stats.open - (stats.open - stats.in_progress) + stats.in_progress,
    };
  }, [stats]);

  const monthlyStats = useMemo(() => {
    if (!stats) return { closedThisMonth: 0, inProgressThisMonth: 0, waitingThisMonth: 0, monthlyPct: 0 };
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    const monthData = (stats.monthly || []).find(m => m.month === currentMonth);
    const closedThisMonth = monthData?.resolved || 0;
    const openedThisMonth = monthData?.opened || 0;
    const totalThisMonth = openedThisMonth;
    const monthlyPct = totalThisMonth > 0 ? Math.round((closedThisMonth / totalThisMonth) * 100) : 0;
    return {
      closedThisMonth,
      inProgressThisMonth: stats.in_progress || 0,
      waitingThisMonth: Math.max(0, openedThisMonth - closedThisMonth),
      monthlyPct: Math.min(monthlyPct, 100),
    };
  }, [stats]);

  if (loading && !projects.length) {
    return (
      <div className="min-h-screen bg-slate-50" dir="rtl">
        <div className="max-w-lg mx-auto px-4 py-6 space-y-3">
          <div className="h-32 bg-slate-200 rounded-xl animate-pulse" />
          <TaskCardSkeleton />
          <TaskCardSkeleton />
          <TaskCardSkeleton />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <header className="text-white sticky top-0 z-50 shadow-lg" style={{ background: 'linear-gradient(135deg, #3b82f6, #60a5fa)' }}>
        <div className="max-w-lg mx-auto px-4 pt-4 pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full bg-white/20 flex items-center justify-center text-white font-bold text-base">
                {getInitials(user?.name)}
              </div>
              <div>
                <h1 className="text-base font-bold leading-tight">{user?.name || t('dashboard', 'contractor_fallback')}</h1>
                <p className="text-xs text-blue-100">
                  {[companyName, tradeName].filter(Boolean).join(' · ') || 'BrikOps'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => navigate('/settings/account')} className="p-2 rounded-full hover:bg-white/10 transition-colors" aria-label={t('dashboard', 'settings_aria')}>
                <Settings className="w-5 h-5" />
              </button>
              <button onClick={handleLogout} className="p-2 rounded-full hover:bg-white/10 transition-colors" aria-label={t('dashboard', 'logout_aria')}>
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-4 gap-2 bg-white/10 rounded-xl p-2.5">
            <div className="text-center">
              <p className="text-xl font-bold">{headerStats.totalHandled}</p>
              <p className="text-[10px] text-blue-100">{t('dashboard', 'total_handled')}</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold">{headerStats.successRate}%</p>
              <p className="text-[10px] text-blue-100">{t('dashboard', 'success_rate')}</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold">—</p>
              <p className="text-[10px] text-blue-100">{t('dashboard', 'avg_hours')}</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold">{stats?.open || 0}</p>
              <p className="text-[10px] text-blue-100">{t('dashboard', 'waiting_for_me')}</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
        {projects.length > 1 && (
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
            <button
              onClick={() => setSelectedProjectId('all')}
              aria-pressed={selectedProjectId === 'all'}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                selectedProjectId === 'all' ? 'bg-blue-500 text-white' : 'bg-white text-slate-600 border border-slate-200'
              }`}
            >
              {t('dashboard', 'all_filter')} ({totalTasks != null ? totalTasks : stats?.total || 0})
            </button>
            {projects.map(p => (
              <button key={p.id}
                onClick={() => setSelectedProjectId(p.id)}
                aria-pressed={selectedProjectId === p.id}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  selectedProjectId === p.id ? 'bg-blue-500 text-white' : 'bg-white text-slate-600 border border-slate-200'
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        )}

        {urgentCount > 0 && (
          <button
            onClick={() => urgentRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            className="w-full rounded-xl p-3 text-white font-medium text-sm flex items-center justify-between touch-manipulation active:scale-[0.98] transition-transform"
            style={{ background: 'linear-gradient(135deg, #ef4444, #f87171)' }}
          >
            <span className="flex items-center gap-2">
              <Flame className="w-5 h-5" />
              <span>{t('dashboard', 'urgent_banner').replace('{count}', urgentCount)}</span>
            </span>
            <ChevronLeft className="w-5 h-5" />
          </button>
        )}

        <Card className="p-4">
          <div className="flex items-center gap-4">
            <div className="relative flex-shrink-0">
              <ProgressRing percentage={monthlyStats.monthlyPct} />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-blue-600">{monthlyStats.monthlyPct}%</span>
              </div>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-slate-700 mb-2">{t('dashboard', 'monthly_progress')}</h3>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-lg font-bold text-green-600">{monthlyStats.closedThisMonth}</p>
                  <p className="text-[10px] text-slate-500">{t('dashboard', 'monthly_handled')}</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-amber-600">{monthlyStats.inProgressThisMonth}</p>
                  <p className="text-[10px] text-slate-500">{t('dashboard', 'monthly_in_progress')}</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-slate-600">{monthlyStats.waitingThisMonth}</p>
                  <p className="text-[10px] text-slate-500">{t('dashboard', 'monthly_waiting')}</p>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <div ref={urgentRef}>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-slate-500" />
              {t('dashboard', 'needs_attention')}
            </h2>
            <span className="text-xs font-medium bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
              {sortedOpenTasks.length}
            </span>
          </div>

          {initialLoading ? (
            <div className="space-y-2.5">
              <TaskCardSkeleton />
              <TaskCardSkeleton />
              <TaskCardSkeleton />
            </div>
          ) : sortedOpenTasks.length === 0 ? (
            <Card className="p-8 text-center">
              <CheckCircle2 className="w-12 h-12 text-green-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">{t('dashboard', 'no_open_defects')}</p>
            </Card>
          ) : (
            <div className="space-y-2.5">
              {sortedOpenTasks.map(task => {
                const statusColor = STATUS_COLORS[task.status] || 'bg-slate-100';
                const priBorder = PRIORITY_BORDER[task.priority] || 'border-r-slate-300';
                const priBadgeCls = PRIORITY_BADGE_CLS[task.priority] || PRIORITY_BADGE_CLS.medium;
                const waitStr = getWaitingTime(task);
                const location = [task.project_name, task.building_name, task.floor_name, task.unit_name].filter(Boolean).join(' · ');

                return (
                  <Card key={task.id} className={`p-0 overflow-hidden border-r-4 ${priBorder}`}>
                    <div className="p-3">
                      <div className="flex items-start justify-between mb-1.5">
                        <h4 className="text-sm font-medium text-slate-800 flex-1 leading-snug">{task.title}</h4>
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-md whitespace-nowrap mr-2 ${statusColor}`}>
                          {tStatus(task.status)}
                        </span>
                      </div>

                      {location && (
                        <p className="text-xs text-slate-400 mb-1.5">{location}</p>
                      )}

                      <div className="flex items-center gap-2 flex-wrap text-[11px]">
                        <span className={`px-1.5 py-0.5 rounded ${priBadgeCls}`}>{tPriority(task.priority)}</span>
                        <CategoryPill>{tCategory(task.category)}</CategoryPill>
                        {waitStr && (
                          <span className="text-slate-400 flex items-center gap-0.5">
                            <Clock className="w-3 h-3" /> {t('dashboard', 'waiting_label')} {waitStr}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 mt-3">
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.id}?action=proof`, { state: { returnTo: '/' } }); }}
                          className="flex-1 py-2.5 rounded-lg bg-green-500 hover:bg-green-600 text-white text-sm font-medium flex items-center justify-center gap-1.5 touch-manipulation active:scale-[0.97] transition-all"
                        >
                          <Camera className="w-4 h-4" />
                          {t('dashboard', 'photo_fix')}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.id}`, { state: { returnTo: '/' } }); }}
                          className="py-2.5 px-4 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium flex items-center justify-center gap-1 touch-manipulation active:scale-[0.97] transition-all"
                        >
                          <Eye className="w-4 h-4" />
                          {t('dashboard', 'details')}
                        </button>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        {!initialLoading && completedTasks.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                {t('dashboard', 'recently_handled')}
              </h2>
              <span className="text-xs font-medium bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                {completedTasks.length}
              </span>
            </div>
            <Card className="divide-y divide-slate-100">
              {completedTasks.map(task => (
                <button key={task.id}
                  className="w-full flex items-center gap-3 p-3 cursor-pointer hover:bg-slate-50 transition-colors touch-manipulation text-right"
                  onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: '/' } })}
                >
                  <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-600 line-through truncate">{task.title}</p>
                    <p className="text-[11px] text-slate-400">
                      {task.project_name && <span>{task.project_name}</span>}
                      {task.updated_at && <span> · {new Date(task.updated_at).toLocaleDateString(lang === 'en' ? 'en-US' : lang === 'ar' ? 'ar-SA' : lang === 'zh' ? 'zh-CN' : 'he-IL')}</span>}
                    </p>
                  </div>
                  <ChevronLeft className="w-4 h-4 text-slate-300 flex-shrink-0" />
                </button>
              ))}
            </Card>
          </div>
        )}

        {hasMore && !initialLoading && (
          <div ref={loaderRef} className="py-4 text-center">
            {loadingMore && (
              <div className="inline-flex items-center gap-2 text-sm text-slate-500">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
                {t('dashboard', 'loading_more')}
              </div>
            )}
          </div>
        )}

        <div className="h-8" />
      </div>
    </div>
  );
};

export default ContractorDashboard;
