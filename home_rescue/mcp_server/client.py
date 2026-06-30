"""Async MCP client helper: call the in-process mock OEM MCP server over streamable HTTP.

Used by the agent's lookup_fixes tool so the authoritative pre-service workflow crosses the MCP
transport (rung 1) instead of calling the projection module in-process. Connects per call to the
loopback URL of the server mounted on the FastAPI backend; any failure raises so the caller can
degrade to the curated table.
"""
from __future__ import annotations

import json

from home_rescue.mcp_server.toolset import mcp_url


async def call_oem_tool(tool_name: str, arguments: dict) -> dict:
    """Connect to the mounted MCP server, call `tool_name`, and return its dict result.

    Raises on connection/transport/parse errors. FastMCP returns the dict as JSON text content
    (structuredContent is unset for plain dict returns), so parse content[0].text; the
    structuredContent branch is a forward-compatible fallback.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(mcp_url()) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
    if getattr(result, "isError", False):
        raise RuntimeError(f"MCP tool {tool_name} returned an error")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    if result.content and getattr(result.content[0], "text", None):
        return json.loads(result.content[0].text)
    raise RuntimeError(f"MCP tool {tool_name} returned no usable content")
