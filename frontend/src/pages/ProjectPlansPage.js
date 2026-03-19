import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, projectPlanService, disciplineService, buildingService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, Upload, FileText, Download, Eye,
  Calendar, User, X, Plus, Search, AlertCircle, FolderOpen, Archive, RefreshCw, Clock, Users, CheckCircle,
  Edit3, Image, Ruler, FileType, ChevronDown, Filter
} from 'lucide-react';

const DEFAULT_DISCIPLINES = [
  'electrical', 'plumbing', 'architecture', 'construction', 'hvac', 'fire_protection'
];

const UPLOAD_ROLES = ['project_manager', 'management_team'];
const MANAGER_VIEW_ROLES = ['super_admin', 'project_manager', 'management_team'];

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

function formatSeenDate(dateStr) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('he-IL', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return dateStr; }
}

const ProjectPlansPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const fileInputRef = useRef(null);
  const replaceFileInputRef = useRef(null);

  const [project, setProject] = useState(null);
  const [plans, setPlans] = useState([]);
  const [disciplines, setDisciplines] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [allFloors, setAllFloors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [plansLoading, setPlansLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [activeDiscipline, setActiveDiscipline] = useState('all');
  const [activeFloor, setActiveFloor] = useState('all');
  const [search, setSearch] = useState('');
  const [loadError, setLoadError] = useState(null);

  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadDiscipline, setUploadDiscipline] = useState('');
  const [uploadNote, setUploadNote] = useState('');
  const [uploadName, setUploadName] = useState('');
  const [uploadPlanType, setUploadPlanType] = useState('standard');
  const [uploadFloorId, setUploadFloorId] = useState('');
  const [uploadUnitId, setUploadUnitId] = useState('');
  const [uploadFile, setUploadFile] = useState(null);

  const [showAddDiscipline, setShowAddDiscipline] = useState(false);
  const [newDisciplineLabel, setNewDisciplineLabel] = useState('');
  const [addingDiscipline, setAddingDiscipline] = useState(false);

  const [showArchiveModal, setShowArchiveModal] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState(null);
  const [archiveNote, setArchiveNote] = useState('');
  const [archivingPlanId, setArchivingPlanId] = useState(null);

  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState(null);
  const [replaceNote, setReplaceNote] = useState('');
  const [replacing, setReplacing] = useState(false);

  const [showSeenModal, setShowSeenModal] = useState(false);
  const [seenModalData, setSeenModalData] = useState(null);
  const [seenModalLoading, setSeenModalLoading] = useState(false);
  const [seenModalPlanName, setSeenModalPlanName] = useState('');

  const [detailPlan, setDetailPlan] = useState(null);
  const [editingDetail, setEditingDetail] = useState(false);
  const [editFields, setEditFields] = useState({});
  const [saving, setSaving] = useState(false);

  const [versionFile, setVersionFile] = useState(null);
  const [versionNote, setVersionNote] = useState('');
  const [uploadingVersion, setUploadingVersion] = useState(false);
  const [showVersionUpload, setShowVersionUpload] = useState(false);
  const [versionHistory, setVersionHistory] = useState([]);
  const [versionHistoryLoading, setVersionHistoryLoading] = useState(false);
  const versionFileRef = useRef(null);

  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkFiles, setBulkFiles] = useState([]);
  const [bulkDefaultDiscipline, setBulkDefaultDiscipline] = useState('');
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkResults, setBulkResults] = useState(null);
  const bulkFileRef = useRef(null);

  const myRole = project?.my_role || user?.role;
  const canManage = user && UPLOAD_ROLES.includes(myRole);
  const isManager = user && (MANAGER_VIEW_ROLES.includes(myRole) || user?.role === 'super_admin');

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

  const loadBuildingsAndFloors = useCallback(async () => {
    try {
      const blds = await projectService.getBuildings(projectId);
      setBuildings(Array.isArray(blds) ? blds : []);
      const floorPromises = (blds || []).map(b =>
        buildingService.getFloors(b.id).then(floors =>
          (floors || []).map(f => ({ ...f, building_id: b.id, building_name: b.name }))
        ).catch(() => [])
      );
      const floorArrays = await Promise.all(floorPromises);
      setAllFloors(floorArrays.flat());
    } catch {
      setBuildings([]);
      setAllFloors([]);
    }
  }, [projectId]);

  useEffect(() => { loadProject(); loadDisciplines(); loadBuildingsAndFloors(); }, [loadProject, loadDisciplines, loadBuildingsAndFloors]);
  useEffect(() => { loadPlans(); }, [loadPlans]);

  const getDisciplineLabel = (key) => {
    const fromI18n = t('unitPlans', 'disciplines')?.[key];
    if (fromI18n) return fromI18n;
    const found = disciplines.find(d => d.key === key);
    return found?.label || key;
  };

  const getFloorName = (floorId) => {
    if (!floorId) return '';
    const floor = allFloors.find(f => f.id === floorId);
    return floor ? (floor.name || `קומה ${floor.number || ''}`) : '';
  };

  const getUnitName = (unitId) => {
    if (!unitId) return '';
    return unitId;
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

  const uniqueDisciplinesCount = useMemo(() => {
    return new Set(plans.map(p => p.discipline).filter(Boolean)).size;
  }, [plans]);

  const filteredPlans = useMemo(() => {
    let result = plans;
    if (activeDiscipline !== 'all') {
      result = result.filter(p => p.discipline === activeDiscipline);
    }
    if (activeFloor !== 'all') {
      result = result.filter(p => p.floor_id === activeFloor);
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
  }, [plans, activeDiscipline, activeFloor, search]);

  const hasActiveFilters = activeDiscipline !== 'all' || activeFloor !== 'all' || search.trim();

  const clearFilters = () => {
    setActiveDiscipline('all');
    setActiveFloor('all');
    setSearch('');
  };

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
    setUploading(true);
    try {
      await projectPlanService.upload(projectId, uploadFile, uploadDiscipline, {
        note: uploadNote,
        name: uploadName,
        plan_type: uploadPlanType,
        floor_id: uploadFloorId || undefined,
        unit_id: uploadUnitId || undefined,
      });
      toast.success('התוכנית הועלתה בהצלחה');
      closeUploadModal();
      loadPlans();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה בהעלאת קובץ');
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
    setUploadFloorId('');
    setUploadUnitId('');
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
      toast.error(err?.response?.data?.detail || 'שגיאה בהוספת תחום');
    } finally {
      setAddingDiscipline(false);
    }
  };

  const openArchiveModal = (plan) => {
    setArchiveTarget(plan);
    setArchiveNote('');
    setShowArchiveModal(true);
  };

  const handleArchive = async () => {
    if (!archiveTarget) return;
    setArchivingPlanId(archiveTarget.id);
    try {
      await projectPlanService.archive(projectId, archiveTarget.id, archiveNote);
      toast.success('התוכנית הועברה לארכיון');
      setShowArchiveModal(false);
      setArchiveTarget(null);
      if (detailPlan?.id === archiveTarget.id) setDetailPlan(null);
      loadPlans();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה בהעברה לארכיון');
    } finally {
      setArchivingPlanId(null);
    }
  };

  const openReplaceModal = (plan) => {
    setReplaceTarget(plan);
    setReplaceNote('');
    setShowReplaceModal(true);
  };

  const handleReplace = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !replaceTarget) return;
    setReplacing(true);
    try {
      await projectPlanService.replace(projectId, replaceTarget.id, file, replaceNote);
      toast.success('התוכנית הוחלפה בהצלחה');
      setShowReplaceModal(false);
      setReplaceTarget(null);
      setReplaceNote('');
      loadPlans();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה בהחלפת תוכנית');
    } finally {
      setReplacing(false);
      if (replaceFileInputRef.current) replaceFileInputRef.current.value = '';
    }
  };

  const handleViewPlan = (plan) => {
    projectPlanService.markSeen(projectId, plan.id);
  };

  const openSeenModal = async (plan) => {
    setSeenModalPlanName(plan.name || plan.original_filename || plan.file_url);
    setShowSeenModal(true);
    setSeenModalLoading(true);
    setSeenModalData(null);
    try {
      const data = await projectPlanService.getSeenStatus(projectId, plan.id);
      setSeenModalData(data);
    } catch {
      toast.error('שגיאה בטעינת סטטוס צפייה');
      setShowSeenModal(false);
    } finally {
      setSeenModalLoading(false);
    }
  };

  const openDetail = (plan) => {
    setDetailPlan(plan);
    setEditingDetail(false);
    setShowVersionUpload(false);
    setVersionFile(null);
    setVersionNote('');
    handleViewPlan(plan);
    loadVersionHistory(plan.id);
  };

  const startEdit = () => {
    setEditFields({
      name: detailPlan.name || detailPlan.original_filename || '',
      discipline: detailPlan.discipline || '',
      floor_id: detailPlan.floor_id || '',
      unit_id: detailPlan.unit_id || '',
      plan_type: detailPlan.plan_type || 'standard',
      note: detailPlan.note || '',
    });
    setEditingDetail(true);
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      const updated = await projectPlanService.update(projectId, detailPlan.id, editFields);
      setDetailPlan(updated);
      setEditingDetail(false);
      toast.success('התוכנית עודכנה');
      loadPlans();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה בעדכון');
    } finally {
      setSaving(false);
    }
  };

  const loadVersionHistory = async (planId) => {
    setVersionHistoryLoading(true);
    try {
      const data = await projectPlanService.getVersions(projectId, planId);
      setVersionHistory(data.versions || []);
    } catch {
      setVersionHistory([]);
    } finally {
      setVersionHistoryLoading(false);
    }
  };

  const handleVersionUpload = async () => {
    if (!versionFile || !detailPlan) return;
    if (versionFile.size > 50 * 1024 * 1024) {
      toast.error('קובץ גדול מדי (מקסימום 50MB)');
      return;
    }
    setUploadingVersion(true);
    try {
      const updated = await projectPlanService.uploadVersion(projectId, detailPlan.id, versionFile, versionNote);
      setDetailPlan(updated);
      setVersionFile(null);
      setVersionNote('');
      setShowVersionUpload(false);
      if (versionFileRef.current) versionFileRef.current.value = '';
      toast.success(`גרסה ${updated.current_version} הועלתה בהצלחה`);
      loadPlans();
      loadVersionHistory(detailPlan.id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה בהעלאת גרסה');
    } finally {
      setUploadingVersion(false);
    }
  };

  const handleBulkFileSelect = (files) => {
    const fileList = Array.from(files);
    if (fileList.length + bulkFiles.length > 20) {
      toast.error('ניתן להעלות עד 20 קבצים');
      return;
    }
    const newFiles = fileList.map(f => ({
      file: f,
      id: Math.random().toString(36).slice(2),
      discipline: bulkDefaultDiscipline || '',
      floor_id: '',
      unit_id: '',
      plan_type: 'standard',
      status: f.size > 50 * 1024 * 1024 ? 'error' : 'pending',
      error: f.size > 50 * 1024 * 1024 ? 'קובץ גדול מדי (מקסימום 50MB)' : '',
      progress: 0,
    }));
    setBulkFiles(prev => [...prev, ...newFiles]);
  };

  const removeBulkFile = (id) => {
    setBulkFiles(prev => prev.filter(f => f.id !== id));
  };

  const updateBulkFile = (id, updates) => {
    setBulkFiles(prev => prev.map(f => f.id === id ? { ...f, ...updates } : f));
  };

  const handleBulkUpload = async () => {
    const toUpload = bulkFiles.filter(f => f.status === 'pending' && f.discipline);
    if (toUpload.length === 0) {
      toast.error('אין קבצים תקינים להעלאה');
      return;
    }
    setBulkUploading(true);
    let succeeded = 0;
    let failed = 0;
    const CONCURRENCY = 3;
    for (let i = 0; i < toUpload.length; i += CONCURRENCY) {
      const batch = toUpload.slice(i, i + CONCURRENCY);
      await Promise.all(batch.map(async (bf) => {
        updateBulkFile(bf.id, { status: 'uploading', progress: 50 });
        try {
          await projectPlanService.upload(projectId, bf.file, bf.discipline, {
            plan_type: bf.plan_type || 'standard',
            floor_id: bf.floor_id || undefined,
            unit_id: bf.unit_id || undefined,
          });
          updateBulkFile(bf.id, { status: 'done', progress: 100 });
          succeeded++;
        } catch (err) {
          updateBulkFile(bf.id, {
            status: 'error',
            error: err?.response?.data?.detail || 'שגיאה בהעלאה',
            progress: 0,
          });
          failed++;
        }
      }));
    }
    setBulkUploading(false);
    setBulkResults({ succeeded, failed, total: toUpload.length });
    if (succeeded > 0) loadPlans();
  };

  const retryBulkFile = async (bf) => {
    updateBulkFile(bf.id, { status: 'uploading', progress: 50, error: '' });
    try {
      await projectPlanService.upload(projectId, bf.file, bf.discipline, {
        plan_type: bf.plan_type || 'standard',
        floor_id: bf.floor_id || undefined,
        unit_id: bf.unit_id || undefined,
      });
      updateBulkFile(bf.id, { status: 'done', progress: 100 });
      loadPlans();
      toast.success(`${bf.file.name} הועלה בהצלחה`);
    } catch (err) {
      updateBulkFile(bf.id, {
        status: 'error',
        error: err?.response?.data?.detail || 'שגיאה בהעלאה',
        progress: 0,
      });
    }
  };

  const closeBulkModal = () => {
    setShowBulkModal(false);
    setBulkFiles([]);
    setBulkDefaultDiscipline('');
    setBulkResults(null);
    setBulkUploading(false);
    if (bulkFileRef.current) bulkFileRef.current.value = '';
  };

  const [uploadFloorUnits, setUploadFloorUnits] = useState([]);
  useEffect(() => {
    if (!uploadFloorId) { setUploadFloorUnits([]); return; }
    const floor = allFloors.find(f => f.id === uploadFloorId);
    if (floor) {
      buildingService.getUnits(floor.id)
        .then(units => setUploadFloorUnits(Array.isArray(units) ? units : []))
        .catch(() => setUploadFloorUnits([]));
    }
  }, [uploadFloorId, allFloors]);

  const [editFloorUnits, setEditFloorUnits] = useState([]);
  useEffect(() => {
    const fid = editFields.floor_id;
    if (!fid) { setEditFloorUnits([]); return; }
    const floor = allFloors.find(f => f.id === fid);
    if (floor) {
      buildingService.getUnits(floor.id)
        .then(units => setEditFloorUnits(Array.isArray(units) ? units : []))
        .catch(() => setEditFloorUnits([]));
    }
  }, [editFields.floor_id, allFloors]);

  const handleBack = () => {
    if (window.history.length > 2) {
      navigate(-1);
    } else {
      if (myRole === 'contractor') navigate('/projects');
      else if (myRole === 'viewer') navigate(`/projects/${projectId}/tasks`);
      else navigate(`/projects/${projectId}/control`);
    }
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
          <div className="max-w-4xl mx-auto px-4 py-3">
            <div className="flex items-center gap-3">
              <button onClick={handleBack} className="p-1.5 hover:bg-amber-700/30 rounded-lg transition-colors">
                <ArrowRight className="w-5 h-5" />
              </button>
              <h1 className="text-base font-bold">תוכניות</h1>
            </div>
          </div>
        </div>
        <div className="max-w-4xl mx-auto px-4 py-12 text-center">
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
                  <span className="truncate">תוכניות {project?.name ? `— ${project.name}` : ''}</span>
                </h1>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-[11px] text-amber-100">{plans.length} תוכניות</span>
                  <span className="text-[11px] text-amber-200">·</span>
                  <span className="text-[11px] text-amber-100">{uniqueDisciplinesCount} תחומים</span>
                </div>
              </div>
            </div>
            <button
              onClick={() => navigate(`/projects/${projectId}/plans/archive`)}
              className="flex items-center gap-1 text-[11px] text-amber-100 hover:text-white transition-colors shrink-0"
            >
              <Archive className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">ארכיון</span>
            </button>
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

          {allFloors.length > 0 && (
            <select
              value={activeFloor}
              onChange={e => setActiveFloor(e.target.value)}
              className="h-9 px-3 bg-white border border-slate-200 rounded-xl text-xs text-slate-600 focus:outline-none focus:ring-1 focus:ring-amber-300 cursor-pointer min-w-0"
            >
              <option value="all">כל הקומות</option>
              {allFloors.map(f => (
                <option key={f.id} value={f.id}>
                  {f.building_name ? `${f.building_name} - ` : ''}{f.name || `קומה ${f.number || ''}`}
                </option>
              ))}
            </select>
          )}

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-amber-600 hover:text-amber-700 whitespace-nowrap"
            >
              נקה סינון
            </button>
          )}

          <div className="mr-auto flex items-center gap-1.5">
            {canManage && (
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

        {canManage && (
          <div className="flex gap-2">
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex-1 flex items-center justify-center gap-2 py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold shadow-sm transition-colors"
            >
              <Upload className="w-4 h-4" />
              העלאת תוכנית
            </button>
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
                <p className="text-sm text-slate-500">אין תוכניות פעילות</p>
                <p className="text-xs text-slate-400 mt-1">
                  {canManage ? 'לחץ על כפתור ההעלאה כדי להוסיף תוכנית' : 'תוכניות יתווספו על ידי צוות הניהול'}
                </p>
              </>
            ) : (
              <p className="text-sm text-slate-400">לא נמצאו תוכניות תואמות</p>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {filteredPlans.map(plan => {
              const fi = getFileIcon(plan);
              const IconComp = fi.icon;
              return (
                <div
                  key={plan.id}
                  onClick={() => openDetail(plan)}
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
                      {plan.floor_id && (
                        <span className="text-[10px] text-slate-400">
                          {getFloorName(plan.floor_id)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400">
                      <span>{formatDate(plan.created_at)}</span>
                      {plan.current_version > 1 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-bold text-[9px]">v{plan.current_version}</span>
                      )}
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
                    {isManager && plan.total_members != null && (
                      <button
                        onClick={(e) => { e.stopPropagation(); openSeenModal(plan); }}
                        className="flex items-center gap-1 mt-1.5 text-[10px] text-slate-400 hover:text-amber-600 transition-colors"
                      >
                        <Users className="w-3 h-3" />
                        {plan.seen_count || 0}/{plan.total_members}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {canManage && (
        <button
          onClick={() => setShowUploadModal(true)}
          className="fixed bottom-6 left-6 z-40 w-14 h-14 bg-amber-500 hover:bg-amber-600 text-white rounded-full shadow-xl flex items-center justify-center transition-colors"
        >
          <Plus className="w-6 h-6" />
        </button>
      )}

      {showUploadModal && canManage && (
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
                <input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.dwg,.dxf" onChange={handleFileSelect} className="hidden" id="plan-file-pick" />
                {uploadFile ? (
                  <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                    <FileText className="w-5 h-5 text-amber-600 shrink-0" />
                    <span className="text-sm text-amber-800 truncate flex-1">{uploadFile.name}</span>
                    <button onClick={() => { setUploadFile(null); if (fileInputRef.current) fileInputRef.current.value = ''; }} className="text-amber-400 hover:text-amber-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label htmlFor="plan-file-pick" className="flex items-center justify-center gap-2 w-full py-4 border-2 border-dashed border-slate-300 rounded-xl text-sm text-slate-500 cursor-pointer hover:border-amber-400 hover:text-amber-600 transition-colors">
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

              {allFloors.length > 0 && (
                <div>
                  <label className="text-xs font-medium text-slate-600 mb-1.5 block">קומה</label>
                  <select
                    value={uploadFloorId}
                    onChange={e => { setUploadFloorId(e.target.value); setUploadUnitId(''); }}
                    className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-amber-300"
                  >
                    <option value="">לא נבחרה</option>
                    {allFloors.map(f => (
                      <option key={f.id} value={f.id}>
                        {f.building_name ? `${f.building_name} - ` : ''}{f.name || `קומה ${f.number || ''}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {uploadFloorId && uploadFloorUnits.length > 0 && (
                <div>
                  <label className="text-xs font-medium text-slate-600 mb-1.5 block">דירה</label>
                  <select
                    value={uploadUnitId}
                    onChange={e => setUploadUnitId(e.target.value)}
                    className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-amber-300"
                  >
                    <option value="">לא נבחרה</option>
                    {uploadFloorUnits.map(u => (
                      <option key={u.id} value={u.id}>{u.name || u.number || u.id}</option>
                    ))}
                  </select>
                </div>
              )}

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
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => { setDetailPlan(null); setEditingDetail(false); }} />
          <div className="relative z-10 w-full sm:max-w-lg sm:mx-4 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl max-h-[92vh] flex flex-col" dir="rtl">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-800 truncate">{detailPlan.name || detailPlan.original_filename}</h3>
              <button onClick={() => { setDetailPlan(null); setEditingDetail(false); }} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors flex-shrink-0">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="overflow-y-auto p-4 space-y-4">
              {(detailPlan.file_type || '').startsWith('image/') ? (
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

              {editingDetail ? (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-medium text-slate-600 mb-1 block">שם</label>
                    <input type="text" value={editFields.name} onChange={e => setEditFields(p => ({ ...p, name: e.target.value }))} className="w-full h-9 px-3 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600 mb-1 block">תחום</label>
                    <select value={editFields.discipline} onChange={e => setEditFields(p => ({ ...p, discipline: e.target.value }))} className="w-full h-9 px-3 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300">
                      {allDisciplinesList.map(d => (
                        <option key={d.key} value={d.key}>{getDisciplineLabel(d.key)}</option>
                      ))}
                    </select>
                  </div>
                  {allFloors.length > 0 && (
                    <div>
                      <label className="text-xs font-medium text-slate-600 mb-1 block">קומה</label>
                      <select value={editFields.floor_id} onChange={e => setEditFields(p => ({ ...p, floor_id: e.target.value, unit_id: '' }))} className="w-full h-9 px-3 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300">
                        <option value="">לא נבחרה</option>
                        {allFloors.map(f => (
                          <option key={f.id} value={f.id}>{f.building_name ? `${f.building_name} - ` : ''}{f.name || `קומה ${f.number || ''}`}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  {editFields.floor_id && editFloorUnits.length > 0 && (
                    <div>
                      <label className="text-xs font-medium text-slate-600 mb-1 block">דירה</label>
                      <select value={editFields.unit_id} onChange={e => setEditFields(p => ({ ...p, unit_id: e.target.value }))} className="w-full h-9 px-3 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300">
                        <option value="">לא נבחרה</option>
                        {editFloorUnits.map(u => (
                          <option key={u.id} value={u.id}>{u.name || u.number || u.id}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  <div>
                    <label className="text-xs font-medium text-slate-600 mb-1 block">סוג</label>
                    <div className="flex gap-2">
                      <button onClick={() => setEditFields(p => ({ ...p, plan_type: 'standard' }))} className={`flex-1 py-1.5 rounded-lg text-xs font-medium border ${editFields.plan_type === 'standard' ? 'bg-amber-500 text-white border-amber-500' : 'bg-white text-slate-600 border-slate-200'}`}>כללית</button>
                      <button onClick={() => setEditFields(p => ({ ...p, plan_type: 'tenant_changes' }))} className={`flex-1 py-1.5 rounded-lg text-xs font-medium border ${editFields.plan_type === 'tenant_changes' ? 'bg-violet-500 text-white border-violet-500' : 'bg-white text-slate-600 border-slate-200'}`}>שינויי דיירים</button>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600 mb-1 block">הערה</label>
                    <input type="text" value={editFields.note} onChange={e => setEditFields(p => ({ ...p, note: e.target.value.slice(0, 200) }))} maxLength={200} className="w-full h-9 px-3 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300" />
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button onClick={saveEdit} disabled={saving} className="flex-1 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                      שמור
                    </button>
                    <button onClick={() => setEditingDetail(false)} className="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50">
                      ביטול
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">{getDisciplineLabel(detailPlan.discipline)}</span>
                      {detailPlan.plan_type === 'tenant_changes' && (
                        <span className="text-[11px] px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">שינויי דיירים</span>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {detailPlan.floor_id && (
                        <div className="bg-slate-50 rounded-lg px-3 py-2">
                          <span className="text-slate-400">קומה</span>
                          <p className="font-medium text-slate-700 mt-0.5">{getFloorName(detailPlan.floor_id)}</p>
                        </div>
                      )}
                      {detailPlan.unit_id && (
                        <div className="bg-slate-50 rounded-lg px-3 py-2">
                          <span className="text-slate-400">דירה</span>
                          <p className="font-medium text-slate-700 mt-0.5">{getUnitName(detailPlan.unit_id)}</p>
                        </div>
                      )}
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
                    <a
                      href={detailPlan.file_url}
                      download
                      onClick={() => handleViewPlan(detailPlan)}
                      className="flex-1 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold transition-colors flex items-center justify-center gap-2"
                    >
                      <Download className="w-4 h-4" />
                      הורד
                    </a>
                    {canManage && (
                      <>
                        <button onClick={() => setShowVersionUpload(v => !v)} className="px-3 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-bold transition-colors flex items-center gap-1.5">
                          <Upload className="w-3.5 h-3.5" />
                          גרסה חדשה
                        </button>
                        <button onClick={startEdit} className="px-3 py-2.5 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50 flex items-center gap-1.5">
                          <Edit3 className="w-3.5 h-3.5" />
                          ערוך
                        </button>
                        <button onClick={() => { setDetailPlan(null); openArchiveModal(detailPlan); }} className="px-3 py-2.5 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50 flex items-center gap-1.5">
                          <Archive className="w-3.5 h-3.5" />
                          ארכיון
                        </button>
                      </>
                    )}
                  </div>

                  {showVersionUpload && canManage && (
                    <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-3 space-y-2">
                      <p className="text-xs font-bold text-indigo-800">העלה גרסה חדשה</p>
                      <input ref={versionFileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.dwg,.dxf" onChange={e => { if (e.target.files?.[0]) setVersionFile(e.target.files[0]); }} className="hidden" id="version-file-pick" />
                      {versionFile ? (
                        <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-indigo-100">
                          <FileText className="w-4 h-4 text-indigo-500 shrink-0" />
                          <span className="text-xs text-indigo-800 truncate flex-1">{versionFile.name}</span>
                          <span className="text-[10px] text-slate-400">{formatFileSize(versionFile.size)}</span>
                          <button onClick={() => { setVersionFile(null); if (versionFileRef.current) versionFileRef.current.value = ''; }} className="text-slate-400 hover:text-slate-600">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <label htmlFor="version-file-pick" className="flex items-center justify-center gap-2 w-full py-3 border-2 border-dashed border-indigo-300 rounded-lg text-xs text-indigo-500 cursor-pointer hover:border-indigo-400 transition-colors">
                          <Upload className="w-4 h-4" />
                          בחר קובץ
                        </label>
                      )}
                      <input
                        type="text"
                        value={versionNote}
                        onChange={e => setVersionNote(e.target.value.slice(0, 200))}
                        placeholder="מה השתנה? (אופציונלי)"
                        maxLength={200}
                        className="w-full h-8 px-3 text-xs bg-white border border-indigo-100 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-300"
                      />
                      <button
                        onClick={handleVersionUpload}
                        disabled={uploadingVersion || !versionFile}
                        className="w-full py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg text-xs font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        {uploadingVersion ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                        {uploadingVersion ? 'מעלה...' : 'העלה גרסה'}
                      </button>
                    </div>
                  )}

                  <div className="border-t border-slate-100 pt-3">
                    <p className="text-xs font-bold text-slate-700 mb-2 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5" />
                      היסטוריית גרסאות
                    </p>
                    {versionHistoryLoading ? (
                      <div className="flex justify-center py-3">
                        <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                      </div>
                    ) : versionHistory.length === 0 ? (
                      <p className="text-[11px] text-slate-400 text-center py-2">אין היסטוריית גרסאות</p>
                    ) : (
                      <div className="space-y-1.5">
                        {versionHistory.map((v, idx) => {
                          const isCurrent = idx === 0;
                          return (
                            <div key={v.version} className={`flex items-center gap-2 rounded-lg px-3 py-2 ${isCurrent ? 'bg-indigo-50 border border-indigo-200' : 'bg-slate-50'}`}>
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${isCurrent ? 'bg-indigo-500 text-white' : 'bg-slate-200 text-slate-600'}`}>v{v.version}</span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
                                  <span>{formatDate(v.uploaded_at)}</span>
                                  <span>—</span>
                                  <span className="truncate">{v.uploaded_by_name || ''}</span>
                                  {isCurrent && <span className="text-indigo-600 font-bold">(נוכחי)</span>}
                                </div>
                                {v.note && <p className="text-[10px] text-slate-400 mt-0.5 truncate">{v.note}</p>}
                              </div>
                              {!isCurrent && v.file_url && (
                                <a href={v.file_url} download className="p-1.5 hover:bg-slate-200 rounded-lg transition-colors shrink-0" title="הורד גרסה זו">
                                  <Download className="w-3.5 h-3.5 text-slate-500" />
                                </a>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {showArchiveModal && archiveTarget && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => { setShowArchiveModal(false); setArchiveTarget(null); }} />
          <div className="relative z-10 w-full sm:max-w-sm sm:mx-4 p-5 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl" dir="rtl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">להעביר לארכיון?</h3>
              <button onClick={() => { setShowArchiveModal(false); setArchiveTarget(null); }} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-3">
              <div className="bg-slate-50 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500">תוכנית</p>
                <p className="text-sm font-medium text-slate-800 mt-0.5 break-words line-clamp-2">{archiveTarget.name || archiveTarget.original_filename}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">הערה (אופציונלי)</label>
                <input type="text" value={archiveNote} onChange={e => setArchiveNote(e.target.value)} placeholder="למה מועברת לארכיון?" className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-amber-300" autoFocus onKeyDown={e => { if (e.key === 'Enter') handleArchive(); }} />
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5 text-xs text-amber-700">
                התוכנית תועבר לארכיון ותוכל לשחזר אותה בכל עת מדף הארכיון.
              </div>
              <div className="flex gap-2 pt-1">
                <button onClick={handleArchive} disabled={!!archivingPlanId} className="flex-1 py-2.5 bg-slate-700 hover:bg-slate-800 text-white rounded-xl text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
                  {archivingPlanId ? <Loader2 className="w-4 h-4 animate-spin" /> : <Archive className="w-4 h-4" />}
                  העבר לארכיון
                </button>
                <button onClick={() => { setShowArchiveModal(false); setArchiveTarget(null); }} className="px-4 py-2.5 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors">
                  ביטול
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showReplaceModal && replaceTarget && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => { setShowReplaceModal(false); setReplaceTarget(null); }} />
          <div className="relative z-10 w-full sm:max-w-sm sm:mx-4 p-5 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl" dir="rtl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">החלפת תוכנית</h3>
              <button onClick={() => { setShowReplaceModal(false); setReplaceTarget(null); }} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-3">
              <div className="bg-slate-50 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500">תוכנית נוכחית</p>
                <p className="text-sm font-medium text-slate-800 mt-0.5 break-words line-clamp-2">{replaceTarget.name || replaceTarget.original_filename}</p>
                <p className="text-[10px] text-slate-400 mt-1">{getDisciplineLabel(replaceTarget.discipline)} · {formatDate(replaceTarget.created_at)}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">הערה לגרסה החדשה (אופציונלי)</label>
                <input type="text" value={replaceNote} onChange={e => setReplaceNote(e.target.value)} placeholder="מה השתנה בגרסה החדשה?" className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-300" autoFocus />
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-xl px-3 py-2.5 text-xs text-blue-700">
                הקובץ הנוכחי יועבר לארכיון והקובץ החדש יהפוך לתוכנית הפעילה.
              </div>
              <div>
                <input ref={replaceFileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.dwg,.dxf" onChange={handleReplace} className="hidden" id="project-plan-replace" />
                <label htmlFor="project-plan-replace" className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-bold cursor-pointer transition-colors ${replacing ? 'bg-slate-200 text-slate-400 cursor-wait' : 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg'}`}>
                  {replacing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  {replacing ? 'מחליף...' : 'בחר קובץ חדש והחלף'}
                </label>
                <p className="text-[10px] text-slate-400 text-center mt-2">PDF, JPG, PNG, DWG, DXF</p>
              </div>
              <button onClick={() => { setShowReplaceModal(false); setReplaceTarget(null); }} className="w-full py-2.5 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors">
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}

      {showBulkModal && canManage && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => { if (!bulkUploading) closeBulkModal(); }} />
          <div className="relative z-10 w-full sm:max-w-lg sm:mx-4 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl max-h-[92vh] flex flex-col" dir="rtl">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-800">העלאה מרובה</h3>
              <button onClick={() => { if (!bulkUploading) closeBulkModal(); }} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="overflow-y-auto p-4 space-y-4">
              {bulkResults ? (
                <div className="space-y-3">
                  <div className={`rounded-xl p-4 text-center ${bulkResults.failed > 0 ? 'bg-amber-50 border border-amber-200' : 'bg-green-50 border border-green-200'}`}>
                    <p className="text-sm font-bold text-slate-800">הועלו {bulkResults.succeeded} מתוך {bulkResults.total}</p>
                    {bulkResults.failed > 0 && <p className="text-xs text-amber-700 mt-1">{bulkResults.failed} קבצים נכשלו — ניתן לנסות שוב</p>}
                  </div>
                  {bulkFiles.filter(f => f.status === 'error').length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-bold text-red-600">קבצים שנכשלו:</p>
                      {bulkFiles.filter(f => f.status === 'error').map(bf => (
                        <div key={bf.id} className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                          <FileText className="w-4 h-4 text-red-400 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-red-800 truncate">{bf.file.name}</p>
                            <p className="text-[10px] text-red-500">{bf.error}</p>
                          </div>
                          <button onClick={() => retryBulkFile(bf)} className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-[10px] rounded-lg font-bold transition-colors">
                            נסה שוב
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <button onClick={closeBulkModal} className="w-full py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-bold transition-colors">
                    סגור
                  </button>
                </div>
              ) : (
                <>
                  <div>
                    <label className="text-xs font-medium text-slate-600 mb-1.5 block">תחום ברירת מחדל</label>
                    <select
                      value={bulkDefaultDiscipline}
                      onChange={e => {
                        const val = e.target.value;
                        setBulkDefaultDiscipline(val);
                        setBulkFiles(prev => prev.map(f => f.discipline ? f : { ...f, discipline: val }));
                      }}
                      className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-300"
                    >
                      <option value="">בחר תחום</option>
                      {allDisciplinesList.map(d => (
                        <option key={d.key} value={d.key}>{getDisciplineLabel(d.key)}</option>
                      ))}
                    </select>
                  </div>

                  <div
                    onDragOver={e => e.preventDefault()}
                    onDrop={e => { e.preventDefault(); handleBulkFileSelect(e.dataTransfer.files); }}
                  >
                    <input ref={bulkFileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.dwg,.dxf" multiple onChange={e => { handleBulkFileSelect(e.target.files); e.target.value = ''; }} className="hidden" id="bulk-file-pick" />
                    <label htmlFor="bulk-file-pick" className="flex flex-col items-center justify-center gap-2 w-full py-6 border-2 border-dashed border-indigo-300 rounded-xl text-sm text-indigo-500 cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/50 transition-colors">
                      <Upload className="w-6 h-6" />
                      <span className="text-xs">גרור קבצים לכאן או לחץ לבחירה</span>
                      <span className="text-[10px] text-slate-400">PDF, JPG, PNG, DWG, DXF · עד 20 קבצים · עד 50MB לקובץ</span>
                    </label>
                  </div>

                  {bulkFiles.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-bold text-slate-600">{bulkFiles.length} קבצים נבחרו</p>
                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {bulkFiles.map(bf => (
                          <div key={bf.id} className={`rounded-xl border p-3 space-y-2 ${bf.status === 'error' ? 'bg-red-50 border-red-200' : bf.status === 'done' ? 'bg-green-50 border-green-200' : bf.status === 'uploading' ? 'bg-indigo-50 border-indigo-200' : 'bg-white border-slate-200'}`}>
                            <div className="flex items-center gap-2">
                              <FileText className={`w-4 h-4 shrink-0 ${bf.status === 'error' ? 'text-red-400' : bf.status === 'done' ? 'text-green-500' : 'text-slate-400'}`} />
                              <span className="text-xs text-slate-700 truncate flex-1">{bf.file.name}</span>
                              <span className="text-[10px] text-slate-400">{formatFileSize(bf.file.size)}</span>
                              {bf.status === 'pending' && (
                                <button onClick={() => removeBulkFile(bf.id)} className="text-slate-400 hover:text-red-500">
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              )}
                              {bf.status === 'done' && <CheckCircle className="w-4 h-4 text-green-500" />}
                              {bf.status === 'uploading' && <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />}
                            </div>
                            {bf.status === 'error' && bf.error && (
                              <p className="text-[10px] text-red-500">{bf.error}</p>
                            )}
                            {bf.status === 'uploading' && (
                              <div className="w-full bg-indigo-100 rounded-full h-1.5">
                                <div className="bg-indigo-500 h-1.5 rounded-full transition-all" style={{ width: `${bf.progress}%` }} />
                              </div>
                            )}
                            {bf.status === 'pending' && (
                              <div className="flex gap-2">
                                <select
                                  value={bf.discipline}
                                  onChange={e => updateBulkFile(bf.id, { discipline: e.target.value })}
                                  className={`flex-1 h-8 px-2 text-[11px] bg-white border rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-300 ${!bf.discipline ? 'border-red-300' : 'border-slate-200'}`}
                                >
                                  <option value="">תחום *</option>
                                  {allDisciplinesList.map(d => (
                                    <option key={d.key} value={d.key}>{getDisciplineLabel(d.key)}</option>
                                  ))}
                                </select>
                                {allFloors.length > 0 && (
                                  <select
                                    value={bf.floor_id}
                                    onChange={e => updateBulkFile(bf.id, { floor_id: e.target.value })}
                                    className="flex-1 h-8 px-2 text-[11px] bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-300"
                                  >
                                    <option value="">קומה</option>
                                    {allFloors.map(f => (
                                      <option key={f.id} value={f.id}>{f.building_name ? `${f.building_name} - ` : ''}{f.name || `קומה ${f.number || ''}`}</option>
                                    ))}
                                  </select>
                                )}
                                <select
                                  value={bf.plan_type}
                                  onChange={e => updateBulkFile(bf.id, { plan_type: e.target.value })}
                                  className="h-8 px-2 text-[11px] bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-300"
                                >
                                  <option value="standard">כללית</option>
                                  <option value="tenant_changes">שינויי דיירים</option>
                                </select>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {bulkFiles.length > 0 && (
                    <button
                      onClick={handleBulkUpload}
                      disabled={bulkUploading || bulkFiles.filter(f => f.status === 'pending' && f.discipline).length === 0}
                      className="w-full py-3 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {bulkUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      {bulkUploading ? 'מעלה...' : `העלה ${bulkFiles.filter(f => f.status === 'pending' && f.discipline).length} קבצים`}
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {showSeenModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowSeenModal(false)} />
          <div className="relative z-10 w-full sm:max-w-md sm:mx-4 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-slate-800">סטטוס צפייה</h3>
                <p className="text-[10px] text-slate-400 truncate mt-0.5">{seenModalPlanName}</p>
              </div>
              <button onClick={() => setShowSeenModal(false)} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors flex-shrink-0">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="overflow-y-auto p-4 space-y-4">
              {seenModalLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                </div>
              ) : seenModalData ? (
                <>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <Users className="w-3.5 h-3.5" />
                    <span>נצפה על ידי {seenModalData.seen_count}/{seenModalData.total_members}</span>
                  </div>
                  {seenModalData.seen?.length > 0 && (
                    <div>
                      <p className="text-[11px] font-bold text-green-700 mb-2 flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5" />צפו ({seenModalData.seen.length})</p>
                      <div className="space-y-1.5">
                        {seenModalData.seen.map(u => (
                          <div key={u.user_id} className="flex items-center justify-between bg-green-50 rounded-lg px-3 py-2">
                            <span className="text-xs font-medium text-slate-700">{u.name || 'ללא שם'}</span>
                            <span className="text-[10px] text-slate-400">{formatSeenDate(u.last_seen_at)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {seenModalData.unseen?.length > 0 && (
                    <div>
                      <p className="text-[11px] font-bold text-slate-500 mb-2 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />טרם צפו ({seenModalData.unseen.length})</p>
                      <div className="space-y-1.5">
                        {seenModalData.unseen.map(u => (
                          <div key={u.user_id} className="flex items-center bg-slate-50 rounded-lg px-3 py-2">
                            <span className="text-xs font-medium text-slate-500">{u.name || 'ללא שם'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectPlansPage;
