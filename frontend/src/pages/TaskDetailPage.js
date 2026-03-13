import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { tCategory, tStatus, tPriority } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import { taskService, companyService, notificationService, projectService, tradeService } from '../services/api';
import { toast } from 'sonner';
import { compressImage } from '../utils/imageCompress';
import {
  ChevronRight, Building2, Layers, DoorOpen, Clock, User, Briefcase,
  MessageSquare, Paperclip, ArrowRight, Send, HardHat, Image as ImageIcon,
  Phone, RefreshCw, CheckCircle, XCircle, AlertTriangle, Bell,
  Upload, ShieldCheck, ShieldX, Camera, X, Download, Eye,
  Settings, ChevronDown, Lock, Edit3, CircleDot, ArrowDownCircle, ArrowUpCircle,
  Copy, Smartphone
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';

const STATUS_CONFIG = {
  open: { label: 'פתוח', color: 'bg-blue-100 text-blue-700', icon: CircleDot },
  assigned: { label: 'שויך', color: 'bg-purple-100 text-purple-700', icon: User },
  in_progress: { label: 'בביצוע', color: 'bg-amber-100 text-amber-700', icon: RefreshCw },
  waiting_verify: { label: 'ממתין לאימות', color: 'bg-orange-100 text-orange-700', icon: Eye },
  pending_contractor_proof: { label: 'ממתין להוכחת קבלן', color: 'bg-orange-100 text-orange-700', icon: Camera },
  pending_manager_approval: { label: 'ממתין לאישור מנהל', color: 'bg-indigo-100 text-indigo-700', icon: ShieldCheck },
  returned_to_contractor: { label: 'הוחזר לקבלן', color: 'bg-rose-100 text-rose-700', icon: ArrowDownCircle },
  closed: { label: 'סגור', color: 'bg-green-100 text-green-700', icon: CheckCircle },
  reopened: { label: 'נפתח מחדש', color: 'bg-red-100 text-red-700', icon: RefreshCw },
};

const PRIORITY_CONFIG = {
  low: { label: 'נמוך', color: 'bg-slate-100 text-slate-600' },
  medium: { label: 'בינוני', color: 'bg-blue-100 text-blue-600' },
  high: { label: 'גבוה', color: 'bg-amber-100 text-amber-600' },
  critical: { label: 'קריטי', color: 'bg-red-100 text-red-600' },
};

const NOTIF_STATUS_CONFIG = {
  queued: { label: 'בתור', color: 'text-blue-600', icon: Clock },
  skipped_dry_run: { label: 'דילוג (מצב בדיקה)', color: 'text-slate-500', icon: AlertTriangle },
  sent: { label: 'נשלח', color: 'text-amber-600', icon: Send },
  delivered: { label: 'התקבל', color: 'text-green-600', icon: CheckCircle },
  read: { label: 'נקרא', color: 'text-green-700', icon: CheckCircle },
  failed: { label: 'נכשל', color: 'text-red-600', icon: XCircle },
};

import { getNotifEventLabel } from '../utils/actionLabels';

const MGMT_ROLES = ['project_manager', 'management_team'];

const VALID_TRANSITIONS = {
  open: ['assigned', 'in_progress'],
  assigned: ['in_progress'],
  in_progress: ['waiting_verify', 'pending_contractor_proof'],
  waiting_verify: ['closed'],
  pending_contractor_proof: ['pending_manager_approval'],
  pending_manager_approval: ['closed', 'returned_to_contractor'],
  returned_to_contractor: ['in_progress', 'pending_contractor_proof'],
  closed: ['reopened'],
  reopened: ['in_progress', 'closed'],
};

const MANAGER_ALLOWED_STATUSES = [
  'open', 'assigned', 'in_progress', 'waiting_verify',
  'pending_contractor_proof', 'pending_manager_approval',
  'returned_to_contractor', 'closed', 'reopened'
];

const CATEGORIES = [
  'electrical', 'plumbing', 'hvac', 'painting', 'flooring', 'carpentry',
  'carpentry_kitchen', 'masonry', 'windows', 'doors', 'general',
  'bathroom_cabinets', 'finishes', 'structural', 'aluminum', 'metalwork', 'glazing'
];

const PRIORITIES = ['low', 'medium', 'high', 'critical'];

const RETURN_TO_KEY = 'taskDetailReturnTo';

const TIMELINE_EVENT_CONFIG = {
  status_change: { icon: RefreshCw, color: 'text-blue-600 bg-blue-100' },
  attachment: { icon: Camera, color: 'text-amber-600 bg-amber-100' },
  comment: { icon: MessageSquare, color: 'text-slate-600 bg-slate-100' },
  assignment: { icon: User, color: 'text-purple-600 bg-purple-100' },
};

const InlineSelect = ({ value, options, onChange, disabled, label }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-colors ${
          disabled ? 'bg-slate-50 text-slate-400 cursor-not-allowed border-slate-200' :
          'bg-white hover:bg-slate-50 cursor-pointer border-slate-300 hover:border-amber-400'
        }`}
      >
        <span>{label}</span>
        {!disabled && <ChevronDown className="w-3.5 h-3.5" />}
        {disabled && <Lock className="w-3 h-3" />}
      </button>
      {open && (
        <div className="absolute z-30 top-full mt-1 right-0 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto min-w-[160px]">
          {options.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              className={`w-full text-right px-3 py-2 text-sm hover:bg-amber-50 transition-colors ${
                opt.value === value ? 'bg-amber-100 font-medium' : ''
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const TaskDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [task, setTask] = useState(null);
  const [updates, setUpdates] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState('');
  const [sending, setSending] = useState(false);
  const [sendingWhatsApp, setSendingWhatsApp] = useState(false);
  const [imageModal, setImageModal] = useState(null);

  const [proofFiles, setProofFiles] = useState([]);
  const [proofNote, setProofNote] = useState('');
  const [submittingProof, setSubmittingProof] = useState(false);

  const [rejectReason, setRejectReason] = useState('');
  const [decidingApprove, setDecidingApprove] = useState(false);
  const [decidingReject, setDecidingReject] = useState(false);
  const [showRejectForm, setShowRejectForm] = useState(false);

  const [projectContractors, setProjectContractors] = useState([]);
  const [savingField, setSavingField] = useState(null);

  const [tradeMismatchModal, setTradeMismatchModal] = useState(null);
  const [errorState, setErrorState] = useState(null);
  const [externalEntry, setExternalEntry] = useState(false);

  const proofCameraRef = useRef(null);
  const proofGalleryRef = useRef(null);
  const uploadCameraRef = useRef(null);
  const uploadGalleryRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [id]);

  useEffect(() => {
    if (location.state?.returnTo) {
      sessionStorage.setItem(RETURN_TO_KEY, location.state.returnTo);
    } else {
      const source = sessionStorage.getItem('deepLinkSource');
      if (source === 'external') {
        sessionStorage.removeItem('deepLinkSource');
        setExternalEntry(true);
        console.log('[DEEP_LINK] TaskDetailPage: external entry for task', id);
      }
    }
  }, [location.state, id]);

  const projectRole = task?.user_project_role || 'none';
  const isManagement = MGMT_ROLES.includes(projectRole);
  const isContractor = projectRole === 'contractor' || user?.role === 'contractor';
  const isAssignee = task?.assignee_id === user?.id;
  const canManage = isManagement;
  const taskIsClosed = task?.status === 'closed';

  const loadTask = useCallback(async () => {
    try {
      const [taskData, updatesData, companiesData] = await Promise.all([
        taskService.get(id),
        taskService.getUpdates(id),
        companyService.list(),
      ]);
      setTask(taskData);
      setUpdates(updatesData);
      setCompanies(companiesData);

      if (MGMT_ROLES.includes(taskData.user_project_role)) {
        try {
          const [notifData, members] = await Promise.all([
            notificationService.getTimeline(id),
            projectService.getMemberships(taskData.project_id),
          ]);
          setNotifications(notifData);
          const contractors = members.filter(m => m.role === 'contractor');
          setProjectContractors(contractors);
        } catch {}
      }
    } catch (err) {
      if (err?.response?.status === 404) {
        toast.error('הליקוי לא נמצא');
        setErrorState('not_found');
      } else if (err?.response?.status === 403) {
        toast.error('אין לך הרשאה לצפות בליקוי זה');
        setErrorState('forbidden');
      } else {
        console.error('[TASK_LOAD_ERROR]', err?.response?.status, err?.message);
        toast.error('שגיאה בטעינת הליקוי');
        setErrorState('load_error');
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadTask(); }, [loadTask]);

  useEffect(() => {
    if (externalEntry && task?.project_id && !location.state?.returnTo) {
      const contractorBack = task.building_id
        ? `/projects/${task.project_id}/buildings/${task.building_id}/defects`
        : `/projects/${task.project_id}/control?tab=defects`;
      sessionStorage.setItem(RETURN_TO_KEY, contractorBack);
      console.log('[DEEP_LINK] TaskDetailPage: set contractor back target', contractorBack);
    }
  }, [externalEntry, task?.project_id, task?.building_id, location.state?.returnTo]);

  const handleAddComment = async () => {
    if (!comment.trim()) return;
    setSending(true);
    try {
      await taskService.addUpdate(id, comment);
      setComment('');
      const updatesData = await taskService.getUpdates(id);
      setUpdates(updatesData);
      toast.success('תגובה נוספה');
    } catch (err) {
      toast.error('שגיאה בהוספת תגובה');
    } finally {
      setSending(false);
    }
  };

  const handleSendWhatsApp = async () => {
    setSendingWhatsApp(true);
    try {
      const result = await notificationService.sendWhatsApp(id);
      toast.success(result.message || 'הודעת WhatsApp נשלחה');
      if (canManage) {
        const notifData = await notificationService.getTimeline(id);
        setNotifications(notifData);
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errorCode = typeof detail === 'object' ? detail?.error_code : null;
      if (errorCode === 'NO_TASK_IMAGE') {
        toast.error(detail.message || 'יש לצרף לפחות תמונה אחת לפני שליחה לקבלן');
      } else {
        const msg = (typeof detail === 'string' ? detail : detail?.message) || 'שגיאה בשליחת הודעה';
        toast.error(msg);
      }
    } finally {
      setSendingWhatsApp(false);
    }
  };

  const handleRetry = async (jobId) => {
    try {
      await notificationService.retry(jobId);
      toast.success('ניסיון חוזר בוצע');
      const notifData = await notificationService.getTimeline(id);
      setNotifications(notifData);
    } catch (err) {
      const msg = err.response?.data?.detail || 'שגיאה בניסיון חוזר';
      toast.error(msg);
    }
  };

  const handleProofFileChange = async (e) => {
    try {
      const file = e.target.files[0];
      if (file) {
        const compressed = await compressImage(file);
        const reader = new FileReader();
        reader.onload = (ev) => {
          setProofFiles(prev => [...prev, { file: compressed, preview: ev.target.result, id: Date.now() + Math.random() }]);
        };
        reader.readAsDataURL(compressed);
      }
    } catch (err) {
      console.error('[proof:file] failed to process image:', err);
      toast.error('שגיאה בעיבוד התמונה. נסה שוב.');
    } finally {
      if (e.target) e.target.value = '';
    }
  };

  const handleAddPhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const compressed = await compressImage(file);
      await taskService.uploadAttachment(task.id, compressed);
      toast.success('תמונה הועלתה בהצלחה');
      loadTask();
    } catch (err) {
      toast.error('שגיאה בהעלאת תמונה');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const removeProofFile = (fileId) => {
    setProofFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleSubmitProof = async () => {
    if (proofFiles.length === 0) {
      toast.error('יש להעלות לפחות תמונת תיקון אחת');
      return;
    }
    const files = proofFiles.map(f => f.file);
    setSubmittingProof(true);
    try {
      const result = await taskService.submitContractorProof(id, files, proofNote);
      toast.success(result.message || 'נשלח לאישור מנהל');
      setProofFiles([]);
      setProofNote('');
      await loadTask();
    } catch (err) {
      if (err.code === 'ECONNABORTED') {
        toast.error('הזמן הקצוב לשליחה עבר. בדוק חיבור אינטרנט ונסה שוב.');
      } else if (err.response?.status === 400) {
        toast.error(err.response?.data?.detail || 'שגיאה בנתונים שנשלחו');
      } else if (err.response?.status >= 500) {
        toast.error('שגיאה בשרת. נסה שוב בעוד רגע.');
      } else {
        toast.error(err.response?.data?.detail || 'שגיאה בשליחת הוכחת תיקון');
      }
    } finally {
      setSubmittingProof(false);
    }
  };

  const handleApprove = async () => {
    setDecidingApprove(true);
    try {
      const result = await taskService.managerDecision(id, 'approve');
      toast.success(result.message || 'תיקון אושר וסגור');
      await loadTask();
    } catch (err) {
      const msg = err.response?.data?.detail || 'שגיאה באישור';
      toast.error(msg);
    } finally {
      setDecidingApprove(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      toast.error('סיבת דחייה היא שדה חובה');
      return;
    }
    setDecidingReject(true);
    try {
      const result = await taskService.managerDecision(id, 'reject', rejectReason);
      toast.success(result.message || 'תיקון נדחה');
      setRejectReason('');
      setShowRejectForm(false);
      await loadTask();
    } catch (err) {
      const msg = err.response?.data?.detail || 'שגיאה בדחייה';
      toast.error(msg);
    } finally {
      setDecidingReject(false);
    }
  };

  const handleUpdateField = async (field, value) => {
    setSavingField(field);
    try {
      await taskService.update(id, { [field]: value });
      toast.success('עודכן בהצלחה');
      await loadTask();
    } catch (err) {
      const msg = err.response?.data?.detail || 'שגיאה בעדכון';
      toast.error(msg);
    } finally {
      setSavingField(null);
    }
  };

  const handleStatusChange = async (newStatus) => {
    setSavingField('status');
    try {
      await taskService.changeStatus(id, newStatus);
      toast.success('סטטוס עודכן');
      await loadTask();
    } catch (err) {
      const msg = err.response?.data?.detail || 'שגיאה בשינוי סטטוס';
      toast.error(msg);
    } finally {
      setSavingField(null);
    }
  };

  const handleAssignContractor = async (contractorUserId, forceCategory = false) => {
    const contractor = projectContractors.find(c => c.user_id === contractorUserId);
    if (!contractor) return;
    const companyId = contractor.user_company_id || contractor.company_id;
    if (!companyId) {
      toast.error('לא נמצאה חברה עבור הקבלן');
      return;
    }
    setSavingField('assignee');
    try {
      const payload = { company_id: companyId, assignee_id: contractorUserId };
      if (forceCategory) payload.force_category_change = true;
      const res = await taskService.assign(id, payload);
      if (res?.category_synced) {
        toast.success(`קבלן שויך — תחום הליקוי שונה ל${tCategory(res.synced_category)}`);
      } else {
        toast.success('קבלן שויך בהצלחה');
      }
      setTradeMismatchModal(null);
      await loadTask();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 && detail?.error === 'trade_mismatch') {
        setTradeMismatchModal({
          contractorUserId,
          contractorName: contractor.user_name || contractor.name,
          taskCategoryLabel: detail.task_category_label,
          contractorTradeLabel: detail.contractor_trade_label,
          contractorTrade: detail.contractor_trade,
        });
      } else {
        const msg = typeof detail === 'string' ? detail : detail?.message || 'שגיאה בשיוך קבלן';
        toast.error(msg);
      }
    } finally {
      setSavingField(null);
    }
  };

  const getCompanyName = (companyId) => {
    const c = companies.find(c => c.id === companyId);
    return c ? c.name : '';
  };

  const getStatusOptions = () => {
    if (!task) return [];
    const allowed = VALID_TRANSITIONS[task.status] || [];
    const options = [{ value: task.status, label: STATUS_CONFIG[task.status]?.label || task.status }];
    allowed.forEach(s => {
      if (STATUS_CONFIG[s]) {
        options.push({ value: s, label: STATUS_CONFIG[s].label });
      }
    });
    return options;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
      </div>
    );
  }

  if (errorState || !task) {
    const isNotFound = errorState === 'not_found';
    const isForbidden = errorState === 'forbidden';
    const isLoadError = errorState === 'load_error' || (!errorState && !task);
    const errorBackUrl = sessionStorage.getItem(RETURN_TO_KEY)
      || (task?.building_id && task?.project_id ? `/projects/${task.project_id}/buildings/${task.building_id}/defects`
        : task?.project_id ? `/projects/${task.project_id}/control?tab=defects` : '/projects');
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50" dir="rtl">
        <div className="text-center space-y-4 p-8">
          {isForbidden ? (
            <ShieldX className="w-16 h-16 text-red-400 mx-auto" />
          ) : (
            <AlertTriangle className="w-16 h-16 text-amber-400 mx-auto" />
          )}
          <h2 className="text-xl font-bold text-slate-700">
            {isForbidden ? 'אין לך הרשאה לצפות בליקוי הזה' : isLoadError ? 'שגיאה בטעינת הליקוי' : 'הליקוי לא קיים או הוסר'}
          </h2>
          <p className="text-slate-500 text-sm">
            {isForbidden ? 'ליקוי זה שייך לפרויקט שאין לך גישה אליו' : isLoadError ? 'בדוק את החיבור לאינטרנט ונסה שוב' : 'ייתכן שהליקוי נמחק או שהקישור אינו תקין'}
          </p>
          {isLoadError ? (
            <Button
              onClick={() => { setErrorState(null); setLoading(true); loadTask(); }}
              className="bg-amber-500 hover:bg-amber-600 text-white mt-4"
            >
              נסה שוב
            </Button>
          ) : (
            <Button
              onClick={() => navigate(errorBackUrl)}
              className="bg-amber-500 hover:bg-amber-600 text-white mt-4"
            >
              חזרה לליקויים שלי
            </Button>
          )}
        </div>
      </div>
    );
  }

  const status = STATUS_CONFIG[task.status] || STATUS_CONFIG.open;
  const priority = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
  const isImageAttachment = (u) => {
    if (u.update_type !== 'attachment') return false;
    const ct = (u.content_type || '').toLowerCase();
    const fn = (u.file_name || u.content || '').toLowerCase();
    if (fn.endsWith('.bin') || fn.endsWith('.txt')) return false;
    if (ct && !ct.startsWith('image/')) return false;
    return true;
  };
  const allAttachments = updates.filter(isImageAttachment);
  const openingAttachments = allAttachments.filter(a => a.user_id === task.created_by);
  const attachments = allAttachments.filter(a => a.user_id === task.assignee_id && a.user_id !== task.created_by);
  const previousAssigneeAttachments = allAttachments.filter(a => a.user_id !== task.created_by && a.user_id !== task.assignee_id);
  const comments = updates.filter(u => u.update_type !== 'attachment');
  const canComment = user?.role !== 'viewer' && projectRole !== 'viewer';

  const proofAllowedStatuses = ['open', 'assigned', 'in_progress', 'pending_contractor_proof', 'returned_to_contractor'];
  const proofLockedStatuses = ['pending_manager_approval', 'closed'];
  const showContractorProof = isContractor && isAssignee && proofAllowedStatuses.includes(task.status);
  const showProofLocked = isContractor && isAssignee && proofLockedStatuses.includes(task.status);

  const showManagerDecision = isManagement && task.status === 'pending_manager_approval';

  const timelineEvents = updates
    .filter(u => u.update_type === 'status_change' || isImageAttachment(u))
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  const hasCreatedEvent = timelineEvents.length > 0;

  return (
    <div className="min-h-screen bg-slate-50 relative" style={{ isolation: 'isolate' }}>
      <input ref={uploadCameraRef} type="file" accept="image/*" capture="environment" onChange={handleAddPhoto} className="hidden" />
      <input ref={uploadGalleryRef} type="file" accept="image/*" onChange={handleAddPhoto} className="hidden" />
      <div className="bg-white border-b shadow-sm sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HardHat className="w-5 h-5 text-amber-500" />
            <span className="font-bold text-slate-800">BrikOps</span>
          </div>
          <button
            onClick={() => {
              const returnTo = location.state?.returnTo || sessionStorage.getItem(RETURN_TO_KEY);
              if (returnTo) {
                sessionStorage.removeItem(RETURN_TO_KEY);
                navigate(returnTo);
              } else if (task?.building_id && task?.project_id) {
                navigate(`/projects/${task.project_id}/buildings/${task.building_id}/defects`);
              } else if (task?.project_id) {
                navigate(`/projects/${task.project_id}/control?tab=defects`);
              } else {
                navigate('/projects');
              }
            }}
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-amber-600 transition-colors"
          >
            {(() => {
              const rt = location.state?.returnTo || sessionStorage.getItem(RETURN_TO_KEY);
              if (externalEntry && !location.state?.returnTo) return 'חזרה לליקויים שלי';
              return rt && rt.includes('/dashboard') ? 'חזרה למרכז ניהול' : 'חזרה לרשימת ליקויים';
            })()}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6 space-y-4" dir="rtl">
        <Card className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex gap-2">
              <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${status.color}`}>
                {status.label}
              </span>
              <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${priority.color}`}>
                {priority.label}
              </span>
            </div>
            <span className="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded">
              {tCategory(task.category)}
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-800 mb-2">{task.title}</h1>
          {task.description && (
            <p className="text-sm text-slate-600 leading-relaxed">{task.description}</p>
          )}

          {canManage && (
            <div className="mt-4 pt-3 border-t border-slate-100">
              {allAttachments.length === 0 ? (
                <div>
                  <p className="text-xs text-amber-600 font-medium mb-2">
                    יש לצרף לפחות תמונה אחת לפני שליחה לקבלן
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => uploadCameraRef.current?.click()}
                      disabled={uploading}
                      className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg bg-amber-500 text-white hover:bg-amber-600 active:bg-amber-700 disabled:opacity-50 transition-colors"
                    >
                      <Camera className="w-3.5 h-3.5" />
                      {uploading ? 'מעלה...' : 'צלם תמונה'}
                    </button>
                    <button
                      onClick={() => uploadGalleryRef.current?.click()}
                      disabled={uploading}
                      className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 active:bg-slate-100 disabled:opacity-50 transition-colors"
                    >
                      <ImageIcon className="w-3.5 h-3.5" />
                      {uploading ? 'מעלה...' : 'בחר תמונה'}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {task.assignee_id && (
                    <Button
                      onClick={handleSendWhatsApp}
                      disabled={sendingWhatsApp}
                      size="sm"
                      className="bg-green-600 hover:bg-green-700 text-white gap-2"
                    >
                      <Phone className="w-4 h-4" />
                      {sendingWhatsApp ? 'שולח...' : 'שלח עדכון בוואטסאפ'}
                    </Button>
                  )}
                </>
              )}
            </div>
          )}
        </Card>

        {(() => {
          const heroImg = updates.find(u => {
            if (!isImageAttachment(u)) return false;
            const within60s = task.created_at && u.created_at &&
              Math.abs(new Date(u.created_at) - new Date(task.created_at)) <= 60000;
            return within60s || u.update_type !== 'contractor_proof';
          });
          if (!heroImg || !heroImg.attachment_url) return null;
          return (
            <Card className="p-0 overflow-hidden">
              <img
                src={heroImg.attachment_url}
                alt={task.title}
                className="w-full max-h-[400px] object-cover cursor-pointer"
                style={{ borderRadius: 'inherit' }}
                onClick={() => setImageModal(heroImg.attachment_url)}
              />
            </Card>
          );
        })()}

        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-500 mb-3 flex items-center gap-2">
            <Building2 className="w-4 h-4" />
            מיקום
          </h3>
          <div className="flex items-center gap-2 text-sm text-slate-700 flex-wrap">
            {task.project_name && (
              <span className="bg-slate-100 px-2 py-1 rounded">{task.project_name}</span>
            )}
            {task.building_name && (
              <>
                <ChevronRight className="w-3 h-3 text-slate-400 rtl:rotate-180" />
                <span className="bg-slate-100 px-2 py-1 rounded flex items-center gap-1">
                  <Building2 className="w-3 h-3" /> {task.building_name}
                </span>
              </>
            )}
            {task.floor_name && (
              <>
                <ChevronRight className="w-3 h-3 text-slate-400 rtl:rotate-180" />
                <span className="bg-slate-100 px-2 py-1 rounded flex items-center gap-1">
                  <Layers className="w-3 h-3" /> {task.floor_name}
                </span>
              </>
            )}
            {task.unit_name && (
              <>
                <ChevronRight className="w-3 h-3 text-slate-400 rtl:rotate-180" />
                <span className="bg-slate-100 px-2 py-1 rounded flex items-center gap-1">
                  <DoorOpen className="w-3 h-3" /> דירה {task.unit_name}
                </span>
              </>
            )}
          </div>
        </Card>

        {task.company_id && (
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-500 mb-3 flex items-center gap-2">
              <Briefcase className="w-4 h-4" />
              שיוך
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-slate-400" />
                <span className="text-slate-600">חברה:</span>
                <span className="font-medium">{getCompanyName(task.company_id) || task.assignee_company_name || ''}</span>
              </div>
              {task.assignee_id && (
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-400" />
                  <span className="text-slate-600">קבלן:</span>
                  <span className="font-medium">
                    {task.assignee_name || projectContractors.find(c => c.user_id === task.assignee_id)?.user_name || 'קבלן משויך'}
                  </span>
                </div>
              )}
            </div>
          </Card>
        )}

        {canManage && (
          <Card className="p-5 border-2 border-amber-300 bg-amber-50/50">
            <h3 className="text-sm font-bold text-amber-800 mb-4 flex items-center gap-2">
              <Settings className="w-4 h-4" />
              פאנל ניהול
              {taskIsClosed && (
                <span className="text-xs bg-slate-200 text-slate-500 px-2 py-0.5 rounded-full mr-2 flex items-center gap-1">
                  <Lock className="w-3 h-3" /> נעול
                </span>
              )}
            </h3>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block">סטטוס</label>
                <InlineSelect
                  value={task.status}
                  options={getStatusOptions()}
                  onChange={handleStatusChange}
                  disabled={taskIsClosed || savingField === 'status'}
                  label={savingField === 'status' ? 'שומר...' : (STATUS_CONFIG[task.status]?.label || task.status)}
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block">דחיפות</label>
                <InlineSelect
                  value={task.priority}
                  options={PRIORITIES.map(p => ({ value: p, label: PRIORITY_CONFIG[p]?.label || p }))}
                  onChange={(v) => handleUpdateField('priority', v)}
                  disabled={taskIsClosed || savingField === 'priority'}
                  label={savingField === 'priority' ? 'שומר...' : (PRIORITY_CONFIG[task.priority]?.label || task.priority)}
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block">תחום</label>
                <InlineSelect
                  value={task.category}
                  options={CATEGORIES.map(c => ({ value: c, label: tCategory(c) }))}
                  onChange={(v) => handleUpdateField('category', v)}
                  disabled={taskIsClosed || savingField === 'category'}
                  label={savingField === 'category' ? 'שומר...' : tCategory(task.category)}
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block">קבלן</label>
                {(() => {
                  if (companies.length === 0) {
                    return (
                      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-center space-y-1.5">
                        <p className="text-xs text-amber-800 font-medium">אין חברות בפרויקט</p>
                        <button
                          onClick={() => navigate(`/projects/${task.project_id}/control?tab=companies`)}
                          className="text-xs text-amber-700 underline hover:text-amber-900"
                        >
                          הוסף חברה
                        </button>
                      </div>
                    );
                  }
                  const assignableContractors = projectContractors.filter(c => c.company_id && c.contractor_trade_key);
                  return assignableContractors.length === 0 && !task.assignee_id ? (
                    <p className="text-xs text-red-500 mt-1">אין קבלנים משויכים. יש לשייך קבלן לחברה/תחום.</p>
                  ) : (
                    <InlineSelect
                      value={task.assignee_id || ''}
                      options={[
                        { value: '', label: 'לא שויך' },
                        ...assignableContractors.map(c => ({
                          value: c.user_id,
                          label: c.user_name || c.user_id
                        }))
                      ]}
                      onChange={handleAssignContractor}
                      disabled={taskIsClosed || savingField === 'assignee'}
                      label={savingField === 'assignee' ? 'שומר...' : (
                        task.assignee_id
                          ? (task.assignee_name || projectContractors.find(c => c.user_id === task.assignee_id)?.user_name || 'קבלן משויך')
                          : 'לא שויך'
                      )}
                    />
                  );
                })()}
              </div>
            </div>
          </Card>
        )}

        {showManagerDecision && (
          <Card className="p-5 border-2 border-indigo-300 bg-indigo-50">
            <h3 className="text-sm font-semibold text-indigo-700 mb-3 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" />
              החלטת ניהול — אישור / דחייה
            </h3>
            <p className="text-xs text-indigo-600 mb-4">
              הקבלן העלה הוכחת תיקון. בדוק את התמונות ואשר או דחה.
            </p>

            <div className="flex gap-3 mb-3">
              <Button
                onClick={handleApprove}
                disabled={decidingApprove}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white gap-2"
              >
                <CheckCircle className="w-4 h-4" />
                {decidingApprove ? 'מאשר...' : 'אשר סגירה'}
              </Button>
              <Button
                onClick={() => setShowRejectForm(!showRejectForm)}
                variant="outline"
                className="flex-1 border-red-400 text-red-600 hover:bg-red-50 gap-2"
              >
                <ShieldX className="w-4 h-4" />
                החזר לקבלן
              </Button>
            </div>

            {showRejectForm && (
              <div className="space-y-2 pt-2 border-t border-indigo-200">
                <label className="text-xs font-medium text-red-600">סיבת דחייה (חובה):</label>
                <textarea
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  placeholder="הסבר מדוע התיקון נדחה..."
                  rows={3}
                  className="w-full px-3 py-2 border border-red-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500 bg-white"
                />
                <Button
                  onClick={handleReject}
                  disabled={decidingReject || !rejectReason.trim()}
                  className="w-full bg-red-600 hover:bg-red-700 text-white gap-2"
                >
                  <XCircle className="w-4 h-4" />
                  {decidingReject ? 'דוחה...' : 'אשר דחייה'}
                </Button>
              </div>
            )}
          </Card>
        )}

        {showContractorProof && (
          <Card className="p-6 border-2 border-amber-400 bg-amber-50 shadow-md">
            <h3 className="text-base font-bold text-amber-800 mb-2 flex items-center gap-2">
              <Camera className="w-5 h-5" />
              העלאת תמונות תיקון
            </h3>
            <p className="text-sm text-amber-700 mb-4">
              צלם או העלה תמונות של התיקון שבוצע ושלח לאישור המנהל
            </p>

            <input ref={proofCameraRef} type="file" accept="image/*" capture="environment" onChange={handleProofFileChange} className="hidden" />
            <input ref={proofGalleryRef} type="file" accept="image/*" onChange={handleProofFileChange} className="hidden" />

            {proofFiles.length > 0 && (
              <div className="mb-4 grid grid-cols-2 gap-3">
                {proofFiles.map((pf) => (
                  <div key={pf.id} className="relative group">
                    <img src={pf.preview} alt="תצוגה מקדימה" className="w-full h-32 object-cover rounded-xl border-2 border-amber-300 bg-white" />
                    <button
                      onClick={() => removeProofFile(pf.id)}
                      className="absolute top-1 left-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shadow-md hover:bg-red-600 transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-3 mb-4">
              <button
                onClick={() => proofCameraRef.current?.click()}
                className="flex-1 py-5 border-2 border-dashed border-amber-400 rounded-xl bg-white hover:bg-amber-50 transition-colors flex flex-col items-center gap-2"
              >
                <Camera className="w-8 h-8 text-amber-500" />
                <span className="text-sm font-semibold text-amber-700">צלם תמונה</span>
              </button>
              <button
                onClick={() => proofGalleryRef.current?.click()}
                className="flex-1 py-5 border-2 border-dashed border-slate-300 rounded-xl bg-white hover:bg-slate-50 transition-colors flex flex-col items-center gap-2"
              >
                <Upload className="w-8 h-8 text-slate-400" />
                <span className="text-sm font-semibold text-slate-600">בחר מגלריה</span>
              </button>
            </div>

            {proofFiles.length > 0 && (
              <p className="text-xs text-amber-600 mb-3 text-center font-medium">{proofFiles.length} תמונ{proofFiles.length === 1 ? 'ה' : 'ות'} נבחר{proofFiles.length === 1 ? 'ה' : 'ו'}</p>
            )}

            <input
              type="text"
              value={proofNote}
              onChange={e => setProofNote(e.target.value)}
              placeholder="הערת ביצוע (אופציונלי)..."
              className="w-full px-4 py-3 border border-amber-300 rounded-xl text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500 bg-white mb-4"
            />

            <Button
              onClick={handleSubmitProof}
              disabled={submittingProof || proofFiles.length === 0}
              className="w-full h-12 text-base font-bold bg-amber-500 hover:bg-amber-600 text-white gap-2 rounded-xl shadow-sm"
            >
              <Send className="w-5 h-5" />
              {submittingProof ? 'שולח...' : `שלח ${proofFiles.length > 0 ? `(${proofFiles.length}) ` : ''}לאישור מנהל`}
            </Button>
          </Card>
        )}

        {showProofLocked && (
          <Card className="p-5 border border-slate-200 bg-slate-50">
            <div className="flex items-center gap-2 text-slate-500">
              <ShieldCheck className="w-5 h-5" />
              <span className="text-sm font-medium">
                {task.status === 'pending_manager_approval'
                  ? 'ההוכחה נשלחה — ממתין לאישור מנהל'
                  : 'הליקוי סגור — לא ניתן להעלות הוכחה'}
              </span>
            </div>
          </Card>
        )}

        {openingAttachments.length > 0 && (
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-500 mb-3 flex items-center gap-2">
              <Camera className="w-4 h-4" />
              תמונות פתיחה ({openingAttachments.length})
            </h3>
            <div className="space-y-3">
              {openingAttachments.map((att, i) => (
                <div key={att.id} className="flex gap-3 items-start bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <button
                    onClick={() => setImageModal(att.attachment_url)}
                    className="w-20 h-20 rounded-lg overflow-hidden border border-slate-200 hover:border-amber-400 transition-colors flex-shrink-0"
                  >
                    <img
                      src={att.attachment_url}
                      alt={`תמונת פתיחה ${i + 1}`}
                      className="w-full h-full object-cover"
                      onError={e => { e.target.style.display = 'none'; }}
                    />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-sm font-medium text-slate-700">{att.user_name || 'לא ידוע'}</span>
                    </div>
                    <div className="flex items-center gap-1.5 mb-2">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-xs text-slate-500">
                        {att.created_at ? new Date(att.created_at).toLocaleString('he-IL') : ''}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setImageModal(att.attachment_url)}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        צפייה
                      </button>
                      <a
                        href={att.attachment_url}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-green-600 hover:text-green-800"
                      >
                        <Download className="w-3.5 h-3.5" />
                        הורדה
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {canManage && (
              <div className="flex items-center gap-3 mt-3 pt-2 border-t border-slate-100">
                <button
                  onClick={() => uploadCameraRef.current?.click()}
                  disabled={uploading}
                  className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-800 disabled:opacity-50 transition-colors"
                >
                  <Camera className="w-3.5 h-3.5" />
                  {uploading ? 'מעלה...' : 'צלם עוד'}
                </button>
                <button
                  onClick={() => uploadGalleryRef.current?.click()}
                  disabled={uploading}
                  className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 disabled:opacity-50 transition-colors"
                >
                  <ImageIcon className="w-3.5 h-3.5" />
                  {uploading ? 'מעלה...' : 'בחר מגלריה'}
                </button>
              </div>
            )}
          </Card>
        )}

        {attachments.length > 0 && (
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-500 mb-3 flex items-center gap-2">
              <Camera className="w-4 h-4" />
              הוכחות קבלן ({attachments.length})
            </h3>
            <div className="space-y-3">
              {attachments.map((att, i) => (
                <div key={att.id} className="flex gap-3 items-start bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <button
                    onClick={() => setImageModal(att.attachment_url)}
                    className="w-20 h-20 rounded-lg overflow-hidden border border-slate-200 hover:border-amber-400 transition-colors flex-shrink-0"
                  >
                    <img
                      src={att.attachment_url}
                      alt={`הוכחה ${i + 1}`}
                      className="w-full h-full object-cover"
                      onError={e => { e.target.style.display = 'none'; }}
                    />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-sm font-medium text-slate-700">{att.user_name || 'לא ידוע'}</span>
                    </div>
                    <div className="flex items-center gap-1.5 mb-2">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-xs text-slate-500">
                        {att.created_at ? new Date(att.created_at).toLocaleString('he-IL') : ''}
                      </span>
                    </div>
                    {att.content && att.content !== 'הוכחת תיקון מקבלן' && (
                      <p className="text-xs text-slate-500 mb-2">{att.content}</p>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setImageModal(att.attachment_url)}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        צפייה
                      </button>
                      <a
                        href={att.attachment_url}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-green-600 hover:text-green-800"
                      >
                        <Download className="w-3.5 h-3.5" />
                        הורדה
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {previousAssigneeAttachments.length > 0 && isManagement && (
          <Card className="p-5 border-slate-200 bg-slate-50/50">
            <h3 className="text-sm font-semibold text-slate-400 mb-3 flex items-center gap-2">
              <Camera className="w-4 h-4" />
              הוכחות מקבלן קודם ({previousAssigneeAttachments.length})
            </h3>
            <div className="space-y-3">
              {previousAssigneeAttachments.map((att, i) => (
                <div key={att.id} className="flex gap-3 items-start bg-white/60 rounded-xl p-3 border border-slate-200 opacity-70">
                  <button
                    onClick={() => setImageModal(att.attachment_url)}
                    className="w-16 h-16 rounded-lg overflow-hidden border border-slate-200 flex-shrink-0"
                  >
                    <img
                      src={att.attachment_url}
                      alt={`הוכחה ישנה ${i + 1}`}
                      className="w-full h-full object-cover"
                      onError={e => { e.target.style.display = 'none'; }}
                    />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-sm text-slate-500">{att.user_name || 'לא ידוע'}</span>
                      <span className="text-xs bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded">קבלן קודם</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-xs text-slate-400">
                        {att.created_at ? new Date(att.created_at).toLocaleString('he-IL') : ''}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {(timelineEvents.length > 0 || task.created_at) && (
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-500 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4" />
              ציר זמן
            </h3>
            <div className="relative pr-6">
              <div className="absolute right-2.5 top-0 bottom-0 w-0.5 bg-slate-200" />

              <div className="relative mb-4">
                <div className="absolute right-[-14px] w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center">
                  <CircleDot className="w-3.5 h-3.5 text-blue-600" />
                </div>
                <div className="mr-4 pb-2">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-medium text-slate-700">ליקוי נפתח</span>
                  </div>
                  <span className="text-xs text-slate-400">
                    {new Date(task.created_at).toLocaleString('he-IL')}
                  </span>
                </div>
              </div>

              {timelineEvents.map((evt, i) => {
                const isLast = i === timelineEvents.length - 1;
                const isStatusChange = evt.update_type === 'status_change';
                const isAttachment = evt.update_type === 'attachment';
                const config = isAttachment
                  ? { icon: Camera, color: 'text-amber-600 bg-amber-100' }
                  : evt.new_status === 'closed'
                    ? { icon: CheckCircle, color: 'text-green-600 bg-green-100' }
                    : evt.new_status === 'returned_to_contractor'
                      ? { icon: ArrowDownCircle, color: 'text-rose-600 bg-rose-100' }
                      : { icon: RefreshCw, color: 'text-blue-600 bg-blue-100' };
                const Icon = config.icon;

                return (
                  <div key={evt.id} className={`relative mb-4 ${isLast ? 'mb-0' : ''}`}>
                    <div className={`absolute right-[-14px] w-6 h-6 rounded-full flex items-center justify-center ${config.color} ${isLast ? 'ring-2 ring-offset-1 ring-amber-400' : ''}`}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="mr-4 pb-2">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={`text-sm font-medium ${isLast ? 'text-amber-700' : 'text-slate-700'}`}>
                          {evt.content}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">
                          {evt.created_at ? new Date(evt.created_at).toLocaleString('he-IL') : ''}
                        </span>
                        {evt.user_name && (
                          <span className="text-xs text-slate-400">• {evt.user_name}</span>
                        )}
                      </div>
                      {isStatusChange && evt.old_status && evt.new_status && (
                        <div className="flex items-center gap-1.5 mt-1">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${STATUS_CONFIG[evt.old_status]?.color || 'bg-slate-100'}`}>
                            {STATUS_CONFIG[evt.old_status]?.label || evt.old_status}
                          </span>
                          <span className="text-slate-400 text-xs">←</span>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${STATUS_CONFIG[evt.new_status]?.color || 'bg-slate-100'}`}>
                            {STATUS_CONFIG[evt.new_status]?.label || evt.new_status}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {canManage && notifications.length > 0 && (
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-500 mb-3 flex items-center gap-2">
              <Bell className="w-4 h-4" />
              היסטוריית התראות ({notifications.length})
            </h3>
            <div className="space-y-3">
              {notifications.map(n => {
                const cfg = NOTIF_STATUS_CONFIG[n.status] || NOTIF_STATUS_CONFIG.queued;
                const Icon = cfg.icon;
                const channelLabel = n.channel === 'sms' ? 'SMS' : n.channel === 'whatsapp' ? 'WhatsApp' : n.channel;
                const maskedPhone = n.target_phone ? (n.target_phone.length > 8 ? n.target_phone.slice(0,4) + '****' + n.target_phone.slice(-4) : n.target_phone.slice(0,3) + '****') : '';
                return (
                  <div key={n.id} className="border-b border-slate-100 pb-3 last:border-0">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <Icon className={`w-4 h-4 ${cfg.color}`} />
                        <span className={`text-sm font-medium ${cfg.color}`}>{cfg.label}</span>
                        {channelLabel && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 font-medium">{channelLabel}</span>
                        )}
                      </div>
                      <span className="text-xs text-slate-400">
                        {n.created_at ? new Date(n.created_at).toLocaleString('he-IL') : ''}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-slate-500">
                        <span className="bg-slate-100 px-1.5 py-0.5 rounded">
                          {getNotifEventLabel(n.event_type)}
                        </span>
                        <span className="mr-2">{maskedPhone}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        {n.status === 'failed' && canManage && (
                          <Button
                            onClick={() => handleRetry(n.id)}
                            size="sm"
                            variant="outline"
                            className="text-xs h-7 gap-1"
                          >
                            <RefreshCw className="w-3 h-3" />
                            נסה שוב
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-xs h-7 gap-1 text-slate-400"
                          onClick={() => {
                            const debug = {
                              task_id: n.task_id,
                              job_id: n.id,
                              masked_phone: maskedPhone,
                              message_id: n.provider_message_id || '',
                              delivery_state: n.status,
                              channel: n.channel,
                              event_type: n.event_type,
                              error: n.last_error || null,
                              created_at: n.created_at,
                              updated_at: n.updated_at,
                            };
                            navigator.clipboard.writeText(JSON.stringify(debug, null, 2));
                            toast.success('דיבוג הועתק ללוח');
                          }}
                        >
                          <Copy className="w-3 h-3" />
                          העתק דיבוג
                        </Button>
                      </div>
                    </div>
                    {n.provider_message_id && (
                      <p className="text-[10px] text-slate-400 mt-1 font-mono truncate" dir="ltr">
                        msg: {n.provider_message_id}
                      </p>
                    )}
                    {n.updated_at && n.updated_at !== n.created_at && (
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        עודכן: {new Date(n.updated_at).toLocaleString('he-IL')}
                      </p>
                    )}
                    {(n.status === 'queued' || n.status === 'sent') && n.created_at && (Date.now() - new Date(n.created_at).getTime() > 60000) && (
                      <div className="mt-1.5 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
                        <p className="font-medium">⚠ לא התקבל אישור מסירה</p>
                        <p className="text-[10px] text-amber-600 mt-0.5">
                          עדכון אחרון: {new Date(n.updated_at || n.created_at).toLocaleString('he-IL')}
                          {n.provider_message_id && (
                            <span className="font-mono mr-2" dir="ltr">
                              msg: {n.provider_message_id.slice(-12)}
                            </span>
                          )}
                        </p>
                      </div>
                    )}
                    {n.last_error && (
                      <p className="text-xs text-red-500 mt-1">{n.last_error}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-500 mb-3 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            עדכונים ({comments.length})
          </h3>
          <div className="space-y-3">
            {comments.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-4">אין עדכונים עדיין</p>
            )}
            {comments.map(u => (
              <div key={u.id} className="border-b border-slate-100 pb-3 last:border-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-400">
                    {new Date(u.created_at).toLocaleString('he-IL')}
                  </span>
                  <span className="text-sm font-medium text-slate-700">{u.user_name}</span>
                </div>
                <p className="text-sm text-slate-600">{u.content}</p>
                {u.update_type === 'status_change' && (
                  <div className="flex items-center gap-2 mt-1 text-xs">
                    <span className={`px-1.5 py-0.5 rounded ${STATUS_CONFIG[u.old_status]?.color || 'bg-slate-100'}`}>
                      {STATUS_CONFIG[u.old_status]?.label || u.old_status}
                    </span>
                    <span className="text-slate-400">&larr;</span>
                    <span className={`px-1.5 py-0.5 rounded ${STATUS_CONFIG[u.new_status]?.color || 'bg-slate-100'}`}>
                      {STATUS_CONFIG[u.new_status]?.label || u.new_status}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
          {canComment && (
            <div className="mt-4 flex gap-2">
              <Button
                onClick={handleAddComment}
                disabled={sending || !comment.trim()}
                size="sm"
                className="bg-amber-500 hover:bg-amber-600 text-white"
              >
                <Send className="w-4 h-4" />
              </Button>
              <input
                type="text"
                value={comment}
                onChange={e => setComment(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAddComment()}
                placeholder="הוסף תגובה..."
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              />
            </div>
          )}
        </Card>

        <div className="text-xs text-slate-400 text-center pb-4">
          <Clock className="w-3 h-3 inline ml-1" />
          נוצר: {new Date(task.created_at).toLocaleString('he-IL')}
          {task.updated_at && ` | עודכן: ${new Date(task.updated_at).toLocaleString('he-IL')}`}
          {process.env.REACT_APP_GIT_SHA && (
            <span className="mr-2">| v{process.env.REACT_APP_GIT_SHA}</span>
          )}
        </div>
      </div>

      {tradeMismatchModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setTradeMismatchModal(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6" dir="rtl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <h3 className="text-lg font-bold text-slate-800">תחום לא תואם</h3>
            </div>
            <p className="text-sm text-slate-600 mb-2">
              תחום הליקוי הנוכחי: <span className="font-semibold text-slate-800">{tradeMismatchModal.taskCategoryLabel}</span>
            </p>
            <p className="text-sm text-slate-600 mb-4">
              תחום הקבלן ({tradeMismatchModal.contractorName}): <span className="font-semibold text-slate-800">{tradeMismatchModal.contractorTradeLabel}</span>
            </p>
            <p className="text-xs text-slate-500 mb-5 bg-amber-50 p-3 rounded-lg border border-amber-200">
              לא ניתן לשייך קבלן שתחום ההתמחות שלו שונה מתחום הליקוי. ניתן לשנות את תחום הליקוי ולשייך, או לבטל.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setTradeMismatchModal(null)}
                className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
              >
                בטל שיוך
              </button>
              <button
                onClick={() => handleAssignContractor(tradeMismatchModal.contractorUserId, true)}
                disabled={savingField === 'assignee'}
                className="flex-1 px-4 py-2.5 rounded-xl bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 transition-colors disabled:opacity-50"
              >
                {savingField === 'assignee' ? 'משייך...' : `שנה ל${tradeMismatchModal.contractorTradeLabel} + שייך`}
              </button>
            </div>
          </div>
        </div>
      )}

      {imageModal && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setImageModal(null)}
        >
          <div className="relative max-w-full max-h-full" onClick={e => e.stopPropagation()}>
            <img src={imageModal} alt="" className="max-w-full max-h-[85vh] rounded-lg" />
            <div className="absolute top-2 left-2 flex gap-2">
              <button
                onClick={() => setImageModal(null)}
                className="bg-black/50 text-white rounded-full w-8 h-8 flex items-center justify-center hover:bg-black/70"
              >
                <X className="w-5 h-5" />
              </button>
              <a
                href={imageModal}
                download
                target="_blank"
                rel="noopener noreferrer"
                className="bg-black/50 text-white rounded-full w-8 h-8 flex items-center justify-center hover:bg-black/70"
              >
                <Download className="w-5 h-5" />
              </a>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default TaskDetailPage;
