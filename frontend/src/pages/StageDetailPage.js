import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { qcService, BACKEND_URL } from '../services/api';
import { getStageVisualStatus, getQualityBadge, getReviewBadge } from '../utils/qcVisualStatus';
import { toast } from 'sonner';
import {
  ArrowRight, Loader2, ClipboardCheck, CheckCircle2, XCircle, Clock,
  Save, RefreshCw, Camera, Send, Lock, AlertCircle, ShieldCheck, ShieldX, ShieldAlert, Navigation,
  RotateCcw, History, User, Filter, Eye, ImagePlus, ChevronDown, ChevronUp, Settings, Info, Users,
  Paperclip, FileText, Phone
} from 'lucide-react';
import WhatsAppRejectionModal from '../components/WhatsAppRejectionModal';
import * as DialogPrimitive from '@radix-ui/react-dialog';

const STATUS_CONFIG = {
  pass: { icon: CheckCircle2, label: 'תקין', color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200', btnBg: 'bg-emerald-500 text-white' },
  fail: { icon: XCircle, label: 'לא תקין', color: 'text-red-600', bg: 'bg-red-50 border-red-200', btnBg: 'bg-red-500 text-white' },
  pending: { icon: Clock, label: 'ממתין', color: 'text-slate-400', bg: 'bg-slate-50 border-slate-200', btnBg: 'bg-slate-200 text-slate-600' },
};

const STAGE_STATUS_BADGES = {
  draft: { label: 'טיוטה', color: 'bg-slate-100 text-slate-600' },
  ready: { label: 'מוכן לשליחה', color: 'bg-amber-100 text-amber-700' },
  pending_review: { label: 'ממתין לאישור', color: 'bg-blue-100 text-blue-700' },
  approved: { label: 'אושר', color: 'bg-emerald-100 text-emerald-700' },
  rejected: { label: 'נדחה', color: 'bg-red-100 text-red-700' },
  reopened: { label: 'נפתח מחדש', color: 'bg-orange-100 text-orange-700' },
};


const formatDateTime = (dateStr) => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const yy = d.getFullYear();
  return `${hh}:${mm} ${dd}.${mo}.${yy}`;
};

const formatHebrewDate = formatDateTime;

const formatShortTime = (dateStr) => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mo} ${hh}:${mm}`;
};

const resolveActorName = (name) => {
  if (name === null || name === undefined) return null;
  if (name === '') return 'משתמש לא ידוע';
  return name;
};

const TIMELINE_ICONS = {
  submit_for_review: { icon: Send, color: 'text-blue-500 bg-blue-50' },
  qc_approved: { icon: ShieldCheck, color: 'text-emerald-500 bg-emerald-50' },
  qc_rejected: { icon: ShieldX, color: 'text-red-500 bg-red-50' },
  qc_reopened: { icon: RotateCcw, color: 'text-orange-500 bg-orange-50' },
  item_rejected: { icon: ShieldX, color: 'text-red-500 bg-red-50' },
  update: { icon: ClipboardCheck, color: 'text-slate-500 bg-slate-50' },
  upload: { icon: Camera, color: 'text-blue-400 bg-blue-50' },
};

const PhotoThumbnail = ({ photo, isPM }) => {
  const src = photo.url?.startsWith('http') ? photo.url : `${BACKEND_URL}${photo.url}`;
  const actorName = resolveActorName(photo.uploaded_by_name);
  return (
    <div className="inline-block">
      <a href={src} target="_blank" rel="noopener noreferrer" className="block">
        <img src={src} alt="" className="w-14 h-14 rounded-lg object-cover border border-slate-200 hover:border-amber-400 transition-all" />
      </a>
      {(actorName || photo.uploaded_at) && (
        <p className="text-xs text-slate-600 mt-1 max-w-[160px] leading-normal" dir="rtl">
          {actorName ? <>צולם ע"י <span className="font-medium text-slate-700">{actorName}</span></> : 'צולם'}
          {photo.uploaded_at && <span className="block text-[11px] text-slate-400">{formatShortTime(photo.uploaded_at)}</span>}
        </p>
      )}
    </div>
  );
};

const StageItemRow = React.forwardRef(({ item, canEdit, isLocked, onToggle, localState, onNoteChange, onUploadPhotos, uploadState, onRetryUpload, itemErrors, isHighlighted, isGreenFlash, isPendingReview, canApproveThis, onRejectItem, canSendWhatsApp, onWhatsAppCta }, ref) => {
  const currentStatus = localState?.status ?? item.status;
  const currentNote = localState?.note ?? item.note ?? '';
  const cfg = STATUS_CONFIG[currentStatus] || STATUS_CONFIG.pending;
  const isFail = currentStatus === 'fail';
  const noteRequired = isFail;
  const [showNote, setShowNote] = useState(!!currentNote || noteRequired);
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReasonLocal] = useState('');
  const [rejectingItem, setRejectingItem] = useState(false);
  const cameraRef = useRef(null);
  const pickerRef = useRef(null);
  const uploadLockRef = useRef(false);
  const rejection = item.reviewer_rejection;
  const photos = item.photos || [];
  const isUploading = uploadState && uploadState.files.some(f => f.status === 'uploading');
  const hasError = itemErrors && itemErrors.length > 0;
  const effectiveCanEdit = canEdit && !isLocked;
  const needsPhoto = item.required_photo && photos.length === 0;
  const needsNote = noteRequired && !(currentNote || '').trim();

  useEffect(() => {
    if (isFail && !showNote) setShowNote(true);
  }, [isFail, showNote]);

  const handleFileChange = useCallback((e) => {
    const fl = e.target.files;
    if (fl && fl.length > 0) onUploadPhotos(item.id, fl);
    e.target.value = '';
    uploadLockRef.current = false;
  }, [item.id, onUploadPhotos]);

  const triggerInput = useCallback((ref) => {
    if (uploadLockRef.current || isUploading) return;
    uploadLockRef.current = true;
    ref.current?.click();
    setTimeout(() => { uploadLockRef.current = false; }, 2000);
  }, [isUploading]);

  const openCamera = useCallback(() => triggerInput(cameraRef), [triggerInput]);
  const openPicker = useCallback(() => triggerInput(pickerRef), [triggerInput]);

  const handleToggleClick = (itemId, newStatus) => {
    if (item.required_photo && photos.length === 0 && newStatus !== 'pending') {
      return;
    }
    onToggle(itemId, newStatus);
  };

  const noteBadgeLabel = () => {
    if (isFail) {
      return (currentNote || '').trim() ? 'הערה צורפה' : 'חובה הערה (בעת סימון לא תקין)';
    }
    return null;
  };

  const notePlaceholder = () => {
    if (isFail) return 'כתוב סיבת אי-תקינות / פירוט';
    return 'אפשר להוסיף הערה אם צריך';
  };

  const noteLabel = () => {
    if (isFail) return 'חובה הערה (בעת סימון לא תקין)';
    return 'הערה (אופציונלי)';
  };

  const badgeText = noteBadgeLabel();

  return (
    <div ref={ref} className={`border rounded-xl p-4 transition-all ${isGreenFlash ? 'ring-2 ring-green-400 bg-green-50 border-green-300' : isHighlighted ? 'ring-2 ring-amber-400 bg-amber-50 border-amber-300' : hasError ? 'bg-red-50 border-red-300 ring-2 ring-red-200' : isLocked ? 'bg-slate-50 border-slate-300 opacity-80' : 'bg-white border-slate-200'}`}>
      {/* 1. Title + always-visible status pill */}
      <div className="flex items-start justify-between gap-3">
        <span className="text-[15px] text-slate-800 font-semibold leading-snug flex-1">
          {item.title}
          {item.pre_work_documentation && (
            <span className="inline-flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 mr-1 align-middle">
              <FileText className="w-2.5 h-2.5" />
              תיעוד לפני עבודה
            </span>
          )}
        </span>
        <span className={`inline-flex items-center gap-1 text-xs font-bold whitespace-nowrap px-2.5 py-1 rounded-full border ${
          currentStatus === 'pass' ? 'bg-emerald-100 text-emerald-700 border-emerald-300' :
          currentStatus === 'fail' ? 'bg-red-100 text-red-700 border-red-300' :
          'bg-slate-100 text-slate-500 border-slate-200'
        }`}>
          {isLocked && <Lock className="w-3 h-3" />}
          {currentStatus === 'pass' && <CheckCircle2 className="w-3.5 h-3.5" />}
          {currentStatus === 'fail' && <XCircle className="w-3.5 h-3.5" />}
          {currentStatus === 'pending' && <Clock className="w-3.5 h-3.5" />}
          {cfg.label}
        </span>
      </div>

      {/* 2. Badges */}
      <div className="flex gap-1.5 mt-1.5 flex-wrap">
        {item.required_photo ? (
          <span className="text-[11px] px-2 py-0.5 rounded-full flex items-center gap-1 font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <Camera className="w-3.5 h-3.5" />
            חובה תמונה
          </span>
        ) : (
          <span className="text-[11px] px-2 py-0.5 rounded-full flex items-center gap-1 bg-slate-100 text-slate-500 border border-slate-200">
            <Camera className="w-3.5 h-3.5" />
            תמונה אופציונלית
          </span>
        )}
        {photos.length > 0 && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            תמונה צורפה
          </span>
        )}
        {badgeText && (
          <span className={`text-[11px] px-2 py-0.5 rounded-full border ${(currentNote || '').trim() ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
            {badgeText}
          </span>
        )}
      </div>

      {/* 3. Metadata (who marked + when) */}
      {currentStatus !== 'pending' && (item.updated_at || item.updated_by_name !== undefined) && (
        <p className="text-xs text-slate-600 mt-2 leading-normal" dir="rtl">
          {currentStatus === 'pass' ? 'סומן תקין' : 'סומן לא תקין'}
          {resolveActorName(item.updated_by_name) && <> ע"י <span className="font-medium text-slate-700">{resolveActorName(item.updated_by_name)}</span></>}
          {item.updated_at && <span className="text-slate-400"> • {formatShortTime(item.updated_at)}</span>}
        </p>
      )}

      {/* 4. Photos */}
      {photos.length > 0 && (
        <div className="flex gap-2 mt-3 flex-wrap">
          {photos.map(p => <PhotoThumbnail key={p.id} photo={p} />)}
        </div>
      )}

      {/* 4b. Upload queue indicator */}
      {uploadState && uploadState.files.length > 0 && (
        <div className="mt-2.5 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2" dir="rtl">
          {isUploading && (
            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium mb-1.5">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500 flex-shrink-0" />
              <span>מעלה {uploadState.completed + uploadState.failed}/{uploadState.total}...</span>
            </div>
          )}
          <div className="space-y-1">
            {uploadState.files.map(f => (
              <div key={f.client_id} className="flex items-center gap-1.5 text-[11px]">
                {f.status === 'uploading' && <Loader2 className="w-3 h-3 animate-spin text-amber-500 flex-shrink-0" />}
                {f.status === 'success' && <CheckCircle2 className="w-3 h-3 text-emerald-500 flex-shrink-0" />}
                {f.status === 'failed' && <XCircle className="w-3 h-3 text-red-500 flex-shrink-0" />}
                <span className={`truncate flex-1 ${f.status === 'failed' ? 'text-red-600' : f.status === 'success' ? 'text-emerald-600' : 'text-slate-500'}`}>
                  {f.name || 'תמונה'}
                </span>
                {f.status === 'failed' && onRetryUpload && (
                  <button
                    onClick={() => onRetryUpload(f.client_id)}
                    className="flex items-center gap-1 text-[11px] font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 active:bg-amber-200 border border-amber-200 rounded px-1.5 py-0.5 flex-shrink-0 transition-all"
                  >
                    <RefreshCw className="w-3 h-3" />
                    נסה שוב
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. Pass/Fail buttons */}
      {effectiveCanEdit && (
        <div className="flex gap-2 mt-3">
          {['pass', 'fail'].map(s => {
            const sc = STATUS_CONFIG[s];
            const isActive = currentStatus === s;
            const photoBlocked = needsPhoto && !isActive;
            return (
              <button
                key={s}
                disabled={photoBlocked}
                aria-label={sc.label}
                onClick={() => handleToggleClick(item.id, s)}
                className={`flex-1 py-2.5 text-sm font-semibold rounded-lg border transition-all ${
                  photoBlocked
                    ? 'opacity-40 cursor-not-allowed bg-slate-50 border-slate-200 text-slate-400'
                    : isActive ? sc.btnBg + ' border-transparent shadow-sm' : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300 active:bg-slate-50'
                }`}
              >
                {sc.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Photo required prompt */}
      {needsPhoto && effectiveCanEdit && (
        <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          <div className="flex items-center gap-1.5 text-xs text-amber-700 font-medium mb-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>חובה לצרף תמונה לפני סימון</span>
          </div>
          <div className="flex gap-2" dir="rtl">
            <button onClick={openCamera} disabled={isUploading}
              aria-label="צלם עכשיו"
              className="flex-1 flex items-center justify-center gap-2 text-sm font-bold text-white bg-amber-500 hover:bg-amber-600 active:bg-amber-700 rounded-xl py-2.5 min-h-[48px] transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
              {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />}
              {isUploading ? 'מעלה...' : 'צלם עכשיו'}
            </button>
            <button onClick={openPicker} disabled={isUploading}
              aria-label="בחר תמונות"
              className="flex items-center justify-center gap-1.5 text-sm font-medium text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 active:bg-slate-100 rounded-xl px-4 py-2.5 min-h-[48px] transition-all disabled:opacity-50 disabled:cursor-not-allowed">
              <Paperclip className="w-4 h-4" />
              <span>בחר תמונות</span>
            </button>
          </div>
        </div>
      )}

      {/* 6. Upload buttons — only when needsPhoto banner is NOT shown */}
      {effectiveCanEdit && !needsPhoto && (
        <div className="mt-3 flex gap-2" dir="rtl">
          <button onClick={openCamera} disabled={isUploading}
            aria-label={photos.length > 0 ? 'צלם עוד' : 'צלם עכשיו'}
            className={`flex-1 flex items-center justify-center gap-2 text-sm font-bold rounded-xl py-2.5 min-h-[48px] transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed ${
              photos.length > 0
                ? 'text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 active:bg-slate-100'
                : 'text-white bg-amber-500 hover:bg-amber-600 active:bg-amber-700'
            }`}>
            {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />}
            {isUploading ? 'מעלה...' : photos.length > 0 ? 'צלם עוד' : 'צלם עכשיו'}
          </button>
          <button onClick={openPicker} disabled={isUploading}
            aria-label="בחר תמונות"
            className="flex items-center justify-center gap-1.5 text-sm font-medium text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 active:bg-slate-100 rounded-xl px-4 py-2.5 min-h-[48px] transition-all disabled:opacity-50 disabled:cursor-not-allowed">
            <Paperclip className="w-4 h-4" />
            <span>בחר תמונות</span>
          </button>
        </div>
      )}

      {/* Hidden file inputs: camera (direct capture) + picker (OS native chooser) */}
      {effectiveCanEdit && (
        <>
          <input ref={cameraRef} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="hidden" onChange={handleFileChange} />
          <input ref={pickerRef} type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={handleFileChange} />
        </>
      )}

      {/* 7. Note field */}
      {(effectiveCanEdit || currentNote) && (
        <div className="mt-3">
          {effectiveCanEdit ? (
            (!showNote && !currentNote && !noteRequired) ? (
              <button onClick={() => setShowNote(true)} className="text-xs text-slate-400 hover:text-slate-600 active:text-slate-700 py-2 min-h-[44px]">+ {noteLabel()}</button>
            ) : (
              <>
                {noteRequired && (
                  <label className="block text-[11px] font-medium text-amber-700 mb-1">{noteLabel()}</label>
                )}
                <input type="text" value={currentNote} onChange={e => onNoteChange(item.id, e.target.value)}
                  placeholder={notePlaceholder()}
                  className={`w-full text-sm border rounded-lg px-3 py-2 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-amber-200 ${
                    needsNote ? 'border-amber-300 bg-amber-50' : 'border-slate-200'
                  }`} dir="rtl" />
              </>
            )
          ) : (
            currentNote && <p className="text-xs text-slate-500">הערה: {currentNote}</p>
          )}
        </div>
      )}

      {/* 8. Rejection notice */}
      {rejection && (
        <div className="mt-3 bg-red-50 border border-red-300 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-xs font-bold text-red-700 mb-1">
            <ShieldX className="w-4 h-4" />
            נדחה בביקורת
          </div>
          <p className="text-xs text-red-700 mb-1" dir="rtl">{rejection.reason}</p>
          <p className="text-[11px] text-red-500" dir="rtl">
            {resolveActorName(rejection.by_name) && <>נדחה ע"י <span className="font-medium">{resolveActorName(rejection.by_name)}</span></>}
            {rejection.at && <> • {formatShortTime(rejection.at)}</>}
          </p>
          {rejection.returned_to_user_name && (
            <p className="text-[11px] text-red-500 mt-0.5" dir="rtl">
              הוחזר ל: <span className="font-medium">{rejection.returned_to_user_name}</span>
            </p>
          )}
          {canSendWhatsApp && onWhatsAppCta && !rejection.returned_to_user_id && (
            <button
              onClick={() => onWhatsAppCta(item.item_id, item.title, rejection.reason)}
              className="mt-2 w-full flex items-center justify-center gap-2 text-xs font-semibold text-green-700 bg-green-50 hover:bg-green-100 active:bg-green-200 border border-green-200 rounded-lg px-3 py-2 min-h-[40px] transition-all"
              dir="rtl"
            >
              <Phone className="w-3.5 h-3.5" />
              שלח הודעת דחייה ב-WhatsApp
            </button>
          )}
        </div>
      )}

      {/* Reject item button (approver in pending_review) */}
      {isPendingReview && canApproveThis && !showRejectInput && (
        <div className="mt-3 bg-red-50/50 border border-red-100 rounded-lg p-2">
          <button onClick={() => setShowRejectInput(true)}
            aria-label="דחה סעיף זה"
            className="w-full flex items-center justify-center gap-2 text-sm font-semibold text-red-600 bg-white hover:bg-red-50 active:bg-red-100 border border-red-200 rounded-lg px-3 py-2.5 min-h-[44px] transition-all shadow-sm">
            <ShieldX className="w-4 h-4" />
            דחה סעיף זה
          </button>
          <p className="text-[11px] text-red-400 text-center mt-1.5">דחיית סעיף תפתח את השלב לתיקון</p>
        </div>
      )}

      {showRejectInput && (
        <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3 space-y-2">
          <label className="block text-xs font-medium text-red-700">סיבת דחיית הסעיף</label>
          <input
            type="text"
            value={rejectReason}
            onChange={e => setRejectReasonLocal(e.target.value)}
            placeholder="פרט את סיבת הדחייה..."
            className="w-full text-sm border border-red-200 rounded-lg px-3 py-2 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-red-200 bg-white"
            dir="rtl"
            autoFocus
          />
          <div className="flex gap-2">
            <button onClick={() => { setShowRejectInput(false); setRejectReasonLocal(''); }}
              className="text-xs text-slate-500 hover:text-slate-700 active:text-slate-800 px-3 py-2 min-h-[44px] rounded-lg">ביטול</button>
            <button
              disabled={rejectingItem || !rejectReason.trim()}
              onClick={async () => {
                setRejectingItem(true);
                try {
                  await onRejectItem(item.id, rejectReason.trim());
                  setShowRejectInput(false);
                  setRejectReasonLocal('');
                } finally {
                  setRejectingItem(false);
                }
              }}
              className={`flex items-center gap-1 text-xs font-medium rounded-lg px-4 py-2 min-h-[44px] transition-all ${
                rejectReason.trim() ? 'bg-red-500 hover:bg-red-600 active:bg-red-700 text-white' : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              }`}>
              {rejectingItem ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldX className="w-4 h-4" />}
              דחה סעיף
            </button>
          </div>
        </div>
      )}

      {/* Inline errors */}
      {hasError && (
        <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-2.5">
          {itemErrors.map((e, i) => (
            <p key={i} className="text-xs text-red-700 font-medium flex items-center gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              {e.reason}
            </p>
          ))}
        </div>
      )}
    </div>
  );
});


const AuditSummaryCard = ({ auditSummary, canSeeFull }) => {
  if (!auditSummary || Object.keys(auditSummary).length === 0) return null;

  const entries = [];
  if (auditSummary.submitted_by_name || auditSummary.submitted_at) {
    entries.push({
      label: 'נשלח לאישור',
      name: auditSummary.submitted_by_name,
      time: auditSummary.submitted_at,
      icon: Send,
      color: 'text-blue-500',
    });
  }
  if (auditSummary.approved_by_name || auditSummary.approved_at) {
    entries.push({
      label: 'אושר',
      name: auditSummary.approved_by_name,
      time: auditSummary.approved_at,
      icon: ShieldCheck,
      color: 'text-emerald-500',
    });
  }
  if (auditSummary.rejected_by_name || auditSummary.rejected_at) {
    entries.push({
      label: 'נדחה',
      name: auditSummary.rejected_by_name,
      time: auditSummary.rejected_at,
      icon: ShieldX,
      color: 'text-red-500',
      reason: auditSummary.rejected_reason,
    });
  }
  if (auditSummary.reopened_by_name || auditSummary.reopened_at) {
    entries.push({
      label: 'נפתח מחדש',
      name: auditSummary.reopened_by_name,
      time: auditSummary.reopened_at,
      icon: RotateCcw,
      color: 'text-orange-500',
      reason: auditSummary.reopened_reason,
    });
  }

  entries.sort((a, b) => {
    const ta = a.time ? new Date(a.time).getTime() : 0;
    const tb = b.time ? new Date(b.time).getTime() : 0;
    return tb - ta;
  });

  if (entries.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-3.5 shadow-sm">
      <h3 className="text-xs font-bold text-slate-600 mb-2.5 flex items-center gap-1.5">
        <User className="w-3.5 h-3.5 text-slate-500" />
        סיכום פעולות
      </h3>
      <div className="space-y-3">
        {entries.map((entry, i) => {
          const Icon = entry.icon;
          return (
            <div key={i} className="flex items-start gap-2.5 text-xs">
              <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${entry.color}`} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-700 leading-snug">{entry.label}</p>
                <div className="flex flex-wrap items-center gap-x-1.5 mt-0.5">
                  {resolveActorName(entry.name) && <span className="text-slate-500">{resolveActorName(entry.name)}</span>}
                  {resolveActorName(entry.name) && entry.time && <span className="text-slate-300">·</span>}
                  {entry.time && <span className="text-slate-400">{formatShortTime(entry.time)}</span>}
                </div>
                {entry.reason && (
                  <p className="text-slate-500 mt-1 bg-slate-50 rounded-lg px-2 py-1">סיבה: {entry.reason}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};


const ApproverInfoCard = ({ approvers, stageId, canManage, projectId, navigate }) => {
  const pmApprovers = approvers.filter(a => a.source === 'pm_default');
  const explicitApprovers = approvers.filter(a => a.source === 'explicit');
  const relevantExplicit = explicitApprovers.filter(a =>
    a.mode === 'all' || (a.mode === 'stages' && (a.stages || []).includes(stageId))
  );

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
      <div className="flex items-center gap-2 text-slate-700 font-bold text-xs mb-3">
        <Users className="w-4 h-4 text-slate-500" />
        מי מאשר שלב זה?
      </div>

      {pmApprovers.length > 0 && (
        <div className="mb-2.5">
          <p className="text-[11px] text-slate-400 font-medium mb-1.5">מנהלי פרויקט (ברירת מחדל)</p>
          <div className="space-y-1.5">
            {pmApprovers.map(a => (
              <div key={a.user_id} className="flex items-center gap-2 text-xs text-slate-700">
                <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 font-bold text-[10px] flex-shrink-0">
                  {(a.name || '?')[0]}
                </div>
                <span className="font-medium truncate">{a.name || 'מנהל פרויקט'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {relevantExplicit.length > 0 && (
        <div>
          {pmApprovers.length > 0 && <div className="border-t border-slate-100 my-2" />}
          <p className="text-[11px] text-slate-400 font-medium mb-1.5">מאשרים נוספים</p>
          <div className="space-y-1.5">
            {relevantExplicit.map(a => (
              <div key={a.user_id} className="flex items-center gap-2 text-xs text-slate-700">
                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold text-[10px] flex-shrink-0">
                  {(a.name || '?')[0]}
                </div>
                <span className="font-medium truncate">{a.name || 'מאשר'}</span>
                <span className="text-[10px] text-slate-400 px-1.5 py-0.5 rounded-full bg-slate-50 border border-slate-200 flex-shrink-0">
                  {a.mode === 'all' ? 'כל השלבים' : 'שלבים נבחרים'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {canManage && (
        <button
          onClick={() => navigate(`/projects/${projectId}/control?tab=settings`)}
          className="flex items-center justify-center gap-1.5 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 active:bg-amber-200 border border-amber-200 rounded-xl px-3 py-2.5 mt-3 min-h-[44px] w-full transition-all"
        >
          <Settings className="w-3.5 h-3.5" />
          ניהול מאשרי בקרת ביצוע
        </button>
      )}
    </div>
  );
};


const TimelineCard = ({ timeline, canSeeFull, defaultExpanded }) => {
  const storageKey = 'qc_timeline_expanded';
  const [isExpanded, setIsExpanded] = useState(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored !== null) return stored === 'true';
    } catch {}
    return defaultExpanded;
  });

  if (!timeline || timeline.length === 0) return null;

  const toggleExpanded = () => {
    const next = !isExpanded;
    setIsExpanded(next);
    try { localStorage.setItem(storageKey, String(next)); } catch {}
  };

  const stageEvents = timeline.filter(ev => ev.event_type === 'stage');
  const itemEvents = timeline.filter(ev => ev.event_type !== 'stage');

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <button
        onClick={toggleExpanded}
        className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-slate-50 active:bg-slate-100 transition-colors min-h-[52px]"
      >
        <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
          <History className="w-4 h-4 text-slate-500" />
          {isExpanded ? 'הסתר היסטוריה' : 'הצג היסטוריה'}
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{timeline.length} פעולות</span>
          {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4">
          {stageEvents.length > 0 && (
            <div className="space-y-3">
              {stageEvents.map((ev, i) => {
                const evCfg = TIMELINE_ICONS[ev.action] || { icon: Clock, color: 'text-slate-400 bg-slate-50' };
                const Icon = evCfg.icon;
                return (
                  <div key={ev.id || `s-${i}`} className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${evCfg.color} ring-2 ring-white shadow-sm`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0 py-0.5">
                      <p className="text-sm font-semibold text-slate-800 leading-snug">{ev.action_label}</p>
                      <div className="flex flex-wrap items-center gap-x-1.5 mt-0.5">
                        {resolveActorName(ev.actor_name) && <span className="text-xs text-slate-500">{resolveActorName(ev.actor_name)}</span>}
                        {resolveActorName(ev.actor_name) && ev.created_at && <span className="text-slate-300">·</span>}
                        {ev.created_at && <span className="text-xs text-slate-400">{formatShortTime(ev.created_at)}</span>}
                      </div>
                      {ev.reason && <p className="text-xs text-slate-500 mt-1 bg-slate-50 rounded-lg px-2 py-1">סיבה: {ev.reason}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {stageEvents.length > 0 && itemEvents.length > 0 && (
            <div className="flex items-center gap-2 my-4">
              <div className="flex-1 border-t border-slate-200" />
              <span className="text-[11px] text-slate-400 font-medium bg-slate-50 px-2 py-0.5 rounded-full">פעולות סעיפים ({itemEvents.length})</span>
              <div className="flex-1 border-t border-slate-200" />
            </div>
          )}

          {itemEvents.length > 0 && (
            <div className="space-y-2.5 pr-1">
              {itemEvents.map((ev, i) => {
                const evCfg = TIMELINE_ICONS[ev.action] || { icon: Clock, color: 'text-slate-400 bg-slate-50' };
                const Icon = evCfg.icon;
                return (
                  <div key={ev.id || `i-${i}`} className="flex items-start gap-2.5">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${evCfg.color}`}>
                      <Icon className="w-3 h-3" />
                    </div>
                    <div className="flex-1 min-w-0 py-0.5">
                      <p className="text-xs font-medium text-slate-600 leading-snug">{ev.action_label}</p>
                      <div className="flex flex-wrap items-center gap-x-1.5 mt-0.5">
                        {resolveActorName(ev.actor_name) && <span className="text-[11px] text-slate-400">{resolveActorName(ev.actor_name)}</span>}
                        {resolveActorName(ev.actor_name) && ev.created_at && <span className="text-slate-300">·</span>}
                        {ev.created_at && <span className="text-[11px] text-slate-400">{formatShortTime(ev.created_at)}</span>}
                      </div>
                      {ev.reason && <p className="text-[11px] text-slate-500 mt-0.5">סיבה: {ev.reason}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};


export default function StageDetailPage() {
  const { projectId, floorId, runId, stageId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const navState = location.state || {};
  const isUnitMode = navState.scope === 'unit';
  const unitName = navState.unitName || '';
  const returnToPath = navState.returnTo || '';

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [runData, setRunData] = useState(null);
  const [localChanges, setLocalChanges] = useState({});
  const [hasChanges, setHasChanges] = useState(false);
  const [uploadingItems, setUploadingItems] = useState({});
  const hasActiveUploads = useMemo(() => {
    return Object.values(uploadingItems).some(item => item.files.some(f => f.status === 'uploading'));
  }, [uploadingItems]);
  const hasActiveUploadsRef = useRef(false);
  useEffect(() => { hasActiveUploadsRef.current = hasActiveUploads; }, [hasActiveUploads]);
  const [validationErrors, setValidationErrors] = useState([]);
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const [timeSinceSave, setTimeSinceSave] = useState('');
  const [approverStatus, setApproverStatus] = useState(null);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [highlightedItemId, setHighlightedItemId] = useState(null);
  const [showReopenModal, setShowReopenModal] = useState(false);
  const [reopenReason, setReopenReason] = useState('');
  const [reopening, setReopening] = useState(false);
  const [timelineData, setTimelineData] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const [lastRejectedItemId, setLastRejectedItemId] = useState(null);
  const [whatsAppModal, setWhatsAppModal] = useState(null);

  const itemRefs = useRef({});

  useEffect(() => {
    if (!lastSavedAt) return;
    const update = () => {
      const diff = Math.floor((Date.now() - lastSavedAt) / 1000);
      if (diff < 5) setTimeSinceSave('עכשיו');
      else if (diff < 60) setTimeSinceSave(`לפני ${diff} שניות`);
      else if (diff < 3600) setTimeSinceSave(`לפני ${Math.floor(diff / 60)} דקות`);
      else setTimeSinceSave('');
    };
    update();
    const iv = setInterval(update, 10000);
    return () => clearInterval(iv);
  }, [lastSavedAt]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await qcService.getRun(runId);
      setRunData(result);
      if (!hasActiveUploadsRef.current) {
        setLocalChanges({});
        setHasChanges(false);
      }
    } catch (err) {
      if (err.response?.status === 403) {
        setError('אין הרשאה לצפות בבקרת ביצוע');
      } else {
        setError(err.response?.data?.detail || 'שגיאה בטעינת נתוני שלב');
      }
    } finally {
      setLoading(false);
    }
  }, [runId]);

  const softLoadGeneration = useRef(0);

  const scrollToAnchor = useCallback((itemId) => {
    if (!itemId) return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const ref = itemRefs.current[itemId];
        if (ref) {
          const headerOffset = 110;
          const y = ref.getBoundingClientRect().top + window.scrollY - headerOffset;
          window.scrollTo({ top: y, behavior: 'auto' });
        }
      });
    });
  }, []);

  const stage = runData?.stages?.find(s => s.id === stageId);
  const isLocked = stage?.computed_status === 'pending_review';
  const isApproved = stage?.computed_status === 'approved';
  const isRejected = stage?.computed_status === 'rejected';
  const isReopened = stage?.computed_status === 'reopened';
  const canEdit = runData?.can_edit && !isLocked && !isApproved;

  const isPM = runData?.role && ['project_manager', 'owner'].includes(runData.role);

  const isItemVisibleInFilter = useCallback((itemId, filterKey) => {
    if (!stage || filterKey === 'all') return true;
    const item = stage.items?.find(i => i.id === itemId);
    if (!item) return false;
    const local = localChanges[itemId];
    const s = local?.status ?? item.status;
    const n = local?.note ?? item.note ?? '';
    switch (filterKey) {
      case 'pass': return s === 'pass';
      case 'unmarked': return s === 'pending';
      case 'fail': return s === 'fail';
      case 'rejected': return !!item.reviewer_rejection;
      case 'missing_photo': return item.required_photo && (!item.photos || item.photos.length === 0);
      case 'missing_note': return s === 'fail' && !(n || '').trim();
      case 'problems':
        if (item.reviewer_rejection) return true;
        if (s === 'pending') return true;
        if (item.required_photo && (!item.photos || item.photos.length === 0)) return true;
        if (s === 'fail' && !(n || '').trim()) return true;
        return false;
      default: return true;
    }
  }, [stage, localChanges]);

  const softLoad = useCallback(async (anchorItemId) => {
    const savedScrollY = window.scrollY;
    const gen = ++softLoadGeneration.current;
    try {
      const result = await qcService.getRun(runId);
      if (softLoadGeneration.current !== gen) return;
      setRunData(result);
    } catch (err) {
      // soft load failure is non-fatal — data stays as-is
      return;
    }
    if (anchorItemId) {
      setActiveFilter(prev => {
        const needReset = !isItemVisibleInFilter(anchorItemId, prev);
        const nextFilter = needReset ? 'all' : prev;
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            const ref = itemRefs.current[anchorItemId];
            if (ref) {
              const headerOffset = 110;
              const y = ref.getBoundingClientRect().top + window.scrollY - headerOffset;
              window.scrollTo({ top: y, behavior: 'auto' });
            } else {
              window.scrollTo({ top: savedScrollY, behavior: 'auto' });
            }
          });
        });
        return nextFilter;
      });
    } else {
      requestAnimationFrame(() => {
        window.scrollTo({ top: savedScrollY, behavior: 'auto' });
      });
    }
  }, [runId, isItemVisibleInFilter]);

  const loadTimeline = useCallback(async () => {
    try {
      const data = await qcService.getStageTimeline(runId, stageId);
      setTimelineData(data);
    } catch (err) {
      // timeline is optional, don't block
    }
  }, [runId, stageId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadTimeline(); }, [loadTimeline]);

  useEffect(() => {
    if (!runId) return;
    qcService.getMyApproverStatus(runId)
      .then(data => setApproverStatus(data))
      .catch(() => setApproverStatus({ is_approver: false }));
  }, [runId]);

  useEffect(() => {
    const shouldWarn = hasActiveUploads || hasChanges;
    if (!shouldWarn) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasActiveUploads, hasChanges]);

  const canApproveThis = approverStatus?.is_approver && (
    approverStatus.mode === 'all' ||
    (approverStatus.mode === 'stages' && (approverStatus.stages || []).includes(stageId))
  );

  const hasBlockingFailures = useMemo(() => {
    if (!stage?.items) return false;
    return stage.items.some(i => i.status === 'fail' || i.reviewer_rejection);
  }, [stage?.items]);

  const blockingFailCount = useMemo(() => {
    if (!stage?.items) return 0;
    return stage.items.filter(i => i.status === 'fail' || i.reviewer_rejection).length;
  }, [stage?.items]);

  const isInconsistent = stage?.computed_status === 'approved' && hasBlockingFailures;

  const handleApprove = async () => {
    if (hasBlockingFailures) {
      toast.error(`לא ניתן לאשר — יש ${blockingFailCount} פריטים שנכשלו`);
      return;
    }
    setApproving(true);
    try {
      await qcService.approveStage(runId, stageId, {});
      toast.success('השלב אושר בהצלחה');
      await load();
      loadTimeline();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message : detail;
      toast.error(msg || 'שגיאה באישור השלב');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      toast.error('יש לציין סיבת דחייה');
      return;
    }
    setRejecting(true);
    try {
      await qcService.rejectStage(runId, stageId, { reason: rejectReason });
      toast.success('השלב נדחה');
      setShowRejectModal(false);
      setRejectReason('');
      await load();
      loadTimeline();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בדחיית השלב');
    } finally {
      setRejecting(false);
    }
  };

  const handleReopen = async () => {
    if (!reopenReason.trim()) {
      toast.error('יש לציין סיבת פתיחה מחדש');
      return;
    }
    setReopening(true);
    try {
      await qcService.reopenStage(runId, stageId, { reason: reopenReason });
      toast.success('השלב נפתח מחדש בהצלחה');
      setShowReopenModal(false);
      setReopenReason('');
      await load();
      loadTimeline();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בפתיחה מחדש של השלב');
    } finally {
      setReopening(false);
    }
  };

  const [flashItems, setFlashItems] = useState({});

  const handleToggle = (itemId, newStatus) => {
    setLocalChanges(prev => {
      const existing = prev[itemId] || {};
      return { ...prev, [itemId]: { ...existing, status: newStatus } };
    });
    setHasChanges(true);
    setValidationErrors(prev => prev.filter(e => e.item_id !== itemId || e.field !== 'status'));
    if (newStatus === 'pass') {
      setFlashItems(prev => ({ ...prev, [itemId]: true }));
      setTimeout(() => setFlashItems(prev => { const next = { ...prev }; delete next[itemId]; return next; }), 600);
    }
  };

  const handleNoteChange = (itemId, note) => {
    setLocalChanges(prev => {
      const existing = prev[itemId] || {};
      return { ...prev, [itemId]: { ...existing, note } };
    });
    setHasChanges(true);
    setValidationErrors(prev => prev.filter(e => e.item_id !== itemId || e.field !== 'note'));
  };

  const hasFailWithoutNote = useMemo(() => {
    if (!stage) return false;
    return Object.entries(localChanges).some(([itemId, change]) => {
      const originalItem = stage.items?.find(i => i.id === itemId);
      const effectiveStatus = change.status ?? originalItem?.status ?? 'pending';
      const effectiveNote = change.note ?? originalItem?.note ?? '';
      return effectiveStatus === 'fail' && !(effectiveNote || '').trim();
    });
  }, [localChanges, stage]);

  const handleSave = async () => {
    if (!runId || Object.keys(localChanges).length === 0) return;
    if (hasFailWithoutNote) {
      toast.error('יש סעיפים מסומנים לא תקין ללא הערה — יש להוסיף הערה לפני שמירה');
      return;
    }
    setSaving(true);
    const savedItemIds = [];
    try {
      const promises = Object.entries(localChanges).map(([itemId, change]) => {
        const payload = {};
        if (change.status !== undefined) payload.status = change.status;
        if (change.note !== undefined) payload.note = change.note;
        savedItemIds.push(itemId);
        return qcService.updateItem(runId, itemId, payload);
      });
      await Promise.all(promises);
      setLocalChanges(prev => {
        const next = { ...prev };
        for (const id of savedItemIds) delete next[id];
        return next;
      });
      setLastSavedAt(Date.now());
      setHasChanges(Object.keys(localChanges).length > savedItemIds.length);
      toast.success(`${savedItemIds.length} סעיפים נשמרו`);
      await load();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message : (typeof detail === 'string' ? detail : err.message);
      toast.error('שגיאה בשמירה: ' + msg);
    } finally {
      setSaving(false);
    }
  };

  const handleUploadPhotos = async (itemId, files) => {
    if (!runId || !files || files.length === 0) return;
    setValidationErrors(prev => prev.filter(e => e.item_id !== itemId || e.field !== 'photo'));

    const MAX_FILE_SIZE = 10 * 1024 * 1024;
    const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
    const fileArray = Array.from(files);
    const validFiles = [];
    for (const file of fileArray) {
      if (file.size > MAX_FILE_SIZE) {
        toast.error('הקובץ גדול מדי (מקסימום 10MB)');
        continue;
      }
      if (file.type && !ALLOWED_TYPES.includes(file.type)) {
        toast.error('פורמט לא נתמך. השתמש ב-JPEG, PNG או WebP');
        continue;
      }
      validFiles.push(file);
    }
    if (validFiles.length === 0) return;

    const tempEntries = validFiles.map((file, idx) => {
      const blobUrl = URL.createObjectURL(file);
      const clientId = `temp_${Date.now()}_${idx}`;
      return { file, blobUrl, clientId };
    });

    const filesState = tempEntries.map(e => ({
      client_id: e.clientId,
      name: e.file.name,
      status: 'uploading',
      _file: e.file,
    }));
    setUploadingItems(prev => ({
      ...prev,
      [itemId]: {
        total: (prev[itemId]?.total || 0) + validFiles.length,
        completed: prev[itemId]?.completed || 0,
        failed: prev[itemId]?.failed || 0,
        files: [...(prev[itemId]?.files || []), ...filesState],
      },
    }));

    setRunData(prev => {
      if (!prev) return prev;
      const updatedStages = prev.stages.map(s => {
        if (s.id !== stageId) return s;
        return {
          ...s,
          items: s.items.map(item => {
            if (item.id !== itemId) return item;
            return {
              ...item,
              photos: [
                ...(item.photos || []),
                ...tempEntries.map(e => ({ id: e.clientId, url: e.blobUrl, uploaded_at: new Date().toISOString(), uploaded_by_name: '' })),
              ],
            };
          }),
        };
      });
      return { ...prev, stages: updatedStages };
    });

    let successCount = 0;
    let failedIds = [];
    for (const entry of tempEntries) {
      try {
        await qcService.uploadPhoto(runId, itemId, entry.file);
        successCount++;
        setUploadingItems(prev => {
          const cur = prev[itemId];
          if (!cur) return prev;
          return {
            ...prev,
            [itemId]: {
              ...cur,
              completed: cur.completed + 1,
              files: cur.files.map(f => f.client_id === entry.clientId ? { ...f, status: 'success' } : f),
            },
          };
        });
      } catch (err) {
        failedIds.push(entry.clientId);
        const errorCode = !err.response ? 'network' : (err.response?.status || 'unknown');
        setUploadingItems(prev => {
          const cur = prev[itemId];
          if (!cur) return prev;
          return {
            ...prev,
            [itemId]: {
              ...cur,
              failed: cur.failed + 1,
              files: cur.files.map(f => f.client_id === entry.clientId ? { ...f, status: 'failed', error_code: errorCode } : f),
            },
          };
        });
        if (!err.response) {
          toast.error('שגיאת רשת — נסה שוב');
        }
      }
      URL.revokeObjectURL(entry.blobUrl);
    }

    if (failedIds.length > 0) {
      setRunData(prev => {
        if (!prev) return prev;
        const rolledBack = prev.stages.map(s => {
          if (s.id !== stageId) return s;
          return {
            ...s,
            items: s.items.map(item => {
              if (item.id !== itemId) return item;
              return {
                ...item,
                photos: (item.photos || []).filter(p => !failedIds.includes(p.id)),
              };
            }),
          };
        });
        return { ...prev, stages: rolledBack };
      });
      toast.error(`${failedIds.length} תמונות נכשלו בהעלאה`);
    }
    if (successCount > 0) {
      toast.success(successCount === 1 ? 'תמונה הועלתה' : `${successCount} תמונות הועלו`);
      const scrollY = window.scrollY;
      const gen = ++softLoadGeneration.current;
      try {
        const result = await qcService.getRun(runId);
        if (softLoadGeneration.current === gen) {
          setRunData(result);
          requestAnimationFrame(() => {
            window.scrollTo({ top: scrollY, behavior: 'auto' });
          });
        }
      } catch (_syncErr) {}
    }

    setUploadingItems(prev => {
      const cur = prev[itemId];
      if (!cur) return prev;
      const hasActiveOrFailed = cur.files.some(f => f.status === 'uploading' || f.status === 'failed');
      if (!hasActiveOrFailed) {
        const next = { ...prev };
        delete next[itemId];
        return next;
      }
      const stillActive = cur.files.some(f => f.status === 'uploading');
      if (!stillActive) {
        const hasFailed = cur.files.some(f => f.status === 'failed');
        if (!hasFailed) {
          const next = { ...prev };
          delete next[itemId];
          return next;
        }
      }
      return prev;
    });
  };

  const handleRetryUpload = async (itemId, clientId) => {
    const uploadEntry = uploadingItems[itemId]?.files?.find(f => f.client_id === clientId);
    if (!uploadEntry || !uploadEntry._file) return;

    const file = uploadEntry._file;
    const scrollY = window.scrollY;

    setUploadingItems(prev => {
      const cur = prev[itemId];
      if (!cur) return prev;
      return {
        ...prev,
        [itemId]: {
          ...cur,
          failed: Math.max(0, cur.failed - 1),
          files: cur.files.map(f => f.client_id === clientId ? { ...f, status: 'uploading', error_code: undefined } : f),
        },
      };
    });

    try {
      await qcService.uploadPhoto(runId, itemId, file);
      setUploadingItems(prev => {
        const cur = prev[itemId];
        if (!cur) return prev;
        const updated = {
          ...prev,
          [itemId]: {
            ...cur,
            completed: cur.completed + 1,
            files: cur.files.map(f => f.client_id === clientId ? { ...f, status: 'success', _file: undefined } : f),
          },
        };
        const hasActiveOrFailed = updated[itemId].files.some(f => f.status === 'uploading' || f.status === 'failed');
        if (!hasActiveOrFailed) {
          delete updated[itemId];
        }
        return updated;
      });
      toast.success('תמונה הועלתה');
      const gen = ++softLoadGeneration.current;
      try {
        const result = await qcService.getRun(runId);
        if (softLoadGeneration.current === gen) {
          setRunData(result);
          requestAnimationFrame(() => {
            window.scrollTo({ top: scrollY, behavior: 'auto' });
          });
        }
      } catch (_syncErr) {}
    } catch (err) {
      const errorCode = !err.response ? 'network' : (err.response?.status || 'unknown');
      setUploadingItems(prev => {
        const cur = prev[itemId];
        if (!cur) return prev;
        return {
          ...prev,
          [itemId]: {
            ...cur,
            failed: cur.failed + 1,
            files: cur.files.map(f => f.client_id === clientId ? { ...f, status: 'failed', error_code: errorCode } : f),
          },
        };
      });
      if (!err.response) {
        toast.error('שגיאת רשת — נסה שוב');
      } else {
        toast.error('העלאה נכשלה — נסה שוב');
      }
    }
  };

  const handleRejectItem = async (itemId, reason) => {
    try {
      const result = await qcService.rejectItem(runId, itemId, { reason });
      if (result?.returned_to?.user_name) {
        toast.success(`הסעיף נדחה — הודעה נשלחה ל${result.returned_to.user_name}`);
      } else {
        toast.success('הסעיף נדחה');
      }
      setLastRejectedItemId(itemId);
      await softLoad(itemId);
      loadTimeline();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בדחיית הסעיף');
      throw err;
    }
  };

  const handleSubmitStage = async () => {
    if (!runId) return;
    if (hasActiveUploads) {
      toast.error('ממתין לסיום העלאות');
      return;
    }
    if (hasChanges) {
      toast.error('יש שינויים שלא נשמרו — שמור קודם');
      return;
    }
    setValidationErrors([]);
    setSubmitting(true);
    try {
      await qcService.submitStage(runId, stageId);
      toast.success('השלב הוגש לאישור בהצלחה');
      await load();
      loadTimeline();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object' && detail.error_code === 'QC_REJECTED_ITEMS_PENDING') {
        toast.error(detail.message, { duration: 6000 });
        await load();
      } else if (typeof detail === 'object' && detail.errors && Array.isArray(detail.errors)) {
        setValidationErrors(detail.errors);
        toast.error(detail.message || 'לא ניתן לשלוח — יש שדות חסרים', { duration: 5000 });
      } else {
        toast.error('שגיאה בשליחה: ' + (typeof detail === 'string' ? detail : err.message));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const itemStats = useMemo(() => {
    if (!stage) return { missingPhotos: 0, missingNotes: 0, unmarked: 0, rejectedItems: 0, failCount: 0, firstMissingId: null, firstRejectedId: null, firstFailId: null, firstPassId: null, firstUnmarkedId: null };
    let missingPhotos = 0, missingNotes = 0, unmarked = 0, rejectedItems = 0, failItems = 0;
    let firstMissingId = null, firstRejectedId = null, firstFailId = null, firstPassId = null, firstUnmarkedId = null;

    for (const item of stage.items) {
      const local = localChanges[item.id];
      const status = local?.status ?? item.status;
      const note = local?.note ?? item.note ?? '';

      if (item.reviewer_rejection) {
        rejectedItems++;
        if (!firstRejectedId) firstRejectedId = item.id;
        if (!firstMissingId) firstMissingId = item.id;
      }
      if (status === 'pass') {
        if (!firstPassId) firstPassId = item.id;
      }
      if (status === 'fail') {
        failItems++;
        if (!firstFailId) firstFailId = item.id;
      }
      if (status === 'pending') {
        unmarked++;
        if (!firstUnmarkedId) firstUnmarkedId = item.id;
        if (!firstMissingId) firstMissingId = item.id;
        continue;
      }
      if (item.required_photo && (!item.photos || item.photos.length === 0)) {
        missingPhotos++;
        if (!firstMissingId) firstMissingId = item.id;
      }
      if (status === 'fail' && !(note || '').trim()) {
        missingNotes++;
        if (!firstMissingId) firstMissingId = item.id;
      }
    }

    return { missingPhotos, missingNotes, unmarked, rejectedItems, failCount: failItems, firstMissingId, firstRejectedId, firstFailId, firstPassId, firstUnmarkedId };
  }, [stage, localChanges]);

  const submitBlockers = useMemo(() => {
    if (!stage) return { canSubmit: false, ...itemStats };
    if (stage.computed_status === 'pending_review' || stage.computed_status === 'approved') {
      return { canSubmit: false, ...itemStats };
    }
    const canSubmit = itemStats.missingPhotos === 0 && itemStats.missingNotes === 0 && itemStats.unmarked === 0 && itemStats.rejectedItems === 0;
    return { canSubmit, ...itemStats };
  }, [stage, itemStats]);

  const filteredItems = useMemo(() => {
    if (!stage) return [];
    const items = stage.items;
    switch (activeFilter) {
      case 'pass':
        return items.filter(i => (localChanges[i.id]?.status ?? i.status) === 'pass');
      case 'unmarked':
        return items.filter(i => (localChanges[i.id]?.status ?? i.status) === 'pending');
      case 'fail':
        return items.filter(i => (localChanges[i.id]?.status ?? i.status) === 'fail');
      case 'rejected':
        return items.filter(i => !!i.reviewer_rejection);
      case 'missing_photo':
        return items.filter(i => i.required_photo && (!i.photos || i.photos.length === 0));
      case 'missing_note':
        return items.filter(i => {
          const s = localChanges[i.id]?.status ?? i.status;
          const n = localChanges[i.id]?.note ?? i.note ?? '';
          return s === 'fail' && !(n || '').trim();
        });
      case 'problems':
        return items.filter(i => {
          if (i.reviewer_rejection) return true;
          const s = localChanges[i.id]?.status ?? i.status;
          const n = localChanges[i.id]?.note ?? i.note ?? '';
          if (s === 'pending') return true;
          if (i.required_photo && (!i.photos || i.photos.length === 0)) return true;
          if (s === 'fail' && !(n || '').trim()) return true;
          return false;
        });
      default:
        return items;
    }
  }, [stage, activeFilter, localChanges]);

  const scrollToItem = useCallback((itemId) => {
    if (!itemId) return;
    if (activeFilter !== 'all') setActiveFilter('all');
    setTimeout(() => {
      const ref = itemRefs.current[itemId];
      if (ref) {
        const headerOffset = 110;
        const y = ref.getBoundingClientRect().top + window.scrollY - headerOffset;
        window.scrollTo({ top: y, behavior: 'smooth' });
        setHighlightedItemId(itemId);
        setTimeout(() => setHighlightedItemId(null), 3000);
      }
    }, activeFilter !== 'all' ? 100 : 0);
  }, [activeFilter]);

  const scrollToFirstMissing = () => scrollToItem(submitBlockers.firstMissingId);

  const handleCountClick = useCallback((filterKey, firstItemId) => {
    setActiveFilter(prev => {
      const isTogglingOff = prev === filterKey;
      const nextFilter = isTogglingOff ? 'all' : filterKey;
      if (!isTogglingOff && firstItemId) {
        setTimeout(() => {
          const ref = itemRefs.current[firstItemId];
          if (ref) {
            const headerOffset = 110;
            const y = ref.getBoundingClientRect().top + window.scrollY - headerOffset;
            window.scrollTo({ top: y, behavior: 'smooth' });
            setHighlightedItemId(firstItemId);
            setTimeout(() => setHighlightedItemId(null), 3000);
          }
        }, 150);
      }
      return nextFilter;
    });
  }, []);

  const scrollToNextItem = useCallback((filterFn) => {
    if (!stage) return;
    const matching = stage.items.filter(filterFn);
    if (matching.length === 0) return;
    scrollToItem(matching[0].id);
  }, [stage, scrollToItem]);

  const goBack = () => {
    if (returnToPath) {
      navigate(returnToPath);
    } else if (window.history.length > 2) {
      navigate(-1);
    } else {
      navigate(`/projects/${projectId}/floors/${floorId}`);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="text-center">
          <p className="text-red-500 mb-3">{error}</p>
          <button onClick={goBack} className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm">חזרה לקומה</button>
        </div>
      </div>
    );
  }

  if (!stage) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="text-center">
          <p className="text-slate-500 mb-3">שלב לא נמצא</p>
          <button onClick={goBack} className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm">חזרה לקומה</button>
        </div>
      </div>
    );
  }

  const pct = stage.total > 0 ? Math.round((stage.done / stage.total) * 100) : 0;
  const passCount = stage.pass_count || 0;
  const failCount = stage.fail_count || 0;
  const pendingCount = stage.pending_count || 0;
  const statusBadge = STAGE_STATUS_BADGES[stage.computed_status] || STAGE_STATUS_BADGES.draft;
  const visualStatus = getStageVisualStatus(stage);
  const qualityBadge = getQualityBadge(stage);
  const reviewBadge = getReviewBadge(stage);

  const canSubmitOrEdit = !isLocked && !isApproved;
  const showReopen = (isApproved || isRejected) && isPM;

  const buildBlockerText = () => {
    const parts = [];
    if (submitBlockers.rejectedItems > 0) parts.push(`${submitBlockers.rejectedItems} סעיפים נדחו בביקורת`);
    if (submitBlockers.unmarked > 0) parts.push(`${submitBlockers.unmarked} סעיפים לא סומנו`);
    if (submitBlockers.missingPhotos > 0) parts.push(`חסרות תמונות ב-${submitBlockers.missingPhotos} סעיפים`);
    if (submitBlockers.missingNotes > 0) parts.push(`חסרות הערות ב-${submitBlockers.missingNotes} סעיפים`);
    return parts.join(', ');
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-48">
      <div className="bg-slate-800 text-white sticky top-0 z-30">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button onClick={goBack} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
                <ArrowRight className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-base font-bold flex items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-amber-400" />
                  {isUnitMode && unitName ? `${stage.title} — ${unitName}` : stage.title}
                </h1>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  {(stage.pre_work_documentation || stage.has_prework_items) && (
                    <span className="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                      <FileText className="w-3 h-3" />
                      {stage.pre_work_documentation ? 'תיעוד לפני עבודה' : 'כולל תיעוד לפני עבודה'}
                    </span>
                  )}
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${qualityBadge.color}`}>
                    איכות: {qualityBadge.label}
                  </span>
                  {reviewBadge && (
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${reviewBadge.color}`}>
                      {reviewBadge.label}
                    </span>
                  )}
                  {runData?.building_name && (
                    <span className="text-[10px] text-slate-400">{runData.building_name} / {runData.floor_name}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => { load(); loadTimeline(); }} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors">
                <RefreshCw className="w-4 h-4" />
              </button>
              <div className="text-left">
                <div className={`text-lg font-bold ${visualStatus.pctColor}`}>{pct}%</div>
                <div className="text-[10px] text-slate-400">{stage.done}/{stage.total}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {isLocked && approverStatus !== null && (
        <div className="max-w-2xl mx-auto px-4 mt-3 space-y-2.5">
          {canApproveThis ? (
            <div className="bg-blue-50 border border-blue-200 rounded-xl px-3.5 py-3">
              <div className="flex items-center gap-2 text-blue-800 font-bold text-sm">
                <ShieldCheck className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <span>ממתין לאישור שלך</span>
              </div>
              <p className="text-xs text-blue-600/80 mt-1 leading-relaxed" dir="rtl">
                {approverStatus.is_pm_implicit ? 'מאשר ברירת מחדל. ' : ''}
                ניתן לאשר, לדחות שלב, או לדחות סעיפים בודדים.
              </p>
            </div>
          ) : (
            <div className="bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-3">
              <div className="flex items-center gap-2 text-slate-700 font-bold text-sm">
                <Info className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span>ממתין לאישור</span>
              </div>
              <p className="text-xs text-slate-500 mt-1" dir="rtl">
                {approverStatus.reason_code === 'role_not_allowed'
                  ? 'קבלנים אינם יכולים לאשר שלבי בקרת ביצוע.'
                  : approverStatus.reason_code === 'not_configured'
                    ? 'אין לך הרשאת אישור לשלב זה.'
                    : 'ממתין לאישור מנהל פרויקט / מאשרי בקרת ביצוע.'}
              </p>
              {approverStatus.can_manage_approvers && (
                <button
                  onClick={() => navigate(`/projects/${projectId}/control?tab=settings`)}
                  className="flex items-center justify-center gap-1.5 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 active:bg-amber-200 border border-amber-200 rounded-xl px-3 py-2.5 mt-2.5 min-h-[44px] w-full transition-all"
                >
                  <Settings className="w-3.5 h-3.5" />
                  ניהול מאשרי בקרת ביצוע
                </button>
              )}
            </div>
          )}

          {approverStatus.active_approvers_for_stage && (
            Array.isArray(approverStatus.active_approvers_for_stage) && approverStatus.active_approvers_for_stage.length > 0 ? (
              <ApproverInfoCard
                approvers={approverStatus.active_approvers_for_stage}
                stageId={stageId}
                canManage={approverStatus.can_manage_approvers}
                projectId={projectId}
                navigate={navigate}
              />
            ) : !Array.isArray(approverStatus.active_approvers_for_stage) && (approverStatus.active_approvers_for_stage.pm_count > 0 || approverStatus.active_approvers_for_stage.explicit_count > 0) ? (
              <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
                <div className="flex items-center gap-2 text-slate-700 font-bold text-xs mb-2">
                  <Users className="w-4 h-4 text-slate-500" />
                  מי מאשר שלב זה?
                </div>
                <div className="flex flex-wrap gap-2">
                  {approverStatus.active_approvers_for_stage.pm_count > 0 && (
                    <span className="text-xs px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">
                      {approverStatus.active_approvers_for_stage.pm_count} מנהלי פרויקט
                    </span>
                  )}
                  {approverStatus.active_approvers_for_stage.explicit_count > 0 && (
                    <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                      {approverStatus.active_approvers_for_stage.explicit_count} מאשרים נוספים
                    </span>
                  )}
                </div>
              </div>
            ) : null
          )}
        </div>
      )}

      {canSubmitOrEdit && !submitBlockers.canSubmit && (
        <>
          <div className="sticky top-[52px] z-20 bg-white/95 backdrop-blur-sm border-b border-amber-200 shadow-sm">
            <div className="max-w-2xl mx-auto px-4 py-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">{stage.done}/{stage.total} סעיפים הושלמו</span>
                <div className="flex gap-2">
                  {submitBlockers.firstMissingId && (
                    <button onClick={scrollToFirstMissing}
                      className="flex items-center gap-1.5 text-xs font-medium text-amber-800 bg-amber-100 hover:bg-amber-200 rounded-lg px-2.5 py-1.5 transition-all">
                      <Navigation className="w-3.5 h-3.5" />
                      לסעיף חסר
                    </button>
                  )}
                  <button onClick={() => setActiveFilter(f => f === 'problems' ? 'all' : 'problems')}
                    className={`flex items-center gap-1.5 text-xs font-medium rounded-lg px-2.5 py-1.5 transition-all ${
                      activeFilter === 'problems'
                        ? 'text-white bg-slate-700 hover:bg-slate-800'
                        : 'text-slate-600 bg-slate-100 hover:bg-slate-200'
                    }`}>
                    {activeFilter === 'problems' ? <Eye className="w-3.5 h-3.5" /> : <Filter className="w-3.5 h-3.5" />}
                    {activeFilter === 'problems' ? 'הצג הכל' : 'רק חסרים'}
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div className="h-[44px]" />
        </>
      )}

      <div className="max-w-2xl mx-auto px-4 py-4 space-y-3">
        <div className={`bg-white rounded-xl border p-3 shadow-sm ${visualStatus.borderColor}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-600">התקדמות שלב</span>
            <span className="text-sm font-bold text-slate-700">{pct}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 mb-2">
            <div className={`h-2 rounded-full transition-all ${visualStatus.barColor}`}
              style={{ width: `${pct}%` }} />
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
            <button onClick={() => handleCountClick('pass', itemStats.firstPassId)}
              className={`rounded-md p-1.5 transition-all cursor-pointer ${activeFilter === 'pass' ? 'ring-2 ring-emerald-400 bg-emerald-100' : 'bg-emerald-50 hover:bg-emerald-100 active:bg-emerald-200'}`}>
              <span className="font-bold text-emerald-600 text-sm">{passCount}</span>
              <span className="block text-emerald-600">תקין</span>
            </button>
            <button onClick={() => handleCountClick('fail', itemStats.firstFailId)}
              className={`rounded-md p-1.5 transition-all cursor-pointer ${activeFilter === 'fail' ? 'ring-2 ring-red-400 bg-red-100' : 'bg-red-50 hover:bg-red-100 active:bg-red-200'}`}>
              <span className="font-bold text-red-600 text-sm">{failCount}</span>
              <span className="block text-red-600">לא תקין</span>
            </button>
            <button onClick={() => handleCountClick('unmarked', itemStats.firstUnmarkedId)}
              className={`rounded-md p-1.5 transition-all cursor-pointer ${activeFilter === 'unmarked' ? 'ring-2 ring-slate-400 bg-slate-200' : 'bg-slate-50 hover:bg-slate-100 active:bg-slate-200'}`}>
              <span className="font-bold text-slate-500 text-sm">{pendingCount}</span>
              <span className="block text-slate-500">ממתין</span>
            </button>
          </div>
        </div>

        {timelineData?.audit_summary && (
          <AuditSummaryCard auditSummary={timelineData.audit_summary} canSeeFull={timelineData.can_see_full} />
        )}

        {isRejected && (canApproveThis || isPM) && (
          <button
            onClick={() => setWhatsAppModal({
              itemId: null,
              rejectionContext: {
                stageTitle: stage?.title,
                reason: timelineData?.audit_summary?.rejected_reason || '',
                buildingName: runData?.building_name,
                floorName: runData?.floor_name,
              },
            })}
            className="w-full flex items-center justify-center gap-2 text-sm font-semibold text-green-700 bg-green-50 hover:bg-green-100 active:bg-green-200 border border-green-200 rounded-xl px-3 py-3 min-h-[48px] transition-all shadow-sm"
            dir="rtl"
          >
            <Phone className="w-4 h-4" />
            שלח הודעת דחייה ב-WhatsApp
          </button>
        )}

        {timeSinceSave && (
          <div className="flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <CheckCircle2 className="w-3 h-3" />
            <span>נשמר {timeSinceSave}</span>
          </div>
        )}

        {(canApproveThis || isPM) && isLocked && (
          <div className="bg-white rounded-xl border border-amber-200 p-3 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Eye className="w-4 h-4 text-amber-600" />
              <span className="text-xs font-bold text-slate-700">סקירת סעיפים</span>
            </div>
            <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] mb-2">
              <button onClick={() => handleCountClick('unmarked', itemStats.firstUnmarkedId)}
                className={`rounded-md p-1.5 transition-all cursor-pointer ${activeFilter === 'unmarked' ? 'ring-2 ring-slate-400 bg-slate-200' : 'bg-slate-50 hover:bg-slate-100 active:bg-slate-200'}`}>
                <span className="font-bold text-slate-600 text-sm">{pendingCount}</span>
                <span className="block text-slate-500">ממתינים</span>
              </button>
              <button onClick={() => handleCountClick('fail', itemStats.firstFailId)}
                className={`rounded-md p-1.5 transition-all cursor-pointer ${activeFilter === 'fail' ? 'ring-2 ring-red-400 bg-red-100' : 'bg-red-50 hover:bg-red-100 active:bg-red-200'}`}>
                <span className="font-bold text-red-600 text-sm">{failCount}</span>
                <span className="block text-red-500">לא תקין</span>
              </button>
              <button onClick={() => handleCountClick('rejected', itemStats.firstRejectedId)}
                className={`rounded-md p-1.5 transition-all cursor-pointer ${activeFilter === 'rejected' ? 'ring-2 ring-orange-400 bg-orange-100' : 'bg-orange-50 hover:bg-orange-100 active:bg-orange-200'}`}>
                <span className="font-bold text-orange-600 text-sm">{itemStats.rejectedItems}</span>
                <span className="block text-orange-500">נדחו</span>
              </button>
            </div>
            <div className="flex gap-1.5">
              {itemStats.rejectedItems > 0 && (
                <button onClick={() => scrollToItem(itemStats.firstRejectedId)}
                  className="flex-1 flex items-center justify-center gap-1 text-[11px] font-medium text-orange-700 bg-orange-50 border border-orange-200 rounded-lg py-1.5 min-h-[36px] active:bg-orange-100">
                  <Navigation className="w-3 h-3" />
                  לסעיף שנדחה
                </button>
              )}
              {itemStats.failCount > 0 && (
                <button onClick={() => scrollToItem(itemStats.firstFailId)}
                  className="flex-1 flex items-center justify-center gap-1 text-[11px] font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg py-1.5 min-h-[36px] active:bg-red-100">
                  <Navigation className="w-3 h-3" />
                  לסעיף לא תקין
                </button>
              )}
              <button onClick={() => setActiveFilter(f => f === 'problems' ? 'all' : 'problems')}
                className={`flex-1 flex items-center justify-center gap-1 text-[11px] font-medium rounded-lg py-1.5 min-h-[36px] border transition-all ${
                  activeFilter === 'problems'
                    ? 'bg-slate-700 text-white border-slate-700'
                    : 'text-slate-600 bg-slate-50 border-slate-200 active:bg-slate-100'
                }`}>
                <Filter className="w-3 h-3" />
                {activeFilter === 'problems' ? 'הצג הכל' : 'רק בעיות'}
              </button>
            </div>
          </div>
        )}

        <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
          {[
            { key: 'all', label: 'הכל', count: stage?.items?.length || 0 },
            { key: 'pass', label: 'תקין', count: passCount, color: 'text-emerald-600' },
            { key: 'unmarked', label: 'לא סומן', count: itemStats.unmarked, color: 'text-slate-600' },
            { key: 'fail', label: 'לא תקין', count: itemStats.failCount, color: 'text-red-600' },
            { key: 'rejected', label: 'נדחו', count: itemStats.rejectedItems, color: 'text-orange-600' },
            { key: 'missing_photo', label: 'חסרה תמונה', count: itemStats.missingPhotos, color: 'text-amber-600' },
            { key: 'missing_note', label: 'חסרה הערה', count: itemStats.missingNotes, color: 'text-amber-600' },
          ].filter(f => f.key === 'all' || f.count > 0).map(f => (
            <button key={f.key} onClick={() => setActiveFilter(f.key)}
              className={`flex items-center gap-1 whitespace-nowrap text-[11px] font-medium rounded-full px-2.5 py-1.5 min-h-[32px] border transition-all ${
                activeFilter === f.key
                  ? 'bg-slate-700 text-white border-slate-700'
                  : 'bg-white text-slate-600 border-slate-200 active:bg-slate-50'
              }`}>
              {f.label}
              <span className={`text-[10px] font-bold ${activeFilter === f.key ? 'text-white/80' : (f.color || 'text-slate-400')}`}>{f.count}</span>
            </button>
          ))}
        </div>

        {activeFilter !== 'all' && (
          <div className="flex items-center justify-between bg-slate-100 rounded-lg px-3 py-1.5">
            <span className="text-[11px] text-slate-600 font-medium">
              {filteredItems.length} מתוך {stage.items.length}
            </span>
            <button onClick={() => setActiveFilter('all')}
              className="text-[11px] text-amber-600 hover:text-amber-700 active:text-amber-800 font-medium">
              הצג הכל
            </button>
          </div>
        )}

        {activeFilter !== 'all' && filteredItems.length === 0 && (
          <div className="text-center py-6">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-1" />
            <p className="text-sm font-medium text-slate-600">אין סעיפים בקטגוריה זו</p>
            <button onClick={() => setActiveFilter('all')}
              className="mt-1 text-xs text-amber-600 hover:text-amber-700 underline">הצג הכל</button>
          </div>
        )}

        {lastRejectedItemId && (canApproveThis || isPM) && (
          <div className="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
            <ShieldX className="w-4 h-4 text-orange-500 flex-shrink-0" />
            <span className="text-xs text-orange-700 font-medium flex-1">הסעיף נדחה בהצלחה</span>
            <div className="flex gap-1.5">
              {itemStats.rejectedItems > 1 && (
                <button onClick={() => { setActiveFilter('rejected'); setLastRejectedItemId(null); }}
                  className="text-[11px] font-medium text-orange-700 bg-white border border-orange-200 rounded-lg px-2.5 py-1.5 min-h-[32px] active:bg-orange-100">
                  סנן נדחים ({itemStats.rejectedItems})
                </button>
              )}
              <button onClick={() => { setLastRejectedItemId(null); }}
                className="text-[11px] text-slate-400 px-1.5 py-1.5 min-h-[32px]">
                <XCircle className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {pct === 100 && pendingCount === 0 && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-center shadow-sm animate-pulse" style={{ animationDuration: '2s', animationIterationCount: '3' }}>
            <div className="text-sm font-bold text-emerald-700">✅ שלב הושלם! כל הסעיפים הושלמו</div>
            <div className="text-xs text-emerald-600 mt-0.5">{failCount > 0 ? `${failCount} לא תקין — תקן לפני שליחה` : 'ניתן לשלוח לאישור'}</div>
          </div>
        )}

        {pct < 100 && pendingCount > 0 && pendingCount <= 3 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 text-center">
            <span className="text-sm font-bold text-amber-700">🎯 עוד {pendingCount} סעיפים!</span>
          </div>
        )}

        <div className="space-y-2">
          {filteredItems.map(item => (
            <StageItemRow
              key={item.id}
              ref={el => { itemRefs.current[item.id] = el; }}
              item={item}
              canEdit={runData?.can_edit}
              isLocked={isLocked || isApproved}
              localState={localChanges[item.id]}
              onToggle={handleToggle}
              onNoteChange={handleNoteChange}
              onUploadPhotos={handleUploadPhotos}
              uploadState={uploadingItems[item.id] || null}
              onRetryUpload={(clientId) => handleRetryUpload(item.id, clientId)}
              itemErrors={validationErrors.filter(e => e.item_id === item.id)}
              isHighlighted={highlightedItemId === item.id}
              isGreenFlash={!!flashItems[item.id]}
              isPendingReview={isLocked}
              canApproveThis={canApproveThis || isPM}
              onRejectItem={handleRejectItem}
              canSendWhatsApp={canApproveThis || isPM}
              onWhatsAppCta={(itemIdForWa, itemTitle, reason) => setWhatsAppModal({
                itemId: itemIdForWa,
                rejectionContext: {
                  stageTitle: stage?.title,
                  itemTitle,
                  reason,
                  buildingName: runData?.building_name,
                  floorName: runData?.floor_name,
                },
              })}
            />
          ))}
        </div>

        {timelineData?.timeline && timelineData.timeline.length > 0 && (
          <TimelineCard timeline={timelineData.timeline} canSeeFull={timelineData.can_see_full} defaultExpanded={canApproveThis || isPM} />
        )}
      </div>

      <DialogPrimitive.Root open={showRejectModal} onOpenChange={setShowRejectModal}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <DialogPrimitive.Content className="fixed inset-x-0 bottom-0 sm:inset-0 z-50 sm:flex sm:items-center sm:justify-center outline-none">
            <div className="bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-md sm:mx-auto">
              <DialogPrimitive.Title className="sr-only">דחיית שלב</DialogPrimitive.Title>
              <DialogPrimitive.Description className="sr-only">טופס דחיית שלב בקרה</DialogPrimitive.Description>
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <ShieldX className="w-4 h-4 text-red-500" />
                  דחיית שלב
                </h3>
                <DialogPrimitive.Close asChild>
                  <button className="p-1 hover:bg-slate-100 rounded-lg">
                    <XCircle className="w-5 h-5 text-slate-400" />
                  </button>
                </DialogPrimitive.Close>
              </div>
              <div className="p-4 space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">סיבת הדחייה</label>
                  <textarea
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    placeholder="פרט את סיבת הדחייה..."
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-200 focus:border-red-300"
                    rows={3}
                    dir="rtl"
                  />
                </div>
                <div className="flex gap-2">
                  <DialogPrimitive.Close asChild>
                    <button
                      className="flex-1 py-2.5 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 active:bg-slate-100 min-h-[44px]">
                      ביטול
                    </button>
                  </DialogPrimitive.Close>
                  <button onClick={handleReject} disabled={rejecting || !rejectReason.trim()}
                    className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all min-h-[44px] ${
                      rejectReason.trim() ? 'bg-red-500 hover:bg-red-600 active:bg-red-700 text-white' : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                    }`}>
                    {rejecting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'דחה שלב'}
                  </button>
                </div>
              </div>
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <DialogPrimitive.Root open={showReopenModal} onOpenChange={setShowReopenModal}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <DialogPrimitive.Content className="fixed inset-x-0 bottom-0 sm:inset-0 z-50 sm:flex sm:items-center sm:justify-center outline-none">
            <div className="bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-md sm:mx-auto">
              <DialogPrimitive.Title className="sr-only">פתיחה מחדש של שלב</DialogPrimitive.Title>
              <DialogPrimitive.Description className="sr-only">טופס פתיחה מחדש של שלב בקרה</DialogPrimitive.Description>
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <RotateCcw className="w-4 h-4 text-orange-500" />
                  פתיחה מחדש של שלב
                </h3>
                <DialogPrimitive.Close asChild>
                  <button className="p-1 hover:bg-slate-100 rounded-lg">
                    <XCircle className="w-5 h-5 text-slate-400" />
                  </button>
                </DialogPrimitive.Close>
              </div>
              <div className="p-4 space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">סיבת פתיחה מחדש</label>
                  <textarea
                    value={reopenReason}
                    onChange={e => setReopenReason(e.target.value)}
                    placeholder="פרט את סיבת הפתיחה מחדש..."
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-orange-200 focus:border-orange-300"
                    rows={3}
                    dir="rtl"
                  />
                </div>
                <div className="flex gap-2">
                  <DialogPrimitive.Close asChild>
                    <button
                      className="flex-1 py-2.5 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 active:bg-slate-100 min-h-[44px]">
                      ביטול
                    </button>
                  </DialogPrimitive.Close>
                  <button onClick={handleReopen} disabled={reopening || !reopenReason.trim()}
                    className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all min-h-[44px] ${
                      reopenReason.trim() ? 'bg-orange-500 hover:bg-orange-600 active:bg-orange-700 text-white' : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                    }`}>
                    {reopening ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'פתח מחדש'}
                  </button>
                </div>
              </div>
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      {(runData?.can_edit || isLocked || isApproved || isRejected || isReopened) && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-sm border-t border-slate-200 shadow-lg"
          style={{ paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}>
          <div className="max-w-2xl mx-auto px-4 pt-2 space-y-1.5">
            {(passCount + failCount) > 0 && (
              <div className="flex items-center justify-center gap-1.5 text-xs text-slate-500 py-0.5">
                <span className="font-medium">{passCount + failCount}/{stage.total} סעיפים הושלמו</span>
              </div>
            )}
            {validationErrors.length > 0 && (
              <div className="bg-red-50 border border-red-300 rounded-lg px-2.5 py-1.5">
                <div className="flex items-center gap-1.5 text-red-700 font-bold text-[11px]">
                  <AlertCircle className="w-3 h-3 flex-shrink-0" />
                  <span>לא ניתן לשלוח — {validationErrors.length} שדות חסרים</span>
                </div>
                <ul className="mt-0.5 pr-4" dir="rtl">
                  {validationErrors.slice(0, 2).map((e, i) => (
                    <li key={i} className="text-[10px] text-red-600">• {e.reason}</li>
                  ))}
                  {validationErrors.length > 2 && (
                    <li className="text-[10px] text-red-500">...ועוד {validationErrors.length - 2}</li>
                  )}
                </ul>
              </div>
            )}

            {canSubmitOrEdit && !submitBlockers.canSubmit && !hasChanges && validationErrors.length === 0 && (() => {
              const totalBlockers = (submitBlockers.unmarked || 0) + (submitBlockers.missingPhotos || 0) + (submitBlockers.missingNotes || 0) + (submitBlockers.rejectedItems || 0);
              return (
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <AlertCircle className="w-3 h-3 text-amber-600 flex-shrink-0" />
                      <span className="text-[11px] font-medium text-amber-800 truncate">
                        {totalBlockers} סעיפים חסרים
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <span className="text-[10px] bg-amber-200 text-amber-800 font-bold px-1.5 py-0.5 rounded-full">{totalBlockers}</span>
                      {submitBlockers.firstMissingId && (
                        <button onClick={scrollToFirstMissing}
                          className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-800 bg-amber-100 hover:bg-amber-200 rounded-md px-2.5 py-1 transition-all">
                          <Navigation className="w-3 h-3" />
                          לסעיף
                        </button>
                      )}
                      {activeFilter === 'all' && totalBlockers > 0 && (
                        <button onClick={() => setActiveFilter('problems')}
                          className="inline-flex items-center gap-1 text-[10px] font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-md px-2.5 py-1 transition-all">
                          <Filter className="w-3 h-3" />
                          חסרים
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })()}

            {hasFailWithoutNote && hasChanges && (
              <div className="flex items-center gap-1.5 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-2">
                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                <span className="text-xs text-red-700 font-medium">סעיף מסומן לא תקין — חובה להוסיף הערה לפני שמירה</span>
              </div>
            )}

            <div className="flex gap-2">
              {canSubmitOrEdit && (
                <button onClick={handleSave} disabled={saving || !hasChanges || hasFailWithoutNote}
                  aria-label="שמור שינויים"
                  className={`flex-1 flex items-center justify-center gap-2 font-bold min-h-[48px] rounded-xl text-sm transition-all ${
                    hasChanges && !hasFailWithoutNote ? 'bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white shadow-sm' : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  }`}>
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {saving ? 'שומר...' : `שמור${hasChanges ? ` (${Object.keys(localChanges).length})` : ''}`}
                </button>
              )}

              {canSubmitOrEdit && (
                <button onClick={handleSubmitStage} disabled={submitting || !submitBlockers.canSubmit || hasChanges || hasActiveUploads}
                  aria-label="שלח לאישור"
                  title={hasActiveUploads ? 'ממתין לסיום העלאות' : undefined}
                  className={`flex-1 flex items-center justify-center gap-2 font-bold min-h-[48px] rounded-xl text-sm transition-all ${
                    submitBlockers.canSubmit && !hasChanges && !hasActiveUploads
                      ? 'bg-slate-700 hover:bg-slate-800 text-white shadow-sm'
                      : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  }`}>
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : hasActiveUploads ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  {submitting ? 'שולח...' : hasActiveUploads ? 'ממתין לסיום העלאות' : 'שלח לאישור'}
                </button>
              )}

              {isLocked && canApproveThis && (
                <div className="flex-1 flex flex-col gap-2">
                  {hasBlockingFailures && (
                    <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-center font-medium">
                      לא ניתן לאשר — יש {blockingFailCount} פריטים שנכשלו
                    </div>
                  )}
                  {isInconsistent && (
                    <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-center font-medium">
                      מצב לא עקבי — דורש תיקון
                    </div>
                  )}
                  <div className="flex gap-2">
                  <button onClick={handleApprove} disabled={approving || hasBlockingFailures}
                    aria-label="אשר שלב"
                    className={`flex-1 flex items-center justify-center gap-2 font-bold min-h-[48px] rounded-xl text-sm shadow-sm transition-all ${hasBlockingFailures ? 'bg-slate-300 text-slate-500 cursor-not-allowed' : 'bg-emerald-500 hover:bg-emerald-600 text-white'}`}>
                    {approving ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                    {approving ? 'מאשר...' : 'אשר שלב'}
                  </button>
                  <button onClick={() => setShowRejectModal(true)} disabled={rejecting}
                    aria-label="דחה שלב"
                    className="flex-1 flex items-center justify-center gap-2 font-bold min-h-[48px] rounded-xl text-sm bg-red-500 hover:bg-red-600 text-white shadow-sm transition-all">
                    <ShieldX className="w-4 h-4" />
                    דחה שלב
                  </button>
                  </div>
                </div>
              )}

              {isLocked && !canApproveThis && (
                <div className="flex-1 flex items-center justify-center gap-2 min-h-[48px] bg-slate-100 border border-slate-200 rounded-xl text-slate-600 text-sm font-bold">
                  <Lock className="w-4 h-4" />
                  ממתין לאישור
                </div>
              )}

              {showReopen && (
                <button onClick={() => setShowReopenModal(true)}
                  aria-label="פתח מחדש"
                  className="flex-1 flex items-center justify-center gap-2 font-bold min-h-[48px] rounded-xl text-sm bg-orange-500 hover:bg-orange-600 text-white shadow-sm transition-all">
                  <RotateCcw className="w-4 h-4" />
                  פתח מחדש
                </button>
              )}

              {isApproved && !isPM && (
                <div className="flex-1 flex items-center justify-center gap-2 min-h-[48px] bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-700 text-sm font-bold">
                  <ShieldCheck className="w-4 h-4" />
                  שלב אושר
                </div>
              )}

              {isRejected && !isPM && (
                <div className="flex-1 flex items-center justify-center gap-2 min-h-[48px] bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm font-bold">
                  <ShieldX className="w-4 h-4" />
                  שלב נדחה — ניתן לתקן ולשלוח שוב
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {whatsAppModal && (
        <WhatsAppRejectionModal
          runId={runId}
          stageId={stageId}
          itemId={whatsAppModal.itemId}
          rejectionContext={whatsAppModal.rejectionContext}
          onClose={() => setWhatsAppModal(null)}
        />
      )}
    </div>
  );
}
