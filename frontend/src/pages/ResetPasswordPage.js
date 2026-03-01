import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { HardHat, Eye, EyeOff, Loader2, ArrowRight, CheckCircle, AlertCircle, XCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { authService } from '../services/api';

const ResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  const validate = () => {
    const errs = {};
    if (password.length < 8) {
      errs.password = 'סיסמה חייבת להכיל לפחות 8 תווים';
    } else if (!/[a-zA-Zא-ת]/.test(password)) {
      errs.password = 'סיסמה חייבת להכיל לפחות אות אחת';
    } else if (!/[0-9]/.test(password)) {
      errs.password = 'סיסמה חייבת להכיל לפחות ספרה אחת';
    }
    if (password !== confirmPassword) {
      errs.confirm = 'הסיסמאות לא תואמות';
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validate()) return;

    setLoading(true);
    try {
      await authService.resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 400) {
        setError(detail || 'קישור לא תקף או שפג תוקפו');
      } else {
        setError('אירעה שגיאה. נסה שוב מאוחר יותר.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-amber-50/30 flex items-center justify-center p-4" dir="rtl">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-2 mb-2">
              <HardHat className="w-8 h-8 text-amber-500" />
              <h1 className="text-2xl font-bold text-slate-900">BrikOps</h1>
            </div>
          </div>
          <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6 sm:p-8 text-center space-y-4">
            <div className="flex justify-center">
              <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center">
                <XCircle className="w-8 h-8 text-red-500" />
              </div>
            </div>
            <h2 className="text-lg font-semibold text-slate-900">קישור לא תקף</h2>
            <p className="text-sm text-slate-600">הקישור חסר או לא תקין. נסה לבקש קישור חדש.</p>
            <Link
              to="/forgot-password"
              className="inline-flex items-center gap-2 text-sm text-amber-600 hover:text-amber-700 font-medium mt-2"
            >
              <ArrowRight className="w-4 h-4" />
              בקש קישור חדש
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-amber-50/30 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <HardHat className="w-8 h-8 text-amber-500" />
            <h1 className="text-2xl font-bold text-slate-900">BrikOps</h1>
          </div>
          <p className="text-slate-500 text-sm">איפוס סיסמה</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200/60 p-6 sm:p-8">
          {success ? (
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="w-16 h-16 bg-emerald-50 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-8 h-8 text-emerald-500" />
                </div>
              </div>
              <h2 className="text-lg font-semibold text-slate-900">הסיסמה עודכנה בהצלחה</h2>
              <p className="text-sm text-slate-600">כעת ניתן להתחבר עם הסיסמה החדשה.</p>
              <Link
                to="/login"
                className="inline-flex items-center justify-center gap-2 w-full h-12 text-base font-medium bg-amber-500 hover:bg-amber-600 text-white rounded-lg mt-4"
              >
                <ArrowRight className="w-4 h-4" />
                לכניסה
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-1">בחר סיסמה חדשה</h2>
                <p className="text-sm text-slate-500">סיסמה חייבת להכיל לפחות 8 תווים, אות וספרה</p>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 mb-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                    סיסמה חדשה
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setFieldErrors(p => { const n = {...p}; delete n.password; return n; }); }}
                      placeholder="לפחות 8 תווים"
                      className={`w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${fieldErrors.password ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(p => !p)}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 touch-manipulation"
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  {fieldErrors.password && (
                    <div className="flex items-center gap-1 text-sm text-red-500">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{fieldErrors.password}</span>
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700">
                    אימות סיסמה
                  </label>
                  <div className="relative">
                    <input
                      id="confirmPassword"
                      type={showConfirm ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => { setConfirmPassword(e.target.value); setFieldErrors(p => { const n = {...p}; delete n.confirm; return n; }); }}
                      placeholder="הזן שוב את הסיסמה"
                      className={`w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${fieldErrors.confirm ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm(p => !p)}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 touch-manipulation"
                      tabIndex={-1}
                    >
                      {showConfirm ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  {fieldErrors.confirm && (
                    <div className="flex items-center gap-1 text-sm text-red-500">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{fieldErrors.confirm}</span>
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
                      מעדכן...
                    </span>
                  ) : 'עדכן סיסמה'}
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResetPasswordPage;
