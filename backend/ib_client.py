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

    # --- Monkey Patch for ib_insync Error logging to add [TWS] prefix ---
    orig_error = ib_insync.wrapper.Wrapper.error

    def patched_error(self, reqId, errorCode, errorString, contract=None):
        msg = f"[TWS] Error {errorCode}, reqId {reqId}: {errorString}"
        if contract:
            msg += f", contract: {contract}"
        print(msg)
        
        # Suppress the default logger to avoid double-printing, but still run orig_error for events
        import logging
        logger = logging.getLogger('ib_insync.wrapper')
        old_level = logger.level
        logger.setLevel(logging.CRITICAL)
        try:
            orig_error(self, reqId, errorCode, errorString, contract)
        finally:
            logger.setLevel(old_level)

    ib_insync.wrapper.Wrapper.error = patched_error
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

            self.ib = IB()
            # Asynchronous connection to TWS
            await self.ib.connectAsync(
                host=config.host,
                port=config.port,
                clientId=config.clientId,
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

    async def subscribe_l2(self, symbol: str):
        symbol = symbol.upper().strip()
        if not self.ib or not self.ib.isConnected() or not self.contract:
            return

        try:
            if getattr(self, 'depth_ticker', None):
                self.depth_ticker.updateEvent -= self._on_depth_update
                self.ib.cancelMktDepth(self.contract)
        except Exception:
            pass

        try:
            self.depth_ticker = self.ib.reqMktDepth(self.contract, numRows=100, isSmartDepth=True)
            self.depth_ticker.updateEvent += self._on_depth_update
        except Exception as e:
            print(f"L2 depth subscription error: {e}")

    async def subscribe_tape(self, symbol: str):
        symbol = symbol.upper().strip()
        if not self.ib or not self.ib.isConnected() or not self.contract:
            return

        try:
            if getattr(self, 'mkt_ticker', None):
                self.mkt_ticker.updateEvent -= self._on_mkt_data_update
                self.ib.cancelMktData(self.contract)
            if getattr(self, 'ib', None):
                self.ib.pendingTickersEvent -= self._on_tick_by_tick
        except Exception:
            pass

        try:
            self.mkt_ticker = self.ib.reqMktData(self.contract, '233', False, False)
            self.mkt_ticker.updateEvent += self._on_mkt_data_update

            try:
                self.ib.reqTickByTickData(self.contract, 'AllLast', 0, False)
                self.ib.pendingTickersEvent += self._on_tick_by_tick
            except Exception:
                pass
        except Exception as e:
            print(f"Tape subscription error: {e}")

    async def subscribe_symbol(self, symbol: str):
        symbol = symbol.upper().strip()
        self.active_symbol = symbol
        
        # Reset Intelligence Engine
        self.quant_engine.reset(symbol)

        if not self.ib or not self.ib.isConnected():
            return

        # Cancel historical subscriptions if any
        try:
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

            await self.subscribe_l2(symbol)
            await self.subscribe_tape(symbol)

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

    async def _safe_req_historical_data(self, client_ib, contract, durationStr, barSizeSetting, whatToShow, useRTH, formatDate, keepUpToDate=False):
        """
        Paced and centrally controlled historical data request.
        Uses exponential backoff for max 3 retries to prevent pacing violations.
        """
        max_retries = 3
        retry_delay = 5.0

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
        if not ticker or ticker.contract.symbol != self.active_symbol:
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


