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
} from 'lucide-vue-next';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import HtmlEditor from '../components/HtmlEditor.vue';
import * as XLSX from 'xlsx';
import { parseTradeStatsCsv } from '../utils/tradeStatsParser';
import {
  getTradesFromLocalStorage,
  loadPersistedTrades,
  persistTrades,
  clearPersistedTrades,
  loadAllTradeMetadata,
  saveTradeMetadata,
  clearAllTradeMetadata,
  STORAGE_KEY,
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

// Load stored transactions synchronously from localStorage on initial render
const loadStoredTransactions = () => {
  try {
    const rawRecords = getTradesFromLocalStorage();
    if (Array.isArray(rawRecords) && rawRecords.length > 0) {
      return parseTradeStatsCsv(rawRecords);
    }
  } catch (err) {
    console.error('Failed to load transactions from localStorage:', err);
  }
  return [];
};

// ---------------------------------------------------------------- state (read directly from storage)
const transactions = shallowRef(loadStoredTransactions());
const tradeMetadata = ref({});
const isOffcanvasOpen = ref(false);
const editingTrade = ref(null);
const offcanvasForm = ref({
  watchedValue: '',
  setupType: '',
  comment: '',
  notes: '',
  images: [],
});
const imagePreviewModal = ref(null);
const isSavingMeta = ref(false);

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

const openEditOffcanvas = (trade) => {
  editingTrade.value = trade;
  const existingMeta = tradeMetadata.value[trade.tradeId] || {};
  offcanvasForm.value = {
    watchedValue: existingMeta.watchedValue || trade.watchedValue || '',
    setupType: existingMeta.setupType || trade.setupType || '',
    comment: existingMeta.comment || trade.comment || existingMeta.notes || trade.notes || '',
    notes: existingMeta.notes || trade.notes || '',
    images: Array.isArray(existingMeta.images)
      ? [...existingMeta.images]
      : Array.isArray(trade.images)
      ? [...trade.images]
      : [],
  };
  isOffcanvasOpen.value = true;
};

const openTradeImages = (trade) => {
  openEditOffcanvas(trade);
};

const closeOffcanvas = () => {
  isOffcanvasOpen.value = false;
  editingTrade.value = null;
};

const selectPresetSetup = (preset) => {
  offcanvasForm.value.setupType = preset;
};

const fillAvgPriceAsWatched = () => {
  if (editingTrade.value?.avgEntryPrice) {
    offcanvasForm.value.watchedValue = '$' + Number(editingTrade.value.avgEntryPrice).toFixed(2);
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
      offcanvasForm.value.images.push(event.target.result);
    };
    reader.readAsDataURL(file);
  }
  e.target.value = '';
};

const removeImage = (index) => {
  offcanvasForm.value.images.splice(index, 1);
};

const saveOffcanvas = async () => {
  if (!editingTrade.value) return;
  isSavingMeta.value = true;
  const tId = editingTrade.value.tradeId;

  const dataToSave = {
    watchedValue: offcanvasForm.value.watchedValue.trim(),
    setupType: offcanvasForm.value.setupType.trim(),
    comment: offcanvasForm.value.comment.trim(),
    notes: offcanvasForm.value.notes.trim() || offcanvasForm.value.comment.trim(),
    images: offcanvasForm.value.images,
  };

  await saveTradeMetadata(tId, dataToSave);

  tradeMetadata.value = {
    ...tradeMetadata.value,
    [tId]: {
      ...dataToSave,
      tradeId: tId,
    },
  };

  status.value = {
    text: `Saved setup & notes for ${editingTrade.value.symbol} (Trade #${editingTrade.value.tradeNumber})`,
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
        offcanvasForm.value.images.push(ev.target.result);
        status.value = {
          text: 'Pasted chart screenshot from clipboard!',
          tone: 'good',
        };
      };
      reader.readAsDataURL(blob);
    }
  }
};

const mainTab = ref('tables'); // 'tables' | 'stats'
const activeTab = ref('by-date'); // 'by-date' | 'by-symbol' (tables sub-tab)
const expandedDates = ref({});
const searchQuery = ref('');
const selectedSide = ref('ALL'); // 'ALL' | 'B' | 'S'
const selectedDate = ref('ALL');
const selectedSymbol = ref('ALL');
const selectedSession = ref('ALL'); // 'ALL' | 'REGULAR' | 'PRE' | 'POST'
const minOrderQty = ref(0);
const status = ref({ text: '', tone: 'muted' });
const isDragging = ref(false);
const fileInput = ref(null);

const hasData = computed(() => transactions.value.length > 0);

// ---------------------------------------------------------------- format helpers
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
  if (s.includes(' ')) {
    return s.split(' ')[1] || s;
  }
  if (s.includes('T')) {
    return s.split('T')[1] || s;
  }
  return s;
};

// ---------------------------------------------------------------- upload / clear
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

      // Excel files (.xlsx, .xls)
      if (fileNameLower.endsWith('.xlsx') || fileNameLower.endsWith('.xls')) {
        const buffer = await file.arrayBuffer();
        const workbook = XLSX.read(buffer, { type: 'array' });
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' });
        const batch = parseTradeStatsCsv(jsonData);
        if (batch.length) parsedIncomingBatches.push(...batch);
      } else {
        // Text / CSV / JSON files
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
      text: 'No valid trade records found in the selected file(s). Expected JSON array, CSV, or Excel file.',
      tone: 'bad',
    };
    return;
  }

  try {
    // 1. Get current stored records
    const currentList =
      transactions.value && transactions.value.length ? [...transactions.value] : loadStoredTransactions();

    // 2. Perform intelligent deduplication
    const { newRecords, duplicateCount, totalIncoming } = deduplicateTrades(currentList, parsedIncomingBatches);

    // 3. If all records were already stored before
    if (!newRecords.length) {
      status.value = {
        text: `No new trades to add. All ${totalIncoming} transaction${
          totalIncoming === 1 ? '' : 's'
        } already exist in storage (${duplicateCount} duplicate${duplicateCount === 1 ? '' : 's'} skipped).`,
        tone: 'muted',
      };
      return;
    }

    // 4. Merge and sort chronologically
    const combined = [...currentList, ...newRecords];
    combined.sort((a, b) => {
      const dtA = `${a.trade_dt || a.tradeDate || ''} ${a.exec_time || a.execTime || ''}`;
      const dtB = `${b.trade_dt || b.tradeDate || ''} ${b.exec_time || b.execTime || ''}`;
      if (dtA && dtB && dtA !== dtB) {
        return dtA.localeCompare(dtB);
      }
      return (Number(a.id) || 0) - (Number(b.id) || 0);
    });

    // 5. Persist to IndexedDB & localStorage
    await persistTrades(combined.map(toCleanJsonRecord));
    transactions.value = combined;
    expandedDates.value = {};

    // 6. User feedback
    if (currentList.length === 0) {
      status.value = {
        text: `Imported and safely stored ${newRecords.length} transaction${
          newRecords.length === 1 ? '' : 's'
        }${duplicateCount > 0 ? ` (${duplicateCount} duplicate${duplicateCount === 1 ? '' : 's'} skipped)` : ''}`,
        tone: 'good',
      };
    } else {
      status.value = {
        text: `Added ${newRecords.length} new transaction${
          newRecords.length === 1 ? '' : 's'
        } (${duplicateCount} duplicate${duplicateCount === 1 ? '' : 's'} skipped). Total: ${combined.length} trades stored.`,
        tone: 'good',
      };
    }

    setTimeout(() => {
      if (status.value.tone === 'good') {
        status.value = { text: '', tone: 'muted' };
      }
    }, 6000);
  } catch (err) {
    console.error(err);
    status.value = { text: `Error processing transactions: ${err.message}`, tone: 'bad' };
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
    await clearPersistedTrades();
    await clearAllTradeMetadata();
    tradeMetadata.value = {};
  } catch (err) {
    console.error('Failed to clear storage:', err);
  }
  expandedDates.value = {};
  searchQuery.value = '';
  selectedSide.value = 'ALL';
  selectedDate.value = 'ALL';
  selectedSymbol.value = 'ALL';
  selectedSession.value = 'ALL';
  minOrderQty.value = 0;
  status.value = { text: 'All stored transactions have been cleared', tone: 'muted' };
};

const confirmClearData = () => {
  if (window.confirm('Are you sure you want to clear all stored transaction records from local storage?')) {
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
  { key: 'id', label: 'id', visible: false, align: 'l', mono: true, width: 80 },
  { key: 'systemId', label: 'systemId', visible: false, align: 'l', mono: true, width: 75 },
  { key: 'system_date', label: 'system_date', visible: false, align: 'l', mono: true, muted: true, width: 120 },
  { key: 'tr_no', label: 'tr_no', visible: true, align: 'l', mono: true, bold: true, width: 95 },
  { key: 'entry_type', label: 'entry_type', visible: false, align: 'c', muted: true, width: 75 },
  { key: 'trd_type', label: 'trd_type', visible: true, align: 'c', badge: true, width: 65 },
  { key: 'trade_dt', label: 'trade_dt', visible: true, align: 'l', mono: true, width: 95 },
  { key: 'settle_dt', label: 'settle_dt', visible: false, align: 'l', mono: true, width: 95 },
  { key: 'exec_time', label: 'exec_time', visible: true, align: 'l', mono: true, bold: true, width: 85 },
  { key: 'symbol', label: 'symbol', visible: true, align: 'l', bold: true, width: 80 },
  { key: 'qty', label: 'qty', visible: true, align: 'r', width: 75 },
  { key: 'price', label: 'price', visible: true, align: 'r', width: 80 },
  { key: 'g_amt', label: 'g_amt', visible: true, align: 'r', mono: true, width: 95 },
  { key: 'n_amt', label: 'n_amt', visible: true, align: 'r', mono: true, width: 95 },
  { key: 'comm', label: 'comm', visible: true, align: 'r', muted: true, width: 70 },
  { key: 'exch_fee', label: 'exch_fee', visible: false, align: 'r', muted: true, width: 70 },
  { key: 'sec_fee', label: 'sec_fee', visible: false, align: 'r', muted: true, width: 75 },
  { key: 'descr', label: 'descr', visible: false, align: 'l', muted: true, width: 140 },
  { key: 'm_fee1', label: 'm_fee1', visible: false, align: 'r', muted: true, width: 70 },
  { key: 'm_fee4', label: 'm_fee4', visible: false, align: 'r', muted: true, width: 70 },
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
        } else if (typeof item.maxWidth === 'string') {
          const num = parseInt(item.maxWidth, 10);
          if (!isNaN(num) && num >= 35) parsedWidth = num;
        }

        result.push({
          ...def,
          visible: typeof item.visible === 'boolean' ? item.visible : def.visible,
          width: parsedWidth,
        });
        defMap.delete(item.key);
      }
    }
    for (const def of defMap.values()) {
      result.push({ ...def });
    }
    return result;
  } catch (err) {
    console.error('Failed to load column settings from localStorage:', err);
    return defaultCols.map((c) => ({ ...c }));
  }
};

const dateCols = ref(loadSavedCols('tradeStats.cols.date', defaultDateCols));
const tradeCols = ref(loadSavedCols('tradeStats.cols.trade', defaultTradeCols));
const symbolCols = ref(loadSavedCols('tradeStats.cols.symbol', defaultSymbolCols));

watch(
  dateCols,
  (val) => {
    try {
      localStorage.setItem('tradeStats.cols.date', JSON.stringify(val));
    } catch {}
  },
  { deep: true },
);

watch(
  tradeCols,
  (val) => {
    try {
      localStorage.setItem('tradeStats.cols.trade', JSON.stringify(val));
    } catch {}
  },
  { deep: true },
);

watch(
  symbolCols,
  (val) => {
    try {
      localStorage.setItem('tradeStats.cols.symbol', JSON.stringify(val));
    } catch {}
  },
  { deep: true },
);

// ---------------------------------------------------------------- Interactive column resizing
const activeResizeCol = ref(null);

const startColResize = (e, col) => {
  const startX = e.clientX;
  const startWidth = col.width || 90;
  activeResizeCol.value = col.key;
  document.body.classList.add('resizing-col');

  const onMouseMove = (moveEvent) => {
    const delta = moveEvent.clientX - startX;
    const newWidth = Math.max(40, Math.min(700, Math.round(startWidth + delta)));
    col.width = newWidth;
  };

  const onMouseUp = () => {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
    document.body.classList.remove('resizing-col');
    activeResizeCol.value = null;
  };

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
};

const resetSingleColWidth = (col, defaultCols) => {
  const def = defaultCols.find((c) => c.key === col.key);
  if (def && def.width) {
    col.width = def.width;
  }
};

const visibleDateCols = computed(() => dateCols.value.filter((c) => c.visible));
const visibleTradeCols = computed(() => tradeCols.value.filter((c) => c.visible));

const activeColDropdown = ref(null); // 'date' | 'trade' | null

const toggleColDropdown = (type) => {
  activeColDropdown.value = activeColDropdown.value === type ? null : type;
};

const closeColDropdown = () => {
  activeColDropdown.value = null;
};

const moveCol = (colsList, index, delta) => {
  const targetIndex = index + delta;
  if (targetIndex < 0 || targetIndex >= colsList.length) return;
  const temp = colsList[index];
  colsList[index] = colsList[targetIndex];
  colsList[targetIndex] = temp;
};

const resetDateCols = () => {
  dateCols.value = defaultDateCols.map((c) => ({ ...c }));
  try {
    localStorage.removeItem('tradeStats.cols.date');
  } catch {}
};

const resetTradeCols = () => {
  tradeCols.value = defaultTradeCols.map((c) => ({ ...c }));
  try {
    localStorage.removeItem('tradeStats.cols.trade');
  } catch {}
};

const onGlobalClick = () => {
  activeColDropdown.value = null;
};

onMounted(async () => {
  window.addEventListener('click', onGlobalClick);
  window.addEventListener('paste', onWindowPaste);

  // Asynchronously verify with IndexedDB for reliable large datasets & migration
  try {
    const persisted = await loadPersistedTrades();
    if (persisted.length > 0 && persisted.length !== transactions.value.length) {
      transactions.value = parseTradeStatsCsv(persisted);
    }
  } catch (err) {
    console.warn('Failed to load from IndexedDB on mount:', err);
  }

  // Load custom trade metadata (watched levels, setup types, screenshots)
  try {
    tradeMetadata.value = await loadAllTradeMetadata();
  } catch (err) {
    console.warn('Failed to load trade metadata on mount:', err);
  }

  if (transactions.value.length > 0) {
    status.value = {
      text: `Loaded ${num(transactions.value.length)} stored trade${transactions.value.length === 1 ? '' : 's'}`,
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
  window.removeEventListener('click', onGlobalClick);
  window.removeEventListener('paste', onWindowPaste);
});

// ---------------------------------------------------------------- distinct filters & session helpers
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

const hasActiveFilters = computed(() => {
  return (
    searchQuery.value.trim() !== '' ||
    selectedSide.value !== 'ALL' ||
    selectedDate.value !== 'ALL' ||
    selectedSymbol.value !== 'ALL' ||
    selectedSession.value !== 'ALL' ||
    minOrderQty.value > 0
  );
});

const resetAllFilters = () => {
  searchQuery.value = '';
  selectedSide.value = 'ALL';
  selectedDate.value = 'ALL';
  selectedSymbol.value = 'ALL';
  selectedSession.value = 'ALL';
  minOrderQty.value = 0;
};

// ---------------------------------------------------------------- filtered transactions
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

// ---------------------------------------------------------------- trader statistics aggregates
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

  const symbolMap = new Map();
  const dayMap = new Map();
  const hourMap = new Map();

  list.forEach((t) => {
    const q = t.quantity || 0;
    totalQty += q;
    totalTurnover += (t.grossAmount || 0);
    totalFees += (t.totalFees || 0);

    if (q > 0) {
      if (q < minQty) minQty = q;
      if (q > maxQty) maxQty = q;
    }

    if (t.tradeType === 'B') buyCount += 1;
    else if (t.tradeType === 'S') sellCount += 1;

    // Symbol distribution
    const sym = t.symbol || 'OTHER';
    const sEntry = symbolMap.get(sym) || { count: 0, qty: 0 };
    sEntry.count += 1;
    sEntry.qty += q;
    symbolMap.set(sym, sEntry);

    // Day distribution
    const d = t.tradeDate || 'Unknown';
    dayMap.set(d, (dayMap.get(d) || 0) + 1);

    // Hour distribution from exec_time or execTime
    const timeStr = String(t.execTime || t.exec_time || '');
    if (timeStr) {
      const match = timeStr.match(/(\d{1,2}):\d{2}/);
      if (match) {
        const hour = parseInt(match[1], 10);
        if (!isNaN(hour)) {
          hourMap.set(hour, (hourMap.get(hour) || 0) + 1);
        }
      }
    }
  });

  // Top symbol by fill count
  let topSym = null;
  let maxSymFills = 0;
  for (const [sym, data] of symbolMap.entries()) {
    if (data.count > maxSymFills) {
      maxSymFills = data.count;
      topSym = {
        symbol: sym,
        count: data.count,
        pct: Math.round((data.count / list.length) * 100),
      };
    }
  }

  // Peak day
  let peakDay = '—';
  let maxDayFills = 0;
  for (const [d, count] of dayMap.entries()) {
    if (count > maxDayFills) {
      maxDayFills = count;
      peakDay = d;
    }
  }

  // Peak hour
  let peakHour = null;
  let maxHourFills = 0;
  for (const [h, count] of hourMap.entries()) {
    if (count > maxHourFills) {
      maxHourFills = count;
      const hStart = String(h).padStart(2, '0') + ':00';
      const hEnd = String((h + 1) % 24).padStart(2, '0') + ':00';
      peakHour = {
        label: `${hStart} - ${hEnd}`,
        count,
        pct: Math.round((count / list.length) * 100),
      };
    }
  }

  const activeDays = Math.max(dayMap.size, 1);
  const avgFillsPerDay = (list.length / activeDays).toFixed(1);
  const avgSize = Math.round(totalQty / Math.max(list.length, 1));
  const feePerShare = totalQty > 0 ? totalFees / totalQty : 0;

  return {
    count: list.length,
    totalQty,
    totalTurnover,
    totalFees,
    avgSize,
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

// ---------------------------------------------------------------- group by date
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

// ---------------------------------------------------------------- group by symbol
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
    .sort((a, b) => (b.sellNet - b.buyNet) - (a.sellNet - a.buyNet))
    .map((g) => ({
      ...g,
      datesCount: g.dates.size,
      netDiff: g.sellNet - g.buyNet,
      openQty: g.buyQty - g.sellQty,
    }));
});

// ---------------------------------------------------------------- statistics charts aggregations
const hoveredDay = ref(null);
const hoveredHour = ref(null);

const dailyChartData = computed(() => {
  return [...byDateRows.value]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((r) => ({
      date: r.date,
      count: r.count,
      qty: r.qty,
      buyQty: r.buyQty,
      sellQty: r.sellQty,
      buyGross: r.buyGross,
      sellGross: r.sellGross,
      netDiff: r.netDiff,
    }));
});

const maxDailyQty = computed(() => {
  if (!dailyChartData.value.length) return 1;
  return Math.max(...dailyChartData.value.map((d) => d.qty), 1);
});

const maxDailyCount = computed(() => {
  if (!dailyChartData.value.length) return 1;
  return Math.max(...dailyChartData.value.map((d) => d.count), 1);
});

const hourlyChartData = computed(() => {
  const hours = Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    label: `${String(i).padStart(2, '0')}:00`,
    count: 0,
    buyCount: 0,
    sellCount: 0,
    qty: 0,
  }));

  filteredTransactions.value.forEach((t) => {
    const timeStr = String(t.execTime || t.exec_time || '');
    if (!timeStr) return;
    const match = timeStr.match(/(\d{1,2}):(\d{2})/);
    if (!match) return;
    const h = parseInt(match[1], 10);
    if (h >= 0 && h < 24) {
      hours[h].count += 1;
      hours[h].qty += t.quantity || 0;
      if (t.tradeType === 'B') hours[h].buyCount += 1;
      else if (t.tradeType === 'S') hours[h].sellCount += 1;
    }
  });

  return hours.filter((h) => (h.hour >= 8 && h.hour <= 17) || h.count > 0);
});

const maxHourlyCount = computed(() => {
  if (!hourlyChartData.value.length) return 1;
  return Math.max(...hourlyChartData.value.map((h) => h.count), 1);
});

const symbolChartData = computed(() => {
  const maxS = bySymbolRows.value.length ? Math.max(...bySymbolRows.value.map((s) => s.qty), 1) : 1;
  return bySymbolRows.value.slice(0, 8).map((s) => ({
    symbol: s.symbol,
    count: s.count,
    qty: s.qty,
    pct: summary.value.totalQty > 0 ? Math.round((s.qty / summary.value.totalQty) * 100) : 0,
    barPct: Math.round((s.qty / maxS) * 100),
    netDiff: s.netDiff,
  }));
});

const sideBreakdown = computed(() => {
  const total = filteredTransactions.value.length;
  const buyC = summary.value.buyCount || 0;
  const sellC = summary.value.sellCount || 0;
  const buyQ = byDateRows.value.reduce((acc, r) => acc + r.buyQty, 0);
  const sellQ = byDateRows.value.reduce((acc, r) => acc + r.sellQty, 0);
  const totalQ = buyQ + sellQ;
  const buyGross = byDateRows.value.reduce((acc, r) => acc + r.buyGross, 0);
  const sellGross = byDateRows.value.reduce((acc, r) => acc + r.sellGross, 0);
  return {
    buyCount: buyC,
    sellCount: sellC,
    buyCountPct: total > 0 ? Math.round((buyC / total) * 100) : 0,
    sellCountPct: total > 0 ? Math.round((sellC / total) * 100) : 0,
    buyQty: buyQ,
    sellQty: sellQ,
    buyQtyPct: totalQ > 0 ? Math.round((buyQ / totalQ) * 100) : 0,
    sellQtyPct: totalQ > 0 ? Math.round((sellQ / totalQ) * 100) : 0,
    buyGross,
    sellGross,
  };
});

// ---------------------------------------------------------------- PDF Export (All Days Expanded)
const isExportingPdf = ref(false);

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
      const raw = meta.comment || meta.notes || t.comment || t.notes || '';
      return String(raw).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
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
      return t.price != null
        ? '$' + Number(t.price).toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
        : 'null';
    case 'g_amt':
      return t.g_amt != null ? fmtMoney(t.g_amt) : 'null';
    case 'n_amt':
      return t.n_amt != null ? fmtMoney(t.n_amt, 4) : 'null';
    case 'exec_time':
      return t.exec_time != null ? fmtExecTime(t.exec_time) : 'null';
    case 'comm':
      return t.comm != null ? fmtMoney(t.comm, 4) : 'null';
    case 'exch_fee':
      return t.exch_fee != null ? fmtMoney(t.exch_fee, 4) : 'null';
    case 'sec_fee':
      return t.sec_fee != null ? fmtMoney(t.sec_fee, 4) : 'null';
    case 'm_fee1':
      return t.m_fee1 != null ? fmtMoney(t.m_fee1, 4) : 'null';
    case 'm_fee4':
      return t.m_fee4 != null ? fmtMoney(t.m_fee4, 4) : 'null';
    default:
      return t[colKey] != null ? String(t[colKey]) : 'null';
  }
};

const isExportingExcel = ref(false);

const exportAllDaysExcel = async () => {
  if (!byDateRows.value.length) return;
  isExportingExcel.value = true;
  await new Promise((resolve) => setTimeout(resolve, 30));

  try {
    const wb = XLSX.utils.book_new();

    // Sheet 1: All Detailed Transactions (using current visible columns)
    const tradeHeaders = visibleTradeCols.value.map((c) => c.label);
    const allTradesData = [];
    byDateRows.value.forEach((r) => {
      r.transactions.forEach((t) => {
        allTradesData.push(visibleTradeCols.value.map((c) => formatTradeCellValue(t, c.key)));
      });
    });

    const wsTrades = XLSX.utils.aoa_to_sheet([tradeHeaders, ...allTradesData]);
    // Set column widths based on current column settings
    wsTrades['!cols'] = visibleTradeCols.value.map((c) => ({
      wch: Math.max(10, Math.min(22, Math.round((c.width || 80) / 7))),
    }));
    XLSX.utils.book_append_sheet(wb, wsTrades, 'All Transactions');

    // Sheet 2: Daily Summaries (using current visible date columns)
    const dateHeaders = visibleDateCols.value.map((c) => c.label);
    const allDaysData = byDateRows.value.map((r) =>
      visibleDateCols.value.map((c) => formatDateCellValue(r, c.key)),
    );
    const wsDays = XLSX.utils.aoa_to_sheet([dateHeaders, ...allDaysData]);
    wsDays['!cols'] = visibleDateCols.value.map((c) => ({
      wch: Math.max(12, Math.min(24, Math.round((c.width || 90) / 7))),
    }));
    XLSX.utils.book_append_sheet(wb, wsDays, 'Daily Summaries');

    const fileDate = new Date().toISOString().slice(0, 10);
    XLSX.writeFile(wb, `Trading_Transactions_All_Days_${fileDate}.xlsx`);
  } catch (err) {
    console.error('Failed to export Excel:', err);
    alert('Failed to generate Excel file: ' + (err.message || String(err)));
  } finally {
    isExportingExcel.value = false;
  }
};

const exportAllDaysPdf = async () => {
  if (!byDateRows.value.length) return;
  isExportingPdf.value = true;

  // Allow UI to render the exporting state
  await new Promise((resolve) => setTimeout(resolve, 40));

  try {
    const doc = new jsPDF({
      orientation: 'landscape',
      unit: 'pt',
      format: 'a4',
    });

    const pageWidth = doc.internal.pageSize.getWidth(); // 841.89 pt
    const pageHeight = doc.internal.pageSize.getHeight(); // 595.28 pt

    // Enhancement: Compact, controlled table width instead of full edge-to-edge
    const tableWidth = 670;
    const marginX = Math.round((pageWidth - tableWidth) / 2); // ~86 pt centered margins
    const topMargin = 26;

    // Report Header Banner (centered to match table width)
    doc.setFillColor(15, 23, 42); // dark navy #0f172a
    doc.roundedRect(marginX, topMargin, tableWidth, 40, 4, 4, 'F');

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(13);
    doc.setTextColor(255, 255, 255);
    doc.text('TRADING ACTIVITY REPORT — ALL DAYS EXPANDED', marginX + 16, topMargin + 25);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(148, 163, 184);
    const exportTime = new Date().toLocaleString();
    doc.text(
      `Generated: ${exportTime}  |  ${byDateRows.value.length} Trading Days  |  ${num(transactions.value.length)} Fills`,
      marginX + tableWidth - 16,
      topMargin + 25,
      { align: 'right' },
    );

    let currentY = topMargin + 52;

    // Loop through all days in byDateRows
    for (let dayIdx = 0; dayIdx < byDateRows.value.length; dayIdx++) {
      const r = byDateRows.value[dayIdx];

      // Page overflow check before starting a new day section
      if (currentY > pageHeight - 130) {
        doc.addPage();
        currentY = topMargin + 10;
      }

      // Date Header Section Bar (centered to match table width)
      doc.setFillColor(241, 245, 249);
      doc.roundedRect(marginX, currentY, tableWidth, 22, 3, 3, 'F');

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(10);
      doc.setTextColor(15, 23, 42);
      doc.text(
        `Trading Day: ${r.date}  ·  ${r.count} Transaction${r.count === 1 ? '' : 's'} (${r.symbolsCount} symbols, ${num(r.qty)} shares)`,
        marginX + 12,
        currentY + 15,
      );

      currentY += 28;

      // 1. Day Summary Table (using visibleDateCols) - Center-aligned with larger font
      const dateHeaders = visibleDateCols.value.map((c) => c.label);
      const dateRowData = [visibleDateCols.value.map((c) => formatDateCellValue(r, c.key))];
      const dateColStyles = Object.fromEntries(
        visibleDateCols.value.map((_, idx) => [
          idx,
          { halign: 'center' }, // text center
        ]),
      );

      autoTable(doc, {
        startY: currentY,
        head: [dateHeaders],
        body: dateRowData,
        theme: 'grid',
        tableWidth: tableWidth,
        margin: { left: marginX, right: marginX },
        styles: {
          fontSize: 9.5, // increased font size (was 7.5)
          cellPadding: 4,
          font: 'helvetica',
          textColor: [30, 41, 59],
          lineColor: [226, 232, 240],
          lineWidth: 0.5,
          halign: 'center', // center all cells
          valign: 'middle',
        },
        headStyles: {
          fillColor: [30, 41, 59],
          textColor: [241, 245, 249],
          fontStyle: 'bold',
          fontSize: 9.5,
          halign: 'center', // center all headers
        },
        columnStyles: dateColStyles,
      });

      currentY = doc.lastAutoTable.finalY + 10;

      // 2. Day Details Transactions Table (using visibleTradeCols) - Center-aligned with larger font
      const tradeHeaders = visibleTradeCols.value.map((c) => c.label);
      const tradeRowsData = r.transactions.map((t) =>
        visibleTradeCols.value.map((c) => formatTradeCellValue(t, c.key)),
      );
      const tradeColStyles = Object.fromEntries(
        visibleTradeCols.value.map((_, idx) => [
          idx,
          { halign: 'center' }, // text center
        ]),
      );

      const tradeColCount = visibleTradeCols.value.length;
      // Increased font size: 8.5pt to 10.2pt (was 6.2 to 7.8!)
      const fSize = tradeColCount > 16 ? 8.5 : tradeColCount > 12 ? 9.2 : 10.2;
      const cPad = tradeColCount > 16 ? 3 : 4;

      autoTable(doc, {
        startY: currentY,
        head: [tradeHeaders],
        body: tradeRowsData,
        theme: 'striped',
        tableWidth: tableWidth,
        margin: { left: marginX, right: marginX },
        styles: {
          fontSize: fSize,
          cellPadding: cPad,
          font: 'helvetica',
          textColor: [51, 65, 85],
          lineColor: [241, 245, 249],
          lineWidth: 0.5,
          halign: 'center', // text center
          valign: 'middle',
          overflow: 'ellipsize',
        },
        headStyles: {
          fillColor: [59, 130, 246], // accent blue
          textColor: [255, 255, 255],
          fontStyle: 'bold',
          fontSize: fSize,
          halign: 'center', // center headers
        },
        alternateRowStyles: {
          fillColor: [248, 250, 252],
        },
        columnStyles: tradeColStyles,
        didParseCell: (data) => {
          data.cell.styles.halign = 'center'; // ensure every body cell is centered
          if (data.section === 'body') {
            const col = visibleTradeCols.value[data.column.index];
            if (col) {
              if (col.key === 'trd_type') {
                if (data.cell.raw === 'B') {
                  data.cell.styles.textColor = [16, 185, 129];
                  data.cell.styles.fontStyle = 'bold';
                } else if (data.cell.raw === 'S') {
                  data.cell.styles.textColor = [239, 68, 68];
                  data.cell.styles.fontStyle = 'bold';
                }
              } else if (col.key === 'symbol') {
                data.cell.styles.fontStyle = 'bold';
                data.cell.styles.textColor = [15, 23, 42];
              } else if (col.key === 'netDiff' || col.key === 'n_amt') {
                const rawStr = String(data.cell.raw || '');
                if (rawStr.startsWith('+')) data.cell.styles.textColor = [16, 185, 129];
                else if (rawStr.startsWith('-')) data.cell.styles.textColor = [239, 68, 68];
              }
            }
          }
        },
      });

      currentY = doc.lastAutoTable.finalY + 18;
    }

    // Running Page Numbers & Footers
    const totalPages = doc.getNumberOfPages();
    for (let p = 1; p <= totalPages; p++) {
      doc.setPage(p);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      doc.text('Trading Transaction History Preview · Confidential Report', marginX, pageHeight - 14);
      doc.text(`Page ${p} of ${totalPages}`, marginX + tableWidth, pageHeight - 14, { align: 'right' });
    }

    const fileDate = new Date().toISOString().slice(0, 10);
    doc.save(`Trading_Transactions_All_Days_${fileDate}.pdf`);
  } catch (err) {
    console.error('Failed to export PDF:', err);
    alert('Failed to generate PDF: ' + (err.message || String(err)));
  } finally {
    isExportingPdf.value = false;
  }
};
</script>

<template>
  <div
    class="ts-view"
    @dragover.prevent="isDragging = true"
    @dragleave.prevent="isDragging = false"
    @drop.prevent="onDrop"
  >
    <!-- Drop Overlay -->
    <div v-if="isDragging" class="drop-overlay">
      <UploadCloud :size="48" />
      <span>Drop JSON file to preview Transaction History</span>
    </div>

    <!-- Hidden file input accessible from anywhere -->
    <input
      ref="fileInput"
      type="file"
      id="jsonFileInput"
      accept=".json,application/json,.csv,text/csv,text/plain,.xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
      multiple
      @change="onFileChange"
    />

    <!-- Floating Top-Right Action Buttons -->
    <div class="floating-actions">
      <button
        v-if="hasData"
        class="floating-btn clear-btn"
        @click="confirmClearData"
        title="Clear all stored transactions from storage"
      >
        <RotateCcw :size="16" />
      </button>
      <label
        for="jsonFileInput"
        class="floating-btn import-btn"
        :title="hasData ? 'Import / Upload trades (JSON, CSV, Excel - skips duplicates)' : 'Upload Trades'"
      >
        <UploadCloud :size="18" />
      </label>
    </div>

    <!-- Floating status toast message (if present) -->
    <div v-if="status.text" class="floating-status" :class="status.tone">
      <span>{{ status.text }}</span>
      <button class="status-close" @click="status.text = ''" title="Dismiss">
        <X :size="12" />
      </button>
    </div>

    <div class="wrap">

      <!-- ================= Empty State ================= -->
      <section v-if="!hasData" class="empty glass">
        <label for="jsonFileInput" class="dropzone">
          <div class="dz-icon"><UploadCloud :size="46" /></div>
          <h2>Drop your Trade History file here (JSON, CSV, Excel)</h2>
          <p>or click to browse. Transactions are saved permanently in local storage & IndexedDB, and duplicates are automatically skipped on re-import.</p>
        </label>
        <div class="format-spec">
          <h3>Expected Formats</h3>
          <p class="format-hint">Supports JSON Array, CSV exports (Webull, IBKR, DAS, TradeZero), and Excel (.xlsx, .xls) spreadsheets.</p>
          <pre>[
  {
    "id": 4419942,
    "systemId": "DX",
    "system_date": "2026-10-20T00:00:00",
    "tr_no": "422889671",
    "entry_type": "TRD",
    "trd_type": "S",
    "trade_dt": "2026-10-20",
    "settle_dt": null,
    "exec_time": "2026-10-20 17:30:55",
    "symbol": "WORX",
    "qty": 2,
    "price": 3.89,
    "g_amt": 7.78,
    "n_amt": 7.7746,
    "comm": 0,
    "exch_fee": null,
    "sec_fee": 0.0002,
    "descr": null,
    "m_fee1": null,
    "m_fee4": null
  }
]</pre>
          <ul>
            <li>Saved permanently in your browser (IndexedDB + LocalStorage).</li>
            <li>Re-importing automatically checks unique identifiers & execution signatures and skips duplicate trades.</li>
          </ul>
        </div>
      </section>

      <!-- ================= Data Preview Area ================= -->
      <template v-else>
        <!-- 1. Universal Filters Bar (Sticky, applies across both Table and Stats tabs) -->
        <div class="universal-filter-bar glass">
          <div class="uf-row">
            <!-- Search -->
            <div class="uf-item uf-search">
              <Search :size="14" class="muted" />
              <input
                type="text"
                v-model="searchQuery"
                placeholder="Search symbol, ID, desc..."
              />
              <button
                v-if="searchQuery"
                class="clear-input-btn"
                @click="searchQuery = ''"
                title="Clear search"
              >
                <X :size="12" />
              </button>
            </div>

            <!-- Side Filter Chips -->
            <div class="uf-item chip-group">
              <button
                class="chip"
                :class="{ on: selectedSide === 'ALL' }"
                @click="selectedSide = 'ALL'"
              >
                All Sides
              </button>
              <button
                class="chip buy-chip"
                :class="{ on: selectedSide === 'B' }"
                @click="selectedSide = 'B'"
              >
                Buys
              </button>
              <button
                class="chip sell-chip"
                :class="{ on: selectedSide === 'S' }"
                @click="selectedSide = 'S'"
              >
                Sells
              </button>
            </div>

            <!-- Symbol Select -->
            <div class="uf-item uf-select-wrap">
              <Tag :size="13" class="muted" />
              <select v-model="selectedSymbol" class="uf-select">
                <option value="ALL">All Symbols ({{ distinctSymbols.length }})</option>
                <option v-for="s in distinctSymbols" :key="s.symbol" :value="s.symbol">
                  {{ s.symbol }} ({{ s.count }})
                </option>
              </select>
            </div>

            <!-- Date Select -->
            <div class="uf-item uf-select-wrap">
              <Calendar :size="13" class="muted" />
              <select v-model="selectedDate" class="uf-select">
                <option value="ALL">All Dates ({{ distinctDates.length }})</option>
                <option v-for="d in distinctDates" :key="d" :value="d">
                  {{ d }}
                </option>
              </select>
            </div>

            <!-- Session Filter -->
            <div class="uf-item uf-select-wrap">
              <Clock :size="13" class="muted" />
              <select v-model="selectedSession" class="uf-select">
                <option value="ALL">All Sessions</option>
                <option value="REGULAR">Regular Market (9:30–16:00)</option>
                <option value="PRE">Pre-Market (&lt; 9:30)</option>
                <option value="POST">Post-Market (&gt; 16:00)</option>
              </select>
            </div>

            <!-- Min Order Size / Qty -->
            <div class="uf-item uf-select-wrap">
              <Layers :size="13" class="muted" />
              <select v-model.number="minOrderQty" class="uf-select">
                <option :value="0">All Order Sizes</option>
                <option :value="10">&ge; 10 shares</option>
                <option :value="50">&ge; 50 shares</option>
                <option :value="100">&ge; 100 shares</option>
                <option :value="500">&ge; 500 shares</option>
                <option :value="1000">&ge; 1,000 shares</option>
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
              <span class="storage-dot"></span> Persistent Storage
            </span>
          </div>
        </div>

        <!-- 2. Main Navigation Tabs (Transactions Table vs Statistics & Charts) -->
        <div class="main-tabs-nav">
          <button
            class="main-tab-btn"
            :class="{ active: mainTab === 'tables' }"
            @click="mainTab = 'tables'"
          >
            <Table :size="15" />
            <span>Transactions Table</span>
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

        <!-- ================= Tab Content 1: Tables ================= -->
        <div v-if="mainTab === 'tables'" class="main-tab-content">
          <!-- Table Toolbar (By Date / By Symbol subtabs, Expand All, Date Columns, Trades Columns, PDF Export) -->
          <div class="toolbar glass">
            <div class="tabs">
              <button
                :class="{ on: activeTab === 'by-date' }"
                @click="activeTab = 'by-date'"
              >
                By Date <em>{{ byDateRows.length }}</em>
              </button>
              <button
                :class="{ on: activeTab === 'by-symbol' }"
                @click="activeTab = 'by-symbol'"
              >
                By Symbol <em>{{ bySymbolRows.length }}</em>
              </button>
            </div>

            <div class="table-actions">
              <!-- Expand / Collapse All -->
              <button
                v-if="activeTab === 'by-date'"
                class="btn ghost small"
                @click="toggleExpandAll"
                :title="allExpanded ? 'Collapse all dates' : 'Expand all dates'"
              >
                {{ allExpanded ? 'Collapse All' : 'Expand All' }}
              </button>

              <!-- Date Columns Manager -->
              <div v-if="activeTab === 'by-date'" class="col-manager-wrapper">
                <button
                  class="btn ghost small"
                  :class="{ active: activeColDropdown === 'date' }"
                  @click.stop="toggleColDropdown('date')"
                  title="Define Date table columns: show, hide, reorder"
                >
                  <Columns :size="13" />
                  <span>Date Columns</span>
                </button>

                <div v-if="activeColDropdown === 'date'" class="col-dropdown glass" @click.stop>
                  <div class="col-dropdown-header">
                    <div class="col-dropdown-title">
                      <Columns :size="14" class="muted" />
                      <strong>Date Columns ({{ visibleDateCols.length }}/{{ dateCols.length }})</strong>
                    </div>
                    <div class="col-header-actions">
                      <button class="link-btn" @click="resetDateCols" title="Reset to defaults">
                        <RotateCcw :size="12" /> Reset
                      </button>
                      <button class="close-btn" @click="closeColDropdown">
                        <X :size="14" />
                      </button>
                    </div>
                  </div>

                  <div class="col-list">
                    <div
                      v-for="(col, idx) in dateCols"
                      :key="col.key"
                      class="col-item"
                      :class="{ inactive: !col.visible }"
                    >
                      <label class="col-label">
                        <input
                          type="checkbox"
                          v-model="col.visible"
                          :disabled="col.visible && visibleDateCols.length <= 1"
                        />
                        <span class="col-name font-mono">{{ col.label }}</span>
                      </label>
                      <div class="col-order-btns">
                        <button
                          class="order-btn"
                          :disabled="idx === 0"
                          @click="moveCol(dateCols, idx, -1)"
                          title="Move Up"
                        >
                          <ArrowUp :size="12" />
                        </button>
                        <button
                          class="order-btn"
                          :disabled="idx === dateCols.length - 1"
                          @click="moveCol(dateCols, idx, 1)"
                          title="Move Down"
                        >
                          <ArrowDown :size="12" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Trades Details Columns Manager -->
              <div v-if="activeTab === 'by-date'" class="col-manager-wrapper">
                <button
                  class="btn ghost small"
                  :class="{ active: activeColDropdown === 'trade' }"
                  @click.stop="toggleColDropdown('trade')"
                  title="Define Day Details Trades table columns: show, hide, reorder"
                >
                  <SlidersHorizontal :size="13" />
                  <span>Trades Columns</span>
                </button>

                <div v-if="activeColDropdown === 'trade'" class="col-dropdown glass" @click.stop>
                  <div class="col-dropdown-header">
                    <div class="col-dropdown-title">
                      <SlidersHorizontal :size="14" class="muted" />
                      <strong>Trades Columns ({{ visibleTradeCols.length }}/{{ tradeCols.length }})</strong>
                    </div>
                    <div class="col-header-actions">
                      <button class="link-btn" @click="resetTradeCols" title="Reset to defaults">
                        <RotateCcw :size="12" /> Reset
                      </button>
                      <button class="close-btn" @click="closeColDropdown">
                        <X :size="14" />
                      </button>
                    </div>
                  </div>

                  <div class="col-list">
                    <div
                      v-for="(col, idx) in tradeCols"
                      :key="col.key"
                      class="col-item"
                      :class="{ inactive: !col.visible }"
                    >
                      <label class="col-label">
                        <input
                          type="checkbox"
                          v-model="col.visible"
                          :disabled="col.visible && visibleTradeCols.length <= 1"
                        />
                        <span class="col-name font-mono">{{ col.label }}</span>
                      </label>
                      <div class="col-order-btns">
                        <button
                          class="order-btn"
                          :disabled="idx === 0"
                          @click="moveCol(tradeCols, idx, -1)"
                          title="Move Up"
                        >
                          <ArrowUp :size="12" />
                        </button>
                        <button
                          class="order-btn"
                          :disabled="idx === tradeCols.length - 1"
                          @click="moveCol(tradeCols, idx, 1)"
                          title="Move Down"
                        >
                          <ArrowDown :size="12" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Export All Days to Excel (.xlsx) Button -->
              <button
                v-if="activeTab === 'by-date'"
                class="btn ghost small export-excel-btn"
                :disabled="isExportingExcel || !byDateRows.length"
                @click="exportAllDaysExcel"
                title="Export all days expanded with current column layout to an Excel (.xlsx) file"
              >
                <FileSpreadsheet :size="13" />
                <span>{{ isExportingExcel ? 'Exporting Excel...' : 'Export Excel (XLSX)' }}</span>
              </button>

              <!-- Export All Days to PDF Button -->
              <button
                v-if="activeTab === 'by-date'"
                class="btn primary small export-pdf-btn"
                :disabled="isExportingPdf || !byDateRows.length"
                @click="exportAllDaysPdf"
                title="Export all days expanded with current column layout to a single PDF"
              >
                <FileDown :size="13" />
                <span>{{ isExportingPdf ? 'Exporting PDF...' : 'Export All Days (PDF)' }}</span>
              </button>
            </div>
          </div>

        <!-- Tab 1: By Date Table with Expandable Transactions -->
        <section v-if="activeTab === 'by-date'" class="panel glass">
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th
                    v-for="col in visibleDateCols"
                    :key="col.key"
                    :class="[col.align === 'l' ? 'l' : '', activeResizeCol === col.key ? 'resizing' : '']"
                    :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                  >
                    <span class="th-content">{{ col.label }}</span>
                    <span
                      class="col-resizer"
                      :class="{ active: activeResizeCol === col.key }"
                      @mousedown.stop.prevent="startColResize($event, col)"
                      @dblclick.stop="resetSingleColWidth(col, defaultDateCols)"
                      title="Drag to resize column (double-click to reset)"
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

                  <!-- Expanded rows: Trades & Executions for this date -->
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
                            <span class="anomaly-legend-pill">
                              <span class="legend-dot-red"></span> Light Red = AVG Down / Extra Buy
                            </span>
                          </div>
                        </div>

                        <!-- Trades List: Each Trade is grouped and framed in its own distinct border -->
                        <div class="trades-cards-stack">
                          <div
                            v-for="trade in r.trades"
                            :key="trade.tradeId"
                            class="trade-card-wrapper"
                            :class="{ 'has-anomaly': trade.hasAnomaly }"
                          >
                            <!-- Trade Card Header -->
                            <div
                              class="trade-card-header clickable-trade-header"
                              @click="openEditOffcanvas(trade)"
                              title="Click to edit trade setup, watched level, screenshots and comment"
                            >
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
                                  title="Edit setup type, watched level, screenshots and review notes"
                                >
                                  <Edit3 :size="13" />
                                  <span>Edit</span>
                                </button>
                              </div>
                            </div>

                            <!-- Executions Table for this Trade -->
                            <div class="trade-table-wrap">
                              <table class="tbl inner">
                                <thead>
                                  <tr>
                                    <th
                                      v-for="col in visibleTradeCols"
                                      :key="col.key"
                                      :class="[col.align, activeResizeCol === col.key ? 'resizing' : '']"
                                      :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                                    >
                                      <span class="th-content">{{ col.label }}</span>
                                      <span
                                        class="col-resizer"
                                        :class="{ active: activeResizeCol === col.key }"
                                        @mousedown.stop.prevent="startColResize($event, col)"
                                        @dblclick.stop="resetSingleColWidth(col, defaultTradeCols)"
                                        title="Drag to resize column (double-click to reset)"
                                      ></span>
                                    </th>
                                    <th class="spacer-col"></th>
                                  </tr>
                                </thead>
                                <tbody>
                                  <tr
                                    v-for="(t, idx) in trade.executions"
                                    :key="t.id ?? (t.tr_no ? t.tr_no + '_' + idx : idx)"
                                    :class="{ 'anomaly-row': t.isAnomaly }"
                                    class="execution-row-clickable"
                                    @click="openEditOffcanvas(trade)"
                                    title="Click row to edit trade setup, watched level, screenshots and comment"
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

                                      <!-- Images Button -->
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

                                      <!-- Actions (Edit button) -->
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
                                        <span :class="t.exec_time != null ? '' : 'null-val'" :title="t.exec_time ? String(t.exec_time) : ''">
                                          {{ t.exec_time != null ? fmtExecTime(t.exec_time) : 'null' }}
                                        </span>
                                      </template>

                                      <!-- Default Key -->
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

        <!-- Tab 3: By Symbol Table -->
        <section v-else-if="activeTab === 'by-symbol'" class="panel glass">
          <div class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th
                    v-for="col in symbolCols"
                    :key="col.key"
                    :class="[col.align === 'l' ? 'l' : '', activeResizeCol === col.key ? 'resizing' : '']"
                    :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
                  >
                    <span class="th-content">{{ col.label }}</span>
                    <span
                      class="col-resizer"
                      :class="{ active: activeResizeCol === col.key }"
                      @mousedown.stop.prevent="startColResize($event, col)"
                      @dblclick.stop="resetSingleColWidth(col, defaultSymbolCols)"
                      title="Drag to resize column (double-click to reset)"
                    ></span>
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
                      col.key === 'fees' ? 'muted' : '',
                    ]"
                    :style="{ width: col.width + 'px', minWidth: col.width + 'px', maxWidth: col.width + 'px' }"
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

        <!-- ================= Tab Content 2: Statistics & Charts ================= -->
        <div v-else-if="mainTab === 'stats'" class="main-tab-content stats-view-container">
          <!-- The 6 KPI Cards -->
          <section class="kpis">
            <!-- Card 1: Volume & Execution Count -->
            <div class="kpi glass">
              <span class="k-label">Volume &amp; Fills</span>
              <strong class="k-value">{{ num(summary.totalQty) }} <small class="unit">sh</small></strong>
              <span class="k-sub">{{ num(summary.count) }} fills ({{ summary.buyCount }}B / {{ summary.sellCount }}S)</span>
            </div>

            <!-- Card 2: Daily Pacing (Overtrading detection) -->
            <div class="kpi glass">
              <span class="k-label">Daily Pace</span>
              <strong class="k-value">{{ summary.avgFillsPerDay }} <small class="unit">fills/day</small></strong>
              <span class="k-sub">Peak: {{ summary.maxDayFills }} fills ({{ summary.peakDay }})</span>
            </div>

            <!-- Card 3: Position Sizing Consistency -->
            <div class="kpi glass">
              <span class="k-label">Avg Order Size</span>
              <strong class="k-value">{{ num(summary.avgSize) }} <small class="unit">sh</small></strong>
              <span class="k-sub">Range: {{ num(summary.minQty) }} – {{ num(summary.maxQty) }} sh</span>
            </div>

            <!-- Card 4: Symbol Focus vs Dispersion -->
            <div class="kpi glass">
              <span class="k-label">Symbol Focus</span>
              <strong class="k-value font-mono">
                {{ summary.topSymbol ? summary.topSymbol.symbol : '—' }}
                <small v-if="summary.topSymbol" class="unit">{{ summary.topSymbol.pct }}%</small>
              </strong>
              <span class="k-sub">{{ summary.symbolsCount }} unique ticker{{ summary.symbolsCount === 1 ? '' : 's' }} traded</span>
            </div>

            <!-- Card 5: Peak Trading Window -->
            <div class="kpi glass">
              <span class="k-label">Peak Time Window</span>
              <strong class="k-value font-mono">{{ summary.peakHour ? summary.peakHour.label : '—' }}</strong>
              <span class="k-sub">{{ summary.peakHour ? summary.peakHour.pct + '% of fills (' + summary.peakHour.count + ' trades)' : 'Based on exec_time' }}</span>
            </div>

            <!-- Card 6: Total Execution Cost & Drag -->
            <div class="kpi glass hero">
              <span class="k-label">Fee Drag &amp; Cost</span>
              <strong class="k-value">{{ fmtMoney(summary.totalFees, summary.totalFees < 1 ? 4 : 2) }}</strong>
              <span class="k-sub">{{ summary.feePerShare > 0 ? '$' + summary.feePerShare.toFixed(4) + '/sh' : '0.00% fee' }} · {{ fmtMoney(summary.totalTurnover) }} gross</span>
            </div>
          </section>

          <!-- Interactive Analytics Charts Grid -->
          <section class="charts-grid">
            <!-- Chart 1: Daily Volume & Shares Breakdown -->
            <div class="chart-card glass">
              <div class="chart-header">
                <div class="chart-title">
                  <TrendingUp :size="16" class="chart-icon" />
                  <strong>Daily Trading Volume &amp; Shares</strong>
                </div>
                <div class="chart-legend">
                  <span class="legend-item"><span class="legend-dot buy"></span>Buy Qty</span>
                  <span class="legend-item"><span class="legend-dot sell"></span>Sell Qty</span>
                </div>
              </div>
              <div class="chart-body">
                <div v-if="!dailyChartData.length" class="chart-empty">No trading day data for selected filters</div>
                <div v-else class="bar-chart-container">
                  <div
                    v-for="d in dailyChartData"
                    :key="d.date"
                    class="bar-group"
                    @mouseenter="hoveredDay = d"
                    @mouseleave="hoveredDay = null"
                  >
                    <div class="bars-pair">
                      <div
                        class="chart-bar buy-bar"
                        :style="{ height: Math.max(4, Math.round((d.buyQty / maxDailyQty) * 150)) + 'px' }"
                        :title="d.date + ' Buys: ' + num(d.buyQty) + ' sh'"
                      ></div>
                      <div
                        class="chart-bar sell-bar"
                        :style="{ height: Math.max(4, Math.round((d.sellQty / maxDailyQty) * 150)) + 'px' }"
                        :title="d.date + ' Sells: ' + num(d.sellQty) + ' sh'"
                      ></div>
                    </div>
                    <span class="bar-label">{{ d.date.slice(5) }}</span>
                  </div>
                </div>
                <!-- Hover inspection panel for Daily Chart -->
                <div class="chart-inspector" v-if="hoveredDay">
                  <span class="ci-date"><b>{{ hoveredDay.date }}</b></span>
                  <span>Total: <b>{{ num(hoveredDay.qty) }}</b> sh ({{ num(hoveredDay.count) }} fills)</span>
                  <span class="pos">Buys: {{ num(hoveredDay.buyQty) }} sh ({{ fmtMoney(hoveredDay.buyGross) }})</span>
                  <span class="neg">Sells: {{ num(hoveredDay.sellQty) }} sh ({{ fmtMoney(hoveredDay.sellGross) }})</span>
                  <span :class="cls(hoveredDay.netDiff)">Net Diff: <b>{{ fmtSigned(hoveredDay.netDiff) }}</b></span>
                </div>
                <div class="chart-inspector-placeholder" v-else>
                  <span class="muted text-xs">Hover over any day bar above to inspect buy/sell fill details</span>
                </div>
              </div>
            </div>

            <!-- Chart 2: Intraday Execution Distribution (Hourly Activity) -->
            <div class="chart-card glass">
              <div class="chart-header">
                <div class="chart-title">
                  <Clock :size="16" class="chart-icon" />
                  <strong>Intraday Hourly Execution Frequency</strong>
                </div>
                <span class="chart-hint">Based on exec_time</span>
              </div>
              <div class="chart-body">
                <div v-if="!hourlyChartData.length" class="chart-empty">No time data available</div>
                <div v-else class="bar-chart-container hourly">
                  <div
                    v-for="h in hourlyChartData"
                    :key="h.hour"
                    class="bar-group"
                    @mouseenter="hoveredHour = h"
                    @mouseleave="hoveredHour = null"
                  >
                    <div class="bars-stacked">
                      <div
                        class="chart-bar hour-bar"
                        :style="{ height: Math.max(4, Math.round((h.count / maxHourlyCount) * 150)) + 'px' }"
                      >
                        <span v-if="h.count > 0" class="bar-val-badge">{{ h.count }}</span>
                      </div>
                    </div>
                    <span class="bar-label">{{ h.label }}</span>
                  </div>
                </div>
                <!-- Hover inspector for Hourly Chart -->
                <div class="chart-inspector" v-if="hoveredHour">
                  <span class="ci-date"><b>{{ hoveredHour.label }} Window</b></span>
                  <span>Fills: <b>{{ hoveredHour.count }}</b> ({{ hoveredHour.buyCount }} Buys / {{ hoveredHour.sellCount }} Sells)</span>
                  <span>Volume: <b>{{ num(hoveredHour.qty) }}</b> shares</span>
                </div>
                <div class="chart-inspector-placeholder" v-else>
                  <span class="muted text-xs">Hover over hourly bars to view intraday fill distribution</span>
                </div>
              </div>
            </div>

            <!-- Chart 3: Top Traded Symbols Volume & Net Difference -->
            <div class="chart-card glass">
              <div class="chart-header">
                <div class="chart-title">
                  <Activity :size="16" class="chart-icon" />
                  <strong>Top Traded Symbols (Share Volume)</strong>
                </div>
                <span class="chart-hint">Top 8 tickers</span>
              </div>
              <div class="chart-body horiz-list">
                <div v-if="!symbolChartData.length" class="chart-empty">No symbol data available</div>
                <div v-else class="symbol-bars-list">
                  <div v-for="s in symbolChartData" :key="s.symbol" class="sym-row">
                    <div class="sym-meta">
                      <strong class="sym-ticker font-mono">{{ s.symbol }}</strong>
                      <span class="sym-stats muted">{{ num(s.count) }} fills · {{ num(s.qty) }} sh ({{ s.pct }}%)</span>
                      <span class="sym-diff" :class="cls(s.netDiff)">{{ fmtSigned(s.netDiff) }}</span>
                    </div>
                    <div class="sym-track">
                      <div class="sym-fill" :style="{ width: s.barPct + '%' }"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Chart 4: Order Flow & Execution Balance -->
            <div class="chart-card glass">
              <div class="chart-header">
                <div class="chart-title">
                  <DollarSign :size="16" class="chart-icon" />
                  <strong>Order Flow &amp; Execution Balance</strong>
                </div>
                <span class="chart-hint">Buy vs Sell Ratios</span>
              </div>
              <div class="chart-body order-flow-body">
                <div class="flow-metric">
                  <div class="flow-header">
                    <span>Fill Count Distribution</span>
                    <span><b>{{ sideBreakdown.buyCount }}</b> Buys ({{ sideBreakdown.buyCountPct }}%) vs <b>{{ sideBreakdown.sellCount }}</b> Sells ({{ sideBreakdown.sellCountPct }}%)</span>
                  </div>
                  <div class="flow-bar-dual">
                    <div class="flow-segment buy" :style="{ width: sideBreakdown.buyCountPct + '%' }"></div>
                    <div class="flow-segment sell" :style="{ width: sideBreakdown.sellCountPct + '%' }"></div>
                  </div>
                </div>

                <div class="flow-metric">
                  <div class="flow-header">
                    <span>Share Volume Balance</span>
                    <span><b>{{ num(sideBreakdown.buyQty) }}</b> Buy sh ({{ sideBreakdown.buyQtyPct }}%) vs <b>{{ num(sideBreakdown.sellQty) }}</b> Sell sh ({{ sideBreakdown.sellQtyPct }}%)</span>
                  </div>
                  <div class="flow-bar-dual">
                    <div class="flow-segment buy" :style="{ width: sideBreakdown.buyQtyPct + '%' }"></div>
                    <div class="flow-segment sell" :style="{ width: sideBreakdown.sellQtyPct + '%' }"></div>
                  </div>
                </div>

                <div class="flow-cards">
                  <div class="flow-mini-card buy-tint">
                    <span class="muted text-xs">Total Buy Turnover</span>
                    <strong class="flow-val pos">{{ fmtMoney(sideBreakdown.buyGross) }}</strong>
                    <span class="muted text-xs">{{ num(sideBreakdown.buyQty) }} shares bought</span>
                  </div>
                  <div class="flow-mini-card sell-tint">
                    <span class="muted text-xs">Total Sell Turnover</span>
                    <strong class="flow-val neg">{{ fmtMoney(sideBreakdown.sellGross) }}</strong>
                    <span class="muted text-xs">{{ num(sideBreakdown.sellQty) }} shares sold</span>
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

    <!-- Offcanvas Drawer -->
    <aside class="offcanvas-drawer" :class="{ open: isOffcanvasOpen }">
      <div v-if="editingTrade" class="offcanvas-content">
        <!-- Drawer Header -->
        <div class="offcanvas-header">
          <div class="offcanvas-title-group">
            <div class="offcanvas-badge-row">
              <span class="offcanvas-tag">Trade #{{ editingTrade.tradeNumber }}</span>
              <span class="offcanvas-symbol font-mono">{{ editingTrade.symbol }}</span>
              <span class="offcanvas-dir-badge" :class="editingTrade.direction.toLowerCase()">
                {{ editingTrade.direction }}
              </span>
              <span class="offcanvas-status-badge" :class="editingTrade.status.toLowerCase()">
                {{ editingTrade.status === 'CLOSED' ? 'Flat (Closed)' : `${editingTrade.openQty} sh open` }}
              </span>
            </div>
            <div class="offcanvas-sub">
              <span>{{ editingTrade.date }}</span>
              <span>·</span>
              <span>{{ editingTrade.entryTime }} → {{ editingTrade.exitTime || 'Open' }}</span>
              <span>·</span>
              <span :class="cls(editingTrade.netPnL)">{{ fmtSigned(editingTrade.netPnL) }}</span>
            </div>
          </div>
          <button class="offcanvas-close-btn" @click="closeOffcanvas" title="Close (Esc)">
            <X :size="18" />
          </button>
        </div>

        <!-- Drawer Body -->
        <div class="offcanvas-body">
          <!-- Section 1: Setup / Strategy Type -->
          <div class="form-group">
            <label class="form-label">
              <span>Setup Type</span>
              <span class="label-hint">Preset or custom catalyst</span>
            </label>
            <div class="setup-presets-grid">
              <button
                type="button"
                v-for="preset in SETUP_PRESETS"
                :key="preset"
                class="preset-chip-btn"
                :class="{ active: offcanvasForm.setupType.toLowerCase() === preset.toLowerCase() }"
                @click="selectPresetSetup(preset)"
              >
                {{ preset }}
              </button>
            </div>
            <div class="custom-input-wrap">
              <input
                type="text"
                v-model="offcanvasForm.setupType"
                class="form-input"
                placeholder="Or type custom setup (e.g. 9ema, high of day, round figure...)"
              />
            </div>
          </div>

          <!-- Section 2: Watched Value / Key Level -->
          <div class="form-group">
            <div class="form-label-row">
              <label class="form-label">
                <span>Watched Key Level</span>
                <span class="label-hint">Price or technical level watched for trigger</span>
              </label>
              <button
                v-if="editingTrade.avgEntryPrice"
                type="button"
                class="btn-quick-fill"
                @click="fillAvgPriceAsWatched"
                title="Auto-fill average entry price"
              >
                Use Entry (${{ Number(editingTrade.avgEntryPrice).toFixed(2) }})
              </button>
            </div>
            <input
              type="text"
              v-model="offcanvasForm.watchedValue"
              class="form-input font-mono"
              placeholder="e.g. 152.50, HOD $14.80, Whole Dollar $150.00..."
            />
          </div>

          <!-- Section 3: Comment -->
          <div class="form-group">
            <label class="form-label">
              <MessageSquare :size="13" class="accent-icon" />
              <span>Comment</span>
              <span class="label-hint">Execution takeaway or key observation</span>
            </label>
            <input
              type="text"
              v-model="offcanvasForm.comment"
              class="form-input"
              placeholder="e.g. Good patience on 9 EMA, followed plan, trimmed at HOD..."
            />
          </div>

          <!-- Section 4: Screenshots / Image Attachments -->
          <div class="form-group">
            <div class="form-label-row">
              <label class="form-label">
                <span>Screenshots & Charts</span>
                <span class="label-hint">({{ offcanvasForm.images.length }} attached)</span>
              </label>
              <label class="btn-upload-label" for="tradeImageInput">
                <Plus :size="13" />
                <span>Upload Screenshot</span>
              </label>
              <input
                id="tradeImageInput"
                type="file"
                accept="image/*"
                multiple
                class="hidden-file-input"
                @change="handleImageUpload"
              />
            </div>

            <div class="clipboard-paste-tip">
              <Camera :size="13" />
              <span>Tip: You can press <b>Ctrl + V</b> anywhere to paste chart screenshots directly from clipboard!</span>
            </div>

            <!-- Image Gallery Grid -->
            <div v-if="offcanvasForm.images.length" class="offcanvas-gallery">
              <div
                v-for="(img, idx) in offcanvasForm.images"
                :key="idx"
                class="gallery-thumb-card"
              >
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
              <Camera :size="26" class="muted" />
              <p>No screenshots attached yet.</p>
              <small>Click "Upload Screenshot" above or paste (Ctrl+V) from clipboard.</small>
            </div>
          </div>

          <!-- Section 4: Trade Notes & Review -->
          <div class="form-group">
            <label class="form-label">
              <span>Trade Notes</span>
              <span class="label-hint">Execution review, thesis, mistakes (Rich HTML Editor)</span>
            </label>
            <HtmlEditor
              v-model="offcanvasForm.notes"
              placeholder="Why did you take this trade? Did you respect your stop? Did you average down improperly?..."
              min-height="120px"
            />
          </div>

          <!-- Section 5: Executions Breakdown inside this Trade -->
          <div class="form-group">
            <label class="form-label">
              <span>Execution Fills ({{ editingTrade.executions.length }})</span>
            </label>
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
        </div>

        <!-- Drawer Footer -->
        <div class="offcanvas-footer">
          <button type="button" class="btn ghost" @click="closeOffcanvas">Cancel</button>
          <button type="button" class="btn primary save-meta-btn" :disabled="isSavingMeta" @click="saveOffcanvas">
            <Check :size="14" />
            <span>{{ isSavingMeta ? 'Saving...' : 'Save Trade Setup' }}</span>
          </button>
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
.ts-view {
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
  backdrop-filter: blur(14px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
}

.muted { color: var(--muted); }
.pos { color: var(--win); }
.neg { color: var(--loss); }
.amber { color: var(--amber); }
.bold { font-weight: 600; }
.font-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.8rem; }

/* ---------- Drop overlay ---------- */
.drop-overlay {
  position: fixed; inset: 0; z-index: 9999; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;
  background: rgba(11, 17, 32, 0.92); border: 3px dashed var(--accent); color: var(--accent); font-size: 1.3rem; font-weight: 600;
  pointer-events: none;
}

/* ---------- Floating Top-Right Action Buttons & Status Toast ---------- */
.floating-actions {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 8px;
}
.floating-btn,
.floating-import-btn {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(255, 255, 255, 0.18);
}
.floating-btn.import-btn,
.floating-import-btn {
  background: linear-gradient(135deg, #3b82f6, #4f46e5);
  color: #fff;
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
}
.floating-btn.import-btn:hover,
.floating-import-btn:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
}
.floating-btn.clear-btn {
  background: rgba(30, 41, 59, 0.85);
  color: #94a3b8;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(8px);
}
.floating-btn.clear-btn:hover {
  transform: translateY(-2px);
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(239, 68, 68, 0.15);
}
.floating-status {
  position: absolute;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
}
.floating-status.good {
  background: rgba(16, 185, 129, 0.2);
  border: 1px solid rgba(52, 211, 153, 0.4);
  color: #34d399;
}
.floating-status.bad {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(248, 113, 113, 0.4);
  color: #f87171;
}
.floating-status.muted {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.3);
  color: #cbd5e1;
}
.storage-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  font-weight: 600;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.25);
  padding: 3px 8px;
  border-radius: 9999px;
  letter-spacing: 0.02em;
}
.storage-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #38bdf8;
  box-shadow: 0 0 8px #38bdf8;
  display: inline-block;
}
.status-close {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.7;
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
}
.status-close:hover { opacity: 1; }

input[type='file'] { display: none; }
.btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 8px;
  font-size: 0.82rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); transition: all 0.15s;
}
.btn.primary {
  background: linear-gradient(135deg, #3b82f6, #4f46e5); color: #fff; border-color: transparent;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}
.btn.primary:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(59, 130, 246, 0.45); }
.btn.ghost { background: rgba(255, 255, 255, 0.05); color: var(--muted); }
.btn.ghost:hover { color: var(--text); border-color: rgba(255, 255, 255, 0.2); }
.export-pdf-btn {
  background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
  color: #fff !important;
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.35);
}
.export-pdf-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.5);
  transform: translateY(-1px);
}
.export-pdf-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
.export-excel-btn {
  background: rgba(16, 185, 129, 0.12) !important;
  color: #34d399 !important;
  border: 1px solid rgba(52, 211, 153, 0.3) !important;
}
.export-excel-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.22) !important;
  border-color: rgba(52, 211, 153, 0.5) !important;
  color: #6ee7b7 !important;
  transform: translateY(-1px);
}
.export-excel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* ---------- Universal Filter Bar (Sticky across tabs) ---------- */
.universal-filter-bar {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: sticky;
  top: 0;
  z-index: 45;
}
.uf-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.uf-item {
  display: flex;
  align-items: center;
}
.uf-search {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 5px 10px;
  gap: 6px;
}
.uf-search input {
  background: transparent;
  border: none;
  color: var(--text);
  font: inherit;
  font-size: 0.82rem;
  outline: none;
  width: 155px;
}
.clear-input-btn {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 0;
  display: grid;
  place-items: center;
}
.clear-input-btn:hover { color: var(--text); }

.buy-chip.on {
  background: rgba(16, 185, 129, 0.22) !important;
  color: #34d399 !important;
}
.sell-chip.on {
  background: rgba(239, 68, 68, 0.22) !important;
  color: #f87171 !important;
}

.uf-select-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px 8px;
}
.uf-select {
  background: transparent;
  border: none;
  color: var(--text);
  font: inherit;
  font-size: 0.78rem;
  outline: none;
  color-scheme: dark;
  cursor: pointer;
}
.uf-select option {
  background: #151d30;
  color: #f1f5f9;
}
.uf-reset-btn {
  margin-left: auto;
}
.uf-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.74rem;
  color: var(--muted);
  padding: 0 4px;
}
.uf-counter b {
  color: var(--text);
}
.active-badge {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 600;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

/* ---------- Main Navigation Tabs (Table vs Statistics & Charts) ---------- */
.main-tabs-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(15, 23, 42, 0.6);
  padding: 4px;
  border-radius: 10px;
  border: 1px solid var(--border);
  width: fit-content;
}
.main-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  border-radius: 7px;
  font-size: 0.85rem;
  font-weight: 600;
  background: transparent;
  border: 1px solid transparent;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s ease;
}
.main-tab-btn:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.04);
}
.main-tab-btn.active {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
}
.tab-badge {
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.2);
  padding: 1px 7px;
  border-radius: 999px;
  font-weight: 700;
}
.main-tab-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ---------- Empty State ---------- */
.empty {
  padding: 24px;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 22px;
}
.dropzone {
  display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 10px; padding: 48px 24px;
  border: 2px dashed rgba(59, 130, 246, 0.4); border-radius: 12px; cursor: pointer; transition: all 0.2s; background: rgba(59, 130, 246, 0.04);
}
.dropzone:hover { background: rgba(59, 130, 246, 0.08); border-color: var(--accent); }
.dz-icon { color: var(--accent); }
.dropzone h2 { margin: 0; font-size: 1.2rem; font-weight: 600; }
.dropzone p { margin: 0; color: var(--muted); font-size: 0.84rem; max-width: 400px; }
.format-spec h3 { margin: 0 0 8px; font-size: 0.95rem; }
.format-hint { font-size: 0.78rem; color: var(--muted); margin: 0 0 10px; line-height: 1.4; }
.format-spec pre {
  background: rgba(0, 0, 0, 0.35); border: 1px solid var(--border); border-radius: 8px; padding: 12px;
  font-size: 0.72rem; color: #cbd5e1; overflow-x: auto; margin: 0 0 10px;
}
.format-spec ul { margin: 0; padding-left: 18px; color: var(--muted); font-size: 0.82rem; display: flex; flex-direction: column; gap: 4px; }

/* ---------- Summary Cards ---------- */
.kpis {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}
.kpi {
  padding: 13px 15px; display: flex; flex-direction: column; gap: 2px; border-radius: 12px;
}
.k-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); font-weight: 600; }
.k-value { font-size: 1.45rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.k-value .unit { font-size: 0.82rem; font-weight: 500; color: var(--muted); margin-left: 2px; }
.k-sub { font-size: 0.74rem; color: var(--muted); }
.kpi.hero { background: linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(30, 41, 59, 0.6)); }

/* ---------- Toolbar ---------- */
.toolbar {
  position: relative;
  z-index: 50;
  padding: 10px 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.tabs { display: flex; align-items: center; gap: 4px; }
.tabs button {
  background: none; border: none; color: var(--muted); font: inherit; font-size: 0.85rem; font-weight: 600;
  padding: 8px 14px; cursor: pointer; border-radius: 8px; transition: all 0.15s;
}
.tabs button:hover { color: var(--text); }
.tabs button.on { background: rgba(59, 130, 246, 0.18); color: #60a5fa; }
.tabs em { font-style: normal; font-size: 0.7rem; background: rgba(255, 255, 255, 0.08); padding: 1px 7px; border-radius: 999px; margin-left: 5px; }

.filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search-box {
  display: flex; align-items: center; gap: 6px; background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border);
  border-radius: 8px; padding: 5px 9px;
}
.search-box input {
  background: transparent; border: none; color: var(--text); font: inherit; font-size: 0.82rem; outline: none; width: 140px;
}
.chip-group { display: flex; background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border); border-radius: 8px; padding: 2px; }
.chip { background: none; border: none; color: var(--muted); padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 0.75rem; font-weight: 600; }
.chip.on { background: rgba(59, 130, 246, 0.22); color: #60a5fa; }
.select-box {
  background: rgba(255, 255, 255, 0.05); color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; padding: 5px 9px; font: inherit; font-size: 0.8rem; outline: none; color-scheme: dark;
}

/* ---------- Table ---------- */
.panel { padding: 14px; border-radius: 12px; }
.tbl-wrap { overflow-x: auto; max-height: 640px; }
.tbl { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: 0.82rem; }
.tbl th {
  text-align: right; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted);
  font-weight: 600; padding: 8px 12px 8px 8px; white-space: nowrap; border-bottom: 1px solid var(--border);
  border-right: 1px solid rgba(255, 255, 255, 0.14);
  position: sticky; top: 0; background: #131c2f; z-index: 2;
  overflow: visible; box-sizing: border-box; user-select: none;
}
.tbl td {
  text-align: right; padding: 8px 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; box-sizing: border-box;
}
.tbl tr:hover td { background: rgba(255, 255, 255, 0.03); }
.tbl .l { text-align: left; }
.tbl .c { text-align: center; }

.th-content {
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  vertical-align: middle;
}

.col-resizer {
  position: absolute;
  top: 0;
  right: -5px;
  bottom: 0;
  width: 9px;
  cursor: col-resize;
  user-select: none;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
}
.col-resizer::after {
  content: '';
  position: absolute;
  top: 15%;
  bottom: 15%;
  left: 4px;
  width: 2px;
  background: transparent;
  border-radius: 1px;
  transition: background 0.15s, box-shadow 0.15s;
}
.col-resizer:hover::after,
.col-resizer.active::after {
  background: #3b82f6;
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.85);
}
.tbl th.resizing,
.tbl.inner th.resizing {
  background: rgba(59, 130, 246, 0.16) !important;
}

:global(body.resizing-col) {
  cursor: col-resize !important;
  user-select: none !important;
}

.spacer-col {
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  padding: 0 !important;
  border-right: none !important;
  border-bottom: 1px solid var(--border);
}
.clickable-row .spacer-col,
.tbl.inner .spacer-col {
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.badge {
  display: inline-block; font-size: 0.68rem; font-weight: 700; padding: 1px 7px; border-radius: 4px;
}
.badge.buy { background: rgba(52, 211, 153, 0.15); color: var(--win); border: 1px solid rgba(52, 211, 153, 0.3); }
.badge.sell { background: rgba(248, 113, 113, 0.15); color: var(--loss); border: 1px solid rgba(248, 113, 113, 0.3); }

/* ---------- Expandable Rows & Detail Tables ---------- */
.clickable-row {
  cursor: pointer;
  transition: background 0.15s;
}
.clickable-row:hover td {
  background: rgba(255, 255, 255, 0.04) !important;
}
.clickable-row.open td {
  background: rgba(59, 130, 246, 0.08) !important;
}
.chev {
  vertical-align: -2px;
  margin-right: 6px;
  color: var(--muted);
}
.detail-row > td {
  padding: 0 !important;
  background: rgba(0, 0, 0, 0.3) !important;
  border-right: none !important;
}
.btn.small {
  padding: 4px 10px;
  font-size: 0.75rem;
}
.null-val {
  color: rgba(148, 163, 184, 0.45);
  font-style: italic;
  font-size: 0.75rem;
}
.inner-wrap {
  padding: 12px 14px 16px 20px;
  border-left: 3px solid var(--accent);
  margin: 6px 0 6px 8px;
  background: rgba(15, 23, 42, 0.55);
  border-radius: 0 8px 8px 0;
  overflow-x: auto;
  max-width: 100%;
  box-sizing: border-box;
}
.inner-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 0.8rem;
}
.tbl.inner {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
}
.tbl.inner th {
  background: rgba(11, 17, 32, 0.7) !important;
  position: static;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.72rem;
  text-transform: none;
  letter-spacing: normal;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  border-right: 1px solid rgba(255, 255, 255, 0.14);
  color: #93c5fd;
  padding: 6px 10px 6px 8px;
  overflow: visible;
  white-space: nowrap;
  box-sizing: border-box;
  user-select: none;
}
.tbl.inner td {
  font-size: 0.78rem;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-sizing: border-box;
}

/* ---------- Column Manager Dropdowns ---------- */
.col-manager-wrapper {
  position: relative;
  display: inline-block;
  z-index: 60;
}
.btn.ghost.active {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border-color: rgba(59, 130, 246, 0.4);
}
.col-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 290px;
  max-height: 440px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  background: #151d30;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 10px;
  box-shadow: 0 16px 45px rgba(0, 0, 0, 0.7);
}
.col-dropdown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
}
.col-dropdown-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 0.8rem;
  color: var(--text);
}
.col-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.link-btn {
  background: none;
  border: none;
  color: #60a5fa;
  font-size: 0.72rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 5px;
  border-radius: 4px;
}
.link-btn:hover {
  background: rgba(96, 165, 250, 0.15);
}
.close-btn {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 2px;
  border-radius: 4px;
}
.close-btn:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.08);
}
.col-list {
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 350px;
}
.col-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid transparent;
  transition: all 0.15s;
}
.col-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.06);
}
.col-item.inactive {
  opacity: 0.5;
}
.col-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.78rem;
  user-select: none;
  flex: 1;
}
.col-label input[type='checkbox'] {
  accent-color: var(--accent);
  cursor: pointer;
  width: 14px;
  height: 14px;
}
.col-name {
  color: var(--text);
}
.col-order-btns {
  display: flex;
  align-items: center;
  gap: 2px;
}
.order-btn {
  background: transparent;
  border: 1px solid transparent;
  color: var(--muted);
  border-radius: 4px;
  padding: 3px 5px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.15s;
}
.order-btn:hover:not(:disabled) {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
}
.order-btn:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

/* ---------- Statistics & Charts Tab ---------- */
.stats-view-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.chart-card {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-radius: 12px;
}
.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding-bottom: 8px;
}
.chart-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  color: var(--text);
}
.chart-icon {
  color: #60a5fa;
}
.chart-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 0.72rem;
  color: var(--muted);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}
.legend-dot.buy { background: #34d399; }
.legend-dot.sell { background: #f87171; }
.chart-hint {
  font-size: 0.72rem;
  color: var(--muted);
}
.chart-body {
  position: relative;
  min-height: 210px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.chart-empty {
  display: grid;
  place-items: center;
  height: 160px;
  color: var(--muted);
  font-size: 0.82rem;
  font-style: italic;
}
.bar-chart-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 180px;
  padding: 0 4px;
  overflow-x: auto;
}
.bar-chart-container.hourly {
  gap: 6px;
}
.bar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 28px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.bar-group:hover {
  opacity: 0.9;
}
.bars-pair {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 150px;
}
.bars-stacked {
  display: flex;
  align-items: flex-end;
  height: 150px;
  width: 100%;
}
.chart-bar {
  width: 11px;
  border-radius: 3px 3px 0 0;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.chart-bar.buy-bar {
  background: linear-gradient(180deg, #34d399, #059669);
  box-shadow: 0 0 10px rgba(52, 211, 153, 0.2);
}
.chart-bar.sell-bar {
  background: linear-gradient(180deg, #f87171, #dc2626);
  box-shadow: 0 0 10px rgba(248, 113, 113, 0.2);
}
.chart-bar.hour-bar {
  width: 100%;
  background: linear-gradient(180deg, #60a5fa, #2563eb);
  position: relative;
  display: flex;
  justify-content: center;
}
.bar-val-badge {
  position: absolute;
  top: -18px;
  font-size: 0.65rem;
  color: #93c5fd;
  font-weight: 600;
}
.bar-label {
  font-size: 0.68rem;
  color: var(--muted);
  white-space: nowrap;
}
.chart-inspector {
  margin-top: 10px;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 0.76rem;
  flex-wrap: wrap;
}
.ci-date {
  color: #60a5fa;
}
.chart-inspector-placeholder {
  margin-top: 10px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  font-size: 0.72rem;
  min-height: 35px;
}
.text-xs {
  font-size: 0.72rem;
}
.symbol-bars-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.sym-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sym-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.78rem;
}
.sym-ticker {
  color: #f8fafc;
  font-size: 0.85rem;
}
.sym-stats {
  font-size: 0.74rem;
}
.sym-diff {
  font-weight: 600;
  font-size: 0.78rem;
}
.sym-track {
  width: 100%;
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  overflow: hidden;
}
.sym-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  border-radius: 999px;
  transition: width 0.3s ease;
}
.order-flow-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  justify-content: center;
}
.flow-metric {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.flow-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--muted);
}
.flow-header b {
  color: var(--text);
}
.flow-bar-dual {
  height: 12px;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  background: rgba(255, 255, 255, 0.05);
}
.flow-segment.buy {
  background: linear-gradient(90deg, #10b981, #34d399);
  transition: width 0.3s ease;
}
.flow-segment.sell {
  background: linear-gradient(90deg, #f87171, #ef4444);
  transition: width 0.3s ease;
}
.flow-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.flow-mini-card {
  padding: 10px 14px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.flow-mini-card.buy-tint {
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(52, 211, 153, 0.2);
}
.flow-mini-card.sell-tint {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.2);
}
.flow-val {
  font-size: 1.15rem;
  font-weight: 700;
}

/* ---------- Trade Card & Position Lifecycle Styling ---------- */
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
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
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
.trade-card-header.clickable-trade-header {
  cursor: pointer;
  transition: background 0.15s ease;
}
.trade-card-header.clickable-trade-header:hover {
  background: rgba(56, 189, 248, 0.12);
}
.execution-row-clickable {
  cursor: pointer;
  transition: background-color 0.12s ease;
}
.execution-row-clickable:hover td {
  background: rgba(56, 189, 248, 0.08) !important;
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
  font-family: monospace;
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

.anomaly-legend-pill {
  font-size: 0.72rem;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  padding: 3px 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.legend-dot-red {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #ef4444;
}

/* Anomaly Row Highlight with light red opacity */
.anomaly-row {
  background-color: rgba(239, 68, 68, 0.14) !important;
  border-left: 3px solid #ef4444 !important;
}
.anomaly-row:hover {
  background-color: rgba(239, 68, 68, 0.22) !important;
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
  letter-spacing: 0.5px;
}

/* Tactics in Card Header */
.trade-header-tactics {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.setup-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.74rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.setup-pill.empty {
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  border: 1px dashed rgba(255, 255, 255, 0.2);
}
.setup-pill.empty:hover {
  background: rgba(255, 255, 255, 0.09);
  color: var(--text);
}
.setup-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
}
.setup-ema {
  background: rgba(59, 130, 246, 0.18);
  color: #60a5fa;
  border: 1px solid rgba(96, 165, 250, 0.35);
}
.setup-hod {
  background: rgba(245, 158, 11, 0.18);
  color: #fcd34d;
  border: 1px solid rgba(252, 211, 77, 0.35);
}
.setup-round {
  background: rgba(168, 85, 247, 0.18);
  color: #c084fc;
  border: 1px solid rgba(192, 132, 252, 0.35);
}
.setup-vwap {
  background: rgba(16, 185, 129, 0.18);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.35);
}
.setup-breakout {
  background: rgba(236, 72, 153, 0.18);
  color: #f472b6;
  border: 1px solid rgba(244, 114, 182, 0.35);
}
.setup-custom {
  background: rgba(148, 163, 184, 0.15);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.watched-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.73rem;
  font-family: monospace;
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
  max-width: 220px;
  transition: all 0.15s ease;
}
.comment-pill-btn:hover {
  background: rgba(16, 185, 129, 0.22);
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

.comment-cell-text {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #cbd5e1;
  font-size: 0.76rem;
  max-width: 100%;
  cursor: pointer;
  transition: color 0.15s ease;
}
.comment-cell-text:hover {
  color: #38bdf8;
}
.comment-icon {
  flex-shrink: 0;
  color: #34d399;
}
.comment-text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.accent-icon {
  color: #38bdf8;
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
  transition: all 0.15s ease;
}
.images-pill-btn:hover {
  background: rgba(139, 92, 246, 0.25);
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
  transition: all 0.2s ease;
}
.btn-edit-trade:hover {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
}

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
  transition: all 0.15s ease;
}
.col-img-btn:hover, .col-edit-btn:hover {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}
.col-img-btn.empty {
  opacity: 0.6;
}

/* ---------- Offcanvas Drawer & Modal ---------- */
.offcanvas-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.68);
  backdrop-filter: blur(4px);
  z-index: 99998;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.offcanvas-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 500px;
  max-width: 92vw;
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
.offcanvas-dir-badge.long {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}
.offcanvas-dir-badge.short {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}
.offcanvas-status-badge {
  font-size: 0.72rem;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
}
.offcanvas-sub {
  font-size: 0.78rem;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
.offcanvas-close-btn {
  background: transparent;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.offcanvas-close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text);
}

.offcanvas-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.form-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  font-weight: 600;
  color: #e2e8f0;
}
.label-hint {
  font-size: 0.72rem;
  color: var(--muted);
  font-weight: 400;
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
.btn-quick-fill:hover {
  background: rgba(59, 130, 246, 0.28);
}
.setup-presets-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}
.preset-chip-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.74rem;
  cursor: pointer;
  transition: all 0.15s ease;
}
.preset-chip-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}
.preset-chip-btn.active {
  background: #2563eb;
  color: #fff;
  border-color: #3b82f6;
  font-weight: 600;
}
.form-input, .form-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  color: var(--text);
  font-size: 0.82rem;
  font-family: inherit;
  outline: none;
  box-sizing: border-box;
}
.form-input:focus, .form-textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
}
.form-textarea {
  resize: vertical;
  line-height: 1.4;
}

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
.btn-upload-label:hover {
  background: rgba(139, 92, 246, 0.3);
}
.hidden-file-input {
  display: none;
}
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
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: pointer;
  display: block;
}
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
.gallery-thumb-card:hover .thumb-overlay {
  opacity: 1;
}
.thumb-act-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  padding: 6px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.thumb-act-btn:hover {
  background: rgba(255, 255, 255, 0.4);
}
.thumb-act-btn.del:hover {
  background: #ef4444;
}
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
.fill-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mini-side-badge {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
}
.mini-side-badge.buy {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
}
.mini-side-badge.sell {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}
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

.offcanvas-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  background: rgba(15, 23, 42, 0.95);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.save-meta-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
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
.lightbox-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}
.lightbox-img {
  max-width: 100%;
  max-height: 85vh;
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
  display: block;
}
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
.lightbox-close:hover {
  background: #ef4444;
}

/* ---------- Responsive ---------- */
@media (max-width: 1300px) {
  .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .empty { grid-template-columns: 1fr; }
}
@media (max-width: 1024px) {
  .charts-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .offcanvas-drawer { width: 100vw; }
}
@media (max-width: 480px) {
  .kpis { grid-template-columns: 1fr; }
}
</style>
