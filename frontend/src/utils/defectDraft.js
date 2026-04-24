const STORAGE_KEY = 'brikops_defect_draft_v1';
const MAX_AGE_MS = 30 * 60 * 1000;

export function saveDefectDraft(state) {
  try {
    const payload = { ...state, createdAt: Date.now() };
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (err) {
    console.warn('[defectDraft] save failed', err);
  }
}

export function loadDefectDraft() {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const age = Date.now() - (parsed.createdAt || 0);
    if (age > MAX_AGE_MS) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch (err) {
    console.warn('[defectDraft] load failed', err);
    return null;
  }
}

export function clearDefectDraft() {
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {}
}

export function hasDefectDraft() {
  return !!loadDefectDraft();
}

export function buildReturnToDefectUrl(draft) {
  if (!draft || !draft.projectId || !draft.unitId) return null;
  const base = draft.returnUrl || `/projects/${draft.projectId}/units/${draft.unitId}/defects`;
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}reopenDefect=1`;
}
