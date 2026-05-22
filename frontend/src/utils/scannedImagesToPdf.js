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
    const dataUrl = await readAsDataURL(files[i]);
    const img = await loadImage(dataUrl);
    const scale = Math.min(pageW / img.width, pageH / img.height);
    const w = img.width * scale;
    const h = img.height * scale;
    const x = (pageW - w) / 2;
    const y = (pageH - h) / 2;
    if (i > 0) pdf.addPage();
    pdf.addImage(dataUrl, 'JPEG', x, y, w, h);
  }
  const blob = pdf.output('blob');
  return new File([blob], `scan-${Date.now()}.pdf`, { type: 'application/pdf' });
}
