import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { adminUserService, stepupService, isStepupError } from '../services/api';
import { toast } from 'sonner';
import {
  ArrowRight, Search, User, Phone, Building2, Calendar,
  Loader2, ChevronLeft, ChevronRight, ChevronDown, X, Shield, Edit3, KeyRound, MoreVertical, Settings
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

const AdminUsersPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const goBack = () => {
    if (location.state?.from) navigate(location.state.from);
    else navigate('/projects');
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

  const handleSearch = (e) => {
    e.preventDefault();
    setSkip(0);
    setQuery(searchInput);
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

  if (!user || user.platform_role !== 'super_admin') {
    return <div className="p-8 text-center text-slate-500">אין גישה</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="bg-white border-b px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={goBack} className="text-slate-500 hover:text-slate-700">
              <ArrowRight className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <Shield className="w-5 h-5 text-amber-500" />
              ניהול משתמשים
            </h1>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate('/admin/billing', { state: { from: '/admin/users' } })}>
              חיוב וארגונים
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-4">
        <form onSubmit={handleSearch} className="mb-4 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="חיפוש לפי שם, טלפון, אימייל או ID..."
              className="w-full pr-10 pl-4 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
            />
          </div>
          <Button type="submit" size="sm" className="bg-amber-500 hover:bg-amber-600 text-white">
            חפש
          </Button>
        </form>

        <div className="text-xs text-slate-500 mb-2">{total} משתמשים</div>

        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
          </div>
        ) : (
          <>
            <div className="bg-white rounded-lg border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 text-right font-medium">שם</th>
                    <th className="px-3 py-2 text-right font-medium">טלפון</th>
                    <th className="px-3 py-2 text-right font-medium">אימייל</th>
                    <th className="px-3 py-2 text-right font-medium">תפקיד</th>
                    <th className="px-3 py-2 text-right font-medium">מנוי</th>
                    <th className="px-3 py-2 text-right font-medium">פרויקטים</th>
                    <th className="px-3 py-2 text-right font-medium">נוצר</th>
                    <th className="px-3 py-2 text-right font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => {
                    const st = STATUS_LABELS[u.billing_status] || STATUS_LABELS.none;
                    return (
                      <tr key={u.id} className="border-t hover:bg-slate-50 cursor-pointer" onClick={() => openDetail(u.id)}>
                        <td className="px-3 py-2 font-medium text-slate-800">
                          <div className="flex items-center gap-1.5">
                            <User className="w-3.5 h-3.5 text-slate-400" />
                            {u.name}
                            {u.platform_role === 'super_admin' && (
                              <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-bold">SA</span>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-slate-600 text-xs"><bdi className="font-mono" dir="ltr">{u.phone_e164 || '-'}</bdi></td>
                        <td className="px-3 py-2 text-slate-600 text-xs">{u.email || '-'}</td>
                        <td className="px-3 py-2">
                          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                            {tRole(u.role)}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={`text-xs px-2 py-0.5 rounded ${st.color}`}>{st.label}</span>
                        </td>
                        <td className="px-3 py-2 text-slate-600">{u.project_count || 0}</td>
                        <td className="px-3 py-2 text-slate-500 text-xs">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString('he-IL') : '-'}
                        </td>
                        <td className="px-3 py-2">
                          <button
                            onClick={(e) => { e.stopPropagation(); setPhoneModal(u); setNewPhone(''); setPhoneNote(''); }}
                            className="text-slate-400 hover:text-amber-600"
                            title="החלפת טלפון"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {total > LIMIT && (
              <div className="flex items-center justify-center gap-4 mt-4">
                <button
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - LIMIT))}
                  className="p-1 rounded hover:bg-slate-200 disabled:opacity-30"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
                <span className="text-sm text-slate-600">
                  {skip + 1}–{Math.min(skip + LIMIT, total)} מתוך {total}
                </span>
                <button
                  disabled={skip + LIMIT >= total}
                  onClick={() => setSkip(skip + LIMIT)}
                  className="p-1 rounded hover:bg-slate-200 disabled:opacity-30"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* User Detail Drawer */}
      {(selectedUser || detailLoading) && (
        <div className="fixed inset-0 bg-black/40 z-50 flex justify-start">
          <div className="bg-white w-full max-w-lg h-full overflow-y-auto shadow-2xl" dir="rtl">
            <div className="sticky top-0 bg-white border-b px-4 py-3 flex items-center justify-between z-10">
              <h2 className="font-bold text-slate-800">פרטי משתמש</h2>
              <button onClick={() => setSelectedUser(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            {detailLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
              </div>
            ) : selectedUser && (
              <div className="p-4 space-y-4">
                <Card className="p-4 space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-lg font-bold flex-shrink-0">
                      {(selectedUser.name || '?')[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-base font-bold text-slate-900 truncate">{selectedUser.name}</div>
                      <div className="text-xs text-slate-500 font-mono">{selectedUser.id?.slice(0, 12)}...</div>
                    </div>
                    {selectedUser.platform_role === 'super_admin' && (
                      <span className="text-[10px] bg-red-100 text-red-600 px-2 py-1 rounded-full font-bold flex-shrink-0">Super Admin</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm border-t pt-3">
                    <div className="flex items-center gap-1">
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      <bdi className="font-mono" dir="ltr">{selectedUser.phone_e164 || '-'}</bdi>
                      <button
                        onClick={() => { setPhoneModal(selectedUser); setNewPhone(''); setPhoneNote(''); }}
                        className="text-amber-600 hover:text-amber-700 mr-1"
                        title="החלפת טלפון"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div><span className="text-slate-500">אימייל:</span> {selectedUser.email || '-'}</div>
                    <div className="col-span-2">
                      <button
                        onClick={() => { setPasswordModal(selectedUser); setNewPassword(''); setPasswordNote(''); }}
                        className="flex items-center gap-1.5 text-xs text-amber-600 hover:text-amber-700 font-medium"
                        title="איפוס סיסמה"
                      >
                        <KeyRound className="w-3.5 h-3.5" />
                        איפוס סיסמה
                      </button>
                    </div>
                    <div><span className="text-slate-500">סטטוס:</span> {selectedUser.status || '-'}</div>
                    <div><span className="text-slate-500">חברה:</span> {selectedUser.company || '-'}</div>
                    <div>
                      <Calendar className="w-3.5 h-3.5 inline text-slate-400 ml-1" />
                      {selectedUser.created_at ? new Date(selectedUser.created_at).toLocaleDateString('he-IL') : '-'}
                    </div>
                  </div>
                </Card>

                {selectedUser.id === user?.id && (
                  <Button
                    variant="outline"
                    className="w-full justify-between text-sm"
                    onClick={() => navigate('/settings/account')}
                  >
                    הגדרות חשבון
                    <Settings className="w-4 h-4" />
                  </Button>
                )}

                <Card className="p-4">
                  <label className="text-xs font-semibold text-slate-500 block mb-2">שפת הודעות WhatsApp</label>
                  <select
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
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
                    <h3 className="font-bold text-sm text-slate-700 mb-2 flex items-center gap-1.5">
                      <Building2 className="w-4 h-4 text-amber-500" />
                      ארגונים
                    </h3>
                    {selectedUser.org_memberships.map((om, i) => {
                      const st = STATUS_LABELS[om.billing_status] || STATUS_LABELS.none;
                      return (
                        <div key={i} className="border rounded p-2 mb-2 text-sm">
                          <div className="flex justify-between items-center">
                            <span className="font-medium">{om.org_name || om.org_id?.slice(0, 8)}</span>
                            <span className={`text-xs px-2 py-0.5 rounded ${st.color}`}>{st.label}</span>
                          </div>
                          <div className="text-xs text-slate-500 mt-1">
                            תפקיד: {tRole(om.role)}
                            {om.trial_end_at && ` | סיום ניסיון: ${new Date(om.trial_end_at).toLocaleDateString('he-IL')}`}
                          </div>
                        </div>
                      );
                    })}
                  </Card>
                )}

                <Card className="p-4">
                    <button
                      onClick={() => setProjectsOpen(!projectsOpen)}
                      className="w-full flex items-center justify-between text-sm font-bold text-slate-700 hover:text-slate-900"
                    >
                      <span className="flex items-center gap-1.5">
                        <Building2 className="w-4 h-4 text-amber-500" />
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
                        ) : selectedUser.project_memberships.map((pm, i) => (
                          <div key={i} className="border rounded p-3 text-sm">
                            <div className="flex justify-between items-center">
                              <div>
                                <span className="font-medium">{pm.project_name || pm.project_id?.slice(0, 8)}</span>
                                {pm.project_code && <span className="text-xs text-slate-500 mr-2">({pm.project_code})</span>}
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
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
                        ))}
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
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-amber-500" />
                איפוס סיסמה
              </h3>
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
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="לפחות 8 תווים, אות + מספר"
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">סיבה / הערה *</label>
                <textarea
                  value={passwordNote}
                  onChange={(e) => setPasswordNote(e.target.value)}
                  placeholder="למשל: המשתמש שכח סיסמה, שחזור גישה..."
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  rows={2}
                />
              </div>
              <Button
                onClick={handleResetPassword}
                disabled={passwordSubmitting || !newPassword.trim() || !passwordNote.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {passwordSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'אפס סיסמה'}
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {stepup && ReactDOM.createPortal(
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
        </div>,
        document.body
      )}

      <UserDrawer
        open={!!drawerMember}
        onClose={() => { setDrawerMember(null); setDrawerProjectId(null); }}
        member={drawerMember}
        projectId={drawerProjectId}
        currentUserRole="project_manager"
        isCurrentUserOrgOwner={true}
        currentUserId={user?.id}
        currentUserPlatformRole={user?.platform_role}
        onRefresh={() => {
          if (selectedUser) openDetail(selectedUser.id);
          loadUsers();
        }}
      />
    </div>
  );
};

export default AdminUsersPage;
