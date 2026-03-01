import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useIdentity } from '../contexts/IdentityContext';
import { identityService } from '../services/api';
import { ShieldCheck, X } from 'lucide-react';

const AUTH_PAGES = ['/login', '/register', '/register-management', '/phone-login', '/pending', '/onboarding', '/forgot-password', '/reset-password'];
const DISMISSED_KEY = 'identity_banner_dismissed';
const SHOWN_KEY = 'identity_banner_shown_logged';

const CompleteAccountBanner = () => {
  const { identityStatus, identityLoading, setShowCompleteForm } = useIdentity();
  const location = useLocation();
  const shownLoggedRef = useRef(false);

  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(DISMISSED_KEY) === 'true'; } catch { return false; }
  });

  const shouldShow =
    !identityLoading &&
    identityStatus &&
    identityStatus.gate_mode === 'soft' &&
    identityStatus.is_management &&
    identityStatus.would_require_completion &&
    !identityStatus.requires_completion &&
    !dismissed;

  useEffect(() => {
    if (shouldShow && !shownLoggedRef.current) {
      const alreadyLogged = sessionStorage.getItem(SHOWN_KEY) === 'true';
      if (!alreadyLogged) {
        shownLoggedRef.current = true;
        try { sessionStorage.setItem(SHOWN_KEY, 'true'); } catch {}
        identityService.logEvent('identity_banner_shown', {
          is_management: true,
          would_require: true,
        });
      }
    }
  }, [shouldShow]);

  if (AUTH_PAGES.includes(location.pathname)) return null;
  if (!shouldShow) return null;

  const handleDismiss = () => {
    setDismissed(true);
    try { sessionStorage.setItem(DISMISSED_KEY, 'true'); } catch {}
    identityService.logEvent('identity_banner_dismissed');
  };

  const handleCTA = () => {
    setShowCompleteForm(true);
  };

  return (
    <div
      className="w-full px-4 py-2 text-center text-sm font-medium bg-amber-50 text-amber-800 border-b border-amber-200 flex items-center justify-center gap-2"
      dir="rtl"
    >
      <ShieldCheck className="w-4 h-4 flex-shrink-0" />
      <span>השלם את פרטי החשבון — הוסף כתובת מייל וסיסמה לאבטחת החשבון</span>
      <button
        onClick={handleCTA}
        className="mr-3 px-3 py-0.5 rounded text-xs font-bold bg-amber-500 text-white hover:bg-amber-600"
      >
        השלמת פרטים
      </button>
      <button onClick={handleDismiss} className="mr-1 p-0.5 rounded hover:bg-amber-200/50" title="הסתר">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};

export default CompleteAccountBanner;
