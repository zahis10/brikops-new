import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useIdentity } from '../contexts/IdentityContext';
import { authService, userService, deletionService, billingService } from '../services/api';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import {
  Mail, Lock, Eye, EyeOff, Loader2, AlertCircle, ArrowRight, Phone, Building2, Briefcase, MessageCircle, Bell, Accessibility, FileText, Trash2, AlertTriangle
} from 'lucide-react';
import PhoneChangeModal from '../components/PhoneChangeModal';
import { tRole, tTrade, t, setLanguage } from '../i18n';
import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog';

const PasswordInput = ({ id, value, onChange, placeholder, show, onToggle, error }) => (
  <div className="space-y-1">
    <div className="relative">
      <input
        id={id}
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={`w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${error ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
      />
      <button
        type="button" onClick={onToggle}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 touch-manipulation"
        aria-label={show ? 'הסתר סיסמה' : 'הצג סיסמה'}
        aria-pressed={show}
      >
        {show ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
      </button>
    </div>
    {error && (
      <div className="flex items-center gap-1 text-sm text-red-500">
        <AlertCircle className="w-4 h-4 flex-shrink-0" />
        <span>{error}</span>
      </div>
    )}
  </div>
);

const DeleteAccountSection = ({ user }) => {
  const navigate = useNavigate();
  const { refreshUser, forceUserStatus, replaceToken } = useAuth();
  const [isOrgOwner, setIsOrgOwner] = useState(false);
  const hasOrg = !!user?.organization;

  const [wizardMode, setWizardMode] = useState(null);
  const [step, setStep] = useState(0);
  const [authMethod, setAuthMethod] = useState(null);
  const [password, setPassword] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [typedOrgName, setTypedOrgName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [otpDebugCode, setOtpDebugCode] = useState('');

  useEffect(() => {
    if (hasOrg) {
      billingService.me().then(b => setIsOrgOwner(!!b?.is_owner)).catch(() => {
        setIsOrgOwner(user?.organization?.owner_user_id === user?.id);
      });
    }
  }, [hasOrg, user?.organization?.owner_user_id, user?.id]);

  const resetWizard = () => {
    setWizardMode(null);
    setStep(0);
    setAuthMethod(null);
    setPassword('');
    setOtpCode('');
    setShowPw(false);
    setTypedOrgName('');
    setLoading(false);
    setError('');
    setOtpDebugCode('');
  };

  const handleStartDeletion = (mode) => {
    if (mode === 'account' && isOrgOwner) {
      setWizardMode('owner_blocked');
      return;
    }
    setWizardMode(mode);
    setStep(1);
    setError('');
  };

  const handleProceedToAuth = async () => {
    setLoading(true);
    setError('');
    try {
      const resp = await deletionService.requestOtp();
      setAuthMethod(resp.auth_method);
      if (resp.otp_debug_code) setOtpDebugCode(resp.otp_debug_code);
      setStep(2);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'object' ? detail.message : (detail || 'שגיאה בשליחת קוד אימות'));
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmDeletion = async () => {
    setError('');

    if (authMethod === 'password' && !password.trim()) {
      setError('נא להזין סיסמה');
      return;
    }
    if (authMethod !== 'password' && !otpCode.trim()) {
      setError('נא להזין קוד אימות');
      return;
    }
    if (wizardMode === 'full') {
      if (!typedOrgName.trim()) {
        setError('נא להקליד את שם הארגון');
        return;
      }
      if (typedOrgName !== user?.organization?.name) {
        setError('שם הארגון אינו תואם. יש להקליד בדיוק כפי שמופיע.');
        return;
      }
    }

    setLoading(true);
    try {
      const body = {};
      if (authMethod === 'password') {
        body.password = password;
      } else {
        body.otp_code = otpCode;
      }

      let result;
      if (wizardMode === 'full') {
        body.typed_org_name = typedOrgName;
        result = await deletionService.requestFullDeletion(body);
      } else {
        result = await deletionService.requestDeletion(body);
      }

      toast.success('בקשת המחיקה נשלחה בהצלחה');
      if (result?.token) {
        replaceToken(result.token);
      }
      forceUserStatus('pending_deletion');
      navigate('/account/pending-deletion', { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'object' ? detail.message : (detail || 'שגיאה בשליחת בקשת מחיקה'));
    } finally {
      setLoading(false);
    }
  };

  if (wizardMode === 'owner_blocked') {
    return (
      <div className="bg-white rounded-2xl shadow-lg border border-red-100 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Trash2 className="w-5 h-5 text-red-500" />
          <h2 className="text-lg font-semibold text-red-700">מחיקת חשבון</h2>
        </div>
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg space-y-3">
          <p className="text-sm text-amber-800 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>יש להעביר בעלות על הארגון לפני מחיקת החשבון.</span>
          </p>
          <Button
            onClick={() => navigate('/org/transfer/settings')}
            variant="outline"
            className="w-full h-10 text-sm text-amber-700 border-amber-300 hover:bg-amber-100"
          >
            העבר בעלות על הארגון
          </Button>
          <Button onClick={resetWizard} variant="ghost" className="w-full h-10 text-sm">
            ביטול
          </Button>
        </div>
      </div>
    );
  }

  if (wizardMode) {
    const isFull = wizardMode === 'full';
    return (
      <div className="bg-white rounded-2xl shadow-lg border border-red-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Trash2 className="w-5 h-5 text-red-500" />
          <h2 className="text-lg font-semibold text-red-700">
            {isFull ? 'מחיקת חשבון וארגון' : 'מחיקת חשבון'}
          </h2>
        </div>

        <div className="flex items-center gap-1 mb-4">
          {[1, 2, 3].map(s => (
            <div key={s} className={`h-1 flex-1 rounded-full ${step >= s ? 'bg-red-500' : 'bg-slate-200'}`} />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg space-y-2">
              <p className="text-sm font-semibold text-red-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                אזהרה — פעולה בלתי הפיכה
              </p>
              <ul className="text-sm text-red-700 space-y-1 mr-6 list-disc">
                <li>כל הנתונים האישיים שלך יימחקו לצמיתות</li>
                <li>לא תוכל לגשת לחשבון שלך יותר</li>
                {isFull && (
                  <>
                    <li>כל הפרויקטים, המשימות והנתונים של הארגון יימחקו</li>
                    <li>כל חברי הארגון יאבדו את הגישה שלהם</li>
                  </>
                )}
              </ul>
              <p className="text-xs text-red-500 pt-1">
                {isFull
                  ? 'לאחר תקופת המתנה, החשבון והארגון יימחקו סופית.'
                  : 'לאחר תקופת המתנה, החשבון יימחק סופית.'}
              </p>
            </div>

            <div className="flex gap-3">
              <Button
                onClick={handleProceedToAuth}
                disabled={loading}
                className="flex-1 h-11 bg-red-600 hover:bg-red-700 text-white font-medium"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                  </span>
                ) : 'המשך'}
              </Button>
              <Button onClick={resetWizard} disabled={loading} variant="outline" className="flex-1 h-11">
                ביטול
              </Button>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-slate-700 font-medium">שלב 2 — אימות זהות</p>

            {authMethod === 'password' ? (
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700">סיסמה נוכחית</label>
                <div className="relative">
                  <input
                    type={showPw ? 'text' : 'password'}
                    value={password}
                    onChange={e => { setPassword(e.target.value); setError(''); }}
                    placeholder="הזן סיסמה"
                    className="w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500"
                  />
                  <button type="button" onClick={() => setShowPw(p => !p)} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
                    {showPw ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700">קוד אימות (נשלח ב-SMS)</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={otpCode}
                  onChange={e => { setOtpCode(e.target.value.replace(/\D/g, '')); setError(''); }}
                  placeholder="הזן קוד 6 ספרות"
                  className="w-full h-11 px-3 py-2 text-center text-slate-900 bg-white border border-slate-300 rounded-lg tracking-widest text-lg font-mono focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500"
                  dir="ltr"
                />
                {otpDebugCode && (
                  <p className="text-xs text-slate-400 text-center mt-1">(dev) קוד: {otpDebugCode}</p>
                )}
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button
                onClick={() => { setError(''); setStep(3); }}
                disabled={loading || (authMethod === 'password' ? !password.trim() : !otpCode.trim())}
                className="flex-1 h-11 bg-red-600 hover:bg-red-700 text-white font-medium"
              >
                המשך
              </Button>
              <Button onClick={resetWizard} disabled={loading} variant="outline" className="flex-1 h-11">
                ביטול
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <p className="text-sm text-slate-700 font-medium">שלב 3 — אישור סופי</p>

            <div className="p-4 bg-red-50 border border-red-200 rounded-lg space-y-2">
              <p className="text-sm font-bold text-red-700">
                {isFull
                  ? `החשבון והארגון "${user?.organization?.name}" יימחקו לצמיתות לאחר תקופת ההמתנה.`
                  : 'החשבון שלך יימחק לצמיתות לאחר תקופת ההמתנה.'}
              </p>
              <p className="text-sm text-red-600">
                האם אתה בטוח? לא ניתן לבטל פעולה זו לאחר תום תקופת ההמתנה.
              </p>
            </div>

            {isFull && (
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700">
                  הקלד את שם הארגון בדיוק: <span className="font-bold text-red-600">{user?.organization?.name}</span>
                </label>
                <input
                  type="text"
                  value={typedOrgName}
                  onChange={e => { setTypedOrgName(e.target.value); setError(''); }}
                  placeholder={user?.organization?.name}
                  className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500"
                />
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button
                onClick={handleConfirmDeletion}
                disabled={loading}
                className="flex-1 h-11 bg-red-600 hover:bg-red-700 text-white font-medium"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    מוחק...
                  </span>
                ) : 'אשר מחיקה סופית'}
              </Button>
              <Button onClick={resetWizard} disabled={loading} variant="outline" className="flex-1 h-11">
                ביטול
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-lg border border-red-100 p-6">
      <div className="flex items-center gap-2 mb-4">
        <Trash2 className="w-5 h-5 text-red-500" />
        <h2 className="text-lg font-semibold text-red-700">מחיקת חשבון</h2>
      </div>
      <p className="text-sm text-slate-600 mb-4">
        מחיקת החשבון היא פעולה בלתי הפיכה. לאחר תקופת המתנה כל הנתונים שלך יימחקו לצמיתות.
      </p>

      <div className="space-y-3">
        <Button
          onClick={() => handleStartDeletion('account')}
          variant="outline"
          className="w-full h-11 justify-start text-sm text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
        >
          <Trash2 className="w-4 h-4 ml-2" />
          מחק את החשבון שלי
        </Button>

        {isOrgOwner && user?.organization && (
          <Button
            onClick={() => handleStartDeletion('full')}
            variant="outline"
            className="w-full h-11 justify-start text-sm text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
          >
            <AlertTriangle className="w-4 h-4 ml-2" />
            מחק הכל ({user.organization.name})
          </Button>
        )}
      </div>
    </div>
  );
};

const AccountSettingsPage = () => {
  const { user, logout } = useAuth();
  const { setShowCompleteForm, identityStatus, refreshIdentity } = useIdentity();
  const navigate = useNavigate();
  const location = useLocation();
  const phoneRef = useRef(null);
  const [showPhoneChange, setShowPhoneChange] = useState(false);
  const [waLang, setWaLang] = useState(user?.preferred_language || 'he');
  const [waLangSaving, setWaLangSaving] = useState(false);
  const [waNotifEnabled, setWaNotifEnabled] = useState(user?.whatsapp_notifications_enabled !== false);
  const [waNotifSaving, setWaNotifSaving] = useState(false);
  const [showWaConfirm, setShowWaConfirm] = useState(false);

  const [reminderPrefs, setReminderPrefs] = useState(null);
  const [reminderPrefsSaving, setReminderPrefsSaving] = useState(false);

  const DAY_LABELS = ['א', 'ב', 'ג', 'ד', 'ה'];

  const memberships = user?.project_memberships_summary || [];
  const userRoles = new Set(memberships.map(m => m.role));
  const isContractor = userRoles.has('contractor');
  const isPmOrOwner = userRoles.has('project_manager') || userRoles.has('owner') || userRoles.has('management_team') || user?.platform_role === 'super_admin';
  const showReminderPrefs = isContractor || isPmOrOwner;

  useEffect(() => {
    if (showReminderPrefs) {
      userService.getReminderPreferences().then(setReminderPrefs).catch(() => {});
    }
  }, [showReminderPrefs]);

  const updateReminderPref = async (type, field, value) => {
    const prev = reminderPrefs;
    const updated = { ...reminderPrefs, [type]: { ...reminderPrefs[type], [field]: value } };
    setReminderPrefs(updated);
    setReminderPrefsSaving(true);
    try {
      const result = await userService.updateReminderPreferences({ [type]: { [field]: value } });
      setReminderPrefs(result);
      toast.success('הגדרות התראות עודכנו');
    } catch (err) {
      setReminderPrefs(prev);
      toast.error(err.response?.data?.detail || 'שגיאה בעדכון הגדרות');
    } finally {
      setReminderPrefsSaving(false);
    }
  };

  const toggleDay = (type, day) => {
    const currentDays = reminderPrefs?.[type]?.days || [0, 1, 2, 3, 4];
    const newDays = currentDays.includes(day) ? currentDays.filter(d => d !== day) : [...currentDays, day].sort();
    updateReminderPref(type, 'days', newDays);
  };

  useEffect(() => {
    if (location.hash === '#phone') {
      const tid = setTimeout(() => {
        phoneRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 150);
      return () => clearTimeout(tid);
    }
  }, [location.hash]);

  const [emailForm, setEmailForm] = useState({ newEmail: '', currentPassword: '' });
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailErrors, setEmailErrors] = useState({});
  const [emailServerError, setEmailServerError] = useState('');
  const [currentEmail, setCurrentEmail] = useState(user?.email || '');

  const [pwForm, setPwForm] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
  const [pwLoading, setPwLoading] = useState(false);
  const [pwErrors, setPwErrors] = useState({});
  const [pwServerError, setPwServerError] = useState('');
  const [setPwForm2, setSetPwForm2] = useState({ newPassword: '', confirmPassword: '' });
  const [setPwLoading2, setSetPwLoading2] = useState(false);
  const [setPwErrors2, setSetPwErrors2] = useState({});
  const [setPwServerError2, setSetPwServerError2] = useState('');
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  const [showEmailPw, setShowEmailPw] = useState(false);

  if (!user) return null;

  const hasEmail = !!currentEmail;
  const hasPassword = identityStatus?.has_password !== false;

  const handleChangeEmail = async (e) => {
    e.preventDefault();
    setEmailServerError('');
    const errs = {};
    const email = emailForm.newEmail.trim().toLowerCase();
    if (!email) errs.newEmail = 'נא להזין כתובת אימייל';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.newEmail = 'כתובת אימייל לא תקינה';
    if (!emailForm.currentPassword) errs.currentPassword = 'נא להזין סיסמה נוכחית';
    setEmailErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setEmailLoading(true);
    try {
      const result = await authService.changeEmail(emailForm.currentPassword, email);
      setCurrentEmail(result.email);
      setEmailForm({ newEmail: '', currentPassword: '' });
      toast.success('האימייל עודכן בהצלחה');
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || '';
      if (status === 401) setEmailServerError('סיסמה נוכחית שגויה');
      else if (status === 403) setEmailServerError('אין הרשאה לבצע פעולה זו');
      else if (status === 409) setEmailServerError(detail || 'כתובת אימייל כבר רשומה במערכת');
      else if (status === 400) setEmailServerError(detail || 'נתונים לא תקינים');
      else setEmailServerError('אירעה שגיאה. נסה שוב מאוחר יותר.');
    } finally {
      setEmailLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPwServerError('');
    const errs = {};
    if (!pwForm.currentPassword) errs.currentPassword = 'נא להזין סיסמה נוכחית';
    if (!pwForm.newPassword || pwForm.newPassword.length < 8) errs.newPassword = 'סיסמה חייבת להכיל לפחות 8 תווים';
    else if (!/[a-zA-Zא-ת]/.test(pwForm.newPassword)) errs.newPassword = 'סיסמה חייבת להכיל לפחות אות אחת';
    else if (!/[0-9]/.test(pwForm.newPassword)) errs.newPassword = 'סיסמה חייבת להכיל לפחות ספרה אחת';
    if (pwForm.newPassword && pwForm.newPassword !== pwForm.confirmPassword) errs.confirmPassword = 'הסיסמאות לא תואמות';
    setPwErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setPwLoading(true);
    try {
      const result = await authService.changePassword(pwForm.currentPassword, pwForm.newPassword);
      toast.success('הסיסמה שונתה בהצלחה. יש להתחבר מחדש.');
      if (result.force_relogin) {
        setTimeout(() => {
          logout();
          navigate('/login', { replace: true });
        }, 1500);
      }
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || '';
      if (status === 401) setPwServerError('סיסמה נוכחית שגויה');
      else if (status === 403) setPwServerError('אין הרשאה לבצע פעולה זו');
      else if (status === 400) setPwServerError(detail || 'סיסמה לא תקינה');
      else setPwServerError('אירעה שגיאה. נסה שוב מאוחר יותר.');
    } finally {
      setPwLoading(false);
    }
  };

  const handleSetPassword = async (e) => {
    e.preventDefault();
    setSetPwServerError2('');
    const errs = {};
    if (!setPwForm2.newPassword || setPwForm2.newPassword.length < 8) errs.newPassword = 'סיסמה חייבת להכיל לפחות 8 תווים';
    else if (!/[a-zA-Zא-ת]/.test(setPwForm2.newPassword)) errs.newPassword = 'סיסמה חייבת להכיל לפחות אות אחת';
    else if (!/[0-9]/.test(setPwForm2.newPassword)) errs.newPassword = 'סיסמה חייבת להכיל לפחות ספרה אחת';
    if (setPwForm2.newPassword && setPwForm2.newPassword !== setPwForm2.confirmPassword) errs.confirmPassword = 'הסיסמאות לא תואמות';
    setSetPwErrors2(errs);
    if (Object.keys(errs).length > 0) return;

    setSetPwLoading2(true);
    try {
      await authService.setPassword(setPwForm2.newPassword);
      toast.success('סיסמה הוגדרה בהצלחה');
      setSetPwForm2({ newPassword: '', confirmPassword: '' });
      await refreshIdentity();
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || '';
      if (status === 400) setSetPwServerError2(detail || 'סיסמה לא תקינה');
      else setSetPwServerError2('אירעה שגיאה. נסה שוב מאוחר יותר.');
    } finally {
      setSetPwLoading2(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-amber-50/30 py-8 px-4" dir="rtl">
      <div className="max-w-lg mx-auto space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <button onClick={() => navigate(-1)} className="p-2 rounded-lg hover:bg-slate-100 transition-colors">
            <ArrowRight className="w-5 h-5 text-slate-600" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-900">הגדרות חשבון</h1>
            <p className="text-sm text-slate-500">{user.name || 'משתמש'}</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Mail className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-slate-900">כתובת אימייל</h2>
          </div>

          <div className="text-sm text-slate-600 mb-4">
            אימייל נוכחי:{' '}
            <span className="font-medium text-slate-900" dir="ltr">
              {hasEmail ? currentEmail : 'לא מוגדר'}
            </span>
          </div>

          {hasEmail ? (
            <form onSubmit={handleChangeEmail} className="space-y-3">
              {emailServerError && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{emailServerError}</span>
                </div>
              )}
              <div className="space-y-1">
                <label htmlFor="newEmail" className="block text-sm font-medium text-slate-700">אימייל חדש</label>
                <input
                  id="newEmail" type="email" dir="ltr"
                  value={emailForm.newEmail}
                  onChange={(e) => { setEmailForm(f => ({ ...f, newEmail: e.target.value })); setEmailErrors(p => { const n = {...p}; delete n.newEmail; return n; }); setEmailServerError(''); }}
                  placeholder="new@email.com"
                  className={`w-full h-11 px-3 py-2 text-left text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${emailErrors.newEmail ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
                />
                {emailErrors.newEmail && (
                  <div className="flex items-center gap-1 text-sm text-red-500">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{emailErrors.newEmail}</span>
                  </div>
                )}
              </div>
              <div className="space-y-1">
                <label htmlFor="emailCurrentPw" className="block text-sm font-medium text-slate-700">סיסמה נוכחית</label>
                <PasswordInput
                  id="emailCurrentPw"
                  value={emailForm.currentPassword}
                  onChange={(e) => { setEmailForm(f => ({ ...f, currentPassword: e.target.value })); setEmailErrors(p => { const n = {...p}; delete n.currentPassword; return n; }); setEmailServerError(''); }}
                  placeholder="הזן סיסמה נוכחית"
                  show={showEmailPw} onToggle={() => setShowEmailPw(p => !p)}
                  error={emailErrors.currentPassword}
                />
              </div>
              <Button type="submit" className="w-full h-11 bg-amber-500 hover:bg-amber-600 text-white font-medium" disabled={emailLoading}>
                {emailLoading ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-5 h-5 animate-spin" />מעדכן...</span> : 'עדכן אימייל'}
              </Button>
            </form>
          ) : (
            <div className="text-center py-4 space-y-3">
              <p className="text-sm text-slate-500">לא הוגדר אימייל עדיין. השלם את החשבון כדי להוסיף אימייל וסיסמה.</p>
              <Button
                onClick={() => setShowCompleteForm(true)}
                className="bg-amber-500 hover:bg-amber-600 text-white font-medium"
              >
                השלמת חשבון (אימייל+סיסמה)
              </Button>
            </div>
          )}
        </div>

        {(user.organization || (user.project_memberships_summary && user.project_memberships_summary.length > 0)) && (
          <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Briefcase className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-semibold text-slate-900">פרטי עבודה</h2>
            </div>

            {user.organization && (
              <div className="flex items-center gap-2 mb-4 text-sm text-slate-600">
                <Building2 className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span>ארגון: <span className="font-medium text-slate-900">{user.organization.name || user.organization.id}</span></span>
              </div>
            )}

            {user.project_memberships_summary && user.project_memberships_summary.length > 0 && (
              <div className="space-y-3">
                <p className="text-sm font-medium text-slate-700">פרויקטים</p>
                {user.project_memberships_summary.map((pm, idx) => (
                  <div key={pm.project_id || idx} className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
                    <div className="font-medium text-slate-900 text-sm">{pm.project_name || pm.project_id}</div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                      {pm.role && <span>תפקיד: <span className="text-slate-700">{tRole(pm.role)}</span></span>}
                      {pm.contractor_trade_key && <span>מקצוע: <span className="text-slate-700">{tTrade(pm.contractor_trade_key)}</span></span>}
                      {pm.company_name && <span>חברה: <span className="text-slate-700">{pm.company_name}</span></span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div ref={phoneRef} id="phone" className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Phone className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-slate-900">מספר טלפון</h2>
          </div>
          <div className="text-sm text-slate-600 mb-4">
            מספר נוכחי:{' '}
            <span className="font-medium text-slate-900">
              {user.phone_e164 ? <bdi dir="ltr">{user.phone_e164}</bdi> : 'לא מוגדר'}
            </span>
          </div>
          <Button
            onClick={() => setShowPhoneChange(true)}
            className="w-full h-11 bg-amber-500 hover:bg-amber-600 text-white font-medium"
          >
            שינוי מספר טלפון
          </Button>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
          <div className="flex items-center gap-2 mb-4">
            <MessageCircle className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-slate-900">{t('settings', 'wa_language_title')}</h2>
          </div>
          <p className="text-sm text-slate-500 mb-4">{t('settings', 'wa_language_desc')}</p>
          <select
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 disabled:opacity-50 disabled:cursor-not-allowed"
            value={waLang}
            disabled={waLangSaving}
            onChange={async (e) => {
              const newLang = e.target.value;
              setWaLangSaving(true);
              try {
                await authService.updateMyPreferredLanguage(newLang);
                setWaLang(newLang);
                setLanguage(newLang);
                toast.success(t('toasts', 'wa_language_updated'));
                window.location.reload();
              } catch (err) {
                toast.error(err.response?.data?.detail || t('toasts', 'language_update_error'));
              } finally {
                setWaLangSaving(false);
              }
            }}
          >
            <option value="he">עברית</option>
            <option value="en">English</option>
            <option value="ar">العربية</option>
            <option value="zh">中文</option>
          </select>
          {waLangSaving && (
            <div className="flex items-center gap-2 mt-2 text-sm text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{t('settings', 'saving')}</span>
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Bell className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-slate-900">הודעות WhatsApp</h2>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-700">קבל הודעות WhatsApp על ליקויים ועדכונים</span>
            <button
              type="button"
              role="switch"
              aria-checked={waNotifEnabled}
              disabled={waNotifSaving}
              onClick={() => {
                if (waNotifEnabled) {
                  setShowWaConfirm(true);
                } else {
                  (async () => {
                    setWaNotifSaving(true);
                    try {
                      await authService.updateWhatsAppNotifications(true);
                      setWaNotifEnabled(true);
                      toast.success('הודעות WhatsApp הופעלו');
                    } catch (err) {
                      toast.error(err.response?.data?.detail || 'שגיאה בעדכון הגדרות');
                    } finally {
                      setWaNotifSaving(false);
                    }
                  })();
                }
              }}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500/50 disabled:opacity-50 ${waNotifEnabled ? 'bg-amber-500' : 'bg-slate-300'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${waNotifEnabled ? '-translate-x-1' : '-translate-x-6'}`} />
            </button>
          </div>
          {waNotifSaving && (
            <div className="flex items-center gap-2 mt-2 text-sm text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>שומר...</span>
            </div>
          )}
        </div>

        <AlertDialogPrimitive.Root open={showWaConfirm} onOpenChange={setShowWaConfirm}>
          <AlertDialogPrimitive.Portal>
            <AlertDialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40" />
            <AlertDialogPrimitive.Content className="fixed inset-0 z-50 flex items-center justify-center outline-none pointer-events-none">
              <div className="bg-white rounded-2xl shadow-xl border border-slate-200 p-6 mx-4 max-w-sm w-full pointer-events-auto" dir="rtl">
                <AlertDialogPrimitive.Title className="text-lg font-semibold text-slate-900 mb-3">כיבוי הודעות WhatsApp</AlertDialogPrimitive.Title>
                <AlertDialogPrimitive.Description className="text-sm text-slate-600 mb-5">
                  לא תקבל עדכונים על ליקויים חדשים או שינויים. ניתן להפעיל מחדש בכל עת.
                </AlertDialogPrimitive.Description>
                <div className="flex gap-3">
                  <AlertDialogPrimitive.Action asChild>
                    <Button
                      onClick={async () => {
                        setShowWaConfirm(false);
                        setWaNotifSaving(true);
                        try {
                          await authService.updateWhatsAppNotifications(false);
                          setWaNotifEnabled(false);
                          toast.success('הודעות WhatsApp כובו');
                        } catch (err) {
                          toast.error(err.response?.data?.detail || 'שגיאה בעדכון הגדרות');
                        } finally {
                          setWaNotifSaving(false);
                        }
                      }}
                      className="flex-1 h-10 bg-red-500 hover:bg-red-600 text-white font-medium"
                    >
                      כבה הודעות
                    </Button>
                  </AlertDialogPrimitive.Action>
                  <AlertDialogPrimitive.Cancel asChild>
                    <Button
                      className="flex-1 h-10 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium"
                    >
                      ביטול
                    </Button>
                  </AlertDialogPrimitive.Cancel>
                </div>
              </div>
            </AlertDialogPrimitive.Content>
          </AlertDialogPrimitive.Portal>
        </AlertDialogPrimitive.Root>

        {showReminderPrefs && reminderPrefs && (
          <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Bell className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-semibold text-slate-900">הגדרות תזכורות</h2>
            </div>
            <p className="text-xs text-slate-400 mb-4">שליטה בתזכורות אוטומטיות בלבד. שליחה ידנית אינה מושפעת מהגדרות אלה.</p>

            {isContractor && (
              <div className="space-y-3 mb-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-700 font-medium">תזכורות ליקויים</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={reminderPrefs.contractor_reminder?.enabled !== false}
                    disabled={reminderPrefsSaving}
                    onClick={() => updateReminderPref('contractor_reminder', 'enabled', !(reminderPrefs.contractor_reminder?.enabled !== false))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500/50 disabled:opacity-50 ${reminderPrefs.contractor_reminder?.enabled !== false ? 'bg-amber-500' : 'bg-slate-300'}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${reminderPrefs.contractor_reminder?.enabled !== false ? '-translate-x-1' : '-translate-x-6'}`} />
                  </button>
                </div>
                {reminderPrefs.contractor_reminder?.enabled !== false && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-slate-500 ml-1">ימים:</span>
                    {DAY_LABELS.map((label, idx) => (
                      <button
                        key={idx}
                        type="button"
                        disabled={reminderPrefsSaving}
                        onClick={() => toggleDay('contractor_reminder', idx)}
                        className={`w-8 h-8 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
                          (reminderPrefs.contractor_reminder?.days || [0,1,2,3,4]).includes(idx)
                            ? 'bg-amber-500 text-white'
                            : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {isPmOrOwner && (
              <div className="space-y-3">
                {isContractor && <div className="border-t border-slate-100 pt-3" />}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-700 font-medium">סיכום יומי</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={reminderPrefs.pm_digest?.enabled !== false}
                    disabled={reminderPrefsSaving}
                    onClick={() => updateReminderPref('pm_digest', 'enabled', !(reminderPrefs.pm_digest?.enabled !== false))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500/50 disabled:opacity-50 ${reminderPrefs.pm_digest?.enabled !== false ? 'bg-amber-500' : 'bg-slate-300'}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${reminderPrefs.pm_digest?.enabled !== false ? '-translate-x-1' : '-translate-x-6'}`} />
                  </button>
                </div>
                {reminderPrefs.pm_digest?.enabled !== false && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-slate-500 ml-1">ימים:</span>
                    {DAY_LABELS.map((label, idx) => (
                      <button
                        key={idx}
                        type="button"
                        disabled={reminderPrefsSaving}
                        onClick={() => toggleDay('pm_digest', idx)}
                        className={`w-8 h-8 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
                          (reminderPrefs.pm_digest?.days || [0,1,2,3,4]).includes(idx)
                            ? 'bg-amber-500 text-white'
                            : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {reminderPrefsSaving && (
              <div className="flex items-center gap-2 mt-3 text-sm text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>שומר...</span>
              </div>
            )}
          </div>
        )}

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-slate-900">{hasPassword ? 'שינוי סיסמה' : 'הגדרת סיסמה'}</h2>
          </div>

          {!hasPassword && !hasEmail ? (
            <div className="text-center py-4 space-y-3">
              <p className="text-sm text-slate-500">לא הוגדרה סיסמה. יש להשלים חשבון תחילה.</p>
              <Button
                onClick={() => setShowCompleteForm(true)}
                className="bg-amber-500 hover:bg-amber-600 text-white font-medium"
              >
                השלמת חשבון (אימייל+סיסמה)
              </Button>
            </div>
          ) : !hasPassword && hasEmail ? (
            <form onSubmit={handleSetPassword} className="space-y-3">
              {setPwServerError2 && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{setPwServerError2}</span>
                </div>
              )}
              <p className="text-sm text-slate-500">טרם הוגדרה סיסמה לחשבון זה. הגדר סיסמה כדי להתחבר גם באימייל.</p>
              <div className="space-y-1">
                <label htmlFor="setPw" className="block text-sm font-medium text-slate-700">סיסמה חדשה</label>
                <PasswordInput
                  id="setPw"
                  value={setPwForm2.newPassword}
                  onChange={(e) => { setSetPwForm2(f => ({ ...f, newPassword: e.target.value })); setSetPwErrors2(p => { const n = {...p}; delete n.newPassword; return n; }); setSetPwServerError2(''); }}
                  placeholder="לפחות 8 תווים, אות וספרה"
                  show={showNewPw} onToggle={() => setShowNewPw(p => !p)}
                  error={setPwErrors2.newPassword}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="setConfirmPw" className="block text-sm font-medium text-slate-700">אימות סיסמה</label>
                <PasswordInput
                  id="setConfirmPw"
                  value={setPwForm2.confirmPassword}
                  onChange={(e) => { setSetPwForm2(f => ({ ...f, confirmPassword: e.target.value })); setSetPwErrors2(p => { const n = {...p}; delete n.confirmPassword; return n; }); setSetPwServerError2(''); }}
                  placeholder="הזן שוב את הסיסמה"
                  show={showConfirmPw} onToggle={() => setShowConfirmPw(p => !p)}
                  error={setPwErrors2.confirmPassword}
                />
              </div>
              <Button type="submit" className="w-full h-11 bg-amber-500 hover:bg-amber-600 text-white font-medium" disabled={setPwLoading2}>
                {setPwLoading2 ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-5 h-5 animate-spin" />שומר...</span> : 'הגדר סיסמה'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleChangePassword} className="space-y-3">
              {pwServerError && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{pwServerError}</span>
                </div>
              )}
              <div className="space-y-1">
                <label htmlFor="currentPw" className="block text-sm font-medium text-slate-700">סיסמה נוכחית</label>
                <PasswordInput
                  id="currentPw"
                  value={pwForm.currentPassword}
                  onChange={(e) => { setPwForm(f => ({ ...f, currentPassword: e.target.value })); setPwErrors(p => { const n = {...p}; delete n.currentPassword; return n; }); setPwServerError(''); }}
                  placeholder="הזן סיסמה נוכחית"
                  show={showCurrentPw} onToggle={() => setShowCurrentPw(p => !p)}
                  error={pwErrors.currentPassword}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="newPw" className="block text-sm font-medium text-slate-700">סיסמה חדשה</label>
                <PasswordInput
                  id="newPw"
                  value={pwForm.newPassword}
                  onChange={(e) => { setPwForm(f => ({ ...f, newPassword: e.target.value })); setPwErrors(p => { const n = {...p}; delete n.newPassword; return n; }); setPwServerError(''); }}
                  placeholder="לפחות 8 תווים, אות וספרה"
                  show={showNewPw} onToggle={() => setShowNewPw(p => !p)}
                  error={pwErrors.newPassword}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="confirmPw" className="block text-sm font-medium text-slate-700">אימות סיסמה חדשה</label>
                <PasswordInput
                  id="confirmPw"
                  value={pwForm.confirmPassword}
                  onChange={(e) => { setPwForm(f => ({ ...f, confirmPassword: e.target.value })); setPwErrors(p => { const n = {...p}; delete n.confirmPassword; return n; }); setPwServerError(''); }}
                  placeholder="הזן שוב את הסיסמה החדשה"
                  show={showConfirmPw} onToggle={() => setShowConfirmPw(p => !p)}
                  error={pwErrors.confirmPassword}
                />
              </div>
              <p className="text-xs text-slate-400">שים לב: לאחר שינוי סיסמה תידרש כניסה מחדש.</p>
              <Button type="submit" className="w-full h-11 bg-amber-500 hover:bg-amber-600 text-white font-medium" disabled={pwLoading}>
                {pwLoading ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-5 h-5 animate-spin" />מעדכן...</span> : 'שנה סיסמה'}
              </Button>
            </form>
          )}
        </div>

        <DeleteAccountSection user={user} />

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-slate-900">מידע משפטי</h2>
          </div>
          <div className="space-y-3">
            <Link to="/accessibility" className="flex items-center gap-2 text-sm text-amber-600 hover:text-amber-700 font-medium">
              <Accessibility className="w-4 h-4" />
              הצהרת נגישות
            </Link>
          </div>
        </div>
      </div>

      {showPhoneChange && (
        <PhoneChangeModal onClose={() => setShowPhoneChange(false)} />
      )}
    </div>
  );
};

export default AccountSettingsPage;
