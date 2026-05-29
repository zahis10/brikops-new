// Offline read-cache — BATCH 1. Tiny dependency-free IndexedDB wrapper.
// Single DB "brikops-offline", single store "reads" keyed by request URL.
// Fail-soft: a missing/blocked IndexedDB (private mode, old WebView) NEVER
// throws — every function resolves to null / no-op so callers behave as
// "no cache". TEXT JSON only; no PII logging, no response-body logging.

const DB_NAME = 'brikops-offline';
const STORE = 'reads';
const DB_VERSION = 1;

const _MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
const _MAX_ENTRIES = 400;
const _EVICT_EVERY = 25;

let _dbPromise = null;
let _writesSinceEvict = 0;

function _supported() {
  return typeof indexedDB !== 'undefined';
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
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'url' });
        store.createIndex('ts', 'ts', { unique: false });
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

export async function cachePutRead(url, data) {
  if (!url) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const req = _store(db, 'readwrite').put({ url, data, ts: Date.now() });
        req.onsuccess = () => resolve();
        req.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
    _writesSinceEvict += 1;
    if (_writesSinceEvict >= _EVICT_EVERY) {
      _writesSinceEvict = 0;
      cacheEvict().catch(() => {});
    }
  } catch (_) {
    /* cache must never throw */
  }
}

export async function cacheGetRead(url) {
  if (!url) return null;
  try {
    const db = await _openDb();
    if (!db) return null;
    return await new Promise((resolve) => {
      try {
        const req = _store(db, 'readonly').get(url);
        req.onsuccess = () => resolve(req.result ? req.result.data : null);
        req.onerror = () => resolve(null);
      } catch (_) {
        resolve(null);
      }
    });
  } catch (_) {
    return null;
  }
}

export async function cacheEvict({ maxAgeMs = _MAX_AGE_MS, maxEntries = _MAX_ENTRIES } = {}) {
  try {
    const db = await _openDb();
    if (!db) return;
    const all = await new Promise((resolve) => {
      try {
        const req = _store(db, 'readonly').getAll();
        req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : []);
        req.onerror = () => resolve([]);
      } catch (_) {
        resolve([]);
      }
    });
    if (!all.length) return;

    const cutoff = Date.now() - maxAgeMs;
    const toDelete = new Set();
    for (const rec of all) {
      if (typeof rec.ts === 'number' && rec.ts < cutoff) toDelete.add(rec.url);
    }
    const remaining = all.filter((r) => !toDelete.has(r.url));
    if (remaining.length > maxEntries) {
      remaining.sort((a, b) => (a.ts || 0) - (b.ts || 0));
      const excess = remaining.length - maxEntries;
      for (let i = 0; i < excess; i++) toDelete.add(remaining[i].url);
    }
    if (!toDelete.size) return;

    await new Promise((resolve) => {
      try {
        const store = _store(db, 'readwrite');
        let pending = toDelete.size;
        toDelete.forEach((url) => {
          const req = store.delete(url);
          req.onsuccess = () => { if (--pending <= 0) resolve(); };
          req.onerror = () => { if (--pending <= 0) resolve(); };
        });
      } catch (_) {
        resolve();
      }
    });
  } catch (_) {
    /* cache must never throw */
  }
}

export async function cacheClearAll() {
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const req = _store(db, 'readwrite').clear();
        req.onsuccess = () => resolve();
        req.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  } catch (_) {
    /* cache must never throw */
  }
}
