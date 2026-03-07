const MAX_SIZE = 800 * 1024;
const MAX_WIDTH = 1600;
const JPEG_QUALITY = 0.7;

function drawToCanvas(source, srcWidth, srcHeight) {
  let width = srcWidth;
  let height = srcHeight;
  if (width > MAX_WIDTH) {
    height = Math.round((height * MAX_WIDTH) / width);
    width = MAX_WIDTH;
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
  return new File([blob], outName, { type: 'image/jpeg', lastModified: Date.now() });
}

export async function compressImage(file) {
  if (file.size <= MAX_SIZE && file.type && file.type.startsWith('image/') && !file.type.includes('heic')) {
    return file;
  }

  try {
    const bitmap = await createImageBitmap(file);
    const canvas = drawToCanvas(bitmap, bitmap.width, bitmap.height);
    bitmap.close();
    const result = await canvasToFile(canvas, file.name);
    console.log(`[compress:bitmap] ${file.name}: ${(file.size/1024).toFixed(0)}KB → ${(result.size/1024).toFixed(0)}KB`);
    return result;
  } catch (bitmapErr) {
    console.warn('[compress:bitmap] failed, trying Image fallback:', bitmapErr.message);
  }

  try {
    const img = new Image();
    const url = URL.createObjectURL(file);
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = () => reject(new Error('Image load failed'));
      img.src = url;
    });
    const canvas = drawToCanvas(img, img.naturalWidth, img.naturalHeight);
    URL.revokeObjectURL(url);
    const result = await canvasToFile(canvas, file.name);
    console.log(`[compress:img] ${file.name}: ${(file.size/1024).toFixed(0)}KB → ${(result.size/1024).toFixed(0)}KB`);
    return result;
  } catch (imgErr) {
    console.warn('[compress:img] fallback also failed:', imgErr.message);
  }

  console.warn(`[compress] all methods failed for ${file.name}, using original (${(file.size/1024).toFixed(0)}KB, type=${file.type})`);
  if (!file.type || file.type === '') {
    return new File([file], file.name, { type: 'image/jpeg', lastModified: Date.now() });
  }
  return file;
}
