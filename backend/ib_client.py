import asyncio
import datetime
import random
import time
from typing import Callable, Dict, List, Optional
import math

try:
    from ib_insync import IB, Stock, util
    util.patchAsyncio()
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False

from models import DepthLevel, OrderBook, TapeTick, IBKRConnectionConfig, ConnectionStatus
from analytics_engine import QuantEngine


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
        self.is_mock = False
        self.active_symbol: Optional[str] = None
        self.last_error = None
        
        # State tracking
        self.current_book: Dict[str, OrderBook] = {}
        self.mock_task: Optional[asyncio.Task] = None
        self.hist_fetch_task: Optional[asyncio.Task] = None
        self.depth_ticker = None
        self.mkt_ticker = None
        self.contract = None

        # Intelligence Engine
        self.quant_engine = QuantEngine()

        # Sample market makers for realistic L2 look
        self.mmids = ["ISLD", "ARCA", "EDGA", "EDGX", "BATS", "NSDQ", "DRCT", "MEMX", "IEX", "NYS"]

    async def initialize(self):
        """Initial start: ready and idle until symbol subscription"""
        if not self.config.useMock and IB_INSYNC_AVAILABLE:
            await self.connect_ibkr(self.config)

    def get_status(self) -> ConnectionStatus:
        return ConnectionStatus(
            connected=self.is_connected or self.is_mock,
            isMock=self.is_mock,
            activeSymbol=self.active_symbol,
            host=self.config.host,
            port=self.config.port,
            clientId=self.config.clientId,
            error=self.last_error
        )

    async def connect_ibkr(self, config: IBKRConnectionConfig):
        self.config = config
        self.last_error = None

        # Stop mock if running
        if self.mock_task and not self.mock_task.done():
            self.mock_task.cancel()
            self.mock_task = None

        if config.useMock or not IB_INSYNC_AVAILABLE:
            self.is_mock = True
            self.is_connected = False
            if self.active_symbol:
                await self.start_mock_engine(self.active_symbol)
            return {"status": "success", "mode": "mock", "message": "Simulator ready"}

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
            self.is_mock = False
            if self.active_symbol:
                await self.subscribe_symbol(self.active_symbol)
            return {"status": "success", "mode": "live", "message": f"Connected to IBKR at {config.host}:{config.port}"}
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            self.is_mock = True
            # Fallback to mock so UI is alive
            if self.active_symbol:
                await self.start_mock_engine(self.active_symbol)
            return {"status": "fallback_to_mock", "mode": "mock", "error": str(e)}

    async def subscribe_symbol(self, symbol: str):
        symbol = symbol.upper().strip()
        self.active_symbol = symbol
        
        # Reset Intelligence Engine
        self.quant_engine.reset(symbol)

        if self.is_mock:
            await self.start_mock_engine(symbol)
            return

        if not self.ib or not self.ib.isConnected():
            await self.start_mock_engine(symbol)
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

    async def _fetch_historical_data_with_retry(self, symbol: str):
        """Fetches 1D 1-min bars for EMA/VWAP calculation with exponential backoff on failure."""
        if not self.ib or not self.ib.isConnected() or not self.contract:
            return
            
        retry_delay = 5
        max_delay = 60
        
        while True:
            try:
                bars_1m = await self.ib.reqHistoricalDataAsync(
                    self.contract, endDateTime='', durationStr='3 D',
                    barSizeSetting='1 min', whatToShow='TRADES', useRTH=False, formatDate=1,
                    keepUpToDate=True
                )
                
                bars_4h = await self.ib.reqHistoricalDataAsync(
                    self.contract, endDateTime='', durationStr='1 M',
                    barSizeSetting='4 hours', whatToShow='TRADES', useRTH=False, formatDate=1
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
                    return  # Success, exit the loop
                else:
                    print(f"Historical data fetch for {symbol} returned empty list. Retrying in {retry_delay}s...")
                    
            except Exception as e:
                print(f"Error fetching historical data for {symbol}: {e}. Retrying in {retry_delay}s...")
                
            await asyncio.sleep(retry_delay)
            retry_delay = min(max_delay, retry_delay * 2)

    def _on_1m_bar_update(self, bars, hasNewBar: bool):
        """Native IBKR live update event for 1m bars"""
        if self.quant_engine.symbol != self.active_symbol:
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

    # -------------------------------------------------------------
    # HIGH-SPEED REALISTIC LEVEL 2 & TIME/SALES SIMULATOR (Mock Mode)
    # -------------------------------------------------------------
    async def start_mock_engine(self, symbol: str):
        if self.mock_task and not self.mock_task.done():
            self.mock_task.cancel()
        
        self.mock_task = asyncio.create_task(self._run_mock_loop(symbol))

    async def _run_mock_loop(self, symbol: str):
        """Generates realistic micro-movements, spoofing, order queue updates and tape prints"""
        # Base prices per popular symbols
        base_prices = {
            "TSLA": 218.50,
            "NVDA": 118.20,
            "AAPL": 224.80,
            "SPY": 560.10,
            "QQQ": 478.40,
            "AMD": 142.30,
            "AMZN": 182.90,
            "MSFT": 415.60
        }
        mid_price = base_prices.get(symbol.upper(), 150.00)
        open_price = mid_price * 0.992
        high_price = mid_price * 1.015
        low_price = mid_price * 0.985
        total_volume = random.randint(12_000_000, 45_000_000)

        # Generate initial 20 L2 levels
        spread = 0.01

        while True:
            try:
                # Random micro-drift in mid price
                drift = random.choice([-0.02, -0.01, -0.01, 0.0, 0.0, 0.01, 0.01, 0.02])
                mid_price = max(1.0, round(mid_price + drift, 2))
                high_price = max(high_price, mid_price)
                low_price = min(low_price, mid_price)

                best_bid = round(mid_price - spread / 2, 2)
                best_ask = round(best_bid + spread, 2)

                bids: List[DepthLevel] = []
                asks: List[DepthLevel] = []

                # Build up to 100 depth levels with realistic tiered order sizes
                for i in range(100):
                    bid_p = round(best_bid - (i * 0.01), 2)
                    ask_p = round(best_ask + (i * 0.01), 2)

                    # Dynamic sizes with occasional large "institutional wall"
                    bid_sz = random.randint(2, 60) * 100
                    if i in [3, 7, 12, 25, 48, 72] and random.random() > 0.4:
                        bid_sz = random.randint(120, 850) * 100  # Big bid wall

                    ask_sz = random.randint(2, 60) * 100
                    if i in [2, 6, 11, 24, 45, 68] and random.random() > 0.4:
                        ask_sz = random.randint(120, 850) * 100  # Big ask wall

                    bids.append(DepthLevel(
                        price=bid_p,
                        size=bid_sz,
                        marketMaker=random.choice(self.mmids),
                        ordersCount=max(1, int(bid_sz / random.randint(100, 300)))
                    ))
                    asks.append(DepthLevel(
                        price=ask_p,
                        size=ask_sz,
                        marketMaker=random.choice(self.mmids),
                        ordersCount=max(1, int(ask_sz / random.randint(100, 300)))
                    ))

                change = round(mid_price - open_price, 2)
                change_pct = round((change / open_price) * 100, 2)

                order_book = OrderBook(
                    symbol=symbol,
                    timestamp=time.time(),
                    bids=bids,
                    asks=asks,
                    lastPrice=mid_price,
                    change=change,
                    changePercent=change_pct,
                    volume=total_volume,
                    high=round(high_price, 2),
                    low=round(low_price, 2),
                    open=round(open_price, 2)
                )

                self.current_book[symbol] = order_book

                # Broadcast L2 Book Snapshot / Delta
                await self.broadcast_callback({
                    "type": "L2_UPDATE",
                    "data": order_book.dict()
                })

                # Generate 1 to 4 fast tape ticks per cycle
                num_ticks = random.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]
                cycle_time_str = datetime.datetime.now().strftime("%M:%S")
                for _ in range(num_ticks):
                    side = random.choices(["BUY", "SELL", "MID"], weights=[48, 46, 6])[0]
                    trade_price = best_ask if side == "BUY" else (best_bid if side == "SELL" else mid_price)
                    # Momentum small-cap trade sizes (all >= 100)
                    trade_size = random.choice([100, 100, 200, 300, 500, 800, 1200, 2200, 3500, 5000])
                    is_block = trade_size >= 2000
                    total_volume += trade_size

                    # Occasionally share identical timestamp to trigger aggregation simulation
                    t_stamp = cycle_time_str if random.random() > 0.4 else datetime.datetime.now().strftime("%M:%S")

                    tick = TapeTick(
                        symbol=symbol,
                        time=t_stamp,
                        timestamp=time.time(),
                        price=trade_price,
                        size=trade_size,
                        side=side,
                        exchange=random.choice(self.mmids),
                        condition="@" if not is_block else "BLK",
                        isBlockTrade=is_block,
                        orderCount=1
                    )

                    await self._emit_or_aggregate_tape_tick(tick)

                # Micro-interval between 60ms to 180ms for ultra responsive momentum feel
                await asyncio.sleep(random.uniform(0.06, 0.16))

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in mock loop: {e}")
                await asyncio.sleep(1)
