import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class TradeSignalEngine:
    """
    Monitors price action to determine entry and exit points based on live data.
    """
    def __init__(self):
        self.state = "NEUTRAL" # NEUTRAL, ARMED_FOR_L2, IN_TRADE
        self.lookback_window = 15
        self.current_pullback_low = 0.0
        self.last_best_ask_price = 0.0
        self.last_best_ask_size = 0
        
    def analyze_entry_setup_1m(self, candles: List[Dict]) -> str:
        """
        Validates entry setup using 1-minute candles.
        """
        if len(candles) < self.lookback_window:
            return "INVALID_SETUP (Not enough candles)"
            
        recent_candles = candles[-self.lookback_window:]
        impulse_low = min([c['low'] for c in recent_candles])
        impulse_low_idx = next(i for i, c in enumerate(recent_candles) if c['low'] == impulse_low)
        
        subsequent_candles = recent_candles[impulse_low_idx:]
        if not subsequent_candles:
            return "INVALID_SETUP (No subsequent candles after low)"
            
        impulse_high = max([c['high'] for c in subsequent_candles])
        impulse_high_idx = impulse_low_idx + next(i for i, c in enumerate(subsequent_candles) if c['high'] == impulse_high)
        
        impulse_range = impulse_high - impulse_low
        if impulse_range <= 0:
            return "INVALID_SETUP (Impulse range <= 0)"
            
        pullback_candles = recent_candles[impulse_high_idx + 1:]
        candles_since_high = len(pullback_candles)
        
        if candles_since_high < 1 or candles_since_high > 4:
            return "INVALID_SETUP (Pullback duration must be strictly 1 to 4 candles)"
            
        self.current_pullback_low = min([c['low'] for c in pullback_candles])
        retracement_percentage = (impulse_high - self.current_pullback_low) / impulse_range
        
        if retracement_percentage >= 0.50:
            return "INVALID_SETUP (Pullback exceeded 50% of impulse leg - Trend reversed)"
            
        impulse_leg_candles = recent_candles[impulse_low_idx:impulse_high_idx + 1]
        green_impulse_candles = [c for c in impulse_leg_candles if c['close'] > c['open']]
        
        if not green_impulse_candles:
             return "INVALID_SETUP (No green candles in impulse leg)"
             
        avg_impulse_volume = sum([c['volume'] for c in green_impulse_candles]) / len(green_impulse_candles)
        avg_pullback_volume = sum([c['volume'] for c in pullback_candles]) / len(pullback_candles)
        
        if avg_pullback_volume >= avg_impulse_volume:
            return "INVALID_SETUP (Volume did not contract during pullback. Selling pressure is too high.)"
            
        return "VALID_SETUP"

    def check_micro_trend_reversal(self, current_5s_candle: Dict, previous_5s_candle: Dict):
        if current_5s_candle['close'] > current_5s_candle['open']:
            if current_5s_candle['close'] > previous_5s_candle['high']:
                self.state = "ARMED_FOR_L2"
                logger.info("Micro-trend reversal detected. State: ARMED_FOR_L2")
                
    def check_execution_trigger(self, current_best_bid: Dict, current_best_ask: Dict, recent_tape_velocity: float, spoofing_status: str) -> Optional[Dict]:
        if self.state != "ARMED_FOR_L2":
            return None
            
        if spoofing_status == "ABORT_TOXIC_BID_SPOOFING":
            logger.info("Aborting entry due to toxic bid spoofing.")
            self.state = "NEUTRAL"
            return None
            
        ask_price = current_best_ask.get('price', 0.0)
        ask_size = current_best_ask.get('size', 0)
        bid_price = current_best_bid.get('price', 0.0)
        bid_size = current_best_bid.get('size', 0)
        
        if self.last_best_ask_price > 0:
            if bid_price == self.last_best_ask_price and bid_size > (self.last_best_ask_size * 0.5):
                VELOCITY_THRESHOLD = 50.0
                if recent_tape_velocity > VELOCITY_THRESHOLD:
                    limit_price = bid_price + 0.01
                    stop_loss = self.current_pullback_low - 0.01
                    logger.info(f"EXECUTE_BUY_ORDER Limit Price: {limit_price}, Stop Loss: {stop_loss}")
                    self.state = "IN_TRADE"
                    return {
                        "action": "BUY",
                        "limit_price": limit_price,
                        "stop_loss": stop_loss
                    }
                    
        self.last_best_ask_price = ask_price
        self.last_best_ask_size = ask_size
        return None

    def check_exit_conditions(self, current_price: float, current_1m_candle: Dict, previous_1m_candle: Dict, ema_9_1m: Optional[float]) -> Optional[str]:
        """
        Determines if exit conditions are met based on price action and EMA.
        Exit rules:
        - Priority 1: Price drops below 9 EMA.
        - Priority 2: Price drops below the low of the 1m candle we entered in, or the previous 1m candle low.
        """
        if self.state != "IN_TRADE":
            return None
            
        if ema_9_1m and current_price < ema_9_1m:
            self.state = "NEUTRAL"
            return "EXIT (Broken 9 EMA on 1m chart)"

        # Check if price breaks the low of the current minute candle
        if current_price < current_1m_candle['low']:
            self.state = "NEUTRAL"
            return "EXIT (Broken current 1m candle low)"

        # Check if price breaks the low of the previous minute candle
        if previous_1m_candle and current_price < previous_1m_candle['low']:
            self.state = "NEUTRAL"
            return "EXIT (Broken previous 1m candle low)"

        return None
