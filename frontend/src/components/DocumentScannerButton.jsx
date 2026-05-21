import React, { useCallback } from 'react';
import { ScanLine } from 'lucide-react';
import { DocumentScanner, ResponseType, ScanDocumentResponseStatus } from '@capgo/capacitor-document-scanner';
import { Capacitor } from '@capacitor/core';
import { StatusBar, Style } from '@capacitor/status-bar';
import { toast } from 'sonner';

// BATCH doc-scanner-statusbar-restore (2026-05-21) — re-apply the
// native status-bar config after the document scanner closes.
// VisionKit's fullscreen VNDocumentCameraViewController leaves the
// Capacitor WebView frame overlaying the iOS status bar on dismiss,
// pushing the app header up under the notch. These three calls
// mirror the startup config in App.js:610-612 — keep them in sync.
async function restoreStatusBar() {
  if (!Capacitor.isNativePlatform()) return;
  try {
    await StatusBar.setOverlaysWebView({ overlay: false });
    await StatusBar.setBackgroundColor({ color: '#0F172A' });
    await StatusBar.setStyle({ style: Style.Dark });
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
      // The scanner dismissed a fullscreen native VC — the WebView
      // frame snaps back over the status bar. Re-apply now, after
      // the ~350ms dismiss animation, and once more at 1200ms as a
      // slow-path backup: Low Power Mode / Reduce Motion / thermal
      // throttling all stretch iOS animations, so a single fixed
      // delay can land BEFORE the layout pass and be overridden.
      // restoreStatusBar is idempotent — once the frame is correct,
      // extra calls are harmless no-ops.
      restoreStatusBar();
      setTimeout(restoreStatusBar, 450);
      setTimeout(restoreStatusBar, 1200);
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
