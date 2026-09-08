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

      <!-- Right Column: MTF Confluence & Price Action/Momentum (Collapsible Slide Right) -->
      <section class="grid-col right-panel-col" :class="{ 'collapsed': isMtfCollapsed }">
        <button 
          class="mtf-toggle-tab" 
          @click="isMtfCollapsed = !isMtfCollapsed" 
          :title="isMtfCollapsed ? 'Expand MTF Confluence' : 'Collapse MTF Confluence'"
        >
          <span class="toggle-arrow">{{ isMtfCollapsed ? '◀' : '▶' }}</span>
          <span v-if="isMtfCollapsed" class="collapsed-title mono">MTF CONFLUENCE</span>
        </button>
        <div class="mtf-inner" v-show="!isMtfCollapsed">
          <MTFConfluence />
        </div>
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
import { ref } from 'vue';
import { useMarketStore } from '../stores/marketStore';
import OrderBook from '../components/OrderBook.vue';
import TimeAndSales from '../components/TimeAndSales.vue';
import MTFConfluence from '../components/MTFConfluence.vue';

const store = useMarketStore();
const isMtfCollapsed = ref(false);
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
  flex: 2.4;
  min-width: 0;
}

.l2-tape-split {
  display: flex;
  flex-direction: row;
  gap: 16px;
  height: 100%;
}

.book-container {
  flex: 1.5;
  min-width: 320px;
}

.tape-container {
  flex: 1.1;
  min-width: 320px;
}

.right-panel-col {
  position: relative;
  flex: 0.8;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: flex 0.3s cubic-bezier(0.4, 0, 0.2, 1), min-width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.right-panel-col.collapsed {
  flex: 0 0 32px !important;
  min-width: 32px !important;
  max-width: 32px;
}

.mtf-inner {
  height: 100%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.mtf-toggle-tab {
  position: absolute;
  top: 8px;
  left: -12px;
  z-index: 40;
  width: 24px;
  height: 38px;
  background: #162032;
  border: 1px solid #38bdf8;
  border-radius: 6px;
  color: #38bdf8;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
  transition: all 0.2s ease;
  padding: 0;
}

.right-panel-col.collapsed .mtf-toggle-tab {
  left: 4px;
  top: 8px;
  width: 24px;
  height: 100%;
  max-height: 150px;
  border-radius: 6px;
  background: rgba(22, 32, 50, 0.95);
}

.mtf-toggle-tab:hover {
  background: #38bdf8;
  color: #0c121e;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
}

.toggle-arrow {
  font-size: 11px;
  line-height: 1;
}

.collapsed-title {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  transform: rotate(180deg);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1px;
  margin-top: 10px;
  white-space: nowrap;
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
