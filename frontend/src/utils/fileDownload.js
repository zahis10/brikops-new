import { Capacitor } from '@capacitor/core';
import { Filesystem, Directory } from '@capacitor/filesystem';
import { Share } from '@capacitor/share';

/**
 * Saves a Blob to the device and opens the share sheet on native,
 * or triggers a browser download on web.
 *
 * @param {Blob} blob - The file data
 * @param {string} filename - File name with extension (e.g. "report.pdf")
 * @param {string} mimeType - e.g. "application/pdf" or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
 * @returns {Promise<{success: boolean, filename: string, uri?: string}>}
 */
export async function downloadBlob(blob, filename, mimeType) {
  const isNative = Capacitor.isNativePlatform?.() || false;

  if (!isNative) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
    return { success: true, filename };
  }

  const base64 = await blobToBase64(blob);
  const result = await Filesystem.writeFile({
    path: filename,
    data: base64,
    directory: Directory.Documents,
  });

  try {
    await Share.share({
      title: filename,
      url: result.uri,
      dialogTitle: 'שמור או שתף קובץ',
    });
  } catch (err) {
    if (err?.message && !/cancel/i.test(err.message)) {
      throw err;
    }
  }

  return { success: true, filename, uri: result.uri };
}

/**
 * qrg-share-fix S1 — share a plain-TEXT message (entry-code messages).
 * Native → Share.share({text}) (cancel-tolerant like downloadBlob).
 * Web → navigator.share({text}) when available, else copy to the clipboard
 * and return {copied:true} so the caller can toast "הועתק".
 * downloadBlob above stays byte-identical — other features depend on it.
 *
 * @param {string} message - The full message text (already localized)
 * @returns {Promise<{success: boolean, copied?: boolean}>}
 */
export async function shareText(message) {
  const isNative = Capacitor.isNativePlatform?.() || false;

  if (isNative) {
    try {
      await Share.share({ text: message });
    } catch (err) {
      if (err?.message && !/cancel/i.test(err.message)) {
        throw err;
      }
    }
    return { success: true };
  }

  if (typeof navigator !== 'undefined' && navigator.share) {
    try {
      await navigator.share({ text: message });
      return { success: true };
    } catch (err) {
      // AbortError = user closed the sheet — not a failure, and NOT a
      // reason to also copy (that would surprise the user).
      if (err?.name === 'AbortError') return { success: true };
      // Fall through to clipboard on any other web-share failure.
    }
  }

  await navigator.clipboard.writeText(message);
  return { success: true, copied: true };
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const dataUrl = reader.result;
      const base64 = dataUrl.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
