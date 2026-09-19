import asyncio
import datetime
import math
from typing import Callable, Dict, Optional

from models import OrderBook, TapeTick, ConnectionStatus, IBKRConnectionConfig
from ibkr_apis.client import IBKRClient
from helpers.data_processing import aggregate_dom, aggregate_tape_tick

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


    def _on_depth_update(self, ticker):
        if not ticker or ticker.contract.symbol != self.active_symbol:
            return

        bids = aggregate_dom(ticker.domBids, True, self.mmids)
        asks = aggregate_dom(ticker.domAsks, False, self.mmids)

        book = OrderBook(
            symbol=self.active_symbol,
            bids=bids,
            asks=asks,
            lastPrice=round(ticker.marketPrice(), 2) if ticker.marketPrice() else None
        )
        self.current_book[self.active_symbol] = book
        asyncio.create_task(self.broadcast_callback({"type": "L2_UPDATE", "data": book.dict()}))
        
        self._last_tape_tick = None

    async def _process_new_tick(self, new_tick: TapeTick):
        if new_tick.size < 100:
            return

        aggregated, current_tick = aggregate_tape_tick(self._last_tape_tick, new_tick)
        if not aggregated:
            self._last_tape_tick = current_tick

        await self.broadcast_callback({"type": "TAPE_TICK", "data": current_tick.dict()})

    def _on_mkt_data_update(self, ticker):
        if not ticker or getattr(ticker.contract, 'symbol', None) != self.active_symbol:
            return
        last_price = ticker.last
        if not last_price:
            return

        raw_size = ticker.lastSize
        size = 100 if raw_size is None or math.isnan(raw_size) else int(raw_size)

        if size < 100:
            return

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
                raw_size = t.size
                size = 100 if raw_size is None or math.isnan(raw_size) else int(raw_size)

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
                asyncio.create_task(self._process_new_tick(tick))
