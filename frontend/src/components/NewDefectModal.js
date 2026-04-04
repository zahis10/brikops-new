import React, { useState, useEffect, useCallback, useRef, useMemo, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectService, buildingService, floorService, projectCompanyService, BACKEND_URL } from '../services/api';
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

const OptionsOverlay = ({ open, options, value, onChange, onClose, label, emptyMessage }) => {
  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <SheetPortal>
        <SheetOverlay className="fixed inset-0 z-[9999] bg-black/40" />
        <SheetPrimitive.Content
          className="fixed inset-x-0 bottom-0 z-[9999] w-full max-w-lg mx-auto bg-white rounded-t-2xl shadow-2xl max-h-[60vh] flex flex-col outline-none animate-in slide-in-from-bottom duration-200"
          dir="rtl"
        >
          <SheetTitle className="sr-only">{label || 'בחר אפשרות'}</SheetTitle>
          <SheetDescription className="sr-only">בחירת ערך מתוך רשימת אפשרויות</SheetDescription>
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
            <SheetClose asChild>
              <button type="button" className="p-1 text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </SheetClose>
            <h3 className="text-sm font-semibold text-slate-700">{label}</h3>
            <div className="w-6" />
          </div>
          <div className="overflow-y-auto flex-1 overscroll-contain">
            {options.length === 0 ? (
              <div className="px-4 py-8 text-sm text-slate-400 text-center">
                {emptyMessage || 'אין אפשרויות'}
              </div>
            ) : (
              options.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => { onChange(opt.value); onClose(); }}
                  className={`w-full px-4 py-3 text-sm text-right flex items-center justify-between border-b border-slate-100 last:border-0 active:bg-amber-50 ${opt.value === value ? 'bg-amber-50 text-amber-700 font-medium' : 'text-slate-700'}`}
                >
                  {opt.label}
                  {opt.value === value && <Check className="w-4 h-4 text-amber-600 flex-shrink-0" />}
                </button>
              ))
            )}
          </div>
        </SheetPrimitive.Content>
      </SheetPortal>
    </Sheet>
  );
};

const SelectField = ({ label, value, onChange, options, error, icon: Icon, placeholder, isLoading, disabled, hasError, onRetry, emptyMessage }) => {
  const [open, setOpen] = useState(false);
  const selectedLabel = options.find(o => o.value === value)?.label;
  const isDisabled = disabled || isLoading;
  const displayText = isLoading ? 'טוען...' : (disabled ? 'בחר שדה אב קודם' : (selectedLabel || placeholder));

  return (
    <div className="space-y-1" dir="rtl">
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <div className="relative">
        {Icon && <Icon className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none z-10" />}
        <button
          type="button"
          onClick={() => { if (!isDisabled) setOpen(true); }}
          className={`w-full ${Icon ? 'pr-10' : 'pr-3'} pl-8 py-2.5 border rounded-lg bg-white text-sm text-right focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${error ? 'border-red-400' : 'border-slate-300'} ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${!selectedLabel && !isLoading && !disabled ? 'text-slate-400' : 'text-slate-900'}`}
        >
          {displayText}
        </button>
        {isLoading ? (
          <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-amber-500 animate-spin pointer-events-none" />
        ) : (
          <ChevronDown className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        )}
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {!isLoading && !disabled && !hasError && options.length === 0 && emptyMessage && (
        <p className="text-xs text-slate-500 mt-1">{emptyMessage}</p>
      )}
      {hasError && onRetry && (
        <button type="button" onClick={onRetry}
          className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 mt-1">
          <RefreshCw className="w-3 h-3" />
          שגיאה בטעינה - לחץ לנסות שוב
        </button>
      )}
      <OptionsOverlay
        open={open}
        options={options}
        value={value}
        onChange={onChange}
        onClose={() => setOpen(false)}
        label={label}
        emptyMessage={emptyMessage}
      />
    </div>
  );
};

const NewDefectModal = ({ isOpen, onClose, onSuccess, prefillData }) => {
  const navigate = useNavigate();
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
  const [companyId, setCompanyId] = useState('');
  const [assigneeId, setAssigneeId] = useState('');

  const [images, setImages] = useState([]);
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
    Promise.all([
      projectCompanyService.list(pid),
      projectService.getMemberships(pid),
    ])
      .then(([compData, memData]) => {
        setCompanies(normalizeList(compData));
        setProjectMembers(normalizeList(memData));
      })
      .catch(err => { console.error('Failed to load companies/members:', err); toast.error('שגיאה בטעינת חברות'); setLoadError(e => ({ ...e, companies: true })); })
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

  const loadBuildings = useCallback((pid) => {
    if (!pid) return;
    setLoading(l => ({ ...l, buildings: true }));
    setLoadError(e => ({ ...e, buildings: false }));
    projectService.getBuildings(pid)
      .then(data => { setBuildings(normalizeList(data)); })
      .catch(err => { console.error('Failed to load buildings:', err); toast.error('שגיאה בטעינת בניינים'); setLoadError(e => ({ ...e, buildings: true })); })
      .finally(() => setLoading(l => ({ ...l, buildings: false })));
  }, []);

  const loadFloors = useCallback((bid) => {
    if (!bid) return;
    setLoading(l => ({ ...l, floors: true }));
    setLoadError(e => ({ ...e, floors: false }));
    buildingService.getFloors(bid)
      .then(data => { setFloors(normalizeList(data)); })
      .catch(err => { console.error('Failed to load floors:', err); toast.error('שגיאה בטעינת קומות'); setLoadError(e => ({ ...e, floors: true })); })
      .finally(() => setLoading(l => ({ ...l, floors: false })));
  }, []);

  const loadUnits = useCallback((fid) => {
    if (!fid) return;
    setLoading(l => ({ ...l, units: true }));
    setLoadError(e => ({ ...e, units: false }));
    floorService.getUnits(fid)
      .then(data => { setUnits(normalizeList(data)); })
      .catch(err => { console.error('Failed to load units:', err); toast.error('שגיאה בטעינת דירות'); setLoadError(e => ({ ...e, units: true })); })
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
  }, []);

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

    images.forEach(img => URL.revokeObjectURL(img.preview));
    setProjectId('');
    setBuildingId('');
    setFloorId('');
    setUnitId('');
    setCategory('');
    setTitle('');
    setDescription('');
    setPriority('medium');
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
        ...(companyId ? { company_id: companyId } : {}),
      };

      const { taskService } = await import('../services/api');

      let task;
      try {
        task = await Promise.race([
          taskService.create(taskData),
          new Promise((_, reject) => setTimeout(() => reject(new Error('שגיאת זמן בשלב: יצירת ליקוי — נסה שוב')), 30000)),
        ]);
        setCreatedTaskId(task.id);
      } catch (err) {
        console.error('Step 1 FAILED: create task', err);
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
    onClose();
  };

  if (!isOpen) return null;

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

          <div className="space-y-3">
            <SelectField
              label="קטגוריה *"
              value={category}
              onChange={handleCategoryChange}
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
          </div>

          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 text-right">שיוך קבלן</h3>
            <p className="text-[11px] text-slate-400 text-right">ניתן לשייך קבלן מאוחר יותר</p>
            {companies.length === 0 && !loading.companies ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center space-y-2">
                <p className="text-sm text-amber-800 font-medium">אין חברות בפרויקט</p>
                <p className="text-xs text-amber-600">כדי להקצות ליקוי לקבלן יש להוסיף חברה.</p>
                <Button
                  onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
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
                  onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
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
                      onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
                      className="text-xs text-amber-600 hover:text-amber-700 font-medium flex items-center gap-1"
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
                        onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
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
            </div>
            {errors.images && <p className="text-xs text-red-500">{errors.images}</p>}
          </div>
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

    {annotatingIndex !== null && images[annotatingIndex] && (
      <Suspense fallback={
        <div className="fixed inset-0 z-[10000] bg-black flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-white animate-spin" />
        </div>
      }>
        <PhotoAnnotation
          imageFile={images[annotatingIndex].originalFile || images[annotatingIndex].file}
          onSave={handleAnnotationSave}
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
        />
      </Suspense>
    )}

  </>
  );
};

export default NewDefectModal;
