import asyncio
from ib_insync import IB, util

async def test_scanner():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 4002, clientId=98)
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    xml = await ib.reqScannerParametersAsync()
    with open('scanner_params.xml', 'w') as f:
        f.write(xml)
    print("Saved scanner parameters to scanner_params.xml")
    ib.disconnect()

util.run(test_scanner())
