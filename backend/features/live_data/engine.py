import asyncio
import datetime
import math
import time
from typing import Callable, Dict, Optional

from models import OrderBook, TapeTick, ConnectionStatus, IBKRConnectionConfig
from ibkr_apis.client import IBKRClient
from helpers.data_processing import aggregate_dom

# Minimum gap between two L2 snapshots sent to the frontend (seconds).
# IBKR can push hundreds of depth events per second; a human can't read more
# than a handful of refreshes, so we coalesce them (~7 updates/s) to keep the
# ladder calm while staying real-time.
L2_MIN_INTERVAL = 0.15

# Tape prints must be strictly larger than this many shares (i.e. > 1 lot).
MIN_TAPE_SIZE = 100

# If tick-by-tick data arrived within this many seconds we trust it exclusively
# and ignore the (duplicate) last-trade field of the market-data ticker.
TBT_FRESH_SECONDS = 5.0

class LiveDataEngine:
    """
    Orchestrates real-time market data connection to IBKR via IBKRClient.
    Feeds data to the QuantEngine and broadcasts to connected clients.
    """
    def __init__(self, broadcast_callback: Callable):
        self.broadcast_callback = broadcast_callback
        self.client = IBKRClient()
        self.active_symbol: Optional[str] = None
        
        self.current_book: Dict[str, OrderBook] = {}
        self.hist_fetch_task: Optional[asyncio.Task] = None
        self.depth_ticker = None
        self.mkt_ticker = None
        self.contract = None
        self._last_tape_tick: Optional[TapeTick] = None

        # L2 throttling state
        self._last_l2_broadcast: float = 0.0
        self._l2_flush_handle = None
        self._last_l2_signature = None

        # Tape de-duplication state
        self._last_tbt_ts: float = 0.0
        self._last_trade_key = None

        self.mmids = ["ISLD", "ARCA", "EDGA", "EDGX", "BATS", "NSDQ", "DRCT", "MEMX", "IEX", "NYS"]

    async def initialize(self):
        # Could auto-connect here if needed
        pass

    def get_status(self) -> ConnectionStatus:
        return ConnectionStatus(
            connected=self.client.is_connected,
            activeSymbol=self.active_symbol,
            host=self.client.config.host,
            port=self.client.config.port,
            clientId=self.client.config.clientId,
            error=self.client.last_error
        )

    async def connect_ibkr(self, config: IBKRConnectionConfig):
        success = await self.client.connect(config)
        if success:
            if self.active_symbol:
                await self.subscribe_symbol(self.active_symbol)
            return {"status": "success", "mode": "live", "message": f"Connected to IBKR at {config.host}:{config.port}"}
        return {"status": "error", "mode": "none", "error": self.client.last_error}

    async def subscribe_l2(self, symbol: str):
        if not self.client.is_connected or not self.contract:
            return

        try:
            if getattr(self, 'depth_ticker', None):
                self.depth_ticker.updateEvent -= self._on_depth_update
                self.client.cancel_mkt_depth(self.depth_ticker.contract)
        except Exception:
            pass

        self.depth_ticker = self.client.req_mkt_depth(self.contract)
        if self.depth_ticker:
            self.depth_ticker.updateEvent += self._on_depth_update

    async def subscribe_tape(self, symbol: str):
        if not self.client.is_connected or not self.contract:
            return

        try:
            if getattr(self, 'mkt_ticker', None):
                self.mkt_ticker.updateEvent -= self._on_mkt_data_update
                self.client.cancel_mkt_data(self.mkt_ticker.contract)
                self.client.cancel_tick_by_tick_data(self.mkt_ticker.contract)
            if self.client.ib:
                self.client.ib.pendingTickersEvent -= self._on_tick_by_tick
        except Exception:
            pass

        self.mkt_ticker = self.client.req_mkt_data(self.contract)
        if self.mkt_ticker:
            self.mkt_ticker.updateEvent += self._on_mkt_data_update

        self.client.req_tick_by_tick_data(self.contract)
        if self.client.ib:
            self.client.ib.pendingTickersEvent += self._on_tick_by_tick

    async def subscribe_symbol(self, symbol: str):
        print(f"\n[LIVE DATA] Subscribing to symbol: {symbol}")
        symbol = symbol.upper().strip()

        if not self.client.is_connected:
            print("[LIVE DATA] Error: IBKR Client is not connected! Cannot subscribe.")
            return

        try:
            # Cancel depth
            if getattr(self, 'depth_ticker', None):
                self.depth_ticker.updateEvent -= self._on_depth_update
                self.client.cancel_mkt_depth(self.depth_ticker.contract)
                self.depth_ticker = None
            
            # Cancel tape
            if getattr(self, 'mkt_ticker', None):
                self.mkt_ticker.updateEvent -= self._on_mkt_data_update
                self.client.cancel_mkt_data(self.mkt_ticker.contract)
                self.client.cancel_tick_by_tick_data(self.mkt_ticker.contract)
                self.mkt_ticker = None

            if self.client.ib:
                self.client.ib.pendingTickersEvent -= self._on_tick_by_tick

            # Cancel historical
            if getattr(self, 'live_bars_1m', None):
                self.client.cancel_historical_data(self.live_bars_1m)
                self.live_bars_1m = None

            if self.hist_fetch_task and not self.hist_fetch_task.done():
                self.hist_fetch_task.cancel()
        except Exception as e:
            print(f"[LIVE DATA] Error clearing previous subscriptions: {e}")

        self.active_symbol = symbol

        # Reset throttling / de-dup state for the new symbol
        if self._l2_flush_handle:
            self._l2_flush_handle.cancel()
            self._l2_flush_handle = None
        self._last_l2_broadcast = 0.0
        self._last_l2_signature = None
        self._last_tbt_ts = 0.0
        self._last_trade_key = None

        print(f"[LIVE DATA] Qualifying contract for {symbol}...")
        self.contract = await self.client.qualify_contract(symbol)
        if not self.contract:
            print(f"[LIVE DATA] Failed to qualify contract for {symbol}.")
            if self.broadcast_callback:
                await self.broadcast_callback({"type": "ERROR", "data": {"message": self.client.last_error}})
            return

        print(f"[LIVE DATA] Contract qualified! Requesting market data and depth...")
        self.client.req_market_data_type(3)
        await self.subscribe_l2(symbol)
        await self.subscribe_tape(symbol)


    @staticmethod
    def _valid_price(value) -> Optional[float]:
        """Return a rounded price, or None for missing / NaN / non-positive values."""
        try:
            if value is None or math.isnan(value) or value <= 0:
                return None
            return round(value, 2)
        except (TypeError, ValueError):
            return None

    def _on_depth_update(self, ticker):
        # NOTE: ib_insync shares a single Ticker per contract, so this handler is
        # also fired by quote / last-trade events. We therefore coalesce events
        # and only broadcast when the visible book really changed.
        if not ticker or ticker.contract.symbol != self.active_symbol:
            return

        elapsed = time.monotonic() - self._last_l2_broadcast
        if elapsed >= L2_MIN_INTERVAL:
            self._flush_l2()
        elif self._l2_flush_handle is None:
            loop = asyncio.get_event_loop()
            self._l2_flush_handle = loop.call_later(L2_MIN_INTERVAL - elapsed, self._flush_l2)

    def _flush_l2(self):
        self._l2_flush_handle = None
        ticker = self.depth_ticker
        if not ticker or ticker.contract.symbol != self.active_symbol:
            return

        bids = aggregate_dom(ticker.domBids, True, self.mmids)
        asks = aggregate_dom(ticker.domAsks, False, self.mmids)

        # Skip the broadcast when nothing visible changed (e.g. trigger was a tape/quote event)
        signature = (
            tuple((l.price, l.size) for l in bids),
            tuple((l.price, l.size) for l in asks),
        )
        if signature == self._last_l2_signature:
            return
        self._last_l2_signature = signature
        self._last_l2_broadcast = time.monotonic()

        book = OrderBook(
            symbol=self.active_symbol,
            bids=bids,
            asks=asks,
            lastPrice=self._valid_price(ticker.marketPrice())
        )
        self.current_book[self.active_symbol] = book
        asyncio.create_task(self.broadcast_callback({"type": "L2_UPDATE", "data": book.dict()}))

    async def _process_new_tick(self, new_tick: TapeTick):
        # Only prints strictly larger than 1 lot (100 shares) are shown.
        if new_tick.size <= MIN_TAPE_SIZE:
            return

        # Every print is sent as-is. (Previously same-price prints were merged and the
        # cumulative size re-broadcast as a new row, which double counted volume.)
        new_tick.isBlockTrade = new_tick.size >= 2000
        await self.broadcast_callback({"type": "TAPE_TICK", "data": new_tick.dict()})

    def _on_mkt_data_update(self, ticker):
        # Fallback tape source (e.g. delayed data without tick-by-tick). The shared
        # Ticker fires this on EVERY depth/quote/trade event, so we must only emit
        # when a genuinely new trade arrived and tick-by-tick isn't already feeding us.
        if not ticker or getattr(ticker.contract, 'symbol', None) != self.active_symbol:
            return
        if time.monotonic() - self._last_tbt_ts < TBT_FRESH_SECONDS:
            return

        last_price = ticker.last
        if not last_price or math.isnan(last_price):
            return

        raw_size = ticker.lastSize
        if raw_size is None or math.isnan(raw_size):
            return
        size = int(raw_size)

        if size <= MIN_TAPE_SIZE:
            return

        volume = ticker.volume
        volume = None if volume is None or math.isnan(volume) else volume
        trade_key = (last_price, size, volume)
        if trade_key == self._last_trade_key:
            return
        self._last_trade_key = trade_key

        side = "BUY" if (ticker.ask and last_price >= ticker.ask) else ("SELL" if (ticker.bid and last_price <= ticker.bid) else "MID")

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
        asyncio.create_task(self._process_new_tick(tick))

    def _on_tick_by_tick(self, tickers):
        for ticker in tickers:
            if getattr(ticker.contract, 'symbol', None) != self.active_symbol:
                continue
            for t in ticker.tickByTicks:
                self._last_tbt_ts = time.monotonic()
                raw_size = t.size
                if raw_size is None or math.isnan(raw_size):
                    continue
                size = int(raw_size)

                if size <= MIN_TAPE_SIZE:
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
                asyncio.create_task(self._process_new_tick(tick))
