import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { onboardingService } from '../services/api';
import { toast } from 'sonner';
import { HardHat, Phone, Loader2, Mail, Lock, User, KeyRound, Hash, Eye, EyeOff, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { canonicalE164, isValidIsraeliMobile } from '../utils/phoneUtils';

const ROLE_LABELS = {
  project_manager_assistant: 'עוזר/ת מנהל פרויקט',
  engineer: 'מהנדס/ת',
  safety: 'בטיחות',
  foreman: 'מנהל עבודה',
  inspector: 'מפקח/ת',
  site_manager: 'מנהל אתר',
  admin_assistant: 'עוזר/ת מנהלה',
};

const displayLocalPhone = (e164) => {
  const m = e164.match(/^\+972(\d)(\d{7})$/);
  if (!m) return e164;
  return `05${m[1]}-${m[2]}`;
};

const RegisterManagementPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const phoneFromState = location.state?.phone || '';
  const phoneVerifiedFromState = location.state?.phone_verified === true;

  const [phoneVerified, setPhoneVerified] = useState(phoneVerifiedFromState);
  const [phone, setPhone] = useState(phoneVerifiedFromState ? '' : phoneFromState);
  const [phoneE164, setPhoneE164] = useState(() => {
    if (phoneFromState) return canonicalE164(phoneFromState);
    return '';
  });
  const [otpStep, setOtpStep] = useState(phoneVerifiedFromState ? 'done' : 'phone');
  const [otpCode, setOtpCode] = useState('');
  const [phoneExistsError, setPhoneExistsError] = useState(false);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [joinCode, setJoinCode] = useState('');
  const [requestedRole, setRequestedRole] = useState('');

  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const otpInputRef = useRef(null);

  useEffect(() => {
    onboardingService.getManagementRoles?.()
      .then(setRoles)
      .catch(() => setRoles(Object.keys(ROLE_LABELS)));
  }, []);

  const handleRequestOtp = useCallback(async (e) => {
    e.preventDefault();
    if (!phone.trim()) {
      setErrors({ phone: 'יש להזין מספר טלפון' });
      return;
    }
    const normalized = canonicalE164(phone);
    if (!isValidIsraeliMobile(normalized)) {
      setErrors({ phone: 'מספר טלפון ישראלי לא תקין' });
      return;
    }
    setPhoneE164(normalized);
    setLoading(true);
    setErrors({});
    try {
      await onboardingService.requestOtp(normalized);
      setOtpStep('otp');
      toast.success('קוד אימות נשלח');
      setTimeout(() => otpInputRef.current?.focus(), 100);
    } catch (error) {
      if (error.response?.status === 429) {
        toast.error('יותר מדי ניסיונות. נסה שוב מאוחר יותר.');
      } else {
        toast.error(error.response?.data?.detail || 'שגיאה בשליחת קוד אימות');
      }
    } finally {
      setLoading(false);
    }
  }, [phone]);

  const handleVerifyOtp = useCallback(async (e) => {
    e.preventDefault();
    if (otpCode.length !== 6) {
      toast.error('יש להזין קוד בן 6 ספרות');
      return;
    }
    setLoading(true);
    try {
      const result = await onboardingService.verifyOtp(phoneE164, otpCode);
      if (result.user_exists) {
        toast.error('מספר זה כבר רשום במערכת. נסה להתחבר.');
        setTimeout(() => navigate('/login'), 1500);
        return;
      }
      setPhoneVerified(true);
      setOtpStep('done');
      toast.success('מספר טלפון אומת בהצלחה');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'קוד אימות שגוי');
    } finally {
      setLoading(false);
    }
  }, [otpCode, phoneE164, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const newErrors = {};
    if (!fullName || fullName.trim().length < 2) newErrors.fullName = 'שם מלא נדרש (לפחות 2 תווים)';
    if (!email) newErrors.email = 'אימייל נדרש';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) newErrors.email = 'אימייל לא תקין';
    if (!password) newErrors.password = 'סיסמה נדרשת';
    else if (password.length < 8) newErrors.password = 'סיסמה חייבת להכיל לפחות 8 תווים';
    if (!requestedRole) newErrors.role = 'יש לבחור תפקיד';
    if (!joinCode.trim()) newErrors.joinCode = 'קוד הצטרפות נדרש';
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setLoading(true);
    setErrors({});
    setPhoneExistsError(false);
    try {
      await onboardingService.registerManagement({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
        phone_e164: phoneE164,
        requested_role: requestedRole,
        join_code: joinCode.trim().toUpperCase(),
      });
      toast.success('ההרשמה הושלמה בהצלחה!');
      navigate('/pending', { state: { fromRegistration: true } });
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (detail && detail.includes('טלפון כבר רשום')) {
        setPhoneExistsError(true);
        toast.error(detail);
      } else if (detail) {
        toast.error(detail);
      } else {
        toast.error('אירעה שגיאה בהרשמה. נסה שוב.');
      }
    } finally {
      setLoading(false);
    }
  };

  const effectiveRoles = roles.length > 0 ? roles : Object.keys(ROLE_LABELS);

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl" dir="rtl">
        <div className="flex flex-col items-center mb-6">
          <div className="w-16 h-16 bg-amber-500 rounded-xl flex items-center justify-center mb-4 shadow-lg">
            <HardHat className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Rubik, sans-serif' }}>
            הרשמה לצוות ניהול
          </h1>
          <p className="text-slate-500 text-sm mt-1">BrikOps — ניהול משימות קבלן</p>
        </div>

        {!phoneVerified && otpStep === 'phone' && (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="reg-phone" className="block text-sm font-medium text-slate-700">
                מספר טלפון
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="reg-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="050-1234567"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  autoFocus
                />
                <Phone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
              {errors.phone && <p className="text-xs text-red-500">{errors.phone}</p>}
              <p className="text-xs text-slate-400">לדוגמה: 050-1234567</p>
            </div>
            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-4 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  שולח...
                </span>
              ) : 'שלח קוד אימות'}
            </Button>
            <div className="text-center mt-3">
              <button type="button" onClick={() => navigate('/login')} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
                חזרה לכניסה
              </button>
            </div>
          </form>
        )}

        {!phoneVerified && otpStep === 'otp' && (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="reg-otp" className="block text-sm font-medium text-slate-700">
                קוד אימות
                <span className="text-red-500 mr-1">*</span>
              </label>
              <input
                ref={otpInputRef}
                id="reg-otp"
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                className="w-full h-11 px-3 py-2 text-center text-lg tracking-[0.5em] text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                autoFocus
              />
              <p className="text-xs text-slate-400">הזן את הקוד שנשלח ל-{displayLocalPhone(phoneE164)}</p>
            </div>
            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-4 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={loading || otpCode.length !== 6}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  מאמת...
                </span>
              ) : 'אמת מספר טלפון'}
            </Button>
            <div className="text-center mt-3">
              <button type="button" onClick={() => { setOtpStep('phone'); setOtpCode(''); }} className="text-sm text-slate-500 hover:text-slate-700">
                שנה מספר טלפון
              </button>
            </div>
          </form>
        )}

        {phoneVerified && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg mb-4">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <div className="flex-1">
                <p className="text-sm text-emerald-700 font-medium">טלפון אומת</p>
                <p className="text-xs text-emerald-600 dir-ltr" dir="ltr">{displayLocalPhone(phoneE164)}</p>
              </div>
            </div>

            {phoneExistsError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700 font-medium mb-2">מספר טלפון כבר רשום במערכת</p>
                <button
                  type="button"
                  onClick={() => navigate('/login')}
                  className="text-sm text-amber-600 hover:text-amber-700 font-medium underline"
                >
                  עבור לכניסה
                </button>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="reg-name" className="block text-sm font-medium text-slate-700">
                שם מלא
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="reg-name"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="ישראל ישראלי"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  autoFocus
                />
                <User className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
              {errors.fullName && <p className="text-xs text-red-500">{errors.fullName}</p>}
            </div>

            <div className="space-y-2">
              <label htmlFor="reg-email" className="block text-sm font-medium text-slate-700">
                אימייל
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="reg-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@company.com"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  dir="ltr"
                />
                <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
              {errors.email && <p className="text-xs text-red-500">{errors.email}</p>}
            </div>

            <div className="space-y-2">
              <label htmlFor="reg-password" className="block text-sm font-medium text-slate-700">
                סיסמה
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="לפחות 8 תווים"
                  className="w-full h-11 px-3 py-2 pr-10 pl-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  dir="ltr"
                />
                <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'} aria-pressed={showPassword}>
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-red-500">{errors.password}</p>}
            </div>

            <div className="space-y-2">
              <label htmlFor="reg-role" className="block text-sm font-medium text-slate-700">
                תפקיד
                <span className="text-red-500 mr-1">*</span>
              </label>
              <select
                id="reg-role"
                value={requestedRole}
                onChange={(e) => setRequestedRole(e.target.value)}
                className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
              >
                <option value="">בחר תפקיד...</option>
                {effectiveRoles.map((role) => (
                  <option key={role} value={role}>
                    {ROLE_LABELS[role] || role}
                  </option>
                ))}
              </select>
              {errors.role && <p className="text-xs text-red-500">{errors.role}</p>}
            </div>

            <div className="space-y-2">
              <label htmlFor="reg-joincode" className="block text-sm font-medium text-slate-700">
                קוד הצטרפות לפרויקט
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="reg-joincode"
                  type="text"
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value)}
                  placeholder="BRK-1234"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400 uppercase"
                  dir="ltr"
                />
                <KeyRound className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
              {errors.joinCode && <p className="text-xs text-red-500">{errors.joinCode}</p>}
              <p className="text-xs text-slate-400">קוד שקיבלת ממנהל הפרויקט</p>
            </div>

            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-4 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  נרשם...
                </span>
              ) : 'הרשמה'}
            </Button>

            <div className="text-center mt-3">
              <button type="button" onClick={() => navigate('/login')} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
                חזרה לכניסה
              </button>
            </div>
          </form>
        )}

        <div className="mt-4 pt-4 border-t border-slate-100 text-center">
          <p className="text-xs text-slate-400">
            יש לך קוד הזמנה או רוצה ליצור ארגון חדש?{' '}
            <button type="button" onClick={() => navigate('/onboarding')} className="text-amber-600 hover:text-amber-700 font-medium">
              כניסה דרך הזמנה
            </button>
          </p>
        </div>
      </Card>
    </div>
  );
};

export default RegisterManagementPage;
