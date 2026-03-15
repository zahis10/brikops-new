import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../services/api';
import {
  HardHat, ArrowRight, Users, Loader2, RefreshCw,
  Shield, BarChart3, Building2, CreditCard, ClipboardList,
  TrendingUp, ChevronLeft
} from 'lucide-react';

const ACTION_LABELS = {
  create: 'יצירה',
  update: 'עדכון',
  delete: 'מחיקה',
  activate: 'הפעלה',
  deactivate: 'השבתה',
  override: 'שינוי ידני',
  upgrade: 'שדרוג',
  downgrade: 'שנמוך',
  cancel: 'ביטול',
  renew: 'חידוש',
  trial_start: 'תחילת ניסיון',
  payment: 'תשלום',
  refund: 'החזר',
};

const ENTITY_LABELS = {
  subscription: 'מנוי',
  billing_plan: 'תוכנית',
  project_billing: 'חיוב פרויקט',
  project: 'פרויקט',
};

const getActionDotColor = (action) => {
  if (['create', 'activate', 'trial_start'].includes(action)) return 'bg-green-400';
  if (['update', 'upgrade', 'downgrade'].includes(action)) return 'bg-blue-400';
  if (['payment', 'refund', 'override'].includes(action)) return 'bg-amber-400';
  return 'bg-slate-400';
};

const formatAuditDescription = (ev) => {
  const action = ACTION_LABELS[ev.action] || ev.action || 'פעולה';
  const entity = ENTITY_LABELS[ev.entity_type] || ev.entity_type || '';
  const actor = ev.actor_name || 'מערכת';
  const detail = ev.description && ev.description !== '—' ? ev.description : '';
  if (detail) return `${actor}: ${detail}`;
  return `${actor} — ${action} ${entity}`;
};

const formatTimeAgo = (dateStr) => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return 'עכשיו';
  if (diff < 3600) return `לפני ${Math.floor(diff / 60)} דק׳`;
  if (diff < 86400) return `לפני ${Math.floor(diff / 3600)} שע׳`;
  if (diff < 604800) return `לפני ${Math.floor(diff / 86400)} ימים`;
  return d.toLocaleDateString('he-IL');
};

const TABS = [
  { id: 'overview', label: 'סקירה', icon: BarChart3 },
  { id: 'users', label: 'משתמשים', icon: Users },
  { id: 'orgs', label: 'ארגונים', icon: Building2 },
  { id: 'billing', label: 'חיובים', icon: CreditCard },
  { id: 'qc-templates', label: 'תבניות בקרת ביצוע / מסירה', icon: ClipboardList },
  { id: 'log', label: 'יומן', icon: ClipboardList },
];

const StatCard = ({ icon: Icon, label, value, bg, borderColor, numberColor, onClick }) => (
  <div
    onClick={onClick}
    className={`rounded-xl p-4 transition-all border-r-4 ${bg} ${
      onClick ? 'cursor-pointer hover:shadow-md hover:-translate-y-0.5 active:scale-[0.98]' : ''
    }`}
    style={{ borderRightColor: borderColor }}
  >
    <div className="flex items-center gap-2 mb-2">
      <Icon className="w-4 h-4" style={{ color: borderColor }} />
      <span className="text-xs text-slate-500 font-medium">{label}</span>
    </div>
    <p className={`text-3xl font-black ${numberColor}`}>{value}</p>
  </div>
);

const AdminPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [systemInfo, setSystemInfo] = useState(null);
  const [systemInfoLoading, setSystemInfoLoading] = useState(false);
  const [apiHealthy, setApiHealthy] = useState(null);
  const [paymentRequests, setPaymentRequests] = useState(null);
  const [auditEvents, setAuditEvents] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  const authHeaders = useCallback(() => {
    const token = localStorage.getItem('token');
    return { 'Authorization': `Bearer ${token}` };
  }, []);

  const loadSystemInfo = useCallback(async () => {
    setSystemInfoLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/system-info`, { headers: authHeaders() });
      if (res.ok) { setSystemInfo(await res.json()); setApiHealthy(true); }
      else { setApiHealthy(false); }
    } catch { setApiHealthy(false); }
    finally { setSystemInfoLoading(false); }
  }, [authHeaders]);

  const loadPaymentRequests = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/billing/payment-requests-summary`, { headers: authHeaders() });
      if (res.ok) setPaymentRequests(await res.json());
    } catch {}
  }, [authHeaders]);

  const loadAuditEvents = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/billing/audit`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setAuditEvents(Array.isArray(data) ? data : []);
      }
    } catch {}
  }, [authHeaders]);

  useEffect(() => {
    loadSystemInfo();
    loadPaymentRequests();
    loadAuditEvents();
  }, [loadSystemInfo, loadPaymentRequests, loadAuditEvents]);

  const handleTabClick = (tabId) => {
    if (tabId === 'users') { navigate('/admin/users'); return; }
    if (tabId === 'orgs') { navigate('/admin/orgs'); return; }
    if (tabId === 'billing') { navigate('/admin/billing?view=billing'); return; }
    if (tabId === 'qc-templates') { navigate('/admin/qc-templates'); return; }
    setActiveTab(tabId);
  };

  const counts = systemInfo?.counts || {};
  const openRequests = paymentRequests?.requests || [];
  const openCount = paymentRequests?.open_count || 0;
  const recentAudit = (auditEvents || []).slice(0, 8);

  const statusBadge = (status) => {
    if (status === 'requested' || status === 'sent') return { label: 'ממתין לתשלום', cls: 'bg-amber-100 text-amber-700' };
    if (status === 'pending_review') return { label: 'ממתין לאישור', cls: 'bg-orange-100 text-orange-700' };
    return { label: status, cls: 'bg-slate-100 text-slate-600' };
  };

  const getInitials = (name) => {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    return parts.length >= 2 ? parts[0][0] + parts[1][0] : parts[0].slice(0, 2);
  };

  if (systemInfoLoading && !systemInfo) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-20" dir="rtl">
      <header className="text-white sticky top-0 z-50" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', boxShadow: '0 2px 12px rgba(0,0,0,0.15)' }}>
        <div className="max-w-[1100px] mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate('/projects')} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="חזרה לפרויקטים">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="w-9 h-9 bg-amber-500 rounded-lg flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold leading-tight">אדמין פאנל</h1>
            <p className="text-xs text-slate-400">{user?.name} • Super Admin</p>
          </div>
          <button onClick={() => { loadSystemInfo(); loadPaymentRequests(); loadAuditEvents(); }} disabled={systemInfoLoading} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="רענן">
            <RefreshCw className={`w-5 h-5 ${systemInfoLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      <div className="sticky top-[52px] z-40 bg-white border-b border-slate-200">
        <div className="max-w-[1100px] mx-auto flex gap-1 px-3 py-2 overflow-x-auto" dir="rtl">
          {TABS.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button key={tab.id} onClick={() => handleTabClick(tab.id)}
                className={`flex items-center gap-1.5 py-2.5 px-3 rounded-lg text-sm font-semibold transition-all touch-manipulation whitespace-nowrap ${
                  isActive ? 'bg-amber-500 text-white shadow-md shadow-amber-500/25' : 'text-slate-400 hover:bg-slate-50'
                }`}>
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="max-w-[1100px] mx-auto px-4 pt-4 space-y-4">
        {activeTab === 'overview' && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                icon={Building2}
                label="ארגונים"
                value={counts.organizations ?? '—'}
                bg="bg-blue-50"
                borderColor="#60a5fa"
                numberColor="text-blue-600"
                onClick={() => handleTabClick('orgs')}
              />
              <StatCard
                icon={Users}
                label="משתמשים"
                value={counts.users ?? '—'}
                bg="bg-purple-50"
                borderColor="#c084fc"
                numberColor="text-purple-600"
                onClick={() => handleTabClick('users')}
              />
              <StatCard
                icon={HardHat}
                label="פרויקטים"
                value={counts.projects ?? '—'}
                bg="bg-amber-50"
                borderColor="#fbbf24"
                numberColor="text-amber-600"
              />
              <StatCard
                icon={TrendingUp}
                label="MRR"
                value="—"
                bg="bg-green-50"
                borderColor="#4ade80"
                numberColor="text-green-600"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl border shadow-sm p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-amber-500" />
                    <h3 className="text-sm font-bold text-slate-700">בקשות תשלום פתוחות</h3>
                    {openCount > 0 && (
                      <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-medium">{openCount}</span>
                    )}
                  </div>
                  <button onClick={() => handleTabClick('billing')} className="text-xs font-medium text-amber-600 hover:text-amber-700 flex items-center gap-1">
                    הכל <ChevronLeft className="w-3 h-3" />
                  </button>
                </div>
                {openRequests.length === 0 ? (
                  <div className="text-center py-6 text-sm text-slate-400">אין בקשות פתוחות</div>
                ) : (
                  <div className="space-y-2">
                    {openRequests.slice(0, 5).map((req, i) => {
                      const badge = statusBadge(req.status);
                      return (
                        <button
                          key={req.id || i}
                          onClick={() => handleTabClick('billing')}
                          className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-amber-50 border border-transparent hover:border-amber-200 transition-all text-right"
                        >
                          <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-xs font-bold text-slate-600 shrink-0">
                            {getInitials(req.org_name)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-slate-700 truncate">{req.org_name || 'ארגון'}</p>
                            <p className="text-xs text-slate-400">
                              {req.amount ? `₪${req.amount.toLocaleString()}` : ''}
                              {req.cycle ? ` • ${req.cycle === 'monthly' ? 'חודשי' : req.cycle}` : ''}
                            </p>
                          </div>
                          <span className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap font-medium ${badge.cls}`}>
                            {badge.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="bg-white rounded-xl border shadow-sm p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <ClipboardList className="w-4 h-4 text-blue-500" />
                    <h3 className="text-sm font-bold text-slate-700">פעילות אחרונה</h3>
                  </div>
                  <button onClick={() => setActiveTab('log')} className="text-xs font-medium text-amber-600 hover:text-amber-700 flex items-center gap-1">
                    הכל <ChevronLeft className="w-3 h-3" />
                  </button>
                </div>
                {recentAudit.length === 0 ? (
                  <div className="text-center py-6 text-sm text-slate-400">אין פעילות אחרונה</div>
                ) : (
                  <div className="space-y-2">
                    {recentAudit.map((ev, i) => (
                      <div key={ev.id || i} className="flex items-start gap-2.5 py-1.5">
                        <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${getActionDotColor(ev.action)}`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-slate-700 leading-snug">{formatAuditDescription(ev)}</p>
                          <p className="text-xs text-slate-400 mt-0.5">{formatTimeAgo(ev.created_at)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {(systemInfo || apiHealthy === false) && (
              <div className="flex flex-wrap items-center gap-2 pt-2 pb-4">
                <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${
                  apiHealthy === false ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${apiHealthy === false ? 'bg-red-500' : 'bg-green-500'}`} />
                  {apiHealthy === false ? 'API שגיאה' : 'API תקין'}
                </span>
                {systemInfo && (
                  <>
                    <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium">
                      DB: {systemInfo.db_name}
                    </span>
                    <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${
                      systemInfo.app_mode === 'prod' ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'
                    }`}>
                      Mode: {systemInfo.app_mode}
                    </span>
                    {systemInfo.git_sha && (
                      <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-500 font-mono">
                        {systemInfo.git_sha}
                      </span>
                    )}
                  </>
                )}
              </div>
            )}
          </>
        )}

        {activeTab === 'log' && (
          <div className="bg-white rounded-xl border shadow-sm p-4">
            <div className="flex items-center gap-2 mb-4">
              <ClipboardList className="w-4 h-4 text-blue-500" />
              <h3 className="text-sm font-bold text-slate-700">יומן פעילות</h3>
              {auditEvents && (
                <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-full">{auditEvents.length}</span>
              )}
            </div>
            {!auditEvents || auditEvents.length === 0 ? (
              <div className="text-center py-8 text-sm text-slate-400">אין רשומות ביומן</div>
            ) : (
              <div className="space-y-1">
                {auditEvents.map((ev, i) => (
                  <div key={ev.id || i} className={`flex items-start gap-3 py-2.5 px-2 rounded-lg ${i % 2 === 1 ? 'bg-slate-50' : ''}`}>
                    <div className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${getActionDotColor(ev.action)}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700">{formatAuditDescription(ev)}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-slate-400">{formatTimeAgo(ev.created_at)}</span>
                        {ev.entity_type && (
                          <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                            {ENTITY_LABELS[ev.entity_type] || ev.entity_type}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminPage;
