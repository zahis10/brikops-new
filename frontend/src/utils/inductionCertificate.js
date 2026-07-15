// ind3 E5 — shared blob download of the induction certificate PDF.
// Kept out of SafetyHomePage to avoid a circular import with the
// evidence modal.
import { safetyService } from '../services/api';

export async function downloadInductionCertificatePdf(projectId, trainingId, workerName) {
  const blob = await safetyService.downloadInductionCertificate(projectId, trainingId);
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `תעודת הדרכת אתר - ${workerName || trainingId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
