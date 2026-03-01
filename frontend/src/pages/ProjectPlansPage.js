import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, projectPlanService, disciplineService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, Upload, FileText, Download, Eye,
  Calendar, User, X, Plus, Trash2
} from 'lucide-react';
import { Card } from '../components/ui/card';
import ProjectSwitcher from '../components/ProjectSwitcher';

const DEFAULT_DISCIPLINES = [
  'electrical', 'plumbing', 'architecture', 'construction', 'hvac', 'fire_protection'
];

const UPLOAD_ROLES = ['project_manager', 'management_team'];

const ProjectPlansPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const fileInputRef = useRef(null);

  const [project, setProject] = useState(null);
  const [plans, setPlans] = useState([]);
  const [disciplines, setDisciplines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [plansLoading, setPlansLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeDiscipline, setActiveDiscipline] = useState('all');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadDiscipline, setUploadDiscipline] = useState('electrical');
  const [uploadNote, setUploadNote] = useState('');
  const [showAddDiscipline, setShowAddDiscipline] = useState(false);
  const [newDisciplineLabel, setNewDisciplineLabel] = useState('');
  const [addingDiscipline, setAddingDiscipline] = useState(false);

  const myRole = project?.my_role || user?.role;
  const canUpload = user && UPLOAD_ROLES.includes(myRole);

  const loadProject = useCallback(async () => {
    try {
      const data = await projectService.get(projectId);
      setProject(data);
    } catch (err) {
      if (err?.response?.status === 403) {
        toast.error('אין לך הרשאה לפרויקט זה');
        navigate('/projects');
        return;
      }
      toast.error('שגיאה בטעינת פרויקט');
    } finally {
      setLoading(false);
    }
  }, [projectId, navigate]);

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
      const params = {};
      if (activeDiscipline !== 'all') params.discipline = activeDiscipline;
      const data = await projectPlanService.list(projectId, params);
      setPlans(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error('שגיאה בטעינת תוכניות');
    } finally {
      setPlansLoading(false);
    }
  }, [projectId, activeDiscipline]);

  useEffect(() => { loadProject(); loadDisciplines(); }, [loadProject, loadDisciplines]);
  useEffect(() => { loadPlans(); }, [loadPlans]);

  const getDisciplineLabel = (key) => {
    const fromI18n = t('unitPlans', 'disciplines')?.[key];
    if (fromI18n) return fromI18n;
    const found = disciplines.find(d => d.key === key);
    return found?.label || key;
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await projectPlanService.upload(projectId, file, uploadDiscipline, uploadNote);
      toast.success('הקובץ הועלה בהצלחה');
      setShowUploadModal(false);
      setUploadNote('');
      loadPlans();
    } catch (err) {
      const msg = err?.response?.data?.detail || 'שגיאה בהעלאת קובץ';
      toast.error(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleAddDiscipline = async () => {
    if (!newDisciplineLabel.trim()) return;
    setAddingDiscipline(true);
    try {
      await disciplineService.add(projectId, newDisciplineLabel.trim());
      toast.success('התחום נוסף בהצלחה');
      setNewDisciplineLabel('');
      setShowAddDiscipline(false);
      loadDisciplines();
    } catch (err) {
      const msg = err?.response?.data?.detail || 'שגיאה בהוספת תחום';
      toast.error(msg);
    } finally {
      setAddingDiscipline(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch { return dateStr; }
  };

  const allDisciplinesList = disciplines.length > 0
    ? disciplines
    : DEFAULT_DISCIPLINES.map(d => ({ key: d, label: d, source: 'default' }));

  const handleDelete = async (plan) => {
    const reason = window.prompt('סיבה למחיקת התוכנית:');
    if (!reason || !reason.trim()) return;
    try {
      await projectPlanService.delete(projectId, plan.id, reason.trim());
      toast.success('התוכנית נמחקה');
      loadPlans();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה במחיקה');
    }
  };

  const getBackPath = () => {
    if (myRole === 'contractor') return `/projects/${projectId}/tasks?assignee=me`;
    if (myRole === 'viewer') return `/projects/${projectId}/tasks`;
    return `/projects/${projectId}/control`;
  };

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <header className="bg-slate-800 text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => navigate(getBackPath())}
            className="p-1 hover:bg-slate-700 rounded-lg transition-colors"
            title="חזרה"
          >
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1">
              <span className="text-base font-bold">תוכניות הפרויקט —</span>
              <ProjectSwitcher currentProjectId={projectId} currentProjectName={project?.name || ''} />
            </div>
          </div>
          {canUpload && (
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-amber-500 hover:bg-amber-600 rounded-lg text-sm font-medium transition-colors"
            >
              <Upload className="w-4 h-4" />
              העלאה
            </button>
          )}
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 mt-4 flex gap-4">
        <div className="w-40 shrink-0">
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden sticky top-16">
            <div className="px-3 py-2.5 bg-slate-50 border-b border-slate-200">
              <h3 className="text-xs font-bold text-slate-600">תחומים</h3>
            </div>
            <div className="py-1">
              <button
                onClick={() => setActiveDiscipline('all')}
                className={`w-full text-right px-3 py-2 text-xs font-medium transition-colors ${
                  activeDiscipline === 'all'
                    ? 'bg-amber-50 text-amber-700 border-l-2 border-amber-500'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                הכל
              </button>
              {allDisciplinesList.map(d => (
                <button
                  key={d.key}
                  onClick={() => setActiveDiscipline(d.key)}
                  className={`w-full text-right px-3 py-2 text-xs font-medium transition-colors flex items-center justify-between ${
                    activeDiscipline === d.key
                      ? 'bg-amber-50 text-amber-700 border-l-2 border-amber-500'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <span className="truncate">{getDisciplineLabel(d.key)}</span>
                  {d.source === 'custom' && (
                    <span className="text-[9px] text-slate-400 mr-1">מותאם</span>
                  )}
                </button>
              ))}
            </div>
            {canUpload && (
              <div className="border-t border-slate-200 p-2">
                {showAddDiscipline ? (
                  <div className="space-y-1.5">
                    <input
                      type="text"
                      value={newDisciplineLabel}
                      onChange={e => setNewDisciplineLabel(e.target.value)}
                      placeholder="שם תחום חדש"
                      className="w-full h-8 px-2 text-xs bg-white border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-amber-500"
                      autoFocus
                      onKeyDown={e => { if (e.key === 'Enter') handleAddDiscipline(); if (e.key === 'Escape') setShowAddDiscipline(false); }}
                    />
                    <div className="flex gap-1">
                      <button
                        onClick={handleAddDiscipline}
                        disabled={addingDiscipline || !newDisciplineLabel.trim()}
                        className="flex-1 h-7 text-[10px] font-medium bg-amber-500 text-white rounded-md hover:bg-amber-600 disabled:opacity-50 transition-colors"
                      >
                        {addingDiscipline ? '...' : 'הוסף'}
                      </button>
                      <button
                        onClick={() => { setShowAddDiscipline(false); setNewDisciplineLabel(''); }}
                        className="h-7 px-2 text-[10px] text-slate-500 hover:text-slate-700 rounded-md hover:bg-slate-100"
                      >
                        ביטול
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowAddDiscipline(true)}
                    className="w-full flex items-center justify-center gap-1 h-8 text-xs font-medium text-amber-600 hover:bg-amber-50 rounded-md transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    הוסף תחום
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 min-w-0 pb-8">
          {plansLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            </div>
          ) : plans.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
              <FileText className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">אין תוכניות עדיין</p>
              <p className="text-xs text-slate-400 mt-1">
                {canUpload ? 'לחץ על כפתור ההעלאה כדי להוסיף תוכנית' : 'תוכניות יתווספו על ידי צוות הניהול'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {plans.map(plan => (
                <Card key={plan.id} className="p-3.5 border-slate-200">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 bg-amber-50 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileText className="w-5 h-5 text-amber-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-slate-800 truncate">{plan.original_filename || plan.file_url}</h3>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                          {getDisciplineLabel(plan.discipline)}
                        </span>
                        {plan.uploaded_by_name && (
                          <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                            <User className="w-3 h-3" />
                            {plan.uploaded_by_name}
                          </span>
                        )}
                        <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                          <Calendar className="w-3 h-3" />
                          {formatDate(plan.created_at)}
                        </span>
                      </div>
                      {plan.note && (
                        <p className="text-xs text-slate-500 mt-1">{plan.note}</p>
                      )}
                    </div>
                    <div className="flex gap-1.5 flex-shrink-0">
                      <a
                        href={plan.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                        title="צפה"
                      >
                        <Eye className="w-4 h-4 text-slate-500" />
                      </a>
                      <a
                        href={plan.file_url}
                        download
                        className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                        title="הורד"
                      >
                        <Download className="w-4 h-4 text-slate-500" />
                      </a>
                      {canUpload && (
                        <button
                          onClick={() => handleDelete(plan)}
                          className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                          title="מחק תוכנית"
                        >
                          <Trash2 className="w-4 h-4 text-red-400" />
                        </button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      {showUploadModal && canUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowUploadModal(false)}
          />
          <Card className="relative z-10 w-full max-w-md mx-4 p-5 bg-white shadow-2xl rounded-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">העלאת תוכנית</h3>
              <button
                onClick={() => setShowUploadModal(false)}
                className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-600 mb-2 block">בחר תחום</label>
                <div className="flex flex-wrap gap-1.5">
                  {allDisciplinesList.map(d => (
                    <button
                      key={d.key}
                      onClick={() => setUploadDiscipline(d.key)}
                      className={`text-xs px-2.5 py-1.5 rounded-full border transition-colors ${
                        uploadDiscipline === d.key
                          ? 'bg-amber-500 text-white border-amber-500'
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      {getDisciplineLabel(d.key)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">הערה</label>
                <input
                  type="text"
                  value={uploadNote}
                  onChange={e => setUploadNote(e.target.value)}
                  placeholder="הערה (אופציונלי)"
                  className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                />
              </div>
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.dwg,.dxf"
                  onChange={handleUpload}
                  className="hidden"
                  id="project-plan-upload"
                />
                <label
                  htmlFor="project-plan-upload"
                  className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-bold cursor-pointer transition-colors ${
                    uploading
                      ? 'bg-slate-200 text-slate-400 cursor-wait'
                      : 'bg-amber-500 hover:bg-amber-600 text-white shadow-lg'
                  }`}
                >
                  {uploading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Upload className="w-4 h-4" />
                  )}
                  {uploading ? 'מעלה...' : 'בחר קובץ והעלה'}
                </label>
                <p className="text-[10px] text-slate-400 text-center mt-2">PDF, JPG, PNG, DWG, DXF</p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ProjectPlansPage;
