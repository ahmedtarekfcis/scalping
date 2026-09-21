<script setup>
import { ref, computed, onMounted } from 'vue';
import Papa from 'papaparse';
import { BarChart2, UploadCloud, FileSpreadsheet, X, Settings2, ChevronUp, ChevronDown } from 'lucide-vue-next';

// State
const uploadStatus = ref('No file chosen');
const dailyStats = ref({});
const minDate = ref(null);
const maxDate = ref(null);
const expandedRows = ref({});
const filterStartDate = ref('');
const filterEndDate = ref('');

const DEFAULT_COLUMNS = [
  { id: 'dateStr', label: 'Date', visible: true, order: 0 },
  { id: 'totalTrades', label: 'Trades', visible: true, order: 1 },
  { id: 'wins', label: 'Win', visible: true, order: 2 },
  { id: 'losses', label: 'Loss', visible: true, order: 3 },
  { id: 'avgWin', label: 'Avg W per Trade', visible: true, order: 4 },
  { id: 'avgLoss', label: 'Avg L per Trade', visible: true, order: 5 },
  { id: 'tickersSummary', label: 'Tickers PnL', visible: true, order: 6 }
];

let initialCols = DEFAULT_COLUMNS;
try {
  const savedColsStr = localStorage.getItem('tradeStatsCols');
  if (savedColsStr) {
    const parsed = JSON.parse(savedColsStr);
    if (parsed.some(c => c.id === 'totalPnL' || c.id === 'netPnL' || c.id === 'dayRet') || !parsed.some(c => c.id === 'tickersSummary')) {
      localStorage.removeItem('tradeStatsCols');
    } else {
      initialCols = parsed.map(c => {
        const defCol = DEFAULT_COLUMNS.find(dc => dc.id === c.id);
        if (defCol) {
          c.label = defCol.label;
        }
        return c;
      });
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
          let execPnL = 0;
          let execCostBasis = 0;
          
          while (remainingQtyToClose > 0 && openLots.length > 0) {
            let lot = openLots[0];
            let qtyToMatch = Math.min(lot.qty, remainingQtyToClose);
            let lotCostProRata = (qtyToMatch / lot.qty) * lot.netAmount;
            let closeRevenueProRata = (qtyToMatch / qty) * netAmount;
            
            let pnl = positionDirection === 'B' || positionDirection === 'BUY'
              ? closeRevenueProRata - lotCostProRata 
              : lotCostProRata - closeRevenueProRata;
            
            execPnL += pnl;
            execCostBasis += lotCostProRata;
            
            currentTradePnL += pnl;
            currentTradeCostBasis += lotCostProRata;
            tickerPnL += pnl;
            
            lot.qty -= qtyToMatch;
            lot.netAmount -= lotCostProRata;
            remainingQtyToClose -= qtyToMatch;
            
            if (lot.qty <= 0) openLots.shift();
          }
          
          exec.pnlPct = execCostBasis > 0 ? (execPnL / execCostBasis) * 100 : 0;
          
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
              currentTradeExecutions = [{ ...exec, pnlPct: undefined }]; // The flip execution starts the next trade
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
  return dates.reverse();
});

const dailyRows = computed(() => {
  return allDates.value.filter(dateObj => {
    if (filterStartDate.value) {
      const start = new Date(filterStartDate.value);
      if (dateObj < start) return false;
    }
    if (filterEndDate.value) {
      const end = new Date(filterEndDate.value);
      end.setUTCHours(23, 59, 59, 999);
      if (dateObj > end) return false;
    }
    return true;
  }).map(dateObj => {
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
    
    let flattenedTrades = [];
    let tickersList = [];
    Object.entries(dayData.tickers).forEach(([ticker, data]) => {
      let tickerTotalPnL = 0;
      let tickerTotalCost = 0;
      let tickerTrades = data.trades.map((trade, index) => {
        tickerTotalPnL += trade.pnl || 0;
        tickerTotalCost += trade.costBasis || 0;
        let t = {
          ...trade,
          symbol: ticker,
          tradeId: `${ticker}#${index + 1}`
        };
        flattenedTrades.push(t);
        return t;
      });
      
      let pct = tickerTotalCost > 0 ? (tickerTotalPnL / tickerTotalCost) * 100 : 0;
      
      tickersList.push({
        symbol: ticker,
        pnl: data.pnl,
        commission: data.commission,
        pct: pct,
        trades: tickerTrades
      });
    });
    
    flattenedTrades.sort((a, b) => {
      let timeA = a.executions[0]?.time || '';
      let timeB = b.executions[0]?.time || '';
      return timeA.localeCompare(timeB);
    });
    
    // Sort tickers alphabetically
    tickersList.sort((a, b) => a.symbol.localeCompare(b.symbol));
    
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
      flattenedTrades,
      tickersList
    };
  });
});

const getColClass = (colId, row) => {
  if (colId === 'wins' || colId === 'avgWin') return 'text-win';
  if (colId === 'losses' || colId === 'avgLoss') return 'text-loss';
  return '';
};

const getColStyle = (colId) => {
  const widths = {
    dateStr: '110px',
    totalTrades: '80px',
    wins: '60px',
    losses: '60px',
    avgWin: '120px',
    avgLoss: '120px',
    tickersSummary: 'auto'
  };
  return { width: widths[colId] || 'auto' };
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

// UI Actions
const toggleRow = (dateStr) => {
  expandedRows.value[dateStr] = !expandedRows.value[dateStr];
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
            <div class="date-filter-group">
              <input type="date" v-model="filterStartDate" class="date-input" title="Start Date" />
              <span class="date-separator">to</span>
              <input type="date" v-model="filterEndDate" class="date-input" title="End Date" />
            </div>
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
                <th v-for="col in visibleColumns" :key="col.id" :style="getColStyle(col.id)">{{ col.label }}</th>
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
                <template v-for="row in dailyRows" :key="row.dateStr">
                  <tr 
                    :class="{ 'row-weekend': row.isWeekend, 'row-empty': row.isEmpty && !row.isWeekend, 'row-expanded': expandedRows[row.dateStr] }"
                    @click="!row.isEmpty ? toggleRow(row.dateStr) : null"
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
                        <template v-else-if="col.id === 'tickersSummary'">
                          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                            <span v-for="t in row.tickersList" :key="t.symbol" 
                                  class="ticker-tag"
                                  :class="t.pct >= 0 ? 'tag-win' : 'tag-loss'">
                              {{ t.symbol }} {{ t.pct >= 0 ? '+' : '' }}{{ t.pct.toFixed(2) }}%
                            </span>
                          </div>
                        </template>
                      </td>
                    </template>
                  </tr>
                  
                  <tr v-if="expandedRows[row.dateStr]" class="expanded-detail-row">
                    <td :colspan="visibleColumns.length">
                      <div class="expanded-content">
                        <div v-for="tickerGroup in row.tickersList" :key="tickerGroup.symbol" class="ticker-group">
                          <div class="trades-grid">
                            <div class="trade-block" v-for="trade in tickerGroup.trades" :key="trade.tradeId">
                              <div class="trade-block-header">
                                <div class="trade-title-group">
                                  <h4>{{ trade.tradeId }}</h4>
                                </div>
                                <div class="trade-block-stats">
                                  <span v-if="trade.isOpen" class="badge-open">OPEN</span>
                                  <span :class="trade.pnl >= 0 ? 'text-win' : 'text-loss'" style="font-weight: 600;">
                                    PnL: {{ trade.pnl >= 0 ? '+' : '' }}{{ trade.costBasis > 0 ? ((trade.pnl / trade.costBasis) * 100).toFixed(2) : '0.00' }}%
                                  </span>
                                </div>
                              </div>
                              
                              <div class="table-container" style="margin-top: 4px; padding: 0;">
                                <table class="executions-table">
                                  <tbody>
                                    <tr v-for="(exec, idx) in trade.executions" :key="idx">
                                      <td :class="exec.type === 'BUY' ? 'text-win' : 'text-loss'"><strong>{{ exec.type }}</strong></td>
                                      <td>${{ exec.price.toFixed(3) }}</td>
                                      <td v-if="exec.pnlPct !== undefined" :class="exec.pnlPct >= 0 ? 'text-win' : 'text-loss'" style="text-align: right; font-weight: 500;">
                                        {{ exec.pnlPct >= 0 ? '+' : '' }}{{ exec.pnlPct.toFixed(2) }}%
                                      </td>
                                      <td v-else></td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
              </template>
            </tbody>
          </table>
        </div>
      </main>
    </div>
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
  margin-right: auto;
  margin-left: auto;
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
.date-filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--panel-border);
}

.date-input {
  background: transparent;
  border: none;
  color: var(--text-main);
  font-family: var(--font-body);
  font-size: 0.85rem;
  outline: none;
  cursor: pointer;
}

.date-input::-webkit-calendar-picker-indicator {
  filter: invert(1);
  opacity: 0.6;
  cursor: pointer;
}

.date-input::-webkit-calendar-picker-indicator:hover {
  opacity: 1;
}

.date-separator {
  color: var(--text-muted);
  font-size: 0.85rem;
}

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
  table-layout: fixed;
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

.stats-table tbody tr:not(.empty-state-row):not(.row-empty):not(.row-weekend):hover {
  background-color: var(--hover-bg);
}

/* Weekend and Empty Rows */
.stats-table tbody tr.row-weekend,
.stats-table tbody tr.row-empty {
  cursor: default;
}

.row-weekend td,
.row-empty td {
  background-color: rgba(0, 0, 0, 0.35);
  color: rgba(255, 255, 255, 0.3);
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

.ticker-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: 0.02em;
}

.ticker-tag.tag-win {
  background-color: var(--win-bg);
  color: var(--win-color);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.ticker-tag.tag-loss {
  background-color: var(--loss-bg);
  color: var(--loss-color);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.text-center {
  text-align: center;
}

.text-muted {
  color: var(--text-muted);
}

/* Expanded Row */
.row-expanded td {
  background-color: var(--hover-bg);
}

.expanded-detail-row td {
  padding: 0;
  border-bottom: 1px solid var(--panel-border);
}

.expanded-content {
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.2);
  box-shadow: inset 0 3px 6px rgba(0,0,0,0.1);
}

.ticker-group {
  margin-bottom: 2rem;
}

.ticker-group:last-child {
  margin-bottom: 0;
}

.ticker-header {
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.ticker-header h3 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-main);
  display: flex;
  align-items: center;
}

.ticker-pnl {
  font-size: 0.95rem;
  margin-left: 0.75rem;
}

.trades-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.trade-block {
  background: var(--panel-bg);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.trade-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
}

.trade-title-group h4 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 1rem;
  color: var(--accent);
  font-weight: 600;
  text-transform: uppercase;
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
  padding: 4px 6px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.executions-table td:nth-child(1) { width: 30%; }
.executions-table td:nth-child(2) { width: 40%; }
.executions-table td:nth-child(3) { width: 30%; }

.executions-table tbody tr:last-child td {
  border-bottom: none;
}

/* Responsive */
@media (max-width: 768px) {
  .trades-grid {
    grid-template-columns: 1fr;
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
