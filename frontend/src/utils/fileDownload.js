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
