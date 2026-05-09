import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from '../contexts/BillingContext';
import { Clock, AlertTriangle, X } from 'lucide-react';
import { toast } from 'sonner';
import { buildOrgBillingUrl } from '../utils/billingHub';
import { BACKEND_URL } from '../services/api';

const AUTH_PAGES = ['/login', '/register', '/register-management', '/phone-login', '/pending', '/onboarding', '/forgot-password', '/reset-password'];
const PROJECTS_LIST_PAGES = ['/', '/projects'];

function getOwnerBannerText(reason) {
  switch (reason) {
    case 'payment_expired': return 'התשלום פג תוקף — מצב צפייה בלבד';
    case 'trial_expired': return 'תקופת הניסיון הסתיימה — מצב צפייה בלבד';
    case 'suspended': return 'המנוי הושעה — מצב צפייה בלבד';
    default: return 'הגישה מוגבלת — מצב צפייה בלבד';
  }
}

function getNonOwnerBannerText(reason) {
  switch (reason) {
    case 'payment_expired': return 'הגישה מוגבלת — התשלום לא חודש. פנה למנהל הארגון.';
    case 'trial_expired': return 'הגישה מוגבלת — תקופת הניסיון הסתיימה. פנה למנהל הארגון.';
    case 'suspended': return 'הגישה מוגבלת — המנוי הושעה. פנה למנהל הארגון.';
    default: return 'הגישה מוגבלת כרגע — פנה למנהל הארגון להפעלת המנוי.';
  }
}

const NON_BILLING_ROLES = ['management_team', 'contractor', 'viewer', 'site_manager', 'execution_engineer', 'safety_assistant'];

const TrialBanner = () => {
  const { user, token } = useAuth();
  const { billing, loading, isReadOnly, isOwner, canManageBilling, isOrgPm, setShowPaywall } = useBilling();
  const location = useLocation();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem('trial_banner_dismissed') === 'true'; } catch { return false; }
  });

  // 2026-05-09 — Track user's role in the CURRENT project (when on a
  // project page). Banner suppresses for contractor/viewer because
  // they can't pay for the project's owning org anyway. Fixes a
  // false-positive where contractor in Project A (paid by Org A)
  // saw expired banner just because their OWN org's subscription
  // was expired — confusing, made them think Project A was broken.
  const projectMatch = location.pathname.match(/^\/projects\/([a-f0-9-]{36})/);
  const projectId = projectMatch ? projectMatch[1] : null;
  const [currentProjectRole, setCurrentProjectRole] = useState(null);

  useEffect(() => {
    if (!projectId || !token) {
      setCurrentProjectRole(null);
      return;
    }
    let cancelled = false;
    axios.get(`${BACKEND_URL}/api/projects/${projectId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(res => {
        if (!cancelled) setCurrentProjectRole(res.data?.my_role || null);
      })
      .catch(() => {
        if (!cancelled) setCurrentProjectRole(null);
      });
    return () => { cancelled = true; };
  }, [projectId, token]);

  if (AUTH_PAGES.includes(location.pathname)) return null;
  if (PROJECTS_LIST_PAGES.includes(location.pathname)) return null;
  if (!user || loading || !billing) return null;

  const isSuperAdmin = user.platform_role === 'super_admin';
  if (isSuperAdmin) return null;

  const roleDisplay = billing.role_display || user.role;
  if (NON_BILLING_ROLES.includes(roleDisplay) || NON_BILLING_ROLES.includes(user.role)) return null;

  // 2026-05-09 — Suppress banner if user is contractor/viewer in the
  // current project (regardless of their global user.role). Fixes
  // false-positive seen on prod 2026-05-09 — user "צחי שמי" with
  // own-org expired (Project 808) was contractor in Project 810
  // (other org paid). Banner showed on both projects; this hides it
  // for the contractor case where the user can't take action anyway.
  if (currentProjectRole === 'contractor' || currentProjectRole === 'viewer') return null;

  const handleDismiss = () => {
    setDismissed(true);
    try { sessionStorage.setItem('trial_banner_dismissed', 'true'); } catch {};
  };

  if (isOrgPm && !canManageBilling) {
    if (!isReadOnly) return null;
    return (
      <div
        className="w-full px-4 py-2 text-center text-sm font-medium bg-slate-100 text-slate-700 border-b border-slate-200 flex items-center justify-center gap-2"
        dir="rtl"
      >
        <AlertTriangle className="w-4 h-4 text-slate-500" />
        <span>צפייה בלבד — אין הרשאה לניהול חיוב</span>
      </div>
    );
  }

  if (canManageBilling || isOwner) {
    if (billing.status === 'trialing' && billing.days_remaining > 0 && billing.days_remaining <= 7) {
      if (dismissed) return null;
      const urgent = billing.days_remaining <= 2;
      return (
        <div
          className={`w-full px-4 py-2 text-center text-sm font-medium flex items-center justify-center gap-2 ${
            urgent
              ? 'bg-red-500 text-white'
              : 'bg-amber-50 text-amber-800 border-b border-amber-200'
          }`}
          dir="rtl"
        >
          {urgent ? <AlertTriangle className="w-4 h-4" /> : <Clock className="w-4 h-4" />}
          <span>
            נשארו {billing.days_remaining} ימים לתקופת הניסיון
          </span>
          <button
            onClick={() => {
              const url = buildOrgBillingUrl({ orgId: billing?.org_id, focus: 'renew' });
              if (url) {
                navigate(url);
              } else {
                toast.error('לא נמצא ארגון לחיוב. נסה לרענן/התחבר מחדש.');
                console.warn('[TrialBanner] Missing org_id for billing navigation', { role: user?.role, path: location.pathname });
              }
            }}
            className={`mr-3 px-3 py-0.5 rounded text-xs font-bold ${
              urgent
                ? 'bg-white text-red-600 hover:bg-red-50'
                : 'bg-amber-500 text-white hover:bg-amber-600'
            }`}
          >
            שדרוג
          </button>
          {!urgent && (
            <button onClick={handleDismiss} className="mr-1 p-0.5 rounded hover:bg-amber-200/50" title="הסתר">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      );
    }

    if (isReadOnly && (canManageBilling || isOwner)) {
      if (billing.subscription_status === 'active') return null;

      const reason = billing.read_only_reason;
      const isSuspended = reason === 'suspended';
      const showUpgrade = !isSuspended;

      return (
        <div
          className="w-full px-4 py-2 text-center text-sm font-medium bg-red-500 text-white flex items-center justify-center gap-2"
          dir="rtl"
        >
          <AlertTriangle className="w-4 h-4" />
          <span>{getOwnerBannerText(reason)}</span>
          {showUpgrade && (
            <button
              onClick={() => {
                const url = buildOrgBillingUrl({ orgId: billing?.org_id, focus: 'renew' });
                if (url) {
                  navigate(url);
                } else {
                  toast.error('לא נמצא ארגון לחיוב. נסה לרענן/התחבר מחדש.');
                  console.warn('[TrialBanner] Missing org_id for billing navigation', { role: user?.role, path: location.pathname });
                }
              }}
              className="mr-3 px-3 py-0.5 rounded text-xs font-bold bg-white text-red-600 hover:bg-red-50"
            >
              שדרוג
            </button>
          )}
          {isSuspended && (
            <span className="mr-3 text-xs opacity-80">פנה לתמיכה</span>
          )}
        </div>
      );
    }

    return null;
  }

  return null;
};

export default TrialBanner;
