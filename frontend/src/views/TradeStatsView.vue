<script setup>
import { ref, computed, onMounted } from 'vue';
import Papa from 'papaparse';
import { BarChart2, UploadCloud, FileSpreadsheet, X, Settings2, ChevronUp, ChevronDown } from 'lucide-vue-next';

// State
const uploadStatus = ref('No file chosen');
const dailyStats = ref({});
const minDate = ref(null);
const maxDate = ref(null);
const isOffcanvasOpen = ref(false);
const selectedDate = ref('');
const selectedDayStats = ref(null);

const DEFAULT_COLUMNS = [
  { id: 'dateStr', label: 'Date', visible: true, order: 0 },
  { id: 'totalTrades', label: 'Total Trades', visible: true, order: 1 },
  { id: 'wins', label: 'Winning Trades', visible: true, order: 2 },
  { id: 'losses', label: 'Losing Trades', visible: true, order: 3 },
  { id: 'avgWin', label: 'Avg Win %', visible: true, order: 4 },
  { id: 'avgLoss', label: 'Avg Loss %', visible: true, order: 5 },
  { id: 'dayRet', label: 'Day Return %', visible: true, order: 6 }
];

let initialCols = DEFAULT_COLUMNS;
try {
  const savedColsStr = localStorage.getItem('tradeStatsCols');
  if (savedColsStr) {
    const parsed = JSON.parse(savedColsStr);
    if (parsed.some(c => c.id === 'totalPnL' || c.id === 'netPnL')) {
      localStorage.removeItem('tradeStatsCols');
    } else {
      initialCols = parsed;
    }
  }
} catch (e) {
  // Ignore
}
const tableColumns = ref(JSON.parse(JSON.stringify(initialCols)));
const isColMenuOpen = ref(false);

const visibleColumns = computed(() => {
  return [...tableColumns.value]
    .filter(col => col.visible)
    .sort((a, b) => a.order - b.order);
});

// Column Management Actions
const toggleColMenu = () => {
  isColMenuOpen.value = !isColMenuOpen.value;
};

const saveColumns = () => {
  localStorage.setItem('tradeStatsCols', JSON.stringify(tableColumns.value));
};

const toggleCol = (index) => {
  tableColumns.value[index].visible = !tableColumns.value[index].visible;
  saveColumns();
};

const moveColUp = (index) => {
  if (index > 0) {
    const item = tableColumns.value.splice(index, 1)[0];
    tableColumns.value.splice(index - 1, 0, item);
    tableColumns.value.forEach((c, i) => c.order = i);
    saveColumns();
  }
};

const moveColDown = (index) => {
  if (index < tableColumns.value.length - 1) {
    const item = tableColumns.value.splice(index, 1)[0];
    tableColumns.value.splice(index + 1, 0, item);
    tableColumns.value.forEach((c, i) => c.order = i);
    saveColumns();
  }
};

// File Upload Handler
const handleFileUpload = (e) => {
  const file = e.target.files[0];
  if (!file) return;

  uploadStatus.value = `Processing ${file.name}...`;

  const reader = new FileReader();
  reader.onload = (event) => {
    let csvText = event.target.result;
    
    // Some CSVs start with "Transaction History", so we find the real header row
    const headerStartIndex = csvText.indexOf('Transaction ID');
    if (headerStartIndex !== -1) {
      csvText = csvText.substring(headerStartIndex);
    }
    
    Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
      complete: (results) => {
        processData(results.data);
        uploadStatus.value = `Loaded ${results.data.length} records`;
      },
      error: (err) => {
        uploadStatus.value = 'Error parsing CSV';
        console.error(err);
      }
    });
  };
  
  reader.onerror = () => {
    uploadStatus.value = 'Error reading file';
  };
  
  reader.readAsText(file);
};

const processData = (data) => {
  let validTrades = data.filter(row => row['Trade Date'] && row['Symbol']);
  
  // Sort chronologically (assuming lower Transaction ID means earlier)
  validTrades.sort((a, b) => parseInt(a['Transaction ID']) - parseInt(b['Transaction ID']));

  const stats = {};
  const dates = new Set();

  validTrades.forEach(trade => {
    const date = trade['Trade Date'];
    dates.add(date);
    
    if (!stats[date]) {
      stats[date] = {
        tickers: {},
        stats: { totalTrades: 0, wins: 0, losses: 0, sumWinPct: 0, sumLossPct: 0, totalPnL: 0, totalCostBasis: 0, totalCommission: 0 }
      };
    }
    
    const symbol = trade['Symbol'];
    if (!stats[date].tickers[symbol]) {
      stats[date].tickers[symbol] = [];
    }
    stats[date].tickers[symbol].push(trade);
  });

  if (dates.size === 0) return;

  const sortedDates = Array.from(dates).sort();
  minDate.value = new Date(sortedDates[0]);
  maxDate.value = new Date(sortedDates[sortedDates.length - 1]);

  Object.keys(stats).forEach(date => {
    const dayData = stats[date];
    let dStats = dayData.stats;
    
    Object.keys(dayData.tickers).forEach(ticker => {
      const trades = dayData.tickers[ticker];
      let openLots = [];
      let positionDirection = null;
      let tickerPnL = 0;
      let tickerComm = 0;
      
      let aggBuys = { qty: 0, netAmount: 0, count: 0, times: [] };
      let aggSells = { qty: 0, netAmount: 0, count: 0, times: [] };
      let inTrade = false;
      let currentTradePnL = 0;
      let currentTradeCostBasis = 0;
      let currentTradeExecutions = [];
      let completedTrades = [];
      
      trades.forEach(trade => {
        let qty = parseFloat(trade['Quantity']);
        let price = parseFloat(trade['Trade Price'] || trade['Price'] || 0);
        let netAmount = parseFloat(trade['Net Amount'] || (qty * price));
        let type = trade['Trade Type'] || (qty > 0 ? 'B' : 'S');
        let comm = Math.abs(parseFloat(trade['Commission'] || trade['Comm/Fee'] || trade['IB Commission'] || 0));
        
        let tTime = trade['Time'] || trade['Trade Time'] || trade['Date/Time'] || '';
        
        qty = Math.abs(qty);
        netAmount = Math.abs(netAmount);
        tickerComm += comm;
        dStats.totalCommission += comm;
        
        let exec = {
          time: tTime,
          type: type === 'B' || type === 'BUY' ? 'BUY' : 'SELL',
          qty: qty,
          price: price,
          netAmount: netAmount,
          comm: comm
        };
        
        if (exec.type === 'BUY') {
          aggBuys.qty += qty;
          aggBuys.netAmount += netAmount;
          aggBuys.count++;
          if (tTime) aggBuys.times.push(tTime);
        } else {
          aggSells.qty += qty;
          aggSells.netAmount += netAmount;
          aggSells.count++;
          if (tTime) aggSells.times.push(tTime);
        }
        
        currentTradeExecutions.push(exec);
        
        if (openLots.length === 0) {
          positionDirection = type;
          openLots.push({ qty, netAmount, type });
          inTrade = true;
        } else if (positionDirection === type) {
          openLots.push({ qty, netAmount, type });
          inTrade = true;
        } else {
          let remainingQtyToClose = qty;
          
          while (remainingQtyToClose > 0 && openLots.length > 0) {
            let lot = openLots[0];
            let qtyToMatch = Math.min(lot.qty, remainingQtyToClose);
            let lotCostProRata = (qtyToMatch / lot.qty) * lot.netAmount;
            let closeRevenueProRata = (qtyToMatch / qty) * netAmount;
            
            let pnl = positionDirection === 'B' || positionDirection === 'BUY'
              ? closeRevenueProRata - lotCostProRata 
              : lotCostProRata - closeRevenueProRata;
            
            currentTradePnL += pnl;
            currentTradeCostBasis += lotCostProRata;
            tickerPnL += pnl;
            
            lot.qty -= qtyToMatch;
            lot.netAmount -= lotCostProRata;
            remainingQtyToClose -= qtyToMatch;
            
            if (lot.qty <= 0) openLots.shift();
          }
          
          if (openLots.length === 0) {
            dStats.totalTrades++;
            dStats.totalPnL += currentTradePnL;
            dStats.totalCostBasis += currentTradeCostBasis;
            
            let pct = currentTradeCostBasis > 0 ? (currentTradePnL / currentTradeCostBasis) * 100 : 0;
            if (currentTradePnL > 0) {
              dStats.wins++;
              dStats.sumWinPct += pct;
            } else {
              dStats.losses++;
              dStats.sumLossPct += pct;
            }
            
            completedTrades.push({
              executions: [...currentTradeExecutions],
              pnl: currentTradePnL,
              costBasis: currentTradeCostBasis
            });
            
            inTrade = false;
            currentTradePnL = 0;
            currentTradeCostBasis = 0;
            currentTradeExecutions = [];
          }
          
          if (remainingQtyToClose > 0) {
            if (inTrade && currentTradeCostBasis > 0) {
              dStats.totalTrades++;
              dStats.totalPnL += currentTradePnL;
              dStats.totalCostBasis += currentTradeCostBasis;
              
              let pct = currentTradeCostBasis > 0 ? (currentTradePnL / currentTradeCostBasis) * 100 : 0;
              if (currentTradePnL > 0) {
                dStats.wins++;
                dStats.sumWinPct += pct;
              } else {
                dStats.losses++;
                dStats.sumLossPct += pct;
              }
              
              completedTrades.push({
                executions: [...currentTradeExecutions],
                pnl: currentTradePnL,
                costBasis: currentTradeCostBasis
              });
              
              currentTradePnL = 0;
              currentTradeCostBasis = 0;
              currentTradeExecutions = [exec]; // The flip execution starts the next trade
            }
            
            positionDirection = type;
            let flipNetAmount = (remainingQtyToClose / qty) * netAmount;
            openLots.push({ qty: remainingQtyToClose, netAmount: flipNetAmount, type });
            inTrade = true;
          }
        }
      });
      
      // End of day processing for open/partial trades
      if (inTrade && (currentTradeCostBasis > 0 || currentTradeExecutions.length > 0)) {
        if (currentTradeCostBasis > 0) {
          dStats.totalTrades++;
          dStats.totalPnL += currentTradePnL;
          dStats.totalCostBasis += currentTradeCostBasis;
          
          let pct = currentTradeCostBasis > 0 ? (currentTradePnL / currentTradeCostBasis) * 100 : 0;
          if (currentTradePnL > 0) {
            dStats.wins++;
            dStats.sumWinPct += pct;
          } else {
            dStats.losses++;
            dStats.sumLossPct += pct;
          }
        }
        
        completedTrades.push({
          executions: [...currentTradeExecutions],
          pnl: currentTradePnL,
          costBasis: currentTradeCostBasis,
          isOpen: true
        });
      }
      
      dayData.tickers[ticker] = {
        trades: completedTrades,
        buys: aggBuys,
        sells: aggSells,
        pnl: tickerPnL,
        commission: tickerComm
      };
    });
  });

  dailyStats.value = stats;
};


// Computed Properties
const allDates = computed(() => {
  if (!minDate.value || !maxDate.value) return [];
  const dates = [];
  let currentDate = new Date(minDate.value);
  while (currentDate <= maxDate.value) {
    dates.push(new Date(currentDate));
    currentDate.setUTCDate(currentDate.getUTCDate() + 1);
  }
  return dates;
});

const dailyRows = computed(() => {
  return allDates.value.map(dateObj => {
    const yyyy = dateObj.getFullYear();
    const mm = String(dateObj.getMonth() + 1).padStart(2, '0');
    const dd = String(dateObj.getDate()).padStart(2, '0');
    const dateStr = `${yyyy}-${mm}-${dd}`;
    
    const dayOfWeek = dateObj.getDay();
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
    
    const displayDate = dateObj.toLocaleDateString('en-GB', {
      timeZone: 'UTC',
      weekday: 'short',
      day: 'numeric',
      month: 'short'
    });
    
    const dayData = dailyStats.value[dateStr];
    const isEmpty = !dayData || dayData.stats.totalTrades === 0;
    
    if (isEmpty) {
      return { dateStr, displayDate, isWeekend, isEmpty: true };
    }
    
    const s = dayData.stats;
    const avgWin = s.wins > 0 ? (s.sumWinPct / s.wins) : 0;
    const avgLoss = s.losses > 0 ? (s.sumLossPct / s.losses) : 0;
    const dayRet = s.totalCostBasis > 0 ? ((s.totalPnL / s.totalCostBasis) * 100) : 0;
    
    return {
      dateStr,
      displayDate,
      isWeekend,
      isEmpty: false,
      totalTrades: s.totalTrades,
      wins: s.wins,
      losses: s.losses,
      avgWin,
      avgLoss,
      dayRet
    };
  });
});

const getColClass = (colId, row) => {
  if (colId === 'wins' || colId === 'avgWin') return 'text-win';
  if (colId === 'losses' || colId === 'avgLoss') return 'text-loss';
  if (colId === 'dayRet') return row.dayRet >= 0 ? 'text-win' : 'text-loss';
  return '';
};

const getTickerPnLPct = (tickerData) => {
  if (!tickerData || !tickerData.trades) return 0;
  let totalPnL = 0;
  let totalCost = 0;
  tickerData.trades.forEach(t => {
    totalPnL += t.pnl || 0;
    totalCost += t.costBasis || 0;
  });
  return totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;
};

const selectedDateDisplay = ref('');
const collapsedTickers = ref({});

// UI Actions
const toggleTickerFold = (ticker) => {
  collapsedTickers.value[ticker] = !collapsedTickers.value[ticker];
};

const openOffcanvas = (row) => {
  if (dailyStats.value[row.dateStr]) {
    selectedDate.value = row.dateStr;
    selectedDateDisplay.value = row.displayDate;
    selectedDayStats.value = dailyStats.value[row.dateStr];
    collapsedTickers.value = {}; // Reset folds
    isOffcanvasOpen.value = true;
  }
};

const closeOffcanvas = () => {
  isOffcanvasOpen.value = false;
};
</script>

<template>
  <div class="trade-stats-view">
    <div class="app-container">
      <!-- Header & Upload -->
      <header class="header glass-panel">
        <div class="header-content">
          <div class="title-group">
            <BarChart2 class="title-icon" />
            <h1>Trade Statistics</h1>
          </div>
          <div class="upload-group">
            <div class="col-manager-wrapper">
              <button class="action-btn" @click="toggleColMenu" title="Manage Columns">
                <Settings2 size="16" />
                <span>Cols</span>
              </button>
              <div class="col-dropdown" v-if="isColMenuOpen">
                <div class="col-dropdown-header">Manage Columns</div>
                <div class="col-list">
                  <div class="col-item" v-for="(col, index) in tableColumns" :key="col.id">
                    <label class="col-label">
                      <input type="checkbox" :checked="col.visible" @change="toggleCol(index)" />
                      <span>{{ col.label }}</span>
                    </label>
                    <div class="col-actions">
                      <button class="col-arrow-btn" @click="moveColUp(index)" :disabled="index === 0">
                        <ChevronUp size="14" />
                      </button>
                      <button class="col-arrow-btn" @click="moveColDown(index)" :disabled="index === tableColumns.length - 1">
                        <ChevronDown size="14" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <label for="csvFileInput" class="upload-btn">
              <UploadCloud />
              <span>Upload CSV</span>
            </label>
            <input type="file" id="csvFileInput" accept=".csv" @change="handleFileUpload" />
            <span class="upload-status">{{ uploadStatus }}</span>
          </div>
        </div>
      </header>

      <!-- Main Daily Stats Table -->
      <main class="main-content">
        <div class="table-container glass-panel">
          <table class="stats-table">
            <thead>
              <tr>
                <th v-for="col in visibleColumns" :key="col.id">{{ col.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="dailyRows.length === 0" class="empty-state-row">
                <td :colspan="visibleColumns.length || 1">
                  <div class="empty-state">
                    <FileSpreadsheet class="empty-icon" />
                    <p>Upload a CSV file to view trade statistics</p>
                  </div>
                </td>
              </tr>
              
              <template v-else>
                <tr 
                  v-for="row in dailyRows" 
                  :key="row.dateStr"
                  :class="{ 'row-weekend': row.isWeekend, 'row-empty': row.isEmpty && !row.isWeekend }"
                  @click="!row.isEmpty ? openOffcanvas(row) : null"
                >
                  <template v-if="row.isEmpty">
                    <td v-if="visibleColumns.length > 0"><strong>{{ row.displayDate }}</strong></td>
                    <td v-if="visibleColumns.length > 1" :colspan="visibleColumns.length - 1" class="text-center text-muted">
                    </td>
                  </template>
                  <template v-else>
                    <td v-for="col in visibleColumns" :key="col.id" :class="getColClass(col.id, row)">
                      <template v-if="col.id === 'dateStr'"><strong>{{ row.displayDate }}</strong></template>
                      <template v-else-if="col.id === 'totalTrades'">{{ row.totalTrades }}</template>
                      <template v-else-if="col.id === 'wins'">{{ row.wins }}</template>
                      <template v-else-if="col.id === 'losses'">{{ row.losses }}</template>
                      <template v-else-if="col.id === 'avgWin'">{{ row.avgWin.toFixed(2) }}%</template>
                      <template v-else-if="col.id === 'avgLoss'">{{ row.avgLoss.toFixed(2) }}%</template>
                      <template v-else-if="col.id === 'dayRet'">{{ row.dayRet > 0 ? '+' : '' }}{{ row.dayRet.toFixed(2) }}%</template>
                    </td>
                  </template>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </main>
    </div>

    <!-- Offcanvas Overlay -->
    <div 
      class="offcanvas-overlay" 
      :class="{ 'active': isOffcanvasOpen }"
      @click="closeOffcanvas"
    ></div>

    <!-- Offcanvas Panel (75% width) -->
    <aside 
      class="offcanvas-panel glass-panel" 
      :class="{ 'active': isOffcanvasOpen }"
    >
      <div class="offcanvas-header">
        <div class="offcanvas-title">
          <h2>{{ selectedDateDisplay || 'Select a Date' }}</h2>
          <span class="badge" v-if="selectedDayStats">{{ selectedDayStats.stats.totalTrades }} Trades Completed</span>
        </div>
        <button class="close-btn" @click="closeOffcanvas">
          <X />
        </button>
      </div>
      
      <div class="offcanvas-body" v-if="selectedDayStats">
        <div class="timeline-container">
          <div 
            v-for="(data, ticker) in selectedDayStats.tickers" 
            :key="ticker" 
            class="ticker-group glass-panel"
          >
            <div class="ticker-header" @click="toggleTickerFold(ticker)" style="cursor: pointer;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <ChevronDown v-if="!collapsedTickers[ticker]" size="18" style="color: var(--text-muted);" />
                <ChevronUp v-else size="18" style="color: var(--text-muted);" />
                <div class="ticker-name">{{ ticker }}</div>
              </div>
              <div class="ticker-summary-pct" :class="getTickerPnLPct(data) >= 0 ? 'text-win' : 'text-loss'">
                {{ getTickerPnLPct(data) >= 0 ? '+' : '' }}{{ getTickerPnLPct(data).toFixed(2) }}%
              </div>
            </div>
            
            <div class="ticker-trades" v-show="!collapsedTickers[ticker]">
              <div class="trade-block" v-for="(trade, index) in data.trades" :key="index">
                <div class="trade-block-header">
                  <h4>Trade #{{ index + 1 }}</h4>
                  <div class="trade-block-stats">
                    <span v-if="trade.isOpen" class="badge-open">OPEN</span>
                    <span :class="trade.pnl >= 0 ? 'text-win' : 'text-loss'" style="font-weight: 600;">
                      PnL: {{ trade.pnl >= 0 ? '+' : '' }}{{ trade.costBasis > 0 ? ((trade.pnl / trade.costBasis) * 100).toFixed(2) : '0.00' }}%
                    </span>
                  </div>
                </div>
                
                <div class="table-container" style="margin-top: 4px;">
                  <table class="executions-table">
                    <tbody>
                      <tr v-for="(exec, idx) in trade.executions" :key="idx">
                        <td :class="exec.type === 'BUY' ? 'text-win' : 'text-loss'"><strong>{{ exec.type }}</strong></td>
                        <td>{{ exec.qty }}</td>
                        <td>${{ exec.price.toFixed(3) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.trade-stats-view {
  /* Using standard CSS variables to align with existing style or define new ones locally */
  --bg-color: #0f172a;
  --panel-bg: rgba(30, 41, 59, 0.7);
  --panel-border: rgba(255, 255, 255, 0.1);
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --win-color: #10b981;
  --win-bg: rgba(16, 185, 129, 0.1);
  --loss-color: #ef4444;
  --loss-bg: rgba(239, 68, 68, 0.1);
  --weekend-bg: rgba(255, 255, 255, 0.03);
  --empty-bg: rgba(255, 255, 255, 0.01);
  --hover-bg: rgba(255, 255, 255, 0.05);
  
  --font-heading: 'Outfit', sans-serif;
  --font-body: 'Inter', sans-serif;
  
  background-color: var(--bg-color);
  background-image: 
      radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
      radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.15) 0px, transparent 50%);
  background-attachment: fixed;
  color: var(--text-main);
  font-family: var(--font-body);
  line-height: 1.6;
  min-height: 100vh;
}

.glass-panel {
  background: var(--panel-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
}

.app-container {
  width: 100%;
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

/* Header */
.header {
  position: relative;
  z-index: 1000;
  padding: 0.5rem 1rem;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.title-icon {
  color: var(--accent);
  width: 20px;
  height: 20px;
}

h1 {
  font-family: var(--font-heading);
  font-size: 1.2rem;
  font-weight: 600;
  letter-spacing: -0.5px;
  margin: 0;
}

/* Upload Area */
.upload-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

input[type="file"] {
  display: none;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--accent);
  color: white;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.upload-btn:hover {
  background-color: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.upload-status {
  color: var(--text-muted);
  font-size: 0.8rem;
}

/* Main Table */
.table-container {
  overflow-x: auto;
  padding: 0.5rem;
}

.stats-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.85rem;
}

.stats-table th {
  font-family: var(--font-heading);
  color: var(--text-muted);
  font-weight: 600;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--panel-border);
  white-space: nowrap;
}

.stats-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: background-color 0.2s ease;
}

.stats-table tbody tr {
  cursor: pointer;
  transition: all 0.2s ease;
}

.stats-table tbody tr:not(.empty-state-row):not(.row-empty):hover {
  background-color: var(--hover-bg);
}

/* Weekend and Empty Rows */
.row-weekend td {
  background-color: var(--weekend-bg);
  color: var(--text-muted);
}

.row-empty td {
  background-color: var(--empty-bg);
  opacity: 0.6;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  color: var(--text-muted);
  gap: 0.5rem;
}

.empty-icon {
  width: 32px;
  height: 32px;
  opacity: 0.5;
}

/* Badges & Colors */
.text-win {
  color: var(--win-color) !important;
  font-weight: 600;
}

.text-loss {
  color: var(--loss-color) !important;
  font-weight: 600;
}

.text-center {
  text-align: center;
}

.text-muted {
  color: var(--text-muted);
}

/* Offcanvas */
.offcanvas-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 1040;
  opacity: 0;
  visibility: hidden;
  transition: all 0.3s ease;
}

.offcanvas-overlay.active {
  opacity: 1;
  visibility: visible;
}

.offcanvas-panel {
  position: fixed;
  top: 0;
  right: -75%;
  width: 75%;
  height: 100vh;
  z-index: 1050;
  border-radius: 24px 0 0 24px;
  display: flex;
  flex-direction: column;
  transition: right 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: -10px 0 40px rgba(0, 0, 0, 0.3);
}

.offcanvas-panel.active {
  right: 0;
}

.offcanvas-header {
  padding: 1rem;
  border-bottom: 1px solid var(--panel-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.offcanvas-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.offcanvas-title h2 {
  font-family: var(--font-heading);
  font-size: 1.2rem;
  margin: 0;
}

.badge {
  background: var(--hover-bg);
  padding: 0.2rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: var(--hover-bg);
  color: var(--text-main);
  transform: rotate(90deg);
}

.offcanvas-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

/* Timeline specific styles */
.timeline-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ticker-group {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--panel-border);
}

.ticker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px dashed var(--panel-border);
}

.ticker-name {
  font-family: var(--font-heading);
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent);
}

.ticker-summary-pct {
  font-size: 1rem;
  font-weight: 700;
}

.ticker-trades {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.trade-block {
  margin-top: 6px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 4px;
  padding: 6px 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.trade-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
}

.trade-block-header h4 {
  margin: 0;
  font-size: 0.85rem;
  color: #e2e8f0;
}

.trade-block-stats {
  display: flex;
  align-items: center;
  gap: 12px;
}

.badge-open {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
}

.executions-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.executions-table th, .executions-table td {
  padding: 3px 6px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.executions-table td:nth-child(1) { width: 30%; }
.executions-table td:nth-child(2) { width: 30%; }
.executions-table td:nth-child(3) { width: 40%; }

.executions-table th {
  color: var(--text-muted);
  font-weight: 500;
}

.executions-table tbody tr:last-child td {
  border-bottom: none;
}

/* Responsive */
@media (max-width: 1024px) {
  .offcanvas-panel {
      width: 90%;
      right: -90%;
  }
}

@media (max-width: 768px) {
  .offcanvas-panel {
      width: 100%;
      right: -100%;
      border-radius: 0;
  }
  .trade-block {
      padding: 8px;
  }
  .executions-table {
      font-size: 0.75rem;
  }
}
</style>

<style scoped>
/* Column Management CSS */
.col-manager-wrapper {
  position: relative;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--hover-bg);
  color: var(--text-main);
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid var(--panel-border);
  transition: all 0.2s ease;
  font-family: var(--font-main);
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}

.col-dropdown {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 250px;
  background: #1e293b; /* Solid dark background */
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  z-index: 9999;
  padding: 10px;
}

.col-dropdown-header {
  font-weight: 600;
  padding-bottom: 10px;
  margin-bottom: 10px;
  border-bottom: 1px dashed var(--panel-border);
  color: var(--accent);
}

.col-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.col-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid transparent;
}

.col-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
}

.col-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  user-select: none;
}

.col-actions {
  display: flex;
  gap: 4px;
}

.col-arrow-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.col-arrow-btn:hover:not(:disabled) {
  background: var(--hover-bg);
  color: var(--text-main);
}

.col-arrow-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
