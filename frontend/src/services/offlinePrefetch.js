// Offline BATCH 2 — "prepare floor for offline" prefetch.
//
// Warm-the-cache loop. It calls the SAME qcService / unitService methods the
// field screens call, for a floor and every unit on it, WHILE ONLINE. Each
// successful call is cached by BATCH 1's axios response interceptor, so when
// the user later opens any of those screens offline the cache keys match by
// construction (same method => same URL => same key) and the screens render
// unchanged.
//
// No new cache code, no raw URLs (call the services so keys match). Throttled
// (concurrency ~3), resilient (one unit failing does NOT abort the rest),
// reports progress. Never throws.

import { qcService, unitService } from './api';
import { FEATURES } from '../config/features';

const _CONCURRENCY = 3;

// Run methods return { run: { id }, stages: [...] } — the runId is at .run.id,
// NOT a top-level .id. Fall back to .id defensively.
function _runId(runResp) {
  return runResp?.run?.id ?? runResp?.id ?? null;
}

// getUnitsStatus returns { stages: [ { units: [ { unit_id } ] } ] }. The floor's
// unit list is the DISTINCT set of unit_id aggregated across all stages' units.
function _unitIdsFromStatus(unitsStatus) {
  const ids = new Set();
  const stages = unitsStatus?.stages || [];
  stages.forEach((stage) => {
    (stage?.units || []).forEach((u) => {
      if (u && u.unit_id != null) ids.add(u.unit_id);
    });
  });
  return Array.from(ids);
}

// Warm every PRIMARY call a single apartment's screens make.
async function _warmUnit(unitId) {
  const unitRun = await qcService.getUnitRun(unitId);   // unit QC run
  const rid = _runId(unitRun);
  if (rid) await qcService.getRun(rid);                 // unit stage items (StageDetailPage)
  await unitService.get(unitId);                        // unit detail (ApartmentDashboardPage)
  await unitService.getTasks(unitId);                   // unit defects
}

// Prefetch one floor for offline. onProgress({done,total,failed}) optional.
// Returns { total, done, failed }. Never throws (per-call failures counted).
export async function prefetchFloorForOffline(floorId, { onProgress } = {}) {
  // floorFailed = we could not enumerate the floor's units (getUnitsStatus
  // threw), so there is nothing to warm — the caller must NOT report success.
  const result = { total: 0, done: 0, failed: 0, floorFailed: false };
  if (!floorId) return result;
  // Double-guard: prefetch is inert when offline mode is off, and pointless
  // (and would just generate errors) when there's no connection.
  if (!FEATURES.OFFLINE_MODE) return result;
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return result;

  // Floor-level PRIMARY warms — each step independently guarded so one failure
  // never skips the others. getUnitsStatus is the one that MUST succeed (it is
  // the source of the unit list); getFloorRun / floor getRun are best-effort
  // (the floor screen already cached them on its own mount).
  let unitsStatus = null;
  let floorRun = null;
  try { floorRun = await qcService.getFloorRun(floorId); } catch (_) { /* best-effort */ }
  try {
    unitsStatus = await qcService.getUnitsStatus(floorId);   // unit list (+ cached)
  } catch (_) {
    result.floorFailed = true;                               // cannot enumerate units
  }
  try {
    const frid = _runId(floorRun);
    if (frid) await qcService.getRun(frid);                  // floor stage items
  } catch (_) { /* best-effort */ }

  const unitIds = _unitIdsFromStatus(unitsStatus);
  result.total = unitIds.length;
  if (onProgress) { try { onProgress({ ...result }); } catch (_) { /* ignore */ } }

  // Throttled worker pool — never fire all units at once.
  let cursor = 0;
  async function worker() {
    while (cursor < unitIds.length) {
      const unitId = unitIds[cursor++];
      try {
        await _warmUnit(unitId);
        result.done += 1;
      } catch (_) {
        result.failed += 1;
      }
      if (onProgress) { try { onProgress({ ...result }); } catch (_) { /* ignore */ } }
    }
  }

  const poolSize = Math.min(_CONCURRENCY, unitIds.length);
  const workers = [];
  for (let i = 0; i < poolSize; i++) workers.push(worker());
  await Promise.all(workers);

  return result;
}
