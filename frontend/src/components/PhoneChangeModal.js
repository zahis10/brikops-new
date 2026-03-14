import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { phoneChangeService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { X, Phone, Loader2, ArrowLeft } from 'lucide-react';
import { Button } from './ui/button';
import * as DialogPrimitive from '@radix-ui/react-dialog';

const PhoneChangeModal = ({ onClose }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState('input');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleRequestOtp = async () => {
    if (!phone.trim()) {
      toast.error('חובה למלא מספר טלפון חדש');
      return;
    }
    setSubmitting(true);
    try {
      await phoneChangeService.requestOtp(phone);
      toast.success('קוד אימות נשלח');
      setStep('verify');
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בשליחת קוד';
      toast.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerify = async () => {
    if (!code.trim()) {
      toast.error('חובה להזין קוד אימות');
      return;
    }
    setSubmitting(true);
    try {
      const result = await phoneChangeService.verifyOtp(phone, code);
      toast.success('מספר הטלפון עודכן — יש להתחבר מחדש');
      onClose();
      if (result.force_logout) {
        logout();
        navigate('/login');
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'קוד שגוי';
      toast.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DialogPrimitive.Root open={true} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <DialogPrimitive.Content
          className="fixed left-[50%] top-[50%] -translate-x-1/2 -translate-y-1/2 z-50 bg-white rounded-xl shadow-2xl max-w-sm w-full p-6 outline-none"
          dir="rtl"
        >
          <DialogPrimitive.Title className="sr-only">שינוי מספר טלפון</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">טופס לשינוי מספר הטלפון של המשתמש</DialogPrimitive.Description>
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <Phone className="w-5 h-5 text-amber-500" />
              שינוי מספר טלפון
            </h3>
            <DialogPrimitive.Close asChild>
              <button className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </DialogPrimitive.Close>
          </div>

          <div className="text-sm text-slate-500 mb-4">
            מספר נוכחי: <bdi className="font-mono font-medium text-slate-700" dir="ltr">{user?.phone_e164 || '-'}</bdi>
          </div>

          {step === 'input' ? (
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-slate-700">מספר חדש</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="050-1234567"
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                  dir="ltr"
                />
              </div>
              <Button
                onClick={handleRequestOtp}
                disabled={submitting || !phone.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'שלח קוד אימות'}
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <button onClick={() => setStep('input')} className="text-xs text-amber-600 hover:underline flex items-center gap-1">
                <ArrowLeft className="w-3 h-3" />
                חזור
              </button>
              <div className="text-sm text-slate-600">
                הזן את הקוד שנשלח למספר <bdi className="font-mono font-medium" dir="ltr">{phone}</bdi>
              </div>
              <div>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="000000"
                  maxLength={6}
                  className="w-full px-3 py-2 border rounded-lg text-center text-lg tracking-widest font-mono focus:ring-2 focus:ring-amber-500"
                  dir="ltr"
                />
              </div>
              <Button
                onClick={handleVerify}
                disabled={submitting || !code.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'אמת ועדכן'}
              </Button>
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
};

export default PhoneChangeModal;
