import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminOrgService } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Building2, Search, X, Loader2,
  ChevronDown, ChevronUp, Users, FolderOpen,
  ShieldCheck, ShieldOff, CreditCard, ExternalLink,
  User, Phone, Mail
} from 'lucide-react';
import {
  getBillingStatusLabel, getPlanLabel, formatCurrency,
} from '../utils/billingLabels';

const ACCESS_FILTERS = [
  { id: 'all', label: 'הכל' },
  { id: 'full_access', label: 'פעילים' },
  { id: 'read_only', label: 'מוגבלים' },
  { id: 'suspended', label: 'חסומים' },
];

const getAccessBadge = (access, reason) => {
  if (reason === 'suspended') return { label: 'חסום', cls: 'bg-red-100 text-red-700' };
  if (access === 'full_access') return { label: 'גישה מלאה', cls: 'bg-green-100 text-green-700' };
  return { label: 'מוגבלת', cls: 'bg-amber-100 text-amber-700' };
};

const getOrgBorderColor = (org) => {
  if (org.subscription?.manual_override?.is_suspended || org.read_only_reason === 'suspended') return 'border-r-red-400';
  if (org.effective_access === 'full_access') return 'border-r-green-400';
  return 'border-r-amber-400';
};

const getOrgFilterCategory = (org) => {
  if (org.subscription?.manual_override?.is_suspended || org.read_only_reason === 'suspended') return 'suspended';
  if (org.effective_access === 'full_access') return 'full_access';
  return 'read_only';
};

const getInitials = (name) => {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return parts[0][0] + parts[1][0];
  return parts[0][0];
};

const getRoleBadge = (role) => {
  if (role === 'owner') return { label: 'בעלים', cls: 'bg-green-100 text-green-700' };
  if (role === 'org_admin' || role === 'billing_admin') return { label: 'מנהל', cls: 'bg-amber-100 text-amber-700' };
  return { label: 'חבר', cls: 'bg-slate-100 text-slate-600' };
};

const formatDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch { return iso; }
};

const AdminOrgsPage = () => {
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [expandedOrgId, setExpandedOrgId] = useState(null);
  const [orgDetails, setOrgDetails] = useState({});

  const loadOrgs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminOrgService.listOrgs();
      setOrgs(data);
    } catch (err) {
      toast.error('שגיאה בטעינת ארגונים');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadOrgs(); }, [loadOrgs]);

  const filteredOrgs = useMemo(() => {
    let list = orgs;
    if (activeFilter !== 'all') {
      list = list.filter(o => getOrgFilterCategory(o) === activeFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(o =>
        (o.name || '').toLowerCase().includes(q) ||
        (o.owner?.name || '').toLowerCase().includes(q) ||
        (o.owner?.email || '').toLowerCase().includes(q)
      );
    }
    return list;
  }, [orgs, activeFilter, searchQuery]);

  const filterCounts = useMemo(() => {
    const counts = { all: orgs.length, full_access: 0, read_only: 0, suspended: 0 };
    orgs.forEach(o => {
      const cat = getOrgFilterCategory(o);
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [orgs]);

  const toggleExpand = async (orgId) => {
    if (expandedOrgId === orgId) {
      setExpandedOrgId(null);
      return;
    }
    setExpandedOrgId(orgId);
    if (!orgDetails[orgId]) {
      setOrgDetails(prev => ({ ...prev, [orgId]: { loading: true } }));
      try {
        const [projects, membersData] = await Promise.all([
          adminOrgService.getOrgProjects(orgId),
          adminOrgService.getOrgMembers(orgId).catch(() => ({ members: [] })),
        ]);
        const members = membersData.members || membersData || [];
        setOrgDetails(prev => ({
          ...prev,
          [orgId]: { loading: false, projects, members },
        }));
      } catch (err) {
        setOrgDetails(prev => ({
          ...prev,
          [orgId]: { loading: false, projects: [], members: [], error: true },
        }));
        toast.error('שגיאה בטעינת פרטי ארגון');
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <header className="bg-gradient-to-l from-slate-900 to-slate-800 text-white">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate('/admin')} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="חזרה לאדמין">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="w-9 h-9 bg-blue-500 rounded-lg flex items-center justify-center">
            <Building2 className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold leading-tight">ניהול ארגונים</h1>
            <p className="text-xs text-slate-400">{orgs.length} ארגונים</p>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-4 space-y-4">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="חיפוש לפי שם ארגון, שם בעלים, אימייל..."
            className="w-full pr-10 pl-10 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400 transition-colors"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
          {ACCESS_FILTERS.map(f => (
            <button
              key={f.id}
              onClick={() => setActiveFilter(f.id)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                activeFilter === f.id
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'bg-white border border-slate-200 text-slate-500 hover:bg-slate-50'
              }`}
            >
              {f.label} ({filterCounts[f.id] || 0})
            </button>
          ))}
        </div>

        {filteredOrgs.length === 0 ? (
          <div className="text-center py-12">
            <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-400">
              {searchQuery || activeFilter !== 'all' ? 'לא נמצאו ארגונים תואמים' : 'אין ארגונים'}
            </p>
            {(searchQuery || activeFilter !== 'all') && (
              <button
                onClick={() => { setSearchQuery(''); setActiveFilter('all'); }}
                className="mt-2 text-xs text-amber-600 hover:text-amber-700 font-medium"
              >
                נקה סינון
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredOrgs.map(org => {
              const badge = getAccessBadge(org.effective_access, org.read_only_reason);
              const borderColor = getOrgBorderColor(org);
              const isExpanded = expandedOrgId === org.id;
              const details = orgDetails[org.id];
              const sub = org.subscription || {};

              return (
                <div key={org.id} className={`bg-white rounded-xl border border-slate-200 border-r-[3px] ${borderColor} overflow-hidden transition-shadow ${isExpanded ? 'shadow-md' : 'hover:shadow-sm'}`}>
                  <button
                    onClick={() => toggleExpand(org.id)}
                    className="w-full text-right px-4 py-3 flex items-center gap-3 hover:bg-slate-50/50 transition-colors"
                  >
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 text-white flex items-center justify-center text-sm font-bold flex-shrink-0">
                      {getInitials(org.name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-base font-bold text-slate-800 truncate">{org.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0 ${badge.cls}`}>
                          {badge.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span>{org.owner?.name || '—'}</span>
                        {org.owner?.email && (
                          <>
                            <span className="text-slate-300">•</span>
                            <span className="truncate">{org.owner.email}</span>
                          </>
                        )}
                        {sub.status && (
                          <>
                            <span className="text-slate-300">•</span>
                            <span>{getBillingStatusLabel(sub.status)}</span>
                          </>
                        )}
                      </div>
                    </div>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
                  </button>

                  {isExpanded && (
                    <div className="border-t border-slate-100 bg-slate-50/50">
                      {details?.loading ? (
                        <div className="flex justify-center py-6">
                          <Loader2 className="w-5 h-5 animate-spin text-amber-500" />
                        </div>
                      ) : details?.error ? (
                        <div className="text-center py-6 text-sm text-slate-400">שגיאה בטעינת פרטים</div>
                      ) : details ? (
                        <div className="p-4 space-y-4">
                          <div className="grid grid-cols-3 gap-2">
                            <div className="bg-white rounded-lg border border-slate-200 p-2.5 text-center">
                              <div className="text-xs text-slate-500 mb-0.5">פרויקטים</div>
                              <div className="text-lg font-bold text-slate-800">{details.projects?.length || 0}</div>
                            </div>
                            <div className="bg-white rounded-lg border border-slate-200 p-2.5 text-center">
                              <div className="text-xs text-slate-500 mb-0.5">חברים</div>
                              <div className="text-lg font-bold text-slate-800">{details.members?.length || 0}</div>
                            </div>
                            <div className="bg-white rounded-lg border border-slate-200 p-2.5 text-center">
                              <div className="text-xs text-slate-500 mb-0.5">סטטוס מנוי</div>
                              <div className={`text-sm font-bold ${badge.cls.includes('green') ? 'text-green-700' : badge.cls.includes('red') ? 'text-red-700' : 'text-amber-700'}`}>
                                {getBillingStatusLabel(sub.status)}
                              </div>
                            </div>
                          </div>

                          {details.projects?.length > 0 && (
                            <div>
                              <div className="flex items-center gap-1.5 mb-2">
                                <FolderOpen className="w-3.5 h-3.5 text-blue-500" />
                                <span className="text-xs font-bold text-slate-700">פרויקטים</span>
                                <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{details.projects.length}</span>
                              </div>
                              <div className="space-y-1.5">
                                {details.projects.map(p => (
                                  <button
                                    key={p.id}
                                    onClick={() => navigate(`/projects/${p.id}/control`)}
                                    className="w-full text-right bg-white rounded-lg border border-slate-200 px-3 py-2.5 hover:border-blue-300 hover:shadow-sm transition-all flex items-center gap-3 group"
                                  >
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2">
                                        <span className="text-sm font-semibold text-slate-800 truncate group-hover:text-blue-600 transition-colors">{p.name || p.id}</span>
                                        {p.code && <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-mono flex-shrink-0">{p.code}</span>}
                                      </div>
                                      <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                                        {p.status && <span>{p.status === 'active' ? 'פעיל' : p.status === 'archived' ? 'בארכיון' : p.status}</span>}
                                        {p.member_count != null && (
                                          <>
                                            <span className="text-slate-300">•</span>
                                            <span className="flex items-center gap-0.5"><Users className="w-3 h-3" />{p.member_count} חברים</span>
                                          </>
                                        )}
                                      </div>
                                    </div>
                                    <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-blue-400 flex-shrink-0 transition-colors" />
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {details.members?.length > 0 && (
                            <div>
                              <div className="flex items-center gap-1.5 mb-2">
                                <Users className="w-3.5 h-3.5 text-purple-500" />
                                <span className="text-xs font-bold text-slate-700">חברים</span>
                                <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{details.members.length}</span>
                              </div>
                              <div className="space-y-1.5">
                                {details.members.map(m => {
                                  const roleBadge = getRoleBadge(m.is_owner ? 'owner' : (m.role || m.org_role));
                                  return (
                                    <div key={m.user_id || m.id} className="bg-white rounded-lg border border-slate-200 px-3 py-2.5 flex items-center gap-3">
                                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-slate-300 to-slate-500 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                                        {getInitials(m.name)}
                                      </div>
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                          <span className="text-sm font-medium text-slate-800 truncate">{m.name || '—'}</span>
                                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0 ${roleBadge.cls}`}>
                                            {roleBadge.label}
                                          </span>
                                          {m.is_owner && (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0 bg-green-100 text-green-700">בעלים</span>
                                          )}
                                        </div>
                                        <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                                          {(m.phone || m.phone_e164) && (
                                            <span className="flex items-center gap-0.5 flex-shrink-0"><Phone className="w-3 h-3" /><bdi dir="ltr">{m.phone || m.phone_e164}</bdi></span>
                                          )}
                                          {m.email && (
                                            <>
                                              {(m.phone || m.phone_e164) && <span className="text-slate-300">•</span>}
                                              <span className="flex items-center gap-0.5 truncate"><Mail className="w-3 h-3 flex-shrink-0" />{m.email}</span>
                                            </>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          <div>
                            <div className="flex items-center gap-1.5 mb-2">
                              <CreditCard className="w-3.5 h-3.5 text-amber-500" />
                              <span className="text-xs font-bold text-slate-700">מנוי</span>
                            </div>
                            <div className="bg-white rounded-lg border border-slate-200 px-3 py-2.5">
                              <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                                <div>
                                  <span className="text-slate-400">תוכנית: </span>
                                  <span className="font-medium">{getPlanLabel(sub.plan_id) || '—'}</span>
                                </div>
                                <div>
                                  <span className="text-slate-400">סטטוס: </span>
                                  <span className="font-medium">{getBillingStatusLabel(sub.status)}</span>
                                </div>
                                {sub.paid_until && (
                                  <div>
                                    <span className="text-slate-400">שולם עד: </span>
                                    <span className="font-medium">{formatDate(sub.paid_until)}</span>
                                  </div>
                                )}
                                {sub.trial_end_at && (
                                  <div>
                                    <span className="text-slate-400">סוף ניסיון: </span>
                                    <span className="font-medium">{formatDate(sub.trial_end_at)}</span>
                                  </div>
                                )}
                                {sub.manual_override?.comped_until && (
                                  <div>
                                    <span className="text-slate-400">מתנה עד: </span>
                                    <span className="font-medium">{formatDate(sub.manual_override.comped_until)}</span>
                                  </div>
                                )}
                                {sub.total_monthly > 0 && (
                                  <div>
                                    <span className="text-slate-400">עלות חודשית: </span>
                                    <span className="font-medium">{formatCurrency(sub.total_monthly)}</span>
                                  </div>
                                )}
                              </div>
                              <div className="mt-2 pt-2 border-t border-slate-100">
                                <button
                                  onClick={() => navigate('/admin/billing', { state: { from: '/admin/orgs' } })}
                                  className="text-xs text-amber-600 hover:text-amber-700 font-semibold flex items-center gap-1"
                                >
                                  <ExternalLink className="w-3 h-3" />
                                  פתח בחיוב
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
};

export default AdminOrgsPage;
