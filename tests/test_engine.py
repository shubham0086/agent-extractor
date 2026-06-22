"""Engine tests — end to end with a fake VLM client and a stubbed renderer."""
import json
import types

from src.engine import ExtractorEngine


_COHERENT = json.dumps({
    "period": "FY2023", "total_revenue": 1000, "cost_of_revenue": 400,
    "gross_profit": 600, "operating_expenses": 200, "operating_income": 400,
    "net_income": 300, "currency": "USD",
})


def _client(text):
    msg = types.SimpleNamespace(content=[types.SimpleNamespace(text=text)])
    return types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **kw: msg))


def _stub_renderer():
    page = types.SimpleNamespace(image_bytes=b"img", number=1)
    return types.SimpleNamespace(
        render=lambda path, pages=None: [page],
        page_count=lambda path: 1,
    )


def test_extract_page_validates_coherent_doc():
    engine = ExtractorEngine(client=_client(_COHERENT))
    engine.renderer = _stub_renderer()

    out = engine.extract_page("any.pdf", 1, "income_statement")
    assert out["parse_ok"] is True
    assert out["fields"]["net_income"] == 300
    assert out["validation"]["ok"] is True


def test_extract_page_with_gold_adds_eval():
    engine = ExtractorEngine(client=_client(_COHERENT))
    engine.renderer = _stub_renderer()

    out = engine.extract_page("any.pdf", 1, "income_statement",
                              gold={"net_income": 300, "currency": "USD"})
    assert out["eval"]["field_accuracy"] == 1.0


def test_extract_document_aggregates_ok():
    engine = ExtractorEngine(client=_client(_COHERENT))
    engine.renderer = _stub_renderer()

    out = engine.extract_document("any.pdf", "income_statement")
    assert out["ok"] is True
    assert len(out["pages"]) == 1
