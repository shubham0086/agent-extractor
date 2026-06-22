"""Validator tests — required fields, type coercion, and financial coherence."""
from src.validator import Validator, _to_number
from src.schema import Schema, Field, get_schema


def _income(**overrides):
    base = {
        "period": "FY2023",
        "total_revenue": 1000,
        "cost_of_revenue": 400,
        "gross_profit": 600,
        "operating_expenses": 200,
        "operating_income": 400,
        "net_income": 300,
        "currency": "USD",
    }
    base.update(overrides)
    return base


def test_parens_are_negative():
    assert _to_number("(100)") == -100
    assert _to_number("$1,250.50") == 1250.50
    assert _to_number("n/a") is None


def test_coherent_income_statement_validates():
    report = Validator().validate(_income(), get_schema("income_statement"))
    assert report["ok"] is True
    assert any("gross_profit" in c for c in report["checked"])


def test_broken_identity_is_an_error():
    report = Validator().validate(_income(gross_profit=999), get_schema("income_statement"))
    assert report["ok"] is False
    assert any("gross_profit" in e for e in report["errors"])


def test_missing_required_is_an_error():
    report = Validator().validate(_income(net_income=None), get_schema("income_statement"))
    assert report["ok"] is False
    assert any("net_income" in e for e in report["errors"])


def test_non_numeric_currency_is_an_error():
    report = Validator().validate(_income(total_revenue="lots"), get_schema("income_statement"))
    assert report["ok"] is False


def test_schema_totals_sum_check():
    schema = Schema(
        "seg", [Field("a", "number"), Field("b", "number"), Field("total", "number")],
        totals={"total": ["a", "b"]},
    )
    assert Validator().validate({"a": 3, "b": 4, "total": 7}, schema)["ok"] is True
    bad = Validator().validate({"a": 3, "b": 4, "total": 99}, schema)
    assert bad["ok"] is False
