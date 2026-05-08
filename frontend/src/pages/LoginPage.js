import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { onboardingService, BACKEND_URL } from '../services/api';
import { toast } from 'sonner';
import { Eye, EyeOff, Phone, ArrowRight, Loader2, Mail, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { canonicalE164, isValidIsraeliMobile } from '../utils/phoneUtils';
import { Capacitor } from '@capacitor/core';
import { SignInWithApple } from '@capacitor-community/apple-sign-in';
import useOtpAutofill from '../hooks/useOtpAutofill';
import useAndroidSmsRetriever from '../hooks/useAndroidSmsRetriever';

const ENABLE_REGISTER_MANAGEMENT_REDIRECTS =
  process.env.REACT_APP_ENABLE_REGISTER_MANAGEMENT_REDIRECTS === 'true';

const SHOW_DEV_LOGIN = process.env.REACT_APP_ENABLE_DEV_LOGIN === 'true';

let DEMO_ACCOUNTS = [];
let SUPER_ADMIN_ACCOUNT = null;
if (process.env.REACT_APP_ENABLE_DEV_LOGIN === 'true') {
  DEMO_ACCOUNTS = [
    { email: 'pm@contractor-ops.com', password: 'pm123', label: 'מנהל פרויקט', role: 'project_manager' },
    { email: 'sitemanager@contractor-ops.com', password: 'mgmt123', label: 'צוות ניהולי', role: 'management_team' },
    { email: 'contractor1@contractor-ops.com', password: 'cont123', label: 'קבלן', role: 'contractor' },
    { email: 'viewer@contractor-ops.com', password: 'view123', label: 'צופה', role: 'viewer' },
  ];
  SUPER_ADMIN_ACCOUNT = { email: 'superadmin@brikops.dev', password: 'super123', label: 'Super Admin', role: 'super_admin' };
}

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

  const [appMode, setAppMode] = useState(SHOW_DEV_LOGIN ? 'dev' : '');

  const [quickLoginEnabled, setQuickLoginEnabled] = useState(SHOW_DEV_LOGIN);
  const [onboardingEnabled, setOnboardingEnabled] = useState(null);

  const googleButtonRef = useRef(null);
  // 2026-05-08 — ToS consent (Israeli Spam Law). MANDATORY checkbox.
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [socialFlow, setSocialFlow] = useState(null);
  const [socialSessionToken, setSocialSessionToken] = useState('');
  const [socialPhoneMasked, setSocialPhoneMasked] = useState('');
  const [socialPhone, setSocialPhone] = useState('');
  const [socialOtp, setSocialOtp] = useState('');
  const [socialLoading, setSocialLoading] = useState(false);

  useOtpAutofill(setOtpCode);
  useOtpAutofill(setSocialOtp);
  useAndroidSmsRetriever(setOtpCode);
  useAndroidSmsRetriever(setSocialOtp);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/config/features`)
      .then(r => r.json())
      .then(d => {
        setOnboardingEnabled(d.feature_flags?.onboarding_v2 === true);
      })
      .catch(() => { setOnboardingEnabled(false); });
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
      document.cookie = 'brikops_logged_in=1; domain=.brikops.com; path=/; max-age=2592000; SameSite=Lax; Secure';
      const intended = sessionStorage.getItem('intendedPath');
      if (intended) {
        sessionStorage.removeItem('intendedPath');
        window.location.href = intended;
      } else {
        window.location.href = '/projects';
      }
    } catch (error) {
      toast.error('אירעה שגיאה. נסה שוב.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (document.getElementById('google-gsi-script')) return;
    const script = document.createElement('script');
    script.id = 'google-gsi-script';
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    document.head.appendChild(script);
  }, []);

  const handleSocialAuthResult = useCallback(async (result) => {
    if (result.status === 'authenticated') {
      loginWithOtp(result.token, result.user);
      toast.success('התחברת בהצלחה!');
      const intended = sessionStorage.getItem('intendedPath');
      if (intended) {
        sessionStorage.removeItem('intendedPath');
        navigate(intended);
      } else {
        navigate('/projects');
      }
      return;
    }

    if (result.status === 'pending_approval') {
      toast.info(result.message || 'מחכה לאישור מנהל פרויקט');
      navigate('/pending');
      return;
    }

    if (result.status === 'rejected') {
      toast.error(result.message || 'הבקשה נדחתה');
      return;
    }

    if (result.status === 'link_required') {
      setSocialSessionToken(result.session_token);
      setSocialPhoneMasked(result.phone_masked);
      setSocialFlow('link');
      try {
        await onboardingService.socialSendOtp(result.session_token);
        toast.info('קוד אימות נשלח לטלפון הרשום');
      } catch (err) {
        toast.error(err.response?.data?.detail || 'שגיאה בשליחת קוד');
      }
      return;
    }

    if (result.status === 'registration_required') {
      setSocialSessionToken(result.session_token);
      setSocialFlow('register');
      return;
    }

    toast.error('תגובה לא צפויה');
  }, [loginWithOtp, navigate]);

  const handleGoogleSignIn = useCallback(() => {
    setSocialLoading(true);

    if (!window.google?.accounts?.id) {
      toast.error('שירות Google לא זמין כרגע');
      setSocialLoading(false);
      return;
    }

    const googleClientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;
    if (!googleClientId) {
      toast.error('שירות Google לא מוגדר');
      setSocialLoading(false);
      return;
    }

    window.google.accounts.id.initialize({
      client_id: googleClientId,
      callback: async (response) => {
        try {
          const result = await onboardingService.socialAuth('google', response.credential);
          await handleSocialAuthResult(result);
        } catch (error) {
          const detail = error.response?.data?.detail;
          if (typeof detail === 'object' && detail.code === 'pending_deletion') {
            navigate('/account/pending-deletion');
            return;
          }
          toast.error(typeof detail === 'string' ? detail : 'אימות Google נכשל');
        } finally {
          setSocialLoading(false);
        }
      },
    });

    const container = googleButtonRef.current;
    if (container) {
      container.innerHTML = '';
      window.google.accounts.id.renderButton(container, {
        theme: 'outline',
        size: 'large',
        width: 300,
      });
      const btn = container.querySelector('div[role="button"]');
      if (btn) {
        btn.click();
      } else {
        setTimeout(() => {
          const retryBtn = container.querySelector('div[role="button"]');
          if (retryBtn) retryBtn.click();
          else setSocialLoading(false);
        }, 50);
      }
    } else {
      setSocialLoading(false);
    }
  }, [navigate, handleSocialAuthResult]);

  const handleAppleSignIn = useCallback(async () => {
    setSocialLoading(true);

    try {
      let idToken;
      let appleName = null;

      if (Capacitor.getPlatform() === 'ios') {
        // iOS native — Face ID / Touch ID sheet
        const nonce = (window.crypto?.randomUUID?.())
          || (Math.random().toString(36).slice(2) + Date.now().toString(36));
        const nativeResult = await SignInWithApple.authorize({
          clientId: 'com.brikops.app',
          redirectURI: '',
          scopes: 'email name',
          state: '',
          nonce,
        });
        idToken = nativeResult.response.identityToken;
        if (nativeResult.response.givenName || nativeResult.response.familyName) {
          appleName = `${nativeResult.response.givenName || ''} ${nativeResult.response.familyName || ''}`.trim();
        }
      } else {
        // Web flow — UNCHANGED. Do NOT modify anything inside this else block.
        if (!window.AppleID) {
          await new Promise((resolve, reject) => {
            if (document.getElementById('apple-signin-script')) {
              const check = setInterval(() => {
                if (window.AppleID) { clearInterval(check); resolve(); }
              }, 100);
              setTimeout(() => { clearInterval(check); reject(new Error('timeout')); }, 5000);
            } else {
              const script = document.createElement('script');
              script.id = 'apple-signin-script';
              script.src = 'https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js';
              script.onload = resolve;
              script.onerror = reject;
              document.head.appendChild(script);
            }
          });
        }

        const appleServicesId = process.env.REACT_APP_APPLE_SERVICES_ID;
        if (!appleServicesId) {
          toast.error('שירות Apple לא מוגדר');
          setSocialLoading(false);
          return;
        }

        window.AppleID.auth.init({
          clientId: appleServicesId,
          scope: 'name email',
          redirectURI: window.location.origin + '/login',
          usePopup: true,
        });

        const response = await window.AppleID.auth.signIn();
        idToken = response.authorization.id_token;
        appleName = response.user
          ? `${response.user.name?.firstName || ''} ${response.user.name?.lastName || ''}`.trim()
          : null;
      }

      const result = await onboardingService.socialAuth('apple', idToken, appleName);
      await handleSocialAuthResult(result);
    } catch (error) {
      if (error.error === 'popup_closed_by_user' || error.code === '1001') {
        // User cancelled — do nothing. 1001 is iOS user cancel.
      } else {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'object' && detail.code === 'pending_deletion') {
          navigate('/account/pending-deletion');
          return;
        }
        toast.error(typeof detail === 'string' ? detail : 'אימות Apple נכשל');
      }
    } finally {
      setSocialLoading(false);
    }
  }, [navigate, handleSocialAuthResult]);

  const handleSocialSendOtp = useCallback(async (e) => {
    e.preventDefault();
    const e164 = canonicalE164(socialPhone);
    if (!isValidIsraeliMobile(e164)) {
      toast.error('מספר טלפון נייד ישראלי לא תקין');
      return;
    }
    setSocialLoading(true);
    try {
      const result = await onboardingService.socialSendOtp(socialSessionToken, e164);
      setSocialPhoneMasked(result.phone_masked);
      setSocialFlow('otp');
      toast.info('קוד אימות נשלח');
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'object' && detail.code === 'pending_deletion') {
        navigate('/account/pending-deletion');
        return;
      }
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בשליחת קוד');
    } finally {
      setSocialLoading(false);
    }
  }, [socialPhone, socialSessionToken, navigate]);

  const handleSocialVerifyOtp = useCallback(async (e) => {
    e.preventDefault();
    if (socialOtp.length !== 6) {
      toast.error('יש להזין קוד בן 6 ספרות');
      return;
    }
    setSocialLoading(true);
    try {
      // 2026-05-08 — ToS consent gate (Israeli Spam Law).
      if (!termsAccepted) {
        toast.error('יש לאשר את תנאי השימוש');
        setSocialLoading(false);
        return;
      }
      const result = await onboardingService.socialVerifyOtp(socialSessionToken, socialOtp, termsAccepted);
      if (result.status === 'authenticated' && result.token) {
        loginWithOtp(result.token, result.user);
        toast.success('התחברת בהצלחה!');
        const intended = sessionStorage.getItem('intendedPath');
        if (intended) {
          sessionStorage.removeItem('intendedPath');
          navigate(intended);
        } else {
          navigate('/projects');
        }
      } else if (result.status === 'pending_approval') {
        toast.info(result.message);
        navigate('/pending');
      } else if (result.status === 'rejected') {
        toast.error(result.message);
      } else {
        toast.error('תגובה לא צפויה');
      }
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'object' && detail.code === 'pending_deletion') {
        navigate('/account/pending-deletion');
        return;
      }
      toast.error(typeof detail === 'string' ? detail : 'קוד אימות שגוי');
    } finally {
      setSocialLoading(false);
    }
  }, [socialOtp, socialSessionToken, loginWithOtp, navigate, termsAccepted]);

  const handleSocialBack = useCallback(() => {
    setSocialFlow(null);
    setSocialSessionToken('');
    setSocialOtp('');
    setSocialPhone('');
    setSocialPhoneMasked('');
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl relative z-10">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo-orange.png" alt="BrikOps" style={{ height: 48, marginBottom: 12 }} />
          <p className="text-slate-500 text-sm mt-1">ניהול משימות קבלן</p>
        </div>

        {!socialFlow && (
        <>
        <div className="flex gap-2 mb-6 p-1 bg-slate-100 rounded-lg" role="tablist">
          <button type="button" role="tab" id="tab-phone" aria-selected={authMethod === 'phone'} aria-controls="tabpanel-phone"
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-all touch-manipulation flex items-center justify-center gap-1.5 ${
              authMethod === 'phone' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
            onClick={() => { setAuthMethod('phone'); setErrors({}); }}
          >
            <Phone className="w-4 h-4" />
            טלפון
          </button>
          <button type="button" role="tab" id="tab-email" aria-selected={authMethod === 'email'} aria-controls="tabpanel-email"
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
          <div role="tabpanel" id="tabpanel-phone" aria-labelledby="tab-phone">
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
            <div className="text-left mt-2">
              <a href="/forgot-password" className="text-sm text-amber-600 hover:text-amber-700 font-medium">
                שכחתי סיסמה?
              </a>
            </div>
          </form>
          </div>
        )}

        {authMethod === 'phone' && phoneStep === 'otp' && (
          <div role="tabpanel" id="tabpanel-phone" aria-labelledby="tab-phone">
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
                autoComplete="one-time-code"
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
          </div>
        )}

        {authMethod === 'email' && (
          <div role="tabpanel" id="tabpanel-email" aria-labelledby="tab-email">
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
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 touch-manipulation"
                  aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'}
                  aria-pressed={showPassword}
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
          </div>
        )}

        </>
        )}

        {!socialFlow && (
          <>
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-white px-3 text-slate-400">או התחבר עם</span>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={socialLoading}
                className="flex-1 h-11 flex items-center justify-center gap-2 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors text-sm font-medium text-slate-700 disabled:opacity-50 touch-manipulation"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Google
              </button>

              <button
                type="button"
                onClick={handleAppleSignIn}
                disabled={socialLoading}
                className="flex-1 h-11 flex items-center justify-center gap-2 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium disabled:opacity-50 touch-manipulation"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
                </svg>
                Apple
              </button>
            </div>
            <div ref={googleButtonRef} className="hidden" />
          </>
        )}

        {socialFlow === 'link' && (
          <form onSubmit={handleSocialVerifyOtp} className="space-y-4" dir="rtl">
            <button
              type="button"
              onClick={handleSocialBack}
              className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-2"
            >
              <ArrowRight className="w-4 h-4" />
              חזרה
            </button>
            <div className="text-center mb-4">
              <p className="text-sm text-slate-600">
                מצאנו חשבון קיים. קוד אימות נשלח למספר
              </p>
              <bdi dir="ltr" className="font-mono text-base font-medium text-slate-900 mt-1 inline-block">
                {socialPhoneMasked}
              </bdi>
            </div>
            <div className="space-y-2">
              <label htmlFor="social-otp" className="block text-sm font-medium text-slate-700">
                קוד אימות
                <span className="text-red-500 mr-1">*</span>
              </label>
              <input
                id="social-otp"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={socialOtp}
                onChange={(e) => setSocialOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="w-full h-14 px-3 py-2 text-center text-2xl tracking-[0.5em] text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-300"
                autoFocus
              />
            </div>
            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-4 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={socialLoading}
            >
              {socialLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  מאמת...
                </span>
              ) : 'אימות והתחברות'}
            </Button>
          </form>
        )}

        {socialFlow === 'register' && (
          <form onSubmit={handleSocialSendOtp} className="space-y-4" dir="rtl">
            <button
              type="button"
              onClick={handleSocialBack}
              className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-2"
            >
              <ArrowRight className="w-4 h-4" />
              חזרה
            </button>
            <div className="text-center mb-4">
              <p className="text-sm text-slate-600">
                להשלמת ההרשמה, הזן מספר טלפון נייד
              </p>
            </div>
            <div className="space-y-2">
              <label htmlFor="social-phone" className="block text-sm font-medium text-slate-700">
                מספר טלפון
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
                  id="social-phone"
                  type="tel"
                  value={socialPhone}
                  onChange={(e) => setSocialPhone(e.target.value)}
                  placeholder="050-1234567"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                />
                <Phone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>
            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-4 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={socialLoading}
            >
              {socialLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  שולח קוד...
                </span>
              ) : 'שלח קוד אימות'}
            </Button>
            {/* 2026-05-08 — ToS consent (Israeli Spam Law). MANDATORY. */}
            <div className="flex items-start gap-2 pt-2">
              <input
                id="login-social-terms"
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="mt-1 h-4 w-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500"
              />
              <label htmlFor="login-social-terms" className="text-xs text-slate-700">
                אני מאשר/ת את <a href="/legal/terms.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">תנאי השימוש</a> ואת <a href="/legal/privacy.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">מדיניות הפרטיות</a>
              </label>
            </div>
          </form>
        )}

        {socialFlow === 'otp' && (
          <form onSubmit={handleSocialVerifyOtp} className="space-y-4" dir="rtl">
            <button
              type="button"
              onClick={() => setSocialFlow('register')}
              className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-2"
            >
              <ArrowRight className="w-4 h-4" />
              חזרה
            </button>
            <div className="text-center mb-4">
              <p className="text-sm text-slate-600">קוד אימות נשלח למספר</p>
              <bdi dir="ltr" className="font-mono text-base font-medium text-slate-900 mt-1 inline-block">
                {socialPhoneMasked}
              </bdi>
            </div>
            <div className="space-y-2">
              <label htmlFor="social-verify-otp" className="block text-sm font-medium text-slate-700">
                קוד אימות
                <span className="text-red-500 mr-1">*</span>
              </label>
              <input
                id="social-verify-otp"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={socialOtp}
                onChange={(e) => setSocialOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="w-full h-14 px-3 py-2 text-center text-2xl tracking-[0.5em] text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-300"
                autoFocus
              />
            </div>
            <Button
              type="submit"
              className="w-full h-12 text-base font-medium mt-4 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
              disabled={socialLoading}
            >
              {socialLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  מאמת...
                </span>
              ) : 'אימות והתחברות'}
            </Button>
          </form>
        )}

        {!socialFlow && (
          <>
            <div className="mt-4 text-center">
              <p className="text-sm text-slate-500">
                אין לך חשבון?{' '}
                <button type="button" onClick={() => navigate(ENABLE_REGISTER_MANAGEMENT_REDIRECTS ? '/register-management' : '/onboarding?mode=register')} className="text-amber-600 hover:text-amber-700 font-medium">
                  הרשמה
                </button>
              </p>
            </div>

            <div className="mt-3 text-center">
              <a href="/accessibility" className="text-xs text-slate-400 hover:text-amber-600 transition-colors">
                הצהרת נגישות
              </a>
            </div>

            {SHOW_DEV_LOGIN && quickLoginEnabled && (
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
                {appMode === 'dev' && SUPER_ADMIN_ACCOUNT && (
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
          </>
        )}
      </Card>
    </div>
  );
};

export default LoginPage;
