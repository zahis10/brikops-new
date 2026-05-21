import React, { useCallback } from 'react';
import { ScanLine } from 'lucide-react';
import { DocumentScanner, ResponseType, ScanDocumentResponseStatus } from '@capgo/capacitor-document-scanner';
import { Capacitor } from '@capacitor/core';
import { StatusBar } from '@capacitor/status-bar';
import { toast } from 'sonner';

// BATCH doc-scanner-webview-reinset (2026-05-21)
// Verified on-device with Safari Web Inspector: after the document
// scanner's fullscreen VC closes, the Capacitor WebView frame is
// sometimes left full-screen (window.innerHeight === screen.height)
// instead of inset below the status bar. The web layout shifts up
// by the status-bar height and the page header lands under the
// status bar.
//
// StatusBar.getInfo() reports overlays=false even when broken, so
// the plugin sees no problem (why v1/v2/v3 failed). A device
// rotation fixes it because rotation triggers Capacitor's internal
// resizeWebView(). setOverlaysWebView only runs resizeWebView()
// when the value CHANGES, so toggling true->false forces it —
// confirmed on-device to re-inset the WebView.
//
// The bug is intermittent and can appear shortly after the
// dismiss, so poll for ~8s: whenever the WebView is full-screen,
// toggle to re-inset it; when already inset, do nothing. No
// flicker — the toggle only runs on an already-broken frame, so
// the overlay:true step is an invisible no-op and only
// overlay:false is seen (the layout snapping back).
// Module-level handle: if the user scans again within the 8s
// window (scanning several documents in a row is a normal field
// flow), cancel the previous poll instead of stacking a second
// one. Parallel polls would be harmless (idempotent) but messy.
let webViewReinsetTimer = null;
function fixWebViewAfterScanner() {
  if (!Capacitor.isNativePlatform()) return;
  if (webViewReinsetTimer) clearInterval(webViewReinsetTimer);
  let ticks = 0;
  webViewReinsetTimer = setInterval(async () => {
    ticks += 1;
    try {
      if (window.innerHeight >= window.screen.height) {
        await StatusBar.setOverlaysWebView({ overlay: true });
        await StatusBar.setOverlaysWebView({ overlay: false });
      }
    } catch (e) {
      console.warn('fixWebViewAfterScanner failed:', e);
    }
    if (ticks >= 40) {
      clearInterval(webViewReinsetTimer);
      webViewReinsetTimer = null;
    }
  }, 200);
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
      fixWebViewAfterScanner();
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
