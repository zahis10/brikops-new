// In-memory only. Holds the current defect draft's image objects across
// the in-app 'הוסף קבלן' navigation (react-router, no reload). Lost on a
// hard reload — that's acceptable: the text draft (sessionStorage) still
// restores, matching today's behavior. Never serialized.
let _imgs = null;
export function stashDraftImages(images) { _imgs = Array.isArray(images) && images.length ? images : null; }
export function takeDraftImages() { const v = _imgs; _imgs = null; return v; }   // one-shot
export function clearDraftImages() { _imgs = null; }
