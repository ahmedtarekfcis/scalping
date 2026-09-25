import time
import math
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import datetime

class StockMomentumState(Enum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    COOLING = "COOLING"
    EXPIRED = "EXPIRED"

@dataclass
class MomentumConfig:
    # Lookback & Cooldowns
    max_history_bars: int = 60
    cooldown_seconds: int = 300 # Wait 5m before allowing EXPIRED -> ACTIVE again
    cooling_grace_bars: int = 3 # Bars in sideways/drop before moving COOLING -> EXPIRED
    
    # Triggers for ACTIVE
    min_daily_gain: float = 3.0 # % (Lowered slightly to catch early momentum)
    min_rvol_1m: float = 2.0
    min_return_1m: float = 1.5 # % return in 1m
    min_return_2m: float = 2.5 # % return in 2m
    range_expansion_ratio: float = 1.5 # Current candle range vs average 10m range
    
    # Triggers for COOLING/EXPIRED
    cooling_range_shrink: float = 1.0 # If candle range shrinks below average
    cooling_min_return: float = 0.5 # If recent return drops
    
    # Scoring Weights (Total 100)
    weight_velocity: int = 25
    weight_rvol: int = 25
    weight_vol_accel: int = 15
    weight_range_expansion: int = 15
    weight_structure: int = 10
    weight_vwap: int = 10

class StockTracker:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state = StockMomentumState.INACTIVE
        self.history: List[Dict] = []  # List of 1m OHLCV dicts: {open, high, low, close, volume, vwap, datetime}
        self.last_update_ts = 0
        
        self.momentum_score = 0
        self.last_alert_time = 0
        self.reason = ""
        self.bars_in_cooling = 0
        
        # Incremental tick data for the CURRENT unclosed candle
        self.current_candle_vol = 0
        self.current_candle_high = 0
        self.current_candle_low = float('inf')
        
    def add_history_bar(self, bar: Dict, max_bars: int):
        # Prevent duplicates based on time
        if self.history and self.history[-1].get('date') == bar.get('date'):
            self.history[-1] = bar
        else:
            self.history.append(bar)
        if len(self.history) > max_bars:
            self.history.pop(0)

class MomentumDetectionEngine:
    def __init__(self, config: MomentumConfig = None):
        self.config = config or MomentumConfig()
        self.trackers: Dict[str, StockTracker] = {}
        
    def get_tracker(self, symbol: str) -> StockTracker:
        if symbol not in self.trackers:
            self.trackers[symbol] = StockTracker(symbol)
        return self.trackers[symbol]

    def _calc_metrics(self, tracker: StockTracker, current_price: float, current_vol: float, daily_gain: float) -> dict:
        hist = tracker.history
        if not hist:
            return {}
            
        metrics = {}
        
        # Append simulated current candle for math (if not closed)
        current_candle = {
            "date": "CURRENT",
            "open": hist[-1]["close"],
            "high": max(hist[-1]["high"], current_price),
            "low": min(hist[-1]["low"], current_price),
            "close": current_price,
            "volume": current_vol
        }
        
        virtual_hist = hist + [current_candle]
        n_bars = len(virtual_hist)
        
        # Calculate Returns
        metrics['ret_1m'] = ((current_price - virtual_hist[-2]['close']) / virtual_hist[-2]['close']) * 100 if n_bars >= 2 else 0
        metrics['ret_2m'] = ((current_price - virtual_hist[-3]['close']) / virtual_hist[-3]['close']) * 100 if n_bars >= 3 else metrics['ret_1m']
        metrics['ret_5m'] = ((current_price - virtual_hist[-6]['close']) / virtual_hist[-6]['close']) * 100 if n_bars >= 6 else metrics['ret_2m']
        
        # Calculate Range & Expansion
        metrics['candle_range'] = virtual_hist[-1]['high'] - virtual_hist[-1]['low']
        
        # Avg Range last 10
        lookback = min(10, n_bars - 1)
        if lookback > 0:
            ranges = [b['high'] - b['low'] for b in virtual_hist[-lookback-1:-1]]
            metrics['avg_range_10'] = sum(ranges) / len(ranges)
            metrics['range_expansion'] = metrics['candle_range'] / metrics['avg_range_10'] if metrics['avg_range_10'] > 0 else 1.0
        else:
            metrics['avg_range_10'] = 0
            metrics['range_expansion'] = 1.0
            
        # VWAP Approximation (simple cumulative typical price)
        cum_vol = 0
        cum_tp_vol = 0
        for b in virtual_hist:
            tp = (b['high'] + b['low'] + b['close']) / 3
            v = b['volume']
            cum_vol += v
            cum_tp_vol += tp * v
        
        metrics['vwap'] = cum_tp_vol / cum_vol if cum_vol > 0 else current_price
        metrics['price_to_vwap_pct'] = ((current_price - metrics['vwap']) / metrics['vwap']) * 100
        
        # 9 EMA Approximation
        ema = virtual_hist[0]['close']
        multiplier = 2 / (9 + 1)
        for b in virtual_hist[1:]:
            ema = (b['close'] - ema) * multiplier + ema
        metrics['ema_9'] = ema
        metrics['price_to_ema9_pct'] = ((current_price - metrics['ema_9']) / metrics['ema_9']) * 100
        
        # VWAP/EMA Rising
        if n_bars >= 3:
            metrics['ema9_rising'] = metrics['ema_9'] > hist[-2].get('ema_9', ema)
            metrics['vwap_rising'] = metrics['vwap'] > hist[-2].get('vwap', metrics['vwap'])
        else:
            metrics['ema9_rising'] = True
            metrics['vwap_rising'] = True
            
        # RVOL (Current vol vs avg 10m vol)
        if lookback > 0:
            vols = [b['volume'] for b in virtual_hist[-lookback-1:-1]]
            metrics['avg_vol_10'] = sum(vols) / len(vols)
            metrics['rvol_1m'] = current_vol / metrics['avg_vol_10'] if metrics['avg_vol_10'] > 0 else 1.0
            
            # Vol Accel
            prev_vol = vols[-1] if vols else 1
            metrics['vol_accel'] = current_vol / prev_vol if prev_vol > 0 else 1.0
        else:
            metrics['avg_vol_10'] = 0
            metrics['rvol_1m'] = 1.0
            metrics['vol_accel'] = 1.0
            
        # HH/HL
        metrics['is_hh'] = current_price >= max([b['high'] for b in hist]) if hist else True
        metrics['daily_gain'] = daily_gain
        
        return metrics

    def _calculate_score(
        self,
        ret_1m: float,
        ret_2m: float,
        rvol_1m: float,
        vol_accel: float,
        range_expansion: float,
        is_hh: bool,
        price_to_vwap_pct: float,
        vwap_rising: bool,
        price_to_ema9_pct: float,
        ema9_rising: bool,
        trend_5m_bullish: bool,
        trend_15m_bullish: bool,
        near_hod_pmh: bool,
        room_to_resistance_pct: float,
    ) -> int:
        """
        Main Momentum Score.

        Measures how strong the stock's CURRENT momentum is.
        It is NOT a probability percentage and does NOT determine entry timing.

        Max Score = 100

        1M Price Velocity / Acceleration : 25
        1M RVOL / Volume Strength        : 20
        Volume Acceleration              : 15
        Range Expansion                  : 10
        5M Trend / Structure             : 10
        15M Trend                        : 5
        HH Bullish Structure             : 5
        VWAP + 9EMA Alignment            : 5
        HOD/PMH + Room                   : 5
        """

        score = 0

        # ---------------------------------------------------------
        # 1. 1M PRICE VELOCITY / ACCELERATION (0-25)
        # ---------------------------------------------------------
        if isinstance(ret_1m, (int, float)) and isinstance(ret_2m, (int, float)):
            ret_max = max(ret_1m, ret_2m / 1.5)

            vel_score = min(
                25,
                max(0, int(ret_max * 10))
            )

            score += vel_score

        # ---------------------------------------------------------
        # 2. 1M RVOL / VOLUME STRENGTH (0-20)
        # ---------------------------------------------------------
        if isinstance(rvol_1m, (int, float)) and rvol_1m > 1:
            rvol_score = min(
                20,
                max(0, int((rvol_1m - 1) * 4))
            )

            score += rvol_score

        # ---------------------------------------------------------
        # 3. VOLUME ACCELERATION (0-15)
        # ---------------------------------------------------------
        if isinstance(vol_accel, (int, float)) and vol_accel > 1:
            vaccel_score = min(
                15,
                max(0, int((vol_accel - 1) * 5))
            )

            score += vaccel_score

        # ---------------------------------------------------------
        # 4. RANGE EXPANSION (0-10)
        # ---------------------------------------------------------
        if isinstance(range_expansion, (int, float)) and range_expansion > 1:
            range_score = min(
                10,
                max(0, int((range_expansion - 1) * 10))
            )

            score += range_score

        # ---------------------------------------------------------
        # 5. 5M BULLISH TREND / STRUCTURE (0-10)
        # ---------------------------------------------------------
        if trend_5m_bullish:
            score += 10

        # ---------------------------------------------------------
        # 6. 15M BULLISH TREND (0-5)
        # ---------------------------------------------------------
        if trend_15m_bullish:
            score += 5

        # ---------------------------------------------------------
        # 7. HIGHER HIGH / BULLISH STRUCTURE (0-5)
        # ---------------------------------------------------------
        if is_hh:
            score += 5

        # ---------------------------------------------------------
        # 8. VWAP + 9 EMA ALIGNMENT (0-5)
        # ---------------------------------------------------------
        if (
            isinstance(price_to_vwap_pct, (int, float))
            and price_to_vwap_pct > 0
            and vwap_rising
        ):
            score += 2.5

        if (
            isinstance(price_to_ema9_pct, (int, float))
            and price_to_ema9_pct > 0
            and ema9_rising
        ):
            score += 2.5

        # ---------------------------------------------------------
        # 9. HOD / PMH + ROOM TO RESISTANCE (0-5)
        # ---------------------------------------------------------
        if near_hod_pmh:

            # Plenty of room before meaningful resistance
            if (
                isinstance(room_to_resistance_pct, (int, float))
                and room_to_resistance_pct >= 2.0
            ):
                score += 5

            # Some room
            elif (
                isinstance(room_to_resistance_pct, (int, float))
                and room_to_resistance_pct >= 1.0
            ):
                score += 3

            # Very close to resistance
            elif (
                isinstance(room_to_resistance_pct, (int, float))
                and room_to_resistance_pct > 0
            ):
                score += 1

        # ---------------------------------------------------------
        # FINAL SCORE
        # ---------------------------------------------------------
        return min(100, max(0, int(round(score))))

    def evaluate_symbol(self, symbol: str, current_price: float, current_vol: float, daily_gain: float, new_bars: List[Dict]) -> dict:
        tracker = self.get_tracker(symbol)
        now = time.time()
        
        # Update history
        for bar in new_bars:
            tracker.add_history_bar(bar, self.config.max_history_bars)
            
        metrics = self._calc_metrics(tracker, current_price, current_vol, daily_gain)
        if not metrics:
            return {"state": tracker.state.value, "reason": f"Gathering data... | +{daily_gain:.1f}% Day", "score": 0, "metrics": {}}
            
        tracker.momentum_score = self._calculate_score(
            ret_1m=metrics.get('ret_1m', 0),
            ret_2m=metrics.get('ret_2m', 0),
            rvol_1m=metrics.get('rvol_1m', 1.0),
            vol_accel=metrics.get('vol_accel', 1.0),
            range_expansion=metrics.get('range_expansion', 1.0),
            is_hh=metrics.get('is_hh', False),
            price_to_vwap_pct=metrics.get('price_to_vwap_pct', 0),
            vwap_rising=metrics.get('vwap_rising', False),
            price_to_ema9_pct=metrics.get('price_to_ema9_pct', 0),
            ema9_rising=metrics.get('ema9_rising', False),
            trend_5m_bullish=metrics.get('trend_5m_bullish', False),
            trend_15m_bullish=metrics.get('trend_15m_bullish', False),
            near_hod_pmh=metrics.get('near_hod_pmh', False),
            room_to_resistance_pct=metrics.get('room_to_resistance_pct', 0.0)
        )
        
        def build_active_reason():
            return f"ACTIVE MOMENTUM | +{metrics['ret_1m']:.1f}% 1m | RVOL {metrics['rvol_1m']:.1f}x | Range {metrics['range_expansion']:.1f}x | {'Above VWAP' if metrics['price_to_vwap_pct']>0 else 'Below VWAP'} | {'New HOD' if metrics['is_hh'] else 'Inside Range'}"
            
        def build_expired_reason(cause):
            return f"MOMENTUM EXPIRED | {cause} | +{daily_gain:.1f}% Day"
            
        def build_cooling_reason():
            return f"COOLING | +{metrics['ret_1m']:.1f}% 1m | Vol slowing | Price sideways"

        if tracker.state == StockMomentumState.EXPIRED:
            if now - tracker.last_alert_time < self.config.cooldown_seconds:
                return {"state": tracker.state.value, "reason": tracker.reason, "score": tracker.momentum_score, "metrics": metrics}
            else:
                tracker.state = StockMomentumState.INACTIVE
                tracker.reason = f"Monitoring | +{daily_gain:.1f}% Day"
        
        if tracker.state == StockMomentumState.INACTIVE:
            if daily_gain >= self.config.min_daily_gain:
                if (metrics['ret_1m'] >= self.config.min_return_1m or metrics['ret_2m'] >= self.config.min_return_2m) and \
                   metrics['rvol_1m'] >= self.config.min_rvol_1m and \
                   metrics['range_expansion'] >= self.config.range_expansion_ratio and \
                   metrics['price_to_vwap_pct'] > 0:
                   
                   tracker.state = StockMomentumState.ACTIVE
                   tracker.reason = build_active_reason()
                   tracker.last_alert_time = now
                   tracker.bars_in_cooling = 0
            
            if tracker.state == StockMomentumState.INACTIVE:
                tracker.reason = f"Monitoring | +{daily_gain:.1f}% Day"
                   
        elif tracker.state == StockMomentumState.ACTIVE:
            tracker.reason = build_active_reason()
            
            if metrics['ret_1m'] < self.config.cooling_min_return and \
               metrics['range_expansion'] < self.config.cooling_range_shrink and \
               metrics['rvol_1m'] < 1.0 and not metrics['is_hh']:
               
               tracker.state = StockMomentumState.COOLING
               tracker.reason = build_cooling_reason()
               tracker.bars_in_cooling = 1
               
        elif tracker.state == StockMomentumState.COOLING:
            if metrics['ret_1m'] >= self.config.min_return_1m and metrics['rvol_1m'] >= self.config.min_rvol_1m and metrics['is_hh']:
                tracker.state = StockMomentumState.ACTIVE
                tracker.reason = build_active_reason()
                tracker.bars_in_cooling = 0
            else:
                tracker.bars_in_cooling += 1
                tracker.reason = build_cooling_reason()
                
                # ~4 updates = 1 bar, so grace_bars * 4 is roughly grace_bars in time if updating every 15s
                if tracker.bars_in_cooling >= self.config.cooling_grace_bars * 4: 
                    tracker.state = StockMomentumState.EXPIRED
                    tracker.reason = build_expired_reason("Price velocity & volume collapsed")
                    tracker.last_alert_time = now
                    
        return {
            "state": tracker.state.value,
            "reason": tracker.reason,
            "score": tracker.momentum_score,
            "metrics": metrics
        }
