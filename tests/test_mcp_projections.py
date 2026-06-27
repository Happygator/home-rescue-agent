from home_rescue.mcp_server import projections as p


def test_get_manual_projection_dishwasher():
    m = p.get_manual("LDFC2423V")
    assert m["found"] is True
    assert m["brand"] == "LG"
    assert m["appliance"] == "dishwasher"
    assert m["manual_url"].startswith("https://")
    assert m["warranty_status"] != "unknown"


def test_get_manual_projection_unknown():
    assert p.get_manual("NOPE-000")["found"] is False


def test_workflow_safe_code_no_dispatch():
    w = p.get_pre_service_workflow("LDFC2423V", "", "OE")
    assert w["brand"] == "LG"
    assert w["error_code"] == "OE"
    assert w["dispatch_recommended"] is False
    assert w["steps"] and w["steps"][0]["safe"] is True


def test_workflow_unsafe_code_dispatches():
    w = p.get_pre_service_workflow("LDFC2423V", "", "HE")
    assert w["dispatch_recommended"] is True
    assert any(not s["safe"] for s in w["steps"])


def test_workflow_symptom_path_is_curated():
    w = p.get_pre_service_workflow("RF28T5001SR", "fresh food warm but freezer still cold", "")
    assert w["brand"] == "SAMSUNG"
    assert w["steps"]
    assert all(s["source"] == "curated" for s in w["steps"])


def test_create_service_request_is_deterministic():
    a = p.create_service_request("LDFC2423V", "leaking under the door", "AE")
    b = p.create_service_request("LDFC2423V", "leaking under the door", "AE")
    assert a["ticket_id"] == b["ticket_id"]
    assert a["ticket_id"].startswith("SR-")
    assert a["status"] == "created"
    assert a["sent"] is False


def test_escalation_steps_samsung_fridge_is_oem():
    e = p.get_escalation_steps("RF28T5001SR")
    assert e["brand"] == "SAMSUNG"
    assert e["appliance"] == "refrigerator"
    assert e["source"] == "oem"
    kinds = [s["kind"] for s in e["steps"]]
    assert kinds == ["check", "check", "action", "wait"]
    assert e["steps"][-1]["wait_hours"] == 2
    assert "call support" in e["steps"][-1]["instruction"].lower()


def test_escalation_steps_dishwasher_falls_back_to_default():
    e = p.get_escalation_steps("LDFC2423V")
    assert e["appliance"] == "dishwasher"
    assert e["source"] == "default"
    assert e["steps"] == p.DEFAULT_ESCALATION_STEPS


def test_escalation_steps_unknown_model_is_default():
    e = p.get_escalation_steps("NOPE-000")
    assert e["brand"] is None
    assert e["source"] == "default"
    assert len(e["steps"]) == 4
