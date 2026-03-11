import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, projectPlanService, disciplineService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, Upload, FileText, Download, Eye,
  Calendar, User, X, Plus, Trash2, Search, AlertCircle, FolderOpen
} from 'lucide-react';

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
  const [search, setSearch] = useState('');
  const [loadError, setLoadError] = useState(null);

  const myRole = project?.my_role || user?.role;
  const canUpload = user && UPLOAD_ROLES.includes(myRole);

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
      const data = await projectPlanService.list(projectId);
      setPlans(Array.isArray(data) ? data : []);
    } catch {
      toast.error('שגיאה בטעינת תוכניות');
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
        (p.note || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [plans, activeDiscipline, search]);

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

  const handleBack = () => {
    if (window.history.length > 2) {
      navigate(-1);
    } else {
      if (myRole === 'contractor') navigate(`/projects/${projectId}/tasks?assignee=me`);
      else if (myRole === 'viewer') navigate(`/projects/${projectId}/tasks`);
      else navigate(`/projects/${projectId}/control`);
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
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <button onClick={handleBack} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="min-w-0">
              <h1 className="text-base font-bold flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-amber-400" />
                תוכניות
              </h1>
              {project?.name && (
                <p className="text-[11px] text-slate-400 truncate">{project.name}</p>
              )}
            </div>
          </div>
          {canUpload && (
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 rounded-lg text-xs font-bold transition-colors"
            >
              <Upload className="w-3.5 h-3.5" />
              העלאה
            </button>
          )}
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
        <p className="text-[11px] text-slate-400 px-1">
          {plans.length} תוכניות
          {activeDiscipline !== 'all' && ` · ${getDisciplineLabel(activeDiscipline)}`}
        </p>

        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="חיפוש תוכנית..."
            className="w-full pr-9 pl-3 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-amber-300"
            dir="rtl"
          />
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-1">
          <button
            onClick={() => setActiveDiscipline('all')}
            className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeDiscipline === 'all'
                ? 'bg-amber-500 text-white'
                : 'bg-white border border-slate-200 text-slate-500 hover:border-slate-300'
            }`}
          >
            הכל ({plans.length})
          </button>
          {allDisciplinesList.map(d => {
            const count = disciplineCounts[d.key] || 0;
            return (
              <button
                key={d.key}
                onClick={() => setActiveDiscipline(d.key)}
                className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeDiscipline === d.key
                    ? 'bg-amber-500 text-white'
                    : 'bg-white border border-slate-200 text-slate-500 hover:border-slate-300'
                }`}
              >
                {getDisciplineLabel(d.key)}{count > 0 ? ` (${count})` : ''}
              </button>
            );
          })}
          {canUpload && (
            showAddDiscipline ? (
              <div className="flex items-center gap-1 shrink-0">
                <input
                  type="text"
                  value={newDisciplineLabel}
                  onChange={e => setNewDisciplineLabel(e.target.value)}
                  placeholder="שם תחום"
                  className="w-24 h-8 px-2 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300"
                  autoFocus
                  onKeyDown={e => { if (e.key === 'Enter') handleAddDiscipline(); if (e.key === 'Escape') { setShowAddDiscipline(false); setNewDisciplineLabel(''); } }}
                />
                <button
                  onClick={handleAddDiscipline}
                  disabled={addingDiscipline || !newDisciplineLabel.trim()}
                  className="h-8 px-2.5 text-xs font-medium bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors"
                >
                  {addingDiscipline ? '...' : 'הוסף'}
                </button>
                <button
                  onClick={() => { setShowAddDiscipline(false); setNewDisciplineLabel(''); }}
                  className="h-8 px-1.5 text-slate-400 hover:text-slate-600"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowAddDiscipline(true)}
                className="whitespace-nowrap px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white border border-dashed border-slate-300 text-slate-400 hover:border-amber-400 hover:text-amber-600 transition-all flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                תחום
              </button>
            )
          )}
        </div>

        {plansLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : filteredPlans.length === 0 ? (
          <div className="py-10 text-center">
            <FileText className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            {plans.length === 0 ? (
              <>
                <p className="text-sm text-slate-500">אין תוכניות עדיין</p>
                <p className="text-xs text-slate-400 mt-1">
                  {canUpload ? 'לחץ על כפתור ההעלאה כדי להוסיף תוכנית' : 'תוכניות יתווספו על ידי צוות הניהול'}
                </p>
              </>
            ) : (
              <p className="text-sm text-slate-400">לא נמצאו תוכניות תואמות</p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredPlans.map(plan => (
              <div key={plan.id} className="bg-white rounded-xl border border-slate-200 px-4 py-3">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileText className="w-4.5 h-4.5 text-amber-500" />
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
                      <p className="text-xs text-slate-500 mt-1.5">{plan.note}</p>
                    )}
                  </div>
                  <div className="flex gap-1 flex-shrink-0">
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
              </div>
            ))}
          </div>
        )}
      </div>

      {showUploadModal && canUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowUploadModal(false)}
          />
          <div className="relative z-10 w-full max-w-md mx-4 p-5 bg-white shadow-2xl rounded-2xl">
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
                  className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-amber-300"
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
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectPlansPage;
