import React, { useEffect, useRef, useState } from 'react';
import { adminAnalyticsService } from '../../services/api';

const DEFAULT_ROLE_LABELS = {
  project_manager: 'מנהל פרויקט',
  contractor: 'קבלן',
  owner: 'בעלים',
  management_team: 'צוות ניהולי',
  super_admin: 'אדמין',
  worker: 'עובד',
};

export function formatRelativeActivityTime(iso) {
  if (!iso) return '—';
  const seenAt = Date.parse(iso);
  if (!Number.isFinite(seenAt)) return '—';
  const seconds = Math.max(0, Math.floor((Date.now() - seenAt) / 1000));
  if (seconds < 60) return 'עכשיו';
  if (seconds < 3600) return `לפני ${Math.floor(seconds / 60)} דק׳`;
  if (seconds < 86400) return `לפני ${Math.floor(seconds / 3600)} שע׳`;
  return `לפני ${Math.floor(seconds / 86400)} ימים`;
}

export default function ActiveNowChip({
  formatRelativeTime = formatRelativeActivityTime,
  roleLabels = DEFAULT_ROLE_LABELS,
  minutes = 15,
}) {
  const [active, setActive] = useState(null);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);
  const requestRef = useRef(0);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      const requestId = ++requestRef.current;
      try {
        const result = await adminAnalyticsService.getActiveNow(minutes);
        if (!mounted || requestId !== requestRef.current) return;
        setActive(result || null);
        setError(false);
      } catch {
        if (!mounted || requestId !== requestRef.current) return;
        setActive(null);
        setError(true);
        setOpen(false);
      }
    };

    load();
    const interval = setInterval(load, 60_000);
    return () => {
      mounted = false;
      requestRef.current += 1;
      clearInterval(interval);
    };
  }, [minutes]);

  const count = error || !active ? null : Number.isFinite(Number(active.count))
    ? Math.max(0, Number(active.count))
    : 0;
  const users = Array.isArray(active?.users) ? active.users : [];
  const label = count === null
    ? '—'
    : count === 0
      ? 'אין פעילים כרגע'
      : `פעילים עכשיו: ${count}`;

  return (
    <div className="relative mr-auto shrink-0" dir="rtl">
      <button
        type="button"
        className="min-h-[44px] inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 text-xs font-medium text-white hover:bg-white/15 transition-colors"
        onClick={() => { if (!error && count !== null) setOpen(value => !value); }}
        aria-expanded={open}
        aria-controls="admin-active-now-users"
        aria-label={count === null ? 'פעילות עכשיו: לא זמין' : label}
      >
        <span className={`h-2 w-2 rounded-full ${count && count > 0 ? 'bg-emerald-400' : 'bg-slate-400'}`} />
        <span>{label}</span>
      </button>
      {open && !error && (
        <div
          id="admin-active-now-users"
          className="absolute left-0 top-full z-50 mt-2 max-h-[60vh] w-72 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white p-3 text-right text-slate-700 shadow-xl"
        >
          <div className="mb-2 text-xs font-bold text-slate-500">פעילים עכשיו</div>
          {users.length === 0 ? (
            <div className="text-xs text-slate-400">אין פעילים כרגע</div>
          ) : (
            <ul className="space-y-2">
              {users.map((user, index) => (
                <li key={user.user_id || `${user.name || 'user'}-${index}`} className="min-w-0 text-xs">
                  <div className="truncate font-medium">{user.name || '—'}</div>
                  <div className="break-words text-slate-500">
                    {user.org_name || '—'} · {roleLabels[user.role] || user.role || '—'} · {formatRelativeTime(user.last_seen_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}