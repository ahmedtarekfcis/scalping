<template>
  <div class="app-layout">
    <!-- Top Nav / Ticker Bar -->
    <HeaderBar 
      :current-page="currentPage"
      @open-settings="showSettings = true" 
      @go-scanner="currentPage = 'scanner'"
      @go-dashboard="currentPage = 'dashboard'"
    />

    <div v-if="store.isLoading" class="global-loader-overlay">
      <div class="spinner"></div>
      <div class="loader-text">CONNECTING TO LEVEL 2 & TAPE DATA...</div>
    </div>

    <!-- Main Content Area -->
    <main class="main-content" :class="{ 'is-loading': store.isLoading }">
      
      <!-- Scalping Dashboard Grid -->
      <div v-if="currentPage === 'dashboard'" class="dashboard-grid">
        <!-- Left Column: Level 2 & Time and Sales -->
        <section class="grid-col left-panel-col">
          <div class="l2-tape-split">
            <div class="book-container">
              <OrderBook />
            </div>
            <div class="tape-container">
              <TimeAndSales />
            </div>
          </div>
        </section>

        <!-- Right Column: MTF Confluence & Price Action/Momentum -->
        <section class="grid-col right-panel-col">
          <MTFConfluence />
        </section>
      </div>

      <!-- Scanner View -->
      <div v-if="currentPage === 'scanner'" class="scanner-wrapper">
        <ScannerView @trade="handleTradeFromScanner" />
      </div>

    </main>

    <!-- Settings & IBKR Connection Modal -->
    <ConfigModal :is-open="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useMarketStore } from './stores/marketStore';
import HeaderBar from './components/HeaderBar.vue';
import OrderBook from './components/OrderBook.vue';
import TimeAndSales from './components/TimeAndSales.vue';
import MTFConfluence from './components/MTFConfluence.vue';
import ConfigModal from './components/ConfigModal.vue';
import ScannerView from './scanner/ScannerView.vue';

const store = useMarketStore();
const showSettings = ref(false);
const currentPage = ref('dashboard'); // 'dashboard' | 'scanner'

function handleTradeFromScanner(symbol) {
  currentPage.value = 'dashboard';
}

onMounted(() => {
  store.initWebSocket();
  
  // Auto-scan market every 1 second in the background
  setInterval(() => {
    store.scanMarket(true);
  }, 1000);
});
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 16px;
  gap: 14px;
  box-sizing: border-box;
  background: radial-gradient(circle at 50% 0%, #151d2e 0%, var(--bg-primary) 70%);
}

/* Removed nav-tabs CSS */

.main-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  transition: opacity 0.3s ease;
}

.main-content.is-loading {
  opacity: 0.2;
  pointer-events: none;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.scanner-wrapper {
  flex: 1;
  display: flex;
  min-height: 0;
}

.global-loader-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  z-index: 100;
  pointer-events: none;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid var(--border-light);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loader-text {
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 14px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.grid-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.l2-tape-split {
  display: flex;
  flex-direction: row;
  gap: 16px;
  height: 100%;
}

.book-container {
  flex: 1;
  min-width: 0;
}

.tape-container {
  width: 460px;
  min-width: 420px;
  max-width: 500px;
  flex-shrink: 0;
}

.right-panel-col {
  min-width: 340px;
}

@media (max-width: 1024px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr 1fr;
  }
}
</style>
