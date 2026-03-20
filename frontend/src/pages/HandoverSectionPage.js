import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { handoverService, taskService } from '../services/api';
import { toast } from 'sonner';
import { t } from '../i18n';
import { compressImage } from '../utils/imageCompress';
import {
  ArrowRight, ArrowLeft, Loader2, CheckCircle2, AlertTriangle, CircleDot,
  MinusCircle, Circle, Bug, Camera, ImagePlus, ChevronLeft, ChevronRight,
  CheckCheck, RotateCcw, X, Info, Trash2
} from 'lucide-react';

const STATUS_BADGE_CONFIG = {
  ok: { label: '✓ תקין', bg: 'bg-[#dcfce7]', text: 'text-green-700', border: 'border-green-300' },
  defective: { label: '✕ לא תקין', bg: 'bg-[#fee2e2]', text: 'text-red-700', border: 'border-red-300' },
  partial: { label: '◐ חלקי', bg: 'bg-[#fef3c7]', text: 'text-amber-700', border: 'border-amber-300' },
  not_relevant: { label: '— לא רלוונטי', bg: 'bg-[#f1f5f9]', text: 'text-slate-600', border: 'border-slate-300' },
  not_checked: { label: 'ממתין', bg: 'bg-slate-100', text: 'text-slate-500', border: 'border-slate-200' },
};

const STATUS_OPTIONS = [
  { value: 'ok', label: 'תקין', icon: CheckCircle2, color: 'bg-green-100 text-green-700 border-green-300', activeColor: 'bg-green-500 text-white border-green-500', flash: 'bg-green-400' },
  { value: 'defective', label: 'לא תקין', icon: AlertTriangle, color: 'bg-red-100 text-red-700 border-red-300', activeColor: 'bg-red-500 text-white border-red-500', flash: 'bg-red-400' },
  { value: 'partial', label: 'חלקי', icon: CircleDot, color: 'bg-amber-100 text-amber-700 border-amber-300', activeColor: 'bg-amber-500 text-white border-amber-500', flash: 'bg-amber-400' },
  { value: 'not_relevant', label: 'לא רלוונטי', icon: MinusCircle, color: 'bg-slate-100 text-slate-600 border-slate-300', activeColor: 'bg-slate-500 text-white border-slate-500', flash: 'bg-slate-400' },
];

const SEVERITY_OPTIONS = [
  { value: 'critical', label: 'קריטי', color: 'bg-red-100 text-red-700 border-red-300', activeColor: 'bg-red-500 text-white border-red-500' },
  { value: 'normal', label: 'רגיל', color: 'bg-amber-100 text-amber-700 border-amber-300', activeColor: 'bg-amber-500 text-white border-amber-500' },
  { value: 'cosmetic', label: 'קוסמטי', color: 'bg-green-100 text-green-700 border-green-300', activeColor: 'bg-green-500 text-white border-green-500' },
];

const SKIP_REASONS = [
  'לא ניתן לצלם — חושך',
  'לא ניתן לצלם — אזור לא נגיש',
];

const LS_ACTIVE_ITEM = 'handover_active_item';
const LS_PROTOCOL_ID = 'handover_protocol_id';
const LS_SECTION_ID = 'handover_section_id';

const HandoverSectionPage = () => {
  const { projectId, unitId, protocolId, sectionId } = useParams();
  const navigate = useNavigate();

  const [protocol, setProtocol] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeItemId, setActiveItemId] = useState(null);
  const [activeTrade, setActiveTrade] = useState(null);

  const [status, setStatus] = useState('not_checked');
  const [notes, setNotes] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [skipPhotoReason, setSkipPhotoReason] = useState('');
  const [showSkipInput, setShowSkipInput] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});
  const [failedPhotoIndexes, setFailedPhotoIndexes] = useState(new Set());
  const [savedDefectId, setSavedDefectId] = useState(null);
  const [existingPhotos, setExistingPhotos] = useState([]);
  const [loadingExisting, setLoadingExisting] = useState(false);
  const [flashStatus, setFlashStatus] = useState(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [showBatchConfirm, setShowBatchConfirm] = useState(null);
  const [showUnsavedConfirm, setShowUnsavedConfirm] = useState(false);
  const [isNarrow, setIsNarrow] = useState(window.innerWidth < 400);

  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const sheetContentRef = useRef(null);
  const originalItemRef = useRef(null);
  const sectionCompletionShown = useRef(new Set());
  const completionToastId = useRef(null);

  useEffect(() => {
    const onResize = () => setIsNarrow(window.innerWidth < 400);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const loadProtocol = useCallback(async () => {
    try {
      setLoading(true);
      const data = await handoverService.getProtocol(projectId, protocolId);
      setProtocol(data);
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'loadError'));
    } finally {
      setLoading(false);
    }
  }, [projectId, protocolId]);

  useEffect(() => { loadProtocol(); }, [loadProtocol]);

  const section = protocol?.sections?.find(s => s.section_id === sectionId);
  const isSigned = protocol?.locked === true;
  const items = useMemo(() => section?.items || [], [section]);
  const checkedCount = items.filter(i => i.status && i.status !== 'not_checked').length;
  const totalCount = items.length;
  const uncheckedCount = totalCount - checkedCount;
  const progressPct = totalCount > 0 ? (checkedCount / totalCount) * 100 : 0;

  const uncheckedItems = useMemo(() => items.filter(i => !i.status || i.status === 'not_checked'), [items]);
  const resettableItems = useMemo(() => items.filter(i => i.status && i.status !== 'not_checked' && !i.defect_id), [items]);
  const defectProtectedCount = useMemo(() => items.filter(i => i.status && i.status !== 'not_checked' && !!i.defect_id).length, [items]);
  const hasDefectsInSection = useMemo(() => items.some(i => !!i.defect_id), [items]);

  const trades = useMemo(() => {
    const tradeSet = new Set();
    items.forEach(i => { if (i.trade) tradeSet.add(i.trade); });
    return Array.from(tradeSet);
  }, [items]);

  const filteredItems = activeTrade ? items.filter(i => i.trade === activeTrade) : items;

  const activeItem = activeItemId ? items.find(i => i.item_id === activeItemId) : null;
  const activeIndex = activeItem ? items.findIndex(i => i.item_id === activeItemId) : -1;

  useEffect(() => {
    const savedItem = localStorage.getItem(LS_ACTIVE_ITEM);
    const savedProtocol = localStorage.getItem(LS_PROTOCOL_ID);
    const savedSection = localStorage.getItem(LS_SECTION_ID);
    if (savedItem && savedProtocol === protocolId && savedSection === sectionId) {
      setActiveItemId(savedItem);
      localStorage.removeItem(LS_ACTIVE_ITEM);
      localStorage.removeItem(LS_PROTOCOL_ID);
      localStorage.removeItem(LS_SECTION_ID);
    }
  }, [protocolId, sectionId]);

  useEffect(() => {
    if (activeItemId) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [activeItemId]);

  const resetForm = useCallback((itemData) => {
    setStatus(itemData?.status || 'not_checked');
    setNotes(itemData?.notes || '');
    setDescription(itemData?.description || '');
    setSeverity(itemData?.severity || null);
    setPhotos([]);
    setSkipPhotoReason(itemData?.skip_photo_reason || '');
    setShowSkipInput(false);
    setErrors({});
    setFailedPhotoIndexes(new Set());
    setSavedDefectId(null);
    setExistingPhotos([]);
    setLoadingExisting(false);
    setFlashStatus(null);
    originalItemRef.current = {
      status: itemData?.status || 'not_checked',
      description: itemData?.description || '',
      severity: itemData?.severity || null,
      notes: itemData?.notes || '',
    };
  }, []);

  useEffect(() => {
    if (activeItem) {
      resetForm(activeItem);
      if (activeItem.defect_id) {
        setLoadingExisting(true);
        taskService.getUpdates(activeItem.defect_id)
          .then(updates => {
            const imgs = (updates || []).filter(u => {
              if (u.update_type !== 'attachment') return false;
              const ct = (u.content_type || '').toLowerCase();
              const fn = (u.file_name || u.content || '').toLowerCase();
              if (fn.endsWith('.bin') || fn.endsWith('.txt')) return false;
              if (ct && !ct.startsWith('image/')) return false;
              return !!u.attachment_url;
            });
            setExistingPhotos(imgs);
          })
          .catch(() => setExistingPhotos([]))
          .finally(() => setLoadingExisting(false));
      }
      if (sheetContentRef.current) {
        sheetContentRef.current.scrollTop = 0;
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeItem?.item_id, resetForm]);

  const hasUnsavedChanges = useCallback(() => {
    if (!originalItemRef.current) return false;
    const orig = originalItemRef.current;
    if (status !== orig.status) return true;
    if (description !== orig.description) return true;
    if (severity !== orig.severity) return true;
    if (photos.length > 0) return true;
    if (notes !== orig.notes) return true;
    return false;
  }, [status, description, severity, photos, notes]);

  const openSheet = useCallback((itemId) => {
    setActiveItemId(itemId);
  }, []);

  const closeSheet = useCallback((force = false) => {
    if (!force && hasUnsavedChanges()) {
      setShowUnsavedConfirm(true);
      return;
    }
    photos.forEach(img => URL.revokeObjectURL(img.preview));
    setActiveItemId(null);
    setShowUnsavedConfirm(false);
    localStorage.removeItem(LS_ACTIVE_ITEM);
  }, [hasUnsavedChanges, photos]);

  const forceCloseSheet = useCallback(() => {
    photos.forEach(img => URL.revokeObjectURL(img.preview));
    setActiveItemId(null);
    setShowUnsavedConfirm(false);
    localStorage.removeItem(LS_ACTIVE_ITEM);
  }, [photos]);

  const updateItemLocally = useCallback((itemId, updates) => {
    setProtocol(prev => {
      if (!prev) return prev;
      const newProtocol = { ...prev };
      newProtocol.sections = newProtocol.sections.map(sec => {
        if (sec.section_id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map(itm => {
            if (itm.item_id !== itemId) return itm;
            return { ...itm, ...updates };
          }),
        };
      });
      return newProtocol;
    });
  }, [sectionId]);

  const mergeItemsFromBatch = useCallback((changedItems) => {
    if (!changedItems || changedItems.length === 0) return;
    const updated = new Map(changedItems.map(i => [i.item_id, i]));
    setProtocol(prev => {
      if (!prev) return prev;
      const newProtocol = { ...prev };
      newProtocol.sections = newProtocol.sections.map(sec => {
        if (sec.section_id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map(itm =>
            updated.has(itm.item_id) ? { ...itm, ...updated.get(itm.item_id) } : itm
          ),
        };
      });
      return newProtocol;
    });
  }, [sectionId]);

  const findNextUnchecked = useCallback((afterIndex) => {
    for (let i = afterIndex + 1; i < items.length; i++) {
      if (!items[i].status || items[i].status === 'not_checked') return items[i].item_id;
    }
    for (let i = 0; i < afterIndex; i++) {
      if (!items[i].status || items[i].status === 'not_checked') return items[i].item_id;
    }
    return null;
  }, [items]);

  const findNextIncompleteSection = useCallback(() => {
    if (!protocol?.sections) return null;
    const currentIdx = protocol.sections.findIndex(s => s.section_id === sectionId);
    const sections = protocol.sections;
    for (let offset = 1; offset < sections.length; offset++) {
      const idx = (currentIdx + offset) % sections.length;
      const sec = sections[idx];
      if (sec.section_id === sectionId) continue;
      const secItems = sec.items || [];
      if (secItems.length === 0) continue;
      const secChecked = secItems.filter(i => i.status && i.status !== 'not_checked').length;
      if (secChecked < secItems.length) {
        return sec;
      }
    }
    return null;
  }, [protocol, sectionId]);

  const showCompletionToast = useCallback(() => {
    if (sectionCompletionShown.current.has(sectionId)) return;
    sectionCompletionShown.current.add(sectionId);

    if (completionToastId.current) {
      toast.dismiss(completionToastId.current);
    }

    const nextSection = findNextIncompleteSection();

    const toastContent = (tId) => (
      <div className="flex flex-col gap-2" dir="rtl">
        <p className="text-sm font-bold text-green-800">הסקשן הושלם! ✓</p>
        <div className="flex gap-2">
          {nextSection ? (
            <button
              onClick={() => {
                toast.dismiss(tId);
                navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}/sections/${nextSection.section_id}`);
              }}
              className="flex-1 py-1.5 px-3 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-700"
            >
              עבור ל: {nextSection.name} ←
            </button>
          ) : (
            <button
              onClick={() => {
                toast.dismiss(tId);
                navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`);
              }}
              className="flex-1 py-1.5 px-3 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700"
            >
              חזרה לפרוטוקול
            </button>
          )}
          <button
            onClick={() => {
              toast.dismiss(tId);
            }}
            className="py-1.5 px-3 rounded-lg bg-white border border-slate-200 text-slate-600 text-xs font-medium hover:bg-slate-50"
          >
            השאר כאן
          </button>
        </div>
      </div>
    );

    const tId = toast.custom(
      (id) => toastContent(id),
      {
        duration: Infinity,
        position: 'bottom-center',
        style: {
          bottom: 'calc(env(safe-area-inset-bottom, 0px) + 16px)',
          background: '#f0fdf4',
          border: '1px solid #bbf7d0',
          borderRadius: '12px',
          padding: '12px',
          maxWidth: '400px',
          width: '90vw',
        },
      }
    );
    completionToastId.current = tId;
  }, [sectionId, findNextIncompleteSection, navigate, projectId, unitId, protocolId]);

  const handleImageAdd = useCallback(async (e) => {
    try {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;
      const compressed = await Promise.all(files.map(f => compressImage(f)));
      const newImages = compressed.map(file => ({
        file,
        preview: URL.createObjectURL(file),
        name: file.name,
      }));
      setPhotos(prev => [...prev, ...newImages]);
      setErrors(prev => { const n = { ...prev }; delete n.photos; return n; });
    } catch (err) {
      console.error('[handover:image] failed to process image:', err);
      toast.error('שגיאה בעיבוד התמונה');
    } finally {
      if (e.target) e.target.value = '';
    }
  }, []);

  const removePhoto = useCallback((index) => {
    setPhotos(prev => {
      URL.revokeObjectURL(prev[index].preview);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const validate = () => {
    const errs = {};
    const isDefect = status === 'defective' || status === 'partial';
    if (!isDefect) return errs;
    if (!severity) errs.severity = 'שדה חובה';
    if (status === 'defective') {
      if (!description.trim()) errs.description = 'שדה חובה';
      if (photos.length === 0 && existingPhotos.length === 0 && !skipPhotoReason.trim()) errs.photos = 'שדה חובה';
    }
    return errs;
  };

  const uploadPhotosToDefect = async (defectId, photosToUpload) => {
    const uploadWithRetry = async (file, maxAttempts = 2) => {
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
          return await taskService.uploadAttachment(defectId, file);
        } catch (err) {
          if (attempt >= maxAttempts) throw err;
          await new Promise(r => setTimeout(r, attempt * 2000));
        }
      }
    };
    const uploadResults = await Promise.allSettled(
      photosToUpload.map(img => uploadWithRetry(img.file))
    );
    const newFailed = new Set();
    uploadResults.forEach((r, i) => {
      if (r.status === 'rejected') newFailed.add(i);
    });
    return newFailed;
  };

  const handleCameraClick = useCallback(() => {
    if (activeItemId) {
      localStorage.setItem(LS_ACTIVE_ITEM, activeItemId);
      localStorage.setItem(LS_PROTOCOL_ID, protocolId);
      localStorage.setItem(LS_SECTION_ID, sectionId);
    }
    cameraInputRef.current?.click();
  }, [activeItemId, protocolId, sectionId]);

  const handleGalleryClick = useCallback(() => {
    if (activeItemId) {
      localStorage.setItem(LS_ACTIVE_ITEM, activeItemId);
      localStorage.setItem(LS_PROTOCOL_ID, protocolId);
      localStorage.setItem(LS_SECTION_ID, sectionId);
    }
    galleryInputRef.current?.click();
  }, [activeItemId, protocolId, sectionId]);

  const advanceAfterSave = useCallback((currentItemId) => {
    const currentIdx = items.findIndex(i => i.item_id === currentItemId);
    const nextId = findNextUnchecked(currentIdx);
    if (nextId) {
      setTimeout(() => openSheet(nextId), 200);
    } else {
      setTimeout(() => {
        forceCloseSheet();
        showCompletionToast();
      }, 200);
    }
  }, [items, findNextUnchecked, openSheet, forceCloseSheet, showCompletionToast]);

  const handleSimpleStatusSave = useCallback(async (newStatus) => {
    if (isSigned || saving || !activeItem) return;
    try {
      setSaving(true);
      setFlashStatus(newStatus);

      const result = await handoverService.updateItem(
        projectId, protocolId, sectionId, activeItem.item_id,
        { status: newStatus, notes }
      );

      if (result?.item) {
        updateItemLocally(activeItem.item_id, result.item);
      } else {
        updateItemLocally(activeItem.item_id, { status: newStatus });
      }
      originalItemRef.current = { ...originalItemRef.current, status: newStatus, notes };

      setTimeout(() => {
        setFlashStatus(null);
        advanceAfterSave(activeItem.item_id);
      }, 400);
    } catch (err) {
      console.error(err);
      setFlashStatus(null);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  }, [isSigned, saving, activeItem, projectId, protocolId, sectionId, notes, updateItemLocally, advanceAfterSave]);

  const handleSaveDefectAndAdvance = useCallback(async () => {
    if (isSigned || saving || !activeItem) return;

    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      if (sheetContentRef.current) {
        const firstError = sheetContentRef.current.querySelector('[data-error="true"]');
        firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    try {
      setSaving(true);
      setFailedPhotoIndexes(new Set());

      const payload = {
        status,
        description: description.trim(),
        severity,
        photos: [],
        photos_pending_count: photos.length,
        skip_photo_reason: skipPhotoReason.trim() || null,
      };

      const result = await handoverService.updateItem(
        projectId, protocolId, sectionId, activeItem.item_id, payload
      );

      const defectId = result?.defect_id;

      if (result?.item) {
        updateItemLocally(activeItem.item_id, result.item);
      } else {
        updateItemLocally(activeItem.item_id, { status, defect_id: defectId });
      }

      if (defectId && photos.length > 0) {
        setSavedDefectId(defectId);
        const failedIndexes = await uploadPhotosToDefect(defectId, photos);
        if (failedIndexes.size > 0) {
          setFailedPhotoIndexes(failedIndexes);
          const succeeded = photos.length - failedIndexes.size;
          if (succeeded > 0) {
            toast.warning(`שמירה הצליחה, ${failedIndexes.size} תמונות לא הועלו`);
          } else {
            toast.error('שמירה הצליחה, העלאת תמונות נכשלה');
          }
          setSaving(false);
          return;
        }
      }

      if (result?.defect_created) {
        toast.success('הפריט נשמר וליקוי נוצר');
      } else if (defectId && !result?.defect_created) {
        toast.success('הפריט נשמר והליקוי עודכן');
      } else {
        toast.success(t('handover', 'itemUpdated'));
      }

      originalItemRef.current = { status, description: description.trim(), severity, notes };
      photos.forEach(img => URL.revokeObjectURL(img.preview));
      advanceAfterSave(activeItem.item_id);
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSigned, saving, activeItem, status, description, severity, photos, skipPhotoReason, projectId, protocolId, sectionId, notes, updateItemLocally, advanceAfterSave]);

  const handleRetryFailedPhotos = useCallback(async () => {
    if (!savedDefectId || failedPhotoIndexes.size === 0) return;
    try {
      setSaving(true);
      const failedPhotos = photos.filter((_, i) => failedPhotoIndexes.has(i));
      const newFailed = await uploadPhotosToDefect(savedDefectId, failedPhotos);
      if (newFailed.size > 0) {
        const failedOriginalIndexes = new Set();
        const failedArr = [...failedPhotoIndexes];
        newFailed.forEach(i => failedOriginalIndexes.add(failedArr[i]));
        setFailedPhotoIndexes(failedOriginalIndexes);
        toast.error(`${newFailed.size} תמונות עדיין נכשלו`);
      } else {
        setFailedPhotoIndexes(new Set());
        toast.success('כל התמונות הועלו בהצלחה');
        photos.forEach(img => URL.revokeObjectURL(img.preview));
        advanceAfterSave(activeItem.item_id);
      }
    } catch (err) {
      console.error(err);
      toast.error('ניסיון חוזר נכשל');
    } finally {
      setSaving(false);
    }
  }, [savedDefectId, failedPhotoIndexes, photos, activeItem, advanceAfterSave]);

  const handleStatusChange = useCallback((newStatus) => {
    if (isSigned || saving) return;
    setStatus(newStatus);
    setErrors({});
    if (newStatus === 'ok' || newStatus === 'not_relevant') {
      handleSimpleStatusSave(newStatus);
    }
  }, [isSigned, saving, handleSimpleStatusSave]);

  const handleMarkAllOk = useCallback(async () => {
    setShowBatchConfirm(null);
    if (uncheckedItems.length === 0 || isSigned) return;
    try {
      setMarkingAll(true);
      const data = await handoverService.batchUpdateItems(projectId, protocolId, sectionId, {
        item_ids: uncheckedItems.map(i => i.item_id),
        status: 'ok',
      });
      mergeItemsFromBatch(data.items);
      const msg = data.skipped > 0
        ? `${data.updated} פריטים סומנו תקין (${data.skipped} דולגו)`
        : t('handover', 'markAllOkDone');
      toast.success(msg);
      if (uncheckedItems.length === uncheckedCount) {
        showCompletionToast();
      }
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
      await loadProtocol();
    } finally {
      setMarkingAll(false);
    }
  }, [uncheckedItems, uncheckedCount, isSigned, projectId, protocolId, sectionId, mergeItemsFromBatch, loadProtocol, showCompletionToast]);

  const handleMarkAllNotRelevant = useCallback(async () => {
    setShowBatchConfirm(null);
    if (uncheckedItems.length === 0 || isSigned) return;
    try {
      setMarkingAll(true);
      const data = await handoverService.batchUpdateItems(projectId, protocolId, sectionId, {
        item_ids: uncheckedItems.map(i => i.item_id),
        status: 'not_relevant',
      });
      mergeItemsFromBatch(data.items);
      const msg = data.skipped > 0
        ? `${data.updated} פריטים סומנו לא רלוונטי (${data.skipped} דולגו)`
        : `${data.updated} פריטים סומנו לא רלוונטי`;
      toast.success(msg);
      if (uncheckedItems.length === uncheckedCount) {
        showCompletionToast();
      }
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
      await loadProtocol();
    } finally {
      setMarkingAll(false);
    }
  }, [uncheckedItems, uncheckedCount, isSigned, projectId, protocolId, sectionId, mergeItemsFromBatch, loadProtocol, showCompletionToast]);

  const handleResetSection = useCallback(async () => {
    setShowBatchConfirm(null);
    if (resettableItems.length === 0 || isSigned) return;
    try {
      setMarkingAll(true);
      const data = await handoverService.batchUpdateItems(projectId, protocolId, sectionId, {
        item_ids: resettableItems.map(i => i.item_id),
        status: 'not_checked',
      });
      mergeItemsFromBatch(data.items);
      const msg = data.skipped > 0
        ? `${data.updated} פריטים אופסו (${data.skipped} עם ליקויים לא אופסו)`
        : 'הסקשן אופס בהצלחה';
      toast.success(msg);
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
      await loadProtocol();
    } finally {
      setMarkingAll(false);
    }
  }, [resettableItems, isSigned, projectId, protocolId, sectionId, mergeItemsFromBatch, loadProtocol]);

  const navigateItem = useCallback((direction) => {
    if (!activeItem) return;
    const newIdx = activeIndex + direction;
    if (newIdx >= 0 && newIdx < items.length) {
      if (hasUnsavedChanges()) {
        setShowUnsavedConfirm(true);
        return;
      }
      openSheet(items[newIdx].item_id);
    }
  }, [activeItem, activeIndex, items, hasUnsavedChanges, openSheet]);

  const getBatchConfirmText = () => {
    if (showBatchConfirm === 'markAll') {
      return `לסמן ${uncheckedItems.length} פריטים כתקינים?`;
    }
    if (showBatchConfirm === 'markNR') {
      if (hasDefectsInSection) {
        return `יש בסעיף ${items.filter(i => !!i.defect_id).length} ליקויים קיימים. הפעולה תחול רק על ${uncheckedItems.length} פריטים שעדיין לא מסומנים.`;
      }
      return `לסמן ${uncheckedItems.length} פריטים כלא רלוונטי?`;
    }
    if (showBatchConfirm === 'reset') {
      if (defectProtectedCount > 0) {
        return `לאפס ${resettableItems.length} פריטים? (${defectProtectedCount} פריטים עם ליקויים לא יאופסו)`;
      }
      return `לאפס ${resettableItems.length} פריטים?`;
    }
    return '';
  };

  const getBatchConfirmAction = () => {
    if (showBatchConfirm === 'markAll') return handleMarkAllOk;
    if (showBatchConfirm === 'markNR') return handleMarkAllNotRelevant;
    if (showBatchConfirm === 'reset') return handleResetSection;
    return () => {};
  };

  const getBatchConfirmColor = () => {
    if (showBatchConfirm === 'markAll') return { bg: 'bg-green-50 border-green-200', text: 'text-green-800', btn: 'bg-green-500 hover:bg-green-600' };
    if (showBatchConfirm === 'markNR') return { bg: 'bg-slate-50 border-slate-300', text: 'text-slate-800', btn: 'bg-slate-500 hover:bg-slate-600' };
    return { bg: 'bg-slate-50 border-slate-200', text: 'text-slate-700', btn: 'bg-slate-500 hover:bg-slate-600' };
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
      </div>
    );
  }

  if (!section) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-slate-500">{t('handover', 'loadError')}</p>
        <button onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`)}
          className="text-purple-600 hover:text-purple-700 font-medium">
          {t('handover', 'backToProtocol')}
        </button>
      </div>
    );
  }

  const isDefectStatus = status === 'defective' || status === 'partial';
  const showMarkAll = uncheckedItems.length > 0;
  const showReset = resettableItems.length > 0;
  const showAnyBatch = showMarkAll || showReset;

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="sticky top-0 z-30">
        <div className="bg-gradient-to-bl from-[#1e1b4b] to-[#312e81] text-white">
          <div className="max-w-lg mx-auto px-4 py-3">
            <div className="flex items-center gap-3">
              <button onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`)}
                className="p-1.5 hover:bg-white/10 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center">
                <ArrowRight className="w-5 h-5" />
              </button>
              <div className="flex-1 min-w-0">
                <h1 className="text-lg font-extrabold truncate">{section.name}</h1>
                <p className="text-indigo-300 text-xs">{checkedCount}/{totalCount} נבדקו</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white border-b border-slate-200">
          <div className="max-w-lg mx-auto">
            <div className="h-1 bg-slate-100">
              <div
                className="h-full rounded-l-full"
                style={{
                  width: `${progressPct}%`,
                  background: progressPct >= 100 ? '#22c55e' : 'linear-gradient(to left, #a78bfa, #7c3aed)',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {!isSigned && showAnyBatch && (
        <div className="max-w-lg mx-auto px-4 mt-3">
          <div className={`flex gap-1.5 ${isNarrow ? '' : 'gap-2'}`}>
            {showMarkAll && (
              <button
                onClick={() => setShowBatchConfirm('markAll')}
                disabled={markingAll}
                className={`flex-1 flex items-center justify-center rounded-xl bg-green-50 border border-green-200 text-green-700 font-medium hover:bg-green-100 active:scale-[0.98] transition-all disabled:opacity-50 ${
                  isNarrow ? 'flex-col gap-0.5 py-2 px-1 text-[10px]' : 'gap-1.5 py-2.5 text-sm'
                }`}
              >
                {markingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCheck className="w-4 h-4" />}
                {isNarrow ? 'תקין' : 'סמן הכל תקין'}
              </button>
            )}
            {showMarkAll && (
              <button
                onClick={() => setShowBatchConfirm('markNR')}
                disabled={markingAll}
                className={`flex-1 flex items-center justify-center rounded-xl bg-slate-50 border border-slate-300 text-slate-600 font-medium hover:bg-slate-100 active:scale-[0.98] transition-all disabled:opacity-50 ${
                  isNarrow ? 'flex-col gap-0.5 py-2 px-1 text-[10px]' : 'gap-1.5 py-2.5 text-sm'
                }`}
              >
                {markingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <MinusCircle className="w-4 h-4" />}
                {isNarrow ? 'N/A' : 'לא רלוונטי'}
              </button>
            )}
            {showReset && (
              <button
                onClick={() => setShowBatchConfirm('reset')}
                disabled={markingAll}
                className={`flex-1 flex items-center justify-center rounded-xl bg-slate-50 border border-slate-200 text-slate-600 font-medium hover:bg-slate-100 active:scale-[0.98] transition-all disabled:opacity-50 ${
                  isNarrow ? 'flex-col gap-0.5 py-2 px-1 text-[10px]' : 'gap-1.5 py-2.5 text-sm'
                }`}
              >
                {markingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                {isNarrow ? 'אפס' : 'אפס סקשן'}
              </button>
            )}
          </div>
        </div>
      )}

      {showBatchConfirm && (
        <div className="max-w-lg mx-auto px-4 mt-2">
          <div className={`rounded-xl p-3 flex flex-col gap-2 border ${getBatchConfirmColor().bg}`}>
            <span className={`text-sm font-medium ${getBatchConfirmColor().text}`}>
              {getBatchConfirmText()}
            </span>
            <div className="flex gap-2 justify-end">
              <button
                onClick={getBatchConfirmAction()}
                disabled={markingAll}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 ${getBatchConfirmColor().btn}`}
              >
                אישור
              </button>
              <button onClick={() => setShowBatchConfirm(null)}
                className="px-3 py-1.5 bg-white border border-slate-200 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-50">
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}

      {trades.length > 1 && (
        <div className="max-w-lg mx-auto mt-2">
          <div className="flex gap-1.5 px-4 overflow-x-auto no-scrollbar py-1">
            <button
              onClick={() => setActiveTrade(null)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors min-h-[36px]
                ${!activeTrade ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
              הכל ({items.length})
            </button>
            {trades.map(trade => (
              <button
                key={trade}
                onClick={() => setActiveTrade(activeTrade === trade ? null : trade)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors min-h-[36px]
                  ${activeTrade === trade ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              >
                {trade} ({items.filter(i => i.trade === trade).length})
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="max-w-lg mx-auto px-4 mt-2 space-y-1 pb-8">
        {filteredItems.map(item => {
          const st = item.status || 'not_checked';
          const badge = STATUS_BADGE_CONFIG[st] || STATUS_BADGE_CONFIG.not_checked;
          const isSelected = activeItemId === item.item_id;

          return (
            <button
              key={item.item_id}
              onClick={() => openSheet(item.item_id)}
              className={`w-full flex items-center gap-2.5 p-2.5 rounded-xl border transition-all active:scale-[0.98]
                hover:shadow-sm min-h-[52px] ${isSelected ? 'border-orange-400 border-2 bg-orange-50/30' : 'border-slate-200 bg-white'}`}
            >
              <span className={`text-[11px] font-medium px-2 py-1 rounded-full ${badge.bg} ${badge.text} ${badge.border} border flex-shrink-0`}>
                {badge.label}
              </span>
              <div className="flex-1 min-w-0 text-right">
                <span className="text-sm font-semibold text-slate-800 truncate block">{item.name}</span>
                <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                  {item.trade && (
                    <span className="text-[10px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{item.trade}</span>
                  )}
                  {item.defect_id && (
                    <span
                      onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${item.defect_id}`); }}
                      className="text-[10px] text-red-600 bg-red-100 px-1.5 py-0.5 rounded font-medium flex items-center gap-0.5 cursor-pointer"
                    >
                      <Bug className="w-2.5 h-2.5" />ליקוי
                    </span>
                  )}
                  {item.photos?.length > 0 && <Camera className="w-3 h-3 text-slate-400" />}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {activeItem && (
        <>
          <div
            className="fixed inset-0 bg-black/30 z-40"
            onClick={() => { if (!saving) closeSheet(); }}
          />

          <div
            className="fixed bottom-0 left-0 right-0 z-50 flex justify-center"
            style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
          >
            <div
              className="w-full bg-white rounded-t-[20px] shadow-[0_-4px_24px_rgba(0,0,0,0.15)] flex flex-col"
              style={{ maxHeight: '65vh', maxWidth: '480px' }}
            >
              <div className="flex items-center justify-center pt-2 pb-1">
                <div className="w-10 h-1 rounded-full bg-slate-300" />
              </div>

              <div className="px-4 pb-2 flex items-center gap-2 border-b border-slate-100">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => navigateItem(-1)}
                    disabled={activeIndex <= 0 || saving}
                    className="p-1.5 hover:bg-slate-100 rounded-lg disabled:opacity-30 transition-colors"
                  >
                    <ChevronRight className="w-4 h-4 text-slate-500" />
                  </button>
                  <button
                    onClick={() => navigateItem(1)}
                    disabled={activeIndex >= items.length - 1 || saving}
                    className="p-1.5 hover:bg-slate-100 rounded-lg disabled:opacity-30 transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4 text-slate-500" />
                  </button>
                </div>
                <button onClick={() => closeSheet()} disabled={saving} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-30">
                  <X className="w-4 h-4 text-slate-400" />
                </button>
                <div className="flex-1 min-w-0 text-right mr-1">
                  <h3 className="text-sm font-bold text-slate-800 truncate">{activeItem.name}</h3>
                  <p className="text-[11px] text-slate-500">
                    {activeItem.trade && <>{activeItem.trade} · </>}
                    {activeIndex + 1}/{totalCount} ({uncheckedCount} ממתינים)
                  </p>
                </div>
              </div>

              <div
                ref={sheetContentRef}
                className="flex-1 overflow-y-auto px-4 pb-4 space-y-3"
                style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 20px) + 16px)' }}
              >
                {isSigned && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-2 text-center text-sm text-green-700 font-medium mt-2">
                    {t('handover', 'readOnly')}
                  </div>
                )}

                <div className="grid grid-cols-4 gap-1.5 mt-2">
                  {STATUS_OPTIONS.map(opt => {
                    const isActive = status === opt.value;
                    const isFlashing = flashStatus === opt.value;
                    const Icon = opt.icon;
                    return (
                      <button
                        key={opt.value}
                        disabled={isSigned || saving}
                        onClick={() => handleStatusChange(opt.value)}
                        className={`flex flex-col items-center gap-1 p-2.5 rounded-lg border transition-all text-center
                          ${isFlashing ? 'bg-green-400 text-white border-green-400 scale-105' : isActive ? opt.activeColor : opt.color}
                          ${isSigned ? 'opacity-60 cursor-not-allowed' : 'active:scale-95'}`}
                      >
                        {isFlashing ? (
                          <CheckCircle2 className="w-5 h-5" />
                        ) : (
                          <Icon className="w-5 h-5" />
                        )}
                        <span className="text-[11px] font-medium leading-tight">{isFlashing ? '✓' : opt.label}</span>
                      </button>
                    );
                  })}
                </div>

                {activeItem.defect_id && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-3">
                    <div className="flex items-center gap-2">
                      <Bug className="w-4 h-4 text-red-500 flex-shrink-0" />
                      <span className="text-sm font-medium text-red-700 flex-1">ליקוי קיים</span>
                      <button
                        onClick={() => { forceCloseSheet(); navigate(`/tasks/${activeItem.defect_id}`); }}
                        className="text-xs text-red-600 hover:text-red-800 font-medium whitespace-nowrap"
                      >
                        צפה בליקוי →
                      </button>
                    </div>
                  </div>
                )}

                {isDefectStatus && (
                  <>
                    {status === 'defective' && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-2.5 flex items-start gap-2">
                        <Info className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                        <p className="text-xs text-red-700 font-medium">ליקוי ייווצר אוטומטית ויקושר לפרוטוקול</p>
                      </div>
                    )}
                    {status === 'partial' && (
                      <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 flex items-start gap-2">
                        <Info className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                        <p className="text-xs text-amber-700 font-medium">סטטוס חלקי — ליקוי ייווצר אוטומטית</p>
                      </div>
                    )}

                    {(existingPhotos.length > 0 || loadingExisting) && (
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-slate-500">תמונות קיימות</label>
                        {loadingExisting ? (
                          <div className="flex items-center gap-2 py-2">
                            <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />
                            <span className="text-xs text-slate-400">טוען תמונות...</span>
                          </div>
                        ) : (
                          <div className="flex gap-2 overflow-x-auto pb-1">
                            {existingPhotos.map((att, i) => (
                              <div key={att.id || i} className="relative flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 border-slate-200">
                                <img src={att.attachment_url} alt="" className="w-full h-full object-cover" />
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <div className={`space-y-1 rounded-lg p-2 -mx-2 ${errors.photos ? 'border border-red-400 ring-1 ring-red-200 bg-red-50/30' : ''}`} data-error={errors.photos ? 'true' : undefined}>
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-medium text-slate-700">
                          {existingPhotos.length > 0 ? 'תמונות חדשות' : 'תמונות'}
                          {status === 'defective' && <span className="text-red-500 mr-1">*</span>}
                        </label>
                      </div>

                      {photos.length > 0 && (
                        <div className="flex gap-2 overflow-x-auto pb-1">
                          {photos.map((img, i) => (
                            <div key={i} className={`relative flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2
                              ${failedPhotoIndexes.has(i) ? 'border-red-500 ring-2 ring-red-200' : 'border-slate-200'}`}>
                              <img src={img.preview} alt="" className="w-full h-full object-cover" />
                              {failedPhotoIndexes.has(i) && (
                                <div className="absolute inset-0 bg-red-500/20 flex items-center justify-center">
                                  <AlertTriangle className="w-5 h-5 text-red-600" />
                                </div>
                              )}
                              {!savedDefectId && (
                                <button onClick={() => removePhoto(i)}
                                  className="absolute top-0.5 left-0.5 p-0.5 bg-red-500 text-white rounded-full">
                                  <X className="w-3 h-3" />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {failedPhotoIndexes.size > 0 && (
                        <button
                          type="button"
                          onClick={handleRetryFailedPhotos}
                          disabled={saving}
                          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-red-100 text-red-700 text-xs font-medium hover:bg-red-200 disabled:opacity-50"
                        >
                          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
                          נסה שוב להעלות {failedPhotoIndexes.size} תמונות
                        </button>
                      )}

                      <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleImageAdd} className="hidden" />
                      <input ref={galleryInputRef} type="file" accept="image/*" multiple onChange={handleImageAdd} className="hidden" />

                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={handleCameraClick}
                          disabled={isSigned || saving}
                          className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg border-2 border-dashed border-purple-300 text-purple-600 text-xs font-medium hover:bg-purple-50 active:bg-purple-100 disabled:opacity-50"
                        >
                          <Camera className="w-4 h-4" />
                          📷 צלם
                        </button>
                        <button
                          type="button"
                          onClick={handleGalleryClick}
                          disabled={isSigned || saving}
                          className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg border-2 border-dashed border-slate-300 text-slate-600 text-xs font-medium hover:bg-slate-50 active:bg-slate-100 disabled:opacity-50"
                        >
                          <ImagePlus className="w-4 h-4" />
                          🖼️ גלריה
                        </button>
                      </div>

                      {status === 'defective' && photos.length === 0 && existingPhotos.length === 0 && (
                        <div className="mt-1">
                          {!showSkipInput ? (
                            <button type="button" onClick={() => setShowSkipInput(true)}
                              className="text-[11px] text-slate-500 hover:text-slate-700 underline">
                              אפשר לדלג עם סיבה
                            </button>
                          ) : (
                            <div className="space-y-1.5">
                              <div className="flex flex-wrap gap-1.5">
                                {SKIP_REASONS.map(reason => (
                                  <button key={reason} type="button"
                                    onClick={() => {
                                      setSkipPhotoReason(reason);
                                      setErrors(prev => { const n = { ...prev }; delete n.photos; return n; });
                                    }}
                                    className={`text-[10px] px-2 py-1 rounded-full border transition-colors ${
                                      skipPhotoReason === reason
                                        ? 'bg-slate-600 text-white border-slate-600'
                                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                                    }`}
                                  >
                                    {reason}
                                  </button>
                                ))}
                              </div>
                              <input
                                type="text"
                                value={skipPhotoReason}
                                onChange={(e) => {
                                  setSkipPhotoReason(e.target.value);
                                  setErrors(prev => { const n = { ...prev }; delete n.photos; return n; });
                                }}
                                placeholder="אחר: סיבה..."
                                className="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-purple-400"
                                dir="rtl"
                              />
                            </div>
                          )}
                        </div>
                      )}

                      {errors.photos && (
                        <p className="text-[11px] text-red-500 mt-0.5 font-medium">{errors.photos}</p>
                      )}
                    </div>

                    <div className="space-y-1" data-error={errors.description ? 'true' : undefined}>
                      <label className="text-sm font-medium text-slate-700">
                        תיאור הליקוי
                        {status === 'defective' && <span className="text-red-500 mr-1">*</span>}
                      </label>
                      <textarea
                        value={description}
                        onChange={(e) => {
                          setDescription(e.target.value);
                          setErrors(prev => { const n = { ...prev }; delete n.description; return n; });
                        }}
                        disabled={isSigned || saving}
                        placeholder="תארו את הליקוי..."
                        className={`w-full px-3 py-2 border rounded-lg text-sm resize-none h-16
                          focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-400
                          disabled:bg-slate-50 disabled:text-slate-500
                          ${errors.description ? 'border-red-400 ring-1 ring-red-200' : 'border-slate-200'}`}
                        dir="rtl"
                      />
                      {errors.description && (
                        <p className="text-[11px] text-red-500 mt-0.5 font-medium">{errors.description}</p>
                      )}
                    </div>

                    <div className="space-y-1" data-error={errors.severity ? 'true' : undefined}>
                      <label className="text-sm font-medium text-slate-700">
                        חומרה <span className="text-red-500 mr-1">*</span>
                      </label>
                      <div className="grid grid-cols-3 gap-1.5">
                        {SEVERITY_OPTIONS.map(opt => (
                          <button
                            key={opt.value}
                            type="button"
                            disabled={isSigned || saving}
                            onClick={() => {
                              setSeverity(opt.value);
                              setErrors(prev => { const n = { ...prev }; delete n.severity; return n; });
                            }}
                            className={`py-2 rounded-lg border text-xs font-medium transition-all
                              ${severity === opt.value ? opt.activeColor : opt.color}
                              ${errors.severity ? 'ring-1 ring-red-200' : ''}
                              ${isSigned ? 'opacity-60 cursor-not-allowed' : 'active:scale-95'}`}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                      {errors.severity && (
                        <p className="text-[11px] text-red-500 mt-0.5 font-medium">{errors.severity}</p>
                      )}
                    </div>
                  </>
                )}

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-500">הערות (אופציונלי)</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    disabled={isSigned || saving}
                    placeholder="הערות נוספות..."
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none h-16
                      focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-400
                      disabled:bg-slate-50 disabled:text-slate-500"
                    dir="rtl"
                  />
                </div>

                {!isSigned && isDefectStatus && (
                  <div className="flex gap-2 pt-1 pb-2">
                    <button
                      onClick={() => closeSheet()}
                      disabled={saving}
                      className="flex-1 py-2.5 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
                    >
                      ביטול
                    </button>
                    <button
                      onClick={handleSaveDefectAndAdvance}
                      disabled={saving || isSigned}
                      className="flex-[2] py-2.5 rounded-xl bg-purple-600 text-white text-sm font-bold
                        hover:bg-purple-700 active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                      {saving ? 'שומר...' : 'שמור והמשך'}
                    </button>
                  </div>
                )}

                {showUnsavedConfirm && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 space-y-2">
                    <p className="text-sm font-medium text-amber-800">יש שינויים שלא נשמרו. לצאת בלי לשמור?</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setShowUnsavedConfirm(false); forceCloseSheet(); }}
                        className="flex-1 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium hover:bg-amber-600"
                      >
                        צא בלי לשמור
                      </button>
                      <button
                        onClick={() => setShowUnsavedConfirm(false)}
                        className="flex-1 py-2 rounded-lg bg-white border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50"
                      >
                        חזור
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default HandoverSectionPage;
