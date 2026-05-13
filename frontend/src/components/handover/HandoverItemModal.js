import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { handoverService, taskService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { useNavigate } from 'react-router-dom';
import { compressImage } from '../../utils/imageCompress';
import {
  Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerDescription,
} from '../ui/drawer';
import {
  CheckCircle2, AlertTriangle, CircleDot, MinusCircle,
  Bug, ExternalLink, Loader2, X, Camera, ImagePlus, Info,
  ChevronLeft, Trash2,
} from 'lucide-react';

const PhotoAnnotation = React.lazy(() => import('../PhotoAnnotation'));

const STATUS_OPTIONS = [
  { value: 'ok', label: 'תקין', icon: CheckCircle2, color: 'bg-green-100 text-green-700 border-green-300', activeColor: 'bg-green-500 text-white border-green-500' },
  { value: 'partial', label: 'חלקי', icon: CircleDot, color: 'bg-amber-100 text-amber-700 border-amber-300', activeColor: 'bg-amber-500 text-white border-amber-500' },
  { value: 'defective', label: 'לא תקין', icon: AlertTriangle, color: 'bg-red-100 text-red-700 border-red-300', activeColor: 'bg-red-500 text-white border-red-500' },
  { value: 'not_relevant', label: 'לא רלוונטי', icon: MinusCircle, color: 'bg-slate-100 text-slate-600 border-slate-300', activeColor: 'bg-slate-500 text-white border-slate-500' },
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

const HandoverItemModal = ({
  open, onClose, item, sectionId, sectionName, projectId, protocolId,
  isSigned, onItemUpdated, allItems, onSelectItem,
}) => {
  const navigate = useNavigate();
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

  const [pendingFile, setPendingFile] = useState(null);

  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const processingImageRef = useRef(false);

  const resetForm = useCallback((itemData) => {
    setStatus(itemData?.status || 'not_checked');
    setNotes(itemData?.notes || '');
    setDescription(itemData?.description || '');
    setSeverity(itemData?.severity || null);
    setPhotos([]);
    setSkipPhotoReason('');
    setShowSkipInput(false);
    setErrors({});
    setFailedPhotoIndexes(new Set());
    setSavedDefectId(null);
    setExistingPhotos([]);
    setLoadingExisting(false);
  }, []);

  const handlePhotosSelected = useCallback(async (e) => {
    if (processingImageRef.current) return;
    processingImageRef.current = true;
    try {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;

      const stableFiles = [];
      for (const file of files) {
        try {
          const compressed = await compressImage(file);
          let stable = compressed;
          if (!compressed._fromCompress) {
            const bytes = await compressed.arrayBuffer();
            stable = new File([bytes], compressed.name, { type: compressed.type });
          }
          stable._fromCompress = true;
          stableFiles.push(stable);
        } catch (err) {
          if (err?.code === 'UNSUPPORTED_FORMAT') {
            toast.error('פורמט תמונה לא נתמך. נסה לצלם מהמצלמה');
            console.error('[handover:compress] HEIC/unsupported:', err.original);
          } else {
            console.error('[handover:compress] failed:', err);
            toast.error('שגיאה בעיבוד התמונה. נסה שוב.');
          }
        }
      }
      if (stableFiles.length === 0) return;

      if (stableFiles.length === 1) {
        setPendingFile(stableFiles[0]);
      } else {
        const newImages = stableFiles.map(f => ({
          file: f,
          preview: URL.createObjectURL(f),
          name: f.name,
        }));
        setPhotos(prev => [...prev, ...newImages]);
        setErrors(prev => { const n = {...prev}; delete n.photos; return n; });
      }
    } finally {
      processingImageRef.current = false;
      if (e.target) e.target.value = '';
    }
  }, []);

  const handleAnnotationSave = useCallback(async (annotatedFile, hasAnnotations) => {
    if (!pendingFile) return;
    try {
      const fileToUpload = (hasAnnotations && annotatedFile) ? annotatedFile : pendingFile;
      try {
        const slice = fileToUpload.slice(0, 1);
        await slice.arrayBuffer();
      } catch {
        toast.error('התמונה אבדה, נא לצרף מחדש');
        setPendingFile(null);
        return;
      }
      const newImage = {
        file: fileToUpload,
        preview: URL.createObjectURL(fileToUpload),
        name: fileToUpload.name,
      };
      setPhotos(prev => [...prev, newImage]);
      setErrors(prev => { const n = {...prev}; delete n.photos; return n; });
      setPendingFile(null);
    } catch (err) {
      console.error('[handover:annotation] save failed:', err);
      toast.error('שגיאה בשמירת התמונה');
    }
  }, [pendingFile]);

  const removePhoto = useCallback((index) => {
    setPhotos(prev => {
      URL.revokeObjectURL(prev[index].preview);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  useEffect(() => {
    if (item && open) {
      resetForm(item);
      if (item.defect_id) {
        setLoadingExisting(true);
        taskService.getUpdates(item.defect_id)
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
    }
  }, [item, open, resetForm]);

  if (!item) return null;

  const isDefectStatus = status === 'defective' || status === 'partial';
  const hasDefect = !!item.defect_id;

  const handleStatusChange = (newStatus) => {
    if (isSigned || saving) return;
    setStatus(newStatus);
    setErrors({});
    if (newStatus !== 'defective' && newStatus !== 'partial') {
      setDescription('');
      setSeverity(null);
      setPhotos([]);
      setSkipPhotoReason('');
      setShowSkipInput(false);
    }
  };

  const handlePassNotesBlur = async () => {
    if (isSigned || saving) return;
    if (status !== 'ok' && status !== 'not_relevant') return;
    try {
      setSaving(true);
      await handoverService.updateItem(projectId, protocolId, sectionId, item.item_id, {
        status,
        notes,
      });
      onItemUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  };

  const validate = () => {
    const errs = {};
    if (!isDefectStatus) return errs;

    if (!severity) {
      errs.severity = 'חובה לבחור חומרה';
    }
    if (status === 'defective') {
      if (!description.trim()) {
        errs.description = 'תיאור חובה עבור "לא תקין"';
      }
      if (photos.length === 0 && !skipPhotoReason.trim()) {
        errs.photos = 'נדרשת תמונה או סיבת דילוג';
      }
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

  const advanceToNext = () => {
    photos.forEach(img => URL.revokeObjectURL(img.preview));
    onItemUpdated?.();
    if (allItems && onSelectItem) {
      const currentIdx = allItems.findIndex(i => i.item_id === item.item_id);
      if (currentIdx >= 0 && currentIdx < allItems.length - 1) {
        onSelectItem(allItems[currentIdx + 1].item_id);
      } else {
        onClose();
      }
    } else {
      onClose();
    }
  };

  const handleRetryFailedPhotos = async () => {
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
        onItemUpdated?.();
        advanceToNext();
      }
    } catch (err) {
      console.error(err);
      toast.error('ניסיון חוזר נכשל');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndAdvance = async () => {
    if (isSigned || saving) return;

    if (isDefectStatus) {
      const errs = validate();
      if (Object.keys(errs).length > 0) {
        setErrors(errs);
        return;
      }
    }

    try {
      setSaving(true);
      setFailedPhotoIndexes(new Set());

      const payload = { status };

      if (isDefectStatus) {
        payload.description = description.trim();
        payload.severity = severity;
        payload.photos = [];
        payload.photos_pending_count = photos.length;
        payload.skip_photo_reason = skipPhotoReason.trim() || null;
      } else {
        payload.notes = notes;
      }

      const result = await handoverService.updateItem(
        projectId, protocolId, sectionId, item.item_id, payload
      );

      const defectId = result?.defect_id;

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
          onItemUpdated?.();
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

      advanceToNext();
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  };

  const handleSimpleStatusSave = async (newStatus) => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateItem(projectId, protocolId, sectionId, item.item_id, {
        status: newStatus,
        notes,
      });
      onItemUpdated?.();
      if (allItems && onSelectItem) {
        const currentIdx = allItems.findIndex(i => i.item_id === item.item_id);
        if (currentIdx >= 0 && currentIdx < allItems.length - 1) {
          onSelectItem(allItems[currentIdx + 1].item_id);
        } else {
          onClose();
        }
      }
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {pendingFile && (
        <Suspense fallback={
          <div className="fixed inset-0 z-[10000] bg-black flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-white animate-spin" />
          </div>
        }>
          <PhotoAnnotation
            imageFile={pendingFile}
            onSave={handleAnnotationSave}
            onDiscard={() => setPendingFile(null)}
          />
        </Suspense>
      )}
    <Drawer open={open} onOpenChange={(o) => { if (!o) { photos.forEach(img => URL.revokeObjectURL(img.preview)); onClose(); } }}>
      <DrawerContent className="max-h-[90vh]" dir="rtl">
        <DrawerHeader className="text-right pb-2">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <DrawerTitle className="text-base font-bold text-slate-800 truncate">
                {item.name}
              </DrawerTitle>
              <DrawerDescription className="text-xs text-slate-500 mt-0.5">
                מקצוע: {item.trade}
              </DrawerDescription>
            </div>
            <button onClick={() => { photos.forEach(img => URL.revokeObjectURL(img.preview)); onClose(); }} className="p-1.5 hover:bg-slate-100 rounded-lg">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </DrawerHeader>

        <div className="px-4 pb-6 space-y-3 overflow-y-auto max-h-[75vh]">
          {isSigned && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-2 text-center text-sm text-green-700 font-medium">
              {t('handover', 'readOnly')}
            </div>
          )}

          <div className="grid grid-cols-4 gap-1.5">
            {STATUS_OPTIONS.map(opt => {
              const isActive = status === opt.value;
              const Icon = opt.icon;
              return (
                <button
                  key={opt.value}
                  disabled={isSigned || saving}
                  onClick={() => {
                    handleStatusChange(opt.value);
                    if (opt.value === 'ok' || opt.value === 'not_relevant') {
                      handleSimpleStatusSave(opt.value);
                    }
                  }}
                  className={`flex flex-col items-center gap-1 p-2.5 rounded-lg border transition-all text-center
                    ${isActive ? opt.activeColor : opt.color}
                    ${isSigned ? 'opacity-60 cursor-not-allowed' : 'active:scale-95'}`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-[11px] font-medium leading-tight">{opt.label}</span>
                </button>
              );
            })}
          </div>

          {hasDefect && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3">
              <div className="flex items-center gap-2">
                <Bug className="w-4 h-4 text-red-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-red-700 block">
                    ליקוי קיים
                  </span>
                  {item.defect_status && (
                    <span className="text-[10px] text-red-500">
                      סטטוס: {item.defect_status}
                      {item.defect_severity && ` · חומרה: ${item.defect_severity}`}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => { photos.forEach(img => URL.revokeObjectURL(img.preview)); onClose(); navigate(`/tasks/${item.defect_id}`); }}
                  className="flex items-center gap-1 text-xs text-red-600 hover:text-red-800 font-medium whitespace-nowrap"
                >
                  צפה בליקוי
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>
            </div>
          )}

          {isDefectStatus && (
            <>
              {status === 'defective' && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-2.5 flex items-start gap-2">
                  <Info className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-700 font-medium">
                    ליקוי ייווצר אוטומטית ויקושר לפרוטוקול
                  </p>
                </div>
              )}
              {status === 'partial' && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 flex items-start gap-2">
                  <Info className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-amber-700 font-medium">
                    סטטוס חלקי — ליקוי ייווצר אוטומטית. הגדירו תיאור וחומרה.
                  </p>
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

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-slate-700">{existingPhotos.length > 0 ? 'תמונות חדשות' : 'תמונות'}</label>
                  <span className="text-[10px] text-slate-400">
                    {photos.length > 0 ? `${photos.length} תמונות` : ''}
                    {status === 'defective' ? ' (חובה)' : ' (אופציונלי)'}
                  </span>
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
                          <button
                            onClick={() => removePhoto(i)}
                            className="absolute top-0.5 left-0.5 p-0.5 bg-red-500 text-white rounded-full"
                          >
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
                    className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-red-100 text-red-700 text-xs font-medium hover:bg-red-200 active:bg-red-300 disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
                    נסה שוב להעלות {failedPhotoIndexes.size} תמונות
                  </button>
                )}

                <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handlePhotosSelected} className="hidden" />
                <input ref={galleryInputRef} type="file" accept="image/*" multiple onChange={handlePhotosSelected} className="hidden" />

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => cameraInputRef.current?.click()}
                    disabled={isSigned}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg border-2 border-dashed border-purple-300 text-purple-600 text-xs font-medium hover:bg-purple-50 active:bg-purple-100 disabled:opacity-50"
                  >
                    <Camera className="w-4 h-4" />
                    צלם
                  </button>
                  <button
                    type="button"
                    onClick={() => galleryInputRef.current?.click()}
                    disabled={isSigned}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg border-2 border-dashed border-slate-300 text-slate-600 text-xs font-medium hover:bg-slate-50 active:bg-slate-100 disabled:opacity-50"
                  >
                    <ImagePlus className="w-4 h-4" />
                    גלריה
                  </button>
                </div>

                {status === 'defective' && photos.length === 0 && (
                  <div className="mt-1">
                    {!showSkipInput ? (
                      <button
                        type="button"
                        onClick={() => setShowSkipInput(true)}
                        className="text-[11px] text-slate-500 hover:text-slate-700 underline"
                      >
                        אפשר לדלג עם סיבה
                      </button>
                    ) : (
                      <div className="space-y-1.5">
                        <div className="flex flex-wrap gap-1.5">
                          {SKIP_REASONS.map(reason => (
                            <button
                              key={reason}
                              type="button"
                              onClick={() => {
                                setSkipPhotoReason(reason);
                                setErrors(prev => { const n = {...prev}; delete n.photos; return n; });
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
                            setErrors(prev => { const n = {...prev}; delete n.photos; return n; });
                          }}
                          placeholder="אחר: סיבה..."
                          className="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-purple-400"
                          dir="rtl"
                        />
                      </div>
                    )}
                  </div>
                )}

                {errors.photos && <p className="text-[11px] text-red-500 mt-0.5">{errors.photos}</p>}
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700">
                  תיאור הליקוי
                  {status === 'defective' && <span className="text-red-500 mr-1">*</span>}
                </label>
                <textarea
                  value={description}
                  onChange={(e) => {
                    setDescription(e.target.value);
                    setErrors(prev => { const n = {...prev}; delete n.description; return n; });
                  }}
                  disabled={isSigned}
                  placeholder="תארו את הליקוי..."
                  className={`w-full px-3 py-2 border rounded-lg text-sm resize-none h-16
                    focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-400
                    disabled:bg-slate-50 disabled:text-slate-500
                    ${errors.description ? 'border-red-400' : 'border-slate-200'}`}
                  dir="rtl"
                />
                {errors.description && <p className="text-[11px] text-red-500">{errors.description}</p>}
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700">
                  חומרה <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                  {SEVERITY_OPTIONS.map(opt => {
                    const isActive = severity === opt.value;
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        disabled={isSigned}
                        onClick={() => {
                          setSeverity(opt.value);
                          setErrors(prev => { const n = {...prev}; delete n.severity; return n; });
                        }}
                        className={`py-2 px-2 rounded-lg border text-sm font-medium transition-all text-center
                          ${isActive ? opt.activeColor : opt.color}
                          ${isSigned ? 'opacity-60 cursor-not-allowed' : 'active:scale-95'}`}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
                {errors.severity && <p className="text-[11px] text-red-500 mt-0.5">{errors.severity}</p>}
              </div>
            </>
          )}

          {!isDefectStatus && (
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">הערות (אופציונלי)</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                onBlur={handlePassNotesBlur}
                disabled={isSigned}
                placeholder="הערות..."
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none h-16
                  focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-400
                  disabled:bg-slate-50 disabled:text-slate-500"
                dir="rtl"
              />
            </div>
          )}

          {isDefectStatus && !isSigned && (
            <button
              onClick={handleSaveAndAdvance}
              disabled={saving}
              className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all
                active:scale-[0.98] disabled:opacity-50
                ${status === 'defective'
                  ? 'bg-red-500 text-white hover:bg-red-600'
                  : 'bg-amber-500 text-white hover:bg-amber-600'}`}
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ChevronLeft className="w-4 h-4" />
              )}
              שמור ועבור לפריט הבא
            </button>
          )}
        </div>
      </DrawerContent>
    </Drawer>
    </>
  );
};

export default HandoverItemModal;
