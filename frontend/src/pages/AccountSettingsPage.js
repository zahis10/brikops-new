import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useIdentity } from '../contexts/IdentityContext';
import { authService } from '../services/api';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import {
  Mail, Lock, Eye, EyeOff, Loader2, AlertCircle, ArrowRight, Phone, Building2, Briefcase, MessageCircle, Bell, Accessibility, FileText
} from 'lucide-react';
import PhoneChangeModal from '../components/PhoneChangeModal';
import { tRole, tTrade } from '../i18n';
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

const AccountSettingsPage = () => {
  const { user, logout } = useAuth();
  const { setShowCompleteForm, identityStatus } = useIdentity();
  const navigate = useNavigate();
  const location = useLocation();
  const phoneRef = useRef(null);
  const [showPhoneChange, setShowPhoneChange] = useState(false);
  const [waLang, setWaLang] = useState(user?.preferred_language || 'he');
  const [waLangSaving, setWaLangSaving] = useState(false);
  const [waNotifEnabled, setWaNotifEnabled] = useState(user?.whatsapp_notifications_enabled !== false);
  const [waNotifSaving, setWaNotifSaving] = useState(false);
  const [showWaConfirm, setShowWaConfirm] = useState(false);

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
            <h2 className="text-lg font-semibold text-slate-900">שפת הודעות WhatsApp</h2>
          </div>
          <p className="text-sm text-slate-500 mb-4">בחר את השפה שבה תקבל הודעות WhatsApp</p>
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
                toast.success('שפת WhatsApp עודכנה בהצלחה');
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
            <option value="zh">中文</option>
          </select>
          {waLangSaving && (
            <div className="flex items-center gap-2 mt-2 text-sm text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>שומר...</span>
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

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="w-5 h-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-slate-900">שינוי סיסמה</h2>
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
