"""ADK MCPToolset wiring + in-process mount for the mock OEM MCP server (gated, OFF by default).

Gated behind HOME_RESCUE_MCP. When on (rung 1) the server is mounted in-process on the FastAPI
backend and the agent connects to it over streamable HTTP at the loopback URL. Set
HOME_RESCUE_MCP_TRANSPORT=stdio to use the legacy co-located stdio subprocess instead. Any wiring
error degrades to None / curated rather than breaking the agent (design section 11).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root, so a spawned `python -m home_rescue.mcp_server.server` resolves the package
# regardless of the agent's working directory (stdio transport only).
_REPO_ROOT = str(Path(__file__).resolve().parents[2])


def mcp_enabled():
    """True when the gated MCP integration is switched on via HOME_RESCUE_MCP."""
    return os.environ.get("HOME_RESCUE_MCP", "").strip().lower() in ("1", "true", "yes", "on")


def _enabled():
    return mcp_enabled()


def mcp_transport():
    """Selected transport: 'http' (default, in-process mounted server) or 'stdio' (subprocess)."""
    return os.environ.get("HOME_RESCUE_MCP_TRANSPORT", "http").strip().lower()


def mcp_url():
    """Loopback URL of the in-process mounted MCP server.

    Matches the backend's bind port: Cloud Run / the Dockerfile serve on $PORT (default 8000, the
    same default the local `__main__` uvicorn run uses). Override wholesale with HOME_RESCUE_MCP_URL.
    """
    return os.environ.get("HOME_RESCUE_MCP_URL") or (
        f"http://127.0.0.1:{os.environ.get('PORT', '8000')}/mcp"
    )


def build_mounted_mcp_app():
    """Return the FastMCP streamable-HTTP ASGI app to mount on the FastAPI backend, or None.

    Served at path "/" so the backend can mount it under the "/mcp" route; returns None if the mcp
    SDK is unavailable or the server cannot be built (the backend then simply skips the mount).
    """
    try:
        from home_rescue.mcp_server.server import build_server

        return build_server(streamable_http_path="/").streamable_http_app()
    except Exception:
        return None


def maybe_mcp_toolset():
    """Return an MCPToolset connected to the mock OEM server, or None if disabled/unavailable.

    Default transport is streamable HTTP to the in-process mounted server; HOME_RESCUE_MCP_TRANSPORT
    =stdio falls back to spawning the server as a co-located subprocess.
    """
    if not _enabled():
        return None
    try:
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StdioConnectionParams,
            StreamableHTTPConnectionParams,
        )
    except ModuleNotFoundError:
        return None
    try:
        if mcp_transport() == "stdio":
            from mcp import StdioServerParameters

            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "home_rescue.mcp_server.server"],
                cwd=_REPO_ROOT,
            )
            return MCPToolset(connection_params=StdioConnectionParams(server_params=server_params))
        return MCPToolset(connection_params=StreamableHTTPConnectionParams(url=mcp_url()))
    except Exception:
        return None
