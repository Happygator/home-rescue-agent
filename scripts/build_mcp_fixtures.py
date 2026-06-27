"""Regenerate the mock-OEM MCP fixtures from the curated appliance modules.

Usage: python -m scripts.build_mcp_fixtures   (or)   python scripts/build_mcp_fixtures.py
"""
from home_rescue.mcp_server import fixtures

if __name__ == "__main__":
    written = fixtures.write()
    print("Wrote MCP fixtures for:", ", ".join(written) if written else "(none)")
