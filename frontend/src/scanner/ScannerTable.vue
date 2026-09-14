<template>
  <div class="scanner-table-container mono">
    <div class="table-header-bar">
      <div class="header-title">LIVE SCANNER (TOP 10)</div>
      <div class="header-actions">
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

    <!-- Table Header -->
    <div class="table-header" :style="gridStyle">
      <span v-for="col in visibleColumns" :key="col.id" :class="['col-' + col.id, { 'calc-col': col.isCalc }]">
        {{ col.label }}
      </span>
    </div>

    <!-- Table Body -->
    <div class="table-body">
      <div v-if="!results || results.length === 0" class="empty-state">
        <span class="empty-icon">📡</span>
        <p>No active momentum scans. Click "SCAN MARKET" to search for top gainers.</p>
      </div>

      <div 
        v-else
        v-for="(item, index) in results" 
        :key="item.symbol"
        class="scan-row"
        :class="{ 'trend-up': item.trend === 'up', 'trend-down': item.trend === 'down' }"
        :style="[gridStyle, { animationDelay: `${index * 0.05}s` }]"
      >
        <template v-for="col in visibleColumns" :key="col.id">
          
          <!-- SYMBOL COLUMN -->
          <div v-if="col.id === 'symbol'" class="col-symbol">
            <span v-if="item.isFetchingHist" class="mini-loader" style="margin-right: 4px;"></span>
            <span v-else class="score-circle" :class="getScoreClass(item.score)" :title="'Score: ' + (item.score || 0)">
              {{ item.score || item.rank || 0 }}
            </span>
            <div class="symbol-info">
              <span class="symbol-name">{{ item.symbol }}</span>
              <span class="symbol-change" :class="getChangeClass(item.changePercent)">
                {{ item.changePercent > 0 ? '+' : '' }}{{ item.changePercent }}%
              </span>
            </div>
          </div>

          <!-- MOVE 5M -->
          <span v-else-if="col.id === 'move5m'" class="col-move5m" :class="getChangeClass(item.move5m)">
            {{ item.move5m !== null && item.move5m !== undefined ? (item.move5m > 0 ? '+' : '') + item.move5m + '%' : '--' }}
          </span>

          <!-- VOL 1M -->
          <span v-else-if="col.id === 'vol1m'" class="col-vol1m">
            {{ item.vol1m || '--' }}
          </span>

          <!-- VOL RATIO -->
          <span v-else-if="col.id === 'volratio'" class="col-volratio font-semibold" :class="getRatioClass(item.volRatio)">
            {{ item.volRatio !== null && item.volRatio !== undefined ? item.volRatio + 'x' : '--' }}
          </span>

          <!-- VOL ACCEL -->
          <span v-else-if="col.id === 'volaccel'" class="col-volaccel font-semibold" :class="getRatioClass(item.volAccel)">
            {{ item.volAccel !== null && item.volAccel !== undefined ? item.volAccel + 'x' : '--' }}
          </span>

          <!-- HISTORICAL: CLOSE -->
          <span v-else-if="col.id === 'close'" class="font-semibold text-white">
            {{ item.close ? '$' + item.close.toFixed(2) : '--' }}
          </span>

          <!-- HISTORICAL: OPEN -->
          <span v-else-if="col.id === 'open'" class="text-muted">
            {{ item.open ? '$' + item.open.toFixed(2) : '--' }}
          </span>

          <!-- HISTORICAL: HIGH -->
          <span v-else-if="col.id === 'high'" class="text-green">
            {{ item.high ? '$' + item.high.toFixed(2) : '--' }}
          </span>

          <!-- HISTORICAL: LOW -->
          <span v-else-if="col.id === 'low'" class="text-red">
            {{ item.low ? '$' + item.low.toFixed(2) : '--' }}
          </span>

          <!-- HISTORICAL: VOLUME -->
          <span v-else-if="col.id === 'volume'" class="text-white">
            {{ formatFloat(item.volume) }}
          </span>

          <!-- HISTORICAL: VWAP -->
          <span v-else-if="col.id === 'vwap'" class="text-yellow">
            {{ item.vwap ? '$' + item.vwap.toFixed(2) : '--' }}
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

        </template>
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

defineProps({
  results: {
    type: Array,
    default: () => []
  }
});

defineEmits(['select-symbol']);

// --- Column Management ---
const defaultCols = [
  { id: 'symbol', label: 'SYMBOL', visible: true, width: '120px' },
  { id: 'close', label: 'CLOSE', visible: true, width: '70px' },
  { id: 'move5m', label: '5M MOVE ✦', visible: true, width: '80px', isCalc: true },
  { id: 'vol1m', label: '1M VOL ✦', visible: true, width: '80px', isCalc: true },
  { id: 'volratio', label: 'VOL RATIO', visible: true, width: '90px' },
  { id: 'volaccel', label: 'VOL ACCEL ✦', visible: true, width: '90px', isCalc: true },
  { id: 'volume', label: 'TOT VOL', visible: false, width: '80px' },
  { id: 'open', label: 'OPEN', visible: false, width: '70px' },
  { id: 'high', label: 'HIGH', visible: false, width: '70px' },
  { id: 'low', label: 'LOW', visible: false, width: '70px' },
  { id: 'vwap', label: 'VWAP', visible: false, width: '70px' },
  { id: 'specs', label: 'SPECS', visible: true, width: '50px' }
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
const gridStyle = computed(() => {
  return {
    display: 'grid',
    gridTemplateColumns: visibleColumns.value.map(c => c.width).join(' '),
    alignItems: 'center'
  };
});

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
}

.table-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.header-title {
  font-size: 12px;
  font-weight: 800;
  color: #94a3b8;
  letter-spacing: 1px;
}

.header-actions {
  position: relative;
}

.btn-columns {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 4px 10px;
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

.table-header {
  padding: 10px 16px 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: transparent;
}

.table-header span {
  font-size: 11px !important;
  font-weight: 800 !important;
  color: #64748b !important;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  line-height: 1.2;
}

.table-header span.calc-col {
  color: #a78bfa !important; /* Distinct purple/pink for calculated columns */
  text-shadow: 0 0 8px rgba(167, 139, 250, 0.4);
}

.table-body {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  overflow-x: auto;
  padding: 8px;
  gap: 4px;
}

.empty-state {
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

.scan-row {
  padding: 10px 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.03);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  animation: slideIn 0.3s ease-out backwards;
  cursor: pointer;
  position: relative;
}

.scan-row:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  z-index: 500;
}

.scan-row.trend-up:hover {
  background: linear-gradient(90deg, rgba(0, 208, 132, 0.1) 0%, transparent 100%);
  border-left: 2px solid #00d084;
}

.scan-row.trend-down:hover {
  background: linear-gradient(90deg, rgba(255, 59, 86, 0.1) 0%, transparent 100%);
  border-left: 2px solid #ff3b56;
}

.col-symbol,
.col-move5m,
.col-vol1m,
.col-volratio,
.col-volaccel {
  font-size: 13px;
  line-height: 1.4;
}

.col-symbol {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.symbol-info {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.symbol-name {
  font-size: 13.5px;
  font-weight: 800;
  color: #38bdf8;
  letter-spacing: 0.5px;
}

.symbol-change {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.score-circle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 4px;
  border-radius: 11px;
  font-size: 10px;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  line-height: 1;
}

.score-circle.text-green {
  background: rgba(0, 208, 132, 0.12);
  border-color: rgba(0, 208, 132, 0.4);
  color: #00d084;
  box-shadow: 0 0 8px rgba(0, 208, 132, 0.2);
}

.score-circle.text-yellow {
  background: rgba(250, 204, 21, 0.12);
  border-color: rgba(250, 204, 21, 0.4);
  color: #facc15;
}

.score-circle.text-muted {
  background: rgba(148, 163, 184, 0.08);
  border-color: rgba(148, 163, 184, 0.2);
  color: #64748b;
}

.col-change,
.col-move5m {
  font-weight: 700;
}

.col-vol1m {
  font-weight: 600;
  color: #cbd5e1;
}

.col-volratio,
.col-volaccel {
  font-weight: 600;
}

.col-specs.specs-icon {
  width: 17px;
  height: 17px;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.2s ease;
  justify-self: start;
}

.col-specs.specs-icon:hover {
  color: rgba(255, 255, 255, 0.95);
  transform: scale(1.15);
}

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

.row-target {
  color: #94a3b8;
  font-weight: 500;
}

.row-val {
  font-weight: 700;
  color: #f1f5f9;
}

.popover-row.met {
  background: rgba(0, 208, 132, 0.1);
  border-color: rgba(0, 208, 132, 0.35);
}
.popover-row.met .row-target { color: #a7f3d0; }
.popover-row.met .row-val { color: #00ff88; text-shadow: 0 0 8px rgba(0, 208, 132, 0.3); }
.popover-no-data { font-size: 12px; color: #64748b; text-align: center; padding: 10px 0; }
@keyframes popoverFadeIn { from { opacity: 0; transform: translate(-50%, -4px); } to { opacity: 1; transform: translate(-50%, 0); } }
.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.text-yellow { color: #facc15; }
.text-muted { color: #64748b; }
.text-white { color: #fff; }
.font-semibold { font-weight: 600; }
.text-glow-red { text-shadow: 0 0 10px rgba(255, 59, 86, 0.4); }
@keyframes slideIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }

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
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
