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
// BATCH 5: offline defect-create records (create payload + photos + assign), one
// per client-minted task id — SEPARATE store again so the v2→v3 upgrade keeps the
// 3a marks + 3b photos intact. Ships at DEPLOY #1 even with the feature dormant.
const DEFECT_STORE = 'defect_creates';
// BATCH 4b: offline handover capture. TWO new stores in the SAME DB so the v3→v4
// upgrade keeps the 3a marks + 3b photos + 5 defect-creates intact.
//   handover_item_updates — per-item marks, keyed `${protocolId}::${sectionId}::${itemId}` (last-write-wins)
//   handover_form_updates — property_details + meters ONLY, keyed `${protocolId}::${field}`
// ⛔ tenants are NEVER written here (ת"ז/phone/email) — enqueueHandoverForm hard-guards the field.
const HANDOVER_ITEM_STORE = 'handover_item_updates';
const HANDOVER_FORM_STORE = 'handover_form_updates';
const DB_VERSION = 4;

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
      // BATCH 5: guarded defect-create store. MUST be created on the v2→v3 upgrade
      // so it exists app-wide even with the feature dormant — the live drain reads
      // it on every flush and a missing store would throw and break 3a/3b sync.
      if (!db.objectStoreNames.contains(DEFECT_STORE)) {
        db.createObjectStore(DEFECT_STORE, { keyPath: 'key' });
      }
      // BATCH 4b: guarded handover stores. Created on the v3→v4 upgrade so they
      // exist app-wide; the live drains read them on every flush and a missing
      // store would throw and break the 3a/3b/5 sync already shipped in prod.
      if (!db.objectStoreNames.contains(HANDOVER_ITEM_STORE)) {
        db.createObjectStore(HANDOVER_ITEM_STORE, { keyPath: 'key' });
      }
      if (!db.objectStoreNames.contains(HANDOVER_FORM_STORE)) {
        db.createObjectStore(HANDOVER_FORM_STORE, { keyPath: 'key' });
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

// ===========================================================================
// BATCH 5 — offline defect-create outbox.
// One record per client-minted task id:
//   { key, payload (taskData incl. id, company_id only — NEVER assignee_id),
//     photos: [{ name, blob }], assign: { company_id?, assignee_id? },
//     unitId, ts, failed }
// ⭐ EVERY getter is FAIL-SOFT → [] (a missing/just-upgraded store must NEVER
// throw — the live drain reads this on every flush, and a throw would break the
// 3a/3b marks+photos sync already shipped in prod).
// ===========================================================================

function _defectStore(db, mode) {
  return db.transaction(DEFECT_STORE, mode).objectStore(DEFECT_STORE);
}

function _getAllDefectsRaw(db) {
  return new Promise((resolve) => {
    try {
      const req = _defectStore(db, 'readonly').getAll();
      req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : []);
      req.onerror = () => resolve([]);
    } catch (_) {
      resolve([]);
    }
  });
}

// Enqueue one defect-create (payload + photo blobs + assign). `record.key` is the
// client-minted task UUID. Returns the key (or null on a fail-soft no-op).
export async function enqueueDefectCreate(record) {
  if (!record || !record.key) return null;
  try {
    const db = await _openDb();
    if (!db) return null;
    const toStore = {
      key: record.key,
      payload: record.payload || {},
      photos: Array.isArray(record.photos) ? record.photos : [],
      assign: record.assign || null,
      unitId: record.unitId || (record.payload && record.payload.unit_id) || null,
      ts: Date.now(),
      failed: false,
    };
    await new Promise((resolve) => {
      try {
        const req = _defectStore(db, 'readwrite').put(toStore);
        req.onsuccess = () => resolve();
        req.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
    return record.key;
  } catch (_) {
    return null;
  }
}

// Every pending defect-create, for the sync engine. FAIL-SOFT → [].
export async function getAllDefectCreates() {
  try {
    const db = await _openDb();
    if (!db) return [];
    return await _getAllDefectsRaw(db);
  } catch (_) {
    return [];
  }
}

// Pending defect-creates for one unit (to hydrate the unit defect list). → [].
export async function getDefectCreatesForUnit(unitId) {
  if (!unitId) return [];
  try {
    const db = await _openDb();
    if (!db) return [];
    const all = await _getAllDefectsRaw(db);
    return all.filter((rec) => rec && rec.unitId === unitId);
  } catch (_) {
    return [];
  }
}

export async function removeDefectCreate(key) {
  if (!key) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const req = _defectStore(db, 'readwrite').delete(key);
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

export async function markDefectCreateFailed(key) {
  if (!key) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const store = _defectStore(db, 'readwrite');
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

// ===========================================================================
// BATCH 4b — offline handover capture.
// (A) handover_item_updates — per-item marks, key `${protocolId}::${sectionId}::${itemId}`,
//     OVERWRITE per key (last-write-wins, like the qc store).
// (B) handover_form_updates — property_details + meters ONLY, key `${protocolId}::${field}`.
//     ⛔ tenants are NEVER written here (ת"ז/phone/email) — hard-guarded in enqueueHandoverForm.
// EVERY getter is FAIL-SOFT → []/null so the live drains never throw on a
// missing/just-upgraded store (would break the 3a/3b/5 sync already in prod).
// ===========================================================================

function _handoverItemStore(db, mode) {
  return db.transaction(HANDOVER_ITEM_STORE, mode).objectStore(HANDOVER_ITEM_STORE);
}

function _handoverFormStore(db, mode) {
  return db.transaction(HANDOVER_FORM_STORE, mode).objectStore(HANDOVER_FORM_STORE);
}

function _getAllHandoverItemsRaw(db) {
  return new Promise((resolve) => {
    try {
      const req = _handoverItemStore(db, 'readonly').getAll();
      req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : []);
      req.onerror = () => resolve([]);
    } catch (_) {
      resolve([]);
    }
  });
}

function _getAllHandoverFormsRaw(db) {
  return new Promise((resolve) => {
    try {
      const req = _handoverFormStore(db, 'readonly').getAll();
      req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : []);
      req.onerror = () => resolve([]);
    } catch (_) {
      resolve([]);
    }
  });
}

function _handoverItemKey(protocolId, sectionId, itemId) {
  return `${protocolId}::${sectionId}::${itemId}`;
}

function _handoverFormKey(protocolId, field) {
  return `${protocolId}::${field}`;
}

// payload = the EXACT body the online updateItem call sends
// (status / notes / description / severity / photos:[] / photos_pending_count / skip_photo_reason).
// Overwrites any existing op for (protocolId,sectionId,itemId) — local last-write-wins.
export async function enqueueHandoverItem(projectId, protocolId, sectionId, itemId, payload) {
  if (!protocolId || !sectionId || !itemId) return;
  try {
    const db = await _openDb();
    if (!db) return;
    const record = {
      key: _handoverItemKey(protocolId, sectionId, itemId),
      projectId,
      protocolId,
      sectionId,
      itemId,
      payload: payload || {},
      queuedAt: Date.now(),
      failed: false,
    };
    await new Promise((resolve) => {
      try {
        const req = _handoverItemStore(db, 'readwrite').put(record);
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

// Pending item marks for one protocol (to hydrate the section on load). → [].
export async function getHandoverItemsForProtocol(protocolId) {
  if (!protocolId) return [];
  try {
    const db = await _openDb();
    if (!db) return [];
    const all = await _getAllHandoverItemsRaw(db);
    return all.filter((rec) => rec && rec.protocolId === protocolId && rec.itemId);
  } catch (_) {
    return [];
  }
}

// Every pending handover item mark, for the sync engine.
export async function getAllHandoverItems() {
  try {
    const db = await _openDb();
    if (!db) return [];
    return await _getAllHandoverItemsRaw(db);
  } catch (_) {
    return [];
  }
}

export async function removeHandoverItem(protocolId, sectionId, itemId) {
  if (!protocolId || !sectionId || !itemId) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const req = _handoverItemStore(db, 'readwrite').delete(_handoverItemKey(protocolId, sectionId, itemId));
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

export async function markHandoverItemFailed(protocolId, sectionId, itemId) {
  if (!protocolId || !sectionId || !itemId) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const store = _handoverItemStore(db, 'readwrite');
        const getReq = store.get(_handoverItemKey(protocolId, sectionId, itemId));
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

// ⛔ PII HARD GUARD: only property_details + meters may ever be written to the
// device. tenants carry ת"ז/phone/email and must NEVER land in IndexedDB (4a rule).
export async function enqueueHandoverForm(projectId, protocolId, field, value) {
  if (field !== 'property_details' && field !== 'meters') return;  // tenants NEVER stored on device (ת"ז)
  if (!protocolId || !field) return;
  try {
    const db = await _openDb();
    if (!db) return;
    const record = {
      key: _handoverFormKey(protocolId, field),
      projectId,
      protocolId,
      field,
      value,
      queuedAt: Date.now(),
      failed: false,
    };
    await new Promise((resolve) => {
      try {
        const req = _handoverFormStore(db, 'readwrite').put(record);
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

// Pending form value for one (protocol, field) — to hydrate the form. → record | null.
export async function getHandoverFormUpdate(protocolId, field) {
  if (!protocolId || !field) return null;
  try {
    const db = await _openDb();
    if (!db) return null;
    return await new Promise((resolve) => {
      try {
        const req = _handoverFormStore(db, 'readonly').get(_handoverFormKey(protocolId, field));
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      } catch (_) {
        resolve(null);
      }
    });
  } catch (_) {
    return null;
  }
}

// Every pending handover form update, for the sync engine.
export async function getAllHandoverForms() {
  try {
    const db = await _openDb();
    if (!db) return [];
    return await _getAllHandoverFormsRaw(db);
  } catch (_) {
    return [];
  }
}

export async function removeHandoverForm(protocolId, field) {
  if (!protocolId || !field) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const req = _handoverFormStore(db, 'readwrite').delete(_handoverFormKey(protocolId, field));
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

export async function markHandoverFormFailed(protocolId, field) {
  if (!protocolId || !field) return;
  try {
    const db = await _openDb();
    if (!db) return;
    await new Promise((resolve) => {
      try {
        const store = _handoverFormStore(db, 'readwrite');
        const getReq = store.get(_handoverFormKey(protocolId, field));
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
