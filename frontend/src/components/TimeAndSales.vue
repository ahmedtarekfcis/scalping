<template>
  <div 
    class="tape-panel glass-panel"
    @mouseenter="setPause(true)"
    @mouseleave="setPause(false)"
  >


    <!-- Tape Table Header (Level 1 Quote) -->
    <div class="tape-table-header l1-header mono">
      <div v-if="isPaused" class="pause-overlay">
        <span>PAUSED</span>
        
        <div class="filter-icon-wrap" @click="showSizeFilter = !showSizeFilter" title="Filter trades by minimum size">
          <svg class="filter-icon" viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
          </svg>
          <div v-if="showSizeFilter" class="filter-popover" @click.stop>
            <span class="filter-ge">&ge;</span>
            <input 
              type="number" 
              v-model.number="store.tapeMinSize" 
              placeholder="0" 
              min="0" 
              step="100"
              class="th-size-input"
            />
          </div>
        </div>
      </div>
      
      <div class="l1-bid">
        {{ bestBid ? bestBid.price.toFixed(2) : '--.--' }}
      </div>
      <div class="l1-spread">
        {{ Math.round(store.spread * 100) }}
      </div>
      <div class="l1-ask">
        {{ bestAsk ? bestAsk.price.toFixed(2) : '--.--' }}
      </div>
    </div>

    <!-- Tape Scrolling Stream -->
    <div 
      class="tape-list mono" 
      ref="tapeContainer"
    >
      <div class="tape-stream">
        <div 
          v-for="tick in displayedTape" 
          :key="tick.id"
          class="tape-item"
          :class="[
            tick.side === 'BUY' ? 'row-buy' : (tick.side === 'SELL' ? 'row-sell' : 'row-mid'),
            tick.hasBorder ? (tick.side === 'BUY' ? 'row-block-buy' : (tick.side === 'SELL' ? 'row-block-sell' : 'row-block-mid')) : ''
          ]"
        >
          <!-- Aggregated Size & Multiplier Badge with Gold Thunder Box -->
          <span 
            class="col-size font-bold"
            :class="[
              tick.side === 'BUY' ? 'text-green' : (tick.side === 'SELL' ? 'text-red' : 'text-mid')
            ]"
          >
            <!-- Thunder Badge: Dynamic size >= median * 6 -->
            <span class="thunder-container">
              <span v-if="tick.hasIcon" class="block-badge" title="Whale Block">⚡</span>
            </span>
            
            <span class="size-val-container" :class="getSizeClasses(tick.size)">
              {{ formatNum(tick.size) }}
            </span>
          </span>
          
          <!-- Price: Always white -->
          <span class="col-price font-bold text-white">
            {{ tick.price.toFixed(2) }}
          </span>
        </div>
      </div>

      <div v-if="filteredTape.length === 0" class="empty-state">
        Listening to tape prints (Min: {{ store.tapeMinSize || 0 }} shares)...
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();

const bestBid = computed(() => store.bestBid);
const bestAsk = computed(() => store.bestAsk);
const lastTrade = computed(() => store.lastTrade);

const filteredTape = computed(() => {
  const minThreshold = (store.tapeMinSize !== undefined && store.tapeMinSize !== null && store.tapeMinSize !== '')
    ? Math.max(0, Number(store.tapeMinSize))
    : 0;
  return (store.tape || []).filter(t => t.size >= minThreshold);
});

const isPaused = ref(false);
const showSizeFilter = ref(false);
const pausedTape = ref([]);

const setPause = (val) => {
  if (val) {
    pausedTape.value = [...filteredTape.value];
    isPaused.value = true;
  } else {
    isPaused.value = false;
    pausedTape.value = [];
  }
};

const displayedTape = computed(() => {
  return isPaused.value ? pausedTape.value : filteredTape.value;
});

const lastTradePriceClass = computed(() => {
  if (!lastTrade.value) return 'text-primary';
  if (lastTrade.value.side === 'BUY') return 'text-green';
  if (lastTrade.value.side === 'SELL') return 'text-red';
  return 'text-mid';
});

const lastTradeSideClass = computed(() => {
  if (!lastTrade.value) return '';
  if (lastTrade.value.size >= 2000 || lastTrade.value.isBlockTrade) return 'last-pod-block';
  if (lastTrade.value.side === 'BUY') return 'last-pod-buy';
  if (lastTrade.value.side === 'SELL') return 'last-pod-sell';
  return 'last-pod-mid';
});

// Format time as MM:SS (minutes and seconds only)
function formatTime(timeStr) {
  if (!timeStr) return '--:--';
  const parts = String(timeStr).split(':');
  if (parts.length >= 3) {
    const min = parts[1];
    const sec = parts[2].split('.')[0];
    return `${min}:${sec}`;
  } else if (parts.length === 2) {
    return `${parts[0]}:${parts[1].split('.')[0]}`;
  }
  return timeStr;
}

function formatLots(num) {
  if (!num || isNaN(num)) return '0';
  const lots = Math.round(num / 100);
  return (lots === 0 && num > 0 ? 1 : lots).toLocaleString();
}

// Format numbers
function formatNum(num) {
  if (num === undefined || num === null || isNaN(num)) return '0';
  return formatLots(num);
}

function getSizeClasses(size) {
  if (size === undefined || size === null || isNaN(size)) return 'size-1-digit';
  if (size >= 10000) return 'size-3-digit'; // 5+ digits
  if (size >= 1000) return 'size-2-digit';  // 4 digits
  return 'size-1-digit';
}
</script>

<style scoped>
.tape-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background: #0d0d0d;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  height: 48px;
  box-sizing: border-box;
  border-bottom: 1px solid var(--border-color);
  background: rgba(13, 17, 23, 0.95);
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title h3 {
  font-size: 13.5px;
  font-weight: 800;
  letter-spacing: 0.5px;
  margin: 0;
}

.tick-counter {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 7px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.live-blink {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green-bid);
  animation: blink 1s infinite alternate;
}

@keyframes blink {
  0% { opacity: 0.3; }
  100% { opacity: 1; box-shadow: 0 0 8px var(--green-bid); }
}

.col-size-th {
  display: flex !important;
  align-items: center;
  justify-content: space-between !important; /* Move icon to the right */
  gap: 6px;
  width: 100%;
}

.size-title-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
}

.lot-indicator {
  font-size: 9px;
  color: var(--text-muted);
  opacity: 0.7;
}

.active-filter-badge {
  font-size: 9px;
  font-weight: 900;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.15);
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.col-price-th {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  padding-right: 8px;
}

.filter-icon-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px; /* Smaller padding */
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.15);
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-icon-wrap:hover {
  background: rgba(0, 0, 0, 0.7);
  border-color: #38bdf8;
}

.filter-icon {
  color: var(--text-muted);
}

.filter-icon-wrap:hover .filter-icon {
  color: #38bdf8;
}

.filter-popover {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 5px;
  background: #0c121e;
  border: 1px solid #38bdf8;
  border-radius: 4px;
  padding: 5px 8px;
  display: flex;
  align-items: center;
  gap: 5px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.7);
  z-index: 50;
  cursor: default;
}

.filter-ge {
  color: #38bdf8;
  font-size: 11px;
  font-weight: 900;
}

.th-size-input {
  background: transparent;
  color: #ffffff;
  border: none;
  padding: 0;
  width: 50px;
  height: 18px;
  outline: none;
  font-family: inherit;
  font-size: 12px;
  font-weight: 800;
  text-align: center;
}

/* ======================================================== */
/* IBKR-STYLE FROZEN PINNED TOP ROW (NBBO & LAST TRADE)      */
/* ======================================================== */
.pinned-current-bar {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 8px;
  padding: 4px 8px;
  box-sizing: border-box;
  background: linear-gradient(180deg, #161f30 0%, #0c121e 100%);
  border-bottom: 2px solid #38bdf8;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  z-index: 10;
  flex-shrink: 0;
}

.bid-pod, .ask-pod {
  width: 25%;
}

.last-pod {
  width: 48%;
}

.pinned-pod {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 5px 8px;
  border-radius: 5px;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.last-pod-row {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
  width: 100%;
  font-variant-numeric: tabular-nums;
}

.last-pod-row .pod-val {
  font-size: 14px;
}

.last-pod-row .pod-size {
  font-size: 12px;
}

.opacity-0 {
  opacity: 0;
}

.last-price-col {
  width: 45px;
  text-align: center;
}

.spread-col {
  width: 30px;
  text-align: center;
}

.size-col {
  width: 38px;
  text-align: center;
}

.agg-col {
  width: 36px;
  text-align: center;
}

.pod-label {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.6px;
  color: var(--text-muted);
}

.bid-pod .pod-label {
  color: #00d084;
}

.ask-pod .pod-label {
  color: #ff3b56;
}

.pod-val {
  font-size: 17px;
  font-weight: 800;
  line-height: 1.2;
}

.pod-size {
  font-size: 12px;
  font-weight: 700;
}

.last-pod {
  border-color: rgba(56, 189, 248, 0.35);
  background: rgba(15, 23, 42, 0.75);
}

.last-pod-buy {
  border-color: rgba(0, 208, 132, 0.5);
  background: rgba(0, 208, 132, 0.08);
}

.last-pod-sell {
  border-color: rgba(255, 59, 86, 0.5);
  background: rgba(255, 59, 86, 0.08);
}

.last-pod-block {
  border-color: #facc15;
  background: rgba(250, 204, 21, 0.18);
}


.spread-chip {
  font-size: 14px;
  color: #facc15;
  font-weight: 800;
}

.block-mini-badge {
  color: #facc15;
  margin-right: 2px;
}

.agg-chip {
  font-size: 12px;
  color: #38bdf8;
  font-weight: 800;
}



/* ======================================================== */
/* TAPE TABLE HEADER & STREAMING LIST                       */
/* ======================================================== */
.tape-table-header {
  position: relative;
  display: flex;
  padding: 0;
  height: 36px;
  box-sizing: border-box;
  font-size: 10px;
  font-weight: 800;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(10, 14, 22, 0.75);
  letter-spacing: 0.5px;
  flex-shrink: 0;
  align-items: center;
}

.l1-bid, .l1-ask, .l1-spread {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.l1-bid {
  flex: 1;
  background: rgba(0, 208, 132, 0.15);
  color: #00d084;
  font-size: 15px;
  font-weight: 800;
}

.l1-ask {
  flex: 1;
  background: rgba(255, 59, 86, 0.15);
  color: #ff3b56;
  font-size: 15px;
  font-weight: 800;
}

.l1-spread {
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #facc15;
  font-size: 13px;
  font-weight: 900;
}

.tape-list {
  flex: 1;
  overflow-y: auto;
  position: relative;
  scrollbar-gutter: stable;
  background: #0d0d0d;
}

.tape-list::-webkit-scrollbar {
  width: 4px;
}
.tape-list::-webkit-scrollbar-track {
  background: #0d0d0d;
}
.tape-list::-webkit-scrollbar-thumb {
  background: #2a2b2f;
  border-radius: 2px;
}
.tape-list::-webkit-scrollbar-thumb:hover {
  background: #38bdf8;
}

.tape-stream {
  display: flex;
  flex-direction: column;
}

.tape-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 72px;
  align-items: stretch;
  padding: 0;
  height: 32px;
  box-sizing: border-box;
  border-left: 4px solid transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  transition: background-color 0.15s ease;
  position: relative;
  overflow: hidden;
}

.tape-item:hover {
  background: transparent;
}

/* Column Alignments */
.col-time {
  font-size: 11.5px;
}

.col-size {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  overflow: hidden;
  height: 100%;
  padding-left: 6px;
  padding-right: 10px;
  gap: 8px;
  font-size: 14.5px;
  font-weight: 800;
}

.col-price {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-width: 0;
  overflow: hidden;
  padding-left: 8px;
  padding-right: 6px;
  height: 100%;
  border-left: 1px solid #202020;
  font-size: 15.5px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: #ffffff;
}

.thunder-container {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  min-width: 18px;
  max-width: 18px;
  height: 100%;
  flex-shrink: 0;
}

.size-val-container {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.col-side {
  text-align: center;
}

/* Side Badges */
.side-tag {
  display: inline-block;
  font-size: 10.5px;
  font-weight: 800;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.4px;
}

.side-ask {
  background: rgba(0, 208, 132, 0.16);
  color: var(--green-bid);
  border: 1px solid rgba(0, 208, 132, 0.35);
}

.side-bid {
  background: rgba(255, 59, 86, 0.16);
  color: var(--red-ask);
  border: 1px solid rgba(255, 59, 86, 0.35);
}

.side-mid {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.side-tag-block {
  background: #facc15;
  color: #0f172a;
  border: 1px solid #eab308;
  font-weight: 900;
}

/* Aggregated Order Count Multiplier Badge */
.agg-count-tag {
  font-size: 10.5px;
  font-weight: 800;
  background: rgba(56, 189, 248, 0.22);
  color: #38bdf8;
  padding: 0 4px;
  border-radius: 4px;
  border: 1px solid rgba(56, 189, 248, 0.35);
  display: inline-block;
  min-width: 22px;
  text-align: center;
}

/* Color Coding */
.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.text-mid { color: #f8fafc; } /* Crisp White */
.text-gold { color: #facc15; }
.text-muted { color: var(--text-muted); }
.text-primary { color: var(--text-primary); }
.font-bold { font-weight: 700; }

.size-3-digit {
  opacity: 1;
  animation: size-pulse-anim 1.5s infinite;
}

.size-2-digit {
  opacity: 1;
}

.size-1-digit {
  opacity: 0.45;
}

@keyframes size-pulse-anim {
  0% { text-shadow: 0 0 2px rgba(255, 255, 255, 0); }
  50% { text-shadow: 0 0 8px currentColor, 0 0 14px currentColor; }
  100% { text-shadow: 0 0 2px rgba(255, 255, 255, 0); }
}

.row-buy {
  background: transparent;
}
.row-sell {
  background: transparent;
}
.row-mid {
  background: transparent;
}

/* ======================================================== */
/* BLOCK TRADE HIGHLIGHTING (>= 2000 SHARES)                */
/* ======================================================== */
.row-block-buy {
  background: transparent !important;
  border-left: 4px solid #00d084 !important;
}

.row-block-buy:hover {
  background: rgba(0, 208, 132, 0.22) !important;
}

.row-block-sell {
  background: transparent !important;
  border-left: 4px solid #ff3b56 !important;
}

.row-block-sell:hover {
  background: rgba(255, 59, 86, 0.22) !important;
}

.row-block-mid {
  background: transparent !important;
  border-left: 4px solid #f8fafc !important;
}

/* Distinctive Gold Box Badge for Thunder ⚡ Icon */
.block-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  line-height: 1;
  color: #facc15;
  background: transparent;
  border: none;
  margin: 0;
  text-shadow: 0 0 6px rgba(250, 204, 21, 0.6);
  animation: pulse-block 1.5s infinite;
}

@keyframes pulse-block {
  0% { transform: scale(0.95); text-shadow: 0 0 4px rgba(250, 204, 21, 0.4); }
  50% { transform: scale(1.15); text-shadow: 0 0 12px rgba(250, 204, 21, 0.8); }
  100% { transform: scale(0.95); text-shadow: 0 0 4px rgba(250, 204, 21, 0.4); }
}

/* Animations removed for maximum visibility */

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}

.waiting-only-text {
  text-align: center;
  font-size: 13px;
  font-weight: 800;
  color: #fbbf24;
  text-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pause-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1px;
  text-align: center;
  z-index: 10;
  pointer-events: auto;
  backdrop-filter: blur(2px);
  border-bottom: 1px solid rgba(245, 158, 11, 0.4);
  gap: 12px;
}
</style>
