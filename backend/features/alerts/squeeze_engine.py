import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("SqueezeEngine")
logger.setLevel(logging.WARNING)

class SqueezeScoreEngine:
    def __init__(self):
        self.last_alert_time = 0
        self.cooldown_period = 300 # seconds
        self.alert_reset_threshold = 70
        self.is_in_cooldown = False
        
        self.last_score = 0
        self.last_fuel = 0
        self.last_ignition = 0
        self.last_bias = "NEUTRAL"
        
    def _normalize_score(self, value: float, min_val: float, max_val: float) -> float:
        """Helper to safely normalize a value to 0-100 based on expected min/max."""
        if max_val == min_val: return 0.0
        normalized = ((value - min_val) / (max_val - min_val)) * 100
        return max(0.0, min(100.0, normalized))

    def calculate_fuel_score(self, fuel_data: Dict[str, Any]) -> float:
        """
        Calculates the SQUEEZE POTENTIAL (Fuel) 0-100 score.
        Weights: SI (12), DTC (7), Fee (7), FeeChange (4), Util/Avail (4), FloatStruct (3), ShortVolAct (3). Total=40
        """
        score = 0.0
        total_weight = 0.0
        
        si_pct = fuel_data.get('short_interest_pct')
        if si_pct is not None:
            # SI% > 20% is extremely high fuel. 5% is low.
            score += self._normalize_score(si_pct, 5.0, 25.0) * 12.0
            total_weight += 12.0
            
        dtc = fuel_data.get('days_to_cover')
        if dtc is not None:
            score += self._normalize_score(dtc, 1.0, 5.0) * 7.0
            total_weight += 7.0
            
        borrow_fee = fuel_data.get('borrow_fee')
        if borrow_fee is not None:
            score += self._normalize_score(borrow_fee, 5.0, 100.0) * 7.0
            total_weight += 7.0
            
        fee_change = fuel_data.get('borrow_fee_change')
        if fee_change is not None:
            score += self._normalize_score(fee_change, 0.0, 20.0) * 4.0
            total_weight += 4.0
            
        utilization = fuel_data.get('utilization')
        if utilization is not None:
            score += self._normalize_score(utilization, 70.0, 100.0) * 4.0
            total_weight += 4.0
            
        float_size = fuel_data.get('float_size')
        if float_size is not None:
            # Smaller float = higher fuel. e.g. < 5M is great, > 50M is poor.
            val = self._normalize_score(float_size, 1_000_000, 50_000_000)
            score += (100.0 - val) * 3.0 # Invert so smaller float = higher score
            total_weight += 3.0
            
        short_vol = fuel_data.get('short_volume_activity')
        if short_vol is not None:
            score += self._normalize_score(short_vol, 30.0, 60.0) * 3.0
            total_weight += 3.0
            
        if total_weight == 0:
            return 0.0
            
        return score / total_weight * 100.0

    def calculate_ignition_score(self, ig_data: Dict[str, Any]) -> float:
        """
        Calculates SQUEEZE IGNITION 0-100 score.
        Total weight = 60
        """
        score = 0.0
        total_weight = 0.0
        
        # 10s/1m Price Momentum (10)
        mom = ig_data.get('momentum_pct')
        if mom is not None:
            score += self._normalize_score(mom, 0.0, 2.0) * 10.0
            total_weight += 10.0
            
        # RVOL / Volume Accel (8)
        rvol = ig_data.get('rvol')
        if rvol is not None:
            score += self._normalize_score(rvol, 1.0, 5.0) * 8.0
            total_weight += 8.0
            
        # Time & Sales Buying Pressure (8)
        buy_pct = ig_data.get('buy_pressure_pct')
        if buy_pct is not None:
            score += self._normalize_score(buy_pct, 45.0, 80.0) * 8.0
            total_weight += 8.0
            
        # Tape Velocity (5)
        tape_vel = ig_data.get('tape_velocity')
        if tape_vel is not None:
            score += self._normalize_score(tape_vel, 0.5, 5.0) * 5.0
            total_weight += 5.0
            
        # Price Response to Aggressive Volume (7)
        price_resp = ig_data.get('price_response_score')
        if price_resp is not None:
            # explicit price-response logic happens before passing into this dict
            # Expecting a 0-100 score where 100 = strong upward price response to volume
            score += price_resp * 7.0
            total_weight += 7.0
            
        # L2 Bid Strength/Absorption (5)
        bid_str = ig_data.get('l2_bid_strength')
        if bid_str is not None:
            score += bid_str * 5.0
            total_weight += 5.0
            
        # Ask Depletion/Wall Consumption (7)
        ask_depletion = ig_data.get('ask_depletion_score')
        if ask_depletion is not None:
            score += ask_depletion * 7.0
            total_weight += 7.0
            
        # HOD/Resistance Breakout (4)
        hod_dist = ig_data.get('hod_distance_pct')
        if hod_dist is not None:
            # If distance is <= 0.5%, it's 100.
            val = max(0.0, 100.0 - self._normalize_score(hod_dist, 0.0, 3.0))
            score += val * 4.0
            total_weight += 4.0
            
        # Pullback Completion + 10s HL->HH (3)
        structure_score = ig_data.get('structure_score')
        if structure_score is not None:
            score += structure_score * 3.0
            total_weight += 3.0
            
        # VWAP/9EMA/21EMA Alignment (3)
        alignment_score = ig_data.get('alignment_score')
        if alignment_score is not None:
            score += alignment_score * 3.0
            total_weight += 3.0
            
        if total_weight == 0:
            return 0.0
            
        return score / total_weight * 100.0

    def calculate_total_score(self, fuel_data: Dict[str, Any], ig_data: Dict[str, Any]) -> Dict[str, Any]:
        fuel_score = self.calculate_fuel_score(fuel_data)
        ig_score = self.calculate_ignition_score(ig_data)
        
        has_critical_data = ig_data.get('buy_pressure_pct') is not None and ig_data.get('tape_velocity') is not None
        
        # 40/60 weighting
        total_score = (fuel_score * 0.4) + (ig_score * 0.6)
        
        # If no real-time L2/T&S data, cap the score
        if not has_critical_data:
            total_score = min(total_score, 50.0)
            
        # If there's 0 fuel data available, fuel_score might be 0. We don't want the max score to be 60.
        # But wait, user said "dynamically reduce the contribution of any unavailable... instead of inventing values"
        # However, if total_weight in fuel is 0, then we rely entirely on ignition.
        if fuel_score == 0 and not fuel_data:
            # No fuel data provided at all. Rely heavily on ignition, but penalize max score.
            total_score = ig_score * 0.8  # Capped at 80
            
        total_score = round(total_score)
        fuel_score = round(fuel_score)
        ig_score = round(ig_score)
        
        classification = self._get_classification(total_score)
        
        self.last_score = total_score
        self.last_fuel = fuel_score
        self.last_ignition = ig_score
        
        # Determine Bias
        bias = "NEUTRAL"
        buy_pct = ig_data.get('buy_pressure_pct', 50.0)
        if buy_pct >= 55: bias = "BULLISH"
        elif buy_pct <= 45: bias = "BEARISH"
        self.last_bias = bias
        
        return {
            'squeeze_score': total_score,
            'squeeze_potential': fuel_score,
            'squeeze_ignition': ig_score,
            'classification': classification,
            'order_flow_bias': bias
        }
        
    def _get_classification(self, score: int) -> str:
        if score <= 39: return "NO SQUEEZE SETUP"
        if score <= 59: return "LOW POTENTIAL"
        if score <= 69: return "DEVELOPING"
        if score <= 79: return "HIGH POTENTIAL / WATCH"
        if score <= 89: return "HIGH-CONFIDENCE SQUEEZE SETUP"
        return "EXTREME SQUEEZE SETUP"
        
    def check_for_alert(self, ticker: str, price: float, result: Dict[str, Any], ig_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        score = result['squeeze_score']
        ig_score = result['squeeze_ignition']
        bias = result['order_flow_bias']
        
        # Reset Cooldown logic
        if self.is_in_cooldown and score < self.alert_reset_threshold:
            self.is_in_cooldown = False
            logger.info(f"[{ticker}] Squeeze alert cooldown reset. Score dropped below {self.alert_reset_threshold}")
            
        if self.is_in_cooldown:
            return None
            
        # The primary alert threshold must be SQUEEZE SCORE >= 80 AND SQUEEZE IGNITION >= 70 AND ORDER FLOW BIAS must not be bearish; 
        # additionally, require sufficient real-time data quality and at least one meaningful bullish ignition condition 
        # such as ask depletion + positive price response, strong aggressive buying + tape acceleration, or HOD/resistance breakout with expanding volume.
        
        has_bullish_condition = (
            (ig_data.get('ask_depletion_score', 0) > 70 and ig_data.get('price_response_score', 0) > 70) or
            (ig_data.get('buy_pressure_pct', 0) > 65 and ig_data.get('tape_velocity', 0) > 3.0) or
            (ig_data.get('hod_distance_pct', 5) < 0.2 and ig_data.get('rvol', 0) > 2.0)
        )
        
        is_high_quality = ig_data.get('buy_pressure_pct') is not None
        
        if score >= 80 and ig_score >= 70 and bias != "BEARISH" and is_high_quality and has_bullish_condition:
            self.is_in_cooldown = True
            
            if score >= 90: severity = "EXTREME SQUEEZE ALERT"
            elif score >= 85: severity = "STRONG SQUEEZE ALERT"
            else: severity = "SQUEEZE WATCH ALERT"
            
            alert = {
                "type": "SHORT_SQUEEZE_ALERT",
                "severity": severity,
                "ticker": ticker,
                "price": price,
                "squeeze_score": score,
                "squeeze_potential": result['squeeze_potential'],
                "squeeze_ignition": ig_score,
                "buy_pressure": f"{ig_data.get('buy_pressure_pct', 0):.1f}%",
                "tape_velocity": f"{ig_data.get('tape_velocity', 0):.1f}/s",
                "rvol": f"{ig_data.get('rvol', 0):.1f}x",
                "reason": "Squeeze score crossed 80 with strong real-time ignition."
            }
            logger.info(f"🚨 {severity} on {ticker} @ {price}. Score: {score}/100")
            return alert
            
        return None
