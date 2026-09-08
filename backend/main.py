import asyncio
import json
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from models import IBKRConnectionConfig, ConnectionStatus
from ib_client import IBKRMarketEngine

app = FastAPI(title="TradeEdge.ai", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.add(connection)
        
        for dead in dead_connections:
            self.active_connections.discard(dead)

manager = ConnectionManager()
engine = IBKRMarketEngine(broadcast_callback=manager.broadcast)


@app.on_event("startup")
async def startup_event():
    await engine.initialize()
    
    # Continuous scanner loop to run in background independently of websocket
    async def continuous_scanner():
        # Small initial delay to let IB connection settle
        await asyncio.sleep(5)
        while True:
            try:
                await engine.scan_market()
            except Exception as e:
                print(f"Error in continuous scanner: {e}")
            await asyncio.sleep(15)
            
    asyncio.create_task(continuous_scanner())


@app.get("/api/status", response_model=ConnectionStatus)
async def get_status():
    return engine.get_status()


@app.post("/api/connect")
async def connect_ibkr(config: IBKRConnectionConfig):
    result = await engine.connect_ibkr(config)
    # Broadcast new connection status
    await manager.broadcast({
        "type": "STATUS_UPDATE",
        "data": engine.get_status().dict()
    })
    return result


@app.post("/api/subscribe/{symbol}")
async def subscribe_symbol(symbol: str):
    await engine.subscribe_symbol(symbol)
    await manager.broadcast({
        "type": "STATUS_UPDATE",
        "data": engine.get_status().dict()
    })
    return {"status": "success", "symbol": symbol.upper()}


@app.websocket("/ws/market-data")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    async def keepalive():
        """Send a ping every 25 seconds to prevent proxy/idle timeouts."""
        while True:
            await asyncio.sleep(25)
            try:
                await websocket.send_text('{"type":"PING"}')
            except Exception:
                break

    ping_task = asyncio.create_task(keepalive())

    try:
        # Send initial status & current book snapshot on connect
        await websocket.send_text(json.dumps({
            "type": "STATUS_UPDATE",
            "data": engine.get_status().dict()
        }))
        if engine.active_symbol in engine.current_book:
            await websocket.send_text(json.dumps({
                "type": "L2_UPDATE",
                "data": engine.current_book[engine.active_symbol].dict()
            }))

        while True:
            raw_data = await websocket.receive_text()
            # Skip keepalive pongs from client
            if raw_data.strip() in ('', '{"type":"PONG"}'):
                continue
            try:
                msg = json.loads(raw_data)
                action = msg.get("action")
                if action == "SUBSCRIBE":
                    symbol = msg.get("symbol", "TSLA")
                    await engine.subscribe_symbol(symbol)
                    await manager.broadcast({
                        "type": "STATUS_UPDATE",
                        "data": engine.get_status().dict()
                    })
                elif action == "CONNECT":
                    cfg_dict = msg.get("config", {})
                    cfg = IBKRConnectionConfig(**cfg_dict)
                    await engine.connect_ibkr(cfg)
                    await manager.broadcast({
                        "type": "STATUS_UPDATE",
                        "data": engine.get_status().dict()
                    })
                elif action == "REFETCH_CRITERIA":
                    symbol = msg.get("symbol", "TSLA")
                    await engine.refetch_historical_data(symbol)
                elif action == "REFETCH_MTF":
                    symbol = msg.get("symbol", "TSLA")
                    await engine.refetch_mtf_data(symbol)
                elif action == "SCAN":
                    asyncio.create_task(engine.scan_market())
                elif action == "SYNC_WEBULL":
                    symbol = msg.get("symbol")
                    if symbol:
                        try:
                            from desktop_sync import sync_all_platforms
                            asyncio.create_task(asyncio.to_thread(sync_all_platforms, symbol))
                        except Exception as e:
                            print(f"Failed to sync webull/cpro: {e}")
                elif action == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG"}))
            except Exception as e:
                # Log but DO NOT disconnect — keep the session alive
                print(f"Error handling WS message (non-fatal): {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket session ended unexpectedly: {e}")
    finally:
        ping_task.cancel()
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
