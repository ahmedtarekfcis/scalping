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
    medianLevelSize: 100,
    
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
    currentMinIndex: -1,
    currentVol1m: 0,
    
    // No intelligence state needed
    
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
    showOrdersCount: true,

    // Absorption Watcher
    // Each entry: { side, initialSize, peakSize, currentSize,
    //               vol15s, vol15sPrints, prints15s, alertFired }
    trackedWhales: {},

    // ── SCORECARD ENGINE ──────────────────────────────────────────────────────
    // All signals use a unified 15-second rolling window.
    scorecard: {
      total: 0,            // -100..+100 composite
      l2Imbalance: 0,      // L2 depth signal       (max ±15)
      tapeDelta15s: 0,     // 15s lit tape vol delta (max ±25)
      tapePressure15s: 0,  // 15s lit tape count     (max ±20)
      whaleAbsorption: 0,  // Whale eating           (max ±30)
      roundFigureCtx: 0,   // Round figure context   (max ±10)
      darkPool: 0,         // Dark pool / DP monitor (max ±8)
      signals: []          // [{label, score, type}] sorted by |score| desc
    },
    // Single 15-second rolling window — lit market tape
    tapeRolling: {
      buy15s:  [],  // {size, ts}  — lit-market BUY  prints, last 15s
      sell15s: []   // {size, ts}  — lit-market SELL prints, last 15s
    },
    // Dark pool / TRF / ADF rolling window — monitored separately
    // Informed dark pool flow is a directional signal even though it doesn't
    // trigger the lit-book absorption confirmation.
    dpRolling: {
      buy15s:  [],  // {size, ts}  — dark-pool BUY  prints, last 15s
      sell15s: []   // {size, ts}  — dark-pool SELL prints, last 15s
    }
    // ─────────────────────────────────────────────────────────────────────────
  }),

  getters: {
    displayedBids: (state) => state.bids.slice(0, 100),
    displayedAsks: (state) => state.asks.slice(0, 100),
    isPositiveChange: (state) => state.change >= 0,
    filteredTape: (state) => state.tape.filter(t => t.size >= Math.max(100, state.tapeMinSize || 100)),
    bestBid: (state) => (state.bids && state.bids.length > 0 ? state.bids[0] : null),
    bestAsk: (state) => (state.asks && state.asks.length > 0 ? state.asks[0] : null),
    lastTrade: (state) => (state.tape && state.tape.length > 0 ? state.tape[0] : null),

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

        case 'SCANNER_UPDATE':
          this.scannerResults = msg.data || [];
          this.isScanning = false;
          break;

        case 'ERROR':
          console.error("Backend Error:", msg.data.message);
          this.isLoading = false;
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

      // Calculate baseline median size across the first 100 rows
      const first100Bids = (data.bids || []).slice(0, 100);
      const first100Asks = (data.asks || []).slice(0, 100);
      const allFirst100 = [...first100Bids, ...first100Asks];
      
      let medianSize = 100;
      if (allFirst100.length > 0) {
        const allSizes = allFirst100.map(x => x.size || 0).sort((a, b) => a - b);
        const mid = Math.floor(allSizes.length / 2);
        medianSize = allSizes.length % 2 === 0 ? (allSizes[mid - 1] + allSizes[mid]) / 2 : allSizes[mid];
      }
      this.medianLevelSize = Math.max(10, medianSize); // Avoid zero, minimum 10

      // ---- ROUND FIGURE DETECTOR ----
      // Returns null | { level: 'minor'|'major'|'key', label: string }
      // Step sizes scale with price so a $2 stock flags $0.05 levels (not $0.50)
      const getRoundFigureInfo = (price) => {
        if (!price || price <= 0) return null;

        let minorStep, majorStep, keyStep;
        if (price < 1) {
          minorStep = 0.05;  majorStep = 0.10;  keyStep = 0.25;
        } else if (price < 5) {
          minorStep = 0.05;  majorStep = 0.50;  keyStep = 1.00;
        } else if (price < 20) {
          minorStep = 0.25;  majorStep = 1.00;  keyStep = 5.00;
        } else if (price < 50) {
          minorStep = 0.50;  majorStep = 2.50;  keyStep = 5.00;
        } else if (price < 100) {
          minorStep = 1.00;  majorStep = 5.00;  keyStep = 10.00;
        } else if (price < 200) {
          minorStep = 2.50;  majorStep = 10.00; keyStep = 25.00;
        } else {
          minorStep = 5.00;  majorStep = 25.00; keyStep = 50.00;
        }

        // 0.5-cent tolerance for floating-point prices
        const eps = 0.005;
        const near = (p, step) => Math.abs(Math.round(p / step) * step - p) < eps;

        if (near(price, keyStep))   return { level: 'key',   step: keyStep   };
        if (near(price, majorStep)) return { level: 'major', step: majorStep };
        if (near(price, minorStep)) return { level: 'minor', step: minorStep };
        return null;
      };
      // --------------------------------

      // Process Bids Cumulative & Floor detection relative to median
      let bidCum = 0;
      const processedBids = (data.bids || []).map((bid) => {
        bidCum += bid.size;
        return {
          ...bid,
          total: bidCum,
          hasBorder: bid.size >= this.medianLevelSize * 3,
          hasIcon:   bid.size >= this.medianLevelSize * 6,
          roundFigure: getRoundFigureInfo(bid.price)
        };
      });

      // Process Asks Cumulative & Wall detection relative to median
      let askCum = 0;
      const processedAsks = (data.asks || []).map((ask) => {
        askCum += ask.size;
        return {
          ...ask,
          total: askCum,
          hasBorder: ask.size >= this.medianLevelSize * 3,
          hasIcon:   ask.size >= this.medianLevelSize * 6,
          roundFigure: getRoundFigureInfo(ask.price)
        };
      });

      // --- ABSORPTION WATCHER (Multi-Confirmation, 15s unified frame) ---
      // Needs: (1) L2 shrinkage ≥15%, (2) ≥2 aggressor prints in 15s, (3) vol ≥40% in 15s
      const currentWhales = {};

      processedBids.forEach(bid => {
        if (bid.hasIcon) currentWhales[bid.price] = { price: bid.price, side: 'BID', size: bid.size };
      });
      processedAsks.forEach(ask => {
        if (ask.hasIcon) currentWhales[ask.price] = { price: ask.price, side: 'ASK', size: ask.size };
      });

      const now15s = Date.now();
      const CUTOFF_15S = 15000;

      // Update existing tracked whales from new L2 snapshot
      for (const price in this.trackedWhales) {
        const whale = this.trackedWhales[price];
        const newWhale = currentWhales[price];

        if (newWhale) {
          // Keep track of peak size (whale may reload)
          if (newWhale.size > whale.peakSize) whale.peakSize = newWhale.size;
          whale.currentSize = newWhale.size;

          // Prune the unified 15s window
          whale.prints15s   = (whale.prints15s   || []).filter(p => now15s - p.ts <= CUTOFF_15S);
          whale.vol15sPrints = (whale.vol15sPrints || []).filter(p => now15s - p.ts <= CUTOFF_15S);
          whale.vol15s = whale.vol15sPrints.reduce((acc, p) => acc + p.size, 0);

          // ---- MULTI-CONFIRMATION CHECK (single 15s frame) ----
          // Cond 1: L2 has actually shrunk ≥20% from peak (real absorption, not spoof)
          const shrinkPct = whale.peakSize > 0 ? (whale.peakSize - whale.currentSize) / whale.peakSize : 0;
          const cond1_l2Shrinkage = shrinkPct >= 0.20;

          // Cond 2: ≥3 aggressor prints in the last 15s (active current pressure)
          const cond2_15sPressure = (whale.prints15s || []).length >= 3;

          // Cond 3: 15s cumulative aggressor volume ≥50% of initial size
          const cond3_15sVol = whale.vol15s >= whale.initialSize * 0.50;

          // Cond 4: Trend Confirmation (Global 15s tape volume heavily favors the break)
          const validBuy15s = (this.tapeRolling.buy15s || []).filter(p => now15s - p.ts <= CUTOFF_15S);
          const validSell15s = (this.tapeRolling.sell15s || []).filter(p => now15s - p.ts <= CUTOFF_15S);
          const tapeBuyVol15s = validBuy15s.reduce((a, b) => a + b.size, 0);
          const tapeSellVol15s = validSell15s.reduce((a, b) => a + b.size, 0);
          const tapeTotalVol15s = tapeBuyVol15s + tapeSellVol15s;
          let cond4_trendConfirmed = false;

          // Trend must be clear (>=60% favoring the break)
          if (tapeTotalVol15s > 0) { 
            if (whale.side === 'BID') { // Breaking bid -> sellers dominate
              cond4_trendConfirmed = (tapeSellVol15s / tapeTotalVol15s) >= 0.60;
            } else if (whale.side === 'ASK') { // Breaking ask -> buyers dominate
              cond4_trendConfirmed = (tapeBuyVol15s / tapeTotalVol15s) >= 0.60;
            }
          }

          if (cond1_l2Shrinkage && cond2_15sPressure && cond3_15sVol && cond4_trendConfirmed && !whale.alertFired) {
            whale.alertFired = true;
            this.playWhaleEatenSound(whale.side);
          }

          // Reset alert if whale reloads significantly
          if (newWhale.size > whale.peakSize * 1.3) {
            whale.alertFired = false;
          }
        } else {
          // Whale dropped off the book entirely — check 15s vol fallback
          if (whale.alertFired === false) {
            whale.vol15sPrints = (whale.vol15sPrints || []).filter(p => now15s - p.ts <= CUTOFF_15S);
            whale.vol15s = whale.vol15sPrints.reduce((acc, p) => acc + p.size, 0);
            
            // Check trend to ensure it was eaten, not just pulled during consolidation
            const validBuy15s = (this.tapeRolling.buy15s || []).filter(p => now15s - p.ts <= CUTOFF_15S);
            const validSell15s = (this.tapeRolling.sell15s || []).filter(p => now15s - p.ts <= CUTOFF_15S);
            const tSellVol = validSell15s.reduce((a, b) => a + b.size, 0);
            const tBuyVol = validBuy15s.reduce((a, b) => a + b.size, 0);
            const tTotalVol = tSellVol + tBuyVol;
            let trendConfirmed = false;
            
            if (tTotalVol > 0) {
              if (whale.side === 'BID') trendConfirmed = (tSellVol / tTotalVol) >= 0.60;
              else if (whale.side === 'ASK') trendConfirmed = (tBuyVol / tTotalVol) >= 0.60;
            }

            // Disappeared with ≥70% of its size hit in last 15s AND trend is confirmed = fully eaten
            if (whale.vol15s >= whale.initialSize * 0.70 && trendConfirmed) {
              this.playWhaleEatenSound(whale.side);
            }
          }
          delete this.trackedWhales[price];
        }
      }

      // Register newly appearing whale levels
      for (const price in currentWhales) {
        if (!this.trackedWhales[price]) {
          this.trackedWhales[price] = {
            side: currentWhales[price].side,
            initialSize: currentWhales[price].size,
            peakSize: currentWhales[price].size,
            currentSize: currentWhales[price].size,
            vol15s: 0,
            vol15sPrints: [],  // { size, ts } — 15s aggressor volume
            prints15s: [],     // { size, ts } — 15s print count
            alertFired: false
          };
        }
      }
      // -----------------------------------------------

      this.bidTotalVolume = bidCum;
      this.askTotalVolume = askCum;

      const totalVol = bidCum + askCum;
      if (totalVol > 0) {
        this.bidRatio = Math.round((bidCum / totalVol) * 100);
        this.askRatio = 100 - this.bidRatio;
      }

      const maxDepth = Math.max(bidCum, askCum, 1);
      this.maxCumulativeDepth = maxDepth;

      // Find the largest size across all rows
      const allSizes = [
        ...(data.bids || []).map(bid => bid.size),
        ...(data.asks || []).map(ask => ask.size)
      ];
      const maxSize = Math.max(...allSizes, 1);

      // Calculate depth bar percentages (Linear Row Size)
      this.bids = processedBids.map((b) => ({
        ...b,
        percent: Math.min(100, (b.size / maxSize) * 100)
      }));

      this.asks = processedAsks.map((a) => ({
        ...a,
        percent: Math.min(100, (a.size / maxSize) * 100)
      }));

      // Calculate spread
      if (this.bids.length > 0 && this.asks.length > 0) {
        this.spread = Math.max(0, +(this.asks[0].price - this.bids[0].price).toFixed(2));
        this.spreadPct = this.lastPrice ? +((this.spread / this.lastPrice) * 100).toFixed(3) : 0;
      }

      // Re-score after every L2 snapshot
      this.computeScorecard();
    },

    processTapeTick(tick) {
      if (!tick) return;

      // 1. Size Filtering: Filter out and do not display any individual trades smaller than 100 shares
      if (tick.size < 100) return;

      // Calculate real-time volume for the *current calendar minute*
      const now = new Date();
      const currentMinute = now.getMinutes();
      
      if (this.currentMinIndex !== currentMinute) {
        this.currentMinIndex = currentMinute;
        this.currentVol1m = 0;
      }
      
      this.currentVol1m += tick.size;

      // Absorption Watcher: Record aggressor tape prints in the 15s bucket
      // Ignore off-exchange / dark pool trades — those don't move lit book levels
      const whale = this.trackedWhales[tick.price];
      const isDarkPool = tick.exchange && ['D', 'TRF', 'ADF', 'O'].includes(tick.exchange.toUpperCase());

      if (whale && !isDarkPool) {
        const isAggressor =
          (whale.side === 'ASK' && tick.side === 'BUY') ||
          (whale.side === 'BID' && tick.side === 'SELL');

        if (isAggressor) {
          const tsPrint = { size: tick.size, ts: Date.now() };
          const CUTOFF = Date.now() - 15000;

          // Unified 15s window for both volume and count
          whale.vol15sPrints = (whale.vol15sPrints || []);
          whale.vol15sPrints.push(tsPrint);
          whale.vol15sPrints = whale.vol15sPrints.filter(p => p.ts > CUTOFF);
          whale.vol15s = whale.vol15sPrints.reduce((acc, p) => acc + p.size, 0);

          whale.prints15s = (whale.prints15s || []);
          whale.prints15s.push(tsPrint);
          whale.prints15s = whale.prints15s.filter(p => p.ts > CUTOFF);
        }
      }

      // 2. Prepend new trade (No aggregation)

      this.tape.unshift({
        ...tick,
        id: `${tick.timestamp || Date.now()}-${Math.random()}`,
        orderCount: tick.orderCount || 1,
        hasBorder: tick.size >= this.medianLevelSize * 3,
        hasIcon: tick.size >= this.medianLevelSize * 6
      });

      if (this.tape.length > this.maxTapeLength) {
        this.tape.pop();
      }

      // Feed the global rolling tape tracker — unified 15s window
      const isDarkPoolTick = tick.exchange && ['D', 'TRF', 'ADF', 'O'].includes(tick.exchange.toUpperCase());
      const rp = { size: tick.size, ts: Date.now() };

      if (isDarkPoolTick) {
        // Track dark pool flow separately — informative but NOT part of absorption confirmation
        if (tick.side === 'BUY')  this.dpRolling.buy15s.push(rp);
        else if (tick.side === 'SELL') this.dpRolling.sell15s.push(rp);
      } else {
        // Lit-market tape for absorption scoring
        if (tick.side === 'BUY')  this.tapeRolling.buy15s.push(rp);
        else if (tick.side === 'SELL') this.tapeRolling.sell15s.push(rp);
      }

      // Re-score after every tape tick
      this.computeScorecard();
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
      this.trackedWhales = {};
      this.tapeRolling = { buy15s: [], sell15s: [] };
      this.dpRolling   = { buy15s: [], sell15s: [] };
      this.scorecard = { total: 0, l2Imbalance: 0, tapeDelta15s: 0, tapePressure15s: 0, whaleAbsorption: 0, roundFigureCtx: 0, darkPool: 0, signals: [] };
      this.currentMinIndex = -1;
      this.currentVol1m = 0;
      this.lastPrice = null;
      this.prevPrice = null;
      this.change = null;
      this.changePercent = null;
      this.volume = null;
      this.high = null;
      this.low = null;
      this.open = null;

      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'SUBSCRIBE', symbol: sym }));
      }
    },

    refetchCriteria() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.symbol) {
        this.ws.send(JSON.stringify({ action: 'REFETCH_CRITERIA', symbol: this.symbol }));
      }
    },

    // ── SCORECARD ENGINE ──────────────────────────────────────────────────────
    // Each signal contributes weighted points.  Clamp result to -100..+100.
    //
    // Signal weights (sum of maxima = 100):
    //   S1  L2 depth imbalance          ±15
    //   S2  1-min rolling tape delta    ±25
    //   S3  5s micro-pressure           ±20
    //   S4  Whale absorption (w/ RF ctx)±30  (penalised if RF obstacle present)
    //   S5  Nearest round-figure ctx    ±10
    // ─────────────────────────────────────────────────────────────────────────
    computeScorecard() {
      const now = Date.now();
      const signals = [];

      // ── S1: L2 Depth Imbalance (±15) ───────────────────────────────────────
      const imbalanceDelta = this.bidRatio - this.askRatio; // -100..+100
      const s1 = Math.round((imbalanceDelta / 100) * 15);
      if (Math.abs(s1) >= 2) {
        signals.push({
          label: s1 > 0
            ? `L2 BID depth dominates (${this.bidRatio}% bid / ${this.askRatio}% ask)`
            : `L2 ASK depth dominates (${this.askRatio}% ask / ${this.bidRatio}% bid)`,
          score: s1,
          type: s1 > 0 ? 'bull' : 'bear'
        });
      }

      // ── S2: 15s Tape Volume Delta (±25) ───────────────────────────────────────
      // Volume-weighted: who sent the heavier orders in the last 15s
      this.tapeRolling.buy15s  = this.tapeRolling.buy15s.filter(p => now - p.ts <= 15000);
      this.tapeRolling.sell15s = this.tapeRolling.sell15s.filter(p => now - p.ts <= 15000);
      const buyVol15s  = this.tapeRolling.buy15s.reduce((a, p) => a + p.size, 0);
      const sellVol15s = this.tapeRolling.sell15s.reduce((a, p) => a + p.size, 0);
      const totalVol15s = buyVol15s + sellVol15s;
      const s2 = totalVol15s > 0 ? Math.round(((buyVol15s - sellVol15s) / totalVol15s) * 25) : 0;
      if (Math.abs(s2) >= 3) {
        const bLots = Math.round(buyVol15s / 100);
        const sLots = Math.round(sellVol15s / 100);
        signals.push({
          label: s2 > 0
            ? `15s vol BUY dominant — ${bLots}K vs ${sLots}K lots`
            : `15s vol SELL dominant — ${sLots}K vs ${bLots}K lots`,
          score: s2,
          type: s2 > 0 ? 'bull' : 'bear'
        });
      }

      // ── S3: 15s Tape Count Pressure (±20) ──────────────────────────────────
      // Count-weighted: who fired more prints (frequency of aggression) in last 15s
      const buyCount15s  = this.tapeRolling.buy15s.length;
      const sellCount15s = this.tapeRolling.sell15s.length;
      const totalCount15s = buyCount15s + sellCount15s;
      const s3 = totalCount15s >= 2
        ? Math.round(((buyCount15s - sellCount15s) / totalCount15s) * 20)
        : 0;
      if (Math.abs(s3) >= 4) {
        signals.push({
          label: s3 > 0
            ? `15s prints: ${buyCount15s} BUY vs ${sellCount15s} SELL`
            : `15s prints: ${sellCount15s} SELL vs ${buyCount15s} BUY`,
          score: s3,
          type: s3 > 0 ? 'bull' : 'bear'
        });
      }

      // ── S4: Whale Absorption + Nearby Round Figure Obstacle (±30) ───────────
      // A confirmed absorption earns ±25 base points.
      // If a KEY or MAJOR round-figure level on the SAME SIDE as the move
      // still exists in the book within 0.5% of price → obstacle not broken
      // → penalise to 40% of base (need RF break too for full confirmation).
      let s4 = 0;
      for (const priceKey in this.trackedWhales) {
        const whale = this.trackedWhales[priceKey];
        if (!whale.alertFired) continue;           // Only count confirmed absorptions

        const wPrice = parseFloat(priceKey);
        const base   = whale.side === 'ASK' ? 25 : -25;
        const hood   = wPrice * 0.005;             // 0.5% neighbourhood

        // For ASK whale (bullish): obstacle = KEY/MAJOR ask still standing above wPrice
        // For BID whale (bearish): obstacle = KEY/MAJOR bid still standing below wPrice
        let hasRFObstacle = false;
        let obstaclePrice = null;

        if (whale.side === 'ASK') {
          const hit = this.asks.find(a =>
            a.price > wPrice &&
            a.price <= wPrice + hood &&
            a.roundFigure &&
            (a.roundFigure.level === 'key' || a.roundFigure.level === 'major') &&
            a.size >= this.medianLevelSize * 2   // Still meaningful size
          );
          if (hit) { hasRFObstacle = true; obstaclePrice = hit.price; }
        } else {
          const hit = this.bids.find(b =>
            b.price < wPrice &&
            b.price >= wPrice - hood &&
            b.roundFigure &&
            (b.roundFigure.level === 'key' || b.roundFigure.level === 'major') &&
            b.size >= this.medianLevelSize * 2
          );
          if (hit) { hasRFObstacle = true; obstaclePrice = hit.price; }
        }

        if (hasRFObstacle) {
          // Partial score only — round figure resistance/support NOT yet broken
          const partial = Math.round(base * 0.4);
          s4 += partial;
          signals.push({
            label: whale.side === 'ASK'
              ? `⚠ ASK whale absorbed BUT $${obstaclePrice?.toFixed(2)} resistance intact — PARTIAL only`
              : `⚠ BID whale absorbed BUT $${obstaclePrice?.toFixed(2)} support intact — PARTIAL only`,
            score: partial,
            type: 'partial'
          });
        } else {
          // No RF obstacle in path → full confirmation
          s4 += base;
          signals.push({
            label: whale.side === 'ASK'
              ? `✓ ASK whale ABSORBED + no RF resistance in path — strong BUY signal`
              : `✓ BID whale ABSORBED + no RF support in path — strong SELL signal`,
            score: base,
            type: whale.side === 'ASK' ? 'bull' : 'bear'
          });
        }
      }
      s4 = Math.max(-30, Math.min(30, s4));

      // ── S5: Nearest Round Figure Context (±10) ──────────────────────────────
      // Checks if current price is pressing against (or bouncing from) a KEY level.
      let s5 = 0;
      if (this.asks.length > 0 && this.bids.length > 0) {
        const nearKeyAsk = this.asks.slice(0, 6).find(a => a.roundFigure?.level === 'key');
        const nearKeyBid = this.bids.slice(0, 6).find(b => b.roundFigure?.level === 'key');

        if (nearKeyAsk && s3 > 4) {
          // Buyers pressing against KEY resistance → obstacle, deduct
          s5 = -8;
          signals.push({
            label: `KEY resistance $${nearKeyAsk.price.toFixed(2)} — 5s buy pressure but blocked`,
            score: s5, type: 'warn'
          });
        } else if (nearKeyBid && s3 < -4) {
          // Sellers pressing against KEY support → obstacle for bears
          s5 = 8;
          signals.push({
            label: `KEY support $${nearKeyBid.price.toFixed(2)} — 5s sell pressure but held`,
            score: s5, type: 'warn'
          });
        } else if (nearKeyAsk && s3 < -4) {
          // Price retreating from KEY resistance = sellers winning
          s5 = -6;
          signals.push({
            label: `Rejected at KEY $${nearKeyAsk.price.toFixed(2)} with sell pressure`,
            score: s5, type: 'bear'
          });
        } else if (nearKeyBid && s3 > 4) {
          // Price bouncing off KEY support = buyers winning
          s5 = 6;
          signals.push({
            label: `Bouncing off KEY $${nearKeyBid.price.toFixed(2)} with buy pressure`,
            score: s5, type: 'bull'
          });
        }
      }

      // ── S6: Dark Pool Flow Monitor (±8) ─────────────────────────────────────────
      // Dark pool / TRF trades are excluded from absorption confirmation
      // (they don't move the lit book) but their DIRECTION is still informative.
      // Institutional dark pool buys = subtle bullish signal and vice versa.
      this.dpRolling.buy15s  = this.dpRolling.buy15s.filter(p => now - p.ts <= 15000);
      this.dpRolling.sell15s = this.dpRolling.sell15s.filter(p => now - p.ts <= 15000);
      const dpBuyVol  = this.dpRolling.buy15s.reduce((a, p) => a + p.size, 0);
      const dpSellVol = this.dpRolling.sell15s.reduce((a, p) => a + p.size, 0);
      const dpTotal   = dpBuyVol + dpSellVol;
      let s6 = 0;
      if (dpTotal >= 500) {  // Only score when there's meaningful dark pool activity
        s6 = Math.round(((dpBuyVol - dpSellVol) / dpTotal) * 8);
        if (Math.abs(s6) >= 2) {
          const dpBLots = Math.round(dpBuyVol / 100);
          const dpSLots = Math.round(dpSellVol / 100);
          signals.push({
            label: s6 > 0
              ? `🔍 DP/TRF flow: ${dpBLots}K BUY vs ${dpSLots}K SELL — institutional buys`
              : `🔍 DP/TRF flow: ${dpSLots}K SELL vs ${dpBLots}K BUY — institutional sells`,
            score: s6,
            type: s6 > 0 ? 'bull' : 'bear'
          });
        }
      }
      s6 = Math.max(-8, Math.min(8, s6));

      // ── Compose & Clamp ─────────────────────────────────────────────────────
      const total = Math.max(-100, Math.min(100, s1 + s2 + s3 + s4 + s5 + s6));

      this.scorecard = {
        total,
        l2Imbalance:     s1,
        tapeDelta15s:    s2,
        tapePressure15s: s3,
        whaleAbsorption: s4,
        roundFigureCtx:  s5,
        darkPool:        s6,
        signals: signals.sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
      };
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
    },

    playWhaleEatenSound(side) {
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const now = audioCtx.currentTime;

        if (side === 'ASK') {
          // Win / Success sound (Ascending chime)
          const osc1 = audioCtx.createOscillator();
          const osc2 = audioCtx.createOscillator();
          const gainNode = audioCtx.createGain();
          
          osc1.type = 'sine';
          osc2.type = 'sine';
          
          // Notes: E5 -> G5 -> C6
          osc1.frequency.setValueAtTime(659.25, now);
          osc1.frequency.setValueAtTime(783.99, now + 0.1);
          osc1.frequency.setValueAtTime(1046.50, now + 0.2);
          
          // One octave lower
          osc2.frequency.setValueAtTime(329.63, now);
          osc2.frequency.setValueAtTime(392.00, now + 0.1);
          osc2.frequency.setValueAtTime(523.25, now + 0.2);

          gainNode.gain.setValueAtTime(0, now);
          gainNode.gain.linearRampToValueAtTime(0.1, now + 0.05); // Lower volume (0.1)
          gainNode.gain.setValueAtTime(0.1, now + 0.2);
          gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.8);

          osc1.connect(gainNode);
          osc2.connect(gainNode);
          gainNode.connect(audioCtx.destination);
          
          osc1.start(now);
          osc2.start(now);
          osc1.stop(now + 0.8);
          osc2.stop(now + 0.8);
          
        } else if (side === 'BID') {
          // Warning / Alert sound (Double buzzer)
          const osc = audioCtx.createOscillator();
          const gainNode = audioCtx.createGain();
          
          osc.type = 'square';
          osc.frequency.setValueAtTime(150, now); // Low harsh pitch
          
          gainNode.gain.setValueAtTime(0, now);
          
          // First beep
          gainNode.gain.linearRampToValueAtTime(0.1, now + 0.02); // Lower volume (0.1)
          gainNode.gain.setValueAtTime(0.1, now + 0.15);
          gainNode.gain.linearRampToValueAtTime(0, now + 0.2);
          
          // Second beep
          gainNode.gain.setValueAtTime(0, now + 0.25);
          gainNode.gain.linearRampToValueAtTime(0.1, now + 0.27);
          gainNode.gain.setValueAtTime(0.1, now + 0.4);
          gainNode.gain.linearRampToValueAtTime(0, now + 0.45);

          osc.connect(gainNode);
          gainNode.connect(audioCtx.destination);
          
          osc.start(now);
          osc.stop(now + 0.5);
        }
      } catch (e) {
        console.error("Audio play failed", e);
      }
    }
  }
});
