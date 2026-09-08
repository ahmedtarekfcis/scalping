from typing import List, Optional, Literal
from pydantic import BaseModel, Field
import time

class DepthLevel(BaseModel):
    price: float
    size: int
    marketMaker: Optional[str] = "ISLD"
    ordersCount: Optional[int] = 1

class OrderBook(BaseModel):
    symbol: str
    timestamp: float = Field(default_factory=lambda: time.time())
    bids: List[DepthLevel] = []  # Sorted high to low
    asks: List[DepthLevel] = []  # Sorted low to high
    lastPrice: Optional[float] = None
    change: Optional[float] = None
    changePercent: Optional[float] = None
    volume: Optional[int] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None

class TapeTick(BaseModel):
    symbol: str
    time: str
    timestamp: float = Field(default_factory=lambda: time.time())
    price: float
    size: int
    side: Literal["BUY", "SELL", "MID"] = "MID"  # BUY (at/above ask), SELL (at/below bid), MID
    exchange: Optional[str] = "NASDAQ"
    condition: Optional[str] = "@"
    isBlockTrade: bool = False
    orderCount: Optional[int] = 1
    aggregated: Optional[bool] = False

class IBKRConnectionConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 4002  # 7497: TWS Paper, 7496: TWS Live, 4002: Gateway Paper, 4001: Gateway Live
    clientId: int = 1

class ConnectionStatus(BaseModel):
    connected: bool
    activeSymbol: Optional[str] = None
    host: str
    port: int
    clientId: int
    error: Optional[str] = None
