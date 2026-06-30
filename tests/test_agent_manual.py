import asyncio

from home_rescue.agent import get_manual, lookup_fixes, root_agent


def _lookup(*args, **kwargs):
    return asyncio.run(lookup_fixes(*args, **kwargs))


def test_get_manual_tool_registered():
    names = [getattr(t, "__name__", str(t)) for t in root_agent.tools]
    assert "get_manual" in names


def test_get_manual_wrapper_returns_record():
    result = get_manual("dishwasher", "LG", "LDFC2423V")
    assert result["found"] is True
    assert result["manual"]["manual_url"].startswith("https://")


def test_get_manual_wrapper_not_found():
    assert get_manual("dishwasher", "LG", "NOPE") == {"found": False}


def test_lookup_fixes_returns_fixes_and_manual():
    result = _lookup("dishwasher", "LG", "LDFC2423V", "it will not drain", "OE")
    assert result["via"] == "curated"  # MCP off by default
    assert result["fixes"] and result["fixes"][0]["source"] == "error_code"
    assert result["fixes"][0]["citation"] and "lg.com" in result["fixes"][0]["citation"]
    assert result["manual"] is not None
    assert "lg.com" in result["manual"]["manual_url"]


def test_lookup_fixes_manual_none_for_uncurated_model():
    result = _lookup("refrigerator", "Samsung", "RF28R7201", "warm fridge", "")
    assert "fixes" in result
    assert result["manual"] is None


def test_lookup_fixes_uses_oem_workflow_when_enabled(monkeypatch):
    # With MCP on, lookup_fixes routes the pre-service workflow through the MCP client. Stub that
    # client with the projection result (the same data the mounted server would return) so the unit
    # test exercises the routing/mapping without a live HTTP server.
    monkeypatch.setenv("HOME_RESCUE_MCP", "1")
    from home_rescue.mcp_server import projections

    async def fake_call_oem_tool(tool_name, arguments):
        assert tool_name == "get_pre_service_workflow"
        return projections.get_pre_service_workflow(
            arguments["model"], arguments.get("symptom", ""), arguments.get("error_code", "")
        )

    monkeypatch.setattr("home_rescue.agent.call_oem_tool", fake_call_oem_tool)
    result = _lookup("dishwasher", "LG", "LDFC2423V", "it will not drain", "OE")
    assert result["via"] == "oem_workflow"
    assert result["fixes"][0]["source"] == "error_code"
    assert result["fixes"][0]["citation"] and "lg.com" in result["fixes"][0]["citation"]
    assert result["manual"] is not None
