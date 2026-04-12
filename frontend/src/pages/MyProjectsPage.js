import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from '../contexts/BillingContext';
import { projectService } from '../services/api';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  Search, Plus, FolderOpen, ArrowLeft, HardHat, Loader2, Building2,
  Users, CreditCard, BarChart3, ClipboardList, Shield, X, ChevronLeft
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import HamburgerMenu from '../components/HamburgerMenu';
import NotificationBell from '../components/NotificationBell';
import { navigateToProject } from '../utils/navigation';
import * as DialogPrimitive from '@radix-ui/react-dialog';

const LAST_PROJECT_KEY = 'lastProjectId';

const STATUS_COLORS = {
  active: 'bg-green-100 text-green-700',
  draft: 'bg-slate-100 text-slate-600',
  suspended: 'bg-red-100 text-red-700',
  completed: 'bg-blue-100 text-blue-700',
};

const CreateProjectDialog = ({ open, onClose, onSuccess }) => {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [nameError, setNameError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const resetFields = () => {
    setName('');
    setCode('');
    setNameError('');
  };

  const handleClose = () => {
    resetFields();
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setNameError('שם פרויקט חובה');
      return;
    }
    setSubmitting(true);
    try {
      const data = { name: name.trim() };
      if (code.trim()) data.code = code.trim();
      const result = await projectService.create(data);
      toast.success('פרויקט נוצר בהצלחה');
      resetFields();
      onClose();
      onSuccess(result);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת פרויקט');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <DialogPrimitive.Content className="fixed inset-0 z-50 flex items-center justify-center outline-none pointer-events-none">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6 pointer-events-auto" dir="rtl">
            <div className="flex items-center justify-between mb-5">
              <DialogPrimitive.Title className="text-lg font-bold text-slate-900">
                צור פרויקט חדש
              </DialogPrimitive.Title>
              <DialogPrimitive.Description className="sr-only">
                יצירת פרויקט חדש
              </DialogPrimitive.Description>
              <DialogPrimitive.Close asChild>
                <button className="p-1 rounded-lg hover:bg-slate-100 transition-colors">
                  <X className="w-5 h-5 text-slate-400" />
                </button>
              </DialogPrimitive.Close>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="create-proj-name" className="block text-sm font-medium text-slate-700">
                  שם הפרויקט <span className="text-red-500">*</span>
                </label>
                <input
                  id="create-proj-name"
                  type="text"
                  value={name}
                  onChange={(e) => { setName(e.target.value); setNameError(''); }}
                  placeholder="לדוגמה: פרויקט רמת השרון"
                  className={`w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400 ${nameError ? 'border-red-500' : 'border-slate-300'}`}
                  autoFocus
                />
                {nameError && <p className="text-xs text-red-500">{nameError}</p>}
              </div>
              <div className="space-y-1.5">
                <label htmlFor="create-proj-code" className="block text-sm font-medium text-slate-700">
                  קוד פרויקט
                </label>
                <input
                  id="create-proj-code"
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="לדוגמה: RS-001"
                  className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                />
              </div>
              <Button
                type="submit"
                disabled={submitting}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11 text-sm font-medium"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
                צור פרויקט
              </Button>
            </form>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
};

const MyProjectsPage = () => {
  const { user, logout } = useAuth();
  const { billing } = useBilling();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [lastProject, setLastProject] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  const isPM = user?.role === 'project_manager';
  const isSuperAdmin = user?.platform_role === 'super_admin';
  const isTrialing = billing?.status === 'trialing';
  const trialProjectLimitReached = isTrialing && projects.length >= 1;
  const canCreate = (isPM || isSuperAdmin) && !(trialProjectLimitReached && !isSuperAdmin);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await projectService.list();
      const projectList = Array.isArray(data) ? data : [];
      setProjects(projectList);

      const lastId = localStorage.getItem(LAST_PROJECT_KEY);
      if (lastId) {
        const found = projectList.find(p => p.id === lastId);
        setLastProject(found || null);
        if (!found) {
          localStorage.removeItem(LAST_PROJECT_KEY);
        }
      }
    } catch (error) {
      toast.error('שגיאה בטעינת פרויקטים');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleProjectClick = (project) => {
    navigateToProject(project, navigate);
  };

  const filteredProjects = projects.filter(p => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    return (
      (p.name || '').toLowerCase().includes(q) ||
      (p.code || '').toLowerCase().includes(q) ||
      (p.address || '').toLowerCase().includes(q)
    );
  });

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500 mb-3" />
        <p className="text-slate-500">{t('myProjects', 'title')}...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <header className="bg-slate-800 text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 bg-amber-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <HardHat className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold leading-tight">{t('myProjects', 'title')}</h1>
            {user && (
              <p className="text-xs text-slate-400 truncate">{user.name || user.email}</p>
            )}
          </div>
          <div className="flex items-center gap-1">
            {isSuperAdmin && (
              <>
                <button
                  onClick={() => navigate('/admin/users', { state: { from: '/projects' } })}
                  className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                  title="משתמשים"
                >
                  <Users className="w-4 h-4" />
                </button>
                <button
                  onClick={() => navigate('/admin/billing', { state: { from: '/projects' } })}
                  className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                  title="חיוב"
                >
                  <CreditCard className="w-4 h-4" />
                </button>
              </>
            )}
            <NotificationBell />
            <HamburgerMenu slim onNavigate={(path) => navigate(path)} onLogout={() => { logout(); navigate('/login'); }} />
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-4 space-y-4">
        {isSuperAdmin && (
          <button
            onClick={() => navigate('/admin')}
            className="w-full flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-xl hover:border-amber-300 hover:shadow-sm transition-all"
          >
            <div className="w-10 h-10 bg-amber-500 rounded-lg flex items-center justify-center shrink-0">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1 text-right min-w-0">
              <p className="text-sm font-bold text-slate-800">אדמין פאנל</p>
              <p className="text-xs text-slate-400">סקירה, משתמשים, ארגונים, חיובים</p>
            </div>
            <ArrowLeft className="w-5 h-5 text-slate-300 shrink-0" />
          </button>
        )}

        {lastProject && (
              <Card className="p-4 bg-amber-50 border-amber-200">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <ArrowLeft className="w-5 h-5 text-amber-600" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm text-amber-700 font-medium">{t('myProjects', 'lastProject')}</p>
                      <p className="text-base font-bold text-slate-900 truncate">{lastProject.name}</p>
                    </div>
                  </div>
                  <Button
                    onClick={() => handleProjectClick(lastProject)}
                    className="bg-amber-500 hover:bg-amber-600 text-white px-5 flex-shrink-0"
                  >
                    {t('myProjects', 'enterProject')}
                  </Button>
                </div>
              </Card>
            )}

            <div className="flex gap-2 items-center">
              <div className="flex-1 relative">
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder={t('myProjects', 'searchPlaceholder')}
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-full h-10 pr-9 pl-3 text-sm text-right bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                />
              </div>
              {canCreate && (
                <Button
                  onClick={() => setShowCreateDialog(true)}
                  className="bg-amber-500 hover:bg-amber-600 text-white h-10 w-10 p-0 flex-shrink-0"
                  title={t('myProjects', 'newProject')}
                >
                  <Plus className="w-5 h-5" />
                </Button>
              )}
            </div>

            {filteredProjects.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <FolderOpen className="w-16 h-16 text-slate-300 mb-4" />
                <h2 className="text-lg font-semibold text-slate-600">{t('myProjects', 'emptyState')}</h2>
                <p className="text-sm text-slate-400 mt-2 max-w-xs">{t('myProjects', 'emptyStateHint')}</p>
                {canCreate && (
                  <Button
                    onClick={() => setShowCreateDialog(true)}
                    className="mt-6 bg-amber-500 hover:bg-amber-600 text-white h-12 px-8 text-base font-medium gap-2"
                  >
                    <Plus className="w-5 h-5" />
                    צור פרויקט חדש
                  </Button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {filteredProjects.map(project => {
                  const statusColor = STATUS_COLORS[project.status] || STATUS_COLORS.active;
                  const statusLabel = t('myProjects', 'projectStatus')?.[project.status] || project.status;
                  return (
                    <Card
                      key={project.id}
                      className="p-4 cursor-pointer hover:shadow-md transition-shadow border border-slate-200 hover:border-amber-300 active:bg-slate-50"
                      onClick={() => handleProjectClick(project)}
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-11 h-11 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                          <Building2 className="w-6 h-6 text-slate-500" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-base font-bold text-slate-900 truncate">{project.name}</h3>
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${statusColor}`}>
                              {statusLabel}
                            </span>
                          </div>
                          {project.code && (
                            <p className="text-xs text-slate-500">{t('myProjects', 'code')}: {project.code}</p>
                          )}
                          {project.address && (
                            <p className="text-xs text-slate-400 mt-0.5 truncate">{t('myProjects', 'address')}: {project.address}</p>
                          )}
                        </div>
                        <ChevronLeft className="w-5 h-5 text-slate-400 flex-shrink-0 self-center" />
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
      </div>

      <CreateProjectDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onSuccess={async (project) => {
          const id = project.id;
          localStorage.setItem(LAST_PROJECT_KEY, id);
          await loadProjects();
          navigate(`/projects/${id}/control`);
        }}
      />
    </div>
  );
};

export default MyProjectsPage;
