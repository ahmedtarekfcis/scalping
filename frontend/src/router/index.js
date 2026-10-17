import { createRouter, createWebHistory } from 'vue-router';
import DashboardView from '../views/DashboardView.vue';
import ScannerView from '../scanner/ScannerView.vue';
import TradeStatsView from '../views/TradeStatsView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView
    },
    {
      path: '/scanner',
      name: 'scanner',
      component: ScannerView
    },
    {
      path: '/trade-stats',
      name: 'trade-stats',
      component: TradeStatsView
    },
    {
      path: '/chart',
      name: 'chart',
      component: () => import('../views/chart/ChartView.vue')
    }
  ]
});

export default router;
