import logging
from typing import List, Dict, Optional
from spoofing_watcher import SpoofingWatcher

logger = logging.getLogger(__name__)

class PredictionAlgo:
    def __init__(self, spoofing_watcher: SpoofingWatcher):
        self.spoofing_watcher = spoofing_watcher
        self.state = "NEUTRAL" # NEUTRAL, ARMED_FOR_L2, IN_TRADE
        self.lookback_window = 15
        
        # Validated parameters
        self.current_pullback_low = 0.0
        
        # Best ask state
        self.last_best_ask_price = 0.0
        self.last_best_ask_size = 0
        
    def analyze_1m_candles(self, candles: List[Dict]) -> str:
        """
        Expects a list of the last 15 1-minute candles.
        Candle dict format expected: {'high': float, 'low': float, 'close': float, 'open': float, 'volume': int, 'timestamp': float}
        """
        if len(candles) < self.lookback_window:
            return "INVALID_SETUP (Not enough candles)"
            
        recent_candles = candles[-self.lookback_window:]
        
        # Step 1: Identify Impulse
        impulse_low = min([c['low'] for c in recent_candles])
        
        # Find index of impulse low
        impulse_low_idx = next(i for i, c in enumerate(recent_candles) if c['low'] == impulse_low)
        
        # Find impulse high AFTER impulse low
        subsequent_candles = recent_candles[impulse_low_idx:]
        if not subsequent_candles:
            return "INVALID_SETUP (No subsequent candles after low)"
            
        impulse_high = max([c['high'] for c in subsequent_candles])
        impulse_high_idx = impulse_low_idx + next(i for i, c in enumerate(subsequent_candles) if c['high'] == impulse_high)
        
        impulse_range = impulse_high - impulse_low
        if impulse_range <= 0:
            return "INVALID_SETUP (Impulse range <= 0)"
            
        # Step 2: Validate Pullback Duration
        pullback_candles = recent_candles[impulse_high_idx + 1:]
        candles_since_high = len(pullback_candles)
        
        if candles_since_high < 1 or candles_since_high > 4:
            return "INVALID_SETUP (Pullback duration must be strictly 1 to 4 candles)"
            
        # Step 3: Validate Pullback Depth
        self.current_pullback_low = min([c['low'] for c in pullback_candles])
        retracement_percentage = (impulse_high - self.current_pullback_low) / impulse_range
        
        if retracement_percentage >= 0.50:
            return "INVALID_SETUP (Pullback exceeded 50% of impulse leg - Trend reversed)"
            
        # Step 4: Validate Volume Contraction
        impulse_leg_candles = recent_candles[impulse_low_idx:impulse_high_idx + 1]
        green_impulse_candles = [c for c in impulse_leg_candles if c['close'] > c['open']]
        
        if not green_impulse_candles:
             return "INVALID_SETUP (No green candles in impulse leg)"
             
        avg_impulse_volume = sum([c['volume'] for c in green_impulse_candles]) / len(green_impulse_candles)
        avg_pullback_volume = sum([c['volume'] for c in pullback_candles]) / len(pullback_candles)
        
        if avg_pullback_volume >= avg_impulse_volume:
            return "INVALID_SETUP (Volume did not contract during pullback. Selling pressure is too high.)"
            
        return "VALID_SETUP"

    def on_5s_candle_close(self, current_5s_candle: Dict, previous_5s_candle: Dict):
        """
        Step 5: Micro-Trend Reversal
        """
        # We only look for micro reversal if the 1m setup was just validated or is valid
        if current_5s_candle['close'] > current_5s_candle['open']: # Green candle
            if current_5s_candle['close'] > previous_5s_candle['high']:
                self.state = "ARMED_FOR_L2"
                logger.info("Micro-trend reversal detected. State: ARMED_FOR_L2")
                
    def on_tape_and_l2_update(self, current_best_bid: Dict, current_best_ask: Dict, recent_tape_velocity: float) -> Optional[Dict]:
        """
        Step 8: Final Execution Trigger
        """
        if self.state != "ARMED_FOR_L2":
            return None
            
        spoofing_status = self.spoofing_watcher.get_spoofing_status()
        if spoofing_status == "ABORT_TOXIC_BID_SPOOFING":
            logger.info("Aborting entry due to toxic bid spoofing.")
            self.state = "NEUTRAL"
            return None
            
        # Monitor Best Ask
        ask_price = current_best_ask.get('price', 0.0)
        ask_size = current_best_ask.get('size', 0)
        bid_price = current_best_bid.get('price', 0.0)
        bid_size = current_best_bid.get('size', 0)
        
        # Condition A: Tape eats the Ask Wall (Size goes to 0 or price moves up)
        # Condition B: The Ask Flip
        # If the previous best ask price becomes the new best bid price with significant size
        
        if self.last_best_ask_price > 0:
            if bid_price == self.last_best_ask_price and bid_size > (self.last_best_ask_size * 0.5): # Significant size
                
                # Condition C: Tape Acceleration
                VELOCITY_THRESHOLD = 50.0 # arbitrary threshold for example
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
