<template>
  <div class="app-layout">
    <!-- Top Right Connection Dot -->
    <div 
      class="connection-status-dot" 
      :class="store.wsConnected ? 'dot-connected' : 'dot-disconnected'"
      :title="store.wsConnected ? 'Connected to IBKR' : 'Disconnected'"
    ></div>

    <!-- Top Nav / Ticker Bar -->
    <HeaderBar />

    <div v-if="store.isLoading" class="global-loader-overlay">
      <div class="spinner"></div>
      <div class="loader-text">CONNECTING TO LEVEL 2 & TAPE DATA...</div>
    </div>

    <div v-if="store.wsError" class="global-error-overlay">
      <div class="error-icon">⚠</div>
      <div class="error-text">CONNECTION ERROR. RECONNECTING...</div>
    </div>

    <!-- Main Content Area -->
    <main class="main-content" :class="{ 'is-loading': store.isLoading }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useMarketStore } from './stores/marketStore';
import HeaderBar from './components/HeaderBar.vue';

const store = useMarketStore();

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

</style>
