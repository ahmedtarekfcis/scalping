<script setup>
import { ref, computed, watch } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();
const inputSymbol = ref(store.symbol || '');

watch(() => store.symbol, (newVal) => {
  if (newVal) {
    inputSymbol.value = newVal;
  }
});

const emit = defineEmits(['open-settings']);

function handleSymbolSubmit() {
  if (inputSymbol.value) {
    store.changeSymbol(inputSymbol.value);
  }
}

const statusClass = computed(() => {
  if (!store.wsConnected) return 'status-disconnected';
  if (store.status.isMock) return 'status-mock';
  return 'status-live';
});

const statusText = computed(() => {
  if (!store.wsConnected) return 'DISCONNECTED';
  if (store.status.isMock) return 'MOCK SIMULATOR';
  return `IBKR LIVE (${store.status.port})`;
});

const surgeDirection = computed(() => store.intelligence?.surge_prediction?.direction || 'CONSOLIDATING');
const isSqueeze = computed(() => surgeDirection.value === 'SURGING_UP');
const isFlush = computed(() => surgeDirection.value === 'DUMPING_DOWN');

const anomaly = computed(() => store.intelligence?.order_flow_anomaly);

const activeAnomalyData = ref(null);
const activeAnomalyClass = ref('');
const anomalyCountdown = ref(5);
let anomalyInterval = null;

const lastTriggeredSize = ref(null);
const lastTriggeredSide = ref(null);
const anomalyTriggerCount = ref(0);

const hasHighRiskAnomaly = computed(() => !!activeAnomalyData.value);

const activeAnomalyText = computed(() => {
  if (!activeAnomalyData.value) return '';
  const d = activeAnomalyData.value;
  return `⚠ SPOOFING: ${d.side} @ $${d.price.toFixed(2)} [${formatSizeK(d.displayed_size)}] (${anomalyTriggerCount.value}x) | RISK: ${d.risk_score} (${anomalyCountdown.value}s)`;
});

const voiceEnabled = ref(true);

function speak(text) {
  if (!voiceEnabled.value || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.1; // Slightly faster pacing for trading
  window.speechSynthesis.speak(utterance);
}

watch(surgeDirection, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    if (newVal === 'SURGING_UP') {
      speak("Potential Squeeze");
    } else if (newVal === 'DUMPING_DOWN') {
      speak("Potential Flush");
    }
  }
});

function formatSizeK(size) {
  if (!size) return '';
  if (size >= 1000) {
    const kVal = (size / 1000).toFixed(1);
    return kVal.endsWith('.0') ? kVal.replace('.0', '') + 'k' : kVal + 'k';
  }
  return size.toString();
}

watch(anomaly, (newVal, oldVal) => {
  if (!newVal || newVal.risk_score < 50) return;

  const isFreshAppearance = !oldVal || oldVal.risk_score < 50 || newVal.side !== oldVal.side;

  if (isFreshAppearance) {
    const isSimilarSize = lastTriggeredSize.value && 
                          Math.abs(lastTriggeredSize.value - newVal.displayed_size) / lastTriggeredSize.value <= 0.15;

    if (isSimilarSize && newVal.side === lastTriggeredSide.value) {
      anomalyTriggerCount.value += 1;
      lastTriggeredSize.value = newVal.displayed_size;
    } else {
      lastTriggeredSize.value = newVal.displayed_size;
      lastTriggeredSide.value = newVal.side;
      anomalyTriggerCount.value = 1;
    }

    if (anomalyTriggerCount.value >= 2) {
      speak('Spoofing');
      
      activeAnomalyData.value = newVal;
      activeAnomalyClass.value = newVal.side === 'BID' ? 'anomaly-bid' : 'anomaly-ask';
      anomalyCountdown.value = 5;

      if (anomalyInterval) clearInterval(anomalyInterval);
      anomalyInterval = setInterval(() => {
        if (anomalyCountdown.value > 1) {
          anomalyCountdown.value -= 1;
        } else {
          clearInterval(anomalyInterval);
          anomalyInterval = null;
          activeAnomalyData.value = null;
        }
      }, 1000);
    }
  } else {
    // Not a fresh appearance, just persisting in backend.
    if (anomalyTriggerCount.value >= 2 && activeAnomalyData.value) {
      // Timer is still running, silently update the UI data
      activeAnomalyData.value = newVal;
    }
  }
}, { deep: true });

function toggleVoice() {
  voiceEnabled.value = !voiceEnabled.value;
  if (voiceEnabled.value) {
    speak("Voice Assistant Enabled");
  } else {
    window.speechSynthesis.cancel();
  }
}
</script>

<template>
  <div class="market-header glass-panel">
    <!-- Left: Symbol Search -->
    <div class="symbol-section">
      <div class="symbol-search-wrap">
        <input 
          v-model="inputSymbol" 
          @keyup.enter="handleSymbolSubmit"
          placeholder="SEARCH SYMBOL..." 
          class="symbol-input mono"
        />
        <button @click="handleSymbolSubmit" class="btn-symbol-go">GO</button>
      </div>
    </div>

    <!-- Center: Alerts -->
    <div class="alert-section" v-if="isSqueeze || isFlush || hasHighRiskAnomaly">
      <div v-if="isSqueeze" class="surge-alert squeeze-alert mono">
        POTENTIAL SQUEEZE
      </div>
      <div v-if="isFlush" class="surge-alert flush-alert mono">
        POTENTIAL FLUSH
      </div>
      <div v-if="hasHighRiskAnomaly" class="surge-alert anomaly-alert mono" :class="activeAnomalyClass">
        {{ activeAnomalyText }}
      </div>
    </div>

    <!-- Right: Connection Badge & Quick Settings -->
    <div class="status-section">
      <button @click="toggleVoice" class="btn-config" :title="voiceEnabled ? 'Mute Voice Alerts' : 'Unmute Voice Alerts'">
        {{ voiceEnabled ? '🔊' : '🔇' }}
      </button>
      <div class="connection-pill" :class="statusClass" @click="$emit('open-settings')">
        <div class="pulse-dot"></div>
        <span class="status-text mono">{{ statusText }}</span>
      </div>
      <button @click="$emit('open-settings')" class="btn-config" title="Connection Settings">
        ⚙ Config
      </button>
    </div>
  </div>
</template>

<style scoped>
.market-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  gap: 16px;
  flex-wrap: wrap;
}

.symbol-section {
  display: flex;
  align-items: center;
  gap: 18px;
}

.symbol-search-wrap {
  display: flex;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow: hidden;
}

.symbol-input {
  background: transparent;
  border: none;
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 800;
  width: 140px;
  outline: none;
  text-transform: uppercase;
}

.btn-symbol-go {
  background: var(--bg-tertiary);
  border: none;
  border-left: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0 14px;
  cursor: pointer;
  font-weight: 800;
  font-size: 12px;
  transition: all 0.2s ease;
}
.btn-symbol-go:hover {
  background: var(--accent-blue);
  color: #fff;
}

.status-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.connection-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.5px;
  cursor: pointer;
}

.status-live {
  background: rgba(0, 208, 132, 0.15);
  color: var(--green-bid);
  border: 1px solid rgba(0, 208, 132, 0.3);
}
.status-live .pulse-dot {
  background: var(--green-bid);
  box-shadow: 0 0 8px var(--green-bid-glow);
}

.status-mock {
  background: rgba(6, 182, 212, 0.15);
  color: var(--accent-cyan);
  border: 1px solid rgba(6, 182, 212, 0.3);
}
.status-mock .pulse-dot {
  background: var(--accent-cyan);
  box-shadow: 0 0 8px rgba(6, 182, 212, 0.4);
}

.status-disconnected {
  background: rgba(255, 59, 86, 0.15);
  color: var(--red-ask);
  border: 1px solid rgba(255, 59, 86, 0.3);
}
.status-disconnected .pulse-dot {
  background: var(--red-ask);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.9); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.8; }
}

.btn-config {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 7px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.2s ease;
}
.btn-config:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.bg-green-soft { background: var(--green-bid-bg); }
.bg-red-soft { background: var(--red-ask-bg); }

.flash-up {
  color: #fff !important;
  text-shadow: 0 0 10px var(--green-bid);
}
.flash-down {
  color: #fff !important;
  text-shadow: 0 0 10px var(--red-ask);
}

.alert-section {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
}

.surge-alert {
  font-size: 16px;
  font-weight: 900;
  padding: 6px 16px;
  border-radius: 8px;
  letter-spacing: 1px;
  animation: extreme-pulse 1s infinite alternate;
  text-transform: uppercase;
}

.squeeze-alert {
  background: rgba(0, 208, 132, 0.2);
  color: #00ff88;
  border: 1px solid #00ff88;
  box-shadow: 0 0 15px rgba(0, 208, 132, 0.4);
}

.flush-alert {
  background: rgba(255, 59, 86, 0.2);
  color: #ff3b56;
  border: 1px solid #ff3b56;
  box-shadow: 0 0 15px rgba(255, 59, 86, 0.4);
}

.anomaly-alert {
  font-weight: 900;
  text-shadow: 0 0 5px rgba(0,0,0,0.5);
}

.anomaly-bid {
  background: rgba(0, 208, 132, 0.15);
  color: var(--green-bid);
  border: 1px solid rgba(0, 208, 132, 0.35);
  box-shadow: 0 0 15px rgba(0, 208, 132, 0.4);
}

.anomaly-ask {
  background: rgba(255, 59, 86, 0.15);
  color: var(--red-ask);
  border: 1px solid rgba(255, 59, 86, 0.35);
  box-shadow: 0 0 15px rgba(255, 59, 86, 0.4);
}

@keyframes extreme-pulse {
  0% { transform: scale(1); opacity: 0.9; }
  100% { transform: scale(1.05); opacity: 1; box-shadow: 0 0 20px currentColor; }
}
</style>
