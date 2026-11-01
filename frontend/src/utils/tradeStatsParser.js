import Papa from 'papaparse';

/** "(0.92)" -> -0.92, "1,762" -> 1762, "$5.00" -> 5, "" -> 0 */
export function parseNum(raw) {
  if (raw === undefined || raw === null) return 0;
  let s = String(raw).trim();
  if (!s || s === '-' || s.toLowerCase() === 'null') return 0;
  let neg = false;
  if (s.startsWith('(') && s.endsWith(')')) {
    neg = true;
    s = s.slice(1, -1);
  }
  s = s.replace(/[$,\s]/g, '');
  if (s.startsWith('-')) {
    neg = !neg;
    s = s.slice(1);
  }
  const n = parseFloat(s);
  return Number.isNaN(n) ? 0 : neg ? -n : n;
}

/**
 * Normalizes an execution time string to "HH:MM:SS" or extracts time from datetime.
 */
function normalizeTime(val) {
  if (val === null || val === undefined) return null;
  const s = String(val).trim();
  if (!s || s.toLowerCase() === 'null') return null;
  if (s.includes(' ')) {
    return s.split(' ')[1] || s;
  }
  if (s.includes('T')) {
    return s.split('T')[1] || s;
  }
  return s;
}

/**
 * Normalizes a trade date to YYYY-MM-DD format.
 */
function normalizeDate(dateVal, timeVal) {
  if (dateVal) {
    const s = String(dateVal).trim();
    if (s.includes('T')) return s.split('T')[0];
    if (s.includes(' ')) return s.split(' ')[0];
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    // Check for MM/DD/YYYY or DD/MM/YYYY
    const parts = s.split(/[-/]/);
    if (parts.length === 3 && parts[2].length === 4) {
      return `${parts[2]}-${parts[0].padStart(2, '0')}-${parts[1].padStart(2, '0')}`;
    }
    return s;
  }
  if (timeVal) {
    const t = String(timeVal).trim();
    if (t.includes(' ') && /^\d{4}-\d{2}-\d{2}/.test(t)) return t.split(' ')[0];
    if (t.includes('T') && /^\d{4}-\d{2}-\d{2}/.test(t)) return t.split('T')[0];
  }
  return null;
}

/**
 * Parses a JSON array or spreadsheet row objects of transactions.
 * Supports camelCase, snake_case, and spaced Title Case keys from broker exports.
 */
export function parseJsonTransactions(items) {
  if (!Array.isArray(items)) return [];

  return items.map((item) => {
    // Symbol
    const symbol = String(
      item.symbol ?? item.Symbol ?? item.sym ?? item.Ticker ?? item.ticker ?? ''
    ).trim().toUpperCase();

    // Quantity & Price
    const qty = parseNum(
      item.qty ?? item.quantity ?? item.Quantity ?? item.Qty ?? item.Shares ?? item.shares ?? item.size ?? 0
    );
    const price = parseNum(
      item.price ?? item.Price ?? item['Trade Price'] ?? item['trade_price'] ?? item['Avg Price'] ?? 0
    );

    // Amounts
    const grossAmount =
      item.g_amt !== undefined && item.g_amt !== null
        ? parseNum(item.g_amt)
        : item.grossAmount !== undefined && item.grossAmount !== null
        ? parseNum(item.grossAmount)
        : item['Gross Amount'] !== undefined && item['Gross Amount'] !== null
        ? parseNum(item['Gross Amount'])
        : qty * price;

    const netAmount =
      item.n_amt !== undefined && item.n_amt !== null
        ? parseNum(item.n_amt)
        : item.netAmount !== undefined && item.netAmount !== null
        ? parseNum(item.netAmount)
        : item['Net Amount'] !== undefined && item['Net Amount'] !== null
        ? parseNum(item['Net Amount'])
        : grossAmount;

    // Fees
    const comm = parseNum(
      item.comm ?? item.commission ?? item.Commission ?? item['Comm/Fee'] ?? item['IB Commission'] ?? 0
    );
    const exch = parseNum(item.exch_fee ?? item.exchFee ?? item['Exch Fee'] ?? 0);
    const sec = parseNum(item.sec_fee ?? item.secFee ?? item['Sec Fee'] ?? 0);
    const m1 = parseNum(item.m_fee1 ?? item.tafFee ?? item['Taf Fee'] ?? 0);
    const m4 = parseNum(item.m_fee4 ?? item.miscFee ?? item['Misc Fee'] ?? 0);

    let fee = comm + exch + sec + m1 + m4;
    if (fee === 0 && grossAmount && netAmount) {
      fee = Math.abs(grossAmount - netAmount);
    }

    // Identifiers
    const rawTrNo =
      item.tr_no ??
      item.transactionId ??
      item['Transaction ID'] ??
      item['Transaction Id'] ??
      item.order_id ??
      item.OrderId ??
      item.ticket ??
      null;
    const tr_no = rawTrNo !== null && rawTrNo !== undefined ? String(rawTrNo).trim() : null;

    const rawId = item.id ?? item.ID ?? item.Id ?? null;
    const id = rawId !== null && rawId !== undefined ? rawId : null;

    // Date & Time
    const rawTime =
      item.exec_time ??
      item.execTime ??
      item['Exec Time'] ??
      item['Execution Time'] ??
      item.Time ??
      item.time ??
      item['Date/Time'] ??
      null;
    const rawDate =
      item.trade_dt ??
      item.tradeDate ??
      item['Trade Date'] ??
      item.Date ??
      item.date ??
      item.system_date ??
      null;

    const trade_dt = normalizeDate(rawDate, rawTime);
    const exec_time = normalizeTime(rawTime);

    // Trade Type / Side
    let rawSide = String(
      item.trd_type ??
      item.tradeType ??
      item['Trade Type'] ??
      item.Side ??
      item.side ??
      item.Action ??
      item.action ??
      ''
    ).trim().toUpperCase();

    if (!rawSide) {
      rawSide = qty < 0 ? 'S' : 'B';
    } else if (rawSide.startsWith('B') || rawSide === 'BUY') {
      rawSide = 'B';
    } else if (rawSide.startsWith('S') || rawSide === 'SELL' || rawSide === 'SHORT') {
      rawSide = 'S';
    }

    const entryType = String(item.entry_type ?? item.entryType ?? 'TRD').trim();
    const settleDate = item.settle_dt ?? item.settleDate ?? item['Settle Date'] ?? null;
    const description = String(item.descr ?? item.description ?? item.Description ?? item.memo ?? '').trim();

    return {
      id,
      systemId: item.systemId ?? item['System ID'] ?? null,
      system_date: item.system_date ?? null,
      tr_no,
      entry_type: entryType || null,
      trd_type: rawSide,
      trade_dt,
      settle_dt: settleDate,
      exec_time,
      symbol,
      qty,
      price,
      g_amt: grossAmount,
      n_amt: netAmount,
      comm,
      exch_fee: exch || null,
      sec_fee: sec || null,
      descr: description || null,
      m_fee1: m1 || null,
      m_fee4: m4 || null,

      // Internal helpers for aggregation / grouping
      transactionId: tr_no || String(id || ''),
      entryType,
      tradeType: rawSide,
      tradeDate: trade_dt || '',
      settleDate: settleDate || '',
      execTime: exec_time || '',
      quantity: qty,
      grossAmount,
      netAmount,
      commission: comm,
      exchFee: exch,
      secFee: sec,
      mFee1: m1,
      mFee4: m4,
      totalFees: fee,
      description,
    };
  });
}

/**
 * Universal parser for CSV text
 */
function parseCsvTransactions(text) {
  const parsed = Papa.parse(text, { skipEmptyLines: 'greedy' });
  const rows = parsed.data;
  if (!rows || !rows.length) return [];

  // Find header row dynamically
  let headerIndex = -1;
  let colMap = null;

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i].map((c) => String(c ?? '').trim().toLowerCase());
    const hasSymbol = row.some((c) => c === 'symbol' || c === 'ticker' || c === 'sym');
    const hasDateOrTx = row.some(
      (c) =>
        c === 'transaction id' ||
        c === 'tr_no' ||
        c === 'trade date' ||
        c === 'date' ||
        c === 'time' ||
        c === 'quantity' ||
        c === 'price'
    );

    if (hasSymbol && hasDateOrTx) {
      headerIndex = i;
      colMap = {};
      row.forEach((colName, idx) => {
        colMap[colName] = idx;
      });
      break;
    }
  }

  // Fallback: check if row 0 has transaction id or tr_no
  if (headerIndex === -1) {
    for (let i = 0; i < Math.min(rows.length, 5); i++) {
      const row = rows[i].map((c) => String(c ?? '').trim().toLowerCase());
      if (row.includes('transaction id') || row.includes('tr_no')) {
        headerIndex = i;
        colMap = {};
        row.forEach((colName, idx) => {
          colMap[colName] = idx;
        });
        break;
      }
    }
  }

  if (headerIndex === -1 || !colMap) return [];

  const getCell = (r, ...keys) => {
    for (const key of keys) {
      const idx = colMap[key.toLowerCase()];
      if (idx !== undefined && idx < r.length) {
        return r[idx];
      }
    }
    return '';
  };

  const transactions = [];

  for (let i = headerIndex + 1; i < rows.length; i++) {
    const row = rows[i];
    if (!row || !row.length) continue;

    const symbol = String(getCell(row, 'symbol', 'ticker', 'sym') ?? '').trim().toUpperCase();
    if (!symbol || symbol === 'NULL') continue;

    const txIdRaw = String(getCell(row, 'transaction id', 'tr_no', 'transactionid', 'order id', 'id') ?? '').trim();
    const txId = txIdRaw && txIdRaw.toLowerCase() !== 'null' ? txIdRaw : null;

    const entryType = String(getCell(row, 'entry type', 'entry_type') || 'TRD').trim();
    let tradeType = String(getCell(row, 'trade type', 'trd_type', 'side', 'action') || '').trim().toUpperCase();

    const rawDate = String(getCell(row, 'trade date', 'trade_date', 'trade_dt', 'date') || '').trim();
    const rawTime = String(getCell(row, 'exec time', 'exec_time', 'time', 'trade time', 'execution time', 'date/time', 'date_time') || '').trim();

    const tradeDate = normalizeDate(rawDate, rawTime);
    const execTime = normalizeTime(rawTime);

    const quantity = parseNum(getCell(row, 'quantity', 'qty', 'shares', 'size'));
    const price = parseNum(getCell(row, 'price', 'trade price', 'exec price', 'avg price'));

    if (quantity === 0 && price === 0) continue;

    if (!tradeType) {
      tradeType = quantity < 0 ? 'S' : 'B';
    } else if (tradeType.startsWith('B') || tradeType === 'BUY') {
      tradeType = 'B';
    } else if (tradeType.startsWith('S') || tradeType === 'SELL' || tradeType === 'SHORT') {
      tradeType = 'S';
    }

    const grossAmount = parseNum(getCell(row, 'gross amount', 'g_amt', 'gross')) || Math.abs(quantity * price);
    const netAmount = parseNum(getCell(row, 'net amount', 'n_amt', 'net', 'amount')) || grossAmount;

    const commission = parseNum(getCell(row, 'commission', 'comm', 'fee', 'fees', 'comm/fee'));
    const exchFee = parseNum(getCell(row, 'exch fee', 'exch_fee'));
    const secFee = parseNum(getCell(row, 'sec fee', 'sec_fee'));
    const tafFee = parseNum(getCell(row, 'taf fee', 'm_fee1'));
    const miscFee = parseNum(getCell(row, 'misc fee', 'm_fee4'));
    const description = String(getCell(row, 'description', 'descr') || '').trim();

    const explicitFees = commission + exchFee + secFee + tafFee + miscFee;
    let fee = explicitFees;
    if (fee === 0 && grossAmount && netAmount) {
      fee = Math.abs(grossAmount - netAmount);
    }

    transactions.push({
      id: null,
      systemId: null,
      system_date: null,
      tr_no: txId,
      entry_type: entryType === 'null' ? null : entryType,
      trd_type: tradeType,
      trade_dt: tradeDate,
      settle_dt: null,
      exec_time: execTime,
      symbol,
      qty: quantity,
      price,
      g_amt: grossAmount,
      n_amt: netAmount,
      comm: commission,
      exch_fee: exchFee || null,
      sec_fee: secFee || null,
      descr: description === 'null' ? null : description,
      m_fee1: tafFee || null,
      m_fee4: miscFee || null,

      transactionId: txId || '',
      entryType: entryType === 'null' ? '' : entryType,
      tradeType,
      tradeDate: tradeDate || '',
      settleDate: '',
      execTime: execTime || '',
      quantity,
      grossAmount,
      netAmount,
      commission,
      exchFee,
      secFee,
      mFee1: tafFee,
      mFee4: miscFee,
      totalFees: fee,
      description: description === 'null' ? '' : description,
    });
  }

  return transactions;
}

/**
 * Universal parser for input (JSON array, JSON string, CSV string, or JS array of objects).
 */
export function parseTradeStatsCsv(input) {
  if (!input) return [];

  if (Array.isArray(input)) {
    return parseJsonTransactions(input);
  }

  if (typeof input === 'object' && input !== null) {
    const arr = Array.isArray(input.data)
      ? input.data
      : Array.isArray(input.transactions)
      ? input.transactions
      : Array.isArray(input.trades)
      ? input.trades
      : Array.isArray(input.history)
      ? input.history
      : input.tr_no || input.symbol || input.id
      ? [input]
      : [];
    return parseJsonTransactions(arr);
  }

  if (typeof input === 'string') {
    let text = input.trim();
    if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);

    // Try parsing as JSON array or object
    if (text.startsWith('[') || text.startsWith('{')) {
      try {
        const parsed = JSON.parse(text);
        const arr = Array.isArray(parsed)
          ? parsed
          : Array.isArray(parsed.data)
          ? parsed.data
          : Array.isArray(parsed.transactions)
          ? parsed.transactions
          : Array.isArray(parsed.trades)
          ? parsed.trades
          : Array.isArray(parsed.history)
          ? parsed.history
          : parsed.tr_no || parsed.symbol || parsed.id
          ? [parsed]
          : [];
        if (arr.length > 0) {
          return parseJsonTransactions(arr);
        }
      } catch (e) {
        // Fall back to CSV if not valid JSON
      }
    }

    return parseCsvTransactions(text);
  }

  return [];
}
