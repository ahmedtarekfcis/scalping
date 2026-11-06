from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any, Union
from .storage import journal_engine

router = APIRouter(prefix="/api/journal", tags=["Journal"])


@router.get("")
async def get_all_journal_trades():
    """
    Read all journal trades directly from data/journal_trades.json.
    """
    try:
        trades = journal_engine.read_trades()
        info = journal_engine.get_file_info()
        return {
            "status": "success",
            "filePath": info["filePath"],
            "fileName": info["fileName"],
            "count": len(trades),
            "lastModified": info["lastModified"],
            "trades": trades,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read journal file: {e}")


@router.get("/info")
async def get_journal_file_info():
    """
    Get metadata regarding the journal trades JSON file.
    """
    try:
        return {
            "status": "success",
            "info": journal_engine.get_file_info(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("")
async def sync_journal_trades(payload: Union[Dict[str, Any], List[Dict[str, Any]]] = Body(...)):
    """
    Overwrite / synchronize all trades in data/journal_trades.json atomically.
    Accepts either {"trades": [...]} or a direct list of trades [...].
    """
    try:
        if isinstance(payload, dict):
            trades = payload.get("trades", [])
        elif isinstance(payload, list):
            trades = payload
        else:
            raise HTTPException(status_code=400, detail="Invalid payload, expected array or {trades: [...]}")

        success = journal_engine.write_trades(trades)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to write trades to JSON file.")

        info = journal_engine.get_file_info()
        return {
            "status": "success",
            "count": len(trades),
            "filePath": info["filePath"],
            "lastModified": info["lastModified"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving trades to file: {e}")


@router.post("")
async def upsert_journal_trade(trade: Dict[str, Any] = Body(...)):
    """
    Add or update a single trade in data/journal_trades.json.
    """
    try:
        if not trade or "id" not in trade:
            raise HTTPException(status_code=400, detail="Trade record must include an 'id'")

        saved = journal_engine.upsert_trade(trade)
        return {
            "status": "success",
            "trade": saved,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upsert trade: {e}")


@router.put("/{trade_id}")
async def update_journal_trade(trade_id: str, trade: Dict[str, Any] = Body(...)):
    """
    Update a specific trade in data/journal_trades.json.
    """
    try:
        trade["id"] = trade_id
        saved = journal_engine.upsert_trade(trade)
        return {
            "status": "success",
            "trade": saved,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update trade: {e}")


@router.delete("/{trade_id}")
async def delete_journal_trade(trade_id: str):
    """
    Delete a specific trade from data/journal_trades.json by its id.
    """
    try:
        success = journal_engine.delete_trade(trade_id)
        return {
            "status": "success",
            "deletedId": trade_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete trade: {e}")


@router.delete("")
async def clear_all_journal_trades():
    """
    Clear all trades from data/journal_trades.json (creates an archive copy first).
    """
    try:
        journal_engine.clear_all()
        return {
            "status": "success",
            "message": "All journal trades cleared and backed up.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear trades: {e}")

