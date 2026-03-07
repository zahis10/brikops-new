import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { onboardingService, BACKEND_URL } from '../services/api';
import { toast } from 'sonner';
import { HardHat, Phone, ArrowRight, Loader2, Mail, MessageCircle, CheckCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { canonicalE164, isValidIsraeliMobile } from '../utils/phoneUtils';

const RESEND_COOLDOWN = 90;

const PhoneLoginPage = () => {
  const [step, setStep] = useState('phone');
  const [phone, setPhone] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [phoneE164, setPhoneE164] = useState('');
  const [resendCountdown, setResendCountdown] = useState(0);
  const countdownRef = useRef(null);

  const { loginWithOtp } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  const startResendCountdown = useCallback(() => {
    setResendCountdown(RESEND_COOLDOWN);
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
      toast.error('יש להזין מספר נייד ישראלי תקין');
      return;
    }
    setLoading(true);
    try {
      const res = await onboardingService.requestOtp(e164);
      console.log('[OTP-DEBUG] PhoneLoginPage handleRequestOtp result:', res);
      setPhoneE164(e164);
      setStep('otp');
      startResendCountdown();
      toast('שולחים קוד אימות...', { icon: '📱' });
    } catch (error) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || error.message;
      if (status === 429) {
        const waitMatch = typeof detail === 'string' && detail.match(/(\d+)/);
        const waitSecs = waitMatch ? parseInt(waitMatch[1]) : 60;
        toast.error(`יותר מדי בקשות. נסה שוב בעוד ${waitSecs} שניות.`);
      } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        setPhoneE164(e164);
        setStep('otp');
        startResendCountdown();
        toast('שולחים קוד אימות, ייתכן עיכוב קצר...', { icon: '⏳' });
      } else if (status >= 500) {
        toast.error('שגיאה בשרת. נסה שוב בעוד רגע.');
      } else {
        console.error('[OTP-DEBUG] PhoneLoginPage error:', { status, detail, code: error.code, message: error.message });
        toast.error(typeof detail === 'string' ? detail : 'שגיאה בשליחת קוד אימות');
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
    } catch (error) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || error.message;
      if (status === 429) {
        toast.error(typeof detail === 'string' ? detail : 'יותר מדי בקשות. נסה שוב בעוד מספר דקות.');
      } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
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
    if (otpCode.length !== 6) {
      toast.error('יש להזין קוד בן 6 ספרות');
      return;
    }
    setLoading(true);
    try {
      const result = await onboardingService.verifyOtp(phoneE164, otpCode);

      if (result.requires_onboarding || result.next === 'onboarding') {
        navigate('/onboarding', { state: { phone: result.phone_e164 || phoneE164 } });
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
        navigate('/projects');
      } else {
        toast.error('תגובה לא צפויה מהשרת');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'קוד אימות שגוי');
    } finally {
      setLoading(false);
    }
  }, [otpCode, phoneE164, loginWithOtp, navigate]);

  const handleWhatsAppLogin = useCallback(async () => {
    if (!phone.trim()) {
      toast.error('יש להזין מספר טלפון');
      return;
    }
    const e164 = canonicalE164(phone);
    if (!isValidIsraeliMobile(e164)) {
      toast.error('יש להזין מספר נייד ישראלי תקין');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/wa/request-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: e164 }),
      });
      if (res.status === 429) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'נא לנסות שוב מאוחר יותר.');
        return;
      }
      if (!res.ok) {
        toast.error('שגיאה בשליחת קישור. נסה שוב.');
        return;
      }
      setPhoneE164(e164);
      setStep('waSuccess');
    } catch (error) {
      if (error.message?.includes('timeout')) {
        setPhoneE164(e164);
        setStep('waSuccess');
        toast('ייתכן עיכוב קצר בשליחה...', { icon: '⏳' });
      } else {
        toast.error('שגיאה בשליחת קישור. נסה שוב.');
      }
    } finally {
      setLoading(false);
    }
  }, [phone]);

  const handleBack = useCallback(() => {
    setStep('phone');
    setOtpCode('');
    setResendCountdown(0);
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
  }, []);

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
          <p className="text-slate-500 text-sm mt-1">כניסה באמצעות טלפון</p>
        </div>

        {step === 'phone' && (
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
                  placeholder="05X-XXXXXXX"
                  inputMode="tel"
                  className="w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                  autoFocus
                />
                <Phone className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              </div>
              <p className="text-xs text-slate-400">אפשר להזין 050… או +972… (נמיר אוטומטית)</p>
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
              ) : (
                'שלח קוד אימות'
              )}
            </Button>
          </form>
        )}

        {step === 'otp' && (
          <form onSubmit={handleVerifyOtp} className="space-y-4" dir="rtl">
            <button
              type="button"
              onClick={handleBack}
              className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-2"
            >
              <ArrowRight className="w-4 h-4" />
              חזרה
            </button>

            <div className="text-center mb-4">
              <p className="text-sm text-slate-600">
                שולחים קוד אימות למספר
              </p>
              <bdi dir="ltr" className="text-base font-medium text-slate-900 mt-1 inline-block">
                {phoneE164}
              </bdi>
              <p className="text-xs text-slate-400 mt-2">
                הקוד יכול להגיע עד 60 שניות
              </p>
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
              ) : (
                'אימות והתחברות'
              )}
            </Button>

            <div className="text-center mt-3">
              {resendCountdown > 0 ? (
                <p className="text-sm text-slate-400">
                  לא קיבלת? אפשר לשלוח שוב בעוד {resendCountdown} שניות
                </p>
              ) : (
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={loading}
                  className="text-sm text-amber-600 hover:text-amber-700 font-medium"
                >
                  לא קיבלת קוד? שלח שוב
                </button>
              )}
            </div>
          </form>
        )}

        {step === 'phone' && (
          <div className="mt-6 pt-5 border-t border-slate-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-1 h-px bg-slate-200" />
              <span className="text-xs text-slate-400">או</span>
              <div className="flex-1 h-px bg-slate-200" />
            </div>
            <button
              type="button"
              onClick={handleWhatsAppLogin}
              disabled={loading}
              className="w-full h-11 flex items-center justify-center gap-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
              style={{ backgroundColor: '#25D366' }}
              onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.backgroundColor = '#1ebe5d'; }}
              onMouseLeave={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.backgroundColor = '#25D366'; }}
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <MessageCircle className="w-5 h-5" />
              )}
              התחבר עם WhatsApp
            </button>
          </div>
        )}

        {step === 'waSuccess' && (
          <div className="space-y-4" dir="rtl">
            <button
              type="button"
              onClick={() => { setStep('phone'); }}
              className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-2"
            >
              <ArrowRight className="w-4 h-4" />
              חזרה
            </button>
            <div className="text-center py-6">
              <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4" style={{ backgroundColor: '#25D366' }}>
                <CheckCircle className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                שלחנו לך קישור התחברות ב-WhatsApp
              </h3>
              <p className="text-sm text-slate-600 mb-1">למספר</p>
              <bdi dir="ltr" className="font-mono text-base font-medium text-slate-900 inline-block">
                {phoneE164}
              </bdi>
              <p className="text-xs text-slate-400 mt-4">
                פתח את WhatsApp ולחץ על הקישור כדי להתחבר
              </p>
              <p className="text-xs text-slate-400 mt-1">
                הקישור תקף ל-10 דקות
              </p>
            </div>
          </div>
        )}

        <div className="mt-4 pt-4 border-t border-slate-200 text-center space-y-2">
          <Link
            to="/login"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
          >
            <Mail className="w-4 h-4" />
            התחבר עם אימייל
          </Link>
          <div>
            <Link
              to="/onboarding"
              className="text-sm text-amber-600 hover:text-amber-700 transition-colors"
            >
              אין לך חשבון? הרשמה
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default PhoneLoginPage;
