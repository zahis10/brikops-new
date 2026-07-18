// qrg2-station F2 — PUBLIC guard-station page (/station/:token, no auth).
// The guard's phone becomes a scanner: full-screen camera preview with a
// continuous decode loop (native BarcodeDetector when available, jsQR
// canvas fallback ~4fps), a big green/red verdict overlay with sound, a
// 5s same-code debounce, wake-lock + torch, and a manual name-search
// fallback (decision 3א). RTL, mobile-first, dark. NO app chrome.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Camera, Flashlight, Search, X, QrCode, RefreshCw } from 'lucide-react';
import { safetyService } from '../services/api';

const SCAN_INTERVAL_MS = 250; // ~4 fps
const RESULT_MS = 2500;
const DEBOUNCE_SAME_CODE_MS = 5000;

// WebAudio feedback — high beep (green) / low buzz (red). Fail-soft.
let _audioCtx = null;
const playTone = (ok) => {
  try {
    _audioCtx = _audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const ctx = _audioCtx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = ok ? 'sine' : 'square';
    osc.frequency.value = ok ? 1320 : 160;
    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + (ok ? 0.35 : 0.6));
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + (ok ? 0.35 : 0.6));
  } catch { /* no audio — fine */ }
};

const initialsOf = (name) => {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase();
};

const PersonBadge = ({ name, photoUrl, size = 96 }) => {
  const [broken, setBroken] = useState(false);
  useEffect(() => { setBroken(false); }, [photoUrl]);
  if (photoUrl && !broken) {
    return (
      <img
        src={photoUrl}
        alt={name || ''}
        onError={() => setBroken(true)}
        style={{ width: size, height: size }}
        className="rounded-full object-cover border-4 border-white/60 shadow-lg"
      />
    );
  }
  return (
    <div
      style={{ width: size, height: size }}
      className="rounded-full bg-white/25 border-4 border-white/60 flex items-center justify-center text-4xl font-bold text-white shadow-lg"
    >
      {initialsOf(name)}
    </div>
  );
};

const GateStationPage = () => {
  const { token: stationToken } = useParams();

  const [meta, setMeta] = useState(null);        // {project_name}
  const [stationDead, setStationDead] = useState(false);
  const [camError, setCamError] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [torchSupported, setTorchSupported] = useState(false);
  const [result, setResult] = useState(null);    // check response
  const [manualOpen, setManualOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [items, setItems] = useState([]);
  const [searching, setSearching] = useState(false);
  const [netErr, setNetErr] = useState(false);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const trackRef = useRef(null);
  const loopRef = useRef(null);
  const busyRef = useRef(false);
  const lastCodeRef = useRef({ code: null, at: 0 });
  const wakeLockRef = useRef(null);
  const detectorRef = useRef(null);
  const jsqrRef = useRef(null);
  const mountedRef = useRef(true);

  // ---- station meta / validity -------------------------------------------
  useEffect(() => {
    mountedRef.current = true;
    (async () => {
      try {
        const m = await safetyService.getStationMeta(stationToken);
        if (mountedRef.current) setMeta(m);
      } catch (e) {
        if (mountedRef.current) {
          if (e?.response?.status === 404) setStationDead(true);
          else setNetErr(true);
        }
      }
    })();
    return () => { mountedRef.current = false; };
  }, [stationToken]);

  // ---- wake lock (fail-soft) ---------------------------------------------
  useEffect(() => {
    const acquire = async () => {
      try {
        if (navigator.wakeLock?.request) {
          wakeLockRef.current = await navigator.wakeLock.request('screen');
        }
      } catch { /* fail-soft */ }
    };
    acquire();
    const onVis = () => { if (document.visibilityState === 'visible') acquire(); };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      try { wakeLockRef.current?.release(); } catch { /* noop */ }
    };
  }, []);

  // ---- camera ------------------------------------------------------------
  const stopCamera = useCallback(() => {
    if (loopRef.current) { clearInterval(loopRef.current); loopRef.current = null; }
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch { /* noop */ }
    streamRef.current = null;
    trackRef.current = null;
  }, []);

  const handleDecoded = useCallback(async (raw) => {
    const now = Date.now();
    if (busyRef.current) return;
    if (lastCodeRef.current.code === raw && now - lastCodeRef.current.at < DEBOUNCE_SAME_CODE_MS) return;
    lastCodeRef.current = { code: raw, at: now };
    busyRef.current = true;
    try {
      const res = await safetyService.stationCheck(stationToken, raw);
      if (!mountedRef.current) return;
      setResult(res);
      playTone(res.result === 'green');
      setTimeout(() => {
        if (mountedRef.current) setResult(null);
        busyRef.current = false;
      }, RESULT_MS);
    } catch (e) {
      busyRef.current = false;
      if (!mountedRef.current) return;
      if (e?.response?.status === 404) setStationDead(true);
      else { setNetErr(true); setTimeout(() => mountedRef.current && setNetErr(false), 3000); }
    }
  }, [stationToken]);

  const startCamera = useCallback(async () => {
    setCamError(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }, audio: false,
      });
      if (!mountedRef.current) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = stream;
      const track = stream.getVideoTracks()[0];
      trackRef.current = track;
      try {
        setTorchSupported(!!track.getCapabilities?.().torch);
      } catch { setTorchSupported(false); }
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play().catch(() => {});
      }
      // Decoder: native BarcodeDetector when available, else jsQR.
      if ('BarcodeDetector' in window && !detectorRef.current) {
        try {
          detectorRef.current = new window.BarcodeDetector({ formats: ['qr_code'] });
        } catch { detectorRef.current = null; }
      }
      if (!detectorRef.current && !jsqrRef.current) {
        jsqrRef.current = (await import('jsqr')).default;
      }
      if (loopRef.current) clearInterval(loopRef.current);
      loopRef.current = setInterval(async () => {
        const v = videoRef.current;
        if (!v || v.readyState < 2 || busyRef.current) return;
        try {
          if (detectorRef.current) {
            const codes = await detectorRef.current.detect(v);
            if (codes?.length && codes[0].rawValue) handleDecoded(codes[0].rawValue);
          } else if (jsqrRef.current) {
            const canvas = canvasRef.current;
            if (!canvas) return;
            const w = 480;
            const h = Math.round((v.videoHeight / v.videoWidth) * w) || 360;
            canvas.width = w; canvas.height = h;
            const ctx2d = canvas.getContext('2d', { willReadFrequently: true });
            ctx2d.drawImage(v, 0, 0, w, h);
            const img = ctx2d.getImageData(0, 0, w, h);
            const found = jsqrRef.current(img.data, w, h, { inversionAttempts: 'dontInvert' });
            if (found?.data) handleDecoded(found.data);
          }
        } catch { /* single-frame decode failure — keep looping */ }
      }, SCAN_INTERVAL_MS);
    } catch {
      if (mountedRef.current) setCamError(true);
    }
  }, [handleDecoded]);

  useEffect(() => {
    if (!stationDead && !manualOpen) startCamera();
    return stopCamera;
  }, [stationDead, manualOpen, startCamera, stopCamera]);

  const toggleTorch = async () => {
    try {
      await trackRef.current?.applyConstraints({ advanced: [{ torch: !torchOn }] });
      setTorchOn((v) => !v);
    } catch { /* unsupported — button hidden anyway */ }
  };

  // ---- manual search (debounced 300ms) -----------------------------------
  useEffect(() => {
    if (!manualOpen) return undefined;
    const q = query.trim();
    if (q.length < 2) { setItems([]); return undefined; }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await safetyService.stationSearch(stationToken, q);
        if (mountedRef.current) setItems(res.items || []);
      } catch (e) {
        if (e?.response?.status === 404) setStationDead(true);
      } finally {
        if (mountedRef.current) setSearching(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [query, manualOpen, stationToken]);

  const checkWorker = async (workerId) => {
    if (busyRef.current) return;
    busyRef.current = true;
    try {
      const res = await safetyService.stationCheckWorker(stationToken, workerId);
      if (!mountedRef.current) return;
      setManualOpen(false);
      setQuery('');
      setItems([]);
      setResult(res);
      playTone(res.result === 'green');
      setTimeout(() => {
        if (mountedRef.current) setResult(null);
        busyRef.current = false;
      }, RESULT_MS);
    } catch (e) {
      busyRef.current = false;
      if (e?.response?.status === 404) setStationDead(true);
      else { setNetErr(true); setTimeout(() => mountedRef.current && setNetErr(false), 3000); }
    }
  };

  // ---- render --------------------------------------------------------------
  if (stationDead) {
    return (
      <div dir="rtl" className="min-h-screen bg-[#10161f] text-white flex flex-col items-center justify-center p-6 text-center">
        <QrCode className="w-14 h-14 text-white/40 mb-4" />
        <h1 className="text-2xl font-bold mb-2">עמדה לא תקפה</h1>
        <p className="text-white/70">פנה למנהל הפרויקט לקבלת קישור עמדה חדש.</p>
      </div>
    );
  }

  const isGreen = result?.result === 'green';
  const isInvalid = result?.result === 'invalid';

  return (
    <div dir="rtl" className="min-h-screen bg-[#10161f] text-white flex flex-col relative overflow-hidden">
      {/* header strip */}
      <header className="bg-[#1c2735] px-4 py-3 flex items-center justify-between shrink-0 z-10">
        <h1 className="text-base font-bold truncate">
          עמדת שער{meta?.project_name ? ` · ${meta.project_name}` : ''}
        </h1>
        <div className="flex items-center gap-2">
          {torchSupported && !manualOpen && (
            <button
              type="button"
              onClick={toggleTorch}
              aria-label="פנס"
              className={`p-2 rounded-lg min-h-[44px] min-w-[44px] flex items-center justify-center ${torchOn ? 'bg-amber-500 text-white' : 'bg-white/10 text-white/80'}`}
            >
              <Flashlight className="w-5 h-5" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setManualOpen((v) => !v)}
            className="px-3 py-2 rounded-lg bg-white/10 text-sm flex items-center gap-1.5 min-h-[44px]"
          >
            {manualOpen ? <X className="w-4 h-4" /> : <Search className="w-4 h-4" />}
            {manualOpen ? 'סגור' : 'חיפוש ידני'}
          </button>
        </div>
      </header>

      {/* SCAN MODE */}
      {!manualOpen && (
        <div className="flex-1 relative">
          {camError ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
              <Camera className="w-12 h-12 text-white/40 mb-4" />
              <h2 className="text-lg font-bold mb-2">אין גישה למצלמה</h2>
              <p className="text-white/70 text-sm mb-4">
                יש לאשר גישה למצלמה בהגדרות הדפדפן ולנסות שוב.
              </p>
              <button
                type="button"
                onClick={startCamera}
                className="px-4 py-2.5 rounded-lg bg-amber-500 text-white font-medium flex items-center gap-2 min-h-[44px]"
              >
                <RefreshCw className="w-4 h-4" />
                נסה שוב
              </button>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                playsInline
                muted
                className="absolute inset-0 w-full h-full object-cover"
              />
              {/* scan frame */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-64 h-64 border-2 border-white/70 rounded-2xl" />
              </div>
              <p className="absolute bottom-6 inset-x-0 text-center text-white/80 text-sm px-4">
                כוון את המצלמה אל קוד ה-QR של העובד או האורח
              </p>
            </>
          )}
          <canvas ref={canvasRef} className="hidden" />
        </div>
      )}

      {/* MANUAL MODE */}
      {manualOpen && (
        <div className="flex-1 p-4 overflow-y-auto">
          <div className="relative mb-3">
            <Search className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-white/50" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="חפש עובד לפי שם…"
              className="w-full bg-white/10 border border-white/20 rounded-xl py-3 pr-9 pl-3 text-white placeholder-white/40 focus:outline-none focus:border-amber-500"
            />
          </div>
          {searching && <p className="text-white/50 text-sm text-center py-4">מחפש…</p>}
          {!searching && query.trim().length >= 2 && items.length === 0 && (
            <p className="text-white/50 text-sm text-center py-4">לא נמצאו עובדים</p>
          )}
          <div className="space-y-2">
            {items.map((w) => (
              <button
                key={w.worker_id}
                type="button"
                onClick={() => checkWorker(w.worker_id)}
                className="w-full flex items-center gap-3 bg-white/5 hover:bg-white/10 rounded-xl p-3 text-right min-h-[56px]"
              >
                <PersonBadge name={w.name} photoUrl={w.photo_display_url} size={40} />
                <span className="font-medium">{w.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* network toast */}
      {netErr && (
        <div className="absolute top-16 inset-x-4 bg-red-600/90 text-white text-sm rounded-xl px-4 py-3 text-center z-20">
          שגיאת רשת — נסה שוב
        </div>
      )}

      {/* RESULT OVERLAY */}
      {result && (
        <div
          className={`absolute inset-0 z-30 flex flex-col items-center justify-center p-6 text-center ${isGreen ? 'bg-green-600' : 'bg-red-600'}`}
        >
          {isGreen ? (
            <>
              <PersonBadge name={result.name} photoUrl={result.photo_display_url} size={96} />
              <div className="text-4xl font-extrabold mt-4 break-words max-w-full">{result.name}</div>
              <div className="text-7xl mt-4" aria-hidden>✓</div>
              <div className="text-xl font-bold mt-2">כניסה מאושרת</div>
            </>
          ) : (
            <>
              <div className="text-7xl" aria-hidden>✗</div>
              <div className="text-3xl font-extrabold mt-4">
                {isInvalid ? 'קוד לא תקף' : 'אין כניסה'}
              </div>
              {!isInvalid && result.name && (
                <div className="text-xl font-bold mt-2 break-words max-w-full">{result.name}</div>
              )}
              {(result.reasons || []).map((r) => (
                <div key={r} className="text-lg mt-2 text-white/90">{r}</div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default GateStationPage;
