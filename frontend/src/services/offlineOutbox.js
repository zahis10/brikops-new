// Offline WRITE outbox — BATCH 3a. Tiny dependency-free IndexedDB queue for
// pending QC item updates (status + note) made while offline.
//
// SEPARATE DB from the read-cache (offlineCache.js uses "brikops-offline") so
// the read-cache eviction can NEVER drop a pending write. Single store
// "qc_item_updates" keyed by `${runId}::${itemId}` so re-marking the same item
// OVERWRITES its pending op (one op per item — local last-write-wins).
//
// Fail-soft: a missing/blocked IndexedDB (private mode, old WebView) NEVER
// throws — every function resolves to null / [] / 0 / no-op so callers behave
// as "no outbox". No PII logging (notes are free text — never logged).

const DB_NAME = 'brikops-outbox';
const STORE = 'qc_item_updates';
// BATCH 3b: photo blobs accumulate (one record per photo, auto client key) —
// SEPARATE store in the SAME DB so a v1→v2 upgrade keeps queued marks intact.
const PHOTO_STORE = 'qc_photo_uploads';
const DB_VERSION = 2;

let _dbPromise = null;

function _supported() {
  return typeof indexedDB !== 'undefined';
}

function _key(runId, itemId) {
  return `${runId}::${itemId}`;
}

function _openDb() {
  if (!_supported()) return Promise.resolve(null);
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve) => {
    let req;
    try {
      req = indexedDB.open(DB_NAME, DB_VERSION);
    } catch (_) {
      resolve(null);
      return;
    }
    req.onupgradeneeded = () => {
      const db = req.result;
      // Leave qc_item_updates UNTOUCHED — a v1 user upgrading with queued marks
      // must keep them (this guard is true on upgrade ⇒ no recreate, no clear).
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'key' });
      }
      // BATCH 3b: ONLY add the photo store (guarded), never recreate the above.
      if (!db.objectStoreNames.contains(PHOTO_STORE)) {
        db.createObjectStore(PHOTO_STORE, { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve(null);
    req.onblocked = () => resolve(null);
  }).catch(() => null);
  return _dbPromise;
}

function _store(db, mode) {
  return db.transaction(STORE, mode).objectStore(STORE);
}

function _photoStore(db, mode) {
  return db.transaction(PHOTO_STORE, mode).objectStore(PHOTO_STORE);
}

function _getAllPhotosRaw(db) {
  return new Promise((resolve) => {
    try {
      const req = _photoStore(db, 'readonly').getAll();
      req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : []);
      req.onerror = () => resolve([]);
    } catch (_) {
      resolve([]);
    }
  });
}

function _getAllRaw(db) {
  return new Promise((resolve) => {
    try {
      const req = _store(db, 'readonly').getAll();
      req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : []);
      req.onerror = () => resolve([]);
    } catch (_) {
      resolve([]);
    }
  });
}

// payload = { status?, note? }. Overwrites any existing op for (runId,itemId)
// so the newest mark on an item replaces the older one (last-write-wins).
export async function enqueueQcUpdate(runId, itemId, payload) {
  if (!runId || !itemId) return;
  try {
    const db = await _openDb();
    if (!db) return;
    const record = {
      key: _key(runId, itemId),
      runId,
      itemId,
      payload: payload || {},
      ts: Date.now(),
      failed: false,
    };
    await new Promise((resolve) => {
      try {
        const req = _store(db, 'readwrite').put(record);
        req.onsuccess = () => resolve();
        req.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  } catch (_) {
    /* outbox must never throw */
  }
}

// → { [itemId]: { status?, note? } } for one run (to hydrate localChanges).
export async function getQcUpdatesForRun(runId) {
  if (!runId) return {};
  try {
    const db = await _openDb();
    if (!db) return {};
    const all = await _getAllRaw(db);
    const out = {};
    for (const rec of all) {
      if (rec && rec.runId === runId && rec.itemId) {
        out[rec.itemId] = rec.payload || {};
      }
    }
    return out;
  } catch (_) {
    return {};
  }
}

// Every pending op, for the sync engine + the global count.
// → [{ key, runId, itemId, payload, ts, failed }]
export async function getAllQcUpdates() {
  try {
    const db = await _openDb();
    if (!db) return [];
    return await _getAllRaw(db);
  } catch (_) {
    return [];
  }
}

export async function removeQcUpdate(runId, itemId) {
  if (!runId || !itemId) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const req = _store(db, 'readwrite').delete(_key(runId, itemId));
        req.onsuccess = () => resolve();
        req.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  } catch (_) {
    /* outbox must never throw */
  }
}

export async function markQcUpdateFailed(runId, itemId) {
  if (!runId || !itemId) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const store = _store(db, 'readwrite');
        const getReq = store.get(_key(runId, itemId));
        getReq.onsuccess = () => {
          const rec = getReq.result;
          if (!rec) { resolve(); return; }
          rec.failed = true;
          const putReq = store.put(rec);
          putReq.onsuccess = () => resolve();
          putReq.onerror = () => resolve();
        };
        getReq.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  } catch (_) {
    /* outbox must never throw */
  }
}

export async function outboxCount() {
  try {
    const db = await _openDb();
    if (!db) return 0;
    return await new Promise((resolve) => {
      try {
        const req = _store(db, 'readonly').count();
        req.onsuccess = () => resolve(typeof req.result === 'number' ? req.result : 0);
        req.onerror = () => resolve(0);
      } catch (_) {
        resolve(0);
      }
    });
  } catch (_) {
    return 0;
  }
}

// ===========================================================================
// BATCH 3b — photo blob outbox (store PHOTO_STORE). Photos ACCUMULATE: every
// enqueuePhoto is a NEW auto key (never overwrite) so two photos on one item
// are two records. Stores the SAME compressed File the upload path uses.
// ===========================================================================

function _photoKey() {
  return `p_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

// Enqueue one compressed photo blob. Returns the generated key (or null).
export async function enqueuePhoto(runId, itemId, file) {
  if (!runId || !itemId || !file) return null;
  try {
    const db = await _openDb();
    if (!db) return null;
    const key = _photoKey();
    const record = {
      key,
      runId,
      itemId,
      blob: file,
      name: file.name || '',
      ts: Date.now(),
      failed: false,
    };
    await new Promise((resolve) => {
      try {
        const req = _photoStore(db, 'readwrite').put(record);
        req.onsuccess = () => resolve();
        req.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
    return key;
  } catch (_) {
    return null;
  }
}

// Pending photos for one run (to hydrate item.photos on load).
// → [{ key, itemId, blob, name, ts, failed }]
export async function getPhotosForRun(runId) {
  if (!runId) return [];
  try {
    const db = await _openDb();
    if (!db) return [];
    const all = await _getAllPhotosRaw(db);
    return all.filter((rec) => rec && rec.runId === runId && rec.itemId);
  } catch (_) {
    return [];
  }
}

// Every pending photo, for the sync engine.
// → [{ key, runId, itemId, blob, name, ts, failed }]
export async function getAllPhotos() {
  try {
    const db = await _openDb();
    if (!db) return [];
    return await _getAllPhotosRaw(db);
  } catch (_) {
    return [];
  }
}

export async function removePhoto(key) {
  if (!key) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const req = _photoStore(db, 'readwrite').delete(key);
        req.onsuccess = () => resolve();
        req.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  } catch (_) {
    /* outbox must never throw */
  }
}

export async function markPhotoFailed(key) {
  if (!key) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const store = _photoStore(db, 'readwrite');
        const getReq = store.get(key);
        getReq.onsuccess = () => {
          const rec = getReq.result;
          if (!rec) { resolve(); return; }
          rec.failed = true;
          const putReq = store.put(rec);
          putReq.onsuccess = () => resolve();
          putReq.onerror = () => resolve();
        };
        getReq.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  } catch (_) {
    /* outbox must never throw */
  }
}

export async function photoOutboxCount() {
  try {
    const db = await _openDb();
    if (!db) return 0;
    return await new Promise((resolve) => {
      try {
        const req = _photoStore(db, 'readonly').count();
        req.onsuccess = () => resolve(typeof req.result === 'number' ? req.result : 0);
        req.onerror = () => resolve(0);
      } catch (_) {
        resolve(0);
      }
    });
  } catch (_) {
    return 0;
  }
}
