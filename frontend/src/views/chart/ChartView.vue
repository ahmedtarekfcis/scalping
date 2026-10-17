<template>
  <div class="chart-container-wrapper">
    <div class="chart-header">
      <h2 class="chart-title">{{ symbol }} - TradingView Lightweight Chart</h2>
      <div class="chart-controls">
        <button @click="toggleEMA" :class="{ active: showEMA }">9 EMA</button>
        <button @click="toggleVWAP" :class="{ active: showVWAP }">VWAP</button>
        <button @click="toggleResistance" :class="{ active: showResistance }">Auto Resistance</button>
      </div>
    </div>
    <div v-if="store.historicalError" class="chart-error">
      ⚠ {{ store.historicalError }}
    </div>
    <div ref="chartContainer" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import { CandlestickSeries, LineSeries, createChart } from 'lightweight-charts';
import { useMarketStore } from '../../stores/marketStore';

const chartContainer = ref(null);
const store = useMarketStore();
const symbol = computed(() => store.symbol || 'No Symbol Selected');

let chart = null;
let candleSeries = null;
let resizeObserver = null;
let emaSeries = null;
let vwapSeries = null;
let resistanceLines = [];

const showEMA = ref(true);
const showVWAP = ref(true);
const showResistance = ref(true);

// Generate Mock Data
function generateData(basePrice = 100) {
  const data = [];
  let time = new Date('2023-01-01T09:30:00Z').getTime() / 1000;
  let close = basePrice;
  
  for (let i = 0; i < 500; i++) {
    const open = close + (Math.random() - 0.5) * 2;
    const high = Math.max(open, close) + Math.random() * 2;
    const low = Math.min(open, close) - Math.random() * 2;
    close = open + (Math.random() - 0.5) * 2;
    const volume = Math.floor(Math.random() * 10000) + 1000;
    
    data.push({ time, open, high, low, close, volume });
    time += 60; // 1 minute candles
  }
  return data;
}

// Calculate EMA
function calculateEMA(data, period) {
  const k = 2 / (period + 1);
  const emaData = [];
  let ema = data[0].close;
  
  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      ema = data[i].close;
    } else {
      ema = (data[i].close - ema) * k + ema;
    }
    emaData.push({ time: data[i].time, value: ema });
  }
  return emaData;
}

// Calculate VWAP
function calculateVWAP(data) {
  const vwapData = [];
  let cumulativeTPV = 0;
  let cumulativeVolume = 0;
  
  for (let i = 0; i < data.length; i++) {
    const tp = (data[i].high + data[i].low + data[i].close) / 3;
    cumulativeTPV += tp * data[i].volume;
    cumulativeVolume += data[i].volume;
    vwapData.push({ time: data[i].time, value: cumulativeTPV / cumulativeVolume });
  }
  return vwapData;
}

// Find Resistance (Swing Highs)
function findResistances(data) {
  const lines = [];
  for (let i = 2; i < data.length - 2; i++) {
    const currentHigh = data[i].high;
    if (
      currentHigh > data[i - 1].high &&
      currentHigh > data[i - 2].high &&
      currentHigh > data[i + 1].high &&
      currentHigh > data[i + 2].high
    ) {
      // It's a local top
      lines.push(currentHigh);
    }
  }
  // Take top 3 unique resistance levels
  const uniqueLines = [...new Set(lines)].sort((a, b) => b - a).slice(0, 3);
  return uniqueLines;
}

function initChart() {
  if (!chartContainer.value) return;

  chart = createChart(chartContainer.value, {
    layout: {
      background: { color: '#0f172a' },
      textColor: '#94a3b8',
    },
    grid: {
      vertLines: { color: '#1e293b' },
      horzLines: { color: '#1e293b' },
    },
    crosshair: {
      mode: 0,
    },
    timeScale: {
      timeVisible: true,
      secondsVisible: false,
    },
  });

  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: '#00d084',
    downColor: '#ff3b56',
    borderVisible: false,
    wickUpColor: '#00d084',
    wickDownColor: '#ff3b56',
  });

  emaSeries = chart.addSeries(LineSeries, {
    color: '#facc15',
    lineWidth: 2,
    title: '9 EMA',
  });

  vwapSeries = chart.addSeries(LineSeries, {
    color: '#38bdf8',
    lineWidth: 2,
    title: 'VWAP',
  });

  updateChartData(store.lastPrice || 100);
}

function updateChartData(basePrice = 100) {
  if (!candleSeries || !emaSeries || !vwapSeries) return;
  
  const rawData = generateData(basePrice);
  
  candleSeries.setData(rawData.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));
  
  const emaData = calculateEMA(rawData, 9);
  emaSeries.setData(emaData);
  
  const vwapData = calculateVWAP(rawData);
  vwapSeries.setData(vwapData);

  drawResistances(rawData);

}

function drawResistances(data) {
  clearResistances();
  if (!showResistance.value) return;
  
  const levels = findResistances(data);
  levels.forEach(level => {
    const priceLine = candleSeries.createPriceLine({
      price: level,
      color: '#ef4444',
      lineWidth: 1,
      lineStyle: 2, // Dashed
      axisLabelVisible: true,
      title: 'Res',
    });
    resistanceLines.push(priceLine);
  });
}

function clearResistances() {
  resistanceLines.forEach(line => candleSeries.removePriceLine(line));
  resistanceLines = [];
}



function toggleEMA() {
  showEMA.value = !showEMA.value;
  emaSeries.applyOptions({ visible: showEMA.value });
}

function toggleVWAP() {
  showVWAP.value = !showVWAP.value;
  vwapSeries.applyOptions({ visible: showVWAP.value });
}

function toggleResistance() {
  showResistance.value = !showResistance.value;
  if (showResistance.value) {
    const currentBasePrice = store.lastPrice || 100;
    const dataToUse = (store.historicalData && store.historicalData.length > 0) ? store.historicalData : generateData(currentBasePrice);
    drawResistances(dataToUse);
  } else {
    clearResistances();
  }
}

onMounted(() => {
  initChart();
  
  watch(() => store.symbol, () => {
    updateChartData(store.lastPrice || 100);
  });
  
  watch(() => store.lastPrice, (newPrice, oldPrice) => {
    if (newPrice && !oldPrice) {
      updateChartData(newPrice);
    }
  });
  
  watch(() => store.historicalData, (newData) => {
    if (newData && newData.length > 0) {
      try {
        applyDataToSeries(newData);
      } catch (err) {
        console.error("Lightweight Charts Error:", err);
      }
    }
  });
  
  if (chartContainer.value) {
    resizeObserver = new ResizeObserver(entries => {
      if (entries.length === 0 || entries[0].target !== chartContainer.value) { return; }
      const newRect = entries[0].contentRect;
      chart.applyOptions({ height: newRect.height, width: newRect.width });
    });
    resizeObserver.observe(chartContainer.value);
  }
});

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect();
  if (chart) {
    chart.remove();
  }
});
</script>

<style scoped>
.chart-container-wrapper {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--bg-primary, #0f172a);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color, #1e293b);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-secondary, #1e293b);
  border-bottom: 1px solid var(--border-color, #334155);
}

.chart-title {
  margin: 0;
  font-size: 16px;
  color: #f8fafc;
  font-weight: 700;
}

.chart-error {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  border-bottom: 1px solid rgba(239, 68, 68, 0.2);
}

.chart-controls {
  display: flex;
  gap: 8px;
}

.chart-controls button {
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.chart-controls button:hover {
  background: #334155;
  color: #f8fafc;
}

.chart-controls button.active {
  background: #38bdf8;
  color: #0f172a;
  border-color: #38bdf8;
  font-weight: 600;
}

.chart-container {
  flex: 1;
  width: 100%;
  min-height: 0; /* Important for flex children to allow shrinking */
}
</style>
