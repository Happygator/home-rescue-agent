"""Standalone mock OEM MCP server (DESIGN_COMPLETE.md section 16).

Exposes the projection layer as MCP tools over stdio so the ADK agent can call them via an
MCPToolset. Requires the `mcp` SDK (pip install mcp). Importing this module is safe without mcp;
the dependency is only needed to actually build/run the server.
"""
from __future__ import annotations

from home_rescue.mcp_server import projections


def build_server():
    """Construct the FastMCP server exposing the 3 OEM tools. Requires the mcp SDK."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "The mock OEM MCP server requires the 'mcp' SDK. Install it with: pip install mcp"
        ) from e

    server = FastMCP("home-rescue-mock-oem")

    @server.tool()
    def get_manual(model: str) -> dict:
        """Return the manufacturer manual reference (product line, manual_url, warranty, recalls)."""
        return projections.get_manual(model)

    @server.tool()
    def get_pre_service_workflow(model: str, symptom: str = "", error_code: str = "") -> dict:
        """Return ordered OEM pre-service steps and a terminal dispatch_recommended flag."""
        return projections.get_pre_service_workflow(model, symptom, error_code)

    @server.tool()
    def get_escalation_steps(model: str, symptom: str = "", error_code: str = "") -> dict:
        """Return the ordered escalation-prep steps the customer should complete (brand-specific or default)."""
        return projections.get_escalation_steps(model, symptom, error_code)

    @server.tool()
    def create_service_request(model: str, symptom: str = "", error_code: str = "", notes: str = "") -> dict:
        """Create a (mock) warranty-aware dispatch ticket; returns a stable ticket id."""
        return projections.create_service_request(model, symptom, error_code, notes=notes)

    return server


def main():
    build_server().run()


if __name__ == "__main__":
    main()
