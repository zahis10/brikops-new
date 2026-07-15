// ind3 E5 — shared blob download of the induction certificate PDF.
// Kept out of SafetyHomePage to avoid a circular import with the
// evidence modal.
// ind3-fix3 F1: route through downloadBlob — <a download> blob anchors
// don't work in the native WebView (iOS/Android); downloadBlob uses
// Filesystem + Share sheet on native, anchor on web.
import { safetyService } from '../services/api';
import { downloadBlob } from './fileDownload';

export async function downloadInductionCertificatePdf(projectId, trainingId, workerName) {
  const blob = await safetyService.downloadInductionCertificate(projectId, trainingId);
  await downloadBlob(
    blob,
    `תעודת הדרכת אתר - ${workerName || trainingId}.pdf`,
    'application/pdf'
  );
}
