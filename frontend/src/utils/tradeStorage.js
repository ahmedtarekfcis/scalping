/**
 * Persistent Storage for Trading Stats
 * Uses IndexedDB as primary persistent storage (unlimited quota, immune to localStorage limits),
 * with localStorage as an immediate synchronous cache and fallback.
 */

const DB_NAME = 'TradeEdgeStatsDB';
const DB_VERSION = 3;
const STORE_NAME = 'trades';
const META_STORE_NAME = 'tradeMetadata';
const JOURNAL_STORE_NAME = 'journalTrades';
const JOURNAL_META_STORE_NAME = 'journalMetadata';
export const STORAGE_KEY = 'tradeStatsData';
export const LEGACY_STORAGE_KEY = 'tradeStatsTransactions';
export const METADATA_STORAGE_KEY = 'tradeStatsMetadata';
export const JOURNAL_STORAGE_KEY = 'journalingTradesData';
export const JOURNAL_METADATA_STORAGE_KEY = 'journalingMetadata';

/**
 * Open IndexedDB database instance
 */
function openIndexedDb() {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      return reject(new Error('IndexedDB is not supported in this environment'));
    }

    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: '__storeId', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(META_STORE_NAME)) {
        db.createObjectStore(META_STORE_NAME, { keyPath: 'tradeId' });
      }
      if (!db.objectStoreNames.contains(JOURNAL_STORE_NAME)) {
        db.createObjectStore(JOURNAL_STORE_NAME, { keyPath: '__storeId', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(JOURNAL_META_STORE_NAME)) {
        db.createObjectStore(JOURNAL_META_STORE_NAME, { keyPath: 'tradeId' });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('Failed to open IndexedDB'));
  });
}

/**
 * Read all transactions from IndexedDB
 */
export async function getTradesFromIndexedDb() {
  try {
    const db = await openIndexedDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error || new Error('Failed to retrieve records from IndexedDB'));
    });
  } catch (err) {
    console.warn('IndexedDB read error:', err);
    return [];
  }
}

/**
 * Replace all transactions in IndexedDB with a clean list
 */
export async function setTradesInIndexedDb(records) {
  const db = await openIndexedDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    store.clear();
    for (let i = 0; i < records.length; i++) {
      const item = { ...records[i] };
      delete item.__storeId;
      store.put(item);
    }
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error || new Error('Failed to save to IndexedDB'));
  });
}

/**
 * Read transactions synchronously from localStorage
 */
export function getTradesFromLocalStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    console.error('Failed to read trades from localStorage:', err);
    return [];
  }
}

/**
 * Save transactions synchronously to localStorage (best effort)
 */
export function setTradesInLocalStorage(records) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    return true;
  } catch (err) {
    console.warn('LocalStorage save warning (may have exceeded 5MB limit):', err);
    return false;
  }
}

/**
 * Load stored transactions asynchronously:
 * 1. Checks IndexedDB first.
 * 2. If IndexedDB has records, returns them.
 * 3. If IndexedDB is empty, checks localStorage. If localStorage has records,
 *    migrates them to IndexedDB in the background.
 */
export async function loadPersistedTrades() {
  const idbRecords = await getTradesFromIndexedDb();
  if (Array.isArray(idbRecords) && idbRecords.length > 0) {
    // Keep localStorage in sync if small enough
    setTradesInLocalStorage(idbRecords);
    return idbRecords;
  }

  // Fallback to localStorage and migrate
  const localRecords = getTradesFromLocalStorage();
  if (localRecords.length > 0) {
    setTradesInIndexedDb(localRecords).catch((e) =>
      console.warn('Background migration to IndexedDB failed:', e)
    );
    return localRecords;
  }

  return [];
}

/**
 * Persist transactions to both IndexedDB and localStorage
 */
export async function persistTrades(records) {
  // Always save to IndexedDB for reliable permanent storage
  let idbSaved = false;
  try {
    await setTradesInIndexedDb(records);
    idbSaved = true;
  } catch (err) {
    console.warn('IndexedDB persistence error:', err);
  }

  // Also sync to localStorage as immediate fast cache
  setTradesInLocalStorage(records);

  return idbSaved;
}

/**
 * Clear all stored trades from both IndexedDB and localStorage
 */
export async function clearPersistedTrades() {
  try {
    const db = await openIndexedDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      store.clear();
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to clear IndexedDB:', err);
  }

  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch (err) {
    console.warn('Failed to clear localStorage:', err);
  }
}

/**
 * Load all custom trade metadata (watchedValue, setupType, notes, images)
 */
export async function loadAllTradeMetadata() {
  const metaMap = {};

  // 1. Try IndexedDB
  try {
    const db = await openIndexedDb();
    const records = await new Promise((resolve, reject) => {
      const tx = db.transaction(META_STORE_NAME, 'readonly');
      const store = tx.objectStore(META_STORE_NAME);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });

    if (Array.isArray(records)) {
      records.forEach((r) => {
        if (r && r.tradeId) {
          metaMap[r.tradeId] = r;
        }
      });
      return metaMap;
    }
  } catch (err) {
    console.warn('IndexedDB metadata read error, falling back to localStorage:', err);
  }

  // 2. Fallback to localStorage
  try {
    const raw = localStorage.getItem(METADATA_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return parsed;
      }
    }
  } catch (err) {
    console.error('Failed to load trade metadata from localStorage:', err);
  }

  return metaMap;
}

/**
 * Save custom trade metadata for a specific tradeId
 */
export async function saveTradeMetadata(tradeId, data) {
  if (!tradeId) return false;

  const record = {
    tradeId,
    watchedValue: data.watchedValue ?? '',
    setupType: data.setupType ?? '',
    comment: data.comment ?? data.notes ?? '',
    notes: data.notes ?? data.comment ?? '',
    images: Array.isArray(data.images) ? data.images : [],
    updatedAt: new Date().toISOString(),
  };

  // 1. Save to IndexedDB
  try {
    const db = await openIndexedDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(META_STORE_NAME, 'readwrite');
      const store = tx.objectStore(META_STORE_NAME);
      store.put(record);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('IndexedDB save metadata error:', err);
  }

  // 2. Sync to localStorage (without heavy images if storage limit threatens)
  try {
    const raw = localStorage.getItem(METADATA_STORAGE_KEY);
    const existing = raw ? JSON.parse(raw) : {};
    existing[tradeId] = {
      ...record,
      // Keep thumbnails / small image count in localStorage
      imagesCount: record.images.length,
    };
    localStorage.setItem(METADATA_STORAGE_KEY, JSON.stringify(existing));
  } catch (err) {
    console.warn('LocalStorage save metadata warning:', err);
  }

  return true;
}

/**
 * Clear all trade metadata
 */
export async function clearAllTradeMetadata() {
  try {
    const db = await openIndexedDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(META_STORE_NAME, 'readwrite');
      const store = tx.objectStore(META_STORE_NAME);
      store.clear();
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('IndexedDB metadata clear error:', err);
  }

  try {
    localStorage.removeItem(METADATA_STORAGE_KEY);
  } catch (err) {
    console.warn('LocalStorage metadata clear error:', err);
  }
}

/* ==========================================================================
   JOURNALING STORAGE (Dedicated storage for manual trade logging)
   ========================================================================== */

/**
 * Read all journal transactions from IndexedDB
 */
export async function getJournalTradesFromIndexedDb() {
  try {
    const db = await openIndexedDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(JOURNAL_STORE_NAME, 'readonly');
      const store = tx.objectStore(JOURNAL_STORE_NAME);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error || new Error('Failed to retrieve journal records from IndexedDB'));
    });
  } catch (err) {
    console.warn('IndexedDB journal read error:', err);
    return [];
  }
}

/**
 * Replace all journal transactions in IndexedDB with a clean list
 */
export async function setJournalTradesInIndexedDb(records) {
  const db = await openIndexedDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(JOURNAL_STORE_NAME, 'readwrite');
    const store = tx.objectStore(JOURNAL_STORE_NAME);
    store.clear();
    for (let i = 0; i < records.length; i++) {
      const item = { ...records[i] };
      delete item.__storeId;
      store.put(item);
    }
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error || new Error('Failed to save journal to IndexedDB'));
  });
}

/**
 * Read journal transactions synchronously from localStorage
 */
export function getJournalTradesFromLocalStorage() {
  try {
    const raw = localStorage.getItem(JOURNAL_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    console.error('Failed to read journal trades from localStorage:', err);
    return [];
  }
}

/**
 * Save journal transactions synchronously to localStorage
 */
export function setJournalTradesInLocalStorage(records) {
  try {
    localStorage.setItem(JOURNAL_STORAGE_KEY, JSON.stringify(records));
    return true;
  } catch (err) {
    console.warn('LocalStorage save journal warning:', err);
    return false;
  }
}

/**
 * Load persisted journal trades (IndexedDB first, fallback to localStorage)
 */
export async function loadPersistedJournalTrades() {
  const idbRecords = await getJournalTradesFromIndexedDb();
  if (Array.isArray(idbRecords) && idbRecords.length > 0) {
    setJournalTradesInLocalStorage(idbRecords);
    return idbRecords;
  }

  const localRecords = getJournalTradesFromLocalStorage();
  if (localRecords.length > 0) {
    setJournalTradesInIndexedDb(localRecords).catch((e) =>
      console.warn('Background journal migration to IndexedDB failed:', e)
    );
    return localRecords;
  }

  return [];
}

/**
 * Persist journal transactions to both IndexedDB and localStorage
 */
export async function persistJournalTrades(records) {
  let idbSaved = false;
  try {
    await setJournalTradesInIndexedDb(records);
    idbSaved = true;
  } catch (err) {
    console.warn('IndexedDB journal persistence error:', err);
  }

  setJournalTradesInLocalStorage(records);
  return idbSaved;
}

/**
 * Clear all journal trades
 */
export async function clearPersistedJournalTrades() {
  try {
    const db = await openIndexedDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(JOURNAL_STORE_NAME, 'readwrite');
      const store = tx.objectStore(JOURNAL_STORE_NAME);
      store.clear();
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to clear journal IndexedDB:', err);
  }

  try {
    localStorage.removeItem(JOURNAL_STORAGE_KEY);
  } catch (err) {
    console.warn('Failed to clear journal localStorage:', err);
  }
}

/**
 * Load all journal trade metadata (setup, watched level, comments, notes, images)
 */
export async function loadAllJournalMetadata() {
  const metaMap = {};

  try {
    const db = await openIndexedDb();
    const records = await new Promise((resolve, reject) => {
      const tx = db.transaction(JOURNAL_META_STORE_NAME, 'readonly');
      const store = tx.objectStore(JOURNAL_META_STORE_NAME);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(tx.error);
    });

    if (Array.isArray(records)) {
      records.forEach((r) => {
        if (r && r.tradeId) {
          metaMap[r.tradeId] = r;
        }
      });
      return metaMap;
    }
  } catch (err) {
    console.warn('IndexedDB journal metadata read error:', err);
  }

  try {
    const raw = localStorage.getItem(JOURNAL_METADATA_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return parsed;
      }
    }
  } catch (err) {
    console.error('Failed to load journal metadata from localStorage:', err);
  }

  return metaMap;
}

/**
 * Save custom journal metadata for a specific tradeId
 */
export async function saveJournalMetadata(tradeId, data) {
  if (!tradeId) return false;

  const record = {
    tradeId,
    watchedValue: data.watchedValue ?? '',
    setupType: data.setupType ?? '',
    comment: data.comment ?? data.notes ?? '',
    notes: data.notes ?? data.comment ?? '',
    images: Array.isArray(data.images) ? data.images : [],
    updatedAt: new Date().toISOString(),
  };

  try {
    const db = await openIndexedDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(JOURNAL_META_STORE_NAME, 'readwrite');
      const store = tx.objectStore(JOURNAL_META_STORE_NAME);
      store.put(record);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('IndexedDB save journal metadata error:', err);
  }

  try {
    const raw = localStorage.getItem(JOURNAL_METADATA_STORAGE_KEY);
    const existing = raw ? JSON.parse(raw) : {};
    existing[tradeId] = {
      ...record,
      imagesCount: record.images.length,
    };
    localStorage.setItem(JOURNAL_METADATA_STORAGE_KEY, JSON.stringify(existing));
  } catch (err) {
    console.warn('LocalStorage save journal metadata warning:', err);
  }

  return true;
}

/**
 * Clear all journal metadata
 */
export async function clearAllJournalMetadata() {
  try {
    const db = await openIndexedDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(JOURNAL_META_STORE_NAME, 'readwrite');
      const store = tx.objectStore(JOURNAL_META_STORE_NAME);
      store.clear();
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('IndexedDB journal metadata clear error:', err);
  }

  try {
    localStorage.removeItem(JOURNAL_METADATA_STORAGE_KEY);
  } catch (err) {
    console.warn('LocalStorage journal metadata clear error:', err);
  }
}

/**
 * Copy all records and metadata from Trade Stats into Journaling
 */
export async function copyTradesFromTradeStatsToJournal() {
  const statsTrades = await loadPersistedTrades();
  const statsMeta = await loadAllTradeMetadata();
  if (!statsTrades.length) return { copiedCount: 0 };

  const currentJournalTrades = await loadPersistedJournalTrades();
  const currentJournalMeta = await loadAllJournalMetadata();

  // Merge trades avoiding exact duplicates by tr_no or composite key
  const existingTrNos = new Set();
  currentJournalTrades.forEach((t) => {
    const id = t.tr_no ?? t.transactionId;
    if (id) existingTrNos.add(String(id).trim());
  });

  const newTrades = [];
  for (const t of statsTrades) {
    const trNo = String(t.tr_no ?? t.transactionId ?? '').trim();
    if (!trNo || !existingTrNos.has(trNo)) {
      newTrades.push(t);
      if (trNo) existingTrNos.add(trNo);
    }
  }

  const mergedTrades = [...currentJournalTrades, ...newTrades];
  await persistJournalTrades(mergedTrades);

  // Merge metadata
  const mergedMeta = { ...statsMeta, ...currentJournalMeta };
  for (const [tId, meta] of Object.entries(mergedMeta)) {
    await saveJournalMetadata(tId, meta);
  }

  return {
    copiedCount: newTrades.length,
    totalJournalTrades: mergedTrades.length,
  };
}

