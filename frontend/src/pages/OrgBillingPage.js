import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { billingService, orgMemberService, invoiceService, projectService, handoverService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { ChevronRight, Lock, Loader2, Users, FileText, ChevronDown, ChevronUp, Copy, Info, Upload, Eye, X, ArrowRight, CreditCard, Clock, Pencil, AlertTriangle } from 'lucide-react';
import ProjectBillingEditModal from '../components/ProjectBillingEditModal';
import UpgradeWizard from '../components/UpgradeWizard';
import PlanSelector from '../components/PlanSelector';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import {
  getBillingStatusLabel, getBillingStatusColor,
  getAccessLabel, getSetupStateLabel, getSetupStateColor,
  getPlanLabel, formatCurrency,
  getInvoiceStatusLabel, getInvoiceStatusColor,
} from '../utils/billingLabels';
import { getPlanBadge } from '../utils/billingPlanCatalog';

const ORG_ROLE_LABELS = {
  owner: 'בעלים',
  org_admin: 'מנהל ארגון',
  billing_admin: 'אחראי חיוב',
  member: 'חבר',
  project_manager: 'מנהל פרויקט',
};

const ASSIGNABLE_ROLES = [
  { value: 'member', label: 'חבר' },
  { value: 'org_admin', label: 'מנהל ארגון' },
  { value: 'billing_admin', label: 'אחראי חיוב' },
];

const ROLE_DESCRIPTIONS = {
  owner: 'גישה מלאה לכל פעולות הארגון והחיוב',
  org_admin: 'ניהול חברי ארגון וצפייה בנתוני חיוב',
  billing_admin: 'ניהול הגדרות חיוב ותוכניות בפרויקטים',
  member: 'חבר ארגון ללא הרשאות חיוב',
  project_manager: 'ניהול פרויקטים ללא הרשאות חיוב ארגוניות',
};

const SUBSCRIPTION_STATUS_LABELS = {
  active: 'פעיל',
  trial: 'ניסיון',
  past_due: 'חוב פתוח',
  expired: 'פג תוקף',
  suspended: 'מושעה',
  none: 'לא פעיל',
};

const SUBSCRIPTION_STATUS_COLORS = {
  active: 'bg-emerald-100 text-emerald-700',
  trial: 'bg-blue-100 text-blue-700',
  past_due: 'bg-red-100 text-red-700',
  expired: 'bg-red-100 text-red-700',
  suspended: 'bg-red-100 text-red-700',
  none: 'bg-amber-100 text-amber-700',
};

const CYCLE_LABELS = {
  monthly: 'חודשי',
  yearly: 'שנתי',
};

function getRoleLabel(role) {
  return ORG_ROLE_LABELS[role] || '—';
}

function formatDate(isoStr) {
  if (!isoStr) return '—';
  try { return new Date(isoStr).toLocaleDateString('he-IL'); } catch { return '—'; }
}

export default function OrgBillingPage() {
  const { orgId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fatalError, setFatalError] = useState(null);
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState(null);
  const [membersDenied, setMembersDenied] = useState(false);
  const [changingRole, setChangingRole] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [editingProjectBilling, setEditingProjectBilling] = useState(null);
  const [highlightedProjectId, setHighlightedProjectId] = useState(null);
  const responsibilityRef = useRef(null);
  const projectsSectionRef = useRef(null);

  const [invoices, setInvoices] = useState([]);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [markingPaid, setMarkingPaid] = useState(null);
  const [expandedInvoice, setExpandedInvoice] = useState(null);
  const [expandedDetail, setExpandedDetail] = useState(null);
  const [invoiceConfirm, setInvoiceConfirm] = useState(null);

  const [renewalCycle, setRenewalCycle] = useState('monthly');
  const [renewalPreview, setRenewalPreview] = useState(null);
  const [renewalLoading, setRenewalLoading] = useState(false);

  const [paymentRequestLoading, setPaymentRequestLoading] = useState(false);
  const [paymentRequestResult, setPaymentRequestResult] = useState(null);
  const [markPaidLoading, setMarkPaidLoading] = useState(false);

  const [paymentRequests, setPaymentRequests] = useState([]);
  const [paymentRequestsLoading, setPaymentRequestsLoading] = useState(false);
  const [paymentRequestsFilter, setPaymentRequestsFilter] = useState('open');
  const [paymentRequestsExpanded, setPaymentRequestsExpanded] = useState(false);
  const [highlightRequestId, setHighlightRequestId] = useState(null);
  const highlightRetried = useRef(false);

  const [paymentConfigBank, setPaymentConfigBank] = useState('');
  const [paymentConfigBit, setPaymentConfigBit] = useState('');
  const [paymentConfigSaving, setPaymentConfigSaving] = useState(false);
  const [paymentConfigExpanded, setPaymentConfigExpanded] = useState(false);
  const [paymentOptionsExpanded, setPaymentOptionsExpanded] = useState(false);

  const [customerMarkPaidLoading, setCustomerMarkPaidLoading] = useState(false);
  const [receiptUploading, setReceiptUploading] = useState(false);
  const receiptFileRef = useRef(null);
  const [rejectModalRequest, setRejectModalRequest] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [sourceProjectName, setSourceProjectName] = useState(null);
  const [sourceProjectId, setSourceProjectId] = useState(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [adminApproveLoading, setAdminApproveLoading] = useState(null);

  const [logoUrl, setLogoUrl] = useState(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoDeleting, setLogoDeleting] = useState(false);
  const logoFileRef = useRef(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [availablePlans, setAvailablePlans] = useState(null);

  const isSA = user?.platform_role === 'super_admin';
  const isOwner = data?.owner_user_id === user?.id;
  const canManageBilling = data?.can_manage_billing || false;
  const isPM = data?.is_org_pm || false;
  const canViewRequests = isSA || canManageBilling || isPM;
  const canEditRoles = isSA || isOwner;
  const canEditLogo = isSA || isOwner || isPM;
  const canMutateInvoices = isSA || isOwner || (data && members.find(m => m.user_id === user?.id && m.role === 'billing_admin'));

  const renewRef = useRef(null);

  const sub = data?.subscription;
  const subStatus = sub?.subscription_status || 'none';
  const needsUpgrade = subStatus === 'expired' || subStatus === 'past_due' || subStatus === 'none';
  const isTrial = subStatus === 'trial';
  const isActive = subStatus === 'active';
  const isSuspended = sub?.read_only_reason === 'suspended';

  const currentPeriod = (() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}`;
  })();

  const loadInvoices = useCallback(async () => {
    if (!orgId) return;
    setInvoicesLoading(true);
    try {
      const result = await invoiceService.list(orgId);
      setInvoices(result.invoices || []);
    } catch {
      setInvoices([]);
    } finally {
      setInvoicesLoading(false);
    }
  }, [orgId]);

  const loadPreview = useCallback(async () => {
    if (!orgId) return;
    setPreviewLoading(true);
    try {
      const result = await invoiceService.preview(orgId, currentPeriod);
      setPreview(result);
    } catch {
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [orgId, currentPeriod]);

  useEffect(() => {
    if (orgId && data) {
      loadInvoices();
      loadPreview();
    }
  }, [orgId, data, loadInvoices, loadPreview]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await invoiceService.generate(orgId, currentPeriod);
      toast.success('חשבונית הופקה בהצלחה');
      await loadInvoices();
      await loadPreview();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בהפקת חשבונית');
    } finally {
      setGenerating(false);
    }
  };

  const handleMarkPaid = async (invoiceId) => {
    setInvoiceConfirm(null);
    setMarkingPaid(invoiceId);
    try {
      await invoiceService.markPaid(orgId, invoiceId);
      toast.success('חשבונית סומנה כשולם');
      await loadInvoices();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בסימון חשבונית');
    } finally {
      setMarkingPaid(null);
    }
  };

  const loadInvoiceDetail = async (invoiceId) => {
    if (expandedInvoice === invoiceId) {
      setExpandedInvoice(null);
      setExpandedDetail(null);
      return;
    }
    setExpandedInvoice(invoiceId);
    try {
      const detail = await invoiceService.get(orgId, invoiceId);
      setExpandedDetail(detail);
    } catch {
      setExpandedDetail(null);
    }
  };

  const formatPeriod = (ym) => {
    if (!ym) return '—';
    const [y, m] = ym.split('-');
    return `${m}/${y}`;
  };

  useEffect(() => {
    if (!orgId) return;
    setLoading(true);
    setFatalError(null);
    billingService.orgBilling(orgId)
      .then(d => { setData(d); setLogoUrl(d?.logo_url || null); })
      .catch(err => {
        const status = err.response?.status;
        const detail = err.response?.data?.detail || 'שגיאה בטעינת נתוני חיוב';
        if (status === 403 || status === 404) {
          setFatalError({ status, detail });
          setData(null);
        } else {
          setError(detail);
        }
        console.warn('[OrgBillingPage] billing load failed:', status, detail);
      })
      .finally(() => setLoading(false));
    billingService.plansAvailable(orgId).then(setAvailablePlans).catch(() => {});
  }, [orgId]);

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (logoFileRef.current) logoFileRef.current.value = '';
    const allowed = ['image/png', 'image/jpeg', 'image/jpg'];
    if (!allowed.includes(file.type)) {
      toast.error('יש להעלות תמונה בפורמט PNG או JPEG בלבד');
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      toast.error('גודל הקובץ חורג מ-2MB');
      return;
    }
    setLogoUploading(true);
    try {
      const result = await handoverService.uploadOrgLogo(orgId, file);
      setLogoUrl(result.logo_url);
      toast.success('הלוגו עודכן בהצלחה');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בהעלאת לוגו');
    } finally {
      setLogoUploading(false);
    }
  };

  const handleLogoDelete = async () => {
    setLogoDeleting(true);
    try {
      await handoverService.deleteOrgLogo(orgId);
      setLogoUrl(null);
      toast.success('הלוגו הוסר');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה במחיקת לוגו');
    } finally {
      setLogoDeleting(false);
    }
  };

  const loadMembers = useCallback(async () => {
    if (!orgId) return;
    setMembersLoading(true);
    setMembersError(null);
    setMembersDenied(false);
    try {
      const result = await orgMemberService.listMembers(orgId);
      setMembers(result.members || []);
    } catch (err) {
      if (err.response?.status === 403) {
        setMembersDenied(true);
        setMembers([]);
      } else {
        setMembersError('שגיאה בטעינת חברי ארגון');
      }
    } finally {
      setMembersLoading(false);
    }
  }, [orgId]);

  useEffect(() => { loadMembers(); }, [loadMembers]);

  useEffect(() => {
    if (!loading && !membersLoading && location.hash === '#responsibility' && responsibilityRef.current) {
      setTimeout(() => {
        responsibilityRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 300);
    }
  }, [loading, membersLoading, location.hash]);

  useEffect(() => {
    if (!loading && location.hash === '#requests') {
      setPaymentRequestsExpanded(true);
    }
  }, [loading, location.hash]);

  const handleRoleChange = (member, newRole) => {
    if (newRole === member.role) return;
    setConfirmDialog({ member, newRole });
  };

  const confirmRoleChange = async () => {
    if (!confirmDialog) return;
    const { member, newRole } = confirmDialog;
    setConfirmDialog(null);
    setChangingRole(member.user_id);
    try {
      await orgMemberService.changeRole(orgId, member.user_id, newRole);
      toast.success(`התפקיד של ${member.name || 'המשתמש'} שונה ל${getRoleLabel(newRole)}`);
      await loadMembers();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בשינוי תפקיד');
    } finally {
      setChangingRole(null);
    }
  };

  const loadRenewalPreview = useCallback(async (cycle) => {
    if (!orgId) return;
    setRenewalLoading(true);
    try {
      const result = await billingService.previewRenewal(orgId, cycle);
      setRenewalPreview(result);
    } catch {
      setRenewalPreview(null);
    } finally {
      setRenewalLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    if (data && !isSuspended) {
      loadRenewalPreview(renewalCycle);
    }
  }, [data, isSuspended, renewalCycle, loadRenewalPreview]);

  const handleCycleChange = (cycle) => {
    setRenewalCycle(cycle);
  };

  const handleHandoffCopy = () => {
    const billingUrl = `${window.location.origin}/billing/org/${orgId}`;
    const orgName = data?.org_name || '';
    const message = `שלום, אני צריך שדרוג/חידוש רישיון עבור הארגון "${orgName}".\nקישור לעמוד החיוב: ${billingUrl}`;
    navigator.clipboard.writeText(message).then(() => {
      toast.success('ההודעה הועתקה — שלח לבעלי הארגון');
    }).catch(() => {
      toast.error('לא הצלחנו להעתיק — נסה ידנית');
    });
  };

  const CYCLE_HE = { monthly: 'חודשי', yearly: 'שנתי' };

  const buildTemplateA = (result) => {
    const orgName = data?.org_name || '';
    const billingUrl = `${window.location.origin}/billing/org/${orgId}`;
    const cycleHe = CYCLE_HE[renewalCycle] || renewalCycle;
    return `שלום,\nכדי להפעיל/לחדש מנוי BrikOps לארגון: ${orgName}\nבחרתי: ${cycleHe}\nתוקף לאחר התשלום: עד ${result.requested_paid_until_display}\nסכום לתשלום: ₪${result.amount_ils}\n\nקישור לעמוד החיוב:\n${billingUrl}\n\nלאחר התשלום אנא שלחו אסמכתא למייל billing@brikops.com ונפעיל מיידית.\nתודה`;
  };

  const buildTemplateC = (result) => {
    const orgName = data?.org_name || '';
    const billingUrl = `${window.location.origin}/billing/org/${orgId}`;
    const cycleHe = CYCLE_HE[renewalCycle] || renewalCycle;
    return `היי,\nצריך לאשר שדרוג/חידוש מנוי BrikOps לארגון ${orgName}.\n\n• מסלול: ${cycleHe}\n• סכום: ₪${result.amount_ils}\n• תוקף לאחר תשלום: עד ${result.requested_paid_until_display}\n\nקישור לעמוד החיוב:\n${billingUrl}\n\nאפשר לאשר לי לאחר תשלום/העברה כדי שאפעיל את הרישיון.\nתודה!`;
  };

  const handlePaymentRequest = async () => {
    setPaymentRequestLoading(true);
    try {
      const result = await billingService.createPaymentRequest(orgId, renewalCycle);
      setPaymentRequestResult(result);
      if (result.existing_open) {
        toast('כבר קיימת בקשת תשלום פתוחה', { icon: 'ℹ️' });
        setPaymentRequestsExpanded(true);
      } else if (result.existing) {
        toast.success('בקשה קיימת נטענה');
      } else {
        toast.success('הבקשה נרשמה בהצלחה');
        loadPaymentRequests(paymentRequestsFilter);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה ביצירת בקשת תשלום';
      if (detail.includes('₪0') || detail.includes('0.00') || detail.toLowerCase().includes('amount is zero')) {
        toast('הסכום לתשלום הוא ₪0. יש לעדכן את תמחור הפרויקטים לפני יצירת בקשה.', { icon: '⚠️', duration: 5000 });
        setTimeout(() => {
          projectsSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 300);
      } else {
        toast.error(detail);
      }
    } finally {
      setPaymentRequestLoading(false);
    }
  };

  const handleCopyPaymentMessage = (template) => {
    if (!paymentRequestResult) return;
    const message = template === 'C' ? buildTemplateC(paymentRequestResult) : template === 'B' ? buildTemplateB(paymentRequestResult) : buildTemplateA(paymentRequestResult);
    navigator.clipboard.writeText(message).then(() => {
      toast.success('ההודעה הועתקה ללוח');
    }).catch(() => {
      toast.error('לא הצלחנו להעתיק — נסה ידנית');
    });
  };

  const handleMarkPaidAction = async () => {
    setMarkPaidLoading(true);
    try {
      const result = await billingService.markPaid(orgId, {
        requestId: paymentRequestResult?.request_id,
        cycle: renewalCycle,
      });
      const paidUntil = result?.paid_until ? new Date(result.paid_until).toLocaleDateString('he-IL') : '';
      toast.success(paidUntil ? `התשלום אושר — הרישיון עודכן עד ${paidUntil}.` : 'התשלום אושר — הרישיון עודכן');
      setPaymentRequestResult(null);
      const updated = await billingService.orgBilling(orgId);
      setData(updated);
      loadPaymentRequests(paymentRequestsFilter);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 403) {
        toast.error('אין לך הרשאה לבצע פעולה זו.');
      } else {
        toast.error(typeof detail === 'string' ? detail : 'שגיאה בסימון תשלום');
      }
    } finally {
      setMarkPaidLoading(false);
    }
  };

  const handleCustomerMarkPaid = async () => {
    if (!paymentRequestResult?.request_id) return;
    setCustomerMarkPaidLoading(true);
    try {
      await billingService.customerMarkPaid(orgId, paymentRequestResult.request_id);
      toast.success('הבקשה עודכנה: ממתין לאישור.');
      loadPaymentRequests(paymentRequestsFilter);
      setPaymentRequestResult(prev => prev ? { ...prev, _customerMarked: true } : prev);
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בסימון תשלום');
    } finally {
      setCustomerMarkPaidLoading(false);
    }
  };

  const handleReceiptUpload = async (requestId, file) => {
    if (!file) return;
    setReceiptUploading(true);
    try {
      await billingService.uploadReceipt(orgId, requestId, file);
      toast.success('האסמכתא הועלתה בהצלחה.');
      loadPaymentRequests(paymentRequestsFilter);
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בהעלאת אסמכתא');
    } finally {
      setReceiptUploading(false);
    }
  };

  const handleViewReceipt = async (requestId) => {
    try {
      const result = await billingService.getReceiptUrl(orgId, requestId);
      if (result.url) window.open(result.url, '_blank');
    } catch (err) {
      toast.error('לא ניתן לצפות באסמכתא');
    }
  };

  const handleAdminApprove = async (pr) => {
    setAdminApproveLoading(pr.id);
    try {
      const result = await billingService.markPaid(orgId, { requestId: pr.id });
      const paidUntil = result?.paid_until ? new Date(result.paid_until).toLocaleDateString('he-IL') : '';
      toast.success(paidUntil ? `התשלום אושר — הרישיון עודכן עד ${paidUntil}.` : 'התשלום אושר — הרישיון עודכן');
      loadPaymentRequests(paymentRequestsFilter);
      const updated = await billingService.orgBilling(orgId);
      setData(updated);
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'שגיאה באישור תשלום');
    } finally {
      setAdminApproveLoading(null);
    }
  };

  const handleAdminReject = async () => {
    if (!rejectModalRequest) return;
    setRejectLoading(true);
    try {
      await billingService.rejectPaymentRequest(orgId, rejectModalRequest.id, rejectReason);
      toast.success('הבקשה נדחתה.');
      setRejectModalRequest(null);
      setRejectReason('');
      loadPaymentRequests(paymentRequestsFilter);
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בדחיית בקשה');
    } finally {
      setRejectLoading(false);
    }
  };

  const handlePmPaymentRequest = async () => {
    setPaymentRequestLoading(true);
    try {
      const result = await billingService.createPaymentRequest(orgId, renewalCycle);
      setPaymentRequestResult(result);
      if (result.existing_open) {
        toast('כבר קיימת בקשת תשלום פתוחה', { icon: 'ℹ️' });
        setPaymentRequestsExpanded(true);
      } else {
        const message = buildTemplateC(result);
        navigator.clipboard.writeText(message).then(() => {
          toast.success('הבקשה נרשמה וההודעה הועתקה — שלח לבעלי הארגון');
        }).catch(() => {
          toast.success('הבקשה נרשמה');
        });
        loadPaymentRequests(paymentRequestsFilter);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה ביצירת בקשת תשלום';
      if (detail.includes('₪0') || detail.includes('0.00') || detail.toLowerCase().includes('amount is zero')) {
        toast('הסכום לתשלום הוא ₪0. יש לעדכן את תמחור הפרויקטים לפני יצירת בקשה.', { icon: '⚠️', duration: 5000 });
        setTimeout(() => {
          projectsSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 300);
      } else {
        toast.error(detail);
      }
    } finally {
      setPaymentRequestLoading(false);
    }
  };

  const loadPaymentRequests = useCallback(async (filter) => {
    if (!orgId || !canViewRequests) return;
    setPaymentRequestsLoading(true);
    try {
      const statusParam = filter === 'open' ? 'requested,sent,pending_review' : filter === 'all' ? '' : filter === 'pending_review' ? 'pending_review' : filter;
      const result = await billingService.listPaymentRequests(orgId, statusParam);
      setPaymentRequests(result.requests || []);
      if (filter === 'open' && (result.requests || []).length > 0) {
        setPaymentRequestsExpanded(true);
      }
    } catch {
      setPaymentRequests([]);
    } finally {
      setPaymentRequestsLoading(false);
    }
  }, [orgId, canViewRequests]);

  useEffect(() => {
    if (data && canViewRequests) {
      loadPaymentRequests(paymentRequestsFilter);
    }
  }, [data, canViewRequests, paymentRequestsFilter, loadPaymentRequests]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const hlId = params.get('highlight');
    const hasRequestsHash = location.hash === '#requests';
    if (hlId || hasRequestsHash) {
      setPaymentRequestsExpanded(true);
      if (hlId) {
        setHighlightRequestId(hlId);
        highlightRetried.current = false;
      }
    }
  }, [location.search, location.hash]);

  useEffect(() => {
    if (!highlightRequestId || paymentRequestsLoading) return;
    if (paymentRequests.length === 0 && highlightRetried.current) return;
    const found = paymentRequests.find(pr => pr.id === highlightRequestId);
    if (!found && !highlightRetried.current) {
      highlightRetried.current = true;
      setPaymentRequestsFilter('all');
      return;
    }
    if (found) {
      setTimeout(() => {
        const el = document.querySelector(`[data-request-id="${highlightRequestId}"]`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('highlight-flash');
          setTimeout(() => {
            el.classList.remove('highlight-flash');
            setHighlightRequestId(null);
          }, 3000);
        }
      }, 200);
    }
  }, [highlightRequestId, paymentRequests, paymentRequestsLoading]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const pid = params.get('project_id');
    if (pid) {
      setSourceProjectId(pid);
      projectService.get(pid).then(p => {
        if (p?.name) setSourceProjectName(p.name);
      }).catch(() => {});
    }
  }, [location.search]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const paymentStatus = params.get('payment');
    if (paymentStatus === 'success') {
      toast.success('התשלום התקבל בהצלחה! הרישיון יעודכן תוך דקות ספורות.');
      const newParams = new URLSearchParams(location.search);
      newParams.delete('payment');
      const newSearch = newParams.toString();
      navigate(`${location.pathname}${newSearch ? '?' + newSearch : ''}${location.hash}`, { replace: true });
      setTimeout(async () => {
        try {
          const updated = await billingService.orgBilling(orgId);
          setData(updated);
        } catch {}
      }, 3000);
    } else if (paymentStatus === 'failure') {
      toast.error('התשלום לא הושלם. ניתן לנסות שוב.');
      const newParams = new URLSearchParams(location.search);
      newParams.delete('payment');
      const newSearch = newParams.toString();
      navigate(`${location.pathname}${newSearch ? '?' + newSearch : ''}${location.hash}`, { replace: true });
    }
  }, [location.search, location.pathname, location.hash, navigate, orgId]);

  useEffect(() => {
    if (data && location.hash === '#billing') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [data, location.hash]);

  useEffect(() => {
    if (!data || loading) return;
    const params = new URLSearchParams(location.search);
    const focus = params.get('focus');
    if ((focus === 'renew' || location.hash === '#renew') && renewRef.current) {
      setTimeout(() => {
        renewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        renewRef.current?.classList.add('renew-highlight');
        setTimeout(() => renewRef.current?.classList.remove('renew-highlight'), 2000);
      }, 400);
    }
  }, [data, loading, location.search, location.hash]);

  useEffect(() => {
    if (data?.payment_config) {
      setPaymentConfigBank(data.payment_config.bank_details || '');
      setPaymentConfigBit(data.payment_config.bit_phone || '');
    }
  }, [data]);

  const handleSavePaymentConfig = async () => {
    setPaymentConfigSaving(true);
    try {
      await billingService.updatePaymentConfig(orgId, {
        bank_details: paymentConfigBank,
        bit_phone: paymentConfigBit,
      });
      toast.success('הגדרות תשלום נשמרו');
      const updated = await billingService.orgBilling(orgId);
      setData(updated);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בשמירת הגדרות');
    } finally {
      setPaymentConfigSaving(false);
    }
  };

  const hasPaymentOptions = data?.payment_config?.has_payment_options;

  const buildTemplateB = (result) => {
    const orgName = data?.org_name || '';
    const billingUrl = `${window.location.origin}/billing/org/${orgId}`;
    const cycleHe = CYCLE_HE[renewalCycle] || renewalCycle;
    const bankLine = paymentConfigBank ? `1) העברה בנקאית: ${paymentConfigBank}` : '';
    const bitLine = paymentConfigBit ? `${bankLine ? '2' : '1'}) Bit: ${paymentConfigBit}` : '';
    const paymentLines = [bankLine, bitLine].filter(Boolean).join('\n');
    return `שלום,\nמצורפת בקשת תשלום להפעלת/חידוש מנוי BrikOps עבור הארגון: ${orgName}\n\n• מסלול: ${cycleHe}\n• תקופת רישיון לאחר אישור התשלום: עד ${result.requested_paid_until_display}\n• סכום: ₪${result.amount_ils}\n• קישור חיוב/פרטים: ${billingUrl}\n\nאפשרויות תשלום:\n${paymentLines}\n\nלאחר התשלום, אנא שלחו אסמכתא (צילום/מספר עסקה) ונעדכן את הרישיון מיידית.\nתודה,\nצוות BrikOps\nsupport@brikops.com`;
  };

  if (loading) return <div className="flex justify-center items-center h-64"><div className="text-slate-500">טוען...</div></div>;
  if (error) return (
    <div className="max-w-2xl mx-auto p-6" dir="rtl">
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 space-y-4">
        <div className="text-red-700 font-medium">{error}</div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setLoading(true);
              setError(null);
              setFatalError(null);
              billingService.orgBilling(orgId)
                .then(setData)
                .catch(err => {
                  const status = err.response?.status;
                  const detail = err.response?.data?.detail || 'שגיאה בטעינת נתוני חיוב';
                  if (status === 403 || status === 404) {
                    setFatalError({ status, detail });
                    setData(null);
                  } else {
                    setError(detail);
                  }
                  console.warn('[OrgBillingPage] retry failed:', status, detail);
                })
                .finally(() => setLoading(false));
            }}
            className="bg-red-600 hover:bg-red-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            נסה שוב
          </button>
          <button onClick={() => navigate(-1)} className="text-slate-500 hover:text-slate-700 text-sm">חזרה</button>
        </div>
      </div>
    </div>
  );
  if (fatalError) return (
    <div className="max-w-2xl mx-auto p-6" dir="rtl">
      <div className="bg-white rounded-xl border border-slate-200 p-8 space-y-6">
        <div className="text-center space-y-3">
          <div className="text-4xl">🚫</div>
          <h2 className="text-xl font-bold text-slate-800">
            {fatalError.status === 403 ? 'אין הרשאת צפייה בחיוב' : 'הארגון לא נמצא'}
          </h2>
          <p className="text-sm text-slate-500">
            {fatalError.status === 403
              ? 'אין לך הרשאה לצפות בנתוני החיוב של ארגון זה. פנה לבעלי הארגון.'
              : 'הארגון המבוקש לא נמצא במערכת. ייתכן שהקישור שגוי.'}
          </p>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
          <div className="flex items-start gap-2 text-sm text-amber-800">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span className="font-medium">צריך עזרה? צרו קשר עם צוות BrikOps</span>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <a
              href="https://wa.me/972559943649?text=%D7%A9%D7%9C%D7%95%D7%9D%2C%20%D7%90%D7%A0%D7%99%20%D7%A8%D7%95%D7%A6%D7%94%20%D7%9C%D7%A9%D7%93%D7%A8%D7%92%20%D7%90%D7%AA%20%D7%94%D7%9E%D7%A0%D7%95%D7%99%20%D7%A9%D7%9C%D7%99"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
            >
              WhatsApp
            </a>
            <a
              href="mailto:billing@brikops.com?subject=בקשת שדרוג מנוי"
              className="flex-1 flex items-center justify-center gap-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
            >
              billing@brikops.com
            </a>
          </div>
        </div>
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            onClick={() => {
              setLoading(true);
              setFatalError(null);
              setError(null);
              billingService.orgBilling(orgId)
                .then(setData)
                .catch(err => {
                  const status = err.response?.status;
                  const detail = err.response?.data?.detail || 'שגיאה בטעינת נתוני חיוב';
                  if (status === 403 || status === 404) {
                    setFatalError({ status, detail });
                    setData(null);
                  } else {
                    setError(detail);
                  }
                })
                .finally(() => setLoading(false));
            }}
            className="flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg px-5 py-2 text-sm font-medium transition-colors"
          >
            נסה שוב
          </button>
          <button onClick={() => navigate(-1)} className="text-slate-500 hover:text-slate-700 text-sm px-4 py-2">
            חזרה
          </button>
        </div>
        <div className="text-center text-xs text-slate-400 pt-2">
          קוד ארגון: <bdi dir="ltr">{orgId}</bdi>
          {fatalError.status && <span className="mr-2">(שגיאה {fatalError.status})</span>}
        </div>
      </div>
    </div>
  );
  if (!data) return (
    <div className="flex justify-center items-center h-64">
      <div className="text-slate-500">טוען נתוני חיוב...</div>
    </div>
  );

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-6" dir="rtl">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <button onClick={() => navigate(-1)} className="hover:text-slate-700">חזרה</button>
        <ChevronRight className="w-4 h-4" />
        <span className="font-medium text-slate-700">חיוב ארגון</span>
      </div>

      {sourceProjectId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 flex items-center justify-between">
          <div className="text-sm text-blue-800">
            {sourceProjectName
              ? <span>הגעת מפרויקט: <strong>{sourceProjectName}</strong></span>
              : <span>הגעת מפרויקט</span>
            }
          </div>
          <button
            onClick={() => navigate(`/projects/${sourceProjectId}`)}
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            <ArrowRight className="w-3.5 h-3.5" />
            חזרה לפרויקט
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {logoUrl && (
              <img src={logoUrl} alt="לוגו ארגון" className="h-10 w-auto max-w-[80px] object-contain rounded" />
            )}
            <h1 className="text-xl font-bold text-slate-800">{data.org_name}</h1>
          </div>
          <span className={`text-sm font-medium px-3 py-1 rounded-full ${
            SUBSCRIPTION_STATUS_COLORS[subStatus] || 'bg-slate-100 text-slate-500'
          }`}>
            {SUBSCRIPTION_STATUS_LABELS[subStatus] || '—'}
          </span>
        </div>

        {canEditLogo && (
          <div className="flex items-center gap-3 bg-slate-50 rounded-lg p-3">
            <div className="flex-shrink-0">
              {logoUrl ? (
                <img src={logoUrl} alt="לוגו ארגון" className="h-14 w-14 object-contain rounded border border-slate-200 bg-white p-1" />
              ) : (
                <div className="h-14 w-14 flex items-center justify-center rounded border border-dashed border-slate-300 bg-white text-slate-400">
                  <Upload className="w-5 h-5" />
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-slate-700">לוגו ארגון</div>
              <div className="text-xs text-slate-500">יוצג בכותרת פרוטוקולי מסירה · PNG/JPEG · עד 2MB</div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <input
                ref={logoFileRef}
                type="file"
                accept="image/png,image/jpeg"
                className="hidden"
                onChange={handleLogoUpload}
              />
              <button
                onClick={() => logoFileRef.current?.click()}
                disabled={logoUploading}
                className="text-xs font-medium px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
              >
                {logoUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                {logoUrl ? 'החלף' : 'העלאה'}
              </button>
              {logoUrl && (
                <button
                  onClick={handleLogoDelete}
                  disabled={logoDeleting}
                  className="text-xs font-medium px-2.5 py-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-50 flex items-center gap-1"
                >
                  {logoDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
                  הסרה
                </button>
              )}
            </div>
          </div>
        )}

        {sub && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-slate-500 mb-1">מצב מנוי</div>
              <div className="font-semibold">
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${
                  SUBSCRIPTION_STATUS_COLORS[subStatus] || 'bg-slate-100 text-slate-500'
                }`}>
                  {SUBSCRIPTION_STATUS_LABELS[subStatus] || '—'}
                </span>
              </div>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-slate-500 mb-1">מצב גישה</div>
              <div className="font-semibold flex items-center gap-1.5">
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${
                  sub.effective_access === 'full_access'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-red-100 text-red-700'
                }`}>
                  {getAccessLabel(sub.effective_access)}
                </span>
                {sub.effective_access === 'read_only' && sub.read_only_reason && (
                  <span className="relative group cursor-help">
                    <Info className="w-3.5 h-3.5 text-slate-400" />
                    <span className="absolute z-10 hidden group-hover:block bg-slate-800 text-white text-xs rounded-lg px-3 py-2 -top-2 right-6 w-48 leading-relaxed shadow-lg">
                      {sub.read_only_reason === 'trial_expired' && 'הניסיון הסתיים. כדי להמשיך לעבוד צריך לחדש מנוי.'}
                      {sub.read_only_reason === 'payment_expired' && 'התשלום פג תוקף. יש לחדש כדי להמשיך.'}
                      {sub.read_only_reason === 'no_subscription' && 'אין מנוי פעיל. יש לרכוש מנוי.'}
                      {sub.read_only_reason === 'suspended' && 'המנוי הושעה על ידי מנהל המערכת.'}
                    </span>
                  </span>
                )}
              </div>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              {subStatus === 'trial' && sub.trial_end_at ? (
                <>
                  <div className="text-slate-500 mb-1">ניסיון עד</div>
                  <div className="font-medium text-blue-600">{formatDate(sub.trial_end_at)}</div>
                </>
              ) : sub.paid_until ? (() => {
                const paidDate = new Date(sub.paid_until);
                const now = new Date();
                const daysLeft = Math.ceil((paidDate - now) / 86400000);
                const isExpired = subStatus === 'expired' || subStatus === 'past_due';
                const isWarning = !isExpired && daysLeft <= 14;
                return (
                  <>
                    <div className="text-slate-500 mb-1">{isExpired ? 'שולם עד' : 'בתוקף עד'}</div>
                    <div className={`font-medium ${
                      isExpired ? 'text-red-600' : isWarning ? 'text-amber-600' : 'text-emerald-600'
                    }`}>
                      {paidDate.toLocaleDateString('he-IL')}
                      {isExpired && ' (פג תוקף)'}
                      {isWarning && ` (${daysLeft} ימים)`}
                    </div>
                  </>
                );
              })() : (
                <>
                  <div className="text-slate-500 mb-1">בתוקף עד</div>
                  <div className="font-medium text-slate-500">—</div>
                </>
              )}
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-slate-500 mb-1">סה״כ חודשי</div>
              <div className="font-bold text-lg text-slate-900">{formatCurrency(sub.total_monthly)}</div>
            </div>
            {sub.billing_cycle && (
              <div className="bg-slate-50 rounded-lg p-3">
                <div className="text-slate-500 mb-1">מחזור חיוב</div>
                <div className="font-medium text-slate-700">{CYCLE_LABELS[sub.billing_cycle] || sub.billing_cycle}</div>
              </div>
            )}
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-slate-500 mb-1">חידוש אוטומטי</div>
              <div className="font-medium text-slate-700">{sub.auto_renew ? 'כן' : 'לא'}</div>
            </div>
          </div>
        )}

        {isActive && !canManageBilling && (
          <div className="flex items-start gap-2 bg-slate-100 border border-slate-200 rounded-lg p-3 text-sm text-slate-700">
            <Info className="w-4 h-4 mt-0.5 shrink-0 text-slate-500" />
            <div>
              <span className="font-medium">צפייה בלבד — אין הרשאה לניהול חיוב</span>
              {data.owner_name && (
                <span className="block text-xs text-slate-500 mt-1">בעלים: {data.owner_name}</span>
              )}
            </div>
          </div>
        )}

        {needsUpgrade && canManageBilling && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span>{sub?.read_only_reason === 'payment_expired'
              ? 'התשלום פג תוקף. יש לחדש את המנוי כדי לשחזר גישה מלאה.'
              : 'תקופת הניסיון הסתיימה. יש לשדרג למנוי בתשלום.'
            }</span>
          </div>
        )}

        {needsUpgrade && !canManageBilling && (
          <div className="flex items-start gap-2 bg-slate-100 border border-slate-200 rounded-lg p-3 text-sm text-slate-700">
            <Info className="w-4 h-4 mt-0.5 shrink-0 text-slate-500" />
            <div>
              <span className="font-medium">הרישיון פג — פנה לבעלי הארגון</span>
              {data.owner_name && (
                <span className="block text-xs text-slate-500 mt-1">בעלים: {data.owner_name}</span>
              )}
            </div>
          </div>
        )}

        {isTrial && canManageBilling && sub?.trial_end_at && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            <span className="shrink-0 mt-0.5">⏳</span>
            <span>תקופת ניסיון עד {formatDate(sub.trial_end_at)} — שדרגו למנוי בתשלום להמשך גישה מלאה.</span>
          </div>
        )}

        {isSuspended && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
            <span className="shrink-0 mt-0.5">⛔</span>
            <span>המנוי הושעה — פנה לתמיכה.</span>
          </div>
        )}
      </div>

      {!isSuspended && (canManageBilling || isOwner || isSA) && (
        <div ref={renewRef} id="renew" className="bg-white rounded-xl border-2 border-amber-200 p-6 space-y-5 transition-all duration-300" style={{ scrollMarginTop: '1rem' }}>
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-slate-800">
              {(needsUpgrade || isTrial) ? 'שדרוג / חידוש מנוי' : 'חידוש מנוי'}
            </h2>
          </div>

          {needsUpgrade && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              {sub?.read_only_reason === 'trial_expired'
                ? 'הניסיון הסתיים — נדרש שדרוג כדי להמשיך לעבוד'
                : sub?.read_only_reason === 'payment_expired'
                  ? 'התשלום פג תוקף — נדרש חידוש כדי לשחזר גישה מלאה'
                  : 'אין מנוי פעיל — נדרש שדרוג'}
            </div>
          )}

          {sub?.plan_id === 'founder_6m' && sub?.plan_locked_until && (() => {
            const daysLeft = Math.max(0, Math.ceil((new Date(sub.plan_locked_until) - new Date()) / (1000 * 60 * 60 * 24)));
            return daysLeft <= 60 ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
                תוכנית מייסדים מסתיימת בעוד {daysLeft} ימים. לאחר מכן תעבור אוטומטית לתוכנית רגילה.
              </div>
            ) : null;
          })()}

          {availablePlans && (needsUpgrade || isTrial) && (
            <PlanSelector
              plans={availablePlans}
              onSelect={setSelectedPlan}
              currentPlan={sub?.plan_id}
              selectedPlan={selectedPlan}
              loading={false}
            />
          )}

          {needsUpgrade && data.projects?.length > 0 && (
            <UpgradeWizard
              orgId={orgId}
              projects={data.projects}
              canManageBilling={canManageBilling || isOwner}
              onPaymentRequested={(result) => {
                setPaymentRequestResult(result);
                loadPaymentRequests(paymentRequestsFilter);
                billingService.orgBilling(orgId).then(setData).catch(() => {});
              }}
              renewalCycle={renewalCycle}
              onCycleChange={(cycle) => setRenewalCycle(cycle)}
              selectedPlan={selectedPlan}
            />
          )}

          {!(needsUpgrade && data.projects?.length > 0) && (<>
          {(() => {
            const isFounderExpiring = sub?.plan_id === 'founder_6m' && sub?.plan_locked_until;
            const lockedDate = isFounderExpiring ? new Date(sub.plan_locked_until) : null;
            const daysLeft = lockedDate ? Math.ceil((lockedDate - new Date()) / 86400000) : null;
            const founderExpiring = daysLeft !== null && daysLeft <= 30;
            const projectedStandard = data.projects?.reduce((sum, pb, idx) => {
              const units = pb.contracted_units || 0;
              const ppu = pb.price_per_unit || 20;
              const license = idx === 0 ? 900 : 450;
              return sum + license + (units * ppu);
            }, 0) || 0;
            if (!founderExpiring) return null;
            const formattedDate = lockedDate.toLocaleDateString('he-IL');
            return (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800 space-y-1">
                <p className="font-semibold">
                  {daysLeft > 0
                    ? `תוכנית המייסדים מסתיימת בתאריך ${formattedDate}`
                    : `תוכנית המייסדים הסתיימה בתאריך ${formattedDate}`}
                </p>
                <p>
                  {`לאחר סיום, המנוי יעבור לתוכנית רגילה בעלות ${projectedStandard.toLocaleString()}₪/חודש`}
                </p>
              </div>
            );
          })()}
          <div className="bg-white border border-emerald-200 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700">תשלום באשראי</span>
            </div>
            {(() => {
              const totalMonthly = sub?.total_monthly || 0;
              const currentPaidUntil = sub?.paid_until ? new Date(sub.paid_until) : new Date();
              const baseDate = currentPaidUntil > new Date() ? currentPaidUntil : new Date();
              const nextDate = new Date(baseDate);
              nextDate.setMonth(nextDate.getMonth() + 1);
              const formatted = nextDate.toLocaleDateString('he-IL');
              return totalMonthly > 0 ? (
                <p className="text-sm text-slate-600 text-center">
                  {`\u200F\u05DC\u05D0\u05D7\u05E8 \u05EA\u05E9\u05DC\u05D5\u05DD ${totalMonthly.toLocaleString()}\u20AA \u05D4\u05DE\u05E0\u05D5\u05D9 \u05D9\u05D4\u05D9\u05D4 \u05D1\u05EA\u05D5\u05E7\u05E3 \u05E2\u05D3 ${formatted}`}
                </p>
              ) : null;
            })()}
            <button
              disabled={checkoutLoading}
              onClick={async () => {
                setCheckoutLoading(true);
                try {
                  const result = await billingService.checkout(orgId, renewalCycle, selectedPlan || 'standard');
                  if (result.payment_page_link) {
                    window.location.href = result.payment_page_link;
                  } else {
                    toast.error('לא התקבל קישור תשלום');
                  }
                } catch (err) {
                  toast.error(err.response?.data?.detail || 'שגיאה ביצירת טופס תשלום');
                } finally {
                  setCheckoutLoading(false);
                }
              }}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 px-4 rounded-lg text-sm flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {checkoutLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
              {checkoutLoading ? 'מעביר לתשלום...' : `שלם באשראי — \u20AA${(sub?.total_monthly || 0).toLocaleString()}`}
            </button>
            <p className="text-xs text-slate-400 text-center">תועבר לדף תשלום מאובטח</p>
          </div>

          <button
            onClick={() => setPaymentOptionsExpanded(!paymentOptionsExpanded)}
            className="w-full flex items-center justify-between bg-white border border-slate-200 rounded-lg px-4 py-3 hover:bg-slate-50 transition-colors"
          >
            <span className="text-sm font-medium text-slate-700">אפשרויות תשלום נוספות</span>
            {paymentOptionsExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {paymentOptionsExpanded && (
          <div className="bg-white border border-amber-200 rounded-lg p-4 space-y-4">
            <span className="text-sm font-medium text-slate-700">שלח בקשת תשלום</span>

            {data.projects?.length > 0 && (
              <div className="space-y-2">
                <span className="text-xs font-medium text-slate-500">תמחור פרויקטים:</span>
                {data.projects.map(pb => {
                  const badge = getPlanBadge(pb.plan_id);
                  const isConfigured = pb.plan_id && pb.contracted_units > 0;
                  return (
                    <div key={pb.project_id} className={`rounded-lg p-3 space-y-1 ${isConfigured ? 'bg-slate-50 border border-slate-200' : 'bg-amber-50 border border-amber-300'}`}>
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-700">{pb.project_name || pb.project_id}</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setEditingProjectBilling(pb)}
                            className="flex items-center gap-1 text-xs text-amber-700 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 px-2 py-1 rounded transition-colors"
                          >
                            <Pencil className="w-3 h-3" />
                            ערוך
                          </button>
                          {isConfigured && (
                            <span className="text-sm font-bold text-slate-900 flex-shrink-0">{formatCurrency(pb.monthly_total)}/חודש</span>
                          )}
                        </div>
                      </div>
                      {isConfigured ? (
                        <div className="flex items-center gap-3 text-xs text-slate-500">
                          <span className="font-medium text-slate-700">{getPlanLabel(pb.plan_id)}</span>
                          {badge && <span className="px-1.5 py-0.5 rounded-full font-medium bg-slate-200 text-slate-600">{badge}</span>}
                          <span>{pb.contracted_units} יחידות</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 text-xs text-amber-700">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>חסר תמחור — יש לבחור חבילה ומספר יחידות</span>
                        </div>
                      )}
                    </div>
                  );
                })}
                {(() => {
                  const totalMonthly = data.projects.reduce((sum, pb) => sum + (pb.monthly_total || 0), 0);
                  return totalMonthly > 0 ? (
                    <div className="flex justify-between items-center pt-2 border-t border-slate-200">
                      <span className="text-sm font-medium text-slate-600">סה״כ חודשי</span>
                      <span className="text-base font-bold text-slate-900">{formatCurrency(totalMonthly)}</span>
                    </div>
                  ) : null;
                })()}
              </div>
            )}

            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-600">מחזור:</span>
              <div className="flex rounded-lg border border-slate-200 overflow-hidden">
                <button
                  onClick={() => handleCycleChange('monthly')}
                  className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                    renewalCycle === 'monthly'
                      ? 'bg-amber-500 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  חודשי
                </button>
                <button
                  onClick={() => handleCycleChange('yearly')}
                  className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                    renewalCycle === 'yearly'
                      ? 'bg-amber-500 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  שנתי
                </button>
              </div>
            </div>
            {renewalLoading ? (
              <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-amber-500" /></div>
            ) : renewalPreview ? (
              <div className="bg-amber-50 rounded-lg p-4 space-y-2">
                <div className="text-sm text-amber-800">
                  <span className="font-medium">הרישיון יהיה בתוקף עד: </span>
                  <span className="font-bold">{renewalPreview.new_paid_until_display}</span>
                </div>
              </div>
            ) : null}

            {data.projects?.some(pb => !pb.plan_id || !pb.contracted_units || pb.contracted_units < 1) && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>יש להגדיר תמחור לכל הפרויקטים לפני שליחת בקשת תשלום</span>
              </div>
            )}

            <button
              onClick={handlePaymentRequest}
              disabled={paymentRequestLoading || data.projects?.some(pb => !pb.plan_id || !pb.contracted_units || pb.contracted_units < 1)}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 px-4 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {paymentRequestLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              שלח בקשת תשלום
            </button>
            {paymentRequestResult && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2 text-emerald-700 text-sm font-medium">
                  <span>הבקשה נשלחה. נחזור אליך בהקדם.</span>
                </div>
                <div className="text-xs text-slate-600 space-y-1">
                  <div>מזהה בקשה: <span className="font-mono text-xs">{paymentRequestResult.request_id?.slice(0, 8)}...</span></div>
                  <div>תוקף לאחר תשלום: <span className="font-bold">{paymentRequestResult.requested_paid_until_display}</span></div>
                  <div>סכום: <span className="font-bold">₪{paymentRequestResult.amount_ils}</span></div>
                </div>
                <button
                  onClick={() => handleCopyPaymentMessage('A')}
                  className="w-full bg-white border border-emerald-300 text-emerald-700 hover:bg-emerald-50 font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2"
                >
                  <Copy className="w-4 h-4" />
                  העתק הודעת תשלום
                </button>
                {hasPaymentOptions && (
                  <button
                    onClick={() => handleCopyPaymentMessage('B')}
                    className="w-full bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2"
                  >
                    <Copy className="w-4 h-4" />
                    העתק הודעה מפורטת (עם אפשרויות תשלום)
                  </button>
                )}
              </div>
            )}
            {paymentRequestResult && (
              <div className="border-t border-slate-200 pt-4 space-y-3">
                {paymentRequestResult._customerMarked ? (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
                    כבר סומן כשולם — ממתין לאישור
                  </div>
                ) : (
                  <>
                    <button
                      onClick={handleCustomerMarkPaid}
                      disabled={customerMarkPaidLoading}
                      className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 px-4 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {customerMarkPaidLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                      סימנתי ששילמתי
                    </button>
                    <p className="text-xs text-slate-500 text-center">הרישיון מתעדכן רק לאחר אישור אדמין.</p>
                  </>
                )}
                <div className="space-y-2">
                  <input
                    type="file"
                    ref={receiptFileRef}
                    className="hidden"
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleReceiptUpload(paymentRequestResult.request_id, file);
                      e.target.value = '';
                    }}
                  />
                  <button
                    onClick={() => receiptFileRef.current?.click()}
                    disabled={receiptUploading}
                    className="w-full bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {receiptUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    העלה אסמכתא
                  </button>
                  <p className="text-xs text-slate-400 text-center">אופציונלי — מסייע לאישור מהיר יותר.</p>
                </div>
              </div>
            )}
          </div>
          )}
          </>)}

          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700">חידוש אוטומטי</span>
              <div className="flex items-center gap-2">
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">בקרוב</span>
                <div className="w-10 h-5 bg-slate-300 rounded-full opacity-50 relative">
                  <div className="w-4 h-4 bg-white rounded-full absolute top-0.5 left-0.5 shadow-sm" />
                </div>
              </div>
            </div>
            <p className="text-xs text-slate-400">בקרוב תוכל להפעיל חידוש אוטומטי באשראי.</p>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-3">
            <span className="text-sm font-medium text-slate-700">צריך עזרה?</span>
            <p className="text-xs text-slate-500">אם יש בעיה טכנית או צורך במסמך/חשבונית</p>
            <div className="flex flex-col sm:flex-row gap-2">
              <a
                href="https://wa.me/972559943649?text=%D7%A9%D7%9C%D7%95%D7%9D%2C%20%D7%90%D7%A0%D7%99%20%D7%A8%D7%95%D7%A6%D7%94%20%D7%9C%D7%A9%D7%93%D7%A8%D7%92%20%D7%90%D7%AA%20%D7%94%D7%9E%D7%A0%D7%95%D7%99%20%D7%A9%D7%9C%D7%99"
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              >
                WhatsApp
              </a>
              <a
                href="mailto:billing@brikops.com?subject=בקשת שדרוג מנוי"
                className="flex-1 flex items-center justify-center gap-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              >
                billing@brikops.com
              </a>
            </div>
          </div>

          {isSA && (
            <div className="border-t border-slate-200 pt-4">
              <button
                onClick={handleMarkPaidAction}
                disabled={markPaidLoading}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 px-4 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {markPaidLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                אשר תשלום
              </button>
            </div>
          )}
        </div>
      )}

      {!isSuspended && !canManageBilling && isPM && !data?.is_owner && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-800">{(needsUpgrade || isTrial) ? 'בקשת שדרוג' : 'בקשת חידוש מנוי'}</h2>
          <p className="text-sm text-slate-600">
            אין לך הרשאה לניהול חיוב. שלח בקשה לבעלי הארגון לחידוש הרישיון.
          </p>
          {data.owner_name && (
            <div className="text-xs text-slate-500">בעלים: {data.owner_name}</div>
          )}
          <button
            onClick={handlePmPaymentRequest}
            disabled={paymentRequestLoading}
            className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 px-4 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {paymentRequestLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Copy className="w-4 h-4" />}
            בקש שדרוג מבעלים
          </button>
          {paymentRequestResult && !canManageBilling && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 space-y-2">
              <div className="text-sm text-emerald-700 font-medium">הבקשה נרשמה</div>
              <div className="text-xs text-slate-600">
                מזהה: <span className="font-mono">{paymentRequestResult.request_id?.slice(0, 8)}...</span>
              </div>
              <button
                onClick={() => handleCopyPaymentMessage('C')}
                className="w-full bg-white border border-emerald-300 text-emerald-700 hover:bg-emerald-50 font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2"
              >
                <Copy className="w-4 h-4" />
                העתק הודעה לבעלים
              </button>
            </div>
          )}
        </div>
      )}

      {canViewRequests && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <button
            onClick={() => setPaymentRequestsExpanded(!paymentRequestsExpanded)}
            className="flex items-center justify-between w-full"
          >
            <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
              בקשות תשלום
              {paymentRequests.length > 0 && (
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{paymentRequests.length}</span>
              )}
            </h2>
            {paymentRequestsExpanded ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
          </button>
          {paymentRequestsExpanded && (
            <div className="space-y-3">
              <div className="flex gap-2 flex-wrap">
                {(isSA ? ['open', 'pending_review', 'paid', 'rejected', 'canceled', 'all'] : ['open', 'pending_review', 'paid', 'canceled', 'all']).map(f => (
                  <button
                    key={f}
                    onClick={() => setPaymentRequestsFilter(f)}
                    className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
                      paymentRequestsFilter === f
                        ? 'bg-amber-500 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {{ open: 'פתוחות', pending_review: 'ממתין לאישור', paid: 'אושר ושולם', rejected: 'נדחה', canceled: 'בוטל', all: 'הכל' }[f]}
                  </button>
                ))}
              </div>
              {isPM && !canManageBilling && (
                <div className="text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2">
                  צפייה בלבד — מוצגות רק הבקשות שפתחת.
                </div>
              )}
              {paymentRequestsLoading ? (
                <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-amber-500" /></div>
              ) : paymentRequests.length === 0 ? (
                <div className="text-sm text-slate-400 py-2">אין בקשות תשלום</div>
              ) : (
                <div className="space-y-2">
                  {paymentRequests.map(pr => {
                    const statusColors = { requested: 'bg-amber-100 text-amber-700', sent: 'bg-blue-100 text-blue-700', pending_review: 'bg-amber-100 text-amber-800', paid: 'bg-emerald-100 text-emerald-700', rejected: 'bg-red-100 text-red-700', canceled: 'bg-slate-100 text-slate-500' };
                    const statusLabels = { requested: 'ממתין לתשלום', sent: 'נשלח', pending_review: 'ממתין לאישור', paid: 'אושר ושולם', rejected: 'נדחה', canceled: 'בוטל' };
                    const statusHelpers = { requested: 'לאחר התשלום סמן \'סימנתי ששילמתי\' (אפשר לצרף אסמכתא כדי לזרז).', pending_review: 'סימנת ששילמת. האישור יתבצע לאחר בדיקה. אפשר לצרף אסמכתא כדי לזרז.', paid: 'התשלום אושר והרישיון עודכן.', rejected: 'הבקשה נדחתה. לפרטים פנה לתמיכה.', canceled: 'הבקשה בוטלה.' };
                    const cycleLabels = { monthly: 'חודשי', yearly: 'שנתי' };
                    const fmtDate = (dt) => { if (!dt) return '—'; const d = new Date(dt); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`; };
                    return (
                      <div key={pr.id} data-request-id={pr.id} className="bg-slate-50 rounded-lg p-3 text-sm space-y-2 transition-colors duration-500">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[pr.status] || 'bg-slate-100 text-slate-500'}`}>
                              {statusLabels[pr.status] || pr.status}
                            </span>
                            <span className="text-xs text-slate-500">{cycleLabels[pr.cycle] || pr.cycle}</span>
                            <span className="text-xs font-medium text-slate-700">₪{pr.amount_ils}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-slate-400">מס׳ בקשה (לתמיכה):</span>
                            <span className="text-xs text-slate-500 font-mono">{pr.id?.slice(-8)}</span>
                            <button
                              onClick={() => { navigator.clipboard.writeText(pr.id); toast.success('מזהה בקשה הועתק'); }}
                              className="text-slate-400 hover:text-slate-600 p-0.5"
                              title="העתק מזהה מלא"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                        <div className="flex items-center justify-between text-xs text-slate-500">
                          <span>{pr.requester_name || '—'}</span>
                          <span>נוצר בתאריך: <bdi dir="ltr">{fmtDate(pr.created_at)}</bdi></span>
                        </div>
                        {pr.requested_paid_until && (
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-emerald-600 font-medium">מבוקש להאריך עד: <bdi dir="ltr">{fmtDate(pr.requested_paid_until)}</bdi></span>
                          </div>
                        )}
                        {pr.note && <div className="text-xs text-slate-400">{pr.note}</div>}
                        {pr.customer_paid_note && <div className="text-xs text-slate-400">הערת לקוח: {pr.customer_paid_note}</div>}
                        {pr.rejection_reason && <div className="text-xs text-red-600">סיבת דחייה: {pr.rejection_reason}</div>}
                        {statusHelpers[pr.status] && (
                          <div className="text-xs text-slate-400 italic">{statusHelpers[pr.status]}</div>
                        )}
                        <div className="flex items-center gap-2 flex-wrap">
                          {pr.has_receipt && (
                            <button onClick={() => handleViewReceipt(pr.id)} className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1">
                              <Eye className="w-3 h-3" /> הצג אסמכתא
                            </button>
                          )}
                          {!isSA && !pr.has_receipt && (pr.status === 'requested' || pr.status === 'pending_review') && (
                            <>
                              <input
                                type="file"
                                id={`receipt-${pr.id}`}
                                className="hidden"
                                accept=".pdf,.jpg,.jpeg,.png"
                                onChange={(e) => {
                                  const file = e.target.files?.[0];
                                  if (file) handleReceiptUpload(pr.id, file);
                                  e.target.value = '';
                                }}
                              />
                              <button
                                onClick={() => document.getElementById(`receipt-${pr.id}`)?.click()}
                                disabled={receiptUploading}
                                className="text-xs text-slate-600 hover:text-slate-800 flex items-center gap-1"
                              >
                                <Upload className="w-3 h-3" /> העלה אסמכתא
                              </button>
                            </>
                          )}
                          {isSA && (pr.status === 'requested' || pr.status === 'pending_review') && (
                            <>
                              <button
                                onClick={() => handleAdminApprove(pr)}
                                disabled={adminApproveLoading === pr.id}
                                className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1 rounded-full flex items-center gap-1 disabled:opacity-50"
                              >
                                {adminApproveLoading === pr.id ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                                אשר תשלום
                              </button>
                              <button
                                onClick={() => { setRejectModalRequest(pr); setRejectReason(''); }}
                                className="text-xs bg-red-100 hover:bg-red-200 text-red-700 px-3 py-1 rounded-full"
                              >
                                דחה בקשה
                              </button>
                            </>
                          )}
                          {canManageBilling && !isSA && (pr.status === 'requested' || pr.status === 'sent') && (
                            <button
                              onClick={async () => {
                                try {
                                  await billingService.cancelPaymentRequest(orgId, pr.id);
                                  toast.success('הבקשה בוטלה');
                                  loadPaymentRequests(paymentRequestsFilter);
                                } catch (err) {
                                  toast.error(err.response?.data?.detail || 'שגיאה בביטול הבקשה');
                                }
                              }}
                              className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1 rounded-full"
                            >
                              בטל בקשה
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {(isSA || isPM || isOwner || canManageBilling) && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <button
            onClick={() => setPaymentConfigExpanded(!paymentConfigExpanded)}
            className="flex items-center justify-between w-full"
          >
            <h2 className="text-lg font-semibold text-slate-800">פרטי תשלום (BrikOps)</h2>
            {paymentConfigExpanded ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
          </button>
          {paymentConfigExpanded && isSA && (
            <div className="space-y-3">
              <p className="text-xs text-slate-500">
                הגדר פרטי חשבון בנק ו/או Bit. לאחר ההגדרה, הודעת התשלום המפורטת (תבנית B) תהיה זמינה להעתקה.
              </p>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700">פרטי חשבון בנק</label>
                <textarea
                  value={paymentConfigBank}
                  onChange={(e) => setPaymentConfigBank(e.target.value)}
                  placeholder="שם בנק, סניף, מספר חשבון..."
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm text-right resize-none"
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700">מספר Bit</label>
                <input
                  type="text"
                  value={paymentConfigBit}
                  onChange={(e) => setPaymentConfigBit(e.target.value)}
                  placeholder="050-1234567"
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm text-right"
                />
              </div>
              <button
                onClick={handleSavePaymentConfig}
                disabled={paymentConfigSaving}
                className="bg-amber-500 hover:bg-amber-600 text-white font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {paymentConfigSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                שמור
              </button>
            </div>
          )}
          {paymentConfigExpanded && !isSA && (
            <div className="space-y-3">
              <p className="text-xs text-slate-500">
                פרטי חשבון לביצוע העברה/תשלום:
              </p>
              {data?.payment_config?.bank_details ? (
                <div className="space-y-1">
                  <label className="block text-sm font-medium text-slate-700">פרטי חשבון בנק</label>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm text-slate-800 whitespace-pre-wrap">{data.payment_config.bank_details}</div>
                </div>
              ) : null}
              {data?.payment_config?.bit_phone ? (
                <div className="space-y-1">
                  <label className="block text-sm font-medium text-slate-700">מספר Bit</label>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm text-slate-800">{data.payment_config.bit_phone}</div>
                </div>
              ) : null}
              {!data?.payment_config?.bank_details && !data?.payment_config?.bit_phone && (
                <p className="text-sm text-slate-400">לא הוגדרו פרטי תשלום עדיין.</p>
              )}
            </div>
          )}
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800">
          <span className="font-medium">איך מחושב החיוב בארגון:</span>{' '}
          סה״כ החיוב הארגוני מחושב כסכום החיוב החודשי של כל הפרויקטים הפעילים בארגון.
        </div>

        <h2 ref={projectsSectionRef} className="text-lg font-semibold text-slate-800">פרויקטים ({data.projects?.length || 0})</h2>
        {data.projects?.length > 0 ? (
          <div className="space-y-3">
            {data.projects.map(pb => {
              const badge = getPlanBadge(pb.plan_id);
              return (
                <div key={pb.project_id} data-project-id={pb.project_id} className={`bg-slate-50 rounded-lg p-4 space-y-2 transition-all ${highlightedProjectId === pb.project_id ? 'billing-highlight-flash' : ''}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-slate-700">{pb.project_name || pb.project_id}</span>
                      {pb.setup_state && (
                        <span className={`text-xs px-2 py-0.5 rounded-full ${getSetupStateColor(pb.setup_state)}`}>
                          {getSetupStateLabel(pb.setup_state)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {(canManageBilling || isSA || isOwner) && (
                        <button
                          onClick={() => setEditingProjectBilling(pb)}
                          className="flex items-center gap-1 text-xs text-amber-700 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 px-2 py-1 rounded transition-colors"
                        >
                          <Pencil className="w-3 h-3" />
                          ערוך
                        </button>
                      )}
                      <span className="text-sm font-bold text-slate-900 flex-shrink-0">{formatCurrency(pb.monthly_total)}/חודש</span>
                    </div>
                  </div>
                  {pb.plan_id && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">חבילה:</span>
                      <span className="text-xs font-medium text-slate-700">{getPlanLabel(pb.plan_id)}</span>
                      {badge && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-slate-200 text-slate-600">
                          {badge}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
                    <div>יחידות: <span className="font-medium text-slate-700">{pb.contracted_units}</span></div>
                    <div>₪/יחידה: <span className="font-medium text-slate-700">{formatCurrency(pb.price_per_unit ?? 20)}</span></div>
                  </div>
                  {pb.cycle_peak_units > pb.contracted_units && (
                    <div className="flex items-center gap-1 text-xs text-amber-700 bg-amber-50 rounded px-2 py-1" title="החיוב נקבע לפי השיא החודשי כדי למנוע שינויים תכופים">
                      <Info className="w-3 h-3" />
                      <span>שיא במחזור: {pb.cycle_peak_units} יחידות</span>
                    </div>
                  )}
                  {pb.pending_contracted_units != null && (
                    <div className="flex items-center gap-1 text-xs text-blue-700 bg-blue-50 rounded px-2 py-1">
                      <Clock className="w-3 h-3" />
                      <span>ירד ל-{pb.pending_contracted_units} יחידות החל מ-{pb.pending_effective_from ? new Date(pb.pending_effective_from).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit' }) : '—'}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-sm text-slate-400">אין פרויקטים עם חיוב</div>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-amber-500" />
          <h2 className="text-lg font-semibold text-slate-800">חשבוניות</h2>
        </div>

        {previewLoading ? (
          <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-amber-500" /></div>
        ) : preview && (
          <div className="bg-amber-50 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-amber-800">תקופה נוכחית: {formatPeriod(preview.period_ym)}</span>
              <span className="text-lg font-bold text-amber-900">{formatCurrency(preview.total_amount)}</span>
            </div>
            <div className="text-xs text-amber-700">
              תאריך יעד לתשלום: {sub?.paid_until ? new Date(sub.paid_until).toLocaleDateString('he-IL') : '—'}
            </div>
            <div className="text-xs text-amber-700">
              {preview.line_items?.length || 0} פרויקטים פעילים
            </div>
            {canMutateInvoices && !invoices.find(inv => inv.period_ym === currentPeriod) && (isSA || paymentRequests.some(pr => pr.status === 'paid')) && (
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                הפקת חשבונית לתקופה {formatPeriod(currentPeriod)}
              </button>
            )}
          </div>
        )}

        {invoicesLoading ? (
          <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-amber-500" /></div>
        ) : invoices.length > 0 ? (
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-slate-600">היסטוריית חשבוניות</h3>
            {invoices.map(inv => (
              <div key={inv.id} className="border border-slate-200 rounded-lg overflow-hidden">
                <button
                  onClick={() => loadInvoiceDetail(inv.id)}
                  className="w-full bg-slate-50 hover:bg-slate-100 p-3 flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-slate-700">{formatPeriod(inv.period_ym)}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${getInvoiceStatusColor(inv.status)}`}>
                      {getInvoiceStatusLabel(inv.status)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-slate-800">{formatCurrency(inv.total_amount)}</span>
                    {expandedInvoice === inv.id ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </div>
                </button>
                {expandedInvoice === inv.id && (
                  <div className="border-t border-slate-200 p-3 space-y-3">
                    {expandedDetail?.line_items?.length > 0 ? (
                      <div className="space-y-2">
                        {expandedDetail.line_items.map((li, idx) => (
                          <div key={idx} className="bg-white rounded p-2 text-xs border border-slate-100 space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-slate-700">{li.project_name_snapshot || '—'}</span>
                              <span className="font-bold text-slate-800">{formatCurrency(li.monthly_total_snapshot)}</span>
                            </div>
                            <div className="flex items-center gap-3 text-slate-500">
                              <span>חבילה: {getPlanLabel(li.plan_id_snapshot)}</span>
                              <span>יחידות: {li.contracted_units_snapshot}</span>
                            </div>
                            <div className="flex items-center gap-3 text-slate-400">
                              <span>רישיון: {formatCurrency(li.license_fee_snapshot ?? li.project_fee_snapshot)}</span>
                              <span>עלות יחידות: {formatCurrency(li.units_fee_snapshot ?? li.tier_fee_snapshot)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-slate-400 text-center py-2">
                        {expandedDetail ? 'אין פריטים' : <Loader2 className="w-4 h-4 animate-spin mx-auto text-amber-500" />}
                      </div>
                    )}
                    <div className="text-xs text-slate-500 space-y-1">
                      {inv.period_ym && <div>תקופה: {inv.period_ym}</div>}
                      {inv.issued_at && <div>הונפק: {new Date(inv.issued_at).toLocaleDateString('he-IL')}</div>}
                      {inv.paid_at && <div>שולם: {new Date(inv.paid_at).toLocaleDateString('he-IL')}</div>}
                      {!inv.paid_at && inv.status !== 'paid' && inv.status !== 'issued' && inv.due_at && (
                        <div>תאריך יעד: {new Date(inv.due_at).toLocaleDateString('he-IL')}</div>
                      )}
                    </div>
                    {inv.gi_download_url && (
                      <a
                        href={inv.gi_download_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium rounded-lg text-xs transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        צפה בחשבונית
                      </a>
                    )}
                    {canMutateInvoices && (inv.status === 'issued' || inv.status === 'past_due') && (
                      <button
                        onClick={() => setInvoiceConfirm(inv.id)}
                        disabled={markingPaid === inv.id}
                        className="w-full border-2 border-dashed border-amber-300 hover:border-amber-400 bg-amber-50 hover:bg-amber-100 disabled:opacity-50 text-amber-800 font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2"
                      >
                        {markingPaid === inv.id ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                        סימון כשולם (סימולציה)
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-slate-400 text-center py-2">אין חשבוניות עדיין</div>
        )}
      </div>

      <div id="responsibility" ref={responsibilityRef} className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-amber-500" />
          <h2 className="text-lg font-semibold text-slate-800">אחריות חיוב בארגון</h2>
        </div>

        <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800 space-y-1">
          <p className="font-medium">מי יכול לנהל חיוב?</p>
          <p>בעלים וגם בעלי תפקיד <strong>אחראי חיוב</strong> או <strong>מנהל ארגון</strong> יכולים לערוך הגדרות חיוב בפרויקטים.</p>
          {canEditRoles && (
            <p className="text-blue-600">ניתן לשנות תפקידים ישירות מהרשימה למטה.</p>
          )}
        </div>

        {membersLoading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
          </div>
        ) : membersError ? (
          <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm flex items-center justify-between">
            <span>{membersError}</span>
            <button onClick={loadMembers} className="text-red-600 hover:text-red-800 font-medium text-sm">נסה שוב</button>
          </div>
        ) : membersDenied ? (
          <div className="text-sm text-slate-400 py-4 text-center">
            רשימת חברי הארגון זמינה לבעלים ולמנהלי הארגון בלבד.
          </div>
        ) : members.length === 0 ? (
          <div className="text-sm text-slate-400 py-4 text-center">אין חברים בארגון</div>
        ) : (
          <div className="space-y-2">
            {members.map(m => (
              <div key={m.user_id} className="bg-slate-50 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-slate-700 text-sm truncate">{m.name || '—'}</div>
                    {m.phone && (
                      <div className="text-xs text-slate-400" dir="ltr">{m.phone}</div>
                    )}
                  </div>
                  <div className="flex-shrink-0">
                    {m.is_owner ? (
                      <div className="flex items-center gap-1 text-sm text-amber-700 bg-amber-50 px-3 py-1.5 rounded-lg">
                        <Lock className="w-3.5 h-3.5" />
                        <span className="font-medium">בעלים</span>
                      </div>
                    ) : canEditRoles ? (
                      changingRole === m.user_id ? (
                        <Loader2 className="w-5 h-5 animate-spin text-amber-500" />
                      ) : (
                        <Select
                          value={m.role}
                          onValueChange={(val) => handleRoleChange(m, val)}
                        >
                          <SelectTrigger className="w-[140px] text-xs h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent position="popper" className="z-[9999]">
                            {ASSIGNABLE_ROLES.map(r => (
                              <SelectItem key={r.value} value={r.value}>
                                {r.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )
                    ) : (
                      <span className="text-sm text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg">
                        {getRoleLabel(m.role)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-slate-400">
                  {ROLE_DESCRIPTIONS[m.is_owner ? 'owner' : m.role] || ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {invoiceConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4" dir="rtl">
            <h3 className="text-lg font-bold text-slate-800">סימון חשבונית כשולם</h3>
            <div className="bg-amber-50 text-amber-800 text-sm rounded-lg p-3 space-y-1">
              <p className="font-medium">סימולציה בלבד — ללא תשלום בפועל</p>
              <p className="text-xs">פעולה זו מסמנת את החשבונית כשולם למטרות בדיקה. לא מתבצע חיוב אמיתי.</p>
            </div>
            <p className="text-sm text-slate-600">לאשר סימון החשבונית כשולם?</p>
            <div className="flex gap-2">
              <button
                onClick={() => handleMarkPaid(invoiceConfirm)}
                className="flex-1 bg-amber-500 hover:bg-amber-600 text-white font-medium py-2 px-4 rounded-lg text-sm"
              >
                אישור
              </button>
              <button
                onClick={() => setInvoiceConfirm(null)}
                className="flex-1 border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium py-2 px-4 rounded-lg text-sm"
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDialog && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4" dir="rtl">
            <h3 className="text-lg font-bold text-slate-800">שינוי תפקיד בארגון</h3>
            <p className="text-sm text-slate-600">
              לשנות את התפקיד של <strong>{confirmDialog.member.name || 'המשתמש'}</strong> מ<strong>{getRoleLabel(confirmDialog.member.role)}</strong> ל<strong>{getRoleLabel(confirmDialog.newRole)}</strong>?
            </p>
            {(confirmDialog.newRole === 'billing_admin' || confirmDialog.newRole === 'org_admin') && (
              <div className="bg-amber-50 text-amber-800 text-xs rounded-lg p-3">
                <strong>שימו לב:</strong> הרשאה זו מאפשרת {confirmDialog.newRole === 'billing_admin' ? 'ניהול הגדרות חיוב בפרויקטים' : 'ניהול חברי ארגון וצפייה בנתוני חיוב'}.
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={confirmRoleChange}
                className="flex-1 bg-amber-500 hover:bg-amber-600 text-white font-medium py-2 px-4 rounded-lg text-sm"
              >
                אישור
              </button>
              <button
                onClick={() => setConfirmDialog(null)}
                className="flex-1 border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium py-2 px-4 rounded-lg text-sm"
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}
      {rejectModalRequest && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4" dir="rtl">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-800">דחיית בקשת תשלום</h3>
              <button onClick={() => setRejectModalRequest(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="text-sm text-slate-600">
              מזהה: <span className="font-mono">{rejectModalRequest.id?.slice(0, 8)}...</span>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">סיבת דחייה</label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="לדוגמה: לא התקבלה אסמכתא / לא נמצא תשלום / סכום שגוי"
                className="w-full border border-slate-300 rounded-lg p-2 text-sm text-right resize-none"
                rows={3}
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAdminReject}
                disabled={rejectLoading}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {rejectLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                דחה
              </button>
              <button
                onClick={() => setRejectModalRequest(null)}
                className="flex-1 border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium py-2 px-4 rounded-lg text-sm"
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}
      <ProjectBillingEditModal
        open={!!editingProjectBilling}
        onClose={() => setEditingProjectBilling(null)}
        projectBilling={editingProjectBilling}
        onSaved={async (response) => {
          try {
            const updated = await billingService.orgBilling(orgId);
            setData(updated);
            const savedId = editingProjectBilling?.project_id;
            if (savedId) {
              setHighlightedProjectId(savedId);
              setTimeout(() => {
                const el = document.querySelector(`[data-project-id="${savedId}"]`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }, 100);
              setTimeout(() => setHighlightedProjectId(null), 2500);
            }
          } catch (e) {}
        }}
      />
      <div className="text-center text-xs text-slate-300 mt-6">build 2026-03-04-v1</div>
    </div>
  );
}
