import asyncio
from typing import Optional, List
import math
import datetime
import logging

# Suppress INFO logs from ib_insync to keep console clean
logging.getLogger('ib_insync').setLevel(logging.WARNING)

try:
    from ib_insync import IB, Stock, util
    import ib_insync.wrapper
    from ib_insync.objects import DOMLevel
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
        # Ignore informational connection OK codes
        if errorCode in [2104, 2106, 2108, 2158]:
            return
            
        error_lower = errorString.lower()
        if errorCode == 162 and ("scanner subscription cancelled" in error_lower or "historical data query cancelled" in error_lower or "historical market data service error message:api historical data query cancelled" in error_lower):
            return
            
        msg = f"[TWS] Error {errorCode}, reqId {reqId}: {errorString}"
        if contract:
            msg += f", contract: {contract}"
        print(msg)
        
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

from models import IBKRConnectionConfig

class IBKRClient:
    """
    Pure IBKR API wrapper. Handles connection and raw requests/subscriptions.
    """
    def __init__(self):
        self.ib: Optional[IB] = None
        self.config = IBKRConnectionConfig()
        self.is_connected = False
        self.last_error = None
        self._hist_semaphore = asyncio.Semaphore(1)

    async def connect(self, config: IBKRConnectionConfig) -> bool:
        self.config = config
        self.last_error = None

        if not IB_INSYNC_AVAILABLE:
            self.is_connected = False
            self.last_error = "IB_INSYNC is not available"
            return False

        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()

            self.ib = IB()
            await self.ib.connectAsync(
                host=config.host,
                port=config.port,
                clientId=config.clientId,
                timeout=5
            )
            
            self.is_connected = True
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            return False
            
    def disconnect(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        self.is_connected = False

    async def qualify_contract(self, symbol: str) -> Optional[Stock]:
        if not self.ib or not self.ib.isConnected():
            return None
        contract = Stock(symbol, 'SMART', 'USD')
        try:
            await self.ib.qualifyContractsAsync(contract)
            return contract
        except Exception as e:
            self.last_error = f"Qualify error for {symbol}: {e}"
            return None

    def req_market_data_type(self, type_id: int):
        if self.ib and self.ib.isConnected():
            self.ib.reqMarketDataType(type_id)

    def req_mkt_depth(self, contract: Stock, num_rows: int = 100, is_smart: bool = True):
        if self.ib and self.ib.isConnected():
            return self.ib.reqMktDepth(contract, numRows=num_rows, isSmartDepth=is_smart)
        return None

    def cancel_mkt_depth(self, contract: Stock):
        if self.ib and self.ib.isConnected():
            self.ib.cancelMktDepth(contract)

    def req_mkt_data(self, contract: Stock, generic_tick_list: str = '233'):
        if self.ib and self.ib.isConnected():
            return self.ib.reqMktData(contract, generic_tick_list, False, False)
        return None

    def cancel_mkt_data(self, contract: Stock):
        if self.ib and self.ib.isConnected():
            self.ib.cancelMktData(contract)

    def req_tick_by_tick_data(self, contract: Stock, tick_type: str = 'AllLast'):
        if self.ib and self.ib.isConnected():
            self.ib.reqTickByTickData(contract, tick_type, 0, False)

    async def req_historical_data_safe(self, contract, durationStr, barSizeSetting, whatToShow, useRTH, formatDate, keepUpToDate=False):
        """
        Paced and centrally controlled historical data request.
        """
        max_retries = 3
        retry_delay = 5.0

        for attempt in range(1, max_retries + 1):
            try:
                async with self._hist_semaphore:
                    await asyncio.sleep(0.5)
                    bars = await self.ib.reqHistoricalDataAsync(
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
                    return []
                    
                if is_pacing_error:
                    await asyncio.sleep(retry_delay * 2)
                    retry_delay *= 2
                else:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5

        return []

    def cancel_historical_data(self, bars):
        if self.ib and self.ib.isConnected() and bars:
            try:
                self.ib.cancelHistoricalData(bars)
            except Exception:
                pass

    async def req_scanner_data(self, subscription):
        if self.ib and self.ib.isConnected():
            return await self.ib.reqScannerDataAsync(subscription)
        return []
