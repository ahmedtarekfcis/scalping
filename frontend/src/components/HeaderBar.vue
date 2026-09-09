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

const props = defineProps({
  currentPage: {
    type: String,
    default: 'dashboard'
  }
});

const emit = defineEmits(['open-settings', 'go-scanner', 'go-dashboard']);

function handleSymbolSubmit() {
  if (inputSymbol.value) {
    store.changeSymbol(inputSymbol.value);
  }
}

function syncWebull() {
  if (store.ws && store.ws.readyState === WebSocket.OPEN && store.symbol) {
    store.ws.send(JSON.stringify({ action: 'SYNC_WEBULL', symbol: store.symbol }));
  }
}

const statusClass = computed(() => {
  if (!store.wsConnected) return 'status-disconnected';
  return 'status-live';
});

const statusText = computed(() => {
  if (!store.wsConnected) return 'DISCONNECTED';
  return `IBKR LIVE (${store.status?.port || 'Connected'})`;
});

const surgeDirection = computed(() => store.intelligence?.surge_prediction?.direction || 'CONSOLIDATING');
const isSqueeze = computed(() => surgeDirection.value === 'SURGING_UP' || surgeDirection.value === 'POTENTIAL_SQUEEZE');
const isFlush = computed(() => surgeDirection.value === 'DUMPING_DOWN' || surgeDirection.value === 'POTENTIAL_FLUSH');

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
let audioCtx = null;
let flushBeepInterval = null;

function speak(text) {
  if (!voiceEnabled.value || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.1; // Slightly faster pacing for trading
  window.speechSynthesis.speak(utterance);
}

function playBeep() {
  if (!voiceEnabled.value) return;
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  
  osc.type = 'sine';
  osc.frequency.setValueAtTime(850, audioCtx.currentTime); // High pitch for parking sensor
  
  gain.gain.setValueAtTime(0, audioCtx.currentTime);
  gain.gain.linearRampToValueAtTime(0.02, audioCtx.currentTime + 0.02);
  gain.gain.linearRampToValueAtTime(0, audioCtx.currentTime + 0.08);
  
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start();
  osc.stop(audioCtx.currentTime + 0.1);
}

const flushScore = computed(() => store.intelligence?.surge_prediction?.flush_score || 0);

watch(flushScore, (newScore) => {
  if (flushBeepInterval) {
    clearInterval(flushBeepInterval);
    flushBeepInterval = null;
  }
  
  // If the score is meaningful, start beeping
  if (newScore >= 30 && isFlush.value) {
    // Score [30, 100] maps to Interval [800ms, 80ms]
    const intervalMs = Math.max(80, 800 - ((newScore - 30) * 10.28));
    flushBeepInterval = setInterval(playBeep, intervalMs);
  }
});

watch(surgeDirection, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    if (newVal === 'POTENTIAL_SQUEEZE' || newVal === 'MOMENTUM_SURGE' || newVal === 'SURGING_UP') {
      speak("Potential Squeeze");
    } else if (newVal === 'DUMPING_DOWN' || newVal === 'POTENTIAL_FLUSH') {
      // Voice removed for flush, replaced by the car sensor beep above
    }
    
    // Clear beep if no longer dumping down
    if (newVal !== 'DUMPING_DOWN' && newVal !== 'POTENTIAL_FLUSH') {
      if (flushBeepInterval) {
        clearInterval(flushBeepInterval);
        flushBeepInterval = null;
      }
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

const activeMomentumScans = computed(() => {
  if (!store.scannerResults) return [];
  return store.scannerResults
    .filter(item => item.state === 'ACTIVE')
    .sort((a, b) => (b.score || 0) - (a.score || 0))
    .slice(0, 5);
});
</script>

<template>
  <div class="market-header glass-panel">
    
    <!-- Floating Toast Alerts for Squeeze, Flush, and Anomaly -->
    <div class="toast-container" v-if="isSqueeze || isFlush || hasHighRiskAnomaly">
      <div v-if="isSqueeze" class="toast-alert squeeze-alert mono">
        🚀 POTENTIAL SQUEEZE
      </div>
      <div v-if="isFlush" class="toast-alert flush-alert mono">
        🔻 POTENTIAL FLUSH (SCORE: {{ flushScore }})
      </div>
      <div v-if="hasHighRiskAnomaly" class="toast-alert anomaly-alert mono" :class="activeAnomalyClass">
        {{ activeAnomalyText }}
      </div>
    </div>

    <!-- Left & Center: Symbol Search + Scanner Chips -->
    <div class="symbol-and-chips">
      <div class="symbol-search-wrap">
        <input 
          v-model="inputSymbol" 
          @keyup.enter="handleSymbolSubmit"
          placeholder="SYMBOL..." 
          class="symbol-input mono"
        />
        <button class="btn-sync" @click="syncWebull" title="Sync to Webull">
          ⮂
        </button>
      </div>

      <div class="chips-container">
        <button 
          v-for="item in activeMomentumScans" 
          :key="item.symbol"
          class="scan-chip mono"
          :class="{ 'chip-up': item.trend === 'up', 'chip-down': item.trend === 'down' }"
          @click="store.changeSymbol(item.symbol)"
          :title="item.reason"
        >
          {{ item.symbol }} 
          <div style="display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; background: rgba(250, 204, 21, 0.2); border: 1px solid rgba(250, 204, 21, 0.5); border-radius: 4px; color: #facc15; font-size: 11px; margin-left: 6px;">
            {{ item.score }}
          </div>
        </button>
        <span v-if="activeMomentumScans.length === 0" class="text-muted" style="font-size: 11px;">
          No ACTIVE Momentum
        </span>
      </div>
    </div>

    <!-- Right: Connection Badge & Quick Settings -->
    <div class="status-section">
      <div class="api-status-dot" :class="store.wsConnected ? 'connected' : 'disconnected'" :title="store.wsConnected ? 'API Connected' : 'API Disconnected'"></div>

      <button @click="toggleVoice" class="btn-config" :title="voiceEnabled ? 'Mute Voice Alerts' : 'Unmute Voice Alerts'">
        {{ voiceEnabled ? '🔊' : '🔇' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.market-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  gap: 16px;
  flex-wrap: wrap;
}

.symbol-and-chips {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.symbol-search-wrap {
  display: flex;
  align-items: center;
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
  font-size: 15px;
  font-weight: 800;
  width: 110px;
  outline: none;
  text-transform: uppercase;
  text-align: center;
}

.btn-sync {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 0 10px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
}

.btn-sync:hover {
  color: var(--accent-blue);
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
  padding: 4px 8px;
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

.api-status-dot {
  position: fixed;
  top: 4px;
  right: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  z-index: 10000;
}

.api-status-dot.connected {
  background-color: var(--green-bid);
  box-shadow: 0 0 8px var(--green-bid-glow, rgba(0, 208, 132, 0.5));
}

.api-status-dot.disconnected {
  background-color: var(--red-ask);
  animation: flash-red 0.8s infinite alternate;
}

@keyframes flash-red {
  0% { transform: scale(1); opacity: 1; box-shadow: 0 0 5px var(--red-ask); }
  100% { transform: scale(1.3); opacity: 0.5; box-shadow: 0 0 15px var(--red-ask); }
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

.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 9999;
  pointer-events: none;
}

.toast-alert {
  font-size: 14px;
  font-weight: 900;
  padding: 10px 24px;
  border-radius: 8px;
  letter-spacing: 1px;
  text-transform: uppercase;
  animation: slideDown 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards, extreme-pulse 1s infinite alternate;
  box-shadow: 0 8px 20px rgba(0,0,0,0.5);
  pointer-events: auto;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-20px); }
  to { opacity: 1; transform: translateY(0); }
}

.squeeze-alert {
  background: rgba(0, 208, 132, 0.9);
  color: #052e16;
  border: 1px solid #00ff88;
}

.flush-alert {
  background: rgba(255, 59, 86, 0.9);
  color: #fff;
  border: 1px solid #ff3b56;
}

.anomaly-alert {
  font-weight: 900;
  text-shadow: 0 0 5px rgba(0,0,0,0.5);
}

.anomaly-bid {
  background: rgba(0, 208, 132, 0.8);
  color: #fff;
  border: 1px solid #00d084;
}

.anomaly-ask {
  background: rgba(255, 59, 86, 0.8);
  color: #fff;
  border: 1px solid #ff3b56;
}

@keyframes extreme-pulse {
  0% { transform: scale(1); opacity: 0.95; }
  100% { transform: scale(1.05); opacity: 1; box-shadow: 0 0 20px currentColor; }
}

/* Scanner Chips */
.chips-container {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.scan-chip {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  padding: 5px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}

.scan-chip:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}

.chip-up {
  border-color: rgba(0, 208, 132, 0.3);
}

.chip-up:hover {
  background: rgba(0, 208, 132, 0.15);
  border-color: #00d084;
}

.chip-down {
  border-color: rgba(255, 59, 86, 0.3);
}

.chip-down:hover {
  background: rgba(255, 59, 86, 0.15);
  border-color: #ff3b56;
}

.chip-change {
  font-size: 12px;
  font-weight: 900;
}

.chip-up .chip-change { color: #00d084; }
.chip-down .chip-change { color: #ff3b56; }
</style>
