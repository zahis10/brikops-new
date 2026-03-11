import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, projectPlanService, disciplineService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, FileText, Download, Eye,
  Calendar, User, Search, AlertCircle, Archive, RotateCcw,
  FolderOpen, X
} from 'lucide-react';

const DEFAULT_DISCIPLINES = [
  'electrical', 'plumbing', 'architecture', 'construction', 'hvac', 'fire_protection'
];

const MANAGE_ROLES = ['project_manager', 'management_team'];

const ProjectPlansArchivePage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [project, setProject] = useState(null);
  const [plans, setPlans] = useState([]);
  const [disciplines, setDisciplines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [plansLoading, setPlansLoading] = useState(false);
  const [activeDiscipline, setActiveDiscipline] = useState('all');
  const [search, setSearch] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [restoringPlanId, setRestoringPlanId] = useState(null);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState(null);

  const myRole = project?.my_role || user?.role;
  const canManage = user && MANAGE_ROLES.includes(myRole);

  const loadProject = useCallback(async () => {
    try {
      const data = await projectService.get(projectId);
      setProject(data);
    } catch (err) {
      if (err?.response?.status === 403) {
        setLoadError('forbidden');
        return;
      }
      setLoadError('error');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const loadDisciplines = useCallback(async () => {
    try {
      const data = await disciplineService.list(projectId);
      setDisciplines(Array.isArray(data) ? data : []);
    } catch {
      setDisciplines(DEFAULT_DISCIPLINES.map(d => ({ key: d, label: d, source: 'default' })));
    }
  }, [projectId]);

  const loadPlans = useCallback(async () => {
    try {
      setPlansLoading(true);
      const data = await projectPlanService.listArchived(projectId);
      setPlans(Array.isArray(data) ? data : []);
    } catch {
      toast.error('שגיאה בטעינת ארכיון תוכניות');
    } finally {
      setPlansLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadProject(); loadDisciplines(); }, [loadProject, loadDisciplines]);
  useEffect(() => { loadPlans(); }, [loadPlans]);

  const getDisciplineLabel = (key) => {
    const fromI18n = t('unitPlans', 'disciplines')?.[key];
    if (fromI18n) return fromI18n;
    const found = disciplines.find(d => d.key === key);
    return found?.label || key;
  };

  const allDisciplinesList = disciplines.length > 0
    ? disciplines
    : DEFAULT_DISCIPLINES.map(d => ({ key: d, label: d, source: 'default' }));

  const disciplineCounts = useMemo(() => {
    const counts = {};
    plans.forEach(p => {
      const key = p.discipline || 'other';
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }, [plans]);

  const filteredPlans = useMemo(() => {
    let result = plans;
    if (activeDiscipline !== 'all') {
      result = result.filter(p => p.discipline === activeDiscipline);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(p =>
        (p.original_filename || '').toLowerCase().includes(q) ||
        (p.note || '').toLowerCase().includes(q) ||
        (p.archive_note || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [plans, activeDiscipline, search]);

  const openRestoreModal = (plan) => {
    setRestoreTarget(plan);
    setShowRestoreModal(true);
  };

  const handleRestore = async () => {
    if (!restoreTarget) return;
    setRestoringPlanId(restoreTarget.id);
    try {
      await projectPlanService.restore(projectId, restoreTarget.id);
      toast.success('התוכנית שוחזרה לרשימה הפעילה');
      setShowRestoreModal(false);
      setRestoreTarget(null);
      loadPlans();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה בשחזור תוכנית');
    } finally {
      setRestoringPlanId(null);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch { return dateStr; }
  };

  const headerBlock = (
    <div className="bg-slate-800 text-white sticky top-0 z-30">
      <div className="max-w-2xl mx-auto px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate(`/projects/${projectId}/plans`)}
            className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors flex-shrink-0"
          >
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="min-w-0">
            <h1 className="text-base font-bold flex items-center gap-2">
              <Archive className="w-4 h-4 text-slate-400" />
              ארכיון תוכניות
            </h1>
            {project?.name && (
              <p className="text-[11px] text-slate-400 truncate">{project.name}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50" dir="rtl">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-slate-50" dir="rtl">
        {headerBlock}
        <div className="max-w-2xl mx-auto px-4 py-12 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          {loadError === 'forbidden' ? (
            <p className="text-slate-600 font-medium">אין הרשאה לצפייה בתוכניות</p>
          ) : (
            <>
              <p className="text-slate-600 font-medium mb-4">לא הצלחנו לטעון את הפרויקט</p>
              <button
                onClick={() => { setLoadError(null); setLoading(true); loadProject(); }}
                className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-bold text-sm shadow-sm transition-colors"
              >
                נסה שוב
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      {headerBlock}

      <div className="max-w-2xl mx-auto px-4 py-3 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-[11px] text-slate-400 px-1">
            {plans.length} תוכניות בארכיון
            {activeDiscipline !== 'all' && ` · ${getDisciplineLabel(activeDiscipline)}`}
          </p>
          <button
            onClick={() => navigate(`/projects/${projectId}/plans`)}
            className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-600 transition-colors px-1"
          >
            <FolderOpen className="w-3.5 h-3.5" />
            תוכניות פעילות
          </button>
        </div>

        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="חיפוש בארכיון..."
            className="w-full pr-9 pl-3 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-slate-300"
            dir="rtl"
          />
        </div>

        <div className="flex gap-1 overflow-x-auto pb-1">
          <button
            onClick={() => setActiveDiscipline('all')}
            className={`whitespace-nowrap px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
              activeDiscipline === 'all'
                ? 'bg-slate-600 text-white'
                : 'bg-white border border-slate-200 text-slate-500 hover:border-slate-300'
            }`}
          >
            הכל ({plans.length})
          </button>
          {allDisciplinesList.map(d => {
            const count = disciplineCounts[d.key] || 0;
            if (count === 0) return null;
            return (
              <button
                key={d.key}
                onClick={() => setActiveDiscipline(d.key)}
                className={`whitespace-nowrap px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
                  activeDiscipline === d.key
                    ? 'bg-slate-600 text-white'
                    : 'bg-white border border-slate-200 text-slate-500 hover:border-slate-300'
                }`}
              >
                {getDisciplineLabel(d.key)} ({count})
              </button>
            );
          })}
        </div>

        {plansLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
          </div>
        ) : filteredPlans.length === 0 ? (
          <div className="py-12 text-center">
            <Archive className="w-10 h-10 text-slate-200 mx-auto mb-2" />
            {plans.length === 0 ? (
              <>
                <p className="text-sm text-slate-400">הארכיון ריק</p>
                <p className="text-xs text-slate-400 mt-1">תוכניות שהועברו לארכיון יופיעו כאן</p>
              </>
            ) : (
              <p className="text-sm text-slate-400">לא נמצאו תוכניות תואמות</p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredPlans.map(plan => (
              <div key={plan.id} className="bg-white rounded-xl border border-slate-200 px-4 py-3 opacity-90">
                <div className="flex items-start gap-2.5">
                  <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileText className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-[13px] font-bold text-slate-600 leading-snug break-words line-clamp-2">
                      {plan.original_filename || plan.file_url}
                    </h3>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">
                        {getDisciplineLabel(plan.discipline)}
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                        plan.archive_reason === 'replaced'
                          ? 'bg-blue-50 text-blue-600'
                          : 'bg-slate-100 text-slate-500'
                      }`}>
                        {plan.archive_reason === 'replaced' ? 'הוחלפה' : 'הועברה לארכיון'}
                      </span>
                      {plan.uploaded_by_name && (
                        <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                          <User className="w-3 h-3" />
                          {plan.uploaded_by_name}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                      <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                        <Calendar className="w-3 h-3" />
                        הועלה: {formatDate(plan.created_at)}
                      </span>
                      {plan.archived_at && (
                        <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                          <Archive className="w-3 h-3" />
                          הועבר: {formatDate(plan.archived_at)}
                        </span>
                      )}
                    </div>
                    {plan.archive_note && (
                      <p className="text-xs text-slate-400 mt-1 italic">{plan.archive_note}</p>
                    )}
                    {plan.note && !plan.archive_note && (
                      <p className="text-xs text-slate-400 mt-1">{plan.note}</p>
                    )}
                  </div>
                  <div className="flex gap-0.5 flex-shrink-0">
                    <a
                      href={plan.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                      title="צפה"
                    >
                      <Eye className="w-3.5 h-3.5 text-slate-400" />
                    </a>
                    <a
                      href={plan.file_url}
                      download
                      className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                      title="הורד"
                    >
                      <Download className="w-3.5 h-3.5 text-slate-400" />
                    </a>
                    {canManage && (
                      <button
                        onClick={() => openRestoreModal(plan)}
                        disabled={restoringPlanId === plan.id}
                        className="p-1.5 hover:bg-green-50 rounded-lg transition-colors disabled:opacity-40"
                        title="שחזר לתוכניות פעילות"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-slate-400 hover:text-green-600" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showRestoreModal && restoreTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => { setShowRestoreModal(false); setRestoreTarget(null); }}
          />
          <div className="relative z-10 w-full max-w-sm mx-4 p-5 bg-white shadow-2xl rounded-2xl" dir="rtl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">שחזור תוכנית</h3>
              <button
                onClick={() => { setShowRestoreModal(false); setRestoreTarget(null); }}
                className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-3">
              <div className="bg-slate-50 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500">תוכנית</p>
                <p className="text-sm font-medium text-slate-800 mt-0.5 break-words line-clamp-2">
                  {restoreTarget.original_filename || restoreTarget.file_url}
                </p>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-xl px-3 py-2.5 text-xs text-green-700">
                התוכנית תועבר חזרה לרשימת התוכניות הפעילות ותהיה גלויה לכל המשתמשים.
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleRestore}
                  disabled={!!restoringPlanId}
                  className="flex-1 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {restoringPlanId ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                  שחזר לתוכניות פעילות
                </button>
                <button
                  onClick={() => { setShowRestoreModal(false); setRestoreTarget(null); }}
                  className="px-4 py-2.5 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors"
                >
                  ביטול
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectPlansArchivePage;
