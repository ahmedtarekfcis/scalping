<template>
  <div class="orderbook-panel glass-panel">
    <!-- Scorecard Bar -->
    <div class="intel-top-bar mono" @mouseenter="showScoreDetails = true" @mouseleave="showScoreDetails = false">

      <!-- Single centered bar: starts at middle, goes green→right or red→left -->
      <div class="sc-single-wrap">
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
        <!-- Score number pinned to centre -->
        <div class="sc-score-center" :class="scoreClass">
          {{ store.scorecard.total > 0 ? '+' : '' }}{{ store.scorecard.total }}
        </div>
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
            <span class="legend-item"><span class="dot dot-purple"></span> RF: {{ store.scorecard.roundFigureCtx > 0 ? '+' : '' }}{{ store.scorecard.roundFigureCtx }}</span>
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
              row.hasBorder ? 'row-floor-highlight' : '',
              row.roundFigure ? `rf-${row.roundFigure.level}` : ''
            ]"
          >
            <span v-if="row.hasIcon" class="block-badge block-badge-bid">⚡</span>
            <!-- Round Figure Badge -->
            <span 
              v-if="row.roundFigure" 
              class="rf-badge" 
              :class="`rf-badge-${row.roundFigure.level}`"
              :title="`Round Figure — $${row.roundFigure.step} level`"
            >
              {{ row.roundFigure.level === 'key' ? '◆' : (row.roundFigure.level === 'major' ? '●' : '·') }}
            </span>
            <!-- Inline Cumulative Depth Fill Bar Container -->
            <div class="depth-bar-container bid-depth-container">
              <div 
                class="depth-bar bid-depth-bar" 
                :style="{ width: `${row.percent}%` }"
              ></div>
            </div>

            <div class="row-content bid-row-content">
              <span 
                class="col-size" 
                :class="getSizeClasses(row.size)"
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
            :class="[
              row.hasBorder ? 'row-wall-highlight' : '',
              row.roundFigure ? `rf-${row.roundFigure.level}` : ''
            ]"
          >
            <span v-if="row.hasIcon" class="block-badge block-badge-ask">⚡</span>
            <!-- Round Figure Badge -->
            <span 
              v-if="row.roundFigure" 
              class="rf-badge" 
              :class="`rf-badge-${row.roundFigure.level}`"
              :title="`Round Figure — $${row.roundFigure.step} level`"
            >
              {{ row.roundFigure.level === 'key' ? '◆' : (row.roundFigure.level === 'major' ? '●' : '·') }}
            </span>
            <!-- Inline Cumulative Depth Fill Bar Container -->
            <div class="depth-bar-container ask-depth-container">
              <div 
                class="depth-bar ask-depth-bar" 
                :style="{ width: `${row.percent}%` }"
              ></div>
            </div>

            <div class="row-content ask-row-content">
              <span class="col-price text-red font-bold">{{ row.price.toFixed(2) }}</span>
              <span 
                class="col-size" 
                :class="getSizeClasses(row.size)"
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
  const lots = Math.floor(num / 100);
  if (lots >= 1000) return (lots / 1000).toFixed(1) + 'K';
  return lots.toString();
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

function getSizeClasses(size) {
  if (size === undefined || size === null || isNaN(size)) return 'size-1-digit';
  const lots = Math.floor(size / 100);
  if (lots >= 100) return 'size-3-digit text-gold'; // 3+ digits
  if (lots >= 10) return 'size-2-digit';            // 2 digits
  return 'size-1-digit';                            // 1 digit
}

</script>

<style scoped>
.orderbook-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: border 0.2s ease, box-shadow 0.2s ease;
}

.intel-top-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0 8px;
  height: 28px;
  box-sizing: border-box;
  background: linear-gradient(180deg, #161f30 0%, #0c121e 100%);
  border-bottom: 2px solid #38bdf8;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
  cursor: default;
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

/* Score number floated over the centre of the bar */
.sc-score-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: -0.5px;
  pointer-events: none;
  z-index: 5;
  text-shadow: 0 1px 3px rgba(0,0,0,0.9);
  transition: color 0.3s;
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
  border-left: 3px solid transparent;
  border-right: 3px solid transparent;
  transition: background-color 0.15s ease;
}

.book-row:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.big-wall {
  border-left: 3px solid var(--gold-block);
}

.depth-bar-container {
  position: absolute;
  top: 1px;
  bottom: 1px;
  pointer-events: none;
}

.bid-depth-container {
  left: 0;
  right: 52px;
}

.ask-depth-container {
  right: 0;
  left: 52px;
}

.depth-bar {
  position: absolute;
  top: 0;
  bottom: 0;
  transition: width 0.15s ease;
  border-radius: 0;
  box-shadow: none;
}

.bid-depth-bar {
  left: 0;
  background: rgba(0, 255, 136, 0.12);
}

.ask-depth-bar {
  right: 0;
  background: rgba(255, 59, 86, 0.12);
}

.row-content {
  position: relative;
  z-index: 2;
  display: flex;
  width: 100%;
  padding: 0 4px;
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
  justify-content: center;
  gap: 5px;
  min-width: 50px;
}

.col-price {
  font-size: 15.5px;
  font-weight: 800;
  min-width: fit-content;
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
  animation: size-pulse-anim 1.5s infinite;
}

.size-2-digit {
  opacity: 1;
}

.size-1-digit {
  opacity: 0.45;
}

@keyframes size-pulse-anim {
  0% { text-shadow: 0 0 2px rgba(255, 255, 255, 0); transform: scale(1); }
  50% { text-shadow: 0 0 8px currentColor; transform: scale(1.05); }
  100% { text-shadow: 0 0 2px rgba(255, 255, 255, 0); transform: scale(1); }
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
  border-left: 3px solid #facc15 !important;
}

.row-wall-highlight {
  border-right: 3px solid #facc15 !important;
}

.block-badge {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 900;
  color: #facc15;
  background: transparent;
  border: none;
  text-shadow: 0 0 8px rgba(250, 204, 21, 0.5);
  animation: pulse-block-anim 1.5s infinite;
  z-index: 5;
}

.block-badge-bid { left: 2px; }
.block-badge-ask { right: 2px; }

@keyframes pulse-block-anim {
  0% { transform: translateY(-50%) scale(0.95); text-shadow: 0 0 4px rgba(250, 204, 21, 0.4); }
  50% { transform: translateY(-50%) scale(1.15); text-shadow: 0 0 12px rgba(250, 204, 21, 0.8); }
  100% { transform: translateY(-50%) scale(0.95); text-shadow: 0 0 4px rgba(250, 204, 21, 0.4); }
}

.empty-state {
  padding: 30px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}

/* ============================================================ */
/* ROUND FIGURE LEVELS (Price-Aware S/R Zones)                  */
/* ============================================================ */

/* Key level: whole-number anchors ($5, $10, $50, $100…)        */
.rf-key {
  background: rgba(250, 204, 21, 0.07) !important;
  border-top: 1px dashed rgba(250, 204, 21, 0.55) !important;
}
.rf-key .col-price {
  text-shadow: 0 0 8px rgba(250, 204, 21, 0.45);
}

/* Major level: half/quarter-dollar steps for the price tier    */
.rf-major {
  background: rgba(56, 189, 248, 0.05) !important;
  border-top: 1px dashed rgba(56, 189, 248, 0.30) !important;
}
.rf-major .col-price {
  text-shadow: 0 0 6px rgba(56, 189, 248, 0.30);
}

/* Minor level: very subtle dotted separator only               */
.rf-minor {
  border-top: 1px dotted rgba(255, 255, 255, 0.12) !important;
}

/* Badges (right-aligned inside the bid/ask row)                */
.rf-badge {
  position: absolute;
  right: 2px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  font-weight: 900;
  line-height: 1;
  z-index: 6;
  pointer-events: none;
  opacity: 0.85;
}

/* Bid side: badge on the LEFT of the price column */
.bid-row .rf-badge {
  left: 2px;
  right: auto;
}

.rf-badge-key {
  color: #facc15;
  text-shadow: 0 0 6px rgba(250, 204, 21, 0.7);
  font-size: 12px;
}

.rf-badge-major {
  color: #38bdf8;
  text-shadow: 0 0 5px rgba(56, 189, 248, 0.5);
}

.rf-badge-minor {
  color: rgba(255, 255, 255, 0.35);
  font-size: 14px;
  font-weight: 400;
}
</style>
