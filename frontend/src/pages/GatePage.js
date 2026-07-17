import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { CheckCircle2, XCircle, AlertTriangle, HelpCircle, ArrowRight, Eraser, Loader2 } from 'lucide-react';
import { safetyService, API } from '../services/api';

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

// qrg1-fix1 B1a — in-app escape hatch. The page is normally opened by an
// external camera scan (browser back exists), but inside the native app the
// scanner navigates here in-place with NO system back UI → user is stuck.
// Native-only floating button, top-right (RTL "back"), rendered in ALL states.
function GateBackButton() {
  const navigate = useNavigate();
  if (!Capacitor.isNativePlatform?.()) return null;
  const goBack = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate('/');
  };
  return (
    <button
      onClick={goBack}
      aria-label="חזרה"
      className="fixed top-4 right-4 z-50 p-2.5 rounded-full bg-black/25 text-white backdrop-blur-sm active:bg-black/40"
    >
      <ArrowRight className="w-6 h-6" />
    </button>
  );
}

// qrg-share-fix S5b — boarding-pass QR card, GREEN states ONLY (worker +
// guest). The page renders its own QR (public /gate/{token}/qr.png — the QR
// encodes the exact URL already shown, zero info gain) so the guard scans it
// straight off the recipient's screen. Gracefully hides on image error.
function GateQrCard({ token }) {
  const [broken, setBroken] = useState(false);
  if (broken) return null;
  return (
    <div className="mt-6 bg-white rounded-2xl p-4 shadow-lg">
      <img
        src={`${API}/gate/${token}/qr.png`}
        alt="קוד QR לכניסה"
        onError={() => setBroken(true)}
        style={{ width: '180px', height: '180px' }}
        className="mx-auto"
      />
      <p className="text-sm font-semibold text-slate-700 text-center mt-2">הצג לסורק בכניסה</p>
    </div>
  );
}

// qrg-guest B-FE-1 — full-screen briefing + INLINE signature canvas.
// Canvas mechanics mirror SafetySignaturePad (draw/clear/toBlob) but rendered
// inline: NO Radix Dialog, NO app-only imports — this is the public page.
function GuestBriefingScreen({ token, data, onSigned, onStale }) {
  const [signerName, setSignerName] = useState(data.guest_name || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const canvasRef = useRef(null);
  const ctxRef = useRef(null);
  const isDrawingRef = useRef(false);
  const hasDrawnRef = useRef(false);

  const initCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctxRef.current = ctx;
    hasDrawnRef.current = false;
  }, []);

  useEffect(() => {
    const timer = setTimeout(initCanvas, 100);
    return () => clearTimeout(timer);
  }, [initCanvas]);

  const getPos = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    if (e.touches && e.touches.length > 0) {
      return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
    }
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };
  const startDraw = (e) => {
    e.preventDefault();
    isDrawingRef.current = true;
    const ctx = ctxRef.current;
    if (!ctx) return;
    const pos = getPos(e);
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
  };
  const draw = (e) => {
    e.preventDefault();
    if (!isDrawingRef.current) return;
    const ctx = ctxRef.current;
    if (!ctx) return;
    hasDrawnRef.current = true;
    const pos = getPos(e);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
  };
  const endDraw = (e) => {
    e.preventDefault();
    isDrawingRef.current = false;
  };
  const clearCanvas = () => {
    const canvas = canvasRef.current;
    const ctx = ctxRef.current;
    if (canvas && ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      hasDrawnRef.current = false;
    }
  };

  const handleSubmit = async () => {
    setError('');
    if (!signerName.trim()) {
      setError('יש להזין שם החותם');
      return;
    }
    if (!hasDrawnRef.current) {
      setError('יש לצייר חתימה לפני אישור');
      return;
    }
    setSaving(true);
    try {
      const canvas = canvasRef.current;
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
      const res = await safetyService.signGuestPass(
        token, blob, signerName.trim(), data.briefing_version
      );
      onSigned(res);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || '';
      // qrg-briefing-edit E3 — the text changed between read and sign:
      // reload the CURRENT briefing so the guest re-reads and re-signs.
      if (status === 409 && detail.includes('נוסח התדריך עודכן')) {
        onStale?.(detail);
      } else if (status === 409) {
        setError('התדריך כבר נחתם');
      } else {
        setError(detail || 'שגיאה בשליחת החתימה — נסה שוב');
      }
      setSaving(false);
    }
  };

  // Briefing text: first line is the title, rest are the numbered clauses.
  const lines = (data.briefing_text || '').split('\n');
  const title = lines[0] || 'תדריך בטיחות למבקרים';
  const body = lines.slice(1).join('\n');

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 flex flex-col">
      <GateBackButton />
      <div className="bg-amber-500 text-white px-5 pt-8 pb-5 text-center">
        <h1 className="text-xl font-extrabold">{title}</h1>
        <p className="mt-2 text-sm font-semibold">
          {data.guest_name}{data.guest_company ? ` · ${data.guest_company}` : ''}
        </p>
      </div>
      <div className="flex-1 px-5 py-5 max-w-md w-full mx-auto space-y-5">
        <pre className="whitespace-pre-wrap font-sans text-[15px] leading-relaxed text-slate-800 text-right">
          {body}
        </pre>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">שם החותם</label>
          <input
            type="text"
            value={signerName}
            onChange={(e) => setSignerName(e.target.value)}
            placeholder="שם החותם"
            dir="rtl"
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white
              focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-400"
          />
        </div>

        <div className="space-y-2">
          <div className="border-2 border-slate-300 rounded-xl overflow-hidden bg-white">
            <canvas
              ref={canvasRef}
              style={{ width: '100%', height: '180px', touchAction: 'none' }}
              className="cursor-crosshair"
              onMouseDown={startDraw}
              onMouseMove={draw}
              onMouseUp={endDraw}
              onMouseLeave={endDraw}
              onTouchStart={startDraw}
              onTouchMove={draw}
              onTouchEnd={endDraw}
            />
          </div>
          <button
            type="button"
            onClick={clearCanvas}
            className="flex items-center gap-1.5 text-xs text-slate-500 font-medium px-2 py-1"
          >
            <Eraser className="w-3.5 h-3.5" />
            נקה
          </button>
        </div>

        {error && (
          <p className="text-sm text-red-600 font-medium text-center">{error}</p>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={saving}
          className="w-full flex items-center justify-center gap-1.5 py-3.5 bg-amber-500 text-white rounded-xl text-base font-bold
            active:scale-[0.98] disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          אני מאשר/ת ומאשר/ת חתימה
        </button>
      </div>
    </div>
  );
}

export default function GatePage() {
  const { token } = useParams();
  const [state, setState] = useState({ loading: true, data: null, error: false });
  // qrg-briefing-edit E3 — one-shot notice after a stale-version 409 reload.
  const [staleNotice, setStaleNotice] = useState('');

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
        <GateBackButton />
        <p className="text-slate-500 text-lg">בודק סטטוס כניסה…</p>
      </div>
    );
  }

  const d = state.data;

  // Network failure OR invalid token — same neutral gray card.
  if (state.error || !d || d.state === 'invalid') {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-200 flex flex-col items-center justify-center px-6 text-center">
        <GateBackButton />
        <HelpCircle className="w-20 h-20 text-slate-400 mb-4" />
        <h1 className="text-2xl font-bold text-slate-700">קוד לא תקף</h1>
        <p className="text-slate-500 mt-2 text-lg">
          {state.error ? 'לא ניתן לבדוק כעת — נסה שוב' : 'יש לפנות למנהל העבודה באתר'}
        </p>
      </div>
    );
  }

  // qrg-guest — unsigned pass: full-screen briefing + inline signature.
  if (d.state === 'guest_briefing') {
    return (
      <>
        {staleNotice && (
          <div dir="rtl" className="fixed top-0 inset-x-0 z-50 bg-amber-500 text-white text-sm font-semibold text-center px-4 py-2.5">
            {staleNotice}
          </div>
        )}
        <GuestBriefingScreen
          key={`v${d.briefing_version}`}
          token={token}
          data={d}
          onSigned={(res) => {
            setStaleNotice('');
            setState({ loading: false, data: res, error: false });
          }}
          onStale={(msg) => {
            // Re-fetch the CURRENT briefing so the guest re-reads + re-signs.
            setStaleNotice(msg || 'נוסח התדריך עודכן — יש לקרוא ולחתום שוב');
            setState({ loading: true, data: null, error: false });
            safetyService.getGateStatus(token)
              .then((data) => setState({ loading: false, data, error: false }))
              .catch(() => setState({ loading: false, data: null, error: true }));
          }}
        />
      </>
    );
  }

  // qrg-guest — signed but wrong day.
  if (d.state === 'red' && d.reason === 'guest_date') {
    return (
      <div dir="rtl" className="min-h-screen bg-red-600 flex flex-col items-center justify-center px-6 text-center text-white">
        <GateBackButton />
        <XCircle className="w-24 h-24 mb-4" />
        <h1 className="text-4xl font-extrabold">אין כניסה</h1>
        {d.guest_name && <p className="text-2xl mt-3 font-semibold">{d.guest_name}</p>}
        <p className="text-xl mt-2 opacity-90">האישור תקף ליום {d.valid_on} בלבד</p>
        <p className="mt-6 text-sm opacity-75">יש לפנות למנהל העבודה</p>
      </div>
    );
  }

  if (d.state === 'red') {
    return (
      <div dir="rtl" className="min-h-screen bg-red-600 flex flex-col items-center justify-center px-6 text-center text-white">
        <GateBackButton />
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

  // qrg-guest — signed guest, valid today.
  if (d.state === 'green' && d.reason === 'guest') {
    return (
      <div dir="rtl" className="min-h-screen bg-green-600 flex flex-col items-center justify-center px-6 text-center text-white">
        <GateBackButton />
        <CheckCircle2 className="w-20 h-20" />
        <h1 className="text-4xl font-extrabold mt-4">אורח מאושר לכניסה</h1>
        <p className="text-2xl mt-3 font-semibold">{d.guest_name}</p>
        {d.guest_company && <p className="text-lg mt-1 opacity-90">{d.guest_company}</p>}
        <p className="text-lg mt-3 opacity-90">מאושר ליום {d.valid_on}</p>
        <GateQrCard token={token} />
      </div>
    );
  }

  // GREEN
  return (
    <div dir="rtl" className="min-h-screen bg-green-600 flex flex-col items-center justify-center px-6 text-center text-white">
      <GateBackButton />
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
      <GateQrCard token={token} />
    </div>
  );
}
