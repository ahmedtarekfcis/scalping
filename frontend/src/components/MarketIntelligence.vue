<template>
  <div class="market-intel-panel glass-panel">
    <div class="panel-header">
      <div class="header-title">
        <span class="live-dot"></span>
        <h3>MARKET INTELLIGENCE</h3>
      </div>
      <span class="status-badge">ACTIVE</span>
    </div>

    <div class="intel-content mono">
      <!-- Price Action & EMAs -->
      <section class="intel-section">
        <h4 class="section-title">critrias</h4>
        <div class="metric-grid">
          <div class="metric-box">
            <span class="label">VWAP</span>
            <span class="value" :class="{ placeholder: !store.intelligence.vwap }">
              {{ store.intelligence.vwap ? store.intelligence.vwap.toFixed(2) : '--' }}
            </span>
          </div>
          <div class="metric-box">
            <span class="label">9 EMA (1m)</span>
            <span class="value" :class="{ placeholder: !store.intelligence.ema_9 }">
              {{ store.intelligence.ema_9 ? store.intelligence.ema_9.toFixed(2) : '--' }}
            </span>
          </div>
          <div class="metric-box">
            <span class="label">21 EMA (1m)</span>
            <span class="value" :class="{ placeholder: !store.intelligence.ema_21 }">
              {{ store.intelligence.ema_21 ? store.intelligence.ema_21.toFixed(2) : '--' }}
            </span>
          </div>
          <div class="metric-box">
            <span class="label">200 EMA (1m)</span>
            <span class="value" :class="{ placeholder: !store.intelligence.ema_200 }">
              {{ store.intelligence.ema_200 ? store.intelligence.ema_200.toFixed(2) : '--' }}
            </span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();
</script>

<style scoped>
.market-intel-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: rgba(13, 17, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title h3 {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-primary);
  margin: 0;
}

.live-dot {
  width: 8px;
  height: 8px;
  background-color: var(--accent-cyan);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent-cyan);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.status-badge {
  font-size: 9px;
  font-weight: 800;
  padding: 3px 6px;
  border-radius: 4px;
  background: rgba(0, 208, 132, 0.15);
  color: var(--green-bid);
  border: 1px solid rgba(0, 208, 132, 0.3);
}

.intel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.intel-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding-bottom: 6px;
  margin: 0;
  letter-spacing: 0.5px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.metric-box {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.metric-box .label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 700;
}

.metric-box .value {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
}

.placeholder {
  color: var(--text-muted) !important;
  opacity: 0.5;
}
</style>
