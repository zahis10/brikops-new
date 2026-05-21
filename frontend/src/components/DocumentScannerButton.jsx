import React, { useCallback } from 'react';
import { ScanLine } from 'lucide-react';
import { DocumentScanner, ResponseType, ScanDocumentResponseStatus } from '@capgo/capacitor-document-scanner';
import { Capacitor } from '@capacitor/core';
import { StatusBar } from '@capacitor/status-bar';
import { toast } from 'sonner';

// BATCH doc-scanner-DIAGNOSTIC (2026-05-21) — TEMPORARY, NOT a fix.
// v1/v2/v3 all failed. This measures the real WebView state after
// the scanner closes and shows it in an on-screen panel, so we can
// see what is actually wrong (and what a device rotation changes).
// Reverted once the real cause is identified.
async function showScannerDiagnostics() {
  if (!Capacitor.isNativePlatform()) return;
  const ID = 'brikops-scanner-diag';

  const readSafeAreaInsets = () => {
    const probe = document.createElement('div');
    probe.style.cssText =
      'position:fixed;top:0;left:0;visibility:hidden;pointer-events:none;' +
      'padding-top:env(safe-area-inset-top);' +
      'padding-bottom:env(safe-area-inset-bottom);' +
      'padding-left:env(safe-area-inset-left);' +
      'padding-right:env(safe-area-inset-right);';
    document.body.appendChild(probe);
    const cs = getComputedStyle(probe);
    const v = {
      top: cs.paddingTop, bottom: cs.paddingBottom,
      left: cs.paddingLeft, right: cs.paddingRight,
    };
    probe.remove();
    return v;
  };

  const measure = async () => {
    let info = {};
    try { info = await StatusBar.getInfo(); }
    catch (e) { info = { error: String(e) }; }
    const sa = readSafeAreaInsets();
    const vv = window.visualViewport || {};
    const text = [
      '=== SCANNER DIAG @ ' + new Date().toLocaleTimeString() + ' ===',
      'innerHeight x innerWidth: ' + window.innerHeight + ' x ' + window.innerWidth,
      'screen.height x width: ' + window.screen.height + ' x ' + window.screen.width,
      'visualViewport h/offsetTop/pageTop/scale: ' +
        vv.height + ' / ' + vv.offsetTop + ' / ' + vv.pageTop + ' / ' + vv.scale,
      'documentElement.clientHeight: ' + document.documentElement.clientHeight,
      'safe-area-inset top/bottom: ' + sa.top + ' / ' + sa.bottom,
      'safe-area-inset left/right: ' + sa.left + ' / ' + sa.right,
      'StatusBar.getInfo: overlays=' + info.overlays +
        ' visible=' + info.visible + ' height=' + info.height +
        ' style=' + info.style + (info.error ? ' ERR=' + info.error : ''),
    ].join('\n');
    console.log('[BRIKOPS DIAG]\n' + text);
    return text;
  };

  let panel = document.getElementById(ID);
  if (!panel) {
    panel = document.createElement('div');
    panel.id = ID;
    panel.style.cssText =
      'position:fixed;top:120px;left:8px;right:8px;z-index:2147483647;' +
      'background:rgba(0,0,0,0.92);color:#00ff66;' +
      'font:12px/1.45 ui-monospace,Menlo,monospace;padding:10px;' +
      'border:2px solid #00ff66;border-radius:8px;white-space:pre-wrap;' +
      'direction:ltr;text-align:left;';
    const textEl = document.createElement('div');
    textEl.id = ID + '-text';
    panel.appendChild(textEl);
    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'margin-top:8px;display:flex;gap:8px;';
    const btnMeasure = document.createElement('button');
    btnMeasure.textContent = 'מדוד שוב';
    btnMeasure.style.cssText =
      'flex:1;padding:8px;background:#00ff66;color:#000;border:0;' +
      'border-radius:6px;font-size:14px;font-weight:bold;';
    btnMeasure.onclick = async () => {
      const el = document.getElementById(ID + '-text');
      if (el) el.textContent = await measure();
    };
    const btnClose = document.createElement('button');
    btnClose.textContent = '✕';
    btnClose.style.cssText =
      'width:44px;padding:8px;background:#333;color:#fff;border:0;' +
      'border-radius:6px;font-size:14px;';
    btnClose.onclick = () => panel.remove();
    btnRow.appendChild(btnMeasure);
    btnRow.appendChild(btnClose);
    panel.appendChild(btnRow);
    document.body.appendChild(panel);
  }

  const render = async () => {
    const el = document.getElementById(ID + '-text');
    if (el) el.textContent = await measure();
  };
  render();
  setTimeout(render, 1000);
  setTimeout(render, 2500);
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
      // BATCH doc-scanner-DIAGNOSTIC — show the measurement panel
      // instead of attempting a fix.
      showScannerDiagnostics();
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
