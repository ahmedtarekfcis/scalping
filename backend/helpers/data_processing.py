import random
from models import DepthLevel, TapeTick
from typing import List, Dict, Optional

def aggregate_dom(dom_list, is_bid: bool, mmids: List[str]) -> List[DepthLevel]:
    """
    Aggregates DOM levels by price.
    """
    aggregated = {}
    for row in dom_list[:100]:
        rounded_price = round(row.price, 2)
        if rounded_price not in aggregated:
            aggregated[rounded_price] = {
                "size": 0,
                "ordersCount": 0,
                "marketMaker": row.marketMaker or random.choice(mmids)
            }
        aggregated[rounded_price]["size"] += int(row.size)
        aggregated[rounded_price]["ordersCount"] += getattr(row, 'orderCount', 1) or 1
        
    result = [
        DepthLevel(
            price=p,
            size=data["size"],
            marketMaker=data["marketMaker"],
            ordersCount=data["ordersCount"]
        )
        for p, data in aggregated.items()
    ]
    result.sort(key=lambda x: x.price, reverse=is_bid)
    return result

def aggregate_tape_tick(last_tick: Optional[TapeTick], new_tick: TapeTick) -> tuple[bool, TapeTick]:
    """
    Aggregates a new tape tick onto the last tick if they match exactly in price, side, time, and symbol.
    Returns (True, aggregated_tick) if aggregated, (False, new_tick) if it's a new print.
    """
    if (
        last_tick is not None
        and last_tick.symbol == new_tick.symbol
        and last_tick.time == new_tick.time
        and last_tick.price == new_tick.price
        and last_tick.side == new_tick.side
    ):
        # Aggregate volume onto existing tick
        last_tick.size += new_tick.size
        last_tick.orderCount = (last_tick.orderCount or 1) + (new_tick.orderCount or 1)
        last_tick.isBlockTrade = last_tick.size >= 2000
        last_tick.aggregated = True
        return True, last_tick

    # New separate print
    new_tick.isBlockTrade = new_tick.size >= 2000
    return False, new_tick

def format_large_number(num) -> str:
    if not num: return "--"
    try:
        n = float(num)
        if n > 1_000_000: return f"{n/1_000_000:.1f}M"
        if n > 1_000: return f"{n/1_000:.1f}K"
        return str(int(n))
    except:
        return "--"
