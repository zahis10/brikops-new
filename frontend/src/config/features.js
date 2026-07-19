export const FEATURES = {
  DEFECT_DRAFT_PRESERVATION: true,
  TRADE_SORT_IN_TEAM_FORM: true,
  // Offline mode — BATCH 1 (read-cache + banner). Default OFF.
  // When false, api.js + OfflineBanner behave exactly as before.
  OFFLINE_MODE: true,
  // Offline DEFECT CREATE — BATCH 5. Ships DORMANT (default false) so the whole
  // batch (backend client-id support + frontend offline-create code) can deploy
  // in ONE ./deploy.sh while the feature stays INERT. After the backend is
  // confirmed live on prod, flip this to true + redeploy to activate. Gates ONLY
  // the enqueue (NewDefectModal) + the pending hydrate/badge (ApartmentDashboard).
  // The outbox store + sync drain ship live but are no-ops while nothing is queued.
  OFFLINE_DEFECT_CREATE: true,
  // Photo-first defect entry (opt-in). On = per-user toggle in the
  // new-defect modal; default stays classic.
  DEFECT_PHOTO_FIRST: true,
};
