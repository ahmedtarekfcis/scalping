/**
 * Trade Deduplication Engine
 *
 * Reliably identifies duplicate trade executions using:
 * 1. Broker Transaction Number (tr_no / transactionId / order_id)
 * 2. Internal / Broker Record ID (id)
 * 3. Execution Composite Signature: [date + time + symbol + side + qty + price + gross_amount]
 *    Tracks occurrence counts to handle multiple executions occurring at the exact same second.
 */

export function cleanId(v) {
  if (v === null || v === undefined) return '';
  const s = String(v).trim();
  if (!s || s.toLowerCase() === 'null' || s.toLowerCase() === 'undefined') return '';
  return s;
}

export function cleanDate(dt, time, sysDate) {
  let s = String(dt || '').trim();
  if (s.includes('T')) s = s.split('T')[0];
  if (s.includes(' ')) s = s.split(' ')[0];
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

  // Try extracting from time if it contains full date
  const t = String(time || '').trim();
  if (t.includes(' ') && /^\d{4}-\d{2}-\d{2}/.test(t)) return t.split(' ')[0];
  if (t.includes('T') && /^\d{4}-\d{2}-\d{2}/.test(t)) return t.split('T')[0];

  // Try extracting from sysDate
  const sd = String(sysDate || '').trim();
  if (sd.includes('T')) return sd.split('T')[0];
  if (sd.includes(' ')) return sd.split(' ')[0];

  return s;
}

export function cleanTime(time) {
  if (!time) return '';
  let s = String(time).trim();
  if (!s || s.toLowerCase() === 'null' || s.toLowerCase() === 'undefined') return '';
  if (s.includes(' ')) s = s.split(' ')[1] || s;
  if (s.includes('T')) s = s.split('T')[1] || s;
  // Strip sub-seconds and timezone if present
  s = s.split('.')[0].replace(/Z|[-+]\d{2}:?\d{2}$/, '').trim();
  return s;
}

export function cleanSide(side, qty) {
  const s = String(side || '').trim().toUpperCase();
  if (s.startsWith('B') || s === 'BUY' || s === 'LONG') return 'B';
  if (s.startsWith('S') || s === 'SELL' || s === 'SHORT' || s === 'SS') return 'S';
  if (qty !== undefined && qty !== null) {
    return Number(qty) < 0 ? 'S' : 'B';
  }
  return s || 'TRD';
}

export function cleanNum(val, decimals = 4) {
  if (val === null || val === undefined) return '0';
  const cleanStr = String(val).replace(/[$,\s]/g, '');
  const n = parseFloat(cleanStr);
  return Number.isNaN(n) ? '0' : Math.abs(n).toFixed(decimals);
}

export function getExecutionCompositeKey(t) {
  const d = cleanDate(t.trade_dt || t.tradeDate, t.exec_time || t.execTime, t.system_date);
  const tm = cleanTime(t.exec_time || t.execTime);
  const sym = String(t.symbol || '').trim().toUpperCase();
  const side = cleanSide(t.trd_type || t.tradeType, t.qty ?? t.quantity);
  const q = cleanNum(t.qty ?? t.quantity, 0);
  const p = cleanNum(t.price, 4);
  const ga = cleanNum(t.g_amt ?? t.grossAmount, 2);
  return `${d}|${tm}|${sym}|${side}|${q}|${p}|${ga}`;
}

/**
 * Deduplicate incoming transactions against existing records.
 *
 * @param {Array} existingList - Current transactions already saved in storage
 * @param {Array} incomingList - Newly parsed transactions to be imported
 * @returns {{ newRecords: Array, duplicateCount: number, totalIncoming: number }}
 */
export function deduplicateTrades(existingList = [], incomingList = []) {
  const existingTrNos = new Set();
  const existingIds = new Set();
  const compositeCount = new Map();

  for (const t of existingList) {
    const trNo = cleanId(t.tr_no ?? t.transactionId);
    if (trNo) existingTrNos.add(trNo);

    const id = cleanId(t.id);
    if (id) existingIds.add(id);

    const compKey = getExecutionCompositeKey(t);
    compositeCount.set(compKey, (compositeCount.get(compKey) || 0) + 1);
  }

  const newRecords = [];
  let duplicateCount = 0;

  for (const item of incomingList) {
    const trNo = cleanId(item.tr_no ?? item.transactionId);
    const id = cleanId(item.id);
    const compKey = getExecutionCompositeKey(item);

    let isDuplicate = false;

    // Check 1: Unique broker transaction number match
    if (trNo && existingTrNos.has(trNo)) {
      isDuplicate = true;
    }
    // Check 2: Unique system ID match
    else if (id && existingIds.has(id)) {
      isDuplicate = true;
    }
    // Check 3: Execution signature match (when IDs are not provided or not present in existing)
    else {
      const availableCount = compositeCount.get(compKey) || 0;
      if (availableCount > 0) {
        compositeCount.set(compKey, availableCount - 1);
        isDuplicate = true;
      }
    }

    if (isDuplicate) {
      duplicateCount++;
    } else {
      newRecords.push(item);
      if (trNo) existingTrNos.add(trNo);
      if (id) existingIds.add(id);
      compositeCount.set(compKey, (compositeCount.get(compKey) || 0) + 1);
    }
  }

  return {
    newRecords,
    duplicateCount,
    totalIncoming: incomingList.length,
  };
}

