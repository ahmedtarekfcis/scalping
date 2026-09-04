<template>
  <div class="scanner-table-container mono">
    <div class="table-header">
      <span class="col-symbol">SYMBOL</span>
      <span class="col-price">PRICE</span>
      <span class="col-change">CHANGE</span>
      <span class="col-vol">TODAY VOL</span>
      <span class="col-rv">RV</span>
      <span class="col-float">FLOAT</span>
      <span class="col-action">ACTION</span>
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
        <span class="col-symbol font-bold">{{ item.symbol }}</span>
        <span class="col-price">${{ item.lastPrice }}</span>
        <span class="col-change" :class="getChangeClass(item.changePercent)">
          {{ item.changePercent > 0 ? '+' : '' }}{{ item.changePercent }}%
        </span>
        <span class="col-vol">{{ item.volume }}</span>
        <span class="col-rv">{{ item.rv }}</span>
        <span class="col-float">{{ item.freeFloat }}</span>
        <div class="col-action">
          <button class="btn-trade" @click="$emit('select-symbol', item.symbol)">
            TRADE
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  results: {
    type: Array,
    default: () => []
  }
});

defineEmits(['select-symbol']);

function getChangeClass(change) {
  if (change > 0) return 'text-green text-glow-green';
  if (change < 0) return 'text-red text-glow-red';
  return 'text-muted';
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
  overflow: hidden;
}

.table-header {
  display: grid;
  grid-template-columns: 100px 100px 100px 120px 80px 1fr 100px;
  align-items: center;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(10, 14, 22, 0.85);
}

.table-body {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
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
  grid-template-columns: 100px 100px 100px 120px 80px 1fr 100px;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  transition: all 0.2s ease;
  animation: slideIn 0.3s ease-out backwards;
}

.scan-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.scan-row.trend-up:hover {
  background: linear-gradient(90deg, rgba(0, 208, 132, 0.1) 0%, transparent 100%);
  border-left: 2px solid #00d084;
}

.scan-row.trend-down:hover {
  background: linear-gradient(90deg, rgba(255, 59, 86, 0.1) 0%, transparent 100%);
  border-left: 2px solid #ff3b56;
}

.col-symbol {
  font-size: 16px;
  color: #38bdf8;
  letter-spacing: 0.5px;
}

.col-price {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.col-change {
  font-size: 15px;
  font-weight: 800;
}

.col-vol {
  font-size: 14px;
  color: var(--text-secondary);
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
