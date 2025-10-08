import asyncio
from fastmcp import Client

client = Client("https://apim-mcp-09871436.azure-api.net/fgs")

async def call_tool(name: str):
    async with client:
        result = await client.call_tool("greet", {"name": name})
        print(result)
        result = await client.call_tool("me")
        print(result)

asyncio.run(call_tool("Ford"))