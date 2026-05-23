// BATCH doc-scanner-in-plans-tabs (2026-05-22)
// Combine scanned document images into ONE multi-page PDF, so a
// multi-page scan (e.g. a 5-page delivery certificate) uploads as a
// single plan file with every page preserved. jsPDF is lazy-imported
// (dynamic import) so it ships as its own chunk, loaded only when the
// user actually scans — no weight added to the main bundle.

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('file read failed'));
    reader.readAsDataURL(file);
  });
}

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('image decode failed'));
    img.src = dataUrl;
  });
}

// BATCH doc-scanner-compress (2026-05-22) — VisionKit returns
// full-resolution JPEGs; embedding them raw produced ~20-40MB
// PDFs for a 3-5 page scan and bloated S3. Downscale each page
// so its longer edge is <= MAX_EDGE and re-encode at
// JPEG_QUALITY — keeps documents fully legible (~170 DPI on A4)
// while cutting file size ~90-95%.
const MAX_EDGE = 2000;
const JPEG_QUALITY = 0.72;

// Downscale `img` (never upscale) so its longer edge is at most
// MAX_EDGE, re-encode as JPEG. Returns { dataUrl, width, height }
// for the compressed page. The scanned image is a local data
// URI, so the canvas is not cross-origin-tainted.
function compressScannedImage(img) {
  const longEdge = Math.max(img.width, img.height);
  const ratio = longEdge > MAX_EDGE ? MAX_EDGE / longEdge : 1;
  const width = Math.max(1, Math.round(img.width * ratio));
  const height = Math.max(1, Math.round(img.height * ratio));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  // high-quality smoothing keeps downscaled text crisp
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, width, height);
  return {
    dataUrl: canvas.toDataURL('image/jpeg', JPEG_QUALITY),
    width,
    height,
  };
}

// files: array of scanned image File objects (JPEG, from
//        DocumentScannerButton).
// returns: a single File — a multi-page application/pdf, one image
//          per page, each image fit-centered on an A4 page.
export async function scannedImagesToPdf(files) {
  const { jsPDF } = await import('jspdf');
  // compress: true — flate-compresses the PDF structure. The JPEG
  // page images are already compressed; this trims the rest and
  // keeps multi-page scans well under the 50 MB plans upload limit.
  const pdf = new jsPDF({ unit: 'pt', format: 'a4', compress: true });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();
  for (let i = 0; i < files.length; i += 1) {
    const rawDataUrl = await readAsDataURL(files[i]);
    const img = await loadImage(rawDataUrl);
    // BATCH doc-scanner-compress (2026-05-22) — downscale +
    // re-encode this page before embedding it in the PDF.
    const page = compressScannedImage(img);
    const scale = Math.min(pageW / page.width, pageH / page.height);
    const w = page.width * scale;
    const h = page.height * scale;
    const x = (pageW - w) / 2;
    const y = (pageH - h) / 2;
    if (i > 0) pdf.addPage();
    pdf.addImage(page.dataUrl, 'JPEG', x, y, w, h);
  }
  const blob = pdf.output('blob');
  return new File([blob], `scan-${Date.now()}.pdf`, { type: 'application/pdf' });
}
