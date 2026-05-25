import websockets
import asyncio

async def server(websocket):

    async for message in websocket:

        print(message)

start_server = websockets.serve(
    server,
    "localhost",
    8765
)

asyncio.get_event_loop().run_until_complete(
    start_server
)

asyncio.get_event_loop().run_forever()
