<script setup>
import { ref, shallowRef, computed, watch, onMounted, onUnmounted } from 'vue';
import {
  FileSpreadsheet,
  UploadCloud,
  Search,
  Filter,
  Calendar,
  Layers,
  ArrowUpDown,
  Tag,
  ChevronDown,
  ChevronRight,
  Columns,
  SlidersHorizontal,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  X,
  FileDown,
  Table,
  BarChart3,
  TrendingUp,
  PieChart,
  Clock,
  Activity,
  DollarSign,
  Edit3,
  Camera,
  Image,
  Eye,
  Trash2,
  ZoomIn,
  Check,
  AlertTriangle,
  Plus,
  MessageSquare,
  BookOpen,
  Copy,
  FolderDown,
} from 'lucide-vue-next';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';
import { parseTradeStatsCsv } from '../utils/tradeStatsParser';
import {
  getJournalTradesFromLocalStorage,
  loadPersistedJournalTrades,
  persistJournalTrades,
  clearPersistedJournalTrades,
  loadAllJournalMetadata,
  saveJournalMetadata,
  clearAllJournalMetadata,
  copyTradesFromTradeStatsToJournal,
  JOURNAL_STORAGE_KEY,
} from '../utils/tradeStorage';
import { deduplicateTrades } from '../utils/tradeDeduplicator';
import { groupTransactionsIntoTrades } from '../utils/tradeGrouper';

// Helper to format clean transaction record for compact storage
const toCleanJsonRecord = (t) => ({
  id: t.id ?? null,
  systemId: t.systemId ?? null,
  system_date: t.system_date ?? null,
  tr_no: t.tr_no ?? (t.transactionId || null),
  entry_type: t.entry_type ?? (t.entryType || null),
  trd_type: t.trd_type ?? (t.tradeType || null),
  trade_dt: t.trade_dt ?? (t.tradeDate || null),
  settle_dt: t.settle_dt ?? (t.settleDate || null),
  exec_time: t.exec_time ?? (t.execTime || null),
  symbol: t.symbol ?? '',
  qty: t.qty !== undefined ? t.qty : (t.quantity ?? 0),
  price: t.price ?? 0,
  g_amt: t.g_amt !== undefined ? t.g_amt : (t.grossAmount ?? 0),
  n_amt: t.n_amt !== undefined ? t.n_amt : (t.netAmount ?? 0),
  comm: t.comm !== undefined ? t.comm : (t.commission ?? 0),
  exch_fee: t.exch_fee !== undefined ? t.exch_fee : (t.exchFee ?? null),
  sec_fee: t.sec_fee !== undefined ? t.sec_fee : (t.secFee ?? null),
  descr: t.descr !== undefined ? t.descr : (t.description ?? null),
  m_fee1: t.m_fee1 !== undefined ? t.m_fee1 : (t.mFee1 ?? null),
  m_fee4: t.m_fee4 !== undefined ? t.m_fee4 : (t.mFee4 ?? null),
});

// Load stored journal transactions synchronously on initial render
const loadStoredJournalTransactions = () => {
  try {
    const rawRecords = getJournalTradesFromLocalStorage();
    if (Array.isArray(rawRecords) && rawRecords.length > 0) {
      return parseTradeStatsCsv(rawRecords);
    }
  } catch (err) {
    console.error('Failed to load journal transactions from localStorage:', err);
  }
  return [];
};

// ---------------------------------------------------------------- state
const transactions = shallowRef(loadStoredJournalTransactions());
const tradeMetadata = ref({});
const isOffcanvasOpen = ref(false);
const offcanvasMode = ref('create'); // 'create' | 'edit'
const editingTrade = ref(null);
const imagePreviewModal = ref(null);
const isSavingMeta = ref(false);

const getTodayDateStr = () => {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const getCurrentTimeStr = () => {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
};

// Form state for creating or editing trades
const createForm = ref({
  symbol: '',
  date: getTodayDateStr(),
  direction: 'LONG', // 'LONG' | 'SHORT'
  setupType: '',
  watchedValue: '',
  comment: '',
  notes: '',
  images: [],

  // Standard simple 1-entry + optional 1-exit
  entryQty: 100,
  entryPrice: null,
  entryTime: getCurrentTimeStr(),
  isStillOpen: false,
  exitQty: 100,
  exitPrice: null,
  exitTime: getCurrentTimeStr(),
  commission: 0,

  // Advanced multi-fill builder
  isMultiLeg: false,
  legs: [
    { side: 'B', qty: 100, price: null, time: getCurrentTimeStr(), comm: 0 },
    { side: 'S', qty: 100, price: null, time: getCurrentTimeStr(), comm: 0 },
  ],
});

// Single execution fill form when adding an extra fill to an existing trade
const newFillForm = ref({
  side: 'B',
  qty: 100,
  price: null,
  time: getCurrentTimeStr(),
  comm: 0,
});
const showAddFillBox = ref(false);

const SETUP_PRESETS = [
  '9 EMA',
  'High of Day',
  'Round Figure',
  'VWAP Bounce',
  'Breakout',
  'Gap & Go',
  'Support Bounce',
  'Resistance Short',
];

const getSetupBadgeClass = (type) => {
  if (!type) return '';
  const s = String(type).toLowerCase();
  if (s.includes('9') || s.includes('ema')) return 'setup-ema';
  if (s.includes('high') || s.includes('hod')) return 'setup-hod';
  if (s.includes('round') || s.includes('figure') || s.includes('dollar')) return 'setup-round';
  if (s.includes('vwap')) return 'setup-vwap';
  if (s.includes('breakout')) return 'setup-breakout';
  return 'setup-custom';
};

// Open offcanvas for logging a new trade
const openCreateOffcanvas = () => {
  offcanvasMode.value = 'create';
  editingTrade.value = null;
  showAddFillBox.value = false;
  createForm.value = {
    symbol: '',
    date: getTodayDateStr(),
    direction: 'LONG',
    setupType: '',
    watchedValue: '',
    comment: '',
    notes: '',
    images: [],
    entryQty: 100,
    entryPrice: null,
    entryTime: getCurrentTimeStr(),
    isStillOpen: false,
    exitQty: 100,
    exitPrice: null,
    exitTime: getCurrentTimeStr(),
    commission: 0,
    isMultiLeg: false,
    legs: [
      { side: 'B', qty: 100, price: null, time: getCurrentTimeStr(), comm: 0 },
      { side: 'S', qty: 100, price: null, time: getCurrentTimeStr(), comm: 0 },
    ],
  };
  isOffcanvasOpen.value = true;
};

// Open offcanvas for editing an existing trade
const openEditOffcanvas = (trade) => {
  offcanvasMode.value = 'edit';
  editingTrade.value = trade;
  showAddFillBox.value = false;
  const existingMeta = tradeMetadata.value[trade.tradeId] || {};
  createForm.value = {
    symbol: trade.symbol,
    date: trade.date,
    direction: trade.direction,
    setupType: existingMeta.setupType || trade.setupType || '',
    watchedValue: existingMeta.watchedValue || trade.watchedValue || '',
    comment: existingMeta.comment || trade.comment || existingMeta.notes || trade.notes || '',
    notes: existingMeta.notes || trade.notes || '',
    images: Array.isArray(existingMeta.images)
      ? [...existingMeta.images]
      : Array.isArray(trade.images)
      ? [...trade.images]
      : [],
    entryQty: trade.totalEntryQty || 100,
    entryPrice: trade.avgEntryPrice || null,
    entryTime: trade.entryTime || getCurrentTimeStr(),
    isStillOpen: trade.status === 'OPEN',
    exitQty: trade.totalExitQty || 100,
    exitPrice: trade.avgExitPrice || null,
    exitTime: trade.exitTime || getCurrentTimeStr(),
    commission: trade.totalFees || 0,
    isMultiLeg: false,
    legs: [],
  };

  // Pre-fill next fill side
  newFillForm.value = {
    side: trade.direction === 'LONG' ? 'S' : 'B',
    qty: trade.openQty > 0 ? trade.openQty : 100,
    price: null,
    time: getCurrentTimeStr(),
    comm: 0,
  };

  isOffcanvasOpen.value = true;
};

const openTradeImages = (trade) => {
  openEditOffcanvas(trade);
};

const closeOffcanvas = () => {
  isOffcanvasOpen.value = false;
  editingTrade.value = null;
  showAddFillBox.value = false;
};

const selectPresetSetup = (preset) => {
  createForm.value.setupType = preset;
};

const fillAvgPriceAsWatched = () => {
  if (editingTrade.value?.avgEntryPrice) {
    createForm.value.watchedValue = '$' + Number(editingTrade.value.avgEntryPrice).toFixed(2);
  } else if (createForm.value.entryPrice) {
    createForm.value.watchedValue = '$' + Number(createForm.value.entryPrice).toFixed(2);
  }
};

const handleImageUpload = (e) => {
  const files = e.target.files;
  if (!files || !files.length) return;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (!file.type.startsWith('image/')) continue;
    const reader = new FileReader();
    reader.onload = (event) => {
      createForm.value.images.push(event.target.result);
    };
    reader.readAsDataURL(file);
  }
  e.target.value = '';
};

const removeImage = (index) => {
  createForm.value.images.splice(index, 1);
};

// Multi-leg helpers
const addLeg = (side = 'B') => {
  createForm.value.legs.push({
    side,
    qty: 100,
    price: null,
    time: getCurrentTimeStr(),
    comm: 0,
  });
};

const removeLeg = (index) => {
  if (createForm.value.legs.length > 1) {
    createForm.value.legs.splice(index, 1);
  }
};

// Clipboard paste listener for screenshots
const onWindowPaste = (e) => {
  if (!isOffcanvasOpen.value) return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (item.type.indexOf('image') !== -1) {
      const blob = item.getAsFile();
      const reader = new FileReader();
      reader.onload = (ev) => {
        createForm.value.images.push(ev.target.result);
        status.value = {
          text: 'Pasted chart screenshot from clipboard!',
          tone: 'good',
        };
      };
      reader.readAsDataURL(blob);
    }
  }
};

// Save a newly created trade
const saveNewTrade = async () => {
  const sym = String(createForm.value.symbol || '').trim().toUpperCase();
  if (!sym) {
    alert('Please enter a Symbol / Ticker (e.g. TSLA, NVDA)');
    return;
  }

  const dt = createForm.value.date || getTodayDateStr();
  const newTransactions = [];
  const baseTimestamp = Date.now();

  if (createForm.value.isMultiLeg) {
    // Multi-leg executions
    for (let i = 0; i < createForm.value.legs.length; i++) {
      const leg = createForm.value.legs[i];
      const q = Math.abs(Number(leg.qty) || 0);
      const p = Number(leg.price) || 0;
      if (q <= 0 || p <= 0) {
        alert(`Fill #${i + 1} requires valid quantity and price`);
        return;
      }
      const side = leg.side === 'B' ? 'B' : 'S';
      const tm = leg.time || getCurrentTimeStr();
      const comm = Number(leg.comm) || 0;
      const g_amt = q * p;
      const n_amt = side === 'B' ? -(g_amt + comm) : g_amt - comm;

      newTransactions.push({
        id: baseTimestamp + i,
        systemId: 'MANUAL',
        system_date: `${dt}T00:00:00`,
        tr_no: `MAN_${baseTimestamp}_${i}`,
        entry_type: 'TRD',
        trd_type: side,
        trade_dt: dt,
        settle_dt: null,
        exec_time: `${dt} ${tm}`,
        symbol: sym,
        qty: q,
        price: p,
        g_amt,
        n_amt,
        comm,
        exch_fee: null,
        sec_fee: null,
        descr: `Manual journal execution #${i + 1}`,
        m_fee1: null,
        m_fee4: null,
      });
    }
  } else {
    // Standard 1-entry + optional 1-exit
    const entryQ = Math.abs(Number(createForm.value.entryQty) || 0);
    const entryP = Number(createForm.value.entryPrice) || 0;
    if (entryQ <= 0 || entryP <= 0) {
      alert('Please enter valid Entry Quantity and Entry Price');
      return;
    }

    const entrySide = createForm.value.direction === 'SHORT' ? 'S' : 'B';
    const entryTm = createForm.value.entryTime || getCurrentTimeStr();
    const entryComm = Number(createForm.value.commission) || 0;
    const entryGross = entryQ * entryP;
    const entryNet = entrySide === 'B' ? -(entryGross + entryComm) : entryGross - entryComm;

    newTransactions.push({
      id: baseTimestamp,
      systemId: 'MANUAL',
      system_date: `${dt}T00:00:00`,
      tr_no: `MAN_${baseTimestamp}_1`,
      entry_type: 'TRD',
      trd_type: entrySide,
      trade_dt: dt,
      settle_dt: null,
      exec_time: `${dt} ${entryTm}`,
      symbol: sym,
      qty: entryQ,
      price: entryP,
      g_amt: entryGross,
      n_amt: entryNet,
      comm: entryComm,
      exch_fee: null,
      sec_fee: null,
      descr: 'Manual journal entry fill',
      m_fee1: null,
      m_fee4: null,
    });

    // Exit fill if not still open
    if (!createForm.value.isStillOpen) {
      const exitQ = Math.abs(Number(createForm.value.exitQty) || entryQ);
      const exitP = Number(createForm.value.exitPrice) || 0;
      if (exitP <= 0) {
        alert('Please enter a valid Exit Price (or check "Trade Still Open")');
        return;
      }
      const exitSide = entrySide === 'B' ? 'S' : 'B';
      const exitTm = createForm.value.exitTime || getCurrentTimeStr();
      const exitGross = exitQ * exitP;
      const exitNet = exitSide === 'B' ? -(exitGross) : exitGross;

      newTransactions.push({
        id: baseTimestamp + 1,
        systemId: 'MANUAL',
        system_date: `${dt}T00:00:00`,
        tr_no: `MAN_${baseTimestamp}_2`,
        entry_type: 'TRD',
        trd_type: exitSide,
        trade_dt: dt,
        settle_dt: null,
        exec_time: `${dt} ${exitTm}`,
        symbol: sym,
        qty: exitQ,
        price: exitP,
        g_amt: exitGross,
        n_amt: exitNet,
        comm: 0,
        exch_fee: null,
        sec_fee: null,
        descr: 'Manual journal exit fill',
        m_fee1: null,
        m_fee4: null,
      });
    }
  }

  isSavingMeta.value = true;

  try {
    const parsedNewRecords = parseTradeStatsCsv(newTransactions);
    const combined = [...transactions.value, ...parsedNewRecords];
    combined.sort((a, b) => {
      const dtA = `${a.trade_dt || a.tradeDate || ''} ${a.exec_time || a.execTime || ''}`;
      const dtB = `${b.trade_dt || b.tradeDate || ''} ${b.exec_time || b.execTime || ''}`;
      if (dtA && dtB && dtA !== dtB) return dtA.localeCompare(dtB);
      return (Number(a.id) || 0) - (Number(b.id) || 0);
    });

    // Group to identify the generated tradeId
    const grouped = groupTransactionsIntoTrades(combined, tradeMetadata.value);
    const matchingTrade = grouped.find(
      (tr) => tr.symbol === sym && tr.date === dt && tr.executions.some((ex) => ex.tr_no === newTransactions[0].tr_no)
    );

    const targetTradeId = matchingTrade ? matchingTrade.tradeId : `TRD_${sym}_${dt}_${baseTimestamp}`;

    const metaData = {
      watchedValue: createForm.value.watchedValue.trim(),
      setupType: createForm.value.setupType.trim(),
      comment: createForm.value.comment.trim(),
      notes: createForm.value.notes.trim() || createForm.value.comment.trim(),
      images: createForm.value.images,
    };

    await saveJournalMetadata(targetTradeId, metaData);
    tradeMetadata.value = {
      ...tradeMetadata.value,
      [targetTradeId]: { ...metaData, tradeId: targetTradeId },
    };

    await persistJournalTrades(combined.map(toCleanJsonRecord));
    transactions.value = combined;
    expandedDates.value[dt] = true;

    status.value = {
      text: `Logged new ${createForm.value.direction} trade on ${sym}!`,
      tone: 'good',
    };

    closeOffcanvas();
  } catch (err) {
    console.error('Failed to log trade:', err);
    status.value = { text: `Error logging trade: ${err.message}`, tone: 'bad' };
  } finally {
    isSavingMeta.value = false;
  }
};

// Save edits to an existing trade
const saveEditedTrade = async () => {
  if (!editingTrade.value) return;
  isSavingMeta.value = true;
  const tId = editingTrade.value.tradeId;

  const dataToSave = {
    watchedValue: createForm.value.watchedValue.trim(),
    setupType: createForm.value.setupType.trim(),
    comment: createForm.value.comment.trim(),
    notes: createForm.value.notes.trim() || createForm.value.comment.trim(),
    images: createForm.value.images,
  };

  await saveJournalMetadata(tId, dataToSave);

  tradeMetadata.value = {
    ...tradeMetadata.value,
    [tId]: {
      ...dataToSave,
      tradeId: tId,
    },
  };

  status.value = {
    text: `Saved trade journal for ${editingTrade.value.symbol} (Trade #${editingTrade.value.tradeNumber})`,
    tone: 'good',
  };

  isSavingMeta.value = false;
  closeOffcanvas();

  setTimeout(() => {
    if (status.value.tone === 'good') {
      status.value = { text: '', tone: 'muted' };
    }
  }, 4000);
};

// Add an extra execution fill directly into an existing trade
const addFillToExistingTrade = async () => {
  if (!editingTrade.value) return;
  const q = Math.abs(Number(newFillForm.value.qty) || 0);
  const p = Number(newFillForm.value.price) || 0;
  if (q <= 0 || p <= 0) {
    alert('Please enter a valid Quantity and Price for the execution');
    return;
  }

  const dt = editingTrade.value.date || getTodayDateStr();
  const sym = editingTrade.value.symbol;
  const tm = newFillForm.value.time || getCurrentTimeStr();
  const side = newFillForm.value.side === 'B' ? 'B' : 'S';
  const comm = Number(newFillForm.value.comm) || 0;
  const g_amt = q * p;
  const n_amt = side === 'B' ? -(g_amt + comm) : g_amt - comm;
  const timestamp = Date.now();

  const newTx = {
    id: timestamp,
    systemId: 'MANUAL',
    system_date: `${dt}T00:00:00`,
    tr_no: `MAN_${timestamp}`,
    entry_type: 'TRD',
    trd_type: side,
    trade_dt: dt,
    settle_dt: null,
    exec_time: `${dt} ${tm}`,
    symbol: sym,
    qty: q,
    price: p,
    g_amt,
    n_amt,
    comm,
    exch_fee: null,
    sec_fee: null,
    descr: `Manual execution (${side === 'B' ? 'Buy' : 'Sell'})`,
    m_fee1: null,
    m_fee4: null,
  };

  const parsed = parseTradeStatsCsv([newTx]);
  const combined = [...transactions.value, ...parsed];
  combined.sort((a, b) => {
    const dtA = `${a.trade_dt || a.tradeDate || ''} ${a.exec_time || a.execTime || ''}`;
    const dtB = `${b.trade_dt || b.tradeDate || ''} ${b.exec_time || b.execTime || ''}`;
    if (dtA && dtB && dtA !== dtB) return dtA.localeCompare(dtB);
    return (Number(a.id) || 0) - (Number(b.id) || 0);
  });

  await persistJournalTrades(combined.map(toCleanJsonRecord));
  transactions.value = combined;

  // Refresh editing trade reference
  const grouped = groupTransactionsIntoTrades(combined, tradeMetadata.value);
  const updated = grouped.find((tr) => tr.tradeId === editingTrade.value.tradeId);
  if (updated) {
    editingTrade.value = updated;
  }

  showAddFillBox.value = false;
  status.value = {
    text: `Added ${side === 'B' ? 'BUY' : 'SELL'} fill (${q} sh @ $${p}) to ${sym}!`,
    tone: 'good',
  };
};

// Delete an entire trade and its executions
const deleteTrade = async (trade) => {
  if (!trade) return;
  if (!confirm(`Are you sure you want to delete Trade #${trade.tradeNumber} on ${trade.symbol} (${trade.executions.length} fills)?`)) {
    return;
  }

  const txIdsToDelete = new Set(trade.executions.map((e) => String(e.tr_no ?? e.transactionId ?? e.id)));
  const remaining = transactions.value.filter((t) => !txIdsToDelete.has(String(t.tr_no ?? t.transactionId ?? t.id)));

  await persistJournalTrades(remaining.map(toCleanJsonRecord));
  transactions.value = remaining;

  status.value = {
    text: `Deleted Trade #${trade.tradeNumber} (${trade.symbol})`,
    tone: 'muted',
  };

  closeOffcanvas();
};

// Copy all records from Trading Stats into Journaling
const copyFromTradingStats = async () => {
  try {
    status.value = { text: 'Importing records from Trading Stats...', tone: 'muted' };
    const res = await copyTradesFromTradeStatsToJournal();
    if (res.copiedCount === 0) {
      status.value = {
        text: 'All records from Trading Stats already exist in Journaling (0 new records).',
        tone: 'muted',
      };
      return;
    }

    const reloaded = await loadPersistedJournalTrades();
    transactions.value = parseTradeStatsCsv(reloaded);
    tradeMetadata.value = await loadAllJournalMetadata();

    status.value = {
      text: `Successfully imported ${res.copiedCount} trades from Trading Stats into Journaling!`,
      tone: 'good',
    };
  } catch (err) {
    console.error(err);
    status.value = { text: `Error copying from Trading Stats: ${err.message}`, tone: 'bad' };
  }
};

// ---------------------------------------------------------------- Navigation & View state
const mainTab = ref('tables'); // 'tables' | 'stats'
const activeTab = ref('by-date'); // 'by-date' | 'by-symbol'
const expandedDates = ref({});
const searchQuery = ref('');
const selectedSide = ref('ALL');
const selectedDate = ref('ALL');
const selectedSymbol = ref('ALL');
const selectedSession = ref('ALL');
const minOrderQty = ref(0);
const status = ref({ text: '', tone: 'muted' });
const isDragging = ref(false);
const fileInput = ref(null);

const hasData = computed(() => transactions.value.length > 0);

// Format helpers
const num = (v) => Number(v || 0).toLocaleString('en-US');
const fmtMoney = (v, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  const abs = Math.abs(v).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${v < 0 ? '-' : ''}$${abs}`;
};
const fmtSigned = (v, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${v > 0 ? '+' : ''}${fmtMoney(v, digits)}`;
};
const cls = (v) => (v > 0.0001 ? 'pos' : v < -0.0001 ? 'neg' : 'muted');
const fmtExecTime = (raw) => {
  if (raw === null || raw === undefined) return 'null';
  const s = String(raw).trim();
  if (!s || s === 'null') return 'null';
  if (s.includes(' ')) return s.split(' ')[1] || s;
  if (s.includes('T')) return s.split('T')[1] || s;
  return s;
};

// Ingest files (JSON, CSV, XLSX)
const ingestFiles = async (fileList) => {
  const files = [...(fileList || [])];
  if (!files.length) return;

  status.value = {
    text: `Processing ${files.length} file${files.length === 1 ? '' : 's'}...`,
    tone: 'muted',
  };

  const parsedIncomingBatches = [];

  for (const file of files) {
    try {
      const fileNameLower = file.name.toLowerCase();

      if (fileNameLower.endsWith('.xlsx') || fileNameLower.endsWith('.xls')) {
        const buffer = await file.arrayBuffer();
        const workbook = XLSX.read(buffer, { type: 'array' });
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' });
        const batch = parseTradeStatsCsv(jsonData);
        if (batch.length) parsedIncomingBatches.push(...batch);
      } else {
        const text = await file.text();
        const batch = parseTradeStatsCsv(text);
        if (batch.length) parsedIncomingBatches.push(...batch);
      }
    } catch (err) {
      console.error(err);
      status.value = { text: `Could not parse "${file.name}": ${err.message}`, tone: 'bad' };
      return;
    }
  }

  if (!parsedIncomingBatches.length) {
    status.value = {
      text: 'No valid trade records found. Expected JSON array, CSV, or Excel file.',
      tone: 'bad',
    };
    return;
  }

  try {
    const currentList = transactions.value && transactions.value.length ? [...transactions.value] : loadStoredJournalTransactions();
    const { newRecords, duplicateCount, totalIncoming } = deduplicateTrades(currentList, parsedIncomingBatches);

    if (!newRecords.length) {
      status.value = {
        text: `No new trades to add. All ${totalIncoming} record${totalIncoming === 1 ? '' : 's'} already exist in journal.`,
        tone: 'muted',
      };
      return;
    }

    const combined = [...currentList, ...newRecords];
    combined.sort((a, b) => {
      const dtA = `${a.trade_dt || a.tradeDate || ''} ${a.exec_time || a.execTime || ''}`;
      const dtB = `${b.trade_dt || b.tradeDate || ''} ${b.exec_time || b.execTime || ''}`;
      if (dtA && dtB && dtA !== dtB) return dtA.localeCompare(dtB);
      return (Number(a.id) || 0) - (Number(b.id) || 0);
    });

    await persistJournalTrades(combined.map(toCleanJsonRecord));
    transactions.value = combined;
    expandedDates.value = {};

    status.value = {
      text: `Added ${newRecords.length} new trades to journal (${duplicateCount} duplicate${duplicateCount === 1 ? '' : 's'} skipped).`,
      tone: 'good',
    };
  } catch (err) {
    console.error(err);
    status.value = { text: `Error processing journal transactions: ${err.message}`, tone: 'bad' };
  }
};

const onFileChange = async (e) => {
  await ingestFiles(e.target.files);
  e.target.value = '';
};

const onDrop = async (e) => {
  isDragging.value = false;
  await ingestFiles(e.dataTransfer?.files);
};

const allExpanded = computed(() => {
  if (!byDateRows.value.length) return false;
  return byDateRows.value.every((r) => expandedDates.value[r.date]);
});

const toggleExpandAll = () => {
  if (allExpanded.value) {
    expandedDates.value = {};
  } else {
    const next = {};
    byDateRows.value.forEach((r) => {
      next[r.date] = true;
    });
    expandedDates.value = next;
  }
};

const clearData = async () => {
  transactions.value = [];
  try {
    await clearPersistedJournalTrades();
    await clearAllJournalMetadata();
    tradeMetadata.value = {};
  } catch (err) {
    console.error('Failed to clear journal storage:', err);
  }
  expandedDates.value = {};
  searchQuery.value = '';
  selectedSide.value = 'ALL';
  selectedDate.value = 'ALL';
  selectedSymbol.value = 'ALL';
  selectedSession.value = 'ALL';
  minOrderQty.value = 0;
  status.value = { text: 'All journal transactions have been cleared', tone: 'muted' };
};

const confirmClearData = () => {
  if (window.confirm('Are you sure you want to clear all journal records from local storage?')) {
    clearData();
  }
};

// ---------------------------------------------------------------- Column configurations
const defaultDateCols = [
  { key: 'trade_dt', label: 'trade_dt', visible: true, align: 'l', width: 130 },
  { key: 'records', label: 'records', visible: true, align: 'r', width: 85 },
  { key: 'symbols', label: 'symbols', visible: true, align: 'r', width: 80 },
  { key: 'qty', label: 'qty', visible: true, align: 'r', width: 95 },
  { key: 'buyQty', label: 'buy qty', visible: true, align: 'r', width: 95 },
  { key: 'sellQty', label: 'sell qty', visible: true, align: 'r', width: 95 },
  { key: 'buyGross', label: 'buy g_amt', visible: true, align: 'r', width: 110 },
  { key: 'sellGross', label: 'sell g_amt', visible: true, align: 'r', width: 110 },
  { key: 'netDiff', label: 'n_amt diff', visible: true, align: 'r', width: 120 },
  { key: 'fees', label: 'fees', visible: true, align: 'r', width: 90 },
];

const defaultTradeCols = [
  { key: 'setupType', label: 'Setup Type', visible: true, align: 'c', badge: true, width: 115 },
  { key: 'watchedValue', label: 'Watched Val', visible: true, align: 'r', mono: true, width: 105 },
  { key: 'comment', label: 'Comment', visible: true, align: 'l', width: 150 },
  { key: 'images', label: 'Images', visible: true, align: 'c', width: 75 },
  { key: 'actions', label: 'Actions', visible: true, align: 'c', width: 75 },
  { key: 'tr_no', label: 'tr_no', visible: true, align: 'l', mono: true, bold: true, width: 95 },
  { key: 'trd_type', label: 'trd_type', visible: true, align: 'c', badge: true, width: 65 },
  { key: 'trade_dt', label: 'trade_dt', visible: true, align: 'l', mono: true, width: 95 },
  { key: 'exec_time', label: 'exec_time', visible: true, align: 'l', mono: true, bold: true, width: 85 },
  { key: 'symbol', label: 'symbol', visible: true, align: 'l', bold: true, width: 80 },
  { key: 'qty', label: 'qty', visible: true, align: 'r', width: 75 },
  { key: 'price', label: 'price', visible: true, align: 'r', width: 80 },
  { key: 'g_amt', label: 'g_amt', visible: true, align: 'r', mono: true, width: 95 },
  { key: 'n_amt', label: 'n_amt', visible: true, align: 'r', mono: true, width: 95 },
  { key: 'comm', label: 'comm', visible: true, align: 'r', muted: true, width: 70 },
  { key: 'descr', label: 'descr', visible: false, align: 'l', muted: true, width: 140 },
];

const defaultSymbolCols = [
  { key: 'symbol', label: 'Symbol', align: 'l', bold: true, width: 90 },
  { key: 'count', label: 'Transactions', align: 'r', width: 95 },
  { key: 'datesCount', label: 'Active Days', align: 'r', width: 90 },
  { key: 'qty', label: 'Total Shares', align: 'r', width: 95 },
  { key: 'buyQty', label: 'Buy Shares', align: 'r', width: 95 },
  { key: 'sellQty', label: 'Sell Shares', align: 'r', width: 95 },
  { key: 'openQty', label: 'Open Qty', align: 'r', width: 85 },
  { key: 'buyGross', label: 'Buy Gross', align: 'r', width: 105 },
  { key: 'sellGross', label: 'Sell Gross', align: 'r', width: 105 },
  { key: 'netDiff', label: 'Net Diff (Sell - Buy)', align: 'r', width: 135 },
  { key: 'fees', label: 'Fees', align: 'r', width: 90 },
];

const loadSavedCols = (storageKey, defaultCols) => {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return defaultCols.map((c) => ({ ...c }));
    const saved = JSON.parse(raw);
    if (!Array.isArray(saved) || !saved.length) return defaultCols.map((c) => ({ ...c }));

    const defMap = new Map(defaultCols.map((c) => [c.key, c]));
    const result = [];

    for (const item of saved) {
      if (defMap.has(item.key)) {
        const def = defMap.get(item.key);
        let parsedWidth = def.width;
        if (typeof item.width === 'number' && item.width >= 35) {
          parsedWidth = item.width;
        }
        result.push({
          ...def,
          visible: typeof item.visible === 'boolean' ? item.visible : def.visible,
          width: parsedWidth,
        });
        defMap.delete(item.key);
      }
    }
    for (const remaining of defMap.values()) {
      result.push({ ...remaining });
    }
    return result;
  } catch (err) {
    return defaultCols.map((c) => ({ ...c }));
  }
};

const dateCols = ref(loadSavedCols('journaling.cols.date', defaultDateCols));
const tradeCols = ref(loadSavedCols('journaling.cols.trade', defaultTradeCols));
const symbolCols = ref(loadSavedCols('journaling.cols.symbol', defaultSymbolCols));

watch(dateCols, (val) => localStorage.setItem('journaling.cols.date', JSON.stringify(val)), { deep: true });
watch(tradeCols, (val) => localStorage.setItem('journaling.cols.trade', JSON.stringify(val)), { deep: true });
watch(symbolCols, (val) => localStorage.setItem('journaling.cols.symbol', JSON.stringify(val)), { deep: true });

const visibleDateCols = computed(() => dateCols.value.filter((c) => c.visible));
const visibleTradeCols = computed(() => tradeCols.value.filter((c) => c.visible));

const activeColDropdown = ref(null);
const toggleColDropdown = (type) => {
  activeColDropdown.value = activeColDropdown.value === type ? null : type;
};
const closeColDropdown = () => {
  activeColDropdown.value = null;
};
const moveCol = (colsArr, index, direction) => {
  const targetIdx = index + direction;
  if (targetIdx < 0 || targetIdx >= colsArr.length) return;
  const temp = colsArr[index];
  colsArr[index] = colsArr[targetIdx];
  colsArr[targetIdx] = temp;
};
const resetDateCols = () => {
  dateCols.value = defaultDateCols.map((c) => ({ ...c }));
};
const resetTradeCols = () => {
  tradeCols.value = defaultTradeCols.map((c) => ({ ...c }));
};

const activeResizeCol = ref(null);
const startColResize = (e, col) => {
  e.preventDefault();
  activeResizeCol.value = col.key;
  const startX = e.pageX;
  const startWidth = col.width || 80;

  const onMouseMove = (moveEvent) => {
    const diff = moveEvent.pageX - startX;
    col.width = Math.max(35, Math.min(600, startWidth + diff));
  };

  const onMouseUp = () => {
    activeResizeCol.value = null;
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  };

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
};

const resetSingleColWidth = (col, defaultList) => {
  const match = defaultList.find((c) => c.key === col.key);
  if (match) col.width = match.width;
};

onMounted(async () => {
  window.addEventListener('click', closeColDropdown);
  window.addEventListener('paste', onWindowPaste);

  try {
    const persisted = await loadPersistedJournalTrades();
    if (persisted.length > 0 && persisted.length !== transactions.value.length) {
      transactions.value = parseTradeStatsCsv(persisted);
    }
  } catch (err) {
    console.warn('Failed to load journal from IndexedDB:', err);
  }

  try {
    tradeMetadata.value = await loadAllJournalMetadata();
  } catch (err) {
    console.warn('Failed to load journal metadata:', err);
  }

  if (transactions.value.length > 0) {
    status.value = {
      text: `Loaded ${num(transactions.value.length)} journal trades`,
      tone: 'good',
    };
    setTimeout(() => {
      if (status.value.tone === 'good') {
        status.value = { text: '', tone: 'muted' };
      }
    }, 3500);
  }
});

onUnmounted(() => {
  window.removeEventListener('click', closeColDropdown);
  window.removeEventListener('paste', onWindowPaste);
});

// ---------------------------------------------------------------- Filter helpers
const distinctDates = computed(() => {
  const set = new Set();
  transactions.value.forEach((t) => {
    if (t.tradeDate) set.add(t.tradeDate);
  });
  return [...set].sort((a, b) => b.localeCompare(a));
});

const distinctSymbols = computed(() => {
  const counts = new Map();
  transactions.value.forEach((t) => {
    const sym = t.symbol || 'OTHER';
    counts.set(sym, (counts.get(sym) || 0) + 1);
  });
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([symbol, count]) => ({ symbol, count }));
});

const getSession = (t) => {
  const timeStr = String(t.execTime || t.exec_time || '');
  if (!timeStr) return 'REGULAR';
  const match = timeStr.match(/(\d{1,2}):(\d{2})/);
  if (!match) return 'REGULAR';
  const h = parseInt(match[1], 10);
  const m = parseInt(match[2], 10);
  const totalM = h * 60 + m;
  if (totalM < 9 * 60 + 30) return 'PRE';
  if (totalM >= 16 * 60) return 'POST';
  return 'REGULAR';
};

const hasActiveFilters = computed(
  () =>
    searchQuery.value.trim() !== '' ||
    selectedSide.value !== 'ALL' ||
    selectedDate.value !== 'ALL' ||
    selectedSymbol.value !== 'ALL' ||
    selectedSession.value !== 'ALL' ||
    minOrderQty.value > 0,
);

const resetAllFilters = () => {
  searchQuery.value = '';
  selectedSide.value = 'ALL';
  selectedDate.value = 'ALL';
  selectedSymbol.value = 'ALL';
  selectedSession.value = 'ALL';
  minOrderQty.value = 0;
};

const filteredTransactions = computed(() => {
  let list = transactions.value;

  if (selectedSide.value !== 'ALL') {
    list = list.filter((t) => t.tradeType === selectedSide.value);
  }
  if (selectedSymbol.value !== 'ALL') {
    list = list.filter((t) => (t.symbol || 'OTHER') === selectedSymbol.value);
  }
  if (selectedDate.value !== 'ALL') {
    list = list.filter((t) => t.tradeDate === selectedDate.value);
  }
  if (selectedSession.value !== 'ALL') {
    list = list.filter((t) => getSession(t) === selectedSession.value);
  }
  if (minOrderQty.value > 0) {
    list = list.filter((t) => (t.quantity || 0) >= minOrderQty.value);
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase();
    list = list.filter((t) => {
      const symMatch = (t.symbol || '').toLowerCase().includes(q);
      const idMatch = String(t.tr_no || t.transactionId || t.id || '').toLowerCase().includes(q);
      const descMatch = String(t.descr || t.description || '').toLowerCase().includes(q);
      const meta = tradeMetadata.value[t.tradeId] || {};
      const setupMatch = String(meta.setupType || '').toLowerCase().includes(q);
      const watchedMatch = String(meta.watchedValue || '').toLowerCase().includes(q);
      const commentMatch = String(meta.comment || meta.notes || '').toLowerCase().includes(q);
      const notesMatch = String(meta.notes || '').toLowerCase().includes(q);
      return symMatch || idMatch || descMatch || setupMatch || watchedMatch || commentMatch || notesMatch;
    });
  }

  return list;
});

// ---------------------------------------------------------------- Summary Stats
const summary = computed(() => {
  const list = filteredTransactions.value;
  if (!list.length) {
    return {
      count: 0,
      totalQty: 0,
      totalTurnover: 0,
      totalFees: 0,
      avgSize: 0,
      minQty: 0,
      maxQty: 0,
      avgFillsPerDay: '0.0',
      maxDayFills: 0,
      peakDay: '—',
      symbolsCount: 0,
      topSymbol: null,
      peakHour: null,
      feePerShare: 0,
      buyCount: 0,
      sellCount: 0,
    };
  }

  let totalQty = 0;
  let totalTurnover = 0;
  let totalFees = 0;
  let minQty = Infinity;
  let maxQty = -Infinity;
  let buyCount = 0;
  let sellCount = 0;

  const dayCounts = new Map();
  const symbolMap = new Map();
  const hourMap = new Map();

  list.forEach((t) => {
    const q = t.quantity || 0;
    totalQty += q;
    totalTurnover += t.grossAmount || 0;
    totalFees += t.totalFees || 0;

    if (q > 0) {
      if (q < minQty) minQty = q;
      if (q > maxQty) maxQty = q;
    }

    if (t.tradeType === 'B') buyCount++;
    else if (t.tradeType === 'S') sellCount++;

    const d = t.tradeDate || 'Unknown';
    dayCounts.set(d, (dayCounts.get(d) || 0) + 1);

    const s = t.symbol || 'OTHER';
    symbolMap.set(s, (symbolMap.get(s) || 0) + q);

    const timeStr = String(t.execTime || t.exec_time || '');
    if (timeStr) {
      const match = timeStr.match(/(\d{1,2}):/);
      if (match) {
        const h = parseInt(match[1], 10);
        hourMap.set(h, (hourMap.get(h) || 0) + 1);
      }
    }
  });

  const uniqueDays = Math.max(1, dayCounts.size);
  const avgFillsPerDay = (list.length / uniqueDays).toFixed(1);

  let maxDayFills = 0;
  let peakDay = '—';
  dayCounts.forEach((cnt, day) => {
    if (cnt > maxDayFills) {
      maxDayFills = cnt;
      peakDay = day;
    }
  });

  let topSym = null;
  let maxSymQty = 0;
  symbolMap.forEach((qty, sym) => {
    if (qty > maxSymQty) {
      maxSymQty = qty;
      topSym = {
        symbol: sym,
        qty,
        pct: totalQty > 0 ? Math.round((qty / totalQty) * 100) : 0,
      };
    }
  });

  let peakHour = null;
  let maxHourFills = 0;
  hourMap.forEach((cnt, h) => {
    if (cnt > maxHourFills) {
      maxHourFills = cnt;
      const hStr = String(h).padStart(2, '0') + ':00';
      const hNext = String(h + 1).padStart(2, '0') + ':00';
      peakHour = {
        hour: h,
        label: `${hStr}–${hNext}`,
        count: cnt,
        pct: list.length > 0 ? Math.round((cnt / list.length) * 100) : 0,
      };
    }
  });

  const feePerShare = totalQty > 0 ? totalFees / totalQty : 0;

  return {
    count: list.length,
    totalQty,
    totalTurnover,
    totalFees,
    avgSize: list.length > 0 ? Math.round(totalQty / list.length) : 0,
    minQty: minQty === Infinity ? 0 : minQty,
    maxQty: maxQty === -Infinity ? 0 : maxQty,
    avgFillsPerDay,
    maxDayFills,
    peakDay,
    symbolsCount: symbolMap.size,
    topSymbol: topSym,
    peakHour,
    feePerShare,
    buyCount,
    sellCount,
  };
});

// Group by Date rows (each date contains grouped round-trip trades!)
const byDateRows = computed(() => {
  const map = new Map();
  filteredTransactions.value.forEach((t) => {
    const d = t.tradeDate || 'Unknown';
    let g = map.get(d);
    if (!g) {
      g = {
        date: d,
        count: 0,
        qty: 0,
        buyQty: 0,
        sellQty: 0,
        buyGross: 0,
        sellGross: 0,
        buyNet: 0,
        sellNet: 0,
        fees: 0,
        symbols: new Set(),
        transactions: [],
      };
      map.set(d, g);
    }
    g.count += 1;
    g.qty += t.quantity;
    g.fees += t.totalFees;
    g.transactions.push(t);
    if (t.symbol) g.symbols.add(t.symbol);
    if (t.tradeType === 'B') {
      g.buyQty += t.quantity;
      g.buyGross += t.grossAmount;
      g.buyNet += t.netAmount;
    } else if (t.tradeType === 'S') {
      g.sellQty += t.quantity;
      g.sellGross += t.grossAmount;
      g.sellNet += t.netAmount;
    }
  });

  return [...map.values()]
    .sort((a, b) => b.date.localeCompare(a.date))
    .map((g) => ({
      ...g,
      symbolsCount: g.symbols.size,
      netDiff: g.sellNet - g.buyNet,
      trades: groupTransactionsIntoTrades(g.transactions, tradeMetadata.value),
    }));
});

// Group by Symbol rows
const bySymbolRows = computed(() => {
  const map = new Map();
  filteredTransactions.value.forEach((t) => {
    const sym = t.symbol || 'OTHER';
    let g = map.get(sym);
    if (!g) {
      g = {
        symbol: sym,
        count: 0,
        qty: 0,
        buyQty: 0,
        sellQty: 0,
        buyGross: 0,
        sellGross: 0,
        buyNet: 0,
        sellNet: 0,
        fees: 0,
        dates: new Set(),
      };
      map.set(sym, g);
    }
    g.count += 1;
    g.qty += t.quantity;
    g.fees += t.totalFees;
    if (t.tradeDate) g.dates.add(t.tradeDate);
    if (t.tradeType === 'B') {
      g.buyQty += t.quantity;
      g.buyGross += t.grossAmount;
      g.buyNet += t.netAmount;
    } else if (t.tradeType === 'S') {
      g.sellQty += t.quantity;
      g.sellGross += t.grossAmount;
      g.sellNet += t.netAmount;
    }
  });

  return [...map.values()]
    .sort((a, b) => b.qty - a.qty)
    .map((g) => ({
      ...g,
      datesCount: g.dates.size,
      openQty: g.buyQty - g.sellQty,
      netDiff: g.sellNet - g.buyNet,
    }));
});

// Charts data
const dailyChartData = computed(() => {
  return [...byDateRows.value]
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-14)
    .map((r) => ({
      date: r.date,
      count: r.count,
      qty: r.qty,
      buyQty: r.buyQty,
      sellQty: r.sellQty,
      netDiff: r.netDiff,
    }));
});

const maxDailyQty = computed(() => {
  if (!dailyChartData.value.length) return 1;
  return Math.max(...dailyChartData.value.map((d) => Math.max(d.buyQty, d.sellQty)), 1);
});

// ---------------------------------------------------------------- Export
const isExportingExcel = ref(false);
const isExportingPdf = ref(false);

const formatTradeCellValue = (t, colKey) => {
  switch (colKey) {
    case 'setupType': {
      const meta = tradeMetadata.value[t.tradeId] || {};
      return meta.setupType || t.setupType || '';
    }
    case 'watchedValue': {
      const meta = tradeMetadata.value[t.tradeId] || {};
      return meta.watchedValue || t.watchedValue || '';
    }
    case 'comment': {
      const meta = tradeMetadata.value[t.tradeId] || {};
      return meta.comment || meta.notes || t.comment || t.notes || '';
    }
    case 'images': {
      const meta = tradeMetadata.value[t.tradeId] || {};
      const count = meta.images?.length || t.images?.length || 0;
      return count > 0 ? `${count} imgs` : '';
    }
    case 'actions':
      return '';
    case 'trd_type':
      return t.trd_type ?? 'null';
    case 'qty':
      return t.qty != null ? num(t.qty) : 'null';
    case 'price':
      return t.price != null ? '$' + Number(t.price).toFixed(4).replace(/0+$/, '').replace(/\.$/, '') : 'null';
    case 'g_amt':
      return t.g_amt != null ? fmtMoney(t.g_amt) : 'null';
    case 'n_amt':
      return t.n_amt != null ? fmtMoney(t.n_amt, 4) : 'null';
    case 'exec_time':
      return t.exec_time != null ? fmtExecTime(t.exec_time) : 'null';
    case 'comm':
      return t.comm != null ? fmtMoney(t.comm, 4) : 'null';
    default:
      return t[colKey] != null ? String(t[colKey]) : 'null';
  }
};

const formatDateCellValue = (r, colKey) => {
  switch (colKey) {
    case 'trade_dt':
      return r.date || '—';
    case 'records':
      return num(r.count);
    case 'symbols':
      return String(r.symbolsCount);
    case 'qty':
      return num(r.qty);
    case 'buyQty':
      return num(r.buyQty);
    case 'sellQty':
      return num(r.sellQty);
    case 'buyGross':
      return fmtMoney(r.buyGross);
    case 'sellGross':
      return fmtMoney(r.sellGross);
    case 'netDiff':
      return fmtSigned(r.netDiff);
    case 'fees':
      return fmtMoney(r.fees, 4);
    default:
      return r[colKey] != null ? String(r[colKey]) : '—';
  }
};

const exportExcel = () => {
  if (!byDateRows.value.length) return;
  const wb = XLSX.utils.book_new();
  const tradeHeaders = visibleTradeCols.value.map((c) => c.label);
  const allTradesData = [];
  byDateRows.value.forEach((r) => {
    r.transactions.forEach((t) => {
      allTradesData.push(visibleTradeCols.value.map((c) => formatTradeCellValue(t, c.key)));
    });
  });

  const wsTrades = XLSX.utils.aoa_to_sheet([tradeHeaders, ...allTradesData]);
  XLSX.utils.book_append_sheet(wb, wsTrades, 'Journal Transactions');

  const dateHeaders = visibleDateCols.value.map((c) => c.label);
  const allDaysData = byDateRows.value.map((r) => visibleDateCols.value.map((c) => formatDateCellValue(r, c.key)));
  const wsDays = XLSX.utils.aoa_to_sheet([dateHeaders, ...allDaysData]);
  XLSX.utils.book_append_sheet(wb, wsDays, 'Daily Summaries');

  XLSX.writeFile(wb, `Trade_Journal_${getTodayDateStr()}.xlsx`);
};

const exportPdf = () => {
  if (!byDateRows.value.length) return;
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
  doc.setFontSize(16);
  doc.text('Trading Journal & Performance Report', 40, 40);

  const headers = [visibleTradeCols.value.map((c) => c.label)];
  const body = [];
  byDateRows.value.forEach((r) => {
    r.transactions.forEach((t) => {
      body.push(visibleTradeCols.value.map((c) => formatTradeCellValue(t, c.key)));
    });
  });

  autoTable(doc, {
    head: headers,
    body: body,
    startY: 60,
    styles: { fontSize: 8 },
  });

  doc.save(`Trade_Journal_${getTodayDateStr()}.pdf`);
};
</script>

<template>
  <div class="journal-view" @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="onDrop">
    <!-- Hidden file input for file imports -->
    <input
      ref="fileInput"
      type="file"
      id="journalFileInput"
      accept=".json,application/json,.csv,text/csv,text/plain,.xlsx,.xls"
      multiple
      class="hidden-file-input"
      @change="onFileChange"
    />

    <!-- Floating Top-Right Action Buttons -->
    <div class="floating-actions">
      <button
        class="floating-btn log-trade-floating-btn"
        @click="openCreateOffcanvas"
        title="Log a new trade manually"
      >
        <Plus :size="18" />
        <span class="btn-text">Log Trade</span>
      </button>
      <button
        v-if="hasData"
        class="floating-btn clear-btn"
        @click="confirmClearData"
        title="Clear all stored journal records"
      >
        <RotateCcw :size="16" />
      </button>
      <label
        for="journalFileInput"
        class="floating-btn import-btn"
        title="Import JSON, CSV, or Excel trades"
      >
        <UploadCloud :size="18" />
      </label>
    </div>

    <!-- Floating status toast message -->
    <div v-if="status.text" class="floating-status" :class="status.tone">
      <span>{{ status.text }}</span>
      <button class="status-close" @click="status.text = ''" title="Dismiss">
        <X :size="12" />
      </button>
    </div>

    <div class="wrap">
      <!-- ================= Page Header Bar ================= -->
      <header class="journal-header glass">
        <div class="jh-left">
          <div class="jh-title-row">
            <BookOpen :size="24" class="jh-icon" />
            <h1 class="jh-title">Trade Journaling</h1>
            <span class="jh-badge">Manual Log &amp; Lifecycle</span>
          </div>
          <p class="jh-desc">
            Log setups, key levels, psychology, and screenshots. Follows exact round-trip position grouping and anomaly detection.
          </p>
        </div>

        <div class="jh-actions">
          <button class="btn primary log-trade-hero-btn" @click="openCreateOffcanvas">
            <Plus :size="16" />
            <span>+ Log Trade</span>
          </button>
          <button class="btn ghost small" @click="copyFromTradingStats" title="Import past trades from Trading Stats into Journal">
            <Copy :size="13" />
            <span>Sync from Trade Stats</span>
          </button>
          <label for="journalFileInput" class="btn ghost small" title="Import trades from file">
            <FolderDown :size="13" />
            <span>Import File</span>
          </label>
          <button v-if="hasData" class="btn ghost small" @click="confirmClearData" title="Clear journal">
            <RotateCcw :size="13" />
            <span>Clear</span>
          </button>
        </div>
      </header>

      <!-- ================= Empty State ================= -->
      <section v-if="!hasData" class="empty glass">
        <div class="empty-journal-card">
          <div class="empty-icon-wrap">
            <BookOpen :size="52" class="empty-icon" />
          </div>
          <h2>Your Trade Journal is Empty</h2>
          <p>
            Start logging your scalps and day trades manually to track your setups, watched trigger levels, execution discipline, and screenshots.
          </p>
          <div class="empty-actions">
            <button class="btn primary large-btn" @click="openCreateOffcanvas">
              <Plus :size="18" />
              <span>Log Your First Trade</span>
            </button>
            <button class="btn ghost" @click="copyFromTradingStats">
              <Copy :size="15" />
              <span>Pull Records from Trade Stats</span>
            </button>
          </div>
        </div>
      </section>

      <!-- ================= Active Journal Area ================= -->
      <template v-else>
        <!-- 1. Universal Filters Bar -->
        <div class="universal-filter-bar glass">
          <div class="uf-row">
            <!-- Search -->
            <div class="uf-item uf-search">
              <Search :size="14" class="uf-icon" />
              <input
                type="text"
                v-model="searchQuery"
                placeholder="Search symbol, setup, level, comment, notes..."
                class="uf-input"
              />
              <button v-if="searchQuery" class="uf-clear-input" @click="searchQuery = ''">
                <X :size="12" />
              </button>
            </div>

            <!-- Side Filter -->
            <div class="uf-item">
              <span class="uf-label">Side:</span>
              <select v-model="selectedSide" class="uf-select">
                <option value="ALL">All Sides</option>
                <option value="B">Buy (Long)</option>
                <option value="S">Sell (Short)</option>
              </select>
            </div>

            <!-- Symbol Filter -->
            <div class="uf-item">
              <span class="uf-label">Symbol:</span>
              <select v-model="selectedSymbol" class="uf-select">
                <option value="ALL">All Symbols ({{ distinctSymbols.length }})</option>
                <option v-for="s in distinctSymbols" :key="s.symbol" :value="s.symbol">
                  {{ s.symbol }} ({{ s.count }})
                </option>
              </select>
            </div>

            <!-- Date Filter -->
            <div class="uf-item">
              <span class="uf-label">Date:</span>
              <select v-model="selectedDate" class="uf-select">
                <option value="ALL">All Dates ({{ distinctDates.length }})</option>
                <option v-for="d in distinctDates" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>

            <!-- Session Filter -->
            <div class="uf-item">
              <span class="uf-label">Session:</span>
              <select v-model="selectedSession" class="uf-select">
                <option value="ALL">All Sessions</option>
                <option value="REGULAR">Regular Market (9:30–16:00)</option>
                <option value="PRE">Pre-market (&lt;9:30)</option>
                <option value="POST">After-hours (&ge;16:00)</option>
              </select>
            </div>

            <!-- Reset Filter Button -->
            <button
              v-if="hasActiveFilters"
              class="btn ghost small uf-reset-btn"
              @click="resetAllFilters"
              title="Reset all filters"
            >
              <RotateCcw :size="12" />
              <span>Reset</span>
            </button>
          </div>

          <div class="uf-meta">
            <span class="uf-counter">
              Showing <b>{{ num(filteredTransactions.length) }}</b> of <b>{{ num(transactions.length) }}</b> transactions
            </span>
            <span v-if="hasActiveFilters" class="active-badge">Filters Active</span>
            <span class="storage-badge" title="Preserved permanently in IndexedDB + LocalStorage">
              <span class="storage-dot"></span> Journal Storage
            </span>
          </div>
        </div>

        <!-- 2. Main Navigation Tabs -->
        <div class="main-tabs-nav">
          <button
            class="main-tab-btn"
            :class="{ active: mainTab === 'tables' }"
            @click="mainTab = 'tables'"
          >
            <Table :size="15" />
            <span>Journal Table</span>
            <span class="tab-badge">{{ num(filteredTransactions.length) }}</span>
          </button>

          <button
            class="main-tab-btn"
            :class="{ active: mainTab === 'stats' }"
            @click="mainTab = 'stats'"
          >
            <BarChart3 :size="15" />
            <span>Statistics &amp; Charts</span>
          </button>
        </div>

        <!-- ================= Tab 1: Tables ================= -->
        <div v-if="mainTab === 'tables'" class="main-tab-content">
          <div class="toolbar glass">
            <div class="tabs">
              <button :class="{ on: activeTab === 'by-date' }" @click="activeTab = 'by-date'">
                By Date <em>{{ byDateRows.length }}</em>
              </button>
              <button :class="{ on: activeTab === 'by-symbol' }" @click="activeTab = 'by-symbol'">
                By Symbol <em>{{ bySymbolRows.length }}</em>
              </button>
            </div>

            <div class="table-actions">
              <button
                v-if="activeTab === 'by-date'"
                class="btn ghost small"
                @click="toggleExpandAll"
                :title="allExpanded ? 'Collapse all dates' : 'Expand all dates'"
              >
                <Layers :size="13" />
                <span>{{ allExpanded ? 'Collapse All' : 'Expand All' }}</span>
              </button>

              <button class="btn primary small" @click="openCreateOffcanvas">
                <Plus :size="13" />
                <span>+ Log Trade</span>
              </button>

              <button class="btn ghost small" @click="exportExcel" title="Export Excel">
                <FileSpreadsheet :size="13" />
                <span>Export Excel</span>
              </button>

              <button class="btn ghost small" @click="exportPdf" title="Export PDF">
                <FileDown :size="13" />
                <span>Export PDF</span>
              </button>
            </div>
          </div>

          <!-- By Date Table -->
          <section v-if="activeTab === 'by-date'" class="panel glass">
            <div class="tbl-wrap">
              <table class="tbl">
                <thead>
                  <tr>
                    <th
                      v-for="col in visibleDateCols"
                      :key="col.key"
                      :class="col.align === 'l' ? 'l' : ''"
                      :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                    >
                      <span class="th-content">{{ col.label }}</span>
                      <span
                        class="col-resizer"
                        @mousedown.stop.prevent="startColResize($event, col)"
                        @dblclick.stop="resetSingleColWidth(col, defaultDateCols)"
                        title="Drag to resize column"
                      ></span>
                    </th>
                    <th class="spacer-col"></th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="r in byDateRows" :key="r.date">
                    <tr
                      class="clickable-row"
                      :class="{ open: expandedDates[r.date] }"
                      @click="expandedDates[r.date] = !expandedDates[r.date]"
                    >
                      <td
                        v-for="col in visibleDateCols"
                        :key="col.key"
                        :class="col.align === 'l' ? 'l' : ''"
                        :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                      >
                        <template v-if="col.key === 'trade_dt'">
                          <span class="bold">
                            <ChevronDown v-if="expandedDates[r.date]" :size="14" class="chev" />
                            <ChevronRight v-else :size="14" class="chev" />
                            {{ r.date }}
                          </span>
                        </template>
                        <template v-else-if="col.key === 'records'">{{ num(r.count) }}</template>
                        <template v-else-if="col.key === 'symbols'">{{ r.symbolsCount }}</template>
                        <template v-else-if="col.key === 'qty'">{{ num(r.qty) }}</template>
                        <template v-else-if="col.key === 'buyQty'">{{ num(r.buyQty) }}</template>
                        <template v-else-if="col.key === 'sellQty'">{{ num(r.sellQty) }}</template>
                        <template v-else-if="col.key === 'buyGross'">{{ fmtMoney(r.buyGross) }}</template>
                        <template v-else-if="col.key === 'sellGross'">{{ fmtMoney(r.sellGross) }}</template>
                        <template v-else-if="col.key === 'netDiff'">
                          <span :class="cls(r.netDiff)"><b>{{ fmtSigned(r.netDiff) }}</b></span>
                        </template>
                        <template v-else-if="col.key === 'fees'">
                          <span class="muted">{{ fmtMoney(r.fees, 4) }}</span>
                        </template>
                      </td>
                      <td class="spacer-col"></td>
                    </tr>

                    <!-- Expanded rows: Grouped Trades with Borders & Anomaly Detection -->
                    <tr v-if="expandedDates[r.date]" class="detail-row">
                      <td :colspan="visibleDateCols.length + 1">
                        <div class="inner-wrap">
                          <div class="inner-header">
                            <div class="inner-title-left">
                              <span class="bold">Trades &amp; Executions for {{ r.date }}</span>
                              <span class="muted">
                                ({{ r.trades.length }} trade{{ r.trades.length === 1 ? '' : 's' }} · {{ r.transactions.length }} fills)
                              </span>
                            </div>
                            <div class="inner-title-right">
                              <button class="btn primary small" @click="openCreateOffcanvas">
                                <Plus :size="12" /> Log Trade on this Day
                              </button>
                            </div>
                          </div>

                          <!-- Trades List -->
                          <div class="trades-cards-stack">
                            <div
                              v-for="trade in r.trades"
                              :key="trade.tradeId"
                              class="trade-card-wrapper"
                              :class="{ 'has-anomaly': trade.hasAnomaly }"
                            >
                              <!-- Trade Card Header -->
                              <div class="trade-card-header">
                                <div class="trade-header-meta">
                                  <span class="trade-num-badge">Trade #{{ trade.tradeNumber }}</span>
                                  <span class="trade-symbol-tag">{{ trade.symbol }}</span>
                                  <span class="trade-dir-tag" :class="trade.direction.toLowerCase()">
                                    {{ trade.direction }}
                                  </span>
                                  <span class="trade-status-tag" :class="trade.status.toLowerCase()">
                                    {{ trade.status === 'CLOSED' ? 'Flat' : `${trade.openQty} sh open` }}
                                  </span>
                                  <span v-if="trade.hasAnomaly" class="anomaly-pill" title="Contains secondary buy / averaging down">
                                    <AlertTriangle :size="12" />
                                    <span>Avg / Extra Buy</span>
                                  </span>
                                </div>

                                <div class="trade-header-tactics">
                                  <!-- Setup Type Badge -->
                                  <span
                                    v-if="trade.setupType"
                                    class="setup-pill"
                                    :class="getSetupBadgeClass(trade.setupType)"
                                    @click.stop="openEditOffcanvas(trade)"
                                    title="Click to edit setup"
                                  >
                                    {{ trade.setupType }}
                                  </span>
                                  <span
                                    v-else
                                    class="setup-pill empty"
                                    @click.stop="openEditOffcanvas(trade)"
                                    title="Add setup type"
                                  >
                                    + Setup
                                  </span>

                                  <!-- Watched Level Badge -->
                                  <span
                                    v-if="trade.watchedValue"
                                    class="watched-pill"
                                    @click.stop="openEditOffcanvas(trade)"
                                    :title="'Watched key level: ' + trade.watchedValue"
                                  >
                                    <Eye :size="12" />
                                    <span>{{ trade.watchedValue }}</span>
                                  </span>
                                  <span
                                    v-else
                                    class="watched-pill empty"
                                    @click.stop="openEditOffcanvas(trade)"
                                    title="Add watched level"
                                  >
                                    <Eye :size="12" /> + Level
                                  </span>

                                  <!-- Comment Badge / Button -->
                                  <button
                                    v-if="trade.comment"
                                    class="comment-pill-btn"
                                    @click.stop="openEditOffcanvas(trade)"
                                    :title="'Comment: ' + trade.comment"
                                  >
                                    <MessageSquare :size="12" />
                                    <span class="comment-pill-text">{{ trade.comment }}</span>
                                  </button>
                                  <button
                                    v-else
                                    class="comment-pill-btn empty"
                                    @click.stop="openEditOffcanvas(trade)"
                                    title="Add comment"
                                  >
                                    <MessageSquare :size="12" />
                                    <span>+ Comment</span>
                                  </button>

                                  <!-- Image Gallery Button -->
                                  <button
                                    v-if="trade.images && trade.images.length"
                                    class="images-pill-btn"
                                    @click.stop="openTradeImages(trade)"
                                    title="View screenshots"
                                  >
                                    <Camera :size="12" />
                                    <span>{{ trade.images.length }} screenshot{{ trade.images.length === 1 ? '' : 's' }}</span>
                                  </button>
                                  <button
                                    v-else
                                    class="images-pill-btn empty"
                                    @click.stop="openEditOffcanvas(trade)"
                                    title="Attach chart screenshot"
                                  >
                                    <Camera :size="12" />
                                    <span>+ Image</span>
                                  </button>
                                </div>

                                <div class="trade-header-actions">
                                  <div class="trade-pnl-box">
                                    <span class="pnl-val" :class="cls(trade.netPnL)">{{ fmtSigned(trade.netPnL) }}</span>
                                    <span class="pnl-shares muted font-mono">{{ num(trade.totalEntryQty) }} sh</span>
                                  </div>
                                  <button
                                    class="btn-edit-trade"
                                    @click.stop="openEditOffcanvas(trade)"
                                    title="Edit setup, comment, screenshots, or add exit fill"
                                  >
                                    <Edit3 :size="13" />
                                    <span>Edit</span>
                                  </button>
                                </div>
                              </div>

                              <!-- Executions Table -->
                              <div class="trade-table-wrap">
                                <table class="tbl inner">
                                  <thead>
                                    <tr>
                                      <th
                                        v-for="col in visibleTradeCols"
                                        :key="col.key"
                                        :class="col.align"
                                        :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                                      >
                                        <span class="th-content">{{ col.label }}</span>
                                        <span
                                          class="col-resizer"
                                          @mousedown.stop.prevent="startColResize($event, col)"
                                          title="Drag to resize column"
                                        ></span>
                                      </th>
                                      <th class="spacer-col"></th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    <tr
                                      v-for="(t, idx) in trade.executions"
                                      :key="t.id ?? idx"
                                      :class="{ 'anomaly-row': t.isAnomaly }"
                                    >
                                      <td
                                        v-for="col in visibleTradeCols"
                                        :key="col.key"
                                        :class="[
                                          col.align === 'c' ? 'c' : col.align === 'r' ? 'r' : 'l',
                                          col.mono ? 'font-mono' : '',
                                          col.bold ? 'bold' : '',
                                        ]"
                                        :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                                        :title="String(t[col.key] ?? '')"
                                      >
                                        <!-- Setup Type -->
                                        <template v-if="col.key === 'setupType'">
                                          <span
                                            v-if="trade.setupType"
                                            class="setup-badge"
                                            :class="getSetupBadgeClass(trade.setupType)"
                                            @click.stop="openEditOffcanvas(trade)"
                                          >
                                            {{ trade.setupType }}
                                          </span>
                                          <span v-else class="muted null-val">—</span>
                                        </template>

                                        <!-- Watched Value -->
                                        <template v-else-if="col.key === 'watchedValue'">
                                          <span
                                            v-if="trade.watchedValue"
                                            class="watched-val-text font-mono"
                                            @click.stop="openEditOffcanvas(trade)"
                                          >
                                            {{ trade.watchedValue }}
                                          </span>
                                          <span v-else class="muted null-val">—</span>
                                        </template>

                                        <!-- Comment -->
                                        <template v-else-if="col.key === 'comment'">
                                          <span
                                            v-if="trade.comment"
                                            class="comment-cell-text"
                                            :title="trade.comment"
                                            @click.stop="openEditOffcanvas(trade)"
                                          >
                                            <MessageSquare :size="11" class="comment-icon" />
                                            <span class="comment-text-truncate">{{ trade.comment }}</span>
                                          </span>
                                          <span v-else class="muted null-val" @click.stop="openEditOffcanvas(trade)">—</span>
                                        </template>

                                        <!-- Images -->
                                        <template v-else-if="col.key === 'images'">
                                          <button
                                            v-if="trade.images && trade.images.length"
                                            class="col-img-btn"
                                            @click.stop="openTradeImages(trade)"
                                            title="View screenshots"
                                          >
                                            <Camera :size="12" /> {{ trade.images.length }}
                                          </button>
                                          <button
                                            v-else
                                            class="col-img-btn empty"
                                            @click.stop="openEditOffcanvas(trade)"
                                            title="Add screenshot"
                                          >
                                            <Camera :size="12" /> +
                                          </button>
                                        </template>

                                        <!-- Actions -->
                                        <template v-else-if="col.key === 'actions'">
                                          <button
                                            class="col-edit-btn"
                                            @click.stop="openEditOffcanvas(trade)"
                                            title="Edit trade setup & notes"
                                          >
                                            <Edit3 :size="13" />
                                          </button>
                                        </template>

                                        <!-- Trade Type / Side -->
                                        <template v-else-if="col.key === 'trd_type'">
                                          <div class="side-cell">
                                            <span v-if="t.trd_type" class="badge" :class="t.trd_type === 'B' ? 'buy' : 'sell'">
                                              {{ t.trd_type }}
                                            </span>
                                            <span v-else class="null-val">null</span>
                                            <span v-if="t.isAnomaly" class="anomaly-label-tag" title="Anomaly: secondary buy / avg down">
                                              AVG
                                            </span>
                                          </div>
                                        </template>

                                        <!-- Quantity -->
                                        <template v-else-if="col.key === 'qty'">
                                          <span :class="t.qty != null ? '' : 'null-val'">
                                            {{ t.qty != null ? num(t.qty) : 'null' }}
                                          </span>
                                        </template>

                                        <!-- Price -->
                                        <template v-else-if="col.key === 'price'">
                                          <span :class="t.price != null ? '' : 'null-val'">
                                            {{ t.price != null ? ('$' + Number(t.price).toFixed(4).replace(/0+$/, '').replace(/\.$/, '')) : 'null' }}
                                          </span>
                                        </template>

                                        <!-- Gross Amount -->
                                        <template v-else-if="col.key === 'g_amt'">
                                          <span :class="t.g_amt != null ? '' : 'null-val'">
                                            {{ t.g_amt != null ? fmtMoney(t.g_amt) : 'null' }}
                                          </span>
                                        </template>

                                        <!-- Net Amount -->
                                        <template v-else-if="col.key === 'n_amt'">
                                          <span :class="t.n_amt != null ? '' : 'null-val'">
                                            {{ t.n_amt != null ? fmtMoney(t.n_amt, 4) : 'null' }}
                                          </span>
                                        </template>

                                        <!-- Exec Time -->
                                        <template v-else-if="col.key === 'exec_time'">
                                          <span :class="t.exec_time != null ? '' : 'null-val'">
                                            {{ t.exec_time != null ? fmtExecTime(t.exec_time) : 'null' }}
                                          </span>
                                        </template>

                                        <!-- Default Column -->
                                        <template v-else>
                                          <span :class="t[col.key] != null ? (col.muted ? 'muted' : '') : 'null-val'">
                                            {{ t[col.key] != null ? t[col.key] : 'null' }}
                                          </span>
                                        </template>
                                      </td>
                                      <td class="spacer-col"></td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </section>

          <!-- By Symbol Table -->
          <section v-else-if="activeTab === 'by-symbol'" class="panel glass">
            <div class="tbl-wrap">
              <table class="tbl">
                <thead>
                  <tr>
                    <th
                      v-for="col in symbolCols"
                      :key="col.key"
                      :class="col.align === 'l' ? 'l' : ''"
                      :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                    >
                      <span class="th-content">{{ col.label }}</span>
                    </th>
                    <th class="spacer-col"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in bySymbolRows" :key="r.symbol">
                    <td
                      v-for="col in symbolCols"
                      :key="col.key"
                      :class="[
                        col.align === 'l' ? 'l' : '',
                        col.bold ? 'bold' : '',
                        col.key === 'openQty' ? (r.openQty !== 0 ? 'amber' : 'muted') : '',
                        col.key === 'netDiff' ? cls(r.netDiff) : '',
                      ]"
                    >
                      <template v-if="col.key === 'symbol'">{{ r.symbol }}</template>
                      <template v-else-if="col.key === 'count'">{{ num(r.count) }}</template>
                      <template v-else-if="col.key === 'datesCount'">{{ r.datesCount }}</template>
                      <template v-else-if="col.key === 'qty'">{{ num(r.qty) }}</template>
                      <template v-else-if="col.key === 'buyQty'">{{ num(r.buyQty) }}</template>
                      <template v-else-if="col.key === 'sellQty'">{{ num(r.sellQty) }}</template>
                      <template v-else-if="col.key === 'openQty'">{{ num(r.openQty) }}</template>
                      <template v-else-if="col.key === 'buyGross'">{{ fmtMoney(r.buyGross) }}</template>
                      <template v-else-if="col.key === 'sellGross'">{{ fmtMoney(r.sellGross) }}</template>
                      <template v-else-if="col.key === 'netDiff'"><b>{{ fmtSigned(r.netDiff) }}</b></template>
                      <template v-else-if="col.key === 'fees'">{{ fmtMoney(r.fees, 4) }}</template>
                    </td>
                    <td class="spacer-col"></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <!-- ================= Tab 2: Statistics & Charts ================= -->
        <div v-else-if="mainTab === 'stats'" class="main-tab-content stats-view-container">
          <section class="kpis">
            <div class="kpi glass">
              <span class="k-label">Volume &amp; Fills</span>
              <strong class="k-value">{{ num(summary.totalQty) }} <small class="unit">sh</small></strong>
              <span class="k-sub">{{ num(summary.count) }} fills ({{ summary.buyCount }}B / {{ summary.sellCount }}S)</span>
            </div>

            <div class="kpi glass">
              <span class="k-label">Daily Pace</span>
              <strong class="k-value">{{ summary.avgFillsPerDay }} <small class="unit">fills/day</small></strong>
              <span class="k-sub">Peak: {{ summary.maxDayFills }} fills ({{ summary.peakDay }})</span>
            </div>

            <div class="kpi glass">
              <span class="k-label">Avg Order Size</span>
              <strong class="k-value">{{ num(summary.avgSize) }} <small class="unit">sh</small></strong>
              <span class="k-sub">Range: {{ num(summary.minQty) }} – {{ num(summary.maxQty) }} sh</span>
            </div>

            <div class="kpi glass">
              <span class="k-label">Top Symbol Focus</span>
              <strong class="k-value font-mono">
                {{ summary.topSymbol ? summary.topSymbol.symbol : '—' }}
                <small v-if="summary.topSymbol" class="unit">{{ summary.topSymbol.pct }}%</small>
              </strong>
              <span class="k-sub">{{ summary.symbolsCount }} unique ticker{{ summary.symbolsCount === 1 ? '' : 's' }}</span>
            </div>

            <div class="kpi glass">
              <span class="k-label">Peak Time Window</span>
              <strong class="k-value font-mono">{{ summary.peakHour ? summary.peakHour.label : '—' }}</strong>
              <span class="k-sub">{{ summary.peakHour ? summary.peakHour.pct + '% of fills' : 'Based on exec_time' }}</span>
            </div>

            <div class="kpi glass hero">
              <span class="k-label">Gross &amp; Fees</span>
              <strong class="k-value">{{ fmtMoney(summary.totalFees, 2) }}</strong>
              <span class="k-sub">{{ fmtMoney(summary.totalTurnover) }} gross turnover</span>
            </div>
          </section>

          <!-- Interactive Charts -->
          <section class="charts-grid">
            <div class="chart-card glass">
              <div class="chart-header">
                <div class="chart-title">
                  <TrendingUp :size="16" class="chart-icon" />
                  <strong>Daily Journal Volume &amp; Shares</strong>
                </div>
              </div>
              <div class="chart-body">
                <div v-if="!dailyChartData.length" class="chart-empty">No daily data for selected filters</div>
                <div v-else class="bar-chart-container">
                  <div v-for="d in dailyChartData" :key="d.date" class="bar-group">
                    <div class="bars-pair">
                      <div
                        class="chart-bar buy-bar"
                        :style="{ height: Math.max(4, Math.round((d.buyQty / maxDailyQty) * 150)) + 'px' }"
                        :title="d.date + ': Buy ' + num(d.buyQty) + ' sh'"
                      ></div>
                      <div
                        class="chart-bar sell-bar"
                        :style="{ height: Math.max(4, Math.round((d.sellQty / maxDailyQty) * 150)) + 'px' }"
                        :title="d.date + ': Sell ' + num(d.sellQty) + ' sh'"
                      ></div>
                    </div>
                    <span class="bar-date-label">{{ d.date.slice(5) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="chart-card glass">
              <div class="chart-header">
                <div class="chart-title">
                  <Activity :size="16" class="chart-icon" />
                  <strong>Symbol Breakdown</strong>
                </div>
              </div>
              <div class="chart-body">
                <div class="symbol-bars-list">
                  <div v-for="s in bySymbolRows.slice(0, 6)" :key="s.symbol" class="sym-row">
                    <div class="sym-meta">
                      <b class="sym-ticker font-mono">{{ s.symbol }}</b>
                      <span class="sym-stats muted">{{ num(s.qty) }} sh · {{ s.count }} fills</span>
                      <span class="sym-diff" :class="cls(s.netDiff)">{{ fmtSigned(s.netDiff) }}</span>
                    </div>
                    <div class="sym-track">
                      <div
                        class="sym-fill"
                        :style="{ width: Math.round((s.qty / (summary.totalQty || 1)) * 100) + '%' }"
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </template>
    </div>

    <!-- Offcanvas Backdrop Overlay -->
    <div v-if="isOffcanvasOpen" class="offcanvas-backdrop" @click="closeOffcanvas"></div>

    <!-- Offcanvas Drawer (Handles both Logging New Trades & Editing Existing Trades) -->
    <aside class="offcanvas-drawer" :class="{ open: isOffcanvasOpen }">
      <div class="offcanvas-content">
        <!-- Drawer Header -->
        <div class="offcanvas-header">
          <div class="offcanvas-title-group">
            <div class="offcanvas-badge-row">
              <span class="offcanvas-tag">
                {{ offcanvasMode === 'create' ? '+ Log New Trade' : `Trade #${editingTrade?.tradeNumber}` }}
              </span>
              <span v-if="offcanvasMode === 'edit'" class="offcanvas-symbol font-mono">
                {{ editingTrade?.symbol }}
              </span>
              <span
                class="offcanvas-dir-badge"
                :class="(offcanvasMode === 'create' ? createForm.direction : editingTrade?.direction || 'LONG').toLowerCase()"
              >
                {{ offcanvasMode === 'create' ? createForm.direction : editingTrade?.direction }}
              </span>
            </div>
            <div v-if="offcanvasMode === 'edit' && editingTrade" class="offcanvas-sub">
              <span>{{ editingTrade.date }}</span>
              <span>·</span>
              <span>{{ editingTrade.entryTime }} → {{ editingTrade.exitTime || 'Open' }}</span>
              <span>·</span>
              <span :class="cls(editingTrade.netPnL)">{{ fmtSigned(editingTrade.netPnL) }}</span>
            </div>
            <div v-else class="offcanvas-sub">
              <span>Record your setup, entries, exits, psychology, and screenshots</span>
            </div>
          </div>
          <button class="offcanvas-close-btn" @click="closeOffcanvas" title="Close">
            <X :size="18" />
          </button>
        </div>

        <!-- Drawer Body -->
        <div class="offcanvas-body">
          <!-- CREATE MODE: Trade Context -->
          <div v-if="offcanvasMode === 'create'" class="form-section-card">
            <h4 class="section-title">Trade Basics</h4>
            <div class="form-row-grid">
              <div class="form-group">
                <label class="form-label">Symbol / Ticker *</label>
                <input
                  type="text"
                  v-model="createForm.symbol"
                  class="form-input font-mono uppercase"
                  placeholder="e.g. TSLA, NVDA"
                  autofocus
                />
              </div>

              <div class="form-group">
                <label class="form-label">Date *</label>
                <input type="date" v-model="createForm.date" class="form-input" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Direction</label>
              <div class="dir-toggle-group">
                <button
                  type="button"
                  class="dir-toggle-btn"
                  :class="{ active: createForm.direction === 'LONG' }"
                  @click="createForm.direction = 'LONG'"
                >
                  LONG (Buy to Open)
                </button>
                <button
                  type="button"
                  class="dir-toggle-btn short"
                  :class="{ active: createForm.direction === 'SHORT' }"
                  @click="createForm.direction = 'SHORT'"
                >
                  SHORT (Sell to Open)
                </button>
              </div>
            </div>
          </div>

          <!-- Section: Strategy Setup & Catalyst -->
          <div class="form-group">
            <label class="form-label">
              <span>Setup / Strategy Type</span>
              <span class="label-hint">Catalyst or pattern</span>
            </label>
            <div class="setup-presets-grid">
              <button
                type="button"
                v-for="preset in SETUP_PRESETS"
                :key="preset"
                class="preset-chip-btn"
                :class="{ active: createForm.setupType.toLowerCase() === preset.toLowerCase() }"
                @click="selectPresetSetup(preset)"
              >
                {{ preset }}
              </button>
            </div>
            <input
              type="text"
              v-model="createForm.setupType"
              class="form-input"
              placeholder="Or enter custom setup (e.g. 9ema, High of Day, Round figure...)"
            />
          </div>

          <!-- Section: Watched Value / Key Level -->
          <div class="form-group">
            <div class="form-label-row">
              <label class="form-label">
                <span>Watched Key Level</span>
                <span class="label-hint">Price watched for trigger</span>
              </label>
              <button
                type="button"
                class="btn-quick-fill"
                @click="fillAvgPriceAsWatched"
                title="Fill entry price"
              >
                Use Entry Price
              </button>
            </div>
            <input
              type="text"
              v-model="createForm.watchedValue"
              class="form-input font-mono"
              placeholder="e.g. $152.50, HOD $14.80, Whole Dollar $150..."
            />
          </div>

          <!-- Section: Comment -->
          <div class="form-group">
            <label class="form-label">
              <MessageSquare :size="13" class="accent-icon" />
              <span>التعليق / Comment</span>
              <span class="label-hint">Execution takeaway or key takeaway</span>
            </label>
            <input
              type="text"
              v-model="createForm.comment"
              class="form-input"
              placeholder="e.g. Good patience on 9 EMA, followed plan, trimmed at HOD..."
            />
          </div>

          <!-- CREATE MODE: Executions Entry/Exit Builder -->
          <div v-if="offcanvasMode === 'create'" class="form-section-card fills-builder-card">
            <div class="section-header-row">
              <h4 class="section-title">Execution Fills</h4>
              <label class="checkbox-label font-xs">
                <input type="checkbox" v-model="createForm.isMultiLeg" />
                <span>Multi-Fill Builder (Scale-in / Avg down)</span>
              </label>
            </div>

            <!-- Standard Mode: 1-Entry and optional 1-Exit -->
            <div v-if="!createForm.isMultiLeg" class="standard-fills-box">
              <!-- Entry Fill Box -->
              <div class="fill-box entry">
                <div class="fill-box-header">
                  <span class="badge buy">{{ createForm.direction === 'LONG' ? 'ENTRY (BUY)' : 'ENTRY (SHORT)' }}</span>
                </div>
                <div class="fill-inputs-grid">
                  <div class="form-group">
                    <label class="form-label font-xs">Shares</label>
                    <input type="number" v-model="createForm.entryQty" class="form-input font-mono" min="1" />
                  </div>
                  <div class="form-group">
                    <label class="form-label font-xs">Price ($)</label>
                    <input type="number" step="0.01" v-model="createForm.entryPrice" class="form-input font-mono" placeholder="0.00" />
                  </div>
                  <div class="form-group">
                    <label class="form-label font-xs">Time</label>
                    <input type="text" v-model="createForm.entryTime" class="form-input font-mono" placeholder="HH:MM:SS" />
                  </div>
                </div>
              </div>

              <!-- Open position toggle -->
              <div class="open-trade-checkbox-row">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="createForm.isStillOpen" />
                  <span>Trade Still Open (No Exit Fill Yet)</span>
                </label>
              </div>

              <!-- Exit Fill Box (if closed) -->
              <div v-if="!createForm.isStillOpen" class="fill-box exit">
                <div class="fill-box-header">
                  <span class="badge sell">{{ createForm.direction === 'LONG' ? 'EXIT (SELL)' : 'EXIT (COVER)' }}</span>
                </div>
                <div class="fill-inputs-grid">
                  <div class="form-group">
                    <label class="form-label font-xs">Shares</label>
                    <input type="number" v-model="createForm.exitQty" class="form-input font-mono" min="1" />
                  </div>
                  <div class="form-group">
                    <label class="form-label font-xs">Price ($)</label>
                    <input type="number" step="0.01" v-model="createForm.exitPrice" class="form-input font-mono" placeholder="0.00" />
                  </div>
                  <div class="form-group">
                    <label class="form-label font-xs">Time</label>
                    <input type="text" v-model="createForm.exitTime" class="form-input font-mono" placeholder="HH:MM:SS" />
                  </div>
                </div>
              </div>
            </div>

            <!-- Multi-Leg Builder (Supports Averaging down!) -->
            <div v-else class="multileg-fills-box">
              <div v-for="(leg, legIdx) in createForm.legs" :key="legIdx" class="leg-row">
                <div class="leg-side-select">
                  <select v-model="leg.side" class="leg-select">
                    <option value="B">Buy</option>
                    <option value="S">Sell</option>
                  </select>
                </div>
                <input type="number" v-model="leg.qty" class="form-input font-mono leg-qty" placeholder="Qty" min="1" />
                <input type="number" step="0.01" v-model="leg.price" class="form-input font-mono leg-price" placeholder="Price" />
                <input type="text" v-model="leg.time" class="form-input font-mono leg-time" placeholder="Time" />
                <button type="button" class="btn-del-leg" @click="removeLeg(legIdx)" title="Remove Fill">
                  <X :size="14" />
                </button>
              </div>
              <div class="multileg-actions">
                <button type="button" class="btn ghost small" @click="addLeg('B')">+ Add Buy Fill</button>
                <button type="button" class="btn ghost small" @click="addLeg('S')">+ Add Sell Fill</button>
              </div>
            </div>
          </div>

          <!-- EDIT MODE: Existing Executions List & Add Fill -->
          <div v-if="offcanvasMode === 'edit' && editingTrade" class="form-section-card">
            <div class="section-header-row">
              <h4 class="section-title">Executions in this Trade ({{ editingTrade.executions.length }})</h4>
              <button
                type="button"
                class="btn primary small"
                @click="showAddFillBox = !showAddFillBox"
              >
                <Plus :size="12" />
                <span>{{ showAddFillBox ? 'Cancel Fill' : '+ Add Fill' }}</span>
              </button>
            </div>

            <!-- Add Fill Box -->
            <div v-if="showAddFillBox" class="add-fill-inline-box">
              <div class="fill-inputs-grid">
                <div class="form-group">
                  <label class="form-label font-xs">Side</label>
                  <select v-model="newFillForm.side" class="form-input">
                    <option value="B">BUY</option>
                    <option value="S">SELL</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label font-xs">Shares</label>
                  <input type="number" v-model="newFillForm.qty" class="form-input font-mono" min="1" />
                </div>
                <div class="form-group">
                  <label class="form-label font-xs">Price ($)</label>
                  <input type="number" step="0.01" v-model="newFillForm.price" class="form-input font-mono" placeholder="0.00" />
                </div>
                <div class="form-group">
                  <label class="form-label font-xs">Time</label>
                  <input type="text" v-model="newFillForm.time" class="form-input font-mono" placeholder="HH:MM:SS" />
                </div>
              </div>
              <div class="add-fill-btn-row">
                <button type="button" class="btn primary small" @click="addFillToExistingTrade">
                  Add Execution Fill
                </button>
              </div>
            </div>

            <!-- Existing Fills Table -->
            <div class="fills-mini-table">
              <div
                v-for="(ex, exIdx) in editingTrade.executions"
                :key="exIdx"
                class="fill-mini-row"
                :class="{ 'anomaly-fill': ex.isAnomaly }"
              >
                <div class="fill-left">
                  <span class="mini-side-badge" :class="ex.trd_type === 'B' ? 'buy' : 'sell'">
                    {{ ex.trd_type }}
                  </span>
                  <span class="fill-qty-price font-mono">
                    {{ num(ex.qty) }} sh @ ${{ Number(ex.price).toFixed(2) }}
                  </span>
                  <span v-if="ex.isAnomaly" class="fill-anomaly-pill">
                    <AlertTriangle :size="10" /> {{ ex.anomalyReason }}
                  </span>
                </div>
                <div class="fill-right font-mono muted">
                  <span>{{ ex.exec_time || ex.execTime || '—' }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Section: Screenshots / Images -->
          <div class="form-group">
            <div class="form-label-row">
              <label class="form-label">
                <span>الصور والرسومات البيانية / Screenshots</span>
                <span class="label-hint">({{ createForm.images.length }} attached)</span>
              </label>
              <label class="btn-upload-label" for="manualTradeImageInput">
                <Plus :size="13" />
                <span>Upload Screenshot</span>
              </label>
              <input
                id="manualTradeImageInput"
                type="file"
                accept="image/*"
                multiple
                class="hidden-file-input"
                @change="handleImageUpload"
              />
            </div>

            <div class="clipboard-paste-tip">
              <Camera :size="13" />
              <span>Tip: Press <b>Ctrl + V</b> anywhere to paste chart screenshots directly from clipboard!</span>
            </div>

            <!-- Gallery Grid -->
            <div v-if="createForm.images.length" class="offcanvas-gallery">
              <div v-for="(img, idx) in createForm.images" :key="idx" class="gallery-thumb-card">
                <img :src="img" alt="Trade Screenshot" class="thumb-img" @click="imagePreviewModal = img" />
                <div class="thumb-overlay">
                  <button class="thumb-act-btn zoom" @click.stop="imagePreviewModal = img" title="View Fullscreen">
                    <ZoomIn :size="14" />
                  </button>
                  <button class="thumb-act-btn del" @click.stop="removeImage(idx)" title="Remove Screenshot">
                    <Trash2 :size="14" />
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="empty-gallery-dropzone">
              <Camera :size="24" class="muted" />
              <p>No screenshots attached.</p>
              <small>Click "Upload Screenshot" or paste with Ctrl+V</small>
            </div>
          </div>

          <!-- Section: Notes & Review -->
          <div class="form-group">
            <label class="form-label">
              <span>ملاحظات الصفقة / Trade Notes</span>
              <span class="label-hint">Thesis, emotional discipline, review</span>
            </label>
            <textarea
              v-model="createForm.notes"
              class="form-textarea"
              rows="3"
              placeholder="Why did you take this trade? Did you respect your stop?..."
            ></textarea>
          </div>
        </div>

        <!-- Drawer Footer -->
        <div class="offcanvas-footer">
          <button v-if="offcanvasMode === 'edit' && editingTrade" type="button" class="btn-delete-trade" @click="deleteTrade(editingTrade)">
            <Trash2 :size="14" />
            <span>Delete Trade</span>
          </button>
          <div class="footer-right-actions">
            <button type="button" class="btn ghost" @click="closeOffcanvas">Cancel</button>
            <button
              v-if="offcanvasMode === 'create'"
              type="button"
              class="btn primary save-meta-btn"
              :disabled="isSavingMeta"
              @click="saveNewTrade"
            >
              <Check :size="14" />
              <span>{{ isSavingMeta ? 'Saving...' : 'Save & Log Trade' }}</span>
            </button>
            <button
              v-else
              type="button"
              class="btn primary save-meta-btn"
              :disabled="isSavingMeta"
              @click="saveEditedTrade"
            >
              <Check :size="14" />
              <span>{{ isSavingMeta ? 'Saving...' : 'Update Trade' }}</span>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Fullscreen Image Lightbox Modal -->
    <div v-if="imagePreviewModal" class="image-lightbox-modal" @click="imagePreviewModal = null">
      <div class="lightbox-content" @click.stop>
        <img :src="imagePreviewModal" alt="Screenshot Full View" class="lightbox-img" />
        <button class="lightbox-close" @click="imagePreviewModal = null" title="Close">
          <X :size="20" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.journal-view {
  --bg: #0b1120;
  --panel: rgba(22, 30, 49, 0.72);
  --border: rgba(255, 255, 255, 0.08);
  --text: #f1f5f9;
  --muted: #94a3b8;
  --accent: #3b82f6;
  --win: #34d399;
  --loss: #f87171;
  --amber: #fbbf24;
  position: relative;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  color: var(--text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-size: 0.875rem;
  line-height: 1.5;
  text-align: left;
  background:
    radial-gradient(1000px 500px at 10% -10%, rgba(59, 130, 246, 0.12), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(139, 92, 246, 0.08), transparent 55%),
    var(--bg);
  border-radius: 14px;
}

.wrap {
  max-width: 1480px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.glass {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  backdrop-filter: blur(12px);
}

/* Header */
.journal-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.jh-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.jh-icon {
  color: #38bdf8;
}
.jh-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 800;
  color: #f8fafc;
}
.jh-badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.12);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
}
.jh-desc {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}
.jh-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.log-trade-hero-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.84rem;
  font-weight: 700;
  padding: 8px 16px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
}

/* Empty State */
.empty {
  padding: 60px 24px;
  display: flex;
  justify-content: center;
  text-align: center;
}
.empty-journal-card {
  max-width: 520px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}
.empty-icon-wrap {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #38bdf8;
}
.empty-journal-card h2 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 800;
}
.empty-journal-card p {
  margin: 0;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.5;
}
.empty-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
}
.large-btn {
  padding: 10px 20px;
  font-size: 0.9rem;
  font-weight: 700;
}

/* Floating Actions */
.floating-actions {
  position: fixed;
  bottom: 24px;
  right: 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 1000;
}
.floating-btn {
  background: rgba(30, 41, 59, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f1f5f9;
  border-radius: 50px;
  padding: 10px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  font-size: 0.82rem;
  font-weight: 700;
  transition: all 0.2s ease;
}
.floating-btn:hover {
  background: #334155;
  transform: translateY(-2px);
}
.log-trade-floating-btn {
  background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
  color: #fff !important;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.45) !important;
}

/* Universal Filter Bar */
.universal-filter-bar {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.uf-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.uf-item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(0, 0, 0, 0.3);
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
}
.uf-label {
  font-size: 0.72rem;
  color: var(--muted);
  font-weight: 600;
}
.uf-select, .uf-input {
  background: transparent;
  border: none;
  color: var(--text);
  font-size: 0.78rem;
  outline: none;
}
.uf-select option {
  background: #1e293b;
  color: #f8fafc;
}
.uf-search {
  flex: 1;
  min-width: 220px;
}
.uf-search input {
  width: 100%;
}
.uf-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.74rem;
  color: var(--muted);
}
.active-badge {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 600;
}
.storage-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #38bdf8;
  font-weight: 600;
}
.storage-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #38bdf8;
}

/* Main Navigation Tabs */
.main-tabs-nav {
  display: flex;
  gap: 8px;
}
.main-tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.82rem;
  transition: all 0.15s ease;
}
.main-tab-btn.active {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.4);
  color: #fff;
}
.tab-badge {
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
}

/* Toolbar */
.toolbar {
  padding: 8px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.toolbar .tabs {
  display: flex;
  gap: 6px;
}
.toolbar .tabs button {
  background: transparent;
  border: none;
  color: var(--muted);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 6px;
}
.toolbar .tabs button.on {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font-weight: 600;
}
.toolbar .tabs button em {
  font-style: normal;
  background: rgba(255, 255, 255, 0.1);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.7rem;
}
.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* General Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid transparent;
}
.btn.primary {
  background: #2563eb;
  color: #fff;
}
.btn.primary:hover {
  background: #1d4ed8;
}
.btn.ghost {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text);
  border-color: var(--border);
}
.btn.ghost:hover {
  background: rgba(255, 255, 255, 0.12);
}
.btn.small {
  padding: 4px 10px;
  font-size: 0.74rem;
}

/* Table styles */
.tbl-wrap {
  overflow-x: auto;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.tbl th {
  padding: 8px 12px;
  font-weight: 600;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  position: relative;
  user-select: none;
}
.tbl td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.clickable-row {
  cursor: pointer;
  transition: background 0.15s ease;
}
.clickable-row:hover {
  background: rgba(255, 255, 255, 0.04);
}
.clickable-row.open {
  background: rgba(59, 130, 246, 0.06);
}
.col-resizer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 5px;
  cursor: col-resize;
}

/* Trade Cards Stack */
.trades-cards-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 12px;
}
.trade-card-wrapper {
  border: 1px solid rgba(59, 130, 246, 0.28);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.55);
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
  transition: all 0.2s ease;
}
.trade-card-wrapper:hover {
  border-color: rgba(59, 130, 246, 0.48);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
}
.trade-card-wrapper.has-anomaly {
  border-color: rgba(239, 68, 68, 0.42);
}
.trade-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: rgba(30, 41, 59, 0.65);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-wrap: wrap;
}
.trade-header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.trade-num-badge {
  font-size: 0.74rem;
  font-weight: 700;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 4px;
}
.trade-symbol-tag {
  font-size: 0.92rem;
  font-weight: 800;
  color: #f8fafc;
}
.trade-dir-tag {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  text-transform: uppercase;
}
.trade-dir-tag.long {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.3);
}
.trade-dir-tag.short {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
}
.trade-status-tag {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 4px;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.04);
}
.trade-status-tag.open {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}
.anomaly-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  font-weight: 700;
  background: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.4);
  padding: 2px 8px;
  border-radius: 999px;
  animation: pulseGlow 2s infinite;
}
@keyframes pulseGlow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.75; }
}

.trade-header-tactics {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.setup-pill {
  font-size: 0.74rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  cursor: pointer;
}
.setup-pill.empty {
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  border: 1px dashed rgba(255, 255, 255, 0.2);
}
.setup-badge {
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 0.72rem;
  font-weight: 600;
}
.setup-ema { background: rgba(59, 130, 246, 0.18); color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.35); }
.setup-hod { background: rgba(245, 158, 11, 0.18); color: #fcd34d; border: 1px solid rgba(252, 211, 77, 0.35); }
.setup-round { background: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.35); }
.setup-vwap { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.35); }
.setup-breakout { background: rgba(236, 72, 153, 0.18); color: #f472b6; border: 1px solid rgba(244, 114, 182, 0.35); }
.setup-custom { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }

.watched-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.73rem;
  background: rgba(56, 189, 248, 0.12);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
  padding: 3px 9px;
  border-radius: 6px;
  cursor: pointer;
}
.watched-pill.empty {
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  border: 1px dashed rgba(255, 255, 255, 0.18);
}
.watched-val-text {
  color: #38bdf8;
  font-weight: 600;
  cursor: pointer;
}

.comment-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  font-weight: 500;
  background: rgba(16, 185, 129, 0.12);
  color: #6ee7b7;
  border: 1px solid rgba(16, 185, 129, 0.28);
  padding: 3px 9px;
  border-radius: 6px;
  cursor: pointer;
  max-width: 200px;
}
.comment-pill-btn.empty {
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  border: 1px dashed rgba(255, 255, 255, 0.18);
  max-width: none;
}
.comment-pill-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.images-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  font-weight: 600;
  background: rgba(139, 92, 246, 0.14);
  color: #a78bfa;
  border: 1px solid rgba(167, 139, 250, 0.3);
  padding: 3px 9px;
  border-radius: 6px;
  cursor: pointer;
}
.images-pill-btn.empty {
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  border: 1px dashed rgba(255, 255, 255, 0.18);
}

.trade-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.trade-pnl-box {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.2;
}
.pnl-val {
  font-size: 0.92rem;
  font-weight: 700;
}
.pnl-shares {
  font-size: 0.7rem;
}
.btn-edit-trade {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.75rem;
  font-weight: 600;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
}

/* Anomaly Row Highlight with light red opacity */
.anomaly-row {
  background-color: rgba(239, 68, 68, 0.14) !important;
  border-left: 3px solid #ef4444 !important;
}
.side-cell {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.anomaly-label-tag {
  font-size: 0.65rem;
  font-weight: 800;
  background: #ef4444;
  color: #fff;
  padding: 1px 4px;
  border-radius: 3px;
}

/* Badges */
.badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
}
.badge.buy { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.badge.sell { background: rgba(239, 68, 68, 0.2); color: #f87171; }

.col-img-btn, .col-edit-btn {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 2px 7px;
  border-radius: 4px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
}

.comment-cell-text {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #cbd5e1;
  font-size: 0.76rem;
  max-width: 100%;
  cursor: pointer;
}
.comment-icon { flex-shrink: 0; color: #34d399; }
.comment-text-truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Offcanvas Drawer */
.offcanvas-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.68);
  backdrop-filter: blur(4px);
  z-index: 99998;
}
.offcanvas-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 520px;
  max-width: 94vw;
  background: #0f172a;
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: -10px 0 35px rgba(0, 0, 0, 0.65);
  z-index: 99999;
  transform: translateX(100%);
  transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}
.offcanvas-drawer.open {
  transform: translateX(0);
}
.offcanvas-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.offcanvas-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 16px 20px;
  background: rgba(30, 41, 59, 0.65);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.offcanvas-title-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.offcanvas-badge-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.offcanvas-tag {
  font-size: 0.75rem;
  font-weight: 700;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 7px;
  border-radius: 4px;
}
.offcanvas-symbol {
  font-size: 1.1rem;
  font-weight: 800;
  color: #f8fafc;
}
.offcanvas-dir-badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
}
.offcanvas-dir-badge.long { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.offcanvas-dir-badge.short { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.offcanvas-sub {
  font-size: 0.78rem;
  color: var(--muted);
}
.offcanvas-close-btn {
  background: transparent;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
}
.offcanvas-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.form-section-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-title {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 700;
  color: #e2e8f0;
}
.section-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.form-row-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  color: #e2e8f0;
}
.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.label-hint {
  font-size: 0.7rem;
  color: var(--muted);
  font-weight: 400;
}
.form-input, .form-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  color: var(--text);
  font-size: 0.82rem;
  outline: none;
  box-sizing: border-box;
}
.form-input:focus, .form-textarea:focus {
  border-color: var(--accent);
}
.uppercase { text-transform: uppercase; }

.dir-toggle-group {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.dir-toggle-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 700;
  font-size: 0.78rem;
  transition: all 0.15s ease;
}
.dir-toggle-btn.active {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border-color: #34d399;
}
.dir-toggle-btn.short.active {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
  border-color: #f87171;
}

.setup-presets-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.preset-chip-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.74rem;
  cursor: pointer;
}
.preset-chip-btn.active {
  background: #2563eb;
  color: #fff;
  border-color: #3b82f6;
  font-weight: 600;
}
.btn-quick-fill {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #60a5fa;
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
}

/* Fills builder */
.standard-fills-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fill-box {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.fill-box.entry { border-left: 3px solid #10b981; }
.fill-box.exit { border-left: 3px solid #ef4444; }
.fill-inputs-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.open-trade-checkbox-row {
  display: flex;
  align-items: center;
  padding: 4px 0;
}
.checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--text);
}

.multileg-fills-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.leg-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.leg-select {
  background: #1e293b;
  border: 1px solid var(--border);
  color: #fff;
  padding: 6px;
  border-radius: 6px;
  font-size: 0.76rem;
}
.leg-qty { width: 85px; }
.leg-price { flex: 1; }
.leg-time { width: 90px; }
.btn-del-leg {
  background: transparent;
  border: none;
  color: #ef4444;
  cursor: pointer;
  padding: 4px;
}
.multileg-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

/* Existing Fills inside Edit Mode */
.fills-mini-table {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px;
  max-height: 180px;
  overflow-y: auto;
}
.fill-mini-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  border-radius: 5px;
  font-size: 0.74rem;
}
.fill-mini-row.anomaly-fill {
  background: rgba(239, 68, 68, 0.16);
  border-left: 2px solid #ef4444;
}
.fill-left { display: flex; align-items: center; gap: 8px; }
.mini-side-badge { font-size: 0.68rem; font-weight: 700; padding: 1px 5px; border-radius: 3px; }
.mini-side-badge.buy { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.mini-side-badge.sell { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.fill-anomaly-pill {
  font-size: 0.65rem;
  font-weight: 700;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.2);
  padding: 1px 5px;
  border-radius: 3px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.add-fill-inline-box {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
}
.add-fill-btn-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

/* Gallery & Lightbox */
.btn-upload-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(139, 92, 246, 0.18);
  color: #c084fc;
  border: 1px solid rgba(192, 132, 252, 0.35);
  padding: 3px 9px;
  border-radius: 5px;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
}
.hidden-file-input { display: none; }
.clipboard-paste-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.03);
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
}
.offcanvas-gallery {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 8px;
}
.gallery-thumb-card {
  position: relative;
  aspect-ratio: 16/10;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: #000;
}
.thumb-img { width: 100%; height: 100%; object-fit: cover; cursor: pointer; display: block; }
.thumb-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.gallery-thumb-card:hover .thumb-overlay { opacity: 1; }
.thumb-act-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  padding: 6px;
  border-radius: 50%;
  cursor: pointer;
}
.thumb-act-btn.del:hover { background: #ef4444; }
.empty-gallery-dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 20px;
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  text-align: center;
  color: var(--muted);
  font-size: 0.78rem;
}

/* Offcanvas Footer */
.offcanvas-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: rgba(15, 23, 42, 0.95);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.footer-right-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
.btn-delete-trade {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
}
.btn-delete-trade:hover {
  background: #ef4444;
  color: #fff;
}

/* Lightbox Modal */
.image-lightbox-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.88);
  backdrop-filter: blur(8px);
  z-index: 100000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.lightbox-content { position: relative; max-width: 90vw; max-height: 90vh; }
.lightbox-img { max-width: 100%; max-height: 85vh; border-radius: 8px; display: block; }
.lightbox-close {
  position: absolute;
  top: -14px;
  right: -14px;
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

/* Toast */
.floating-status {
  position: fixed;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100001;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 0.82rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
}
.floating-status.good { background: rgba(16, 185, 129, 0.9); color: #fff; }
.floating-status.bad { background: rgba(239, 68, 68, 0.9); color: #fff; }
.floating-status.muted { background: rgba(30, 41, 59, 0.95); color: #cbd5e1; }
.status-close { background: transparent; border: none; color: #fff; cursor: pointer; }

/* KPI Cards */
.kpis {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
.kpi {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.k-label { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; font-weight: 700; }
.k-value { font-size: 1.25rem; font-weight: 800; color: #fff; }
.k-sub { font-size: 0.72rem; color: var(--muted); }
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.chart-card { padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.chart-header { display: flex; align-items: center; justify-content: space-between; }
.chart-title { display: flex; align-items: center; gap: 6px; font-size: 0.84rem; font-weight: 700; }
.bar-chart-container {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  height: 180px;
  padding-top: 10px;
}
.bar-group { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; }
.bars-pair { display: flex; gap: 3px; align-items: flex-end; height: 150px; }
.chart-bar { width: 10px; border-radius: 3px 3px 0 0; }
.chart-bar.buy-bar { background: #10b981; }
.chart-bar.sell-bar { background: #ef4444; }
.bar-date-label { font-size: 0.65rem; color: var(--muted); }

.symbol-bars-list { display: flex; flex-direction: column; gap: 10px; }
.sym-row { display: flex; flex-direction: column; gap: 4px; }
.sym-meta { display: flex; justify-content: space-between; font-size: 0.78rem; }
.sym-track { width: 100%; height: 6px; background: rgba(255, 255, 255, 0.05); border-radius: 999px; overflow: hidden; }
.sym-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 999px; }

/* Responsive */
@media (max-width: 1200px) {
  .kpis { grid-template-columns: repeat(3, 1fr); }
  .charts-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .kpis { grid-template-columns: repeat(2, 1fr); }
  .offcanvas-drawer { width: 100vw; }
}
</style>

