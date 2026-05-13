import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { unitService, unitPlanService, disciplineService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, Upload, FileText, Download, Eye,
  Calendar, User, X, Plus, Search, AlertCircle, FolderOpen,
  Image, Ruler, FileType, Maximize2
} from 'lucide-react';
import PlanViewer from '../components/PlanViewer';
import BulkPlanUploadModal from '../components/BulkPlanUploadModal';

const DEFAULT_DISCIPLINES = [
  'electrical', 'plumbing', 'architecture', 'construction', 'hvac', 'fire_protection'
];

const UPLOAD_ROLES = ['project_manager', 'management_team'];

const FILE_ICONS = {
  'application/pdf': { icon: FileText, color: 'text-red-500', bg: 'bg-red-50', label: 'PDF' },
  'image/jpeg': { icon: Image, color: 'text-blue-500', bg: 'bg-blue-50', label: 'JPG' },
  'image/jpg': { icon: Image, color: 'text-blue-500', bg: 'bg-blue-50', label: 'JPG' },
  'image/png': { icon: Image, color: 'text-emerald-500', bg: 'bg-emerald-50', label: 'PNG' },
  'dwg': { icon: Ruler, color: 'text-violet-500', bg: 'bg-violet-50', label: 'DWG' },
  'dxf': { icon: Ruler, color: 'text-violet-500', bg: 'bg-violet-50', label: 'DXF' },
};

function getFileIcon(plan) {
  const mime = plan.file_type || '';
  const filename = (plan.original_filename || '').toLowerCase();
  if (FILE_ICONS[mime]) return FILE_ICONS[mime];
  if (filename.endsWith('.dwg')) return FILE_ICONS['dwg'];
  if (filename.endsWith('.dxf')) return FILE_ICONS['dxf'];
  if (filename.endsWith('.pdf')) return FILE_ICONS['application/pdf'];
  if (filename.endsWith('.jpg') || filename.endsWith('.jpeg')) return FILE_ICONS['image/jpeg'];
  if (filename.endsWith('.png')) return FILE_ICONS['image/png'];
  return { icon: FileType, color: 'text-slate-400', bg: 'bg-slate-50', label: '' };
}

function formatFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch { return dateStr; }
}

const UnitPlansPage = () => {
  const { projectId, unitId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const fileInputRef = useRef(null);

  const [unitData, setUnitData] = useState(null);
  const [plans, setPlans] = useState([]);
  const [disciplines, setDisciplines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [plansLoading, setPlansLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeDiscipline, setActiveDiscipline] = useState('all');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadDiscipline, setUploadDiscipline] = useState('');
  const [uploadNote, setUploadNote] = useState('');
  const [uploadName, setUploadName] = useState('');
  const [uploadPlanType, setUploadPlanType] = useState('standard');
  const [uploadFile, setUploadFile] = useState(null);
  const [showAddDiscipline, setShowAddDiscipline] = useState(false);
  const [newDisciplineLabel, setNewDisciplineLabel] = useState('');
  const [addingDiscipline, setAddingDiscipline] = useState(false);
  const [search, setSearch] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [detailPlan, setDetailPlan] = useState(null);
  const [fullscreenPlan, setFullscreenPlan] = useState(null);

  // BATCH H.1 (2026-05-13) — bulk upload state for unit plans.
  // Internal file list / progress / results live in <BulkPlanUploadModal>.
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkDefaultDiscipline, setBulkDefaultDiscipline] = useState('');

  const myRole = unitData?.project?.my_role || user?.role;
  const canUpload = user && UPLOAD_ROLES.includes(myRole);

  const loadUnit = useCallback(async () => {
    try {
      const data = await unitService.get(unitId);
      setUnitData(data);
    } catch (err) {
      if (err?.response?.status === 403) {
        setLoadError('forbidden');
        return;
      }
      setLoadError('error');
    } finally {
      setLoading(false);
    }
  }, [unitId]);

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
      const data = await unitPlanService.list(projectId, unitId);
      setPlans(Array.isArray(data) ? data : []);
    } catch {
      toast.error(t('unitPlans', 'loadError'));
    } finally {
      setPlansLoading(false);
    }
  }, [projectId, unitId]);

  useEffect(() => { loadUnit(); loadDisciplines(); }, [loadUnit, loadDisciplines]);
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
        (p.name || '').toLowerCase().includes(q) ||
        (p.original_filename || '').toLowerCase().includes(q) ||
        (p.note || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [plans, activeDiscipline, search]);

  const tenantPlans = useMemo(() => filteredPlans.filter(p => p.plan_type === 'tenant_changes'), [filteredPlans]);
  const standardPlans = useMemo(() => filteredPlans.filter(p => p.plan_type !== 'tenant_changes'), [filteredPlans]);

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadFile(file);
    if (!uploadName) {
      const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '');
      setUploadName(nameWithoutExt);
    }
  };

  const handleUploadSubmit = async () => {
    if (!uploadFile || !uploadDiscipline) {
      toast.error('יש לבחור קובץ ותחום');
      return;
    }
    if (uploadFile.size > 50 * 1024 * 1024) {
      toast.error('קובץ גדול מדי (מקסימום 50MB)');
      return;
    }
    setUploading(true);
    try {
      await unitPlanService.upload(projectId, unitId, uploadFile, uploadDiscipline, {
        note: uploadNote,
        name: uploadName,
        plan_type: uploadPlanType,
      });
      toast.success('התוכנית הועלתה בהצלחה');
      closeUploadModal();
      loadPlans();
    } catch (err) {
      const msg = err?.response?.data?.detail || t('unitPlans', 'uploadError');
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  };

  const closeUploadModal = () => {
    setShowUploadModal(false);
    setUploadFile(null);
    setUploadName('');
    setUploadDiscipline('');
    setUploadNote('');
    setUploadPlanType('standard');
    if (fileInputRef.current) fileInputRef.current.value = '';
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

  const handleBack = () => {
    navigate(`/projects/${projectId}/units/${unitId}`);
  };

  const { unit, floor, building, project } = unitData || {};
  const effectiveLabel = unit?.effective_label || unit?.unit_no || '';

  const subtitleParts = [];
  if (project?.name) subtitleParts.push(project.name);
  if (building?.name) subtitleParts.push(building.name);
  if (floor?.name) subtitleParts.push(floor.name);

  const hasActiveFilters = activeDiscipline !== 'all' || search.trim();
  const clearFilters = () => { setActiveDiscipline('all'); setSearch(''); };

  const renderPlanCard = (plan) => {
    const fi = getFileIcon(plan);
    const IconComp = fi.icon;
    return (
      <div
        key={plan.id}
        onClick={() => setDetailPlan(plan)}
        className="bg-white rounded-xl border border-slate-200 overflow-hidden cursor-pointer hover:shadow-md hover:border-amber-200 transition-all group"
      >
        {plan.thumbnail_url ? (
          <div className="h-24 bg-slate-50 flex items-center justify-center overflow-hidden">
            <img src={plan.thumbnail_url} alt={plan.name || ''} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
          </div>
        ) : (
          <div className={`h-24 ${fi.bg} flex items-center justify-center`}>
            <IconComp className={`w-10 h-10 ${fi.color} opacity-60 group-hover:opacity-80 transition-opacity`} />
          </div>
        )}
        <div className="px-3 py-2.5">
          <h3 className="text-[12px] font-bold text-slate-800 leading-snug break-words line-clamp-2">
            {plan.name || plan.original_filename || ''}
          </h3>
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
              {getDisciplineLabel(plan.discipline)}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400">
            <span>{formatDate(plan.created_at)}</span>
            {(plan.file_type || plan.file_size) && (
              <>
                <span>·</span>
                <span>{fi.label}{plan.file_size ? ` · ${formatFileSize(plan.file_size)}` : ''}</span>
              </>
            )}
          </div>
          {plan.plan_type === 'tenant_changes' && (
            <span className="inline-block mt-1.5 text-[9px] px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">
              שינויי דיירים
            </span>
          )}
        </div>
      </div>
    );
  };

  const renderSection = (title, sectionPlans, color = 'amber') => {
    if (sectionPlans.length === 0) return null;
    const colors = {
      amber: 'text-amber-700 border-amber-200',
      violet: 'text-violet-700 border-violet-200',
    };
    return (
      <div className="space-y-2">
        <div className={`flex items-center gap-2 px-1 pb-1 border-b ${colors[color]}`}>
          <FolderOpen className="w-3.5 h-3.5" />
          <span className="text-xs font-bold">{title}</span>
          <span className="text-[10px] opacity-60">({sectionPlans.length})</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {sectionPlans.map(renderPlanCard)}
        </div>
      </div>
    );
  };

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
        <div className="bg-gradient-to-l from-amber-600 to-amber-500 text-white sticky top-0 z-30">
          <div className="max-w-2xl mx-auto px-4 py-3">
            <div className="flex items-center gap-3">
              <button onClick={handleBack} className="p-1.5 hover:bg-amber-700/30 rounded-lg transition-colors">
                <ArrowRight className="w-5 h-5" />
              </button>
              <h1 className="text-base font-bold">תוכניות</h1>
            </div>
          </div>
        </div>
        <div className="max-w-2xl mx-auto px-4 py-12 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          {loadError === 'forbidden' ? (
            <p className="text-slate-600 font-medium">אין הרשאה לצפייה בתוכניות</p>
          ) : (
            <>
              <p className="text-slate-600 font-medium mb-4">לא הצלחנו לטעון את הדירה</p>
              <button
                onClick={() => { setLoadError(null); setLoading(true); loadUnit(); }}
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
    <div className="min-h-screen bg-slate-50 overflow-x-hidden" dir="rtl">
      <div className="bg-gradient-to-l from-amber-600 to-amber-500 text-white sticky top-0 z-30">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <button onClick={handleBack} className="p-1.5 hover:bg-amber-700/30 rounded-lg transition-colors shrink-0">
                <ArrowRight className="w-5 h-5" />
              </button>
              <div className="min-w-0">
                <h1 className="text-base font-bold flex items-center gap-2 truncate">
                  <FolderOpen className="w-4 h-4 shrink-0" />
                  <span className="truncate">תוכניות — {formatUnitLabel(effectiveLabel)}</span>
                </h1>
                {subtitleParts.length > 0 && (
                  <p className="text-[11px] text-amber-100 truncate">{subtitleParts.join(' › ')}</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-3 space-y-3">
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

        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={activeDiscipline}
            onChange={e => setActiveDiscipline(e.target.value)}
            className="h-9 px-3 bg-white border border-slate-200 rounded-xl text-xs text-slate-600 focus:outline-none focus:ring-1 focus:ring-amber-300 cursor-pointer min-w-0"
          >
            <option value="all">כל התחומים</option>
            {allDisciplinesList.map(d => (
              <option key={d.key} value={d.key}>
                {getDisciplineLabel(d.key)} {disciplineCounts[d.key] ? `(${disciplineCounts[d.key]})` : ''}
              </option>
            ))}
          </select>

          {hasActiveFilters && (
            <button onClick={clearFilters} className="text-xs text-amber-600 hover:text-amber-700 whitespace-nowrap">
              נקה סינון
            </button>
          )}

          <div className="mr-auto flex items-center gap-1.5">
            {canUpload && (
              showAddDiscipline ? (
                <div className="flex items-center gap-1 shrink-0">
                  <input
                    type="text"
                    value={newDisciplineLabel}
                    onChange={e => setNewDisciplineLabel(e.target.value)}
                    placeholder="שם תחום"
                    className="w-20 h-8 px-2 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300"
                    autoFocus
                    onKeyDown={e => { if (e.key === 'Enter') handleAddDiscipline(); if (e.key === 'Escape') { setShowAddDiscipline(false); setNewDisciplineLabel(''); } }}
                  />
                  <button onClick={handleAddDiscipline} disabled={addingDiscipline || !newDisciplineLabel.trim()} className="h-8 px-2 text-xs font-medium bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors">
                    {addingDiscipline ? '...' : 'הוסף'}
                  </button>
                  <button onClick={() => { setShowAddDiscipline(false); setNewDisciplineLabel(''); }} className="h-8 px-1 text-slate-400 hover:text-slate-600">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <button onClick={() => setShowAddDiscipline(true)} className="whitespace-nowrap px-2 py-1.5 rounded-lg text-[11px] font-medium bg-white border border-dashed border-slate-300 text-slate-400 hover:border-amber-400 hover:text-amber-600 transition-all flex items-center gap-1">
                  <Plus className="w-3 h-3" />
                  תחום
                </button>
              )
            )}
          </div>
        </div>

        {canUpload && (
          <div className="flex gap-2">
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex-1 flex items-center justify-center gap-2 py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold shadow-sm transition-colors"
            >
              <Upload className="w-4 h-4" />
              העלאת תוכנית
            </button>
            {/* BATCH H.1 (2026-05-13) — bulk upload entry for unit plans. */}
            <button
              onClick={() => setShowBulkModal(true)}
              className="flex items-center justify-center gap-2 px-4 py-3 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-bold shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              העלאה מרובה
            </button>
          </div>
        )}

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
          <div className="space-y-5">
            {renderSection('שינויי דיירים', tenantPlans, 'violet')}
            {renderSection('תוכניות כלליות', standardPlans, 'amber')}
          </div>
        )}
      </div>

      {canUpload && (
        <button
          onClick={() => setShowUploadModal(true)}
          className="fixed bottom-6 left-6 z-40 w-14 h-14 bg-amber-500 hover:bg-amber-600 text-white rounded-full shadow-xl flex items-center justify-center transition-colors"
        >
          <Plus className="w-6 h-6" />
        </button>
      )}

      {/* BATCH H.1 — bulk upload modal for unit plans. Unit context
          implies floor → showFloorField=false. */}
      {canUpload && (
        <BulkPlanUploadModal
          open={showBulkModal}
          onClose={() => setShowBulkModal(false)}
          allDisciplines={allDisciplinesList}
          getDisciplineLabel={getDisciplineLabel}
          defaultDiscipline={bulkDefaultDiscipline}
          onDefaultDisciplineChange={setBulkDefaultDiscipline}
          showFloorField={false}
          uploadFn={(file, discipline, opts) =>
            unitPlanService.upload(projectId, unitId, file, discipline, opts)
          }
          onUploadComplete={loadPlans}
        />
      )}

      {showUploadModal && canUpload && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closeUploadModal} />
          <div className="relative z-10 w-full sm:max-w-md sm:mx-4 p-5 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl max-h-[92vh] overflow-y-auto" dir="rtl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">העלאת תוכנית</h3>
              <button onClick={closeUploadModal} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.dwg,.dxf" onChange={handleFileSelect} className="hidden" id="unit-plan-file-pick" />
                {uploadFile ? (
                  <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                    <FileText className="w-5 h-5 text-amber-600 shrink-0" />
                    <span className="text-sm text-amber-800 truncate flex-1">{uploadFile.name}</span>
                    <button onClick={() => { setUploadFile(null); if (fileInputRef.current) fileInputRef.current.value = ''; }} className="text-amber-400 hover:text-amber-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label htmlFor="unit-plan-file-pick" className="flex items-center justify-center gap-2 w-full py-4 border-2 border-dashed border-slate-300 rounded-xl text-sm text-slate-500 cursor-pointer hover:border-amber-400 hover:text-amber-600 transition-colors">
                    <Upload className="w-5 h-5" />
                    בחר קובץ (PDF, JPG, PNG, DWG, DXF)
                  </label>
                )}
              </div>

              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">שם התוכנית</label>
                <input
                  type="text"
                  value={uploadName}
                  onChange={e => setUploadName(e.target.value)}
                  placeholder="שם התוכנית"
                  className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-amber-300"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-600 mb-2 block">תחום *</label>
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
                <label className="text-xs font-medium text-slate-600 mb-2 block">סוג</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setUploadPlanType('standard')}
                    className={`flex-1 py-2 rounded-xl text-xs font-medium border transition-colors ${
                      uploadPlanType === 'standard'
                        ? 'bg-amber-500 text-white border-amber-500'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    תוכנית כללית
                  </button>
                  <button
                    onClick={() => setUploadPlanType('tenant_changes')}
                    className={`flex-1 py-2 rounded-xl text-xs font-medium border transition-colors ${
                      uploadPlanType === 'tenant_changes'
                        ? 'bg-violet-500 text-white border-violet-500'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    שינויי דיירים
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">הערה</label>
                <input
                  type="text"
                  value={uploadNote}
                  onChange={e => setUploadNote(e.target.value.slice(0, 200))}
                  placeholder="הערה (אופציונלי, עד 200 תווים)"
                  maxLength={200}
                  className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-amber-300"
                />
              </div>

              <button
                onClick={handleUploadSubmit}
                disabled={uploading || !uploadFile || !uploadDiscipline}
                className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-bold transition-colors bg-amber-500 hover:bg-amber-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                {uploading ? 'מעלה...' : 'העלה'}
              </button>
            </div>
          </div>
        </div>
      )}

      {detailPlan && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setDetailPlan(null)} />
          <div className="relative z-10 w-full sm:max-w-lg sm:mx-4 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl max-h-[92vh] flex flex-col" dir="rtl">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-800 truncate">{detailPlan.name || detailPlan.original_filename}</h3>
              <button onClick={() => setDetailPlan(null)} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors flex-shrink-0">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="overflow-y-auto p-4 space-y-4">
              {detailPlan.thumbnail_url ? (
                <div className="rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
                  <img src={detailPlan.thumbnail_url} alt={detailPlan.name || ''} className="w-full max-h-64 object-contain" />
                </div>
              ) : (detailPlan.file_type || '').startsWith('image/') ? (
                <div className="rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
                  <img src={detailPlan.file_url} alt={detailPlan.name || ''} className="w-full max-h-64 object-contain" />
                </div>
              ) : (detailPlan.file_type === 'application/pdf') ? (
                <div className="rounded-xl overflow-hidden border border-slate-200 bg-slate-50 h-64">
                  <iframe src={detailPlan.file_url} title={detailPlan.name || ''} className="w-full h-full" />
                </div>
              ) : (
                <div className={`h-32 ${getFileIcon(detailPlan).bg} rounded-xl flex items-center justify-center`}>
                  {React.createElement(getFileIcon(detailPlan).icon, { className: `w-12 h-12 ${getFileIcon(detailPlan).color} opacity-50` })}
                </div>
              )}

              <div className="space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">{getDisciplineLabel(detailPlan.discipline)}</span>
                  {detailPlan.plan_type === 'tenant_changes' && (
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">שינויי דיירים</span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <span className="text-slate-400">תאריך</span>
                    <p className="font-medium text-slate-700 mt-0.5">{formatDate(detailPlan.created_at)}</p>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <span className="text-slate-400">גודל</span>
                    <p className="font-medium text-slate-700 mt-0.5">{getFileIcon(detailPlan).label} · {formatFileSize(detailPlan.file_size)}</p>
                  </div>
                  {detailPlan.uploaded_by_name && (
                    <div className="bg-slate-50 rounded-lg px-3 py-2 col-span-2">
                      <span className="text-slate-400">הועלה על ידי</span>
                      <p className="font-medium text-slate-700 mt-0.5">{detailPlan.uploaded_by_name}</p>
                    </div>
                  )}
                </div>
                {detailPlan.note && (
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <span className="text-xs text-slate-400">הערה</span>
                    <p className="text-xs font-medium text-slate-700 mt-0.5">{detailPlan.note}</p>
                  </div>
                )}
              </div>

              <div className="flex gap-2 pt-1 flex-wrap">
                <button
                  onClick={() => setFullscreenPlan(detailPlan)}
                  className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-sm font-bold transition-colors flex items-center justify-center gap-2"
                >
                  <Maximize2 className="w-4 h-4" />
                  צפייה במסך מלא
                </button>
                <a
                  href={detailPlan.file_url}
                  download
                  className="flex-1 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold transition-colors flex items-center justify-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  הורד
                </a>
                <a
                  href={detailPlan.file_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2.5 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors flex items-center gap-1.5"
                >
                  <Eye className="w-4 h-4" />
                  צפה
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {fullscreenPlan && (
        <PlanViewer
          plan={fullscreenPlan}
          onClose={() => setFullscreenPlan(null)}
        />
      )}
    </div>
  );
};

export default UnitPlansPage;
