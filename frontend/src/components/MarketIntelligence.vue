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
      <!-- Squeeze Score Metrics -->
      <section class="intel-section" v-if="store.intelligence.surge_prediction">
        <h4 class="section-title">SQUEEZE ENGINE</h4>
        
        <div class="metric-box squeeze-main">
          <span class="label">SQUEEZE SCORE</span>
          <span class="value" :class="getScoreClass(store.intelligence.surge_prediction.squeeze_score)">
            {{ store.intelligence.surge_prediction.squeeze_score }}/100
          </span>
          <span class="classification">{{ store.intelligence.surge_prediction.classification }}</span>
        </div>
        
        <div class="metric-grid">
          <div class="metric-box">
            <span class="label">POTENTIAL (FUEL)</span>
            <span class="value">{{ store.intelligence.surge_prediction.squeeze_potential }}/100</span>
          </div>
          <div class="metric-box">
            <span class="label">IGNITION (REAL-TIME)</span>
            <span class="value">{{ store.intelligence.surge_prediction.squeeze_ignition }}/100</span>
          </div>
          <div class="metric-box">
            <span class="label">ORDER FLOW BIAS</span>
            <span class="value" :class="getBiasClass(store.intelligence.surge_prediction.order_flow_bias)">
              {{ store.intelligence.surge_prediction.order_flow_bias }}
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

function getScoreClass(score) {
  if (score >= 80) return 'text-green text-glow-green';
  if (score >= 60) return 'text-yellow';
  return 'text-muted';
}

function getBiasClass(bias) {
  if (bias === 'BULLISH') return 'text-green';
  if (bias === 'BEARISH') return 'text-red';
  return 'text-muted';
}
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

.squeeze-main {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 16px;
  margin-bottom: 12px;
}

.squeeze-main .value {
  font-size: 28px;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.1);
}

.classification {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 4px;
  color: #38bdf8;
}

.text-green { color: #00d084; }
.text-red { color: #ff3b56; }
.text-yellow { color: #facc15; }
.text-muted { color: #64748b; }
.text-glow-green { text-shadow: 0 0 12px rgba(0, 208, 132, 0.5); }
</style>
