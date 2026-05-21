import React, { useCallback } from 'react';
import { ScanLine } from 'lucide-react';
import { DocumentScanner, ResponseType, ScanDocumentResponseStatus } from '@capgo/capacitor-document-scanner';
import { Capacitor } from '@capacitor/core';
import { StatusBar, Style } from '@capacitor/status-bar';
import { toast } from 'sonner';

// BATCH doc-scanner-statusbar-restore-v3 (2026-05-21)
// CONFIRMED ON DEVICE: after the document scanner closes the iOS
// header overlaps the status bar, and ROTATING the device fixes
// it. Rotation makes Capacitor run resizeWebView() (via
// viewWillTransition), which re-positions the WebView below the
// status bar. The scanner's fullscreen VC dismissal leaves the
// WebView frame stale and nothing runs resizeWebView().
//
// resizeWebView() only runs when setOverlaysWebView gets a
// CHANGED value (it short-circuits otherwise — why v1/v2, which
// only ever set `false`, did nothing). So TOGGLE true→false to
// force it — the programmatic equivalent of a rotation.
//
// Timing: resizeWebView() reads the live status-bar height. Just
// after the scanner dismisses the status bar can still be hidden
// (height 0) — toggling then resizes to y=0 (still broken). So
// wait until getInfo() reports height > 0. And because the
// toggle runs WHILE the header is still broken (WebView already
// at y=0), the `true` step is a visual no-op — only the `false`
// step shows (the header snapping into place). No flicker.
async function restoreStatusBar() {
  if (!Capacitor.isNativePlatform()) return true;
  try {
    const info = await StatusBar.getInfo();
    // Status bar not fully restored yet — let the caller retry.
    if (!info || !info.height || info.height <= 0) return false;
    await StatusBar.setOverlaysWebView({ overlay: true });
    await StatusBar.setOverlaysWebView({ overlay: false });
    await StatusBar.setStyle({ style: Style.Dark });
    await StatusBar.setBackgroundColor({ color: '#0F172A' });
    return true;
  } catch (e) {
    console.warn('restoreStatusBar failed:', e);
    return true;
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
      // Poll until the status bar is back (restoreStatusBar returns
      // false while it is not), then force ONE WebView re-layout and
      // stop. ~15 tries x 350ms covers a slow dismiss (Low Power
      // Mode / Reduce Motion stretch the animation).
      let attempts = 0;
      const runRestore = async () => {
        const done = await restoreStatusBar();
        if (!done && ++attempts < 15) setTimeout(runRestore, 350);
      };
      runRestore();
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
