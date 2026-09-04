<template>
  <div class="app-layout">
    <!-- Top Nav / Ticker Bar -->
    <HeaderBar @open-settings="showSettings = true" />

    <div v-if="store.isLoading" class="global-loader-overlay">
      <div class="spinner"></div>
      <div class="loader-text">CONNECTING TO LEVEL 2 & TAPE DATA...</div>
    </div>

    <!-- Main Scalping Dashboard Grid -->
    <main class="dashboard-grid" :class="{ 'is-loading': store.isLoading }">
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

const store = useMarketStore();
const showSettings = ref(false);

onMounted(() => {
  store.initWebSocket();
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

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  flex: 1;
  min-height: 0; /* Important for inner overflow */
  transition: opacity 0.3s ease;
}

.dashboard-grid.is-loading {
  opacity: 0.2;
  pointer-events: none;
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
