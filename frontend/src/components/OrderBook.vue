<template>
  <div class="orderbook-panel glass-panel">
    <!-- Imbalance & Spoofing Top Row -->
    <div class="intel-top-bar mono">
      <div class="spoofing-col">
        <span class="spoofing-text" :class="{ 'opacity-0': !spoofingMsg }">
          ⚠️ {{ spoofingMsg || 'SPOOFING PLACEHOLDER' }}
        </span>
      </div>
      <div class="delta-col">
        <span class="delta-val" :class="deltaImbalance > 0 ? 'text-green' : (deltaImbalance < 0 ? 'text-red' : 'text-muted')">
          {{ deltaImbalance > 0 ? '+' : (deltaImbalance < 0 ? '-' : '') }}{{ Math.abs(deltaImbalance).toLocaleString(undefined, { maximumFractionDigits: 0 }) }}
        </span>
      </div>
    </div>

    <!-- Dual Columns (Bids Left, Asks Right) - No Level 2 Title, 100 Rows Max -->
    <div class="book-container mono">
      <!-- BIDS TABLE -->
      <div class="book-half bids-half">

        <div class="table-body">
          <div 
            v-for="(row, idx) in store.displayedBids" 
            :key="'bid-' + row.price + '-' + idx"
            class="book-row bid-row"
            :class="{ 'big-wall': row.size >= 10000 }"
          >
            <!-- Inline Cumulative Depth Fill Bar (Right aligned) -->
            <div 
              class="depth-bar bid-depth-bar" 
              :style="{ width: `${row.percent}%` }"
            ></div>

            <div class="row-content bid-row-content">
              <span 
                class="col-size" 
                :class="[
                  (row.size >= 10000 ? 'text-gold' : '')
                ]"
              >
                {{ formatNum(row.size) }}
              </span>
              <span class="col-price text-green font-bold">{{ row.price.toFixed(2) }}</span>
            </div>
          </div>

          <div v-if="store.displayedBids.length === 0" class="empty-state">
            Waiting for Bid data...
          </div>
        </div>
      </div>

      <!-- ASKS TABLE -->
      <div class="book-half asks-half">

        <div class="table-body">
          <div 
            v-for="(row, idx) in store.displayedAsks" 
            :key="'ask-' + row.price + '-' + idx"
            class="book-row ask-row"
            :class="{ 'big-wall': row.size >= 10000 }"
          >
            <!-- Inline Cumulative Depth Fill Bar (Left aligned) -->
            <div 
              class="depth-bar ask-depth-bar" 
              :style="{ width: `${row.percent}%` }"
            ></div>

            <div class="row-content ask-row-content">
              <span class="col-price text-red font-bold">{{ row.price.toFixed(2) }}</span>
              <span 
                class="col-size" 
                :class="[
                  (row.size >= 10000 ? 'text-gold' : '')
                ]"
              >
                {{ formatNum(row.size) }}
              </span>
            </div>
          </div>

          <div v-if="store.displayedAsks.length === 0" class="empty-state">
            Waiting for Ask data...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();

const spoofingMsg = ref('');
let spoofingTimeout = null;
let prevBids = [];
let prevAsks = [];

const deltaImbalance = computed(() => {
  let bidVal = 0;
  for (const b of store.displayedBids) {
    bidVal += (b.size * b.price);
  }
  let askVal = 0;
  for (const a of store.displayedAsks) {
    askVal += (a.size * a.price);
  }
  return bidVal - askVal;
});

function detectSpoofing(oldBook, newBook, side) {
  if (!oldBook || oldBook.length === 0) return;
  
  for (const oldLevel of oldBook) {
    if (oldLevel.size >= 10000) {
      const newLevel = newBook.find(l => l.price === oldLevel.price);
      const newSize = newLevel ? newLevel.size : 0;
      
      if (oldLevel.size - newSize >= 9000) {
        spoofingMsg.value = `${side} WALL PULLED AT $${oldLevel.price.toFixed(2)}`;
        if (spoofingTimeout) clearTimeout(spoofingTimeout);
        spoofingTimeout = setTimeout(() => {
          spoofingMsg.value = '';
        }, 4000);
      }
    }
  }
}

watch(() => store.displayedBids, (newBids) => {
  detectSpoofing(prevBids, newBids, 'BUY');
  prevBids = newBids.map(b => ({ price: b.price, size: b.size }));
}, { deep: true });

watch(() => store.displayedAsks, (newAsks) => {
  detectSpoofing(prevAsks, newAsks, 'SELL');
  prevAsks = newAsks.map(a => ({ price: a.price, size: a.size }));
}, { deep: true });

function formatLots(num) {
  const lotSize = 100;
  if (num < lotSize) return '0';
  const lots = Math.floor(num / lotSize);
  return lots.toLocaleString();
}

function formatNum(num) {
  if (num === undefined || num === null || isNaN(num)) return '0';
  return formatLots(num);
}

function formatSizeK(size) {
  if (!size) return '';
  if (size >= 1000) {
    const kVal = (size / 1000).toFixed(1);
    return kVal.endsWith('.0') ? kVal.replace('.0', '') + 'k' : kVal + 'k';
  }
  return size.toString();
}

</script>

<style scoped>
.orderbook-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  border-radius: 8px;
  background: rgba(13, 17, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: border 0.2s ease, box-shadow 0.2s ease;
}

.intel-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: linear-gradient(180deg, #161f30 0%, #0c121e 100%);
  border-bottom: 2px solid #38bdf8;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.spoofing-col {
  display: flex;
  align-items: center;
  height: 100%;
}

.spoofing-text {
  font-size: 11px;
  font-weight: 800;
  color: #facc15;
  text-transform: uppercase;
}

.delta-col {
  display: flex;
  align-items: center;
  gap: 6px;
}

.delta-label {
  font-size: 11px;
  font-weight: 800;
  color: var(--text-muted);
}

.delta-val {
  font-size: 14px;
  font-weight: 800;
}

.opacity-0 {
  opacity: 0;
}

.border-squeeze {
  border: 1px solid #00ff88 !important;
  box-shadow: 0 0 15px rgba(0, 255, 136, 0.2);
}

.border-flush {
  border: 1px solid #ff3b56 !important;
  box-shadow: 0 0 15px rgba(255, 59, 86, 0.2);
}

.border-spoof {
  border: 1px solid #facc15 !important;
  box-shadow: 0 0 15px rgba(250, 204, 21, 0.2);
}

.spoofing-msg-area {
  font-size: 0.75rem;
  font-weight: 800;
  color: #facc15;
  display: flex;
  align-items: center;
  justify-content: center;
  text-transform: uppercase;
  padding: 6px;
  border-bottom: 1px solid rgba(250, 204, 21, 0.2);
}

.book-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  height: 100%;
}

.book-half {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.bids-half {
  border-right: 1px solid var(--border-color);
}



.table-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.book-row {
  position: relative;
  height: 32px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.025);
  transition: background-color 0.15s ease;
}

.book-row:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.big-wall {
  border-left: 3px solid var(--gold-block);
}

.depth-bar {
  position: absolute;
  top: 1px;
  bottom: 1px;
  pointer-events: none;
  transition: width 0.15s ease;
}

.bid-depth-bar {
  left: 0;
  background: var(--green-bid-bar);
  border-right: 2px solid rgba(0, 208, 132, 0.45);
}

.ask-depth-bar {
  right: 0;
  background: var(--red-ask-bar);
  border-left: 2px solid rgba(255, 59, 86, 0.45);
}

.row-content {
  position: relative;
  z-index: 2;
  display: flex;
  width: 100%;
  padding: 0 16px;
  align-items: center;
}

.bid-row-content {
  justify-content: space-between;
}

.ask-row-content {
  justify-content: space-between;
}

.col-size {
  font-size: 15px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 5px;
}

.col-price {
  font-size: 15.5px;
  font-weight: 800;
}

.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.text-gold { color: var(--gold-block); font-weight: 800; }
.text-yellow-glow {
  color: #facc15 !important;
  text-shadow: 0 0 10px rgba(250, 204, 21, 0.5);
  font-weight: 800;
}
.text-muted { color: var(--text-muted); }
.font-bold { font-weight: 700; }

.wall-floor-chip {
  display: inline-block;
  font-size: 9px;
  font-weight: 900;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.4px;
}

.floor-chip {
  background: rgba(250, 204, 21, 0.22);
  color: #facc15;
  border: 1px solid rgba(250, 204, 21, 0.5);
}

.wall-chip {
  background: rgba(250, 204, 21, 0.22);
  color: #facc15;
  border: 1px solid rgba(250, 204, 21, 0.5);
}

.row-floor-highlight {
  background: rgba(250, 204, 21, 0.1) !important;
  border-left: 3px solid #facc15 !important;
}

.row-wall-highlight {
  background: rgba(250, 204, 21, 0.1) !important;
  border-right: 3px solid #facc15 !important;
}

.empty-state {
  padding: 30px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}
</style>
