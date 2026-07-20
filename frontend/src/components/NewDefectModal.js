import React, { useState, useEffect, useCallback, useRef, useMemo, Suspense } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { projectService, buildingService, floorService, projectCompanyService, BACKEND_URL, classifyDefectPhoto } from '../services/api';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import {
  X, Upload, ChevronDown, Camera, Loader2, Building2, Layers, DoorOpen, AlertTriangle, RefreshCw, Check, ImagePlus, Plus, Pencil
} from 'lucide-react';

const PhotoAnnotation = React.lazy(() => import('./PhotoAnnotation'));
import { Button } from './ui/button';
import { tCategory } from '../i18n';
import { compressImage } from '../utils/imageCompress';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Sheet, SheetPortal, SheetOverlay, SheetClose, SheetTitle, SheetDescription } from './ui/sheet';
import * as SheetPrimitive from '@radix-ui/react-dialog';
import { SelectField } from './BottomSheetSelect';
import QuickAddCompanyModal from './QuickAddCompanyModal';
import DocumentScannerButton from './DocumentScannerButton';
import { FEATURES } from '../config/features';
import { saveDefectDraft, loadDefectDraft, clearDefectDraft } from '../utils/defectDraft';
import { stashDraftImages, takeDraftImages, clearDraftImages } from '../utils/defectDraftImages';
import { enqueueDefectCreate } from '../services/offlineOutbox';

// A load failure that is EXPECTED while offline (so we must NOT toast a red
// error): the device is offline, OR the rejection has no HTTP response (network
// failure / transport). A real server error online (has reason.response) still
// toasts. Mirrors api.js's transient classification.
const _isOfflineFail = (reason) =>
  (typeof navigator !== 'undefined' && navigator.onLine === false) || !reason?.response;

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && typeof data === 'object') {
    const arrKey = Object.keys(data).find(k => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
  }
  return [];
};

const CATEGORIES = [
  'electrical', 'plumbing', 'hvac', 'painting', 'flooring',
  'carpentry', 'masonry', 'windows', 'doors', 'general',
  'bathroom_cabinets', 'finishes', 'structural', 'aluminum',
  'metalwork', 'glazing', 'carpentry_kitchen'
].map(key => ({ value: key, label: tCategory(key) }));

const PRIORITIES = [
  { value: 'low', label: 'נמוך', color: 'text-slate-500' },
  { value: 'medium', label: 'בינוני', color: 'text-blue-600' },
  { value: 'high', label: 'גבוה', color: 'text-amber-600' },
  { value: 'critical', label: 'קריטי', color: 'text-red-600' },
];

const NewDefectModal = ({ isOpen, onClose, onSuccess, prefillData }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const hasPrefill = !!(prefillData && prefillData.project_id && prefillData.unit_id);

  const isOpenRef = useRef(isOpen);
  isOpenRef.current = isOpen;

  useEffect(() => {
    if (!isOpen) return;
    window.history.pushState({ modal: 'new-defect' }, '');
    const handlePopState = () => {
      if (isOpenRef.current) {
        window.history.pushState({ modal: 'new-defect' }, '');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = () => {
      if (document.visibilityState === 'visible' && isOpenRef.current) {
        window.history.pushState({ modal: 'new-defect' }, '');
      }
    };
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, [isOpen]);

  const [projectId, setProjectId] = useState('');
  const [buildingId, setBuildingId] = useState('');
  const [floorId, setFloorId] = useState('');
  const [unitId, setUnitId] = useState('');
  const [category, setCategory] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('medium');
  const [isSafety, setIsSafety] = useState(false);
  const [companyId, setCompanyId] = useState('');
  const [assigneeId, setAssigneeId] = useState('');

  const [images, setImages] = useState([]);
  // BATCH defect-photo-first E3b: per-user opt-in layout preference. Only
  // meaningful while FEATURES.DEFECT_PHOTO_FIRST is on; default = classic.
  const [photoFirst, setPhotoFirst] = useState(() => {
    if (!FEATURES.DEFECT_PHOTO_FIRST) return false;
    try { return window.localStorage.getItem('brikops_defect_photo_first_v1') === '1'; } catch { return false; }
  });
  const applyPhotoFirst = (on) => {
    setPhotoFirst(on);
    try { window.localStorage.setItem('brikops_defect_photo_first_v1', on ? '1' : '0'); } catch {}
  };
  const effectivePhotoFirst = FEATURES.DEFECT_PHOTO_FIRST && photoFirst;
  // BATCH AI Phase 2c E3a: AI suggestion only in photo-first + behind the flag.
  const effectiveAiSuggest = FEATURES.DEFECT_AI_SUGGEST && effectivePhotoFirst;
  // BATCH AI Phase 2c E3b: AI suggestion state (all reset on open/close + submit).
  const [aiState, setAiState] = useState('idle');          // 'idle'|'analyzing'|'done'
  const [aiSuggestion, setAiSuggestion] = useState(null);  // classify response or null
  const [aiSurface, setAiSurface] = useState(null);        // 'floor'|'wall'|null
  const [aiAutoFilled, setAiAutoFilled] = useState(false); // "✓ מולא אוטומטית" marker
  const aiTriedRef = useRef(false);                        // at most once per modal session
  const [annotatingIndex, setAnnotatingIndex] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);
  const [createdTaskId, setCreatedTaskId] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [projects, setProjects] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [floors, setFloors] = useState([]);
  const [units, setUnits] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [contractors, setContractors] = useState([]);
  const [projectMembers, setProjectMembers] = useState([]);
  const [autoSelectedCompany, setAutoSelectedCompany] = useState(false);
  const [autoSelectedAssignee, setAutoSelectedAssignee] = useState(false);
  const [showQuickAddCompany, setShowQuickAddCompany] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitStep, setSubmitStep] = useState(null);
  const [errors, setErrors] = useState({});

  const [loading, setLoading] = useState({});
  const [loadError, setLoadError] = useState({});

  const loadProjects = useCallback(() => {
    setLoading(l => ({ ...l, projects: true }));
    setLoadError(e => ({ ...e, projects: false }));
    projectService.list()
      .then(data => { setProjects(normalizeList(data)); })
      .catch(err => { console.error('Failed to load projects:', err); toast.error('שגיאה בטעינת פרויקטים'); setLoadError(e => ({ ...e, projects: true })); })
      .finally(() => setLoading(l => ({ ...l, projects: false })));
  }, []);

  const loadCompanies = useCallback((pid) => {
    if (!pid) return;
    setLoading(l => ({ ...l, companies: true }));
    setLoadError(e => ({ ...e, companies: false }));
    // allSettled (NOT Promise.all): a memberships failure (memberships is NOT
    // cached — personal PII) must NEVER blank the now-cacheable companies list.
    // compRes.value / memRes.value are the unwrapped data arrays the services
    // resolve to (response.data), matching the old destructured-.then shape.
    Promise.allSettled([
      projectCompanyService.list(pid),
      projectService.getMemberships(pid),
    ])
      .then(([compRes, memRes]) => {
        if (compRes.status === 'fulfilled') setCompanies(normalizeList(compRes.value));
        if (memRes.status === 'fulfilled') setProjectMembers(normalizeList(memRes.value));
        // Only the COMPANIES load failing is user-visible. A memberships-only
        // miss → companies still show, assignee picker just empty, NO toast.
        if (compRes.status === 'rejected') {
          console.error('Failed to load companies:', compRes.reason);
          setLoadError(e => ({ ...e, companies: true }));
          if (!_isOfflineFail(compRes.reason)) toast.error('שגיאה בטעינת חברות');
        }
      })
      .finally(() => setLoading(l => ({ ...l, companies: false })));
  }, []);

  useEffect(() => {
    if (isOpen) {
      setCreatedTaskId(null);
      setUploadError(null);
      if (hasPrefill) {
        setProjectId(prefillData.project_id);
        setBuildingId(prefillData.building_id);
        setFloorId(prefillData.floor_id);
        setUnitId(prefillData.unit_id);
        loadCompanies(prefillData.project_id);
      }
      if (!hasPrefill) {
        loadProjects();
      }
    }
  }, [isOpen, hasPrefill, prefillData, loadProjects, loadCompanies]);

  // Restore in-progress draft from the "+ הוסף קבלן" → add contractor → return flow.
  // Gated on FEATURES.DEFECT_DRAFT_PRESERVATION; off = no-op (matches pre-batch).
  // Runs after the prefill effect above so the unit-match guard sees the right values.
  useEffect(() => {
    if (!FEATURES.DEFECT_DRAFT_PRESERVATION) return;
    if (!isOpen) return;
    const draft = loadDefectDraft();
    if (!draft) return;
    // Project-scope guard: if the draft was saved for a different project than
    // the one this modal is currently opened for, bail out. Covers the case
    // where NewDefectModal is opened from ProjectTasksPage (no unit_id in
    // prefillData, so the unit-match guard below can't fire).
    if (draft.projectId && prefillData?.project_id && draft.projectId !== prefillData.project_id) {
      return;
    }
    if (hasPrefill && draft.unitId && prefillData?.unit_id && draft.unitId !== prefillData.unit_id) {
      return;
    }
    if (draft.category) setCategory(draft.category);
    if (draft.title) setTitle(draft.title);
    if (draft.description) setDescription(draft.description);
    if (draft.priority) setPriority(draft.priority);
    if (typeof draft.is_safety === 'boolean') setIsSafety(draft.is_safety);
    if (draft.companyId) setCompanyId(draft.companyId);
    if (draft.assigneeId) setAssigneeId(draft.assigneeId);
    clearDefectDraft();
    // BATCH defect-photo-first E3e: restore stashed images (photo-first round-trip).
    // Classic mode / hard reload → nothing stashed → the exact original toast fires.
    const restoredImgs = takeDraftImages();
    if (restoredImgs && restoredImgs.length) {
      setImages(restoredImgs);
      toast.info('הטיוטה והתמונות שוחזרו.');
    } else {
      toast.info('הטיוטה שוחזרה. יש לצרף תמונות מחדש.');
    }
  }, [isOpen, hasPrefill, prefillData]);

  const loadBuildings = useCallback((pid) => {
    if (!pid) return;
    setLoading(l => ({ ...l, buildings: true }));
    setLoadError(e => ({ ...e, buildings: false }));
    projectService.getBuildings(pid)
      .then(data => { setBuildings(normalizeList(data)); })
      .catch(err => { console.error('Failed to load buildings:', err); if (!_isOfflineFail(err)) toast.error('שגיאה בטעינת בניינים'); setLoadError(e => ({ ...e, buildings: true })); })
      .finally(() => setLoading(l => ({ ...l, buildings: false })));
  }, []);

  const loadFloors = useCallback((bid) => {
    if (!bid) return;
    setLoading(l => ({ ...l, floors: true }));
    setLoadError(e => ({ ...e, floors: false }));
    buildingService.getFloors(bid)
      .then(data => { setFloors(normalizeList(data)); })
      .catch(err => { console.error('Failed to load floors:', err); if (!_isOfflineFail(err)) toast.error('שגיאה בטעינת קומות'); setLoadError(e => ({ ...e, floors: true })); })
      .finally(() => setLoading(l => ({ ...l, floors: false })));
  }, []);

  const loadUnits = useCallback((fid) => {
    if (!fid) return;
    setLoading(l => ({ ...l, units: true }));
    setLoadError(e => ({ ...e, units: false }));
    floorService.getUnits(fid)
      .then(data => { setUnits(normalizeList(data)); })
      .catch(err => { console.error('Failed to load units:', err); if (!_isOfflineFail(err)) toast.error('שגיאה בטעינת דירות'); setLoadError(e => ({ ...e, units: true })); })
      .finally(() => setLoading(l => ({ ...l, units: false })));
  }, []);

  const handleProjectChange = useCallback((v) => {
    setProjectId(v);
    setBuildingId('');
    setFloorId('');
    setUnitId('');
    setCompanyId('');
    setAssigneeId('');
    setAutoSelectedCompany(false);
    setAutoSelectedAssignee(false);
    setBuildings([]);
    setFloors([]);
    setUnits([]);
    setCompanies([]);
    setContractors([]);
    setProjectMembers([]);
    if (v) {
      loadBuildings(v);
      loadCompanies(v);
    }
  }, [loadBuildings, loadCompanies]);

  const handleBuildingChange = useCallback((v) => {
    setBuildingId(v);
    setFloorId('');
    setUnitId('');
    setFloors([]);
    setUnits([]);
    if (v) {
      loadFloors(v);
    }
  }, [loadFloors]);

  const handleFloorChange = useCallback((v) => {
    setFloorId(v);
    setUnitId('');
    setUnits([]);
    if (v) {
      loadUnits(v);
    }
  }, [loadUnits]);

  const handleCategoryChange = useCallback((v) => {
    setCategory(v);
    setCompanyId('');
    setAssigneeId('');
    setAutoSelectedCompany(false);
    setAutoSelectedAssignee(false);
  }, []);

  // BATCH AI Phase 2c: refs so the []-dep handleImageAdd callback reads CURRENT
  // values (category / photos emptiness / gating) instead of stale closures.
  const categoryRef = useRef(category);
  categoryRef.current = category;
  const aiSuggestEnabledRef = useRef(effectiveAiSuggest);
  aiSuggestEnabledRef.current = effectiveAiSuggest;
  const photosEmptyRef = useRef(true);
  photosEmptyRef.current = images.length === 0 && !pendingFile;
  const handleCategoryChangeRef = useRef(handleCategoryChange);
  handleCategoryChangeRef.current = handleCategoryChange;

  // BATCH AI Phase 2c E3b: reset the AI state on every modal open/close.
  // aiSessionIdRef invalidates any in-flight classify response from a previous
  // modal session so a late response can never leak into a fresh session.
  const aiSessionIdRef = useRef(0);
  useEffect(() => {
    aiSessionIdRef.current += 1;
    aiTriedRef.current = false;
    setAiState('idle');
    setAiSuggestion(null);
    setAiSurface(null);
    setAiAutoFilled(false);
  }, [isOpen]);

  // BATCH AI Phase 2c E3c: fire-once classify on the FIRST photo when the
  // category is still empty. Best-effort — ANY failure is silent (no toast,
  // no block); the form behaves exactly as photo-first-without-AI.
  const triggerAiClassify = useCallback((file) => {
    if (!aiSuggestEnabledRef.current) return;    // never in classic / flag off
    if (aiTriedRef.current) return;              // at most once per modal session
    if (!photosEmptyRef.current) return;         // only empty→first photo
    if (categoryRef.current !== '') return;      // never override a chosen category
    aiTriedRef.current = true;
    const sessionId = aiSessionIdRef.current;   // ignore responses from a stale session
    setAiState('analyzing');
    classifyDefectPhoto(file)
      .then((data) => {
        if (aiSessionIdRef.current !== sessionId) return;   // modal closed/reopened meanwhile
        setAiState('done');
        setAiSuggestion(data);
        if (categoryRef.current === '' && data && data.suggested_category) {
          handleCategoryChangeRef.current(data.suggested_category);
          setAiAutoFilled(true);
        }
        if (data && data.needs_surface_choice) setAiSurface('floor');
      })
      .catch(() => {
        if (aiSessionIdRef.current !== sessionId) return;
        setAiState('idle');
        setAiSuggestion(null);
      });
  }, []);

  // BATCH AI Phase 2c E3d: chip / toggle / manual dropdown all flow through the
  // SAME handleCategoryChange (Zahi amendment) so company/assignee reset and the
  // contractor filter behave exactly like a manual pick.
  const handleAiChipPick = useCallback((value) => {
    setAiAutoFilled(false);
    handleCategoryChange(value);
  }, [handleCategoryChange]);
  const handleAiSurfacePick = useCallback((surface) => {
    setAiSurface(surface);
    setAiAutoFilled(false);
    handleCategoryChange(surface === 'wall' ? 'masonry' : 'flooring');
  }, [handleCategoryChange]);
  const handleCategoryChangeUser = useCallback((v) => {
    setAiAutoFilled(false);
    handleCategoryChange(v);
  }, [handleCategoryChange]);

  const handleCompanyChange = useCallback((v) => {
    setCompanyId(v);
    setAssigneeId('');
    setAutoSelectedCompany(false);
    setAutoSelectedAssignee(false);
  }, []);

  useEffect(() => {
    if (companyId && projectMembers.length > 0) {
      const matched = projectMembers.filter(m =>
        m.role === 'contractor' &&
        (m.company_id === companyId || m.user_company_id === companyId)
      );
      if (matched.length > 0) {
        setContractors(matched);
        if (matched.length === 1) {
          setAssigneeId(matched[0].user_id || matched[0].id);
          setAutoSelectedAssignee(true);
        }
      } else {
        setContractors([]);
        setAssigneeId('');
      }
    } else if (!companyId) {
      setContractors([]);
    }
  }, [companyId, projectMembers, companies]);

  const categoryMatchedCompanies = useMemo(() => {
    if (!category) return [];
    return companies.filter(c =>
      c.trade === category ||
      (c.specialties && c.specialties.includes(category))
    );
  }, [category, companies]);

  const filteredCompanies = category ? categoryMatchedCompanies : companies;

  useEffect(() => {
    if (!category) return;
    if (!companyId && categoryMatchedCompanies.length === 1) {
      setCompanyId(categoryMatchedCompanies[0].id);
      setAssigneeId('');
      setAutoSelectedCompany(true);
      setAutoSelectedAssignee(false);
    }
  }, [category, categoryMatchedCompanies, companyId]);

  const galleryInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  const processingImageRef = useRef(false);
  const handleImageAdd = useCallback(async (e) => {
    if (processingImageRef.current) return;
    processingImageRef.current = true;
    try {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;
      const compressed = await Promise.all(files.map(f => compressImage(f)));

      if (compressed.length === 1) {
        let stableFile = compressed[0];
        if (!stableFile._fromCompress) {
          const bytes = await stableFile.arrayBuffer();
          stableFile = new File([bytes], compressed[0].name, { type: compressed[0].type });
        }
        triggerAiClassify(stableFile); // BATCH AI Phase 2c E3c (no-op unless gated on)
        setPendingFile(stableFile);
      } else {
        const newImages = await Promise.all(compressed.map(async (file) => {
          let stable = file;
          if (!file._fromCompress) {
            const bytes = await file.arrayBuffer();
            stable = new File([bytes], file.name, { type: file.type });
          }
          return {
            file: stable,
            preview: URL.createObjectURL(stable),
            name: stable.name,
          };
        }));
        if (newImages.length > 0) triggerAiClassify(newImages[0].file); // BATCH AI Phase 2c E3c
        setImages(prev => [...prev, ...newImages]);
        toast.info(`${compressed.length} תמונות נוספו. ניתן לסמן כל תמונה בנפרד`);
      }
    } catch (err) {
      if (err?.code === 'UNSUPPORTED_FORMAT') {
        toast.error('פורמט תמונה לא נתמך. נסה לצלם מהמצלמה');
        console.error('[COMPRESS] HEIC/unsupported:', err.original);
      } else {
        console.error('[defect:image] failed to process image:', err);
        toast.error('שגיאה בעיבוד התמונה. נסה שוב.');
      }
    } finally {
      processingImageRef.current = false;
      if (e.target) e.target.value = '';
    }
  }, [triggerAiClassify]);

  const removeImage = useCallback((index) => {
    setImages(prev => {
      URL.revokeObjectURL(prev[index].preview);
      if (prev[index].originalPreview) URL.revokeObjectURL(prev[index].originalPreview);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const handleAnnotationSave = useCallback((annotatedFile, hasAnnotations) => {
    const idx = annotatingIndex;
    if (idx === null) return;
    if (!hasAnnotations || !annotatedFile) {
      setAnnotatingIndex(null);
      return;
    }
    setImages(prev => {
      const updated = [...prev];
      const original = updated[idx];
      if (original.isAnnotated && original.preview) {
        URL.revokeObjectURL(original.preview);
      }
      const annotatedPreview = URL.createObjectURL(annotatedFile);
      updated[idx] = {
        file: annotatedFile,
        preview: annotatedPreview,
        name: 'annotated_' + (original.name || 'photo.jpg'),
        originalFile: original.originalFile || original.file,
        originalPreview: original.originalPreview || original.preview,
        isAnnotated: true,
      };
      return updated;
    });
    setAnnotatingIndex(null);
  }, [annotatingIndex]);

  const handlePendingAnnotationSave = useCallback((annotatedFile, hasAnnotations) => {
    if (!pendingFile) return;
    if (hasAnnotations && annotatedFile) {
      const annotatedPreview = URL.createObjectURL(annotatedFile);
      const originalPreview = URL.createObjectURL(pendingFile);
      setImages(prev => [...prev, {
        file: annotatedFile,
        preview: annotatedPreview,
        name: 'annotated_' + (pendingFile.name || 'photo.jpg'),
        originalFile: pendingFile,
        originalPreview,
        isAnnotated: true,
      }]);
    } else {
      setImages(prev => [...prev, {
        file: pendingFile,
        preview: URL.createObjectURL(pendingFile),
        name: pendingFile.name,
      }]);
    }
    setPendingFile(null);
  }, [pendingFile]);

  const validate = useCallback(() => {
    const errs = {};
    if (!projectId) errs.project_id = 'חובה';
    if (!buildingId) errs.building_id = 'חובה';
    if (!floorId) errs.floor_id = 'חובה';
    if (!unitId) errs.unit_id = 'חובה';
    if (!category) errs.category = 'חובה';
    if (!title.trim()) errs.title = 'חובה';
    if (images.length === 0) errs.images = 'נדרשת לפחות תמונה אחת';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [projectId, buildingId, floorId, unitId, category, title, images]);

  const doUploadAndAssign = async (taskId) => {
    setUploadError(null);

    const { taskService } = await import('../services/api');
    const imagesToUpload = [...images];

    const uploadList = [];
    for (const img of imagesToUpload) {
      uploadList.push({ file: img.file, name: img.name });
    }

    if (uploadList.length > 0) {
      setSubmitStep('uploading');
      const results = [];
      for (let i = 0; i < uploadList.length; i++) {
        if (i > 0) await new Promise(r => setTimeout(r, 500));
        try {
          const val = await taskService.uploadAttachment(taskId, uploadList[i].file);
          results.push({ status: 'fulfilled', value: val });
        } catch (reason) {
          results.push({ status: 'rejected', reason });
        }
      }
      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failedResults = results.filter(r => r.status === 'rejected');

      if (succeeded === 0) {
        const firstErr = failedResults[0]?.reason;
        const status = firstErr?.response?.status;
        const errCode = firstErr?.code;
        const isTimeout = errCode === 'ECONNABORTED' || firstErr?.message?.includes('timeout');
        const isNetwork = !firstErr?.response && firstErr?.message?.includes('Network');
        const serverMsg = firstErr?.response?.data?.detail;
        const shortServer = typeof serverMsg === 'string' ? serverMsg.slice(0, 80) : (typeof serverMsg === 'object' && serverMsg?.message ? serverMsg.message.slice(0, 80) : '');
        const fileSizeMB = imagesToUpload[0]?.file?.size ? (imagesToUpload[0].file.size / (1024 * 1024)).toFixed(1) : '?';

        const uploadUrl = `${BACKEND_URL}/api/tasks/${taskId}/attachments`;
        console.error('[upload:diagnostic]', {
          status, code: errCode, message: firstErr?.message,
          responseBody: firstErr?.response?.data,
          fileSizeKB: imagesToUpload[0]?.file?.size ? Math.round(imagesToUpload[0].file.size / 1024) : null,
          url: uploadUrl, online: navigator.onLine,
        });

        let diagMsg;
        if (isTimeout) {
          diagMsg = `העלאת תמונה נכשלה: timeout בזמן העלאה (${fileSizeMB}MB)`;
        } else if (isNetwork) {
          let reachable = false;
          try {
            const hc = await fetch(`${BACKEND_URL}/api/health`, { method: 'GET', mode: 'cors' });
            reachable = hc.ok;
          } catch (_) {}
          if (reachable) {
            diagMsg = `העלאת תמונה נכשלה: שגיאת רשת — השרת זמין אך ההעלאה נחסמה (${fileSizeMB}MB)`;
          } else {
            diagMsg = `העלאת תמונה נכשלה: שגיאת רשת — השרת לא זמין (${fileSizeMB}MB, online=${navigator.onLine})`;
          }
          console.error('[upload:network-diag]', { reachable, online: navigator.onLine, url: uploadUrl });
        } else if (status) {
          diagMsg = `העלאת תמונה נכשלה: HTTP ${status}${shortServer ? ' — ' + shortServer : ''} (${fileSizeMB}MB)`;
        } else {
          diagMsg = `העלאת תמונה נכשלה: ${firstErr?.message || 'שגיאה לא ידועה'} (${fileSizeMB}MB)`;
        }
        setUploadError(diagMsg + ' — ניתן לנסות שוב.');
        return;
      }
      if (failedResults.length > 0) {
        console.warn(`Upload: ${failedResults.length}/${imagesToUpload.length} failed, ${succeeded} succeeded — proceeding to assign`);
        toast.warning(`${failedResults.length} תמונות לא הועלו, אך ממשיך בשיוך הקבלן.`);
      }
    }

    const isContactFallback = assigneeId === '__company_contact__';
    const effectiveAssigneeId = isContactFallback ? null : assigneeId;
    if (!companyId) {
      toast.success('הליקוי נוצר בהצלחה!');
      onSuccess?.(taskId);
      return;
    }

    setSubmitStep('assigning');

    let assignResult;
    try {
      assignResult = await Promise.race([
        taskService.assign(taskId, { company_id: companyId, assignee_id: effectiveAssigneeId || null }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('שגיאת זמן בשלב: שיוך קבלן — נסה שוב')), 30000)),
      ]);
    } catch (err) {
      console.error('ASSIGN FAILED', err);
      const detail = err.response?.data?.detail;
      const errorCode = typeof detail === 'object' ? detail?.error_code : null;
      if (errorCode === 'NO_TASK_IMAGE') {
        setUploadError(detail.message || 'יש לצרף לפחות תמונה אחת לפני שליחה לקבלן');
      } else {
        const msg = typeof detail === 'string' ? detail : (typeof detail === 'object' && detail?.message ? detail.message : err.message || 'שיוך לקבלן נכשל');
        toast.error(msg);
      }
      return;
    }

    toast.success('הליקוי נוצר בהצלחה!');

    const ns = assignResult?.notification_status;
    if (ns) {
      const phone = ns.to_phone_masked || '';
      const msgId = ns.provider_message_id || '';
      const pStatus = ns.provider_status || '';
      const ch = ns.channel === 'sms' ? 'SMS' : 'WhatsApp';
      switch (pStatus) {
        case 'sent':
        case 'queued':
          toast.info(`נשלחה הודעה ב-${ch} ל-${phone} (בהמתנה למסירה)`);
          break;
        case 'delivered':
          toast.success(`הודעה נמסרה ל-${phone}`);
          break;
        case 'failed':
          toast.error(`נכשל לשלוח ל-${phone}: ${ns.error || ns.reason || 'שגיאה לא ידועה'}`);
          break;
        case 'skipped_dry_run':
          toast.warning('הודעה לא נשלחה (מצב בדיקה)');
          break;
        case 'duplicate':
          toast.info('הודעה כבר נשלחה לקבלן זה');
          break;
        default:
          if (ns.sent && msgId) {
            toast.info(`נשלחה הודעה ב-${ch} ל-${phone} (בהמתנה למסירה)`);
          } else {
            toast.warning(`לא ניתן לשלוח הודעה לקבלן: ${ns.error || ns.reason || 'סיבה לא ידועה'}`);
          }
      }
    }

    clearDraftImages(); // BATCH defect-photo-first E3e: terminal outcome — drop any stale stash
    images.forEach(img => URL.revokeObjectURL(img.preview));
    setProjectId('');
    setBuildingId('');
    setFloorId('');
    setUnitId('');
    setCategory('');
    setTitle('');
    setDescription('');
    setPriority('medium');
    setIsSafety(false);
    setCompanyId('');
    setAssigneeId('');
    setAutoSelectedCompany(false);
    setAutoSelectedAssignee(false);
    setImages([]);
    setPendingFile(null);
    setAnnotatingIndex(null);
    setErrors({});
    setCreatedTaskId(null);
    setUploadError(null);
    // BATCH AI Phase 2c E3b: reset AI state on successful submit.
    aiTriedRef.current = false;
    setAiState('idle');
    setAiSuggestion(null);
    setAiSurface(null);
    setAiAutoFilled(false);
    onSuccess(taskId);
  };

  const handleSubmit = async () => {
    if (createdTaskId && uploadError) {
      setSubmitting(true);
      setSubmitStep('uploading');
      try {
        await doUploadAndAssign(createdTaskId);
      } catch (err) {
        console.error('[submit:retry:unhandled]', err);
        toast.error('שגיאה לא צפויה. נסה שוב.');
      } finally {
        setSubmitting(false);
        setSubmitStep(null);
      }
      return;
    }

    if (images.length > 0) {
      const staleFiles = [];
      for (const img of images) {
        try {
          const slice = img.file.slice(0, 1);
          await slice.arrayBuffer();
        } catch {
          staleFiles.push(img);
        }
      }
      if (staleFiles.length > 0) {
        toast.error(staleFiles.length === 1
          ? 'התמונה אבדה, נא לצרף מחדש'
          : `${staleFiles.length} תמונות אבדו, נא לצרף מחדש`);
        setImages(prev => prev.filter(img => !staleFiles.includes(img)));
        return;
      }
    }

    if (!validate()) return;
    setSubmitting(true);
    setSubmitStep('creating');
    setUploadError(null);

    try {
      const taskData = {
        project_id: projectId,
        building_id: buildingId,
        floor_id: floorId,
        unit_id: unitId,
        category: category,
        title: title,
        description: description,
        priority: priority,
        is_safety: isSafety,
        ...(companyId ? { company_id: companyId } : {}),
      };

      const { taskService } = await import('../services/api');

      // BATCH 5 — offline defect-create. Gated on BOTH flags, so while
      // OFFLINE_DEFECT_CREATE is dormant this whole block is dead code and the
      // online path below is byte-for-byte unchanged in prod. The task id is
      // minted CLIENT-side (valid UUID) so queued photos reference the FINAL id
      // and the idempotent backend accepts the same id on sync (no temp-id remap,
      // no dup on retry). payload carries company_id ONLY — NEVER assignee_id
      // (create rejects assignee_id with 400 ⇒ would wedge the queue forever);
      // the contractor assign is replayed separately from `assign`.
      const mintId = () => {
        if (window.crypto?.randomUUID) return window.crypto.randomUUID();
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
          const r = (Math.random() * 16) | 0;
          const v = c === 'x' ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        });
      };
      const saveOffline = async (clientId) => {
        const isContactFallback = assigneeId === '__company_contact__';
        const effectiveAssigneeId = isContactFallback ? null : assigneeId;
        await enqueueDefectCreate({
          key: clientId,
          payload: { ...taskData, id: clientId },
          photos: images.map(img => ({ name: img.name, blob: img.file })),
          assign: { company_id: companyId || null, assignee_id: effectiveAssigneeId || null },
          unitId,
        });
        clearDefectDraft();
        clearDraftImages(); // BATCH defect-photo-first E3e: terminal outcome — drop any stale stash
        toast.success('הליקוי נשמר במכשיר — יישלח כשתחזור הרשת');
        images.forEach(img => { try { URL.revokeObjectURL(img.preview); } catch (_) {} });
        onSuccess?.(clientId);
      };

      // Proactive: known-offline ⇒ skip the network entirely and queue now.
      if (FEATURES.OFFLINE_MODE && FEATURES.OFFLINE_DEFECT_CREATE && navigator.onLine === false) {
        await saveOffline(mintId());
        return;
      }

      let task;
      try {
        task = await Promise.race([
          taskService.create(taskData),
          new Promise((_, reject) => setTimeout(() => reject(new Error('שגיאת זמן בשלב: יצירת ליקוי — נסה שוב')), 30000)),
        ]);
        setCreatedTaskId(task.id);
      } catch (err) {
        console.error('Step 1 FAILED: create task', err);
        // Reactive: a TRUE network failure (no err.response) while online-flagged
        // ⇒ queue instead of erroring. A real server 4xx/5xx (err.response set)
        // falls through to today's toast — bad data must NOT be silently queued.
        if (FEATURES.OFFLINE_MODE && FEATURES.OFFLINE_DEFECT_CREATE && !err.response) {
          await saveOffline(mintId());
          return;
        }
        const detail = err.response?.data?.detail;
        const msg = typeof detail === 'string' ? detail : (typeof detail === 'object' && detail?.message ? detail.message : err.message || 'שגיאה ביצירת הליקוי');
        toast.error(msg);
        return;
      }

      await doUploadAndAssign(task.id);
    } catch (err) {
      console.error('[submit:unhandled]', err);
      if (createdTaskId) {
        toast.error('הליקוי נשמר כטיוטה — ניתן להשלים מדף הליקוי');
      } else {
        toast.error('שגיאה לא צפויה. נסה שוב.');
      }
    } finally {
      setSubmitting(false);
      setSubmitStep(null);
    }
  };

  const handleClose = () => {
    if (createdTaskId && uploadError) {
      toast.info('הליקוי נשמר כטיוטה — ניתן להשלים מדף הליקוי');
    }
    clearDraftImages(); // BATCH defect-photo-first E3e: modal close/cancel — drop any stale stash
    onClose();
  };

  if (!isOpen) return null;

  // BATCH defect-photo-first E3c: the photos section, extracted VERBATIM from its
  // original bottom position. Rendered in exactly ONE place depending on mode:
  // classic → bottom (as today), photo-first → top (after location, before category).
  const photosBlock = (
          <div className="space-y-2" dir="rtl">
            <label className="block text-sm font-medium text-slate-700">
              תמונות * <span className="text-xs text-slate-400">(לפחות 1)</span>
            </label>
            <input ref={galleryInputRef} type="file" accept="image/*" multiple onChange={handleImageAdd} className="hidden" />
            <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleImageAdd} className="hidden" />
            {images.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {images.map((img, i) => (
                  <div key={i} className="relative w-20 h-20 rounded-lg overflow-hidden border border-slate-200 group">
                    <img src={img.preview} alt="" className="w-full h-full object-cover" />
                    <button
                      onClick={() => removeImage(i)}
                      className="absolute top-0.5 right-0.5 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
                    >
                      <X className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => setAnnotatingIndex(i)}
                      className={`absolute bottom-0.5 right-0.5 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs transition-opacity ${img.isAnnotated ? 'bg-green-500' : 'bg-amber-500 hover:bg-amber-600'}`}
                      title={img.isAnnotated ? 'ערוך סימון' : 'סמן על התמונה'}
                    >
                      <Pencil className="w-3 h-3" />
                    </button>
                    {img.isAnnotated && (
                      <div className="absolute top-0.5 left-0.5 bg-green-500 text-white rounded-full w-4 h-4 flex items-center justify-center">
                        <Check className="w-2.5 h-2.5" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 rounded-lg border-2 border-dashed transition-colors cursor-pointer hover:bg-amber-50 active:bg-amber-100 ${errors.images ? 'border-red-400' : 'border-amber-300'}`}
              >
                <Camera className="w-6 h-6 text-amber-500" />
                <span className="text-xs font-medium text-amber-700">צלם תמונה</span>
              </button>
              <button
                type="button"
                onClick={() => galleryInputRef.current?.click()}
                className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 rounded-lg border-2 border-dashed transition-colors cursor-pointer hover:bg-slate-50 active:bg-slate-100 ${errors.images ? 'border-red-400' : 'border-slate-300'}`}
              >
                <ImagePlus className="w-6 h-6 text-slate-400" />
                <span className="text-xs font-medium text-slate-600">בחר מגלריה</span>
              </button>
              {/* BATCH H.2a (2026-05-13) — native document scanner. Hidden on web. */}
              <DocumentScannerButton
                onScan={(files) => {
                  const newImages = files.map(f => ({
                    file: f,
                    preview: URL.createObjectURL(f),
                    name: f.name,
                    originalFile: f,
                  }));
                  setImages(prev => [...prev, ...newImages]);
                }}
                className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 rounded-lg border-2 border-dashed transition-colors cursor-pointer hover:bg-emerald-50 active:bg-emerald-100 ${errors.images ? 'border-red-400' : 'border-emerald-300'}`}
              />
            </div>
            {errors.images && <p className="text-xs text-red-500">{errors.images}</p>}
          </div>
  );

  return (<>
    <DialogPrimitive.Root modal={false} open={true} onOpenChange={(open) => {
      if (!open && (pendingFile || annotatingIndex !== null)) return;
      if (!open) handleClose();
    }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 outline-none"
          onPointerDownOutside={(e) => e.preventDefault()}
          onInteractOutside={(e) => e.preventDefault()}
        >
          <DialogPrimitive.Title className="sr-only">{hasPrefill ? `ליקוי חדש — ${formatUnitLabel(prefillData.unit_label)}` : 'ליקוי חדש'}</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">טופס יצירת ליקוי חדש</DialogPrimitive.Description>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg my-8 overflow-hidden">
        <div className="bg-amber-500 text-white px-6 py-4 flex items-center justify-between">
          <DialogPrimitive.Close asChild>
            <button className="p-1 hover:bg-amber-600 rounded-lg transition-colors">
              <X className="w-5 h-5" />
            </button>
          </DialogPrimitive.Close>
          <h2 className="text-lg font-bold">{hasPrefill ? `ליקוי חדש — ${formatUnitLabel(prefillData.unit_label)}` : 'ליקוי חדש'}</h2>
        </div>

        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {/* BATCH defect-photo-first E3d: opt-in mode toggle. Renders ONLY when the
              flag is on — flag off = zero visual change from today. */}
          {FEATURES.DEFECT_PHOTO_FIRST && (
            <div className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2">
              <span className="text-xs text-slate-500">מצב מילוי</span>
              <div className="inline-flex bg-slate-100 rounded-lg p-0.5">
                <button type="button" onClick={() => applyPhotoFirst(false)}
                  className={`px-3 py-1 text-xs rounded-md ${!photoFirst ? 'bg-amber-500 text-white font-semibold' : 'text-slate-500'}`}>קלאסי</button>
                <button type="button" onClick={() => applyPhotoFirst(true)}
                  className={`px-3 py-1 text-xs rounded-md ${photoFirst ? 'bg-amber-500 text-white font-semibold' : 'text-slate-500'}`}>📸 תמונה קודם</button>
              </div>
            </div>
          )}
          {hasPrefill ? (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
              <h3 className="text-sm font-semibold text-amber-800 flex items-center gap-2 justify-end">
                <span>מיקום (נעול)</span>
                <Building2 className="w-4 h-4" />
              </h3>
              <div className="grid grid-cols-2 gap-2 text-sm" dir="rtl">
                <div className="flex items-center gap-1.5 text-slate-700">
                  <Building2 className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{prefillData.project_name}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <Building2 className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{prefillData.building_name}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <Layers className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{prefillData.floor_name}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <DoorOpen className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{formatUnitLabel(prefillData.unit_label)}</span>
                </div>
              </div>
            </div>
          ) : (
          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 flex items-center gap-2 justify-end">
              <span>מיקום</span>
              <Building2 className="w-4 h-4" />
            </h3>
            <SelectField
              label="פרויקט *"
              value={projectId}
              onChange={handleProjectChange}
              options={projects.map(p => ({ value: p.id, label: `${p.name} (${p.code})` }))}
              error={errors.project_id}
              placeholder="בחר פרויקט"
              isLoading={loading.projects}
              hasError={loadError.projects}
              onRetry={loadProjects}
              emptyMessage="אין פרויקטים זמינים"
            />
            <SelectField
              label="בניין *"
              value={buildingId}
              onChange={handleBuildingChange}
              options={buildings.map(b => ({ value: b.id, label: b.name }))}
              error={errors.building_id}
              icon={Building2}
              placeholder="בחר בניין"
              isLoading={loading.buildings}
              disabled={!projectId}
              hasError={loadError.buildings}
              onRetry={() => projectId && loadBuildings(projectId)}
              emptyMessage="אין בניינים לפרויקט זה"
            />
            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="קומה *"
                value={floorId}
                onChange={handleFloorChange}
                options={floors.map(f => ({ value: f.id, label: f.name }))}
                error={errors.floor_id}
                icon={Layers}
                placeholder="בחר קומה"
                isLoading={loading.floors}
                disabled={!buildingId}
                hasError={loadError.floors}
                onRetry={() => buildingId && loadFloors(buildingId)}
                emptyMessage="אין קומות לבניין זה"
              />
              <SelectField
                label="יחידה *"
                value={unitId}
                onChange={v => setUnitId(v)}
                options={units.map(u => ({ value: u.id, label: formatUnitLabel(u.unit_no) }))}
                error={errors.unit_id}
                icon={DoorOpen}
                placeholder="בחר יחידה"
                isLoading={loading.units}
                disabled={!floorId}
                hasError={loadError.units}
                onRetry={() => floorId && loadUnits(floorId)}
                emptyMessage="אין דירות לקומה זו"
              />
            </div>
          </div>
          )}

          {/* BATCH defect-photo-first E3c: photo-first slot — same block, top position. */}
          {effectivePhotoFirst && photosBlock}

          {/* BATCH AI Phase 2c E3d: AI suggestion block — after photos, before category. */}
          {effectiveAiSuggest && aiState === 'analyzing' && (
            <div dir="rtl" className="flex items-center gap-2 text-sm text-indigo-600 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>✨ מזהה קטגוריה…</span>
            </div>
          )}
          {effectiveAiSuggest && aiState === 'done' && aiSuggestion && (
            <div dir="rtl" className="bg-indigo-50 border border-indigo-200 rounded-xl p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-indigo-800">הצעת AI ✨</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${aiSuggestion.low_confidence ? 'bg-slate-200 text-slate-600' : 'bg-indigo-200 text-indigo-800'}`}>
                  {aiSuggestion.low_confidence
                    ? (aiSuggestion.suggested_category === 'general' ? 'לא זוהה' : 'לא בטוח')
                    : `${Math.round((aiSuggestion.confidence || 0) * 100)}% ביטחון`}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => handleAiChipPick(aiSuggestion.suggested_category)}
                  className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${category === aiSuggestion.suggested_category
                    ? 'bg-amber-100 border-amber-400 text-amber-800 font-medium'
                    : 'bg-white border-slate-300 text-slate-700'}`}
                >
                  {tCategory(aiSuggestion.suggested_category)}
                </button>
                {(aiSuggestion.alternatives || []).map(alt => (
                  <button
                    key={alt}
                    type="button"
                    onClick={() => handleAiChipPick(alt)}
                    className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${category === alt
                      ? 'bg-amber-100 border-amber-400 text-amber-800 font-medium'
                      : 'bg-white border-slate-300 text-slate-700'}`}
                  >
                    {tCategory(alt)}
                  </button>
                ))}
              </div>
              {aiSuggestion.needs_surface_choice && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">איפה האריחים?</span>
                  <button
                    type="button"
                    onClick={() => handleAiSurfacePick('floor')}
                    className={`text-xs px-2.5 py-1 rounded-full border ${aiSurface === 'floor' ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-slate-300 text-slate-600'}`}
                  >
                    רצפה
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAiSurfacePick('wall')}
                    className={`text-xs px-2.5 py-1 rounded-full border ${aiSurface === 'wall' ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-slate-300 text-slate-600'}`}
                  >
                    קיר
                  </button>
                </div>
              )}
              <p className="text-xs text-slate-500">אפשר להתעלם מההצעה ולבחור קטגוריה מהרשימה כרגיל.</p>
            </div>
          )}

          <div className="space-y-3">
            {effectiveAiSuggest && aiAutoFilled && (
              <div dir="rtl" className="flex items-center gap-1 text-xs text-green-600">
                <Check className="w-3 h-3" />
                <span>מולא אוטומטית</span>
              </div>
            )}
            <SelectField
              label="קטגוריה *"
              value={category}
              onChange={effectiveAiSuggest ? handleCategoryChangeUser : handleCategoryChange}
              options={CATEGORIES}
              error={errors.category}
              placeholder="בחר קטגוריה"
            />
            <div className="space-y-1" dir="rtl">
              <label className="block text-sm font-medium text-slate-700">פירוט ליקוי *</label>
              <input
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="תאר את הליקוי בקצרה"
                className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${errors.title ? 'border-red-400' : 'border-slate-300'}`}
              />
              {errors.title && <p className="text-xs text-red-500">{errors.title}</p>}
            </div>
            <div className="space-y-1" dir="rtl">
              <label className="block text-sm font-medium text-slate-700">תיאור (אופציונלי)</label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="תאר את הליקוי בפירוט"
                rows={3}
                className="w-full px-3 py-2.5 border rounded-lg text-sm resize-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 border-slate-300"
              />
            </div>
            <SelectField
              label="עדיפות"
              value={priority}
              onChange={v => setPriority(v)}
              options={PRIORITIES}
              icon={AlertTriangle}
              placeholder="בחר עדיפות"
            />
            {/* Batch #469 — safety tag toggle */}
            <div className="flex items-center justify-between py-3 border-t border-slate-100" dir="rtl">
              <div className="flex items-center gap-2">
                <span className="text-orange-500" aria-hidden="true">🛡️</span>
                <label htmlFor="is-safety-toggle" className="text-sm font-medium text-slate-700 cursor-pointer">
                  סמן כליקוי בטיחות
                </label>
              </div>
              <input
                id="is-safety-toggle"
                type="checkbox"
                checked={isSafety}
                onChange={(e) => setIsSafety(e.target.checked)}
                className="w-5 h-5 rounded text-orange-500 focus:ring-orange-500 cursor-pointer"
              />
            </div>
          </div>

          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 text-right">שיוך קבלן</h3>
            <p className="text-[11px] text-slate-400 text-right">ניתן לשייך קבלן מאוחר יותר</p>
            {companies.length === 0 && !loading.companies && loadError.companies ? (
              // Offline miss (no cache yet) — don't imply there are zero companies.
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center space-y-2">
                <p className="text-sm text-amber-800 font-medium">רשימת החברות תיטען כשתחזור הרשת</p>
                <p className="text-xs text-amber-600">אפשר ליצור ליקוי גם ללא שיוך קבלן.</p>
              </div>
            ) : companies.length === 0 && !loading.companies ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center space-y-2">
                <p className="text-sm text-amber-800 font-medium">אין חברות בפרויקט</p>
                <p className="text-xs text-amber-600">כדי להקצות ליקוי לקבלן יש להוסיף חברה.</p>
                <Button
                  onClick={() => setShowQuickAddCompany(true)}
                  className="bg-amber-500 hover:bg-amber-600 text-white text-sm px-4 py-2 rounded-lg"
                  disabled={!projectId}
                >
                  <Plus className="w-4 h-4 ml-1 inline" />
                  הוסף חברה
                </Button>
              </div>
            ) : category && filteredCompanies.length === 0 && !loading.companies ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center space-y-2">
                <p className="text-sm text-amber-800 font-medium">אין חברות המשויכות לתחום {tCategory(category)}</p>
                <p className="text-xs text-amber-600">כדי להקצות ליקוי לקבלן יש להוסיף חברה בתחום המתאים.</p>
                <Button
                  onClick={() => setShowQuickAddCompany(true)}
                  className="bg-amber-500 hover:bg-amber-600 text-white text-sm px-4 py-2 rounded-lg"
                  disabled={!projectId}
                >
                  <Plus className="w-4 h-4 ml-1 inline" />
                  הוסף חברה
                </Button>
              </div>
            ) : (
              <>
                <div className="space-y-1">
                  <SelectField
                    label="חברה"
                    value={companyId}
                    onChange={handleCompanyChange}
                    options={filteredCompanies.map(c => ({ value: c.id, label: c.name }))}
                    error={errors.company_id}
                    placeholder={category ? 'בחר חברה (מסונן לפי קטגוריה)' : 'בחר קטגוריה קודם'}
                    isLoading={loading.companies}
                    disabled={!category}
                  />
                  {autoSelectedCompany && companyId && (
                    <p className="text-[11px] text-blue-500 font-medium">נבחר אוטומטית</p>
                  )}
                  {category && (
                    <button
                      type="button"
                      onClick={() => setShowQuickAddCompany(true)}
                      disabled={!projectId}
                      className="text-xs text-amber-600 hover:text-amber-700 font-medium flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Plus className="w-3 h-3" />
                      הוסף חברה
                    </button>
                  )}
                </div>
                <div className="space-y-1">
                  <SelectField
                    label="קבלן מבצע"
                    value={assigneeId}
                    onChange={v => { setAssigneeId(v); setAutoSelectedAssignee(false); }}
                    options={contractors.map(m => ({ value: m.user_id, label: m.user_name || m.name || 'קבלן' }))}
                    error={errors.assignee_id}
                    placeholder={companyId ? 'בחר קבלן' : 'בחר חברה קודם'}
                    isLoading={loading.contractors}
                    disabled={!companyId}
                  />
                  {autoSelectedAssignee && assigneeId && (
                    <p className="text-[11px] text-blue-500 font-medium">נבחר אוטומטית</p>
                  )}
                  {companyId && !loading.contractors && contractors.length === 0 && (
                    <div className="space-y-1">
                      <p className="text-xs text-amber-700">אין קבלנים משויכים לחברה זו</p>
                      <button
                        type="button"
                        onClick={() => {
                          if (!FEATURES.DEFECT_DRAFT_PRESERVATION) {
                            onClose();
                            if (projectId) navigate(`/projects/${projectId}/control?tab=companies`);
                            return;
                          }
                          if (!projectId) { onClose(); return; }
                          if (effectivePhotoFirst) stashDraftImages(images);
                          saveDefectDraft({
                            projectId,
                            buildingId,
                            floorId,
                            unitId,
                            category,
                            title,
                            description,
                            priority,
                            is_safety: isSafety,
                            companyId,
                            assigneeId,
                            prefillData: prefillData || null,
                            returnUrl: location.pathname,
                          });
                          onClose();
                          const params = new URLSearchParams({
                            tab: 'team',
                            openInvite: '1',
                            returnToDefect: '1',
                          });
                          if (category) params.set('prefillTrade', category);
                          navigate(`/projects/${projectId}/control?${params.toString()}`);
                        }}
                        className="text-xs text-amber-600 hover:text-amber-700 font-medium flex items-center gap-1"
                      >
                        <Plus className="w-3 h-3" />
                        הוסף קבלן
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          {!effectivePhotoFirst && photosBlock}
        </div>

        {uploadError && (
          <div className="border-t border-red-200 bg-red-50 px-6 py-3 flex items-center gap-3" dir="rtl">
            <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700 flex-1">{uploadError}</p>
          </div>
        )}

        <div className="border-t px-6 py-4 flex gap-3" dir="rtl">
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className={`flex-1 font-medium py-2.5 rounded-lg ${uploadError ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-amber-500 hover:bg-amber-600 text-white'}`}
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                {submitStep === 'uploading' ? 'מעלה תמונות...' : submitStep === 'assigning' ? 'משייך קבלן...' : 'יוצר ליקוי...'}
              </span>
            ) : uploadError ? (
              <span className="flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4" />
                נסה שוב להעלות
              </span>
            ) : (
              'צור ליקוי'
            )}
          </Button>
          <Button
            onClick={handleClose}
            variant="outline"
            disabled={submitting}
            className="px-6 py-2.5 rounded-lg"
          >
            ביטול
          </Button>
        </div>
      </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>

    {annotatingIndex !== null && images[annotatingIndex] &&
     (images[annotatingIndex].file || images[annotatingIndex].originalFile) && (
      <Suspense fallback={
        <div className="fixed inset-0 z-[10000] bg-black flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-white animate-spin" />
        </div>
      }>
        <PhotoAnnotation
          // BATCH F.2-polish-1 (2026-05-13) — load the annotated file
          // first when re-editing. User sees their previous drawings
          // as rasterized pixels on the canvas; can add new strokes
          // on top. Old strokes can't be edited individually
          // (rasterized — that's the "Re-editable annotations"
          // backlog batch). originalFile fallback covers the edge
          // case where file is missing (shouldn't happen but defensive).
          // The gate above ALSO guards against both being null —
          // prevents PhotoAnnotation receiving undefined imageFile.
          imageFile={images[annotatingIndex].file || images[annotatingIndex].originalFile}
          onSave={handleAnnotationSave}
          onDiscard={() => setAnnotatingIndex(null)}
        />
      </Suspense>
    )}

    {pendingFile && (
      <Suspense fallback={
        <div className="fixed inset-0 z-[10000] bg-black flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-white animate-spin" />
        </div>
      }>
        <PhotoAnnotation
          imageFile={pendingFile}
          onSave={handlePendingAnnotationSave}
          onDiscard={() => setPendingFile(null)}
        />
      </Suspense>
    )}

    <QuickAddCompanyModal
      open={showQuickAddCompany}
      onOpenChange={setShowQuickAddCompany}
      projectId={projectId}
      categories={CATEGORIES}
      initialTrade={category}
      onSuccess={(newCompany) => {
        setCompanies(prev => [...prev, newCompany]);
        setCompanyId(newCompany.id);
        setShowQuickAddCompany(false);
      }}
    />

  </>
  );
};

export default NewDefectModal;
