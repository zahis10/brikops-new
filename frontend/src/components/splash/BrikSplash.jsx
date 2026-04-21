import React, { useEffect, useRef, useState } from 'react';
import { Capacitor } from '@capacitor/core';
import D2DailySplash from './D2DailySplash';
import D3ABrickAssembly from './D3ABrickAssembly';

const LAST_SEEN_VERSION_KEY = 'brikops_last_seen_version_v2';
const MIN_DURATION_MS = { D3A: 3600, D2: 800 };
const FADE_OUT_MS = 250;

const BUILD_SHA = (process.env.REACT_APP_GIT_SHA || '').slice(0, 7) || 'dev';
const BUILD_TAG = `W2c · ${BUILD_SHA}`;

/**
 * BrikSplash — top-level splash overlay that owns its own minimum
 * display lifecycle.
 *
 * Mounted ONCE at the App shell, wrapping the routed app tree as
 * `<BrikSplash isAppReady={!authLoading}>{<AppRoutes/>}</BrikSplash>`.
 * It always renders `children` underneath; on top it paints a fixed
 * full-screen overlay (D2 or D3-A) until BOTH:
 *   1. The minimum display time has elapsed
 *      (3600ms for D3-A, 800ms for D2), and
 *   2. The parent signals `isAppReady === true` (auth resolved, etc.)
 *
 * After the overlay first reveals the children, it never re-overlays
 * for the lifetime of this component (one-shot via `revealedRef`).
 *
 * Variant decision:
 *   - D3-A (Brick Assembly): first launch + after every version bump.
 *     Persisted to Preferences ONLY after D3-A's onComplete fires, so
 *     killing the app mid-animation re-shows D3-A on next launch.
 *   - D2 (Skeleton + Shimmer): every other launch. Web always uses D2.
 *
 * The overlay fades out over 250ms once the gate opens, then unmounts.
 */
export default function BrikSplash({ isAppReady = true, children = null }) {
  const [variant, setVariant] = useState(null); // null | 'D2' | 'D3A'
  const [d3aDone, setD3aDone] = useState(false);
  const [pendingVersionToSave, setPendingVersionToSave] = useState(null);
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);
  const [hiding, setHiding] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const revealedRef = useRef(false);

  // 1. Decide variant on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!Capacitor.isNativePlatform?.()) {
        if (!cancelled) setVariant('D2');
        return;
      }
      try {
        const { App } = await import('@capacitor/app');
        const { Preferences } = await import('@capacitor/preferences');
        const info = await App.getInfo();
        const currentVersion = info?.version;
        const { value: lastSeenVersion } = await Preferences.get({
          key: LAST_SEEN_VERSION_KEY,
        });
        if (cancelled) return;
        if (!lastSeenVersion || lastSeenVersion !== currentVersion) {
          setPendingVersionToSave(currentVersion);
          setVariant('D3A');
        } else {
          setVariant('D2');
        }
      } catch (e) {
        console.warn('[BrikSplash] version check failed, falling back to D2:', e);
        if (!cancelled) setVariant('D2');
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // 2. Start minimum-display timer once the variant is known.
  useEffect(() => {
    if (!variant) return;
    const ms = MIN_DURATION_MS[variant === 'D3A' ? 'D3A' : 'D2'];
    const t = setTimeout(() => setMinTimeElapsed(true), ms);
    return () => clearTimeout(t);
  }, [variant]);

  // 3. Persist version ONLY after D3-A actually finished playing in full.
  useEffect(() => {
    if (!d3aDone || !pendingVersionToSave) return;
    (async () => {
      try {
        const { Preferences } = await import('@capacitor/preferences');
        await Preferences.set({
          key: LAST_SEEN_VERSION_KEY,
          value: pendingVersionToSave,
        });
      } catch (e) {
        console.warn('[BrikSplash] failed to persist version:', e);
      }
    })();
  }, [d3aDone, pendingVersionToSave]);

  // 4. Open the gate when min time + isAppReady (+ d3aDone for D3-A).
  //    One-shot: once revealedRef flips true, never re-overlay.
  const gateOpen =
    variant !== null &&
    minTimeElapsed &&
    isAppReady &&
    (variant === 'D2' || d3aDone);

  useEffect(() => {
    if (!gateOpen || revealedRef.current) return;
    setHiding(true);
    const t = setTimeout(() => {
      revealedRef.current = true;
      setRevealed(true);
    }, FADE_OUT_MS);
    return () => clearTimeout(t);
  }, [gateOpen]);

  // After first reveal, just render children — no overlay ever again.
  if (revealed) return children;

  return (
    <>
      {children}
      <div
        style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          opacity: hiding ? 0 : 1,
          transition: `opacity ${FADE_OUT_MS}ms ease-out`,
          pointerEvents: hiding ? 'none' : 'auto',
        }}
      >
        {variant === null ? (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(180deg, #3A4258 0%, #323A4E 50%, #2A3142 100%)',
          }}/>
        ) : variant === 'D3A' && !d3aDone ? (
          <D3ABrickAssembly onComplete={() => setD3aDone(true)} />
        ) : (
          <D2DailySplash isReady={isAppReady && minTimeElapsed} loadingText="טוען" />
        )}
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)',
            left: 0,
            right: 0,
            textAlign: 'center',
            fontSize: '10px',
            fontWeight: 500,
            letterSpacing: '0.5px',
            color: 'rgba(255, 255, 255, 0.45)',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
            pointerEvents: 'none',
            userSelect: 'none',
            zIndex: 10000,
          }}
        >
          {BUILD_TAG}
        </div>
      </div>
    </>
  );
}
