import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { onboardingService } from '../services/api';
import { toast } from 'sonner';
import { Eye, EyeOff, HardHat, Phone, ArrowRight, Loader2, Mail, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { canonicalE164, isValidIsraeliMobile } from '../utils/phoneUtils';

const ENABLE_REGISTER_MANAGEMENT_REDIRECTS =
  process.env.REACT_APP_ENABLE_REGISTER_MANAGEMENT_REDIRECTS === 'true';

const DEMO_ACCOUNTS = [
  { email: 'pm@contractor-ops.com', password: 'pm123', label: 'מנהל פרויקט', role: 'project_manager' },
  { email: 'sitemanager@contractor-ops.com', password: 'mgmt123', label: 'צוות ניהולי', role: 'management_team' },
  { email: 'contractor1@contractor-ops.com', password: 'cont123', label: 'קבלן', role: 'contractor' },
  { email: 'viewer@contractor-ops.com', password: 'view123', label: 'צופה', role: 'viewer' },
];

const SUPER_ADMIN_ACCOUNT = { email: 'superadmin@brikops.dev', password: 'super123', label: 'Super Admin', role: 'super_admin' };

const roleColors = {
  project_manager: 'bg-blue-100 text-blue-700 border-blue-200',
  management_team: 'bg-purple-100 text-purple-700 border-purple-200',
  contractor: 'bg-amber-100 text-amber-700 border-amber-200',
  viewer: 'bg-green-100 text-green-700 border-green-200',
  super_admin: 'bg-red-100 text-red-700 border-red-200',
};

const LoginPage = () => {
  const [authMethod, setAuthMethod] = useState('phone');
  const [phoneStep, setPhoneStep] = useState('phone');
  const [phone, setPhone] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [phoneE164, setPhoneE164] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [gitSha, setGitSha] = useState('');

  const { login, loginWithOtp } = useAuth();
  const navigate = useNavigate();

  const [appMode, setAppMode] = useState('');

  const [quickLoginEnabled, setQuickLoginEnabled] = useState(false);

  useEffect(() => {
    const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
    fetch(`${BACKEND_URL}/api/debug/version`)
      .then(r => r.json())
      .then(d => {
        setGitSha(d.git_sha || '');
        setAppMode(d.feature_flags?.app_mode || '');
        setQuickLoginEnabled(d.feature_flags?.enable_quick_login === true);
      })
      .catch(() => {});
  }, []);

  const handleRequestOtp = useCallback(async (e) => {
    e.preventDefault();
    if (!phone.trim()) {
      toast.error('יש להזין מספר טלפון');
      return;
    }
    const e164 = canonicalE164(phone);
    if (!isValidIsraeliMobile(e164)) {
      toast.error('מספר טלפון לא תקין');
      return;
    }
    setLoading(true);
    try {
      const res = await onboardingService.requestOtp(e164);
      console.log('[OTP-DEBUG] LoginPage handleRequestOtp result:', res);
      setPhoneE164(e164);
      setPhoneStep('otp');
      toast('שולחים קוד אימות...', { icon: '📱' });
    } catch (error) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || error.message;
      if (status === 429) {
        toast.error(typeof detail === 'string' ? detail : 'יותר מדי בקשות. נסה שוב בעוד מספר דקות.');
      } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        setPhoneE164(e164);
        setPhoneStep('otp');
        toast('שולחים קוד אימות, ייתכן עיכוב קצר...', { icon: '⏳' });
      } else if (status >= 500) {
        toast.error('שגיאה בשרת. נסה שוב בעוד רגע.');
      } else {
        console.error('[OTP-DEBUG] LoginPage error:', { status, detail, code: error.code, message: error.message });
        toast.error(typeof detail === 'string' ? detail : 'שגיאה בשליחת קוד אימות');
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

      if (result.requires_onboarding || result.next === 'onboarding') {
        if (ENABLE_REGISTER_MANAGEMENT_REDIRECTS) {
          navigate('/register-management', { state: { phone: result.phone_e164 || phoneE164, phone_verified: true } });
        } else {
          navigate('/onboarding', { state: { phone: result.phone_e164 || phoneE164 } });
        }
        return;
      }

      if (result.user_status === 'pending_pm_approval') {
        if (result.token) {
          loginWithOtp(result.token, result.user);
        }
        navigate('/pending');
        return;
      }

      if (result.user_status === 'rejected') {
        toast.error(result.message || 'הבקשה נדחתה. פנה למנהל הפרויקט.');
        return;
      }

      if (result.user_status === 'suspended') {
        toast.error(result.message || 'חשבון מושהה. פנה למנהל.');
        return;
      }

      if (result.token && result.user) {
        loginWithOtp(result.token, result.user);
        toast.success('התחברת בהצלחה!');
        const intended = sessionStorage.getItem('intendedPath');
        if (intended) {
          sessionStorage.removeItem('intendedPath');
          navigate(intended);
        } else {
          navigate('/projects');
        }
      } else {
        toast.error('תגובה לא צפויה מהשרת');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'קוד אימות שגוי');
    } finally {
      setLoading(false);
    }
  }, [otpCode, phoneE164, loginWithOtp, navigate]);

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    const newErrors = {};
    if (!email) newErrors.email = 'יש להזין אימייל';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) newErrors.email = 'אימייל לא תקין';
    if (!password) newErrors.password = 'יש להזין סיסמה';
    else if (password.length < 8) newErrors.password = 'סיסמה חייבת להכיל לפחות 8 תווים';
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result.success) {
        toast.success('התחברת בהצלחה!');
        const intended = sessionStorage.getItem('intendedPath');
        if (intended) {
          sessionStorage.removeItem('intendedPath');
          navigate(intended);
        } else {
          navigate('/projects');
        }
      } else {
        toast.error(result.error);
      }
    } catch (error) {
      toast.error('אירעה שגיאה. נסה שוב.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (account) => {
    setLoading(true);
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const res = await fetch(`${BACKEND_URL}/api/auth/dev-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: account.role }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'שגיאה בכניסה מהירה');
        return;
      }
      const data = await res.json();
      const { token: newToken, user: userData, platform_role } = data;
      localStorage.setItem('token', newToken);
      window.location.href = '/projects';
    } catch (error) {
      toast.error('אירעה שגיאה. נסה שוב.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl relative z-10">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-amber-500 rounded-xl flex items-center justify-center mb-4 shadow-lg">
            <HardHat className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-slate-900" style={{ fontFamily: 'Rubik, sans-serif' }}>
            BrikOps
          </h1>
          <p className="text-slate-500 text-sm mt-1">ניהול משימות קבלן</p>
        </div>

        <div className="flex gap-2 mb-6 p-1 bg-slate-100 rounded-lg" role="tablist">
          <button type="button" role="tab" aria-selected={authMethod === 'phone'}
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-all touch-manipulation flex items-center justify-center gap-1.5 ${
              authMethod === 'phone' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
            onClick={() => { setAuthMethod('phone'); setErrors({}); }}
          >
            <Phone className="w-4 h-4" />
            טלפון
          </button>
          <button type="button" role="tab" aria-selected={authMethod === 'email'}
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-all touch-manipulation flex items-center justify-center gap-1.5 ${
              authMethod === 'email' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
            onClick={() => { setAuthMethod('email'); setErrors({}); }}
          >
            <Mail className="w-4 h-4" />
            אימייל
          </button>
        </div>

        {authMethod === 'phone' && phoneStep === 'phone' && (
          <form onSubmit={handleRequestOtp} className="space-y-4" dir="rtl">
            <div className="space-y-2">
              <label htmlFor="phone" className="block text-sm font-medium text-slate-700">
                מספר טלפון
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="050-1234567"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  autoFocus
                />
                <Phone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
              <p className="text-xs text-slate-400">לדוגמה: 050-1234567</p>
            </div>
            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-6 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  שולח קוד...
                </span>
              ) : 'שלח קוד אימות'}
            </Button>
          </form>
        )}

        {authMethod === 'phone' && phoneStep === 'otp' && (
          <form onSubmit={handleVerifyOtp} className="space-y-4" dir="rtl">
            <button
              type="button"
              onClick={() => { setPhoneStep('phone'); setOtpCode(''); }}
              className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-2"
            >
              <ArrowRight className="w-4 h-4" />
              חזרה
            </button>
            <div className="text-center mb-4">
              <p className="text-sm text-slate-600">קוד אימות נשלח למספר</p>
              <bdi dir="ltr" className="font-mono text-base font-medium text-slate-900 mt-1 inline-block">{phoneE164}</bdi>
            </div>
            <div className="space-y-2">
              <label htmlFor="otp" className="block text-sm font-medium text-slate-700">
                קוד אימות
                <span className="text-red-500 mr-1">*</span>
              </label>
              <input
                id="otp"
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="w-full h-14 px-3 py-2 text-center text-2xl tracking-[0.5em] text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-300"
                autoFocus
              />
            </div>
            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-6 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={loading || otpCode.length !== 6}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  מאמת...
                </span>
              ) : 'אימות והתחברות'}
            </Button>
            <button
              type="button"
              onClick={handleRequestOtp}
              disabled={loading}
              className="w-full text-sm text-amber-600 hover:text-amber-700 mt-2"
            >
              שלח קוד חדש
            </button>
          </form>
        )}

        {authMethod === 'email' && (
          <form onSubmit={handleEmailLogin} className="space-y-4" dir="rtl">
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                אימייל <span className="text-red-500 mr-1">*</span>
              </label>
              <input
                id="email" type="email" value={email}
                onChange={(e) => { setEmail(e.target.value); setErrors(prev => { const n = {...prev}; delete n.email; return n; }); }}
                placeholder="your@email.com"
                className={`w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${errors.email ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
              />
              {errors.email && (
                <div className="flex items-center gap-1 text-sm text-red-500">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{errors.email}</span>
                </div>
              )}
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                סיסמה <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="password" type={showPassword ? 'text' : 'password'} value={password}
                  onChange={(e) => { setPassword(e.target.value); setErrors(prev => { const n = {...prev}; delete n.password; return n; }); }}
                  placeholder="לפחות 8 תווים"
                  className={`w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${errors.password ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
                />
                <button type="button" onClick={() => setShowPassword(p => !p)}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 touch-manipulation" tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {errors.password && (
                <div className="flex items-center gap-1 text-sm text-red-500">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{errors.password}</span>
                </div>
              )}
              <div className="text-left">
                <a href="/forgot-password" className="text-sm text-amber-600 hover:text-amber-700 font-medium">
                  שכחתי סיסמה?
                </a>
              </div>
            </div>
            <Button type="submit"
              className="w-full h-12 text-base font-medium mt-6 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  מתחבר...
                </span>
              ) : 'התחבר'}
            </Button>
          </form>
        )}

        <div className="mt-4 text-center">
          <p className="text-sm text-slate-500">
            אין לך חשבון?{' '}
            <button type="button" onClick={() => navigate(ENABLE_REGISTER_MANAGEMENT_REDIRECTS ? '/register-management' : '/onboarding')} className="text-amber-600 hover:text-amber-700 font-medium">
              הרשמה
            </button>
          </p>
        </div>

        {quickLoginEnabled && (
          <div className="mt-6 pt-5 border-t border-slate-200">
            <p className="text-xs text-slate-500 font-medium text-center mb-3">כניסה מהירה לדמו</p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_ACCOUNTS.map(account => (
                <button key={account.email} onClick={() => handleDemoLogin(account)} disabled={loading}
                  className={`px-2 py-2 rounded-lg text-xs font-medium border transition-all hover:shadow-sm touch-manipulation ${roleColors[account.role]}`}
                >
                  {account.label}
                </button>
              ))}
            </div>
            {appMode === 'dev' && (
              <div className="mt-3">
                <button onClick={() => handleDemoLogin(SUPER_ADMIN_ACCOUNT)} disabled={loading}
                  className={`w-full px-2 py-2 rounded-lg text-xs font-medium border transition-all hover:shadow-sm touch-manipulation ${roleColors.super_admin}`}
                >
                  {SUPER_ADMIN_ACCOUNT.label}
                </button>
              </div>
            )}
          </div>
        )}

        {gitSha && (
          <p className="text-center text-[10px] text-slate-300 mt-4">v{gitSha}</p>
        )}
      </Card>
    </div>
  );
};

export default LoginPage;
