import json

from home_rescue.mcp_server import fixtures


def test_fixtures_present_and_match_live_projection():
    built = fixtures.build()
    assert built  # at least one curated model projects to a fixture
    for model, payload in built.items():
        path = fixtures.FIXTURE_DIR / f"{model}.json"
        assert path.exists(), f"missing fixture {path}; run scripts/build_mcp_fixtures.py"
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == payload, f"fixture drift for {model}; run scripts/build_mcp_fixtures.py"
