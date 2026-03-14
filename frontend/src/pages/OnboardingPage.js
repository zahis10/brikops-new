import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { onboardingService, BACKEND_URL } from '../services/api';
import { toast } from 'sonner';
import {
  HardHat, Phone, ArrowRight, ArrowLeft, Loader2, Eye, EyeOff,
  Building2, Users, KeyRound, CheckCircle2, AlertCircle, Mail
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { canonicalE164, isValidIsraeliMobile } from '../utils/phoneUtils';
import { navigateToProject } from '../utils/navigation';

const OnboardingPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { loginWithOtp, token: authToken } = useAuth();

  const inviteToken = searchParams.get('invite') || '';
  const isInviteFlow = !!inviteToken;

  const incomingPhone = location.state?.phone || '';
  const [step, setStep] = useState(incomingPhone ? 'choose-path' : 'phone');
  const [phone, setPhone] = useState(incomingPhone || '');
  const [otpCode, setOtpCode] = useState('');
  const [phoneE164, setPhoneE164] = useState(incomingPhone || '');
  const [phoneVerified, setPhoneVerified] = useState(!!incomingPhone);

  const [path, setPath] = useState(null);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [orgName, setOrgName] = useState('');
  const [projectName, setProjectName] = useState('');
  const [password, setPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [joinCode, setJoinCode] = useState(searchParams.get('code') || '');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLang, setInviteLang] = useState('he');

  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedInvite, setSelectedInvite] = useState(null);

  const [onboardingEnabled, setOnboardingEnabled] = useState(null);

  const [inviteInfo, setInviteInfo] = useState(null);
  const [inviteError, setInviteError] = useState(null);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const countdownRef = useRef(null);

  const validatePassword = useCallback((pw) => {
    const common = new Set(['123456', '1234567', '12345678', '123456789', '1234567890', '111111', '000000', 'password', 'qwerty', 'abcdef', 'abcd1234', 'password1', 'abc123', 'admin123', '11111111']);
    if (!pw || pw.length < 8) return 'סיסמה נדרשת (לפחות 8 תווים)';
    if (!/[a-zA-Zא-ת]/.test(pw)) return 'סיסמה חייבת לכלול לפחות אות אחת';
    if (!/[0-9]/.test(pw)) return 'סיסמה חייבת לכלול לפחות מספר אחד';
    if (common.has(pw.toLowerCase())) return 'סיסמה זו נפוצה מדי, יש לבחור סיסמה חזקה יותר';
    return '';
  }, []);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/config/features`)
      .then(r => r.json())
      .then(d => {
        setOnboardingEnabled(d.feature_flags?.onboarding_v2 === true);
      })
      .catch(() => setOnboardingEnabled(false));
  }, []);

  useEffect(() => {
    if (incomingPhone && phoneVerified && !isInviteFlow) {
      onboardingService.getOnboardingStatus(incomingPhone)
        .then(statusData => setStatus(statusData))
        .catch(() => {});
    }
  }, [incomingPhone, phoneVerified, isInviteFlow]);

  useEffect(() => {
    if (isInviteFlow && authToken && !inviteInfo && !inviteError) {
      setInviteLoading(true);
      onboardingService.getInviteInfo(inviteToken)
        .then(info => {
          setInviteInfo(info);
          setSelectedInvite({ invite_id: info.invite_id, project_name: info.project_name, role: info.role });
          setStep('invite-accept');
        })
        .catch(err => {
          const detail = err.response?.data?.detail || 'ההזמנה לא נמצאה או שפגה תוקפה';
          setInviteError(detail);
          setStep('invite-error');
        })
        .finally(() => setInviteLoading(false));
    }
  }, [isInviteFlow, authToken, inviteToken, inviteInfo, inviteError]);

  useEffect(() => {
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  const startResendCountdown = useCallback(() => {
    setResendCountdown(90);
    if (countdownRef.current) clearInterval(countdownRef.current);
    countdownRef.current = setInterval(() => {
      setResendCountdown(prev => {
        if (prev <= 1) {
          clearInterval(countdownRef.current);
          countdownRef.current = null;
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
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
      console.log('[OTP-DEBUG] OnboardingPage handleRequestOtp result:', res);
      setPhoneE164(e164);
      setStep('otp');
      startResendCountdown();
      toast('שולחים קוד אימות...', { icon: '📱' });
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.message;
      if (status === 429) {
        toast.error(typeof detail === 'string' ? detail : 'יותר מדי בקשות. נסה שוב בעוד מספר דקות.');
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setPhoneE164(e164);
        setStep('otp');
        startResendCountdown();
        toast('שולחים קוד אימות, ייתכן עיכוב קצר...', { icon: '⏳' });
      } else if (status >= 500) {
        toast.error('שגיאה בשרת. נסה שוב בעוד רגע.');
      } else {
        console.error('[OTP-DEBUG] OnboardingPage error:', { status, detail, code: err.code, message: err.message });
        toast.error(typeof detail === 'string' ? detail : 'שגיאה בשליחת קוד');
      }
    } finally {
      setLoading(false);
    }
  }, [phone, startResendCountdown]);

  const handleResendOtp = useCallback(async () => {
    if (resendCountdown > 0 || !phoneE164) return;
    setLoading(true);
    try {
      await onboardingService.requestOtp(phoneE164);
      startResendCountdown();
      toast('שולחים קוד חדש...', { icon: '📱' });
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.message;
      if (status === 429) {
        toast.error(typeof detail === 'string' ? detail : 'יותר מדי בקשות.');
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        startResendCountdown();
        toast('שולחים קוד, ייתכן עיכוב קצר...', { icon: '⏳' });
      } else {
        toast.error(typeof detail === 'string' ? detail : 'שגיאה בשליחה חוזרת');
      }
    } finally {
      setLoading(false);
    }
  }, [phoneE164, resendCountdown, startResendCountdown]);

  const handleVerifyOtp = useCallback(async (e) => {
    e.preventDefault();
    if (!otpCode.trim() || otpCode.length < 4) {
      toast.error('יש להזין קוד אימות');
      return;
    }
    setLoading(true);
    try {
      const result = await onboardingService.verifyOtp(phoneE164, otpCode);
      if (result.token && result.user) {
        loginWithOtp(result.token, result.user, result.user?.platform_role);
        if (isInviteFlow) {
          return;
        }
        toast.success('התחברת בהצלחה!');
        navigate('/projects');
        return;
      }
      setPhoneVerified(true);
      if (isInviteFlow) {
        setStep('invite-login-needed');
        toast.success('טלפון אומת. יש ליצור חשבון כדי להמשיך.');
        return;
      }
      try {
        const statusData = await onboardingService.getOnboardingStatus(phoneE164);
        setStatus(statusData);
        if (statusData.has_account && statusData.has_org) {
          setStep('login-password');
        } else if (statusData.pending_invites?.length > 0) {
          setStep('choose-path');
        } else {
          setStep('choose-path');
        }
      } catch {
        setStep('choose-path');
      }
      toast.success('טלפון אומת בהצלחה');
    } catch (err) {
      const detail = err.response?.data?.detail || 'קוד לא תקין';
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [phoneE164, otpCode, loginWithOtp, navigate, isInviteFlow]);

  const handleLoginPassword = useCallback(async (e) => {
    e.preventDefault();
    if (!password) {
      toast.error('יש להזין סיסמה');
      return;
    }
    setLoading(true);
    try {
      const result = await onboardingService.loginPhone(phoneE164, password);
      if (result.token && result.user) {
        loginWithOtp(result.token, result.user, result.user?.platform_role);
        if (isInviteFlow) {
          return;
        }
        toast.success('התחברת בהצלחה!');
        navigate('/projects');
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'סיסמה שגויה';
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [phoneE164, password, loginWithOtp, navigate, isInviteFlow]);

  const handleCreateOrg = useCallback(async (e) => {
    e.preventDefault();
    if (!fullName || fullName.trim().length < 2) {
      toast.error('שם מלא נדרש (לפחות 2 תווים)');
      return;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      toast.error('כתובת אימייל נדרשת');
      return;
    }
    if (!orgName || orgName.trim().length < 2) {
      toast.error('שם ארגון נדרש (לפחות 2 תווים)');
      return;
    }
    if (!projectName || projectName.trim().length < 2) {
      toast.error('שם פרויקט נדרש (לפחות 2 תווים)');
      return;
    }
    const pwErr = validatePassword(password);
    if (pwErr) {
      setPasswordError(pwErr);
      toast.error(pwErr);
      return;
    }
    setPasswordError('');
    setLoading(true);
    try {
      const result = await onboardingService.createOrg({
        phone: phoneE164,
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        org_name: orgName.trim(),
        project_name: projectName.trim(),
        password,
      });
      if (result.success && result.token) {
        loginWithOtp(result.token, result.user, result.user?.platform_role);
        toast.success('הארגון נוצר בהצלחה! תקופת ניסיון 7 ימים.');
        if (result.project?.id) {
          localStorage.setItem('lastProjectId', result.project.id);
          navigate(`/projects/${result.project.id}/control?showQuickSetup=true`);
        } else {
          navigate('/projects');
        }
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה ביצירת ארגון';
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [phoneE164, fullName, email, orgName, projectName, password, validatePassword, loginWithOtp, navigate]);

  const handleAcceptInvite = useCallback(async (e) => {
    e.preventDefault();
    const invite = selectedInvite || inviteInfo || (inviteToken ? { invite_id: inviteToken } : null);
    if (!invite) {
      toast.error('יש לבחור הזמנה');
      return;
    }
    if (!fullName || fullName.trim().length < 2) {
      toast.error('שם מלא נדרש');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        invite_id: invite.invite_id,
        phone: phoneE164,
        full_name: fullName.trim(),
        password: password || undefined,
      };
      if (inviteEmail.trim()) payload.email = inviteEmail.trim();
      if (inviteLang && inviteLang !== 'he') payload.preferred_language = inviteLang;
      const result = await onboardingService.acceptInvite(payload);
      if (result.success && result.token) {
        loginWithOtp(result.token, result.user, result.user?.platform_role);
        if (result.org_name && result.project_name) {
          toast.success(`הצטרפת לארגון ${result.org_name} בפרויקט ${result.project_name}`);
        } else if (result.project_name) {
          toast.success(`הצטרפת לפרויקט ${result.project_name} בהצלחה!`);
        } else {
          toast.success('הצטרפת לפרויקט בהצלחה!');
        }
        if (result.effective_access === 'read_only' && result.org_id) {
          toast('הגישה מוגבלת כרגע — פנה למנהל הארגון להפעלת המנוי', { icon: 'ℹ️', duration: 6000 });
        }
        const projectId = result.project_id || invite.project_id;
        const memberRole = result.invite_role || invite.role || 'viewer';
        if (projectId) {
          navigateToProject({ id: projectId, my_role: memberRole }, navigate);
        } else {
          navigate('/projects');
        }
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בקבלת הזמנה';
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [selectedInvite, inviteInfo, inviteToken, phoneE164, fullName, password, inviteEmail, inviteLang, loginWithOtp, navigate]);

  const handleJoinByCode = useCallback(async (e) => {
    e.preventDefault();
    if (!joinCode.trim()) {
      toast.error('יש להזין קוד הצטרפות');
      return;
    }
    if (!fullName || fullName.trim().length < 2) {
      toast.error('שם מלא נדרש');
      return;
    }
    setLoading(true);
    try {
      const result = await onboardingService.joinByCode({
        join_code: joinCode.trim(),
        phone: phoneE164,
        full_name: fullName.trim(),
        password: password || undefined,
      });
      if (result.success) {
        toast.success(result.message || 'הבקשה נשלחה');
        navigate('/login');
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'קוד הצטרפות לא תקין';
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [joinCode, phoneE164, fullName, password, navigate]);

  if (onboardingEnabled === null) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
        <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
      </div>
    );
  }

  const isRegistrationIntent = new URLSearchParams(location.search).get('mode') === 'register';

  if (onboardingEnabled === false && !incomingPhone && !isRegistrationIntent && !isInviteFlow) {
    sessionStorage.removeItem('onboarding_phone');
    sessionStorage.removeItem('onboarding_step');
    navigate('/login', { replace: true });
    return null;
  }

  const renderHeader = () => (
    <div className="flex flex-col items-center mb-6">
      <div className="w-14 h-14 bg-amber-500 rounded-xl flex items-center justify-center mb-3 shadow-lg">
        <HardHat className="w-8 h-8 text-white" />
      </div>
      <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Rubik, sans-serif' }}>
        BrikOps
      </h1>
      <p className="text-slate-500 text-sm mt-1">
        {isInviteFlow ? 'הזמנה לפרויקט' : 'הרשמה למערכת'}
      </p>
    </div>
  );

  const renderInvitePhoneStep = () => (
    <div className="space-y-4" dir="rtl">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
        <Mail className="w-8 h-8 text-blue-500 mx-auto mb-2" />
        <p className="text-sm font-medium text-blue-800">
          יש לך הזמנה לפרויקט
        </p>
        <p className="text-xs text-blue-600 mt-1">
          התחבר כדי לצפות בפרטי ההזמנה ולהצטרף
        </p>
      </div>
      <form onSubmit={handleRequestOtp} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="onb-phone" className="block text-sm font-medium text-slate-700">
            מספר טלפון <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              id="onb-phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="050-1234567"
              className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              autoFocus
            />
            <Phone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
        </div>
        <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
          {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
          שלח קוד אימות
        </Button>
      </form>
      <div className="text-center mt-3">
        <button type="button" onClick={() => navigate('/login')} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
          יש לי כבר חשבון - התחברות
        </button>
      </div>
    </div>
  );

  const renderInviteAccept = () => {
    if (inviteLoading) {
      return (
        <div className="flex flex-col items-center py-8" dir="rtl">
          <Loader2 className="w-8 h-8 text-amber-500 animate-spin mb-4" />
          <p className="text-sm text-slate-500">טוען פרטי הזמנה...</p>
        </div>
      );
    }
    if (!inviteInfo) return null;
    return (
      <div className="space-y-4" dir="rtl">
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 text-center">
          <CheckCircle2 className="w-10 h-10 text-green-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-slate-900 mb-1">הוזמנת לפרויקט</h3>
          <p className="text-base font-semibold text-green-800">{inviteInfo.project_name}</p>
          <p className="text-sm text-slate-600 mt-1">תפקיד: {inviteInfo.role_display}</p>
        </div>

        <form onSubmit={handleAcceptInvite} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="invite-fullname" className="block text-sm font-medium text-slate-700">
              שם מלא <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="invite-fullname"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="ישראל ישראלי"
                className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                autoFocus
              />
              <Users className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="invite-password" className="block text-sm font-medium text-slate-700">
              סיסמה {!status?.has_account && <span className="text-red-500">*</span>}
            </label>
            <div className="relative">
              <input
                id="invite-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={status?.has_account ? 'השאר ריק לשמירת סיסמה קיימת' : 'לפחות 8 תווים, אות + מספר'}
                className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'} aria-pressed={showPassword}>
                {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="invite-email" className="block text-sm font-medium text-slate-700">
              כתובת אימייל (אופציונלי)
            </label>
            <div className="relative">
              <input
                id="invite-email"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="example@email.com"
                className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                dir="ltr"
              />
              <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            </div>
            <p className="text-xs text-slate-400">לשחזור סיסמה והתראות</p>
          </div>

          <div className="space-y-2">
            <label htmlFor="invite-lang" className="block text-sm font-medium text-slate-700">
              שפת WhatsApp
            </label>
            <select
              id="invite-lang"
              value={inviteLang}
              onChange={(e) => setInviteLang(e.target.value)}
              className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
            >
              <option value="he">עברית</option>
              <option value="en">English</option>
              <option value="ar">العربية</option>
              <option value="zh">中文</option>
            </select>
          </div>

          <Button type="submit" disabled={loading} className="w-full bg-green-600 hover:bg-green-700 text-white h-12 text-base font-bold">
            {loading ? <Loader2 className="w-5 h-5 animate-spin ml-2" /> : null}
            המשך לפרויקט
          </Button>
        </form>
      </div>
    );
  };

  const renderInviteError = () => (
    <div className="space-y-4 text-center" dir="rtl">
      <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
      <h3 className="text-lg font-bold text-slate-900">ההזמנה לא תקינה</h3>
      <p className="text-sm text-slate-600">{inviteError || 'ההזמנה לא נמצאה, פגה תוקפה, או שכבר טופלה.'}</p>
      <Button onClick={() => navigate('/login')} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
        חזרה להתחברות
      </Button>
    </div>
  );

  const renderInviteLoginNeeded = () => (
    <div className="space-y-4" dir="rtl">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
        <Mail className="w-8 h-8 text-blue-500 mx-auto mb-2" />
        <p className="text-sm font-medium text-blue-800">
          יש לך הזמנה לפרויקט. צור חשבון כדי להמשיך.
        </p>
      </div>
      <form onSubmit={handleAcceptInvite} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="join-fullname" className="block text-sm font-medium text-slate-700">
            שם מלא <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              id="join-fullname"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="ישראל ישראלי"
              className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              autoFocus
            />
            <Users className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
        </div>
        <div className="space-y-2">
          <label htmlFor="join-password" className="block text-sm font-medium text-slate-700">
            סיסמה <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              id="join-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="לפחות 8 תווים, אות + מספר"
              className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'} aria-pressed={showPassword}>
              {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          <label htmlFor="join-email" className="block text-sm font-medium text-slate-700">
            כתובת אימייל (אופציונלי)
          </label>
          <div className="relative">
            <input
              id="join-email"
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="example@email.com"
              className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              dir="ltr"
            />
            <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
          <p className="text-xs text-slate-400">לשחזור סיסמה והתראות</p>
        </div>

        <div className="space-y-2">
          <label htmlFor="join-lang" className="block text-sm font-medium text-slate-700">
            שפת WhatsApp
          </label>
          <select
            id="join-lang"
            value={inviteLang}
            onChange={(e) => setInviteLang(e.target.value)}
            className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
          >
            <option value="he">עברית</option>
            <option value="en">English</option>
            <option value="ar">العربية</option>
            <option value="zh">中文</option>
          </select>
        </div>

        <Button type="submit" disabled={loading} className="w-full bg-green-600 hover:bg-green-700 text-white h-12 text-base font-bold">
          {loading ? <Loader2 className="w-5 h-5 animate-spin ml-2" /> : null}
          צור חשבון והצטרף
        </Button>
      </form>
    </div>
  );

  const renderPhoneStep = () => (
    <form onSubmit={handleRequestOtp} className="space-y-4" dir="rtl">
      <div className="space-y-2">
        <label htmlFor="onb-phone" className="block text-sm font-medium text-slate-700">
          מספר טלפון <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <input
            id="onb-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="050-1234567"
            className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
            autoFocus
          />
          <Phone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        </div>
      </div>
      <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
        {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
        שלח קוד אימות
      </Button>
      <div className="text-center mt-3">
        <button type="button" onClick={() => navigate('/login')} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
          יש לי כבר חשבון - התחברות
        </button>
      </div>
    </form>
  );

  const renderOtpStep = () => (
    <form onSubmit={handleVerifyOtp} className="space-y-4" dir="rtl">
      <div className="text-center">
        <p className="text-sm text-slate-600">
          שולחים קוד אימות ל-<bdi dir="ltr" className="font-mono font-medium text-slate-900 inline-block">{phoneE164}</bdi>
        </p>
        <p className="text-xs text-slate-400 mt-1">הקוד יכול להגיע עד 60 שניות</p>
      </div>
      <div className="space-y-2">
        <label htmlFor="onb-otp" className="block text-sm font-medium text-slate-700">קוד אימות</label>
        <input
          id="onb-otp"
          type="text"
          value={otpCode}
          onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="123456"
          className="w-full h-11 px-3 py-2 text-center text-2xl tracking-[0.3em] text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
          autoFocus
        />
      </div>
      <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
        {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
        אימות
      </Button>
      <div className="text-center">
        {resendCountdown > 0 ? (
          <p className="text-sm text-slate-400">
            לא קיבלת? אפשר לשלוח שוב בעוד {resendCountdown} שניות
          </p>
        ) : (
          <button type="button" onClick={handleResendOtp} disabled={loading} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
            לא קיבלת קוד? שלח שוב
          </button>
        )}
      </div>
      <button type="button" onClick={() => { setStep('phone'); setOtpCode(''); setResendCountdown(0); if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; } }} className="w-full text-sm text-slate-500 hover:text-slate-700">
        <ArrowRight className="w-3 h-3 inline ml-1" />
        חזרה
      </button>
    </form>
  );

  const renderLoginPassword = () => (
    <form onSubmit={handleLoginPassword} className="space-y-4" dir="rtl">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 text-center">
        <CheckCircle2 className="w-4 h-4 inline ml-1" />
        נמצא חשבון קיים. הזן סיסמה להתחברות.
      </div>
      <div className="space-y-2">
        <label htmlFor="login-password" className="block text-sm font-medium text-slate-700">סיסמה</label>
        <div className="relative">
          <input
            id="login-password"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
            autoFocus
          />
          <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'} aria-pressed={showPassword}>
            {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
          </button>
        </div>
      </div>
      <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
        {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
        התחבר
      </Button>
    </form>
  );

  const renderChoosePath = () => (
    <div className="space-y-4" dir="rtl">
      <p className="text-sm text-slate-600 text-center mb-2">
        <CheckCircle2 className="w-4 h-4 inline ml-1 text-green-500" />
        הטלפון אומת בהצלחה. מה תרצה לעשות?
      </p>

      {status?.pending_invites?.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-700">הזמנות ממתינות:</h3>
          {status.pending_invites.map((inv) => (
            <button
              key={inv.invite_id}
              onClick={() => { setSelectedInvite(inv); setPath('invite'); setStep('details'); }}
              className="w-full p-3 border border-slate-200 rounded-lg hover:border-amber-400 hover:bg-amber-50 transition-colors text-right"
            >
              <div className="font-medium text-slate-900">{inv.project_name}</div>
              <div className="text-xs text-slate-500">תפקיד: {inv.role} {inv.sub_role ? `(${inv.sub_role})` : ''}</div>
            </button>
          ))}
        </div>
      )}

      <div className="border-t border-slate-200 pt-4 space-y-3">
        <button
          onClick={() => { setPath('new'); setStep('details'); }}
          className="w-full p-4 border-2 border-dashed border-slate-300 rounded-lg hover:border-amber-400 hover:bg-amber-50/50 transition-colors flex items-center gap-3"
        >
          <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center flex-shrink-0">
            <Building2 className="w-5 h-5 text-amber-600" />
          </div>
          <div className="text-right">
            <div className="font-medium text-slate-900">חשבון חדש + ארגון</div>
            <div className="text-xs text-slate-500">צור ארגון חדש עם תקופת ניסיון חינמית</div>
          </div>
        </button>

        <button
          onClick={() => { setPath('code'); setStep('details'); }}
          className="w-full p-4 border-2 border-dashed border-slate-300 rounded-lg hover:border-amber-400 hover:bg-amber-50/50 transition-colors flex items-center gap-3"
        >
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
            <KeyRound className="w-5 h-5 text-blue-600" />
          </div>
          <div className="text-right">
            <div className="font-medium text-slate-900">הצטרפות עם קוד</div>
            <div className="text-xs text-slate-500">קיבלת קוד הצטרפות מהמנהל? הזן אותו כאן</div>
          </div>
        </button>
      </div>
    </div>
  );

  const renderDetails = () => {
    const isNew = path === 'new';
    const isInvite = path === 'invite';
    const isCode = path === 'code';

    const title = isNew ? 'יצירת חשבון חדש' : isInvite ? 'קבלת הזמנה' : 'הצטרפות עם קוד';
    const subtitle = isNew ? 'מלא את הפרטים ליצירת ארגון חדש' :
      isInvite ? `הצטרפות לפרויקט: ${selectedInvite?.project_name}` :
      'הזן קוד הצטרפות שקיבלת מהמנהל';

    const handleSubmit = isNew ? handleCreateOrg : isInvite ? handleAcceptInvite : handleJoinByCode;

    return (
      <form onSubmit={handleSubmit} className="space-y-4" dir="rtl">
        <div className="mb-2">
          <h3 className="text-lg font-bold text-slate-900">{title}</h3>
          <p className="text-sm text-slate-500">{subtitle}</p>
        </div>

        {isCode && (
          <div className="space-y-2">
            <label htmlFor="onb-joincode" className="block text-sm font-medium text-slate-700">
              קוד הצטרפות <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="onb-joincode"
                type="text"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                placeholder="BRK-1234"
                className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400 font-mono"
                autoFocus
              />
              <KeyRound className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            </div>
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="onb-fullname" className="block text-sm font-medium text-slate-700">
            שם מלא <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              id="onb-fullname"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="ישראל ישראלי"
              className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              autoFocus={!isCode}
            />
            <Users className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
        </div>

        {isNew && (
          <>
            <div className="space-y-2">
              <label htmlFor="onb-email" className="block text-sm font-medium text-slate-700">אימייל <span className="text-red-500">*</span></label>
              <div className="relative">
                <input
                  id="onb-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@company.com"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  dir="ltr"
                />
                <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="onb-orgname" className="block text-sm font-medium text-slate-700">שם הארגון <span className="text-red-500">*</span></label>
              <div className="relative">
                <input
                  id="onb-orgname"
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="למשל: חברת בנייה א.ב"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                />
                <Building2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="onb-projectname" className="block text-sm font-medium text-slate-700">שם הפרויקט <span className="text-red-500">*</span></label>
              <div className="relative">
                <input
                  id="onb-projectname"
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="הפרויקט הראשון שלי"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                />
                <Building2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>
          </>
        )}

        <div className="space-y-2">
          <label htmlFor="onb-password" className="block text-sm font-medium text-slate-700">
            סיסמה {(isNew || !status?.has_account) && <span className="text-red-500">*</span>}
          </label>
          <div className="relative">
            <input
              id="onb-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => { setPassword(e.target.value); setPasswordError(''); }}
              placeholder={status?.has_account ? 'השאר ריק לשמירת סיסמה קיימת' : 'לפחות 8 תווים, אות + מספר'}
              className={`w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400 ${passwordError ? 'border-red-400' : 'border-slate-300'}`}
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'} aria-pressed={showPassword}>
              {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
            </button>
          </div>
          {passwordError && <p className="text-xs text-red-500 mt-1">{passwordError}</p>}
        </div>

        {isNew && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            <Building2 className="w-4 h-4 inline ml-1" />
            תקופת ניסיון חינמית של 7 ימים כוללת פרויקט אחד.
          </div>
        )}

        <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
          {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
          {isNew ? 'צור ארגון והתחל' : isInvite ? 'קבל הזמנה' : 'שלח בקשת הצטרפות'}
        </Button>

        <button
          type="button"
          onClick={() => { setStep('choose-path'); setPath(null); setSelectedInvite(null); }}
          className="w-full text-sm text-slate-500 hover:text-slate-700 flex items-center justify-center gap-1"
        >
          <ArrowRight className="w-3 h-3" />
          חזרה לבחירת נתיב
        </button>
      </form>
    );
  };

  const renderCurrentStep = () => {
    if (isInviteFlow) {
      if (step === 'invite-accept') return renderInviteAccept();
      if (step === 'invite-error') return renderInviteError();
      if (step === 'invite-login-needed') return renderInviteLoginNeeded();
      if (step === 'otp') return renderOtpStep();
      if (step === 'login-password') return renderLoginPassword();
      return renderInvitePhoneStep();
    }
    if (step === 'phone') return renderPhoneStep();
    if (step === 'otp') return renderOtpStep();
    if (step === 'login-password') return renderLoginPassword();
    if (step === 'choose-path') return renderChoosePath();
    if (step === 'details') return renderDetails();
    return null;
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl relative z-10">
        {renderHeader()}
        {renderCurrentStep()}
      </Card>
    </div>
  );
};

export default OnboardingPage;
