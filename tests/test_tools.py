from appliance_fixer.case_store import CaseStore
from appliance_fixer.tools import read_and_cache_plate, read_spec_plate, validate_model


class _FakeResp:
    def __init__(self, text): self.text = text


class _FakeModels:
    def __init__(self, text): self._text = text
    def generate_content(self, model, contents): return _FakeResp(self._text)


class FakeClient:
    def __init__(self, text): self.models = _FakeModels(text)


def test_validate_model_malformed():
    assert validate_model("???", "Samsung") is None
    assert validate_model("", None) is None


def test_validate_model_valid_but_wrong():
    assert validate_model("RF99Z9999ZZ", "Samsung") is None


def test_validate_model_exact():
    assert validate_model("RF28R7201", "Samsung") == "RF28R7201"


def test_validate_model_glyph_confusions():
    glyph_input = "RF28R7201".replace("0", "O").replace("1", "I")
    assert "O" in glyph_input
    assert "I" in glyph_input
    assert validate_model(glyph_input, "Samsung") == "RF28R7201"


def test_validate_model_suffix_strip():
    assert validate_model("RF28T5001SR/AA", "Samsung") == "RF28T5001SR"
    assert validate_model("WRFF3336SZ00", "Whirlpool") == "WRFF3336SZ"


def test_read_spec_plate_with_fake_client(tmp_path):
    photo = tmp_path / "plate.jpg"
    photo.write_bytes(b"fake jpeg")
    client = FakeClient('{"brand":"Samsung","model_number":"RF28T5001SR","error_code":null}')

    result = read_spec_plate(photo, client=client)

    assert result == {
        "brand": "Samsung",
        "model_number": "RF28T5001SR",
        "error_code": None,
    }


def test_read_spec_plate_tolerates_junk_response(tmp_path):
    photo = tmp_path / "plate.jpg"
    photo.write_bytes(b"fake jpeg")

    assert read_spec_plate(photo, client=FakeClient("not json")) == {
        "brand": None,
        "model_number": None,
        "error_code": None,
    }


def test_read_spec_plate_parses_markdown_fenced_json(tmp_path):
    photo = tmp_path / "plate.jpg"
    photo.write_bytes(b"fake jpeg")
    client = FakeClient(
        '```json\n{"brand":"Samsung","model_number":"RF28T5001SR","error_code":null}\n```'
    )

    result = read_spec_plate(photo, client=client)

    assert result == {
        "brand": "Samsung",
        "model_number": "RF28T5001SR",
        "error_code": None,
    }


def test_read_and_cache_plate_short_circuits_cached_read(tmp_path):
    photo = tmp_path / "plate.jpg"
    photo.write_bytes(b"fake jpeg")
    store = CaseStore(tmp_path / "cases.db")
    store.new_case("case-1", "user-1", appliance="refrigerator")

    first = read_and_cache_plate(
        "case-1",
        photo,
        store,
        client=FakeClient('{"brand":"Samsung","model_number":"RF28T5001SR","error_code":null}'),
    )
    second = read_and_cache_plate(
        "case-1",
        photo,
        store,
        client=FakeClient('{"brand":"Whirlpool","model_number":"WRFF3336SZ","error_code":"PF"}'),
    )

    assert second == first
    assert first["matched_model"] == "RF28T5001SR"
    case = store.load_case("case-1")
    assert case["data"]["cache"]["plate_read"] == first
    assert case["data"]["cache"]["plate_read"]["matched_model"] == "RF28T5001SR"
