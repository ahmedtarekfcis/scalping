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
        asyncio.create_task(self._handle_scanner_update(list(data[:10])))

    async def _handle_scanner_update(self, scan_results):
        enriched = []
        now = time.time()
        contracts_to_fetch = []
        
        # 1. Build immediate payload and identify what needs fetching
        for item in scan_results:
            contract = item.contractDetails.contract
            symbol = contract.symbol
            
            base_item = {
                "symbol": symbol,
                "rank": item.rank,
                "changePercent": "--"
            }
            
            needs_fetch = symbol not in self.cached_hist or (now - self.last_fetch_time.get(symbol, 0) > 60)
            
            if needs_fetch:
                base_item["isFetchingHist"] = True
                if not self.is_fetching.get(symbol, False):
                    self.is_fetching[symbol] = True
                    contracts_to_fetch.append(contract)
            else:
                base_item["isFetchingHist"] = False
                base_item.update(self.cached_hist.get(symbol, {}))
                
            enriched.append(base_item)
            
        # 2. Broadcast immediately so the UI shows the loaders instantly
        if self.broadcast_callback:
            await self.broadcast_callback({
                "type": "SCANNER_UPDATE",
                "data": enriched
            })
            
        # 3. Fetch missing data sequentially in the background, updating the UI as they complete
        if contracts_to_fetch:
            for contract in contracts_to_fetch:
                symbol = contract.symbol
                try:
                    bars = await self.scanner_ib.reqHistoricalDataAsync(
                        contract, endDateTime='', durationStr='600 S',
                        barSizeSetting='1 min', whatToShow='TRADES',
                        useRTH=False, formatDate=1, keepUpToDate=False
                    )
                    if bars:
                        latest = bars[-1]
                        
                        # Use helper for calculations
                        move5m, vol1m, vol_accel = calculate_historical_metrics(bars)
                        
                        self.cached_hist[symbol] = {
                            "open": round(latest.open, 2),
                            "high": round(latest.high, 2),
                            "low": round(latest.low, 2),
                            "close": round(latest.close, 2),
                            "volume": latest.volume,
                            "vwap": round(getattr(latest, 'average', getattr(latest, 'wap', 0)), 2),
                            "move5m": move5m,
                            "vol1m": vol1m,
                            "volAccel": vol_accel
                        }
                    self.last_fetch_time[symbol] = time.time()
                    await asyncio.sleep(0.1) # Pacing
                except Exception as e:
                    print(f"Scanner hist error for {symbol}: {e}")
                finally:
                    self.is_fetching[symbol] = False
                    
            # 4. Broadcast the final state once all fetching for this batch is done
            final_enriched = []
            for item in scan_results:
                sym = item.contractDetails.contract.symbol
                b_item = {
                    "symbol": sym,
                    "rank": item.rank,
                    "changePercent": "--",
                    "isFetchingHist": self.is_fetching.get(sym, False)
                }
                b_item.update(self.cached_hist.get(sym, {}))
                final_enriched.append(b_item)
                
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
                scanCode='HOT_BY_VOLUME',
                abovePrice=1.5
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
