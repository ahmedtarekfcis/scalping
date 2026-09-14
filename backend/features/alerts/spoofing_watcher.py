import time
import collections
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class SpoofingWatcher:
    def __init__(self):
        self.SPOOF_THRESHOLD_SHARES = 10000
        self.SPOOF_TIME_WINDOW_MS = 200
        self.ROLLING_SPOOF_WINDOW_SEC = 10
        
        self.bid_spoof_counter = 0
        self.ask_spoof_counter = 0
        
        # State tracking
        self._last_bids = {}
        self._last_asks = {}
        
        # History of tape prints to match against cancellations
        self._recent_tape_prints = collections.deque(maxlen=1000)
        
        # Track active large orders: price -> {size, timestamp, side}
        self._tracked_large_orders = {}
        
        # Track spoof events: list of timestamps
        self._bid_spoof_events = []
        self._ask_spoof_events = []

    def _cleanup_old_events(self, current_time: float):
        cutoff = current_time - self.ROLLING_SPOOF_WINDOW_SEC
        self._bid_spoof_events = [t for t in self._bid_spoof_events if t >= cutoff]
        self._ask_spoof_events = [t for t in self._ask_spoof_events if t >= cutoff]
        self.bid_spoof_counter = len(self._bid_spoof_events)
        self.ask_spoof_counter = len(self._ask_spoof_events)

    def on_tape_tick(self, price: float, size: int, side: str, timestamp: Optional[float] = None):
        """Record a tape print to match against potential cancellations."""
        ts = timestamp if timestamp is not None else time.time()
        self._recent_tape_prints.append({'price': price, 'size': size, 'side': side, 'timestamp': ts})

    def on_l2_update(self, current_price: float, bids: List[Dict], asks: List[Dict], timestamp: Optional[float] = None):
        ts = timestamp if timestamp is not None else time.time()
        self._cleanup_old_events(ts)
        
        current_bids = {b['price']: b['size'] for b in bids}
        current_asks = {a['price']: a['size'] for a in asks}
        
        # Process Bids
        self._process_side(current_bids, self._last_bids, 'BID', ts)
        # Process Asks
        self._process_side(current_asks, self._last_asks, 'ASK', ts)
        
        self._last_bids = current_bids
        self._last_asks = current_asks
        
    def _process_side(self, current_levels: Dict[float, int], last_levels: Dict[float, int], side: str, ts: float):
        # 1. Track new or increased large orders
        for price, size in current_levels.items():
            if size >= self.SPOOF_THRESHOLD_SHARES:
                last_size = last_levels.get(price, 0)
                if size > last_size:
                    # New large order or size increased
                    order_key = (price, side)
                    if order_key not in self._tracked_large_orders:
                        self._tracked_large_orders[order_key] = {
                            'initial_size': size,
                            'timestamp': ts,
                            'side': side,
                            'price': price
                        }
        
        # 2. Check for cancellations of tracked large orders
        keys_to_remove = []
        for (price, tracked_side), order_info in self._tracked_large_orders.items():
            if tracked_side != side:
                continue
            
            current_size = current_levels.get(price, 0)
            initial_size = order_info['initial_size']
            order_ts = order_info['timestamp']
            
            # If the size dropped significantly (cancelled)
            if current_size < initial_size:
                time_alive_ms = (ts - order_ts) * 1000
                
                # Was it cancelled within the spoof window?
                if time_alive_ms <= self.SPOOF_TIME_WINDOW_MS:
                    size_difference = initial_size - current_size
                    
                    # Check if this size difference executed on the tape
                    executed_size = self._check_tape_execution(price, side, order_ts, ts)
                    
                    if executed_size < size_difference * 0.5: # Mostly cancelled, not executed
                        # Spoofing detected!
                        if side == 'BID':
                            self._bid_spoof_events.append(ts)
                            self.bid_spoof_counter = len(self._bid_spoof_events)
                        else:
                            self._ask_spoof_events.append(ts)
                            self.ask_spoof_counter = len(self._ask_spoof_events)
                        
                        logger.info(f"Spoofing detected on {side} at {price}. Counter: {self.bid_spoof_counter if side=='BID' else self.ask_spoof_counter}")
                
                # Order no longer exists in its initial large form
                keys_to_remove.append((price, side))
                
            # If the order is older than the spoof window, we stop tracking it for spoofing purposes
            elif (ts - order_ts) * 1000 > self.SPOOF_TIME_WINDOW_MS:
                keys_to_remove.append((price, side))
                
        for k in keys_to_remove:
            del self._tracked_large_orders[k]

    def _check_tape_execution(self, price: float, side: str, start_ts: float, end_ts: float) -> int:
        """Check how much of the order executed on the tape within the timeframe."""
        executed = 0
        for print in reversed(self._recent_tape_prints):
            if print['timestamp'] < start_ts:
                break
            if print['timestamp'] <= end_ts:
                # Tape side is often relative to aggression, but any execution at this price might match
                if print['price'] == price:
                    executed += print['size']
        return executed

    def get_spoofing_status(self) -> str:
        """Returns the current conviction level based on spoofing counters."""
        if self.bid_spoof_counter >= 2:
            return "ABORT_TOXIC_BID_SPOOFING"
        if self.ask_spoof_counter >= 2:
            return "HIGH_CONVICTION_BULLISH_ACCUMULATION"
        return "NEUTRAL"
