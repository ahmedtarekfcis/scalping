<template>
  <div class="scanner-table-container mono">
    <div class="table-header-bar">
      <div class="header-title">LIVE SCANNER (TOP 10)</div>
      <div class="header-actions">
        <button 
          class="btn-scan mono font-bold" 
          @click="store.scanMarket()"
          :class="{ 'is-scanning': store.isScanning }"
        >
          <span class="scan-icon">⚡</span>
          {{ store.isScanning ? 'SCANNING...' : 'FORCE RE-SCAN' }}
        </button>

        <button class="btn-columns" @click="toggleColSettings">
          <svg class="icon" viewBox="0 0 20 20" fill="currentColor">
            <path d="M5 4h10v2H5V4zm0 5h10v2H5V9zm0 5h10v2H5v-2z" />
          </svg>
          Columns
        </button>
        
        <!-- Column Settings Popover -->
        <div v-if="showColSettings" class="col-settings-popover">
          <div class="col-settings-header">Manage Columns</div>
          <div class="col-list">
            <div 
              v-for="(col, idx) in columns" 
              :key="col.id"
              class="col-item"
            >
              <label class="col-label">
                <input type="checkbox" v-model="col.visible" @change="saveCols" />
                {{ col.label }}
              </label>
              <div class="col-movers">
                <button @click="moveCol(idx, -1)" :disabled="idx === 0">▲</button>
                <button @click="moveCol(idx, 1)" :disabled="idx === columns.length - 1">▼</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Cards Grid -->
    <div class="cards-grid">
      <div v-if="!results || results.length === 0" class="empty-state">
        <span class="empty-icon">📡</span>
        <p>No active momentum scans. Click "SCAN MARKET" to search for top gainers.</p>
      </div>

      <div 
        v-else
        v-for="(item, index) in results" 
        :key="item.symbol"
        class="scan-card"
        :class="{ 'trend-up': item.trend === 'up', 'trend-down': item.trend === 'down' }"
        :style="{ animationDelay: `${index * 0.05}s` }"
      >
        <!-- CARD HEADER -->
        <div class="card-header">
           <div class="symbol-info">
             <span v-if="item.isFetchingHist" class="mini-loader" style="margin-right: 6px;"></span>
             <span class="symbol-name">{{ item.symbol }}</span>
             <span class="symbol-change" :class="getChangeClass(item.gap_pct)">
               {{ item.gap_pct !== '--' && item.gap_pct !== undefined ? (item.gap_pct > 0 ? '+' : '') + item.gap_pct + '%' : '' }}
             </span>
           </div>
           
           <span v-if="isScoreVisible" class="score-circle" :class="getScoreClass(item.score)" :title="'Score: ' + (item.score || 0)">
              {{ item.score || item.rank || 0 }}
           </span>
        </div>

        <!-- CARD BODY (Configurable Columns) -->
        <div class="card-body">
          <template v-for="col in visibleColumns" :key="col.id">
            <div class="card-stat" v-if="col.id !== 'symbol' && col.id !== 'score'">
              <span class="stat-label" :class="{'calc-col': col.isCalc}">{{ col.label }}</span>
              <span class="stat-value">
                
                <!-- PRICE -->
                <span v-if="col.id === 'price'" class="font-semibold text-white">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <span v-else>{{ item.price ? item.price.toFixed(2) : '--' }}</span>
                </span>

                <!-- FLOAT -->
                <span v-else-if="col.id === 'float'" class="text-muted font-semibold">
                  --
                </span>

                <!-- VOLUME (Daily) -->
                <span v-else-if="col.id === 'volume'" class="text-white font-semibold">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <span v-else>{{ formatFloat(item.daily_vol) }}</span>
                </span>

                <!-- GAP -->
                <span v-else-if="col.id === 'gap'" class="font-semibold" :class="getChangeClass(item.gap_pct)">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <span v-else>{{ item.gap_pct !== '--' ? (item.gap_pct > 0 ? '+' : '') + item.gap_pct + '%' : '--' }}</span>
                </span>

                <!-- 1M MOMENTUM -->
                <span v-else-if="col.id === 'mom1m'" class="font-semibold" :class="getChangeClass(item.mom1m)">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <span v-else>{{ item.mom1m !== '--' ? (item.mom1m > 0 ? '+' : '') + item.mom1m + '%' : '--' }}</span>
                </span>

                <!-- VOL ACCEL -->
                <span v-else-if="col.id === 'volaccel'" class="font-semibold" :class="getRatioClass(item.volAccel)">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <span v-else>{{ item.volAccel !== '--' ? item.volAccel + 'x' : '--' }}</span>
                </span>

                <!-- 5M/15M TREND -->
                <div v-else-if="col.id === 'trend'" class="flex-col font-semibold">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <template v-else>
                    <span :class="getChangeClass(item.move5m)">5M: {{ item.move5m !== '--' ? (item.move5m > 0 ? '+' : '') + item.move5m + '%' : '--' }}</span>
                    <span :class="getChangeClass(item.move15m)" style="font-size: 0.9em; opacity: 0.8">15M: {{ item.move15m !== '--' ? (item.move15m > 0 ? '+' : '') + item.move15m + '%' : '--' }}</span>
                  </template>
                </div>

                <!-- VWAP/EMA -->
                <div v-else-if="col.id === 'vwap_ema'" class="flex-col font-semibold">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <template v-else>
                    <span class="text-yellow">V: {{ item.vwap ? item.vwap.toFixed(2) : '--' }}</span>
                    <span class="text-muted" style="font-size: 0.9em;">E: {{ item.ema !== '--' ? item.ema : '--' }}</span>
                  </template>
                </div>

                <!-- HOD ROOM -->
                <span v-else-if="col.id === 'hod_room'" class="text-white font-semibold">
                  <span v-if="item.isFetchingHist" class="mini-loader"></span>
                  <span v-else>{{ item.hod_room !== '--' ? item.hod_room + '%' : '--' }}</span>
                </span>

                <!-- SPECS -->
                <svg 
                  v-else-if="col.id === 'specs'"
                  class="col-specs specs-icon" 
                  viewBox="0 0 20 20" 
                  fill="currentColor"
                  title="View Specs"
                  @mouseenter="showPopover($event, item)"
                  @mouseleave="hidePopover"
                >
                  <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                </svg>

              </span>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Teleported Global Popover -->
    <Teleport to="body">
      <div 
        v-if="activePopoverItem" 
        class="specs-popover-teleported mono"
        :style="popoverStyle"
        @mouseenter="keepPopover"
        @mouseleave="hidePopover"
      >
        <div class="popover-header">
          <span class="popover-sym">{{ activePopoverItem.symbol }}</span>
          <span class="popover-badge">SPECS</span>
        </div>

        <div class="popover-list" v-if="activePopoverItem.specs">
          <!-- Price -->
          <div class="popover-row" :class="{ 'met': activePopoverItem.specs.price }">
            <span class="row-target">Price $1.5 – 15</span>
            <span class="row-val">${{ activePopoverItem.lastPrice }}</span>
          </div>
          <!-- Total Volume -->
          <div class="popover-row" :class="{ 'met': activePopoverItem.specs.vol }">
            <span class="row-target">Vol &gt; 800K</span>
            <span class="row-val">{{ activePopoverItem.volume }}</span>
          </div>
          <!-- Relative Volume (RV) -->
          <div class="popover-row" :class="{ 'met': activePopoverItem.specs.rv }">
            <span class="row-target">Rel Vol &gt; 3.0</span>
            <span class="row-val">{{ activePopoverItem.rv ? activePopoverItem.rv : '--' }}</span>
          </div>
          <!-- Float -->
          <div class="popover-row" :class="{ 'met': activePopoverItem.specs.float }">
            <span class="row-target">Float &lt; 20M</span>
            <span class="row-val">{{ formatFloat(activePopoverItem.freeFloat) }}</span>
          </div>
        </div>

        <div v-else class="popover-no-data">
          No specs data
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();

defineProps({
  results: {
    type: Array,
    default: () => []
  }
});

defineEmits(['select-symbol']);

// --- Column Management ---
const defaultCols = [
  { id: 'symbol', label: 'SYMBOL', visible: true },
  { id: 'price', label: 'PRICE', visible: true },
  { id: 'float', label: 'FLOAT', visible: true },
  { id: 'volume', label: 'VOLUME', visible: true },
  { id: 'gap', label: 'GAP %', visible: true },
  { id: 'mom1m', label: '1M MOM ✦', visible: true, isCalc: true },
  { id: 'volaccel', label: 'VOL ACCEL ✦', visible: true, isCalc: true },
  { id: 'trend', label: '5M/15M TREND ✦', visible: true, isCalc: true },
  { id: 'vwap_ema', label: 'VWAP/EMA ✦', visible: true, isCalc: true },
  { id: 'hod_room', label: 'HOD ROOM', visible: true },
  { id: 'score', label: 'MOMENTUM', visible: true },
  { id: 'specs', label: 'SPECS', visible: false }
];

const columns = ref([...defaultCols]);
const showColSettings = ref(false);

onMounted(() => {
  const saved = localStorage.getItem('scannerColumns');
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      // Merge saved state with defaults to support new columns
      const merged = parsed.map(p => {
        const def = defaultCols.find(d => d.id === p.id);
        return def ? { ...def, visible: p.visible } : null;
      }).filter(Boolean);
      
      // Add any new columns that aren't in saved state
      defaultCols.forEach(d => {
        if (!merged.find(m => m.id === d.id)) merged.push(d);
      });
      
      columns.value = merged;
    } catch (e) {
      console.error(e);
    }
  }
});

const visibleColumns = computed(() => columns.value.filter(c => c.visible));
const isScoreVisible = computed(() => columns.value.some(c => c.id === 'score' && c.visible));

function toggleColSettings() {
  showColSettings.value = !showColSettings.value;
}

function saveCols() {
  localStorage.setItem('scannerColumns', JSON.stringify(columns.value));
}

function moveCol(idx, dir) {
  if (idx + dir < 0 || idx + dir >= columns.value.length) return;
  const temp = columns.value[idx];
  columns.value[idx] = columns.value[idx + dir];
  columns.value[idx + dir] = temp;
  saveCols();
}

// --- Popover & Formatting Logic ---
const activePopoverItem = ref(null);
const popoverPos = ref({ top: 0, left: 0 });
let hideTimeout = null;

function showPopover(event, item) {
  if (hideTimeout) {
    clearTimeout(hideTimeout);
    hideTimeout = null;
  }
  const rect = event.currentTarget.getBoundingClientRect();
  popoverPos.value = {
    top: rect.bottom + 8,
    left: rect.left + rect.width / 2
  };
  activePopoverItem.value = item;
}

function hidePopover() {
  hideTimeout = setTimeout(() => {
    activePopoverItem.value = null;
  }, 120);
}

function keepPopover() {
  if (hideTimeout) {
    clearTimeout(hideTimeout);
    hideTimeout = null;
  }
}

const popoverStyle = computed(() => ({
  top: `${popoverPos.value.top}px`,
  left: `${popoverPos.value.left}px`
}));

function getChangeClass(change) {
  if (change > 0) return 'text-green text-glow-green';
  if (change < 0) return 'text-red text-glow-red';
  return 'text-muted';
}

function getScoreClass(score) {
  if (score >= 75) return 'text-green text-glow-green';
  if (score >= 40) return 'text-yellow';
  return 'text-muted';
}

function getRatioClass(ratio) {
  if (ratio === null || ratio === undefined) return 'text-muted';
  if (ratio >= 2.0) return 'text-green text-glow-green';
  if (ratio >= 1.2) return 'text-yellow';
  return 'text-muted';
}

function formatFloat(val) {
  if (val === undefined || val === null || val === 0 || val === 'N/A') return 'N/A';
  const num = typeof val === 'string' ? parseFloat(val.replace(/,/g, '')) : val;
  if (isNaN(num)) return val;
  if (num >= 1_000_000_000) return (num / 1_000_000_000).toFixed(1) + 'B';
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
  if (num >= 1_000) return (num / 1_000).toFixed(0) + 'K';
  return num.toLocaleString();
}
</script>

<style scoped>
.scanner-table-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(13, 17, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  max-height: calc(100vh - 100px);
}

.table-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px 8px 0 0;
}

.header-title {
  font-size: 13px;
  font-weight: 800;
  color: #94a3b8;
  letter-spacing: 1px;
}

.header-actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-scan {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(37, 99, 235, 0.2) 100%);
  border: 1px solid rgba(56, 189, 248, 0.5);
  color: #38bdf8;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.1);
}

.btn-scan:hover {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.3) 0%, rgba(37, 99, 235, 0.3) 100%);
  border-color: #38bdf8;
  box-shadow: 0 0 15px rgba(56, 189, 248, 0.3);
  transform: translateY(-1px);
}

.btn-scan:active {
  transform: translateY(1px);
}

.btn-scan.is-scanning {
  opacity: 0.7;
  pointer-events: none;
  animation: pulse 1s infinite alternate;
}

@keyframes pulse {
  0% { opacity: 0.6; box-shadow: 0 0 10px rgba(56, 189, 248, 0.1); }
  100% { opacity: 1; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5); }
}

.btn-columns {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-columns:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.btn-columns .icon {
  width: 14px;
  height: 14px;
}

.col-settings-popover {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  width: 220px;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 6px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.5);
  z-index: 1000;
  padding: 8px;
}

.col-settings-header {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  padding-bottom: 6px;
  margin-bottom: 6px;
  border-bottom: 1px solid #1e293b;
}

.col-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 250px;
  overflow-y: auto;
}

.col-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.02);
}

.col-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.col-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #cbd5e1;
  cursor: pointer;
}

.col-movers {
  display: flex;
  gap: 2px;
}

.col-movers button {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 2px;
  font-size: 10px;
}

.col-movers button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.col-movers button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* CARDS GRID LAYOUT */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 16px;
  overflow-y: auto;
  max-height: 100%;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
  gap: 16px;
}

.empty-icon {
  font-size: 40px;
  opacity: 0.5;
}

/* INDIVIDUAL CARD */
.scan-card {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  overflow: hidden;
  height: max-content;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  animation: slideIn 0.4s ease-out backwards;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.scan-card:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.25);
  z-index: 10;
}

.scan-card.trend-up {
  border-top: 3px solid #00d084;
}

.scan-card.trend-down {
  border-top: 3px solid #ff3b56;
}

.scan-card.trend-up:hover {
  box-shadow: 0 10px 30px rgba(0, 208, 132, 0.15);
}

.scan-card.trend-down:hover {
  box-shadow: 0 10px 30px rgba(255, 59, 86, 0.15);
}

/* CARD HEADER */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.symbol-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.symbol-name {
  font-size: 18px;
  font-weight: 900;
  color: #38bdf8;
  letter-spacing: 0.5px;
  text-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
}

.symbol-change {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.score-circle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 26px;
  padding: 0 6px;
  border-radius: 13px;
  font-size: 12px;
  font-weight: 900;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  line-height: 1;
}

.score-circle.text-green {
  background: rgba(0, 208, 132, 0.12);
  border-color: rgba(0, 208, 132, 0.4);
  color: #00d084;
  box-shadow: 0 0 12px rgba(0, 208, 132, 0.25);
}

.score-circle.text-yellow {
  background: rgba(250, 204, 21, 0.12);
  border-color: rgba(250, 204, 21, 0.4);
  color: #facc15;
}

.card-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
.card-stat:last-child {
  border-bottom: none;
}

.stat-label {
  font-size: 10px;
  font-weight: 800;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-label.calc-col {
  color: #a78bfa;
  text-shadow: 0 0 8px rgba(167, 139, 250, 0.3);
}

.stat-value {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  min-height: 20px;
}

.flex-col {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.col-specs.specs-icon {
  width: 17px;
  height: 17px;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.2s ease;
}

.col-specs.specs-icon:hover {
  color: rgba(255, 255, 255, 0.95);
  transform: scale(1.15);
}

/* POPOVER STYLES */
.specs-popover-teleported {
  position: fixed;
  transform: translateX(-50%);
  width: 320px;
  background: #090d16;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.9), 0 0 0 1px rgba(255, 255, 255, 0.08);
  z-index: 999999;
  pointer-events: auto;
  cursor: default;
  animation: popoverFadeIn 0.15s ease-out;
}

.popover-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.popover-sym {
  font-size: 14px;
  font-weight: 800;
  color: #38bdf8;
  letter-spacing: 0.5px;
}

.popover-badge {
  font-size: 10px;
  font-weight: 800;
  color: #64748b;
  letter-spacing: 0.5px;
}

.popover-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.popover-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 12.5px;
}

.row-target { color: #94a3b8; font-weight: 500; }
.row-val { font-weight: 700; color: #f1f5f9; }
.popover-row.met { background: rgba(0, 208, 132, 0.1); border-color: rgba(0, 208, 132, 0.35); }
.popover-row.met .row-target { color: #a7f3d0; }
.popover-row.met .row-val { color: #00ff88; text-shadow: 0 0 8px rgba(0, 208, 132, 0.3); }
.popover-no-data { font-size: 12px; color: #64748b; text-align: center; padding: 10px 0; }

@keyframes popoverFadeIn { from { opacity: 0; transform: translate(-50%, -4px); } to { opacity: 1; transform: translate(-50%, 0); } }
@keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

/* UTILITY CLASSES */
.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.text-yellow { color: #facc15; }
.text-muted { color: #64748b; }
.text-white { color: #fff; }
.font-semibold { font-weight: 600; }
.text-glow-red { text-shadow: 0 0 10px rgba(255, 59, 86, 0.4); }
.text-glow-green { text-shadow: 0 0 10px rgba(0, 208, 132, 0.4); }

/* Mini Loader */
.mini-loader {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-left-color: #38bdf8;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
