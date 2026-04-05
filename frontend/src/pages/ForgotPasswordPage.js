import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, Loader2, ArrowRight, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { authService } from '../services/api';

const ForgotPasswordPage = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      setError('נא להזין כתובת אימייל');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError('כתובת אימייל לא תקינה');
      return;
    }

    setLoading(true);
    try {
      await authService.forgotPassword(trimmed);
      setSent(true);
    } catch (err) {
      if (err.response?.status === 429) {
        setError('יותר מדי בקשות. נסה שוב בעוד מספר דקות.');
      } else {
        setError('אירעה שגיאה. נסה שוב מאוחר יותר.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-amber-50/30 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/logo-orange.png" alt="BrikOps" style={{ height: 48, marginBottom: 8 }} />
          <p className="text-slate-500 text-sm">איפוס סיסמה</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6 sm:p-8">
          {sent ? (
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="w-16 h-16 bg-emerald-50 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-8 h-8 text-emerald-500" />
                </div>
              </div>
              <h2 className="text-lg font-semibold text-slate-900">הבקשה נשלחה</h2>
              <p className="text-sm text-slate-600 leading-relaxed">
                אם הכתובת רשומה במערכת, נשלח אליה קישור לאיפוס סיסמה.
                <br />
                הקישור תקף ל-60 דקות.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 text-sm text-amber-600 hover:text-amber-700 font-medium mt-4"
              >
                <ArrowRight className="w-4 h-4" />
                חזרה לכניסה
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-1">שכחת סיסמה?</h2>
                <p className="text-sm text-slate-500">הזן את כתובת האימייל שלך ונשלח לך קישור לאיפוס</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                    אימייל
                  </label>
                  <div className="relative">
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => { setEmail(e.target.value); setError(''); }}
                      placeholder="your@email.com"
                      className={`w-full h-11 px-3 py-2 pr-10 text-right text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${error ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
                      autoFocus
                    />
                    <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  </div>
                  {error && (
                    <div className="flex items-center gap-1 text-sm text-red-500">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}
                </div>

                <Button
                  type="submit"
                  className="w-full h-12 text-base font-medium mt-2 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
                  disabled={loading}
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 className="w-5 h-5 animate-spin" />
                      שולח...
                    </span>
                  ) : 'שלח קישור איפוס'}
                </Button>
              </form>

              <div className="mt-4 text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1 text-sm text-amber-600 hover:text-amber-700 font-medium"
                >
                  <ArrowRight className="w-4 h-4" />
                  חזרה לכניסה
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
