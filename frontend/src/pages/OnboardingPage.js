import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { onboardingService, BACKEND_URL } from '../services/api';
import { toast } from 'sonner';
import {
  Phone, ArrowRight, ArrowLeft, Loader2, Eye, EyeOff,
  Building2, Users, KeyRound, CheckCircle2, AlertCircle, Mail
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { canonicalE164, isValidIsraeliMobile } from '../utils/phoneUtils';
import { navigateToProject } from '../utils/navigation';
import { t } from '../i18n';
import { Capacitor } from '@capacitor/core';
import { SignInWithApple } from '@capacitor-community/apple-sign-in';

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
  const [totalUnits, setTotalUnits] = useState('');
  const [unitsError, setUnitsError] = useState('');
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

  const googleButtonRef = useRef(null);
  // 2026-05-08 — ToS consent (Israeli Spam Law). Mandatory checkbox on
  // all register/link forms; backend rejects with 400 if not true.
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [socialFlow, setSocialFlow] = useState(null);
  const [socialSessionToken, setSocialSessionToken] = useState('');
  const [socialPhoneMasked, setSocialPhoneMasked] = useState('');
  const [socialPhone, setSocialPhone] = useState('');
  const [socialOtp, setSocialOtp] = useState('');
  const [socialLoading, setSocialLoading] = useState(false);

  const validatePassword = useCallback((pw) => {
    const common = new Set(['123456', '1234567', '12345678', '123456789', '1234567890', '111111', '000000', 'password', 'qwerty', 'abcdef', 'abcd1234', 'password1', 'abc123', 'admin123', '11111111']);
    if (!pw || pw.length < 8) return t('onboarding', 'pw_min_length');
    if (!/[a-zA-Zא-ת]/.test(pw)) return t('onboarding', 'pw_letter');
    if (!/[0-9]/.test(pw)) return t('onboarding', 'pw_digit');
    if (common.has(pw.toLowerCase())) return t('onboarding', 'pw_common');
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
    if (isInviteFlow && inviteToken && !inviteInfo && !inviteError) {
      setInviteLoading(true);
      onboardingService.getInviteInfo(inviteToken)
        .then(info => {
          setInviteInfo(info);
          setSelectedInvite({ invite_id: info.invite_id, project_name: info.project_name, role: info.role });
          if (authToken) {
            setStep('invite-accept');
          }
        })
        .catch(err => {
          const detail = err.response?.data?.detail || t('onboarding', 'err_invite_not_found');
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
      // 2026-05-09 — invite-flow Google: handleSocialAuthResult was
      // called from renderInvitePhoneStep (step='invite-accept'-ish),
      // which doesn't render socialFlow='register' UI. Transition to
      // step='phone' so renderPhoneStep socialFlow='register' branch
      // shows the OTP UI. No-op for non-invite flows that already
      // started on step='phone'.
      setStep('phone');
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
          // 2026-05-08 — pass inviteToken so backend applies role/project on register.
          const result = await onboardingService.socialAuth('google', response.credential, null, inviteToken || null);
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
  }, [navigate, handleSocialAuthResult, inviteToken]);

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

      // 2026-05-08 — pass inviteToken so backend applies role/project on register.
      const result = await onboardingService.socialAuth('apple', idToken, appleName, inviteToken || null);
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
  }, [navigate, handleSocialAuthResult, inviteToken]);

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
    // 2026-05-08 — ToS consent gate (mandatory on both register + link).
    if (!termsAccepted) {
      toast.error('יש לאשר את תנאי השימוש');
      return;
    }
    setSocialLoading(true);
    try {
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
      toast.error(t('onboarding', 'err_phone_required'));
      return;
    }
    const e164 = canonicalE164(phone);
    if (!isValidIsraeliMobile(e164)) {
      toast.error(t('onboarding', 'err_phone_invalid'));
      return;
    }
    setLoading(true);
    try {
      const res = await onboardingService.requestOtp(e164);
      setPhoneE164(e164);
      setStep('otp');
      startResendCountdown();
      toast(t('onboarding', 'toast_sending_otp'), { icon: '📱' });
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.message;
      if (status === 429) {
        toast.error(typeof detail === 'string' ? detail : t('onboarding', 'err_too_many_requests'));
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setPhoneE164(e164);
        setStep('otp');
        startResendCountdown();
        toast(t('onboarding', 'toast_sending_delayed'), { icon: '⏳' });
      } else if (status >= 500) {
        toast.error(t('onboarding', 'err_server'));
      } else {
        console.error('[OTP-DEBUG] OnboardingPage error:', { status, detail, code: err.code, message: err.message });
        toast.error(typeof detail === 'string' ? detail : t('onboarding', 'err_otp_send'));
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
      toast(t('onboarding', 'toast_resending'), { icon: '📱' });
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.message;
      if (status === 429) {
        toast.error(typeof detail === 'string' ? detail : t('onboarding', 'err_too_many_requests'));
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        startResendCountdown();
        toast(t('onboarding', 'toast_resend_delayed'), { icon: '⏳' });
      } else {
        toast.error(typeof detail === 'string' ? detail : t('onboarding', 'err_resend'));
      }
    } finally {
      setLoading(false);
    }
  }, [phoneE164, resendCountdown, startResendCountdown]);

  const handleVerifyOtp = useCallback(async (e) => {
    e.preventDefault();
    if (!otpCode.trim() || otpCode.length < 4) {
      toast.error(t('onboarding', 'err_otp_required'));
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
        toast.success(t('onboarding', 'toast_logged_in'));
        navigate('/projects');
        return;
      }
      setPhoneVerified(true);
      if (isInviteFlow) {
        setStep('invite-login-needed');
        toast.success(t('onboarding', 'toast_phone_verified_create'));
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
      toast.success(t('onboarding', 'toast_phone_verified'));
    } catch (err) {
      const detail = err.response?.data?.detail || t('onboarding', 'err_otp_invalid');
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [phoneE164, otpCode, loginWithOtp, navigate, isInviteFlow]);

  const handleLoginPassword = useCallback(async (e) => {
    e.preventDefault();
    if (!password) {
      toast.error(t('onboarding', 'err_password_required'));
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
        toast.success(t('onboarding', 'toast_logged_in'));
        navigate('/projects');
      }
    } catch (err) {
      const detail = err.response?.data?.detail || t('onboarding', 'err_wrong_password');
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [phoneE164, password, loginWithOtp, navigate, isInviteFlow]);

  const handleCreateOrg = useCallback(async (e) => {
    e.preventDefault();
    if (!fullName || fullName.trim().length < 2) {
      toast.error(t('onboarding', 'err_name_required'));
      return;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      toast.error(t('onboarding', 'err_email_required'));
      return;
    }
    if (!orgName || orgName.trim().length < 2) {
      toast.error(t('onboarding', 'err_org_required'));
      return;
    }
    if (!projectName || projectName.trim().length < 2) {
      toast.error(t('onboarding', 'err_project_required'));
      return;
    }
    const unitsNum = parseInt(totalUnits, 10);
    if (!totalUnits || isNaN(unitsNum) || unitsNum < 1) {
      setUnitsError('חובה להזין כמות יחידות דיור (לפחות 1)');
      toast.error('חובה להזין כמות יחידות דיור (לפחות 1)');
      return;
    }
    setUnitsError('');
    const pwErr = validatePassword(password);
    if (pwErr) {
      setPasswordError(pwErr);
      toast.error(pwErr);
      return;
    }
    setPasswordError('');
    setLoading(true);
    try {
      // 2026-05-08 — ToS consent gate (Israeli Spam Law).
      if (!termsAccepted) {
        toast.error('יש לאשר את תנאי השימוש');
        setLoading(false);
        return;
      }
      const result = await onboardingService.createOrg({
        phone: phoneE164,
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        org_name: orgName.trim(),
        project_name: projectName.trim(),
        total_units: parseInt(totalUnits, 10),
        password,
        terms_accepted: termsAccepted,
      });
      if (result.success && result.token) {
        loginWithOtp(result.token, result.user, result.user?.platform_role);
        toast.success(t('onboarding', 'toast_org_created'));
        if (result.project?.id) {
          localStorage.setItem('lastProjectId', result.project.id);
          navigate(`/projects/${result.project.id}/control?showQuickSetup=true`);
        } else {
          navigate('/projects');
        }
      }
    } catch (err) {
      const detail = err.response?.data?.detail || t('onboarding', 'err_create_org');
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [phoneE164, fullName, email, orgName, projectName, totalUnits, password, validatePassword, loginWithOtp, navigate, termsAccepted]);

  const handleAcceptInvite = useCallback(async (e) => {
    e.preventDefault();
    const invite = selectedInvite || inviteInfo || (inviteToken ? { invite_id: inviteToken } : null);
    if (!invite) {
      toast.error(t('onboarding', 'err_invite_required'));
      return;
    }
    if (!fullName || fullName.trim().length < 2) {
      toast.error(t('onboarding', 'err_name_required_short'));
      return;
    }
    if (!authToken) {
      const pwError = validatePassword(password);
      if (pwError) {
        toast.error(pwError);
        return;
      }
    }
    setLoading(true);
    try {
      // 2026-05-08 — ToS consent gate (Israeli Spam Law).
      if (!termsAccepted) {
        toast.error('יש לאשר את תנאי השימוש');
        setLoading(false);
        return;
      }
      const payload = {
        invite_id: invite.invite_id,
        phone: phoneE164,
        full_name: fullName.trim(),
        password: password || undefined,
        terms_accepted: termsAccepted,
      };
      if (inviteEmail.trim()) payload.email = inviteEmail.trim();
      if (inviteLang) payload.preferred_language = inviteLang;
      const result = await onboardingService.acceptInvite(payload);
      if (result.success && result.token) {
        loginWithOtp(result.token, result.user, result.user?.platform_role);
        if (result.org_name && result.project_name) {
          toast.success(t('onboarding', 'toast_joined_org_project').replace('{org}', result.org_name).replace('{project}', result.project_name));
        } else if (result.project_name) {
          toast.success(t('onboarding', 'toast_joined_project').replace('{project}', result.project_name));
        } else {
          toast.success(t('onboarding', 'toast_joined_generic'));
        }
        if (result.effective_access === 'read_only' && result.org_id) {
          toast(t('onboarding', 'toast_access_limited'), { icon: 'ℹ️', duration: 6000 });
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
      const detail = err.response?.data?.detail || t('onboarding', 'err_accept_invite');
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }, [selectedInvite, inviteInfo, inviteToken, phoneE164, fullName, password, inviteEmail, inviteLang, loginWithOtp, navigate, authToken, validatePassword, termsAccepted]);

  const handleJoinByCode = useCallback(async (e) => {
    e.preventDefault();
    if (!joinCode.trim()) {
      toast.error(t('onboarding', 'err_join_code_required'));
      return;
    }
    if (!fullName || fullName.trim().length < 2) {
      toast.error(t('onboarding', 'err_name_required_short'));
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
        toast.success(result.message || t('onboarding', 'toast_request_sent'));
        navigate('/login');
      }
    } catch (err) {
      const detail = err.response?.data?.detail || t('onboarding', 'err_join_code_invalid');
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
      <img src="/logo-orange.png" alt="BrikOps" style={{ height: 48, marginBottom: 8 }} />
      <p className="text-slate-500 text-sm mt-1">
        {isInviteFlow ? t('onboarding', 'invite_title') : t('onboarding', 'register_title')}
      </p>
    </div>
  );

  const renderInvitePhoneStep = () => (
    <div className="space-y-4" dir="rtl">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
        <Mail className="w-8 h-8 text-blue-500 mx-auto mb-2" />
        <p className="text-sm font-medium text-blue-800">
          {t('onboarding', 'invite_has_invite')}
        </p>
        <p className="text-xs text-blue-600 mt-1">
          {t('onboarding', 'invite_login_hint')}
        </p>
      </div>
      <form onSubmit={handleRequestOtp} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="onb-phone" className="block text-sm font-medium text-slate-700">
            {t('onboarding', 'phone_label')} <span className="text-red-500">*</span>
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
        <Button type="submit" disabled={loading || !termsAccepted} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
          {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
          {t('onboarding', 'send_otp')}
        </Button>
      </form>

      {/* 2026-05-09 — ToS consent (Israeli Spam Law). Gates BOTH
           phone+OTP path (above) AND Google/Apple buttons (below).
           Same pattern as L869 in renderInviteAccept and L1193 in
           renderPhoneStep. */}
      <div className="flex items-start gap-2 pt-2">
        <input
          id="onb-invitelanding-terms"
          type="checkbox"
          checked={termsAccepted}
          onChange={(e) => setTermsAccepted(e.target.checked)}
          className="mt-1 h-4 w-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500"
        />
        <label htmlFor="onb-invitelanding-terms" className="text-xs text-slate-700">
          אני מאשר/ת את <a href="/legal/terms.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">תנאי השימוש</a> ואת <a href="/legal/privacy.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">מדיניות הפרטיות</a>
        </label>
      </div>

      {/* 2026-05-09 — SSO alternative path. Mirror of renderPhoneStep
           pattern. Backend phone-match check at
           onboarding_router.py:2137 enforces invite.target_phone == OTP'd
           phone, so security parity with existing phone+OTP path. */}
      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-3 text-slate-400">או הרשמה עם</span>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={socialLoading || !termsAccepted}
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
          disabled={socialLoading || !termsAccepted}
          className="flex-1 h-11 flex items-center justify-center gap-2 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium disabled:opacity-50 touch-manipulation"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
          </svg>
          Apple
        </button>
      </div>
      <div ref={googleButtonRef} className="hidden" />

      <div className="text-center mt-3">
        <button type="button" onClick={() => navigate('/login')} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
          {t('onboarding', 'have_account')}
        </button>
      </div>
    </div>
  );

  const renderInviteAccept = () => {
    if (inviteLoading) {
      return (
        <div className="flex flex-col items-center py-8" dir="rtl">
          <Loader2 className="w-8 h-8 text-amber-500 animate-spin mb-4" />
          <p className="text-sm text-slate-500">{t('onboarding', 'loading_invite')}</p>
        </div>
      );
    }
    if (!inviteInfo) return null;
    return (
      <div className="space-y-4" dir="rtl">
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 text-center">
          <CheckCircle2 className="w-10 h-10 text-green-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-slate-900 mb-1">{t('onboarding', 'invited_to_project')}</h3>
          <p className="text-base font-semibold text-green-800">{inviteInfo.project_name}</p>
          <p className="text-sm text-slate-600 mt-1">{t('onboarding', 'role_label')} {inviteInfo.role_display}</p>
        </div>

        <form onSubmit={handleAcceptInvite} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="invite-fullname" className="block text-sm font-medium text-slate-700">
              {t('onboarding', 'full_name')} <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="invite-fullname"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder={t('onboarding', 'name_placeholder')}
                className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                autoFocus
              />
              <Users className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="invite-password" className="block text-sm font-medium text-slate-700">
              {t('onboarding', 'password')} {!status?.has_account && <span className="text-red-500">*</span>}
            </label>
            <div className="relative">
              <input
                id="invite-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={status?.has_account ? t('onboarding', 'keep_existing_pw') : t('onboarding', 'pw_requirements')}
                className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? t('onboarding', 'hide_password') : t('onboarding', 'show_password')} aria-pressed={showPassword}>
                {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="invite-email" className="block text-sm font-medium text-slate-700">
              {t('onboarding', 'email_optional')}
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
            <p className="text-xs text-slate-400">{t('onboarding', 'email_recovery_hint')}</p>
          </div>

          <div className="space-y-2">
            <label htmlFor="invite-lang" className="block text-sm font-medium text-slate-700">
              {t('onboarding', 'wa_language')}
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

          {/* 2026-05-08 — ToS consent (Israeli Spam Law). MANDATORY. */}
          <div className="flex items-start gap-2 pt-2">
            <input
              id="onb-invite-terms"
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="mt-1 h-4 w-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500"
            />
            <label htmlFor="onb-invite-terms" className="text-xs text-slate-700">
              אני מאשר/ת את <a href="/legal/terms.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">תנאי השימוש</a> ואת <a href="/legal/privacy.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">מדיניות הפרטיות</a>
            </label>
          </div>

          <Button type="submit" disabled={loading} className="w-full bg-green-600 hover:bg-green-700 text-white h-12 text-base font-bold">
            {loading ? <Loader2 className="w-5 h-5 animate-spin ml-2" /> : null}
            {t('onboarding', 'continue_to_project')}
          </Button>
        </form>
      </div>
    );
  };

  const renderInviteError = () => (
    <div className="space-y-4 text-center" dir="rtl">
      <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
      <h3 className="text-lg font-bold text-slate-900">{t('onboarding', 'invite_invalid')}</h3>
      <p className="text-sm text-slate-600">{inviteError || t('onboarding', 'invite_error_desc')}</p>
      <Button onClick={() => navigate('/login')} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
        {t('onboarding', 'back_to_login')}
      </Button>
    </div>
  );

  const renderInviteLoginNeeded = () => (
    <div className="space-y-4" dir="rtl">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
        <Mail className="w-8 h-8 text-blue-500 mx-auto mb-2" />
        <p className="text-sm font-medium text-blue-800">
          {inviteInfo?.project_name
            ? t('onboarding', 'invite_create_account_for').replace('{project}', inviteInfo.project_name)
            : t('onboarding', 'invite_create_account')}
        </p>
        {inviteInfo?.role_display && (
          <p className="text-xs text-blue-600 mt-1">{t('onboarding', 'role_label')} {inviteInfo.role_display}</p>
        )}
      </div>
      <form onSubmit={handleAcceptInvite} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="join-fullname" className="block text-sm font-medium text-slate-700">
            {t('onboarding', 'full_name')} <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              id="join-fullname"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t('onboarding', 'name_placeholder')}
              className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              autoFocus
            />
            <Users className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
        </div>
        <div className="space-y-2">
          <label htmlFor="join-password" className="block text-sm font-medium text-slate-700">
            {t('onboarding', 'password')} <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              id="join-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('onboarding', 'pw_requirements')}
              className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? t('onboarding', 'hide_password') : t('onboarding', 'show_password')} aria-pressed={showPassword}>
              {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          <label htmlFor="join-email" className="block text-sm font-medium text-slate-700">
            {t('onboarding', 'email_optional')}
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
          <p className="text-xs text-slate-400">{t('onboarding', 'email_recovery_hint')}</p>
        </div>

        <div className="space-y-2">
          <label htmlFor="join-lang" className="block text-sm font-medium text-slate-700">
            {t('onboarding', 'wa_language')}
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

        {/* 2026-05-09 — Hotfix: ToS consent (Israeli Spam Law). MANDATORY.
             Was missing in initial 505 ship — broke new-contractor invite flow
             at the 400 gate in handleAcceptInvite L634. */}
        <div className="flex items-start gap-2 pt-2">
          <input
            id="onb-invite-newuser-terms"
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            className="mt-1 h-4 w-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500"
          />
          <label htmlFor="onb-invite-newuser-terms" className="text-xs text-slate-700">
            אני מאשר/ת את <a href="/legal/terms.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">תנאי השימוש</a> ואת <a href="/legal/privacy.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">מדיניות הפרטיות</a>
          </label>
        </div>

        <Button type="submit" disabled={loading || !termsAccepted} className="w-full bg-green-600 hover:bg-green-700 text-white h-12 text-base font-bold">
          {loading ? <Loader2 className="w-5 h-5 animate-spin ml-2" /> : null}
          {t('onboarding', 'create_and_join')}
        </Button>
      </form>
    </div>
  );

  const renderPhoneStep = () => (
    <div>
      {!socialFlow && (
        <form onSubmit={handleRequestOtp} className="space-y-4" dir="rtl">
          <div className="space-y-2">
            <label htmlFor="onb-phone" className="block text-sm font-medium text-slate-700">
              {t('onboarding', 'phone_label')} <span className="text-red-500">*</span>
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
          {/* 2026-05-08 — ToS consent (Israeli Spam Law). Initial screen — gates ALL register paths. */}
          <div className="flex items-start gap-2 mb-3">
            <input
              type="checkbox"
              id="onb-register-terms"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="mt-1 w-4 h-4"
            />
            <label htmlFor="onb-register-terms" className="text-xs text-slate-600">
              קראתי ואני מאשר/ת את{' '}
              <a href="/legal/terms.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 underline">
                תנאי השימוש
              </a>
              {' '}ואת{' '}
              <a href="/legal/privacy.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 underline">
                מדיניות הפרטיות
              </a>
            </label>
          </div>
          <Button type="submit" disabled={loading || !termsAccepted} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
            {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
            {t('onboarding', 'send_otp')}
          </Button>
        </form>
      )}

      {!socialFlow && (
        <>
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-white px-3 text-slate-400">או הרשמה עם</span>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={socialLoading || !termsAccepted}
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
              disabled={socialLoading || !termsAccepted}
              className="flex-1 h-11 flex items-center justify-center gap-2 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium disabled:opacity-50 touch-manipulation"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
              </svg>
              Apple
            </button>
          </div>
          <div ref={googleButtonRef} className="hidden" />

          <div className="text-center mt-3">
            <button type="button" onClick={() => navigate('/login')} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
              {t('onboarding', 'have_account')}
            </button>
          </div>
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
                autoFocus
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
              id="onb-social-terms"
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="mt-1 h-4 w-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500"
            />
            <label htmlFor="onb-social-terms" className="text-xs text-slate-700">
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
    </div>
  );

  const renderOtpStep = () => (
    <form onSubmit={handleVerifyOtp} className="space-y-4" dir="rtl">
      <div className="text-center">
        <p className="text-sm text-slate-600">
          {t('onboarding', 'otp_sent_to')} <bdi dir="ltr" className="font-mono font-medium text-slate-900 inline-block">{phoneE164}</bdi>
        </p>
        <p className="text-xs text-slate-400 mt-1">{t('onboarding', 'otp_delay_hint')}</p>
      </div>
      <div className="space-y-2">
        <label htmlFor="onb-otp" className="block text-sm font-medium text-slate-700">{t('onboarding', 'otp_label')}</label>
        <input
          id="onb-otp"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          value={otpCode}
          onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="123456"
          className="w-full h-11 px-3 py-2 text-center text-2xl tracking-[0.3em] text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
          autoFocus
        />
      </div>
      <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
        {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
        {t('onboarding', 'verify')}
      </Button>
      <div className="text-center">
        {resendCountdown > 0 ? (
          <p className="text-sm text-slate-400">
            {t('onboarding', 'resend_countdown').replace('{seconds}', resendCountdown)}
          </p>
        ) : (
          <button type="button" onClick={handleResendOtp} disabled={loading} className="text-sm text-amber-600 hover:text-amber-700 font-medium">
            {t('onboarding', 'resend_otp')}
          </button>
        )}
      </div>
      <button type="button" onClick={() => { setStep('phone'); setOtpCode(''); setResendCountdown(0); if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; } }} className="w-full text-sm text-slate-500 hover:text-slate-700">
        <ArrowRight className="w-3 h-3 inline ml-1" />
        {t('onboarding', 'back')}
      </button>
    </form>
  );

  const renderLoginPassword = () => (
    <form onSubmit={handleLoginPassword} className="space-y-4" dir="rtl">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 text-center">
        <CheckCircle2 className="w-4 h-4 inline ml-1" />
        {t('onboarding', 'existing_account_found')}
      </div>
      <div className="space-y-2">
        <label htmlFor="login-password" className="block text-sm font-medium text-slate-700">{t('onboarding', 'password')}</label>
        <div className="relative">
          <input
            id="login-password"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
            autoFocus
          />
          <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? t('onboarding', 'hide_password') : t('onboarding', 'show_password')} aria-pressed={showPassword}>
            {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
          </button>
        </div>
      </div>
      <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
        {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
        {t('onboarding', 'login')}
      </Button>
    </form>
  );

  const renderChoosePath = () => (
    <div className="space-y-4" dir="rtl">
      <p className="text-sm text-slate-600 text-center mb-2">
        <CheckCircle2 className="w-4 h-4 inline ml-1 text-green-500" />
        {t('onboarding', 'phone_verified_choose')}
      </p>

      {status?.pending_invites?.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-700">{t('onboarding', 'pending_invites')}</h3>
          {status.pending_invites.map((inv) => (
            <button
              key={inv.invite_id}
              onClick={() => { setSelectedInvite(inv); setPath('invite'); setStep('details'); }}
              className="w-full p-3 border border-slate-200 rounded-lg hover:border-amber-400 hover:bg-amber-50 transition-colors text-right"
            >
              <div className="font-medium text-slate-900">{inv.project_name}</div>
              <div className="text-xs text-slate-500">{t('onboarding', 'role_label')} {inv.role} {inv.sub_role ? `(${inv.sub_role})` : ''}</div>
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
            <div className="font-medium text-slate-900">{t('onboarding', 'new_account_org')}</div>
            <div className="text-xs text-slate-500">{t('onboarding', 'new_account_org_desc')}</div>
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
            <div className="font-medium text-slate-900">{t('onboarding', 'join_with_code')}</div>
            <div className="text-xs text-slate-500">{t('onboarding', 'join_with_code_desc')}</div>
          </div>
        </button>
      </div>
    </div>
  );

  const renderDetails = () => {
    const isNew = path === 'new';
    const isInvite = path === 'invite';
    const isCode = path === 'code';

    const title = isNew ? t('onboarding', 'create_new_account') : isInvite ? t('onboarding', 'accept_invite') : t('onboarding', 'join_with_code');
    const subtitle = isNew ? t('onboarding', 'fill_details_new_org') :
      isInvite ? `${t('onboarding', 'joining_project')} ${selectedInvite?.project_name}` :
      t('onboarding', 'enter_join_code_desc');

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
              {t('onboarding', 'join_code_label')} <span className="text-red-500">*</span>
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
            {t('onboarding', 'full_name')} <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              id="onb-fullname"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t('onboarding', 'name_placeholder')}
              className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
              autoFocus={!isCode}
            />
            <Users className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
        </div>

        {isNew && (
          <>
            <div className="space-y-2">
              <label htmlFor="onb-email" className="block text-sm font-medium text-slate-700">{t('onboarding', 'email_label')} <span className="text-red-500">*</span></label>
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
              <label htmlFor="onb-orgname" className="block text-sm font-medium text-slate-700">{t('onboarding', 'org_name_label')} <span className="text-red-500">*</span></label>
              <div className="relative">
                <input
                  id="onb-orgname"
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder={t('onboarding', 'org_name_placeholder')}
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                />
                <Building2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="onb-projectname" className="block text-sm font-medium text-slate-700">{t('onboarding', 'project_name_label')} <span className="text-red-500">*</span></label>
              <div className="relative">
                <input
                  id="onb-projectname"
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder={t('onboarding', 'project_name_placeholder')}
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                />
                <Building2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="onb-totalunits" className="block text-sm font-medium text-slate-700">
                כמות יחידות דיור <span className="text-red-500">*</span>
              </label>
              <input
                id="onb-totalunits"
                type="number"
                min="1"
                step="1"
                value={totalUnits}
                onChange={(e) => { setTotalUnits(e.target.value); setUnitsError(''); }}
                placeholder="למשל: 120"
                className={`w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400 ${unitsError ? 'border-red-500' : 'border-slate-300'}`}
              />
              {unitsError && <p className="text-xs text-red-500 mt-1">{unitsError}</p>}
              <p className="text-xs text-slate-500">מספר זה לקוח מהיתר הבנייה. אם אין לך עדיין — השג את המספר לפני יצירת הפרויקט.</p>
            </div>
          </>
        )}

        <div className="space-y-2">
          <label htmlFor="onb-password" className="block text-sm font-medium text-slate-700">
            {t('onboarding', 'password')} {(isNew || !status?.has_account) && <span className="text-red-500">*</span>}
          </label>
          <div className="relative">
            <input
              id="onb-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => { setPassword(e.target.value); setPasswordError(''); }}
              placeholder={status?.has_account ? t('onboarding', 'keep_existing_pw') : t('onboarding', 'pw_requirements')}
              className={`w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400 ${passwordError ? 'border-red-400' : 'border-slate-300'}`}
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute left-3 top-1/2 -translate-y-1/2" aria-label={showPassword ? t('onboarding', 'hide_password') : t('onboarding', 'show_password')} aria-pressed={showPassword}>
              {showPassword ? <EyeOff className="w-4 h-4 text-slate-400" /> : <Eye className="w-4 h-4 text-slate-400" />}
            </button>
          </div>
          {passwordError && <p className="text-xs text-red-500 mt-1">{passwordError}</p>}
        </div>

        {isInvite && (
          <>
            <div className="space-y-2">
              <label htmlFor="onb-invite-email" className="block text-sm font-medium text-slate-700">
                {t('onboarding', 'email_optional')}
              </label>
              <div className="relative">
                <input
                  id="onb-invite-email"
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="example@email.com"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  dir="ltr"
                />
                <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
              <p className="text-xs text-slate-400">{t('onboarding', 'email_recovery_hint')}</p>
            </div>

            <div className="space-y-2">
              <label htmlFor="onb-invite-lang" className="block text-sm font-medium text-slate-700">
                {t('onboarding', 'wa_language')}
              </label>
              <select
                id="onb-invite-lang"
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
          </>
        )}

        {isNew && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            <Building2 className="w-4 h-4 inline ml-1" />
            {t('onboarding', 'trial_info')}
          </div>
        )}

        <Button type="submit" disabled={loading} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
          {loading ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
          {isNew ? t('onboarding', 'create_org_start') : isInvite ? t('onboarding', 'accept_invite') : t('onboarding', 'send_join_request')}
        </Button>
        {/* 2026-05-08 — ToS consent (Israeli Spam Law). MANDATORY for create-org and accept-invite. */}
        <div className="flex items-start gap-2 pt-2">
          <input
            id="onb-org-terms"
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            className="mt-1 h-4 w-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500"
          />
          <label htmlFor="onb-org-terms" className="text-xs text-slate-700">
            אני מאשר/ת את <a href="/legal/terms.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">תנאי השימוש</a> ואת <a href="/legal/privacy.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">מדיניות הפרטיות</a>
          </label>
        </div>

        <button
          type="button"
          onClick={() => { setStep('choose-path'); setPath(null); setSelectedInvite(null); }}
          className="w-full text-sm text-slate-500 hover:text-slate-700 flex items-center justify-center gap-1"
        >
          <ArrowRight className="w-3 h-3" />
          {t('onboarding', 'back_to_path')}
        </button>
      </form>
    );
  };

  const renderCurrentStep = () => {
    // 2026-05-09 — 506 hotfix: when user clicks Google/Apple from the
    // invite landing screen, handleSocialAuthResult sets socialFlow=
    // 'link'/'register'. The OTP-input + phone-input UIs for SSO live
    // in renderPhoneStep, NOT in renderInvitePhoneStep. Without this
    // early return, the user gets stuck on the invite landing form
    // with no way to enter OTP after OAuth.
    if (socialFlow) return renderPhoneStep();
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
