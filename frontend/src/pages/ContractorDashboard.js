import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectService, taskService } from '../services/api';
import { tCategory } from '../i18n';
import { toast } from 'sonner';
import {
  LogOut, Clock, CheckCircle2, AlertTriangle,
  Camera, Eye, Settings, ChevronLeft, Flame
} from 'lucide-react';
import { Card } from '../components/ui/card';

const STATUS_CONFIG = {
  open: { label: 'פתוח', color: 'bg-blue-100 text-blue-700' },
  assigned: { label: 'שויך', color: 'bg-purple-100 text-purple-700' },
  in_progress: { label: 'בביצוע', color: 'bg-amber-100 text-amber-700' },
  waiting_verify: { label: 'ממתין לאימות', color: 'bg-orange-100 text-orange-700' },
  pending_contractor_proof: { label: 'ממתין להוכחת קבלן', color: 'bg-orange-100 text-orange-700' },
  pending_manager_approval: { label: 'ממתין לאישור מנהל', color: 'bg-indigo-100 text-indigo-700' },
  closed: { label: 'סגור', color: 'bg-green-100 text-green-700' },
  reopened: { label: 'נפתח מחדש', color: 'bg-red-100 text-red-700' },
};

const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
const PRIORITY_BORDER = { critical: 'border-r-red-500', high: 'border-r-orange-500', medium: 'border-r-blue-400', low: 'border-r-slate-300' };
const PRIORITY_BADGE = {
  critical: { label: 'קריטי', cls: 'bg-red-100 text-red-700' },
  high: { label: 'גבוה', cls: 'bg-orange-100 text-orange-700' },
  medium: { label: 'בינוני', cls: 'bg-blue-100 text-blue-600' },
  low: { label: 'נמוך', cls: 'bg-slate-100 text-slate-500' },
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
  if (hours < 1) return 'עכשיו';
  if (hours < 24) return `${hours} שעות`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'יום';
  return `${days} ימים`;
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
    <svg width={size} height={size} className="transform -rotate-90" role="progressbar" aria-valuenow={Math.round(percentage)} aria-valuemin={0} aria-valuemax={100} aria-label={`התקדמות ${Math.round(percentage)}%`}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
        stroke="#e2e8f0" strokeWidth={strokeWidth} />
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
        stroke="#3b82f6" strokeWidth={strokeWidth}
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round" className="transition-all duration-700" />
    </svg>
  );
}

const ContractorDashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedProjectId, setSelectedProjectId] = useState('all');
  const urgentRef = useRef(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [projectList, taskList] = await Promise.all([
        projectService.list(),
        taskService.list(),
      ]);
      setProjects(Array.isArray(projectList) ? projectList : []);
      setTasks(Array.isArray(taskList) ? taskList : []);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('שגיאה בטעינת נתונים');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleLogout = () => { logout(); navigate('/login'); };

  const membership = useMemo(() => {
    const summaries = user?.project_memberships_summary;
    if (!summaries || summaries.length === 0) return null;
    return summaries[0];
  }, [user]);

  const companyName = membership?.company_name || '';
  const tradeName = membership?.contractor_trade_key ? tCategory(membership.contractor_trade_key) : '';

  const projectTasks = useMemo(() => {
    if (selectedProjectId === 'all') return tasks;
    return tasks.filter(t => t.project_id === selectedProjectId);
  }, [tasks, selectedProjectId]);

  const openTasks = useMemo(() =>
    projectTasks.filter(t => OPEN_STATUSES.includes(t.status)),
    [projectTasks]
  );

  const completedTasks = useMemo(() =>
    projectTasks
      .filter(t => HANDLED_STATUSES.includes(t.status))
      .sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))
      .slice(0, 10),
    [projectTasks]
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

  const urgentTasks = useMemo(() =>
    openTasks.filter(t => t.priority === 'critical' || getWaitingHours(t) > 48),
    [openTasks]
  );

  const stats = useMemo(() => {
    const closed = projectTasks.filter(t => t.status === 'closed');
    const handled = projectTasks.filter(t => HANDLED_STATUSES.includes(t.status));
    const totalHandled = handled.length;
    const successRate = totalHandled > 0 ? Math.max(0, Math.round((closed.length / totalHandled) * 100)) : 0;
    const waiting = projectTasks.filter(t => WAITING_FOR_ME_STATUSES.includes(t.status)).length;

    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    const tasksThisMonth = projectTasks.filter(t => t.created_at && new Date(t.created_at) >= monthStart);
    const closedThisMonth = tasksThisMonth.filter(t => HANDLED_STATUSES.includes(t.status)).length;
    const inProgressThisMonth = tasksThisMonth.filter(t => t.status === 'in_progress').length;
    const waitingThisMonth = tasksThisMonth.filter(t =>
      OPEN_STATUSES.includes(t.status) && t.status !== 'in_progress'
    ).length;
    const totalThisMonth = closedThisMonth + inProgressThisMonth + waitingThisMonth;
    const monthlyPct = totalThisMonth > 0 ? Math.round((closedThisMonth / totalThisMonth) * 100) : 0;

    return { totalHandled, successRate, waiting, closedThisMonth, waitingThisMonth, inProgressThisMonth, monthlyPct };
  }, [projectTasks]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="text-slate-500 mt-4">טוען נתונים...</p>
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
                <h1 className="text-base font-bold leading-tight">{user?.name || 'קבלן'}</h1>
                <p className="text-xs text-blue-100">
                  {[companyName, tradeName].filter(Boolean).join(' · ') || 'BrikOps'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => navigate('/settings/account')} className="p-2 rounded-full hover:bg-white/10 transition-colors" aria-label="הגדרות חשבון">
                <Settings className="w-5 h-5" />
              </button>
              <button onClick={handleLogout} className="p-2 rounded-full hover:bg-white/10 transition-colors" aria-label="יציאה">
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-4 gap-2 bg-white/10 rounded-xl p-2.5">
            <div className="text-center">
              <p className="text-xl font-bold">{stats.totalHandled}</p>
              <p className="text-[10px] text-blue-100">סה"כ טופלו</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold">{stats.successRate}%</p>
              <p className="text-[10px] text-blue-100">שיעור הצלחה</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold">—</p>
              <p className="text-[10px] text-blue-100">שע׳ ממוצע</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold">{stats.waiting}</p>
              <p className="text-[10px] text-blue-100">ממתינים לי</p>
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
              הכל ({tasks.length})
            </button>
            {projects.map(p => {
              const count = tasks.filter(t => t.project_id === p.id).length;
              return (
                <button key={p.id}
                  onClick={() => setSelectedProjectId(p.id)}
                  aria-pressed={selectedProjectId === p.id}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                    selectedProjectId === p.id ? 'bg-blue-500 text-white' : 'bg-white text-slate-600 border border-slate-200'
                  }`}
                >
                  {p.name} ({count})
                </button>
              );
            })}
          </div>
        )}

        {urgentTasks.length > 0 && (
          <button
            onClick={() => urgentRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            className="w-full rounded-xl p-3 text-white font-medium text-sm flex items-center justify-between touch-manipulation active:scale-[0.98] transition-transform"
            style={{ background: 'linear-gradient(135deg, #ef4444, #f87171)' }}
          >
            <span className="flex items-center gap-2">
              <Flame className="w-5 h-5" />
              <span>{urgentTasks.length} ליקויים דורשים טיפול מיידי</span>
            </span>
            <ChevronLeft className="w-5 h-5" />
          </button>
        )}

        <Card className="p-4">
          <div className="flex items-center gap-4">
            <div className="relative flex-shrink-0">
              <ProgressRing percentage={stats.monthlyPct} />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-blue-600">{stats.monthlyPct}%</span>
              </div>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-slate-700 mb-2">התקדמות החודש</h3>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-lg font-bold text-green-600">{stats.closedThisMonth}</p>
                  <p className="text-[10px] text-slate-500">טופלו</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-amber-600">{stats.inProgressThisMonth}</p>
                  <p className="text-[10px] text-slate-500">בטיפול</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-slate-600">{stats.waitingThisMonth}</p>
                  <p className="text-[10px] text-slate-500">ממתינים</p>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <div ref={urgentRef}>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-slate-500" />
              דורשים טיפול
            </h2>
            <span className="text-xs font-medium bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
              {sortedOpenTasks.length}
            </span>
          </div>

          {sortedOpenTasks.length === 0 ? (
            <Card className="p-8 text-center">
              <CheckCircle2 className="w-12 h-12 text-green-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">אין ליקויים פתוחים — כל הכבוד!</p>
            </Card>
          ) : (
            <div className="space-y-2.5">
              {sortedOpenTasks.map(task => {
                const statusCfg = STATUS_CONFIG[task.status] || {};
                const priBorder = PRIORITY_BORDER[task.priority] || 'border-r-slate-300';
                const priBadge = PRIORITY_BADGE[task.priority] || PRIORITY_BADGE.medium;
                const waitStr = getWaitingTime(task);
                const location = [task.project_name, task.building_name, task.floor_name, task.unit_name].filter(Boolean).join(' · ');

                return (
                  <Card key={task.id} className={`p-0 overflow-hidden border-r-4 ${priBorder}`}>
                    <div className="p-3">
                      <div className="flex items-start justify-between mb-1.5">
                        <h4 className="text-sm font-medium text-slate-800 flex-1 leading-snug">{task.title}</h4>
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-md whitespace-nowrap mr-2 ${statusCfg.color || 'bg-slate-100'}`}>
                          {statusCfg.label || task.status}
                        </span>
                      </div>

                      {location && (
                        <p className="text-xs text-slate-400 mb-1.5">{location}</p>
                      )}

                      <div className="flex items-center gap-2 flex-wrap text-[11px]">
                        <span className={`px-1.5 py-0.5 rounded ${priBadge.cls}`}>{priBadge.label}</span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{tCategory(task.category)}</span>
                        {waitStr && (
                          <span className="text-slate-400 flex items-center gap-0.5">
                            <Clock className="w-3 h-3" /> ממתין {waitStr}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 mt-3">
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.id}?action=proof`, { state: { returnTo: '/' } }); }}
                          className="flex-1 py-2.5 rounded-lg bg-green-500 hover:bg-green-600 text-white text-sm font-medium flex items-center justify-center gap-1.5 touch-manipulation active:scale-[0.97] transition-all"
                        >
                          <Camera className="w-4 h-4" />
                          צלם ותקן
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.id}`, { state: { returnTo: '/' } }); }}
                          className="py-2.5 px-4 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium flex items-center justify-center gap-1 touch-manipulation active:scale-[0.97] transition-all"
                        >
                          <Eye className="w-4 h-4" />
                          פרטים
                        </button>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        {completedTasks.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                טופלו לאחרונה
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
                      {task.updated_at && <span> · {new Date(task.updated_at).toLocaleDateString('he-IL')}</span>}
                    </p>
                  </div>
                  <ChevronLeft className="w-4 h-4 text-slate-300 flex-shrink-0" />
                </button>
              ))}
            </Card>
          </div>
        )}

        <div className="h-8" />
      </div>
    </div>
  );
};

export default ContractorDashboard;
