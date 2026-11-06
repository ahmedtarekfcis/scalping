<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import {
  Plus,
  BookOpen,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Eye,
  Edit3,
  Trash2,
  X,
  Upload,
  Image as ImageIcon,
  Download,
  Flame,
  Award,
  RefreshCw,
  Clock,
  Layers,
  ArrowRight,
  ArrowDown,
  ArrowUp,
  ShieldAlert,
  BrainCircuit,
  Target,
  BarChart2,
  SunMedium,
  FileJson,
  FileDown,
} from 'lucide-vue-next';
import { jsPDF } from 'jspdf';
import html2canvas from 'html2canvas';
import HtmlEditor from '../components/HtmlEditor.vue';
import {
  MISTAKE_DEFINITIONS,
  MISTAKE_CATEGORIES,
  TRADING_SESSIONS,
  getDefaultCurrentDateStr,
  getDefaultCurrentTimeStr,
  convertLocalToEst,
  detectSessionFromTime,
  evaluateTradeMistakes,
  calculateOverallStats,
  calculateMistakeFrequencyAnalysis,
  calculateWeeklyReview,
  getWeekDateRange,
} from '../utils/behavioralMistakes';
import {
  loadPersistedBehavioralTrades,
  persistBehavioralTrades,
  saveSingleBehavioralTrade,
  deleteSingleBehavioralTrade,
  clearAllBehavioralTrades,
  getBehavioralTradesFromLocalStorage,
  setBehavioralTradesInLocalStorage,
  mergeTradesById,
  fetchJournalTradesFromFile,
  getJournalFileInfo,
} from '../utils/tradeStorage';

// ----------------------------------------------------------------------------
// Core Reactive State (Saved directly to data/journal_trades.json on disk)
// ----------------------------------------------------------------------------
const trades = ref(
  getBehavioralTradesFromLocalStorage().filter((t) => t && !String(t.id).startsWith('demo-'))
);

// Safety net: continuously keep localStorage updated whenever trades change
watch(
  trades,
  (newTrades) => {
    if (Array.isArray(newTrades) && newTrades.length > 0) {
      setBehavioralTradesInLocalStorage(newTrades);
    }
  },
  { deep: true }
);

// Journal JSON file storage metadata & sync status
const jsonFileInfo = ref({
  filePath: 'data/journal_trades.json',
  fileName: 'journal_trades.json',
  exists: true,
  sizeBytes: 0,
  lastModified: null,
  tradeCount: 0,
});
const isBackendConnected = ref(true);
const isReloading = ref(false);
const isLoading = ref(true);
const activeTab = ref('history'); // Default active tab is "Trade Log" ('history')
const isOffcanvasOpen = ref(false);
const editingTradeId = ref(null);
const expandedTradeIds = ref(new Set());
const activeLightboxImage = ref(null);
const toast = ref({ show: false, message: '', type: 'success' });

// Selection & PDF Export State
const selectedTradeIds = ref(new Set());
const isExportingPdf = ref(false);

// Filter & Search Controls
const searchQuery = ref('');
const selectedMistakeFilter = ref('ALL');
const selectedDisciplineFilter = ref('ALL'); // 'ALL' | 'CLEAN' | 'MISTAKES'
const selectedDateFilter = ref('ALL'); // 'ALL' | 'THIS_WEEK' | 'THIS_MONTH' | 'LAST_WEEK'
const selectedSessionFilter = ref('ALL'); // 'ALL' | session ID

// Trade Log List Filter & Sort Controls
const tradeLogDateFilter = ref('TODAY'); // 'TODAY' | 'LAST_WEEK' | 'LAST_MONTH' | 'CUSTOM' | 'ALL' (default TODAY)
const customStartDate = ref('');
const customEndDate = ref('');
const isCalendarPickerOpen = ref(false);
const calendarPickerRef = ref(null);
const sortOrder = ref('desc'); // 'desc' | 'asc' (default desc)

// Weekly Review Navigation (anchor Monday)
const targetWeekMonday = ref(getWeekDateRange(new Date()).start);

// ----------------------------------------------------------------------------
// Trade Form State (Offcanvas)
// ----------------------------------------------------------------------------
const initialFormState = () => {
  const currentTime = getDefaultCurrentTimeStr();
  const currentDate = getDefaultCurrentDateStr();
  return {
    id: '',
    tradeDate: currentDate,
    tradeTime: currentTime,
    session: detectSessionFromTime(currentTime, currentDate), // Auto-converted from Cairo to EST market session
    symbol: '',
    direction: 'LONG',
    entryPrice: null,
    tradeSequence: 1,
    frontsideSetup: null, // true | false | null

    // Section B: Technical Levels
    ema9Value: null,
    vwapValue: null,
    nearestResistance: null,

    // Section C: Entry Discipline
    predefinedEntry: null, // true | false | null
    plannedEntryPrice: null,
    entryType: '', // 'Breakout' | 'FOMO' | 'Retest 9 EMA' | 'Retest VWAP'
    enteredAtPredefinedPrice: null, // true | false | null
    entryDeviationDirection: null, // 'ABOVE' | 'BELOW' | null
    entryDeviationReason: '',
    enteredAboveAction: null, // 'SOLD_HALF' | 'CLOSED_ENTIRE' | 'HELD_FULL' | null
    enteredAboveReason: '',

    // Section D: Risk Management & Execution
    predefinedStopLoss: null, // true | false | null
    stopLossPrice: null,
    averagedDown: null, // true | false | null
    averagedDownReason: '',
    frozeOnLoss: null, // true | false | null
    frozeReason: '',
    finalExitType: null, // 'SETUP' | 'FEAR' | null
    finalExitFearReason: '',
    flushOccurred: null, // true | false | null
    flushReason: '',

    // Section E: Notes & Screenshots
    notes: '',
    screenshots: [],
  };
};

const form = ref(initialFormState());

// Helper for Session Metadata
const getSessionMeta = (sessionId) => {
  return (
    TRADING_SESSIONS.find((s) => s.id === sessionId) || {
      id: sessionId || 'MARKET_OPEN',
      label: sessionId || 'Market Hours',
      hours: '',
      color: '#34d399',
      bg: 'rgba(52, 211, 153, 0.15)',
    }
  );
};

// Helper to format Date and Time as 'DD Mon - HH:MM:SS'
const formatTradeDateTime = (dateStr, timeStr) => {
  if (!dateStr) return timeStr || '';
  try {
    const parts = dateStr.split('-');
    if (parts.length === 3) {
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const mIdx = parseInt(parts[1], 10) - 1;
      const mName = monthNames[mIdx] || parts[1];
      const day = String(parts[2]).padStart(2, '0');
      const datePart = `${day} ${mName}`;
      if (timeStr) {
        return `${datePart} - ${timeStr}`;
      }
      return datePart;
    }
  } catch (e) {
    // fallback
  }
  return `${dateStr}${timeStr ? ' - ' + timeStr : ''}`;
};

// Quick Chips Presets
const ENTRY_WAS_CHIPS = [
  'Breakout',
  'FOMO',
  'Retest 9 EMA',
  'Retest VWAP',
];

const ENTRY_DEVIATION_CHIPS = [
  'FOMO / Chased breakout',
  'Tape sped up / Feared missing move',
  'Market order slippage',
  'Hesitation & late execution',
  'Anticipated break prematurely',
];

const HELD_FULL_CHIPS = [
  'Greed / Wanted full profit',
  'Hoped momentum would continue',
  'Did not want to accept immediate loss',
  'Lack of clear reduction plan',
  'Confident in bigger timeframe',
];

const AVERAGED_DOWN_CHIPS = [
  'Wanted to lower average price',
  'Hoped for breakeven bounce',
  'Refused to take the loss',
  'Overly biased / In love with the stock',
  'Size was initially small',
];

const FROZE_ON_LOSS_CHIPS = [
  'Frozen in shock by sudden drop',
  'Hoped / Prayed for recovery',
  'Fear of realizing the dollar loss',
  'Position size was too large',
  'Removed or ignored mental stop',
];

const FEAR_EXIT_CHIPS = [
  'Feared giving back gains',
  'Panic on pullback candle',
  'Anxiety / Fear of loss',
  'Hesitation after fast move',
  'Rushed to lock green prematurely',
];

const FLUSH_REASON_CHIPS = [
  'Stock stalled before flush and failed to exit',
  'Broke key support / Broke VWAP',
  'Large ask wall appeared',
  'Bids pulled / Buyers evaporated',
  'Fakeout / Failed breakout',
  'Greed / Held too long for more',
  'Blow-off top / Sharp reversal',
  'Chased late at the top',
  'Volume dried up / Momentum lost',
  'Tape stalled / Price halted',
];

// ----------------------------------------------------------------------------
// Multi-Select Reason Helpers
// ----------------------------------------------------------------------------
const isChipSelected = (fieldName, chipText) => {
  const val = form.value[fieldName] || '';
  if (!val) return false;
  const parts = val.split(/\s*•\s*|\n+/).map((p) => p.trim());
  return parts.includes(chipText.trim());
};

const toggleReasonChip = (fieldName, chipText) => {
  const trimmed = chipText.trim();
  const currentVal = form.value[fieldName] || '';
  let parts = currentVal
    .split(/\s*•\s*|\n+/)
    .map((p) => p.trim())
    .filter(Boolean);

  const idx = parts.indexOf(trimmed);
  if (idx >= 0) {
    // Unselect chip
    parts.splice(idx, 1);
  } else {
    // Select chip
    parts.push(trimmed);
  }

  form.value[fieldName] = parts.join(' • ');
};

const clearReasonChips = (fieldName) => {
  form.value[fieldName] = '';
};

// Show Toast Alert
const showToast = (message, type = 'success') => {
  toast.value = { show: true, message, type };
  setTimeout(() => {
    toast.value.show = false;
  }, 3500);
};

// ----------------------------------------------------------------------------
// Lifecycle & Data Loading (Strictly Manual Data)
// ----------------------------------------------------------------------------
onMounted(async () => {
  try {
    const loaded = await loadPersistedBehavioralTrades();
    if (Array.isArray(loaded) && loaded.length > 0) {
      // Merge with in-memory trades so no trades are ever overwritten or lost
      trades.value = mergeTradesById(trades.value, loaded);
    } else if (trades.value.length > 0) {
      // If loaded was empty but in-memory has trades, persist in-memory immediately!
      await persistBehavioralTrades(trades.value);
    }
    const info = await getJournalFileInfo();
    if (info) {
      jsonFileInfo.value = info;
      isBackendConnected.value = true;
    }
  } catch (err) {
    console.error('Failed to load behavioral journal:', err);
    isBackendConnected.value = false;
  } finally {
    isLoading.value = false;
  }

  window.addEventListener('paste', handleGlobalPaste);
  window.addEventListener('click', handleWindowClick);
});

// Reload fresh trades from backend data/journal_trades.json
const reloadFromJsonFile = async () => {
  if (isReloading.value) return;
  isReloading.value = true;
  try {
    const res = await fetchJournalTradesFromFile();
    if (res.success) {
      trades.value = res.trades.filter((t) => t && !String(t.id).startsWith('demo-'));
      isBackendConnected.value = true;
      jsonFileInfo.value = {
        filePath: res.filePath || jsonFileInfo.value.filePath,
        fileName: res.fileName || 'journal_trades.json',
        exists: true,
        sizeBytes: 0,
        lastModified: res.lastModified,
        tradeCount: trades.value.length,
      };
      showToast(`Loaded ${trades.value.length} trades from ${res.fileName || 'journal_trades.json'}`, 'success');
    } else {
      isBackendConnected.value = false;
      showToast('Could not reach backend to reload JSON file (is backend running?)', 'error');
    }
  } catch (err) {
    console.error('Reload error:', err);
    showToast('Failed to reload JSON file', 'error');
  } finally {
    isReloading.value = false;
  }
};

onUnmounted(() => {
  window.removeEventListener('paste', handleGlobalPaste);
  window.removeEventListener('click', handleWindowClick);
});

// Compress image before adding to screenshots (lightweight ~50KB per image, perfectly safe for localStorage & IDB)
const compressImageFile = (file, maxWidth = 1200, maxHeight = 900, quality = 0.75) => {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        if (width > maxWidth || height > maxHeight) {
          const ratio = Math.min(maxWidth / width, maxHeight / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        const compressed = canvas.toDataURL('image/jpeg', quality);
        resolve(compressed);
      };
      img.onerror = () => resolve(e.target?.result || null);
      img.src = e.target?.result;
    };
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(file);
  });
};

// Clipboard Paste for Chart Screenshots (Supports multiple pasted images)
const handleGlobalPaste = async (e) => {
  if (!isOffcanvasOpen.value) return;
  const items = e.clipboardData?.items;
  if (!items) return;
  let count = 0;
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (item.type.indexOf('image') !== -1) {
      const blob = item.getAsFile();
      if (!blob) continue;
      const dataUrl = await compressImageFile(blob);
      if (dataUrl) {
        form.value.screenshots.push(dataUrl);
        count++;
      }
    }
  }
  if (count > 0) {
    showToast(`Pasted ${count} screenshot${count > 1 ? 's' : ''} from clipboard!`, 'success');
  }
};

// ----------------------------------------------------------------------------
// Dynamic Analytics Calculations (Derived strictly from manual records)
// ----------------------------------------------------------------------------
// Trades with dynamically attached mistakes (no double-counting, missing data safe)
const enrichedTrades = computed(() => {
  return trades.value.map((t) => {
    const mistakes = evaluateTradeMistakes(t);
    let pnl = t.pnl;
    let status = t.status;
    if (t.entryPrice && t.exitPrice && t.shares) {
      const diff = t.direction === 'SHORT' ? t.entryPrice - t.exitPrice : t.exitPrice - t.entryPrice;
      pnl = Number((diff * t.shares).toFixed(2));
      if (!status) {
        status = pnl > 0 ? 'WIN' : pnl < 0 ? 'LOSS' : 'BREAKEVEN';
      }
    }
    return {
      ...t,
      session: t.session || detectSessionFromTime(t.tradeTime, t.tradeDate),
      mistakes,
      mistakesCount: mistakes.length,
      isClean: mistakes.length === 0,
      calculatedPnl: pnl,
      calculatedStatus: status || (t.isStillOpen ? 'OPEN' : 'UNKNOWN'),
    };
  });
});

// Date-Filtered Trades for Analytics
const filteredTrades = computed(() => {
  let list = enrichedTrades.value;

  if (selectedDateFilter.value === 'THIS_WEEK') {
    const week = getWeekDateRange(new Date());
    list = list.filter((t) => t.tradeDate >= week.startStr && t.tradeDate <= week.endStr);
  } else if (selectedDateFilter.value === 'LAST_WEEK') {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    const week = getWeekDateRange(d);
    list = list.filter((t) => t.tradeDate >= week.startStr && t.tradeDate <= week.endStr);
  } else if (selectedDateFilter.value === 'THIS_MONTH') {
    const now = new Date();
    const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    list = list.filter((t) => (t.tradeDate || '').startsWith(ym));
  }

  return list;
});

// Overall Stats for active period
const overallStats = computed(() => {
  return calculateOverallStats(filteredTrades.value);
});

// Mistake Frequency & Trends Analysis
const mistakeFrequencyList = computed(() => {
  return calculateMistakeFrequencyAnalysis(filteredTrades.value);
});

// Weekly Review Data
const weeklyReview = computed(() => {
  return calculateWeeklyReview(enrichedTrades.value, targetWeekMonday.value);
});

// Category Distribution for Charting
const categoryDistribution = computed(() => {
  const map = {};
  MISTAKE_CATEGORIES.forEach((cat) => {
    map[cat.id] = { ...cat, count: 0 };
  });

  filteredTrades.value.forEach((t) => {
    t.mistakes.forEach((m) => {
      const cat = m.category || 'Discipline';
      if (map[cat]) map[cat].count++;
    });
  });

  const total = Object.values(map).reduce((sum, item) => sum + item.count, 0);
  return Object.values(map).map((item) => ({
    ...item,
    percentage: total > 0 ? Number(((item.count / total) * 100).toFixed(1)) : 0,
  }));
});

// Behavioral Pattern: Sequence Overtrading Impact
const sequenceImpactStats = computed(() => {
  const buckets = {
    1: { label: '1st Trade', total: 0, flawed: 0, mistakes: 0 },
    2: { label: '2nd Trade', total: 0, flawed: 0, mistakes: 0 },
    3: { label: '3rd Trade', total: 0, flawed: 0, mistakes: 0 },
    '4+': { label: '4th+ Trade', total: 0, flawed: 0, mistakes: 0 },
  };

  filteredTrades.value.forEach((t) => {
    const seq = Number(t.tradeSequence) || 1;
    const bucket = seq === 1 ? 1 : seq === 2 ? 2 : seq === 3 ? 3 : '4+';
    buckets[bucket].total++;
    if (t.mistakesCount > 0) {
      buckets[bucket].flawed++;
      buckets[bucket].mistakes += t.mistakesCount;
    }
  });

  return Object.values(buckets).map((b) => ({
    ...b,
    flawRate: b.total > 0 ? Number(((b.flawed / b.total) * 100).toFixed(1)) : 0,
  }));
});

// Behavioral Pattern: Frontside vs Backside Setup Impact
const frontsideImpactStats = computed(() => {
  let frontsideTotal = 0;
  let frontsideFlawed = 0;
  let backsideTotal = 0;
  let backsideFlawed = 0;

  filteredTrades.value.forEach((t) => {
    if (t.frontsideSetup === true) {
      frontsideTotal++;
      if (t.mistakesCount > 0) frontsideFlawed++;
    } else if (t.frontsideSetup === false) {
      backsideTotal++;
      if (t.mistakesCount > 0) backsideFlawed++;
    }
  });

  return {
    frontside: {
      total: frontsideTotal,
      flawed: frontsideFlawed,
      rate: frontsideTotal > 0 ? Number(((frontsideFlawed / frontsideTotal) * 100).toFixed(1)) : 0,
    },
    backside: {
      total: backsideTotal,
      flawed: backsideFlawed,
      rate: backsideTotal > 0 ? Number(((backsideFlawed / backsideTotal) * 100).toFixed(1)) : 0,
    },
  };
});

// Behavioral Pattern: Session Breakdown
const sessionImpactStats = computed(() => {
  const map = {};
  TRADING_SESSIONS.forEach((s) => {
    map[s.id] = { ...s, total: 0, flawed: 0, mistakes: 0 };
  });

  filteredTrades.value.forEach((t) => {
    const sId = t.session || detectSessionFromTime(t.tradeTime, t.tradeDate);
    if (!map[sId]) {
      map[sId] = {
        id: sId,
        label: sId,
        hours: '',
        color: '#94a3b8',
        bg: 'rgba(148, 163, 184, 0.15)',
        total: 0,
        flawed: 0,
        mistakes: 0,
      };
    }
    map[sId].total++;
    if (t.mistakesCount > 0) {
      map[sId].flawed++;
      map[sId].mistakes += t.mistakesCount;
    }
  });

  return Object.values(map).map((s) => ({
    ...s,
    flawRate: s.total > 0 ? Number(((s.flawed / s.total) * 100).toFixed(1)) : 0,
  }));
});

// Helper to get local date string YYYY-MM-DD
const getLocalDateString = (d) => {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Date-filtered trades specifically for the Trading Log tab
const dateFilteredTrades = computed(() => {
  let list = enrichedTrades.value;
  const todayStr = getDefaultCurrentDateStr();

  if (tradeLogDateFilter.value === 'TODAY') {
    list = list.filter((t) => (t.tradeDate || '') === todayStr);
  } else if (tradeLogDateFilter.value === 'LAST_WEEK') {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    const lastWeekStartStr = getLocalDateString(d);
    list = list.filter((t) => (t.tradeDate || '') >= lastWeekStartStr);
  } else if (tradeLogDateFilter.value === 'LAST_MONTH') {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    const lastMonthStartStr = getLocalDateString(d);
    list = list.filter((t) => (t.tradeDate || '') >= lastMonthStartStr);
  } else if (tradeLogDateFilter.value === 'CUSTOM') {
    if (customStartDate.value) {
      list = list.filter((t) => (t.tradeDate || '') >= customStartDate.value);
    }
    if (customEndDate.value) {
      list = list.filter((t) => (t.tradeDate || '') <= customEndDate.value);
    }
  }

  return list;
});

// Stats for the active date range in Trade Log (for Clean / Flawed discipline buttons)
const dateFilteredStats = computed(() => {
  const list = dateFilteredTrades.value;
  let clean = 0;
  let flaws = 0;
  list.forEach((t) => {
    if (t.isClean) clean++;
    else flaws++;
  });
  return {
    total: list.length,
    clean,
    flaws,
  };
});

// Robust trade comparator (descending by default)
const compareTrades = (a, b) => {
  // 1. Compare Date (YYYY-MM-DD)
  const dateA = a.tradeDate || '';
  const dateB = b.tradeDate || '';
  if (dateA !== dateB) {
    return sortOrder.value === 'asc' ? dateA.localeCompare(dateB) : dateB.localeCompare(dateA);
  }

  // 2. Compare Time (normalize HH:MM[:SS] with zero-padding)
  const normTime = (t) => {
    if (!t) return '00:00:00';
    const parts = String(t).trim().split(':');
    const h = (parts[0] || '0').padStart(2, '0');
    const m = (parts[1] || '0').padStart(2, '0');
    const s = (parts[2] || '0').padStart(2, '0');
    return `${h}:${m}:${s}`;
  };
  const timeA = normTime(a.tradeTime);
  const timeB = normTime(b.tradeTime);
  if (timeA !== timeB) {
    return sortOrder.value === 'asc' ? timeA.localeCompare(timeB) : timeB.localeCompare(timeA);
  }

  // 3. Compare Sequence within day
  const seqA = Number(a.tradeSequence) || 0;
  const seqB = Number(b.tradeSequence) || 0;
  if (seqA !== seqB) {
    return sortOrder.value === 'asc' ? seqA - seqB : seqB - seqA;
  }

  // 4. Compare creation timestamp or ID
  const getTs = (tr) => {
    if (tr.createdAt) {
      const p = Date.parse(tr.createdAt);
      if (!isNaN(p)) return p;
    }
    const match = String(tr.id || '').match(/JT-(\d+)/);
    if (match) return Number(match[1]);
    return 0;
  };
  const tsA = getTs(a);
  const tsB = getTs(b);
  if (tsA !== tsB) {
    return sortOrder.value === 'asc' ? tsA - tsB : tsB - tsA;
  }

  const idA = String(a.id || '');
  const idB = String(b.id || '');
  return sortOrder.value === 'asc' ? idA.localeCompare(idB) : idB.localeCompare(idA);
};

// Filtered Trades for Table Log Display
const displayedTrades = computed(() => {
  let list = dateFilteredTrades.value;

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toUpperCase();
    list = list.filter(
      (t) =>
        (t.symbol || '').toUpperCase().includes(q) ||
        (t.notes || '').toUpperCase().includes(q) ||
        (t.entryDeviationReason || '').toUpperCase().includes(q)
    );
  }

  if (selectedMistakeFilter.value !== 'ALL') {
    list = list.filter((t) => t.mistakes.some((m) => m.id === selectedMistakeFilter.value));
  }

  if (selectedDisciplineFilter.value === 'CLEAN') {
    list = list.filter((t) => t.isClean);
  } else if (selectedDisciplineFilter.value === 'MISTAKES') {
    list = list.filter((t) => !t.isClean);
  }

  if (selectedSessionFilter.value !== 'ALL') {
    list = list.filter((t) => (t.session || detectSessionFromTime(t.tradeTime, t.tradeDate)) === selectedSessionFilter.value);
  }

  // Sort trades (descending by default)
  return [...list].sort(compareTrades);
});

// Recent trades strictly sorted descending
const recentTrades = computed(() => {
  return [...enrichedTrades.value].sort(compareTrades).slice(0, 5);
});

// Date filter actions
const setDateFilter = (filterKey) => {
  tradeLogDateFilter.value = filterKey;
  isCalendarPickerOpen.value = false;
};

const toggleCalendarPicker = () => {
  isCalendarPickerOpen.value = !isCalendarPickerOpen.value;
  if (isCalendarPickerOpen.value && !customStartDate.value && !customEndDate.value) {
    const todayStr = getDefaultCurrentDateStr();
    customStartDate.value = todayStr;
    customEndDate.value = todayStr;
  }
};

const applyCustomRange = () => {
  let start = customStartDate.value;
  let end = customEndDate.value;
  if (start && end && start > end) {
    [start, end] = [end, start];
    customStartDate.value = start;
    customEndDate.value = end;
  }
  tradeLogDateFilter.value = 'CUSTOM';
  isCalendarPickerOpen.value = false;
};

const clearCustomRange = () => {
  customStartDate.value = '';
  customEndDate.value = '';
  tradeLogDateFilter.value = 'TODAY';
  isCalendarPickerOpen.value = false;
};

const customRangeLabel = computed(() => {
  if (!customStartDate.value && !customEndDate.value) return '';
  if (customStartDate.value && customEndDate.value) {
    if (customStartDate.value === customEndDate.value) {
      return formatTradeDateTime(customStartDate.value);
    }
    return `${formatTradeDateTime(customStartDate.value)} - ${formatTradeDateTime(customEndDate.value)}`;
  }
  if (customStartDate.value) {
    return `≥ ${formatTradeDateTime(customStartDate.value)}`;
  }
  return `≤ ${formatTradeDateTime(customEndDate.value)}`;
});

const toggleSortOrder = () => {
  sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc';
};

const handleWindowClick = (e) => {
  if (isCalendarPickerOpen.value && calendarPickerRef.value && !calendarPickerRef.value.contains(e.target)) {
    isCalendarPickerOpen.value = false;
  }
};

// Live Form Mistakes Preview
const liveFormMistakes = computed(() => {
  return evaluateTradeMistakes(form.value);
});

// ----------------------------------------------------------------------------
// Form Methods (Add / Edit / Delete)
// ----------------------------------------------------------------------------
const openAddModal = () => {
  editingTradeId.value = null;
  const currentTime = getDefaultCurrentTimeStr();
  const currentDate = getDefaultCurrentDateStr();
  form.value = {
    ...initialFormState(),
    tradeDate: currentDate,
    tradeTime: currentTime,
    session: detectSessionFromTime(currentTime, currentDate),
  };
  isOffcanvasOpen.value = true;
};

const openEditModal = (trade) => {
  if (!trade) return;
  editingTradeId.value = trade.id;
  form.value = {
    ...initialFormState(),
    ...JSON.parse(JSON.stringify(trade)),
    id: trade.id,
    screenshots: Array.isArray(trade.screenshots) ? [...trade.screenshots] : [],
    session: trade.session || detectSessionFromTime(trade.tradeTime, trade.tradeDate),
  };
  isOffcanvasOpen.value = true;
};

const closeOffcanvas = () => {
  isOffcanvasOpen.value = false;
  editingTradeId.value = null;
};

const handleImageUpload = async (e) => {
  const files = e.target?.files;
  if (!files || !files.length) return;
  const fileArray = Array.from(files).filter((f) => f.type.startsWith('image/'));
  if (!fileArray.length) return;

  for (const file of fileArray) {
    const dataUrl = await compressImageFile(file);
    if (dataUrl) {
      form.value.screenshots.push(dataUrl);
    }
  }
  showToast(`Added ${fileArray.length} screenshot${fileArray.length > 1 ? 's' : ''}!`, 'success');
  e.target.value = '';
};

const handleDropImages = async (e) => {
  e.preventDefault();
  const files = e.dataTransfer?.files;
  if (!files || !files.length) return;
  const fileArray = Array.from(files).filter((f) => f.type.startsWith('image/'));
  if (!fileArray.length) return;

  for (const file of fileArray) {
    const dataUrl = await compressImageFile(file);
    if (dataUrl) {
      form.value.screenshots.push(dataUrl);
    }
  }
  showToast(`Added ${fileArray.length} screenshot${fileArray.length > 1 ? 's' : ''}!`, 'success');
};

const removeScreenshot = (index) => {
  form.value.screenshots.splice(index, 1);
};

const saveTrade = async () => {
  if (!form.value.symbol.trim()) {
    showToast('Please enter a Stock Symbol / Ticker', 'error');
    return;
  }
  if (!form.value.entryPrice || Number(form.value.entryPrice) <= 0) {
    showToast('Please enter a valid Entry Price', 'error');
    return;
  }

  const cleanSymbol = form.value.symbol.trim().toUpperCase();
  const currentTime = getDefaultCurrentTimeStr();
  const currentDate = getDefaultCurrentDateStr();

  const tradePayload = {
    ...form.value,
    notes: cleanHtmlNotes(form.value.notes || ''),
    symbol: cleanSymbol,
    tradeDate: form.value.tradeDate || currentDate,
    tradeTime: form.value.tradeTime || currentTime,
    session: form.value.session || detectSessionFromTime(form.value.tradeTime || currentTime, form.value.tradeDate || currentDate),
    entryPrice: Number(form.value.entryPrice),
    tradeSequence: Number(form.value.tradeSequence) || 1,
    ema9Value: form.value.ema9Value ? Number(form.value.ema9Value) : null,
    vwapValue: form.value.vwapValue ? Number(form.value.vwapValue) : null,
    nearestResistance: form.value.nearestResistance ? Number(form.value.nearestResistance) : null,
    plannedEntryPrice: form.value.plannedEntryPrice ? Number(form.value.plannedEntryPrice) : null,
    stopLossPrice: form.value.stopLossPrice ? Number(form.value.stopLossPrice) : null,
  };

  const isEditing = Boolean(editingTradeId.value);
  if (isEditing) {
    tradePayload.id = editingTradeId.value;
    tradePayload.updatedAt = new Date().toISOString();
  } else {
    tradePayload.id = `JT-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    tradePayload.createdAt = new Date().toISOString();
  }

  try {
    // 1. Immediately update in-memory trades so UI never flashes or loses data
    const targetId = String(tradePayload.id).trim();
    const existingIdx = trades.value.findIndex((t) => t && String(t.id || '').trim() === targetId);
    if (existingIdx >= 0) {
      trades.value[existingIdx] = { ...trades.value[existingIdx], ...tradePayload };
    } else {
      trades.value.unshift({ ...tradePayload });
    }

    // 2. Persist to data/journal_trades.json on disk (and sync local caches)
    await persistBehavioralTrades(trades.value);

    closeOffcanvas();
    showToast(isEditing ? `Trade ${cleanSymbol} updated in JSON file!` : `Trade ${cleanSymbol} saved to JSON file!`, 'success');
    getJournalFileInfo().then((info) => { if (info) jsonFileInfo.value = info; });
  } catch (err) {
    console.error('Save trade error:', err);
    showToast('Failed to save trade. Please try again.', 'error');
  }
};

const deleteTrade = async (id) => {
  if (!confirm('Are you sure you want to delete this trade record?')) return;
  try {
    const targetId = String(id || '').trim();
    selectedTradeIds.value.delete(id);
    trades.value = trades.value.filter((t) => t && String(t.id || '').trim() !== targetId);
    await persistBehavioralTrades(trades.value);
    showToast('Trade record removed from JSON file', 'info');
    getJournalFileInfo().then((info) => { if (info) jsonFileInfo.value = info; });
  } catch (err) {
    console.error('Delete error:', err);
    showToast('Failed to delete trade', 'error');
  }
};

const toggleExpandTrade = (id) => {
  if (expandedTradeIds.value.has(id)) {
    expandedTradeIds.value.delete(id);
  } else {
    expandedTradeIds.value.add(id);
  }
};

// Clear All Trades
const clearAllTrades = async () => {
  if (!confirm('Are you sure you want to delete ALL trades from your journal? An archive backup of data/journal_trades.json will be saved.')) return;
  await clearAllBehavioralTrades();
  selectedTradeIds.value.clear();
  trades.value = [];
  showToast('All journal records cleared (backup created)', 'info');
  getJournalFileInfo().then((info) => { if (info) jsonFileInfo.value = info; });
};

// Weekly Navigation
const prevWeek = () => {
  const d = new Date(targetWeekMonday.value);
  d.setDate(d.getDate() - 7);
  targetWeekMonday.value = d;
};

const nextWeek = () => {
  const d = new Date(targetWeekMonday.value);
  d.setDate(d.getDate() + 7);
  targetWeekMonday.value = d;
};

const resetToCurrentWeek = () => {
  targetWeekMonday.value = getWeekDateRange(new Date()).start;
};

// Export to JSON Backup
const exportDataJson = () => {
  const blob = new Blob([JSON.stringify(trades.value, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `trading_journal_backup_${new Date().toISOString().split('T')[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Journal data exported to JSON', 'success');
};

// ----------------------------------------------------------------------------
// Trade Selection Methods
// ----------------------------------------------------------------------------
const isTradeSelected = (id) => selectedTradeIds.value.has(id);

const toggleSelectTrade = (id) => {
  if (selectedTradeIds.value.has(id)) {
    selectedTradeIds.value.delete(id);
  } else {
    selectedTradeIds.value.add(id);
  }
};

const isAllSelected = computed(() => {
  return displayedTrades.value.length > 0 && displayedTrades.value.every((t) => selectedTradeIds.value.has(t.id));
});

const isIndeterminate = computed(() => {
  if (displayedTrades.value.length === 0) return false;
  const count = displayedTrades.value.filter((t) => selectedTradeIds.value.has(t.id)).length;
  return count > 0 && count < displayedTrades.value.length;
});

const toggleSelectAll = () => {
  if (isAllSelected.value) {
    displayedTrades.value.forEach((t) => selectedTradeIds.value.delete(t.id));
  } else {
    displayedTrades.value.forEach((t) => selectedTradeIds.value.add(t.id));
  }
};

const selectAllTrades = () => {
  displayedTrades.value.forEach((t) => selectedTradeIds.value.add(t.id));
};

const deselectAllTrades = () => {
  selectedTradeIds.value.clear();
};

// ----------------------------------------------------------------------------
// Single-Page Trade PDF Export Engine (jsPDF)
// ----------------------------------------------------------------------------
const getImageDimensions = (src) => {
  return new Promise((resolve) => {
    if (!src || typeof src !== 'string') return resolve(null);
    const img = new Image();
    img.onload = () => {
      resolve({
        width: img.naturalWidth || img.width || 800,
        height: img.naturalHeight || img.height || 450,
      });
    };
    img.onerror = () => resolve(null);
    img.src = src;
  });
};

// Clean HTML notes from fragmented tags, noise, or split numbers across tags
function cleanHtmlNotes(html) {
  if (!html) return '';
  let cleaned = String(html);

  // 1. Remove useless spans that have no meaningful style (e.g. empty spans, class="", data-*, animation-*)
  cleaned = cleaned.replace(/<span(?:\s+(?:class=["']\s*["']|data-[\w-]+=(?:"[^"]*"|'[^']*')|style=["'](?:--[\w-]+:[^"';]+;?\s*)*["']))*\s*>(.*?)<\/span>/gi, '$1');

  // 2. Fix decimal numbers split across tags: e.g. "1.</span>94" or "1.<span ...>23"
  cleaned = cleaned.replace(/(\d+[.,])\s*(<\/(?:span|b|strong|em|i)>)\s*(<(?:span|b|strong|em|i)[^>]*>)?\s*(\d+)/gi, (m, p1, closeTag, openTag, p2) => {
    return `${p1}${p2}${closeTag || ''}${openTag || ''}`;
  });
  cleaned = cleaned.replace(/(\d+[.,])\s*(<(?:span|b|strong|em|i)[^>]*>)\s*(\d+)/gi, '$2$1$3');

  // 3. Fix parentheses split from numbers across tags: e.g. "(</span>1.94", "(<span ...>1.94", "1.94</span>)"
  cleaned = cleaned.replace(/([(])\s*(<\/(?:span|b|strong|em|i)>)\s*(<(?:span|b|strong|em|i)[^>]*>)?\s*(\d+)/gi, '$2$3$1$4');
  cleaned = cleaned.replace(/([(])\s*(<(?:span|b|strong|em|i)[^>]*>)\s*(\d+)/gi, '$2$1$3');
  cleaned = cleaned.replace(/(\d+(?:[.,]\d+)?)\s*(<\/(?:span|b|strong|em|i)>)\s*(<(?:span|b|strong|em|i)[^>]*>)?\s*([)])/gi, '$1$4$2$3');
  cleaned = cleaned.replace(/(\d+(?:[.,]\d+)?)\s*(<(?:span|b|strong|em|i)[^>]*>)\s*([)])/gi, '$1$3$2');

  return cleaned;
}

// Helper to protect and isolate numbers, currencies, decimals, ranges, indicator tokens, and parenthesized expressions in RTL Arabic text
function formatBidiNumbers(html) {
  if (!html) return '';
  // Clean empty/split spans and strip any existing bidi-num spans to ensure idempotency
  const cleanHtml = cleanHtmlNotes(html).replace(/<span\s+class=["']bidi-num["'][^>]*>(.*?)<\/span>/gi, '$1');

  // Matches parenthesized numbers/indicators/terms like (1.94), (9 EMA), (VWAP), (Freeze),
  // as well as bare numbers, currencies, percentages, ranges, and indicators like 1.94, +5%, -$50, 14.20 - 15.00
  const bidiNumberPattern = /((?:\(\s*[+\-±]?\$?\d+(?:[.,:\/]\d+)*(?:\s*[-–—]\s*\$?\d+(?:[.,:\/]\d+)*)?%?\$?(?:\s*(?:EMA|SMA|VWAP|ema|sma|vwap|min|sec|shares?|pts?|[mhdkMK]))?\s*\))|(?:\(\s*[A-Za-z0-9._\-+/%$][A-Za-z0-9\s._\-+/%$]*\s*\))|(?:[+\-±]?\$?\d+(?:[.,:\/]\d+)*(?:\s*[-–—]\s*\$?\d+(?:[.,:\/]\d+)*)?%?\$?(?:\s*(?:EMA|SMA|VWAP|ema|sma|vwap|min|sec|shares?|pts?|[mhdkMK]))?))/g;

  return cleanHtml.replace(/(<[^>]+>)|([^<]+)/g, (match, tag, text) => {
    if (tag) return tag;
    return text.replace(bidiNumberPattern, (num) => {
      const trimmed = num.trim();
      if (!trimmed || !/[0-9a-zA-Z]/.test(trimmed)) return num;
      const lead = num.match(/^\s*/)[0];
      const trail = num.match(/\s*$/)[0];
      return `${lead}<span class="bidi-num" dir="ltr">${trimmed}</span>${trail}`;
    });
  });
}

const renderHtmlToPdfImage = async (htmlContent, widthPt) => {
  if (!htmlContent || !htmlContent.trim()) return null;

  const bidiHtml = formatBidiNumbers(htmlContent);

  const container = document.createElement('div');
  container.className = 'pdf-html-render-temp';
  container.style.position = 'fixed';
  container.style.left = '-9999px';
  container.style.top = '0';
  container.style.width = `${Math.round(widthPt * 1.5)}px`;
  container.style.padding = '10px 14px';
  container.style.background = '#ffffff';
  container.style.color = '#0f172a';
  container.style.fontFamily = "'Segoe UI', Tahoma, Arial, sans-serif";
  container.style.fontSize = '16px';
  container.style.lineHeight = '1.75';
  container.style.direction = 'rtl';
  container.style.textAlign = 'right';
  container.style.letterSpacing = 'normal';
  container.style.boxSizing = 'border-box';
  container.setAttribute('dir', 'rtl');

  const styleElem = document.createElement('style');
  styleElem.textContent = `
    .pdf-html-render-temp { direction: rtl !important; text-align: right !important; }
    .pdf-html-render-temp p,
    .pdf-html-render-temp div,
    .pdf-html-render-temp li,
    .pdf-html-render-temp h2,
    .pdf-html-render-temp h3 {
      direction: rtl !important;
      text-align: right !important;
      letter-spacing: normal !important;
      unicode-bidi: isolate !important;
    }
    .pdf-html-render-temp .bidi-num {
      direction: ltr !important;
      unicode-bidi: isolate !important;
      display: inline-block !important;
      text-align: left !important;
      white-space: nowrap !important;
      font-family: 'Segoe UI', Tahoma, Arial, sans-serif !important;
    }
    .pdf-html-render-temp ul { list-style: none !important; margin: 4px 0 !important; padding: 0 !important; direction: rtl !important; text-align: right !important; }
    .pdf-html-render-temp ul li { position: relative !important; padding-right: 22px !important; padding-left: 0 !important; margin: 4px 0 !important; direction: rtl !important; text-align: right !important; list-style: none !important; font-size: 16px !important; }
    .pdf-html-render-temp ul li::before { content: '•' !important; position: absolute !important; right: 2px !important; top: -1px !important; color: #0284c7 !important; font-size: 18px !important; line-height: 1.4 !important; }
    .pdf-html-render-temp ol { margin: 4px 0 !important; padding-right: 26px !important; padding-left: 0 !important; list-style-position: inside !important; direction: rtl !important; text-align: right !important; font-size: 16px !important; }
    .pdf-html-render-temp ol li { margin: 3px 0 !important; direction: rtl !important; text-align: right !important; }
    .pdf-html-render-temp h2, .pdf-html-render-temp h3 { color: #0284c7 !important; margin: 6px 0 3px 0 !important; font-weight: 700 !important; font-size: 18px !important; }
    .pdf-html-render-temp p { margin: 4px 0 !important; font-size: 16px !important; }
    .pdf-html-render-temp strong, .pdf-html-render-temp b { font-weight: 700 !important; color: #000000 !important; }
  `;
  container.appendChild(styleElem);

  const contentWrapper = document.createElement('div');
  contentWrapper.setAttribute('dir', 'rtl');
  contentWrapper.style.direction = 'rtl';
  contentWrapper.style.textAlign = 'right';
  contentWrapper.innerHTML = bidiHtml;
  container.appendChild(contentWrapper);

  document.body.appendChild(container);

  try {
    const canvas = await html2canvas(container, {
      scale: 2,
      backgroundColor: '#ffffff',
      logging: false,
      useCORS: true,
    });
    const imgData = canvas.toDataURL('image/png');
    const aspect = canvas.height / canvas.width;
    return { imgData, aspect, canvasW: canvas.width, canvasH: canvas.height };
  } catch (e) {
    console.warn('html2canvas render error for trade notes', e);
    return null;
  } finally {
    if (document.body.contains(container)) {
      document.body.removeChild(container);
    }
  }
};

// FIFO trade comparator for PDF export (earliest/first-entered trades first)
const fifoSortTrades = (a, b) => {
  // 1. Compare Date (YYYY-MM-DD ascending)
  const dateA = a.tradeDate || '';
  const dateB = b.tradeDate || '';
  if (dateA !== dateB) return dateA.localeCompare(dateB);

  // 2. Compare Time (normalized HH:MM[:SS] ascending)
  const normTime = (t) => {
    if (!t) return '00:00:00';
    const parts = String(t).trim().split(':');
    const h = (parts[0] || '0').padStart(2, '0');
    const m = (parts[1] || '0').padStart(2, '0');
    const s = (parts[2] || '0').padStart(2, '0');
    return `${h}:${m}:${s}`;
  };
  const timeA = normTime(a.tradeTime);
  const timeB = normTime(b.tradeTime);
  if (timeA !== timeB) return timeA.localeCompare(timeB);

  // 3. Compare Sequence within day (ascending)
  const seqA = Number(a.tradeSequence) || 0;
  const seqB = Number(b.tradeSequence) || 0;
  if (seqA !== seqB) return seqA - seqB;

  // 4. Compare creation timestamp or ID (ascending)
  const getTs = (tr) => {
    if (tr.createdAt) {
      const p = Date.parse(tr.createdAt);
      if (!isNaN(p)) return p;
    }
    const match = String(tr.id || '').match(/JT-(\d+)/);
    if (match) return Number(match[1]);
    return 0;
  };
  const tsA = getTs(a);
  const tsB = getTs(b);
  if (tsA !== tsB) return tsA - tsB;

  return String(a.id || '').localeCompare(String(b.id || ''));
};

const exportSelectedTradesPdf = async () => {
  // Determine trades to export: either explicitly selected, or all currently displayed/filtered
  const rawTrades = selectedTradeIds.value.size > 0
    ? displayedTrades.value.filter((t) => selectedTradeIds.value.has(t.id))
    : displayedTrades.value;

  // Strict FIFO: first entered trade is first shown in the PDF
  const tradesToExport = [...rawTrades].sort(fifoSortTrades);

  if (!tradesToExport || tradesToExport.length === 0) {
    showToast('No trades available to export', 'error');
    return;
  }

  isExportingPdf.value = true;
  showToast(`Generating PDF report for ${tradesToExport.length} trade${tradesToExport.length > 1 ? 's' : ''}...`, 'info');

  // Allow UI time to display spinner and toast
  await new Promise((r) => setTimeout(r, 60));

  try {
    const doc = new jsPDF({
      orientation: 'portrait',
      unit: 'pt',
      format: 'a4',
    });

    const pageWidth = doc.internal.pageSize.getWidth(); // 595.28 pt
    const pageHeight = doc.internal.pageSize.getHeight(); // 841.89 pt
    const marginX = 26;
    const contentWidth = pageWidth - (marginX * 2); // 543.28 pt

    // Pre-load image dimensions for all trades
    const tradeImageMetas = [];
    for (const trade of tradesToExport) {
      const shots = Array.isArray(trade.screenshots) ? trade.screenshots : [];
      const metas = [];
      for (const shot of shots) {
        const dim = await getImageDimensions(shot);
        metas.push(dim);
      }
      tradeImageMetas.push(metas);
    }

    // Pre-render HTML notes for all trades using browser DOM & html2canvas
    const tradeNotesImages = [];
    for (const trade of tradesToExport) {
      if (trade.notes && trade.notes.trim()) {
        const noteImg = await renderHtmlToPdfImage(trade.notes, contentWidth - 20);
        tradeNotesImages.push(noteImg);
      } else {
        tradeNotesImages.push(null);
      }
    }

    // Helper: Draw rounded card panel
    const drawCard = (x, y, w, h, fill = [248, 250, 252], stroke = [226, 232, 240], radius = 4) => {
      doc.setFillColor(fill[0], fill[1], fill[2]);
      doc.setDrawColor(stroke[0], stroke[1], stroke[2]);
      doc.setLineWidth(0.75);
      doc.roundedRect(x, y, w, h, radius, radius, 'FD');
    };

    // Helper: Draw label-value item
    const drawMetaRow = (x, y, label, value, valColor = [15, 23, 42], isBold = false) => {
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8.5);
      doc.setTextColor(100, 116, 139);
      doc.text(label, x, y);

      const labelWidth = doc.getTextWidth(label);
      doc.setFont('helvetica', isBold ? 'bold' : 'normal');
      doc.setFontSize(9);
      doc.setTextColor(valColor[0], valColor[1], valColor[2]);
      doc.text(String(value), x + labelWidth + 4.5, y);
    };

    for (let i = 0; i < tradesToExport.length; i++) {
      if (i > 0) doc.addPage();
      const trade = tradesToExport[i];
      const metas = tradeImageMetas[i] || [];
      const shots = Array.isArray(trade.screenshots) ? trade.screenshots : [];

      // ----------------------------------------------------------------------
      // 1. TOP HEADER BANNER (Y = 22 to 54 pt, Height = 32 pt)
      // ----------------------------------------------------------------------
      const headerY = 22;
      const headerH = 32;
      doc.setFillColor(15, 23, 42); // deep navy #0f172a
      doc.setDrawColor(30, 41, 59);
      doc.roundedRect(marginX, headerY, contentWidth, headerH, 4, 4, 'F');

      // Left: Ticker Symbol (Centered vertically, NO date, NO time, NO direction)
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(17);
      doc.setTextColor(255, 255, 255);
      const symbolText = (trade.symbol || 'UNTITLED').toUpperCase();
      doc.text(symbolText, marginX + 12, headerY + 21);

      // Right: Session & Sequence Pill
      const sessionObj = getSessionMeta(trade.session);
      const seqText = `#${trade.tradeSequence || 1} Trade  ·  ${sessionObj.label}`;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(203, 213, 225);
      doc.text(seqText, marginX + contentWidth - 12, headerY + 20, { align: 'right' });

      let currentY = headerY + headerH + 1.5;

      // ----------------------------------------------------------------------
      // 2. SCREENSHOT SECTION (Tight fit, ~500x130, attached directly to banner)
      // ----------------------------------------------------------------------
      const hasScreenshots = shots.length > 0;

      if (hasScreenshots) {
        for (let sIdx = 0; sIdx < shots.length; sIdx++) {
          const shot = shots[sIdx];
          if (!shot) continue;

          const dim = metas[sIdx] || { width: 500, height: 130 };
          const maxW = Math.min(contentWidth - 6, 510);
          const maxH = 136; // Target height ~130 pt as requested
          const imgW = dim.width || 500;
          const imgH = dim.height || 130;
          const ratio = Math.min(maxW / imgW, maxH / imgH);
          const rW = Math.round(imgW * ratio);
          const rH = Math.round(imgH * ratio);
          const shotBoxH = rH + 4; // Snug vertical fit with no dead empty space

          // If adding this image row exceeds the printable page area, start a new page
          if (currentY + shotBoxH > 800) {
            doc.setDrawColor(226, 232, 240);
            doc.setLineWidth(0.75);
            doc.line(marginX, 818, marginX + contentWidth, 818);

            doc.addPage();
            // Redraw top banner on new page
            doc.setFillColor(15, 23, 42);
            doc.roundedRect(marginX, headerY, contentWidth, headerH, 4, 4, 'F');
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(16);
            doc.setTextColor(255, 255, 255);
            doc.text(`${symbolText} (Cont.)`, marginX + 12, headerY + 21);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(8.5);
            doc.setTextColor(203, 213, 225);
            doc.text(seqText, marginX + contentWidth - 12, headerY + 20, { align: 'right' });
            currentY = headerY + headerH + 1.5;
          }

          drawCard(marginX, currentY, contentWidth, shotBoxH, [248, 250, 252], [226, 232, 240]);

          const imgX = marginX + Math.round((contentWidth - rW) / 2);
          const imgY = currentY + 2;

          try {
            const fmt = shot.startsWith('data:image/png') ? 'PNG' : 'JPEG';
            doc.addImage(shot, fmt, imgX, imgY, rW, rH);
          } catch (e) {
            console.warn(`Screenshot ${sIdx + 1} render failed`, e);
            doc.setFont('helvetica', 'italic');
            doc.setFontSize(8.5);
            doc.setTextColor(148, 163, 184);
            doc.text(`Chart Screenshot #${sIdx + 1} (Failed to load)`, marginX + (contentWidth / 2), currentY + Math.round(shotBoxH / 2), { align: 'center' });
          }

          currentY += shotBoxH + 3;
        }
      } else {
        // Subtle placeholder banner when no screenshot
        const placeH = 26;
        drawCard(marginX, currentY, contentWidth, placeH, [248, 250, 252], [226, 232, 240]);
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(8);
        doc.setTextColor(148, 163, 184);
        doc.text('No Chart Screenshot Attached for this Trade Record', marginX + (contentWidth / 2), currentY + 17, { align: 'center' });
        currentY += placeH + 3;
      }

      // ----------------------------------------------------------------------
      // 3. INTERNAL REFLECTION & NOTES (Directly below image, RTL Arabic)
      // ----------------------------------------------------------------------
      // Check if details need a fresh page
      if (currentY + 246 > 810) {
        doc.setDrawColor(226, 232, 240);
        doc.setLineWidth(0.75);
        doc.line(marginX, 818, marginX + contentWidth, 818);

        doc.addPage();
        doc.setFillColor(15, 23, 42);
        doc.roundedRect(marginX, headerY, contentWidth, headerH, 4, 4, 'F');
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(16);
        doc.setTextColor(255, 255, 255);
        doc.text(`${symbolText} (Cont.)`, marginX + 12, headerY + 21);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(8.5);
        doc.setTextColor(203, 213, 225);
        doc.text(seqText, marginX + contentWidth - 12, headerY + 20, { align: 'right' });
        currentY = headerY + headerH + 1.5;
      }
      // ----------------------------------------------------------------------
      const noteImg = tradeNotesImages[i];
      const maxAllowedNotesH = Math.max(50, 810 - 246 - currentY);
      let notesH = 38;

      if (noteImg && noteImg.imgData) {
        const naturalH = Math.round((contentWidth - 20) * noteImg.aspect);
        notesH = Math.min(maxAllowedNotesH, Math.max(48, naturalH + 14));
      } else if (trade.notes && trade.notes.trim()) {
        const plainText = trade.notes.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
        const splitNotes = doc.splitTextToSize(plainText, contentWidth - 20);
        notesH = Math.min(maxAllowedNotesH, Math.max(38, splitNotes.length * 11 + 16));
      }

      drawCard(marginX, currentY, contentWidth, notesH, [255, 255, 255], [226, 232, 240]);

      if (noteImg && noteImg.imgData) {
        const maxRenderW = contentWidth - 20;
        const maxRenderH = notesH - 12;
        const aspect = noteImg.aspect;
        let rW = maxRenderW;
        let rH = rW * aspect;
        if (rH > maxRenderH) {
          rH = maxRenderH;
          rW = rH / aspect;
        }
        // Align right for RTL Arabic layout
        const imgX = marginX + contentWidth - 10 - rW;
        try {
          doc.addImage(noteImg.imgData, 'PNG', imgX, currentY + 6, rW, rH);
        } catch (e) {
          console.warn('Failed to draw html2canvas image to doc', e);
        }
      } else if (trade.notes && trade.notes.trim()) {
        const plainText = trade.notes.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(9.5);
        doc.setTextColor(51, 65, 85);
        const splitNotes = doc.splitTextToSize(plainText, contentWidth - 20);
        const maxLines = Math.floor((notesH - 14) / 13);
        const linesToDraw = splitNotes.slice(0, maxLines);
        if (splitNotes.length > maxLines) {
          linesToDraw[maxLines - 1] = (linesToDraw[maxLines - 1] || '').substring(0, 80) + '...';
        }
        let noteLineY = currentY + 17;
        for (const line of linesToDraw) {
          doc.text(line, marginX + contentWidth - 10, noteLineY, { align: 'right' });
          noteLineY += 13;
        }
      } else {
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(8.5);
        doc.setTextColor(148, 163, 184);
        doc.text('No internal reflection recorded for this trade.', marginX + (contentWidth / 2), currentY + 22, { align: 'center' });
      }

      currentY += notesH + 6;

      // ----------------------------------------------------------------------
      // 4. TWO-COLUMN DETAILS: TECHNICAL LEVELS & ENTRY DISCIPLINE
      // ----------------------------------------------------------------------
      const midGap = 8;
      const subCardW = (contentWidth - midGap) / 2;
      const subCardH = 114;

      // Left Box: Technical Levels (contains Entry Price and Setup & Sequence)
      drawCard(marginX, currentY, subCardW, subCardH, [248, 250, 252], [226, 232, 240]);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8.5);
      doc.setTextColor(15, 23, 42);
      doc.text('TECHNICAL LEVELS AT ENTRY', marginX + 10, currentY + 15);

      let techY = currentY + 30;
      const entryPriceStr = trade.entryPrice ? `$${Number(trade.entryPrice).toFixed(2)}` : 'N/A';
      drawMetaRow(marginX + 10, techY, 'Entry Price:', entryPriceStr, [15, 23, 42], true);

      techY += 14.5;
      const setupType = trade.frontsideSetup === true ? 'Frontside Setup' : trade.frontsideSetup === false ? 'Backside Setup' : 'Setup Not Logged';
      const seqStr = trade.tradeSequence ? ` (#${trade.tradeSequence} Trade)` : '';
      drawMetaRow(marginX + 10, techY, 'Setup & Sequence:', `${setupType}${seqStr}`, [14, 165, 233], true);

      techY += 14.5;
      drawMetaRow(marginX + 10, techY, '9 EMA Value:', trade.ema9Value ? `$${Number(trade.ema9Value).toFixed(2)}` : 'Not recorded', [15, 23, 42], true);

      techY += 14.5;
      drawMetaRow(marginX + 10, techY, 'VWAP Value:', trade.vwapValue ? `$${Number(trade.vwapValue).toFixed(2)}` : 'Not recorded', [15, 23, 42], true);

      techY += 14.5;
      drawMetaRow(marginX + 10, techY, 'Nearest Resistance:', trade.nearestResistance ? `$${Number(trade.nearestResistance).toFixed(2)}` : 'Not recorded', [15, 23, 42], true);

      techY += 14.5;
      drawMetaRow(marginX + 10, techY, 'Market Session:', sessionObj.label, [51, 65, 85], false);

      // Right Box: Entry Discipline
      const rightBoxX = marginX + subCardW + midGap;
      drawCard(rightBoxX, currentY, subCardW, subCardH, [248, 250, 252], [226, 232, 240]);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8.5);
      doc.setTextColor(15, 23, 42);
      doc.text('ENTRY DISCIPLINE & DEVIATION', rightBoxX + 10, currentY + 15);

      let entryDisY = currentY + 30;
      const isPredefined = trade.predefinedEntry;
      const predefColor = isPredefined === true ? [16, 185, 129] : isPredefined === false ? [225, 29, 72] : [100, 116, 139];
      const predefLabel = isPredefined === true ? 'Yes (Planned)' : isPredefined === false ? 'No (Impulsive / Mistake)' : 'Unspecified';
      drawMetaRow(rightBoxX + 10, entryDisY, 'Predefined Entry:', predefLabel, predefColor, true);

      entryDisY += 14.5;
      const planPriceStr = trade.plannedEntryPrice ? `$${Number(trade.plannedEntryPrice).toFixed(2)}` : 'Same as execution';
      drawMetaRow(rightBoxX + 10, entryDisY, 'Planned Price:', planPriceStr, [15, 23, 42], true);

      entryDisY += 14.5;
      drawMetaRow(rightBoxX + 10, entryDisY, 'Entry Type:', trade.entryType || 'Not specified', [14, 165, 233], true);

      entryDisY += 14.5;
      const devStr = trade.enteredAtPredefinedPrice === false
        ? `Entered ${trade.entryDeviationDirection || 'Off-plan'}${trade.entryDeviationReason ? ' (' + trade.entryDeviationReason.substring(0, 32) + '...)' : ''}`
        : 'Executed on-plan at planned price';
      const devColor = trade.enteredAtPredefinedPrice === false ? [225, 29, 72] : [16, 185, 129];
      drawMetaRow(rightBoxX + 10, entryDisY, 'Deviation:', devStr, devColor, false);

      currentY += subCardH + 6;

      // ----------------------------------------------------------------------
      // 5. TWO-COLUMN DETAILS: RISK MANAGEMENT & PSYCHOLOGY
      // ----------------------------------------------------------------------
      const riskCardH = 92;

      // Left Box: Risk Management
      drawCard(marginX, currentY, subCardW, riskCardH, [248, 250, 252], [226, 232, 240]);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8.5);
      doc.setTextColor(15, 23, 42);
      doc.text('RISK MANAGEMENT EXECUTION', marginX + 10, currentY + 15);

      let riskY = currentY + 30;
      const stopVal = trade.predefinedStopLoss;
      const stopLabel = stopVal === true ? `Yes${trade.stopLossPrice ? ' ($' + Number(trade.stopLossPrice).toFixed(2) + ')' : ''}` : stopVal === false ? 'No Stop Defined (Critical Mistake)' : 'Unspecified';
      const stopColor = stopVal === true ? [16, 185, 129] : stopVal === false ? [225, 29, 72] : [100, 116, 139];
      drawMetaRow(marginX + 10, riskY, 'Predefined Stop Loss:', stopLabel, stopColor, true);

      riskY += 14.5;
      const avgDown = trade.averagedDown;
      const avgLabel = avgDown === true ? `Yes (Critical Mistake)${trade.averagedDownReason ? ' - ' + trade.averagedDownReason.substring(0, 24) : ''}` : avgDown === false ? 'No (Disciplined)' : 'Unspecified';
      const avgColor = avgDown === true ? [225, 29, 72] : [16, 185, 129];
      drawMetaRow(marginX + 10, riskY, 'Averaged Down:', avgLabel, avgColor, true);

      riskY += 14.5;
      const flushVal = trade.flushOccurred;
      const flushLabel = flushVal === true ? `Yes, Caught in Flush${trade.flushReason ? ' (' + trade.flushReason.substring(0, 26) + ')' : ''}` : flushVal === false ? 'No' : 'Unspecified';
      const flushColor = flushVal === true ? [225, 29, 72] : [51, 65, 85];
      drawMetaRow(marginX + 10, riskY, 'Caught in Flush?:', flushLabel, flushColor, false);

      riskY += 14.5;
      const rrrEst = trade.entryPrice && trade.stopLossPrice ? `Risk: $${Math.abs(Number(trade.entryPrice) - Number(trade.stopLossPrice)).toFixed(2)} / share` : 'N/A';
      drawMetaRow(marginX + 10, riskY, 'Calculated Risk:', rrrEst, [51, 65, 85], false);

      // Right Box: Psychology & Final Exit
      drawCard(rightBoxX, currentY, subCardW, riskCardH, [248, 250, 252], [226, 232, 240]);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8.5);
      doc.setTextColor(15, 23, 42);
      doc.text('EXECUTION PSYCHOLOGY & TRAPS', rightBoxX + 10, currentY + 15);

      let psychY = currentY + 30;
      const frozeVal = trade.frozeOnLoss;
      const frozeLabel = frozeVal === true ? `Yes (Froze During Loss)${trade.frozeReason ? ' - ' + trade.frozeReason.substring(0, 24) : ''}` : frozeVal === false ? 'No (Cut Decisively)' : 'Unspecified';
      const frozeColor = frozeVal === true ? [225, 29, 72] : [16, 185, 129];
      drawMetaRow(rightBoxX + 10, psychY, 'Froze on Loss?:', frozeLabel, frozeColor, true);

      psychY += 14.5;
      const exitTypeVal = trade.finalExitType;
      const exitLabel = exitTypeVal === 'FEAR' ? 'Fear Exit (Premature / Panic)' : exitTypeVal === 'SETUP' ? 'Setup Exit (Target Met / Plan Followed)' : 'Unspecified';
      const exitColor = exitTypeVal === 'FEAR' ? [225, 29, 72] : exitTypeVal === 'SETUP' ? [16, 185, 129] : [100, 116, 139];
      drawMetaRow(rightBoxX + 10, psychY, 'Final Exit Type:', exitLabel, exitColor, true);

      psychY += 14.5;
      const fearReasonStr = trade.finalExitFearReason ? `"${trade.finalExitFearReason.substring(0, 48)}"` : 'None cited';
      drawMetaRow(rightBoxX + 10, psychY, 'Exit Reason:', fearReasonStr, [100, 116, 139], false);

      psychY += 14.5;
      const seqWarn = Number(trade.tradeSequence) >= 3 ? 'High Fatigue Risk (3rd+ Trade)' : 'Normal Fatigue Zone';
      const seqWarnColor = Number(trade.tradeSequence) >= 3 ? [217, 119, 6] : [51, 65, 85];
      drawMetaRow(rightBoxX + 10, psychY, 'Overtrading State:', seqWarn, seqWarnColor, false);

      currentY += riskCardH + 6;

      // ----------------------------------------------------------------------
      // 6. BEHAVIORAL MISTAKES AUDIT
      // ----------------------------------------------------------------------
      const mistakes = Array.isArray(trade.mistakes) ? trade.mistakes : [];
      const isClean = trade.isClean || mistakes.length === 0;

      if (isClean) {
        const cleanH = 26;
        drawCard(marginX, currentY, contentWidth, cleanH, [236, 253, 245], [16, 185, 129]);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(8.5);
        doc.setTextColor(5, 150, 105);
        doc.text('CLEAN EXECUTION - ZERO BEHAVIORAL MISTAKES COMMITTED', marginX + 12, currentY + 17);
        currentY += cleanH + 6;
      } else {
        const flawBoxH = 38;
        drawCard(marginX, currentY, contentWidth, flawBoxH, [255, 241, 242], [244, 63, 94]);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(8.5);
        doc.setTextColor(225, 29, 72);
        doc.text(`BEHAVIORAL MISTAKES DETECTED (${mistakes.length})`, marginX + 10, currentY + 14);

        const mistakeTitles = mistakes.map((m) => `[${m.title}]`).join('   ');
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(8.5);
        doc.setTextColor(159, 18, 57);
        const mistakeLines = doc.splitTextToSize(mistakeTitles, contentWidth - 20);
        doc.text(mistakeLines[0] || '', marginX + 10, currentY + 27);
        currentY += flawBoxH + 6;
      }

      // ----------------------------------------------------------------------
      // 7. PAGE FOOTER (Y = 818 to 832 pt)
      // ----------------------------------------------------------------------
      doc.setDrawColor(226, 232, 240);
      doc.setLineWidth(0.75);
      doc.line(marginX, 818, marginX + contentWidth, 818);

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      const nowStr = new Date().toLocaleString();
      doc.text(`Trading Journal Performance Audit · Generated ${nowStr}`, marginX, 829);

      doc.setFont('helvetica', 'bold');
      doc.text(`Trade ${i + 1} of ${tradesToExport.length}  |  Page ${i + 1} of ${tradesToExport.length}`, marginX + contentWidth, 829, { align: 'right' });
    }

    const todayDateStr = new Date().toISOString().split('T')[0];
    const fileName = `trading_journal_trades_${todayDateStr}_${tradesToExport.length}trades.pdf`;
    doc.save(fileName);
    showToast(`Successfully exported ${tradesToExport.length} trade${tradesToExport.length > 1 ? 's' : ''} to ${fileName}`, 'success');
  } catch (err) {
    console.error('Failed to export PDF:', err);
    showToast('Failed to generate PDF. Check browser console.', 'error');
  } finally {
    isExportingPdf.value = false;
  }
};
</script>

<template>
  <div class="journal-root">
    <!-- Toast Notification -->
    <transition name="fade">
      <div v-if="toast.show" class="toast-popup" :class="toast.type">
        <span>{{ toast.message }}</span>
      </div>
    </transition>

    <!-- Top Header & Navigation -->
    <header class="journal-header glass-card">
      <div class="header-left">
        <div class="brand-badge">
          <div class="brand-icon">
            <BrainCircuit :size="20" />
          </div>
          <div>
            <h1 class="brand-title">TRADING JOURNAL</h1>
            <p class="brand-sub">Behavioral Performance & Mistake Analysis System</p>
          </div>
        </div>

        <!-- Navigation Tabs -->
        <nav class="nav-tabs">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'analytics' }"
            @click="activeTab = 'analytics'"
          >
            <BarChart2 :size="15" />
            <span>Behavioral Analytics</span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'weekly' }"
            @click="activeTab = 'weekly'"
          >
            <Calendar :size="15" />
            <span>Weekly Review</span>
            <span v-if="weeklyReview.currentStats.totalMistakes > 0" class="badge-pill warn">
              {{ weeklyReview.currentStats.totalMistakes }}
            </span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'history' }"
            @click="activeTab = 'history'"
          >
            <BookOpen :size="15" />
            <span>Trade Log ({{ enrichedTrades.length }})</span>
          </button>
        </nav>
      </div>

      <div class="header-actions">
        <!-- Date Scope Filter (for Analytics) -->
        <div v-if="activeTab === 'analytics'" class="date-chips">
          <button
            class="chip-btn"
            :class="{ active: selectedDateFilter === 'ALL' }"
            @click="selectedDateFilter = 'ALL'"
          >
            All Time
          </button>
          <button
            class="chip-btn"
            :class="{ active: selectedDateFilter === 'THIS_MONTH' }"
            @click="selectedDateFilter = 'THIS_MONTH'"
          >
            This Month
          </button>
          <button
            class="chip-btn"
            :class="{ active: selectedDateFilter === 'THIS_WEEK' }"
            @click="selectedDateFilter = 'THIS_WEEK'"
          >
            This Week
          </button>
          <button
            class="chip-btn"
            :class="{ active: selectedDateFilter === 'LAST_WEEK' }"
            @click="selectedDateFilter = 'LAST_WEEK'"
          >
            Last Week
          </button>
        </div>

        <!-- Main Add Trade Button -->
        <button class="btn-primary-glow" @click="openAddModal">
          <Plus :size="18" />
          <span>Add Trade</span>
        </button>

        <!-- Utility Actions Menu -->
        <div class="utility-actions">
          <!-- JSON Storage Status Pill & Reload Action -->
          <div
            class="json-file-status-pill"
            :title="`Persistent JSON File:\n${jsonFileInfo.filePath || 'data/journal_trades.json'}\n\nClick to reload fresh from disk file`"
            @click="reloadFromJsonFile"
          >
            <span class="file-dot" :class="isBackendConnected ? 'connected' : 'disconnected'"></span>
            <FileJson :size="14" class="file-icon" />
            <span class="file-label">data/journal_trades.json</span>
            <span class="file-count" v-if="jsonFileInfo.tradeCount !== undefined">({{ trades.length }})</span>
          </div>

          <button
            class="btn-icon"
            :class="{ 'icon-spin': isReloading }"
            title="Reload fresh from data/journal_trades.json"
            @click="reloadFromJsonFile"
          >
            <RefreshCw :size="16" />
          </button>
          <button class="btn-icon" title="Export Backup (JSON)" @click="exportDataJson">
            <Download :size="16" />
          </button>
          <button class="btn-icon danger" title="Clear All Trades" @click="clearAllTrades">
            <Trash2 :size="16" />
          </button>
        </div>
      </div>
    </header>

    <!-- MAIN BODY CONTAINER -->
    <main class="journal-main">
      <!-- Empty state when 0 trades logged -->
      <div v-if="enrichedTrades.length === 0" class="empty-journal-card glass-card">
        <div class="ej-icon">
          <BrainCircuit :size="48" />
        </div>
        <h2 class="ej-title">Your Trading Journal is Ready</h2>
        <p class="ej-desc">
          Analytics and behavioral mistake tracking count <strong>strictly from your manual entries</strong>.
          Click below to record your first trade, define your planned price, and track your execution discipline.
        </p>
        <button class="btn-primary-glow mx-auto" @click="openAddModal">
          <Plus :size="18" />
          <span>Log First Manual Trade</span>
        </button>
      </div>

      <!-- ================================================================= -->
      <!-- TAB 1: BEHAVIORAL ANALYTICS & MISTAKES DEEP DIVE                  -->
      <!-- ================================================================= -->
      <section v-else-if="activeTab === 'analytics'" class="analytics-tab space-y-6">
        <!-- 1. Overall Trading Statistics KPI Cards -->
        <div class="kpi-grid">
          <!-- Total Trades -->
          <div class="kpi-card glass-card">
            <div class="kpi-icon-wrap blue">
              <Layers :size="20" />
            </div>
            <div class="kpi-content">
              <span class="kpi-label">TOTAL TRADES</span>
              <div class="kpi-val">{{ overallStats.totalTrades }}</div>
              <span class="kpi-sub text-muted">Manually recorded trades</span>
            </div>
          </div>

          <!-- Total Mistakes -->
          <div class="kpi-card glass-card">
            <div class="kpi-icon-wrap rose">
              <AlertTriangle :size="20" />
            </div>
            <div class="kpi-content">
              <span class="kpi-label">TOTAL MISTAKES</span>
              <div class="kpi-val text-rose">{{ overallStats.totalMistakes }}</div>
              <span class="kpi-sub text-muted">
                Avg {{ overallStats.mistakesPerFlawedTrade }} per flawed trade
              </span>
            </div>
          </div>

          <!-- Discipline Score (Clean Trades %) -->
          <div class="kpi-card glass-card highlight-border">
            <div
              class="kpi-icon-wrap"
              :class="overallStats.cleanPercentage >= 70 ? 'green' : 'amber'"
            >
              <Award :size="20" />
            </div>
            <div class="kpi-content">
              <span class="kpi-label">DISCIPLINE SCORE</span>
              <div
                class="kpi-val"
                :class="overallStats.cleanPercentage >= 70 ? 'text-green' : 'text-amber'"
              >
                {{ overallStats.cleanPercentage }}%
              </div>
              <div class="progress-bar-wrap">
                <div
                  class="progress-bar"
                  :style="{
                    width: `${overallStats.cleanPercentage}%`,
                    backgroundColor: overallStats.cleanPercentage >= 70 ? '#10b981' : '#f59e0b',
                  }"
                ></div>
              </div>
              <span class="kpi-sub text-muted">
                {{ overallStats.cleanTrades }} of {{ overallStats.totalTrades }} trades 100% clean
              </span>
            </div>
          </div>

          <!-- Trades with Mistakes (%) -->
          <div class="kpi-card glass-card">
            <div class="kpi-icon-wrap purple">
              <ShieldAlert :size="20" />
            </div>
            <div class="kpi-content">
              <span class="kpi-label">TRADES WITH MISTAKES</span>
              <div class="kpi-val text-amber">{{ overallStats.tradesWithMistakes }}</div>
              <span class="kpi-sub text-muted">
                {{ overallStats.mistakePercentage }}% of all trades affected
              </span>
            </div>
          </div>

          <!-- Most Repeated Mistake -->
          <div class="kpi-card glass-card span-2">
            <div class="kpi-icon-wrap red">
              <Flame :size="20" />
            </div>
            <div class="kpi-content">
              <span class="kpi-label">#1 MOST REPEATED MISTAKE</span>
              <div v-if="overallStats.mostFrequentMistake" class="most-frequent-box">
                <span class="mf-title">{{ overallStats.mostFrequentMistake.title }}</span>
                <div class="mf-tags">
                  <span class="badge-pill red">
                    {{ overallStats.mostFrequentMistake.count }} occurrences
                  </span>
                  <span class="badge-pill outline">
                    {{ overallStats.mostFrequentMistake.percentage }}% of trades
                  </span>
                  <span class="badge-pill outline">
                    {{ overallStats.mostFrequentMistake.category }}
                  </span>
                </div>
              </div>
              <div v-else class="text-muted italic">Zero mistakes committed! Flawless discipline 🎯</div>
            </div>
          </div>
        </div>

        <!-- 2. Mistake Frequency Analysis (Dedicated Section) -->
        <div class="section-card glass-card">
          <div class="section-header">
            <div>
              <h2 class="section-title">Mistake Frequency & Trend Analysis</h2>
              <p class="section-sub">
                Track how often each behavioral rule is broken and whether it is increasing or decreasing over time.
              </p>
            </div>
            <span class="text-xs text-muted">
              Trend compares recent 50% vs prior 50% trades
            </span>
          </div>

          <div class="mistake-list">
            <div
              v-for="item in mistakeFrequencyList"
              :key="item.id"
              class="mistake-row"
              :class="{ 'has-occurrences': item.count > 0 }"
            >
              <!-- Left: Identity & Category -->
              <div class="m-left">
                <div class="m-color-indicator" :style="{ backgroundColor: item.color }"></div>
                <div class="m-info">
                  <div class="m-title-row">
                    <span class="m-title">{{ item.title }}</span>
                    <span class="badge-cat" :style="{ color: item.color, borderColor: item.border, background: item.bg }">
                      {{ item.category }}
                    </span>
                  </div>
                  <p class="m-desc">{{ item.description }}</p>
                </div>
              </div>

              <!-- Center: Visual Bar & Numbers -->
              <div class="m-center">
                <div class="m-bar-bg">
                  <div
                    class="m-bar-fill"
                    :style="{
                      width: `${item.percentage}%`,
                      backgroundColor: item.color,
                    }"
                  ></div>
                </div>
                <div class="m-stats">
                  <span class="m-count">{{ item.count }} times</span>
                  <span class="m-pct">({{ item.percentage }}% of trades)</span>
                </div>
              </div>

              <!-- Right: Trend Indicator -->
              <div class="m-right">
                <div
                  v-if="item.trend === 'increasing'"
                  class="trend-tag bad"
                  title="Frequency is increasing in recent trades"
                >
                  <TrendingUp :size="14" />
                  <span>Increasing (+{{ item.trendDelta }}%)</span>
                </div>
                <div
                  v-else-if="item.trend === 'decreasing'"
                  class="trend-tag good"
                  title="Discipline is improving on this rule"
                >
                  <TrendingDown :size="14" />
                  <span>Decreasing ({{ item.trendDelta }}%)</span>
                </div>
                <div v-else class="trend-tag neutral" title="Frequency remains unchanged">
                  <Minus :size="14" />
                  <span>Stable</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 3. Behavioral Patterns Deep-Dive (3 Columns: Sequence, Frontside, Sessions) -->
        <div class="patterns-grid">
          <!-- Pattern A: Overtrading by Trade Sequence -->
          <div class="pattern-card glass-card">
            <div class="pattern-header">
              <div class="p-icon yellow"><Clock :size="18" /></div>
              <div>
                <h3 class="pattern-title">Trade Sequence vs Mistake Rate</h3>
                <p class="pattern-sub">Does executing multiple trades on the same stock trigger emotional mistakes?</p>
              </div>
            </div>
            <div class="sequence-bars">
              <div
                v-for="seq in sequenceImpactStats"
                :key="seq.label"
                class="seq-item"
              >
                <div class="seq-top">
                  <span class="seq-label">{{ seq.label }}</span>
                  <span class="seq-rate" :class="seq.flawRate > 50 ? 'text-red' : 'text-muted'">
                    {{ seq.flawRate }}% Mistake Rate ({{ seq.flawed }}/{{ seq.total }})
                  </span>
                </div>
                <div class="seq-progress-wrap">
                  <div
                    class="seq-progress"
                    :style="{
                      width: `${seq.flawRate}%`,
                      backgroundColor: seq.flawRate > 50 ? '#ef4444' : '#f59e0b',
                    }"
                  ></div>
                </div>
              </div>
            </div>
            <div class="pattern-note">
              <span class="text-amber font-bold">Insight:</span> Scalpers frequently take revenge or overstay on the 3rd and 4th trades of a ticker after the primary setup has concluded.
            </div>
          </div>

          <!-- Pattern B: Frontside Setup Edge -->
          <div class="pattern-card glass-card">
            <div class="pattern-header">
              <div class="p-icon orange"><Target :size="18" /></div>
              <div>
                <h3 class="pattern-title">Frontside Setup Discipline</h3>
                <p class="pattern-sub">Comparing execution quality on Frontside momentum vs Backside chop</p>
              </div>
            </div>
            <div class="frontside-boxes">
              <div class="fs-box green">
                <div class="fs-head">Frontside Setups</div>
                <div class="fs-val text-green">
                  {{ frontsideImpactStats.frontside.rate }}% Flawed
                </div>
                <div class="fs-sub">
                  {{ frontsideImpactStats.frontside.total }} recorded trades
                </div>
              </div>
              <div class="fs-box red">
                <div class="fs-head">Backside Setups</div>
                <div class="fs-val text-red">
                  {{ frontsideImpactStats.backside.rate }}% Flawed
                </div>
                <div class="fs-sub">
                  {{ frontsideImpactStats.backside.total }} recorded trades
                </div>
              </div>
            </div>
            <div class="pattern-note">
              <span class="text-orange font-bold">Insight:</span> Trading against the primary trend (Backside) dramatically increases the probability of averaging down, freezing, and chasing.
            </div>
          </div>

          <!-- Pattern C: Trading Session Discipline -->
          <div class="pattern-card glass-card">
            <div class="pattern-header">
              <div class="p-icon purple"><SunMedium :size="18" /></div>
              <div>
                <h3 class="pattern-title">Trading Session Breakdown</h3>
                <p class="pattern-sub">Mistake frequency across market sessions</p>
              </div>
            </div>
            <div class="sequence-bars">
              <div
                v-for="sess in sessionImpactStats"
                :key="sess.id"
                class="seq-item"
              >
                <div class="seq-top">
                  <span class="seq-label" :style="{ color: sess.color }">{{ sess.label }}</span>
                  <span class="seq-rate" :class="sess.flawRate > 50 ? 'text-red' : 'text-muted'">
                    {{ sess.flawRate }}% ({{ sess.flawed }}/{{ sess.total }})
                  </span>
                </div>
                <div class="seq-progress-wrap">
                  <div
                    class="seq-progress"
                    :style="{
                      width: `${sess.flawRate}%`,
                      backgroundColor: sess.color,
                    }"
                  ></div>
                </div>
              </div>
            </div>
            <div class="pattern-note">
              <span class="text-purple font-bold">Insight:</span> Mid-day chop often produces premature entries and overtrading compared to clean Morning Open trends.
            </div>
          </div>
        </div>

        <!-- 4. Mistake Categories Distribution -->
        <div class="section-card glass-card">
          <div class="section-header">
            <div>
              <h2 class="section-title">Root Cause Categories</h2>
              <p class="section-sub">Where does your trading friction originate?</p>
            </div>
          </div>
          <div class="category-bars-grid">
            <div
              v-for="cat in categoryDistribution"
              :key="cat.id"
              class="cat-bar-card"
            >
              <div class="cat-bar-header">
                <span class="cat-bar-name" :style="{ color: cat.color }">{{ cat.label }}</span>
                <span class="cat-bar-num">{{ cat.count }} mistakes ({{ cat.percentage }}%)</span>
              </div>
              <div class="cat-bar-outer">
                <div
                  class="cat-bar-inner"
                  :style="{ width: `${cat.percentage}%`, backgroundColor: cat.color }"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Recent Logged Trades (Click any row to edit) -->
        <div v-if="enrichedTrades.length > 0" class="section-card glass-card">
          <div class="section-header flex items-center justify-between">
            <div>
              <h2 class="section-title">Recent Logged Trades (Click any row to edit)</h2>
              <p class="section-sub">Quickly inspect or click any trade row to update its entry, levels, or rules.</p>
            </div>
            <button
              type="button"
              class="btn-secondary-sm"
              @click="activeTab = 'history'"
            >
              View All {{ enrichedTrades.length }} Trades →
            </button>
          </div>

          <div class="trades-container space-y-3 mt-4">
            <div
              v-for="trade in recentTrades"
              :key="'recent-' + trade.id"
              class="trade-card glass-card clickable-row"
              :class="{ 'has-flaws': trade.mistakesCount > 0, 'is-clean': trade.isClean }"
              title="Click to edit / update this trade record"
              @click="openEditModal(trade)"
            >
              <div class="tc-header">
                <div class="tc-left">
                  <span class="tc-symbol">{{ trade.symbol }}</span>
                  <span
                    class="badge-session-pill"
                    :style="{ color: getSessionMeta(trade.session).color, borderColor: getSessionMeta(trade.session).color, background: getSessionMeta(trade.session).bg }"
                  >
                    {{ getSessionMeta(trade.session).label }}
                  </span>
                  <span class="badge-seq" :class="{ 'warn': trade.tradeSequence >= 3 }">
                    #{{ trade.tradeSequence }} Trade
                  </span>
                  <span
                    class="badge-fs"
                    :class="trade.frontsideSetup === true ? 'front' : trade.frontsideSetup === false ? 'back' : 'none'"
                  >
                    {{ trade.frontsideSetup === true ? 'Frontside' : trade.frontsideSetup === false ? 'Backside' : 'Setup Unspecified' }}
                  </span>
                  <!-- Entry price next to frontside & market type boxes -->
                  <span class="tc-entry-inline">
                    Entry: <strong>${{ Number(trade.entryPrice).toFixed(2) }}</strong>
                    <span v-if="trade.tradeDate || trade.tradeTime" class="tc-entry-time">
                      at "{{ formatTradeDateTime(trade.tradeDate, trade.tradeTime) }}"
                    </span>
                  </span>
                </div>

                <div class="tc-center"></div>

                <div class="tc-right">
                  <button
                    class="btn-row-action"
                    title="Edit Trade"
                    @click.stop="openEditModal(trade)"
                  >
                    <Edit3 :size="15" />
                  </button>
                </div>
              </div>

              <!-- Mistakes Summary Badges Bar -->
              <div class="tc-mistakes-bar">
                <div v-if="trade.isClean" class="clean-badge">
                  <CheckCircle2 :size="14" />
                  <span>CLEAN EXECUTION — ZERO MISTAKES</span>
                </div>
                <div v-else class="mistake-pills-wrap">
                  <span
                    v-for="m in trade.mistakes"
                    :key="m.id"
                    class="mistake-pill"
                    :style="{ backgroundColor: m.bg, borderColor: m.border, color: m.color }"
                  >
                    <AlertTriangle :size="12" />
                    <span>{{ m.title }}</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ================================================================= -->
      <!-- TAB 2: WEEKLY PERFORMANCE REVIEW                                  -->
      <!-- ================================================================= -->
      <section v-else-if="activeTab === 'weekly'" class="weekly-tab space-y-6">
        <!-- Week Navigator -->
        <div class="week-nav-card glass-card">
          <div class="wn-left">
            <button class="nav-arrow-btn" @click="prevWeek">
              <ChevronLeft :size="18" />
              <span>Prior Week</span>
            </button>
            <div class="wn-label-box">
              <span class="wn-title">WEEKLY AUDIT:</span>
              <span class="wn-range">{{ weeklyReview.weekLabel }}</span>
            </div>
            <button class="nav-arrow-btn" @click="nextWeek">
              <span>Next Week</span>
              <ChevronRight :size="18" />
            </button>
          </div>
          <button class="btn-ghost" @click="resetToCurrentWeek">
            <RefreshCw :size="14" />
            <span>Current Week</span>
          </button>
        </div>

        <!-- Weekly Comparison KPI Grid -->
        <div class="kpi-grid">
          <!-- Total Trades This Week -->
          <div class="kpi-card glass-card">
            <div class="kpi-icon-wrap blue"><Layers :size="20" /></div>
            <div class="kpi-content">
              <span class="kpi-label">TRADES THIS WEEK</span>
              <div class="kpi-val">{{ weeklyReview.currentStats.totalTrades }}</div>
              <span class="kpi-sub" :class="weeklyReview.tradesDelta >= 0 ? 'text-muted' : 'text-muted'">
                {{ weeklyReview.tradesDelta >= 0 ? `+${weeklyReview.tradesDelta}` : weeklyReview.tradesDelta }} vs prior week ({{ weeklyReview.priorStats.totalTrades }})
              </span>
            </div>
          </div>

          <!-- Total Mistakes This Week -->
          <div class="kpi-card glass-card">
            <div class="kpi-icon-wrap rose"><AlertTriangle :size="20" /></div>
            <div class="kpi-content">
              <span class="kpi-label">MISTAKES THIS WEEK</span>
              <div
                class="kpi-val"
                :class="weeklyReview.currentStats.totalMistakes > weeklyReview.priorStats.totalMistakes ? 'text-rose' : 'text-green'"
              >
                {{ weeklyReview.currentStats.totalMistakes }}
              </div>
              <span
                class="kpi-sub"
                :class="weeklyReview.mistakesDelta <= 0 ? 'text-green' : 'text-rose'"
              >
                {{ weeklyReview.mistakesDelta <= 0 ? `${weeklyReview.mistakesDelta}` : `+${weeklyReview.mistakesDelta}` }} vs prior week ({{ weeklyReview.priorStats.totalMistakes }})
                {{ weeklyReview.mistakesDelta <= 0 ? '🟢 Improvement!' : '🔴 Worsened' }}
              </span>
            </div>
          </div>

          <!-- Weekly Discipline Score -->
          <div class="kpi-card glass-card">
            <div class="kpi-icon-wrap green"><Award :size="20" /></div>
            <div class="kpi-content">
              <span class="kpi-label">WEEKLY DISCIPLINE SCORE</span>
              <div class="kpi-val text-green">
                {{ weeklyReview.currentStats.cleanPercentage }}%
              </div>
              <span class="kpi-sub text-muted">
                {{ weeklyReview.currentStats.cleanTrades }} of {{ weeklyReview.currentStats.totalTrades }} trades 100% clean
              </span>
            </div>
          </div>

          <!-- Most Repeated Mistake This Week -->
          <div class="kpi-card glass-card">
            <div class="kpi-icon-wrap red"><Flame :size="20" /></div>
            <div class="kpi-content">
              <span class="kpi-label">TOP MISTAKE THIS WEEK</span>
              <div v-if="weeklyReview.currentStats.mostFrequentMistake" class="mf-title-sm">
                {{ weeklyReview.currentStats.mostFrequentMistake.title }} ({{ weeklyReview.currentStats.mostFrequentMistake.count }})
              </div>
              <div v-else class="text-green text-sm italic">Zero mistakes this week! Perfect discipline 🎉</div>
            </div>
          </div>
        </div>

        <!-- Weekly Comparison Highlights (Improved vs Worsened) -->
        <div class="weekly-delta-grid">
          <!-- Column 1: Improved Mistakes -->
          <div class="delta-col glass-card green-border">
            <div class="delta-col-header">
              <CheckCircle2 :size="18" class="text-green" />
              <div>
                <h3 class="delta-title text-green">What Improved This Week?</h3>
                <p class="delta-sub">Mistakes reduced or eliminated compared to prior week</p>
              </div>
            </div>

            <div v-if="weeklyReview.improvedMistakes.length > 0" class="delta-list">
              <div
                v-for="m in weeklyReview.improvedMistakes"
                :key="m.id"
                class="delta-item good"
              >
                <div class="di-info">
                  <span class="di-title">{{ m.title }}</span>
                  <span class="di-desc">{{ m.category }}</span>
                </div>
                <div class="di-pill good">
                  <span>{{ m.prevCount }} ➔ {{ m.currCount }}</span>
                  <strong>({{ m.delta }})</strong>
                </div>
              </div>
            </div>
            <div v-else class="empty-delta text-muted">
              No mistakes improved this week or no trades logged in prior week.
            </div>
          </div>

          <!-- Column 2: Worsened Mistakes -->
          <div class="delta-col glass-card red-border">
            <div class="delta-col-header">
              <XCircle :size="18" class="text-red" />
              <div>
                <h3 class="delta-title text-red">What Worsened / Repeated?</h3>
                <p class="delta-sub">Mistakes that increased in frequency this week</p>
              </div>
            </div>

            <div v-if="weeklyReview.worsenedMistakes.length > 0" class="delta-list">
              <div
                v-for="m in weeklyReview.worsenedMistakes"
                :key="m.id"
                class="delta-item bad"
              >
                <div class="di-info">
                  <span class="di-title">{{ m.title }}</span>
                  <span class="di-desc">{{ m.category }}</span>
                </div>
                <div class="di-pill bad">
                  <span>{{ m.prevCount }} ➔ {{ m.currCount }}</span>
                  <strong>(+{{ m.delta }})</strong>
                </div>
              </div>
            </div>
            <div v-else class="empty-delta text-green">
              Zero mistakes worsened this week! Excellent progress. 🛡️
            </div>
          </div>
        </div>

        <!-- Weekly Detailed Breakdown Table -->
        <div class="section-card glass-card">
          <div class="section-header">
            <div>
              <h2 class="section-title">All Rules Comparison (This Week vs Prior Week)</h2>
              <p class="section-sub">Direct week-over-week audit of every trading mistake.</p>
            </div>
          </div>

          <div class="table-responsive">
            <table class="audit-table">
              <thead>
                <tr>
                  <th>TRADING RULE & MISTAKE</th>
                  <th>CATEGORY</th>
                  <th>PRIOR WEEK</th>
                  <th>THIS WEEK</th>
                  <th>NET DELTA</th>
                  <th>STATUS</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in weeklyReview.comparison" :key="item.id">
                  <td class="font-bold">{{ item.title }}</td>
                  <td>
                    <span class="badge-cat-sm" :style="{ color: item.color }">{{ item.category }}</span>
                  </td>
                  <td>{{ item.prevCount }}</td>
                  <td class="font-bold">{{ item.currCount }}</td>
                  <td>
                    <span
                      class="delta-badge"
                      :class="item.delta < 0 ? 'good' : item.delta > 0 ? 'bad' : 'neutral'"
                    >
                      {{ item.delta > 0 ? `+${item.delta}` : item.delta }}
                    </span>
                  </td>
                  <td>
                    <span v-if="item.status === 'improved'" class="status-pill good">Improved ↘</span>
                    <span v-else-if="item.status === 'worsened'" class="status-pill bad">Worsened ↗</span>
                    <span v-else class="status-pill neutral">No Change —</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- ================================================================= -->
      <!-- TAB 3: COMPLETE TRADE HISTORY & LOG                               -->
      <!-- ================================================================= -->
      <section v-else-if="activeTab === 'history'" class="history-tab space-y-6">
        <!-- Filter and Search Bar -->
        <div class="filter-bar glass-card">
          <!-- Date Filter Group: [Today, Last Week, Last Month, Calendar Icon (Pick Range)] -->
          <div class="date-filter-group">
            <button
              type="button"
              class="date-filter-btn"
              :class="{ active: tradeLogDateFilter === 'TODAY' }"
              @click="setDateFilter('TODAY')"
            >
              Today
            </button>
            <button
              type="button"
              class="date-filter-btn"
              :class="{ active: tradeLogDateFilter === 'LAST_WEEK' }"
              @click="setDateFilter('LAST_WEEK')"
            >
              Last Week
            </button>
            <button
              type="button"
              class="date-filter-btn"
              :class="{ active: tradeLogDateFilter === 'LAST_MONTH' }"
              @click="setDateFilter('LAST_MONTH')"
            >
              Last Month
            </button>
            <button
              type="button"
              class="date-filter-btn"
              :class="{ active: tradeLogDateFilter === 'ALL' }"
              @click="setDateFilter('ALL')"
            >
              All
            </button>

            <!-- Calendar Icon to Pick Custom Range -->
            <div class="calendar-picker-wrapper" ref="calendarPickerRef">
              <button
                type="button"
                class="date-filter-btn calendar-btn"
                :class="{ active: tradeLogDateFilter === 'CUSTOM' }"
                @click="toggleCalendarPicker"
                title="Pick Custom Date Range"
              >
                <Calendar :size="15" />
                <span v-if="tradeLogDateFilter === 'CUSTOM' && customRangeLabel" class="custom-range-text">
                  {{ customRangeLabel }}
                </span>
              </button>

              <!-- Custom Range Popover -->
              <div v-if="isCalendarPickerOpen" class="range-popover glass-card" @click.stop>
                <div class="range-popover-header">
                  <span class="range-title">Pick Date Range</span>
                  <button type="button" class="btn-popover-close" @click="isCalendarPickerOpen = false">
                    <X :size="14" />
                  </button>
                </div>
                <div class="range-inputs-row">
                  <div class="range-input-group">
                    <label>From</label>
                    <input
                      type="date"
                      v-model="customStartDate"
                      class="date-input"
                      @change="applyCustomRange"
                    />
                  </div>
                  <div class="range-input-group">
                    <label>To</label>
                    <input
                      type="date"
                      v-model="customEndDate"
                      class="date-input"
                      @change="applyCustomRange"
                    />
                  </div>
                </div>
                <div class="range-actions">
                  <button type="button" class="btn-apply-range" @click="applyCustomRange">
                    Apply Range
                  </button>
                  <button type="button" class="btn-clear-range" @click="clearCustomRange">
                    Clear
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <div class="filter-divider"></div>

          <!-- Search -->
          <div class="search-box">
            <Search :size="16" class="text-muted" />
            <input
              v-model="searchQuery"
              placeholder="Search symbol, notes, reasons..."
              class="search-input"
            />
            <button v-if="searchQuery" class="clear-search" @click="searchQuery = ''">
              <X :size="14" />
            </button>
          </div>

          <!-- Session Filter -->
          <div class="filter-select-wrap">
            <SunMedium :size="15" class="text-muted" />
            <select v-model="selectedSessionFilter" class="filter-select">
              <option value="ALL">All Sessions</option>
              <option v-for="s in TRADING_SESSIONS" :key="s.id" :value="s.id">
                {{ s.label }} ({{ s.hours }})
              </option>
            </select>
          </div>

          <!-- Mistake Type Filter -->
          <div class="filter-select-wrap">
            <Filter :size="15" class="text-muted" />
            <select v-model="selectedMistakeFilter" class="filter-select">
              <option value="ALL">All Mistakes Filter</option>
              <option
                v-for="def in MISTAKE_DEFINITIONS"
                :key="def.id"
                :value="def.id"
              >
                {{ def.title }}
              </option>
            </select>
          </div>

          <!-- Discipline Filter Buttons -->
          <div class="discipline-chips">
            <button
              class="disc-chip"
              :class="{ active: selectedDisciplineFilter === 'ALL' }"
              @click="selectedDisciplineFilter = 'ALL'"
            >
              All ({{ dateFilteredStats.total }})
            </button>
            <button
              class="disc-chip clean"
              :class="{ active: selectedDisciplineFilter === 'CLEAN' }"
              @click="selectedDisciplineFilter = 'CLEAN'"
            >
              Clean ({{ dateFilteredStats.clean }})
            </button>
            <button
              class="disc-chip flaws"
              :class="{ active: selectedDisciplineFilter === 'MISTAKES' }"
              @click="selectedDisciplineFilter = 'MISTAKES'"
            >
              Flawed ({{ dateFilteredStats.flaws }})
            </button>
          </div>

          <!-- Sort Order Toggle Button -->
          <button
            type="button"
            class="btn-sort-toggle"
            @click="toggleSortOrder"
            :title="sortOrder === 'desc' ? 'Sorting: Newest First (Click to sort Oldest First)' : 'Sorting: Oldest First (Click to sort Newest First)'"
          >
            <ArrowDown v-if="sortOrder === 'desc'" :size="14" />
            <ArrowUp v-else :size="14" />
            <span>{{ sortOrder === 'desc' ? 'Newest First' : 'Oldest First' }}</span>
          </button>
        </div>

        <!-- Selection & Export Action Bar -->
        <div class="selection-toolbar glass-card">
          <div class="st-left">
            <label class="st-checkbox-label" title="Toggle select all filtered trades">
              <input
                type="checkbox"
                :checked="isAllSelected"
                class="trade-checkbox"
                @change="toggleSelectAll"
              />
              <span class="st-select-text">
                Select All Filtered ({{ displayedTrades.length }})
              </span>
            </label>

            <span v-if="selectedTradeIds.size > 0" class="st-count-pill">
              {{ selectedTradeIds.size }} of {{ displayedTrades.length }} selected
            </span>

            <button
              v-if="selectedTradeIds.size > 0"
              type="button"
              class="btn-clear-selection"
              @click="deselectAllTrades"
            >
              Clear Selection
            </button>
          </div>

          <div class="st-right">
            <button
              type="button"
              class="btn-export-pdf"
              :disabled="isExportingPdf || displayedTrades.length === 0"
              :class="{ 'is-loading': isExportingPdf }"
              @click="exportSelectedTradesPdf"
              :title="selectedTradeIds.size > 0 ? `Export ${selectedTradeIds.size} selected trade(s) into single-page PDF` : `Export all ${displayedTrades.length} displayed trade(s) into single-page PDF`"
            >
              <RefreshCw v-if="isExportingPdf" :size="16" class="icon-spin" />
              <FileDown v-else :size="16" />
              <span>
                {{ isExportingPdf ? 'Generating PDF...' : (selectedTradeIds.size > 0 ? `Export Selected to PDF (${selectedTradeIds.size})` : `Export All to PDF (${displayedTrades.length})`) }}
              </span>
            </button>
          </div>
        </div>

        <!-- Trades List / Cards -->
        <div v-if="displayedTrades.length > 0" class="trades-container space-y-4">
          <div
            v-for="trade in displayedTrades"
            :key="trade.id"
            class="trade-card glass-card clickable-row"
            :class="{ 'has-flaws': trade.mistakesCount > 0, 'is-clean': trade.isClean, 'is-selected': selectedTradeIds.has(trade.id) }"
            title="Click to edit / update this trade record"
            @click="openEditModal(trade)"
          >
            <!-- Card Header -->
            <div class="tc-header">
              <div class="tc-left">
                <!-- Trade Selection Checkbox -->
                <div
                  class="tc-select-wrap"
                  title="Select trade for PDF export"
                  @click.stop="toggleSelectTrade(trade.id)"
                >
                  <input
                    type="checkbox"
                    :checked="selectedTradeIds.has(trade.id)"
                    class="trade-checkbox"
                    @click.stop="toggleSelectTrade(trade.id)"
                  />
                </div>
                <span class="tc-symbol">{{ trade.symbol }}</span>
                <span
                  class="badge-session-pill"
                  :style="{ color: getSessionMeta(trade.session).color, borderColor: getSessionMeta(trade.session).color, background: getSessionMeta(trade.session).bg }"
                >
                  {{ getSessionMeta(trade.session).label }}
                </span>
                <span class="badge-seq" :class="{ 'warn': trade.tradeSequence >= 3 }">
                  #{{ trade.tradeSequence }} Trade
                </span>
                <span
                  class="badge-fs"
                  :class="trade.frontsideSetup === true ? 'front' : trade.frontsideSetup === false ? 'back' : 'none'"
                >
                  {{ trade.frontsideSetup === true ? 'Frontside' : trade.frontsideSetup === false ? 'Backside' : 'Setup Unspecified' }}
                </span>
                <!-- Entry price next to frontside & market type boxes -->
                <span class="tc-entry-inline">
                  Entry: <strong>${{ Number(trade.entryPrice).toFixed(2) }}</strong>
                  <span v-if="trade.tradeDate || trade.tradeTime" class="tc-entry-time">
                    at "{{ formatTradeDateTime(trade.tradeDate, trade.tradeTime) }}"
                  </span>
                </span>
              </div>

              <!-- Price & PnL details -->
              <div class="tc-center">
                <span v-if="trade.exitPrice" class="tc-exit">
                  Exit: <strong>${{ Number(trade.exitPrice).toFixed(2) }}</strong>
                </span>
                <span
                  v-if="trade.calculatedPnl !== undefined && trade.calculatedPnl !== null"
                  class="tc-pnl"
                  :class="trade.calculatedPnl >= 0 ? 'text-green' : 'text-rose'"
                >
                  {{ trade.calculatedPnl >= 0 ? `+$${trade.calculatedPnl}` : `-$${Math.abs(trade.calculatedPnl)}` }}
                </span>
                <span v-else-if="trade.isStillOpen" class="badge-open">OPEN</span>
              </div>

              <!-- Actions (Date & Time removed from right side) -->
              <div class="tc-right">
                <button
                  class="btn-row-action"
                  title="Expand / Collapse Details"
                  @click.stop="toggleExpandTrade(trade.id)"
                >
                  <ChevronDown v-if="!expandedTradeIds.has(trade.id)" :size="16" />
                  <ChevronUp v-else :size="16" />
                </button>
                <button
                  class="btn-row-action"
                  title="Edit Trade"
                  @click.stop="openEditModal(trade)"
                >
                  <Edit3 :size="15" />
                </button>
                <button
                  class="btn-row-action danger"
                  title="Delete Trade"
                  @click.stop="deleteTrade(trade.id)"
                >
                  <Trash2 :size="15" />
                </button>
              </div>
            </div>

            <!-- Mistakes Summary Badges Bar -->
            <div class="tc-mistakes-bar">
              <div v-if="trade.isClean" class="clean-badge">
                <CheckCircle2 :size="14" />
                <span>CLEAN EXECUTION — ZERO MISTAKES</span>
              </div>
              <div v-else class="mistake-pills-wrap">
                <span
                  v-for="m in trade.mistakes"
                  :key="m.id"
                  class="mistake-pill"
                  :style="{ backgroundColor: m.bg, borderColor: m.border, color: m.color }"
                >
                  <AlertTriangle :size="12" />
                  <span>{{ m.title }}</span>
                </span>
              </div>
            </div>

            <!-- Expanded Details View -->
            <div v-if="expandedTradeIds.has(trade.id)" class="tc-expanded-body">
              <div class="tc-expanded-top-bar flex items-center justify-between pb-2 mb-3">
                <span class="text-xs text-muted font-bold tracking-wider">TRADE DETAILS &amp; AUDIT BREAKDOWN</span>
                <button
                  type="button"
                  class="btn-edit-inside-expanded"
                  @click.stop="openEditModal(trade)"
                  title="Open offcanvas to edit this trade record"
                >
                  <Edit3 :size="13" />
                  <span>Edit This Trade</span>
                </button>
              </div>
              <div class="detail-grid">
                <!-- Col 1: Technical Levels -->
                <div class="detail-box">
                  <h4 class="detail-box-title">Technical Levels at Entry</h4>
                  <div class="detail-rows">
                    <div class="dr-item">
                      <span class="dr-lbl">Session:</span>
                      <span class="dr-val" :style="{ color: getSessionMeta(trade.session).color }">
                        {{ getSessionMeta(trade.session).label }} ({{ getSessionMeta(trade.session).hours }})
                      </span>
                    </div>
                    <div v-if="trade.tradeTime" class="dr-item">
                      <span class="dr-lbl">EST Time (New York):</span>
                      <span class="dr-val text-sky font-bold">
                        🇺🇸 {{ convertLocalToEst(trade.tradeDate, trade.tradeTime).estDisplay }}
                      </span>
                    </div>
                    <div class="dr-item">
                      <span class="dr-lbl">9 EMA Value:</span>
                      <span class="dr-val">{{ trade.ema9Value ? `$${Number(trade.ema9Value).toFixed(2)}` : 'Not recorded' }}</span>
                    </div>
                    <div class="dr-item">
                      <span class="dr-lbl">VWAP Value:</span>
                      <span class="dr-val">{{ trade.vwapValue ? `$${Number(trade.vwapValue).toFixed(2)}` : 'Not recorded' }}</span>
                    </div>
                    <div class="dr-item">
                      <span class="dr-lbl">Nearest Resistance:</span>
                      <span class="dr-val">{{ trade.nearestResistance ? `$${Number(trade.nearestResistance).toFixed(2)}` : 'Not recorded' }}</span>
                    </div>
                  </div>
                </div>

                <!-- Col 2: Entry Discipline & Deviation -->
                <div class="detail-box">
                  <h4 class="detail-box-title">Entry Discipline</h4>
                  <div class="detail-rows">
                    <div class="dr-item">
                      <span class="dr-lbl">Predefined Entry?</span>
                      <span class="dr-val" :class="trade.predefinedEntry === false ? 'text-red font-bold' : 'text-green'">
                        {{ trade.predefinedEntry === true ? 'Yes' : trade.predefinedEntry === false ? 'No (Mistake)' : 'Unspecified' }}
                      </span>
                    </div>
                    <div v-if="trade.predefinedEntry" class="dr-item">
                      <span class="dr-lbl">Planned Price:</span>
                      <span class="dr-val">${{ Number(trade.plannedEntryPrice || trade.entryPrice).toFixed(2) }}</span>
                    </div>
                    <div v-if="trade.entryType" class="dr-item full">
                      <span class="dr-lbl">Entry Type:</span>
                      <span class="dr-val text-sky font-semibold">{{ trade.entryType }}</span>
                    </div>
                    <div v-if="trade.enteredAtPredefinedPrice === false" class="dr-item">
                      <span class="dr-lbl">Deviation:</span>
                      <span class="dr-val text-rose font-bold">
                        Entered {{ trade.entryDeviationDirection || 'off-plan' }}
                      </span>
                    </div>
                    <div v-if="trade.entryDeviationReason" class="dr-item full">
                      <span class="dr-lbl">Reason:</span>
                      <span class="dr-val italic text-amber">"{{ trade.entryDeviationReason }}"</span>
                    </div>
                    <div v-if="trade.enteredAboveAction" class="dr-item full">
                      <span class="dr-lbl">Size Management:</span>
                      <span class="dr-val" :class="trade.enteredAboveAction === 'HELD_FULL' ? 'text-red font-bold' : 'text-green'">
                        {{ trade.enteredAboveAction === 'HELD_FULL' ? 'Held Full Size (Mistake)' : trade.enteredAboveAction === 'SOLD_HALF' ? 'Sold Half (Mitigated)' : 'Closed Entire' }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Col 3: Risk Management & Psychology -->
                <div class="detail-box">
                  <h4 class="detail-box-title">Risk Management & Psychology</h4>
                  <div class="detail-rows">
                    <div class="dr-item">
                      <span class="dr-lbl">Predefined Stop Loss?</span>
                      <span class="dr-val" :class="trade.predefinedStopLoss === false ? 'text-red font-bold' : 'text-green'">
                        {{ trade.predefinedStopLoss === true ? 'Yes' : trade.predefinedStopLoss === false ? 'No (Mistake)' : 'Unspecified' }}
                      </span>
                    </div>
                    <div class="dr-item">
                      <span class="dr-lbl">Averaged Down?</span>
                      <span class="dr-val" :class="trade.averagedDown === true ? 'text-red font-bold' : 'text-green'">
                        {{ trade.averagedDown === true ? 'Yes (Critical Mistake)' : trade.averagedDown === false ? 'No' : 'Unspecified' }}
                      </span>
                    </div>
                    <div v-if="trade.averagedDownReason" class="dr-item full">
                      <span class="dr-lbl">Avg Down Reason:</span>
                      <span class="dr-val italic text-red">"{{ trade.averagedDownReason }}"</span>
                    </div>
                    <div class="dr-item">
                      <span class="dr-lbl">Froze During Loss?</span>
                      <span class="dr-val" :class="trade.frozeOnLoss === true ? 'text-red font-bold' : 'text-green'">
                        {{ trade.frozeOnLoss === true ? 'Yes (Psychology Mistake)' : trade.frozeOnLoss === false ? 'No' : 'Unspecified' }}
                      </span>
                    </div>
                    <div v-if="trade.frozeReason" class="dr-item full">
                      <span class="dr-lbl">Freezing Reason:</span>
                      <span class="dr-val italic text-purple">"{{ trade.frozeReason }}"</span>
                    </div>
                    <div class="dr-item">
                      <span class="dr-lbl">Final Exit:</span>
                      <span class="dr-val" :class="trade.finalExitType === 'FEAR' ? 'text-red font-bold' : trade.finalExitType === 'SETUP' ? 'text-green font-bold' : 'text-muted'">
                        {{ trade.finalExitType === 'FEAR' ? 'Fear Exit 🔴' : trade.finalExitType === 'SETUP' ? 'Setup Exit 🟢' : 'Unspecified' }}
                      </span>
                    </div>
                    <div v-if="trade.finalExitFearReason" class="dr-item full">
                      <span class="dr-lbl">Fear Exit Reason:</span>
                      <span class="dr-val italic text-purple">"{{ trade.finalExitFearReason }}"</span>
                    </div>
                    <div class="dr-item">
                      <span class="dr-lbl">Caught in Flush?:</span>
                      <span class="dr-val" :class="trade.flushOccurred === true ? 'text-red font-bold' : trade.flushOccurred === false ? 'text-green font-bold' : 'text-muted'">
                        {{ trade.flushOccurred === true ? 'Yes, Caught in Flush 🔴' : trade.flushOccurred === false ? 'No 🟢' : 'Unspecified' }}
                      </span>
                    </div>
                    <div v-if="trade.flushReason" class="dr-item full">
                      <span class="dr-lbl">Flush / Error Reason:</span>
                      <span class="dr-val italic text-red">"{{ trade.flushReason }}"</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Notes / Reflection (RTL Arabic Preview) -->
              <div v-if="trade.notes" class="tc-notes-box" dir="rtl">
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-xs text-muted font-bold">التفكير الداخلى:</span>
                  <span class="badge-rtl-pill">RTL Arabic 🇸🇦</span>
                </div>
                <div class="html-rendered-notes text-sm text-gray-200" dir="rtl" v-html="formatBidiNumbers(trade.notes)"></div>
              </div>

              <!-- Attached Screenshots -->
              <div v-if="trade.screenshots && trade.screenshots.length > 0" class="tc-screenshots-box">
                <span class="text-xs text-muted font-bold block mb-2">CHART SCREENSHOTS:</span>
                <div class="screenshot-thumbnails">
                  <div
                    v-for="(img, idx) in trade.screenshots"
                    :key="idx"
                    class="thumb-wrap"
                    @click="activeLightboxImage = img"
                  >
                    <img :src="img" alt="Trade Chart" class="thumb-img" />
                    <div class="thumb-overlay">
                      <Eye :size="16" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="empty-state glass-card text-center py-12">
          <BookOpen :size="48" class="mx-auto text-muted mb-4" />
          <h3 class="text-lg font-bold text-gray-200">No trades match your filter criteria</h3>
          <p class="text-sm text-muted mt-1 mb-4">
            {{ tradeLogDateFilter === 'TODAY' ? 'No trades recorded for today yet.' : 'Try resetting your filters or click "+ Add Trade" to log a new position.' }}
          </p>
          <div class="empty-actions flex gap-3 justify-center">
            <button
              v-if="tradeLogDateFilter !== 'ALL' && enrichedTrades.length > 0"
              type="button"
              class="btn-secondary-sm"
              @click="setDateFilter('ALL')"
            >
              View All {{ enrichedTrades.length }} Trades
            </button>
            <button type="button" class="btn-primary-glow" @click="openAddModal">
              <Plus :size="16" />
              <span>Add Trade</span>
            </button>
          </div>
        </div>
      </section>
    </main>

    <!-- ================================================================= -->
    <!-- OFFCANVAS DRAWER: ADD / EDIT TRADE FORM (DYNAMIC LOGIC)           -->
    <!-- ================================================================= -->
    <transition name="slide-drawer">
      <div v-if="isOffcanvasOpen" class="offcanvas-backdrop" @click.self="closeOffcanvas">
        <aside class="offcanvas-drawer glass-card">
          <!-- Drawer Header -->
          <div class="drawer-header">
            <div class="dh-title-box">
              <h2 class="drawer-title">
                {{ editingTradeId ? 'Edit Trade Record' : 'Add New Trade' }}
              </h2>
              <p class="drawer-sub">
                Record your manual trade data and evaluate your behavioral discipline.
              </p>
            </div>
            <button class="btn-close" @click="closeOffcanvas">
              <X :size="20" />
            </button>
          </div>

          <!-- Drawer Form Body -->
          <form class="drawer-body" @submit.prevent="saveTrade">
            <!-- SECTION A: TRADE INFORMATION -->
            <fieldset class="form-section">
              <legend class="section-legend">
                <span class="legend-num">A</span> Trade Information
              </legend>

              <!-- Stock Symbol -->
              <div class="form-group">
                <label class="form-label required">Stock Symbol / Ticker</label>
                <input
                  v-model="form.symbol"
                  placeholder="e.g. TSLA, NVDA"
                  class="form-input uppercase font-bold"
                  required
                />
              </div>

              <!-- Trading Session Picker (shown only when editing) -->
              <div v-if="editingTradeId" class="form-group">
                <div class="flex-between mb-1">
                  <label class="form-label required">
                    Trading Session <span class="text-xs text-muted font-normal">(EST / New York Time)</span>
                  </label>
                  <span class="text-xs font-bold" :style="{ color: getSessionMeta(form.session).color }">
                    Active: {{ getSessionMeta(form.session).label }} ({{ getSessionMeta(form.session).hours }})
                  </span>
                </div>
                <div class="session-chips-grid">
                  <button
                    v-for="s in TRADING_SESSIONS"
                    :key="s.id"
                    type="button"
                    class="session-chip-btn"
                    :class="{ active: form.session === s.id }"
                    :style="form.session === s.id ? { borderColor: s.color, color: s.color, background: s.bg } : {}"
                    @click="form.session = s.id"
                  >
                    <span class="sc-name">{{ s.label }}</span>
                    <span class="sc-time">{{ s.hours }}</span>
                  </button>
                </div>
              </div>

              <!-- Entry Price -->
              <div class="form-group">
                <label class="form-label required">Entry Price ($)</label>
                <input
                  v-model.number="form.entryPrice"
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  class="form-input font-bold"
                  required
                />
              </div>

              <!-- Trade Sequence on this stock today -->
              <div class="form-group">
                <label class="form-label">
                  Trade Sequence on this stock today
                  <span class="text-xs text-muted font-normal">(Overtrading Detection)</span>
                </label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.tradeSequence === 1 }"
                    @click="form.tradeSequence = 1"
                  >
                    1st Trade
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.tradeSequence === 2 }"
                    @click="form.tradeSequence = 2"
                  >
                    2nd Trade
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.tradeSequence === 3 }"
                    @click="form.tradeSequence = 3"
                  >
                    3rd Trade ⚠️
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.tradeSequence >= 4 }"
                    @click="form.tradeSequence = 4"
                  >
                    4th+ Trade ⚠️
                  </button>
                </div>
                <div v-if="form.tradeSequence >= 3" class="alert-box warn mt-2">
                  <AlertTriangle :size="14" />
                  <span>Flagged Mistake: Overtrading / Revenge risk on same stock.</span>
                </div>
              </div>

              <!-- Frontside Setup -->
              <div class="form-group">
                <label class="form-label">Was this stock trading on the Frontside?</label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.frontsideSetup === true }"
                    @click="form.frontsideSetup = true"
                  >
                    Yes (Frontside 🟢)
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.frontsideSetup === false }"
                    @click="form.frontsideSetup = false"
                  >
                    No (Backside 🔴)
                  </button>
                </div>
                <div v-if="form.frontsideSetup === false" class="alert-box danger mt-2">
                  <AlertTriangle :size="14" />
                  <span>Flagged Mistake: Trading backside setups has significantly lower edge.</span>
                </div>
              </div>
            </fieldset>

            <!-- SECTION B: TECHNICAL LEVELS AT ENTRY -->
            <fieldset class="form-section">
              <legend class="section-legend">
                <span class="legend-num">B</span> Technical Levels at Entry
              </legend>

              <div class="form-row-3">
                <div class="form-group">
                  <label class="form-label">9 EMA Value ($)</label>
                  <input
                    v-model.number="form.ema9Value"
                    type="number"
                    step="0.01"
                    placeholder="e.g. 182.10"
                    class="form-input"
                  />
                </div>
                <div class="form-group">
                  <label class="form-label">VWAP Value ($)</label>
                  <input
                    v-model.number="form.vwapValue"
                    type="number"
                    step="0.01"
                    placeholder="e.g. 181.80"
                    class="form-input"
                  />
                </div>
                <div class="form-group">
                  <label class="form-label">Nearest Resistance ($)</label>
                  <input
                    v-model.number="form.nearestResistance"
                    type="number"
                    step="0.01"
                    placeholder="e.g. 185.00"
                    class="form-input"
                  />
                </div>
              </div>
            </fieldset>

            <!-- SECTION C: ENTRY DISCIPLINE (CONDITIONAL LOGIC) -->
            <fieldset class="form-section">
              <legend class="section-legend">
                <span class="legend-num">C</span> Entry Discipline
              </legend>

              <!-- Question 8: Predefined Entry Price -->
              <div class="form-group">
                <label class="form-label required">
                  Did I define my entry price before entering the trade?
                </label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.predefinedEntry === true }"
                    @click="form.predefinedEntry = true"
                  >
                    Yes
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.predefinedEntry === false }"
                    @click="form.predefinedEntry = false"
                  >
                    No
                  </button>
                </div>
                <div v-if="form.predefinedEntry === false" class="alert-box danger mt-2">
                  <AlertTriangle :size="14" />
                  <span>Flagged Mistake: Entering without predefined entry price.</span>
                </div>
              </div>

              <!-- Dynamic Sub-questions if Predefined Entry was YES -->
              <div v-if="form.predefinedEntry === true" class="nested-conditional space-y-4">
                <div class="form-group">
                  <label class="form-label">What was your Planned Entry Price? ($)</label>
                  <input
                    v-model.number="form.plannedEntryPrice"
                    type="number"
                    step="0.01"
                    placeholder="Planned price"
                    class="form-input"
                  />
                </div>

                <!-- Multi-select: Was entry [breakout, fomo, retest 9ema, retest vwap] -->
                <div class="form-group">
                  <div class="flex-between mb-1">
                    <label class="form-label">
                      What was the entry based on? (Entry was)
                      <span class="text-xs text-muted font-normal">(Multi-select: Click chips to toggle)</span>
                    </label>
                    <button
                      v-if="form.entryType"
                      type="button"
                      class="btn-xs-link text-rose"
                      @click="clearReasonChips('entryType')"
                    >
                      Clear
                    </button>
                  </div>
                  <div class="chips-selector mb-2">
                    <button
                      v-for="chip in ENTRY_WAS_CHIPS"
                      :key="chip"
                      type="button"
                      class="quick-chip"
                      :class="{ active: isChipSelected('entryType', chip) }"
                      @click="toggleReasonChip('entryType', chip)"
                    >
                      <span v-if="isChipSelected('entryType', chip)" class="chip-check">✓</span>
                      {{ chip }}
                    </button>
                  </div>
                  <input
                    v-model="form.entryType"
                    placeholder="Breakout, FOMO, Retest 9 EMA, Retest VWAP..."
                    class="form-input"
                  />
                </div>

                <!-- Question 9: Entered at Predefined Price? -->
                <div class="form-group">
                  <label class="form-label required">
                    Did I enter at my predefined entry price?
                  </label>
                  <div class="segmented-control">
                    <button
                      type="button"
                      class="seg-btn"
                      :class="{ active: form.enteredAtPredefinedPrice === true }"
                      @click="form.enteredAtPredefinedPrice = true"
                    >
                      Yes, executed at planned price 🟢
                    </button>
                    <button
                      type="button"
                      class="seg-btn"
                      :class="{ active: form.enteredAtPredefinedPrice === false }"
                      @click="form.enteredAtPredefinedPrice = false"
                    >
                      No, deviated from plan 🔴
                    </button>
                  </div>
                </div>

                <!-- If NO to entered at predefined price -->
                <div v-if="form.enteredAtPredefinedPrice === false" class="nested-conditional space-y-4">
                  <div class="form-group">
                    <label class="form-label required">
                      Did you enter Above or Below your planned entry price?
                    </label>
                    <div class="segmented-control">
                      <button
                        type="button"
                        class="seg-btn"
                        :class="{ active: form.entryDeviationDirection === 'ABOVE' }"
                        @click="form.entryDeviationDirection = 'ABOVE'"
                      >
                        Above Planned Price (Chased) ⚠️
                      </button>
                      <button
                        type="button"
                        class="seg-btn"
                        :class="{ active: form.entryDeviationDirection === 'BELOW' }"
                        @click="form.entryDeviationDirection = 'BELOW'"
                      >
                        Below Planned Price (Dip / Discount)
                      </button>
                    </div>
                  </div>

                  <!-- Reason for Deviation (Multi-Select) -->
                  <div class="form-group">
                    <div class="flex-between mb-1">
                      <label class="form-label">
                        Why did you deviate from your planned entry?
                        <span class="text-xs text-muted font-normal">(Multi-select: Click chips to toggle)</span>
                      </label>
                      <button
                        v-if="form.entryDeviationReason"
                        type="button"
                        class="btn-xs-link text-rose"
                        @click="clearReasonChips('entryDeviationReason')"
                      >
                        Clear
                      </button>
                    </div>
                    <div class="chips-selector mb-2">
                      <button
                        v-for="chip in ENTRY_DEVIATION_CHIPS"
                        :key="chip"
                        type="button"
                        class="quick-chip"
                        :class="{ active: isChipSelected('entryDeviationReason', chip) }"
                        @click="toggleReasonChip('entryDeviationReason', chip)"
                      >
                        <span v-if="isChipSelected('entryDeviationReason', chip)" class="chip-check">✓</span>
                        {{ chip }}
                      </button>
                    </div>
                    <input
                      v-model="form.entryDeviationReason"
                      placeholder="Type reason or select multiple chips above..."
                      class="form-input"
                    />
                  </div>

                  <!-- Question 10: Entering Above Planned Price Position Reduction -->
                  <div v-if="form.entryDeviationDirection === 'ABOVE'" class="nested-conditional space-y-4">
                    <div class="alert-box danger">
                      <AlertTriangle :size="14" />
                      <span>Flagged Mistake: Chased entry above planned price.</span>
                    </div>

                    <div class="form-group">
                      <label class="form-label required">
                        How did you manage position size after entering at a worse price?
                      </label>
                      <select v-model="form.enteredAboveAction" class="form-select">
                        <option :value="null" disabled>Select position size management...</option>
                        <option value="SOLD_HALF">Sold half of position immediately (Mitigated risk 🟢)</option>
                        <option value="CLOSED_ENTIRE">Closed entire position immediately (Cut bad entry 🟢)</option>
                        <option value="HELD_FULL">Held full position despite entering at worse price (🔴 Mistake)</option>
                      </select>
                    </div>

                    <div v-if="form.enteredAboveAction === 'HELD_FULL'" class="form-group">
                      <div class="flex-between mb-1">
                        <label class="form-label">
                          Why did you hold full size despite the bad entry?
                          <span class="text-xs text-muted font-normal">(Multi-select: Click chips to toggle)</span>
                        </label>
                        <button
                          v-if="form.enteredAboveReason"
                          type="button"
                          class="btn-xs-link text-rose"
                          @click="clearReasonChips('enteredAboveReason')"
                        >
                          Clear
                        </button>
                      </div>
                      <div class="chips-selector mb-2">
                        <button
                          v-for="chip in HELD_FULL_CHIPS"
                          :key="chip"
                          type="button"
                          class="quick-chip"
                          :class="{ active: isChipSelected('enteredAboveReason', chip) }"
                          @click="toggleReasonChip('enteredAboveReason', chip)"
                        >
                          <span v-if="isChipSelected('enteredAboveReason', chip)" class="chip-check">✓</span>
                          {{ chip }}
                        </button>
                      </div>
                      <input
                        v-model="form.enteredAboveReason"
                        placeholder="Why did you hold full size?"
                        class="form-input"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </fieldset>

            <!-- SECTION D: RISK MANAGEMENT & EXECUTION (CONDITIONAL LOGIC) -->
            <fieldset class="form-section">
              <legend class="section-legend">
                <span class="legend-num">D</span> Risk Management & Execution
              </legend>

              <!-- Question 11: Predefined Stop Loss -->
              <div class="form-group">
                <label class="form-label required">
                  Did I define my stop-loss level before entering the trade?
                </label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.predefinedStopLoss === true }"
                    @click="form.predefinedStopLoss = true"
                  >
                    Yes
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.predefinedStopLoss === false }"
                    @click="form.predefinedStopLoss = false"
                  >
                    No
                  </button>
                </div>
              </div>

              <!-- Question 12: Averaging Down -->
              <div class="form-group">
                <label class="form-label required">
                  Did I average down on this trade?
                </label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.averagedDown === false }"
                    @click="form.averagedDown = false"
                  >
                    No 🟢
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.averagedDown === true }"
                    @click="form.averagedDown = true"
                  >
                    Yes 🔴
                  </button>
                </div>

                <!-- If YES to Averaging Down -->
                <div v-if="form.averagedDown === true" class="nested-conditional mt-3 space-y-3">
                  <div class="alert-box danger">
                    <AlertTriangle :size="14" />
                    <span>Critical Mistake: Averaging down into a losing position.</span>
                  </div>
                  <div class="flex-between mb-1">
                    <label class="form-label">
                      Why did you average down?
                      <span class="text-xs text-muted font-normal">(Multi-select: Click chips to toggle)</span>
                    </label>
                    <button
                      v-if="form.averagedDownReason"
                      type="button"
                      class="btn-xs-link text-rose"
                      @click="clearReasonChips('averagedDownReason')"
                    >
                      Clear
                    </button>
                  </div>
                  <div class="chips-selector mb-2">
                    <button
                      v-for="chip in AVERAGED_DOWN_CHIPS"
                      :key="chip"
                      type="button"
                      class="quick-chip"
                      :class="{ active: isChipSelected('averagedDownReason', chip) }"
                      @click="toggleReasonChip('averagedDownReason', chip)"
                    >
                      <span v-if="isChipSelected('averagedDownReason', chip)" class="chip-check">✓</span>
                      {{ chip }}
                    </button>
                  </div>
                  <input
                    v-model="form.averagedDownReason"
                    placeholder="Explain why you averaged down or select chips above..."
                    class="form-input"
                  />
                </div>
              </div>

              <!-- Question 13: Freezing During Losing Trade -->
              <div class="form-group">
                <label class="form-label required">
                  Did the stock move against me while I froze and failed to exit?
                </label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.frozeOnLoss === false }"
                    @click="form.frozeOnLoss = false"
                  >
                    No, executed exit cleanly 🟢
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.frozeOnLoss === true }"
                    @click="form.frozeOnLoss = true"
                  >
                    Yes, froze / hesitated 🔴
                  </button>
                </div>

                <!-- If YES to Freezing -->
                <div v-if="form.frozeOnLoss === true" class="nested-conditional mt-3 space-y-3">
                  <div class="alert-box danger">
                    <AlertTriangle :size="14" />
                    <span>Psychological Mistake: Froze and failed to execute stop loss.</span>
                  </div>
                  <div class="flex-between mb-1">
                    <label class="form-label">
                      What prevented you from exiting?
                      <span class="text-xs text-muted font-normal">(Multi-select: Click chips to toggle)</span>
                    </label>
                    <button
                      v-if="form.frozeReason"
                      type="button"
                      class="btn-xs-link text-rose"
                      @click="clearReasonChips('frozeReason')"
                    >
                      Clear
                    </button>
                  </div>
                  <div class="chips-selector mb-2">
                    <button
                      v-for="chip in FROZE_ON_LOSS_CHIPS"
                      :key="chip"
                      type="button"
                      class="quick-chip"
                      :class="{ active: isChipSelected('frozeReason', chip) }"
                      @click="toggleReasonChip('frozeReason', chip)"
                    >
                      <span v-if="isChipSelected('frozeReason', chip)" class="chip-check">✓</span>
                      {{ chip }}
                    </button>
                  </div>
                  <input
                    v-model="form.frozeReason"
                    placeholder="What caused you to freeze? Select chips or type..."
                    class="form-input"
                  />
                </div>
              </div>

              <!-- Question 14: Final Exit (Setup vs Fear) -->
              <div class="form-group">
                <label class="form-label required">
                  Did you exit your final size based on Setup or Fear?
                </label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.finalExitType === 'SETUP' }"
                    @click="form.finalExitType = 'SETUP'"
                  >
                    Setup Exit 🟢
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.finalExitType === 'FEAR' }"
                    @click="form.finalExitType = 'FEAR'"
                  >
                    Fear Exit 🔴
                  </button>
                </div>

                <!-- If FEAR -->
                <div v-if="form.finalExitType === 'FEAR'" class="nested-conditional mt-3 space-y-3">
                  <div class="alert-box danger">
                    <AlertTriangle :size="14" />
                    <span>⚠️ Flagged Mistake: Exited out of fear instead of respecting setup rules.</span>
                  </div>
                  <div class="flex-between mb-1">
                    <label class="form-label">
                      What was the reason for the fear exit?
                      <span class="text-xs text-muted font-normal">(Multi-select: Click chips to toggle)</span>
                    </label>
                    <button
                      v-if="form.finalExitFearReason"
                      type="button"
                      class="btn-xs-link text-rose"
                      @click="clearReasonChips('finalExitFearReason')"
                    >
                      Clear
                    </button>
                  </div>
                  <div class="chips-selector mb-2">
                    <button
                      v-for="chip in FEAR_EXIT_CHIPS"
                      :key="chip"
                      type="button"
                      class="quick-chip"
                      :class="{ active: isChipSelected('finalExitFearReason', chip) }"
                      @click="toggleReasonChip('finalExitFearReason', chip)"
                    >
                      <span v-if="isChipSelected('finalExitFearReason', chip)" class="chip-check">✓</span>
                      {{ chip }}
                    </button>
                  </div>
                  <input
                    v-model="form.finalExitFearReason"
                    placeholder="State fear exit reason or select multiple chips above..."
                    class="form-input"
                  />
                </div>
              </div>

              <!-- Question 15: Flush Occurred & Reason -->
              <div class="form-group">
                <label class="form-label required">
                  Were you caught in a sudden Flush?
                </label>
                <div class="segmented-control">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.flushOccurred === false }"
                    @click="form.flushOccurred = false"
                  >
                    No, avoided flush 🟢
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: form.flushOccurred === true }"
                    @click="form.flushOccurred = true"
                  >
                    Yes, caught in flush 🔴
                  </button>
                </div>

                <!-- If Flush Occurred -->
                <div v-if="form.flushOccurred === true" class="nested-conditional mt-3 space-y-3">
                  <div class="alert-box danger">
                    <AlertTriangle :size="14" />
                    <span>⚠️ Flagged Mistake: Caught in a flush or failed to exit on signs of weakness.</span>
                  </div>
                  <div class="flex-between mb-1">
                    <label class="form-label">
                      What caused the flush or what error occurred?
                      <span class="text-xs text-muted font-normal">(Multi-select: Click chips to toggle)</span>
                    </label>
                    <button
                      v-if="form.flushReason"
                      type="button"
                      class="btn-xs-link text-rose"
                      @click="clearReasonChips('flushReason')"
                    >
                      Clear
                    </button>
                  </div>
                  <div class="chips-selector mb-2">
                    <button
                      v-for="chip in FLUSH_REASON_CHIPS"
                      :key="chip"
                      type="button"
                      class="quick-chip"
                      :class="{ active: isChipSelected('flushReason', chip) }"
                      @click="toggleReasonChip('flushReason', chip)"
                    >
                      <span v-if="isChipSelected('flushReason', chip)" class="chip-check">✓</span>
                      {{ chip }}
                    </button>
                  </div>
                  <input
                    v-model="form.flushReason"
                    placeholder="State flush reason or select chips above..."
                    class="form-input"
                  />
                </div>
              </div>
            </fieldset>

            <!-- SECTION E: SCREENSHOTS & NOTES -->
            <fieldset class="form-section">
              <legend class="section-legend">
                <span class="legend-num">E</span> Chart Screenshots & Notes
              </legend>

              <div class="form-group">
                <div class="flex-between mb-1">
                  <label class="form-label">
                    Chart Screenshots
                    <span class="text-xs text-muted font-normal">(Multi-upload supported, drag & drop, or Ctrl+V)</span>
                  </label>
                  <span v-if="form.screenshots.length > 0" class="text-xs font-bold text-sky">
                    {{ form.screenshots.length }} screenshot{{ form.screenshots.length > 1 ? 's' : '' }} attached
                  </span>
                </div>
                <label
                  class="upload-dropzone"
                  @dragover.prevent
                  @dragenter.prevent
                  @drop="handleDropImages"
                >
                  <Upload :size="24" class="text-sky mb-1" />
                  <span class="text-sm font-semibold text-gray-200">Click to upload multiple screenshots or drag & drop here</span>
                  <span class="text-xs text-muted">Select multiple images at once (PNG, JPG, WebP) or paste with Ctrl+V</span>
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    class="hidden"
                    @change="handleImageUpload"
                  />
                </label>

                <!-- Thumbnails -->
                <div v-if="form.screenshots.length > 0" class="screenshot-thumbnails mt-3">
                  <div
                    v-for="(img, idx) in form.screenshots"
                    :key="idx"
                    class="thumb-wrap"
                    title="Click to view image"
                    @click="activeLightboxImage = img"
                  >
                    <img :src="img" alt="Thumbnail" class="thumb-img" />
                    <span class="thumb-idx">#{{ idx + 1 }}</span>
                    <button
                      type="button"
                      class="btn-thumb-remove"
                      title="Remove image"
                      @click.stop="removeScreenshot(idx)"
                    >
                      <X :size="12" />
                    </button>
                  </div>
                </div>
              </div>

              <div class="form-group">
                <div class="flex items-center justify-between mb-1">
                  <label class="form-label mb-0">التفكير الداخلى</label>
                  <span class="badge-rtl-indicator">RTL Arabic 🇸🇦</span>
                </div>
                <HtmlEditor
                  v-model="form.notes"
                  dir="rtl"
                  placeholder="اكتب ملاحظاتك، حالتك النفسية، والدروس المستفادة من هذه الصفقة..."
                  min-height="130px"
                />
              </div>
            </fieldset>

            <!-- Real-Time Mistakes Feedback in Form Footer -->
            <div v-if="liveFormMistakes.length > 0" class="form-live-summary">
              <div class="text-rose text-sm font-bold">
                {{ liveFormMistakes.length }} Mistake(s) will be logged:
              </div>
            </div>

            <!-- Drawer Submit Buttons -->
            <div class="drawer-footer">
              <button type="button" class="btn-ghost" @click="closeOffcanvas">
                Cancel
              </button>
              <button type="submit" class="btn-primary-glow">
                {{ editingTradeId ? 'Update Trade' : 'Save & Analyze Trade' }}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </transition>

    <!-- Fullscreen Image Lightbox Preview -->
    <div
      v-if="activeLightboxImage"
      class="lightbox-backdrop"
      @click="activeLightboxImage = null"
    >
      <div class="lightbox-content" @click.stop>
        <button class="btn-lightbox-close" @click="activeLightboxImage = null">
          <X :size="24" />
        </button>
        <img :src="activeLightboxImage" alt="Enlarged Trade Chart" class="lightbox-img" />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ============================================================================
   DARK TRADING TERMINAL THEME STYLING
   ============================================================================ */
.journal-root {
  min-height: 100vh;
  background-color: #0b0f19;
  color: #f1f5f9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  padding: 18px 26px;
  box-sizing: border-box;
  font-size: 15px;
  line-height: 1.5;
}

/* Glass Panels */
.glass-card {
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}

/* Header */
.journal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 22px;
  margin-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.brand-badge {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 42px;
  height: 42px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 0 16px rgba(59, 130, 246, 0.4);
}

.brand-title {
  font-size: 1.3rem;
  font-weight: 900;
  letter-spacing: 0.05em;
  margin: 0;
  background: linear-gradient(to right, #ffffff, #94a3b8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-sub {
  font-size: 0.85rem;
  color: #94a3b8;
  margin: 0;
}

/* Nav Tabs */
.nav-tabs {
  display: flex;
  gap: 6px;
  background: rgba(0, 0, 0, 0.35);
  padding: 5px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #94a3b8;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.04);
}

.tab-btn.active {
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.3);
}

/* Header Actions */
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.date-chips {
  display: flex;
  gap: 4px;
  background: rgba(0, 0, 0, 0.25);
  padding: 4px;
  border-radius: 6px;
}

.chip-btn {
  padding: 6px 14px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #94a3b8;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
}

.chip-btn.active {
  background: #1e293b;
  color: #f8fafc;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}

.btn-primary-glow {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 9px 20px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #ffffff;
  border: 1px solid rgba(59, 130, 246, 0.6);
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 0 14px rgba(37, 99, 235, 0.4);
  transition: all 0.2s ease;
}

.btn-primary-glow:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 20px rgba(37, 99, 235, 0.6);
}

.utility-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.json-file-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.25);
  border-radius: 6px;
  font-size: 13px;
  font-family: monospace;
  color: #34d399;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.json-file-status-pill:hover {
  background: rgba(16, 185, 129, 0.16);
  border-color: rgba(16, 185, 129, 0.45);
}

.json-file-status-pill .file-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}

.json-file-status-pill .file-dot.disconnected {
  background: #f59e0b;
  box-shadow: 0 0 6px #f59e0b;
}

.json-file-status-pill .file-icon {
  color: #10b981;
  flex-shrink: 0;
}

.json-file-status-pill .file-label {
  font-weight: 600;
  letter-spacing: 0.3px;
}

.json-file-status-pill .file-count {
  opacity: 0.85;
  font-weight: 500;
}

.icon-spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-icon:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.1);
}

.btn-icon.danger:hover {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.4);
}

/* Empty Journal Welcome Card */
.empty-journal-card {
  text-align: center;
  padding: 48px 24px;
  max-width: 600px;
  margin: 40px auto;
}

.ej-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto 16px auto;
  border-radius: 50%;
  background: rgba(56, 189, 248, 0.12);
  color: #38bdf8;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ej-title {
  font-size: 1.3rem;
  font-weight: 800;
  margin: 0 0 8px 0;
  color: #fff;
}

.ej-desc {
  font-size: 0.86rem;
  color: #94a3b8;
  line-height: 1.5;
  margin: 0 0 24px 0;
}

/* KPI Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  position: relative;
  overflow: hidden;
}

.kpi-card.span-2 {
  grid-column: span 2;
}

.kpi-card.highlight-border {
  border-color: rgba(16, 185, 129, 0.35);
}

.kpi-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kpi-icon-wrap.blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.kpi-icon-wrap.rose { background: rgba(244, 63, 94, 0.15); color: #fb7185; }
.kpi-icon-wrap.green { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.kpi-icon-wrap.amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.kpi-icon-wrap.purple { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
.kpi-icon-wrap.red { background: rgba(239, 68, 68, 0.15); color: #f87171; }

.kpi-content {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.kpi-label {
  font-size: 0.8rem;
  font-weight: 800;
  color: #94a3b8;
  letter-spacing: 0.05em;
}

.kpi-val {
  font-size: 1.7rem;
  font-weight: 900;
  line-height: 1.2;
}

.kpi-sub {
  font-size: 0.84rem;
  margin-top: 2px;
}

.progress-bar-wrap {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  margin-top: 6px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.most-frequent-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mf-title {
  font-size: 1.05rem;
  font-weight: 800;
  color: #fca5a5;
}

.mf-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* Sections */
.section-card {
  padding: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.section-title {
  font-size: 1.15rem;
  font-weight: 800;
  margin: 0;
  color: #f8fafc;
}

.section-sub {
  font-size: 0.88rem;
  color: #94a3b8;
  margin: 2px 0 0 0;
}

/* Mistake Rows */
.mistake-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mistake-row {
  display: grid;
  grid-template-columns: 2fr 1.5fr 1fr;
  align-items: center;
  gap: 16px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  transition: all 0.15s ease;
}

.mistake-row.has-occurrences {
  background: rgba(255, 255, 255, 0.04);
}

.mistake-row:hover {
  background: rgba(255, 255, 255, 0.06);
}

.m-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.m-color-indicator {
  width: 4px;
  height: 36px;
  border-radius: 2px;
}

.m-info {
  display: flex;
  flex-direction: column;
}

.m-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-title {
  font-size: 0.98rem;
  font-weight: 700;
  color: #f1f5f9;
}

.badge-cat {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  border: 1px solid;
}

.badge-cat-sm {
  font-size: 0.8rem;
  font-weight: 700;
}

.m-desc {
  font-size: 0.84rem;
  color: #94a3b8;
  margin: 2px 0 0 0;
}

.m-center {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.m-bar-bg {
  width: 100%;
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  overflow: hidden;
}

.m-bar-fill {
  height: 100%;
  border-radius: 4px;
}

.m-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.84rem;
}

.m-count {
  font-weight: 800;
  color: #cbd5e1;
}

.m-pct {
  color: #94a3b8;
}

.m-right {
  display: flex;
  justify-content: flex-end;
}

.trend-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 700;
}

.trend-tag.bad { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.trend-tag.good { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
.trend-tag.neutral { background: rgba(148, 163, 184, 0.1); color: #94a3b8; }

/* Patterns Grid */
.patterns-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.pattern-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pattern-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.p-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.p-icon.yellow { background: rgba(234, 179, 8, 0.15); color: #facc15; }
.p-icon.orange { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
.p-icon.purple { background: rgba(192, 132, 252, 0.15); color: #c084fc; }

.pattern-title {
  font-size: 1.08rem;
  font-weight: 800;
  margin: 0;
  color: #f8fafc;
}

.pattern-sub {
  font-size: 0.84rem;
  color: #94a3b8;
  margin: 2px 0 0 0;
}

.sequence-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.seq-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.seq-top {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
}

.seq-label { font-weight: 700; color: #cbd5e1; }
.seq-rate { font-weight: 600; }

.seq-progress-wrap {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}

.seq-progress {
  height: 100%;
  border-radius: 3px;
}

.pattern-note {
  font-size: 0.86rem;
  color: #cbd5e1;
  background: rgba(0, 0, 0, 0.25);
  padding: 10px 12px;
  border-radius: 6px;
  border-left: 3px solid #3b82f6;
  line-height: 1.45;
}

.frontside-boxes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.fs-box {
  padding: 14px;
  border-radius: 8px;
  border: 1px solid;
  text-align: center;
}

.fs-box.green {
  background: rgba(16, 185, 129, 0.08);
  border-color: rgba(16, 185, 129, 0.25);
}

.fs-box.red {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.25);
}

.fs-head {
  font-size: 0.85rem;
  font-weight: 700;
  color: #cbd5e1;
}

.fs-val {
  font-size: 1.45rem;
  font-weight: 900;
  margin: 4px 0;
}

.fs-sub {
  font-size: 0.8rem;
  color: #94a3b8;
}

/* Category Bars Grid */
.category-bars-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.cat-bar-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 12px;
  border-radius: 8px;
}

.cat-bar-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  font-weight: 700;
  margin-bottom: 6px;
}

.cat-bar-outer {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}

.cat-bar-inner {
  height: 100%;
  border-radius: 3px;
}

/* ============================================================================
   TAB 2: WEEKLY AUDIT & COMPARISON
   ============================================================================ */
.week-nav-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  flex-wrap: wrap;
  gap: 12px;
}

.wn-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-arrow-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #cbd5e1;
  padding: 7px 14px;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
}

.nav-arrow-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.wn-label-box {
  display: flex;
  flex-direction: column;
}

.wn-title {
  font-size: 0.8rem;
  font-weight: 800;
  color: #94a3b8;
}

.wn-range {
  font-size: 1.15rem;
  font-weight: 800;
  color: #38bdf8;
}

.weekly-delta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.delta-col {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.delta-col.green-border { border-color: rgba(16, 185, 129, 0.3); }
.delta-col.red-border { border-color: rgba(239, 68, 68, 0.3); }

.delta-col-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.delta-title {
  font-size: 1.08rem;
  font-weight: 800;
  margin: 0;
}

.delta-sub {
  font-size: 0.85rem;
  color: #94a3b8;
  margin: 1px 0 0 0;
}

.delta-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.delta-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
}

.delta-item.good { background: rgba(16, 185, 129, 0.08); border-left: 3px solid #10b981; }
.delta-item.bad { background: rgba(239, 68, 68, 0.08); border-left: 3px solid #ef4444; }

.di-info {
  display: flex;
  flex-direction: column;
}

.di-title {
  font-size: 0.92rem;
  font-weight: 700;
}

.di-desc {
  font-size: 0.82rem;
  color: #94a3b8;
}

.di-pill {
  font-size: 0.85rem;
  padding: 3px 8px;
  border-radius: 4px;
}

.di-pill.good { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.di-pill.bad { background: rgba(239, 68, 68, 0.2); color: #f87171; }

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

.audit-table th {
  text-align: left;
  padding: 10px 12px;
  color: #94a3b8;
  font-weight: 700;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.audit-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.delta-badge {
  font-size: 0.84rem;
  font-weight: 700;
  padding: 3px 7px;
  border-radius: 4px;
}

.delta-badge.good { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.delta-badge.bad { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.delta-badge.neutral { background: rgba(148, 163, 184, 0.1); color: #94a3b8; }

.status-pill {
  font-size: 0.82rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
}

.status-pill.good { color: #34d399; background: rgba(16, 185, 129, 0.15); }
.status-pill.bad { color: #f87171; background: rgba(239, 68, 68, 0.15); }
.status-pill.neutral { color: #94a3b8; }

/* ============================================================================
   TAB 3: TRADE HISTORY & DETAIL LOG
   ============================================================================ */
/* Date Filter Group in Trading Log List */
.date-filter-group {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(0, 0, 0, 0.25);
  padding: 4px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.date-filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 13px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #94a3b8;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.date-filter-btn:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.05);
}

.date-filter-btn.active {
  background: #1e293b;
  color: #38bdf8;
  border-color: rgba(56, 189, 248, 0.4);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}

.calendar-picker-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.calendar-btn {
  padding: 6px 10px;
}

.custom-range-text {
  font-size: 0.8rem;
  color: #38bdf8;
  font-weight: 600;
  margin-left: 2px;
}

.range-popover {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 100;
  min-width: 280px;
  padding: 14px;
  background: #0f172a;
  border: 1px solid rgba(56, 189, 248, 0.35);
  border-radius: 10px;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.75), 0 0 15px rgba(56, 189, 248, 0.15);
}

.range-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.range-title {
  font-size: 0.88rem;
  font-weight: 700;
  color: #f8fafc;
}

.btn-popover-close {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  border-radius: 4px;
}

.btn-popover-close:hover {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.1);
}

.range-inputs-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.range-input-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.range-input-group label {
  font-size: 0.76rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.date-input {
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 7px 10px;
  color: #f1f5f9;
  font-size: 0.88rem;
  outline: none;
  color-scheme: dark;
}

.date-input:focus {
  border-color: #38bdf8;
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
}

.range-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.btn-apply-range {
  padding: 6px 14px;
  background: #2563eb;
  border: 1px solid #3b82f6;
  border-radius: 6px;
  color: #ffffff;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-apply-range:hover {
  background: #1d4ed8;
}

.btn-clear-range {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #94a3b8;
  font-size: 0.82rem;
  cursor: pointer;
}

.btn-clear-range:hover {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.05);
}

.filter-divider {
  width: 1px;
  height: 24px;
  background: rgba(255, 255, 255, 0.08);
  margin: 0 4px;
}

.btn-sort-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn-sort-toggle:hover {
  background: #1e293b;
  color: #38bdf8;
  border-color: rgba(56, 189, 248, 0.3);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  flex-wrap: wrap;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 6px 10px;
  flex: 1;
  min-width: 200px;
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: #f1f5f9;
  font-size: 0.92rem;
  width: 100%;
}

.clear-search {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
}

.filter-select-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 6px 12px;
}

.filter-select {
  background: transparent;
  border: none;
  color: #cbd5e1;
  font-size: 0.88rem;
  outline: none;
}

.filter-select option {
  background: #0f172a;
  color: #f8fafc;
}

.discipline-chips {
  display: flex;
  gap: 4px;
}

.disc-chip {
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: #94a3b8;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
}

.disc-chip.active {
  background: #1e293b;
  color: #f8fafc;
  border-color: #38bdf8;
}

.disc-chip.clean.active { border-color: #10b981; color: #34d399; }
.disc-chip.flaws.active { border-color: #ef4444; color: #f87171; }

/* Selection & Export Action Bar */
.selection-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px;
  gap: 14px;
  flex-wrap: wrap;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.65);
}

.st-left, .st-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.st-checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.st-select-text {
  font-size: 0.88rem;
  font-weight: 600;
  color: #cbd5e1;
}

.st-count-pill {
  font-size: 0.82rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.35);
}

.btn-clear-selection {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 0.82rem;
  text-decoration: underline;
  cursor: pointer;
  padding: 2px 6px;
  transition: color 0.15s ease;
}

.btn-clear-selection:hover {
  color: #f87171;
}

.btn-export-pdf {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 0.88rem;
  font-weight: 700;
  background: linear-gradient(135deg, #0284c7, #0369a1);
  color: #ffffff;
  border: 1px solid rgba(56, 189, 248, 0.45);
  box-shadow: 0 4px 14px rgba(2, 132, 199, 0.3);
  cursor: pointer;
  transition: all 0.18s ease;
}

.btn-export-pdf:hover:not(:disabled) {
  background: linear-gradient(135deg, #0369a1, #075985);
  border-color: rgba(56, 189, 248, 0.75);
  box-shadow: 0 6px 18px rgba(2, 132, 199, 0.45);
  transform: translateY(-1px);
}

.btn-export-pdf:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.tc-select-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  cursor: pointer;
  border-radius: 4px;
  margin-right: 2px;
}

.tc-select-wrap:hover {
  background: rgba(255, 255, 255, 0.08);
}

.trade-checkbox {
  width: 17px;
  height: 17px;
  cursor: pointer;
  accent-color: #0284c7;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.trade-card {
  padding: 16px 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
  transform: none !important;
}

.trade-card.is-selected {
  border-color: rgba(56, 189, 248, 0.75) !important;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(14, 116, 144, 0.18)) !important;
  box-shadow: 0 0 16px rgba(56, 189, 248, 0.22);
}

.trade-card.clickable-row {
  cursor: pointer;
}

.trade-card.clickable-row:hover {
  transform: none !important;
  border-color: rgba(56, 189, 248, 0.55);
  background: rgba(30, 41, 59, 0.45);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.trade-card.has-flaws {
  border-color: rgba(239, 68, 68, 0.35);
}

.trade-card.has-flaws.clickable-row:hover {
  transform: none !important;
  border-color: rgba(239, 68, 68, 0.65);
  background: rgba(30, 41, 59, 0.45);
}

.trade-card.is-clean {
  border-color: rgba(16, 185, 129, 0.3);
}

.trade-card.is-clean.clickable-row:hover {
  transform: none !important;
  border-color: rgba(16, 185, 129, 0.65);
  background: rgba(30, 41, 59, 0.45);
}

.tc-entry-inline {
  display: inline-flex;
  align-items: center;
  font-size: 0.9rem;
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.05);
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-left: 2px;
}

.tc-entry-inline strong {
  color: #fff;
  font-weight: 700;
  margin-left: 4px;
}

.tc-entry-time {
  color: #94a3b8;
  font-size: 0.82rem;
  margin-left: 6px;
  font-weight: 400;
}

.tc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.tc-left, .tc-center, .tc-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tc-symbol {
  font-size: 1.25rem;
  font-weight: 900;
  letter-spacing: 0.05em;
  color: #fff;
}

.badge-direction {
  font-size: 0.78rem;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
}

.badge-direction.long { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.badge-direction.short { background: rgba(239, 68, 68, 0.2); color: #f87171; }

.badge-session-pill {
  font-size: 0.82rem;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 4px;
  border: 1px solid;
}

.badge-seq {
  font-size: 0.82rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
}

.badge-seq.warn {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.badge-fs {
  font-size: 0.82rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
}

.badge-fs.front { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.badge-fs.back { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.badge-fs.none { background: rgba(148, 163, 184, 0.1); color: #94a3b8; }

.tc-entry, .tc-exit {
  font-size: 0.92rem;
  color: #cbd5e1;
}

.tc-pnl {
  font-size: 1.2rem;
  font-weight: 900;
}

.badge-open {
  font-size: 0.8rem;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
}

.tc-time-group {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.tc-time {
  font-size: 0.86rem;
}

.tc-est-badge {
  font-size: 0.82rem;
  font-weight: 700;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.12);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(56, 189, 248, 0.25);
  font-family: var(--font-mono, monospace);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.btn-row-action {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 5px;
  color: #cbd5e1;
  cursor: pointer;
}

.btn-row-action:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.btn-row-action.danger:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.tc-mistakes-bar {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.clean-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  font-weight: 800;
  color: #34d399;
  background: rgba(16, 185, 129, 0.1);
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid rgba(16, 185, 129, 0.25);
}

.mistake-pills-wrap {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.mistake-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.82rem;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid;
}

.tc-expanded-body {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tc-expanded-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 8px;
}

.btn-edit-inside-expanded {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: rgba(56, 189, 248, 0.15);
  border: 1px solid rgba(56, 189, 248, 0.35);
  border-radius: 5px;
  color: #38bdf8;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-edit-inside-expanded:hover {
  background: rgba(56, 189, 248, 0.28);
  border-color: #38bdf8;
  color: #fff;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.detail-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 14px;
}

.detail-box-title {
  font-size: 0.88rem;
  font-weight: 800;
  color: #94a3b8;
  margin: 0 0 8px 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.detail-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dr-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.88rem;
}

.dr-item.full {
  flex-direction: column;
  gap: 3px;
  margin-top: 4px;
}

.dr-lbl { color: #94a3b8; }
.dr-val { font-weight: 600; color: #f1f5f9; }

.tc-notes-box {
  background: rgba(0, 0, 0, 0.3);
  padding: 12px 14px;
  border-radius: 8px;
  border-right: 3px solid #38bdf8;
}

.badge-rtl-pill {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.badge-rtl-indicator {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.html-rendered-notes {
  line-height: 1.65;
  color: #e2e8f0;
  direction: rtl;
  text-align: right;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.html-rendered-notes :deep(h2),
.html-rendered-notes h2 {
  font-size: 1.05rem;
  font-weight: 700;
  color: #38bdf8;
  margin: 6px 0 3px 0;
  direction: rtl;
  text-align: right;
}

.html-rendered-notes :deep(h3),
.html-rendered-notes h3 {
  font-size: 0.98rem;
  font-weight: 700;
  color: #7dd3fc;
  margin: 4px 0 2px 0;
  direction: rtl;
  text-align: right;
}

.html-rendered-notes :deep(p),
.html-rendered-notes p {
  margin: 4px 0;
  direction: rtl;
  text-align: right;
}

.html-rendered-notes :deep(.bidi-num),
.html-rendered-notes .bidi-num {
  direction: ltr !important;
  unicode-bidi: isolate !important;
  display: inline-block !important;
  text-align: left !important;
  white-space: nowrap !important;
}

.html-rendered-notes :deep(ul),
.html-rendered-notes ul {
  margin: 4px 22px 4px 0;
  padding-right: 4px;
  list-style-type: disc;
  list-style-position: outside;
  direction: rtl;
  text-align: right;
}

.html-rendered-notes :deep(ol),
.html-rendered-notes ol {
  margin: 4px 22px 4px 0;
  padding-right: 4px;
  list-style-type: decimal;
  list-style-position: outside;
  direction: rtl;
  text-align: right;
}

.html-rendered-notes :deep(li),
.html-rendered-notes li {
  margin: 2px 0;
  direction: rtl;
  text-align: right;
}

.html-rendered-notes :deep(strong),
.html-rendered-notes :deep(b),
.html-rendered-notes strong,
.html-rendered-notes b {
  font-weight: 700;
  color: #ffffff;
}

.html-rendered-notes :deep(em),
.html-rendered-notes :deep(i),
.html-rendered-notes em,
.html-rendered-notes i {
  font-style: italic;
}

.html-rendered-notes :deep(u),
.html-rendered-notes u {
  text-decoration: underline;
}

.html-rendered-notes :deep(strike),
.html-rendered-notes :deep(s),
.html-rendered-notes strike,
.html-rendered-notes s {
  text-decoration: line-through;
  opacity: 0.75;
}

.screenshot-thumbnails {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.thumb-wrap {
  width: 80px;
  height: 55px;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.thumb-wrap:hover .thumb-overlay {
  opacity: 1;
}

/* ============================================================================
   OFFCANVAS FORM DRAWER
   ============================================================================ */
.offcanvas-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  justify-content: flex-end;
}

.offcanvas-drawer {
  width: 50vw;
  min-width: 460px;
  max-width: 95vw;
  height: 100vh;
  background: #0f172a;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  border-radius: 0;
  overflow: hidden;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.6);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.drawer-title {
  font-size: 1.3rem;
  font-weight: 800;
  margin: 0;
}

.drawer-sub {
  font-size: 0.85rem;
  color: #94a3b8;
  margin: 2px 0 0 0;
}

.btn-close {
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
}

.btn-close:hover { color: #fff; }

.drawer-body {
  padding: 22px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
  flex: 1;
}

.form-section {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.015);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-legend {
  font-size: 1.02rem;
  font-weight: 800;
  color: #38bdf8;
  padding: 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-num {
  background: #1e293b;
  color: #38bdf8;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  font-size: 0.82rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quick-helpers {
  display: flex;
  gap: 8px;
}

.btn-xs-link {
  background: transparent;
  border: none;
  font-size: 0.82rem;
  font-weight: 700;
  color: #94a3b8;
  cursor: pointer;
  padding: 0;
}

.btn-xs-link:hover { color: #fff; }
.btn-xs-link.text-sky { color: #38bdf8; }
.btn-xs-link.text-sky:hover { color: #7dd3fc; }

.form-label {
  font-size: 0.92rem;
  font-weight: 700;
  color: #f1f5f9;
}

.form-label.required::after {
  content: " *";
  color: #ef4444;
}

.form-input, .form-textarea, .form-select {
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 10px 14px;
  color: #f1f5f9;
  font-size: 0.92rem;
  outline: none;
  transition: border-color 0.15s ease;
}

.form-input:focus, .form-textarea:focus, .form-select:focus {
  border-color: #38bdf8;
}

.form-select {
  cursor: pointer;
  appearance: auto;
  width: 100%;
}

.form-select option {
  background: #0f172a;
  color: #f1f5f9;
  padding: 8px 12px;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-row-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
}

/* Session Chips Grid */
.session-chips-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 8px;
}

.session-chip-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 6px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s ease;
}

.session-chip-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.session-chip-btn.active {
  font-weight: 800;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.4);
}

.sc-name {
  font-size: 0.85rem;
  font-weight: 700;
}

.sc-time {
  font-size: 0.74rem;
  opacity: 0.8;
}

/* Converted EST Preview Pill */
.est-preview-pill {
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.25);
  font-size: 0.85rem;
}

.est-flag {
  color: #94a3b8;
  font-weight: 600;
}

.est-val {
  color: #38bdf8;
  font-family: var(--font-mono, monospace);
  font-weight: 700;
  letter-spacing: 0.02em;
}

/* Segmented Control */
.segmented-control {
  display: flex;
  gap: 14px;
  background: rgba(0, 0, 0, 0.25);
  padding: 6px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.segmented-control.vertical {
  flex-direction: column;
  gap: 10px;
}

.seg-btn {
  flex: 1;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #94a3b8;
  font-size: 0.94rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: center;
}

.seg-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  color: #f8fafc;
}

.seg-btn.active {
  background: #1e293b;
  border-color: rgba(56, 189, 248, 0.55);
  color: #38bdf8;
  font-weight: 700;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.15);
}

.nested-conditional {
  background: rgba(0, 0, 0, 0.25);
  border-left: 3px solid #38bdf8;
  padding: 14px;
  border-radius: 0 6px 6px 0;
}

.alert-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.88rem;
  font-weight: 600;
}

.alert-box.danger {
  background: rgba(239, 68, 68, 0.14);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.alert-box.warn {
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.chips-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.quick-chip {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 0.85rem;
  color: #cbd5e1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all 0.15s ease;
  user-select: none;
}

.quick-chip:hover {
  background: rgba(56, 189, 248, 0.15);
  border-color: rgba(56, 189, 248, 0.35);
  color: #38bdf8;
}

.quick-chip.active {
  background: rgba(56, 189, 248, 0.22);
  border-color: #38bdf8;
  color: #38bdf8;
  font-weight: 700;
  box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
}

.chip-check {
  font-size: 0.85rem;
  font-weight: 900;
  color: #38bdf8;
}

.thumb-idx {
  position: absolute;
  top: 3px;
  left: 3px;
  background: rgba(0, 0, 0, 0.75);
  color: #38bdf8;
  font-size: 0.72rem;
  font-weight: 800;
  padding: 1px 4px;
  border-radius: 3px;
  pointer-events: none;
}

.upload-dropzone {
  border: 2px dashed rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.2);
}

.upload-dropzone:hover {
  border-color: #38bdf8;
}

.btn-thumb-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.85);
  border: none;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.form-live-summary {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 12px 16px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(15, 23, 42, 0.95);
}

.btn-ghost {
  padding: 9px 18px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #94a3b8;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
}

.btn-ghost:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}

/* Lightbox */
.lightbox-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lightbox-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

.lightbox-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 0 30px rgba(0, 0, 0, 0.8);
}

.btn-lightbox-close {
  position: absolute;
  top: -40px;
  right: 0;
  background: transparent;
  border: none;
  color: #fff;
  cursor: pointer;
}

/* Toast */
.toast-popup {
  position: fixed;
  top: 24px;
  right: 24px;
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 0.82rem;
  font-weight: 700;
  z-index: 10001;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
}

.toast-popup.success { background: #065f46; color: #34d399; border: 1px solid #10b981; }
.toast-popup.error { background: #7f1d1d; color: #f87171; border: 1px solid #ef4444; }
.toast-popup.info { background: #1e3a8a; color: #60a5fa; border: 1px solid #3b82f6; }

/* Transitions */
.slide-drawer-enter-active, .slide-drawer-leave-active {
  transition: opacity 0.25s ease;
}
.slide-drawer-enter-active .offcanvas-drawer,
.slide-drawer-leave-active .offcanvas-drawer {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-drawer-enter-from, .slide-drawer-leave-to {
  opacity: 0;
}
.slide-drawer-enter-from .offcanvas-drawer {
  transform: translateX(100%);
}
.slide-drawer-leave-to .offcanvas-drawer {
  transform: translateX(100%);
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Utilities */
.text-green { color: #34d399; }
.text-rose { color: #fb7185; }
.text-red { color: #f87171; }
.text-amber { color: #fbbf24; }
.text-orange { color: #fb923c; }
.text-purple { color: #c084fc; }
.text-muted { color: #64748b; }
.font-bold { font-weight: 700; }
.space-y-6 > * + * { margin-top: 1.5rem; }
.space-y-4 > * + * { margin-top: 1rem; }
.space-y-3 > * + * { margin-top: 0.75rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-3 { margin-top: 0.75rem; }
.hidden { display: none; }
</style>
