"""Extractor tests — inject a fake VLM client, no SDK or network needed."""
import types

from src.extractor import Extractor, _clean_json
from src.schema import get_schema


def _client(text):
    msg = types.SimpleNamespace(content=[types.SimpleNamespace(text=text)])
    messages = types.SimpleNamespace(create=lambda **kw: msg)
    return types.SimpleNamespace(messages=messages)


def test_clean_json_strips_fences():
    assert _clean_json('```json\n{"x": 1}\n```') == '{"x": 1}'
    assert _clean_json('here you go: {"x": 1} done') == '{"x": 1}'


def test_extract_parses_fields():
    ex = Extractor(client=_client('{"period": "FY2023", "net_income": 300}'))
    out = ex.extract(b"img", get_schema("income_statement"))
    assert out["parse_ok"] is True
    assert out["fields"]["period"] == "FY2023"
    assert out["fields"]["net_income"] == 300


def test_extract_handles_fenced_output():
    ex = Extractor(client=_client('```json\n{"net_income": 12}\n```'))
    out = ex.extract(b"img", get_schema("income_statement"))
    assert out["parse_ok"] is True
    assert out["fields"]["net_income"] == 12


def test_extract_garbage_is_not_ok():
    ex = Extractor(client=_client("the model rambled with no json"))
    out = ex.extract(b"img", get_schema("income_statement"))
    assert out["parse_ok"] is False
    assert out["fields"] == {}
