<script setup>
import { computed } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();

const levelOptions = [5, 10, 15, 20];

function formatSize(val) {
  if (!val) return '0';
  return Number(val).toLocaleString();
}
</script>

<template>
  <div class="level2-container glass-panel">
    <!-- Header with Book Controls & Volume Pressure Bar -->
    <div class="l2-header">
      <div class="l2-title-area">
        <div class="title-with-pulse">
          <span class="live-dot"></span>
          <span class="l2-title">LEVEL 2 MARKET DEPTH</span>
        </div>
        <span class="l2-subtitle">TOTAL DEPTH (BID vs ASK)</span>
      </div>

      <!-- Controls for levels -->
      <div class="l2-controls">
        <div class="level-selector">
          <button 
            v-for="lvl in levelOptions" 
            :key="lvl"
            :class="['lvl-btn', { active: store.visibleLevels === lvl }]"
            @click="store.visibleLevels = lvl"
          >
            {{ lvl }}L
          </button>
        </div>
      </div>
    </div>

    <!-- Webull-style Volume Pressure Ratio Bar -->
    <div class="pressure-gauge-container">
      <div class="pressure-labels mono">
        <div class="gauge-side-info color-green">
          <span class="gauge-label">BIDS (BUY)</span>
          <span class="gauge-num">{{ formatSize(store.bidTotalVolume) }} ({{ store.bidRatio }}%)</span>
        </div>
        <div class="spread-indicator">
          <span>SPREAD: ${{ store.spread.toFixed(2) }}</span>
        </div>
        <div class="gauge-side-info color-red">
          <span class="gauge-num">{{ store.askRatio }}% ({{ formatSize(store.askTotalVolume) }})</span>
          <span class="gauge-label">ASKS (SELL)</span>
        </div>
      </div>

      <div class="pressure-bar">
        <div class="bar-bid" :style="{ width: `${store.bidRatio}%` }"></div>
        <div class="bar-ask" :style="{ width: `${store.askRatio}%` }"></div>
      </div>
    </div>

    <!-- Split Dual Table (Bids Left, Asks Right) -->
    <div class="books-wrapper">
      <!-- BIDS TABLE -->
      <div class="book-side bids-side">
        <div class="table-head mono">
          <span class="th-size">SIZE</span>
          <span class="th-price">BID</span>
        </div>

        <div class="table-body">
          <div 
            v-for="(bid, index) in store.displayedBids" 
            :key="`bid-${index}-${bid.price}`"
            class="depth-row bid-row mono"
            :class="{ 'row-floor-highlight': bid.isFloor }"
          >
            <div 
              class="depth-bar-fill bid-fill" 
              :style="{ width: `${bid.percent}%` }"
            ></div>

            <span class="td-size font-bold" :class="bid.isFloor ? 'text-yellow' : 'text-primary'">
              <span v-if="bid.isFloor" class="wall-badge">FLOOR</span>
              {{ formatSize(bid.size) }}
            </span>
            <span class="td-price color-green font-bold">${{ bid.price.toFixed(2) }}</span>
          </div>

          <div v-if="store.displayedBids.length === 0" class="empty-state">
            Waiting for Bid Depth...
          </div>
        </div>
      </div>

      <!-- ASKS TABLE -->
      <div class="book-side asks-side">
        <div class="table-head mono">
          <span class="th-price">ASK</span>
          <span class="th-size">SIZE</span>
        </div>

        <div class="table-body">
          <div 
            v-for="(ask, index) in store.displayedAsks" 
            :key="`ask-${index}-${ask.price}`"
            class="depth-row ask-row mono"
            :class="{ 'row-wall-highlight': ask.isWall }"
          >
            <!-- Webull Depth Fill Bar (Fills from Left to Right for Asks) -->
            <div 
              class="depth-bar-fill ask-fill" 
              :style="{ width: `${ask.percent}%` }"
            ></div>

            <span class="td-price color-red font-bold">${{ ask.price.toFixed(2) }}</span>
            <span class="td-size font-bold" :class="ask.isWall ? 'text-yellow' : 'text-primary'">
              <span v-if="ask.isWall" class="wall-badge">WALL</span>
              {{ formatSize(ask.size) }}
            </span>
          </div>

          <div v-if="store.displayedAsks.length === 0" class="empty-state">
            Waiting for Ask Depth...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.level2-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 14px;
  overflow: hidden;
}

.l2-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.l2-title-area {
  display: flex;
  flex-direction: column;
}

.title-with-pulse {
  display: flex;
  align-items: center;
  gap: 8px;
}

.live-dot {
  width: 7px;
  height: 7px;
  background: var(--green-bid);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--green-bid);
  animation: pulse-dot 1.5s infinite;
}

@keyframes pulse-dot {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.l2-title {
  font-size: 0.85rem;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: var(--text-primary);
}

.l2-subtitle {
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 1px;
}

.l2-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.level-selector {
  display: flex;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 2px;
}

.lvl-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.lvl-btn.active {
  background: var(--accent-blue);
  color: white;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.toggle-label input {
  accent-color: var(--accent-blue);
}

/* Volume Pressure Ratio Gauge */
.pressure-gauge-container {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
}

.pressure-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.72rem;
  font-weight: 600;
  margin-bottom: 6px;
}

.gauge-side-info {
  display: flex;
  align-items: center;
  gap: 6px;
}

.gauge-label {
  font-size: 0.65rem;
  opacity: 0.8;
}

.spread-indicator {
  font-size: 0.68rem;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: 4px;
}

.pressure-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: var(--bg-tertiary);
}

.bar-bid {
  background: linear-gradient(90deg, #00b870, var(--green-bid));
  transition: width 0.2s ease;
}

.bar-ask {
  background: linear-gradient(90deg, var(--red-ask), #e11d48);
  transition: width 0.2s ease;
}

/* Books Wrapper */
.books-wrapper {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  flex: 1;
  overflow: hidden;
}

.book-side {
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.table-head {
  display: grid;
  padding: 6px 10px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}

.bids-side .table-head {
  grid-template-columns: 1fr 1fr 1.2fr;
  text-align: right;
}

.asks-side .table-head {
  grid-template-columns: 1.2fr 1fr 1fr;
  text-align: left;
}
.asks-side .table-head .th-size,
.asks-side .table-head .th-total {
  text-align: right;
}

.table-body {
  flex: 1;
  overflow-y: auto;
  position: relative;
}

.depth-row {
  display: grid;
  padding: 5px 10px;
  font-size: 0.76rem;
  align-items: center;
  position: relative;
  border-bottom: 1px solid rgba(255, 255, 255, 0.02);
  transition: background 0.1s;
}

.depth-row:hover {
  background: rgba(255, 255, 255, 0.05);
}

.bids-side .depth-row {
  grid-template-columns: 1fr 1fr 1.2fr;
  text-align: right;
}

.asks-side .depth-row {
  grid-template-columns: 1.2fr 1fr 1fr;
  text-align: left;
}
.asks-side .depth-row .td-size,
.asks-side .depth-row .td-total {
  text-align: right;
}

/* Webull Cumulative Volume Depth Bar within row */
.depth-bar-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 0;
  transition: width 0.18s ease-out;
}

.bid-fill {
  right: 0;
  background: var(--green-bid-bar);
  border-left: 2px solid rgba(0, 208, 132, 0.6);
}

.ask-fill {
  left: 0;
  background: var(--red-ask-bar);
  border-right: 2px solid rgba(255, 59, 86, 0.6);
}

.depth-row span {
  position: relative;
  z-index: 1;
}

.badge-mmid {
  font-size: 0.62rem;
  background: var(--bg-tertiary);
  padding: 1px 4px;
  border-radius: 3px;
  color: var(--accent-cyan);
  display: inline-block;
  width: fit-content;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-size: 0.8rem;
  padding: 40px 0;
}

.font-bold { font-weight: 700; }
.color-green { color: var(--green-bid); }
.color-red { color: var(--red-ask); }
.text-muted { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }
.text-primary { color: var(--text-primary); }
</style>
