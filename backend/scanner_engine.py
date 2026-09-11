import asyncio
import time
import math
from typing import Callable, Optional

try:
    from ib_insync import IB, ScannerSubscription
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False

from models import IBKRConnectionConfig
from momentum_scanner import MomentumDetectionEngine

class IBKRScannerEngine:
    def __init__(self, broadcast_callback: Callable):
        self.broadcast_callback = broadcast_callback
        self.config = IBKRConnectionConfig()
        self.scanner_ib: Optional[IB] = None
        self.momentum_engine = MomentumDetectionEngine()
        self._last_scan_time = 0
        self._hist_semaphore = asyncio.Semaphore(1)
        self._hist_cache = {}

    async def connect(self, config: IBKRConnectionConfig):
        self.config = config
        if not IB_INSYNC_AVAILABLE:
            return False
            
        try:
            if self.scanner_ib and self.scanner_ib.isConnected():
                self.scanner_ib.disconnect()

            self.scanner_ib = IB()
            await self.scanner_ib.connectAsync(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.clientId + 10,
                timeout=5
            )
            return True
        except Exception as e:
            print(f"Failed to reconnect scanner: {e}")
            return False

    async def scan_market(self):
        """Scans for momentum stocks using a dedicated IBKR connection to avoid affecting L2 data"""
        if not IB_INSYNC_AVAILABLE:
            return

        current_time = time.time()
        if not getattr(self, '_last_scan_time', None):
            self._last_scan_time = 0
            
        # Rate limit live IBKR scans to once every 10 seconds to prevent pacing violations
        if (current_time - self._last_scan_time) < 10:
            return
            
        self._last_scan_time = current_time

        if not getattr(self, 'scanner_ib', None) or not self.scanner_ib.isConnected():
            connected = await self.connect(self.config)
            if not connected:
                return

        scanner_ib = self.scanner_ib
        try:
            # Use the persistent dedicated connection
            
            sub = ScannerSubscription(
                instrument='STK',
                locationCode='STK.US.MAJOR',
                scanCode='HOT_BY_VOLUME',
                abovePrice=1.5
            )
            scan_data = await scanner_ib.reqScannerDataAsync(sub)
            
            results = []
            # Grab top 30 to give us enough buffer for custom python filtering
            contracts = [item.contractDetails.contract for item in scan_data[:30]]
            
            # Qualify contracts first (essential for reqMktData)
            await scanner_ib.qualifyContractsAsync(*contracts)
            
            # Request streaming market data with 165 (Misc Stats), 233 (RTVolume)
            # Note: 258 (Fundamental Ratios) is omitted as it causes Error 300 on some stocks and drops the entire subscription
            tickers = [scanner_ib.reqMktData(c, '165,233', False, False) for c in contracts]
            
            # Wait up to 3s for data to populate dynamically
            for _ in range(30):
                if sum(1 for t in tickers if not math.isnan(t.marketPrice())) >= 5:
                    break
                await asyncio.sleep(0.1)
            
            populated_count = sum(1 for t in tickers if not math.isnan(t.marketPrice()))
            print(f"[SCAN] Market data populated for {populated_count}/{len(tickers)} tickers.")

            # Fast market data filtering
            finalists = []
            
            try:
                for i, item in enumerate(scan_data[:30]):
                    contract = item.contractDetails.contract
                    ticker = tickers[i]
                    
                    last_price = ticker.marketPrice()
                    if math.isnan(last_price) or last_price == 0:
                        last_price = None

                    # ── Filter 1: Price must be >= $1.50 and < $15.00
                    if last_price is None or not (1.5 <= last_price < 15.0):
                        continue
                        
                    close_price = ticker.close
                    if math.isnan(close_price) or close_price == 0:
                        close_price = None
                        
                    change_pct = None
                    if last_price and close_price:
                        change_pct = ((last_price - close_price) / close_price) * 100
                    elif getattr(ticker, 'changePercent', None) and not math.isnan(ticker.changePercent):
                        change_pct = ticker.changePercent
                        
                    vol = ticker.volume
                    if math.isnan(vol):
                        vol = None

                    # ── Filter 2: Volume > 800k  OR  RV > 3x
                    rv = None
                    av_vol = getattr(ticker, 'avVolume', None)
                    if vol and av_vol and not math.isnan(av_vol) and av_vol > 0:
                        rv = vol / av_vol

                    vol_ok = (vol and vol > 800_000) or (rv and rv > 3.0)
                    if not vol_ok:
                        continue

                    # ── Filter 3: Free Float (without shortableShares fallback)
                    free_float = None
                    fr = getattr(ticker, 'fundamentalRatios', None)
                    if fr:
                        float_val = getattr(fr, 'FLOAT', None) or getattr(fr, 'Float', None)
                        if float_val:
                            try:
                                # IBKR typically provides FLOAT in millions
                                free_float = float(float_val) * 1_000_000
                            except Exception:
                                pass

                    finalists.append({
                        "contract": contract,
                        "last_price": last_price,
                        "change_pct": change_pct,
                        "vol": vol,
                        "rv": rv,
                        "free_float": free_float,
                        "vol_ok": vol_ok
                    })
                    
                    if len(finalists) >= 10:
                        break
            finally:
                # ALWAYS clean up market-data subscriptions
                for t in tickers:
                    try:
                        scanner_ib.cancelMktData(t.contract)
                    except Exception:
                        pass
                        
            print(f"[SCAN] Scanner generated {len(scan_data[:30])} candidates, {len(finalists)} survived fast filters.")

            # Limit historical data requests to avoid pacing violations (Limit is 60 req/10 mins)
            # Scan runs every 15 seconds (4x/min). Max 1 req/scan = 4 req/min = 40 req/10 mins. Safe.
            MAX_HIST_REQS = 1
            hist_reqs_this_scan = 0

            # Process historical data and momentum for finalists only
            for f in finalists:
                contract = f["contract"]
                last_price = f["last_price"]
                change_pct = f["change_pct"]
                vol = f["vol"]
                rv = f["rv"]
                free_float = f["free_float"]
                vol_ok = f["vol_ok"]
                
                tracker = self.momentum_engine.get_tracker(contract.symbol)
                new_bars = []
                
                if not tracker.history:
                    if hist_reqs_this_scan < MAX_HIST_REQS:
                        hist_reqs_this_scan += 1
                        try:
                            bars_obj = await self._safe_req_historical_data(
                                scanner_ib, contract, durationStr='3600 S',
                                barSizeSetting='1 min', whatToShow='TRADES',
                                useRTH=False, formatDate=1
                            )
                            if bars_obj:
                                new_bars = [{"date": str(b.date), "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume} for b in bars_obj]
                        except Exception as e:
                            print(f"[SCAN] Failed history fetch for {contract.symbol}: {e}")
                            
                if new_bars and new_bars[-1]['volume'] <= 10_000 and not tracker.history:
                     continue
                     
                momentum_data = self.momentum_engine.evaluate_symbol(
                    symbol=contract.symbol,
                    current_price=last_price,
                    current_vol=vol or 0,
                    daily_gain=change_pct or 0,
                    new_bars=new_bars
                )

                vol_str = "--"
                if vol:
                    if vol > 1_000_000:
                        vol_str = f"{vol/1_000_000:.1f}M"
                    elif vol > 1_000:
                        vol_str = f"{vol/1_000:.1f}K"
                    else:
                        vol_str = str(int(vol))
                
                def format_large(num):
                    if not num: return "--"
                    try:
                        n = float(num)
                        if n > 1_000_000: return f"{n/1_000_000:.1f}M"
                        if n > 1_000: return f"{n/1_000:.1f}K"
                        return str(int(n))
                    except:
                        return "--"
                        
                m_metrics = momentum_data.get("metrics") or {}
                move_5m = m_metrics.get("ret_5m")
                vol_1m = m_metrics.get("rvol_1m")
                # Vol Ratio: ratio of current 1m vol vs average 10m vol (or rvol)
                vol_ratio = m_metrics.get("rvol_1m")
                vol_accel = m_metrics.get("vol_accel")

                # Get raw 1m volume from the latest bar if present
                latest_bar_vol = new_bars[-1]["volume"] if new_bars else (vol or 0)

                results.append({
                    "symbol": contract.symbol,
                    "lastPrice": round(last_price, 2),
                    "changePercent": round(change_pct, 2) if change_pct is not None else "--",
                    "move5m": round(move_5m, 2) if move_5m is not None else None,
                    "vol1m": format_large(latest_bar_vol),
                    "volRatio": round(vol_ratio, 2) if vol_ratio is not None else None,
                    "volAccel": round(vol_accel, 2) if vol_accel is not None else None,
                    "volume": vol_str,
                    "rv": f"{rv:.1f}x" if rv else "--",
                    "freeFloat": format_large(free_float),
                    "reason": momentum_data["reason"],
                    "state": momentum_data["state"],
                    "score": momentum_data["score"],
                    "trend": "up" if (change_pct and change_pct > 0) else "down",
                    "specs": {
                        "price": last_price is not None and (1.5 <= last_price < 15.0),
                        "vol": vol is not None and vol > 800_000,
                        "rv": rv is not None and rv > 3.0,
                        "float": free_float is not None and (200_000 <= free_float <= 20_000_000)
                    }
                })
                
            # Sort results by score descending
            results.sort(key=lambda x: x.get("score", 0), reverse=True)

            await self.broadcast_callback({
                "type": "SCANNER_UPDATE",
                "data": results
            })
            
        except Exception as e:
            print(f"Scanner error: {e}")
            await self.broadcast_callback({"type": "ERROR", "data": {"message": f"Scanner failed: {e}"}})

    async def _safe_req_historical_data(self, client_ib, contract, durationStr, barSizeSetting, whatToShow, useRTH, formatDate, keepUpToDate=False):
        """
        Paced and centrally controlled historical data request.
        Uses exponential backoff for max 3 retries to prevent pacing violations.
        """
        max_retries = 3
        retry_delay = 5.0
        
        # Check cache (only for 1 min bars from scanner if keepUpToDate is False)
        is_scanner_cacheable = (durationStr == '3600 S' and barSizeSetting == '1 min' and not keepUpToDate)
        if is_scanner_cacheable:
            cached = self._hist_cache.get(contract.symbol)
            if cached and (time.time() - cached["timestamp"]) < 60:
                return cached["bars"]

        for attempt in range(1, max_retries + 1):
            try:
                # Strictly serialize historical data requests globally across the app
                async with self._hist_semaphore:
                    # Small intrinsic delay between any historical requests to avoid pacing violations
                    await asyncio.sleep(0.5)
                    bars = await client_ib.reqHistoricalDataAsync(
                        contract, endDateTime='', durationStr=durationStr,
                        barSizeSetting=barSizeSetting, whatToShow=whatToShow,
                        useRTH=useRTH, formatDate=formatDate, keepUpToDate=keepUpToDate
                    )
                    
                    if is_scanner_cacheable and bars:
                        self._hist_cache[contract.symbol] = {
                            "timestamp": time.time(),
                            "bars": bars
                        }
                        
                    return bars
                    
            except Exception as e:
                err_str = str(e)
                print(f"[HIST] {contract.symbol} request attempt {attempt}/{max_retries} failed: {err_str}")
                
                is_pacing_error = "162" in err_str or "pacing" in err_str.lower() or "Historical Market Data Service error" in err_str
                
                if attempt == max_retries:
                    print(f"[HIST] {contract.symbol} historical request failed after {max_retries} attempts.")
                    return []
                    
                # Backoff logic
                if is_pacing_error:
                    print(f"[HIST] {contract.symbol} pacing error detected - backing off {retry_delay * 2}s")
                    await asyncio.sleep(retry_delay * 2)
                    retry_delay *= 2
                else:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5

        return []
