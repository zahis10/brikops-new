import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from '../contexts/BillingContext';
import { transferService } from '../services/api';
import { toast } from 'sonner';
import { Loader2, CheckCircle2, AlertCircle, ArrowRight, Phone, Shield } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';

const OwnershipTransferPage = () => {
  const { token } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const isSettingsView = location.pathname === '/org/transfer/settings';
  const isRecipientView = !!token && !isSettingsView;

  if (isRecipientView) {
    return <RecipientView token={token} />;
  }
  return <OwnerSettingsView prefillPhone={location.state?.prefillPhone} />;
};

const OwnerSettingsView = ({ prefillPhone }) => {
  const { user, loading: authLoading } = useAuth();
  const { isOwner, loading: billingLoading } = useBilling();
  const navigate = useNavigate();
  const [pending, setPending] = useState(null);
  const [loadingPending, setLoadingPending] = useState(true);
  const [phone, setPhone] = useState(prefillPhone || '');
  const [submitting, setSubmitting] = useState(false);

  const fetchPending = useCallback(async () => {
    setLoadingPending(true);
    try {
      const data = await transferService.getPending();
      setPending(data.pending || null);
    } catch {
      setPending(null);
    } finally {
      setLoadingPending(false);
    }
  }, []);

  useEffect(() => {
    if (user && isOwner) {
      fetchPending();
    } else {
      setLoadingPending(false);
    }
  }, [user, isOwner, fetchPending]);

  if (authLoading || billingLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
        <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
      </div>
    );
  }

  if (!isOwner) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
        <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl text-center" dir="rtl">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">אין לך הרשאה לצפות בדף זה</h2>
          <Button onClick={() => navigate('/projects')} className="bg-amber-500 hover:bg-amber-600 text-white w-full mt-4">
            חזרה לפרויקטים
          </Button>
        </Card>
      </div>
    );
  }

  const handleInitiate = async (e) => {
    e.preventDefault();
    if (!phone.trim()) {
      toast.error('יש להזין מספר טלפון');
      return;
    }
    setSubmitting(true);
    try {
      await transferService.initiate(phone.trim());
      toast.success('בקשה נשלחה – ממתין לאישור');
      setPhone('');
      fetchPending();
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בשליחת בקשה';
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בשליחת בקשה');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!pending?.request_id) return;
    setSubmitting(true);
    try {
      await transferService.cancel(pending.request_id);
      toast.success('הבקשה בוטלה');
      setPending(null);
      fetchPending();
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בביטול';
      toast.error(typeof detail === 'string' ? detail : 'שגיאה בביטול');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl" dir="rtl">
        <div className="flex flex-col items-center mb-6">
          <div className="w-14 h-14 bg-amber-500 rounded-xl flex items-center justify-center mb-3 shadow-lg">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Rubik, sans-serif' }}>
            העברת בעלות
          </h1>
          <p className="text-slate-500 text-sm mt-1">העברת ניהול תשלום לבעלים חדש</p>
        </div>

        {loadingPending ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : pending ? (
          <div className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
              <h3 className="text-base font-bold text-amber-800 mb-3">בקשה ממתינה</h3>
              <div className="space-y-2 text-sm text-slate-700">
                <p>נשלח אל: <bdi dir="ltr" className="font-mono">{pending.masked_phone}</bdi></p>
                <p>נשלח בתאריך: {pending.created_at}</p>
                <p>תוקף עד: {pending.expires_at} (48 שעות)</p>
              </div>
            </div>
            <Button
              onClick={handleCancel}
              disabled={submitting}
              className="w-full bg-red-500 hover:bg-red-600 text-white h-11"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin ml-2" /> : null}
              בטל בקשה
            </Button>
          </div>
        ) : (
          <form onSubmit={handleInitiate} className="space-y-4">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">
                מספר טלפון של הבעלים החדש
                <span className="text-red-500 mr-1">*</span>
              </label>
              <div className="relative">
                <input
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
            <Button
              type="submit"
              disabled={submitting}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white h-12 text-base font-medium"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  שולח...
                </span>
              ) : 'שלח בקשת העברה'}
            </Button>
          </form>
        )}

        <div className="mt-6 text-center">
          <button type="button" onClick={() => navigate('/projects')} className="text-sm text-slate-500 hover:text-slate-700 flex items-center justify-center gap-1 mx-auto">
            <ArrowRight className="w-4 h-4" />
            חזרה לפרויקטים
          </button>
        </div>
      </Card>
    </div>
  );
};

const RecipientView = ({ token }) => {
  const navigate = useNavigate();
  const [step, setStep] = useState('verifying');
  const [orgName, setOrgName] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [debugCode, setDebugCode] = useState('');
  const [typedOrgName, setTypedOrgName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    transferService.verifyToken(token)
      .then((data) => {
        setOrgName(data.org_name);
        setStep('confirm');
      })
      .catch((err) => {
        const status = err.response?.status;
        if (status === 410) {
          setError('תוקף הבקשה פג');
        } else if (status === 404) {
          setError('קישור לא תקין או שפג תוקפו');
        } else {
          setError(err.response?.data?.detail || 'קישור לא תקין');
        }
        setStep('error');
      });
  }, [token]);

  const handleRequestOtp = async () => {
    setLoading(true);
    try {
      const data = await transferService.requestOtp(token);
      if (data.otp_debug_code) {
        setDebugCode(data.otp_debug_code);
      }
      setStep('otp');
    } catch (err) {
      const status = err.response?.status;
      if (status === 429) {
        toast.error('חרגת ממספר הניסיונות');
      } else if (status === 410) {
        toast.error('תוקף הבקשה פג');
      } else {
        toast.error(err.response?.data?.detail || 'שגיאה בשליחת קוד');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (otpCode.length !== 6) {
      toast.error('יש להזין קוד בן 6 ספרות');
      return;
    }
    setStep('typed-confirm');
  };

  const handleAccept = async () => {
    if (!typedOrgName.trim()) {
      toast.error('יש להקליד את שם הארגון');
      return;
    }
    setLoading(true);
    try {
      await transferService.accept(token, otpCode, typedOrgName.trim());
      setStep('success');
    } catch (err) {
      const status = err.response?.status;
      if (status === 403) {
        toast.error('קוד אימות שגוי');
      } else if (status === 422) {
        toast.error(err.response?.data?.detail || 'שם הארגון לא תואם');
      } else if (status === 410) {
        toast.error('תוקף הבקשה פג');
      } else if (status === 409) {
        toast.error(err.response?.data?.detail || 'שגיאה');
      } else if (status === 429) {
        toast.error('חרגת ממספר הניסיונות');
      } else {
        toast.error(err.response?.data?.detail || 'שגיאה בהעברת בעלות');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl" dir="rtl">
        {step === 'verifying' && (
          <div className="flex flex-col items-center py-8">
            <Loader2 className="w-8 h-8 text-amber-500 animate-spin mb-4" />
            <p className="text-sm text-slate-500">מאמת קישור...</p>
          </div>
        )}

        {step === 'error' && (
          <div className="text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
            <h2 className="text-xl font-bold text-slate-900">{error}</h2>
            <Button onClick={() => navigate('/login')} className="w-full bg-amber-500 hover:bg-amber-600 text-white h-11">
              חזרה להתחברות
            </Button>
          </div>
        )}

        {step === 'confirm' && (
          <div className="space-y-5">
            <div className="flex flex-col items-center mb-4">
              <div className="w-14 h-14 bg-amber-500 rounded-xl flex items-center justify-center mb-3 shadow-lg">
                <Shield className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-xl font-bold text-slate-900">אישור בעלות על הארגון</h1>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 text-sm text-slate-700 leading-relaxed space-y-2">
              <p>
                התקבלה בקשה להפוך אותך לבעלים היחיד של הארגון: <strong>{orgName}</strong>.
              </p>
              <p>כבעלים תוכל לנהל תשלום, מנוי וחשבוניות.</p>
              <p>מנהל הפרויקט הנוכחי ימשיך לעבוד כרגיל – רק ניהול התשלום יעבור אליך.</p>
            </div>

            <p className="text-xs text-slate-400 text-center">אם אינך מכיר/ה את הבקשה – אל תאשר/י.</p>

            <Button
              onClick={handleRequestOtp}
              disabled={loading}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white h-12 text-base font-medium"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  שולח...
                </span>
              ) : 'שלח קוד אימות'}
            </Button>

            <div className="text-center">
              <button type="button" onClick={() => navigate('/login')} className="text-sm text-slate-500 hover:text-slate-700">
                זה לא אני
              </button>
            </div>
          </div>
        )}

        {step === 'otp' && (
          <div className="space-y-5">
            <div className="flex flex-col items-center mb-4">
              <h2 className="text-xl font-bold text-slate-900">הזנת קוד אימות</h2>
              <p className="text-sm text-slate-500 mt-1">הקוד נשלח לטלפון שלך</p>
            </div>

            {debugCode && (
              <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-3 text-center">
                <p className="text-xs text-yellow-700">קוד דיבאג: <span className="font-mono font-bold">{debugCode}</span></p>
              </div>
            )}

            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">קוד אימות</label>
              <input
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
              onClick={handleVerifyOtp}
              disabled={loading || otpCode.length !== 6}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white h-12 text-base font-medium"
            >
              אמת קוד
            </Button>
          </div>
        )}

        {step === 'typed-confirm' && (
          <div className="space-y-5">
            <div className="flex flex-col items-center mb-4">
              <h2 className="text-xl font-bold text-slate-900">אישור סופי</h2>
            </div>

            <div className="space-y-3">
              <p className="text-sm text-slate-700">להמשך, הקלד/י את שם הארגון בדיוק:</p>
              <p className="text-center text-lg font-bold text-slate-900">{orgName}</p>
              <input
                type="text"
                value={typedOrgName}
                onChange={(e) => setTypedOrgName(e.target.value)}
                placeholder="הקלד/י את שם הארגון"
                className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
                autoFocus
              />
            </div>

            <Button
              onClick={handleAccept}
              disabled={loading || !typedOrgName.trim()}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white h-12 text-base font-medium"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  מעבד...
                </span>
              ) : 'אני מאשר/ת העברת בעלות'}
            </Button>
          </div>
        )}

        {step === 'success' && (
          <div className="text-center space-y-5">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto" />
            <h2 className="text-xl font-bold text-slate-900">העברת הבעלות הושלמה בהצלחה!</h2>
            <p className="text-sm text-slate-600">הנך כעת הבעלים של הארגון: <strong>{orgName}</strong></p>
            <Button
              onClick={() => navigate('/projects')}
              className="w-full bg-green-600 hover:bg-green-700 text-white h-12 text-base font-medium"
            >
              מעבר לפרויקטים
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
};

export default OwnershipTransferPage;
