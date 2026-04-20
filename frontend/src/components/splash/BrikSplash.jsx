import React, { useEffect, useState } from 'react';
import { Capacitor } from '@capacitor/core';
import D2DailySplash from './D2DailySplash';
import D3ABrickAssembly from './D3ABrickAssembly';

const LAST_SEEN_VERSION_KEY = 'brikops_last_seen_version';

/**
 * BrikSplash — top-level loading screen wrapper.
 *
 * Decides between two variants based on app version:
 *   - D3-A (Brick Assembly): first launch + after every version bump.
 *     Saved to Preferences ONLY after the animation completes — if the
 *     user kills the app mid-animation, they should see D3-A again next time.
 *   - D2 (Skeleton + Shimmer): every other launch. Stays mounted until
 *     `isReady` flips to true.
 *
 * When D3-A finishes (after 2100ms) and `isReady` is still false, we fall
 * through to D2, NOT to a blank dashboard. This is anchored by the final
 * return statement below.
 */
export default function BrikSplash({ isReady = false, loadingText = 'מתחבר' }) {
  // variant: null (deciding) | 'D2' | 'D3A'
  const [variant, setVariant] = useState(null);
  const [d3aDone, setD3aDone] = useState(false);
  const [pendingVersionToSave, setPendingVersionToSave] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Web fallback — no native APIs, always show D2.
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
          // First install or after a version bump → show D3-A.
          // DO NOT save the version yet — only after animation completes.
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

  // Persist version ONLY after D3-A finished playing in full.
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

  // Deciding phase — show the same gradient as the native splash so there
  // is no white flash while Preferences responds (~50-100ms).
  if (variant === null) {
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'linear-gradient(180deg, #3A4258 0%, #323A4E 50%, #2A3142 100%)',
      }}/>
    );
  }

  // D3-A is playing.
  if (variant === 'D3A' && !d3aDone) {
    return <D3ABrickAssembly onComplete={() => setD3aDone(true)} />;
  }

  // Either variant === 'D2' from the start, or D3-A finished.
  // CRITICAL: when D3-A finishes and isReady is still false, fall through
  // to D2 (Skeleton + Shimmer) — not to a blank dashboard.
  return <D2DailySplash isReady={isReady} loadingText={loadingText} />;
}
