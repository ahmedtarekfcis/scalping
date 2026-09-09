import { defineStore } from 'pinia';

export const useMarketStore = defineStore('market', {
  state: () => ({
    symbol: '',
    isLoading: false,
    status: {
      connected: false,
      activeSymbol: null,
      host: '127.0.0.1',
      port: 4002,
      clientId: 1,
      error: null
    },
    // Level 2 Order Book
    bids: [], // [{ price, size, marketMaker, ordersCount, total, percent }]
    asks: [], // [{ price, size, marketMaker, ordersCount, total, percent }]
    maxCumulativeDepth: 1,
    bidTotalVolume: 0,
    askTotalVolume: 0,
    bidRatio: 50,
    askRatio: 50,
    spread: 0,
    spreadPct: 0,
    
    // Header Stats
    lastPrice: null,
    prevPrice: null,
    priceDirection: 'neutral', // 'up' | 'down' | 'neutral'
    change: null,
    changePercent: null,
    volume: null,
    high: null,
    low: null,
    open: null,
    
    // Time & Sales (Tape)
    tape: [], // Max 30 elements rolling
    maxTapeLength: 30,
    tapeMinSize: 0, // Default no size filter
    
    // Market Intelligence
    intelligence: {
      vwap: null,
      ema_9: null,
      ema_21: null,
      ema_200: null,
      hod: null,
      lod: null,
      mtf_levels: [],
      bid_walls: [],
      ask_walls: [],
      tape_speed: 0,
      aggressive_buy_vol: 0,
      aggressive_sell_vol: 0,
      ai_evidence: "Awaiting sufficient market data to form a conclusion.",
      signal: null,
      trade_ideas: [],
      surge_prediction: null,
      order_flow_anomaly: null
    },
    
    // Scanner
    scannerResults: [],
    isScanning: false,
    
    // WebSocket
    ws: null,
    wsConnected: false,
    wsError: false,          // True only after grace period expires without reconnect
    wsReconnectTimeout: null,
    wsErrorTimeout: null,    // Grace period timer before showing error overlay
    wsReconnectDelay: 1000,  // Start at 1s, backoff up to 15s
    wsReconnectAttempts: 0,
    
    // UI Settings
    visibleLevels: 100, // Show up to 100 rows all the time
    showMMID: true,
    showOrdersCount: true
  }),

  getters: {
    displayedBids: (state) => state.bids.slice(0, 100),
    displayedAsks: (state) => state.asks.slice(0, 100),
    isPositiveChange: (state) => state.change >= 0,
    filteredTape: (state) => state.tape.filter(t => t.size >= Math.max(100, state.tapeMinSize || 100)),
    bestBid: (state) => (state.bids && state.bids.length > 0 ? state.bids[0] : null),
    bestAsk: (state) => (state.asks && state.asks.length > 0 ? state.asks[0] : null),
    lastTrade: (state) => (state.tape && state.tape.length > 0 ? state.tape[0] : null),
    surgePrediction: (state) => {
      const intel = state.intelligence || {};
      const sp = intel.surge_prediction;
      
      const isMissingCriteria = !intel.vwap || !intel.ema_9 || !intel.ema_21 || !intel.ema_200;

      if (isMissingCriteria) {
        return {
          ...(sp || {}),
          direction: 'WAITING_10S_UPTREND',
          catalyst: 'waiting to fulfill critrias',
          target_price: state.lastPrice,
          current_price: state.lastPrice,
          price_delta: 0,
          price_delta_pct: 0,
          confidence: 50,
          speed: 'STEADY',
          meets_bullish_criteria: false,
          meets_bearish_criteria: false
        };
      }

      if (sp) {
        // Strictly enforce ALL bullish criteria (all green/ABOVE)
        if (!sp.meets_bullish_criteria) {
          return {
            ...sp,
            direction: 'WAITING_10S_UPTREND',
            catalyst: 'waiting to fulfill critrias'
          };
        }

        // If actively surging, always pass through
        if (sp.direction === 'SURGING_UP' || sp.direction === 'POTENTIAL_SQUEEZE' || sp.direction === 'MOMENTUM_SURGE') {
          return sp;
        }
        
        if (!sp.is_10s_uptrend) {
          return {
            ...sp,
            direction: 'WAITING_10S_UPTREND',
            catalyst: 'waiting uptrend'
          };
        }
        
        return sp; // Default pass-through if criteria met but not surging
      }
      
      return {
        direction: 'CONSOLIDATING',
        target_price: state.lastPrice,
        current_price: state.lastPrice,
        price_delta: 0,
        price_delta_pct: 0,
        confidence: 50,
        speed: 'STEADY',
        catalyst: 'Awaiting sufficient market data to form a conclusion.',
        meets_bullish_criteria: false,
        meets_bearish_criteria: false
      };
    }
  },

  actions: {
    initWebSocket() {
      if (this.ws) {
        try { this.ws.close(); } catch (e) {}
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/market-data`;

      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.wsConnected = true;
        this.wsError = false;
        this.wsReconnectAttempts = 0;
        this.wsReconnectDelay = 1000;
        // Cancel any pending error overlay timer
        if (this.wsErrorTimeout) {
          clearTimeout(this.wsErrorTimeout);
          this.wsErrorTimeout = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this.handleSocketMessage(payload);
        } catch (err) {
          console.error('WS Parse Error:', err);
        }
      };

      this.ws.onclose = (event) => {
        console.warn(`WebSocket Closed (code: ${event.code}). Reconnecting in ${this.wsReconnectDelay}ms...`);
        this.wsConnected = false;
        this.wsReconnectAttempts++;

        // Only show the error overlay after a 4-second grace period
        // This prevents flicker during normal brief reconnects
        if (!this.wsErrorTimeout) {
          this.wsErrorTimeout = setTimeout(() => {
            if (!this.wsConnected) {
              this.wsError = true;
            }
            this.wsErrorTimeout = null;
          }, 4000);
        }

        clearTimeout(this.wsReconnectTimeout);
        this.wsReconnectTimeout = setTimeout(() => {
          this.initWebSocket();
        }, this.wsReconnectDelay);

        // Exponential backoff: 1s -> 2s -> 4s -> 8s -> 15s max
        this.wsReconnectDelay = Math.min(15000, this.wsReconnectDelay * 2);
      };

      this.ws.onerror = (err) => {
        console.error('WebSocket Error:', err);
      };
    },

    handleSocketMessage(msg) {
      if (!msg || !msg.type) return;

      switch (msg.type) {
        case 'STATUS_UPDATE':
          this.status = { ...this.status, ...msg.data };
          if (msg.data.activeSymbol) {
            this.symbol = msg.data.activeSymbol;
          }
          break;

        case 'L2_UPDATE':
          this.processL2Book(msg.data);
          break;

        case 'TAPE_TICK':
          this.processTapeTick(msg.data);
          break;

        case 'INTELLIGENCE_UPDATE':
          this.intelligence = { ...this.intelligence, ...msg.data };
          break;

        case 'SCANNER_UPDATE':
          this.scannerResults = msg.data || [];
          this.isScanning = false;
          break;

        case 'ERROR':
          console.error("Backend Error:", msg.data.message);
          this.isLoading = false;
          this.intelligence = {
            ...this.intelligence,
            ai_evidence: `ERROR: ${msg.data.message}`,
            surge_prediction: null
          };
          break;
      }
    },

    processL2Book(data) {
      if (!data) return;
      this.isLoading = false;

      if (data.lastPrice !== undefined && data.lastPrice !== null) {
        if (data.lastPrice > this.lastPrice) this.priceDirection = 'up';
        else if (data.lastPrice < this.lastPrice) this.priceDirection = 'down';
        this.prevPrice = this.lastPrice;
        this.lastPrice = data.lastPrice;
      }

      if (data.change !== undefined) this.change = data.change;
      if (data.changePercent !== undefined) this.changePercent = data.changePercent;
      if (data.volume !== undefined) this.volume = data.volume;
      if (data.high !== undefined) this.high = data.high;
      if (data.low !== undefined) this.low = data.low;
      if (data.open !== undefined) this.open = data.open;

      // Calculate baseline average size across the first 100 rows
      const first100Bids = (data.bids || []).slice(0, 100);
      const first100Asks = (data.asks || []).slice(0, 100);
      const allFirst100 = [...first100Bids, ...first100Asks];
      const avgLevelSize = allFirst100.length > 0
        ? (allFirst100.reduce((acc, x) => acc + (x.size || 0), 0) / allFirst100.length)
        : 1000;

      // Wall / Floor threshold: >= 2.2x the average of the first 100 rows or >= 6,000 shares
      const wallThreshold = Math.max(800, avgLevelSize * 2.2);

      // Process Bids Cumulative & Floor detection relative to first 100 rows
      let bidCum = 0;
      const processedBids = (data.bids || []).map((bid) => {
        bidCum += bid.size;
        const relStrength = +(bid.size / Math.max(1, avgLevelSize)).toFixed(1);
        const isFloor = bid.size >= wallThreshold || bid.size >= 6000;
        return {
          ...bid,
          total: bidCum,
          isFloor,
          relativeStrength: relStrength
        };
      });

      // Process Asks Cumulative & Wall detection relative to first 100 rows
      let askCum = 0;
      const processedAsks = (data.asks || []).map((ask) => {
        askCum += ask.size;
        const relStrength = +(ask.size / Math.max(1, avgLevelSize)).toFixed(1);
        const isWall = ask.size >= wallThreshold || ask.size >= 6000;
        return {
          ...ask,
          total: askCum,
          isWall,
          relativeStrength: relStrength
        };
      });

      this.bidTotalVolume = bidCum;
      this.askTotalVolume = askCum;

      const totalVol = bidCum + askCum;
      if (totalVol > 0) {
        this.bidRatio = Math.round((bidCum / totalVol) * 100);
        this.askRatio = 100 - this.bidRatio;
      }

      const maxDepth = Math.max(bidCum, askCum, 1);
      this.maxCumulativeDepth = maxDepth;

      // Calculate depth bar percentages for Webull-style inline bars
      this.bids = processedBids.map((b) => ({
        ...b,
        percent: Math.min(100, (b.total / maxDepth) * 100)
      }));

      this.asks = processedAsks.map((a) => ({
        ...a,
        percent: Math.min(100, (a.total / maxDepth) * 100)
      }));

      // Calculate spread
      if (this.bids.length > 0 && this.asks.length > 0) {
        this.spread = Math.max(0, +(this.asks[0].price - this.bids[0].price).toFixed(2));
        this.spreadPct = this.lastPrice ? +((this.spread / this.lastPrice) * 100).toFixed(3) : 0;
      }
    },

    processTapeTick(tick) {
      if (!tick) return;

      // 1. Size Filtering: Filter out and do not display any individual trades smaller than 100 shares
      if (tick.size < 100) return;

      // 2. Trade Aggregation: Group consecutive trades that occur at the exact same price within the same millisecond timestamp
      if (this.tape.length > 0) {
        const prev = this.tape[0];
        if (
          prev.time === tick.time &&
          prev.price === tick.price &&
          prev.side === tick.side
        ) {
          prev.size += tick.size;
          prev.orderCount = (prev.orderCount || 1) + (tick.orderCount || 1);
          prev.isBlockTrade = prev.size >= 2000;
          prev.aggregated = true;
          return;
        }
      }

      // Prepend new trade
      this.tape.unshift({
        ...tick,
        id: `${tick.timestamp || Date.now()}-${Math.random()}`,
        orderCount: tick.orderCount || 1,
        isBlockTrade: tick.size >= 2000
      });

      if (this.tape.length > this.maxTapeLength) {
        this.tape.pop();
      }
    },

    changeSymbol(newSymbol) {
      if (!newSymbol) return;
      const sym = newSymbol.toUpperCase().trim();
      this.symbol = sym;
      this.isLoading = true;
      
      // Clear all previous data
      this.bids = [];
      this.asks = [];
      this.tape = [];
      this.lastPrice = null;
      this.prevPrice = null;
      this.change = null;
      this.changePercent = null;
      this.volume = null;
      this.high = null;
      this.low = null;
      this.open = null;
      this.intelligence = {
        vwap: null,
        ema_9: null,
        ema_21: null,
        ema_200: null,
        hod: null,
        lod: null,
        mtf_levels: [],
        bid_walls: [],
        ask_walls: [],
        tape_speed: 0,
        aggressive_buy_vol: 0,
        aggressive_sell_vol: 0,
        ai_evidence: "Awaiting sufficient market data to form a conclusion.",
        signal: null,
        trade_ideas: [],
        surge_prediction: null,
        order_flow_anomaly: null
      };

      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'SUBSCRIBE', symbol: sym }));
      }
    },

    refetchCriteria() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.symbol) {
        this.ws.send(JSON.stringify({ action: 'REFETCH_CRITERIA', symbol: this.symbol }));
      }
    },

    refetchMtf() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.symbol) {
        this.ws.send(JSON.stringify({ action: 'REFETCH_MTF', symbol: this.symbol }));
      }
    },

    scanMarket(isBackground = false) {
      if (!isBackground) {
        this.isScanning = true;
      }
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'SCAN' }));
      }
    },

    connectIBKR(config) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'CONNECT', config }));
      }
    }
  }
});
