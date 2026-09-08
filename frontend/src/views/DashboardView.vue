<template>
  <div class="dashboard-grid">
    <template v-if="store.symbol">
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
    </template>
    
    <!-- No Ticker State -->
    <div v-else class="empty-ticker-state">
      <div class="empty-icon-wrap">
        <div class="pulse-ring"></div>
        <span class="empty-icon">🎯</span>
      </div>
      <h2 class="empty-title mono">NO TICKER SUBSCRIBED</h2>
      <p class="empty-subtitle mono">Enter a symbol in the top bar or click a scanner chip to connect to the live tape.</p>
    </div>
  </div>
</template>

<script setup>
import { useMarketStore } from '../stores/marketStore';
import OrderBook from '../components/OrderBook.vue';
import TimeAndSales from '../components/TimeAndSales.vue';
import MTFConfluence from '../components/MTFConfluence.vue';

const store = useMarketStore();
</script>

<style scoped>
.dashboard-grid {
  display: flex;
  flex-direction: row;
  gap: 16px;
  flex: 1;
  min-height: 0;
  width: 100%;
}

.grid-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.left-panel-col {
  flex: 2;
  min-width: 0;
}

.l2-tape-split {
  display: flex;
  flex-direction: row;
  gap: 16px;
  height: 100%;
}

.book-container {
  flex: 1;
  min-width: 280px;
}

.tape-container {
  flex: 1.3;
  min-width: 380px;
}

.right-panel-col {
  flex: 1;
  min-width: 320px;
}

@media (max-width: 1024px) {
  .dashboard-grid {
    flex-direction: column;
  }
}

.empty-ticker-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  flex: 1;
  background: rgba(13, 17, 23, 0.4);
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  text-align: center;
  padding: 40px;
}

.empty-icon-wrap {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid rgba(56, 189, 248, 0.5);
  animation: radar-pulse 2s infinite ease-out;
}

.empty-icon {
  font-size: 42px;
  z-index: 2;
  filter: drop-shadow(0 0 15px rgba(56, 189, 248, 0.4));
}

@keyframes radar-pulse {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(1.6); opacity: 0; }
}

.empty-title {
  font-size: 24px;
  font-weight: 900;
  color: var(--text-primary);
  margin: 0 0 12px 0;
  letter-spacing: 2px;
  text-shadow: 0 0 15px rgba(255,255,255,0.1);
}

.empty-subtitle {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-muted);
  max-width: 400px;
  line-height: 1.5;
  margin: 0;
}
</style>
