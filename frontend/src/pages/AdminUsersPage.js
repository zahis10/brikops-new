import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { adminUserService, stepupService, isStepupError } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Search, User, Phone, Building2, Calendar,
  Loader2, ChevronLeft, ChevronRight, ChevronDown, X, Shield, Edit3, KeyRound, MoreVertical, Settings,
  Users, Mail, HardHat, UserX, Globe
} from 'lucide-react';
import ReactDOM from 'react-dom';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { tRole, tSubRole } from '../i18n';
import UserDrawer from '../components/UserDrawer';

const STATUS_LABELS = {
  trialing: { label: 'ניסיון', color: 'bg-amber-100 text-amber-700' },
  active: { label: 'פעיל', color: 'bg-green-100 text-green-700' },
  suspended: { label: 'מושעה', color: 'bg-red-100 text-red-700' },
  comped: { label: 'מתנה', color: 'bg-blue-100 text-blue-700' },
  none: { label: 'ללא', color: 'bg-slate-100 text-slate-500' },
};

const ROLE_STYLE = {
  super_admin: { badge: 'bg-red-100 text-red-600', border: 'border-r-red-400', avatar: 'bg-gradient-to-br from-red-400 to-red-600 text-white', label: 'אדמין מערכת' },
  project_manager: { badge: 'bg-amber-100 text-amber-600', border: 'border-r-amber-400', avatar: 'bg-gradient-to-br from-amber-400 to-amber-600 text-white', label: 'מנהל פרויקט' },
  contractor: { badge: 'bg-blue-100 text-blue-600', border: 'border-r-blue-400', avatar: 'bg-gradient-to-br from-blue-400 to-blue-600 text-white', label: 'קבלן' },
  management_team: { badge: 'bg-purple-100 text-purple-600', border: 'border-r-purple-400', avatar: 'bg-gradient-to-br from-purple-400 to-purple-600 text-white', label: 'צוות ניהולי' },
  viewer: { badge: 'bg-slate-100 text-slate-500', border: 'border-r-slate-300', avatar: 'bg-gradient-to-br from-slate-300 to-slate-500 text-white', label: 'צופה' },
  default: { badge: 'bg-slate-100 text-slate-500', border: 'border-r-slate-300', avatar: 'bg-gradient-to-br from-slate-300 to-slate-500 text-white', label: 'משתמש' },
};

const getUserRole = (u) => {
  if (u.platform_role === 'super_admin') return 'super_admin';
  if (u.role) return u.role;
  return 'default';
};

const getRoleStyle = (u) => ROLE_STYLE[getUserRole(u)] || ROLE_STYLE.default;

const isDemo = (u) => u.is_demo === true || (u.email && /demo.*@brikops\.com/i.test(u.email));

const getInitials = (name) => {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return parts[0][0] + parts[1][0];
  return parts[0][0];
};

const FILTERS = [
  { id: 'all', label: 'הכל', countLabel: 'משתמשים' },
  { id: 'super_admin', label: 'אדמין מערכת', countLabel: 'אדמיני מערכת' },
  { id: 'demo', label: 'דמו', countLabel: 'משתמשי דמו' },
];

const AdminUsersPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const goBack = () => {
    if (location.state?.from) navigate(location.state.from);
    else navigate('/admin');
  };
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [phoneModal, setPhoneModal] = useState(null);
  const [newPhone, setNewPhone] = useState('');
  const [phoneNote, setPhoneNote] = useState('');
  const [phoneSubmitting, setPhoneSubmitting] = useState(false);
  const [roleEdit, setRoleEdit] = useState(null);
  const [roleNote, setRoleNote] = useState('');
  const [roleSubmitting, setRoleSubmitting] = useState(false);
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [stepup, setStepup] = useState(null);
  const [stepupCode, setStepupCode] = useState('');
  const [stepupLoading, setStepupLoading] = useState(false);
  const [passwordModal, setPasswordModal] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [passwordNote, setPasswordNote] = useState('');
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [drawerMember, setDrawerMember] = useState(null);
  const [drawerProjectId, setDrawerProjectId] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const LIMIT = 50;

  const openMemberDrawer = (userDetail, pm) => {
    setDrawerMember({
      user_id: userDetail.id,
      user_name: userDetail.name,
      user_phone: userDetail.phone_e164,
      role: pm.role,
      sub_role: pm.sub_role,
      org_role: pm.org_role || null,
      is_org_owner: pm.is_org_owner || false,
      preferred_language: userDetail.preferred_language || null,
    });
    setDrawerProjectId(pm.project_id);
  };

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminUserService.listUsers(query, skip, LIMIT);
      setUsers(data.users || []);
      setTotal(data.total || 0);
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => loadUsers());
      } else {
        toast.error('שגיאה בטעינת משתמשים');
      }
    } finally {
      setLoading(false);
    }
  }, [query, skip]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const handleSearchChange = (e) => {
    setSearchInput(e.target.value);
    setSkip(0);
    setQuery(e.target.value);
  };

  const openDetail = async (userId) => {
    setDetailLoading(true);
    setProjectsOpen(false);
    try {
      const data = await adminUserService.getUser(userId);
      setSelectedUser(data);
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => openDetail(userId));
      } else {
        toast.error('שגיאה בטעינת פרטי משתמש');
      }
    } finally {
      setDetailLoading(false);
    }
  };

  const handlePhoneChange = async () => {
    if (!newPhone.trim() || !phoneNote.trim()) {
      toast.error('חובה למלא מספר חדש וסיבה');
      return;
    }
    setPhoneSubmitting(true);
    try {
      await adminUserService.changeUserPhone(phoneModal.id, newPhone, phoneNote);
      toast.success('מספר טלפון עודכן בהצלחה');
      setPhoneModal(null);
      setNewPhone('');
      setPhoneNote('');
      if (selectedUser && selectedUser.id === phoneModal.id) {
        openDetail(phoneModal.id);
      }
      loadUsers();
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => handlePhoneChange());
      } else {
        const detail = err.response?.data?.detail || 'שגיאה בעדכון מספר';
        toast.error(typeof detail === 'object' ? detail.message : detail);
      }
    } finally {
      setPhoneSubmitting(false);
    }
  };

  const startStepup = async (retryAction) => {
    setStepupLoading(true);
    try {
      const result = await stepupService.requestChallenge();
      setStepup({ challengeId: result.challenge_id, maskedEmail: result.masked_email, retryAction });
      setStepupCode('');
      if (result.fallback) {
        toast.info('SMTP לא זמין — קוד Step-Up זמין בלוגים (Break-glass)');
      } else {
        toast.success(`קוד אימות נשלח ל-${result.masked_email}`);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בשליחת קוד אימות';
      toast.error(typeof detail === 'object' ? (detail.message || JSON.stringify(detail)) : detail);
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

  const handleRoleChange = async () => {
    if (!roleEdit || !roleNote.trim()) {
      toast.error('חובה לציין סיבה לשינוי');
      return;
    }
    setRoleSubmitting(true);
    try {
      await adminUserService.changeUserRole(roleEdit.userId, roleEdit.projectId, roleEdit.newRole, roleNote);
      toast.success('התפקיד עודכן בהצלחה');
      const refreshUserId = selectedUser?.id;
      setRoleEdit(null);
      setRoleNote('');
      await loadUsers();
      if (refreshUserId) {
        await openDetail(refreshUserId);
      }
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => handleRoleChange());
      } else {
        const detail = err.response?.data?.detail;
        if (err.response?.status === 409 && detail?.code === 'ROLE_CONFLICT') {
          toast.error('לא ניתן לשלב תפקיד קבלן עם תפקיד ניהולי בארגון');
        } else {
          toast.error(typeof detail === 'object' ? detail.message : (detail || 'שגיאה בעדכון תפקיד'));
        }
      }
    } finally {
      setRoleSubmitting(false);
    }
  };

  const handleResetPassword = async () => {
    if (!newPassword.trim() || !passwordNote.trim()) {
      toast.error('חובה למלא סיסמה חדשה וסיבה');
      return;
    }
    setPasswordSubmitting(true);
    try {
      await adminUserService.resetUserPassword(passwordModal.id, newPassword, passwordNote);
      toast.success('הסיסמה אופסה בהצלחה');
      setPasswordModal(null);
      setNewPassword('');
      setPasswordNote('');
      if (selectedUser && selectedUser.id === passwordModal.id) {
        openDetail(passwordModal.id);
      }
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => handleResetPassword());
      } else {
        const detail = err.response?.data?.detail || 'שגיאה באיפוס סיסמה';
        toast.error(typeof detail === 'object' ? detail.message : detail);
      }
    } finally {
      setPasswordSubmitting(false);
    }
  };

  const filterCounts = useMemo(() => ({
    all: users.length,
    super_admin: users.filter(u => u.platform_role === 'super_admin').length,
    demo: users.filter(u => isDemo(u)).length,
  }), [users]);

  const filteredUsers = useMemo(() => {
    if (activeFilter === 'all') return users;
    if (activeFilter === 'super_admin') return users.filter(u => u.platform_role === 'super_admin');
    if (activeFilter === 'demo') return users.filter(u => isDemo(u));
    return users;
  }, [users, activeFilter]);

  const activeFilterObj = FILTERS.find(f => f.id === activeFilter) || FILTERS[0];

  if (!user || user.platform_role !== 'super_admin') {
    return <div className="p-8 text-center text-slate-500">אין גישה</div>;
  }

  const drawerRoleStyle = selectedUser ? getRoleStyle(selectedUser) : ROLE_STYLE.default;

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <header className="text-white sticky top-0 z-50" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', boxShadow: '0 2px 12px rgba(0,0,0,0.15)' }}>
        <div className="max-w-[1100px] mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={goBack} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors" title="חזרה לאדמין">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="w-9 h-9 bg-amber-500 rounded-lg flex items-center justify-center">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold leading-tight">ניהול משתמשים</h1>
            <p className="text-xs text-slate-400">{total} משתמשים</p>
          </div>
          <button
            onClick={() => navigate('/admin/billing', { state: { from: '/admin/users' } })}
            className="px-3 py-1.5 text-xs bg-white/[0.07] border border-white/10 rounded-lg hover:bg-white/[0.14] transition-colors"
          >
            חיוב וארגונים
          </button>
        </div>
      </header>

      <div className="max-w-[1100px] mx-auto px-4 pt-4">
        <div className="relative mb-3">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchInput}
            onChange={handleSearchChange}
            placeholder="חיפוש שם, טלפון, אימייל..."
            className="w-full pr-10 pl-4 py-2.5 border border-slate-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-400"
          />
        </div>

        <div className="flex gap-2 overflow-x-auto pb-2 mb-1 scrollbar-hide">
          {FILTERS.map(f => {
            const isActive = activeFilter === f.id;
            return (
              <button
                key={f.id}
                onClick={() => setActiveFilter(f.id)}
                className={`flex items-center gap-1 py-1.5 px-3 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                  isActive
                    ? 'bg-amber-500 text-white shadow-sm shadow-amber-500/25'
                    : 'bg-white border border-slate-200 text-slate-500 hover:border-slate-300'
                }`}
              >
                {f.label}
                <span className={`${isActive ? 'text-amber-100' : 'text-slate-400'}`}>({filterCounts[f.id]})</span>
              </button>
            );
          })}
        </div>

        <div className="text-xs text-slate-400 mb-3">
          {filteredUsers.length} {activeFilterObj.countLabel}
          {activeFilter !== 'all' && total > users.length && <span className="text-slate-300"> (מתוך {total} סה״כ)</span>}
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <UserX className="w-14 h-14 text-slate-300 mb-3" />
            <p className="text-sm font-semibold text-slate-500 mb-1">לא נמצאו משתמשים</p>
            <p className="text-xs text-slate-400 mb-4">נסה לשנות את החיפוש או הפילטר</p>
            <button
              onClick={() => { setActiveFilter('all'); setSearchInput(''); setQuery(''); }}
              className="text-xs text-amber-600 font-semibold hover:text-amber-700"
            >
              נקה חיפוש ופילטרים
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-2 lg:grid lg:grid-cols-2 lg:gap-3 lg:space-y-0">
              {filteredUsers.map(u => {
                const rs = getRoleStyle(u);
                const st = STATUS_LABELS[u.billing_status] || STATUS_LABELS.none;
                return (
                  <div
                    key={u.id}
                    onClick={() => openDetail(u.id)}
                    className={`bg-white rounded-xl border border-slate-200 border-r-[3px] ${rs.border} p-3 cursor-pointer hover:border-amber-200 hover:shadow-sm transition-all active:bg-slate-50`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full ${rs.avatar} flex items-center justify-center text-xs font-bold flex-shrink-0`}>
                        {getInitials(u.name)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-bold text-slate-800 truncate">{u.name}</span>
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0 ${rs.badge}`}>
                            {u.platform_role === 'super_admin' ? rs.label : tRole(u.role || 'default')}
                          </span>
                          {isDemo(u) && (
                            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-yellow-100 text-yellow-600 flex-shrink-0">דמו</span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-slate-500">
                          {u.phone_e164 && (
                            <span className="flex items-center gap-1">
                              <Phone className="w-3 h-3" />
                              <bdi className="font-mono" dir="ltr">{u.phone_e164}</bdi>
                            </span>
                          )}
                          {u.email && (
                            <span className="flex items-center gap-1 truncate">
                              <Mail className="w-3 h-3" />
                              {u.email}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1 flex-shrink-0">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${st.color}`}>{st.label}</span>
                        <span className="text-[10px] text-slate-400">{u.project_count || 0} פרויקטים</span>
                        <span className="text-[10px] text-slate-300">{u.created_at ? new Date(u.created_at).toLocaleDateString('he-IL') : ''}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {total > LIMIT && (
              <div className="flex items-center justify-center gap-4 mt-4 mb-4">
                <button
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - LIMIT))}
                  className="p-2 rounded-lg hover:bg-slate-200 disabled:opacity-30 transition-colors"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
                <span className="text-sm text-slate-600 font-medium">
                  {skip + 1}–{Math.min(skip + LIMIT, total)} מתוך {total}
                </span>
                <button
                  disabled={skip + LIMIT >= total}
                  onClick={() => setSkip(skip + LIMIT)}
                  className="p-2 rounded-lg hover:bg-slate-200 disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {(selectedUser || detailLoading) && (
        <div className="fixed inset-0 bg-black/40 z-50 flex justify-start">
          <div className="bg-white w-full max-w-lg h-full overflow-y-auto shadow-2xl" dir="rtl">
            <div className="sticky top-0 z-10" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)' }}>
              <div className="px-4 py-3 flex items-center justify-between text-white">
                <h2 className="font-bold text-sm">פרטי משתמש</h2>
                <button onClick={() => setSelectedUser(null)} className="text-white/60 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            {detailLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
              </div>
            ) : selectedUser && (
              <div className="p-4 space-y-3">
                <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-xl">
                  <div className={`w-14 h-14 rounded-full ${drawerRoleStyle.avatar} flex items-center justify-center text-lg font-bold flex-shrink-0`}>
                    {getInitials(selectedUser.name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-base font-bold text-slate-900 truncate">{selectedUser.name}</span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${drawerRoleStyle.badge}`}>
                        {drawerRoleStyle.label}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 font-mono">{selectedUser.id?.slice(0, 12)}...</div>
                  </div>
                </div>

                <Card className="p-4 space-y-2.5">
                  <div className="flex items-center gap-2 text-sm">
                    <Phone className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    <bdi className="font-mono" dir="ltr">{selectedUser.phone_e164 || '-'}</bdi>
                    <button
                      onClick={() => { setPhoneModal(selectedUser); setNewPhone(''); setPhoneNote(''); }}
                      className="text-amber-600 hover:text-amber-700 mr-auto"
                      title="החלפת טלפון"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Mail className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    <span className="truncate">{selectedUser.email || '-'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    <span className="text-slate-600">
                      {selectedUser.created_at ? new Date(selectedUser.created_at).toLocaleDateString('he-IL') : '-'}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-slate-500">סטטוס:</span>
                    <span>{selectedUser.status || '-'}</span>
                  </div>
                  {selectedUser.company && (
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-slate-500">חברה:</span>
                      <span>{selectedUser.company}</span>
                    </div>
                  )}
                </Card>

                <div className="flex gap-2">
                  <button
                    onClick={() => { setPasswordModal(selectedUser); setNewPassword(''); setPasswordNote(''); }}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-medium text-amber-600 bg-amber-50 rounded-lg hover:bg-amber-100 transition-colors"
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    איפוס סיסמה
                  </button>
                  {selectedUser.id === user?.id && (
                    <button
                      onClick={() => navigate('/settings/account')}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                    >
                      <Settings className="w-3.5 h-3.5" />
                      הגדרות חשבון
                    </button>
                  )}
                </div>

                <Card className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Globe className="w-4 h-4 text-green-500" />
                    <label className="text-xs font-semibold text-slate-600">שפת הודעות WhatsApp</label>
                  </div>
                  <select
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
                    value={selectedUser.preferred_language || 'he'}
                    onChange={async (e) => {
                      const newLang = e.target.value;
                      try {
                        await adminUserService.updatePreferredLanguage(selectedUser.id, newLang);
                        setSelectedUser({ ...selectedUser, preferred_language: newLang });
                        toast.success('שפת WhatsApp עודכנה');
                      } catch (err) {
                        toast.error(err.response?.data?.detail || 'שגיאה בעדכון שפה');
                      }
                    }}
                  >
                    <option value="he">עברית</option>
                    <option value="en">English</option>
                    <option value="ar">العربية</option>
                    <option value="zh">中文 (fallback to en)</option>
                  </select>
                </Card>

                {selectedUser.org_memberships?.length > 0 && (
                  <Card className="p-4">
                    <h3 className="font-bold text-sm text-slate-700 mb-3 flex items-center gap-1.5">
                      <Building2 className="w-4 h-4 text-blue-500" />
                      ארגונים ({selectedUser.org_memberships.length})
                    </h3>
                    <div className="space-y-2">
                      {selectedUser.org_memberships.map((om, i) => {
                        const st = STATUS_LABELS[om.billing_status] || STATUS_LABELS.none;
                        return (
                          <div key={i} className="border border-blue-100 rounded-lg p-3 bg-blue-50/30">
                            <div className="flex justify-between items-center">
                              <span className="text-sm font-medium text-slate-800">{om.org_name || om.org_id?.slice(0, 8)}</span>
                              <span className={`text-[10px] px-2 py-0.5 rounded-full ${st.color}`}>{st.label}</span>
                            </div>
                            <div className="text-xs text-slate-500 mt-1">
                              תפקיד: <span className="font-medium">{tRole(om.role)}</span>
                              {om.trial_end_at && ` | סיום ניסיון: ${new Date(om.trial_end_at).toLocaleDateString('he-IL')}`}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}

                <Card className="p-4">
                  <button
                    onClick={() => setProjectsOpen(!projectsOpen)}
                    className="w-full flex items-center justify-between text-sm font-bold text-slate-700 hover:text-slate-900"
                  >
                    <span className="flex items-center gap-1.5">
                      <HardHat className="w-4 h-4 text-amber-500" />
                      פרויקטים ({selectedUser.project_memberships?.length || 0})
                    </span>
                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${projectsOpen ? 'rotate-180' : ''}`} />
                  </button>
                  {projectsOpen && (
                    <div className="mt-3 space-y-2">
                      {(selectedUser.project_memberships?.length || 0) === 0 ? (
                        <div className="text-center py-4 text-sm text-slate-400">
                          המשתמש לא משויך לאף פרויקט
                        </div>
                      ) : selectedUser.project_memberships.map((pm, i) => {
                        const pmRoleStyle = ROLE_STYLE[pm.role] || ROLE_STYLE.default;
                        return (
                          <div key={i} className="border rounded-lg p-3 text-sm hover:bg-slate-50 transition-colors">
                            <div className="flex justify-between items-center">
                              <div className="min-w-0 flex-1">
                                <span className="font-medium text-slate-800">{pm.project_name || pm.project_id?.slice(0, 8)}</span>
                                {pm.project_code && <span className="text-xs text-slate-400 mr-2">({pm.project_code})</span>}
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${pmRoleStyle.badge}`}>
                                  {tRole(pm.role)}
                                  {pm.role === 'management_team' && pm.sub_role && ` · ${tSubRole(pm.sub_role)}`}
                                </span>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openMemberDrawer(selectedUser, pm);
                                  }}
                                  className="p-1 rounded hover:bg-slate-200"
                                  title="ניהול חבר צוות"
                                >
                                  <MoreVertical className="w-3.5 h-3.5 text-slate-400" />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setRoleEdit({
                                      userId: selectedUser.id,
                                      projectId: pm.project_id,
                                      projectName: pm.project_name,
                                      currentRole: pm.role,
                                      newRole: pm.role,
                                      isOrgOwner: pm.is_org_owner || false,
                                      orgRole: pm.org_role || null,
                                    });
                                    setRoleNote('');
                                  }}
                                  className="text-xs text-amber-600 hover:text-amber-700 font-medium"
                                >
                                  שנה תפקיד
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </Card>
              </div>
            )}
          </div>
          <div className="flex-1" onClick={() => setSelectedUser(null)} />
        </div>
      )}

      {roleEdit && ReactDOM.createPortal(
        <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4" onClick={() => setRoleEdit(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6" dir="rtl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-slate-800">שינוי תפקיד בפרויקט</h3>
              <button onClick={() => setRoleEdit(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="text-sm text-slate-600 mb-4">
              פרויקט: <span className="font-medium">{roleEdit.projectName}</span>
              <br />
              תפקיד נוכחי: <span className="font-medium">{tRole(roleEdit.currentRole)}</span>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-slate-700">תפקיד חדש *</label>
                <select
                  value={(roleEdit.isOrgOwner || ['org_admin', 'billing_admin'].includes(roleEdit.orgRole)) && roleEdit.newRole === 'contractor' ? roleEdit.currentRole : roleEdit.newRole}
                  onChange={(e) => setRoleEdit({ ...roleEdit, newRole: e.target.value })}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                >
                  <option value="project_manager">{tRole('project_manager')}</option>
                  <option value="management_team">{tRole('management_team')}</option>
                  <option value="contractor" disabled={roleEdit.isOrgOwner || ['org_admin', 'billing_admin'].includes(roleEdit.orgRole)}>{tRole('contractor')}{(roleEdit.isOrgOwner || ['org_admin', 'billing_admin'].includes(roleEdit.orgRole)) ? ' (תפקיד ניהולי — לא זמין)' : ''}</option>
                  <option value="viewer">{tRole('viewer')}</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">סיבה (חובה) *</label>
                <textarea
                  value={roleNote}
                  onChange={(e) => setRoleNote(e.target.value)}
                  placeholder="למשל: שדרוג לאחר הכשרה, סיום עבודה..."
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  rows={2}
                />
              </div>
              <Button
                onClick={handleRoleChange}
                disabled={roleSubmitting || roleEdit.newRole === roleEdit.currentRole || !roleNote.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {roleSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'שמור שינוי'}
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {phoneModal && ReactDOM.createPortal(
        <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4" onClick={() => setPhoneModal(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6" dir="rtl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-slate-800">החלפת מספר טלפון</h3>
              <button onClick={() => setPhoneModal(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="text-sm text-slate-600 mb-4">
              משתמש: <span className="font-medium">{phoneModal.name}</span>
              <br />
              מספר נוכחי: <bdi className="font-mono" dir="ltr">{phoneModal.phone_e164 || '-'}</bdi>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-slate-700">מספר חדש *</label>
                <input
                  type="tel"
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="050-1234567"
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">סיבה / הערה *</label>
                <textarea
                  value={phoneNote}
                  onChange={(e) => setPhoneNote(e.target.value)}
                  placeholder="למשל: המשתמש החליף מספר, שחזור גישה..."
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  rows={2}
                />
              </div>
              <Button
                onClick={handlePhoneChange}
                disabled={phoneSubmitting || !newPhone.trim() || !phoneNote.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {phoneSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'עדכן מספר'}
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {passwordModal && ReactDOM.createPortal(
        <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4" onClick={() => setPasswordModal(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6" dir="rtl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-slate-800">איפוס סיסמה</h3>
              <button onClick={() => setPasswordModal(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="text-sm text-slate-600 mb-4">
              משתמש: <span className="font-medium">{passwordModal.name}</span>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-slate-700">סיסמה חדשה *</label>
                <input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="לפחות 8 תווים"
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">סיבה / הערה *</label>
                <textarea
                  value={passwordNote}
                  onChange={(e) => setPasswordNote(e.target.value)}
                  placeholder="למשל: שכח סיסמה, גישה חירום..."
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  rows={2}
                />
              </div>
              <Button
                onClick={handleResetPassword}
                disabled={passwordSubmitting || !newPassword.trim() || !passwordNote.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {passwordSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'איפוס סיסמה'}
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {stepup && ReactDOM.createPortal(
        <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6" dir="rtl">
            <h3 className="font-bold text-slate-800 mb-2">אימות Step-Up נדרש</h3>
            <p className="text-sm text-slate-600 mb-4">קוד נשלח ל-{stepup.maskedEmail}</p>
            <input
              type="text"
              value={stepupCode}
              onChange={(e) => setStepupCode(e.target.value)}
              placeholder="הכנס קוד 6 ספרות"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500 mb-3"
              dir="ltr"
              autoFocus
            />
            <div className="flex gap-2">
              <Button onClick={handleStepupVerify} disabled={stepupLoading || !stepupCode.trim()} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white">
                {stepupLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'אמת'}
              </Button>
              <Button variant="outline" onClick={() => { setStepup(null); setStepupCode(''); }} className="flex-1">
                ביטול
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      <UserDrawer
        open={!!drawerMember}
        onClose={() => { setDrawerMember(null); setDrawerProjectId(null); }}
        member={drawerMember}
        projectId={drawerProjectId}
        currentUserRole="project_manager"
        currentUserId={user?.id}
        currentUserPlatformRole={user?.platform_role}
        onRefresh={() => { if (selectedUser) openDetail(selectedUser.id); loadUsers(); }}
      />
    </div>
  );
};

export default AdminUsersPage;
