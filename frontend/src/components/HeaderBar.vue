<script setup>
import { ref, computed, watch } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();
const inputSymbol = ref(store.symbol || '');

watch(() => store.symbol, (newVal) => {
  if (newVal) {
    inputSymbol.value = newVal;
  }
});

const props = defineProps({
  currentPage: {
    type: String,
    default: 'dashboard'
  }
});

const emit = defineEmits(['open-settings', 'go-scanner', 'go-dashboard']);

function handleSymbolSubmit() {
  if (inputSymbol.value) {
    store.changeSymbol(inputSymbol.value);
  }
}

function syncWebull() {
  if (store.ws && store.ws.readyState === WebSocket.OPEN && store.symbol) {
    store.ws.send(JSON.stringify({ action: 'SYNC_WEBULL', symbol: store.symbol }));
  }
}

const statusClass = computed(() => {
  if (!store.wsConnected) return 'status-disconnected';
  return 'status-live';
});

const statusText = computed(() => {
  if (!store.wsConnected) return 'DISCONNECTED';
  return `IBKR LIVE (${store.status?.port || 'Connected'})`;
});


const activeMomentumScans = computed(() => {
  if (!store.scannerResults) return [];
  return [...store.scannerResults]
    .sort((a, b) => (b.score || 0) - (a.score || 0))
    .slice(0, 5);
});

// --- Popover Logic ---
const hoveredItem = ref(null);
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
  hoveredItem.value = item;
}

function hidePopover() {
  hideTimeout = setTimeout(() => {
    hoveredItem.value = null;
  }, 100);
}

const popoverStyle = computed(() => ({
  top: `${popoverPos.value.top}px`,
  left: `${popoverPos.value.left}px`
}));

function formatFloat(val) {
  if (val === undefined || val === null || val === 0 || val === 'N/A' || val === '--') return '--';
  const num = typeof val === 'string' ? parseFloat(val.replace(/,/g, '')) : val;
  if (isNaN(num)) return val;
  if (num >= 1_000_000_000) return (num / 1_000_000_000).toFixed(1) + 'B';
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
  if (num >= 1_000) return (num / 1_000).toFixed(0) + 'K';
  return num.toLocaleString();
}
</script>

<template>
  <div class="market-header glass-panel">
    


    <!-- Left & Center: Symbol Search + Scanner Chips -->
    <div class="symbol-and-chips">
      <div class="symbol-search-wrap">
        <button class="btn-sync" @click="syncWebull" title="Sync to Webull">
          ⮂
        </button>
        <input 
          v-model="inputSymbol" 
          @keyup.enter="handleSymbolSubmit"
          placeholder="SYMBOL..." 
          class="symbol-input mono"
        />
      </div>

      <div class="chips-container">
        <button 
          v-for="item in activeMomentumScans" 
          :key="item.symbol"
          class="scan-chip mono"
          :class="{ 'chip-up': item.trend === 'up', 'chip-down': item.trend === 'down' }"
          @click="store.changeSymbol(item.symbol)"
          @mouseenter="showPopover($event, item)"
          @mouseleave="hidePopover"
        >
          {{ item.symbol }} 
          <div style="position: absolute; top: -5px; right: -3px; color: #facc15; font-size: 10px; font-weight: 900; text-shadow: 0 0 4px rgba(0,0,0,0.8);">
            {{ item.score }}
          </div>
          <!-- Live 1M Vol (Bottom Right, only if subscribed) -->
          <div v-if="item.symbol === store.symbol && store.currentVol1m > 0" style="position: absolute; bottom: -5px; right: -3px; color: #38bdf8; font-size: 9.5px; font-weight: 900; background: #0f172a; border-radius: 3px; padding: 0 3px; border: 1px solid rgba(56, 189, 248, 0.4); text-shadow: none;">
             {{ formatFloat(store.currentVol1m) }}
          </div>
        </button>
        <span v-if="activeMomentumScans.length === 0" class="text-muted" style="font-size: 11px;">
          No ACTIVE Momentum
        </span>
      </div>
    </div>

    <!-- Right: Connection Badge & Quick Settings -->
    <div class="status-section">
      <div class="api-status-dot" :class="store.wsConnected ? 'connected' : 'disconnected'" :title="store.wsConnected ? 'API Connected' : 'API Disconnected'"></div>
    </div>
  </div>

  <!-- Teleported Global Popover for Chips -->
  <Teleport to="body">
    <div 
      v-if="hoveredItem" 
      class="chip-popover mono"
      :style="popoverStyle"
    >
      <div class="popover-title">{{ hoveredItem.symbol }}</div>
      <div class="popover-row">
        <span class="row-label">Total Vol:</span> 
        <span class="row-val">{{ formatFloat(hoveredItem.daily_vol) }}</span>
      </div>
      <div class="popover-row">
        <span class="row-label">VWAP:</span> 
        <span class="row-val">{{ hoveredItem.vwap || '--' }}</span>
      </div>
      <div class="popover-row">
        <span class="row-label">1M Vol:</span> 
        <span class="row-val">{{ formatFloat(hoveredItem.vol1m) }}</span>
      </div>
      <div class="popover-row">
        <span class="row-label">RV:</span> 
        <span class="row-val text-green">{{ hoveredItem.volAccel !== '--' ? hoveredItem.volAccel + 'x' : '--' }}</span>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.market-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  gap: 16px;
  flex-wrap: wrap;
}

.symbol-and-chips {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.symbol-search-wrap {
  display: flex;
  align-items: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.symbol-input {
  background: transparent;
  border: none;
  padding: 6px 8px 6px 24px;
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 800;
  width: calc(5ch + 32px);
  outline: none;
  text-transform: uppercase;
  text-align: center;
}

.btn-sync {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 0 4px 0 6px;
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
}

.btn-sync:hover {
  color: var(--accent-blue);
}

.status-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.connection-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.5px;
  cursor: pointer;
}

.status-live {
  background: rgba(0, 208, 132, 0.15);
  color: var(--green-bid);
  border: 1px solid rgba(0, 208, 132, 0.3);
}
.status-live .pulse-dot {
  background: var(--green-bid);
  box-shadow: 0 0 8px var(--green-bid-glow);
}



.status-disconnected {
  background: rgba(255, 59, 86, 0.15);
  color: var(--red-ask);
  border: 1px solid rgba(255, 59, 86, 0.3);
}
.status-disconnected .pulse-dot {
  background: var(--red-ask);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.9); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.8; }
}


.api-status-dot {
  position: fixed;
  top: 4px;
  right: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  z-index: 10000;
}

.api-status-dot.connected {
  background-color: var(--green-bid);
  box-shadow: 0 0 8px var(--green-bid-glow, rgba(0, 208, 132, 0.5));
}

.api-status-dot.disconnected {
  background-color: var(--red-ask);
  animation: flash-red 0.8s infinite alternate;
}

@keyframes flash-red {
  0% { transform: scale(1); opacity: 1; box-shadow: 0 0 5px var(--red-ask); }
  100% { transform: scale(1.3); opacity: 0.5; box-shadow: 0 0 15px var(--red-ask); }
}

.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.bg-green-soft { background: var(--green-bid-bg); }
.bg-red-soft { background: var(--red-ask-bg); }

.flash-up {
  color: #fff !important;
  text-shadow: 0 0 10px var(--green-bid);
}
.flash-down {
  color: #fff !important;
  text-shadow: 0 0 10px var(--red-ask);
}



/* Scanner Chips */
.chips-container {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.scan-chip {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  padding: 5px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.scan-chip:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}

.chip-up {
  border-color: rgba(0, 208, 132, 0.3);
}

.chip-up:hover {
  background: rgba(0, 208, 132, 0.15);
  border-color: #00d084;
}

.chip-down {
  border-color: rgba(255, 59, 86, 0.3);
}

.chip-down:hover {
  background: rgba(255, 59, 86, 0.15);
  border-color: #ff3b56;
}

.chip-change {
  font-size: 12px;
  font-weight: 900;
}

.chip-up .chip-change { color: #00d084; }
.chip-down .chip-change { color: #ff3b56; }

/* Popover Styles */
.chip-popover {
  position: fixed;
  transform: translateX(-50%);
  background: #090d16;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 8px 12px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.05);
  z-index: 999999;
  pointer-events: none;
  animation: popoverFadeIn 0.1s ease-out;
  min-width: 140px;
}

.popover-title {
  font-size: 13px;
  font-weight: 900;
  color: #38bdf8;
  margin-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 4px;
}

.popover-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  padding: 2px 0;
}

.row-label {
  color: #94a3b8;
  font-weight: 600;
}

.row-val {
  font-weight: 800;
  color: #f8fafc;
}

@keyframes popoverFadeIn {
  from { opacity: 0; transform: translate(-50%, -4px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}
</style>
