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
</script>

<template>
  <div class="market-header glass-panel">
    


    <!-- Left & Center: Symbol Search + Scanner Chips -->
    <div class="symbol-and-chips">
      <div class="symbol-search-wrap">
        <input 
          v-model="inputSymbol" 
          @keyup.enter="handleSymbolSubmit"
          placeholder="SYMBOL..." 
          class="symbol-input mono"
        />
        <button class="btn-sync" @click="syncWebull" title="Sync to Webull">
          ⮂
        </button>
      </div>

      <div class="chips-container">
        <button 
          v-for="item in activeMomentumScans" 
          :key="item.symbol"
          class="scan-chip mono"
          :class="{ 'chip-up': item.trend === 'up', 'chip-down': item.trend === 'down' }"
          @click="store.changeSymbol(item.symbol)"
          :title="item.reason"
        >
          {{ item.symbol }} 
          <div style="display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; background: rgba(250, 204, 21, 0.2); border: 1px solid rgba(250, 204, 21, 0.5); border-radius: 4px; color: #facc15; font-size: 11px; margin-left: 6px;">
            {{ item.score }}
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
}

.symbol-input {
  background: transparent;
  border: none;
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 800;
  width: 110px;
  outline: none;
  text-transform: uppercase;
  text-align: center;
}

.btn-sync {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 0 10px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
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
</style>
