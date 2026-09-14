<template>
  <ScannerTable 
    :results="sortedResults" 
    @select-symbol="handleSelectSymbol"
  />
</template>

<script setup>
import { computed } from 'vue';
import { useMarketStore } from '../stores/marketStore';
import ScannerTable from './ScannerTable.vue';

const store = useMarketStore();
const emit = defineEmits(['trade']);

const sortedResults = computed(() => {
  if (!store.scannerResults) return [];
  // Sort descending by score. If scores are equal or undefined, fallback to changePercent
  return [...store.scannerResults].sort((a, b) => {
    const scoreA = a.score || 0;
    const scoreB = b.score || 0;
    if (scoreB !== scoreA) {
      return scoreB - scoreA;
    }
    const pctA = a.changePercent === "--" ? 0 : Number(a.changePercent) || 0;
    const pctB = b.changePercent === "--" ? 0 : Number(b.changePercent) || 0;
    return pctB - pctA;
  });
});

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
}
</style>
