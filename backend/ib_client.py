import asyncio
import datetime
import random
import time
from typing import Callable, Dict, List, Optional
import math
from zoneinfo import ZoneInfo

try:
    from ib_insync import IB, Stock, ScannerSubscription, util
    from ib_insync.objects import DOMLevel
    import ib_insync.wrapper
    util.patchAsyncio()
    IB_INSYNC_AVAILABLE = True

    # --- Monkey Patch for ib_insync L2 Depth IndexError bug ---
    orig_updateMktDepthL2 = ib_insync.wrapper.Wrapper.updateMktDepthL2

    def patched_updateMktDepthL2(self, reqId, position, marketMaker, operation, side, price, size, *args, **kwargs):
        try:
            orig_updateMktDepthL2(self, reqId, position, marketMaker, operation, side, price, size, *args, **kwargs)
        except IndexError:
            ticker = getattr(self, 'reqId2Ticker', {}).get(reqId)
            if ticker:
                dom = ticker.domBids if side == 1 else ticker.domAsks
                if operation == 0:
                    while len(dom) < position:
                        dom.append(DOMLevel(0, 0, ''))
                    dom.insert(position, DOMLevel(price, size, marketMaker))
                elif operation == 1:
                    while len(dom) <= position:
                        dom.append(DOMLevel(0, 0, ''))
                    dom[position] = DOMLevel(price, size, marketMaker)
                elif operation == 2:
                    if position < len(dom):
                        dom.pop(position)

    ib_insync.wrapper.Wrapper.updateMktDepthL2 = patched_updateMktDepthL2
    # ------------------------------------------------------------

except ImportError:
    IB_INSYNC_AVAILABLE = False

from models import DepthLevel, OrderBook, TapeTick, IBKRConnectionConfig, ConnectionStatus
from analytics_engine import QuantEngine
from momentum_scanner import MomentumDetectionEngine

class IBKRMarketEngine:
    """
    Manages real-time market data connection to IBKR (TWS/IB Gateway) using ib_insync and asyncio.
    Provides automatic fallback / mock simulation mode for high-speed testing anytime.
    """
    def __init__(self, broadcast_callback: Callable):
        self.broadcast_callback = broadcast_callback
        self.config = IBKRConnectionConfig()
        self.ib: Optional[IB] = None
        self.scanner_ib: Optional[IB] = None
        self.is_connected = False
        self.active_symbol: Optional[str] = None
        self.last_error = None
        
        # State tracking
        self.current_book: Dict[str, OrderBook] = {}
        self.hist_fetch_task: Optional[asyncio.Task] = None
        self.depth_ticker = None
        self.mkt_ticker = None
        self.contract = None
        self._last_tape_tick: Optional[TapeTick] = None
        self._tape_aggregation_task: Optional[asyncio.Task] = None

        # Intelligence Engine
        self.quant_engine = QuantEngine()
        self.momentum_engine = MomentumDetectionEngine()

        # Sample market makers for realistic L2 look
        self.mmids = ["ISLD", "ARCA", "EDGA", "EDGX", "BATS", "NSDQ", "DRCT", "MEMX", "IEX", "NYS"]

        # Historical Data Request Pacing
        self._hist_semaphore = asyncio.Semaphore(1)
        self._hist_cache = {}

    async def initialize(self):
        """Initial start: ready and idle until symbol subscription"""
        if IB_INSYNC_AVAILABLE:
            await self.connect_ibkr(self.config)

    def get_status(self) -> ConnectionStatus:
        return ConnectionStatus(
            connected=self.is_connected,
            activeSymbol=self.active_symbol,
            host=self.config.host,
            port=self.config.port,
            clientId=self.config.clientId,
            error=self.last_error
        )

    async def connect_ibkr(self, config: IBKRConnectionConfig):
        self.config = config
        self.last_error = None

        if not IB_INSYNC_AVAILABLE:
            self.is_connected = False
            return {"status": "error", "message": "IB_INSYNC is not available"}

        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            if getattr(self, 'scanner_ib', None) and self.scanner_ib.isConnected():
                self.scanner_ib.disconnect()

            self.ib = IB()
            # Asynchronous connection to TWS
            await self.ib.connectAsync(
                host=config.host,
                port=config.port,
                clientId=config.clientId,
                timeout=5
            )
            
            # Persistent scanner connection to avoid IB Gateway spam
            self.scanner_ib = IB()
            await self.scanner_ib.connectAsync(
                host=config.host,
                port=config.port,
                clientId=config.clientId + 10,
                timeout=5
            )
            
            self.is_connected = True
            if self.active_symbol:
                await self.subscribe_symbol(self.active_symbol)
            return {"status": "success", "mode": "live", "message": f"Connected to IBKR at {config.host}:{config.port}"}
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            return {"status": "error", "mode": "none", "error": str(e)}

    async def subscribe_symbol(self, symbol: str):
        symbol = symbol.upper().strip()
        self.active_symbol = symbol
        
        # Reset Intelligence Engine
        self.quant_engine.reset(symbol)

        if not self.ib or not self.ib.isConnected():
            return

        # Cancel previous subscriptions if any
        try:
            if self.depth_ticker:
                self.depth_ticker.updateEvent -= self._on_depth_update
                self.ib.cancelMktDepth(self.contract)
            if self.mkt_ticker:
                self.mkt_ticker.updateEvent -= self._on_mkt_data_update
                self.ib.cancelMktData(self.contract)
            if self.ib:
                self.ib.pendingTickersEvent -= self._on_tick_by_tick
            
            if getattr(self, 'live_bars_1m', None):
                self.live_bars_1m.updateEvent -= self._on_1m_bar_update
                try:
                    self.ib.cancelHistoricalData(self.live_bars_1m)
                except Exception:
                    pass
                self.live_bars_1m = None

            if self.hist_fetch_task and not self.hist_fetch_task.done():
                self.hist_fetch_task.cancel()
        except Exception:
            pass

        try:
            self.contract = Stock(symbol, 'SMART', 'USD')
            await self.ib.qualifyContractsAsync(self.contract)

            # Request delayed market data (3) if real-time stream is not subscribed on account, or 1 (real-time)
            try:
                self.ib.reqMarketDataType(3)  # 3 = Delayed (15-min delayed for free live testing), 1 = Real-time
            except Exception:
                pass

            # 1. Level 2 Market Depth (numRows=100)
            try:
                self.depth_ticker = self.ib.reqMktDepth(self.contract, numRows=100, isSmartDepth=True)
                self.depth_ticker.updateEvent += self._on_depth_update
            except Exception as e:
                print(f"L2 depth subscription error: {e}")

            # 2. Time & Sales / Tick stream & stats (233: RTVolume, 236: Shortable)
            self.mkt_ticker = self.ib.reqMktData(self.contract, '233', False, False)
            self.mkt_ticker.updateEvent += self._on_mkt_data_update

            # 3. Tick by tick if supported
            try:
                self.ib.reqTickByTickData(self.contract, 'AllLast', 0, False)
                self.ib.pendingTickersEvent += self._on_tick_by_tick
            except Exception:
                pass

        except Exception as e:
            self.last_error = f"Subscription error for {symbol}: {e}"
            if hasattr(self, 'broadcast_callback') and self.broadcast_callback:
                await self.broadcast_callback({"type": "ERROR", "data": {"message": self.last_error}})
            
        # Start background task to fetch historical bars
        self.hist_fetch_task = asyncio.create_task(self._fetch_historical_data_with_retry(symbol))

    async def refetch_historical_data(self, symbol: str):
        if self.hist_fetch_task and not self.hist_fetch_task.done():
            self.hist_fetch_task.cancel()
        
        self.quant_engine.state.ema_9 = None
        self.quant_engine.state.ema_21 = None
        self.quant_engine.state.ema_200 = None
        self.quant_engine.state.vwap = None
        
        await self.broadcast_callback({"type": "INTELLIGENCE_UPDATE", "data": self.quant_engine.get_payload()})
        
        self.hist_fetch_task = asyncio.create_task(self._fetch_historical_data_with_retry(symbol))

    async def refetch_mtf_data(self, symbol: str):
        if self.hist_fetch_task and not self.hist_fetch_task.done():
            self.hist_fetch_task.cancel()
        
        self.quant_engine.state.mtf_levels = []
        
        await self.broadcast_callback({"type": "INTELLIGENCE_UPDATE", "data": self.quant_engine.get_payload()})
        
        self.hist_fetch_task = asyncio.create_task(self._fetch_historical_data_with_retry(symbol))

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
            try:
                self.scanner_ib = IB()
                await self.scanner_ib.connectAsync(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.clientId + 10,
                    timeout=5
                )
            except Exception as e:
                print(f"Failed to reconnect scanner: {e}")
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
            
            # Request streaming market data with 165 (Misc Stats for Avg Volume).
            tickers = [scanner_ib.reqMktData(c, '165,233', False, False) for c in contracts]
            
            # Wait up to 1.5s for data to populate
            await asyncio.sleep(1.5)
            
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
                
                # Historical Market Data fetch commented out to prevent API pacing / subscription cancellation
                # if not tracker.history:
                #     bars_obj = await self._safe_req_historical_data(
                #         scanner_ib, contract, durationStr='3600 S',
                #         barSizeSetting='1 min', whatToShow='TRADES',
                #         useRTH=False, formatDate=1
                #     )
                #     if bars_obj:
                #         new_bars = [{"date": str(b.date), "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume} for b in bars_obj]
                #     
                # if new_bars and new_bars[-1]['volume'] <= 10_000 and not tracker.history:
                #      continue
                     
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

    async def _fetch_historical_data_with_retry(self, symbol: str):
        """Fetches 1D 1-min bars for EMA/VWAP calculation."""
        if not self.ib or not self.ib.isConnected() or not self.contract:
            return
            
        try:
            bars_1m = await self._safe_req_historical_data(
                self.ib, self.contract, durationStr='3 D',
                barSizeSetting='1 min', whatToShow='TRADES', useRTH=False, formatDate=1,
                keepUpToDate=True
            )
            
            bars_4h = await self._safe_req_historical_data(
                self.ib, self.contract, durationStr='1 M',
                barSizeSetting='4 hours', whatToShow='TRADES', useRTH=False, formatDate=1,
                keepUpToDate=False
            )
            
            if bars_1m and bars_4h:
                def convert(bars_list):
                    return [{"date": str(b.date), "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume} for b in bars_list]
                    
                self.quant_engine.process_historical_data('1m', convert(bars_1m), recalc_snr=True)
                self.quant_engine.process_historical_data('4h', convert(bars_4h), recalc_snr=True)
                
                # Attach live update event for 1m bars
                self.live_bars_1m = bars_1m
                self.live_bars_1m.updateEvent += self._on_1m_bar_update
                
                await self.broadcast_callback({"type": "INTELLIGENCE_UPDATE", "data": self.quant_engine.get_payload()})
            else:
                print(f"[HIST] Historical data fetch for {symbol} returned empty list.")
                
        except Exception as e:
            print(f"[HIST] Error fetching historical data for {symbol}: {e}")

    def _on_1m_bar_update(self, bars, hasNewBar: bool):
        """Native IBKR live update event for 1m bars"""
        if getattr(bars, 'contract', None) and bars.contract.symbol != self.active_symbol:
            return
            
        def convert(bars_list):
            return [{"date": str(b.date), "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume} for b in bars_list]
            
        self.quant_engine.process_historical_data('1m', convert(bars), recalc_snr=hasNewBar)
        
        if hasattr(self, 'broadcast_callback') and self.broadcast_callback:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.broadcast_callback({"type": "INTELLIGENCE_UPDATE", "data": self.quant_engine.get_payload()}))
            except Exception as e:
                pass

    def _on_depth_update(self, ticker):
        if not ticker or not ticker.domBids or ticker.contract.symbol != self.active_symbol:
            return

        bids = [
            DepthLevel(
                price=round(row.price, 2),
                size=int(row.size),
                marketMaker=row.marketMaker or random.choice(self.mmids),
                ordersCount=getattr(row, 'orderCount', 1) or 1
            )
            for row in ticker.domBids[:100]
        ]
        asks = [
            DepthLevel(
                price=round(row.price, 2),
                size=int(row.size),
                marketMaker=row.marketMaker or random.choice(self.mmids),
                ordersCount=getattr(row, 'orderCount', 1) or 1
            )
            for row in ticker.domAsks[:100]
        ]

        book = OrderBook(
            symbol=self.active_symbol,
            bids=bids,
            asks=asks,
            lastPrice=round(ticker.marketPrice(), 2) if ticker.marketPrice() else None
        )
        self.current_book[self.active_symbol] = book
        asyncio.create_task(self.broadcast_callback({"type": "L2_UPDATE", "data": book.dict()}))
        
        # Feed intelligence engine
        bids_dict = [{"price": b.price, "size": b.size} for b in bids]
        asks_dict = [{"price": a.price, "size": a.size} for a in asks]
        self.quant_engine.on_l2_update(book.lastPrice or 0.0, bids_dict, asks_dict)
        asyncio.create_task(self.broadcast_callback({"type": "INTELLIGENCE_UPDATE", "data": self.quant_engine.get_payload()}))

        # Last aggregated tick cache for consecutive trade grouping
        self._last_tape_tick: Optional[TapeTick] = None

    async def _emit_or_aggregate_tape_tick(self, new_tick: TapeTick):
        """
        Groups consecutive trades that occur at the exact same price within the same millisecond timestamp
        into a single, combined print showing the total volume.
        Filters out trades smaller than 100 shares.
        """
        if new_tick.size < 100:
            return

        if (
            self._last_tape_tick is not None
            and self._last_tape_tick.symbol == new_tick.symbol
            and self._last_tape_tick.time == new_tick.time
            and self._last_tape_tick.price == new_tick.price
            and self._last_tape_tick.side == new_tick.side
        ):
            # Aggregate volume onto existing tick
            self._last_tape_tick.size += new_tick.size
            self._last_tape_tick.orderCount = (self._last_tape_tick.orderCount or 1) + (new_tick.orderCount or 1)
            self._last_tape_tick.isBlockTrade = self._last_tape_tick.size >= 2000
            self._last_tape_tick.aggregated = True
            
            # Broadcast updated aggregated tick
            await self.broadcast_callback({"type": "TAPE_TICK", "data": self._last_tape_tick.dict()})
            self.quant_engine.on_tape_tick(new_tick.price, new_tick.size, new_tick.side)
            await self.broadcast_callback({"type": "INTELLIGENCE_UPDATE", "data": self.quant_engine.get_payload()})
            return

        # New separate print
        new_tick.isBlockTrade = new_tick.size >= 2000
        self._last_tape_tick = new_tick
        await self.broadcast_callback({"type": "TAPE_TICK", "data": new_tick.dict()})
        self.quant_engine.on_tape_tick(new_tick.price, new_tick.size, new_tick.side)
        await self.broadcast_callback({"type": "INTELLIGENCE_UPDATE", "data": self.quant_engine.get_payload()})

    def _on_mkt_data_update(self, ticker):
        if not ticker or getattr(ticker.contract, 'symbol', None) != self.active_symbol:
            return
        last_price = ticker.last
        if not last_price:
            return

        # Handle NaN size
        raw_size = ticker.lastSize
        if raw_size is None or math.isnan(raw_size):
            size = 100
        else:
            size = int(raw_size)

        # Filter out prints < 100 shares
        if size < 100:
            return

        side = "BUY" if (ticker.ask and last_price >= ticker.ask) else ("SELL" if (ticker.bid and last_price <= ticker.bid) else "MID")

        # Emit tape tick from tick update
        tick = TapeTick(
            symbol=self.active_symbol,
            time=datetime.datetime.now().strftime("%M:%S"),
            price=round(last_price, 2),
            size=size,
            side=side,
            exchange="SMART",
            isBlockTrade=size >= 2000,
            orderCount=1
        )
        asyncio.create_task(self._emit_or_aggregate_tape_tick(tick))

    def _on_tick_by_tick(self, tickers):
        for ticker in tickers:
            if getattr(ticker.contract, 'symbol', None) != self.active_symbol:
                continue
            for t in ticker.tickByTicks:
                raw_size = t.size
                if raw_size is None or math.isnan(raw_size):
                    size = 100
                else:
                    size = int(raw_size)

                # Filter out prints < 100 shares
                if size < 100:
                    continue

                time_str = t.time.strftime("%M:%S") if hasattr(t.time, 'strftime') else datetime.datetime.now().strftime("%M:%S")
                side = "BUY" if t.price >= (ticker.ask or t.price) else ("SELL" if t.price <= (ticker.bid or t.price) else "MID")

                tick = TapeTick(
                    symbol=self.active_symbol,
                    time=time_str,
                    price=round(t.price, 2),
                    size=size,
                    side=side,
                    exchange=getattr(t, 'exchange', 'SMART') or 'SMART',
                    condition=getattr(t, 'specialConditions', '@') or '@',
                    isBlockTrade=size >= 2000,
                    orderCount=1
                )
                asyncio.create_task(self._emit_or_aggregate_tape_tick(tick))


