import asyncio
import time
from typing import Callable, Optional

try:
    from ib_insync import IB, ScannerSubscription
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False

from models import IBKRConnectionConfig
from helpers.data_processing import calculate_historical_metrics

class IBKRScannerEngine:
    """
    New simplified Scanner Engine using reqScannerSubscription.
    """
    def __init__(self, broadcast_callback: Callable):
        self.broadcast_callback = broadcast_callback
        self.config = IBKRConnectionConfig()
        self.scanner_ib: Optional[IB] = None
        self.scanner_data = None
        self.is_running = False
        self.last_fetch_time = {}
        self.cached_hist = {}
        self.is_fetching = {}
        self.subscribed_symbols = {}

    async def connect(self, config: IBKRConnectionConfig):
        self.config = config
        if not IB_INSYNC_AVAILABLE:
            return False
            
        try:
            if self.scanner_ib and self.scanner_ib.isConnected():
                self.scanner_ib.disconnect()

            self.scanner_ib = IB()
            # Use clientId + 10 to keep it separate from the live data connection
            await self.scanner_ib.connectAsync(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.clientId + 10,
                timeout=5
            )
            print("Scanner IB connected successfully.")
            return True
        except Exception as e:
            print(f"Failed to reconnect scanner: {e}")
            return False

    def on_scanner_data(self, data):
        """Callback for live scanner updates"""
        # Take top 30 instead of 10 so we have enough buffer to filter out dead stocks
        asyncio.create_task(self._handle_scanner_update(list(data[:30])))

    async def _handle_scanner_update(self, scan_results):
        now = time.time()
        contracts_to_fetch = []
        
        current_symbols = {item.contractDetails.contract.symbol for item in scan_results}
        
        # Unsubscribe from symbols that dropped off the scanner list
        for sym in list(self.subscribed_symbols.keys()):
            if sym not in current_symbols:
                contract = self.subscribed_symbols[sym]
                try:
                    self.scanner_ib.cancelMktData(contract)
                except Exception:
                    pass
                del self.subscribed_symbols[sym]
        
        # 1. Identify what needs fetching
        for item in scan_results:
            contract = item.contractDetails.contract
            symbol = contract.symbol
            
            # Subscribe to market data for daily vol, high, prev close
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols[symbol] = contract
                try:
                    self.scanner_ib.reqMktData(contract, '', False, False)
                except Exception as e:
                    pass

            needs_fetch = symbol not in self.cached_hist or (now - self.last_fetch_time.get(symbol, 0) > 60)
            
            if needs_fetch and not self.is_fetching.get(symbol, False):
                self.is_fetching[symbol] = True
                contracts_to_fetch.append(contract)
            
        # 2. Fetch missing data sequentially in the background
        if contracts_to_fetch:
            for contract in contracts_to_fetch:
                symbol = contract.symbol
                try:
                    bars = await self.scanner_ib.reqHistoricalDataAsync(
                        contract, endDateTime='', durationStr='900 S',
                        barSizeSetting='1 min', whatToShow='TRADES',
                        useRTH=False, formatDate=1, keepUpToDate=False
                    )
                    if bars:
                        latest = bars[-1]
                        
                        # Use helper for calculations
                        move5m, move15m, mom1m, vol1m, vol_accel, ema = calculate_historical_metrics(bars)
                        
                        self.cached_hist[symbol] = {
                            "price": round(latest.close, 2),
                            "vwap": round(getattr(latest, 'average', getattr(latest, 'wap', 0)), 2),
                            "move5m": move5m,
                            "move15m": move15m,
                            "mom1m": mom1m,
                            "vol1m": vol1m,
                            "volAccel": vol_accel,
                            "ema": ema
                        }
                    self.last_fetch_time[symbol] = time.time()
                    await asyncio.sleep(0.1) # Pacing
                except Exception as e:
                    print(f"Scanner hist error for {symbol}: {e}")
                finally:
                    self.is_fetching[symbol] = False
                    
        # 3. Build final list, filtering out illiquid stocks, then limit to top 10
        final_enriched = []
        for item in scan_results:
            sym = item.contractDetails.contract.symbol
            hist_data = self.cached_hist.get(sym, {})
            
            # Live Market Data overrides
            ticker = self.scanner_ib.ticker(item.contractDetails.contract)
            gap_pct = "--"
            hod_room = "--"
            daily_vol = "--"
            
            if ticker:
                if ticker.volume and ticker.volume > 0:
                    daily_vol = ticker.volume
                
                # Gap % = (Open - PrevClose) / PrevClose
                if ticker.close and ticker.close > 0 and ticker.open and ticker.open > 0:
                    gap_pct = round(((ticker.open - ticker.close) / ticker.close) * 100, 2)
                    
                # HOD Room = (High - Price) / Price
                price = ticker.marketPrice()
                if not price or price != price: # NaN check
                    price = hist_data.get("price", 0)
                    
                if ticker.high and ticker.high > 0 and price > 0:
                    hod_room = round(((ticker.high - price) / price) * 100, 2)
            
            # Filter condition: must have a valid move5m (meaning it has recent active candles)
            if hist_data.get("move5m") != "--":
                score = 0
                m5 = hist_data.get("move5m", 0)
                m1 = hist_data.get("mom1m", 0)
                va = hist_data.get("volAccel", 0)
                
                if isinstance(m5, (int, float)) and m5 > 0:
                    score += min(35, int(m5 * 10))
                if isinstance(m1, (int, float)) and m1 > 0:
                    score += min(35, int(m1 * 20))
                if isinstance(va, (int, float)) and va > 1:
                    score += min(30, int((va - 1) * 10))
                score = min(100, max(0, score))

                b_item = {
                    "symbol": sym,
                    "rank": item.rank,
                    "score": score,
                    "isFetchingHist": self.is_fetching.get(sym, False),
                    "daily_vol": daily_vol,
                    "gap_pct": gap_pct,
                    "hod_room": hod_room
                }
                b_item.update(hist_data)
                final_enriched.append(b_item)
                
            if len(final_enriched) >= 10:
                break
                
        # 4. Broadcast the final state
        if self.broadcast_callback:
            await self.broadcast_callback({
                "type": "SCANNER_UPDATE",
                "data": final_enriched
            })

    async def scan_market(self):
        """Starts the live scanner subscription if not already running."""
        if not IB_INSYNC_AVAILABLE:
            print("ib_insync is not available")
            return
            
        if self.is_running:
            return # Already subscribed and running

        if not getattr(self, 'scanner_ib', None) or not self.scanner_ib.isConnected():
            connected = await self.connect(self.config)
            if not connected:
                return

        try:
            # 1. Define the Scanner Subscription Parameters
            sub = ScannerSubscription(
                instrument='STK',
                locationCode='STK.US.MAJOR',
                scanCode='TOP_PERC_GAIN',
                abovePrice=1.5,
                belowPrice=17.0
            )
            
            # print("\n" + "="*50)
            # print(f"[{time.strftime('%X')}] Sending Live Scanner Subscription: {sub.scanCode}...")
            
            # 2. Subscribe to live scanner data
            self.scanner_data = self.scanner_ib.reqScannerSubscription(sub)
            self.scanner_data.updateEvent += self.on_scanner_data
            
            self.is_running = True
            
        except Exception as e:
            print(f"Scanner error: {e}")
            self.is_running = False
