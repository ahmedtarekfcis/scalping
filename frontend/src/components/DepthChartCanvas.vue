<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const store = useMarketStore();
const canvasRef = ref(null);
let animationFrameId = null;

function renderDepthChart() {
  const canvas = canvasRef.value;
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;

  // Handle high-DPI crisp rendering
  if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
  }

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  const bids = store.bids;
  const asks = store.asks;

  if (bids.length === 0 || asks.length === 0) {
    // Empty state text
    ctx.fillStyle = '#64748b';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Depth Visualization Loading...', width / 2, height / 2);
    ctx.restore();
    return;
  }

  const maxTotal = store.maxCumulativeDepth || 1;
  const midX = width / 2;
  const paddingBottom = 15;
  const chartHeight = height - paddingBottom;

  // 1. Draw Mid Center Line
  ctx.strokeStyle = '#202b3d';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(midX, 0);
  ctx.lineTo(midX, chartHeight);
  ctx.stroke();
  ctx.setLineDash([]);

  // 2. Draw Bids Wall (Left Half)
  ctx.beginPath();
  ctx.moveTo(midX, chartHeight);

  // Traverse bids from closest to mid to lowest
  const bidPoints = bids.map((b, i) => {
    const x = midX - ((i + 1) / bids.length) * (midX - 10);
    const y = chartHeight - (b.total / maxTotal) * (chartHeight * 0.88);
    return { x, y, price: b.price };
  });

  if (bidPoints.length > 0) {
    ctx.lineTo(midX, bidPoints[0].y);
    for (let pt of bidPoints) {
      ctx.lineTo(pt.x, pt.y);
    }
    ctx.lineTo(bidPoints[bidPoints.length - 1].x, chartHeight);
  }
  ctx.closePath();

  // Green gradient fill for bids
  const bidGrad = ctx.createLinearGradient(0, 0, 0, chartHeight);
  bidGrad.addColorStop(0, 'rgba(0, 208, 132, 0.45)');
  bidGrad.addColorStop(1, 'rgba(0, 208, 132, 0.03)');
  ctx.fillStyle = bidGrad;
  ctx.fill();

  // Bid Stroke Line
  ctx.strokeStyle = '#00d084';
  ctx.lineWidth = 2;
  ctx.stroke();

  // 3. Draw Asks Wall (Right Half)
  ctx.beginPath();
  ctx.moveTo(midX, chartHeight);

  const askPoints = asks.map((a, i) => {
    const x = midX + ((i + 1) / asks.length) * (midX - 10);
    const y = chartHeight - (a.total / maxTotal) * (chartHeight * 0.88);
    return { x, y, price: a.price };
  });

  if (askPoints.length > 0) {
    ctx.lineTo(midX, askPoints[0].y);
    for (let pt of askPoints) {
      ctx.lineTo(pt.x, pt.y);
    }
    ctx.lineTo(askPoints[askPoints.length - 1].x, chartHeight);
  }
  ctx.closePath();

  // Red gradient fill for asks
  const askGrad = ctx.createLinearGradient(0, 0, 0, chartHeight);
  askGrad.addColorStop(0, 'rgba(255, 59, 86, 0.45)');
  askGrad.addColorStop(1, 'rgba(255, 59, 86, 0.03)');
  ctx.fillStyle = askGrad;
  ctx.fill();

  // Ask Stroke Line
  ctx.strokeStyle = '#ff3b56';
  ctx.lineWidth = 2;
  ctx.stroke();

  // 4. Draw Mid Price Label
  ctx.fillStyle = '#f0f4f8';
  ctx.font = 'bold 11px JetBrains Mono, monospace';
  ctx.textAlign = 'center';
  ctx.fillText(`MID $${store.lastPrice.toFixed(2)}`, midX, height - 2);

  ctx.restore();
}

function startLoop() {
  function frame() {
    renderDepthChart();
    animationFrameId = requestAnimationFrame(frame);
  }
  animationFrameId = requestAnimationFrame(frame);
}

onMounted(() => {
  startLoop();
  window.addEventListener('resize', renderDepthChart);
});

onUnmounted(() => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  window.removeEventListener('resize', renderDepthChart);
});
</script>

<template>
  <div class="depth-chart-card glass-panel">
    <div class="chart-header">
      <span class="chart-title">VISUAL ORDER BOOK DEPTH</span>
      <div class="legend mono">
        <span class="legend-bid"><span class="dot-bid"></span> Bids (Buy Wall)</span>
        <span class="legend-ask"><span class="dot-ask"></span> Asks (Sell Wall)</span>
      </div>
    </div>

    <div class="canvas-container">
      <canvas ref="canvasRef"></canvas>
    </div>
  </div>
</template>

<style scoped>
.depth-chart-card {
  display: flex;
  flex-direction: column;
  height: 180px;
  padding: 12px 14px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.chart-title {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
}

.legend {
  display: flex;
  gap: 12px;
  font-size: 0.68rem;
}

.legend-bid {
  color: var(--green-bid);
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-ask {
  color: var(--red-ask);
  display: flex;
  align-items: center;
  gap: 4px;
}

.dot-bid {
  width: 6px;
  height: 6px;
  background: var(--green-bid);
  border-radius: 50%;
}

.dot-ask {
  width: 6px;
  height: 6px;
  background: var(--red-ask);
  border-radius: 50%;
}

.canvas-container {
  flex: 1;
  position: relative;
  width: 100%;
}

canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
