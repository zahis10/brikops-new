import React, { useCallback } from 'react';
import { ScanLine } from 'lucide-react';
import { DocumentScanner, ResponseType, ScanDocumentResponseStatus } from '@capgo/capacitor-document-scanner';
import { Capacitor } from '@capacitor/core';
import { StatusBar, Style } from '@capacitor/status-bar';
import { toast } from 'sonner';

// BATCH doc-scanner-statusbar-restore-v2 (2026-05-21)
// After the document scanner's fullscreen native VC closes,
// Capacitor's bridge re-runs handleViewDidAppear, which
// re-applies the StatusBar plugin CONFIG. The real fix is the
// StatusBar block in capacitor.config.json (overlaysWebView
// false). This helper is the OTA safety net for devices still
// on the pre-config native build.
//
// Capacitor's setOverlaysWebView is a no-op when the value is
// unchanged (it short-circuits before resizeWebView). So we
// must only call it when the WebView is ACTUALLY overlaying —
// getInfo() tells us. When it is, setOverlaysWebView(false) is
// a real change and triggers the WebView re-layout.
async function restoreStatusBar() {
  if (!Capacitor.isNativePlatform()) return;
  try {
    const info = await StatusBar.getInfo();
    if (info?.overlays) {
      await StatusBar.setOverlaysWebView({ overlay: false });
    }
    await StatusBar.setStyle({ style: Style.Dark });
    await StatusBar.setBackgroundColor({ color: '#0F172A' });
  } catch (e) {
    console.warn('restoreStatusBar failed:', e);
  }
}

export default function DocumentScannerButton({ onScan, label = 'סרוק מסמך', className = '' }) {
  const handleClick = useCallback(async () => {
    try {
      const result = await DocumentScanner.scanDocument({
        responseType: ResponseType.ImageFilePath,
      });
      if (result?.status === ScanDocumentResponseStatus.Cancel) return;
      const uris = result?.scannedImages || [];
      if (uris.length === 0) return;
      const files = await Promise.all(uris.map(async (uri, i) => {
        // BATCH H.2a-hotfix-1 — convert file:// URI to WebView-readable URL.
        // iOS WKWebView blocks direct fetch on file:// per security policy.
        // Capacitor.convertFileSrc() returns a capacitor://... URL on iOS
        // and a localhost-based URL on Android, both fetch-safe.
        const webViewUrl = Capacitor.convertFileSrc(uri);
        const resp = await fetch(webViewUrl);
        const blob = await resp.blob();
        return new File([blob], `scan-${Date.now()}-${i}.jpg`, { type: 'image/jpeg' });
      }));
      if (files.length > 0) onScan(files);
    } catch (err) {
      console.error('DocumentScanner error:', err, 'stack:', err?.stack);
      toast.error('שגיאה בסריקת המסמך');
    } finally {
      // Capacitor re-applies its StatusBar config at an
      // unobservable moment after the native VC dismisses (~350ms+,
      // longer under Low Power Mode / Reduce Motion). There is no
      // JS event for it — poll a few times and correct whenever
      // getInfo() reports the WebView is overlaying.
      restoreStatusBar();
      setTimeout(restoreStatusBar, 700);
      setTimeout(restoreStatusBar, 1500);
      setTimeout(restoreStatusBar, 3000);
      setTimeout(restoreStatusBar, 5000);
    }
  }, [onScan]);

  if (!Capacitor.isNativePlatform()) return null;

  return (
    <button type="button" onClick={handleClick} className={className}>
      <ScanLine className="w-6 h-6 text-emerald-500" />
      <span className="text-xs font-medium text-emerald-700">{label}</span>
    </button>
  );
}
