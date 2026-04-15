import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { billingService, stepupService, isStepupError } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Building2, Clock, ShieldCheck, ShieldOff,
  CalendarPlus, Gift, Ban, Unlock, RefreshCw, Loader2,
  FileText, User, KeyRound, X, Package, Database, Play,
  CheckCircle2, AlertTriangle, ChevronDown, ChevronUp, Users
} from 'lucide-react';
import { Button } from '../components/ui/button';

import {
  getBillingStatusLabel, getBillingStatusColor,
  getAccessLabel, getPlanLabel, formatCurrency,
  getInvoiceStatusLabel, getInvoiceStatusColor,
} from '../utils/billingLabels';
import { getPlanCatalog, getPlanBadge } from '../utils/billingPlanCatalog';

const ACCESS_LABELS = {
  full_access: { label: 'גישה מלאה', color: 'bg-green-100 text-green-700', icon: ShieldCheck },
  read_only: { label: 'צפייה בלבד', color: 'bg-red-100 text-red-700', icon: ShieldOff },
};

import { getActionLabel } from '../utils/actionLabels';

const getAuditDescription = (ev) => {
  if (ev.payload?.note) return ev.payload.note;
  const action = getActionLabel(ev.action);
  const actor = ev.actor_name || 'מערכת';
  const orgName = ev.payload?.org_name || ev.payload?.organization_name || '';
  if (action !== '—' && orgName) return `${actor} — ${action} (${orgName})`;
  if (action !== '—') return `${actor} — ${action}`;
  return `${actor} — ${ev.action || 'פעולה'}`;
};

const getActionDotColor = (action) => {
  if (['extend_trial', 'billing_extend_trial', 'comp', 'billing_comp', 'activate'].includes(action)) return 'bg-green-400';
  if (['suspend', 'billing_suspend', 'billing_override'].includes(action)) return 'bg-red-400';
  if (['unsuspend', 'billing_unsuspend'].includes(action)) return 'bg-blue-400';
  if (['invoice_generated', 'invoice_marked_paid'].includes(action)) return 'bg-amber-400';
  return 'bg-slate-400';
};

const getOrgBorderColor = (org) => {
  if (org.subscription?.manual_override?.is_suspended) return 'border-r-red-400';
  if (org.effective_access === 'full_access') return 'border-r-green-400';
  return 'border-r-amber-400';
};

const getInitials = (name) => {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return parts[0][0] + parts[1][0];
  return parts[0][0];
};

const QuotaRequestCard = ({ request, onAction }) => {
  const [processing, setProcessing] = useState(false);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const handleApprove = async () => {
    const confirmMsg = `לאשר הגדלה מ-${request.current_total_units} ל-${request.requested_total_units} יחידות?`;
    if (!window.confirm(confirmMsg)) return;
    setProcessing(true);
    try {
      await billingService.approveQuotaRequest(request.id, {});
      toast.success('הבקשה אושרה');
      onAction();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה באישור');
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    setProcessing(true);
    try {
      await billingService.rejectQuotaRequest(request.id, {
        rejection_reason: rejectReason.trim(),
      });
      toast.success('הבקשה נדחתה');
      onAction();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בדחייה');
    } finally {
      setProcessing(false);
    }
  };

  const dateStr = request.created_at
    ? new Date(request.created_at).toLocaleDateString('he-IL', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : '—';

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-1">
          <div className="font-semibold text-slate-800">
            {request.project_name_snapshot || request.project_id}
          </div>
          <div className="text-xs text-slate-500">
            מבקש: <span className="font-medium text-slate-700">{request.requester_user_name || '—'}</span>
          </div>
          <div className="text-sm">
            <span className="text-slate-500">כמות:</span>{' '}
            <span className="font-medium">{request.current_total_units}</span>
            <span className="text-slate-400 mx-2">→</span>
            <span className="font-bold text-blue-700">{request.requested_total_units}</span>
            <span className="text-slate-500 mr-1">יחידות</span>
          </div>
          {request.reason && (
            <div className="text-xs text-slate-600 italic bg-slate-50 rounded px-2 py-1 mt-1">
              סיבה: {request.reason}
            </div>
          )}
          <div className="text-xs text-slate-400">
            נוצרה: {dateStr}
          </div>
        </div>
        <div className="flex flex-col gap-2 flex-shrink-0">
          <Button
            onClick={handleApprove}
            disabled={processing}
            className="bg-green-500 hover:bg-green-600 text-white text-xs px-4 py-1.5"
          >
            אשר
          </Button>
          <Button
            onClick={() => setShowRejectForm(!showRejectForm)}
            variant="outline"
            disabled={processing}
            className="text-red-600 border-red-300 text-xs px-4 py-1.5"
          >
            דחה
          </Button>
        </div>
      </div>

      {showRejectForm && (
        <div className="border-t border-slate-200 mt-3 pt-3 space-y-2">
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="סיבת דחייה (אופציונלי, יוצג למבקש)"
            rows={2}
            className="w-full border border-slate-300 rounded p-2 text-sm"
          />
          <div className="flex gap-2">
            <Button
              onClick={handleReject}
              disabled={processing}
              className="bg-red-500 hover:bg-red-600 text-white text-xs"
            >
              אשר דחייה
            </Button>
            <Button
              onClick={() => { setShowRejectForm(false); setRejectReason(''); }}
              variant="outline"
              className="text-xs"
            >
              ביטול
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

const AdminBillingPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const goBack = () => {
    if (location.state?.from) navigate(location.state.from);
    else navigate('/admin');
  };
  const [orgs, setOrgs] = useState([]);
  const [audit, setAudit] = useState([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const loadGenRef = useRef(0);
  const hasDataRef = useRef(false);
  const [actionModal, setActionModal] = useState(null);
  const [actionDate, setActionDate] = useState('');
  const [actionNote, setActionNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [stepup, setStepup] = useState(null);
  const [stepupCode, setStepupCode] = useState('');
  const [stepupLoading, setStepupLoading] = useState(false);
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(false);
  const [showPlans, setShowPlans] = useState(false);
  const [migrationResult, setMigrationResult] = useState(null);
  const [migrationLoading, setMigrationLoading] = useState(false);
  const [showMigration, setShowMigration] = useState(false);
  const [showOrgs, setShowOrgs] = useState(false);
  const [applyingMigration, setApplyingMigration] = useState(false);
  const [orgInvoices, setOrgInvoices] = useState({});
  const [paidThisMonth, setPaidThisMonth] = useState(0);
  const [openRequests, setOpenRequests] = useState({ open_count: 0, requests: [] });
  const [openRequestsExpanded, setOpenRequestsExpanded] = useState(false);
  const [showAudit, setShowAudit] = useState(true);
  const [failedRenewals, setFailedRenewals] = useState({ items: [], unresolved_count: 0 });
  const [resolvingId, setResolvingId] = useState(null);
  const [pricingModal, setPricingModal] = useState(null);
  const [pricingMode, setPricingMode] = useState('standard');
  const [pricingCustomAmount, setPricingCustomAmount] = useState('');
  const [pricingSaving, setPricingSaving] = useState(false);
  const [founderEnabled, setFounderEnabled] = useState(null);
  const [founderCount, setFounderCount] = useState(0);
  const [founderMaxSlots, setFounderMaxSlots] = useState(30);
  const [founderToggling, setFounderToggling] = useState(false);
  const [pendingQuotaRequests, setPendingQuotaRequests] = useState([]);
  const [loadingQuotaRequests, setLoadingQuotaRequests] = useState(false);

  const loadQuotaRequests = useCallback(async () => {
    setLoadingQuotaRequests(true);
    try {
      const res = await billingService.listQuotaRequests('pending');
      setPendingQuotaRequests(res.requests || []);
    } catch (err) {
      toast.error('שגיאה בטעינת בקשות quota');
      setPendingQuotaRequests([]);
    } finally {
      setLoadingQuotaRequests(false);
    }
  }, []);

  useEffect(() => { loadQuotaRequests(); }, [loadQuotaRequests]);

  const loadOrgInvoices = useCallback(async (gen) => {
    try {
      const data = await billingService.invoicesSummary();
      if (gen === loadGenRef.current) {
        setOrgInvoices(data?.by_org || {});
        setPaidThisMonth(data?.paid_this_month || 0);
      }
    } catch {}
  }, []);

  const formatLoadError = (err) => {
    const status = err.response?.status;
    let detail = err.response?.data?.detail;
    if (detail && typeof detail === 'object') {
      detail = detail.message || JSON.stringify(detail).slice(0, 80);
    }
    if (status && detail) return `שגיאה ברענון (HTTP ${status}): ${detail}`;
    if (status) return `שגיאה ברענון (HTTP ${status})`;
    if (err.message) return `שגיאה ברענון: ${err.message}`;
    return 'שגיאה ברענון נתוני חיוב';
  };

  const loadingRef = useRef(false);
  const loadData = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    const gen = ++loadGenRef.current;
    const isFirstLoad = !hasDataRef.current;
    if (isFirstLoad) {
      setInitialLoading(true);
    } else {
      setRefreshing(true);
    }
    setLoadError(null);
    try {
      const [orgsData, auditData, openReqs, failedRen] = await Promise.all([
        billingService.listOrgs(),
        billingService.auditLog(),
        billingService.openPaymentRequestsSummary().catch(() => ({ open_count: 0, requests: [] })),
        billingService.failedRenewals().catch(() => ({ items: [], unresolved_count: 0 })),
      ]);
      if (gen !== loadGenRef.current) return;
      hasDataRef.current = true;
      setOrgs(orgsData);
      setAudit(auditData);
      setOpenRequests(openReqs);
      setFailedRenewals(failedRen);
      if (openReqs.open_count > 0) setOpenRequestsExpanded(true);
      if (orgsData.length > 0) loadOrgInvoices(gen);
      loadQuotaRequests();
      billingService.getFounderConfig().then(cfg => {
        setFounderEnabled(cfg.enabled);
        setFounderCount(cfg.active_founder_count || 0);
        setFounderMaxSlots(cfg.max_slots || 30);
      }).catch(() => {});
    } catch (err) {
      if (gen !== loadGenRef.current) return;
      if (isStepupError(err)) {
        startStepup(() => loadData());
        return;
      }
      const errMsg = formatLoadError(err);
      if (isFirstLoad) {
        setLoadError(errMsg);
      } else {
        toast.error(errMsg);
      }
    } finally {
      if (gen === loadGenRef.current) {
        setInitialLoading(false);
        setRefreshing(false);
      }
      loadingRef.current = false;
    }
  }, [loadOrgInvoices, loadQuotaRequests]);

  useEffect(() => { loadData(); }, [loadData]);

  const loadPlans = useCallback(async () => {
    setPlansLoading(true);
    try {
      const data = await billingService.plans();
      setPlans(data);
    } catch (err) {
      if (err.response?.status === 404) {
        setPlans([]);
      } else if (isStepupError(err)) {
        startStepup(() => loadPlans());
      } else {
        toast.error('שגיאה בטעינת תוכניות');
      }
    } finally {
      setPlansLoading(false);
    }
  }, []);

  const runDryRun = useCallback(async () => {
    setMigrationLoading(true);
    try {
      const data = await billingService.migrationDryRun();
      setMigrationResult(data);
    } catch (err) {
      if (err.response?.status === 404) {
        setMigrationResult(null);
        toast.info('תכונת חיוב v1 אינה מופעלת');
      } else if (isStepupError(err)) {
        startStepup(() => runDryRun());
      } else {
        toast.error('שגיאה בהרצת סימולציה');
      }
    } finally {
      setMigrationLoading(false);
    }
  }, []);

  const applyMigration = async () => {
    setApplyingMigration(true);
    try {
      const data = await billingService.migrationApply();
      setMigrationResult(prev => ({ ...prev, ...data, applied: true }));
      toast.success(`הועברו ${data.applied_count} פרויקטים`);
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => applyMigration());
      } else {
        toast.error(err.response?.data?.detail || 'שגיאה בהפעלת מיגרציה');
      }
    } finally {
      setApplyingMigration(false);
    }
  };


  const handleAction = async () => {
    if (!actionNote.trim()) {
      toast.error('חובה לציין הערה');
      return;
    }
    if ((actionModal.action === 'extend_trial' || actionModal.action === 'activate' || actionModal.action === 'comp') && !actionDate) {
      toast.error('חובה לבחור תאריך');
      return;
    }
    setSubmitting(true);
    try {
      const until = actionDate ? new Date(actionDate).toISOString() : undefined;
      await billingService.override({
        org_id: actionModal.orgId,
        action: actionModal.action,
        until,
        note: actionNote,
      });
      toast.success('הפעולה בוצעה בהצלחה');
      setActionModal(null);
      setActionDate('');
      setActionNote('');
      loadData();
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => handleAction());
      } else {
        const detail = err.response?.data?.detail;
        toast.error(typeof detail === 'object' ? detail.message : (detail || 'שגיאה'));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const startStepup = async (retryAction) => {
    setStepupLoading(true);
    try {
      const result = await stepupService.requestChallenge();
      setStepup({ challengeId: result.challenge_id, maskedEmail: result.masked_email, retryAction });
      setStepupCode('');
      toast.success(`קוד אימות נשלח ל-${result.masked_email}`);
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בשליחת קוד אימות';
      toast.error(typeof detail === 'object' ? detail.message : detail);
    } finally {
      setStepupLoading(false);
    }
  };

  const handleStepupVerify = async () => {
    if (!stepup || !stepupCode.trim()) return;
    setStepupLoading(true);
    try {
      await stepupService.verifyChallenge(stepup.challengeId, stepupCode);
      toast.success('אימות הצליח');
      const retry = stepup.retryAction;
      setStepup(null);
      setStepupCode('');
      if (retry) retry();
    } catch (err) {
      const detail = err.response?.data?.detail || 'קוד לא תקין';
      toast.error(typeof detail === 'object' ? detail.message : detail);
    } finally {
      setStepupLoading(false);
    }
  };

  const handleResolveRenewal = async (attemptId) => {
    setResolvingId(attemptId);
    try {
      await billingService.resolveFailedRenewal(attemptId);
      toast.success('החידוש תוקן בהצלחה');
      loadData();
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => handleResolveRenewal(attemptId));
      } else {
        const detail = err.response?.data?.detail;
        toast.error(typeof detail === 'object' ? detail.message : (detail || 'שגיאה בתיקון'));
      }
    } finally {
      setResolvingId(null);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch { return iso; }
  };

  const formatDateTime = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  if (initialLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (loadError && !hasDataRef.current) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 gap-4" dir="rtl">
        <AlertTriangle className="w-10 h-10 text-amber-500" />
        <p className="text-slate-700 text-sm">{loadError}</p>
        <Button variant="outline" size="sm" onClick={loadData}>
          <RefreshCw className="w-4 h-4 ml-1" />
          נסה שוב
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <header className="bg-gradient-to-l from-slate-900 to-slate-800 text-white">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={goBack} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="חזרה לאדמין">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="w-9 h-9 bg-amber-500 rounded-lg flex items-center justify-center">
            <Building2 className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold leading-tight">ניהול חיוב ומנויים</h1>
            <p className="text-xs text-slate-400">{orgs.length} ארגונים</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate('/admin/users', { state: { from: '/admin/billing' } })}
              className="px-3 py-1.5 text-xs bg-white/[0.07] border border-white/10 rounded-lg hover:bg-white/[0.14] transition-colors flex items-center gap-1"
            >
              <Users className="w-3.5 h-3.5" />
              משתמשים
            </button>
            <button
              onClick={loadData}
              disabled={refreshing}
              className="px-3 py-1.5 text-xs bg-white/[0.07] border border-white/10 rounded-lg hover:bg-white/[0.14] transition-colors flex items-center gap-1"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              רענון
            </button>
          </div>
        </div>
      </header>

      <section className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {(() => {
          const activeOrgs = orgs.filter(o => o.effective_access === 'full_access').length;
          const totalMonthly = orgs
            .filter(o => o.effective_access === 'full_access' && o.subscription?.status === 'active')
            .reduce((sum, o) => sum + (o.subscription?.billable_amount ?? o.subscription?.total_monthly ?? 0), 0);
          return (
            <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-blue-50 rounded-xl border border-blue-100 border-r-[3px] border-r-blue-400 p-3">
                <div className="text-xs text-blue-600 font-medium mb-1">סה״כ ארגונים</div>
                <div className="text-2xl font-bold text-slate-800">{orgs.length}</div>
              </div>
              <div className="bg-green-50 rounded-xl border border-green-100 border-r-[3px] border-r-green-400 p-3">
                <div className="text-xs text-green-600 font-medium mb-1">ארגונים פעילים</div>
                <div className="text-2xl font-bold text-green-700">{activeOrgs}</div>
              </div>
              <div className="bg-amber-50 rounded-xl border border-amber-100 border-r-[3px] border-r-amber-400 p-3">
                <div className="text-xs text-amber-600 font-medium mb-1">צפי MRR</div>
                <div className="text-2xl font-bold text-slate-800">{formatCurrency(totalMonthly)}</div>
              </div>
              <div className="bg-emerald-50 rounded-xl border border-emerald-100 border-r-[3px] border-r-emerald-400 p-3">
                <div className="text-xs text-emerald-600 font-medium mb-1">שולם החודש</div>
                <div className={`text-2xl font-bold ${paidThisMonth > 0 ? 'text-emerald-700' : 'text-red-500'}`}>{formatCurrency(paidThisMonth)}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">(כל התשלומים החודש)</div>
              </div>
            </section>
          );
        })()}

        {founderEnabled != null && (
          <section className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-slate-700">תוכנית מייסדים</span>
                <span className="text-xs text-slate-500">{founderCount}/{founderMaxSlots} לקוחות פעילים</span>
              </div>
              <button
                onClick={async () => {
                  setFounderToggling(true);
                  try {
                    const res = await billingService.toggleFounderPlan(!founderEnabled);
                    setFounderEnabled(res.enabled);
                    setFounderCount(res.active_founder_count || 0);
                    toast.success(res.enabled ? 'תוכנית מייסדים פעילה' : 'תוכנית מייסדים כבויה');
                  } catch (err) {
                    toast.error(err.response?.data?.detail || 'שגיאה');
                  } finally {
                    setFounderToggling(false);
                  }
                }}
                disabled={founderToggling}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  founderEnabled
                    ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                {founderToggling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : founderEnabled ? 'פעיל' : 'כבוי'}
              </button>
            </div>
          </section>
        )}

        {failedRenewals.unresolved_count > 0 && (
          <section className="bg-red-50 rounded-xl border-2 border-red-300 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              <span className="text-sm font-bold text-red-700">
                ⚠️ חיובים שהצליחו אבל עדכון המנוי נכשל ({failedRenewals.unresolved_count})
              </span>
            </div>
            <p className="text-xs text-red-600">הלקוחות חויבו בהצלחה אך המנוי לא עודכן. יש ללחוץ "תקן" כדי לעדכן את המנוי.</p>
            {failedRenewals.items.map(item => (
              <div key={item.id} className="bg-white rounded-lg border border-red-200 p-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-slate-800 text-sm">{item.org_name || item.org_id}</span>
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">נכשל</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500">
                    <span>סכום: <bdi dir="ltr">₪{(item.amount || 0).toLocaleString('he-IL')}</bdi></span>
                    <span>מסמך: <span className="font-mono">{item.gi_document_id?.slice(0, 8)}...</span></span>
                    <span>{formatDateTime(item.created_at)}</span>
                  </div>
                  {item.error && <div className="text-[10px] text-red-500 mt-1 truncate">{item.error}</div>}
                </div>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={resolvingId === item.id}
                  onClick={() => handleResolveRenewal(item.id)}
                  className="flex-shrink-0"
                >
                  {resolvingId === item.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 ml-1" />}
                  תקן
                </Button>
              </div>
            ))}
          </section>
        )}

        <section className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <button
            onClick={() => setOpenRequestsExpanded(!openRequestsExpanded)}
            className="flex items-center justify-between w-full px-4 py-3 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-500" />
              <span className="text-sm font-bold text-slate-700">בקשות תשלום פתוחות</span>
              {openRequests.open_count > 0 && (
                <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">{openRequests.open_count}</span>
              )}
            </div>
            {openRequestsExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {openRequestsExpanded && (
            <div className="px-4 pb-4 space-y-2">
              {openRequests.requests.length === 0 ? (
                <div className="text-sm text-slate-400 py-2">אין בקשות פתוחות</div>
              ) : (
                openRequests.requests.map(req => {
                  const statusBorderColors = { requested: 'border-r-amber-400', sent: 'border-r-blue-400', pending_review: 'border-r-orange-400' };
                  const statusColors = { requested: 'bg-amber-100 text-amber-700', sent: 'bg-blue-100 text-blue-700', pending_review: 'bg-amber-100 text-amber-800' };
                  const statusLabels = { requested: 'ממתין לתשלום', sent: 'נשלח', pending_review: 'ממתין לאישור' };
                  const cycleLabels = { monthly: 'חודשי', yearly: 'שנתי' };
                  const fmtDate = (dt) => {
                    if (!dt) return '—';
                    const d = new Date(dt);
                    const dd = String(d.getDate()).padStart(2, '0');
                    const mm = String(d.getMonth() + 1).padStart(2, '0');
                    const yyyy = d.getFullYear();
                    return `${dd}/${mm}/${yyyy}`;
                  };
                  return (
                    <div key={req.id} className={`bg-slate-50 rounded-xl border border-slate-200 border-r-[3px] ${statusBorderColors[req.status] || 'border-r-slate-300'} p-3 text-sm`}>
                      <div className="flex items-center gap-3 mb-2">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                          {getInitials(req.org_name)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-800 truncate">{req.org_name}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0 ${statusColors[req.status] || 'bg-slate-100 text-slate-500'}`}>
                              {statusLabels[req.status] || req.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                            {req.amount_ils > 0 && (
                              <span className="font-medium text-slate-700"><bdi dir="ltr">₪{req.amount_ils.toLocaleString('he-IL')}</bdi></span>
                            )}
                            <span>{cycleLabels[req.cycle] || req.cycle}</span>
                            {req.has_receipt && <span className="text-emerald-600">📎</span>}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <div className="flex items-center gap-3">
                          <span className="text-emerald-600 font-medium">להאריך עד: <bdi dir="ltr">{fmtDate(req.requested_paid_until)}</bdi></span>
                          <span className="text-slate-400">נוצר: <bdi dir="ltr">{fmtDate(req.created_at)}</bdi></span>
                        </div>
                        <button
                          onClick={() => navigate(`/billing/org/${req.org_id}?highlight=${req.id}#requests`)}
                          className="text-xs text-amber-600 hover:text-amber-700 font-semibold whitespace-nowrap px-2 py-1 rounded-lg hover:bg-amber-50 transition-colors"
                        >
                          פתח חיוב ארגון ←
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-bold text-slate-800">
              בקשות quota ממתינות ({pendingQuotaRequests.length})
            </h2>
            <button
              onClick={loadQuotaRequests}
              className="text-xs text-slate-500 hover:text-slate-700"
              disabled={loadingQuotaRequests}
            >
              {loadingQuotaRequests ? 'טוען...' : 'רענן'}
            </button>
          </div>

          {loadingQuotaRequests ? (
            <div className="text-sm text-slate-500 py-4 text-center">טוען...</div>
          ) : pendingQuotaRequests.length === 0 ? (
            <div className="text-sm text-slate-500 bg-slate-50 rounded-lg p-4 text-center">
              אין בקשות ממתינות
            </div>
          ) : (
            <div className="space-y-2">
              {pendingQuotaRequests.map(req => (
                <QuotaRequestCard
                  key={req.id}
                  request={req}
                  onAction={loadQuotaRequests}
                />
              ))}
            </div>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <button
            onClick={() => { const next = !showOrgs; setShowOrgs(next); if (next && orgs.length > 0) loadOrgInvoices(loadGenRef.current); }}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-bold text-slate-700">ארגונים</span>
              <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">{orgs.length}</span>
            </div>
            {showOrgs ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {showOrgs && (
            <div className="px-4 pb-4 space-y-3">
              {orgs.map(org => {
                const accessInfo = ACCESS_LABELS[org.effective_access] || ACCESS_LABELS.read_only;
                const AccessIcon = accessInfo.icon;
                const sub = org.subscription || {};
                const borderColor = getOrgBorderColor(org);
                return (
                  <div key={org.id} className={`bg-white rounded-xl border border-slate-200 border-r-[3px] ${borderColor} p-4 hover:shadow-sm transition-shadow`}>
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                          {getInitials(org.name)}
                        </div>
                        <div>
                          <h3 className="text-base font-bold text-slate-800">{org.name}</h3>
                          <p className="text-xs text-slate-500">
                            {org.owner?.name || '—'} | {org.owner?.email || (org.owner?.phone_e164 ? <bdi className="font-mono" dir="ltr">{org.owner.phone_e164}</bdi> : '—')}
                          </p>
                        </div>
                      </div>
                      <div className={`px-2.5 py-1 rounded-full text-xs font-semibold flex items-center gap-1 ${accessInfo.color}`}>
                        <AccessIcon className="w-3 h-3" />
                        {accessInfo.label}
                      </div>
                    </div>

                    {org.read_only_reason && (
                      <div className={`mb-3 px-2.5 py-1.5 rounded-lg border text-xs flex items-center gap-1.5 ${
                        org.read_only_reason === 'suspended'
                          ? 'bg-red-50 border-red-200 text-red-800'
                          : 'bg-amber-50 border-amber-200 text-amber-800'
                      }`}>
                        <AlertTriangle className={`w-3.5 h-3.5 shrink-0 ${
                          org.read_only_reason === 'suspended' ? 'text-red-500' : 'text-amber-500'
                        }`} />
                        <span>{
                          org.read_only_reason === 'payment_expired' ? 'גישה מוגבלת — התשלום פג תוקף' :
                          org.read_only_reason === 'trial_expired' ? 'גישה מוגבלת — תקופת הניסיון הסתיימה' :
                          org.read_only_reason === 'suspended' ? 'גישה מוגבלת — המנוי הושעה' :
                          'גישה מוגבלת'
                        }</span>
                      </div>
                    )}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-slate-600 mb-3">
                      <div>
                        <span className="text-slate-400">סטטוס מנוי: </span>
                        <span className="font-medium">{getBillingStatusLabel(sub.status)}</span>
                      </div>
                      {sub.status === 'trialing' && (
                        <div>
                          <span className="text-slate-400">סוף ניסיון: </span>
                          <span className="font-medium">{formatDate(sub.trial_end_at)}</span>
                        </div>
                      )}
                      {sub.status === 'active' && (
                        <div>
                          <span className="text-slate-400">שולם עד: </span>
                          <span className={`font-medium ${org.read_only_reason === 'payment_expired' ? 'text-red-600' : ''}`}>
                            {sub.paid_until ? formatDate(sub.paid_until) : '—'}
                          </span>
                        </div>
                      )}
                      <div>
                        <span className="text-slate-400">מחובר עד: </span>
                        <span className="font-medium">{formatDate(sub.manual_override?.comped_until)}</span>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {sub.status === 'active' ? (
                        <Button
                          size="sm" variant="outline"
                          onClick={() => setActionModal({ orgId: org.id, action: 'activate', orgName: org.name })}
                          className="text-xs text-emerald-600 border-emerald-300 hover:bg-emerald-50"
                        >
                          <Play className="w-3 h-3 ml-1" />
                          הפעלת מנוי
                        </Button>
                      ) : (
                        <Button
                          size="sm" variant="outline"
                          onClick={() => setActionModal({ orgId: org.id, action: 'extend_trial', orgName: org.name })}
                          className="text-xs text-emerald-600 border-emerald-300 hover:bg-emerald-50"
                        >
                          <CalendarPlus className="w-3 h-3 ml-1" />
                          הארכת ניסיון
                        </Button>
                      )}
                      <Button
                        size="sm" variant="outline"
                        onClick={() => setActionModal({ orgId: org.id, action: 'comp', orgName: org.name })}
                        className="text-xs text-slate-600 border-slate-300 hover:bg-slate-50"
                      >
                        <Gift className="w-3 h-3 ml-1" />
                        מתנה עד תאריך
                      </Button>
                      {sub.manual_override?.is_suspended ? (
                        <Button
                          size="sm" variant="outline"
                          onClick={() => setActionModal({ orgId: org.id, action: 'unsuspend', orgName: org.name })}
                          className="text-xs text-green-600 border-green-300 hover:bg-green-50"
                        >
                          <Unlock className="w-3 h-3 ml-1" />
                          ביטול חסימה
                        </Button>
                      ) : (
                        <Button
                          size="sm" variant="outline"
                          onClick={() => setActionModal({ orgId: org.id, action: 'suspend', orgName: org.name })}
                          className="text-xs text-red-600 border-red-300 hover:bg-red-50"
                        >
                          <Ban className="w-3 h-3 ml-1" />
                          חסימה
                        </Button>
                      )}
                      <Button
                        size="sm" variant="outline"
                        onClick={() => {
                          const sub = org.subscription || {};
                          const projects = org.projects || [];
                          let mode = 'standard';
                          if (sub.manual_override?.total_monthly) mode = 'custom';
                          else if (projects.some(p => p.plan_id === 'founder_6m')) mode = 'founder';
                          setPricingMode(mode);
                          setPricingCustomAmount(mode === 'custom' ? String(sub.manual_override.total_monthly) : '');
                          setPricingModal({ orgId: org.id, orgName: org.name });
                        }}
                        className="text-xs text-purple-600 border-purple-300 hover:bg-purple-50"
                      >
                        <Package className="w-3 h-3 ml-1" />
                        תמחור
                      </Button>
                    </div>
                    {orgInvoices[org.id] && (() => {
                      const latestInv = orgInvoices[org.id];
                      const period = latestInv.period_ym ? `${latestInv.period_ym.split('-')[1]}/${latestInv.period_ym.split('-')[0]}` : '—';
                      return (
                        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-2 text-xs text-slate-600">
                          <FileText className="w-3.5 h-3.5 text-slate-400" />
                          <span>חשבונית אחרונה: {period}</span>
                          <span className={`px-1.5 py-0.5 rounded-full ${getInvoiceStatusColor(latestInv.status)}`}>
                            {getInvoiceStatusLabel(latestInv.status)}
                          </span>
                          <span className="font-medium">{formatCurrency(latestInv.total_amount)}</span>
                        </div>
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <button
            onClick={() => { setShowPlans(!showPlans); if (!showPlans && plans.length === 0) loadPlans(); }}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-purple-500" />
              <span className="text-sm font-bold text-slate-700">תוכניות תמחור</span>
              {plans.length > 0 && <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">{plans.length}</span>}
            </div>
            {showPlans ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {showPlans && (
            <div className="px-4 pb-4 space-y-3">
              {plansLoading ? (
                <div className="flex justify-center py-4"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
              ) : plans.length === 0 ? (
                <div className="p-4 text-sm text-slate-400">אין תוכניות — תכונת חיוב אינה מופעלת או לא הוגדרו תוכניות</div>
              ) : (
                plans.map(plan => {
                  const cat = getPlanCatalog(plan.id);
                  const badge = getPlanBadge(plan.id);
                  return (
                    <div key={plan.id} className={`rounded-xl border p-4 ${!plan.is_active ? 'opacity-50 border-slate-200' : 'border-slate-200'}`}>
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-lg font-bold text-slate-800">{getPlanLabel(plan.id)}</h3>
                            {badge && (
                              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-200 text-slate-600">
                                {badge}
                              </span>
                            )}
                          </div>
                          {cat && <p className="text-xs text-slate-500 mt-0.5">{cat.shortDescription}</p>}
                          <p className="text-xs text-slate-400 mt-1">מזהה: {plan.id}</p>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {plan.is_active ? (
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">פעיל</span>
                          ) : (
                            <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium">מושבת</span>
                          )}
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs text-slate-600 mb-2">
                        <div>רישיון ראשון: <span className="font-medium">{formatCurrency(plan.license_first ?? plan.project_fee_monthly)}</span></div>
                        <div>רישיון נוסף: <span className="font-medium">{formatCurrency(plan.license_additional)}</span></div>
                        <div>₪/יחידה: <span className="font-medium">{formatCurrency(plan.price_per_unit)}</span></div>
                      </div>
                    </div>
                  );
                })
              )}
              <Button variant="outline" size="sm" onClick={loadPlans} disabled={plansLoading}>
                <RefreshCw className="w-3 h-3 ml-1" />
                רענון תוכניות
              </Button>
            </div>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <button
            onClick={() => { setShowMigration(!showMigration); }}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-bold text-slate-700">מיגרציה</span>
            </div>
            {showMigration ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {showMigration && (
            <div className="px-4 pb-3 space-y-3">
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={runDryRun} disabled={migrationLoading}>
                  {migrationLoading ? <Loader2 className="w-3 h-3 animate-spin ml-1" /> : <Play className="w-3 h-3 ml-1" />}
                  הרצת סימולציה
                </Button>
                {migrationResult && migrationResult.auto_resolvable_count > 0 && !migrationResult.applied && (
                  <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" onClick={applyMigration} disabled={applyingMigration}>
                    {applyingMigration ? <Loader2 className="w-3 h-3 animate-spin ml-1" /> : <CheckCircle2 className="w-3 h-3 ml-1" />}
                    הפעל מיגרציה
                  </Button>
                )}
              </div>
              {migrationResult && (
                <div className="border border-slate-200 rounded-lg p-3 space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
                    <div className="bg-slate-50 rounded p-2">
                      <div className="text-slate-500 text-xs">סה״כ פרויקטים</div>
                      <div className="font-bold text-slate-800">{migrationResult.total_projects}</div>
                    </div>
                    <div className="bg-green-50 rounded p-2">
                      <div className="text-green-600 text-xs">עם org_id</div>
                      <div className="font-bold text-green-700">{migrationResult.projects_with_org_id}</div>
                    </div>
                    <div className="bg-amber-50 rounded p-2">
                      <div className="text-amber-600 text-xs">חסר org_id</div>
                      <div className="font-bold text-amber-700">{migrationResult.projects_missing_org_id}</div>
                    </div>
                    <div className="bg-blue-50 rounded p-2">
                      <div className="text-blue-600 text-xs">אוטומטי</div>
                      <div className="font-bold text-blue-700">{migrationResult.auto_resolvable_count}</div>
                    </div>
                    <div className="bg-red-50 rounded p-2">
                      <div className="text-red-600 text-xs">עמום (דורש ידני)</div>
                      <div className="font-bold text-red-700">{migrationResult.ambiguous_count}</div>
                    </div>
                    {migrationResult.applied_count !== undefined && (
                      <div className="bg-emerald-50 rounded p-2">
                        <div className="text-emerald-600 text-xs">הופעלו</div>
                        <div className="font-bold text-emerald-700">{migrationResult.applied_count}</div>
                      </div>
                    )}
                  </div>
                  {migrationResult.ambiguous?.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-red-600 flex items-center gap-1 mb-1">
                        <AlertTriangle className="w-3 h-3" />
                        פרויקטים עמומים (דורשים הקצאה ידנית)
                      </h4>
                      <div className="text-xs text-slate-600 space-y-1">
                        {migrationResult.ambiguous.map(p => (
                          <div key={p.project_id} className="bg-red-50 rounded px-2 py-1">
                            {p.project_name || p.project_id} — יוצר: {p.created_by?.slice(0, 8)}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <button
            onClick={() => setShowAudit(!showAudit)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-bold text-slate-700">יומן פעולות</span>
              {audit.length > 0 && <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">{Math.min(audit.length, 50)}</span>}
            </div>
            {showAudit ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {showAudit && (
            <div className="px-4 pb-4">
              {audit.length === 0 ? (
                <p className="text-sm text-slate-400">אין אירועים</p>
              ) : (
                <>
                  <div className="hidden sm:block rounded-lg border border-slate-200 overflow-hidden">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50 text-slate-500">
                        <tr>
                          <th className="px-3 py-2 text-right">תאריך</th>
                          <th className="px-3 py-2 text-right">פעולה</th>
                          <th className="px-3 py-2 text-right">משתמש</th>
                          <th className="px-3 py-2 text-right">תיאור</th>
                        </tr>
                      </thead>
                      <tbody>
                        {audit.slice(0, 50).map(ev => (
                          <tr key={ev.id} className="border-t border-slate-100 hover:bg-slate-50/50">
                            <td className="px-3 py-2 text-slate-500">{formatDateTime(ev.created_at)}</td>
                            <td className="px-3 py-2">
                              <span className="flex items-center gap-1.5">
                                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${getActionDotColor(ev.action)}`} />
                                <span className="font-medium text-slate-700">{getActionLabel(ev.action)}</span>
                              </span>
                            </td>
                            <td className="px-3 py-2 text-slate-600">
                              <span className="flex items-center gap-1">
                                <User className="w-3 h-3" />
                                {ev.actor_name || ev.actor_id?.slice(0, 8)}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-slate-500">{getAuditDescription(ev)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="sm:hidden space-y-2">
                    {audit.slice(0, 50).map(ev => (
                      <div key={ev.id} className="bg-slate-50 rounded-xl border border-slate-200 p-3 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-1.5">
                            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${getActionDotColor(ev.action)}`} />
                            <span className="text-xs font-medium text-slate-700">{getActionLabel(ev.action)}</span>
                          </span>
                          <span className="text-[10px] text-slate-400">{formatDateTime(ev.created_at)}</span>
                        </div>
                        <div className="text-xs text-slate-600 flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {ev.actor_name || ev.actor_id?.slice(0, 8)}
                        </div>
                        <div className="text-xs text-slate-500">{getAuditDescription(ev)}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </section>
      </section>

      {actionModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6" dir="rtl">
            <h3 className="text-lg font-bold text-slate-800 mb-1">
              {actionModal.action === 'extend_trial' && 'הארכת ניסיון'}
              {actionModal.action === 'activate' && 'הפעלת מנוי'}
              {actionModal.action === 'comp' && 'מתנה עד תאריך'}
              {actionModal.action === 'suspend' && 'חסימת ארגון'}
              {actionModal.action === 'unsuspend' && 'ביטול חסימה'}
            </h3>
            <p className="text-sm text-slate-500 mb-4">{actionModal.orgName}</p>

            {(actionModal.action === 'extend_trial' || actionModal.action === 'activate' || actionModal.action === 'comp') && (
              <div className="mb-3">
                <label className="block text-sm text-slate-600 mb-1">עד תאריך *</label>
                <input
                  type="date"
                  value={actionDate}
                  onChange={e => setActionDate(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                />
              </div>
            )}

            <div className="mb-4">
              <label className="block text-sm text-slate-600 mb-1">הערה (חובה) *</label>
              <textarea
                value={actionNote}
                onChange={e => setActionNote(e.target.value)}
                rows={2}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                placeholder="סיבה לפעולה..."
              />
            </div>

            <div className="flex gap-2">
              <Button onClick={handleAction} disabled={submitting} className="flex-1">
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'אישור'}
              </Button>
              <Button variant="outline" onClick={() => { setActionModal(null); setActionDate(''); setActionNote(''); }}>
                ביטול
              </Button>
            </div>
          </div>
        </div>
      )}

      {pricingModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6" dir="rtl">
            <h3 className="text-lg font-bold text-slate-800 mb-1">עדכון תמחור</h3>
            <p className="text-sm text-slate-500 mb-4">{pricingModal.orgName}</p>

            <div className="mb-3">
              <label className="block text-sm text-slate-600 mb-1">מצב תמחור</label>
              <select
                value={pricingMode}
                onChange={e => { setPricingMode(e.target.value); if (e.target.value !== 'custom') setPricingCustomAmount(''); }}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              >
                <option value="standard">תמחור רגיל</option>
                <option value="founder">מנוי מייסדים (₪500)</option>
                <option value="custom">תמחור מותאם</option>
              </select>
            </div>

            {pricingMode === 'custom' && (
              <div className="mb-3">
                <label className="block text-sm text-slate-600 mb-1">סכום חודשי (₪)</label>
                <input
                  type="number"
                  value={pricingCustomAmount}
                  onChange={e => setPricingCustomAmount(e.target.value)}
                  min="1"
                  max="99999"
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                  placeholder="הזן סכום..."
                />
              </div>
            )}

            <div className="flex gap-2">
              <Button
                onClick={async () => {
                  setPricingSaving(true);
                  try {
                    const payload = { mode: pricingMode };
                    if (pricingMode === 'custom') payload.custom_amount = Number(pricingCustomAmount);
                    await billingService.updateOrgPricing(pricingModal.orgId, payload);
                    toast.success('תמחור עודכן');
                    setPricingModal(null);
                    loadData();
                  } catch (err) {
                    toast.error(err.response?.data?.detail || 'שגיאה בעדכון תמחור');
                  } finally {
                    setPricingSaving(false);
                  }
                }}
                disabled={pricingSaving || (pricingMode === 'custom' && (!pricingCustomAmount || Number(pricingCustomAmount) <= 0))}
                className="flex-1"
              >
                {pricingSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'שמור'}
              </Button>
              <Button variant="outline" onClick={() => setPricingModal(null)}>
                ביטול
              </Button>
            </div>
          </div>
        </div>
      )}

      {stepup && (
        <div className="fixed inset-0 bg-black/60 z-[10000] flex items-center justify-center p-4" onClick={() => setStepup(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-sm w-full p-6" dir="rtl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-amber-500" />
                אימות נוסף נדרש
              </h3>
              <button onClick={() => setStepup(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-slate-600 mb-4">
              קוד אימות נשלח לכתובת: <span className="font-medium">{stepup.maskedEmail}</span>
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-slate-700">קוד אימות *</label>
                <input
                  type="text"
                  value={stepupCode}
                  onChange={(e) => setStepupCode(e.target.value)}
                  placeholder="הזן את הקוד שקיבלת"
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm text-center font-mono tracking-widest focus:ring-2 focus:ring-amber-500"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleStepupVerify()}
                />
              </div>
              <Button
                onClick={handleStepupVerify}
                disabled={stepupLoading || !stepupCode.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {stepupLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'אמת וחזור לפעולה'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminBillingPage;
