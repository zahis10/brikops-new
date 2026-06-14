// Offline WRITE sync engine — BATCH 3a. Render-less; drains the outbox when
// connectivity returns. Reuses qcService.updateItem (no raw axios).
//
// ⭐⭐ DATA-LOSS-CRITICAL success/error policy (a wrong rule here silently loses
// field work):
//   · 2xx SUCCESS (the await RESOLVED)  → removeQcUpdate. THE ONLY place
//     removeQcUpdate is ever called. Never on "any response".
//   · NETWORK error (!error.response)   → KEEP (transient; retried next flush).
//   · 4xx/5xx (error.response present)  → markQcUpdateFailed + KEEP. Never drop
//     a write on a server rejection (keeps it visible, avoids infinite retry of
//     bad data being silently lost).

import { FEATURES } from '../config/features';
import { qcService, taskService, handoverService } from './api';
import {
  getAllQcUpdates, removeQcUpdate, markQcUpdateFailed, outboxCount,
  getAllPhotos, removePhoto, markPhotoFailed,
  getAllDefectCreates, removeDefectCreate, markDefectCreateFailed,
  getAllHandoverItems, removeHandoverItem, markHandoverItemFailed, replaceHandoverItemPhotos,
  getAllHandoverForms, removeHandoverForm, markHandoverFormFailed,
  getAllMeterPhotos, removeMeterPhoto, markMeterPhotoFailed,
} from './offlineOutbox';

const _CONCURRENCY = 3;

let _flushing = false;
let _started = false;

// FIX 2 — 429/503 backoff. When the sync's OWN requests hit a server-busy status
// we stop adding load for a cooldown (the 30s interval + reconnect triggers would
// otherwise keep hammering a rate-limited user). Honored at the top of flushOutbox.
let _backoffUntil = 0;
const _BACKOFF_MS = 60000;
// FIX 3 — coalesce bursty reconnect triggers into ONE flush.
let _flushTimer = null;

function _isOnline() {
  return !(typeof navigator !== 'undefined' && navigator.onLine === false);
}

// A sync request hit a server-busy status (rate-limit / overloaded). EXACTLY
// {429,503} — a transient must NOT be treated as a real rejection (no markFailed)
// and must back the WHOLE flush off, not just the current drain.
function _isTransientStatus(error) {
  const s = error?.response?.status;
  return s === 429 || s === 503;
}

// online + visibilitychange + appStateChange + startup can all fire within a
// second of a reconnect → several flushes. Debounce them into one (~1500ms).
function scheduleFlush() {
  if (_flushTimer) return;
  _flushTimer = setTimeout(() => {
    _flushTimer = null;
    flushOutbox().catch(() => {});
  }, 1500);
}

// Attempt to flush every pending op once. Returns { synced, failed }.
export async function flushOutbox() {
  if (!FEATURES.OFFLINE_MODE || !_isOnline()) return { synced: 0, failed: 0 };
  if (_flushing) return { synced: 0, failed: 0 };  // re-entrancy guard
  if (Date.now() < _backoffUntil) return { synced: 0, failed: 0 };  // 429/503 cooldown
  _flushing = true;

  let synced = 0;
  let failed = 0;
  let hitBackoff = false;  // a 429/503 in ANY drain aborts the WHOLE flush
  const syncedRunIds = new Set();
  const syncedUnitIds = new Set();
  const syncedProtocolIds = new Set();

  try {
    const ops = await getAllQcUpdates();

    // Throttle: process in chunks of _CONCURRENCY so we never fire the whole
    // backlog at once (a basement worker may have dozens of queued marks).
    for (let i = 0; i < ops.length; i += _CONCURRENCY) {
      const chunk = ops.slice(i, i + _CONCURRENCY);
      await Promise.all(chunk.map(async (op) => {
        if (!op || !op.runId || !op.itemId) return;
        try {
          await qcService.updateItem(op.runId, op.itemId, op.payload || {});
          // RESOLVED ⇒ 2xx ⇒ the server has it ⇒ safe to remove.
          await removeQcUpdate(op.runId, op.itemId);
          synced += 1;
          syncedRunIds.add(op.runId);
        } catch (error) {
          if (_isTransientStatus(error)) {
            // Server BUSY (429/503) — back the WHOLE flush off 60s; KEEP (transient).
            _backoffUntil = Date.now() + _BACKOFF_MS;
            hitBackoff = true;
          } else if (!error || !error.response) {
            // Network failure — KEEP, retried on the next flush.
          } else {
            // Server REJECTED (real 4xx/5xx) — flag + KEEP, never silently drop.
            await markQcUpdateFailed(op.runId, op.itemId);
            failed += 1;
          }
        }
      }));
      if (hitBackoff) break;
    }

    // BATCH 3b — drain queued photo blobs with the IDENTICAL data-loss policy.
    // Runs even when there are no pending marks (photos can outlive the marks).
    // SKIPPED entirely if a transient (429/503) already tripped backoff — piling
    // photos onto the same rate-limited user would just eat more 429s.
    if (!hitBackoff) {
      const photoOps = await getAllPhotos();
      for (let i = 0; i < photoOps.length; i += _CONCURRENCY) {
        const chunk = photoOps.slice(i, i + _CONCURRENCY);
        await Promise.all(chunk.map(async (op) => {
          if (!op || !op.key || !op.runId || !op.itemId || !op.blob) return;
          try {
            await qcService.uploadPhoto(op.runId, op.itemId, op.blob);
            // RESOLVED ⇒ 2xx ⇒ the server has it ⇒ THE ONLY removePhoto call site.
            await removePhoto(op.key);
            synced += 1;
            syncedRunIds.add(op.runId);
          } catch (error) {
            if (_isTransientStatus(error)) {
              _backoffUntil = Date.now() + _BACKOFF_MS;
              hitBackoff = true;
            } else if (!error || !error.response) {
              // Network failure — KEEP, retried on the next flush.
            } else {
              // Server REJECTED (real 4xx/5xx) — flag + KEEP, never silently drop.
              await markPhotoFailed(op.key);
              failed += 1;
            }
          }
        }));
        if (hitBackoff) break;
      }
    }

    // BATCH 5 — drain queued defect-creates. SHIPS LIVE but no-ops while the
    // store is empty (the enqueue is flag-gated; nothing is queued until
    // OFFLINE_DEFECT_CREATE is on). getAllDefectCreates is fail-soft → [] for a
    // missing/just-upgraded store, so this NEVER breaks the marks+photos drains.
    // SEQUENTIAL per defect (create → photos → assign) so a create network-fail
    // throws BEFORE the photo loop (no POST to a non-existent id), and the record
    // is removed ONLY after all three succeed (idempotent backend makes a
    // partial-success retry safe — create returns the existing task, no dup).
    // Also skipped if a transient already tripped backoff above (same user).
    if (!hitBackoff) {
      const defectOps = await getAllDefectCreates();
      for (let i = 0; i < defectOps.length; i += _CONCURRENCY) {
        const chunk = defectOps.slice(i, i + _CONCURRENCY);
        await Promise.all(chunk.map(async (op) => {
          if (!op || !op.key || !op.payload) return;
          try {
            await taskService.create(op.payload);
            const photos = Array.isArray(op.photos) ? op.photos : [];
            for (const ph of photos) {
              if (ph && ph.blob) await taskService.uploadAttachment(op.key, ph.blob);
            }
            if (op.assign && op.assign.company_id) {
              await taskService.assign(op.key, op.assign);
            }
            // RESOLVED ⇒ full 2xx ⇒ THE ONLY removeDefectCreate call site.
            await removeDefectCreate(op.key);
            synced += 1;
            if (op.unitId) syncedUnitIds.add(op.unitId);
          } catch (error) {
            if (_isTransientStatus(error)) {
              _backoffUntil = Date.now() + _BACKOFF_MS;
              hitBackoff = true;
            } else if (!error || !error.response) {
              // Network failure — KEEP, retried on the next flush.
            } else {
              // Server REJECTED (real 4xx/5xx) — flag + KEEP, never silently drop.
              await markDefectCreateFailed(op.key);
              failed += 1;
            }
          }
        }));
        if (hitBackoff) break;
      }
    }

    // BATCH 4b — drain queued handover ITEM marks. IDENTICAL data-loss policy as
    // the qc drain (remove on 2xx only; network keep; transient backoff; real
    // 4xx/5xx markFailed+keep — a protocol locked since the mark surfaces here,
    // never silently dropped). Skipped if a transient already tripped backoff.
    if (!hitBackoff) {
      const itemOps = await getAllHandoverItems();
      for (let i = 0; i < itemOps.length; i += _CONCURRENCY) {
        const chunk = itemOps.slice(i, i + _CONCURRENCY);
        await Promise.all(chunk.map(async (op) => {
          if (!op || !op.protocolId || !op.sectionId || !op.itemId) return;
          try {
            const result = await handoverService.updateItem(op.projectId, op.protocolId, op.sectionId, op.itemId, op.payload || {});
            // BATCH 4c — handover-defect photos ride the record (photos:[{ blob }]).
            // SEQUENTIAL after the mark (BATCH 5 pattern): upload each to the defect
            // the mark just created/reused. INCREMENTAL de-queue — re-put the record
            // without each uploaded blob so a mid-loop failure resumes from the
            // REMAINING photos only (updateItem replay reuses the same defect ⇒ no
            // dup defect, no dup upload).
            const itemPhotos = Array.isArray(op.photos) ? op.photos.filter((p) => p && p.blob) : [];
            if (itemPhotos.length > 0) {
              if (!result || !result.defect_id) {
                // Anomaly: a defective payload returned no defect_id — surface + KEEP.
                await markHandoverItemFailed(op.protocolId, op.sectionId, op.itemId);
                failed += 1;
                return;
              }
              let remaining = itemPhotos.slice();
              for (const ph of itemPhotos) {
                await taskService.uploadAttachment(result.defect_id, ph.blob);
                remaining = remaining.slice(1);
                await replaceHandoverItemPhotos(op.protocolId, op.sectionId, op.itemId, remaining);
              }
            }
            // RESOLVED ⇒ 2xx (mark + all photos) ⇒ THE ONLY removeHandoverItem call site.
            await removeHandoverItem(op.protocolId, op.sectionId, op.itemId);
            synced += 1;
            syncedProtocolIds.add(op.protocolId);
          } catch (error) {
            if (_isTransientStatus(error)) {
              _backoffUntil = Date.now() + _BACKOFF_MS;
              hitBackoff = true;
            } else if (!error || !error.response) {
              // Network failure — KEEP, retried on the next flush.
            } else {
              // Server REJECTED (real 4xx/5xx) — flag + KEEP, never silently drop.
              await markHandoverItemFailed(op.protocolId, op.sectionId, op.itemId);
              failed += 1;
            }
          }
        }));
        if (hitBackoff) break;
      }
    }

    // BATCH 4b — drain queued handover FORM updates (property_details / meters
    // only — tenants are never enqueued). Same policy via updateProtocol.
    if (!hitBackoff) {
      const formOps = await getAllHandoverForms();
      for (let i = 0; i < formOps.length; i += _CONCURRENCY) {
        const chunk = formOps.slice(i, i + _CONCURRENCY);
        await Promise.all(chunk.map(async (op) => {
          if (!op || !op.protocolId || !op.field) return;
          try {
            let value = op.value;
            if (op.field === 'meters' && value && typeof value === 'object') {
              // FIX 1 — legacy 4c records may carry a session-dead blob: display_url;
              // never send display_url to the server (regenerated per-GET from photo_url).
              value = Object.fromEntries(Object.entries(value).map(([k, v]) =>
                (v && typeof v === 'object') ? [k, (({ display_url, ...rest }) => rest)(v)] : [k, v]
              ));
            }
            await handoverService.updateProtocol(op.projectId, op.protocolId, { [op.field]: value });
            // RESOLVED ⇒ 2xx ⇒ THE ONLY removeHandoverForm call site.
            await removeHandoverForm(op.protocolId, op.field);
            synced += 1;
            syncedProtocolIds.add(op.protocolId);
          } catch (error) {
            if (_isTransientStatus(error)) {
              _backoffUntil = Date.now() + _BACKOFF_MS;
              hitBackoff = true;
            } else if (!error || !error.response) {
              // Network failure — KEEP, retried on the next flush.
            } else {
              // Server REJECTED (real 4xx/5xx) — flag + KEEP, never silently drop.
              await markHandoverFormFailed(op.protocolId, op.field);
              failed += 1;
            }
          }
        }));
        if (hitBackoff) break;
      }
    }

    // BATCH 4c — drain queued METER PHOTOS. ⚠ MUST run AFTER the forms drain:
    // upload_meter_photo $sets ONLY meters.{type}.photo_url (a subfield) while the
    // 4b form op $sets the WHOLE meters object from a possibly-stale offline snapshot
    // — so photos-LAST guarantees the fresh photo_url survives (forms-after-photos
    // would clobber it). Same data-loss policy; the deterministic S3 key makes a
    // replay overwrite the same object (idempotent).
    if (!hitBackoff) {
      const meterPhotoOps = await getAllMeterPhotos();
      for (let i = 0; i < meterPhotoOps.length; i += _CONCURRENCY) {
        const chunk = meterPhotoOps.slice(i, i + _CONCURRENCY);
        await Promise.all(chunk.map(async (op) => {
          if (!op || !op.protocolId || !op.type || !op.blob) return;
          try {
            await handoverService.uploadMeterPhoto(op.projectId, op.protocolId, op.type, op.blob);
            // RESOLVED ⇒ 2xx ⇒ THE ONLY removeMeterPhoto call site.
            await removeMeterPhoto(op.protocolId, op.type);
            synced += 1;
            syncedProtocolIds.add(op.protocolId);
          } catch (error) {
            if (_isTransientStatus(error)) {
              _backoffUntil = Date.now() + _BACKOFF_MS;
              hitBackoff = true;
            } else if (!error || !error.response) {
              // Network failure — KEEP, retried on the next flush.
            } else {
              // Server REJECTED (real 4xx/5xx) — flag + KEEP, never silently drop.
              await markMeterPhotoFailed(op.protocolId, op.type);
              failed += 1;
            }
          }
        }));
        if (hitBackoff) break;
      }
    }
  } catch (_) {
    /* sync must never throw */
  } finally {
    _flushing = false;
  }

  if ((syncedRunIds.size > 0 || syncedUnitIds.size > 0 || syncedProtocolIds.size > 0) && typeof window !== 'undefined') {
    try {
      window.dispatchEvent(new CustomEvent('brikops:outbox-synced', {
        detail: {
          runIds: Array.from(syncedRunIds),
          unitIds: Array.from(syncedUnitIds),
          protocolIds: Array.from(syncedProtocolIds),
          failed,
        },
      }));
    } catch (_) { /* event dispatch must never throw */ }
  }

  return { synced, failed };
}

// Wire listeners (online event + foreground) and do one startup flush.
// Idempotent — guarded against double-binding.
export function startOutboxSync() {
  if (_started || typeof window === 'undefined') return;
  _started = true;

  const onOnline = () => { scheduleFlush(); };
  window.addEventListener('online', onOnline);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && _isOnline()) {
      scheduleFlush();
    }
  });

  // (B.1) Safety-net retry. A sparse trigger can fire a beat before the radio is
  // truly ready (the attempt network-fails → correctly KEPT → but nothing retries
  // it). A cheap IndexedDB count every 30s flushes ONLY when there is a backlog
  // and we are online, so a stranded op never waits longer than ~30s.
  setInterval(async () => {
    if (!FEATURES.OFFLINE_MODE) return;
    if (!_isOnline()) return;
    try { if ((await outboxCount()) > 0) flushOutbox().catch(() => {}); }
    catch (_) { /* never throw */ }
  }, 30000);

  // (B.4) Capacitor app-resume — belt-and-suspenders for iOS where the WebView's
  // visibilitychange can be unreliable. Dynamic import of an ALREADY-installed
  // plugin (@capacitor/app, used in App.js) — JS-only, still OTA, no new dep.
  import('@capacitor/app').then(({ App }) => {
    App.addListener('appStateChange', ({ isActive }) => {
      if (isActive) scheduleFlush();
    });
  }).catch(() => {});

  // Startup flush in case we launched already-online with a backlog.
  scheduleFlush();
}
