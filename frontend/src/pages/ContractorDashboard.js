import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from '../contexts/BillingContext';
import { projectService, taskService, feedService, membershipService } from '../services/api';
import { tRole } from '../i18n';
import { toast } from 'sonner';
import {
  HardHat, LogOut, FolderOpen, ListTodo, Clock, CheckCircle2,
  AlertTriangle, ArrowLeftRight, MessageSquare, ChevronLeft,
  Building2, Plus, Search
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { tCategory } from '../i18n';
import NewDefectModal from '../components/NewDefectModal';
import {
  ManagementToggle, ProjectFilters, ManagementFAB,
  ProjectCardMenu, ManagementModals,
} from '../components/ManagementPanel';

const STATUS_CONFIG = {
  open: { label: 'פתוח', color: 'bg-blue-100 text-blue-700', icon: FolderOpen },
  assigned: { label: 'שויך', color: 'bg-purple-100 text-purple-700', icon: ListTodo },
  in_progress: { label: 'בביצוע', color: 'bg-amber-100 text-amber-700', icon: Clock },
  waiting_verify: { label: 'ממתין לאימות', color: 'bg-orange-100 text-orange-700', icon: AlertTriangle },
  pending_contractor_proof: { label: 'ממתין להוכחת קבלן', color: 'bg-orange-100 text-orange-700', icon: AlertTriangle },
  pending_manager_approval: { label: 'ממתין לאישור מנהל', color: 'bg-indigo-100 text-indigo-700', icon: Clock },
  closed: { label: 'סגור', color: 'bg-green-100 text-green-700', icon: CheckCircle2 },
  reopened: { label: 'נפתח מחדש', color: 'bg-red-100 text-red-700', icon: ArrowLeftRight },
};

const PRIORITY_CONFIG = {
  low: { label: 'נמוך', color: 'text-slate-500' },
  medium: { label: 'בינוני', color: 'text-blue-600' },
  high: { label: 'גבוה', color: 'text-amber-600' },
  critical: { label: 'קריטי', color: 'text-red-600' },
};


const ContractorDashboard = () => {
  const { user, logout } = useAuth();
  const { isOwner: billingIsOwner } = useBilling();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [feed, setFeed] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [taskStatusFilter, setTaskStatusFilter] = useState('');
  const [taskSearchQuery, setTaskSearchQuery] = useState('');
  const [selectedProject, setSelectedProject] = useState(null);
  const [showNewDefect, setShowNewDefect] = useState(false);
  const canCreate = user?.role === 'project_manager';
  const isPM = user?.role === 'project_manager';
  const isOwner = billingIsOwner || user?.platform_role === 'super_admin';
  const [gitSha, setGitSha] = useState('');

  const [isManageMode, setManageMode] = useState(false);
  const [projectSearchQuery, setProjectSearchQuery] = useState('');
  const [projectStatusFilter, setProjectStatusFilter] = useState('');
  const [hideTestProjects, setHideTestProjects] = useState(true);
  const [myMemberships, setMyMemberships] = useState([]);

  const [activeModal, setActiveModal] = useState(null);
  const [modalProject, setModalProject] = useState(null);

  useEffect(() => {
    const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
    fetch(`${BACKEND_URL}/api/debug/version`)
      .then(r => r.json())
      .then(d => setGitSha(d.git_sha || ''))
      .catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const promises = [
        projectService.list(),
        taskService.list(),
        feedService.list(null, 20),
      ];
      if (isPM) {
        promises.push(membershipService.getMyMemberships());
      }
      const results = await Promise.all(promises);
      const [projectList, taskList, feedList] = results;
      setProjects(Array.isArray(projectList) ? projectList : []);
      setTasks(Array.isArray(taskList) ? taskList : []);
      setFeed(Array.isArray(feedList) ? feedList : []);
      if (isPM && results[3]) {
        setMyMemberships(Array.isArray(results[3]) ? results[3] : []);
      }

      const pList = Array.isArray(projectList) ? projectList : [];
      if (pList.length > 0) {
        const dash = await projectService.getDashboard(pList[0].id);
        setDashboard(dash);
        setSelectedProject(pList[0]);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('שגיאה בטעינת נתונים');
    } finally {
      setLoading(false);
    }
  }, [isPM]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const canManageProject = useCallback((project) => {
    if (isOwner) return true;
    if (isPM) {
      return myMemberships.some(m => m.project_id === project.id);
    }
    return false;
  }, [isOwner, isPM, myMemberships]);

  const filteredProjects = projects.filter(p => {
    if (hideTestProjects) {
      const nameLC = (p.name || '').toLowerCase();
      const codeLC = (p.code || '').toLowerCase();
      if (nameLC.includes('e2e') || nameLC.includes('test') || codeLC.includes('e2e') || codeLC.includes('test')) {
        return false;
      }
    }
    if (projectStatusFilter && p.status !== projectStatusFilter) return false;
    if (projectSearchQuery) {
      const q = projectSearchQuery.toLowerCase();
      return (p.name || '').toLowerCase().includes(q) || (p.code || '').toLowerCase().includes(q);
    }
    return true;
  });

  const filteredTasks = tasks.filter(t => {
    if (taskStatusFilter && t.status !== taskStatusFilter) return false;
    if (taskSearchQuery) {
      const q = taskSearchQuery.toLowerCase();
      return t.title.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q);
    }
    return true;
  });

  const handleManagementAction = useCallback((action, project = null) => {
    setModalProject(project);
    setActiveModal(action);
  }, []);

  const handleModalSuccess = useCallback(() => {
    setActiveModal(null);
    setModalProject(null);
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500 mx-auto"></div>
          <p className="text-slate-500 mt-4">טוען נתונים...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-slate-800 text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-500 rounded-lg flex items-center justify-center">
              <HardHat className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight">BrikOps</h1>
              <p className="text-xs text-slate-400">{user?.name} • {tRole(user?.role)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ManagementToggle
              isManageMode={isManageMode}
              setManageMode={setManageMode}
              isOwner={isOwner}
              isPM={isPM}
            />
            {isOwner && (
              <Button size="sm" onClick={() => navigate('/admin')} className="bg-blue-500 hover:bg-blue-600 text-white">
                <Building2 className="w-4 h-4 ml-1" />
                <span className="hidden sm:inline">ניהול מערכת</span>
              </Button>
            )}
            {isPM && (
              <Button size="sm" onClick={() => navigate('/join-requests')} className="bg-green-500 hover:bg-green-600 text-white">
                <ListTodo className="w-4 h-4 ml-1" />
                <span className="hidden sm:inline">בקשות הצטרפות</span>
              </Button>
            )}
            {canCreate && !isManageMode && (
              <Button size="sm" onClick={() => setShowNewDefect(true)} className="bg-amber-500 hover:bg-amber-600 text-white">
                <Plus className="w-4 h-4 ml-1" />
                <span className="hidden sm:inline">ליקוי חדש</span>
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={handleLogout} className="text-slate-300 hover:text-white hover:bg-slate-700">
              <LogOut className="w-4 h-4 ml-1" />
              <span className="hidden sm:inline">יציאה</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex gap-2 mb-4 p-1 bg-white rounded-lg shadow-sm border">
          {[
            { id: 'overview', label: 'סקירה', icon: Building2 },
            { id: 'tasks', label: 'משימות', icon: ListTodo },
            { id: 'feed', label: 'עדכונים', icon: MessageSquare },
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-1.5 touch-manipulation ${
                activeTab === tab.id ? 'bg-amber-500 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <div className="space-y-4">
            {dashboard && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Card className="p-4 text-center">
                  <p className="text-3xl font-bold text-slate-800">{dashboard.total_tasks}</p>
                  <p className="text-xs text-slate-500 mt-1">סה"כ משימות</p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-3xl font-bold text-amber-600">{dashboard.by_status?.in_progress || 0}</p>
                  <p className="text-xs text-slate-500 mt-1">בביצוע</p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-3xl font-bold text-green-600">{dashboard.by_status?.closed || 0}</p>
                  <p className="text-xs text-slate-500 mt-1">הושלמו</p>
                </Card>
                <Card
                  className="p-4 text-center cursor-pointer hover:shadow-md hover:border-red-200 transition-all active:scale-95"
                  onClick={() => selectedProject && navigate(`/projects/${selectedProject.id}/tasks?status=open`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && selectedProject) { e.preventDefault(); navigate(`/projects/${selectedProject.id}/tasks?status=open`); } }}
                >
                  <p className="text-3xl font-bold text-red-600">{(dashboard.by_status?.open || 0) + (dashboard.by_status?.assigned || 0) + (dashboard.by_status?.in_progress || 0)}</p>
                  <p className="text-xs text-slate-500 mt-1">ליקויים פתוחים ←</p>
                </Card>
              </div>
            )}

            {dashboard && Object.keys(dashboard.by_status || {}).length > 0 && (
              <Card className="p-4">
                <h3 className="text-sm font-medium text-slate-700 mb-3">משימות לפי סטטוס</h3>
                <div className="space-y-2">
                  {Object.entries(dashboard.by_status).map(([status, count]) => {
                    const config = STATUS_CONFIG[status];
                    const pct = dashboard.total_tasks > 0 ? Math.round((count / dashboard.total_tasks) * 100) : 0;
                    return (
                      <div key={status} className="flex items-center gap-3">
                        <span className={`text-xs font-medium px-2 py-1 rounded-md min-w-[90px] text-center ${config?.color || 'bg-slate-100'}`}>
                          {config?.label || status}
                        </span>
                        <div className="flex-1 bg-slate-100 rounded-full h-2.5">
                          <div className="h-2.5 rounded-full bg-amber-500 transition-all" style={{width: `${pct}%`}}></div>
                        </div>
                        <span className="text-sm font-medium text-slate-700 min-w-[32px] text-left">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            )}

            {dashboard && Object.keys(dashboard.by_category || {}).length > 0 && (
              <Card className="p-4">
                <h3 className="text-sm font-medium text-slate-700 mb-3">משימות לפי קטגוריה</h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(dashboard.by_category).map(([cat, count]) => (
                    <span key={cat} className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-xs font-medium">
                      {tCategory(cat)}: {count}
                    </span>
                  ))}
                </div>
              </Card>
            )}

            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-slate-700">פרויקטים ({filteredProjects.length})</h3>
              </div>

              <ProjectFilters
                searchQuery={projectSearchQuery}
                setSearchQuery={setProjectSearchQuery}
                statusFilter={projectStatusFilter}
                setStatusFilter={setProjectStatusFilter}
                hideTestProjects={hideTestProjects}
                setHideTestProjects={setHideTestProjects}
              />

              {filteredProjects.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4">אין פרויקטים</p>
              ) : (
                <div className="space-y-2 mt-3">
                  {filteredProjects.map(project => (
                    <div key={project.id}
                      className="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                    >
                      <div className="flex items-center gap-3 flex-1 cursor-pointer" onClick={() => {
                        if (isOwner || isPM) {
                          navigate(`/projects/${project.id}/control`);
                        } else {
                          setSelectedProject(project);
                          projectService.getDashboard(project.id).then(setDashboard).catch(() => {});
                        }
                      }}>
                        <Building2 className="w-5 h-5 text-amber-500" />
                        <div>
                          <p className="text-sm font-medium text-slate-800">{project.name}</p>
                          <p className="text-xs text-slate-500">קוד: {project.code} {project.status !== 'active' ? `• ${project.status}` : ''}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        {isManageMode && (
                          <ProjectCardMenu
                            project={project}
                            isOwner={isOwner}
                            isPM={isPM}
                            canManage={canManageProject(project)}
                            onAction={handleManagementAction}
                          />
                        )}
                        <ChevronLeft className="w-4 h-4 text-slate-400" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className="space-y-3">
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input type="text" placeholder="חיפוש משימות..." value={taskSearchQuery}
                  onChange={e => setTaskSearchQuery(e.target.value)}
                  className="w-full h-10 pr-9 pl-3 text-sm text-right bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                />
              </div>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => {
                    const statuses = ['', ...Object.keys(STATUS_CONFIG)];
                    const idx = statuses.indexOf(taskStatusFilter);
                    setTaskStatusFilter(statuses[(idx + 1) % statuses.length]);
                  }}
                  className="h-10 px-3 text-sm bg-white border border-slate-200 rounded-lg whitespace-nowrap"
                >
                  {taskStatusFilter ? STATUS_CONFIG[taskStatusFilter]?.label : 'כל הסטטוסים'}
                </button>
              </div>
            </div>

            {filteredTasks.length === 0 ? (
              <Card className="p-8 text-center">
                <ListTodo className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">אין משימות להצגה</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {filteredTasks.map(task => {
                  const statusCfg = STATUS_CONFIG[task.status] || {};
                  const priorityCfg = PRIORITY_CONFIG[task.priority] || {};
                  return (
                    <Card key={task.id} className="p-3 hover:shadow-md transition-shadow cursor-pointer" onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: '/' } })}>
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h4 className="text-sm font-medium text-slate-800">{task.title}</h4>
                          {task.description && (
                            <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{task.description}</p>
                          )}
                        </div>
                        <span className={`text-xs font-medium px-2 py-1 rounded-md whitespace-nowrap mr-2 ${statusCfg.color || 'bg-slate-100'}`}>
                          {statusCfg.label || task.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-500">
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
              </div>
            )}
          </div>
        )}

        {activeTab === 'feed' && (
          <div className="space-y-2">
            {feed.length === 0 ? (
              <Card className="p-8 text-center">
                <MessageSquare className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">אין עדכונים</p>
              </Card>
            ) : (
              feed.map(update => (
                <Card key={update.id} className="p-3">
                  <div className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      update.update_type === 'status_change' ? 'bg-amber-100' :
                      update.update_type === 'attachment' ? 'bg-blue-100' : 'bg-slate-100'
                    }`}>
                      {update.update_type === 'status_change' ? (
                        <ArrowLeftRight className="w-4 h-4 text-amber-600" />
                      ) : update.update_type === 'attachment' ? (
                        <Plus className="w-4 h-4 text-blue-600" />
                      ) : (
                        <MessageSquare className="w-4 h-4 text-slate-600" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-800">{update.content}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                        <span>{update.user_name || 'מערכת'}</span>
                        {update.created_at && (
                          <span>{new Date(update.created_at).toLocaleDateString('he-IL')}</span>
                        )}
                        {update.old_status && update.new_status && (
                          <span className="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">
                            {STATUS_CONFIG[update.old_status]?.label || update.old_status} → {STATUS_CONFIG[update.new_status]?.label || update.new_status}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        )}
      </div>

      {canCreate && !isManageMode && (
        <button
          onClick={() => setShowNewDefect(true)}
          className="fixed bottom-6 left-6 w-14 h-14 bg-amber-500 hover:bg-amber-600 text-white rounded-full shadow-lg flex items-center justify-center transition-colors z-40 md:hidden"
        >
          <Plus className="w-6 h-6" />
        </button>
      )}

      <ManagementFAB
        isManageMode={isManageMode}
        isOwner={isOwner}
        isPM={isPM}
        onAction={handleManagementAction}
      />

      <ManagementModals
        activeModal={activeModal}
        modalProject={modalProject}
        onClose={() => { setActiveModal(null); setModalProject(null); }}
        onSuccess={handleModalSuccess}
        isOwner={isOwner}
        isPM={isPM}
        myMemberships={myMemberships}
      />

      <NewDefectModal
        isOpen={showNewDefect}
        onClose={() => setShowNewDefect(false)}
        onSuccess={(taskId) => {
          setShowNewDefect(false);
          loadData();
          navigate(`/tasks/${taskId}`);
        }}
      />

      {gitSha && (
        <div className="text-center py-2">
          <p className="text-[10px] text-slate-300">v{gitSha}</p>
        </div>
      )}
    </div>
  );
};

export default ContractorDashboard;
