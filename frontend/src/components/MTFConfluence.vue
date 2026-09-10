<template>
  <div class="mtf-panel glass-panel">
    <!-- Mobile-style collapse handle -->
    <div class="mobile-collapse-handle" @click="$emit('collapse-mtf')" title="Collapse MTF Panel">
      <div class="handle-bar"></div>
    </div>
    <div class="mtf-content mono">
      <!-- Section 1: MTF Floors & Walls Table -->
      <div class="mtf-section" style="position: relative;">
        <button 
          @click="handleMtfRefresh" 
          class="btn-refresh-criteria btn-float" 
          title="Refetch S&R Levels"
        >
          ↻
        </button>

        <div class="mtf-rows" :class="{ 'flash-white': flashMtf }">
          <div 
            v-for="item in frameRows" 
            :key="item.frame"
            class="mtf-frame-card"
          >
            <!-- Floated Badge -->
            <div class="frame-badge-float">
              {{ item.frame }}
            </div>
            
            <div class="frame-card-levels">
              <div class="level-col-card">
                <span class="val-price font-bold" :class="item.floor ? 'text-green text-glow-green' : 'text-dash'">
                  {{ item.floor ? `$${Number(item.floor).toFixed(2)}` : '-' }}
                </span>
              </div>
              <div class="level-col-card">
                <span class="val-price font-bold" :class="item.wall ? 'text-red text-glow-red' : 'text-dash'">
                  {{ item.wall ? `$${Number(item.wall).toFixed(2)}` : '-' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Section 2: critrias (Colored Red if below, Green if above) -->
      <div class="momentum-section" style="position: relative;">
        <button 
          @click="handleCriteriaRefresh" 
          class="btn-refresh-criteria btn-float" 
          title="Refetch Moving Averages"
        >
          ↻
        </button>

        <div class="metric-grid" :class="{ 'flash-white': flashCriteria }">
          <div 
            v-for="item in momentumMetrics" 
            :key="item.label"
            class="metric-box"
            :class="item.stateClass"
          >
            <div class="metric-box-top">
              <span class="label">{{ item.label }}</span>
              <span v-if="item.stateTag" class="metric-tag">{{ item.stateTag }}</span>
            </div>
            <span class="value font-bold">{{ item.formattedVal }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();
defineEmits(['collapse-mtf']);

const flashCriteria = ref(false);
const flashMtf = ref(false);

let retryTimeout = null;

watch(
  () => store.symbol,
  () => {
    // When symbol changes, set a timeout to automatically retry fetching if it fails to load within 4 seconds
    if (retryTimeout) clearTimeout(retryTimeout);
    retryTimeout = setTimeout(() => {
      if (!store.intelligence?.ema_9) {
        store.refetchCriteria();
      }
      if (!store.intelligence?.mtf_levels || store.intelligence.mtf_levels.length === 0) {
        store.refetchMtf();
      }
    }, 4000);
  }
);

onUnmounted(() => {
  if (retryTimeout) clearTimeout(retryTimeout);
});

watch(() => store.intelligence?.last_update_time, (newVal, oldVal) => {
  if (newVal && newVal !== oldVal) {
    flashCriteria.value = true;
    setTimeout(() => {
      flashCriteria.value = false;
    }, 800);
  }
});

watch(() => store.intelligence?.last_mtf_update_time, (newVal, oldVal) => {
  if (newVal && newVal !== oldVal) {
    flashMtf.value = true;
    setTimeout(() => {
      flashMtf.value = false;
    }, 800);
  }
});

function handleMtfRefresh() {
  flashMtf.value = true;
  setTimeout(() => { flashMtf.value = false; }, 800);
  store.refetchMtf();
}

function handleCriteriaRefresh() {
  flashCriteria.value = true;
  setTimeout(() => { flashCriteria.value = false; }, 800);
  store.refetchCriteria();
}

// 1. MTF Frame Rows
const frameRows = computed(() => {
  const backendLevels = store.intelligence?.mtf_levels || [];

  return ['5s', '10s', '1m', '5m', '15m', '4h'].map(frame => {
    const frameZones = backendLevels.filter(z => z.timeframe === frame);
    const floorZone = frameZones.find(z => z.type === 'FLOOR' || z.type === 'Support');
    const wallZone = frameZones.find(z => z.type === 'WALL' || z.type === 'Resistance');

    let floor = floorZone ? floorZone.price : null;
    let wall = wallZone ? wallZone.price : null;

    // Fallbacks if backend doesn't provide it yet (before first tick)
    if (floor === null && wall === null) {
      const curPrice = store.lastPrice || 100.0;
      if (frame === '5s') { floor = +(curPrice - 0.05).toFixed(2); wall = +(curPrice + 0.05).toFixed(2); }
      else if (frame === '10s') { floor = +(curPrice - 0.12).toFixed(2); wall = +(curPrice + 0.12).toFixed(2); }
      else if (frame === '1m') { floor = +(curPrice - 0.25).toFixed(2); wall = null; }
      else if (frame === '5m') { floor = +(curPrice - 0.55).toFixed(2); wall = null; }
      else if (frame === '15m') { floor = +(curPrice - 1.00).toFixed(2); wall = +(curPrice + 1.00).toFixed(2); }
      else if (frame === '4h') { floor = +(curPrice - 2.50).toFixed(2); wall = null; }
    }

    return {
      frame,
      floor,
      wall
    };
  });
});

// 2. Price Action & Momentum with Dynamic Color Based on Current Price
const momentumMetrics = computed(() => {
  const curPrice = store.lastPrice || 0;
  const vwap = store.intelligence?.vwap || null;
  const ema9 = store.intelligence?.ema_9 || null;
  const ema21 = store.intelligence?.ema_21 || null;
  const ema200 = store.intelligence?.ema_200 || null;

  const list = [
    { label: 'VWAP', val: vwap },
    { label: '9 EMA (1m)', val: ema9 },
    { label: '21 EMA (1m)', val: ema21 },
    { label: '200 EMA (1m)', val: ema200 },
  ];

  return list.map(item => {
    let stateClass = 'box-neutral';
    let stateTag = '';

    if (item.val && curPrice > 0) {
      if (curPrice > item.val) {
        stateClass = 'box-above'; // Price is ABOVE -> Green
        stateTag = 'ABOVE';
      } else if (curPrice < item.val) {
        stateClass = 'box-below'; // Price is BELOW -> Red
        stateTag = 'BELOW';
      }
    }

    return {
      label: item.label,
      val: item.val,
      formattedVal: item.val ? `$${Number(item.val).toFixed(2)}` : '--',
      stateClass,
      stateTag
    };
  });
});
</script>

<style scoped>
.mtf-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: rgba(13, 17, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.mobile-collapse-handle {
  width: 100%;
  padding: 8px 0;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.02);
  transition: background 0.2s;
  flex-shrink: 0;
}

.mobile-collapse-handle:hover {
  background: rgba(255, 255, 255, 0.05);
}

.mobile-collapse-handle:hover .handle-bar {
  background: #38bdf8;
  box-shadow: 0 0 8px rgba(56, 189, 248, 0.6);
}

.handle-bar {
  width: 36px;
  height: 4px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 4px;
  transition: all 0.2s;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  height: 52px;
  box-sizing: border-box;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-price-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-price {
  font-size: 20px;
  font-weight: 900;
  letter-spacing: 0.5px;
  color: #38bdf8;
  text-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
}

.ticker-badge {
  font-size: 11px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.35);
}

.header-sub {
  font-size: 11px;
  font-weight: 800;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}

.live-dot {
  width: 9px;
  height: 9px;
  background-color: var(--accent-cyan);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent-cyan);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.15); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.mtf-content {
  flex: 1;
  overflow-y: auto;
  padding: 6px 14px 12px 14px;
  display: flex;
  flex-direction: row;
  gap: 16px;
}

.mtf-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Frame Rows Grid */
.mtf-rows {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.mtf-frame-card {
  position: relative;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.025);
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 14px 6px 6px 6px;
  gap: 8px;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.mtf-frame-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(56, 189, 248, 0.35);
}

.frame-badge-float {
  position: absolute;
  top: -1px;
  left: -1px;
  background: rgba(37, 99, 235, 0.4);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
  padding: 1px 5px;
  border-top-left-radius: 6px;
  border-bottom-right-radius: 6px;
  font-weight: 900;
  font-size: 9px;
  letter-spacing: 0.5px;
  z-index: 2;
}

.frame-card-levels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}

.level-col-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  padding: 4px 0;
  min-height: 24px;
}

.val-price {
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.3px;
}

.text-dash {
  color: var(--text-muted);
  font-size: 18px;
  font-weight: 800;
  opacity: 0.5;
}

.text-green {
  color: var(--green-bid);
}

.text-glow-green {
  text-shadow: 0 0 8px rgba(0, 208, 132, 0.4);
}

.text-red {
  color: #ff3b56;
}

.text-glow-red {
  text-shadow: 0 0 8px rgba(255, 59, 86, 0.4);
}

/* Section 2: Momentum Section */
.momentum-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  padding-left: 16px;
}

.momentum-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.momentum-title {
  font-size: 11px;
  font-weight: 800;
  color: var(--text-muted);
  letter-spacing: 0.8px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.metric-box {
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.metric-box-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-box .label {
  font-size: 10.5px;
  font-weight: 800;
  color: var(--text-muted);
  letter-spacing: 0.4px;
}

.metric-tag {
  font-size: 8.5px;
  font-weight: 900;
  padding: 1px 4px;
  border-radius: 3px;
  letter-spacing: 0.3px;
}

.metric-box .value {
  font-size: 16px;
  font-weight: 900;
}

/* Price is ABOVE -> Colored Green */
.box-above {
  background: rgba(0, 208, 132, 0.09);
  border: 1px solid rgba(0, 208, 132, 0.45);
  box-shadow: 0 0 10px rgba(0, 208, 132, 0.12) inset, 0 0 6px rgba(0, 208, 132, 0.15);
}

.box-above .value {
  color: #00d084;
  text-shadow: 0 0 8px rgba(0, 208, 132, 0.4);
}

.box-above .metric-tag {
  background: rgba(0, 208, 132, 0.22);
  color: #00d084;
  border: 1px solid rgba(0, 208, 132, 0.45);
}

/* Price is BELOW -> Colored Red */
.box-below {
  background: rgba(255, 59, 86, 0.09);
  border: 1px solid rgba(255, 59, 86, 0.45);
  box-shadow: 0 0 10px rgba(255, 59, 86, 0.12) inset, 0 0 6px rgba(255, 59, 86, 0.15);
}

.box-below .value {
  color: #ff3b56;
  text-shadow: 0 0 8px rgba(255, 59, 86, 0.4);
}

.box-below .metric-tag {
  background: rgba(255, 59, 86, 0.22);
  color: #ff3b56;
  border: 1px solid rgba(255, 59, 86, 0.45);
}

/* Neutral Box */
.box-neutral {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.box-neutral .value {
  color: var(--text-primary);
}

.flash-update {
  animation: flashGreen 0.8s ease-out;
}

@keyframes flashGreen {
  0% {
    background-color: rgba(0, 255, 128, 0.2);
    box-shadow: 0 0 15px rgba(0, 255, 128, 0.4);
  }
  100% {
    background-color: transparent;
    box-shadow: none;
  }
}

.flash-white {
  animation: flashWhite 0.8s ease-out;
}

@keyframes flashWhite {
  0% {
    background-color: rgba(255, 255, 255, 0.2);
    box-shadow: 0 0 15px rgba(255, 255, 255, 0.4);
  }
  100% {
    background-color: transparent;
    box-shadow: none;
  }
}

.btn-refresh-criteria {
  background: linear-gradient(180deg, var(--bg-tertiary) 0%, rgba(255, 255, 255, 0.05) 100%);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  transition: all 0.15s ease;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.1);
  letter-spacing: 0.5px;
}

.btn-refresh-criteria:hover {
  background: var(--accent-blue);
  color: #fff;
  border-color: #38bdf8;
  box-shadow: 0 4px 10px rgba(56, 189, 248, 0.4), inset 0 1px 0 rgba(255,255,255,0.2);
  transform: translateY(-1px);
}

.btn-refresh-criteria:active {
  transform: translateY(1px);
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}

.btn-float {
  position: absolute;
  top: -12px;
  right: -4px;
  padding: 2px 6px;
  font-size: 13px;
  border-radius: 4px;
  z-index: 10;
  opacity: 0.6;
}

.btn-float:hover {
  opacity: 1;
}
</style>
