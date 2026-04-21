import { useEffect } from 'react';
import { Capacitor } from '@capacitor/core';
import SmsRetriever from '../native/SmsRetriever';

/**
 * Android-only OTP autofill via Google Play Services SMS Retriever API.
 *
 * Mirrors the iOS-friendly useOtpAutofill hook but for Android. On any
 * non-Android platform (iOS, web) it is a no-op — iOS uses Web OTP API +
 * Associated Domains via useOtpAutofill (#393 + #394).
 *
 * Extracts the first 6-digit run from the received SMS body and feeds it
 * to setCode. Does NOT auto-submit (matches #393 UX).
 *
 * @param {(code: string) => void} setCode  state setter for the OTP input
 */
export default function useAndroidSmsRetriever(setCode) {
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    if (Capacitor.getPlatform() !== 'android') return;
    if (typeof setCode !== 'function') return;

    let cancelled = false;
    let smsListener = null;

    const handleMessage = ({ message }) => {
      if (cancelled || !message) return;
      const match = String(message).match(/\b(\d{6})\b/);
      if (match && match[1]) {
        setCode(match[1]);
      }
    };

    const wire = async () => {
      try {
        const handle = await SmsRetriever.addListener('smsReceived', handleMessage);
        if (cancelled) {
          handle?.remove?.();
          return;
        }
        smsListener = handle;
        await SmsRetriever.start();
      } catch (_e) {
        // fail-silent — autofill is a nice-to-have, never block login
      }
    };

    wire();

    return () => {
      cancelled = true;
      try { smsListener?.remove?.(); } catch (_e) { /* ignore */ }
      try { SmsRetriever.stop?.(); } catch (_e) { /* ignore */ }
    };
  }, [setCode]);
}
