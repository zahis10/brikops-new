import React, { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from '../contexts/BillingContext';
import { ShieldAlert, CreditCard, MessageCircle, X } from 'lucide-react';
import { Button } from './ui/button';
import { getBillingHubUrl } from '../utils/billingHub';

const AUTH_PAGES = ['/login', '/register', '/register-management', '/phone-login', '/pending', '/forgot-password', '/reset-password'];

function getReasonDescription(reason) {
  switch (reason) {
    case 'payment_expired':
      return (
        <>
          התשלום פג תוקף. חדש את המנוי כדי לשחזר גישה מלאה.
          <br />
          <span className="text-slate-500 mt-2 block">
            צפייה בנתונים הקיימים עדיין זמינה.
          </span>
        </>
      );
    case 'suspended':
      return (
        <>
          המנוי הושעה. פנה לתמיכה לפרטים נוספים.
          <br />
          <span className="text-slate-500 mt-2 block">
            צפייה בנתונים הקיימים עדיין זמינה.
          </span>
        </>
      );
    default:
      return (
        <>
          תקופת הניסיון הסתיימה. כדי להמשיך ליצור, לערוך ולנהל ליקויים,
          תוכניות ופרויקטים — יש לשדרג את החשבון.
          <br />
          <span className="text-slate-500 mt-2 block">
            צפייה בנתונים הקיימים עדיין זמינה.
          </span>
        </>
      );
  }
}

const PaywallModal = () => {
  const { user } = useAuth();
  const { billing, showPaywall, setShowPaywall, isOwner } = useBilling();
  const location = useLocation();
  const navigate = useNavigate();

  const isSuperAdmin = user?.platform_role === 'super_admin';
  const isActiveSubscription = billing?.subscription_status === 'active';
  const canAccessBilling = isOwner || isSuperAdmin;
  const orgId = billing?.org_id;
  const isTrialActive = billing?.status === 'trialing' && billing?.days_remaining > 0;
  const daysLeft = billing?.days_remaining || 0;
  const reason = billing?.read_only_reason;

  useEffect(() => {
    if (isActiveSubscription && showPaywall) {
      setShowPaywall(false);
    }
  }, [isActiveSubscription, showPaywall, setShowPaywall]);

  if (AUTH_PAGES.includes(location.pathname)) return null;
  if (!user || !showPaywall) return null;
  if (isSuperAdmin) return null;
  if (isActiveSubscription) return null;

  const handleGoToBilling = () => {
    setShowPaywall(false);
    if (orgId) {
      navigate(getBillingHubUrl({ orgId }));
    }
  };

  if (!canAccessBilling) {
    return (
      <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 relative" dir="rtl">
          <button
            onClick={() => setShowPaywall(false)}
            className="absolute top-4 left-4 text-slate-400 hover:text-slate-600"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
              <ShieldAlert className="w-8 h-8 text-slate-500" />
            </div>
            <h2 className="text-xl font-bold text-slate-800 mb-2">הגישה מוגבלת</h2>
            <p className="text-slate-600 mb-6 text-sm leading-relaxed">
              כדי להמשיך בעבודה מלאה, פנה לבעלי הארגון להפעלת המנוי.
            </p>
            <Button variant="outline" onClick={() => setShowPaywall(false)} className="w-full">
              חזרה
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4">
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 relative"
        dir="rtl"
      >
        <button
          onClick={() => setShowPaywall(false)}
          className="absolute top-4 left-4 text-slate-400 hover:text-slate-600"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex flex-col items-center text-center">
          <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 ${isTrialActive ? 'bg-amber-100' : 'bg-red-100'}`}>
            <ShieldAlert className={`w-8 h-8 ${isTrialActive ? 'text-amber-600' : 'text-red-600'}`} />
          </div>

          <h2 className="text-xl font-bold text-slate-800 mb-2">
            {isTrialActive ? 'שדרוג חשבון' : (reason === 'payment_expired' ? 'חידוש מנוי' : 'נדרש שדרוג')}
          </h2>

          <p className="text-slate-600 mb-6 text-sm leading-relaxed">
            {isTrialActive ? (
              <>
                נשארו לך <strong>{daysLeft} ימים</strong> בתקופת הניסיון.
                <br />
                שדרג עכשיו כדי להבטיח גישה רציפה לכל היכולות.
              </>
            ) : getReasonDescription(reason)}
          </p>

          <div className="flex flex-col gap-3 w-full">
            {orgId && (
              <Button
                onClick={handleGoToBilling}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white flex items-center justify-center gap-2"
              >
                <CreditCard className="w-4 h-4" />
                מעבר לדף החיוב
              </Button>
            )}

            <button
              onClick={() => {
                window.open('https://wa.me/972500000001?text=שלום, אני מעוניין לשדרג את חשבון BrikOps', '_blank');
              }}
              className="text-xs text-slate-500 hover:text-green-600 flex items-center justify-center gap-1"
            >
              <MessageCircle className="w-3 h-3" />
              צריך עזרה? דבר איתנו בוואטסאפ
            </button>

            <Button
              variant="outline"
              onClick={() => setShowPaywall(false)}
              className="w-full"
            >
              {isTrialActive ? 'אולי אחר כך' : 'חזרה לצפייה'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaywallModal;
