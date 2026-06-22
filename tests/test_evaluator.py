"""Evaluator tests — field accuracy, precision, recall vs a gold record."""
from src.evaluator import Evaluator


GOLD = {"currency": "USD", "total_revenue": 1000, "net_income": 300}


def test_perfect_extraction_scores_one():
    got = {"currency": "usd", "total_revenue": 1000.001, "net_income": 300}
    m = Evaluator().evaluate(got, GOLD)
    assert m["field_accuracy"] == 1.0
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0


def test_missing_field_lowers_recall():
    got = {"currency": "USD", "total_revenue": 1000}  # net_income omitted
    m = Evaluator().evaluate(got, GOLD)
    assert m["recall"] < 1.0
    assert m["correct"] == 2


def test_wrong_value_counts_against_precision():
    got = {"currency": "USD", "total_revenue": 9999, "net_income": 300}
    m = Evaluator().evaluate(got, GOLD)
    assert m["correct"] == 2
    assert m["precision"] < 1.0  # 3 filled, 2 correct


def test_only_gold_fields_are_scored():
    got = {"currency": "USD", "total_revenue": 1000, "net_income": 300, "extra": "ignored"}
    m = Evaluator().evaluate(got, GOLD)
    assert m["total"] == 3
