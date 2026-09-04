<script setup>
import { computed } from 'vue';
import { useMarketStore } from '../stores/marketStore';
import { Zap, ShieldAlert } from 'lucide-vue-next';

const store = useMarketStore();

function formatSize(val) {
  if (!val) return '0';
  return val.toLocaleString();
}
</script>

<template>
  <div class="tape-container glass-panel">
    <!-- Header -->
    <div class="tape-header">
      <div class="title-box">
        <Zap class="tape-icon" :size="16" />
        <span class="tape-title">TIME & SALES (TAPE)</span>
      </div>
      <div class="tape-stats mono">
        <span class="tick-count">{{ store.tape.length }} TICKS</span>
      </div>
    </div>

    <!-- Table Header -->
    <div class="table-head mono">
      <span class="th-time">TIME</span>
      <span class="th-price">PRICE</span>
      <span class="th-size">SIZE</span>
      <span class="th-side">SIDE</span>
      <span class="th-ex">EX</span>
    </div>

    <!-- Live Fast Virtualized / Rolling Tick Stream -->
    <div class="table-body">
      <transition-group name="tick-list" tag="div" class="tick-list-wrapper">
        <div 
          v-for="tick in store.tape" 
          :key="tick.id"
          :class="[
            'tape-row mono',
            tick.side === 'BUY' ? 'row-buy' : tick.side === 'SELL' ? 'row-sell' : 'row-mid',
            { 'row-block': tick.isBlockTrade }
          ]"
        >
          <span class="td-time text-muted">{{ tick.time }}</span>
          
          <span 
            :class="[
              'td-price font-bold',
              tick.side === 'BUY' ? 'color-green' : tick.side === 'SELL' ? 'color-red' : 'text-primary'
            ]"
          >
            ${{ tick.price.toFixed(2) }}
          </span>

          <span :class="['td-size font-bold', { 'color-gold-glow': tick.isBlockTrade }]">
            {{ formatSize(tick.size) }}
            <span v-if="tick.isBlockTrade" class="block-badge" title="Block Order (>1k shares)">⚡</span>
          </span>

          <span class="td-side">
            <span 
              :class="[
                'side-badge',
                tick.side === 'BUY' ? 'badge-buy' : tick.side === 'SELL' ? 'badge-sell' : 'badge-mid'
              ]"
            >
              {{ tick.side === 'BUY' ? 'ASK' : tick.side === 'SELL' ? 'BID' : 'MID' }}
            </span>
          </span>

          <span class="td-ex text-muted">{{ tick.exchange }}</span>
        </div>
      </transition-group>

      <div v-if="store.tape.length === 0" class="empty-state">
        Awaiting tape prints...
      </div>
    </div>
  </div>
</template>

<style scoped>
.tape-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 14px;
  overflow: hidden;
}

.tape-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.title-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tape-icon {
  color: var(--gold-block);
}

.tape-title {
  font-size: 0.85rem;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: var(--text-primary);
}

.tape-stats {
  font-size: 0.68rem;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}

.table-head {
  display: grid;
  grid-template-columns: 80px 1fr 1fr 50px 55px;
  padding: 6px 10px;
  background: var(--bg-tertiary);
  border-radius: 6px 6px 0 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--text-muted);
}

.th-price, .th-size {
  text-align: right;
}
.th-side, .th-ex {
  text-align: center;
}

.table-body {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-top: none;
  border-radius: 0 0 6px 6px;
  position: relative;
}

.tick-list-wrapper {
  display: flex;
  flex-direction: column;
}

.tape-row {
  display: grid;
  grid-template-columns: 80px 1fr 1fr 50px 55px;
  padding: 5px 10px;
  font-size: 0.74rem;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.02);
  transition: background 0.15s;
}

.td-price, .td-size {
  text-align: right;
}
.td-side, .td-ex {
  text-align: center;
}

/* Row Styling by trade condition */
.row-buy {
  background: rgba(0, 208, 132, 0.03);
}
.row-buy:hover {
  background: rgba(0, 208, 132, 0.08);
}

.row-sell {
  background: rgba(255, 59, 86, 0.03);
}
.row-sell:hover {
  background: rgba(255, 59, 86, 0.08);
}

.row-block {
  background: rgba(255, 184, 0, 0.08) !important;
  border-left: 3px solid var(--gold-block);
}

.side-badge {
  font-size: 0.62rem;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  display: inline-block;
}

.badge-buy {
  background: var(--green-bid-bg);
  color: var(--green-bid);
}

.badge-sell {
  background: var(--red-ask-bg);
  color: var(--red-ask);
}

.badge-mid {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.block-badge {
  color: var(--gold-block);
  font-size: 0.8rem;
  margin-left: 2px;
}

.color-gold-glow {
  color: #fde047;
  text-shadow: 0 0 6px var(--gold-glow);
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-size: 0.8rem;
  padding: 40px 0;
}

/* Quick slide down animation for new ticks */
.tick-list-enter-active {
  transition: all 0.2s ease-out;
}
.tick-list-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

.font-bold { font-weight: 700; }
.color-green { color: var(--green-bid); }
.color-red { color: var(--red-ask); }
.text-muted { color: var(--text-muted); }
.text-primary { color: var(--text-primary); }
</style>
