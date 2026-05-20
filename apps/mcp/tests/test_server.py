import asyncio

from who2be_mcp.server import mcp


def test_server_exposes_ping_tool() -> None:
    tools = asyncio.run(mcp.list_tools())
    assert "ping" in {tool.name for tool in tools}
