import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerDescription, DrawerFooter, DrawerClose
} from './ui/drawer';
import { Button } from './ui/button';
import { tRole, tSubRole, tTrade } from '../i18n';
import { projectService, adminUserService, membershipService, tradeService, projectCompanyService } from '../services/api';
import { toast } from 'sonner';
import {
  Phone, Shield, Crown, UserMinus, ArrowRightLeft, Loader2, ChevronDown, AlertTriangle,
  Briefcase, Users, HardHat, Eye, Settings, Edit3, Plus
} from 'lucide-react';

const ALL_PROJECT_ROLES = [
  'project_manager',
  'management_team',
  'contractor',
  'viewer',
];

const ROLE_ICONS = {
  project_manager: Briefcase,
  management_team: Users,
  contractor: HardHat,
  viewer: Eye,
};

const formatIsraeliPhone = (phone) => {
  if (!phone) return '';
  const p = String(phone);
  if (p.startsWith('+972') && p.length === 13) {
    const d = p.slice(4);
    return `0${d.slice(0, 2)}-${d.slice(2, 5)}-${d.slice(5)}`;
  }
  return p;
};

export default function UserDrawer({ open, onClose, member, projectId, currentUserRole, isCurrentUserOrgOwner, currentUserId, onRefresh, currentUserPlatformRole, companies = [], trades = [], onRefreshCompanies }) {
  const navigate = useNavigate();
  const [roleChanging, setRoleChanging] = useState(false);
  const [selectedRole, setSelectedRole] = useState('');
  const [showRoleSelect, setShowRoleSelect] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [removingOrg, setRemovingOrg] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [confirmRemoveOrg, setConfirmRemoveOrg] = useState(false);
  const [waLang, setWaLang] = useState(member?.preferred_language || 'he');
  const [waLangSaving, setWaLangSaving] = useState(false);
  const [showContractorEdit, setShowContractorEdit] = useState(false);
  const [editCompanyId, setEditCompanyId] = useState('');
  const [editTradeKey, setEditTradeKey] = useState('');
  const [contractorSaving, setContractorSaving] = useState(false);
  const [localTrades, setLocalTrades] = useState([]);
  const [showNewCompany, setShowNewCompany] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState('');
  const [newCompanyTrade, setNewCompanyTrade] = useState('');
  const [creatingCompany, setCreatingCompany] = useState(false);
  const tradeSelectRef = useRef(null);
  const focusTradeTimerRef = useRef(null);
  const isSA = currentUserPlatformRole === 'super_admin';

  useEffect(() => {
    return () => { if (focusTradeTimerRef.current) clearTimeout(focusTradeTimerRef.current); };
  }, []);

  useEffect(() => {
    if (open && member?.role === 'contractor' && trades.length === 0 && projectId) {
      tradeService.listForProject(projectId)
        .then(data => setLocalTrades((data.trades || []).map(t => ({ value: t.key, label: t.label_he }))))
        .catch(() => {});
    }
  }, [open, member?.role, trades.length, projectId]);

  const tradeOptions = trades.length > 0 ? trades : localTrades;
  const companyOptions = companies.map(c => ({ value: c.id, label: c.name }));

  if (!member) return null;

  const isSelf = member.user_id === currentUserId;
  const isTargetOrgOwner = member.is_org_owner;
  const isPMorOwner = currentUserRole === 'project_manager' || isCurrentUserOrgOwner;
  const canManageProject = isPMorOwner && !isTargetOrgOwner && !isSelf;
  const canManageSelfRole = isPMorOwner && isSelf;
  const hasOrgMembership = !!member.org_role;
  const canRemoveFromOrg = isCurrentUserOrgOwner && !isTargetOrgOwner && !isSelf && hasOrgMembership;
  const canTransferOwnership = isCurrentUserOrgOwner && !isSelf && hasOrgMembership;

  const availableRoles = ALL_PROJECT_ROLES.filter(r => r !== member.role);
  const isContractorDisabled = isTargetOrgOwner || ['org_admin', 'billing_admin'].includes(member.org_role);

  const handleChangeRole = async () => {
    if (!selectedRole || selectedRole === member.role) return;
    setRoleChanging(true);
    try {
      await projectService.changeMemberRole(projectId, member.user_id, selectedRole);
      toast.success(`התפקיד שונה ל${tRole(selectedRole)}`);
      setShowRoleSelect(false);
      setSelectedRole('');
      onRefresh();
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 && detail?.code === 'ROLE_CONFLICT') {
        toast.error('לא ניתן לשלב תפקיד קבלן עם תפקיד ניהולי בארגון');
      } else {
        toast.error(typeof detail === 'object' ? detail.message : (detail || 'שגיאה בשינוי תפקיד'));
      }
    } finally {
      setRoleChanging(false);
    }
  };

  const handleRemoveFromProject = async () => {
    setRemoving(true);
    try {
      await projectService.removeMember(projectId, member.user_id);
      toast.success(`${member.user_name || 'המשתמש'} הוסר מהפרויקט`);
      setConfirmRemove(false);
      onRefresh();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בהסרה מהפרויקט');
    } finally {
      setRemoving(false);
    }
  };

  const handleRemoveFromOrg = async () => {
    setRemovingOrg(true);
    try {
      const result = await projectService.removeOrgMember(member.user_id);
      const count = result.removed_from_projects || 0;
      toast.success(`${member.user_name || 'המשתמש'} הוסר מהארגון${count > 0 ? ` ומ-${count} פרויקטים` : ''}`);
      setConfirmRemoveOrg(false);
      onRefresh();
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'שגיאה בהסרה מהארגון'));
    } finally {
      setRemovingOrg(false);
    }
  };

  const handleTransferOwnership = () => {
    onClose();
    navigate('/org/transfer/settings', { state: { prefillPhone: member.user_phone } });
  };

  const handleAddCompanyInDrawer = async () => {
    if (!newCompanyName.trim()) return;
    if (!newCompanyTrade) {
      toast.error('יש לבחור תחום');
      return;
    }
    setCreatingCompany(true);
    try {
      const result = await projectCompanyService.create(projectId, { name: newCompanyName.trim(), trade: newCompanyTrade });
      toast.success('חברה נוספה בהצלחה');
      setNewCompanyName('');
      setNewCompanyTrade('');
      setShowNewCompany(false);
      if (onRefreshCompanies) await onRefreshCompanies();
      if (result?.id) {
        setEditCompanyId(result.id);
        if (!editTradeKey) setEditTradeKey(newCompanyTrade);
      }
      if (focusTradeTimerRef.current) clearTimeout(focusTradeTimerRef.current);
      focusTradeTimerRef.current = setTimeout(() => {
        if (tradeSelectRef.current) {
          tradeSelectRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          tradeSelectRef.current.focus({ preventScroll: true });
        }
      }, 250);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת חברה');
    } finally {
      setCreatingCompany(false);
    }
  };

  const handleSaveContractorProfile = async () => {
    if (!editCompanyId || !editTradeKey) {
      toast.error('יש לבחור חברה ותחום');
      return;
    }
    setContractorSaving(true);
    try {
      await projectService.updateContractorProfile(projectId, member.user_id, {
        company_id: editCompanyId,
        trade_key: editTradeKey,
      });
      toast.success('פרופיל קבלן עודכן בהצלחה');
      setShowContractorEdit(false);
      onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'שגיאה בעדכון פרופיל קבלן'));
    } finally {
      setContractorSaving(false);
    }
  };

  const handleDrawerClose = () => {
    setShowRoleSelect(false);
    setSelectedRole('');
    setConfirmRemove(false);
    setConfirmRemoveOrg(false);
    setShowContractorEdit(false);
    setShowNewCompany(false);
    setNewCompanyName('');
    setNewCompanyTrade('');
    onClose();
  };

  const subRoleLabel = member.sub_role ? tSubRole(member.sub_role) : null;

  return (
    <Drawer open={open} onOpenChange={(o) => { if (!o) handleDrawerClose(); }}>
      <DrawerContent className="max-h-[85vh]">
        <DrawerHeader className="text-right">
          <DrawerTitle className="text-lg font-bold text-slate-800">
            {member.user_name || 'משתמש'}
          </DrawerTitle>
          <DrawerDescription className="text-sm text-slate-500">
            כרטיס חבר צוות
          </DrawerDescription>
        </DrawerHeader>

        <div className="px-4 pb-4 space-y-4 overflow-y-auto" dir="rtl">
          <div className="space-y-3">
            {member.user_phone && (
              <a href={`tel:${member.user_phone}`} className="flex items-center gap-2 text-sm text-slate-600 hover:text-amber-600 transition-colors">
                <Phone className="w-4 h-4 text-slate-400 shrink-0" />
                <bdi className="font-mono" dir="ltr">{formatIsraeliPhone(member.user_phone)}</bdi>
              </a>
            )}

            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Shield className="w-4 h-4 text-slate-400 shrink-0" />
              <span>תפקיד בפרויקט: <span className="font-medium text-slate-800">{tRole(member.role)}</span></span>
              {member.role === 'management_team' && subRoleLabel && (
                <span className="text-xs text-slate-500">· {subRoleLabel}</span>
              )}
            </div>

            {hasOrgMembership && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Crown className="w-4 h-4 text-amber-500 shrink-0" />
                <span>
                  {isTargetOrgOwner ? (
                    <span className="font-medium text-amber-700">בעלים של הארגון</span>
                  ) : (
                    <span>חבר בארגון</span>
                  )}
                </span>
              </div>
            )}

            {member.role === 'contractor' && (
              <div className="space-y-2">
                {member.company_id && member.contractor_trade_key ? (
                  <div className="flex items-center gap-2 text-sm text-slate-600">
                    <Briefcase className="w-4 h-4 text-slate-400 shrink-0" />
                    <span>
                      {member.company_name || member.company_id}
                      {' · '}
                      {tTrade(member.contractor_trade_key)}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium px-2 py-1 rounded-full bg-red-100 text-red-700">
                      לא משויך לחברה/תחום
                    </span>
                  </div>
                )}
                {isPMorOwner && !showContractorEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs text-amber-700 border-amber-200 hover:bg-amber-50"
                    onClick={() => {
                      setEditCompanyId(member.company_id || '');
                      setEditTradeKey(member.contractor_trade_key || '');
                      setShowContractorEdit(true);
                    }}
                  >
                    <Edit3 className="w-3.5 h-3.5 ml-1" />
                    {member.company_id && member.contractor_trade_key ? 'ערוך שיוך' : 'שייך עכשיו'}
                  </Button>
                )}
                {showContractorEdit && (
                  <div className="space-y-3 p-3 border rounded-lg bg-slate-50">
                    <div className="space-y-1">
                      <label className="block text-xs font-medium text-slate-600">חברה *</label>
                      {companyOptions.length === 0 && !showNewCompany ? (
                        <p className="text-xs text-slate-400 py-1">אין חברות בפרויקט</p>
                      ) : (
                        <select
                          className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
                          value={editCompanyId}
                          onChange={e => setEditCompanyId(e.target.value)}
                        >
                          <option value="">בחר חברה...</option>
                          {companyOptions.map(c => (
                            <option key={c.value} value={c.value}>{c.label}</option>
                          ))}
                        </select>
                      )}
                      {!showNewCompany && (
                        <button
                          type="button"
                          onClick={() => setShowNewCompany(true)}
                          className="w-full mt-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded-lg border border-dashed border-amber-300 text-amber-700 hover:bg-amber-50 active:bg-amber-100 transition-colors"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          הוסף חברה חדשה
                        </button>
                      )}
                      {showNewCompany && (
                        <div className="mt-1 p-2.5 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
                          <label className="block text-xs font-medium text-slate-600">שם חברה *</label>
                          <input
                            type="text"
                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
                            value={newCompanyName}
                            onChange={e => setNewCompanyName(e.target.value)}
                            placeholder="למשל: חברת חשמל"
                          />
                          <label className="block text-xs font-medium text-slate-600">תחום *</label>
                          <select
                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
                            value={newCompanyTrade}
                            onChange={e => setNewCompanyTrade(e.target.value)}
                          >
                            <option value="">בחר תחום...</option>
                            {tradeOptions.map(t => (
                              <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                          </select>
                          <div className="flex gap-2">
                            <Button size="sm" onClick={handleAddCompanyInDrawer} disabled={creatingCompany || !newCompanyName.trim() || !newCompanyTrade} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-xs">
                              {creatingCompany ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'שמור'}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => { setShowNewCompany(false); setNewCompanyName(''); setNewCompanyTrade(''); }} className="flex-1 text-xs">
                              ביטול
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="space-y-1">
                      <label className="block text-xs font-medium text-slate-600">תחום *</label>
                      <select
                        ref={tradeSelectRef}
                        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
                        value={editTradeKey}
                        onChange={e => setEditTradeKey(e.target.value)}
                      >
                        <option value="">בחר תחום...</option>
                        {tradeOptions.map(t => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveContractorProfile} disabled={contractorSaving || !editCompanyId || !editTradeKey} className="flex-1">
                        {contractorSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'שמור'}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setShowContractorEdit(false)}>
                        ביטול
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {isSelf && (
            <div className="border-t pt-3">
              <Button
                variant="outline"
                className="w-full justify-between text-sm"
                onClick={() => { navigate('/settings/account'); onClose(); }}
              >
                הגדרות חשבון
                <Settings className="w-4 h-4" />
              </Button>
            </div>
          )}

          {(isSA || isPMorOwner) && (
            <div className="border-t pt-3">
              <label className="text-xs font-semibold text-slate-500 block mb-2">שפת הודעות WhatsApp</label>
              <select
                className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
                value={waLang}
                disabled={waLangSaving}
                onChange={async (e) => {
                  const newLang = e.target.value;
                  setWaLangSaving(true);
                  try {
                    if (isSA) {
                      await adminUserService.updatePreferredLanguage(member.user_id, newLang);
                    } else {
                      await membershipService.updatePreferredLanguage(projectId, member.user_id, newLang);
                    }
                    setWaLang(newLang);
                    toast.success('שפת WhatsApp עודכנה');
                  } catch (err) {
                    toast.error(err.response?.data?.detail || 'שגיאה בעדכון שפה');
                  } finally {
                    setWaLangSaving(false);
                  }
                }}
              >
                <option value="he">עברית</option>
                <option value="en">English</option>
                <option value="ar">العربية</option>
                <option value="zh">中文 (fallback to en)</option>
              </select>
            </div>
          )}

          {(canManageProject || canManageSelfRole) && (
            <div className="border-t pt-3 space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">פעולות</p>

              {!showRoleSelect ? (
                <Button variant="outline" className="w-full justify-between text-sm" onClick={() => { setShowRoleSelect(true); setSelectedRole(''); }}>
                  שנה תפקיד בפרויקט
                  <ChevronDown className="w-4 h-4" />
                </Button>
              ) : (
                <div className="space-y-3 p-3 border rounded-lg bg-slate-50">
                  <label className="text-xs font-medium text-slate-600">בחר תפקיד חדש:</label>
                  <div className="space-y-1.5">
                    {availableRoles.map(role => {
                      const Icon = ROLE_ICONS[role] || Shield;
                      const isSelected = selectedRole === role;
                      const isDisabled = role === 'contractor' && isContractorDisabled;
                      return (
                        <button
                          key={role}
                          type="button"
                          onClick={() => !isDisabled && setSelectedRole(role)}
                          disabled={isDisabled}
                          title={isDisabled ? 'לא ניתן לשלב תפקיד קבלן עם תפקיד ניהולי בארגון' : undefined}
                          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border text-sm transition-all text-right ${
                            isDisabled
                              ? 'border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed opacity-60'
                              : isSelected
                                ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-200 text-amber-900 font-medium'
                                : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-700'
                          }`}
                        >
                          <Icon className={`w-4 h-4 shrink-0 ${isDisabled ? 'text-slate-300' : isSelected ? 'text-amber-600' : 'text-slate-400'}`} />
                          <span className="flex-1">{tRole(role)}{isDisabled ? ' (תפקיד ניהולי — לא זמין)' : ''}</span>
                          {isSelected && !isDisabled && (
                            <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center shrink-0">
                              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                  <div className="flex gap-2 pt-1">
                    <Button size="sm" onClick={handleChangeRole} disabled={roleChanging || !selectedRole} className="flex-1">
                      {roleChanging ? <Loader2 className="w-4 h-4 animate-spin" /> : 'שמור'}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => { setShowRoleSelect(false); setSelectedRole(''); }}>
                      ביטול
                    </Button>
                  </div>
                </div>
              )}

              {canManageProject && (
                <>
                  {!confirmRemove ? (
                    <Button variant="outline" className="w-full justify-start text-sm text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200" onClick={() => setConfirmRemove(true)}>
                      <UserMinus className="w-4 h-4 ml-2" />
                      הסר מהפרויקט
                    </Button>
                  ) : (
                    <div className="p-3 border border-red-200 rounded-lg bg-red-50 space-y-2">
                      <p className="text-sm text-red-700 flex items-center gap-1">
                        <AlertTriangle className="w-4 h-4" />
                        להסיר את {member.user_name || 'המשתמש'} מהפרויקט?
                      </p>
                      <div className="flex gap-2">
                        <Button size="sm" variant="destructive" onClick={handleRemoveFromProject} disabled={removing} className="flex-1">
                          {removing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'כן, הסר'}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setConfirmRemove(false)}>ביטול</Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {canRemoveFromOrg && (
            <div className="border-t pt-3 space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">פעולות ארגון</p>
              {!confirmRemoveOrg ? (
                <Button variant="outline" className="w-full justify-start text-sm text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200" onClick={() => setConfirmRemoveOrg(true)}>
                  <UserMinus className="w-4 h-4 ml-2" />
                  הסר מהארגון (וכל הפרויקטים)
                </Button>
              ) : (
                <div className="p-3 border border-red-200 rounded-lg bg-red-50 space-y-2">
                  <p className="text-sm text-red-700 flex items-center gap-1">
                    <AlertTriangle className="w-4 h-4" />
                    להסיר את {member.user_name || 'המשתמש'} מהארגון ומכל הפרויקטים?
                  </p>
                  <div className="flex gap-2">
                    <Button size="sm" variant="destructive" onClick={handleRemoveFromOrg} disabled={removingOrg} className="flex-1">
                      {removingOrg ? <Loader2 className="w-4 h-4 animate-spin" /> : 'כן, הסר'}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmRemoveOrg(false)}>ביטול</Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {canTransferOwnership && (
            <div className="border-t pt-3">
              <Button variant="outline" className="w-full justify-start text-sm text-amber-700 hover:text-amber-800 hover:bg-amber-50 border-amber-200" onClick={handleTransferOwnership}>
                <ArrowRightLeft className="w-4 h-4 ml-2" />
                העבר בעלות לארגון למשתמש זה
              </Button>
            </div>
          )}
        </div>

        <DrawerFooter>
          <DrawerClose asChild>
            <Button variant="outline" onClick={handleDrawerClose}>סגור</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
