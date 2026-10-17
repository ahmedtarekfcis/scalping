<template>
  <div class="orderbook-panel glass-panel">
    <!-- Scorecard Bar (1:1.50 Ratio Layout) -->
    <div class="intel-top-bar mono" @mouseenter="showScoreDetails = true" @mouseleave="showScoreDetails = false">

      <!-- Left Side (Bid Dominance & Score) -->
      <div class="sc-side-area sc-left-area">
        <span class="sc-ratio-label text-green" title="Bid Depth Dominance">
          {{ store.bidRatio }}%
        </span>
        <span class="sc-score-val" :class="scoreClass">
          {{ store.scorecard.total > 0 ? '+' : '' }}{{ store.scorecard.total }}
        </span>
      </div>

      <!-- Center Bar (1.5x width of total side areas) -->
      <div class="sc-single-wrap sc-center-bar">
        <div class="sc-track">
          <!-- Center divider -->
          <div class="sc-center-mark"></div>
          <!-- The fill -->
          <div
            class="sc-fill-single"
            :class="store.scorecard.total >= 0 ? 'sc-fill-bull' : 'sc-fill-bear'"
            :style="fillStyle"
          ></div>
        </div>
      </div>

      <!-- Right Side (Ask Dominance) -->
      <div class="sc-side-area sc-right-area">
        <span class="sc-ratio-label text-red" title="Ask Depth Dominance">
          {{ store.askRatio }}%
        </span>
      </div>

    <!-- Right: signal breakdown tooltip -->
      <Teleport to="body">
        <div v-if="showScoreDetails && store.scorecard.signals.length" class="sc-tooltip mono">
          <div class="sc-tooltip-title">
            SCORECARD — {{ store.symbol }}
            <span :class="scoreClass"> {{ store.scorecard.total > 0 ? '+' : '' }}{{ store.scorecard.total }}</span>
          </div>
          <div class="sc-tooltip-row" v-for="(sig, i) in store.scorecard.signals" :key="i">
            <span class="sc-row-bar" :class="'sc-row-' + sig.type" :style="{ width: Math.abs(sig.score) * 0.8 + 'px' }"></span>
            <span class="sc-row-score" :class="sig.score > 0 ? 'text-green' : (sig.score < 0 ? 'text-red' : 'text-muted')">
              {{ sig.score > 0 ? '+' : '' }}{{ sig.score }}
            </span>
            <span class="sc-row-label">{{ sig.label }}</span>
          </div>
          <div class="sc-tooltip-legend">
            <span class="legend-item"><span class="dot dot-green"></span> L2: {{ store.scorecard.l2Imbalance > 0 ? '+' : '' }}{{ store.scorecard.l2Imbalance }}</span>
            <span class="legend-item"><span class="dot dot-teal"></span> 15s vol: {{ store.scorecard.tapeDelta15s > 0 ? '+' : '' }}{{ store.scorecard.tapeDelta15s }}</span>
            <span class="legend-item"><span class="dot dot-blue"></span> 15s cnt: {{ store.scorecard.tapePressure15s > 0 ? '+' : '' }}{{ store.scorecard.tapePressure15s }}</span>
            <span class="legend-item"><span class="dot dot-gold"></span> ★: {{ store.scorecard.whaleAbsorption > 0 ? '+' : '' }}{{ store.scorecard.whaleAbsorption }}</span>
            <span class="legend-item"><span class="dot dot-gray"></span> DP: {{ store.scorecard.darkPool > 0 ? '+' : '' }}{{ store.scorecard.darkPool }}</span>
          </div>
        </div>
      </Teleport>
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
            :class="[
              idx < 9 ? `row-tier-${idx}` : 'row-tier-default',
              row.hasBorder ? 'row-floor-highlight' : ''
            ]"
          >
            <!-- Inline Cumulative Depth Fill Bar Container -->
            <div class="depth-bar-container bid-depth-container">
              <div 
                class="depth-bar bid-depth-bar" 
                :style="{ width: `${row.percent}%` }"
              ></div>
            </div>

            <div class="row-content bid-row-content">
              <span class="col-size bid-size">
                <span class="size-val">{{ formatNum(row.size) }}</span>
                <span v-if="row.hasIcon" class="block-badge block-badge-bid" title="Whale Block">⚡</span>
              </span>
              <div class="col-price-box">
                {{ formatPrice(row.price) }}
              </div>
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
            :class="[
              idx < 9 ? `row-tier-${idx}` : 'row-tier-default',
              row.hasBorder ? 'row-wall-highlight' : ''
            ]"
          >
            <!-- Inline Cumulative Depth Fill Bar Container -->
            <div class="depth-bar-container ask-depth-container">
              <div 
                class="depth-bar ask-depth-bar" 
                :style="{ width: `${row.percent}%` }"
              ></div>
            </div>

            <div class="row-content ask-row-content">
              <div class="col-price-box">
                {{ formatPrice(row.price) }}
              </div>
              <span class="col-size ask-size">
                <span v-if="row.hasIcon" class="block-badge block-badge-ask" title="Whale Block">⚡</span>
                <span class="size-val">{{ formatNum(row.size) }}</span>
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

const showScoreDetails = ref(false);

// ── Score bar ─────────────────────────────────────────────────────────────
// Matches L2 layout: LEFT = bids (buyers) = GREEN, RIGHT = asks (sellers) = RED
// Positive score (buyers winning) → bar grows LEFT from center (green)
// Negative score (sellers winning) → bar grows RIGHT from center (red)
const fillStyle = computed(() => {
  const total = store.scorecard.total;
  const pct = Math.abs(total) / 2;   // 0..50% of track width
  if (total >= 0) return { right: '50%', width: pct + '%' };  // extends left  (green)
  return { left: '50%', width: pct + '%' };                   // extends right (red)
});


const scoreClass = computed(() => {
  const t = store.scorecard.total;
  if (t >= 40)  return 'score-strong-bull';
  if (t >= 15)  return 'score-bull';
  if (t <= -40) return 'score-strong-bear';
  if (t <= -15) return 'score-bear';
  return 'score-neutral';
});

const topSignal = computed(() => store.scorecard.signals[0] || null);
const topSignalType = computed(() => topSignal.value?.type || 'neutral');

// ── Near depth (top 5 levels from spread) ────────────────────────────────
// Using only the 5 levels closest to the spread gives a much more
// accurate read of immediate supply/demand than the full 100-row book.
const NEAR_LEVELS = 5;
const nearBidVol = computed(() =>
  store.displayedBids.slice(0, NEAR_LEVELS).reduce((a, b) => a + b.size, 0)
);
const nearAskVol = computed(() =>
  store.displayedAsks.slice(0, NEAR_LEVELS).reduce((a, b) => a + b.size, 0)
);
const nearTotal = computed(() => nearBidVol.value + nearAskVol.value);
const nearBidRatio = computed(() =>
  nearTotal.value > 0 ? Math.round((nearBidVol.value / nearTotal.value) * 100) : 50
);
const nearAskRatio = computed(() => 100 - nearBidRatio.value);

function formatLots(num) {
  if (!num || isNaN(num)) return '0';
  const lots = Math.round(num / 100);
  return (lots === 0 && num > 0 ? 1 : lots).toLocaleString();
}

// ── Spoofing detector (unchanged) ────────────────────────────────────────
const spoofingMsg = ref('');
let spoofingTimeout = null;
let prevBids = [];
let prevAsks = [];

const deltaImbalance = computed(() => {
  let bidVal = 0;
  for (const b of store.displayedBids) { bidVal += (b.size * b.price); }
  let askVal = 0;
  for (const a of store.displayedAsks) { askVal += (a.size * a.price); }
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



function formatPrice(price) {
  if (price === undefined || price === null || isNaN(price)) return '--';
  return Number(price).toFixed(2);
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
  border-radius: 6px;
  background: #0d0d0d;
  border: 1px solid #202020;
  transition: border 0.2s ease, box-shadow 0.2s ease;
}

.intel-top-bar {
  display: flex;
  align-items: center;
  padding: 0 6px;
  height: 28px;
  box-sizing: border-box;
  background: #111214;
  border-bottom: 1px solid #202020;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
  cursor: default;
}

.sc-side-area {
  flex: 1; /* 1 part */
  display: flex;
  align-items: center;
}

.sc-left-area {
  justify-content: space-between;
  padding-right: 12px;
}

.sc-right-area {
  justify-content: flex-end;
  padding-left: 12px;
}

.sc-ratio-label {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: -0.2px;
  text-shadow: 0 1px 3px rgba(0,0,0,0.9);
}

.sc-score-val {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: -0.5px;
  text-shadow: 0 1px 3px rgba(0,0,0,0.9);
  transition: color 0.3s;
}

.sc-center-bar {
  flex: 3; /* 3 parts (which is 1.5x of the combined 2 parts of left+right) */
}

/* Single centered bar */
.sc-single-wrap {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sc-track {
  position: relative;
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

/* Thin center divider line */
.sc-center-mark {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.25);
  z-index: 2;
  transform: translateX(-50%);
}

.sc-fill-single {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 4px;
  transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.sc-fill-bull {
  /* Buyers winning: bar extends LEFT — bright end at right (center), fades to dark left */
  background: linear-gradient(270deg, #00913f, #00d084, #4fffb0);
  box-shadow: 0 0 8px rgba(0, 208, 132, 0.5);
}

.sc-fill-bear {
  /* Sellers winning: bar extends RIGHT — bright end at left (center), fades to dark right */
  background: linear-gradient(90deg, #8b0000, #ff3b56, #ff7c8a);
  box-shadow: 0 0 8px rgba(255, 59, 86, 0.5);
}



.score-strong-bull { color: #00d084; text-shadow: 0 0 10px rgba(0,208,132,0.8), 0 1px 3px rgba(0,0,0,0.9); }
.score-bull        { color: #00d084; text-shadow: 0 1px 3px rgba(0,0,0,0.9); }
.score-strong-bear { color: #ff3b56; text-shadow: 0 0 10px rgba(255,59,86,0.8),  0 1px 3px rgba(0,0,0,0.9); }
.score-bear        { color: #ff3b56; text-shadow: 0 1px 3px rgba(0,0,0,0.9); }
.score-neutral     { color: #94a3b8; }

/* Scorecard tooltip */
.sc-tooltip {
  position: fixed;
  top: 44px;
  left: 50%;
  transform: translateX(-50%);
  background: #090d16;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 10px 14px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.85);
  z-index: 999999;
  min-width: 320px;
  max-width: 460px;
  animation: tooltipFadeIn 0.12s ease-out;
}
@keyframes tooltipFadeIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-4px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}
.sc-tooltip-title {
  font-size: 11px;
  font-weight: 900;
  color: #38bdf8;
  letter-spacing: 1px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 6px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
}
.sc-tooltip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
  font-size: 10px;
}
.sc-row-bar {
  height: 5px;
  border-radius: 3px;
  flex-shrink: 0;
  min-width: 4px;
}
.sc-row-bull    { background: #00d084; }
.sc-row-bear    { background: #ff3b56; }
.sc-row-partial { background: #facc15; }
.sc-row-warn    { background: #fb923c; }
.sc-row-score {
  font-size: 10px;
  font-weight: 900;
  min-width: 28px;
  text-align: right;
  flex-shrink: 0;
}
.sc-row-label {
  color: #cbd5e1;
  font-size: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sc-tooltip-legend {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid rgba(255,255,255,0.06);
  font-size: 9.5px;
  font-weight: 700;
  color: #94a3b8;
}
.legend-item { display: flex; align-items: center; gap: 4px; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-green  { background: #00d084; }
.dot-teal   { background: #2dd4bf; }
.dot-blue   { background: #38bdf8; }
.dot-gold   { background: #facc15; }
.dot-purple { background: #a78bfa; }

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
  background: #0d0d0d;
}

/* ============================================================ */
/* DEPTH METER (BID vs ASK volume above the book)              */
/* ============================================================ */
.depth-meter-wrap {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 5px 8px 4px 8px;
  background: rgba(8, 12, 20, 0.9);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.dm-row {
  display: flex;
  align-items: center;
  gap: 5px;
  height: 14px;
}

.dm-label {
  font-size: 8.5px;
  font-weight: 900;
  letter-spacing: 0.5px;
  width: 28px;
  flex-shrink: 0;
}
.dm-label-bid { color: #00d084; }

.dm-vol {
  font-size: 9.5px;
  font-weight: 800;
  width: 32px;
  text-align: right;
  flex-shrink: 0;
}

.dm-bar-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.05);
  display: flex;
  overflow: hidden;
  position: relative;
}

.dm-bar-fill {
  height: 100%;
  transition: width 0.25s ease;
}

.dm-fill-bid {
  background: linear-gradient(90deg, #007a4d, #00d084);
  border-radius: 3px 0 0 3px;
}

.dm-fill-ask {
  background: linear-gradient(90deg, #ff6b6b, #ff3b56);
  border-radius: 0 3px 3px 0;
}

.dm-pct {
  font-size: 9px;
  font-weight: 900;
  width: 34px;
  text-align: right;
  flex-shrink: 0;
}

.book-half {
  flex: 1;
  flex-basis: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.bids-half {
  border-right: 1px solid #202020;
}

.table-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  background: #0d0d0d;
}

.table-body::-webkit-scrollbar {
  width: 4px;
}
.table-body::-webkit-scrollbar-track {
  background: #0d0d0d;
}
.table-body::-webkit-scrollbar-thumb {
  background: #2a2b2f;
  border-radius: 2px;
}

.book-row {
  position: relative;
  height: 23px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid #202020;
  border-left: 3px solid transparent;
  border-right: 3px solid transparent;
  box-sizing: border-box;
  background-color: #0d0d0d;
  transition: filter 0.15s ease;
}

/* Tiered row background levels matching reference L2 price levels */
.book-row.row-tier-0 { background-color: #28292b; }
.book-row.row-tier-1 { background-color: #1e1e20; }
.book-row.row-tier-2 { background-color: #161718; }
.book-row.row-tier-3,
.book-row.row-tier-4,
.book-row.row-tier-5,
.book-row.row-tier-6,
.book-row.row-tier-7,
.book-row.row-tier-8,
.book-row.row-tier-default {
  background-color: #0d0d0d;
}

.book-row:hover {
  filter: brightness(1.18);
}

.big-wall {
  border-left: 3px solid rgba(250, 204, 21, 0.45);
}

.depth-bar-container {
  position: absolute;
  top: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
}

.bid-depth-container {
  left: 0;
  right: 38px;
}

.ask-depth-container {
  left: 38px;
  right: 0;
}

.depth-bar {
  position: absolute;
  top: 0;
  bottom: 0;
  transition: width 0.2s cubic-bezier(0.22, 1, 0.36, 1);
  border-radius: 0;
  box-shadow: none;
}

/* Overlay bg matching requested color */
.bid-depth-bar {
  right: 0;
  background: rgb(52, 62, 72);
}

.ask-depth-bar {
  left: 0;
  background: rgb(52, 62, 72);
}

.row-content {
  position: relative;
  z-index: 2;
  display: flex;
  width: 100%;
  padding: 0 4px;
  align-items: center;
  height: 100%;
}

.bid-row-content {
  justify-content: space-between;
  padding-left: 4px;
  padding-right: 0;
}

.ask-row-content {
  justify-content: space-between;
  padding-left: 0;
  padding-right: 4px;
}

.col-size {
  font-family: var(--font-mono), Consolas, monospace;
  font-size: 13px;
  font-weight: 500;
  color: #D1D5DB;
  letter-spacing: -0.2px;
  z-index: 2;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
}

.bid-size {
  padding-left: 8px;
  justify-content: flex-start;
  gap: 4px;
}

.ask-size {
  padding-right: 8px;
  justify-content: flex-end;
  gap: 4px;
}

.col-price-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(67, 68, 71, 0.25);
  border: 1px solid rgba(78, 79, 82, 0.35);
  border-radius: 2px;
  padding: 0 3px;
  min-width: 36px;
  height: 16px;
  box-sizing: border-box;
  font-family: var(--font-mono), Consolas, monospace;
  font-size: 10px;
  font-weight: 500;
  color: #D1D5DB;
  text-align: center;
  z-index: 2;
  user-select: none;
  line-height: 1;
  margin: 0;
}

.col-price {
  font-size: 11.5px;
  font-weight: 500;
  min-width: fit-content;
  color: #D1D5DB;
}
.bid-row-content .col-price {
  text-align: right;
}
.ask-row-content .col-price {
  text-align: left;
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

.size-3-digit {
  opacity: 1;
}

.size-2-digit {
  opacity: 1;
}

.size-1-digit {
  opacity: 1;
}

.wall-floor-chip {
  display: inline-block;
  font-size: 9px;
  font-weight: 900;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.4px;
}

.floor-chip {
  background: rgba(250, 204, 21, 0.15);
  color: rgba(250, 204, 21, 0.85);
  border: 1px solid rgba(250, 204, 21, 0.45);
}

.wall-chip {
  background: rgba(250, 204, 21, 0.15);
  color: rgba(250, 204, 21, 0.85);
  border: 1px solid rgba(250, 204, 21, 0.45);
}

.row-floor-highlight {
  border-left: 3px solid rgba(250, 204, 21, 0.45) !important;
}

.row-wall-highlight {
  border-right: 3px solid rgba(250, 204, 21, 0.45) !important;
}

.block-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  line-height: 1;
  color: #fbbf24;
  opacity: 0.85;
  background: transparent;
  border: none;
  filter: drop-shadow(0 0 3px rgba(245, 158, 11, 0.45));
  animation: pulse-block-anim 1.5s infinite;
  z-index: 5;
  flex-shrink: 0;
  user-select: none;
}

@keyframes pulse-block-anim {
  0% { transform: scale(0.95); opacity: 0.75; }
  50% { transform: scale(1.1); opacity: 0.95; filter: drop-shadow(0 0 5px rgba(245, 158, 11, 0.55)); }
  100% { transform: scale(0.95); opacity: 0.75; }
}

.empty-state {
  padding: 30px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}

</style>
