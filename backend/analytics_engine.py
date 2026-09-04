import collections
import time
from typing import Dict, List, Optional
import pandas as pd
from pydantic import BaseModel, Field

SNR_TIMEFRAME_CONFIG = {
    "5s": {
        "lookback_candles_range": [120, 300],
        "tolerance_cents": [1, 2],
        "fractal_n": 3,
        "purpose": "Precise entry point execution and pullback bottom detection."
    },
    "10s": {
        "lookback_candles_range": [100, 200],
        "tolerance_cents": [2, 3],
        "fractal_n": 3,
        "purpose": "Confirm consolidation and seller absorption."
    },
    "1m": {
        "lookback_candles_range": [60, 120],
        "tolerance_cents": [3, 5],
        "fractal_n": 2,
        "purpose": "Primary frame for pullback structure and continuation validation."
    },
    "5m": {
        "lookback_candles_range": [40, 80],
        "tolerance_cents": [5, 8],
        "fractal_n": 2,
        "purpose": "Read overall session trend and filter out fakeouts."
    },
    "15m": {
        "lookback_candles_range": [30, 50],
        "tolerance_cents": [8, 15],
        "fractal_n": 3,
        "purpose": "Identify major take-profit targets and pre-market levels."
    },
    "4h": {
        "lookback_candles_range": [30, 60],
        "tolerance_cents": [15, 30],
        "fractal_n": 5,
        "purpose": "Flag major historical resistance to avoid buying near the top."
    }
}

class LiquidityWall(BaseModel):
    price: float
    size: int
    side: str
    relative_strength: float
    distance_pct: float
    is_replenishing: bool = False
    consumed_size: int = 0
    # New tracking fields
    original_size: int = 0
    timestamp: float = Field(default_factory=time.time)
    persistence_seconds: float = 0.0
    depletion_rate: float = 0.0

class ConfluenceZone(BaseModel):
    price: float
    timeframe: str
    strength: str
    type: str # 'Support' or 'Resistance'

class TradeSignal(BaseModel):
    action: str # 'BUY', 'SELL', 'WAIT'
    entry: float
    target: float
    stop: float
    reasoning: str

class TradeIdea(BaseModel):
    side: str # 'BUY', 'SHORT'
    entry: float
    target: float
    stop: float
    rr_ratio: float
    score: int
    reasoning: str

class SurgePrediction(BaseModel):
    direction: str = "CONSOLIDATING"  # "MOMENTUM_SURGE", "POTENTIAL_SQUEEZE", "SQUEEZE_LIKE_ORDER_FLOW", "DUMPING_DOWN", "CONSOLIDATING", "WAITING_10S_UPTREND"
    target_price: float = 0.0
    current_price: float = 0.0
    price_delta: float = 0.0
    price_delta_pct: float = 0.0
    confidence: int = 50  # 0 to 100%
    speed: str = "NORMAL"  # "EXPLOSIVE", "FAST", "STEADY"
    catalyst: str = ""
    floor_price: Optional[float] = None
    wall_price: Optional[float] = None
    buy_pressure_pct: int = 50
    block_bias: str = "NEUTRAL"
    is_10s_uptrend: bool = False
    trend_status: str = "WAITING_10S_UPTREND"
    hh_hl_detail: str = ""
    # New tracking fields
    squeeze_score: int = 0
    target_distance: float = 0.0
    meets_bullish_criteria: bool = False
    meets_bearish_criteria: bool = False

class OrderFlowAnomaly(BaseModel):
    risk_score: int = 0
    classification: str = "NORMAL"
    pattern: str = ""
    side: str = ""
    price: float = 0.0
    displayed_size: int = 0
    lifetime: float = 0.0
    cancellations: int = 0
    executed_volume: int = 0
    evidence: str = ""

class MicroBar10s:
    def __init__(self, timestamp: float, price: float):
        self.start_time = timestamp
        self.open = price
        self.high = price
        self.low = price
        self.close = price
        self.volume = 0

    def update(self, price: float, size: int):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += size

class IntelligenceState(BaseModel):
    vwap: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    ema_200: Optional[float] = None
    
    mtf_levels: List[ConfluenceZone] = []
    
    hod: Optional[float] = None
    lod: Optional[float] = None
    
    bid_walls: List[LiquidityWall] = []
    ask_walls: List[LiquidityWall] = []
    
    tape_speed: float = 0.0
    aggressive_buy_vol: int = 0
    aggressive_sell_vol: int = 0
    
    ai_evidence: str = "Awaiting sufficient market data to form a conclusion."
    signal: Optional[TradeSignal] = None
    trade_ideas: List[TradeIdea] = []
    surge_prediction: Optional[SurgePrediction] = None
    order_flow_anomaly: Optional[OrderFlowAnomaly] = None
    
    last_update_time: Optional[float] = None
    last_mtf_update_time: Optional[float] = None
    
    # Live Liquidity Tracking Layer (Separate from MTF)
    live_liquidity_bids: Dict[float, LiquidityWall] = {}
    live_liquidity_asks: Dict[float, LiquidityWall] = {}

class QuantEngine:
    def __init__(self):
        self.symbol = None
        self.state = IntelligenceState()
        
        # VWAP trackers
        self.cum_vol = 0
        self.cum_vol_price = 0.0
        self.last_price = 0.0
        
        # Tape speed / volume trackers (rolling 10 seconds)
        self.recent_ticks = collections.deque(maxlen=5000)  # tuple: (timestamp, size, side)
        
        # 10-second micro-bars for trend structure confirmation (HH & HL)
        self.bars_10s: collections.deque = collections.deque(maxlen=300)
        self.current_10s_bar: Optional[MicroBar10s] = None
        
        self.bars_5s: collections.deque = collections.deque(maxlen=400)
        self.current_5s_bar: Optional[MicroBar10s] = None # We can reuse MicroBar10s structure since it's just a generic OHLCV
        
        # Historical bar storage for S&R
        self.historical_dfs: Dict[str, pd.DataFrame] = {}
        
        # Liquidity wall state for iceberg/absorption tracking
        self.tracked_levels: Dict[float, Dict] = {}
        
        # Cached S&R zones for each timeframe
        self.cached_tf_zones: Dict[str, List[ConfluenceZone]] = {
            "5s": [], "10s": [], "1m": [], "5m": [], "15m": [], "4h": []
        }
        
        # Manipulation engine state tracking
        self.rolling_l2_history = collections.deque(maxlen=1000) # (timestamp, price, size, side)
        
    def reset(self, symbol: str):
        self.symbol = symbol
        self.state = IntelligenceState()
        self.cum_vol = 0
        self.cum_vol_price = 0.0
        self.last_price = 0.0
        self.recent_ticks.clear()
        self.bars_10s.clear()
        self.current_10s_bar = None
        self.bars_5s.clear()
        self.current_5s_bar = None
        self.historical_dfs.clear()
        self.tracked_levels.clear()
        for k in self.cached_tf_zones:
            self.cached_tf_zones[k] = []
        
    def process_historical_data(self, timeframe: str, bars: List[Dict], recalc_snr: bool = True):
        if not bars:
            return
            
        df = pd.DataFrame(bars)
        if df.empty or 'close' not in df.columns:
            return
            
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Sort index just in case
        df.sort_index(inplace=True)
        self.historical_dfs[timeframe] = df
        
        if timeframe == '1m':
            # Calculate EMAs on 1m
            df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
            
            # Resample for 5m
            df_5m = df.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
            self.historical_dfs['5m'] = df_5m
            
            # Resample for 15m
            df_15m = df.resample('15min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
            self.historical_dfs['15m'] = df_15m
            
            # VWAP calculation (Current day only)
            if 'volume' in df.columns:
                last_date = df.index[-1].date()
                df_today = df[df.index.date == last_date].copy()
                if not df_today.empty:
                    df_today['typical_price'] = (df_today['high'] + df_today['low'] + df_today['close']) / 3
                    pv_sum = (df_today['typical_price'] * df_today['volume']).sum()
                    v_sum = df_today['volume'].sum()
                    self.cum_vol = v_sum
                    self.cum_vol_price = pv_sum
                    self.state.vwap = round(pv_sum / (v_sum or 1), 5)
                
            latest = df.iloc[-1]
            self.state.ema_9 = round(latest['ema_9'], 5)
            self.state.ema_21 = round(latest['ema_21'], 5)
            self.state.ema_200 = round(latest['ema_200'], 5)
            
            if recalc_snr:
                self.state.last_update_time = time.time()
                self._recalc_tf_snr('1m')
                self._recalc_tf_snr('5m')
                self._recalc_tf_snr('15m')
        elif timeframe == '4h' and recalc_snr:
            self._recalc_tf_snr('4h')
        
    def on_tape_tick(self, price: float, size: int, side: str):
        self.last_price = price

        # 1. Update VWAP
        self.cum_vol += size
        self.cum_vol_price += (price * size)
        self.state.vwap = round(self.cum_vol_price / (self.cum_vol or 1), 5)
        
        # 1.5 Update live EMAs based on the last closed bar
        if '1m' in self.historical_dfs and not self.historical_dfs['1m'].empty:
            df = self.historical_dfs['1m']
            if 'ema_9' in df.columns:
                prev_ema9 = df['ema_9'].iloc[-1]
                self.state.ema_9 = round((price * (2/10)) + (prev_ema9 * (1 - 2/10)), 5)
            if 'ema_21' in df.columns:
                prev_ema21 = df['ema_21'].iloc[-1]
                self.state.ema_21 = round((price * (2/22)) + (prev_ema21 * (1 - 2/22)), 5)
            if 'ema_200' in df.columns:
                prev_ema200 = df['ema_200'].iloc[-1]
                self.state.ema_200 = round((price * (2/201)) + (prev_ema200 * (1 - 2/201)), 5)
        
        # 2. Update HOD / LOD
        if self.state.hod is None or price > self.state.hod:
            self.state.hod = price
        if self.state.lod is None or price < self.state.lod:
            self.state.lod = price
            
        # 3. Track recent aggressive volume and tape speed
        now = time.time()
        self.recent_ticks.append((now, size, side, price))
        
        # 4a. Track 10-second micro-bars for HH / HL detection
        if self.current_10s_bar is None or (now - self.current_10s_bar.start_time) >= 10.0:
            if self.current_10s_bar:
                self.bars_10s.append(self.current_10s_bar)
                self._recalc_tf_snr('10s')
            self.current_10s_bar = MicroBar10s(now, price)
        self.current_10s_bar.update(price, size)
        
        # 4b. Track 5-second micro-bars
        if self.current_5s_bar is None or (now - self.current_5s_bar.start_time) >= 5.0:
            if self.current_5s_bar:
                self.bars_5s.append(self.current_5s_bar)
                self._recalc_tf_snr('5s')
            self.current_5s_bar = MicroBar10s(now, price)
        self.current_5s_bar.update(price, size)

        # 5. Track execution logic for aggressive orders (Block trades or Sweep)Clean up old ticks (> 10 seconds)
        while self.recent_ticks and now - self.recent_ticks[0][0] > 10.0:
            self.recent_ticks.popleft()
            
        buy_vol = sum(t[1] for t in self.recent_ticks if t[2] == "BUY")
        sell_vol = sum(t[1] for t in self.recent_ticks if t[2] == "SELL")
        
        self.state.aggressive_buy_vol = buy_vol
        self.state.aggressive_sell_vol = sell_vol
        self.state.tape_speed = len(self.recent_ticks) / 10.0  # Trades per second
        
        self._evaluate_evidence()

    def _find_fractals(self, highs: List[float], lows: List[float], n: int) -> tuple:
        """Finds swing highs and lows based on checking n bars to the left and right."""
        swing_highs = []
        swing_lows = []
        length = len(highs)
        
        for i in range(n, length - n):
            # Check swing high
            is_high = True
            for j in range(1, n + 1):
                if highs[i - j] >= highs[i] or highs[i + j] >= highs[i]:
                    is_high = False
                    break
            if is_high:
                swing_highs.append(highs[i])
                
            # Check swing low
            is_low = True
            for j in range(1, n + 1):
                if lows[i - j] <= lows[i] or lows[i + j] <= lows[i]:
                    is_low = False
                    break
            if is_low:
                swing_lows.append(lows[i])
                
        return swing_highs, swing_lows

    def on_l2_update(self, current_price: float, bids: List[Dict], asks: List[Dict]):
        if current_price > 0:
            self.last_price = current_price

        # Wall and floor detection logic based on sizes relative to first 100 rows
        if not bids or not asks:
            return
            
        first_100_bids = bids[:100]
        first_100_asks = asks[:100]
        avg_bid_size = sum(b['size'] for b in first_100_bids) / len(first_100_bids) if first_100_bids else 1
        avg_ask_size = sum(a['size'] for a in first_100_asks) / len(first_100_asks) if first_100_asks else 1
        
        now = time.time()
        
        # Track live bids strictly below current_price
        new_bids = {}
        for b in bids:
            price = b['price']
            if price >= self.last_price:
                continue
            if b['size'] > avg_bid_size * 2 and b['size'] > 500:
                dist = abs(self.last_price - price) / (self.last_price or 1.0) * 100
                if price in self.state.live_liquidity_bids:
                    wall = self.state.live_liquidity_bids[price]
                    wall.persistence_seconds = now - wall.timestamp
                    if b['size'] > wall.size:
                        wall.is_replenishing = True
                    elif b['size'] < wall.size:
                        wall.depletion_rate = (wall.size - b['size']) / max(1.0, wall.persistence_seconds)
                    wall.size = b['size']
                    wall.distance_pct = round(dist, 2)
                    wall.relative_strength = round(b['size'] / avg_bid_size, 1)
                    new_bids[price] = wall
                else:
                    new_bids[price] = LiquidityWall(
                        price=price, size=b['size'], side="BID",
                        relative_strength=round(b['size'] / avg_bid_size, 1),
                        distance_pct=round(dist, 2), original_size=b['size'], timestamp=now
                    )
        self.state.live_liquidity_bids = new_bids
        self.state.bid_walls = list(new_bids.values())
        
        # Track live asks strictly above current_price
        new_asks = {}
        for a in asks:
            price = a['price']
            if price <= self.last_price:
                continue
            if a['size'] > avg_ask_size * 2 and a['size'] > 500:
                dist = abs(price - self.last_price) / (self.last_price or 1.0) * 100
                if price in self.state.live_liquidity_asks:
                    wall = self.state.live_liquidity_asks[price]
                    wall.persistence_seconds = now - wall.timestamp
                    if a['size'] > wall.size:
                        wall.is_replenishing = True
                    elif a['size'] < wall.size:
                        wall.depletion_rate = (wall.size - a['size']) / max(1.0, wall.persistence_seconds)
                    wall.size = a['size']
                    wall.distance_pct = round(dist, 2)
                    wall.relative_strength = round(a['size'] / avg_ask_size, 1)
                    new_asks[price] = wall
                else:
                    new_asks[price] = LiquidityWall(
                        price=price, size=a['size'], side="ASK",
                        relative_strength=round(a['size'] / avg_ask_size, 1),
                        distance_pct=round(dist, 2), original_size=a['size'], timestamp=now
                    )
        self.state.live_liquidity_asks = new_asks
        self.state.ask_walls = list(new_asks.values())
                
        self._calculate_order_flow_manipulation_score(self.last_price, bids, asks, avg_bid_size, avg_ask_size)
        self._evaluate_evidence()
        
    def _calculate_order_flow_manipulation_score(self, current_price: float, bids: List[Dict], asks: List[Dict], avg_bid_size: float, avg_ask_size: float):
        now = time.time()
        
        current_book = {b['price']: b for b in bids}
        current_book.update({a['price']: a for a in asks})
        
        # Prune and Update State
        prices_to_remove = []
        for price, level in self.tracked_levels.items():
            if price not in current_book:
                if now - level["last_seen"] > 10.0:
                    prices_to_remove.append(price)
                else:
                    # Missing from current book update, might be cancelled
                    old_size = level["last_size"]
                    if old_size > 0:
                        level["cancel_count"] += 1
                        level["last_size"] = 0
                        level["last_cancel_time"] = now
            else:
                order = current_book[price]
                level["last_seen"] = now
                old_size = level["last_size"]
                new_size = order['size']
                
                if new_size < old_size:
                    diff = old_size - new_size
                    # Check if executed in recent tape
                    exec_vol = sum(t[1] for t in self.recent_ticks if t[3] == price and t[2] == ("SELL" if level["side"]=="BID" else "BUY"))
                    if exec_vol >= diff * 0.5:
                        level["executed_vol"] += diff
                    else:
                        if diff > 1000:
                            level["cancel_count"] += 1
                            level["last_cancel_time"] = now
                elif new_size > old_size:
                    if old_size == 0:
                        level["refresh_count"] += 1
                        
                level["max_size"] = max(level["max_size"], new_size)
                level["last_size"] = new_size
                
        for p in prices_to_remove:
            del self.tracked_levels[p]
            
        for price, order in current_book.items():
            if price not in self.tracked_levels:
                self.tracked_levels[price] = {
                    "first_seen": now,
                    "last_seen": now,
                    "side": "BID" if price < current_price else "ASK",
                    "max_size": order['size'],
                    "last_size": order['size'],
                    "cancel_count": 0,
                    "refresh_count": 0,
                    "executed_vol": 0,
                    "price": price,
                    "last_cancel_time": 0
                }
                
        # Analyze for Spoofing
        highest_risk = 0
        best_anomaly = None
        
        for price, level in self.tracked_levels.items():
            score = 0
            pattern = ""
            evidence = ""
            lifetime = now - level["first_seen"]
            avg_size = avg_bid_size if level["side"] == "BID" else avg_ask_size
            
            # Sub-scores
            large_pull_score = 0
            refresh_score = 0
            migration_score = 0
            absorption_discount = 0
            
            # Only evaluate anomalies if it's currently in the book OR it was just cancelled this very second
            is_ghost = level["last_size"] == 0
            just_cancelled = is_ghost and (now - level.get("last_cancel_time", 0)) < 1.0

            if is_ghost and not just_cancelled:
                continue
            
            if level["max_size"] > avg_size * 3 and level["max_size"] > 1000:
                dist = abs(current_price - price) / (current_price or 1) * 100
                
                if level["cancel_count"] > 0 and dist < 0.2 and level["executed_vol"] < level["max_size"] * 0.1:
                    large_pull_score = 60 + (level["cancel_count"] * 10)
                    pattern = "LARGE_ORDER_PULL"
                    evidence = f"Wall of {level['max_size']} pulled when price approached within {dist:.2f}% without execution."
                    
                if level["refresh_count"] >= 2:
                    refresh_score = 40 + (level["refresh_count"] * 10)
                    pattern = "REPEATED_REPLACEMENT" if not pattern else "PULL_AND_REPLACE"
                    evidence += f" Order replaced/refreshed {level['refresh_count']} times."
                    
                # Absorption (legitimate execution)
                if level["executed_vol"] > level["max_size"] * 0.4:
                    absorption_discount = 50
                    pattern = "GENUINE_ABSORPTION"
                    evidence = f"Strong legitimate execution of {level['executed_vol']} shares against wall."
                    
            score = large_pull_score + refresh_score - absorption_discount
            score = max(0, min(100, score))
            
            if score > highest_risk:
                highest_risk = score
                classification = "NORMAL"
                if score >= 85: classification = "VERY_HIGH_RISK"
                elif score >= 70: classification = "HIGH_RISK"
                elif score >= 50: classification = "SUSPICIOUS"
                elif score >= 30: classification = "LOW_RISK"
                
                best_anomaly = OrderFlowAnomaly(
                    risk_score=score,
                    classification=classification,
                    pattern=pattern or "NORMAL_FLOW",
                    side=level["side"],
                    price=price,
                    displayed_size=level["max_size"],
                    lifetime=round(lifetime, 1),
                    cancellations=level["cancel_count"],
                    executed_volume=level["executed_vol"],
                    evidence=evidence or "Standard order flow behavior."
                )
                
        if best_anomaly and best_anomaly.risk_score >= 30:
            self.state.order_flow_anomaly = best_anomaly
        else:
            self.state.order_flow_anomaly = None

    def _evaluate_evidence(self):
        # AI / Rules engine to generate human-readable text
        evidence = []
        
        # Momentum
        if self.state.aggressive_buy_vol > self.state.aggressive_sell_vol * 2 and self.state.aggressive_buy_vol > 1000:
            evidence.append(f"Strong aggressive BUYING pressure detected ({self.state.aggressive_buy_vol} shares in last 10s).")
        elif self.state.aggressive_sell_vol > self.state.aggressive_buy_vol * 2 and self.state.aggressive_sell_vol > 1000:
            evidence.append(f"Heavy aggressive SELLING pressure detected ({self.state.aggressive_sell_vol} shares in last 10s).")
            
        # Walls
        if self.state.ask_walls and any(w.distance_pct < 0.2 for w in self.state.ask_walls):
            nearest = min((w for w in self.state.ask_walls if w.distance_pct < 0.2), key=lambda x: x.distance_pct)
            evidence.append(f"Immediate ASK wall capping price at ${nearest.price} (Size: {nearest.size}).")
            
        if self.state.bid_walls and any(w.distance_pct < 0.2 for w in self.state.bid_walls):
            nearest = min((w for w in self.state.bid_walls if w.distance_pct < 0.2), key=lambda x: x.distance_pct)
            evidence.append(f"Strong BID support absorbing selling at ${nearest.price} (Size: {nearest.size}).")
            
        if not evidence:
            self.state.ai_evidence = "Market is in balance. No significant anomalies or walls detected in the immediate vicinity."
        else:
            self.state.ai_evidence = " ".join(evidence)
            
        self._generate_trade_signal()
        self._calculate_surge_prediction()

    def _evaluate_10s_trend(self) -> tuple[bool, str, str]:
        """
        Evaluates 10-second micro-structure for confirmed Higher Highs (HH) and Higher Lows (HL).
        Returns: (is_10s_uptrend: bool, trend_status: str, hh_hl_detail: str)
        """
        if not self.current_10s_bar:
            return False, "WAITING_10S_UPTREND", "Building initial 10s micro-bars..."

        if len(self.bars_10s) < 1:
            curr = self.current_10s_bar
            if self.state.vwap and curr.close >= self.state.vwap:
                return True, "CONFIRMED_HH_HL", f"10s HH (${curr.high:.2f}) & HL (${curr.low:.2f}) above VWAP"
            return False, "WAITING_10S_UPTREND", "Awaiting 10s candle formation (HH & HL)..."

        prev = self.bars_10s[-1]
        curr = self.current_10s_bar

        # Check Higher High and Higher Low on 10s frame
        is_hh = (curr.high > prev.high) or (curr.close > prev.high)
        is_hl = (curr.low >= prev.low and curr.close >= prev.close) or (curr.low > prev.low)

        if is_hh and is_hl:
            return True, "CONFIRMED_HH_HL", f"10s HH (${curr.high:.2f}) & HL (${curr.low:.2f}) Confirmed"
        
        if curr.high < prev.high and curr.low < prev.low:
            return False, "WAITING_10S_UPTREND", f"10s Downtrend: Lower High (${curr.high:.2f}) & Lower Low (${curr.low:.2f})"
        
        return False, "WAITING_10S_UPTREND", f"10s Consolidating: Awaiting HH > ${prev.high:.2f} & HL > ${prev.low:.2f}"

    def _evaluate_technical_criteria(self, current_price: float) -> tuple[bool, bool]:
        """
        Evaluates if the price passes basic bullish or bearish structural criteria.
        Bullish: Price > VWAP, Price > 9 EMA, Price > 21 EMA, Price > 200 EMA
        Bearish: Price < VWAP, Price < 9 EMA, Price < 21 EMA, Price < 200 EMA
        """
        is_above_vwap = current_price > (self.state.vwap or 0.0)
        is_above_9ema = current_price > (self.state.ema_9 or 0.0)
        is_above_21ema = current_price > (self.state.ema_21 or 0.0)
        is_above_200ema = current_price > (self.state.ema_200 or 0.0)
        meets_bullish = is_above_vwap and is_above_9ema and is_above_21ema and is_above_200ema
        
        is_below_vwap = current_price < (self.state.vwap or 999999.0)
        is_below_9ema = current_price < (self.state.ema_9 or 999999.0)
        is_below_21ema = current_price < (self.state.ema_21 or 999999.0)
        is_below_200ema = current_price < (self.state.ema_200 or 999999.0)
        meets_bearish = is_below_vwap and is_below_9ema and is_below_21ema and is_below_200ema
            
        return meets_bullish, meets_bearish

    def _calculate_squeeze_score(self, buy_vol: int, sell_vol: int, tape_speed: float, block_bias: str, price_moved_up: bool, current_price: float = 0.0, nearest_ceiling=None, anomaly: Optional[OrderFlowAnomaly] = None) -> int:
        """
        Calculates a dedicated 0-100 SQUEEZE_SCORE for upward surging momentum.
        """
        score = 50
        total_vol = buy_vol + sell_vol
        if total_vol == 0:
            return 0
            
        buy_pressure_pct = int((buy_vol / total_vol) * 100)
        score += int((buy_pressure_pct - 50) * 0.8)
        
        # Block Bias & Trapped Shorts
        if block_bias == "BUY_BLOCKS":
            score += 20
        elif block_bias == "SELL_BLOCKS" and price_moved_up:
            score += 20 # Shorts are getting run over and trapped
            
        # Tape Velocity
        if tape_speed > 5.0:
            score += 25
        elif tape_speed > 3.0:
            score += 15
        elif tape_speed < 1.0:
            score -= 10
            
        # HOD Proximity Bonus
        if self.state.hod and self.state.hod > 0:
            dist_to_hod = (self.state.hod - current_price) / current_price
            if 0 < dist_to_hod <= 0.01:
                score += 15
            
        # Wall eating (aggressive buying > 50% of nearest ask wall)
        if nearest_ceiling and buy_vol > (nearest_ceiling.size * 0.5):
            score += 10
            
        # Spoofing Anomaly (Ask wall pulled)
        if anomaly and anomaly.risk_score >= 50 and anomaly.side == "ASK" and anomaly.pattern == "LARGE_ORDER_PULL":
            score += 15
            
        # Absorption penalty (Trapped under ask wall)
        is_trapped_under_wall = nearest_ceiling and (nearest_ceiling.price - current_price) <= 0.05
        if buy_vol > (total_vol * 0.6) and total_vol > 1000 and not price_moved_up:
            score -= 50 if is_trapped_under_wall else 40
            
        return max(0, min(100, int(score)))

    def _calculate_flush_score(self, buy_vol: int, sell_vol: int, tape_speed: float, block_bias: str, price_moved_down: bool, current_price: float = 0.0, nearest_floor=None, anomaly: Optional[OrderFlowAnomaly] = None) -> int:
        """
        Calculates a dedicated 0-100 FLUSH_SCORE for downward dumping momentum.
        """
        score = 50
        total_vol = buy_vol + sell_vol
        if total_vol == 0:
            return 0
            
        sell_pressure_pct = int((sell_vol / total_vol) * 100)
        score += int((sell_pressure_pct - 50) * 0.8)
        
        # Block Bias & Trapped Longs
        if block_bias == "SELL_BLOCKS":
            score += 20
        elif block_bias == "BUY_BLOCKS" and price_moved_down:
            score += 20 # Dip-buyers are getting run over and trapped
            
        # Tape Velocity
        if tape_speed > 5.0:
            score += 25
        elif tape_speed > 3.0:
            score += 15
        elif tape_speed < 1.0:
            score -= 10
            
        # LOD Proximity Bonus
        if self.state.lod and self.state.lod > 0:
            dist_to_lod = (current_price - self.state.lod) / current_price
            if 0 < dist_to_lod <= 0.01:
                score += 15
            
        # Wall eating (aggressive selling > 50% of nearest bid floor)
        if nearest_floor and sell_vol > (nearest_floor.size * 0.5):
            score += 10
            
        # Spoofing Anomaly (Bid wall pulled)
        if anomaly and anomaly.risk_score >= 50 and anomaly.side == "BID" and anomaly.pattern == "LARGE_ORDER_PULL":
            score += 15
            
        # Absorption penalty (Trapped above bid floor)
        is_trapped_above_floor = nearest_floor and (current_price - nearest_floor.price) <= 0.05
        if sell_vol > (total_vol * 0.6) and total_vol > 1000 and not price_moved_down:
            score -= 50 if is_trapped_above_floor else 40
            
        return max(0, min(100, int(score)))

    def _calculate_confidence_score(self, direction: str, current_price: float, squeeze_score: int, nearest_floor, nearest_ceiling, is_10s_uptrend: bool, target_price: float) -> int:
        """
        Dynamically calculates a probabilistic confidence score blending SQUEEZE_SCORE with PA structure.
        """
        if direction in ["WAITING_10S_UPTREND", "CONSOLIDATING"]:
            return 50

        # Base confidence heavily weighted on the squeeze score (order flow)
        score = squeeze_score
        
        # Technical confirmation
        if direction in ["POTENTIAL_SQUEEZE", "MOMENTUM_SURGE"]:
            if is_10s_uptrend:
                score += 15
            if self.state.vwap and current_price > self.state.vwap:
                score += 10
            if self.state.ema_9 and current_price > self.state.ema_9:
                score += 5
            
            # Distance to target (closer target = higher confidence)
            if target_price > current_price:
                dist = target_price - current_price
                if dist < 0.10:
                    score += 10
                elif dist > 0.30:
                    score -= 10
                    
        elif direction in ["POTENTIAL_FLUSH", "DUMPING_DOWN"]:
            if not is_10s_uptrend:
                score += 15
            if self.state.vwap and current_price < self.state.vwap:
                score += 10
            if self.state.ema_9 and current_price < self.state.ema_9:
                score += 5

        return max(5, min(99, int(score)))

    def _calculate_surge_prediction(self):
        """
        Predicts whether price is surging up or dumping down and calculates the exact target price.
        """
        current_price = self.last_price or (self.state.vwap or 0.0)
        if current_price <= 0:
            return

        # 1. Micro-Structure check
        is_10s_uptrend, trend_status, hh_hl_detail = self._evaluate_10s_trend()
        meets_bullish, meets_bearish = self._evaluate_technical_criteria(current_price)

        # 2. Live Liquidity Walls (filtered)
        bid_walls = [w for w in self.state.bid_walls if w.price < current_price]
        ask_walls = [w for w in self.state.ask_walls if w.price > current_price]
        nearest_floor = min(bid_walls, key=lambda w: current_price - w.price) if bid_walls else None
        nearest_ceiling = min(ask_walls, key=lambda w: w.price - current_price) if ask_walls else None

        floor_price = nearest_floor.price if nearest_floor else round(current_price - 0.15, 2)
        ceiling_price = nearest_ceiling.price if nearest_ceiling else round(current_price + 0.15, 2)

        # 3. Tape Order Flow Normalization
        buy_vol = self.state.aggressive_buy_vol
        sell_vol = self.state.aggressive_sell_vol
        total_vol = buy_vol + sell_vol
        tape_speed = self.state.tape_speed

        avg_trade_size = total_vol / max(1, len(self.recent_ticks))
        block_threshold = max(1000, avg_trade_size * 5)
        
        buy_block_vol = sum(t[1] for t in self.recent_ticks if t[2] == "BUY" and t[1] >= block_threshold)
        sell_block_vol = sum(t[1] for t in self.recent_ticks if t[2] == "SELL" and t[1] >= block_threshold)

        buy_pressure_pct = int((buy_vol / max(1, total_vol)) * 100)
        if buy_block_vol > sell_block_vol and buy_block_vol > 0:
            block_bias = "BUY_BLOCKS"
        elif sell_block_vol > buy_block_vol and sell_block_vol > 0:
            block_bias = "SELL_BLOCKS"
        else:
            block_bias = "NEUTRAL"

        price_moved_up = (current_price > self.current_10s_bar.open) if self.current_10s_bar else True
        price_moved_down = (current_price < self.current_10s_bar.open) if self.current_10s_bar else False

        # 4. Target Generation (Dynamic Candidates)
        # We blend L2 walls and Structural PA
        upside_candidates = []
        if nearest_ceiling:
            upside_candidates.append(nearest_ceiling.price)
        if self.state.hod and self.state.hod > current_price:
            upside_candidates.append(self.state.hod)
        
        downside_candidates = []
        if nearest_floor:
            downside_candidates.append(nearest_floor.price)
        if self.state.lod and self.state.lod < current_price:
            downside_candidates.append(self.state.lod)

        target_price = current_price
        squeeze_score = 0
        confidence = 50
        speed = "STEADY"
        catalyst = ""
        direction = "CONSOLIDATING"

        # 5. Decision Engine
        if buy_pressure_pct >= 55 or block_bias == "BUY_BLOCKS":
            if price_moved_down and total_vol > 1000:
                # Bull Trap Fake-out: Heavy buying but price is dropping (Absorption by sellers)
                flush_score = self._calculate_flush_score(buy_vol, sell_vol, tape_speed, block_bias, price_moved_down, current_price, nearest_floor, self.state.order_flow_anomaly)
                direction = "POTENTIAL_FLUSH" if flush_score > 75 else "DUMPING_DOWN"
                target_price = max(downside_candidates) if downside_candidates else round(current_price - 0.20, 2)
                confidence = self._calculate_confidence_score(direction, current_price, flush_score, nearest_floor, nearest_ceiling, is_10s_uptrend, target_price)
                speed = "EXPLOSIVE"
                catalyst = f"BULL TRAP (Buyers Absorbed). Flush Score: {flush_score}"
                squeeze_score = flush_score
            else:
                squeeze_score = self._calculate_squeeze_score(buy_vol, sell_vol, tape_speed, block_bias, price_moved_up, current_price, nearest_ceiling, self.state.order_flow_anomaly)
                
                if not meets_bullish:
                    direction = "WAITING_10S_UPTREND"
                    target_price = min(upside_candidates) if upside_candidates else round(current_price + 0.10, 2)
                    catalyst = f"Waiting to fulfill criteria (Price > VWAP & 9EMA). Score: {squeeze_score}"
                elif not is_10s_uptrend:
                    direction = "WAITING_10S_UPTREND"
                    target_price = min(upside_candidates) if upside_candidates else round(current_price + 0.10, 2)
                    catalyst = f"Waiting for 10s HH/HL. Score: {squeeze_score}"
                else:
                    if squeeze_score > 75:
                        direction = "POTENTIAL_SQUEEZE"
                    else:
                        direction = "MOMENTUM_SURGE"
                    
                    target_price = min(upside_candidates) if upside_candidates else round(current_price + 0.20, 2)
                    confidence = self._calculate_confidence_score(direction, current_price, squeeze_score, nearest_floor, nearest_ceiling, is_10s_uptrend, target_price)
                    speed = "EXPLOSIVE" if (tape_speed > 3.0 or squeeze_score > 85) else ("FAST" if tape_speed > 1.2 else "STEADY")
                    catalyst = f"Squeeze Score {squeeze_score}: Targeting {target_price}"

        elif buy_pressure_pct <= 45 or block_bias == "SELL_BLOCKS":
            if price_moved_up and total_vol > 1000:
                # Bear Trap Fake-out: Heavy selling but price is rising (Absorption by buyers)
                squeeze_score = self._calculate_squeeze_score(buy_vol, sell_vol, tape_speed, block_bias, price_moved_up, current_price, nearest_ceiling, self.state.order_flow_anomaly)
                direction = "POTENTIAL_SQUEEZE" if squeeze_score > 75 else "MOMENTUM_SURGE"
                target_price = min(upside_candidates) if upside_candidates else round(current_price + 0.20, 2)
                confidence = self._calculate_confidence_score(direction, current_price, squeeze_score, nearest_floor, nearest_ceiling, is_10s_uptrend, target_price)
                speed = "EXPLOSIVE"
                catalyst = f"BEAR TRAP (Sellers Absorbed). Squeeze Score: {squeeze_score}"
            else:
                squeeze_score = self._calculate_flush_score(buy_vol, sell_vol, tape_speed, block_bias, price_moved_down, current_price, nearest_floor, self.state.order_flow_anomaly)
                
                if not meets_bearish:
                    direction = "CONSOLIDATING"
                    target_price = max(downside_candidates) if downside_candidates else round(current_price - 0.10, 2)
                    catalyst = f"Waiting to fulfill criteria (Price < VWAP & 9EMA). Score: {squeeze_score}"
                elif is_10s_uptrend:
                    direction = "CONSOLIDATING"
                    target_price = max(downside_candidates) if downside_candidates else round(current_price - 0.10, 2)
                    catalyst = f"Waiting for 10s Downtrend (LH/LL). Score: {squeeze_score}"
                else:
                    if squeeze_score > 75:
                        direction = "POTENTIAL_FLUSH"
                    else:
                        direction = "DUMPING_DOWN"
                        
                    target_price = max(downside_candidates) if downside_candidates else round(current_price - 0.20, 2)
                    confidence = self._calculate_confidence_score(direction, current_price, squeeze_score, nearest_floor, nearest_ceiling, is_10s_uptrend, target_price)
                    speed = "EXPLOSIVE" if (tape_speed > 3.0 or squeeze_score > 85) else ("FAST" if tape_speed > 1.2 else "STEADY")
                    catalyst = f"Flush Score {squeeze_score}: Targeting {target_price}"
        else:
            direction = "CONSOLIDATING"
            catalyst = f"Range corridor: Bid Floor ${floor_price:.2f} ↔ Ask Ceiling ${ceiling_price:.2f} ({hh_hl_detail})"

        price_delta = round(target_price - current_price, 2)
        price_delta_pct = round((price_delta / current_price) * 100, 2) if current_price else 0.0

        self.state.surge_prediction = SurgePrediction(
            direction=direction,
            target_price=target_price,
            current_price=current_price,
            price_delta=price_delta,
            price_delta_pct=price_delta_pct,
            confidence=confidence,
            speed=speed,
            catalyst=catalyst,
            floor_price=floor_price,
            wall_price=ceiling_price,
            buy_pressure_pct=buy_pressure_pct,
            block_bias=block_bias,
            is_10s_uptrend=is_10s_uptrend,
            trend_status=trend_status,
            hh_hl_detail=hh_hl_detail,
            squeeze_score=squeeze_score,
            target_distance=abs(price_delta),
            meets_bullish_criteria=meets_bullish,
            meets_bearish_criteria=meets_bearish
        )
        
        # 6. Comprehensive Debug Logging
        print(f"--- PREDICTION LOG: {direction} ---")
        print(f"Price: {current_price} | Tgt: {target_price} (Dist: {price_delta}) | Score: {squeeze_score} | Conf: {confidence}%")
        print(f"L2: Bids < price ({len(bid_walls)}) | Asks > price ({len(ask_walls)})")
        print(f"Tape: BVol {buy_vol} SVol {sell_vol} | BPress {buy_pressure_pct}% | Spd {tape_speed} | Bias {block_bias}")
        print(f"PA: 10s Uptrend? {is_10s_uptrend} | Moved Up? {price_moved_up} Moved Dn? {price_moved_down}")
        print("-----------------------------------")

    def _find_fractals(self, highs: List[float], lows: List[float], n: int) -> tuple:
        """Finds swing highs and lows based on checking n bars to the left and right."""
        swing_highs = []
        swing_lows = []
        length = len(highs)
        
        for i in range(n, length - n):
            # Check swing high
            is_high = True
            for j in range(1, n + 1):
                if highs[i - j] >= highs[i] or highs[i + j] >= highs[i]:
                    is_high = False
                    break
            if is_high:
                swing_highs.append(highs[i])
                
            # Check swing low
            is_low = True
            for j in range(1, n + 1):
                if lows[i - j] <= lows[i] or lows[i + j] <= lows[i]:
                    is_low = False
                    break
            if is_low:
                swing_lows.append(lows[i])
                
        return swing_highs, swing_lows

    def _cluster_zones(self, prices: List[float], tolerance_cents: float) -> List[tuple]:
        """Clusters prices that are within tolerance into zones, returning (price, touch_count)."""
        if not prices:
            return []
            
        prices = sorted(prices)
        clusters = []
        
        current_cluster = [prices[0]]
        
        for price in prices[1:]:
            # Check if price is within tolerance of the cluster average
            avg_price = sum(current_cluster) / len(current_cluster)
            if abs(price - avg_price) <= (tolerance_cents / 100.0):
                current_cluster.append(price)
            else:
                clusters.append(current_cluster)
                current_cluster = [price]
                
        if current_cluster:
            clusters.append(current_cluster)
            
        # Return the rounded average price and the touch count
        result = []
        for cluster in clusters:
            avg_price = sum(cluster) / len(cluster)
            result.append((round(avg_price, 2), len(cluster)))
            
        return result

    def _calculate_fractal_snr(self, timeframe: str) -> List[ConfluenceZone]:
        config = SNR_TIMEFRAME_CONFIG.get(timeframe)
        if not config:
            return []
            
        max_lookback = config["lookback_candles_range"][1]
        tolerance_cents = config["tolerance_cents"][1] # Use upper bound of tolerance
        n = config["fractal_n"]
        
        highs = []
        lows = []
        
        if timeframe in ['5s', '10s']:
            # Use real-time micro bars
            bars = self.bars_5s if timeframe == '5s' else self.bars_10s
            if len(bars) < n * 2 + 1:
                return []
            # Slice to max_lookback
            bars_list = list(bars)[-max_lookback:]
            highs = [b.high for b in bars_list]
            lows = [b.low for b in bars_list]
        else:
            # Use historical DataFrames
            if timeframe not in self.historical_dfs:
                return []
            df = self.historical_dfs[timeframe]
            if len(df) < n * 2 + 1:
                return []
            df_slice = df.tail(max_lookback)
            highs = df_slice['high'].tolist()
            lows = df_slice['low'].tolist()
            
        swing_highs, swing_lows = self._find_fractals(highs, lows, n)
        
        # Cluster them
        res_clusters = self._cluster_zones(swing_highs, tolerance_cents)
        sup_clusters = self._cluster_zones(swing_lows, tolerance_cents)
        
        zones = []
        for price, touches in res_clusters:
            strength = f"{touches}x"
            zones.append(ConfluenceZone(price=price, timeframe=timeframe, strength=strength, type="WALL"))
            
        for price, touches in sup_clusters:
            strength = f"{touches}x"
            zones.append(ConfluenceZone(price=price, timeframe=timeframe, strength=strength, type="FLOOR"))
            
        return zones

    def _recalc_tf_snr(self, timeframe: str):
        """Calculates structural Floor and Wall for a specific timeframe using fractals."""
        zones = self._calculate_fractal_snr(timeframe)
        self.cached_tf_zones[timeframe] = zones
        
        # Flatten and update state
        levels = []
        for tf_zones in self.cached_tf_zones.values():
            levels.extend(tf_zones)
            
        self.state.mtf_levels = levels
        self.state.last_mtf_update_time = time.time()
            
    def _generate_trade_signal(self):
        """Generates a trade signal based on MTF levels, Walls, and Momentum."""
        # Simple AI rules for a signal
        if not self.state.vwap:
            return
            
        buy_pressure = self.state.aggressive_buy_vol > self.state.aggressive_sell_vol
        nearest_bid_wall = min(self.state.bid_walls, key=lambda x: x.distance_pct) if self.state.bid_walls else None
        nearest_ask_wall = min(self.state.ask_walls, key=lambda x: x.distance_pct) if self.state.ask_walls else None
        
        # BUY Setup: Near a strong Bid wall with buying pressure
        if nearest_bid_wall and nearest_bid_wall.distance_pct < 0.3 and buy_pressure:
            entry = nearest_bid_wall.price + 0.02
            stop = nearest_bid_wall.price - 0.05
            target = nearest_ask_wall.price - 0.01 if nearest_ask_wall else entry + 0.50
            self.state.signal = TradeSignal(
                action="BUY",
                entry=round(entry, 2),
                target=round(target, 2),
                stop=round(stop, 2),
                reasoning=f"Bounce off strong Bid wall at ${nearest_bid_wall.price} with buying momentum."
            )
        # SELL Setup: Near a strong Ask wall with selling pressure
        elif nearest_ask_wall and nearest_ask_wall.distance_pct < 0.3 and not buy_pressure:
            entry = nearest_ask_wall.price - 0.02
            stop = nearest_ask_wall.price + 0.05
            target = nearest_bid_wall.price + 0.01 if nearest_bid_wall else entry - 0.50
            self.state.signal = TradeSignal(
                action="SELL",
                entry=round(entry, 2),
                target=round(target, 2),
                stop=round(stop, 2),
                reasoning=f"Rejection at strong Ask wall at ${nearest_ask_wall.price} with selling momentum."
            )
        else:
            self.state.signal = TradeSignal(
                action="WAIT",
                entry=0.0,
                target=0.0,
                stop=0.0,
                reasoning="Waiting for clear confirmation near a major liquidity wall."
            )
            
    def get_payload(self) -> dict:
        return self.state.dict()
