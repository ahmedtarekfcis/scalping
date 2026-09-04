<template>
  <div class="depth-meter-wrap glass-panel mono">
    <div class="meter-labels">
      <div class="bid-stat">
        <span class="label">BIDS (BUY)</span>
        <span class="val text-green">{{ formatNum(store.bidTotalVolume) }} ({{ store.bidRatio }}%)</span>
      </div>
      <div class="center-stat">
        <span class="label">SPREAD</span>
        <span class="val text-accent">${{ store.spread.toFixed(2) }}</span>
      </div>
      <div class="ask-stat">
        <span class="val text-red">({{ store.askRatio }}%) {{ formatNum(store.askTotalVolume) }}</span>
        <span class="label">ASKS (SELL)</span>
      </div>
    </div>

    <!-- Power Bar -->
    <div class="progress-track">
      <div 
        class="progress-bid" 
        :style="{ width: `${store.bidRatio}%` }"
      ></div>
      <div 
        class="progress-ask" 
        :style="{ width: `${store.askRatio}%` }"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();

function formatNum(num) {
  if (!num) return '0';
  return num.toLocaleString();
}
</script>

<style scoped>
.depth-meter-wrap {
  padding: 10px 16px;
  margin-bottom: 16px;
}

.meter-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 11px;
}

.bid-stat, .ask-stat, .center-stat {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.label {
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.5px;
}

.val {
  font-weight: 700;
  font-size: 13px;
}

.progress-track {
  display: flex;
  height: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.progress-bid {
  background: linear-gradient(90deg, #009e60, var(--green-bid));
  height: 100%;
  transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 8px var(--green-bid-glow);
}

.progress-ask {
  background: linear-gradient(90deg, var(--red-ask), #c9183b);
  height: 100%;
  transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 8px var(--red-ask-glow);
}

.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.text-accent { color: var(--accent-cyan); }
</style>
