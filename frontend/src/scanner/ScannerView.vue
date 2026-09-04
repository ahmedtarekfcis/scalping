<template>
  <div class="scanner-view glass-panel">
    <div class="scanner-content">
      <div class="scanner-controls">
        <button 
          class="btn-scan mono font-bold" 
          @click="store.scanMarket()"
          :class="{ 'is-scanning': store.isScanning }"
        >
          <span class="scan-icon">⚡</span>
          {{ store.isScanning ? 'SCANNING...' : 'FORCE RE-SCAN' }}
        </button>
      </div>
      <ScannerTable 
        :results="store.scannerResults" 
        @select-symbol="handleSelectSymbol"
      />
    </div>
  </div>
</template>

<script setup>
import { useMarketStore } from '../stores/marketStore';
import ScannerTable from './ScannerTable.vue';

const store = useMarketStore();
const emit = defineEmits(['trade']);

function handleSelectSymbol(symbol) {
  store.changeSymbol(symbol);
  emit('trade', symbol);
}
</script>

<style scoped>
.scanner-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
}

.scanner-content {
  flex: 1;
  overflow: hidden;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.scanner-controls {
  display: flex;
  justify-content: flex-end;
}

.btn-scan {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(37, 99, 235, 0.2) 100%);
  border: 1px solid rgba(56, 189, 248, 0.5);
  color: #38bdf8;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.1);
}

.btn-scan:hover {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.3) 0%, rgba(37, 99, 235, 0.3) 100%);
  border-color: #38bdf8;
  box-shadow: 0 0 15px rgba(56, 189, 248, 0.3);
  transform: translateY(-1px);
}

.btn-scan:active {
  transform: translateY(1px);
}

.btn-scan.is-scanning {
  opacity: 0.7;
  pointer-events: none;
  animation: pulse 1s infinite alternate;
}

@keyframes pulse {
  0% { opacity: 0.6; box-shadow: 0 0 10px rgba(56, 189, 248, 0.1); }
  100% { opacity: 1; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5); }
}
</style>
