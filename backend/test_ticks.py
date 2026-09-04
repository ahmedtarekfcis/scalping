import asyncio
from ib_insync import IB, Stock, util

async def test_ticks():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 4002, clientId=99)
        print("Connected to IBKR on 4002")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    contract = Stock('TSLA', 'SMART', 'USD')
    await ib.qualifyContractsAsync(contract)
    print(f"Qualified: {contract}")

    ticker = ib.reqMktData(contract, '165,233', False, False)
    print("Requested market data...")
    
    for i in range(10):
        await asyncio.sleep(0.5)
        print(f"\n--- Second {i*0.5} ---")
        print(f"avVolume: {ticker.avVolume}")
        print(f"fundamentalRatios: {ticker.fundamentalRatios}")
        print(f"volume: {ticker.volume}")
        print(f"last: {ticker.last}, close: {ticker.close}")
        if ticker.avVolume and ticker.fundamentalRatios:
            print("Received both! Exiting early.")
            break

    ib.disconnect()

util.run(test_ticks())
