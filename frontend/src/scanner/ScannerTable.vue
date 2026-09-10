<template>
  <div class="scanner-table-container mono">
    <div class="table-header">
      <span class="col-symbol">SYMBOL</span>
      <span class="col-move5m">5M MOVE</span>
      <span class="col-vol1m">1M VOL</span>
      <span class="col-volratio">VOL RATIO</span>
      <span class="col-volaccel">VOL ACCEL</span>
      <span class="col-specs">SPECS</span>
    </div>

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
        :style="{ animationDelay: `${index * 0.05}s` }"
      >
        <div class="col-symbol">
          <span class="score-circle" :class="getScoreClass(item.score)" :title="'Score: ' + (item.score || 0)">
            {{ item.score || 0 }}
          </span>
          <div class="symbol-info">
            <span class="symbol-name">{{ item.symbol }}</span>
            <span class="symbol-change" :class="getChangeClass(item.changePercent)">
              {{ item.changePercent > 0 ? '+' : '' }}{{ item.changePercent }}%
            </span>
          </div>
        </div>

        <span class="col-move5m" :class="getChangeClass(item.move5m)">
          {{ item.move5m !== null && item.move5m !== undefined ? (item.move5m > 0 ? '+' : '') + item.move5m + '%' : '--' }}
        </span>

        <span class="col-vol1m">
          {{ item.vol1m || '--' }}
        </span>

        <span class="col-volratio font-semibold" :class="getRatioClass(item.volRatio)">
          {{ item.volRatio !== null && item.volRatio !== undefined ? item.volRatio + 'x' : '--' }}
        </span>

        <span class="col-volaccel font-semibold" :class="getRatioClass(item.volAccel)">
          {{ item.volAccel !== null && item.volAccel !== undefined ? item.volAccel + 'x' : '--' }}
        </span>
        
        <svg 
          class="col-specs specs-icon" 
          viewBox="0 0 20 20" 
          fill="currentColor"
          title="View Specs"
          @mouseenter="showPopover($event, item)"
          @mouseleave="hidePopover"
        >
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
        </svg>
      </div>
    </div>

    <!-- Teleported Global Popover (Free from any table overflow/clipping) -->
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
import { ref, computed } from 'vue';

defineProps({
  results: {
    type: Array,
    default: () => []
  }
});

defineEmits(['select-symbol']);

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

function getStateClass(state) {
  if (state === 'ACTIVE') return 'badge-up';
  if (state === 'COOLING') return 'badge-warning';
  if (state === 'EXPIRED') return 'badge-down';
  return 'badge-neutral';
}

function getSpecsStatusClass(specs) {
  if (!specs) return 'status-unknown';
  const metCount = (specs.price ? 1 : 0) + (specs.vol ? 1 : 0) + (specs.float ? 1 : 0);
  if (metCount === 3) return 'status-all-met';
  if (metCount > 0) return 'status-partial-met';
  return 'status-none-met';
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

.table-header {
  display: grid;
  grid-template-columns: 140px 100px 100px 100px 100px 50px;
  align-items: center;
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
  display: grid;
  grid-template-columns: 140px 100px 100px 100px 100px 50px;
  align-items: center;
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

/* Uniform font size across row data */
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

/* Score Circle Badge */
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

/* Specs Icon (Direct SVG with half-white color) */
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

/* Hover Popover Box (Teleported - Clean & Concise) */
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

/* Met Criteria Highlights */
.popover-row.met {
  background: rgba(0, 208, 132, 0.1);
  border-color: rgba(0, 208, 132, 0.35);
}

.popover-row.met .row-target {
  color: #a7f3d0;
}

.popover-row.met .row-val {
  color: #00ff88;
  text-shadow: 0 0 8px rgba(0, 208, 132, 0.3);
}

.popover-no-data {
  font-size: 12px;
  color: #64748b;
  text-align: center;
  padding: 10px 0;
}

@keyframes popoverFadeIn {
  from {
    opacity: 0;
    transform: translate(-50%, -4px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}

.reason-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.badge-up {
  background: rgba(0, 208, 132, 0.15);
  color: #00ff88;
  border: 1px solid rgba(0, 208, 132, 0.3);
}

.badge-down {
  background: rgba(255, 59, 86, 0.15);
  color: #ff3b56;
  border: 1px solid rgba(255, 59, 86, 0.3);
}

.badge-warning {
  background: rgba(250, 204, 21, 0.15);
  color: #facc15;
  border: 1px solid rgba(250, 204, 21, 0.3);
}

.badge-neutral {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.btn-trade {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}

.btn-trade:hover {
  background: #38bdf8;
  color: #0f172a;
  border-color: #38bdf8;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
}

.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.text-yellow { color: #facc15; }
.text-glow-green { text-shadow: 0 0 10px rgba(0, 208, 132, 0.4); }
.text-glow-red { text-shadow: 0 0 10px rgba(255, 59, 86, 0.4); }

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
