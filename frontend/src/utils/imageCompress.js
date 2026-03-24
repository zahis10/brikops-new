const MAX_SIZE = 800 * 1024;
const MAX_WIDTH = 1600;
const JPEG_QUALITY = 0.7;
const COMPRESS_TIMEOUT_MS = 15000;

function drawToCanvas(source, srcWidth, srcHeight) {
  let width = srcWidth;
  let height = srcHeight;
  const maxDim = Math.max(width, height);
  if (maxDim > MAX_WIDTH) {
    const scale = MAX_WIDTH / maxDim;
    width = Math.round(width * scale);
    height = Math.round(height * scale);
  }
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(source, 0, 0, width, height);
  return canvas;
}

async function canvasToFile(canvas, origName) {
  const blob = await new Promise(resolve =>
    canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY)
  );
  if (!blob || blob.size === 0) throw new Error('Canvas toBlob returned empty');
  const outName = origName.replace(/\.[^.]+$/, '.jpg');
  const f = new File([blob], outName, { type: 'image/jpeg', lastModified: Date.now() });
  f._fromCompress = true;
  return f;
}

async function _doCompress(file) {
  let lastErr = null;

  try {
    const img = new Image();
    const url = URL.createObjectURL(file);
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = () => reject(new Error('Image load failed'));
      img.src = url;
    });
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    const canvas = drawToCanvas(img, w, h);
    URL.revokeObjectURL(url);
    const result = await canvasToFile(canvas, file.name);
    return result;
  } catch (imgErr) {
    lastErr = imgErr;
    console.warn('[compress] Image() failed:', imgErr.message);
  }

  try {
    const bitmap = await createImageBitmap(file);
    const canvas = drawToCanvas(bitmap, bitmap.width, bitmap.height);
    bitmap.close();
    const result = await canvasToFile(canvas, file.name);
    return result;
  } catch (bitmapErr) {
    lastErr = bitmapErr;
    console.warn('[compress:bitmap] fallback failed:', bitmapErr.message);
  }

  const isHeic = file.type && (file.type.includes('heic') || file.type.includes('heif'));
  const ext = file.name?.toLowerCase() || '';
  const isHeicExt = ext.endsWith('.heic') || ext.endsWith('.heif');
  if (isHeic || isHeicExt) {
    console.error(`[compress] HEIC/HEIF not supported: ${file.name} (${file.type})`);
    throw { code: 'UNSUPPORTED_FORMAT', original: lastErr };
  }

  console.warn(`[compress] all methods failed for ${file.name}, using original (${(file.size/1024).toFixed(0)}KB, type=${file.type})`);
  if (!file.type || file.type === '') {
    const f = new File([file], file.name, { type: 'image/jpeg', lastModified: Date.now() });
    f._fromCompress = true;
    return f;
  }
  return file;
}

export async function compressImage(file) {
  const typeLC = (file.type || '').toLowerCase();
  const isHeicType = typeLC.includes('heic') || typeLC.includes('heif');
  if (file.size <= MAX_SIZE && typeLC.startsWith('image/') && !isHeicType) {
    return file;
  }

  try {
    const result = await Promise.race([
      _doCompress(file),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('compression timeout')), COMPRESS_TIMEOUT_MS)
      ),
    ]);
    return result;
  } catch (err) {
    if (err?.code === 'UNSUPPORTED_FORMAT') throw err;
    console.warn(`[compress:timeout] ${file.name} — compression timed out or failed (${err?.message || err}), using original (${(file.size/1024).toFixed(0)}KB)`);
    return file;
  }
}
