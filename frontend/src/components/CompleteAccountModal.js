import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useIdentity } from '../contexts/IdentityContext';
import { identityService } from '../services/api';
import { ShieldCheck, X } from 'lucide-react';

const AUTH_PAGES = ['/login', '/register', '/register-management', '/phone-login', '/pending', '/onboarding', '/forgot-password', '/reset-password'];
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const CompleteAccountModal = () => {
  const { identityStatus, identityLoading, refreshIdentity, showCompleteForm, setShowCompleteForm } = useIdentity();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const isBlocking = identityStatus?.requires_completion === true;
  const isVoluntary = showCompleteForm && !isBlocking;
  const shouldShow = isBlocking || isVoluntary;

  useEffect(() => {
    if (isBlocking) {
      try {
        if (sessionStorage.getItem('identity_modal_shown_logged') !== 'true') {
          sessionStorage.setItem('identity_modal_shown_logged', 'true');
          identityService.logEvent('identity_modal_shown', { requires_completion: true });
        }
      } catch {}
    }
  }, [isBlocking]);

  if (AUTH_PAGES.includes(location.pathname)) return null;
  if (identityLoading) return null;
  if (!shouldShow) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !EMAIL_RE.test(email.trim())) {
      setError('כתובת מייל לא תקינה');
      return;
    }
    if (password.length < 8) {
      setError('סיסמה חייבת להכיל לפחות 8 תווים');
      return;
    }
    if (password !== confirmPassword) {
      setError('הסיסמאות לא תואמות');
      return;
    }

    setSubmitting(true);
    try {
      await identityService.completeAccount(email.trim(), password);
      setSuccess(true);
      try { sessionStorage.removeItem('identity_modal_shown_logged'); } catch {}
      await refreshIdentity();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || 'שגיאה בשמירת הפרטים, נסה שוב');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isBlocking) {
      setShowCompleteForm(false);
      setEmail('');
      setPassword('');
      setConfirmPassword('');
      setError('');
      setSuccess(false);
    }
  };

  if (success) return null;

  return (
    <div className="fixed inset-0 bg-black/60 z-[9998] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 relative" dir="rtl">
        {!isBlocking && (
          <button
            onClick={handleClose}
            className="absolute top-4 left-4 text-slate-400 hover:text-slate-600"
          >
            <X className="w-5 h-5" />
          </button>
        )}

        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mb-4">
            <ShieldCheck className="w-8 h-8 text-amber-600" />
          </div>
          <h2 className="text-xl font-bold text-slate-800 mb-2">השלמת פרטי חשבון</h2>
          <p className="text-slate-600 text-sm leading-relaxed">
            {isBlocking
              ? 'כדי להמשיך להשתמש במערכת, יש להוסיף כתובת מייל וסיסמה.'
              : 'הוסף כתובת מייל וסיסמה לאבטחת החשבון שלך.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">כתובת מייל</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="example@email.com"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
              dir="ltr"
              autoComplete="email"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">סיסמה</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="לפחות 8 תווים"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
              dir="ltr"
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">אימות סיסמה</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="הזן סיסמה שוב"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
              dir="ltr"
              autoComplete="new-password"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-medium rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? 'שומר...' : 'שמירה'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default CompleteAccountModal;
