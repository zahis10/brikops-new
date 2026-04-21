import { useEffect } from 'react';

/**
 * Web OTP API autofill hook.
 * On mount: if navigator.credentials supports OTPCredential (Android Chrome,
 * desktop Chrome, and some Android WebViews), requests a one-time code from
 * an incoming SMS that ends with `@<origin> #<code>`. When the user taps the
 * popup, the code is written via setCode.
 *
 * Silently no-ops on iOS Safari/WebKit (autocomplete="one-time-code" handles
 * those via the "From Messages" keyboard chip).
 *
 * Automatically aborts when the component unmounts.
 */
export default function useOtpAutofill(setCode) {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!('OTPCredential' in window)) return;
    if (!navigator.credentials || !navigator.credentials.get) return;

    const ac = new AbortController();

    navigator.credentials
      .get({ otp: { transport: ['sms'] }, signal: ac.signal })
      .then((cred) => {
        if (cred && typeof cred.code === 'string' && cred.code.length > 0) {
          const digits = cred.code.replace(/\D/g, '').slice(0, 6);
          if (digits.length === 6) {
            setCode(digits);
          }
        }
      })
      .catch((err) => {
        if (err && err.name !== 'AbortError') {
          // eslint-disable-next-line no-console
          console.debug('[useOtpAutofill] Web OTP not available:', err.name);
        }
      });

    return () => ac.abort();
  }, [setCode]);
}
