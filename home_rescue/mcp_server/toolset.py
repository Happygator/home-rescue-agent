"""Optional ADK MCPToolset wiring for the mock OEM MCP server (gated, OFF by default).

Returns a toolset ONLY when HOME_RESCUE_MCP is truthy AND the mcp SDK + ADK MCP support are
importable; otherwise returns None and the agent runs on the in-process curated tools (the design
section 11 degrade-to-curated fallback). Any wiring error degrades to None rather than breaking the
agent.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root, so the spawned `python -m home_rescue.mcp_server.server` resolves the package
# regardless of the agent's working directory.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])


def mcp_enabled():
    """True when the gated MCP integration is switched on via HOME_RESCUE_MCP."""
    return os.environ.get("HOME_RESCUE_MCP", "").strip().lower() in ("1", "true", "yes", "on")


def _enabled():
    return mcp_enabled()


def maybe_mcp_toolset():
    """Return an MCPToolset connected to the mock OEM server over stdio, or None if disabled/unavailable."""
    if not _enabled():
        return None
    try:
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
        from mcp import StdioServerParameters
    except ModuleNotFoundError:
        return None
    try:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "home_rescue.mcp_server.server"],
            cwd=_REPO_ROOT,
        )
        return MCPToolset(connection_params=StdioConnectionParams(server_params=server_params))
    except Exception:
        return None
