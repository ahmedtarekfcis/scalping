<template>
  <div class="orderbook-panel glass-panel">
    <!-- Dual Columns (Bids Left, Asks Right) - No Level 2 Title, 100 Rows Max -->
    <div class="book-container mono">
      <!-- BIDS TABLE -->
      <div class="book-half bids-half">
        <div class="table-header bid-th">
          <span class="col-size">SIZE</span>
          <span class="col-price">BID</span>
        </div>

        <div class="table-body">
          <div 
            v-for="(row, idx) in store.displayedBids" 
            :key="'bid-' + row.price + '-' + idx"
            class="book-row bid-row"
            :class="{ 'row-floor-highlight': row.isFloor, 'big-wall': row.size >= 10000 }"
          >
            <!-- Inline Cumulative Depth Fill Bar (Right aligned) -->
            <div 
              class="depth-bar bid-depth-bar" 
              :style="{ width: `${row.percent}%` }"
            ></div>

            <div class="row-content bid-row-content">
              <span 
                class="col-size" 
                :class="[
                  row.isFloor ? 'text-yellow-glow font-bold' : (row.size >= 10000 ? 'text-gold' : '')
                ]"
              >
                <span v-if="row.isFloor" class="wall-floor-chip floor-chip" :title="`Floor detected: ${row.relativeStrength}x average of first 100 rows`">
                  FLOOR
                </span>
                {{ formatNum(row.size) }}
              </span>
              <span class="col-price text-green font-bold">{{ row.price.toFixed(2) }}</span>
            </div>
          </div>

          <div v-if="store.displayedBids.length === 0" class="empty-state">
            Waiting for Bid data...
          </div>
        </div>
      </div>

      <!-- ASKS TABLE -->
      <div class="book-half asks-half">
        <div class="table-header ask-th">
          <span class="col-price">ASK</span>
          <span class="col-size">SIZE</span>
        </div>

        <div class="table-body">
          <div 
            v-for="(row, idx) in store.displayedAsks" 
            :key="'ask-' + row.price + '-' + idx"
            class="book-row ask-row"
            :class="{ 'row-wall-highlight': row.isWall, 'big-wall': row.size >= 10000 }"
          >
            <!-- Inline Cumulative Depth Fill Bar (Left aligned) -->
            <div 
              class="depth-bar ask-depth-bar" 
              :style="{ width: `${row.percent}%` }"
            ></div>

            <div class="row-content ask-row-content">
              <span class="col-price text-red font-bold">{{ row.price.toFixed(2) }}</span>
              <span 
                class="col-size" 
                :class="[
                  row.isWall ? 'text-yellow-glow font-bold' : (row.size >= 10000 ? 'text-gold' : '')
                ]"
              >
                <span v-if="row.isWall" class="wall-floor-chip wall-chip" :title="`Wall detected: ${row.relativeStrength}x average of first 100 rows`">
                  WALL
                </span>
                {{ formatNum(row.size) }}
              </span>
            </div>
          </div>

          <div v-if="store.displayedAsks.length === 0" class="empty-state">
            Waiting for Ask data...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();

function formatNum(num) {
  if (num === undefined || num === null) return '0';
  return num.toLocaleString();
}
</script>

<style scoped>
.orderbook-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  border-radius: 8px;
  background: rgba(13, 17, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.book-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  height: 100%;
}

.book-half {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.bids-half {
  border-right: 1px solid var(--border-color);
}

.table-header {
  display: flex;
  padding: 8px 16px;
  height: 42px;
  box-sizing: border-box;
  font-size: 12.5px;
  font-weight: 800;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(10, 13, 20, 0.75);
  flex-shrink: 0;
  align-items: center;
}

.bid-th {
  justify-content: space-between;
}

.ask-th {
  justify-content: space-between;
}

.table-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.book-row {
  position: relative;
  height: 32px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.025);
  transition: background-color 0.15s ease;
}

.book-row:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.big-wall {
  border-left: 3px solid var(--gold-block);
}

.depth-bar {
  position: absolute;
  top: 1px;
  bottom: 1px;
  pointer-events: none;
  transition: width 0.15s ease;
}

.bid-depth-bar {
  left: 0;
  background: var(--green-bid-bar);
  border-right: 2px solid rgba(0, 208, 132, 0.45);
}

.ask-depth-bar {
  right: 0;
  background: var(--red-ask-bar);
  border-left: 2px solid rgba(255, 59, 86, 0.45);
}

.row-content {
  position: relative;
  z-index: 2;
  display: flex;
  width: 100%;
  padding: 0 16px;
  align-items: center;
}

.bid-row-content {
  justify-content: space-between;
}

.ask-row-content {
  justify-content: space-between;
}

.col-size {
  font-size: 15px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 5px;
}

.col-price {
  font-size: 15.5px;
  font-weight: 800;
}

.text-green { color: var(--green-bid); }
.text-red { color: var(--red-ask); }
.text-gold { color: var(--gold-block); font-weight: 800; }
.text-yellow-glow {
  color: #facc15 !important;
  text-shadow: 0 0 10px rgba(250, 204, 21, 0.5);
  font-weight: 800;
}
.text-muted { color: var(--text-muted); }
.font-bold { font-weight: 700; }

.wall-floor-chip {
  display: inline-block;
  font-size: 9px;
  font-weight: 900;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.4px;
}

.floor-chip {
  background: rgba(250, 204, 21, 0.22);
  color: #facc15;
  border: 1px solid rgba(250, 204, 21, 0.5);
}

.wall-chip {
  background: rgba(250, 204, 21, 0.22);
  color: #facc15;
  border: 1px solid rgba(250, 204, 21, 0.5);
}

.row-floor-highlight {
  background: rgba(250, 204, 21, 0.1) !important;
  border-left: 3px solid #facc15 !important;
}

.row-wall-highlight {
  background: rgba(250, 204, 21, 0.1) !important;
  border-right: 3px solid #facc15 !important;
}

.empty-state {
  padding: 30px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}
</style>
