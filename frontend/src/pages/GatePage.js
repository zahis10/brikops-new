import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CheckCircle2, XCircle, AlertTriangle, HelpCircle } from 'lucide-react';
import { safetyService } from '../services/api';

// Batch qrg1-entry-gate — PUBLIC live entry-gate status page (/gate/:token).
// Scanned by the gate guard: mobile-first, RTL, no auth, one glance verdict.
// The backend never returns PII beyond first name + photo — nothing to hide
// here. Every load re-fetches (live status: block/expiry reflects instantly).

const initialsOf = (name) => (name || '').trim().charAt(0).toUpperCase() || '?';

function Avatar({ url, name }) {
  const [broken, setBroken] = useState(false);
  if (url && !broken) {
    return (
      <img
        src={url}
        alt={name}
        onError={() => setBroken(true)}
        className="w-24 h-24 rounded-full object-cover border-4 border-white shadow-lg"
      />
    );
  }
  return (
    <div className="w-24 h-24 rounded-full bg-white/30 border-4 border-white shadow-lg flex items-center justify-center text-4xl font-bold text-white">
      {initialsOf(name)}
    </div>
  );
}

export default function GatePage() {
  const { token } = useParams();
  const [state, setState] = useState({ loading: true, data: null, error: false });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, data: null, error: false });
    safetyService.getGateStatus(token)
      .then((data) => { if (!cancelled) setState({ loading: false, data, error: false }); })
      .catch(() => { if (!cancelled) setState({ loading: false, data: null, error: true }); });
    return () => { cancelled = true; };
  }, [token]);

  if (state.loading) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-100 flex items-center justify-center">
        <p className="text-slate-500 text-lg">בודק סטטוס כניסה…</p>
      </div>
    );
  }

  const d = state.data;

  // Network failure OR invalid token — same neutral gray card.
  if (state.error || !d || d.state === 'invalid') {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-200 flex flex-col items-center justify-center px-6 text-center">
        <HelpCircle className="w-20 h-20 text-slate-400 mb-4" />
        <h1 className="text-2xl font-bold text-slate-700">קוד לא תקף</h1>
        <p className="text-slate-500 mt-2 text-lg">
          {state.error ? 'לא ניתן לבדוק כעת — נסה שוב' : 'יש לפנות למנהל העבודה באתר'}
        </p>
      </div>
    );
  }

  if (d.state === 'red') {
    return (
      <div dir="rtl" className="min-h-screen bg-red-600 flex flex-col items-center justify-center px-6 text-center text-white">
        <XCircle className="w-24 h-24 mb-4" />
        <h1 className="text-4xl font-extrabold">אין כניסה</h1>
        {d.first_name && <p className="text-2xl mt-3 font-semibold">{d.first_name}</p>}
        <p className="text-xl mt-2 opacity-90">
          {d.reason === 'blocked'
            ? 'העובד חסום לכניסה לאתר'
            : d.expired_at
              ? `הדרכת האתר פגה בתאריך ${d.expired_at}`
              : 'לא בוצעה הדרכת אתר'}
        </p>
        {d.project_name && <p className="mt-6 text-sm opacity-75">{d.project_name}</p>}
        <p className="mt-1 text-sm opacity-75">יש לפנות למנהל העבודה</p>
      </div>
    );
  }

  // GREEN
  return (
    <div dir="rtl" className="min-h-screen bg-green-600 flex flex-col items-center justify-center px-6 text-center text-white">
      <Avatar url={d.photo_display_url} name={d.first_name} />
      <CheckCircle2 className="w-16 h-16 mt-4" />
      <h1 className="text-4xl font-extrabold mt-2">מאושר לכניסה</h1>
      <p className="text-2xl mt-2 font-semibold">{d.first_name}</p>
      {d.induction_valid_until && (
        <p className="text-lg mt-1 opacity-90">הדרכת אתר בתוקף עד {d.induction_valid_until}</p>
      )}
      {!!(d.warnings || []).length && (
        <div className="mt-5 bg-amber-400 text-amber-950 rounded-xl px-4 py-3 max-w-sm w-full text-right">
          <div className="flex items-center gap-2 font-bold mb-1">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            שים לב — הסמכות שפג תוקפן
          </div>
          <ul className="text-sm space-y-0.5">
            {d.warnings.map((w) => (
              <li key={w.type}>{w.type} — פג בתאריך {w.expired_at}</li>
            ))}
          </ul>
        </div>
      )}
      {d.project_name && <p className="mt-6 text-sm opacity-75">{d.project_name}</p>}
    </div>
  );
}
