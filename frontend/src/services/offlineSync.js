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
import { qcService } from './api';
import {
  getAllQcUpdates, removeQcUpdate, markQcUpdateFailed, outboxCount,
  getAllPhotos, removePhoto, markPhotoFailed,
} from './offlineOutbox';

const _CONCURRENCY = 3;

let _flushing = false;
let _started = false;

function _isOnline() {
  return !(typeof navigator !== 'undefined' && navigator.onLine === false);
}

// Attempt to flush every pending op once. Returns { synced, failed }.
export async function flushOutbox() {
  if (!FEATURES.OFFLINE_MODE || !_isOnline()) return { synced: 0, failed: 0 };
  if (_flushing) return { synced: 0, failed: 0 };  // re-entrancy guard
  _flushing = true;

  let synced = 0;
  let failed = 0;
  const syncedRunIds = new Set();

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
          if (!error || !error.response) {
            // Network failure — KEEP, retried on the next flush.
          } else {
            // Server REJECTED (4xx/5xx) — flag + KEEP, never silently drop.
            await markQcUpdateFailed(op.runId, op.itemId);
            failed += 1;
          }
        }
      }));
    }

    // BATCH 3b — drain queued photo blobs with the IDENTICAL data-loss policy.
    // Runs even when there are no pending marks (photos can outlive the marks).
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
          if (!error || !error.response) {
            // Network failure — KEEP, retried on the next flush.
          } else {
            // Server REJECTED (4xx/5xx) — flag + KEEP, never silently drop.
            await markPhotoFailed(op.key);
            failed += 1;
          }
        }
      }));
    }
  } catch (_) {
    /* sync must never throw */
  } finally {
    _flushing = false;
  }

  if (syncedRunIds.size > 0 && typeof window !== 'undefined') {
    try {
      window.dispatchEvent(new CustomEvent('brikops:outbox-synced', {
        detail: { runIds: Array.from(syncedRunIds), failed },
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

  const onOnline = () => { flushOutbox().catch(() => {}); };
  window.addEventListener('online', onOnline);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && _isOnline()) {
      flushOutbox().catch(() => {});
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
      if (isActive) flushOutbox().catch(() => {});
    });
  }).catch(() => {});

  // Startup flush in case we launched already-online with a backlog.
  flushOutbox().catch(() => {});
}
