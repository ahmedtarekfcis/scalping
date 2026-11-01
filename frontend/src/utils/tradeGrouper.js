/**
 * Trade Grouping & Position Lifecycle Engine
 *
 * Groups atomic transaction executions into complete round-trip Trades (Positions):
 * - An entry (Buy for Long, Sell Short for Short) initiates a Trade.
 * - Subsequent executions belong to that Trade until the position is completely flat (qty returns to 0).
 * - Identifies anomalous / secondary entries (e.g. Averaging down or adding to a position).
 * - Associates custom setup metadata (watchedValue, setupType, notes, images) per Trade.
 */

export function buildTradeId(symbol, date, entryTime, firstTxId) {
  const s = String(symbol || 'UNKNOWN').trim().toUpperCase();
  const d = String(date || '').trim();
  const t = String(entryTime || '').trim().replace(/:/g, '');
  const id = String(firstTxId || '').trim();
  return `TRD_${s}_${d}_${t}${id ? '_' + id : ''}`;
}

/**
 * Group raw transactions into round-trip Trades.
 *
 * @param {Array} rawTransactions - List of all transaction objects
 * @param {Object} metadataMap - Map of tradeId -> { watchedValue, setupType, notes, images }
 * @returns {Array} Array of grouped Trade objects
 */
export function groupTransactionsIntoTrades(rawTransactions = [], metadataMap = {}) {
  if (!Array.isArray(rawTransactions) || !rawTransactions.length) return [];

  // 1. Sort all transactions chronologically
  const sorted = [...rawTransactions].sort((a, b) => {
    const dtA = `${a.trade_dt || a.tradeDate || ''} ${a.exec_time || a.execTime || ''}`;
    const dtB = `${b.trade_dt || b.tradeDate || ''} ${b.exec_time || b.execTime || ''}`;
    if (dtA && dtB && dtA !== dtB) {
      return dtA.localeCompare(dtB);
    }
    return (Number(a.id) || 0) - (Number(b.id) || 0);
  });

  // 2. Group by date and symbol
  const symbolMap = new Map();

  for (const tx of sorted) {
    const sym = String(tx.symbol || 'OTHER').trim().toUpperCase();
    const dt = String(tx.trade_dt || tx.tradeDate || '').trim();
    const groupKey = `${dt}_${sym}`;

    if (!symbolMap.has(groupKey)) {
      symbolMap.set(groupKey, []);
    }
    symbolMap.get(groupKey).push(tx);
  }

  const allTrades = [];

  // 3. Process each symbol-day stream into trades
  for (const [groupKey, txList] of symbolMap.entries()) {
    let currentTrade = null;
    let openQty = 0;
    let tradeIndex = 1;

    for (let i = 0; i < txList.length; i++) {
      const tx = txList[i];
      const rawSide = String(tx.trd_type || tx.tradeType || '').trim().toUpperCase();
      const isBuy = rawSide.startsWith('B') || rawSide === 'BUY';
      const isSell = rawSide.startsWith('S') || rawSide === 'SELL' || rawSide === 'SHORT';
      const qty = Math.abs(Number(tx.qty !== undefined ? tx.qty : tx.quantity) || 0);
      const price = Number(tx.price) || 0;
      const fee = Number(tx.totalFees ?? (tx.comm || 0)) || 0;

      // Start a new trade if not currently tracking one
      if (!currentTrade) {
        const direction = isBuy ? 'LONG' : isSell ? 'SHORT' : 'LONG';
        const date = tx.trade_dt || tx.tradeDate || '';
        const entryTime = tx.exec_time || tx.execTime || '';
        const firstTxId = tx.tr_no ?? tx.transactionId ?? tx.id ?? i;
        const tradeId = buildTradeId(tx.symbol, date, entryTime, `${firstTxId}_${tradeIndex}`);

        currentTrade = {
          tradeId,
          tradeNumber: tradeIndex++,
          symbol: String(tx.symbol || '').trim().toUpperCase(),
          date,
          direction,
          status: 'OPEN',
          entryTime,
          exitTime: '',
          executions: [],
          openQty: 0,
          totalQty: 0,
          totalEntryQty: 0,
          totalExitQty: 0,
          totalEntryAmount: 0,
          totalExitAmount: 0,
          totalFees: 0,
          avgEntryPrice: 0,
          avgExitPrice: 0,
          grossPnL: 0,
          netPnL: 0,
          hasAnomaly: false,
          watchedValue: metadataMap[tradeId]?.watchedValue || '',
          setupType: metadataMap[tradeId]?.setupType || '',
          comment: metadataMap[tradeId]?.comment || metadataMap[tradeId]?.notes || '',
          notes: metadataMap[tradeId]?.notes || metadataMap[tradeId]?.comment || '',
          images: metadataMap[tradeId]?.images || [],
        };
        openQty = 0;
      }

      // Check if this execution is an anomaly (AVG DOWN or secondary buy while already in position)
      let isAnomaly = false;
      let anomalyReason = '';

      if (currentTrade.direction === 'LONG') {
        if (isBuy) {
          if (currentTrade.executions.length > 0 && openQty > 0) {
            isAnomaly = true;
            anomalyReason = 'AVG / Extra Buy';
            currentTrade.hasAnomaly = true;
          }
          openQty += qty;
          currentTrade.totalEntryQty += qty;
          currentTrade.totalEntryAmount += qty * price;
        } else if (isSell) {
          openQty -= qty;
          currentTrade.totalExitQty += qty;
          currentTrade.totalExitAmount += qty * price;
        }
      } else {
        // SHORT position
        if (isSell) {
          if (currentTrade.executions.length > 0 && openQty > 0) {
            isAnomaly = true;
            anomalyReason = 'AVG / Extra Short';
            currentTrade.hasAnomaly = true;
          }
          openQty += qty;
          currentTrade.totalEntryQty += qty;
          currentTrade.totalEntryAmount += qty * price;
        } else if (isBuy) {
          openQty -= qty;
          currentTrade.totalExitQty += qty;
          currentTrade.totalExitAmount += qty * price;
        }
      }

      currentTrade.totalQty += qty;
      currentTrade.totalFees += fee;
      currentTrade.exitTime = tx.exec_time || tx.execTime || currentTrade.exitTime;

      // Attach annotated execution
      currentTrade.executions.push({
        ...tx,
        tradeId: currentTrade.tradeId,
        isAnomaly,
        anomalyReason,
        posAfter: Math.max(0, openQty),
      });

      // If position reached 0 (or negative from full closure/reversal), trade is closed
      if (openQty <= 0.0001) {
        currentTrade.status = 'CLOSED';
        currentTrade.openQty = 0;

        // Calculate averages & PnL
        if (currentTrade.totalEntryQty > 0) {
          currentTrade.avgEntryPrice = currentTrade.totalEntryAmount / currentTrade.totalEntryQty;
        }
        if (currentTrade.totalExitQty > 0) {
          currentTrade.avgExitPrice = currentTrade.totalExitAmount / currentTrade.totalExitQty;
        }

        const closedQty = Math.min(currentTrade.totalEntryQty, currentTrade.totalExitQty);
        if (currentTrade.direction === 'LONG') {
          currentTrade.grossPnL = (currentTrade.avgExitPrice - currentTrade.avgEntryPrice) * closedQty;
        } else {
          currentTrade.grossPnL = (currentTrade.avgEntryPrice - currentTrade.avgExitPrice) * closedQty;
        }
        currentTrade.netPnL = currentTrade.grossPnL - currentTrade.totalFees;

        allTrades.push(currentTrade);
        currentTrade = null;
        openQty = 0;
      }
    }

    // If still open at end of data stream
    if (currentTrade) {
      currentTrade.status = 'OPEN';
      currentTrade.openQty = openQty;
      if (currentTrade.totalEntryQty > 0) {
        currentTrade.avgEntryPrice = currentTrade.totalEntryAmount / currentTrade.totalEntryQty;
      }
      if (currentTrade.totalExitQty > 0) {
        currentTrade.avgExitPrice = currentTrade.totalExitAmount / currentTrade.totalExitQty;
      }
      const closedQty = Math.min(currentTrade.totalEntryQty, currentTrade.totalExitQty);
      if (closedQty > 0) {
        if (currentTrade.direction === 'LONG') {
          currentTrade.grossPnL = (currentTrade.avgExitPrice - currentTrade.avgEntryPrice) * closedQty;
        } else {
          currentTrade.grossPnL = (currentTrade.avgEntryPrice - currentTrade.avgExitPrice) * closedQty;
        }
        currentTrade.netPnL = currentTrade.grossPnL - currentTrade.totalFees;
      }
      allTrades.push(currentTrade);
    }
  }

  // 4. Sort all trades chronologically by date and entry time
  allTrades.sort((a, b) => {
    const dtA = `${a.date || ''} ${a.entryTime || ''}`;
    const dtB = `${b.date || ''} ${b.entryTime || ''}`;
    return dtA.localeCompare(dtB);
  });

  return allTrades;
}

