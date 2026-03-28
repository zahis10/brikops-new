import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAnalyticsService } from '../services/api';
import {
  Loader2, ChevronLeft, ChevronRight, Search, TrendingUp, TrendingDown,
  Minus, Sparkles, Users, ArrowUpDown
} from 'lucide-react';

const ROLE_LABELS = {
  project_manager: 'מנהל פרויקט',
  contractor: 'קבלן',
  owner: 'בעלים',
  management_team: 'צוות ניהולי',
  super_admin: 'אדמין',
  worker: 'עובד',
};

const STATUS_DOTS = {
  active: 'bg-emerald-400',
  low: 'bg-amber-400',
  dormant: 'bg-red-400',
  never: 'bg-slate-300',
};

const STATUS_LABELS = {
  active: 'פעיל',
  low: 'נמוך',
  dormant: 'רדום',
  never: 'מעולם לא',
};

const TREND_ICONS = {
  growing: { icon: TrendingUp, color: 'text-emerald-500', label: 'עולה' },
  declining: { icon: TrendingDown, color: 'text-red-500', label: 'יורד' },
  stable: { icon: Minus, color: 'text-slate-400', label: 'יציב' },
  new: { icon: Sparkles, color: 'text-blue-500', label: 'חדש' },
  inactive: { icon: Minus, color: 'text-slate-300', label: 'לא פעיל' },
};

const FEATURE_COLORS = {
  defects: 'border-red-200 bg-red-50',
  qc: 'border-blue-200 bg-blue-50',
  handover: 'border-emerald-200 bg-emerald-50',
  whatsapp: 'border-green-200 bg-green-50',
  plans: 'border-violet-200 bg-violet-50',
};

function formatLoginDate(iso) {
  if (!iso) return 'מעולם לא';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return 'עכשיו';
    if (diff < 3600) return `לפני ${Math.floor(diff / 60)} דק׳`;
    if (diff < 86400) return `לפני ${Math.floor(diff / 3600)} שע׳`;
    if (diff < 604800) return `לפני ${Math.floor(diff / 86400)} ימים`;
    return d.toLocaleDateString('he-IL');
  } catch {
    return '—';
  }
}

function TrendBadge({ trend }) {
  const t = TREND_ICONS[trend] || TREND_ICONS.stable;
  const Icon = t.icon;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs ${t.color}`}>
      <Icon className="w-3.5 h-3.5" />
      <span>{t.label}</span>
    </span>
  );
}

export default function AdminActivityPage() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState(30);
  const [role, setRole] = useState('');
  const [orgId, setOrgId] = useState('');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('score');
  const [order, setOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [data, setData] = useState(null);
  const [featureData, setFeatureData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [featureLoading, setFeatureLoading] = useState(true);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = { period, page, limit, sort, order };
      if (role) params.role = role;
      if (orgId) params.org_id = orgId;
      if (search) params.search = search;
      const result = await adminAnalyticsService.getUserActivity(params);
      setData(result);
    } catch {}
    finally { setLoading(false); }
  }, [period, page, limit, sort, order, role, orgId, search]);

  const loadFeatures = useCallback(async () => {
    setFeatureLoading(true);
    try {
      const result = await adminAnalyticsService.getFeatureUsage(period);
      setFeatureData(result);
    } catch {}
    finally { setFeatureLoading(false); }
  }, [period]);

  useEffect(() => { loadUsers(); }, [loadUsers]);
  useEffect(() => { loadFeatures(); }, [loadFeatures]);

  const toggleSort = (col) => {
    if (sort === col) {
      setOrder(o => o === 'desc' ? 'asc' : 'desc');
    } else {
      setSort(col);
      setOrder('desc');
    }
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total_count / limit) : 0;
  const orgs = data?.orgs || [];

  return (
    <div className="min-h-screen bg-slate-50 pb-20" dir="rtl">
      <header className="text-white sticky top-0 z-50" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)' }}>
        <div className="max-w-[1200px] mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate('/admin')} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors">
            <ChevronRight className="w-5 h-5" />
          </button>
          <Users className="w-5 h-5 text-amber-400" />
          <h1 className="text-base font-bold">פעילות משתמשים</h1>
        </div>
      </header>

      <div className="max-w-[1200px] mx-auto px-4 py-4 space-y-6">
        <div className="flex flex-wrap gap-2 items-center">
          <div className="flex bg-white border border-slate-200 rounded-lg overflow-hidden text-sm">
            {[7, 30, 90].map(p => (
              <button
                key={p}
                onClick={() => { setPeriod(p); setPage(1); }}
                className={`px-3 py-1.5 transition-colors ${period === p ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
              >
                {p} ימים
              </button>
            ))}
          </div>
          <div className="relative">
            <Search className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="חיפוש שם..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="pr-8 pl-3 py-1.5 border border-slate-200 rounded-lg text-sm w-40"
            />
          </div>
          <select
            value={role}
            onChange={e => { setRole(e.target.value); setPage(1); }}
            className="border border-slate-200 rounded-lg text-sm px-2 py-1.5"
          >
            <option value="">כל התפקידים</option>
            {Object.entries(ROLE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select
            value={orgId}
            onChange={e => { setOrgId(e.target.value); setPage(1); }}
            className="border border-slate-200 rounded-lg text-sm px-2 py-1.5"
          >
            <option value="">כל הארגונים</option>
            {orgs.map(o => (
              <option key={o.id} value={o.id}>{o.name || o.id}</option>
            ))}
          </select>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-800">פעילות משתמשים</h2>
            {data && <span className="text-xs text-slate-500">{data.total_count} משתמשים</span>}
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50 text-slate-500">
                      <SortHeader label="שם" col="name" current={sort} order={order} onSort={toggleSort} />
                      <th className="px-3 py-2 text-right font-medium">תפקיד</th>
                      <th className="px-3 py-2 text-right font-medium">ארגון</th>
                      <SortHeader label="כניסה אחרונה" col="last_login" current={sort} order={order} onSort={toggleSort} />
                      <SortHeader label="כניסות" col="login_count" current={sort} order={order} onSort={toggleSort} />
                      <th className="px-3 py-2 text-center font-medium">ליקויים</th>
                      <th className="px-3 py-2 text-center font-medium">בק״ב</th>
                      <th className="px-3 py-2 text-center font-medium">מסירות</th>
                      <th className="px-3 py-2 text-center font-medium">תמונות</th>
                      <SortHeader label="ציון" col="score" current={sort} order={order} onSort={toggleSort} />
                      <th className="px-3 py-2 text-center font-medium">סטטוס</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.users || []).map(u => (
                      <tr key={u.user_id} className="border-b border-slate-50 hover:bg-slate-50/50">
                        <td className="px-3 py-2 font-medium text-slate-800 whitespace-nowrap">{u.name || '—'}</td>
                        <td className="px-3 py-2 text-slate-600 whitespace-nowrap">
                          <span className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{ROLE_LABELS[u.role] || u.role}</span>
                        </td>
                        <td className="px-3 py-2 text-slate-600 whitespace-nowrap text-xs">{u.org_name || '—'}</td>
                        <td className="px-3 py-2 text-slate-500 whitespace-nowrap text-xs">{formatLoginDate(u.last_login)}</td>
                        <td className="px-3 py-2 text-center text-slate-600">{u.login_count || 0}</td>
                        <td className="px-3 py-2 text-center">
                          <span className="text-xs">{u.metrics?.defects_created || 0}/{u.metrics?.defects_closed || 0}</span>
                        </td>
                        <td className="px-3 py-2 text-center text-xs">{u.metrics?.qc_checked || 0}</td>
                        <td className="px-3 py-2 text-center text-xs">{u.metrics?.handover || 0}</td>
                        <td className="px-3 py-2 text-center text-xs">{u.metrics?.photos || 0}</td>
                        <td className="px-3 py-2 text-center">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${
                            u.activity_score >= 50 ? 'bg-emerald-100 text-emerald-700' :
                            u.activity_score >= 20 ? 'bg-amber-100 text-amber-700' :
                            'bg-slate-100 text-slate-500'
                          }`}>{u.activity_score}</span>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className="inline-flex items-center gap-1">
                            <span className={`w-2 h-2 rounded-full ${STATUS_DOTS[u.status] || 'bg-slate-300'}`} />
                            <span className="text-xs text-slate-500">{STATUS_LABELS[u.status] || u.status}</span>
                          </span>
                        </td>
                      </tr>
                    ))}
                    {(!data?.users || data.users.length === 0) && (
                      <tr><td colSpan={11} className="px-4 py-8 text-center text-slate-400 text-sm">אין תוצאות</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 py-3 border-t border-slate-100">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage(p => p - 1)}
                    className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                  <span className="text-xs text-slate-500">עמוד {page} מתוך {totalPages}</span>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage(p => p + 1)}
                    className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <div>
          <h2 className="text-sm font-bold text-slate-800 mb-3">אימוץ פיצ׳רים</h2>
          {featureLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {featureData && Object.entries(featureData.features || {}).map(([key, f]) => (
                <div key={key} className={`rounded-xl border p-4 ${FEATURE_COLORS[key] || 'border-slate-200 bg-white'}`}>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-bold text-slate-800 text-sm">{f.name}</h3>
                    <TrendBadge trend={f.trend} />
                  </div>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    <div className="text-center">
                      <div className="text-lg font-bold text-slate-800">{f.adoption_pct}%</div>
                      <div className="text-[10px] text-slate-500">אימוץ</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-slate-800">{f.orgs_using}</div>
                      <div className="text-[10px] text-slate-500">ארגונים</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-slate-800">{f.total_actions}</div>
                      <div className="text-[10px] text-slate-500">פעולות</div>
                    </div>
                  </div>
                  {f.top_power_users?.length > 0 && (
                    <div className="border-t border-slate-200/50 pt-2">
                      <div className="text-[10px] text-slate-500 mb-1">משתמשים מובילים</div>
                      {f.top_power_users.slice(0, 3).map((pu, i) => (
                        <div key={i} className="flex items-center justify-between text-xs text-slate-600">
                          <span>{pu.name || pu.user_id?.slice(0, 8)}</span>
                          <span className="font-medium">{pu.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SortHeader({ label, col, current, order, onSort }) {
  const active = current === col;
  return (
    <th
      className="px-3 py-2 text-right font-medium cursor-pointer hover:text-slate-700 select-none whitespace-nowrap"
      onClick={() => onSort(col)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown className={`w-3 h-3 ${active ? 'text-slate-800' : 'text-slate-300'}`} />
        {active && <span className="text-[9px]">{order === 'desc' ? '▼' : '▲'}</span>}
      </span>
    </th>
  );
}
