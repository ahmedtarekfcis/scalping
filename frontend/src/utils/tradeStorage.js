/**
 * Persistent Storage for Trading Stats
 * Uses IndexedDB as primary persistent storage (unlimited quota, immune to localStorage limits),
 * with localStorage as an immediate synchronous cache and fallback.
 */

const DB_NAME = 'TradeEdgeStatsDB';
const DB_VERSION = 5;
const STORE_NAME = 'trades';
const META_STORE_NAME = 'tradeMetadata';
const JOURNAL_STORE_NAME = 'journalTrades';
const JOURNAL_META_STORE_NAME = 'journalMetadata';
const BEHAVIORAL_STORE_NAME = 'behavioralTrades';
export const STORAGE_KEY = 'tradeStatsData';
export const LEGACY_STORAGE_KEY = 'tradeStatsTransactions';
export const METADATA_STORAGE_KEY = 'tradeStatsMetadata';
export const JOURNAL_STORAGE_KEY = 'journalingTradesData';
export const JOURNAL_METADATA_STORAGE_KEY = 'journalingMetadata';
export const BEHAVIORAL_JOURNAL_STORAGE_KEY = 'behavioralJournalTrades';

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
      if (!db.objectStoreNames.contains(BEHAVIORAL_STORE_NAME)) {
        db.createObjectStore(BEHAVIORAL_STORE_NAME, { keyPath: 'id' });
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

// ============================================================================
// BEHAVIORAL TRADING JOURNAL STORAGE (Rebuilt from scratch)
// ============================================================================

/**
 * Get behavioral journal trades synchronously from localStorage
 */
/**
 * Merges multiple trade lists by id.
 * Prevents any trade from being lost or deleted by stale reads or partial writes.
 * If the same trade id appears multiple times, preserves the most recent update.
 */
export function mergeTradesById(...lists) {
  const map = new Map();
  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    for (const t of list) {
      if (!t || !t.id) continue;
      const id = String(t.id).trim();
      if (id.startsWith('demo-')) continue;

      if (!map.has(id)) {
        map.set(id, { ...t });
      } else {
        const existing = map.get(id);
        const existingTime = new Date(existing.updatedAt || existing.createdAt || 0).getTime();
        const newTime = new Date(t.updatedAt || t.createdAt || 0).getTime();
        if (newTime >= existingTime) {
          map.set(id, { ...existing, ...t });
        } else {
          map.set(id, { ...t, ...existing });
        }
      }
    }
  }
  return Array.from(map.values()).sort((a, b) => {
    const dtA = `${a.tradeDate || ''} ${a.tradeTime || ''}`;
    const dtB = `${b.tradeDate || ''} ${b.tradeTime || ''}`;
    return dtB.localeCompare(dtA);
  });
}

/**
 * Get behavioral journal trades synchronously from localStorage.
 * Checks primary key and legacy/fallback keys to ensure nothing is missed.
 */
export function getBehavioralTradesFromLocalStorage() {
  try {
    const raw = localStorage.getItem(BEHAVIORAL_JOURNAL_STORAGE_KEY);
    let parsed = [];
    if (raw) {
      try {
        const data = JSON.parse(raw);
        if (Array.isArray(data)) parsed = data;
      } catch (e) {
        console.error('Failed to parse behavioral trades from localStorage:', e);
      }
    }

    // Also check alternate manual key in case trades were saved there previously
    let legacy = [];
    try {
      const legRaw = localStorage.getItem(JOURNAL_STORAGE_KEY);
      if (legRaw) {
        const legParsed = JSON.parse(legRaw);
        if (Array.isArray(legParsed)) {
          legacy = legParsed.filter((t) => t && String(t.id || '').startsWith('JT-'));
        }
      }
    } catch (e) { /* ignore */ }

    return mergeTradesById(parsed, legacy);
  } catch (err) {
    console.error('Failed to read behavioral trades from localStorage:', err);
    return [];
  }
}

/**
 * Set behavioral journal trades synchronously in localStorage.
 * Handles storage quota limits safely by storing lightweight fallback if heavy base64 screenshots exceed quota.
 */
export function setBehavioralTradesInLocalStorage(trades) {
  try {
    const clean = Array.isArray(trades) ? trades.filter((t) => t && !String(t.id).startsWith('demo-')) : [];
    localStorage.setItem(BEHAVIORAL_JOURNAL_STORAGE_KEY, JSON.stringify(clean));
    return true;
  } catch (err) {
    console.warn('LocalStorage save warning, trying safe screenshot-stripped fallback:', err);
    try {
      // Fallback: If quota exceeded due to large base64 screenshots,
      // store the trades without heavy screenshots in localStorage (screenshots remain in IndexedDB),
      // ensuring that trade records, prices, discipline stats, and dates are NEVER lost!
      const safeTrades = trades.map((t) => {
        const copy = { ...t };
        if (Array.isArray(copy.screenshots) && copy.screenshots.length > 0) {
          copy.screenshots = copy.screenshots.map((s) => (s && s.length > 20000 ? '[STORED_IN_IDB]' : s));
        }
        return copy;
      });
      localStorage.setItem(BEHAVIORAL_JOURNAL_STORAGE_KEY, JSON.stringify(safeTrades));
      return true;
    } catch (fallbackErr) {
      console.error('Critical: LocalStorage save failed completely:', fallbackErr);
      return false;
    }
  }
}

/**
 * Read all behavioral journal trades from IndexedDB
 */
export async function getBehavioralTradesFromIndexedDb() {
  try {
    const db = await openIndexedDb();
    if (!db.objectStoreNames.contains(BEHAVIORAL_STORE_NAME)) {
      console.warn(`IndexedDB store ${BEHAVIORAL_STORE_NAME} not present yet`);
      return [];
    }
    return new Promise((resolve, reject) => {
      const tx = db.transaction(BEHAVIORAL_STORE_NAME, 'readonly');
      const store = tx.objectStore(BEHAVIORAL_STORE_NAME);
      const req = store.getAll();
      req.onsuccess = () => {
        const list = req.result || [];
        resolve(list.filter((t) => t && !String(t.id).startsWith('demo-')));
      };
      req.onerror = () => reject(req.error || new Error('Failed to retrieve behavioral trades'));
    });
  } catch (err) {
    console.warn('IndexedDB behavioral trades read error:', err);
    return [];
  }
}

/**
 * Save all behavioral journal trades to IndexedDB
 */
export async function setBehavioralTradesInIndexedDb(trades) {
  try {
    const db = await openIndexedDb();
    if (!db.objectStoreNames.contains(BEHAVIORAL_STORE_NAME)) {
      console.warn(`IndexedDB store ${BEHAVIORAL_STORE_NAME} not present yet`);
      return false;
    }
    return new Promise((resolve, reject) => {
      const tx = db.transaction(BEHAVIORAL_STORE_NAME, 'readwrite');
      const store = tx.objectStore(BEHAVIORAL_STORE_NAME);
      store.clear();
      const clean = Array.isArray(trades) ? trades.filter((t) => t && !String(t.id).startsWith('demo-')) : [];
      for (let i = 0; i < clean.length; i++) {
        store.put(clean[i]);
      }
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error || new Error('Failed to save behavioral trades to IndexedDB'));
    });
  } catch (err) {
    console.warn('IndexedDB set error:', err);
    return false;
  }
}

/**
 * Backend API URL resolver
 */
export function getApiBaseUrl() {
  if (typeof window === 'undefined') return 'http://localhost:8000';
  const hostname = window.location.hostname || 'localhost';
  return `http://${hostname}:8000`;
}

/**
 * Read all trades from the backend JSON file (data/journal_trades.json).
 */
export async function fetchJournalTradesFromFile() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    let res;
    try {
      res = await fetch('/api/journal', { signal: controller.signal });
    } catch {
      res = await fetch(`${getApiBaseUrl()}/api/journal`, { signal: controller.signal });
    }
    clearTimeout(timeoutId);

    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();
    return {
      success: true,
      trades: Array.isArray(data.trades) ? data.trades : [],
      filePath: data.filePath || '',
      fileName: data.fileName || 'journal_trades.json',
      lastModified: data.lastModified || null,
      count: data.count ?? (Array.isArray(data.trades) ? data.trades.length : 0),
    };
  } catch (err) {
    console.warn('Could not read journal from backend JSON file (backend offline?):', err);
    return {
      success: false,
      trades: [],
      error: err.message || String(err),
    };
  }
}

/**
 * Write/sync trades directly into the backend JSON file (data/journal_trades.json).
 */
export async function saveJournalTradesToFile(trades) {
  try {
    const clean = Array.isArray(trades) ? trades.filter((t) => t && !String(t.id).startsWith('demo-')) : [];
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);

    let res;
    try {
      res = await fetch('/api/journal', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trades: clean }),
        signal: controller.signal,
      });
    } catch {
      res = await fetch(`${getApiBaseUrl()}/api/journal`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trades: clean }),
        signal: controller.signal,
      });
    }
    clearTimeout(timeoutId);

    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();
    return { success: true, ...data };
  } catch (err) {
    console.warn('Could not save journal to backend JSON file:', err);
    return { success: false, error: err.message || String(err) };
  }
}

/**
 * Delete a trade from the backend JSON file.
 */
export async function deleteJournalTradeFromFile(tradeId) {
  try {
    let res;
    try {
      res = await fetch(`/api/journal/${encodeURIComponent(tradeId)}`, { method: 'DELETE' });
    } catch {
      res = await fetch(`${getApiBaseUrl()}/api/journal/${encodeURIComponent(tradeId)}`, { method: 'DELETE' });
    }
    return res.ok;
  } catch (e) {
    console.warn('Could not delete trade from backend JSON file:', e);
    return false;
  }
}

/**
 * Clear all trades from the backend JSON file.
 */
export async function clearJournalTradesFile() {
  try {
    let res;
    try {
      res = await fetch('/api/journal', { method: 'DELETE' });
    } catch {
      res = await fetch(`${getApiBaseUrl()}/api/journal`, { method: 'DELETE' });
    }
    return res.ok;
  } catch (e) {
    console.warn('Could not clear backend JSON file:', e);
    return false;
  }
}

/**
 * Get file status information from backend.
 */
export async function getJournalFileInfo() {
  try {
    let res;
    try {
      res = await fetch('/api/journal/info');
    } catch {
      res = await fetch(`${getApiBaseUrl()}/api/journal/info`);
    }
    if (!res.ok) return null;
    const data = await res.json();
    return data.info || null;
  } catch (e) {
    return null;
  }
}

/**
 * Load persisted behavioral journal trades.
 * Primary source of truth: local JSON file (data/journal_trades.json).
 * Automatically migrates existing localStorage / IndexedDB trades on first run so no past trades are lost!
 */
export async function loadPersistedBehavioralTrades() {
  // 1. Read existing local storage & IndexedDB as fallback/migration pool
  const localRecords = getBehavioralTradesFromLocalStorage();
  let idbRecords = [];
  try {
    idbRecords = await getBehavioralTradesFromIndexedDb();
  } catch (err) {
    console.warn('IDB read error, relying on localStorage:', err);
  }

  const localMerged = mergeTradesById(localRecords, idbRecords);

  // 2. Fetch primary source of truth from backend JSON file
  const fileResult = await fetchJournalTradesFromFile();

  if (fileResult.success) {
    // If the JSON file has trades, use it as the source of truth!
    if (Array.isArray(fileResult.trades) && fileResult.trades.length > 0) {
      // Merge with any offline local records
      const allMerged = mergeTradesById(fileResult.trades, localMerged);
      // Sync local caches
      setBehavioralTradesInLocalStorage(allMerged);
      setBehavioralTradesInIndexedDb(allMerged).catch(() => {});
      // If we merged offline trades not yet in the file, save back to file!
      if (allMerged.length > fileResult.trades.length) {
        await saveJournalTradesToFile(allMerged);
      }
      return allMerged;
    } else if (localMerged.length > 0) {
      // JSON file is empty, but user already had trades in browser localStorage/IndexedDB!
      // Auto-migrate them immediately into data/journal_trades.json!
      console.info(`Migrating ${localMerged.length} trades from browser storage into JSON file...`);
      await saveJournalTradesToFile(localMerged);
      return localMerged;
    }
    return fileResult.trades;
  }

  // 3. Backend not reachable; fallback to local storage & IndexedDB
  console.warn('Backend JSON file unreachable; using local storage cache');
  return localMerged;
}

/**
 * Persist behavioral journal trades to the backend JSON file (data/journal_trades.json),
 * with localStorage and IndexedDB maintained as fast synchronous offline caches.
 */
export async function persistBehavioralTrades(trades) {
  const clean = Array.isArray(trades) ? trades.filter((t) => t && !String(t.id).startsWith('demo-')) : [];

  // 1. Immediately update localStorage and IndexedDB so UI feels instantaneous
  setBehavioralTradesInLocalStorage(clean);
  setBehavioralTradesInIndexedDb(clean).catch((err) =>
    console.warn('IndexedDB behavioral persistence error:', err)
  );

  // 2. Persist safely and atomically to data/journal_trades.json
  const fileResult = await saveJournalTradesToFile(clean);

  return fileResult.success;
}

/**
 * Save or update a single behavioral trade.
 * Persists immediately to the JSON file and local caches.
 */
export async function saveSingleBehavioralTrade(trade) {
  if (!trade || !trade.id) return [];
  const targetId = String(trade.id).trim();

  // Read current existing trades
  const fileRes = await fetchJournalTradesFromFile();
  let currentList = [];
  if (fileRes.success && fileRes.trades.length > 0) {
    currentList = fileRes.trades;
  } else {
    const local = getBehavioralTradesFromLocalStorage();
    let idb = [];
    try {
      idb = await getBehavioralTradesFromIndexedDb();
    } catch (e) { /* ignore */ }
    currentList = mergeTradesById(local, idb);
  }

  const index = currentList.findIndex((t) => t && String(t.id).trim() === targetId);
  const nowIso = new Date().toISOString();

  if (index >= 0) {
    currentList[index] = { ...currentList[index], ...trade, updatedAt: nowIso };
  } else {
    currentList.unshift({ ...trade, createdAt: trade.createdAt || nowIso });
  }

  await persistBehavioralTrades(currentList);
  return currentList;
}

/**
 * Delete a single behavioral trade by id
 */
export async function deleteSingleBehavioralTrade(id) {
  const targetId = String(id || '').trim();
  const fileRes = await fetchJournalTradesFromFile();
  let currentList = [];
  if (fileRes.success && fileRes.trades.length > 0) {
    currentList = fileRes.trades;
  } else {
    const local = getBehavioralTradesFromLocalStorage();
    let idb = [];
    try {
      idb = await getBehavioralTradesFromIndexedDb();
    } catch (e) { /* ignore */ }
    currentList = mergeTradesById(local, idb);
  }

  const filtered = currentList.filter((t) => t && String(t.id || '').trim() !== targetId);
  await persistBehavioralTrades(filtered);
  await deleteJournalTradeFromFile(targetId);
  return filtered;
}

/**
 * Clear all behavioral journal trades from both JSON file and local caches.
 */
export async function clearAllBehavioralTrades() {
  await clearJournalTradesFile();

  try {
    const db = await openIndexedDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(BEHAVIORAL_STORE_NAME, 'readwrite');
      const store = tx.objectStore(BEHAVIORAL_STORE_NAME);
      store.clear();
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('Failed to clear behavioral trades in IndexedDB:', err);
  }

  try {
    localStorage.removeItem(BEHAVIORAL_JOURNAL_STORAGE_KEY);
  } catch (err) {
    console.warn('Failed to clear behavioral trades in localStorage:', err);
  }
}


