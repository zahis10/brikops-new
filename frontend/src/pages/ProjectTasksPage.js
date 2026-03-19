import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { taskService, projectService } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Search, ListTodo, Clock, Filter, X, Plus,
  CheckCircle2, AlertTriangle, ArrowLeftRight, MessageSquare, Users, UserPlus
} from 'lucide-react';
import NewDefectModal from '../components/NewDefectModal';
import { Card } from '../components/ui/card';
import { tCategory } from '../i18n';
import ProjectSwitcher from '../components/ProjectSwitcher';
import { getProjectBackPath } from '../utils/navigation';

const PAGE_SIZE = 50;

const STATUS_CONFIG = {
  open: { label: 'פתוח', color: 'bg-blue-100 text-blue-700' },
  assigned: { label: 'שויך', color: 'bg-purple-100 text-purple-700' },
  in_progress: { label: 'בביצוע', color: 'bg-amber-100 text-amber-700' },
  waiting_verify: { label: 'ממתין לאימות', color: 'bg-orange-100 text-orange-700' },
  pending_contractor_proof: { label: 'ממתין להוכחת קבלן', color: 'bg-orange-100 text-orange-700' },
  pending_manager_approval: { label: 'ממתין לאישור מנהל', color: 'bg-indigo-100 text-indigo-700' },
  returned_to_contractor: { label: 'הוחזר לקבלן', color: 'bg-rose-100 text-rose-700' },
  closed: { label: 'סגור', color: 'bg-green-100 text-green-700' },
  reopened: { label: 'נפתח מחדש', color: 'bg-red-100 text-red-700' },
};

const CONTRACTOR_STATUS_CHIPS = [
  { key: 'active', label: 'פעילים', statusIn: 'open,assigned,in_progress,pending_contractor_proof,returned_to_contractor' },
  { key: 'pending_manager_approval', label: 'ממתין לאישור מנהל', status: 'pending_manager_approval' },
  { key: 'closed', label: 'סגור', status: 'closed' },
];

const MANAGER_STATUS_CHIPS = [
  { key: '', label: 'הכל' },
  { key: 'open', label: 'פתוח', status: 'open' },
  { key: 'assigned', label: 'שויך', status: 'assigned' },
  { key: 'in_progress', label: 'בביצוע', status: 'in_progress' },
  { key: 'pending_contractor_proof', label: 'ממתין להוכחת קבלן', status: 'pending_contractor_proof' },
  { key: 'pending_manager_approval', label: 'ממתין לאישור מנהל', status: 'pending_manager_approval' },
  { key: 'returned_to_contractor', label: 'הוחזר לקבלן', status: 'returned_to_contractor' },
  { key: 'closed', label: 'סגור', status: 'closed' },
  { key: 'reopened', label: 'נפתח מחדש', status: 'reopened' },
];

const PRIORITY_CONFIG = {
  low: { label: 'נמוך', color: 'text-slate-500' },
  medium: { label: 'בינוני', color: 'text-blue-600' },
  high: { label: 'גבוה', color: 'text-amber-600' },
  critical: { label: 'קריטי', color: 'text-red-600' },
};

function TaskCardSkeleton() {
  return (
    <Card className="p-3">
      <div className="animate-pulse">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            <div className="h-4 bg-slate-200 rounded w-3/4 mb-1"></div>
            <div className="h-3 bg-slate-100 rounded w-1/2"></div>
          </div>
          <div className="h-5 bg-slate-200 rounded w-16 mr-2"></div>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-4 bg-slate-100 rounded w-16"></div>
          <div className="h-4 bg-slate-100 rounded w-12"></div>
        </div>
      </div>
    </Card>
  );
}

const ProjectTasksPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [bucketData, setBucketData] = useState(null);
  const [showNewDefect, setShowNewDefect] = useState(false);

  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const taskIdsRef = useRef(new Set());
  const loaderRef = useRef(null);
  const abortRef = useRef(null);

  const isManager = ['owner', 'admin', 'project_manager', 'management_team'].includes(project?.my_role);

  const statusChip = searchParams.get('statusChip') || '';
  const bucketFilter = searchParams.get('bucket') || 'all';
  const fromDashboard = searchParams.get('from') === 'dashboard';
  const overdueFilter = searchParams.get('overdue') === 'true';
  const searchQuery = searchParams.get('q') || '';
  const [searchInput, setSearchInput] = useState(searchQuery);
  const searchTimerRef = useRef(null);

  const updateParams = useCallback((key, value) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (!value || value === 'all' || value === '') {
        next.delete(key);
      } else {
        next.set(key, value);
      }
      next.delete('status');
      next.delete('status_in');
      return next;
    });
  }, [setSearchParams]);

  const handleSearchChange = useCallback((value) => {
    setSearchInput(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      updateParams('q', value);
    }, 350);
  }, [updateParams]);

  useEffect(() => {
    return () => { if (searchTimerRef.current) clearTimeout(searchTimerRef.current); };
  }, []);

  const clearAllFilters = useCallback(() => {
    setSearchParams({});
    setSearchInput('');
  }, [setSearchParams]);

  const assigneeFilter = searchParams.get('assignee') || '';

  const isContractor = project?.my_role === 'contractor';

  useEffect(() => {
    if (isContractor) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        let changed = false;
        if (prev.get('assignee') !== 'me') {
          next.set('assignee', 'me');
          changed = true;
        }
        const myTrade = project?.my_trade_key;
        if (myTrade && prev.get('bucket') !== myTrade) {
          next.set('bucket', myTrade);
          changed = true;
        }
        if (!prev.get('statusChip')) {
          next.set('statusChip', 'active');
          changed = true;
        }
        return changed ? next : prev;
      }, { replace: true });
    }
  }, [isContractor, project?.my_trade_key, setSearchParams]);

  const getStatusParams = useCallback((chipKey, isContr) => {
    const chips = isContr ? CONTRACTOR_STATUS_CHIPS : MANAGER_STATUS_CHIPS;
    const chip = chips.find(c => c.key === chipKey);
    if (!chip) return {};
    if (chip.statusIn) return { status_in: chip.statusIn };
    if (chip.status) return { status: chip.status };
    return {};
  }, []);

  const buildTaskParams = useCallback((projIsContractor) => {
    const effectiveChip = statusChip || (projIsContractor ? 'active' : '');
    const statusParams = getStatusParams(effectiveChip, projIsContractor);
    const params = { project_id: projectId, ...statusParams };
    if (bucketFilter && bucketFilter !== 'all') {
      params.bucket_key = bucketFilter;
    }
    if (assigneeFilter === 'me' || projIsContractor) {
      params.assignee_id = 'me';
    }
    if (overdueFilter) {
      params.overdue = true;
    }
    if (searchQuery) {
      params.q = searchQuery;
    }
    return params;
  }, [projectId, statusChip, bucketFilter, assigneeFilter, overdueFilter, searchQuery, getStatusParams]);

  const loadMore = useCallback(async (fromOffset = 0, projIsContractor = null) => {
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();
    const { signal } = abortRef.current;

    setLoadingMore(true);
    try {
      const effectiveIsContractor = projIsContractor ?? isContractor;
      const params = buildTaskParams(effectiveIsContractor);

      const data = await taskService.list({
        ...params,
        limit: PAGE_SIZE,
        offset: fromOffset,
        signal,
      });
      if (signal.aborted) return;

      const newItems = data.items.filter(
        item => !taskIdsRef.current.has(item.id)
      );
      newItems.forEach(item => taskIdsRef.current.add(item.id));

      if (fromOffset === 0) {
        setTasks(newItems);
      } else {
        setTasks(prev => [...prev, ...newItems]);
      }
      setTotal(data.total);

      const nextOffset = fromOffset + data.items.length;
      setOffset(nextOffset);
      setHasMore(nextOffset < data.total);
    } catch (err) {
      if (err.name === 'AbortError' || err?.code === 'ERR_CANCELED') return;
      console.error('Failed to load tasks:', err);
      if (err?.response?.status === 403) {
        toast.error('אין לך הרשאה לצפות בליקויים של פרויקט זה');
        navigate('/projects');
        return;
      }
      toast.error('שגיאה בטעינת ליקויים');
    } finally {
      if (!signal.aborted) {
        setLoadingMore(false);
        setInitialLoading(false);
      }
    }
  }, [isContractor, buildTaskParams, navigate]);

  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      try {
        const proj = await projectService.get(projectId);
        if (cancelled) return;
        setProject(proj);
        localStorage.setItem('lastProjectId', projectId);

        const projIsContractor = proj.my_role === 'contractor';
        const effectiveChip = statusChip || (projIsContractor ? 'active' : '');
        const statusParams = getStatusParams(effectiveChip, projIsContractor);

        const bucketsResp = await taskService.taskBuckets(projectId, statusParams.status || null);
        if (cancelled) return;
        setBucketData(bucketsResp);

        taskIdsRef.current.clear();
        setTasks([]);
        setOffset(0);
        setTotal(null);
        setHasMore(true);
        setInitialLoading(true);

        await loadMore(0, projIsContractor);
      } catch (err) {
        if (cancelled) return;
        console.error('Failed to load project:', err);
        if (err?.response?.status === 403) {
          toast.error('אין לך הרשאה לצפות בליקויים של פרויקט זה');
          navigate('/projects');
          return;
        }
        toast.error('שגיאה בטעינת ליקויים');
        setInitialLoading(false);
      }
    };
    init();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, statusChip, bucketFilter, assigneeFilter, overdueFilter, searchQuery, getStatusParams, navigate]);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && hasMore && !loadingMore && !initialLoading) {
        loadMore(offset, isContractor);
      }
    }, { threshold: 0.1 });
    if (loaderRef.current) observer.observe(loaderRef.current);
    return () => observer.disconnect();
  }, [hasMore, offset, loadingMore, initialLoading, loadMore, isContractor]);

  const hasActiveFilter = statusChip || bucketFilter !== 'all' || searchQuery || overdueFilter;

  const getActiveFilterLabel = () => {
    const parts = [];
    if (statusChip) {
      const chips = isContractor ? CONTRACTOR_STATUS_CHIPS : MANAGER_STATUS_CHIPS;
      const chip = chips.find(c => c.key === statusChip);
      if (chip) parts.push(chip.label);
    }
    if (bucketFilter && bucketFilter !== 'all') {
      const bucket = (bucketData?.buckets || []).find(b => b.bucket_key === bucketFilter);
      if (bucket) parts.push(bucket.label_he);
    }
    if (overdueFilter) {
      parts.push('באיחור');
    }
    if (searchQuery) {
      parts.push(`"${searchQuery}"`);
    }
    return parts.length > 0 ? parts.join(' · ') : null;
  };

  if (initialLoading && !project) {
    return (
      <div className="min-h-screen bg-slate-50" dir="rtl">
        <div className="max-w-7xl mx-auto px-4 py-8 space-y-3">
          <TaskCardSkeleton />
          <TaskCardSkeleton />
          <TaskCardSkeleton />
          <TaskCardSkeleton />
        </div>
      </div>
    );
  }

  const activeFilterLabel = getActiveFilterLabel();

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <header className="bg-slate-800 text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate(fromDashboard ? `/projects/${projectId}/dashboard` : getProjectBackPath(project?.my_role, projectId))} className="p-1 hover:bg-slate-700 rounded-lg transition-colors" title="חזרה לפרויקט">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1">
              <span className="text-base font-bold">{isContractor ? 'הליקויים שלי —' : 'ליקויים —'}</span>
              <ProjectSwitcher currentProjectId={projectId} currentProjectName={project?.name || ''} />
            </div>
            <p className="text-xs text-slate-300">{total != null ? total : (bucketData?.total || 0)} ליקויים{statusChip ? ` (${(isContractor ? CONTRACTOR_STATUS_CHIPS : MANAGER_STATUS_CHIPS).find(c => c.key === statusChip)?.label || ''})` : ''}</p>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-4 space-y-3">
        <div className="flex items-center gap-2">
          {isManager && (
            <button
              onClick={() => setShowNewDefect(true)}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              הוסף ליקוי
            </button>
          )}
        </div>

        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="חיפוש ליקויים..."
            value={searchInput}
            onChange={e => handleSearchChange(e.target.value)}
            className="w-full h-10 pr-9 pl-3 text-sm text-right bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          />
        </div>

        <div className="overflow-x-auto -mx-4 px-4 scrollbar-thin">
          <div className="flex gap-1.5 pb-1" style={{ minWidth: 'max-content' }}>
            {(isContractor ? CONTRACTOR_STATUS_CHIPS : MANAGER_STATUS_CHIPS).map(chip => {
              const sc = bucketData?.status_counts || {};
              let chipCount = null;
              if (chip.key === '') {
                chipCount = Object.values(sc).reduce((a, b) => a + b, 0);
              } else if (chip.statusIn) {
                chipCount = chip.statusIn.split(',').reduce((sum, s) => sum + (sc[s] || 0), 0);
              } else if (chip.status) {
                chipCount = sc[chip.status] || 0;
              }
              return (
              <button
                key={chip.key}
                onClick={() => updateParams('statusChip', chip.key)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  statusChip === chip.key || (!statusChip && chip.key === '' && !isContractor) || (!statusChip && chip.key === 'active' && isContractor)
                    ? 'bg-slate-700 text-white shadow-sm'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                }`}
              >
                {chip.label}{chipCount != null ? ` (${chipCount})` : ''}
              </button>
              );
            })}
          </div>
        </div>

        {!isContractor && (
        <div className="overflow-x-auto -mx-4 px-4 scrollbar-thin">
          <div className="flex gap-1.5 pb-1" style={{ minWidth: 'max-content' }}>
            <button
              onClick={() => updateParams('bucket', 'all')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                bucketFilter === 'all'
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              <Users className="w-3 h-3" />
              הכול ({bucketData?.total || 0})
            </button>
            {(bucketData?.buckets || []).map(b => (
              <button
                key={b.bucket_key}
                onClick={() => updateParams('bucket', b.bucket_key)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  bucketFilter === b.bucket_key
                    ? 'bg-amber-500 text-white shadow-sm'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                }`}
              >
                {b.label_he} ({b.count})
              </button>
            ))}
            {project?.my_role === 'project_manager' && (
              <button
                onClick={() => {
                  const tradeParam = bucketFilter && bucketFilter !== 'all' ? `&prefillTrade=${bucketFilter}` : '';
                  navigate(`/projects/${projectId}/control?openInvite=1${tradeParam}`);
                }}
                className="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 flex items-center gap-1"
              >
                <UserPlus className="w-3 h-3" />
                הוסף קבלן
              </button>
            )}
          </div>
        </div>
        )}

        {activeFilterLabel && (
          <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            <Filter className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span className="text-xs text-amber-800 font-medium">מסונן לפי: {activeFilterLabel}</span>
            <button
              onClick={clearAllFilters}
              className="mr-auto flex items-center gap-1 text-xs text-amber-600 hover:text-amber-800 font-medium transition-colors"
            >
              <X className="w-3 h-3" />
              נקה
            </button>
          </div>
        )}

        {initialLoading ? (
          <div className="space-y-2">
            <TaskCardSkeleton />
            <TaskCardSkeleton />
            <TaskCardSkeleton />
          </div>
        ) : tasks.length === 0 ? (
          <Card className="p-8 text-center">
            <ListTodo className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-700 mb-1">
              {hasActiveFilter ? 'אין ליקויים התואמים את הסינון' : 'אין ליקויים עדיין'}
            </h3>
            <p className="text-sm text-slate-500 mb-4">
              {hasActiveFilter
                ? 'נסה לשנות את הסינון או לחפש מחדש'
                : 'הוסף ליקוי חדש כדי להתחיל לנהל את הפרויקט'}
            </p>
            {hasActiveFilter ? (
              <button
                onClick={clearAllFilters}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-500 text-white text-sm font-medium rounded-lg hover:bg-amber-600 transition-colors shadow-sm"
              >
                <X className="w-4 h-4" />
                נקה סינון
              </button>
            ) : isManager && (
              <button
                onClick={() => setShowNewDefect(true)}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-amber-500 text-white text-sm font-bold rounded-lg hover:bg-amber-600 transition-colors shadow-sm"
              >
                <Plus className="w-4 h-4" />
                הוסף ליקוי חדש
              </button>
            )}
          </Card>
        ) : (
          <div className="space-y-2">
            {tasks.map(task => {
              const statusCfg = STATUS_CONFIG[task.status] || {};
              const priorityCfg = PRIORITY_CONFIG[task.priority] || {};
              return (
                <Card
                  key={task.id}
                  className="p-3 hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: fromDashboard ? `/projects/${projectId}/dashboard` : `/projects/${projectId}/tasks?${searchParams.toString()}` } })}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-medium text-slate-800 truncate">{task.title}</h4>
                      {task.description && (
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{task.description}</p>
                      )}
                    </div>
                    <span className={`text-xs font-medium px-2 py-1 rounded-md whitespace-nowrap mr-2 ${statusCfg.color || 'bg-slate-100'}`}>
                      {statusCfg.label || task.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                    <span className="bg-slate-100 px-2 py-0.5 rounded">{tCategory(task.category)}</span>
                    <span className={priorityCfg.color || ''}>{priorityCfg.label || task.priority}</span>
                    {task.due_date && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {task.due_date}
                      </span>
                    )}
                    {task.comments_count > 0 && (
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" /> {task.comments_count}
                      </span>
                    )}
                  </div>
                </Card>
              );
            })}

            {hasMore && (
              <div ref={loaderRef} className="py-4 text-center">
                <div className="inline-flex items-center gap-2 text-sm text-slate-500">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-amber-500"></div>
                  טוען עוד...
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showNewDefect && (
        <NewDefectModal
          isOpen={showNewDefect}
          onClose={() => setShowNewDefect(false)}
          onSuccess={() => {
            setShowNewDefect(false);
            taskIdsRef.current.clear();
            setTasks([]);
            setOffset(0);
            setTotal(null);
            setHasMore(true);
            setInitialLoading(true);
            loadMore(0, isContractor);
          }}
          prefillData={{ project_id: projectId }}
        />
      )}
    </div>
  );
};

export default ProjectTasksPage;
