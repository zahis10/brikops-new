import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  ArrowRight, RefreshCw, Building2, FolderKanban, Home, DollarSign,
  AlertTriangle, ChevronDown, ChevronUp, ExternalLink, Loader2,
  ArrowUpDown, Search
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { BACKEND_URL } from '../services/api';

const CHURN_COLORS = { active: '#22c55e', at_risk: '#eab308', dormant: '#ef4444', unknown: '#94a3b8' };
const CHURN_LABELS = { active: 'פעיל', at_risk: 'בסיכון', dormant: 'רדום', unknown: 'לא ידוע' };
const FILTER_OPTIONS = [
  { key: 'all', label: 'הכל' },
  { key: 'active', label: 'פעילים', color: '#22c55e' },
  { key: 'at_risk', label: 'בסיכון', color: '#eab308' },
  { key: 'dormant', label: 'רדומים', color: '#ef4444' },
];
const SUB_STATUS_COLORS = {
  active: 'bg-green-100 text-green-700',
  trial: 'bg-blue-100 text-blue-700',
  inactive: 'bg-slate-100 text-slate-600',
  paywalled: 'bg-red-100 text-red-700',
};
const SUB_STATUS_LABELS = {
  active: 'פעיל',
  trial: 'ניסיון',
  inactive: 'לא פעיל',
  paywalled: 'חסום',
};

const currencyFmt = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });

function relativeDate(iso) {
  if (!iso) return 'לא ידוע';
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `לפני ${mins} דקות`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `לפני ${hours} שעות`;
    const days = Math.floor(hours / 24);
    if (days <= 30) return `לפני ${days} ימים`;
    const months = Math.floor(days / 30);
    return `לפני ${months} חודשים`;
  } catch { return 'לא ידוע'; }
}

function churnDot(status) {
  const colors = { active: 'bg-green-500', at_risk: 'bg-yellow-500', dormant: 'bg-red-500', unknown: 'bg-slate-400' };
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${colors[status] || colors.unknown}`} />;
}

const KpiCard = ({ icon: Icon, label, value, color }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3 shadow-sm">
    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
      <Icon className="w-5 h-5 text-white" />
    </div>
    <div>
      <p className="text-[11px] text-slate-500 font-medium">{label}</p>
      <p className="text-xl font-bold text-slate-800">{value}</p>
    </div>
  </div>
);

const ALERT_CONFIG = {
  dormant: { icon: '🔴', desc: (a) => `רדום — לא נכנס ${a.days_inactive ? `${a.days_inactive} ימים` : ''}` },
  overdue_invoice: { icon: '🔴', desc: (a) => `חשבונית באיחור ${a.days_overdue} ימים` },
  trial_ending: { icon: '🟡', desc: (a) => `תקופת ניסיון מסתיימת בקרוב` },
  no_projects: { icon: '🟡', desc: (a) => `ללא פרויקטים` },
};

const AdminDashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [alertsOpen, setAlertsOpen] = useState(true);
  const [sortCol, setSortCol] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [filter, setFilter] = useState('all');

  const authHeaders = useCallback(() => {
    const token = localStorage.getItem('token');
    return { Authorization: `Bearer ${token}` };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/dashboard/stats`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [authHeaders]);

  useEffect(() => { load(); }, [load]);

  const handleSort = (col) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('asc'); }
  };

  const filteredOrgs = useMemo(() => {
    if (!data) return [];
    let list = data.organizations;
    if (filter !== 'all') list = list.filter(o => o.churn_status === filter);
    return [...list].sort((a, b) => {
      let av = a[sortCol], bv = b[sortCol];
      if (typeof av === 'string') av = av.toLowerCase();
      if (typeof bv === 'string') bv = bv.toLowerCase();
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, filter, sortCol, sortDir]);

  const churnChartData = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.churn_chart)
      .filter(([_, v]) => v > 0)
      .map(([k, v]) => ({ name: CHURN_LABELS[k], value: v, fill: CHURN_COLORS[k] }));
  }, [data]);

  const totalOrgs = data ? Object.values(data.churn_chart).reduce((s, v) => s + v, 0) : 0;

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-2">שגיאה: {error}</p>
          <button onClick={load} className="text-amber-600 underline">נסה שוב</button>
        </div>
      </div>
    );
  }

  const SortHeader = ({ col, children, className = '' }) => (
    <th
      onClick={() => handleSort(col)}
      className={`px-2 py-2.5 text-right text-[11px] font-semibold text-slate-600 cursor-pointer hover:bg-slate-100 whitespace-nowrap select-none ${className}`}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {sortCol === col && <ArrowUpDown className="w-3 h-3 text-amber-500" />}
      </span>
    </th>
  );

  return (
    <div className="min-h-screen bg-slate-50 pb-10" dir="rtl">
      <header className="text-white sticky top-0 z-50" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', boxShadow: '0 2px 12px rgba(0,0,0,0.15)' }}>
        <div className="max-w-[1200px] mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => window.history.length > 2 ? navigate(-1) : navigate('/admin')} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="חזרה לאדמין">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold leading-tight">דשבורד CS</h1>
            <p className="text-xs text-slate-400">{user?.name} • Super Admin</p>
          </div>
          <button onClick={load} disabled={loading} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="רענן">
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      <div className="max-w-[1200px] mx-auto px-4 mt-4 space-y-4">
        {data && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <KpiCard icon={Building2} label="ארגונים פעילים" value={data.summary.active_orgs.toLocaleString()} color="bg-emerald-500" />
              <KpiCard icon={FolderKanban} label="פרויקטים" value={data.summary.total_projects.toLocaleString()} color="bg-blue-500" />
              <KpiCard icon={Home} label="דירות" value={data.summary.total_units.toLocaleString()} color="bg-purple-500" />
              <KpiCard icon={DollarSign} label="הכנסה חודשית" value={currencyFmt.format(data.summary.monthly_revenue)} color="bg-amber-500" />
            </div>

            {data.alerts.length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <button onClick={() => setAlertsOpen(o => !o)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                  <span className="text-sm font-bold text-slate-800 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    דורשים תשומת לב ({data.alerts.length})
                  </span>
                  {alertsOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                </button>
                {alertsOpen && (
                  <div className="border-t border-slate-100 divide-y divide-slate-100">
                    {data.alerts.map((a, i) => {
                      const cfg = ALERT_CONFIG[a.type] || { icon: '⚪', desc: () => a.type };
                      return (
                        <div key={i} className="px-4 py-2.5 flex items-center gap-3 text-sm">
                          <span className="text-base">{cfg.icon}</span>
                          <button onClick={() => navigate(`/admin/orgs`)} className="font-semibold text-slate-800 hover:text-amber-600 flex items-center gap-1">
                            {a.org_name}
                            <ExternalLink className="w-3 h-3" />
                          </button>
                          <span className="text-slate-500 text-xs">{cfg.desc(a)}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                <h3 className="text-sm font-bold text-slate-800 mb-3">פעילות לפי ארגון (30 יום)</h3>
                {data.activity_chart.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={data.activity_chart} layout="vertical" margin={{ right: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis type="category" dataKey="org_name" width={100} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="defects_30d" name="ליקויים" fill="#ef4444" radius={[0, 4, 4, 0]} />
                      <Bar dataKey="protocols_30d" name="מסירות" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-xs text-slate-400 text-center py-8">אין נתוני פעילות</p>
                )}
              </div>
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                <h3 className="text-sm font-bold text-slate-800 mb-3">סיכון נטישה</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie data={churnChartData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2}>
                      {churnChartData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                    </Pie>
                    <Tooltip />
                    <Legend />
                    <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" className="text-xl font-bold fill-slate-800">{totalOrgs}</text>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-bold text-slate-800 ml-auto">ארגונים</h3>
                <div className="flex gap-1.5">
                  {FILTER_OPTIONS.map(f => (
                    <button
                      key={f.key}
                      onClick={() => setFilter(f.key)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                        filter === f.key
                          ? 'bg-slate-800 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {f.color && <span className="inline-block w-2 h-2 rounded-full mr-1" style={{ backgroundColor: f.color }} />}
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <SortHeader col="name">ארגון</SortHeader>
                      <SortHeader col="created_at">הצטרפות</SortHeader>
                      <SortHeader col="projects_count">פרויקטים</SortHeader>
                      <SortHeader col="buildings_count">בניינים</SortHeader>
                      <SortHeader col="units_count">דירות</SortHeader>
                      <SortHeader col="defects_30d">ליקויים 30י׳</SortHeader>
                      <SortHeader col="protocols_30d">מסירות 30י׳</SortHeader>
                      <SortHeader col="defect_close_rate">% סגירה</SortHeader>
                      <SortHeader col="last_login">כניסה אחרונה</SortHeader>
                      <SortHeader col="subscription_status">מצב חיוב</SortHeader>
                      <SortHeader col="monthly_cost">חודשי</SortHeader>
                      <SortHeader col="open_invoices">חשב׳ פתוחות</SortHeader>
                      <SortHeader col="churn_status">סטטוס</SortHeader>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredOrgs.map(org => (
                      <tr key={org.id} className={`hover:bg-slate-50 ${org.churn_status === 'dormant' ? 'bg-red-50/40' : ''}`}>
                        <td className="px-2 py-2">
                          <button onClick={() => navigate('/admin/orgs')} className="text-sm font-medium text-slate-800 hover:text-amber-600 text-right">
                            {org.name || '—'}
                          </button>
                        </td>
                        <td className="px-2 py-2 text-xs text-slate-500 whitespace-nowrap">
                          {org.created_at ? new Date(org.created_at).toLocaleDateString('he-IL') : '—'}
                        </td>
                        <td className="px-2 py-2 text-center text-xs">{org.projects_count}</td>
                        <td className="px-2 py-2 text-center text-xs">{org.buildings_count}</td>
                        <td className="px-2 py-2 text-center text-xs font-medium">{org.units_count}</td>
                        <td className="px-2 py-2 text-center text-xs">{org.defects_30d}</td>
                        <td className="px-2 py-2 text-center text-xs">{org.protocols_30d}</td>
                        <td className="px-2 py-2 text-center text-xs">
                          <span className={org.defect_close_rate < 30 && org.defects_30d > 0 ? 'text-red-600 font-medium' : ''}>
                            {org.defect_close_rate}%
                          </span>
                        </td>
                        <td className="px-2 py-2 text-xs text-slate-500 whitespace-nowrap">{relativeDate(org.last_login)}</td>
                        <td className="px-2 py-2">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${SUB_STATUS_COLORS[org.subscription_status] || 'bg-slate-100 text-slate-600'}`}>
                            {SUB_STATUS_LABELS[org.subscription_status] || org.subscription_status}
                          </span>
                        </td>
                        <td className="px-2 py-2 text-xs font-medium whitespace-nowrap">{currencyFmt.format(org.monthly_cost)}</td>
                        <td className="px-2 py-2 text-center text-xs">
                          {org.open_invoices > 0 ? (
                            <span className="text-red-600 font-medium">{org.open_invoices}</span>
                          ) : '0'}
                        </td>
                        <td className="px-2 py-2">
                          <span className="flex items-center gap-1.5 text-xs whitespace-nowrap">
                            {churnDot(org.churn_status)}
                            {CHURN_LABELS[org.churn_status] || org.churn_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {filteredOrgs.length === 0 && (
                      <tr><td colSpan={13} className="text-center text-slate-400 py-8 text-sm">אין ארגונים להצגה</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AdminDashboardPage;
